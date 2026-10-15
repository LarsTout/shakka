"""AC-6 (unit): season closures in local time."""

from datetime import UTC, date, datetime

import pytest

from shakka.domain.season import closure_applies, in_period, is_season_closed
from shakka.domain.spot import SeasonClosure


def sc(**kw: str) -> SeasonClosure:
    return SeasonClosure.model_validate(kw)


S = sc(start="05-01", end="09-30", from_time="10:00", to_time="18:00")
DST = sc(start="03-01", end="11-30", from_time="10:00", to_time="18:00")


def z(m: int, d: int, h: int, y: int = 2026) -> datetime:
    return datetime(y, m, d, h, tzinfo=UTC)


@pytest.mark.parametrize(
    ("at", "closed"),
    [
        (z(7, 15, 10), True),
        (z(7, 15, 17), False),
        (z(10, 15, 10), False),
        (z(7, 15, 7), False),  # 09:00 local
        (z(7, 15, 15), True),  # 17:00 local
        (z(7, 15, 16), False),  # 18:00 local
    ],
)
def test_window(at: datetime, closed: bool) -> None:
    assert closure_applies(S, at) is closed


def test_over_year_boundary() -> None:
    c = sc(start="11-15", end="02-15")
    assert closure_applies(c, z(1, 10, 12, 2027)) is True
    assert closure_applies(c, z(2, 16, 12, 2027)) is False


@pytest.mark.parametrize(
    ("at", "closed"),
    [
        (z(3, 28, 9), True),
        (z(3, 28, 8), False),
        (z(3, 29, 8), True),
        (z(3, 29, 7), False),
        (z(3, 29, 16), False),
        (z(3, 29, 15), True),
        (z(10, 24, 8), True),
        (z(10, 24, 7), False),
        (z(10, 25, 9), True),
        (z(10, 25, 8), False),
        (z(10, 25, 17), False),
        (z(10, 25, 16), True),
    ],
)
def test_dst(at: datetime, closed: bool) -> None:
    assert closure_applies(DST, at) is closed


def test_local_date_counts() -> None:
    c = sc(start="03-01", end="03-28")
    assert closure_applies(c, z(3, 28, 22)) is True
    assert closure_applies(c, z(3, 28, 23)) is False


def test_partial_overlap_is_closed() -> None:
    c = sc(start="05-01", end="09-30", from_time="10:30", to_time="18:00")
    assert closure_applies(c, z(7, 15, 8)) is True


def test_leap_day() -> None:
    assert in_period("12-01", "02-29", date(2027, 2, 28)) is True
    assert in_period("12-01", "02-29", date(2027, 3, 1)) is False
    assert in_period("02-29", "03-31", date(2027, 3, 1)) is True


def test_is_season_closed_any() -> None:
    assert is_season_closed([], z(7, 15, 10)) is False
    assert is_season_closed([sc(start="01-01", end="01-02"), S], z(7, 15, 10)) is True


def test_naive_raises() -> None:
    with pytest.raises(ValueError):
        closure_applies(S, datetime(2026, 7, 15, 10))  # noqa: DTZ001
