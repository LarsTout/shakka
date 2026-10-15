"""Tests for shakka.domain.dedup (WP-08)."""

import inspect
import json
import re
import typing
from datetime import timedelta, timezone

import pytest
from pydantic import ValidationError

from alert_fixtures import go_run, migration_sql, rule
from dedup_fixtures import NOW, entry, go_hour, make_window, persist, utc
from shakka.domain import dedup
from shakka.domain.alerts import Window, find_windows
from shakka.domain.consensus import Confidence
from shakka.domain.dedup import (
    ALERT_STATE_COLUMNS,
    SNAPSHOT_KEYS,
    AlertEvent,
    AlertEventKind,
    AlertStateEntry,
    AlertStatus,
    WindowSnapshot,
    classify_change,
    diff_windows,
    snapshot_window,
)
from shakka.domain.defaults import LOCAL_TZ
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


# diff_windows (AC-1 .. AC-5)

D = (2026, 7, 15)


def t(h: int, extra: int = 0):
    return utc(*D, h) + timedelta(minutes=extra)


K = AlertEventKind
BASE_WINDOW = make_window(t(10), 6, winds=[16.0, 18.0, 20.0, 22.0, 20.0, 18.0])
B = snapshot_window(BASE_WINDOW)


def _kinds(r):
    return [(e.kind, e.state_index) for e in r.events]


@pytest.mark.parametrize(
    ("prev", "cur", "now"),
    [
        ([], [make_window(t(10), 4)], NOW),
        ([], [make_window(t(10), 3), make_window(t(14), 2)], NOW),
        ([entry(t(10), t(16), id="a1")], [make_window(t(12), 4)], t(11, 30)),
        (
            [
                entry(
                    t(9),
                    t(11),
                    status="cancelled",
                    last_event=AlertEventKind.CANCELLED,
                    id="c1",
                )
            ],
            [make_window(t(13), 3)],
            NOW,
        ),
    ],
)
def test_idempotent(prev, cur, now):
    r1 = diff_windows(prev, cur, now=now)
    stored = persist(r1.new_state)
    r2 = diff_windows(stored, cur, now=now)
    assert r2.events == []
    assert r2.new_state == stored


def test_running_window_hourly_sequence():
    evals = go_run(t(10), 4)
    state: list[AlertStateEntry] = []
    total = []
    statuses = {}
    for hh in (8, 9, 10, 11, 12, 13, 14):
        now = t(hh, 17)
        windows = find_windows(evals, rule(min_go_hours=2), now=now)
        r = diff_windows(state, windows, now=now)
        total += r.events
        state = persist(r.new_state)
        statuses[hh] = state[0] if state else None
    assert [e.kind for e in total] == [K.NEW]
    assert statuses[12].status == "active"
    assert statuses[12].window_start == t(10)
    assert statuses[14].status == "expired"


def test_new_window():
    w = make_window(t(10), 4)
    r = diff_windows([], [w], now=NOW)
    assert len(r.events) == 1
    ev = r.events[0]
    assert (ev.kind, ev.state_index, ev.previous) == (K.NEW, 0, None)
    assert ev.current == snapshot_window(w)
    e = r.new_state[0]
    assert (e.id, e.status, e.window_start, e.window_end) == (None, "active", w.start, w.end)
    assert (e.last_event, e.last_notified_at) == (K.NEW, None)


def test_cancel_before_start():
    e = entry(t(10), t(14), id="a")
    r = diff_windows([e], [], now=NOW)
    assert len(r.events) == 1
    assert r.events[0].kind == K.CANCELLED
    assert r.events[0].current is None
    assert r.events[0].previous == e.snapshot
    assert r.new_state[0].status == "cancelled"
    assert r.new_state[0].last_event == K.CANCELLED
    assert r.new_state[0].snapshot == e.snapshot


def test_expired_no_event():
    r = diff_windows([entry(t(2), t(5), id="a")], [], now=NOW)
    assert r.events == []
    assert r.new_state[0].status == "expired"
    r = diff_windows([entry(t(2), t(6), id="a")], [], now=NOW)
    assert r.events == []
    assert r.new_state[0].status == "expired"


