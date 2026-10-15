"""Seams for the CLI runners: tests replace these two functions (never imported by name)."""

from datetime import UTC, datetime

from shakka.config import Settings
from shakka.db import SupabaseRest


def open_db(settings: Settings) -> SupabaseRest:
    """Open the Supabase REST client; the caller closes it."""
    return SupabaseRest.from_settings(settings)


def utcnow() -> datetime:
    """The current time, timezone-aware (UTC). The only clock read of the job layer."""
    return datetime.now(UTC)
