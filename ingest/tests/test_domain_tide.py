import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from shakka.db import to_json
from shakka.domain.tide import TideExtreme, estimate_tide_level


def ext(iso, kind, level, station="x"):
    return TideExtreme(station=station, at=datetime.fromisoformat(iso), kind=kind, level_cm=level)


def at(h, m=0, s=0):
    return datetime(2026, 10, 14, h, m, s, tzinfo=UTC)


H1 = ext("2026-10-14T06:00:00+00:00", "high", 100)
L1 = ext("2026-10-14T12:00:00+00:00", "low", -80)
H2 = ext("2026-10-14T18:00:00+00:00", "high", 100)
SERIES = [H1, L1, H2]


def test_exact_extremes():
    assert estimate_tide_level(SERIES, at(6)) == 100
    assert estimate_tide_level(SERIES, at(12)) == -80
    assert estimate_tide_level(SERIES, at(18)) == 100


def test_halfway():
    value = estimate_tide_level(SERIES, at(9))
    assert value == 10
    assert 9 <= value <= 11


def test_quarter():
    assert estimate_tide_level(SERIES, at(7, 30)) == 74


def test_outside_and_empty():
    assert estimate_tide_level(SERIES, at(5, 59)) is None
    assert estimate_tide_level(SERIES, at(18, 1)) is None
    assert estimate_tide_level([], at(9)) is None
    assert estimate_tide_level([H1], at(7)) is None


def test_gap_limit():
    high = ext("2026-10-14T00:00:00+00:00", "high", 100)
    over = ext("2026-10-14T09:00:01+00:00", "low", -80)
    exact = ext("2026-10-14T09:00:00+00:00", "low", -80)
    assert estimate_tide_level([high, over], at(4, 30)) is None
    assert estimate_tide_level([high, exact], at(4, 30)) is not None


def test_monotonic():
    minute = timedelta(minutes=1)
    t = at(6)
    prev = estimate_tide_level(SERIES, t)
    while t < at(12):
        t += minute
        cur = estimate_tide_level(SERIES, t)
        assert cur <= prev
        prev = cur
    while t < at(18):
        t += minute
        cur = estimate_tide_level(SERIES, t)
        assert cur >= prev
        prev = cur


def test_order_independent():
    for h in range(5, 20):
        assert estimate_tide_level(SERIES[::-1], at(h, 20)) == estimate_tide_level(
            SERIES, at(h, 20)
        )


def test_low_low_agger():
    a = ext("2026-10-14T12:00:00+00:00", "low", -60)
    b = ext("2026-10-14T15:00:00+00:00", "low", -55)
    assert estimate_tide_level([a, b], at(13, 30)) == -57


def test_errors():
    with pytest.raises(ValueError):
        estimate_tide_level(SERIES, datetime(2026, 10, 14, 9))  # noqa: DTZ001
    with pytest.raises(ValueError):
        estimate_tide_level([H1, ext("2026-10-14T12:00:00+00:00", "low", 1, station="y")], at(9))
    with pytest.raises(ValueError):
        estimate_tide_level([H1, ext("2026-10-14T06:00:00+00:00", "high", 99)], at(9))


def test_same_instant_same_level_ok():
    assert estimate_tide_level([H1, H1, L1], at(9)) == 10


def test_offset_at():
    local = datetime(2026, 10, 14, 11, 0, tzinfo=timezone(timedelta(hours=2)))
    assert estimate_tide_level(SERIES, local) == estimate_tide_level(SERIES, at(9))


def test_model():
    with pytest.raises(ValidationError):
        TideExtreme(station="x", at=datetime(2026, 1, 1), kind="high", level_cm=1)  # noqa: DTZ001
    e = ext("2026-10-14T12:00:00+01:00", "high", 5)
    assert e.at == at(11)
    assert e.at.tzinfo is UTC
    for bad in (12.0, True, 1001):
        with pytest.raises(ValidationError):
            TideExtreme(station="x", at=at(1), kind="high", level_cm=bad)
    with pytest.raises(ValidationError):
        TideExtreme(station="x", at=at(1), kind="agger", level_cm=1)
    with pytest.raises(ValidationError):
        TideExtreme(station="x", at=at(1), kind="high", level_cm=1, extra=1)
    with pytest.raises(ValidationError):
        e.level_cm = 3


def test_rows():
    row = {
        "station": "x",
        "at": "2026-10-14T11:00:00+00:00",
        "kind": "high",
        "level_cm": 90,
        "fetched_at": "...",
    }
    assert TideExtreme.from_row(row).level_cm == 90
    e = ext("2026-10-14T06:00:00+00:00", "low", -3)
    assert TideExtreme.from_row(json.loads(to_json(e.to_row()))) == e
    assert set(e.to_row()) == {"station", "at", "kind", "level_cm"}
