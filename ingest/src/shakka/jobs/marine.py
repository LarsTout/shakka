"""Marine ingest job: spots -> Open-Meteo Marine (budget guarded) -> marine_hours (WP-12).

Display only: wave data never feeds evaluations or alerts.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Protocol

import httpx

from shakka.budget import SOURCE_OPEN_METEO_MARINE, BudgetGuard, estimate_call_weight
from shakka.db import SupabaseRest, iso_utc
from shakka.domain.forecast import SpotLocation
from shakka.domain.marine import MarineHour
from shakka.jobs.forecast import load_spot_locations
from shakka.jobs.inputs import require_aware
from shakka.openmeteo.marine import (
    DEFAULT_MARINE_DAYS,
    MARINE_MODELS,
    MARINE_VARIABLES,
    MAX_LOCATIONS_PER_REQUEST,
    MarineFetchError,
    fetch_marine,
)

RETENTION: Final = timedelta(hours=48)
CHUNK_SIZE: Final = MAX_LOCATIONS_PER_REQUEST
MARINE_TABLE: Final = "marine_hours"
MARINE_ON_CONFLICT: Final = "spot_id,valid_at"

logger = logging.getLogger("shakka.jobs.marine")


class FetchMarine(Protocol):
    def __call__(
        self,
        http: httpx.Client,
        locations: Sequence[SpotLocation],
        *,
        forecast_days: int = ...,
    ) -> list[MarineHour]: ...


@dataclass(frozen=True)
class MarineIngestResult:
    spots: int  # spots with coordinates considered
    rows: int  # rows upserted (after de-duplication)
    calls: float  # Open-Meteo weight recorded this run, rounded to 2 decimals
    skipped_budget: bool  # True if a chunk was not fetched because of the budget
    errors: list[str]  # one line per failed chunk: "chunk <n>/<total>: <message>"
    deleted: int = 0  # rows removed by delete_old_marine


def _chunk_weight(n_locations: int) -> float:
    """estimate_call_weight(n_locations, len(MARINE_VARIABLES), len(MARINE_MODELS),
    DEFAULT_MARINE_DAYS)."""
    return estimate_call_weight(
        n_locations, len(MARINE_VARIABLES), len(MARINE_MODELS), DEFAULT_MARINE_DAYS
    )


def delete_old_marine(db: SupabaseRest, *, now: datetime) -> int:
    """Remove rows with valid_at < now - 48h; returns the number of rows removed."""
    require_aware(now)
    return db.delete(MARINE_TABLE, filters={"valid_at": f"lt.{iso_utc(now - RETENTION)}"})


def run_marine_ingest(
    db: SupabaseRest,
    http: httpx.Client,
    budget: BudgetGuard,
    *,
    now: datetime,
    fetch: FetchMarine = fetch_marine,
) -> MarineIngestResult:
    require_aware(now)
    locations, _missing = load_spot_locations(db)
    chunks = [locations[i : i + CHUNK_SIZE] for i in range(0, len(locations), CHUNK_SIZE)]
    total = len(chunks)
    rows_stored = 0
    calls = 0.0
    skipped_budget = False
    errors: list[str] = []

    for n, chunk in enumerate(chunks, start=1):
        weight = _chunk_weight(len(chunk))
        if not budget.can_spend(weight, now=now):
            skipped_budget = True
            logger.warning("chunk %d/%d skipped: Open-Meteo budget exhausted", n, total)
            break
        logger.info("chunk %d/%d: %d locations, weight %.2f", n, total, len(chunk), weight)
        hours: list[MarineHour] | None
        try:
            hours = fetch(http, chunk)
        except MarineFetchError as exc:
            errors.append(f"chunk {n}/{total}: {exc}")
            hours = None
        # Always book the weight, also after a failure: Open-Meteo may have counted attempts.
        budget.record(SOURCE_OPEN_METEO_MARINE, weight, now=now, requests=1)
        calls += weight
        if hours is not None:
            unique = {(h.spot_id, h.valid_at): h for h in hours}
            payload = [h.to_row(fetched_at=now) for h in unique.values()]
            if payload:
                db.upsert(MARINE_TABLE, payload, on_conflict=MARINE_ON_CONFLICT)
            rows_stored += len(payload)

    deleted = delete_old_marine(db, now=now)
    return MarineIngestResult(
        spots=len(locations),
        rows=rows_stored,
        calls=round(calls, 2),
        skipped_budget=skipped_budget,
        errors=errors,
        deleted=deleted,
    )
