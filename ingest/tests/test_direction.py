"""AC-1: direction classes, ridable ranges and the Dutch compass."""

import math

import pytest

from shakka.domain import defaults
from shakka.domain.direction import (
    COMPASS_POINTS_NL,
    DirClass,
    angular_distance,
    classify_direction,
    compass_label,
    in_ranges,
)
from shakka.domain.spot import DirRange

RANK = {
    DirClass.ONSHORE: 0,
    DirClass.SIDE_ONSHORE: 1,
    DirClass.SIDESHORE: 2,
    DirClass.SIDE_OFFSHORE: 3,
    DirClass.OFFSHORE: 4,
}


def rng(a: int, b: int) -> DirRange:
    return DirRange.model_validate({"from": a, "to": b})


@pytest.mark.parametrize(
    ("wind", "expected"),
    [
        (270, DirClass.ONSHORE),
        (225, DirClass.SIDE_ONSHORE),
        (315, DirClass.SIDE_ONSHORE),
        (180, DirClass.SIDESHORE),
        (0, DirClass.SIDESHORE),
        (135, DirClass.SIDE_OFFSHORE),
        (45, DirClass.SIDE_OFFSHORE),
        (90, DirClass.OFFSHORE),
    ],
)
def test_examples_270(wind: int, expected: DirClass) -> None:
    assert classify_direction(wind, 270) == expected


def test_wraparound() -> None:
    assert classify_direction(350, 10) == DirClass.ONSHORE
    assert classify_direction(10, 350) == DirClass.ONSHORE
    assert angular_distance(350, 10) == 20


@pytest.mark.parametrize("normal", [0, 45, 270, 359])
def test_exhaustive_symmetry_and_monotonic(normal: int) -> None:
    for d in range(0, 181):
        assert classify_direction(normal + d, normal) == classify_direction(normal - d, normal)
    winds = sorted(range(360), key=lambda w: angular_distance(w, normal))
    ranks = [RANK[classify_direction(w, normal)] for w in winds]
    assert ranks == sorted(ranks)


@pytest.mark.parametrize(
    ("d", "expected"),
    [
        (0, DirClass.ONSHORE),
        (22, DirClass.ONSHORE),
        (23, DirClass.SIDE_ONSHORE),
        (67, DirClass.SIDE_ONSHORE),
        (68, DirClass.SIDESHORE),
        (90, DirClass.SIDESHORE),
        (91, DirClass.SIDE_OFFSHORE),
        (157, DirClass.SIDE_OFFSHORE),
        (158, DirClass.OFFSHORE),
        (180, DirClass.OFFSHORE),
    ],
)
def test_class_boundaries(d: int, expected: DirClass) -> None:
    assert classify_direction(d, 0) == expected
    assert classify_direction(360 - d, 0) == expected


def test_boundaries_explicit() -> None:
    assert classify_direction(90, 0) == DirClass.SIDESHORE
    assert classify_direction(270, 0) == DirClass.SIDESHORE
    assert classify_direction(91, 0) == DirClass.SIDE_OFFSHORE
    assert classify_direction(269, 0) == DirClass.SIDE_OFFSHORE
    assert classify_direction(180, 270) == DirClass.SIDESHORE
    assert classify_direction(0, 270) == DirClass.SIDESHORE
    assert classify_direction(179, 270) == DirClass.SIDE_OFFSHORE
    assert classify_direction(1, 270) == DirClass.SIDE_OFFSHORE


def test_thresholds_ordered() -> None:
    d = defaults
    assert 0 < d.ONSHORE_MAX_DEG < d.SIDE_ONSHORE_MAX_DEG < d.SIDESHORE_MAX_DEG
    assert d.SIDESHORE_MAX_DEG < d.SIDE_OFFSHORE_MAX_DEG < 180
    assert 1 < d.GUSTY_RATIO < d.TOO_GUSTY_RATIO
    assert d.CONFIDENCE_HIGH_SPEED_SPREAD_KN < d.CONFIDENCE_LOW_SPEED_SPREAD_KN
    assert d.CONFIDENCE_HIGH_DIR_SPREAD_DEG < d.CONFIDENCE_LOW_DIR_SPREAD_DEG
    assert 0 < d.TIDE_LOW_BAND < d.TIDE_HIGH_BAND < 1


def test_in_ranges() -> None:
    r = [rng(200, 340)]
    assert in_ranges(200, r) and in_ranges(340, r)
    assert not in_ranges(199, r) and not in_ranges(341, r)
    wrap = [rng(300, 20)]
    assert all(in_ranges(x, wrap) for x in (350, 0, 20))
    assert not in_ranges(21, wrap) and not in_ranges(299, wrap)
    assert in_ranges(100, [rng(100, 100)])
    assert not in_ranges(101, [rng(100, 100)])
    assert not in_ranges(10, [])
    assert in_ranges(50, [rng(200, 340), rng(40, 60)])
    assert in_ranges(560, [rng(200, 210)])  # 560 % 360 = 200
    assert not in_ranges(340.4, r)


def test_compass_label() -> None:
    cases = [
        (0, "N"),
        (11.24, "N"),
        (11.25, "NNO"),
        (90, "O"),
        (180, "Z"),
        (225, "ZW"),
        (270, "W"),
        (348.75, "N"),
        (359.9, "N"),
        (-10, "N"),
    ]
    for deg, label in cases:
        assert compass_label(deg) == label, deg
    assert [compass_label(i * 22.5) for i in range(16)] == list(COMPASS_POINTS_NL)


def test_angular_distance_invalid() -> None:
    with pytest.raises(ValueError):
        angular_distance(math.nan, 0)
    with pytest.raises(ValueError):
        classify_direction(0, math.inf)