def test_cancelled_comes_back():
    r1 = diff_windows([entry(t(10), t(14), id="a")], [], now=NOW)
    stored = persist(r1.new_state)
    r2 = diff_windows(stored, [make_window(t(11), 4)], now=NOW)
    assert _kinds(r2) == [(K.NEW, 0)]
    e = r2.new_state[0]
    assert (e.id, e.status, e.last_event) == ("a", "active", K.NEW)
    assert e.snapshot == snapshot_window(make_window(t(11), 4))
    assert len(r2.new_state) == 1


def test_begun_not_cancelled():
    e = entry(t(10), t(14), id="a")
    r = diff_windows([e], [], now=t(10))
    assert r.events == []
    assert r.new_state == [e]
    r = diff_windows([e], [], now=t(14))
    assert r.events == []
    assert r.new_state[0].status == "expired"


def test_active_beats_cancelled():
    c = entry(t(9), t(12), status="cancelled", last_event=K.CANCELLED, id="c")
    a = entry(t(13), t(16), id="a")
    r = diff_windows([c, a], [make_window(t(11), 5)], now=NOW)
    assert _kinds(r) == [(K.IMPROVED, 1)]
    assert r.new_state[0] == c


def test_shift_without_overlap():
    r = diff_windows([entry(t(10), t(12), id="a")], [make_window(t(14), 2)], now=NOW)
    assert _kinds(r) == [(K.CANCELLED, 0), (K.NEW, 1)]


def _winds(n, lo=16.0, hi=22.0):
    """n hours of wind with minimum lo (first hour) and maximum hi (second hour)."""
    return [lo, hi] + [(lo + hi) / 2] * (n - 2)


def mw(start_h, end_h, lo=16.0, hi=22.0):
    n = end_h - start_h
    return make_window(t(start_h), n, winds=_winds(n, lo, hi))


def _shifted(start_h, end_h, lo=16.0, hi=22.0):
    return snapshot_window(mw(start_h, end_h, lo, hi))


B = _shifted(10, 16)

SMALL = {
    "begin+1": (11, 16, 16.0, 22.0),
    "begin-1": (9, 16, 16.0, 22.0),
    "end+1": (10, 17, 16.0, 22.0),
    "end-1": (10, 15, 16.0, 22.0),
    "later": (11, 17, 16.0, 22.0),
    "earlier": (9, 15, 16.0, 22.0),
    "both-in": (11, 15, 16.0, 22.0),
    "wind+2": (10, 16, 18.0, 24.0),
    "wind-2": (10, 16, 14.0, 20.0),
    "min-3.9": (10, 16, 12.1, 22.0),
    "max+3.9": (10, 16, 16.0, 25.9),
}


@pytest.mark.parametrize("name", list(SMALL))
def test_small_changes_no_event(name):
    s, e, lo, hi = SMALL[name]
    cur = mw(s, e, lo, hi)
    assert classify_change(B, snapshot_window(cur), now=NOW) is None
    r = diff_windows([entry(t(10), t(16), id="b1", snapshot=B)], [cur], now=NOW)
    assert r.events == []
    assert r.new_state[0].snapshot == B


THRESH = [
    ("begin-2", (8, 16, 16.0, 22.0), K.IMPROVED),
    ("begin+2", (12, 16, 16.0, 22.0), K.WORSENED),
    ("end+2", (10, 18, 16.0, 22.0), K.IMPROVED),
    ("end-2", (10, 14, 16.0, 22.0), K.WORSENED),
    ("min+4", (10, 16, 20.0, 22.0), K.IMPROVED),
    ("min-4", (10, 16, 12.0, 22.0), K.WORSENED),
    ("max+4", (10, 16, 16.0, 26.0), K.IMPROVED),
    ("max-4", (10, 16, 16.0, 18.0), K.WORSENED),
]


@pytest.mark.parametrize(("name", "spec", "kind"), THRESH)
def test_threshold_events(name, spec, kind):
    s, e, lo, hi = spec
    cur = mw(s, e, lo, hi)
    cs = snapshot_window(cur)
    assert classify_change(B, cs, now=NOW) == kind
    r = diff_windows([entry(t(10), t(16), id="b1", snapshot=B)], [cur], now=NOW)
    assert len(r.events) == 1
    ev = r.events[0]
    assert (ev.kind, ev.previous, ev.current, ev.state_index) == (kind, B, cs, 0)
    assert r.new_state[0].snapshot == cs
    assert r.new_state[0].last_event == kind


