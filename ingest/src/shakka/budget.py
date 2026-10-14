"""Open-Meteo call budget: weight estimate and a guard on api_usage (80% of the free limit)."""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

from shakka.db import SupabaseRest

OPEN_METEO_DAILY_LIMIT: Final = 10_000
OPEN_METEO_MONTHLY_LIMIT: Final = 300_000
GUARD_FRACTION: Final = 0.8
DEFAULT_DAILY_LIMIT: Final = 8000.0  # == GUARD_FRACTION * OPEN_METEO_DAILY_LIMIT
DEFAULT_MONTHLY_LIMIT: Final = 240000.0  # == GUARD_FRACTION * OPEN_METEO_MONTHLY_LIMIT
REFERENCE_VARIABLES: Final = 10
REFERENCE_DAYS: Final = 14
OPEN_METEO_PREFIX: Final = "open_meteo_"
SOURCE_OPEN_METEO_FORECAST: Final = "open_meteo_forecast"
SOURCE_OPEN_METEO_MARINE: Final = "open_meteo_marine"
SOURCE_RWS: Final = "rws"
API_USAGE_SOURCES: Final = frozenset(
    {SOURCE_OPEN_METEO_FORECAST, SOURCE_OPEN_METEO_MARINE, SOURCE_RWS}
)


def estimate_call_weight(
    n_locations: int, n_hourly_vars: int, n_models: int, forecast_days: int
) -> float:
    """n_locations * max(1, vars*models/10) * max(1, days/14), rounded to 4 decimals.
    Upper bound of Open-Meteo's calculateQueryWeight; equal for days <= 14.
    ValueError if any argument < 1."""
    if min(n_locations, n_hourly_vars, n_models, forecast_days) < 1:
        raise ValueError("all arguments must be at least 1")
    variables = max(1.0, n_hourly_vars * n_models / REFERENCE_VARIABLES)
    days = max(1.0, forecast_days / REFERENCE_DAYS)
    return round(n_locations * variables * days, 4)


@dataclass(frozen=True)
class BudgetUsage:
    daily: float  # sum of open_meteo_* calls on the UTC day of `now`
    monthly: float  # sum of open_meteo_* calls in the UTC month of `now`


def _utc_day(now: datetime) -> date:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(UTC).date()


def _check_weight(weight: float) -> None:
    if not math.isfinite(weight) or weight < 0:
        raise ValueError("weight must be finite and >= 0")


class BudgetGuard:
    def __init__(
        self,
        db: SupabaseRest,
        *,
        daily_limit: float = DEFAULT_DAILY_LIMIT,
        monthly_limit: float = DEFAULT_MONTHLY_LIMIT,
    ) -> None:
        if not (daily_limit > 0 and monthly_limit > 0):
            raise ValueError("limits must be positive")
        self._db = db
        self._daily_limit = daily_limit
        self._monthly_limit = monthly_limit

    @property
    def daily_limit(self) -> float:
        return self._daily_limit

    @property
    def monthly_limit(self) -> float:
        return self._monthly_limit

    def usage(self, *, now: datetime) -> BudgetUsage:
        day = _utc_day(now)
        first = day.replace(day=1)
        next_first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        rows = self._db.select(
            "api_usage",
            columns="day,source,calls",
            filters={"day": [f"gte.{first.isoformat()}", f"lt.{next_first.isoformat()}"]},
        )
        daily = monthly = 0.0
        for row in rows:
            if not str(row["source"]).startswith(OPEN_METEO_PREFIX):
                continue
            calls = float(row["calls"])
            monthly += calls
            if str(row["day"]) == day.isoformat():
                daily += calls
        return BudgetUsage(daily=daily, monthly=monthly)

    def can_spend(self, weight: float, *, now: datetime) -> bool:
        _utc_day(now)
        _check_weight(weight)
        usage = self.usage(now=now)
        return (
            usage.daily + weight <= self._daily_limit
            and usage.monthly + weight <= self._monthly_limit
        )

    def record(self, source: str, weight: float, *, now: datetime, requests: int = 1) -> None:
        day = _utc_day(now)
        if source not in API_USAGE_SOURCES:
            raise ValueError("unknown api_usage source")
        _check_weight(weight)
        if requests < 0:
            raise ValueError("requests must be >= 0")
        existing = self._db.select(
            "api_usage",
            filters={"day": f"eq.{day.isoformat()}", "source": f"eq.{source}"},
        )
        old_calls = float(existing[0]["calls"]) if existing else 0.0
        old_requests = int(existing[0]["requests"]) if existing else 0
        self._db.upsert(
            "api_usage",
            [
                {
                    "day": day,
                    "source": source,
                    "calls": round(old_calls + weight, 2),
                    "requests": old_requests + requests,
                }
            ],
            on_conflict="day,source",
        )
