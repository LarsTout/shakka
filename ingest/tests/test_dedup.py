"""Tests for shakka.domain.dedup (WP-08)."""

import json
import re
import typing
from datetime import timedelta

import pytest
from pydantic import ValidationError

from alert_fixtures import migration_sql
from dedup_fixtures import NOW, entry, go_hour, make_window, utc
from shakka.domain.alerts import Window
from shakka.domain.consensus import Confidence
from shakka.domain.dedup import (
    ALERT_STATE_COLUMNS,
    SNAPSHOT_KEYS,
    AlertEvent,
    AlertEventKind,
    AlertStateEntry,
    AlertStatus,
    WindowSnapshot,
    snapshot_window,
)
from shakka.domain.direction import DirClass

S_SUMMER = WindowSnapshot(
    start=utc(2026, 7, 18, 12),
    end=utc(2026, 7, 18, 16),
    wind_min_kn=16.0,
    wind_max_kn=22.4,
    gust_max_kn=27.5,
    dir_deg=225,
    dir_class=DirClass.SIDE_ONSHORE,
    confidence=Confidence.HIGH,
)
S_WINTER = WindowSnapshot(
    start=utc(2026, 11, 7, 11),
    end=utc(2026, 11, 7, 14),
    wind_min_kn=18.0,
    wind_max_kn=24.0,
    gust_max_kn=None,
    dir_deg=270,
    dir_class=DirClass.ONSHORE,
    confidence=Confidence.MEDIUM,
)
P_WINTER = WindowSnapshot(
    start=utc(2026, 11, 7, 11),
    end=utc(2026, 11, 7, 16),
    wind_min_kn=18.0,
    wind_max_kn=25.0,
    gust_max_kn=30.0,
    dir_deg=265,
    dir_class=DirClass.ONSHORE,
    confidence=Confidence.MEDIUM,
)


def _snap_kwargs(**over):
    base = S_SUMMER.model_dump()
    base.update(over)
    return base


def test_snapshot_window_basic():
    w = make_window(
        utc(2026, 7, 15, 10),
        4,
        winds=[14.0, 18.5, 22.0, 16.0],
        gusts=[None, 25.0, None, 30.5],
        dirs=[260, 270, 280, 270],
        classes=[DirClass.ONSHORE] * 4,
        confidences=[Confidence.HIGH, Confidence.MEDIUM, Confidence.HIGH, Confidence.HIGH],
    )
    s = snapshot_window(w)
    assert (s.wind_min_kn, s.wind_max_kn, s.gust_max_kn) == (14.0, 22.0, 30.5)
    assert s.dir_deg == 270
    assert s.dir_class == DirClass.ONSHORE
    assert s.confidence == Confidence.MEDIUM
    assert (s.start, s.end) == (w.start, w.end)


def test_snapshot_gust_unknown():
    s = snapshot_window(make_window(utc(2026, 7, 15, 10), 3, gusts=[None, None, None]))
    assert s.gust_max_kn is None


def test_snapshot_dir_wrap():
    s = snapshot_window(make_window(utc(2026, 7, 15, 10), 2, dirs=[350, 10]))
    assert s.dir_deg == 0
    s = snapshot_window(make_window(utc(2026, 7, 15, 10), 2, dirs=[0, 180]))
    assert s.dir_deg == 0
    s = snapshot_window(make_window(utc(2026, 7, 15, 10), 2, dirs=[90, 270]))
    assert s.dir_deg == 90


def test_snapshot_dir_class_mode_and_tie():
    o, so, ss = DirClass.ONSHORE, DirClass.SIDE_ONSHORE, DirClass.SIDESHORE
    t = utc(2026, 7, 15, 10)
    assert snapshot_window(make_window(t, 3, classes=[o, o, so])).dir_class == o
    assert snapshot_window(make_window(t, 4, classes=[o, o, ss, ss])).dir_class == ss
    assert snapshot_window(make_window(t, 2, classes=[so, o])).dir_class == so


@pytest.mark.parametrize("field", ["wind", "dir_deg", "confidence"])
def test_snapshot_window_invalid_hours(field):
    t = utc(2026, 7, 15, 10)
    good = go_hour(t)
    bad = go_hour(t + timedelta(hours=1), **{field: None})
    w = Window(spot_id="test-strand", start=t, end=t + timedelta(hours=2), hours=(good, bad))
    with pytest.raises(ValueError):
        snapshot_window(w)


