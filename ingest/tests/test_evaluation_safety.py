"""AC-2: offshore and side-offshore are always no_go, and nothing can switch that off."""

import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

import shakka.domain.direction as direction_mod
import shakka.domain.evaluation as evaluation_mod
from evaluation_fixtures import LIMITS, NOON, STATION, extremes, make_spot, model_hours, per_model
from shakka.domain.consensus import Confidence, compute_consensus
from shakka.domain.defaults import SIDESHORE_MAX_DEG
from shakka.domain.direction import DirClass, angular_distance, classify_direction
from shakka.domain.evaluation import (
    HourEvaluation,
    ReasonCode,
    RiderLimits,
    Verdict,
    default_limits,
    evaluate_hour,
    evaluate_spot,
)
from shakka.domain.forecast import ModelKey as M

OFFSHORE_CLASSES = {DirClass.OFFSHORE, DirClass.SIDE_OFFSHORE}
REASON_FOR = {
    DirClass.OFFSHORE: ReasonCode.OFFSHORE,
    DirClass.SIDE_OFFSHORE: ReasonCode.SIDE_OFFSHORE,
}


def test_offshore_always_no_go() -> None:
    count = 0
    for normal in range(0, 360, 15):
        spot = make_spot(shore_normal_deg=normal, ridable_dirs=[{"from": 0, "to": 359}])
        for wind_from in range(360):
            cls = classify_direction(wind_from, normal)
            if cls not in OFFSHORE_CLASSES:
                continue
            count += 1
            e = evaluate_hour(
                spot,
                NOON,
                model_hours(NOON, wind=20, gust=24, dir_deg=wind_from),
                [],
                RiderLimits(min_kn=0, max_kn=100),
            )
            assert e.verdict == Verdict.NO_GO
            assert REASON_FOR[cls] in e.reasons
            assert e.dir_class == cls
    assert count > 0


def _offshore_winds() -> list[int]:
    return [w for w in range(360) if classify_direction(w, 270) in OFFSHORE_CLASSES][::5]


def _variants():
    d = lambda h: datetime(2026, 7, 15, h, 30, tzinfo=UTC)  # noqa: E731
    low_tide = extremes((d(0), "high", 100), (d(10), "low", -80), (d(16), "high", 100))
    plain = make_spot()
    tidal = make_spot(tide_sensitive="prefer_low", rws_station=STATION)
    agree = lambda w: model_hours(NOON, dir_deg=w)  # noqa: E731
    disagree = lambda w: per_model(  # noqa: E731
        NOON,
        {
            M.KNMI: (10.0, 14.0, w),
            M.ICON: (12.0, 16.0, w),
            M.ECMWF: (18.1, 22.0, w),
            M.GFS: (14.0, 18.0, w),
        },
    )
    return [
        (plain, agree, [], RiderLimits(min_kn=0, max_kn=100)),
        (plain, agree, [], RiderLimits(min_kn=12, max_kn=30)),
        (plain, agree, [], RiderLimits(min_kn=25, max_kn=26)),
        (tidal, agree, low_tide, LIMITS),
        (plain, disagree, [], LIMITS),
        (plain, agree, [], default_limits(plain)),
    ]


@pytest.mark.parametrize("wind_from", _offshore_winds())
def test_offshore_no_go_under_variants(wind_from: int) -> None:
    cls = classify_direction(wind_from, 270)
    for spot, hours, tides, limits in _variants():
        e = evaluate_hour(spot, NOON, hours(wind_from), tides, limits)
        assert e.verdict == Verdict.NO_GO
        assert REASON_FOR[cls] in e.reasons


def test_no_bypass_parameters() -> None:
    def params(fn) -> list[str]:
        return list(inspect.signature(fn).parameters)

    assert params(evaluate_hour) == ["spot", "valid_at", "hours", "tides", "limits"]
    assert params(evaluate_spot) == ["spot", "forecasts", "tides", "limits"]
    assert params(classify_direction) == ["wind_from_deg", "shore_normal_deg"]
    assert params(compute_consensus) == ["hours"]
    assert params(default_limits) == ["spot"]
    for mod in (evaluation_mod, direction_mod):
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_") or fn.__module__ != mod.__name__:
                continue
            for p in params(fn):
                assert not any(
                    bad in p for bad in ("offshore", "allow", "override", "force", "unsafe")
                ), (name, p)


def test_sideshore_bound_is_hard_rule() -> None:
    assert SIDESHORE_MAX_DEG == 90.0
    for normal in range(0, 360, 15):
        for wind in range(360):
            offshore_component = angular_distance(wind, normal) > 90
            assert offshore_component == (classify_direction(wind, normal) in OFFSHORE_CLASSES)


def _eval_dirs(dirs: tuple[int, ...], normal: int):
    hours = per_model(NOON, {m: (20.0, 24.0, d) for m, d in zip(M, dirs, strict=True)})
    spot = make_spot(shore_normal_deg=normal)
    return compute_consensus(hours), evaluate_hour(spot, NOON, hours, [], LIMITS)


