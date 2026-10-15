"""AC-8 (unit): consensus over the models and the confidence."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from evaluation_fixtures import model_hours, per_model
from shakka.domain.consensus import Confidence, Consensus, circular_mean_deg, compute_consensus
from shakka.domain.direction import angular_distance
from shakka.domain.forecast import ModelKey as M

T = datetime(2026, 7, 15, 10, tzinfo=UTC)


def four(winds, dirs=(270,) * 4, gust=24.0):
    return per_model(T, {m: (w, gust, d) for m, w, d in zip(M, winds, dirs, strict=True)})


def test_four_models_agree_is_high() -> None:
    c = compute_consensus(
        four((20.0, 20.5, 19.8, 20.2), dirs=(268, 270, 272, 270)),
    )
    assert c is not None
    assert c.wind_kn == 20.1
    assert c.dir_deg == 270
    assert c.confidence == Confidence.HIGH
    assert c.models_used == (M.KNMI, M.ICON, M.ECMWF, M.GFS)


def test_speed_spread_boundary() -> None:
    low = compute_consensus(four((10, 12, 18.1, 14)))
    assert low is not None and low.speed_spread_kn == 8.1
    assert low.confidence == Confidence.LOW
    edge = compute_consensus(four((10, 12, 18, 14)))
    assert edge is not None and edge.speed_spread_kn == 8.0
    assert edge.confidence != Confidence.LOW


def test_dir_spread_low() -> None:
    c = compute_consensus(four((20,) * 4, dirs=(270, 270, 270, 0)))
    assert c is not None
    assert c.dir_deg == 288
    assert c.dir_spread_deg == 71.6
    assert c.confidence == Confidence.LOW


def test_dir_spread_medium_just_under_low() -> None:
    c = compute_consensus(four((20,) * 4, dirs=(270, 270, 270, 320)))
    assert c is not None
    assert c.dir_deg == 282
    assert c.dir_spread_deg == 38.1
    assert c.confidence == Confidence.MEDIUM


def test_n_dir_limits_confidence() -> None:
    vals = {
        M.KNMI: (20.0, 24.0, 270),
        M.ICON: (20.0, 24.0, None),
        M.ECMWF: (20.0, 24.0, None),
    }
    c = compute_consensus(per_model(T, vals))
    assert c is not None
    assert c.dir_spread_deg == 0.0
    assert c.confidence == Confidence.MEDIUM
    vals4 = {m: (20.0, 24.0, 270 if m != M.GFS else None) for m in M}
    c4 = compute_consensus(per_model(T, vals4))
    assert c4 is not None and c4.confidence == Confidence.HIGH


def test_single_model_is_low() -> None:
    """One model is always low: without a second model there is no spread to measure."""
    c = compute_consensus(model_hours(T, models=(M.ICON,)))
    assert c is not None and c.confidence == Confidence.LOW


def test_two_equal_models_medium() -> None:
    c = compute_consensus(model_hours(T, models=(M.ICON, M.ECMWF)))
    assert c is not None and c.confidence == Confidence.MEDIUM


def test_unknown_gust_caps_at_medium() -> None:
    c = compute_consensus(model_hours(T, gust=None))
    assert c is not None
    assert c.gust_kn is None
    assert c.confidence == Confidence.MEDIUM


def test_gust_median_over_known() -> None:
    vals = {M.KNMI: (20.0, 30.0, 270), M.ICON: (20.0, None, 270), M.ECMWF: (20.0, 24.0, 270)}
    c = compute_consensus(per_model(T, vals))
    assert c is not None and c.gust_kn == 27.0


def test_all_none_is_none() -> None:
    assert compute_consensus(model_hours(T, wind=None, gust=None, dir_deg=None)) is None
    assert compute_consensus([]) is None


def test_wrap_350_10() -> None:
    c = compute_consensus(per_model(T, {M.ICON: (20, 24, 350), M.ECMWF: (20, 24, 10)}))
    assert c is not None
    assert c.dir_deg is not None and angular_distance(c.dir_deg, 0) <= 1
    assert c.dir_spread_deg == 10.0


def test_opposite_directions_unknown() -> None:
    c = compute_consensus(per_model(T, {M.ICON: (20, 24, 0), M.ECMWF: (20, 24, 180)}))
    assert c is not None
    assert c.dir_deg is None and c.dir_mean_deg is None and c.dir_spread_deg is None
    assert c.confidence == Confidence.LOW


def test_models_used_order_and_gust_only() -> None:
    vals = {M.GFS: (20.0, 24.0, 270), M.ICON: (20.0, 24.0, 270), M.KNMI: (None, 25.0, None)}
    c = compute_consensus(per_model(T, vals))
    assert c is not None
    assert c.models_used == (M.KNMI, M.ICON, M.GFS)


def test_errors() -> None:
    with pytest.raises(ValueError):
        compute_consensus(model_hours(T, models=(M.ICON,)) + model_hours(T, models=(M.ICON,)))
    other = datetime(2026, 7, 15, 11, tzinfo=UTC)
    with pytest.raises(ValueError):
        compute_consensus(model_hours(T, models=(M.ICON,)) + model_hours(other, models=(M.GFS,)))
    with pytest.raises(ValueError):
        compute_consensus(
            model_hours(T, models=(M.ICON,)) + model_hours(T, models=(M.GFS,), spot_id="other")
        )


def test_spread_rounding_no_float_error() -> None:
    vals = {
        M.KNMI: (12.3, 24.0, 270),
        M.ICON: (8.3, 24.0, 270),
        M.ECMWF: (10.0, 24.0, 270),
        M.GFS: (10.0, 24.0, 270),
    }
    c = compute_consensus(per_model(T, vals))
    assert c is not None
    assert c.speed_spread_kn == 4.0
    assert c.confidence == Confidence.HIGH


def test_circular_mean_exact_for_equal_directions() -> None:
    assert circular_mean_deg([180, 180]) == 180.0
    assert circular_mean_deg([180] * 4) == 180.0
    assert circular_mean_deg([0] * 4) == 0.0
    assert circular_mean_deg([90] * 4) == 90.0
    assert circular_mean_deg([270] * 4) == 270.0
    assert circular_mean_deg([359.9999999, 359.9999999]) == 0.0
    assert circular_mean_deg([]) is None
    assert circular_mean_deg([0, 180]) is None


def test_consensus_dir_coupling_validator() -> None:
    ok = {"wind_kn": 20.0, "gust_kn": None, "confidence": Confidence.LOW, "models_used": ()}
    Consensus(**ok, dir_deg=90, dir_mean_deg=90.25)
    Consensus(**ok, dir_deg=None, dir_mean_deg=None)
    for bad in (
        {"dir_deg": 90, "dir_mean_deg": None},
        {"dir_deg": None, "dir_mean_deg": 90.0},
        {"dir_deg": 91, "dir_mean_deg": 90.25},
        {"dir_deg": 0, "dir_mean_deg": 360.0},
        {"dir_deg": 0, "dir_mean_deg": -1.0},
    ):
        with pytest.raises(ValidationError):
            Consensus(**ok, **bad)
