"""The single place where httpx clients are created."""

import importlib.metadata
import math
import time
from collections.abc import Callable
from typing import Final

import httpx


def _version() -> str:
    try:
        return importlib.metadata.version("shakka")
    except importlib.metadata.PackageNotFoundError:
        return "0+unknown"


USER_AGENT: Final[str] = f"shakka-ingest/{_version()} (+https://github.com/LarsTout/shakka)"


def make_client(*, timeout: float = 30.0) -> httpx.Client:
    """Return an httpx.Client with an explicit timeout and the Shakka User-Agent."""
    if not (math.isfinite(timeout) and timeout > 0):
        raise ValueError("timeout must be a positive, finite number")
    return httpx.Client(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
    )


RETRY_MAX_DELAY_S: Final = 30.0
_sleep: Callable[[float], None] = time.sleep  # module seam; looked up at call time


class TransientError(Exception):
    """A failure worth another attempt. `retry_after` (s) overrides the backoff when set."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def is_transient(exc: BaseException) -> bool:
    return isinstance(exc, TransientError | httpx.TransportError)


def with_retries[T](
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff: float = 1.0,
    retry_if: Callable[[BaseException], bool] = is_transient,
    sleep: Callable[[float], None] | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    """Call fn up to `attempts` times; wait backoff * 2 ** (n - 2) before attempt n.
    The last exception is re-raised unchanged. Only Exception subclasses are caught."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if not (math.isfinite(backoff) and backoff >= 0):
        raise ValueError("backoff must be a non-negative, finite number")
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts or not retry_if(exc):
                raise
            failure = exc
        if isinstance(failure, TransientError) and failure.retry_after is not None:
            delay = min(max(failure.retry_after, 0.0), RETRY_MAX_DELAY_S)
        else:
            delay = backoff * 2 ** (attempt - 1)
        if on_retry is not None:
            on_retry(attempt, failure, delay)
        (sleep or _sleep)(delay)
    raise AssertionError("unreachable")
