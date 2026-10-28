"""`shakka doctor`: check configuration and Supabase REST connectivity.

Prints, per optional variable, only whether it is set. Never outputs variable values, the
Supabase URL, response bodies or exception messages (only exception class names).
"""

from collections.abc import Callable
from typing import Final

import httpx
from pydantic import SecretStr, ValidationError

from shakka.config import OPTIONAL_ENV_VARS, REQUIRED_ENV_VARS, URL_ERROR, get_settings
from shakka.http import make_client

DOCTOR_TIMEOUT_S: Final[float] = 10.0


def _status_line(code: int) -> tuple[bool, str]:
    if 200 <= code < 300:
        return True, f"ok      Supabase REST API reachable (HTTP {code})"
    if code in (401, 403):
        return False, (
            f"error   Supabase REST API rejected the key (HTTP {code}); "
            "SUPABASE_SECRET_KEY must be a secret key (sb_secret_...)"
        )
    if code == 404:
        return False, "error   Supabase REST API returned HTTP 404; check SUPABASE_URL"
    if 300 <= code < 400:
        return False, f"error   Supabase REST API redirected (HTTP {code}); check SUPABASE_URL"
    return False, f"error   Supabase REST API returned HTTP {code}"


def _key_usable(value: str) -> bool:
    """False if the key cannot be sent as an HTTP header value (non-ASCII, whitespace, control)."""
    return value.isascii() and not any(c.isspace() or not c.isprintable() for c in value)


def _is_set(value: object) -> bool:
    if value is None:
        return False
    raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    return bool(raw.strip())


def run_doctor(*, echo: Callable[[str], None]) -> int:
    """Check configuration and Supabase REST connectivity. Returns the exit code (0 or 1)."""
    failed = False
    try:
        settings = get_settings()
    except ValidationError as exc:
        failed = True
        errors: dict[str, str] = {}
        for err in exc.errors(include_input=False, include_url=False, include_context=False):
            name = str(err["loc"][0]).upper() if err["loc"] else "SETTINGS"
            if err["type"] == "missing":
                errors[name] = f"missing {name}"
            elif name == "SUPABASE_URL":
                errors[name] = f"invalid {name}: {URL_ERROR}"
            else:
                errors[name] = f"invalid {name}"
        for name in REQUIRED_ENV_VARS:
            echo(errors.pop(name, f"ok      {name}"))
        for line in errors.values():
            echo(line)
        echo("skip    Supabase REST check (configuration incomplete)")
        echo("doctor: failed")
        return 1
    except Exception as exc:
        echo(f"error   could not read settings ({type(exc).__name__})")
        echo("doctor: failed")
        return 1

    secret = settings.supabase_secret_key.get_secret_value()
    key_ok = _key_usable(secret)
    echo("ok      SUPABASE_URL")
    if key_ok:
        echo("ok      SUPABASE_SECRET_KEY")
    else:
        failed = True
        echo("invalid SUPABASE_SECRET_KEY: contains non-ASCII, whitespace or control characters")
    publishable = settings.supabase_publishable_key
    if publishable:
        echo("ok      SUPABASE_PUBLISHABLE_KEY")
    else:
        echo("unset   SUPABASE_PUBLISHABLE_KEY (optional)")
    for name in OPTIONAL_ENV_VARS:
        state = "set    " if _is_set(getattr(settings, name.lower(), None)) else "unset  "
        echo(f"{state} {name} (optional)")
    if key_ok and not secret.startswith("sb_secret_"):
        echo(
            "warn    SUPABASE_SECRET_KEY does not start with sb_secret_ "
            "(legacy keys stop working end of 2026)"
        )
    if publishable and not publishable.startswith("sb_publishable_"):
        echo("warn    SUPABASE_PUBLISHABLE_KEY does not start with sb_publishable_")

    if not key_ok:
        echo("skip    Supabase REST check (configuration invalid)")
        echo("doctor: failed")
        return 1

    try:
        with make_client(timeout=DOCTOR_TIMEOUT_S) as client:
            response = client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={"apikey": secret},
            )
        ok, line = _status_line(response.status_code)
    except httpx.TimeoutException:
        ok, line = False, "error   Supabase REST API timed out after 10s"
    except httpx.HTTPError as exc:
        ok, line = False, f"error   Supabase REST API unreachable ({type(exc).__name__})"
    except Exception as exc:  # last resort, e.g. httpx.InvalidURL is not an HTTPError
        ok, line = False, f"error   Supabase REST check failed ({type(exc).__name__})"
    echo(line)
    failed = failed or not ok
    echo("doctor: failed" if failed else "doctor: ok")
    return 1 if failed else 0