def test_rounding_never_makes_offshore_ridable() -> None:
    assert classify_direction(90.4, 0) == DirClass.SIDE_OFFSHORE
    assert classify_direction(269.6, 0) == DirClass.SIDE_OFFSHORE
    assert classify_direction(90.0, 0) == DirClass.SIDESHORE
    assert classify_direction(270.0, 0) == DirClass.SIDESHORE

    # (90, 90, 90, 91): mean ~90.25, dir_deg rounds to 90, class is side_offshore.
    c, e = _eval_dirs((90, 90, 90, 91), 0)
    assert c is not None and c.dir_mean_deg == pytest.approx(90.25, abs=0.01)
    assert e.dir_deg == 90
    assert e.dir_class == DirClass.SIDE_OFFSHORE
    assert e.verdict == Verdict.NO_GO and ReasonCode.SIDE_OFFSHORE in e.reasons

    # (88, 91, 91, 90): arithmetic mean is 90, circular mean ~90.000076: still side_offshore.
    c, e = _eval_dirs((88, 91, 91, 90), 0)
    assert c is not None and c.dir_mean_deg is not None and c.dir_mean_deg > 90.0
    assert e.dir_class == DirClass.SIDE_OFFSHORE
    assert e.verdict == Verdict.NO_GO and ReasonCode.SIDE_OFFSHORE in e.reasons

    # exactly 90.0 stays sideshore, no direction reason
    c, e = _eval_dirs((90, 90, 90, 90), 0)
    assert c is not None and c.dir_mean_deg == 90.0
    assert e.dir_class == DirClass.SIDESHORE
    assert not set(e.reasons) & {ReasonCode.OFFSHORE, ReasonCode.SIDE_OFFSHORE}

    # no float noise across the border
    for d in (180, 0):
        c, e = _eval_dirs((d,) * 4, 270)
        assert c is not None and c.dir_mean_deg == float(d)
        assert e.dir_class == DirClass.SIDESHORE
        assert e.confidence == Confidence.HIGH


def _ev(**kw):
    base = {
        "spot_id": "s",
        "valid_at": NOON,
        "verdict": Verdict.GO,
        "reasons": (),
        "wind_kn": 20.0,
        "gust_kn": 24.0,
        "dir_deg": 270,
        "dir_class": DirClass.ONSHORE,
        "confidence": Confidence.HIGH,
        "tide_level_cm": None,
    }
    base.update(kw)
    return HourEvaluation(**base)


R = ReasonCode


def test_model_rejects_offshore_go() -> None:
    with pytest.raises(ValidationError):
        _ev(dir_class=DirClass.OFFSHORE, verdict=Verdict.GO, reasons=())


@pytest.mark.parametrize(
    ("dir_class", "reasons"),
    [
        (DirClass.OFFSHORE, (R.DARK,)),
        (DirClass.SIDE_OFFSHORE, (R.OFFSHORE,)),
        (DirClass.SIDESHORE, (R.SIDE_OFFSHORE,)),
        (None, (R.OFFSHORE, R.DIRECTION_UNKNOWN)),
    ],
)
def test_model_requires_offshore_reason(dir_class, reasons) -> None:
    with pytest.raises(ValidationError):
        _ev(dir_class=dir_class, verdict=Verdict.NO_GO, reasons=reasons)


def test_model_valid_counterexamples() -> None:
    _ev(dir_class=DirClass.OFFSHORE, verdict=Verdict.NO_GO, reasons=(R.OFFSHORE, R.DARK))
    _ev(dir_class=DirClass.SIDE_OFFSHORE, verdict=Verdict.NO_GO, reasons=(R.SIDE_OFFSHORE,))


def test_model_other_invariants() -> None:
    with pytest.raises(ValidationError):
        _ev(verdict=Verdict.NO_GO, reasons=())  # verdict must match reasons
    with pytest.raises(ValidationError):
        _ev(verdict=Verdict.MARGINAL, reasons=(R.GUSTY, R.GUSTY))  # duplicates
    with pytest.raises(ValidationError):
        _ev(verdict=Verdict.MARGINAL, reasons=(R.GUSTY, R.WIND_BORDERLINE))  # order
    with pytest.raises(ValidationError):
        _ev(valid_at=datetime(2026, 7, 15, 10, 30, tzinfo=UTC))


def test_model_copy_revalidates() -> None:
    off = evaluate_hour(make_spot(), NOON, model_hours(NOON, dir_deg=90), [], LIMITS)
    assert off.verdict == Verdict.NO_GO
    with pytest.raises(ValidationError):
        off.model_copy(update={"verdict": Verdict.GO, "reasons": ()})
    with pytest.raises(ValidationError):
        off.model_copy(update={"dir_class": DirClass.SIDESHORE})
    with pytest.raises(ValidationError):
        off.model_copy(update={"unknown_field": 1})
    base = evaluate_hour(make_spot(), NOON, model_hours(NOON), [], LIMITS)
    assert base.verdict == Verdict.GO
    changed = base.model_copy(update={"tide_level_cm": 5})
    assert changed.tide_level_cm == 5
    assert changed.model_copy(update={"tide_level_cm": None}) == base
    assert base.model_copy() == base
    assert base.model_copy(deep=True) == base


def test_no_model_construct_in_src() -> None:
    src = Path(evaluation_mod.__file__).resolve().parents[1]
    offenders = [
        str(p) for p in src.rglob("*.py") if "model_construct" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
