"""Shared Open-Meteo request helper: GET with retries. Messages never contain the URL."""

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any, Final

import httpx

RETRY_ATTEMPTS: Final = 3
RETRY_BASE_DELAY_S: Final = 1.0  # delay before attempt n (n >= 2): base * 2 ** (n - 2)
RETRY_MAX_DELAY_S: Final = 30.0  # cap for Retry-After
MAX_REASON_CHARS: Final = 200

logger = logging.getLogger("shakka.openmeteo")


class OpenMeteoRequestError(Exception):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _reason(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return ""
    if isinstance(data, dict) and isinstance(data.get("reason"), str):
        return data["reason"][:MAX_REASON_CHARS]
    return ""


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After", "").strip()
    if raw.isdigit():
        return min(max(float(int(raw)), 1.0), RETRY_MAX_DELAY_S)
    return None


def request_json(
    http: httpx.Client,
    url: str,
    params: Mapping[str, str],
    *,
    attempts: int = RETRY_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET url with params and return the parsed JSON.
    Retries on 429, 5xx and httpx.HTTPError; other statuses and invalid JSON fail at once.
    Raises OpenMeteoRequestError. Messages never contain the URL."""
    failure = "no attempt made"
    for attempt in range(1, attempts + 1):
        delay = base_delay * 2 ** (attempt - 1)
        try:
            response = http.get(url, params=dict(params))
        except httpx.HTTPError as exc:
            failure = type(exc).__name__
        else:
            status = response.status_code
            if 200 <= status < 300:
                try:
                    return response.json()
                except ValueError:
                    raise OpenMeteoRequestError("invalid JSON response", status=status) from None
            if status != 429 and status < 500:
                reason = _reason(response)
                message = f"HTTP {status}: {reason}" if reason else f"HTTP {status}"
                raise OpenMeteoRequestError(message, status=status)
            failure = f"HTTP {status}"
            if status == 429:
                retry_after = _retry_after(response)
                if retry_after is not None:
                    delay = retry_after
        if attempt < attempts:
            logger.warning(
                "open-meteo request attempt %d/%d failed: %s; retrying in %.1fs",
                attempt,
                attempts,
                failure,
                delay,
            )
            sleep(delay)
    raise OpenMeteoRequestError(f"failed after {attempts} attempts: {failure}")
