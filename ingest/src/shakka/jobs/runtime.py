"""Seams for the CLI runners: tests replace these functions (never imported by name)."""

from datetime import UTC, datetime
from typing import Final

import httpx

from shakka.config import Settings
from shakka.db import SupabaseRest
from shakka.http import make_client

HTTP_TIMEOUT_S: Final = 30.0


def open_db(settings: Settings) -> SupabaseRest:
    """Open the Supabase REST client; the caller closes it."""
    return SupabaseRest.from_settings(settings)


def open_http() -> httpx.Client:
    """Open the shared HTTP client for the hourly run; the caller closes it."""
    return make_client(timeout=HTTP_TIMEOUT_S)


def utcnow() -> datetime:
    """The current time, timezone-aware (UTC). The only clock read of the job layer."""
    return datetime.now(UTC)
