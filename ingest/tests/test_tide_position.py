"""relative_tide_position, including the double low water (agger)."""

from datetime import UTC, datetime

import pytest

from evaluation_fixtures import extremes
from shakka.domain.tide import relative_tide_position


def t(h: int, d: int = 15) -> datetime:
    return datetime(2026, 7, d, h, tzinfo=UTC)


BASIC = extremes((t(0), "high", 100), (t(6), "low", -80), (t(12), "high", 100), (t(18), "low", -80))


def test_high_low_and_half() -> None:
    assert relative_tide_position(BASIC, t(12)) == 1.0
    assert relative_tide_position(BASIC, t(6)) == 0.0
    assert relative_tide_position(BASIC, datetime(2026, 7, 15, 9, tzinfo=UTC)) == pytest.approx(
        0.5, abs=0.01
    )


def test_agger_is_around_low_water() -> None:
    ext = extremes(
        (t(3), "high", 110),
        (t(10), "low", -60),
        (t(14), "low", -55),
        (t(19), "high", 120),
    )
    assert relative_tide_position(ext, t(12)) <= 0.05  # type: ignore[operator]
    pos = relative_tide_position(ext, datetime(2026, 7, 15, 16, 30, tzinfo=UTC))
    assert pos == pytest.approx(0.5, abs=0.05)


def test_only_lows_is_none() -> None:
    ext = extremes((t(6), "low", -80), (t(12), "low", -70))
    assert relative_tide_position(ext, t(9)) is None


def test_equal_distance_picks_earliest_low() -> None:
    ext = extremes((t(10), "low", -60), (t(14), "low", -40), (t(19), "high", 100))
    pos = relative_tide_position(ext, t(12))
    assert pos is not None
    # level at 12:00 is -50; the earliest low (-60) is the reference: 10 / 160
    assert pos == pytest.approx(10 / 160)


def test_high_not_above_low_is_none() -> None:
    ext = extremes((t(6), "low", 50), (t(12), "high", 50))
    assert relative_tide_position(ext, datetime(2026, 7, 15, 9, tzinfo=UTC)) is None


def test_no_level_is_none() -> None:
    assert relative_tide_position([], t(9)) is None
    assert relative_tide_position(BASIC, datetime(2026, 7, 14, 9, tzinfo=UTC)) is None
