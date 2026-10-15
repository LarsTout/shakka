"""Tests for the wave forecast value type."""

import json
import math
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from shakka.db import to_json
from shakka.domain.marine import MarineHour

T0 = datetime(2026, 10, 14, 12, tzinfo=UTC)


def make(**overrides) -> MarineHour:
    values = {
        "spot_id": "spot-a",
        "valid_at": T0,
        "wave_height_m": 1.2,
        "wave_period_s": 5.0,
        "wave_dir_deg": 250,
    }
    values.update(overrides)
    return MarineHour(**values)


def test_marine_hour_requires_aware() -> None:
    with pytest.raises(ValidationError):
        make(valid_at=T0.replace(tzinfo=None))


def test_normalizes_to_utc() -> None:
    local = datetime(2026, 10, 14, 14, tzinfo=timezone(timedelta(hours=2)))
    hour = make(valid_at=local)
    assert hour.valid_at == T0
    assert hour.valid_at.tzinfo is UTC


@pytest.mark.parametrize(
    "valid_at",
    [
        datetime(2026, 10, 14, 12, 30, tzinfo=UTC),
        datetime(2026, 10, 14, 12, 0, 5, tzinfo=UTC),
        datetime(2026, 10, 14, 12, 0, 0, 1, tzinfo=UTC),
    ],
)
def test_rejects_non_hour(valid_at: datetime) -> None:
    with pytest.raises(ValidationError):
        make(valid_at=valid_at)


@pytest.mark.parametrize(
    "overrides",
    [
        {"wave_height_m": -1.0},
        {"wave_period_s": -1.0},
        {"wave_dir_deg": 360},
        {"wave_dir_deg": -1},
        {"wave_height_m": math.nan},
        {"wave_period_s": math.inf},
    ],
)
def test_ranges(overrides) -> None:
    with pytest.raises(ValidationError):
        make(**overrides)


def test_all_none_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one wave value"):
        make(wave_height_m=None, wave_period_s=None, wave_dir_deg=None)


def test_single_value_allowed() -> None:
    hour = make(wave_height_m=0.0, wave_period_s=None, wave_dir_deg=None)
    assert hour.wave_height_m == 0.0


def test_frozen() -> None:
    with pytest.raises(ValidationError):
        make().wave_height_m = 2.0  # type: ignore[misc]


def test_to_row_keys_exact() -> None:
    row = make().to_row(fetched_at=T0)
    assert list(row) == [
        "spot_id",
        "valid_at",
        "wave_height_m",
        "wave_period_s",
        "wave_dir_deg",
        "fetched_at",
    ]
    with pytest.raises(ValueError):
        make().to_row(fetched_at=T0.replace(tzinfo=None))


@pytest.mark.parametrize("suffix", ["+00:00", "Z"])
def test_from_row_roundtrip(suffix: str) -> None:
    hour = make()
    row = json.loads(to_json(hour.to_row(fetched_at=T0)))
    row["valid_at"] = row["valid_at"].removesuffix("+00:00").removesuffix("Z") + suffix
    row["unknown"] = 1
    assert MarineHour.from_row(row) == hour
    assert MarineHour.from_row(hour.to_row(fetched_at=T0)) == hour
