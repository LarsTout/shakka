"""Forecast ingest job: spots -> Open-Meteo (budget guarded) -> forecast_hours."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Protocol

import httpx
from pydantic import ValidationError

from shakka.budget import (
    SOURCE_OPEN_METEO_FORECAST,
    BudgetGuard,
    BudgetUsage,
    estimate_call_weight,
)
from shakka.db import SupabaseRest, iso_utc
from shakka.domain.forecast import ForecastHour, SpotLocation
from shakka.openmeteo.forecast import (
    DEFAULT_FORECAST_DAYS,
    HOURLY_VARIABLES,
    MAX_LOCATIONS_PER_REQUEST,
    ForecastFetchError,
    fetch_forecast,
)
from shakka.openmeteo.models import OPEN_METEO_MODELS

RETENTION: Final = timedelta(hours=48)
CHUNK_SIZE: Final = MAX_LOCATIONS_PER_REQUEST
FORECAST_TABLE: Final = "forecast_hours"
FORECAST_ON_CONFLICT: Final = "spot_id,model,valid_at"

logger = logging.getLogger("shakka.jobs.forecast")


class FetchForecast(Protocol):
    def __call__(
        self,
        http: httpx.Client,
        locations: Sequence[SpotLocation],
        *,
        forecast_days: int = ...,
    ) -> list[ForecastHour]: ...


@dataclass(frozen=True)
class ForecastIngestResult:
    spots: int  # spots with coordinates considered
    rows: int  # rows upserted (after de-duplication)
    calls: float  # Open-Meteo weight recorded this run, rounded to 2 decimals
    skipped_budget: bool  # True if a chunk was not fetched because of the budget
    errors: list[str]  # one line per failed chunk: "chunk <n>/<total>: <message>"
    deleted: int = 0  # rows removed by delete_old_forecasts


@dataclass(frozen=True)
class ForecastIngestPlan:
    spots: int
    without_coords: list[str]  # spot ids without lat or lon, sorted
    requests: int
    weight: float
    usage: BudgetUsage
    within_budget: bool  # budget.can_spend(weight, now=now)


def _require_aware(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")


def _chunk_weight(n_locations: int) -> float:
    """estimate_call_weight(n_locations, len(HOURLY_VARIABLES), len(OPEN_METEO_MODELS),
    DEFAULT_FORECAST_DAYS). Used by both run_forecast_ingest and plan_forecast_ingest."""
    return estimate_call_weight(
        n_locations, len(HOURLY_VARIABLES), len(OPEN_METEO_MODELS), DEFAULT_FORECAST_DAYS
    )


def _chunks(locations: list[SpotLocation]) -> list[list[SpotLocation]]:
    return [locations[i : i + CHUNK_SIZE] for i in range(0, len(locations), CHUNK_SIZE)]


def load_spot_locations(db: SupabaseRest) -> tuple[list[SpotLocation], list[str]]:
    """select spots(id,lat,lon) in id order; returns (locations, ids without coordinates)."""
    rows = db.select("spots", columns="id,lat,lon", order="id")
    locations: list[SpotLocation] = []
    missing: list[str] = []
    for row in rows:
        if row.get("lat") is None or row.get("lon") is None:
            missing.append(str(row["id"]))
            continue
        try:
            locations.append(
                SpotLocation(spot_id=str(row["id"]), lat=float(row["lat"]), lon=float(row["lon"]))
            )
        except (ValidationError, ValueError):
            missing.append(str(row["id"]))
    return locations, sorted(missing)


def plan_forecast_ingest(
    db: SupabaseRest, budget: BudgetGuard, *, now: datetime
) -> ForecastIngestPlan:
    """No HTTP, no writes."""
    _require_aware(now)
    locations, missing = load_spot_locations(db)
    chunks = _chunks(locations)
    weight = round(sum(_chunk_weight(len(chunk)) for chunk in chunks), 4)
    return ForecastIngestPlan(
        spots=len(locations),
        without_coords=missing,
        requests=len(chunks),
        weight=weight,
        usage=budget.usage(now=now),
        within_budget=budget.can_spend(weight, now=now),
    )


def delete_old_forecasts(db: SupabaseRest, *, now: datetime) -> int:
    """Remove rows with valid_at < now - 48h; returns the number of rows removed."""
    _require_aware(now)
    return db.delete(FORECAST_TABLE, filters={"valid_at": f"lt.{iso_utc(now - RETENTION)}"})


def run_forecast_ingest(
    db: SupabaseRest,
    http: httpx.Client,
    budget: BudgetGuard,
    *,
    now: datetime,
    fetch: FetchForecast = fetch_forecast,
) -> ForecastIngestResult:
    _require_aware(now)
    locations, _missing = load_spot_locations(db)
    chunks = _chunks(locations)
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
        hours: list[ForecastHour] | None
        try:
            hours = fetch(http, chunk)
        except ForecastFetchError as exc:
            errors.append(f"chunk {n}/{total}: {exc}")
            hours = None
        # Always book the weight, also after a failure: Open-Meteo may have counted attempts.
        budget.record(SOURCE_OPEN_METEO_FORECAST, weight, now=now, requests=1)
        calls += weight
        if hours is not None:
            unique = {(h.spot_id, h.model, h.valid_at): h for h in hours}
            payload = [h.to_row(fetched_at=now) for h in unique.values()]
            if payload:
                db.upsert(FORECAST_TABLE, payload, on_conflict=FORECAST_ON_CONFLICT)
            rows_stored += len(payload)
        logger.info("chunk %d/%d: %d locations, weight %.2f", n, total, len(chunk), weight)

    deleted = delete_old_forecasts(db, now=now)
    return ForecastIngestResult(
        spots=len(locations),
        rows=rows_stored,
        calls=round(calls, 2),
        skipped_budget=skipped_budget,
        errors=errors,
        deleted=deleted,
    )
