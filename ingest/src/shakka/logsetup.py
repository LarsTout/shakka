"""Logging to stdout without secrets, and GitHub Actions annotations.

The Actions logs of this public repository are public: log lines carry counts and statuses
only, and every formatted line is scrubbed of known secrets as a safety net.
"""

import logging
import sys
import time
from collections.abc import Iterable
from typing import Final, Literal, TextIO

from shakka.config import Settings

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_DATEFMT: Final = "%Y-%m-%dT%H:%M:%SZ"
QUIET_LOGGERS: Final = ("httpx", "httpcore", "urllib3")
MIN_SECRET_LENGTH: Final = 8
REDACTED: Final = "***"


def redact(text: str, secrets: Iterable[str]) -> str:
    """Replace every secret of at least MIN_SECRET_LENGTH characters by '***'."""
    for secret in secrets:
        if len(secret) >= MIN_SECRET_LENGTH:
            text = text.replace(secret, REDACTED)
    return text


def secret_values(settings: Settings) -> tuple[str, ...]:
    values = [settings.supabase_secret_key.get_secret_value()]
    if settings.vapid_private_key is not None:
        values.append(settings.vapid_private_key.get_secret_value())
    if settings.vapid_subject is not None and settings.vapid_subject.strip():
        values.append(settings.vapid_subject.strip())  # an e-mail address: personal data
    return tuple(values)


class RedactingFormatter(logging.Formatter):
    converter = time.gmtime

    def __init__(self, fmt: str, datefmt: str, *, secrets: Iterable[str] = ()) -> None:
        super().__init__(fmt, datefmt)
        self._secrets = tuple(secrets)

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self._secrets)


def configure_logging(
    *, stream: TextIO | None = None, secrets: Iterable[str] = ()
) -> logging.Handler:
    """One stdout handler with redaction; httpx, httpcore and urllib3 on WARNING (full URLs)."""
    root = logging.getLogger()
    for old in [h for h in root.handlers if getattr(h, "_shakka_handler", False)]:
        root.removeHandler(old)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, LOG_DATEFMT, secrets=secrets))
    handler._shakka_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    return handler


def escape_command_data(text: str) -> str:
    """Escape '%' (GitHub decodes %25) and flatten CR/LF so an annotation stays one line."""
    return text.replace("%", "%25").replace("\r", " ").replace("\n", " ")


def github_annotation(level: Literal["warning", "error"], message: str) -> str:
    return f"::{level}::{escape_command_data(message)}"
