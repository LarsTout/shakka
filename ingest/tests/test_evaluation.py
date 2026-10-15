"""AC-3, AC-4, AC-6 (status and season), AC-7, AC-8 (integration)."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from evaluation_fixtures import LIMITS, NOON, STATION, extremes, make_spot, model_hours, per_model
from shakka.domain.consensus import Confidence
from shakka.domain.defaults import TIDE_SAMPLE_OFFSET
from shakka.domain.direction import DirClass
from shakka.domain.evaluation import (
    ReasonCode as R,
)
from shakka.domain.evaluation import (
    RiderLimits,
    Verdict,
    default_limits,
    evaluate_hour,
    evaluate_spot,
)
from shakka.domain.forecast import ModelKey as M
from shakka.domain.tide import estimate_tide_level


def ev(spot=None, hours=None, at=NOON, tides=(), limits=LIMITS):
    spot = spot or make_spot()
    hours = model_hours(at) if hours is None else hours
    return evaluate_hour(spot, at, hours, tides, limits)


def test_baseline_is_go() -> None:
    e = ev()
    assert e.verdict == Verdict.GO
    assert e.reasons == ()
    assert e.dir_class == DirClass.ONSHORE
    assert e.confidence == Confidence.HIGH
    assert e.wind_kn == 20.0 and e.gust_kn == 24.0 and e.dir_deg == 270


# AC-3
def test_no_shore_normal_every_hour() -> None:
    spot = make_spot(shore_normal_deg=None)
    day = datetime(2026, 7, 15, 0, tzinfo=UTC)
    fc = [f for h in range(24) for f in model_hours(day + timedelta(hours=h))]
    out = evaluate_spot(spot, fc, [], LIMITS)
    assert len(out) == 24
    for e in out:
        assert e.verdict == Verdict.NO_GO
        assert R.DIRECTION_UNKNOWN in e.reasons
        assert e.dir_class is None


def test_ridable_dirs_restricts() -> None:
    spot = make_spot(ridable_dirs=[{"from": 200, "to": 340}])
    e = ev(spot, model_hours(NOON, dir_deg=190))
    assert e.dir_class == DirClass.SIDESHORE
    assert R.DIRECTION_NOT_RIDABLE in e.reasons
    assert not ev(spot).reasons


def test_ridable_dirs_use_unrounded_direction() -> None:
    spot = make_spot(ridable_dirs=[{"from": 200, "to": 340}])
    hours = model_hours(NOON, dir_deg=340)[:3] + model_hours(NOON, dir_deg=341)[3:]
    e = ev(spot, hours)  # mean 340.25, outside the range although dir_deg rounds to 340
    assert e.dir_deg == 340
    assert R.DIRECTION_NOT_RIDABLE in e.reasons


def test_ridable_dirs_cannot_allow_offshore() -> None:
    spot = make_spot(ridable_dirs=[{"from": 0, "to": 359}])
    e = ev(spot, model_hours(NOON, dir_deg=90))
    assert R.OFFSHORE in e.reasons
    assert R.DIRECTION_NOT_RIDABLE not in e.reasons


# AC-4
@pytest.mark.parametrize(
    ("wind", "reason"),
    [
        (11.9, R.WIND_TOO_LIGHT),
        (12.0, R.WIND_BORDERLINE),
        (13.9, R.WIND_BORDERLINE),
        (14.0, None),
        (28.0, None),
        (28.1, R.WIND_BORDERLINE),
        (30.0, R.WIND_BORDERLINE),
        (30.1, R.WIND_TOO_STRONG),
    ],
)
def test_wind_thresholds(wind: float, reason: R | None) -> None:
    e = ev(hours=model_hours(NOON, wind=wind, gust=wind + 2))
    wind_reasons = {R.WIND_TOO_LIGHT, R.WIND_TOO_STRONG, R.WIND_BORDERLINE}
    assert set(e.reasons) & wind_reasons == (set() if reason is None else {reason})


@pytest.mark.parametrize(
    ("wind", "gust", "expected"),
    [
        (20, 31.9, set()),
        (20, 32.0, {R.GUSTY}),
        (20, 37.9, {R.GUSTY}),
        (20, 38.0, {R.TOO_GUSTY}),
        (12, 19.9, set()),
        (12, 20.0, {R.GUSTY}),
        (20, 18, set()),
    ],
)
def test_gust_thresholds(wind: float, gust: float, expected: set[R]) -> None:
    e = ev(hours=model_hours(NOON, wind=wind, gust=gust))
    assert set(e.reasons) & {R.GUSTY, R.TOO_GUSTY} == expected


def test_unknown_gust() -> None:
    e = ev(hours=model_hours(NOON, gust=None))
    assert not set(e.reasons) & {R.GUSTY, R.TOO_GUSTY}
    assert e.gust_kn is None
    assert e.confidence == Confidence.MEDIUM


def test_zero_wind_skips_gusts() -> None:
    e = ev(hours=model_hours(NOON, wind=0.0, gust=20.0))
    assert R.WIND_TOO_LIGHT in e.reasons
    assert not set(e.reasons) & {R.GUSTY, R.TOO_GUSTY}


def test_default_limits() -> None:
    assert default_limits(make_spot()) == RiderLimits(min_kn=12, max_kn=30)
    assert default_limits(make_spot(default_min_kn=14)) == RiderLimits(min_kn=14, max_kn=30)
    assert default_limits(make_spot(default_min_kn=35)) == RiderLimits(min_kn=35, max_kn=40)


@pytest.mark.parametrize(
    ("lo", "hi"), [(10, 10), (20, 10), (-1, 10), (float("nan"), 10), (5, float("inf"))]
)
def test_rider_limits_invalid(lo: float, hi: float) -> None:
    with pytest.raises(ValidationError):
        RiderLimits(min_kn=lo, max_kn=hi)


def test_narrow_limits_single_borderline() -> None:
    e = ev(hours=model_hours(NOON, wind=20, gust=22), limits=RiderLimits(min_kn=19, max_kn=21))
    assert e.reasons.count(R.WIND_BORDERLINE) == 1


# AC-5 via evaluate_hour
def test_dark_at_night() -> None:
    at = datetime(2026, 6, 21, 3, tzinfo=UTC)
    e = ev(at=at, hours=model_hours(at))
    assert R.DARK in e.reasons and e.verdict == Verdict.NO_GO


# AC-6
def test_status_reasons() -> None:
    day = datetime(2026, 7, 15, 8, tzinfo=UTC)
    fc = [f for h in range(6) for f in model_hours(day + timedelta(hours=h))]
    cases = {
        "forbidden": (R.SPOT_FORBIDDEN, Verdict.NO_GO),
        "limited": (R.SPOT_LIMITED, Verdict.MARGINAL),
        None: (R.STATUS_UNKNOWN, Verdict.MARGINAL),
        "allowed": (None, Verdict.GO),
    }
    for status, (reason, verdict) in cases.items():
        out = evaluate_spot(make_spot(status=status), fc, [], LIMITS)
        assert len(out) == 6
        for e in out:
            assert e.verdict == verdict
            assert e.reasons == (() if reason is None else (reason,))


def test_season_closed_via_evaluate() -> None:
    spot = make_spot(
        season=[{"start": "05-01", "end": "09-30", "from_time": "10:00", "to_time": "18:00"}]
    )
    e = ev(spot)
    assert R.SEASON_CLOSED in e.reasons and e.verdict == Verdict.NO_GO
    at = datetime(2026, 7, 15, 17, tzinfo=UTC)  # 19:00 local; daylight in July
    assert R.SEASON_CLOSED not in ev(spot, model_hours(at), at=at).reasons


# AC-7
def day_tide(low_level: int = -80):
    d = lambda h, day=15: datetime(2026, 7, day, h, 30, tzinfo=UTC)  # noqa: E731
    return extremes(
        (d(0), "high", 100),
        (d(6), "low", low_level),
        (d(12), "high", 100),
        (d(18), "low", low_level),
        (d(0, 16), "high", 100),
    )


def at_h(h: int) -> datetime:
    return datetime(2026, 7, 15, h, tzinfo=UTC)


TIDE_REASONS = {R.TIDE_TOO_LOW, R.TIDE_UNFAVORABLE, R.TIDE_UNKNOWN}


def tide_ev(spot, h: int, tides=None):
    at = at_h(h)
    return evaluate_hour(spot, at, model_hours(at), day_tide() if tides is None else tides, LIMITS)


def test_tide_none_has_level_but_no_reason() -> None:
    spot = make_spot(rws_station=STATION)
    for h in (6, 9, 12):
        e = tide_ev(spot, h)
        assert not set(e.reasons) & TIDE_REASONS
        assert e.tide_level_cm == estimate_tide_level(day_tide(), at_h(h) + TIDE_SAMPLE_OFFSET)
        assert e.tide_level_cm is not None


def test_tide_too_low() -> None:
    spot = make_spot(tide_sensitive="avoid_low", tide_min_level_cm=0, rws_station=STATION)
    assert R.TIDE_TOO_LOW in tide_ev(spot, 6, day_tide(-50)).reasons
    assert R.TIDE_TOO_LOW not in tide_ev(spot, 12).reasons


def test_tide_min_level_boundary() -> None:
    spot = make_spot(tide_sensitive="prefer_high", tide_min_level_cm=100, rws_station=STATION)
    assert R.TIDE_TOO_LOW not in tide_ev(spot, 12).reasons  # level == min: not too low


@pytest.mark.parametrize(
    ("sens", "low_bad", "high_bad"),
    [("prefer_low", False, True), ("prefer_high", True, False), ("avoid_low", True, False)],
)
def test_tide_preference(sens: str, low_bad: bool, high_bad: bool) -> None:
    spot = make_spot(tide_sensitive=sens, rws_station=STATION)
    assert (R.TIDE_UNFAVORABLE in tide_ev(spot, 6).reasons) is low_bad
    assert (R.TIDE_UNFAVORABLE in tide_ev(spot, 12).reasons) is high_bad


def test_tide_unknown_cases() -> None:
    sens = {"tide_sensitive": "prefer_low"}
    assert R.TIDE_UNKNOWN in tide_ev(make_spot(rws_station=STATION, **sens), 9, []).reasons
    assert R.TIDE_UNKNOWN in tide_ev(make_spot(**sens), 9).reasons
    other = extremes((at_h(6), "low", -80), (at_h(12), "high", 100), station="anderstation")
    e = tide_ev(make_spot(rws_station=STATION, **sens), 9, other)
    assert R.TIDE_UNKNOWN in e.reasons and e.tide_level_cm is None


def test_tide_station_is_stripped() -> None:
    spot = make_spot(tide_sensitive="prefer_low", rws_station=f"  {STATION} ")
    assert R.TIDE_UNKNOWN not in tide_ev(spot, 9).reasons


def test_only_lows_gives_unknown_but_checks_level() -> None:
    lows = extremes((at_h(6), "low", -80), (at_h(12), "low", -70))
    spot = make_spot(tide_sensitive="prefer_low", rws_station=STATION)
    assert R.TIDE_UNKNOWN in tide_ev(spot, 8, lows).reasons
    spot2 = make_spot(tide_sensitive="prefer_low", tide_min_level_cm=0, rws_station=STATION)
    assert R.TIDE_TOO_LOW in tide_ev(spot2, 8, lows).reasons


# AC-8 integration
def test_low_confidence_makes_go_marginal() -> None:
    vals = {
        M.KNMI: (10.0, 14.0, 270),
        M.ICON: (12.0, 16.0, 270),
        M.ECMWF: (18.1, 22.0, 270),
        M.GFS: (14.0, 18.0, 270),
    }
    e = ev(hours=per_model(NOON, vals))
    assert e.confidence == Confidence.LOW
    assert e.verdict == Verdict.MARGINAL
    assert R.LOW_CONFIDENCE in e.reasons


def test_no_go_keeps_low_confidence_reason() -> None:
    vals = {M.KNMI: (5.0, 6.0, 270), M.ICON: (5.0, 6.0, 270), M.ECMWF: (14.2, 16.0, 270)}
    e = ev(hours=per_model(NOON, vals))
    assert e.verdict == Verdict.NO_GO and R.LOW_CONFIDENCE in e.reasons


def test_single_model_marginal() -> None:
    e = ev(hours=model_hours(NOON, models=(M.ICON,)))
    assert e.verdict == Verdict.MARGINAL and e.confidence == Confidence.LOW


def test_no_data() -> None:
    for hours in ([], model_hours(NOON, wind=None, gust=None, dir_deg=None)):
        e = ev(hours=hours)
        assert e.verdict == Verdict.NO_GO
        assert R.NO_DATA in e.reasons and R.DIRECTION_UNKNOWN in e.reasons
        assert e.confidence is None and e.dir_class is None


def test_gust_and_dir_only_is_no_data_with_low_confidence() -> None:
    e = ev(hours=per_model(NOON, {M.ICON: (None, 25.0, 270)}))
    assert R.NO_DATA in e.reasons and R.LOW_CONFIDENCE in e.reasons


def test_all_reasons_visible_together() -> None:
    at = datetime(2026, 6, 21, 3, tzinfo=UTC)
    e = ev(hours=model_hours(at, dir_deg=90), at=at)
    assert {R.DARK, R.OFFSHORE} <= set(e.reasons)


# input errors
def test_input_errors() -> None:
    spot = make_spot()
    with pytest.raises(ValueError):
        evaluate_hour(spot, datetime(2026, 7, 15, 10), model_hours(NOON), [], LIMITS)  # noqa: DTZ001
    with pytest.raises(ValueError):
        evaluate_hour(spot, NOON + timedelta(minutes=30), [], [], LIMITS)
    with pytest.raises(ValueError):
        evaluate_hour(spot, NOON, model_hours(NOON, spot_id="x"), [], LIMITS)
    with pytest.raises(ValueError):
        evaluate_hour(spot, NOON, model_hours(NOON + timedelta(hours=1)), [], LIMITS)
    with pytest.raises(ValueError):
        evaluate_hour(make_spot(lat=None, lon=None), NOON, model_hours(NOON), [], LIMITS)
    with pytest.raises(ValueError):
        evaluate_spot(spot, model_hours(NOON, spot_id="x"), [], LIMITS)
    assert evaluate_spot(spot, [], [], LIMITS) == []
    assert evaluate_spot(make_spot(lat=None, lon=None), [], [], LIMITS) == []


def test_evaluate_spot_sorted_unique() -> None:
    hours = [f for h in (3, 1, 2) for f in model_hours(NOON + timedelta(hours=h))]
    out = evaluate_spot(make_spot(), hours, [], LIMITS)
    assert [e.valid_at for e in out] == [NOON + timedelta(hours=h) for h in (1, 2, 3)]
