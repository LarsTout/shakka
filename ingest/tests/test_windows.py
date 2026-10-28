"""WP-07 AC-3 and AC-4: go windows."""

from datetime import UTC, datetime, time, timedelta
from itertools import combinations

import pytest
from pydantic import ValidationError

from alert_fixtures import SPOT_ID, H, go_run, hour, rule, utc
from evaluation_fixtures import make_spot, model_hours
from shakka.domain.alerts import AlertRuleOverride, Window, find_windows, resolve_rule, rider_limits
from shakka.domain.defaults import LOCAL_TZ
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass
from shakka.domain.evaluation import Verdict, evaluate_spot

NOW = utc(2026, 7, 15, 6)  # Wednesday 08:00 local


def spans(windows: list[Window]) -> list[tuple[datetime, datetime]]:
    return [(w.start, w.end) for w in windows]


def test_three_go_hours_min_two() -> None:
    ws = find_windows(go_run(utc(2026, 7, 15, 10), 3), rule(min_go_hours=2), now=NOW)
    assert spans(ws) == [(utc(2026, 7, 15, 10), utc(2026, 7, 15, 13))]
    assert len(ws[0].hours) == 3


def test_single_go_hour_no_window() -> None:
    assert find_windows(go_run(utc(2026, 7, 15, 10), 1), rule(), now=NOW) == []


def test_go_marginal_go_min_one() -> None:
    evs = [
        hour(utc(2026, 7, 15, 10)),
        hour(utc(2026, 7, 15, 11), "marginal"),
        hour(utc(2026, 7, 15, 12)),
    ]
    ws = find_windows(evs, rule(min_go_hours=1), now=NOW)
    assert spans(ws) == [
        (utc(2026, 7, 15, 10), utc(2026, 7, 15, 11)),
        (utc(2026, 7, 15, 12), utc(2026, 7, 15, 13)),
    ]


def test_weekend_filter_local_date() -> None:
    evs = go_run(utc(2026, 7, 17, 20), 4) + go_run(utc(2026, 7, 19, 21), 2)
    ws = find_windows(evs, rule(min_go_hours=1, weekdays={6, 7}), now=utc(2026, 7, 17, 6))
    assert spans(ws) == [
        (utc(2026, 7, 17, 22), utc(2026, 7, 18, 0)),
        (utc(2026, 7, 19, 21), utc(2026, 7, 19, 22)),
    ]


def test_earliest_17_summer() -> None:
    ws = find_windows(
        go_run(utc(2026, 7, 15, 14), 3),
        rule(min_go_hours=1, earliest_local=time(17, 0)),
        now=NOW,
    )
    assert spans(ws) == [(utc(2026, 7, 15, 15), utc(2026, 7, 15, 17))]


def test_earliest_17_winter() -> None:
    ws = find_windows(
        go_run(utc(2026, 11, 4, 15), 3),
        rule(min_go_hours=1, earliest_local=time(17, 0)),
        now=utc(2026, 11, 4, 6),
    )
    assert spans(ws) == [(utc(2026, 11, 4, 16), utc(2026, 11, 4, 18))]


def test_latest_local() -> None:
    ws = find_windows(
        go_run(utc(2026, 7, 15, 17), 2),
        rule(min_go_hours=1, latest_local=time(20, 0)),
        now=NOW,
    )
    assert spans(ws) == [(utc(2026, 7, 15, 17), utc(2026, 7, 15, 18))]


def test_latest_end_of_day_from_row() -> None:
    row = {
        "enabled": None,
        "min_kn": None,
        "max_kn": None,
        "dir_classes": None,
        "weekdays": None,
        "earliest_local": "17:00:00",
        "latest_local": "24:00:00",
        "min_go_hours": 1,
        "days_ahead": None,
    }
    r = resolve_rule(make_spot(), None, AlertRuleOverride.from_row(row))
    ws = find_windows(go_run(utc(2026, 7, 15, 19), 3), r, now=NOW)
    assert spans(ws) == [(utc(2026, 7, 15, 19), utc(2026, 7, 15, 22))]


def test_days_ahead_one() -> None:
    ws = find_windows(
        go_run(utc(2026, 7, 16, 20), 4),
        rule(min_go_hours=1, days_ahead=1),
        now=utc(2026, 7, 15, 8),
    )
    assert spans(ws) == [(utc(2026, 7, 16, 20), utc(2026, 7, 16, 22))]


def test_days_ahead_zero_and_local_today() -> None:
    now = utc(2026, 7, 15, 22) + timedelta(minutes=30)
    evs = [hour(utc(2026, 7, 16, 8)), hour(utc(2026, 7, 16, 22))]
    ws = find_windows(evs, rule(min_go_hours=1, days_ahead=0), now=now)
    assert spans(ws) == [(utc(2026, 7, 16, 8), utc(2026, 7, 16, 9))]


