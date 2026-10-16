"""Load the inputs of the evaluation and alert jobs: spots, forecasts and tide extremes.

Per spot with coordinates: the profile, the forecast rows in the load range (stale rows
removed) and the extremes of its station. A spot without forecast rows is loaded with
`forecasts == []`; that is not an error. A broken row isolates only its own spot.
`load_inputs_checked` logs counts only, never spot ids: in the alert context it loads
favorite spots only, and a favorite is a user preference.
"""

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

from shakka.db import DatabaseError, SupabaseRest, in_filter, iso_utc
from shakka.domain.forecast import ForecastHour
from shakka.domain.spot import SPOT_COLUMNS, SpotProfile
from shakka.domain.tide import TideExtreme

logger = logging.getLogger(__name__)

FORECAST_LOOKBACK: Final = timedelta(hours=1)
FORECAST_HORIZON: Final = timedelta(days=8)
TIDE_MARGIN: Final = timedelta(hours=12)
STALE_FETCH_AGE: Final = timedelta(hours=3)
MAX_FETCH_AGE: Final = timedelta(hours=3)  # absolute: rows older than this are dropped (WP-22)
FORECAST_COLUMNS: Final = "spot_id,model,valid_at,wind_kn,gust_kn,dir_deg,fetched_at"
TIDE_COLUMNS: Final = "station,at,kind,level_cm"
MAX_ERROR_TEXT: Final = 200


@dataclass(frozen=True, slots=True)
class SpotInputs:
    spot: SpotProfile
    forecasts: list[ForecastHour]  # sorted by (valid_at, model), stale rows removed; [] if none
    tides: list[TideExtreme]  # only spot.rws_station.strip(), sorted by at


@dataclass(frozen=True, slots=True)
class InputsLoad:
    inputs: dict[str, SpotInputs]  # by spot id, in id order
    invalid: list[str]  # spot ids skipped because of a ValueError, sorted
    without_coords: list[str]  # sorted
    errors: list[str]  # "spot <id>: <ExcType>: <short message>"
    stale: list[str] = field(default_factory=list)  # spots whose rows were all too old, sorted


def require_aware(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")


def floor_hour(value: datetime) -> datetime:
    """Aware datetime to UTC with minutes, seconds and microseconds zeroed."""
    require_aware(value)
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def short_error(exc: BaseException) -> str:
    """One line, at most 200 characters."""
    return " ".join(str(exc).split())[:MAX_ERROR_TEXT]


def db_error_summary(exc: DatabaseError) -> str:
    """'DatabaseError (HTTP 409, code 23503)'; never the message (it may hold a user id)."""
    parts = []
    if exc.status is not None:
        parts.append(f"HTTP {exc.status}")
    if exc.code is not None:
        parts.append(f"code {exc.code}")
    return "DatabaseError" + (f" ({', '.join(parts)})" if parts else "")


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def load_inputs_checked(
    db: SupabaseRest,
    *,
    now: datetime,
    spot_ids: Collection[str] | None = None,
    max_fetch_age: timedelta | None = None,
) -> InputsLoad:
    """Load inputs per spot with coordinates. DatabaseError goes to the caller.

    With `max_fetch_age`, rows fetched before `now - max_fetch_age` are dropped first (exactly
    on the boundary a row stays); the relative stale rule applies to what is left. A spot that
    had rows but none left is listed in `stale` and loaded with `forecasts == []`."""
    require_aware(now)
    if spot_ids is not None and not spot_ids:
        return InputsLoad({}, [], [], [])
    spot_filters = None if spot_ids is None else {"id": in_filter(sorted(spot_ids))}
    rows = db.select("spots", columns=",".join(SPOT_COLUMNS), filters=spot_filters, order="id")

    start = floor_hour(now) - FORECAST_LOOKBACK
    end = now + FORECAST_HORIZON
    tide_cache: dict[str, list[TideExtreme] | ValueError] = {}
    inputs: dict[str, SpotInputs] = {}
    invalid: list[str] = []
    without_coords: list[str] = []
    errors: list[str] = []
    stale: list[str] = []

    for row in rows:
        if row.get("lat") is None or row.get("lon") is None:
            without_coords.append(str(row.get("id")))
            continue
        try:
            spot = SpotProfile.from_row(row)
            fc_rows = db.select(
                "forecast_hours",
                columns=FORECAST_COLUMNS,
                filters={
                    "spot_id": f"eq.{spot.id}",
                    "valid_at": [f"gte.{iso_utc(start)}", f"lt.{iso_utc(end)}"],
                },
            )
            forecasts: list[ForecastHour] = []
            if fc_rows and max_fetch_age is not None:
                oldest_allowed = now - max_fetch_age
                fresh = [r for r in fc_rows if _parse_ts(r["fetched_at"]) >= oldest_allowed]
                if not fresh:
                    stale.append(spot.id)
                fc_rows = fresh
            if fc_rows:
                newest = max(_parse_ts(r["fetched_at"]) for r in fc_rows)
                kept = [
                    r for r in fc_rows if _parse_ts(r["fetched_at"]) >= newest - STALE_FETCH_AGE
                ]
                forecasts = sorted(
                    (ForecastHour.from_row(r) for r in kept),
                    key=lambda f: (f.valid_at, f.model.value),
                )
            tides: list[TideExtreme] = []
            if spot.rws_station is not None:
                station = spot.rws_station.strip()
                if station not in tide_cache:
                    tide_rows = db.select(
                        "tide_extremes",
                        columns=TIDE_COLUMNS,
                        filters={
                            "station": f"eq.{station}",
                            "at": [
                                f"gte.{iso_utc(start - TIDE_MARGIN)}",
                                f"lte.{iso_utc(end + TIDE_MARGIN)}",
                            ],
                        },
                        order="at",
                    )
                    try:
                        tide_cache[station] = [TideExtreme.from_row(r) for r in tide_rows]
                    except ValueError as exc:
                        tide_cache[station] = exc
                cached = tide_cache[station]
                if isinstance(cached, ValueError):
                    raise cached
                tides = cached
            inputs[spot.id] = SpotInputs(spot, forecasts, tides)
        except ValueError as exc:
            sid = str(row.get("id"))
            invalid.append(sid)
            errors.append(f"spot {sid}: {type(exc).__name__}: {short_error(exc)}")

    invalid.sort()
    without_coords.sort()
    stale.sort()
    args = (len(rows), len(inputs), len(invalid), len(without_coords), len(stale))
    text = "inputs: spots=%d loaded=%d invalid=%d without_coords=%d stale=%d"
    if invalid:
        logger.warning(text, *args)
    else:
        logger.info(text, *args)
    return InputsLoad(inputs, invalid, without_coords, errors, stale)


def load_inputs(
    db: SupabaseRest,
    *,
    now: datetime,
    spot_ids: Collection[str] | None = None,
    max_fetch_age: timedelta | None = None,
) -> dict[str, SpotInputs]:
    return load_inputs_checked(db, now=now, spot_ids=spot_ids, max_fetch_age=max_fetch_age).inputs
