"""Tests for the forecast value types."""

import json
import math
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from shakka.db import to_json
from shakka.domain.forecast import ForecastHour, ModelKey, SpotLocation

T0 = datetime(2026, 10, 14, 12, tzinfo=UTC)


def make(**overrides) -> ForecastHour:
    values = {
        "spot_id": "spot-a",
        "model": ModelKey.ICON,
        "valid_at": T0,
        "wind_kn": 12.5,
        "gust_kn": 18.0,
        "dir_deg": 270,
    }
    values.update(overrides)
    return ForecastHour(**values)


def test_forecast_hour_requires_aware() -> None:
    with pytest.raises(ValidationError):
        make(valid_at=T0.replace(tzinfo=None))


def test_forecast_hour_normalizes_to_utc() -> None:
    local = datetime(2026, 10, 14, 14, tzinfo=timezone(timedelta(hours=2)))
    hour = make(valid_at=local)
    assert hour.valid_at == T0
    assert hour.valid_at.utcoffset() == timedelta(0)
    assert hour.valid_at.tzinfo is UTC


@pytest.mark.parametrize(
    "valid_at",
    [
        datetime(2026, 10, 14, 12, 30, tzinfo=UTC),
        datetime(2026, 10, 14, 12, 0, 5, tzinfo=UTC),
        datetime(2026, 10, 14, 12, 0, 0, 1, tzinfo=UTC),
    ],
)
def test_forecast_hour_rejects_non_hour(valid_at: datetime) -> None:
    with pytest.raises(ValidationError):
        make(valid_at=valid_at)


@pytest.mark.parametrize(
    "overrides",
    [
        {"wind_kn": -1.0},
        {"gust_kn": -0.1},
        {"dir_deg": 360},
        {"dir_deg": -1},
        {"wind_kn": math.nan},
        {"gust_kn": math.inf},
    ],
)
def test_forecast_hour_ranges(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        make(**overrides)


def test_forecast_hour_allows_none_values() -> None:
    hour = make(wind_kn=None, gust_kn=None, dir_deg=None)
    assert hour.wind_kn is None and hour.gust_kn is None and hour.dir_deg is None


def test_forecast_hour_fields_are_required() -> None:
    with pytest.raises(ValidationError):
        ForecastHour(spot_id="a", model=ModelKey.GFS, valid_at=T0)  # type: ignore[call-arg]


def test_forecast_hour_frozen() -> None:
    hour = make()
    with pytest.raises(ValidationError):
        hour.wind_kn = 1.0  # type: ignore[misc]


def test_forecast_hour_forbids_extra() -> None:
    with pytest.raises(ValidationError):
        make(extra=1)


def test_to_row_keys_exact() -> None:
    row = make().to_row(fetched_at=T0)
    assert list(row) == [
        "spot_id",
        "model",
        "valid_at",
        "wind_kn",
        "gust_kn",
        "dir_deg",
        "fetched_at",
    ]
    assert row["model"] == "icon"
    assert type(row["model"]) is str
    assert row["fetched_at"] == T0


def test_to_row_rejects_naive_fetched_at() -> None:
    with pytest.raises(ValueError):
        make().to_row(fetched_at=T0.replace(tzinfo=None))


@pytest.mark.parametrize("suffix", ["+00:00", "Z"])
def test_from_row_roundtrip(suffix: str) -> None:
    hour = make(gust_kn=None)
    row = json.loads(to_json(hour.to_row(fetched_at=T0)))
    assert row["valid_at"].endswith("Z")
    if suffix == "+00:00":
        row["valid_at"] = row["valid_at"].removesuffix("Z") + "+00:00"
    assert ForecastHour.from_row(row) == hour


def test_from_row_accepts_datetime_and_ignores_extras() -> None:
    hour = make()
    row = hour.to_row(fetched_at=T0) | {"unknown": 1}
    assert ForecastHour.from_row(row) == hour


def test_spot_location_ranges() -> None:
    SpotLocation(spot_id="a", lat=52.0, lon=4.0)
    for bad in (
        {"spot_id": "", "lat": 0, "lon": 0},
        {"spot_id": "a", "lat": 91, "lon": 0},
        {"spot_id": "a", "lat": 0, "lon": 181},
        {"spot_id": "a", "lat": math.nan, "lon": 0},
    ):
        with pytest.raises(ValidationError):
            SpotLocation(**bad)


def test_model_key_values() -> None:
    assert [m.value for m in ModelKey] == ["knmi", "icon", "ecmwf", "gfs"]
