"""AC-5 and AC-11: daylight."""

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

import shakka.domain.daylight as daylight
from shakka.domain.daylight import is_daylight, sun_times

LAT, LON = 52.47, 4.57  # test coordinates, not spot data
MARGIN = timedelta(minutes=15)


def utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=UTC)


def test_summer_night_is_dark() -> None:
    assert is_daylight(LAT, LON, utc(2026, 6, 21, 3)) is False


def test_summer_noon_is_light() -> None:
    assert is_daylight(LAT, LON, utc(2026, 6, 21, 12)) is True


def test_winter_evening_is_dark() -> None:
    assert is_daylight(LAT, LON, utc(2026, 12, 21, 17)) is False


def test_sun_times_plausible() -> None:
    sr, ss = sun_times(LAT, LON, date(2026, 6, 21))
    assert utc(2026, 6, 21, 3, 10) <= sr <= utc(2026, 6, 21, 3, 30)
    assert utc(2026, 6, 21, 19, 55) <= ss <= utc(2026, 6, 21, 20, 15)
    sr, ss = sun_times(LAT, LON, date(2026, 12, 21))
    assert utc(2026, 12, 21, 7, 35) <= sr <= utc(2026, 12, 21, 8, 0)
    assert utc(2026, 12, 21, 15, 20) <= ss <= utc(2026, 12, 21, 15, 45)


def test_margin_boundaries() -> None:
    sr, ss = sun_times(LAT, LON, date(2026, 6, 21))
    second = timedelta(seconds=1)
    hour = timedelta(hours=1)
    assert is_daylight(LAT, LON, sr - MARGIN) is True
    assert is_daylight(LAT, LON, sr - MARGIN - second) is False
    assert is_daylight(LAT, LON, ss + MARGIN - hour) is True
    assert is_daylight(LAT, LON, ss + MARGIN - hour + second) is False


def test_naive_raises() -> None:
    with pytest.raises(ValueError):
        is_daylight(LAT, LON, datetime(2026, 6, 21, 12))  # noqa: DTZ001


def test_winter_daylight_hours() -> None:
    hours = [h for h in range(24) if is_daylight(LAT, LON, utc(2026, 12, 21, h))]
    assert hours == list(range(8, 15))  # 08:00 through 14:00 (UTC hour starts)


def test_sun_times_is_cached() -> None:
    sun_times.cache_clear()
    sun_times(LAT, LON, date(2026, 6, 21))
    sun_times(LAT, LON, date(2026, 6, 21))
    assert sun_times.cache_info().hits == 1


def test_astral_calls_always_pass_date() -> None:
    tree = ast.parse(Path(daylight.__file__).read_text(encoding="utf-8"))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in {"sunrise", "sunset"}
    ]
    assert len(calls) == 2
    for call in calls:
        assert "date" in {k.arg for k in call.keywords}