def test_snapshot_rejects_offshore():
    for cls in (DirClass.OFFSHORE, DirClass.SIDE_OFFSHORE):
        with pytest.raises(ValidationError):
            WindowSnapshot(**_snap_kwargs(dir_class=cls))
        data = S_SUMMER.to_json()
        data["dir_class"] = cls.value
        with pytest.raises(ValidationError):
            WindowSnapshot.from_json(data)
        with pytest.raises(ValidationError):
            S_SUMMER.model_copy(update={"dir_class": cls})


@pytest.mark.parametrize(
    "over",
    [
        {"start": utc(2026, 7, 18, 12).replace(tzinfo=None)},
        {"start": utc(2026, 7, 18, 12) + timedelta(minutes=30)},
        {"end": utc(2026, 7, 18, 12)},
        {"wind_min_kn": 30.0},
        {"wind_min_kn": -1.0, "wind_max_kn": 5.0},
        {"wind_max_kn": float("nan")},
        {"dir_deg": 360},
        {"dir_deg": 225.0},
    ],
)
def test_snapshot_validation(over):
    with pytest.raises(ValidationError):
        WindowSnapshot(**_snap_kwargs(**over))


@pytest.mark.parametrize("s", [S_SUMMER, S_WINTER, P_WINTER])
def test_snapshot_json_roundtrip(s):
    data = s.to_json()
    assert tuple(data) == SNAPSHOT_KEYS
    assert WindowSnapshot.from_json(data) == s
    dumped = json.dumps(data)
    assert WindowSnapshot.from_json(json.loads(dumped)) == s


def test_snapshot_json_details():
    data = S_SUMMER.to_json()
    assert data["start"] == "2026-07-18T12:00:00Z"
    plus = dict(data, start="2026-07-18T12:00:00+00:00", end="2026-07-18T16:00:00+00:00")
    assert WindowSnapshot.from_json(plus) == S_SUMMER
    missing = {k: v for k, v in data.items() if k != "wind_max_kn"}
    with pytest.raises(ValueError, match="wind_max_kn"):
        WindowSnapshot.from_json(missing)
    assert WindowSnapshot.from_json(dict(data, extra=1)) == S_SUMMER


def test_entry_row_roundtrip():
    e = entry(utc(2026, 7, 18, 12), utc(2026, 7, 18, 16), id="a1", snapshot=S_SUMMER)
    row = e.to_row()
    assert tuple(row) == ALERT_STATE_COLUMNS
    assert row["snapshot"] == S_SUMMER.to_json()
    assert row["status"] == "active"
    assert row["last_event"] == "new"
    no_id = e.model_copy(update={"id": None}).to_row()
    assert "id" not in no_id
    assert tuple(no_id) == tuple(c for c in ALERT_STATE_COLUMNS if c != "id")
    pg = {
        "id": "a1",
        "user_id": "u1",
        "spot_id": "test-strand",
        "window_start": "2026-07-18T12:00:00+00:00",
        "window_end": "2026-07-18T16:00:00+00:00",
        "status": "active",
        "snapshot": S_SUMMER.to_json(),
        "last_event": "new",
        "last_notified_at": None,
        "created_at": "2026-07-15T06:00:00+00:00",
        "updated_at": "2026-07-15T06:00:00+00:00",
    }
    assert AlertStateEntry.from_row(pg) == e
    del pg["status"]
    with pytest.raises(ValueError, match="status"):
        AlertStateEntry.from_row(pg)


def _enum_values(constraint: str) -> set[str]:
    sql = migration_sql()
    chunk = sql[sql.index(constraint) :]
    m = re.search(r"in \(([^)]*)\)", chunk)
    assert m is not None
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def test_alert_state_enums_match_migration():
    assert _enum_values("alert_state_status_enum") == set(typing.get_args(AlertStatus))
    assert _enum_values("alert_state_last_event_enum") == {k.value for k in AlertEventKind}


def test_event_invariants():
    kw = {"spot_id": "test-strand", "state_index": 0}
    N, C = AlertEventKind.NEW, AlertEventKind.CANCELLED
    with pytest.raises(ValidationError):
        AlertEvent(kind=N, current=S_SUMMER, previous=S_WINTER, **kw)
    with pytest.raises(ValidationError):
        AlertEvent(kind=C, current=S_SUMMER, previous=S_WINTER, **kw)
    with pytest.raises(ValidationError):
        AlertEvent(kind=AlertEventKind.IMPROVED, current=S_SUMMER, previous=None, **kw)
    with pytest.raises(ValidationError):
        AlertEvent(kind=N, current=S_SUMMER, previous=None, spot_id="x", state_index=-1)
    AlertEvent(kind=N, current=S_SUMMER, previous=None, **kw)
    AlertEvent(kind=C, current=None, previous=S_SUMMER, **kw)


_ = NOW
