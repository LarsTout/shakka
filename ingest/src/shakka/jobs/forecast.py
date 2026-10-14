"""Forecast ingest job: spots -> Open-Meteo (budget guarded) -> forecast_hours."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

import httpx
from pydantic import ValidationError

from shakka.budget import (
    SOURCE_OPEN_METEO_FORECAST,
    BudgetGuard,
    BudgetUsage,
    estimate_call_weight,
)
from shakka.config import Settings, get_settings
from shakka.db import DatabaseError, SupabaseRest, iso_utc
from shakka.domain.forecast import ForecastHour, SpotLocation
from shakka.http import make_client
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


def _open_resources(settings: Settings) -> tuple[SupabaseRest, httpx.Client]:
    """Test seam: create the database client and the HTTP client."""
    return SupabaseRest.from_settings(settings), make_client(timeout=30.0)


def _utcnow() -> datetime:
    """Test seam: the current time."""
    return datetime.now(UTC)


def _run_dry(
    db: SupabaseRest, budget: BudgetGuard, *, now: datetime, echo: Callable[[str], None]
) -> int:
    plan = plan_forecast_ingest(db, budget, now=now)
    echo("forecast: dry run, no requests to Open-Meteo and no database writes")
    echo(f"spots with coordinates: {plan.spots}, without coordinates: {len(plan.without_coords)}")
    echo(f"requests: {plan.requests}, estimated weight: {plan.weight:.2f}")
    echo(
        f"usage today: {plan.usage.daily:.2f} / {budget.daily_limit:.0f}, "
        f"this month: {plan.usage.monthly:.2f} / {budget.monthly_limit:.0f}"
    )
    echo("budget: ok" if plan.within_budget else "budget: exceeded")
    return 0


def _run_real(
    db: SupabaseRest,
    http: httpx.Client,
    budget: BudgetGuard,
    *,
    now: datetime,
    echo: Callable[[str], None],
) -> int:
    result = run_forecast_ingest(db, http, budget, now=now)
    echo(
        f"forecast: spots={result.spots} rows={result.rows} calls={result.calls:.2f} "
        f"deleted={result.deleted} skipped_budget={'yes' if result.skipped_budget else 'no'} "
        f"errors={len(result.errors)}"
    )
    for line in result.errors:
        echo(f"error   {line}")
    failed = bool(result.errors) or result.skipped_budget
    echo("forecast: failed" if failed else "forecast: ok")
    return 1 if failed else 0


def run_forecast_cli(*, dry_run: bool, echo: Callable[[str], None]) -> int:
    """Run `shakka forecast fetch`. Returns the exit code. Never prints environment values."""
    try:
        settings = get_settings()
    except ValidationError:
        echo("forecast: configuration incomplete; run shakka doctor")
        return 1
    db, http = _open_resources(settings)
    try:
        budget = BudgetGuard(db)
        now = _utcnow()
        if dry_run:
            return _run_dry(db, budget, now=now, echo=echo)
        return _run_real(db, http, budget, now=now, echo=echo)
    except DatabaseError as exc:
        echo(f"forecast: database error: {exc}")
        return 1
    finally:
        http.close()
        db.close()
