"""Tests for shakka.domain.kite (WP-06)."""

import math

import pytest

from shakka.domain.kite import KiteFit, classify_fit, ideal_kite_size, pick_from_quiver
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
