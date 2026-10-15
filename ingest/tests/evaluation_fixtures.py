"""Helpers for the evaluation tests. Test coordinates are test data, not spot data."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from shakka.domain.forecast import ForecastHour, ModelKey
from shakka.domain.spot import SpotProfile
from shakka.domain.tide import TideExtreme

LAT, LON = 52.47, 4.57  # test coordinates (WP-05 AC-5), not spot data
NOON = datetime(2026, 7, 15, 10, tzinfo=UTC)  # 12:00 local, daylight
STATION = "teststation"


def make_spot(**overrides: Any) -> SpotProfile:
    base: dict[str, Any] = {
        "id": "test-strand",
        "name": "Teststrand",
        "lat": LAT,
        "lon": LON,
        "shore_normal_deg": 270,
        "status": "allowed",
        "level": "intermediate",
        "verified": False,
    }
    base.update(overrides)
    return SpotProfile.model_validate(base)


def model_hours(
    valid_at: datetime,
    *,
    wind: float | None = 20.0,
    gust: float | None = 24.0,
    dir_deg: int | None = 270,
    models: tuple[ModelKey, ...] = tuple(ModelKey),
    spot_id: str = "test-strand",
) -> list[ForecastHour]:
    """Same values for each model."""
    return [
        ForecastHour(
            spot_id=spot_id, model=m, valid_at=valid_at, wind_kn=wind, gust_kn=gust, dir_deg=dir_deg
        )
        for m in models
    ]


def per_model(
    valid_at: datetime,
    values: Mapping[ModelKey, tuple[float | None, float | None, int | None]],
    spot_id: str = "test-strand",
) -> list[ForecastHour]:
    """(wind, gust, dir) per model."""
    return [
        ForecastHour(spot_id=spot_id, model=m, valid_at=valid_at, wind_kn=w, gust_kn=g, dir_deg=d)
        for m, (w, g, d) in values.items()
    ]


def extremes(*points: tuple[datetime, str, int], station: str = STATION) -> list[TideExtreme]:
    return [
        TideExtreme.model_validate({"station": station, "at": at, "kind": kind, "level_cm": lvl})
        for at, kind, lvl in points
    ]
