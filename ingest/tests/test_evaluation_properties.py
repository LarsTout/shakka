"""AC-9: invariants over a grid of spots, hours, model sets and directions."""

from datetime import UTC, datetime, timedelta

import pytest

from evaluation_fixtures import LIMITS, STATION, extremes, make_spot, model_hours, per_model
from shakka.domain.direction import DirClass
from shakka.domain.evaluation import (
    REASON_EFFECT,
    REASON_LABEL_NL,
    ReasonCode,
    Verdict,
    evaluate_spot,
    worst_verdict,
)
from shakka.domain.forecast import ModelKey as M

DAY = datetime(2026, 7, 15, 0, tzinfo=UTC)
HOURS = [DAY + timedelta(hours=h) for h in range(24)]
TIDES = extremes(
    (datetime(2026, 7, 14, 18, 30, tzinfo=UTC), "high", 100),
    (datetime(2026, 7, 15, 0, 30, tzinfo=UTC), "low", -80),
    (datetime(2026, 7, 15, 6, 30, tzinfo=UTC), "high", 100),
    (datetime(2026, 7, 15, 12, 30, tzinfo=UTC), "low", -80),
    (datetime(2026, 7, 15, 18, 30, tzinfo=UTC), "high", 100),
    (datetime(2026, 7, 16, 0, 30, tzinfo=UTC), "low", -80),
)
SPOTS = [
    make_spot(),
    make_spot(shore_normal_deg=None),
    make_spot(status="forbidden"),
    make_spot(status="limited"),
    make_spot(status=None),
    make_spot(tide_sensitive="prefer_low", rws_station=STATION),
    make_spot(
        season=[{"start": "05-01", "end": "09-30", "from_time": "10:00", "to_time": "18:00"}]
    ),
    make_spot(ridable_dirs=[{"from": 200, "to": 340}]),
]


def model_sets(at: datetime, d: int):
    return [
        model_hours(at, dir_deg=d),
        per_model(
            at,
            {
                M.KNMI: (8.0, 20.0, d),
                M.ICON: (22.0, 25.0, (d + 60) % 360),
                M.ECMWF: (30.0, 40.0, d),
                M.GFS: (14.0, 18.0, (d + 90) % 360),
            },
        ),
        model_hours(at, dir_deg=d, models=(M.ICON,)),
        model_hours(at, wind=None, gust=None, dir_deg=None),
    ]


def all_evaluations():
    for spot in SPOTS:
        for d in (0, 90, 180, 270):
            for idx in range(4):
                fc = [f for at in HOURS for f in [*model_sets(at, d)[idx]]]
                yield spot, evaluate_spot(spot, fc, TIDES, LIMITS)


def test_invariants_over_grid() -> None:
    n = 0
    for _spot, evals in all_evaluations():
        for e in evals:
            n += 1
            assert e.verdict == worst_verdict(e.reasons)
            assert (e.verdict == Verdict.GO) == (e.reasons == ())
            assert len(set(e.reasons)) == len(e.reasons)
            order = list(ReasonCode)
            assert list(e.reasons) == sorted(e.reasons, key=order.index)
            if e.dir_class in (DirClass.OFFSHORE, DirClass.SIDE_OFFSHORE):
                assert e.verdict == Verdict.NO_GO
            assert (e.dir_class == DirClass.OFFSHORE) == (ReasonCode.OFFSHORE in e.reasons)
            assert (e.dir_class == DirClass.SIDE_OFFSHORE) == (
                ReasonCode.SIDE_OFFSHORE in e.reasons
            )
    assert n == len(SPOTS) * 4 * 4 * 24


def test_deterministic_and_order_independent() -> None:
    spot = make_spot(tide_sensitive="prefer_low", rws_station=STATION)
    fc = [f for at in HOURS for f in model_sets(at, 270)[1]]
    shuffled = fc[::-1]
    shuffled = shuffled[::2] + shuffled[1::2]
    a = evaluate_spot(spot, fc, TIDES, LIMITS)
    assert a == evaluate_spot(spot, fc, TIDES, LIMITS)
    b = evaluate_spot(spot, shuffled, TIDES, LIMITS)
    assert a == b
    assert [e.valid_at for e in a] == HOURS


EXPECTED_EFFECT = {
    "no_data": "no_go",
    "wind_too_light": "no_go",
    "wind_too_strong": "no_go",
    "wind_borderline": "marginal",
    "too_gusty": "no_go",
    "gusty": "marginal",
    "offshore": "no_go",
    "side_offshore": "no_go",
    "direction_unknown": "no_go",
    "direction_not_ridable": "no_go",
    "dark": "no_go",
    "season_closed": "no_go",
    "spot_forbidden": "no_go",
    "spot_limited": "marginal",
    "status_unknown": "marginal",
    "tide_too_low": "no_go",
    "tide_unfavorable": "marginal",
    "tide_unknown": "marginal",
    "low_confidence": "marginal",
}


def test_effect_and_label_tables_are_complete() -> None:
    assert set(REASON_EFFECT) == set(ReasonCode) == set(REASON_LABEL_NL)
    assert {r.value: v.value for r, v in REASON_EFFECT.items()} == EXPECTED_EFFECT
    assert all(label for label in REASON_LABEL_NL.values())


def test_to_row_columns() -> None:
    spot = make_spot()
    e = evaluate_spot(spot, model_hours(HOURS[10]), [], LIMITS)[0]
    row = e.to_row(evaluated_at=datetime(2026, 7, 15, 9, tzinfo=UTC))
    assert list(row) == [
        "spot_id", "valid_at", "verdict", "reasons", "wind_kn", "gust_kn", "dir_deg",
        "dir_class", "confidence", "tide_level_cm", "evaluated_at",
    ]  # fmt: skip
    assert row["reasons"] == [] and isinstance(row["reasons"], list)
    off = evaluate_spot(spot, model_hours(HOURS[10], dir_deg=90), [], LIMITS)[0]
    assert off.to_row(evaluated_at=datetime(2026, 7, 15, 9, tzinfo=UTC))["reasons"] == ["offshore"]
    with pytest.raises(ValueError):
        e.to_row(evaluated_at=datetime(2026, 7, 15, 9))  # noqa: DTZ001