def test_hours_before_now_excluded() -> None:
    now = utc(2026, 7, 15, 10) + timedelta(minutes=17)
    ws = find_windows(go_run(utc(2026, 7, 15, 9), 4), rule(min_go_hours=1), now=now)
    assert spans(ws) == [(utc(2026, 7, 15, 11), utc(2026, 7, 15, 13))]


def test_now_on_whole_hour() -> None:
    ws = find_windows(
        go_run(utc(2026, 7, 15, 10), 3), rule(min_go_hours=1), now=utc(2026, 7, 15, 10)
    )
    assert spans(ws) == [(utc(2026, 7, 15, 11), utc(2026, 7, 15, 13))]


def test_missing_hour_splits() -> None:
    evs = go_run(utc(2026, 7, 15, 10), 2) + go_run(utc(2026, 7, 15, 13), 2)
    ws = find_windows(evs, rule(min_go_hours=2), now=NOW)
    assert spans(ws) == [
        (utc(2026, 7, 15, 10), utc(2026, 7, 15, 12)),
        (utc(2026, 7, 15, 13), utc(2026, 7, 15, 15)),
    ]


def test_dir_class_outside_rule_splits() -> None:
    evs = [
        hour(utc(2026, 7, 15, 10)),
        hour(utc(2026, 7, 15, 11)),
        hour(utc(2026, 7, 15, 12), dir_class=DirClass.ONSHORE),
        hour(utc(2026, 7, 15, 13)),
    ]
    ws = find_windows(evs, rule(min_go_hours=1, dir_classes={DirClass.SIDESHORE}), now=NOW)
    assert spans(ws) == [
        (utc(2026, 7, 15, 10), utc(2026, 7, 15, 12)),
        (utc(2026, 7, 15, 13), utc(2026, 7, 15, 14)),
    ]


def test_exact_min_length() -> None:
    r = rule(min_go_hours=3)
    assert len(find_windows(go_run(utc(2026, 7, 15, 10), 3), r, now=NOW)) == 1
    assert find_windows(go_run(utc(2026, 7, 15, 10), 2), r, now=NOW) == []


def test_dst_fall_back_continuous() -> None:
    ws = find_windows(
        go_run(utc(2026, 10, 25, 0), 3), rule(min_go_hours=3), now=utc(2026, 10, 24, 20)
    )
    assert spans(ws) == [(utc(2026, 10, 25, 0), utc(2026, 10, 25, 3))]
    assert len(ws[0].hours) == 3


def test_dst_spring_forward_continuous() -> None:
    ws = find_windows(
        go_run(utc(2027, 3, 28, 0), 3), rule(min_go_hours=3), now=utc(2027, 3, 27, 20)
    )
    assert spans(ws) == [(utc(2027, 3, 28, 0), utc(2027, 3, 28, 3))]
    assert [h.valid_at.astimezone(LOCAL_TZ).hour for h in ws[0].hours] == [1, 3, 4]


def test_unsorted_input_same_result() -> None:
    evs = go_run(utc(2026, 7, 15, 10), 3) + go_run(utc(2026, 7, 15, 14), 2)
    r = rule(min_go_hours=2)
    reversed_evs = list(reversed(evs))
    snapshot = list(reversed_evs)
    assert find_windows(reversed_evs, r, now=NOW) == find_windows(evs, r, now=NOW)
    assert reversed_evs == snapshot


def test_invalid_input() -> None:
    r = rule(min_go_hours=1)
    evs = go_run(utc(2026, 7, 15, 10), 2)
    with pytest.raises(ValueError):
        find_windows(evs, r, now=datetime(2026, 7, 15, 6))  # noqa: DTZ001
    with pytest.raises(ValueError):
        find_windows([evs[0], hour(utc(2026, 7, 15, 11), spot_id="other")], r, now=NOW)
    with pytest.raises(ValueError):
        find_windows([evs[0], evs[0]], r, now=NOW)
    assert find_windows([], r, now=NOW) == []


def test_now_other_timezone() -> None:
    evs = go_run(utc(2026, 7, 15, 10), 3)
    r = rule(min_go_hours=1)
    assert find_windows(evs, r, now=NOW.astimezone(LOCAL_TZ)) == find_windows(evs, r, now=NOW)


_SUBSETS = [frozenset(c) for n in range(1, 4) for c in combinations(sorted(RIDABLE_DIR_CLASSES), n)]
_CYCLE = [
    ("go", DirClass.ONSHORE),
    ("go", DirClass.SIDE_ONSHORE),
    ("go", DirClass.SIDESHORE),
    ("go", None),
    ("marginal", DirClass.SIDESHORE),
    ("no_go", DirClass.OFFSHORE),
    ("no_go", DirClass.SIDE_OFFSHORE),
    ("no_go", None),
]


