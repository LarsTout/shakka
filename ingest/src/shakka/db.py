"""Thin client for the Supabase REST API (PostgREST). The only module that talks to the database."""

from collections.abc import Mapping
from typing import Final

PAGE_SIZE: Final = 1000
BATCH_SIZE: Final = 500

# Primary key per table, in key order. Used for default ordering, for counting rows on
# update/delete, and by FakeSupabase. Later WPs add their tables here (marine_hours, ...).
TABLE_KEYS: Final[Mapping[str, tuple[str, ...]]] = {
    "spots": ("id",),
    "forecast_hours": ("spot_id", "model", "valid_at"),
    "tide_extremes": ("station", "at"),
    "evaluations": ("spot_id", "valid_at"),
    "profiles": ("user_id",),
    "favorites": ("user_id", "spot_id"),
    "alert_rules": ("user_id", "spot_id"),
    "alert_state": ("id",),
    "api_usage": ("day", "source"),
    "ingest_runs": ("id",),
}
