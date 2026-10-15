"""Tests for shakka.domain.kite (WP-06)."""

import math

import pytest
from pydantic import ValidationError

from shakka.domain.kite import (
    KiteFit,
    RiderProfile,
    classify_fit,
    ideal_kite_size,
    pick_from_quiver,
    recommend_kite,
)
from shakka.domain.spot import Level

BAD_WINDS = [0, 0.5, 100.5, -5, math.nan, math.inf, True, "15"]


def test_ideal_values():
    assert ideal_kite_size(75, Level.INTERMEDIATE, 15) == 11.0
    assert ideal_kite_size(75, Level.BEGINNER, 15) == 9.0
    assert ideal_kite_size(75, Level.ADVANCED, 15) == 11.0
    assert ideal_kite_size(75, Level.INTERMEDIATE, 20) == 8.3
    assert ideal_kite_size(75, "beginner", 15) == 9.0  # type: ignore[arg-type]


@pytest.mark.parametrize("weight", [29, 201, 75.0, True])
def test_ideal_rejects_weight(weight):
    with pytest.raises(ValueError):
        ideal_kite_size(weight, Level.INTERMEDIATE, 15)


def test_ideal_rejects_unknown_level():
    with pytest.raises(ValueError):
        ideal_kite_size(75, "expert", 15)  # type: ignore[arg-type]


@pytest.mark.parametrize("wind", BAD_WINDS)
def test_ideal_wind_rejects(wind):
    with pytest.raises(ValueError):
        ideal_kite_size(75, Level.INTERMEDIATE, wind)


@pytest.mark.parametrize("wind", [1, 100])
def test_ideal_wind_bounds_valid(wind):
    assert ideal_kite_size(75, Level.INTERMEDIATE, wind) > 0


def test_pick_tie_goes_to_smaller():
    assert pick_from_quiver((9, 16), 12.0) == 9
    assert pick_from_quiver((9, 16), 12.1) == 16
    assert pick_from_quiver((9, 16), 11.9) == 9
    assert pick_from_quiver((), 10.0) is None
    assert pick_from_quiver((16, 9, 9), 12.1) == 16


def test_classify_fit_bounds():
    assert classify_fit(10, 8.0) == KiteFit.IDEAL
    assert classify_fit(10, 12.5) == KiteFit.IDEAL
    assert classify_fit(10, 7.9) == KiteFit.OVERPOWERED
    assert classify_fit(10, 12.6) == KiteFit.UNDERPOWERED


def test_pick_tie_via_recommend_kite():
    rider = RiderProfile(weight_kg=60, level="intermediate", quiver_m2=(9, 16))
    advice = recommend_kite(rider, 11)
    assert advice is not None
    assert (advice.ideal_size_m2, advice.size_m2, advice.fit) == (12.0, 9.0, KiteFit.UNDERPOWERED)


@pytest.mark.parametrize("wind", BAD_WINDS)
@pytest.mark.parametrize("quiver", [(), (9, 12)])
def test_recommend_wind_rejects(wind, quiver):
    rider = RiderProfile(weight_kg=75, level="intermediate", quiver_m2=quiver)
    with pytest.raises(ValueError):
        recommend_kite(rider, wind)


def test_rider_profile_normalizes_quiver():
    rider = RiderProfile(weight_kg=75, level="intermediate", quiver_m2=[12, 7, 9, 9])
    assert rider.quiver_m2 == (7.0, 9.0, 12.0)
    assert RiderProfile(weight_kg=75, level="beginner", quiver_m2=[]).quiver_m2 == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quiver_m2": list(range(3, 14))},
        {"quiver_m2": [9] * 11},
        {"quiver_m2": [2.9]},
        {"quiver_m2": [21.5]},
        {"quiver_m2": [math.nan]},
        {"quiver_m2": [math.inf]},
        {"quiver_m2": [True]},
        {"quiver_m2": ["9"]},
        {"weight_kg": 29},
        {"weight_kg": 201},
        {"weight_kg": 75.0},
        {"weight_kg": True},
        {"level": "expert"},
        {"name": "x"},
    ],
)
def test_rider_profile_rejects(kwargs):
    base = {"weight_kg": 75, "level": "intermediate", "quiver_m2": [9]}
    with pytest.raises(ValueError):
        RiderProfile(**{**base, **kwargs})


def test_rider_profile_is_frozen():
    rider = RiderProfile(weight_kg=75, level="intermediate")
    with pytest.raises(ValidationError):
        rider.weight_kg = 80  # type: ignore[misc]
