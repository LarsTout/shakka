"""Quiet hours: pure check in local time (WP-30)."""

from datetime import UTC, datetime, time, timedelta, timezone

import pytest

from shakka.domain.quiet import QuietHours, in_quiet_hours, quiet_hours_from_row

NIGHT = QuietHours(time(22), time(7))
DAY = QuietHours(time(13), time(14))


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def quarters(quiet: QuietHours, start: datetime) -> int:
    """Quiet quarters of an hour in the 24 real hours from `start` (UTC)."""
    return sum(in_quiet_hours(start + timedelta(minutes=15 * i), quiet) for i in range(96))


def test_overnight_boundaries() -> None:
    # 2026-07-15 is CEST (UTC+2)
    assert in_quiet_hours(utc(2026, 7, 14, 20, 0), NIGHT)  # 22:00 local
    assert in_quiet_hours(utc(2026, 7, 14, 21, 30), NIGHT)  # 23:30
    assert in_quiet_hours(utc(2026, 7, 15, 4, 59), NIGHT)  # 06:59
    assert not in_quiet_hours(utc(2026, 7, 15, 5, 0), NIGHT)  # 07:00
    assert not in_quiet_hours(utc(2026, 7, 14, 19, 59), NIGHT)  # 21:59


def test_same_day_boundaries() -> None:
    assert in_quiet_hours(utc(2026, 7, 15, 11, 0), DAY)  # 13:00
    assert in_quiet_hours(utc(2026, 7, 15, 11, 59), DAY)  # 13:59
    assert not in_quiet_hours(utc(2026, 7, 15, 12, 0), DAY)  # 14:00
    assert not in_quiet_hours(utc(2026, 7, 15, 10, 59), DAY)  # 12:59


def test_dst_spring_2026_03_29() -> None:
    assert in_quiet_hours(utc(2026, 3, 29, 4, 59), NIGHT)
    assert not in_quiet_hours(utc(2026, 3, 29, 5, 0), NIGHT)
    assert not in_quiet_hours(utc(2026, 3, 28, 20, 59), NIGHT)
    assert in_quiet_hours(utc(2026, 3, 28, 21, 0), NIGHT)
    assert quarters(NIGHT, utc(2026, 3, 28, 12)) == 32


def test_dst_autumn_2026_10_25() -> None:
    assert in_quiet_hours(utc(2026, 10, 25, 5, 59), NIGHT)
    assert not in_quiet_hours(utc(2026, 10, 25, 6, 0), NIGHT)
    assert not in_quiet_hours(utc(2026, 10, 24, 19, 59), NIGHT)
    assert in_quiet_hours(utc(2026, 10, 24, 20, 0), NIGHT)
    assert quarters(NIGHT, utc(2026, 10, 24, 12)) == 40


def test_dst_gap_and_fold() -> None:
    small = QuietHours(time(2), time(3))
    assert quarters(small, utc(2026, 3, 29, 0)) == 0  # 02:xx does not exist
    assert quarters(small, utc(2026, 10, 25, 0)) == 8  # 02:xx occurs twice


def test_none_is_never_quiet() -> None:
    assert in_quiet_hours(utc(2026, 7, 15, 12), None) is False


def test_naive_now_raises() -> None:
    naive = datetime(2026, 7, 15, 12)  # noqa: DTZ001
    with pytest.raises(ValueError):
        in_quiet_hours(naive, NIGHT)
    with pytest.raises(ValueError):
        in_quiet_hours(naive, None)


def test_quiet_hours_validation() -> None:
    with pytest.raises(ValueError):
        QuietHours(time(22), time(22))
    with pytest.raises(ValueError):
        QuietHours(time(22, tzinfo=UTC), time(7))
    with pytest.raises(ValueError):
        QuietHours(time(22), time(7, tzinfo=timezone(timedelta(hours=1))))
    with pytest.raises(ValueError):
        QuietHours("22:00", time(7))  # type: ignore[arg-type]


def test_from_row() -> None:
    expected = QuietHours(time(22), time(7))
    assert quiet_hours_from_row({"quiet_from": "22:00:00", "quiet_until": "07:00:00"}) == expected
    assert quiet_hours_from_row({"quiet_from": "22:00", "quiet_until": "07:00"}) == expected
    assert quiet_hours_from_row({"quiet_from": time(22), "quiet_until": time(7)}) == expected
    assert quiet_hours_from_row({"quiet_from": None, "quiet_until": None}) is None
    assert quiet_hours_from_row({}) is None


@pytest.mark.parametrize(
    "row",
    [
        {"quiet_from": "22:00:00", "quiet_until": None},
        {"quiet_from": None, "quiet_until": "07:00:00"},
        {"quiet_from": "22:00:00"},
        {"quiet_from": "abc", "quiet_until": "07:00"},
        {"quiet_from": "22:00+01:00", "quiet_until": "07:00"},
        {"quiet_from": "22:00", "quiet_until": "22:00:00"},
        {"quiet_from": 22, "quiet_until": 7},
        {"quiet_from": time(22, tzinfo=UTC), "quiet_until": time(7)},
    ],
)
def test_from_row_invalid(row: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        quiet_hours_from_row(row)