def test_threshold_float_noise():
    prev = snapshot_window(make_window(t(10), 2, winds=[14.2, 20.0]))
    cur = snapshot_window(make_window(t(10), 2, winds=[18.2, 20.0]))
    assert classify_change(prev, cur, now=NOW) == K.IMPROVED


def test_worsened_wins():
    assert classify_change(B, _shifted(8, 16, 12.0, 22.0), now=NOW) == K.WORSENED
    assert classify_change(B, _shifted(10, 19, 16.0, 17.0), now=NOW) == K.WORSENED
    assert classify_change(B, _shifted(12, 18), now=NOW) == K.WORSENED
    assert classify_change(B, _shifted(8, 14), now=NOW) == K.WORSENED
    r = diff_windows([entry(t(10), t(16), id="b1", snapshot=B)], [mw(12, 18)], now=NOW)
    assert _kinds(r) == [(K.WORSENED, 0)]


def test_ignored_fields():
    def s(**kw):
        base = dict(
            start=t(10),
            end=t(14),
            wind_min_kn=16.0,
            wind_max_kn=20.0,
            gust_max_kn=20.0,
            dir_deg=270,
            dir_class=DirClass.ONSHORE,
            confidence=Confidence.HIGH,
        )
        base.update(kw)
        return WindowSnapshot(**base)

    assert classify_change(s(gust_max_kn=None), s(gust_max_kn=30.0), now=NOW) is None
    assert classify_change(s(), s(gust_max_kn=35.0), now=NOW) is None
    assert classify_change(s(), s(confidence=Confidence.MEDIUM), now=NOW) is None
    assert classify_change(s(), s(dir_deg=225, dir_class=DirClass.SIDE_ONSHORE), now=NOW) is None


def test_wind_ignored_once_begun():
    now = t(11, 30)
    for winds in ([22.0, 24.0, 26.0, 25.0], [10.0, 12.0, 14.0, 12.0]):
        cur = make_window(t(12), 4, winds=winds)
        assert classify_change(B, snapshot_window(cur), now=now) is None
        r = diff_windows([entry(t(10), t(16), id="b1", snapshot=B)], [cur], now=now)
        assert r.events == []
        assert r.new_state[0].window_start == t(10)
        assert r.new_state[0].snapshot == B
    up = snapshot_window(make_window(t(10), 6, winds=[22.0, 24.0, 26.0, 25.0, 23.0, 22.0]))
    down = snapshot_window(make_window(t(10), 6, winds=[10.0, 12.0, 14.0, 12.0, 11.0, 10.0]))
    assert classify_change(B, up, now=NOW) == K.IMPROVED
    assert classify_change(B, down, now=NOW) == K.WORSENED


def test_classify_change_now_timezone():
    base = t(11, 30)
    c1 = _shifted(13, 16)
    c2 = _shifted(14, 16)
    for now in (
        base,
        base.astimezone(LOCAL_TZ),
        base.astimezone(timezone(timedelta(hours=5, minutes=30))),
    ):
        assert classify_change(B, c1, now=now) is None
        assert classify_change(B, c2, now=now) == K.WORSENED
    with pytest.raises(ValueError):
        classify_change(B, c1, now=base.replace(tzinfo=None))


def test_one_hour_window_shift():
    e = entry(t(10), t(11), id="h1")
    r = diff_windows([e], [make_window(t(11), 1)], now=NOW)
    assert _kinds(r) == [(K.CANCELLED, 0), (K.NEW, 1)]
    assert diff_windows([e], [make_window(t(9), 2)], now=NOW).events == []
    assert diff_windows([e], [make_window(t(10), 2)], now=NOW).events == []


def test_drift_accumulates():
    kinds = []
    state: list[AlertStateEntry] = []
    for s in (10, 11, 12):
        r = diff_windows(state, [make_window(t(s), 6)], now=NOW)
        kinds.append([e.kind for e in r.events])
        state = persist(r.new_state)
        if s == 12:
            assert r.events[0].previous.start == t(10)
    assert kinds == [[K.NEW], [], [K.WORSENED]]


