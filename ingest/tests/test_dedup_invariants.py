"""AC-5: invariants of diff_windows over two deterministic scenario grids (WP-08)."""

import itertools
from datetime import timedelta

import pytest

from dedup_fixtures import NOW, entry, make_window, persist, utc, windows_from_pattern
from shakka.domain.alerts import Window
from shakka.domain.dedup import (
    AlertEventKind,
    AlertStateEntry,
    DiffResult,
    diff_windows,
)

K = AlertEventKind
DAY = utc(2026, 7, 15, 10)


def _inside(w: Window, e: AlertStateEntry) -> bool:
    return e.window_start <= w.start and w.end <= e.window_end


def check_invariants(prev: list[AlertStateEntry], cur: list[Window], now, r: DiffResult) -> None:
    live = [e for e in r.new_state if e.status == "active" and e.window_end > now]
    # I1
    for w in cur:
        owners = [e for e in r.new_state if e.status == "active" and _inside(w, e)]
        assert len(owners) == 1, (w.start, w.end)
    # I2
    for a, b in itertools.combinations(live, 2):
        assert a.window_end <= b.window_start or b.window_end <= a.window_start
    # I3
    idxs = [ev.state_index for ev in r.events]
    assert len(idxs) == len(set(idxs))
    for ev in r.events:
        e = r.new_state[ev.state_index]
        if ev.kind == K.CANCELLED:
            assert e.status == "cancelled"
        else:
            assert e.status == "active"
            assert e.last_event == ev.kind
    # I4
    matched = set()
    for w in cur:
        for i, p in enumerate(prev):
            ns = r.new_state[i] if i < len(r.new_state) else None
            if p.status == "active" and ns is not None and ns.status == "active" and _inside(w, ns):
                matched.add((w.start, w.end))
    new_events = [ev for ev in r.events if ev.kind == K.NEW]
    assert len(new_events) == len(cur) - len(matched)
    spans = [(ev.current.start, ev.current.end) for ev in new_events]
    for a, b in itertools.combinations(spans, 2):
        assert a[1] <= b[0] or b[1] <= a[0]
    # I5
    for ev in r.events:
        if ev.kind == K.CANCELLED:
            assert prev[ev.state_index].window_start > now
    # I6
    assert len(r.new_state) >= len(prev)
    for i, p in enumerate(prev):
        assert r.new_state[i].id == p.id
    # I7
    stored = persist(r.new_state)
    again = diff_windows(stored, cur, now=now)
    assert again.events == []
    assert again.new_state == stored


def _patterns(n: int) -> list[str]:
    return ["".join("G" if c == "1" else "." for c in f"{x:0{n}b}") for x in range(2**n)]


def test_grid_a_not_begun():
    pats = _patterns(6)
    cache = {p: windows_from_pattern(DAY, p, now=NOW) for p in pats}
    for p1 in pats:
        r1 = diff_windows([], cache[p1], now=NOW)
        check_invariants([], cache[p1], NOW, r1)
        stored = persist(r1.new_state)
        for p2 in pats:
            r2 = diff_windows(stored, cache[p2], now=NOW)
            check_invariants(stored, cache[p2], NOW, r2)
            if p1 == p2:
                assert r2.events == [], (p1, p2)


def test_grid_b_begun():
    pats = _patterns(5)
    now0 = utc(2026, 7, 15, 9) + timedelta(minutes=30)
    now1 = utc(2026, 7, 15, 11) + timedelta(minutes=30)
    for p1 in pats:
        w1 = windows_from_pattern(DAY, p1, now=now0)
        r1 = diff_windows([], w1, now=now0)
        check_invariants([], w1, now0, r1)
        stored = persist(r1.new_state)
        for p2 in pats:
            w2 = windows_from_pattern(DAY, p2, now=now1)
            r2 = diff_windows(stored, w2, now=now1)
            check_invariants(stored, w2, now1, r2)


def _e(start, end, id, **kw):
    return entry(utc(2026, 7, 15, start), utc(2026, 7, 15, end), id=id, **kw)


def _mw(start, n):
    return make_window(utc(2026, 7, 15, start), n)


MID = utc(2026, 7, 15, 11) + timedelta(minutes=30)


def _states(r):
    return [(e.id, e.status, e.window_start.hour, e.window_end.hour) for e in r.new_state]


def _events(r):
    return [(ev.kind, ev.state_index) for ev in r.events]


def _by_id(r):
    return {(e.id or f"new-{e.window_start.hour}"): e for e in r.new_state}, sorted(
        (r.new_state[ev.state_index].id or "new", ev.kind) for ev in r.events
    )


CASES = {
    "half_split": (
        NOW,
        [_e(10, 18, "a"), _e(15, 18, "n")],
        [_mw(10, 3), _mw(15, 3)],
        [K.WORSENED, K.NEW],
        [0, 2],
        [("a", "active", 10, 13), ("n", "expired", 15, 18), (None, "active", 15, 18)],
    ),
    "same_start": (
        NOW,
        [_e(10, 14, "b"), _e(10, 16, "a")],
        [_mw(10, 6)],
        [],
        [],
        [("b", "expired", 10, 14), ("a", "active", 10, 16)],
    ),
    "begun_wins": (
        MID,
        [_e(10, 16, "x"), _e(12, 16, "a")],
        [_mw(12, 4)],
        [],
        [],
        [("x", "active", 10, 16), ("a", "expired", 12, 16)],
    ),
    "chain": (
        NOW,
        [_e(10, 14, "c"), _e(12, 16, "b"), _e(15, 18, "a")],
        [],
        [K.CANCELLED, K.CANCELLED],
        [0, 2],
        [("c", "cancelled", 10, 14), ("b", "expired", 12, 16), ("a", "cancelled", 15, 18)],
    ),
}


@pytest.mark.parametrize("name", list(CASES))
def test_overlap_repair(name):
    now, prev, cur, kinds, idxs, states = CASES[name]
    r = diff_windows(prev, cur, now=now)
    assert [ev.kind for ev in r.events] == kinds
    assert [ev.state_index for ev in r.events] == idxs
    assert _states(r) == states
    if name == "half_split":
        assert r.events[0].previous == prev[0].snapshot
        assert r.new_state[1].last_event == K.NEW
    if name == "begun_wins":
        assert r.new_state[0].window_start == utc(2026, 7, 15, 10)
    check_invariants(prev, cur, now, r)
    rev = diff_windows(prev[::-1], cur, now=now)
    assert _by_id(r) == _by_id(rev)