@pytest.mark.parametrize("subset", _SUBSETS, ids=lambda s: "+".join(sorted(c.value for c in s)))
def test_safety_grid(subset: frozenset[DirClass]) -> None:
    start = utc(2026, 7, 15, 8)
    evs = [hour(start + i * H, v, d) for i, (v, d) in enumerate(_CYCLE * 3)]
    ws = find_windows(evs, rule(min_go_hours=1, dir_classes=subset), now=NOW)
    assert ws
    in_windows = [h for w in ws for h in w.hours]
    for h in in_windows:
        assert h.verdict == Verdict.GO
        assert h.dir_class in subset
        assert h.dir_class not in (DirClass.SIDE_OFFSHORE, DirClass.OFFSHORE, None)
    expected = [e for e in evs if e.verdict == Verdict.GO and e.dir_class in subset]
    assert sorted(h.valid_at for h in in_windows) == sorted(e.valid_at for e in expected)
    assert len({h.valid_at for h in in_windows}) == len(in_windows)


def test_go_without_dir_class_not_counted() -> None:
    evs = [
        hour(utc(2026, 7, 15, 10)),
        hour(utc(2026, 7, 15, 11), dir_class=None),
        hour(utc(2026, 7, 15, 12)),
    ]
    ws = find_windows(evs, rule(min_go_hours=1), now=NOW)
    assert spans(ws) == [
        (utc(2026, 7, 15, 10), utc(2026, 7, 15, 11)),
        (utc(2026, 7, 15, 12), utc(2026, 7, 15, 13)),
    ]


def _forecasts(dir_deg: int) -> list:
    out = []
    for i in range(6):
        out += model_hours(utc(2026, 7, 15, 8) + i * H, wind=20.0, gust=22.0, dir_deg=dir_deg)
    return out


def test_integration_evaluate_spot() -> None:
    spot = make_spot()
    r = rule()
    evs = evaluate_spot(spot, _forecasts(270), [], rider_limits(r))
    ws = find_windows(evs, r, now=NOW)
    assert spans(ws) == [(utc(2026, 7, 15, 8), utc(2026, 7, 15, 14))]
    for deg in (90, 135):
        bad = evaluate_spot(spot, _forecasts(deg), [], rider_limits(r))
        for subset in _SUBSETS:
            assert find_windows(bad, rule(dir_classes=subset), now=NOW) == []
    r22 = rule(min_kn=22)
    evs22 = evaluate_spot(spot, _forecasts(270), [], rider_limits(r22))
    assert find_windows(evs22, r22, now=NOW) == []


def test_window_invariants() -> None:
    good = go_run(utc(2026, 7, 15, 10), 2)
    start, end = utc(2026, 7, 15, 10), utc(2026, 7, 15, 12)

    def make(**kw: object) -> Window:
        data = {"spot_id": SPOT_ID, "start": start, "end": end, "hours": tuple(good)}
        data.update(kw)
        return Window(**data)

    w = make()
    assert w.end == end
    bad_hours = [
        (hour(utc(2026, 7, 15, 10)), hour(utc(2026, 7, 15, 11), "marginal")),
        (hour(utc(2026, 7, 15, 10)), hour(utc(2026, 7, 15, 11), dir_class=None)),
        (hour(utc(2026, 7, 15, 10)), hour(utc(2026, 7, 15, 12))),
        (hour(utc(2026, 7, 15, 10)), hour(utc(2026, 7, 15, 11), spot_id="other")),
    ]
    for hrs in bad_hours:
        with pytest.raises(ValidationError):
            make(hours=hrs)
    with pytest.raises(ValidationError):
        make(hours=())
    with pytest.raises(ValidationError):
        make(start=utc(2026, 7, 15, 9))
    with pytest.raises(ValidationError):
        make(end=utc(2026, 7, 15, 13))
    with pytest.raises(ValidationError):
        make(start=datetime(2026, 7, 15, 10))  # noqa: DTZ001
    with pytest.raises(ValidationError):
        w.model_copy(update={"end": utc(2026, 7, 15, 15)})
    assert w.start.tzinfo is UTC or w.start.utcoffset() == timedelta(0)


def test_disabled_returns_empty() -> None:
    assert find_windows(go_run(utc(2026, 7, 15, 10), 5), rule(enabled=False), now=NOW) == []


def test_disabled_skips_input_checks() -> None:
    evs = [hour(utc(2026, 7, 15, 10)), hour(utc(2026, 7, 15, 11), spot_id="other")]
    assert find_windows(evs, rule(enabled=False), now=NOW) == []
    with pytest.raises(ValueError):
        find_windows(evs, rule(enabled=False), now=datetime(2026, 7, 15, 6))  # noqa: DTZ001


def test_days_ahead_seven_reaches_local_today_plus_seven() -> None:
    evs = go_run(utc(2026, 7, 22, 10), 3)
    ws = find_windows(evs, rule(min_go_hours=1, days_ahead=7), now=NOW)
    assert spans(ws) == [(utc(2026, 7, 22, 10), utc(2026, 7, 22, 13))]
    assert find_windows(evs, rule(min_go_hours=1, days_ahead=6), now=NOW) == []
