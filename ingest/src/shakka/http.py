"""The single place where httpx clients are created."""

import importlib.metadata
import math
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