def test_split_equal():
    r = diff_windows(
        [entry(t(10), t(18), id="a")], [make_window(t(10), 3), make_window(t(15), 3)], now=NOW
    )
    assert _kinds(r) == [(K.WORSENED, 0), (K.NEW, 1)]
    assert (r.new_state[0].window_start, r.new_state[0].window_end) == (t(10), t(13))
    assert (r.new_state[1].window_start, r.new_state[1].window_end) == (t(15), t(18))
    assert r.new_state[1].id is None


def test_split_unequal():
    r = diff_windows(
        [entry(t(10), t(19), id="a")], [make_window(t(10), 2), make_window(t(13), 6)], now=NOW
    )
    assert _kinds(r) == [(K.WORSENED, 0), (K.NEW, 1)]
    assert (r.new_state[0].window_start, r.new_state[0].window_end) == (t(13), t(19))
    assert (r.new_state[1].window_start, r.new_state[1].window_end) == (t(10), t(12))


def test_merge():
    r = diff_windows(
        [entry(t(10), t(13), id="a"), entry(t(15), t(18), id="b")],
        [make_window(t(10), 8)],
        now=NOW,
    )
    assert _kinds(r) == [(K.IMPROVED, 0)]
    assert r.new_state[0].window_end == t(18)
    assert r.new_state[1].status == "expired"
    assert len(r.new_state) == 2


def test_split_begun():
    now = t(11, 30)
    r = diff_windows(
        [entry(t(10), t(18), id="a")], [make_window(t(13), 2), make_window(t(16), 2)], now=now
    )
    assert _kinds(r) == [(K.WORSENED, 0), (K.NEW, 1)]
    assert r.new_state[0].window_start == t(10)
    assert r.new_state[0].window_end == t(15)


def _stable(r):
    return {(e.id or f"new-{e.window_start}"): e for e in r.new_state}


def test_deterministic_order():
    prev = [entry(t(10), t(13), id="a"), entry(t(15), t(18), id="b")]
    cur = [make_window(t(10), 8)]
    r1 = diff_windows(prev, cur, now=NOW)
    assert r1 == diff_windows(prev, cur, now=NOW)
    cur2 = [make_window(t(10), 3), make_window(t(15), 2)]
    assert diff_windows(prev, cur2, now=NOW) == diff_windows(prev, cur2[::-1], now=NOW)
    ra = diff_windows(prev, cur, now=NOW)
    rb = diff_windows(prev[::-1], cur, now=NOW)
    assert _stable(ra) == _stable(rb)
    key = lambda r: sorted((r.new_state[e.state_index].id, e.kind) for e in r.events)  # noqa: E731
    assert key(ra) == key(rb)


def test_invalid_input():
    good = make_window(t(10), 2)
    with pytest.raises(ValueError):
        diff_windows([], [good], now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        diff_windows([entry(t(10), t(12), spot_id="other")], [good], now=NOW)
    with pytest.raises(ValueError):
        diff_windows([entry(t(10), t(12), id="x"), entry(t(14), t(16), id="x")], [], now=NOW)
    with pytest.raises(ValueError):
        diff_windows([], [make_window(t(10), 3), make_window(t(12), 2)], now=NOW)
    with pytest.raises(ValueError):
        diff_windows([], [make_window(t(10), 2)], now=t(10, 30))
    assert diff_windows([], [make_window(t(11), 2)], now=t(10, 30)).events != []
    empty = diff_windows([], [], now=NOW)
    assert empty == dedup.DiffResult(events=[], new_state=[])
    prev = [entry(t(10), t(12), id="x")]
    cur = [make_window(t(10), 2)]
    diff_windows(prev, cur, now=NOW)
    assert prev == [entry(t(10), t(12), id="x")]
    assert cur == [make_window(t(10), 2)]


def test_no_bypass_parameters():
    for fn in (diff_windows, classify_change, snapshot_window):
        for name in inspect.signature(fn).parameters:
            assert not any(w in name for w in ("offshore", "allow", "force", "unsafe")), name
    assert inspect.signature(diff_windows).parameters["now"].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(classify_change).parameters["now"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )
