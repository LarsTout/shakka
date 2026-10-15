"""Tests for shakka.domain.kite (WP-06)."""

import itertools
import math
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from shakka.domain.kite import (
    KiteFit,
    RiderProfile,
    classify_fit,
    ideal_kite_size,
    pick_from_quiver,
    recommend_for_window,
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


EXAMPLES_PATH = Path(__file__).parent / "fixtures" / "kite_examples.yaml"
EXAMPLES = yaml.safe_load(EXAMPLES_PATH.read_text(encoding="utf-8"))


def test_examples_file_shape():
    assert set(EXAMPLES) == {"checked_by_lars", "cases"}
    assert isinstance(EXAMPLES["checked_by_lars"], bool)
    cases = EXAMPLES["cases"]
    assert len(cases) >= 15
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert set(case) == {"id", "weight_kg", "level", "quiver_m2", "wind_kn", "expected"}
        assert set(case["expected"]) == {"size_m2", "ideal_size_m2", "fit"}
        assert case["expected"]["size_m2"] in case["quiver_m2"]


@pytest.mark.parametrize("case", EXAMPLES["cases"], ids=[c["id"] for c in EXAMPLES["cases"]])
def test_example(case):
    rider = RiderProfile(
        weight_kg=case["weight_kg"], level=case["level"], quiver_m2=case["quiver_m2"]
    )
    advice = recommend_kite(rider, case["wind_kn"])
    assert advice is not None
    expected = case["expected"]
    assert advice.size_m2 == expected["size_m2"]
    assert advice.ideal_size_m2 == expected["ideal_size_m2"]
    assert advice.fit == KiteFit(expected["fit"])


QUIVERS = [
    (7.0, 9.0, 12.0),
    (5.0, 7.0, 9.0, 12.0, 14.0),
    (6.0, 8.0, 10.0),
    (9.0, 12.0, 15.0, 17.0),
    (10.0,),
    (7.5, 10.5, 13.5),
]
WEIGHTS = range(50, 111, 5)
WINDS = [8 + 0.5 * i for i in range(65)]  # 8.0 .. 40.0
LEVELS = list(Level)


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("quiver", QUIVERS)
def test_size_always_from_quiver(quiver, level):
    for weight in WEIGHTS:
        rider = RiderProfile(weight_kg=weight, level=level, quiver_m2=quiver)
        for wind in WINDS:
            advice = recommend_kite(rider, wind)
            assert advice is not None
            assert advice.size_m2 in rider.quiver_m2
            assert advice.size_m2 in quiver


@pytest.mark.parametrize("level", LEVELS)
def test_empty_quiver_gives_none(level):
    for weight in WEIGHTS:
        rider = RiderProfile(weight_kg=weight, level=level, quiver_m2=())
        assert all(recommend_kite(rider, wind) is None for wind in WINDS)
        assert recommend_for_window(rider, [15, 18]) is None


@pytest.mark.parametrize("kite", [3.0, 10.0, 21.0])
@pytest.mark.parametrize("level", LEVELS)
def test_single_kite_always_chosen(kite, level):
    for weight in WEIGHTS:
        rider = RiderProfile(weight_kg=weight, level=level, quiver_m2=(kite,))
        for wind in WINDS:
            advice = recommend_kite(rider, wind)
            assert advice is not None
            assert advice.size_m2 == kite


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("quiver", QUIVERS)
def test_more_wind_never_bigger(quiver, level):
    winds = sorted({1.0, 100.0, *WINDS})
    for weight in WEIGHTS:
        rider = RiderProfile(weight_kg=weight, level=level, quiver_m2=quiver)
        advices = [recommend_kite(rider, wind) for wind in winds]
        assert all(a is not None for a in advices)
        sizes = [a.size_m2 for a in advices if a]
        ideals = [a.ideal_size_m2 for a in advices if a]
        assert sizes == sorted(sizes, reverse=True)
        assert ideals == sorted(ideals, reverse=True)


@pytest.mark.parametrize("weight", [30, 75, 200])
@pytest.mark.parametrize("level", LEVELS)
def test_ideal_monotone_in_wind_fine_grid(weight, level):
    # Built as i / 10, not by repeated addition, so the last value is exactly 100.0.
    ideals = [ideal_kite_size(weight, level, i / 10) for i in range(10, 1001)]
    assert ideals == sorted(ideals, reverse=True)


@pytest.mark.parametrize("level", LEVELS)
def test_heavier_never_smaller_ideal(level):
    for wind in WINDS:
        ideals = [ideal_kite_size(w, level, wind) for w in range(30, 201)]
        assert ideals == sorted(ideals)


@pytest.mark.parametrize("level", LEVELS)
def test_heavier_never_smaller_size(level):
    quiver = (5.0, 7.0, 9.0, 12.0, 14.0)
    for wind in WINDS:
        sizes = []
        for w in range(30, 201):
            advice = recommend_kite(RiderProfile(weight_kg=w, level=level, quiver_m2=quiver), wind)
            assert advice is not None
            sizes.append(advice.size_m2)
        assert sizes == sorted(sizes)


WINDOW_RIDER = RiderProfile(weight_kg=75, level="intermediate", quiver_m2=(7, 9, 12))


def test_window_uses_upper_median():
    values = [12, 18, 25, 14]
    assert recommend_for_window(WINDOW_RIDER, values) == recommend_kite(WINDOW_RIDER, 18)
    advice = recommend_for_window(WINDOW_RIDER, values)
    assert advice is not None
    assert (advice.ideal_size_m2, advice.size_m2) == (9.2, 9)
    for alternative in (17.25, 16, 25):  # mean, plain median, maximum
        assert ideal_kite_size(75, Level.INTERMEDIATE, alternative) != 9.2
    other = recommend_kite(WINDOW_RIDER, 25)
    assert other is not None
    assert other.size_m2 == 7 != advice.size_m2


def test_window_upper_median_changes_size_too():
    # Plain median is 15.5 kn (12 m2); the upper median is 17 kn (9 m2).
    advice = recommend_for_window(WINDOW_RIDER, [12, 14, 17, 25])
    plain = recommend_kite(WINDOW_RIDER, 15.5)
    assert advice == recommend_kite(WINDOW_RIDER, 17)
    assert advice is not None and plain is not None
    assert (advice.size_m2, plain.size_m2) == (9, 12)


def test_window_odd_length():
    advice = recommend_for_window(WINDOW_RIDER, [20, 10, 15])
    assert advice == recommend_kite(WINDOW_RIDER, 15)
    assert advice is not None
    assert (advice.size_m2, advice.ideal_size_m2) == (12, 11.0)


def test_window_order_invariant():
    values = [12, 18, 25, 14]
    expected = recommend_kite(WINDOW_RIDER, 18)
    for perm in itertools.permutations(values):
        assert recommend_for_window(WINDOW_RIDER, perm) == expected


def test_window_single_hour():
    assert recommend_for_window(WINDOW_RIDER, [18]) == recommend_kite(WINDOW_RIDER, 18)


def test_window_empty():
    assert recommend_for_window(WINDOW_RIDER, []) is None


@pytest.mark.parametrize("values", [[15, None], [15, math.nan], [15, 0]])
def test_window_invalid_value(values):
    with pytest.raises(ValueError):
        recommend_for_window(WINDOW_RIDER, values)
