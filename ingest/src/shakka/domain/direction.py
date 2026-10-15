"""Direction classes relative to the shore normal, ridable ranges and the Dutch compass.

Offshore and side-offshore are always not ridable. There is no parameter to change that.
"""

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from shakka.domain.defaults import (
    ONSHORE_MAX_DEG,
    SIDE_OFFSHORE_MAX_DEG,
    SIDE_ONSHORE_MAX_DEG,
    SIDESHORE_MAX_DEG,
)
from shakka.domain.spot import DirRange


class DirClass(StrEnum):
    ONSHORE = "onshore"
    SIDE_ONSHORE = "side_onshore"
    SIDESHORE = "sideshore"
    SIDE_OFFSHORE = "side_offshore"
    OFFSHORE = "offshore"


RIDABLE_DIR_CLASSES: Final[frozenset[DirClass]] = frozenset(
    {DirClass.ONSHORE, DirClass.SIDE_ONSHORE, DirClass.SIDESHORE}
)
DIR_CLASS_LABEL_NL: Final[dict[DirClass, str]] = {
    DirClass.ONSHORE: "Aanlandig",
    DirClass.SIDE_ONSHORE: "Schuin aanlandig",
    DirClass.SIDESHORE: "Sideshore (langs de kust)",
    DirClass.SIDE_OFFSHORE: "Schuin aflandig",
    DirClass.OFFSHORE: "Aflandig",
}
COMPASS_POINTS_NL: Final[tuple[str, ...]] = (
    "N",
    "NNO",
    "NO",
    "ONO",
    "O",
    "OZO",
    "ZO",
    "ZZO",
    "Z",
    "ZZW",
    "ZW",
    "WZW",
    "W",
    "WNW",
    "NW",
    "NNW",
)


def _finite(*values: float) -> None:
    for v in values:
        if not math.isfinite(v):
            raise ValueError("direction must be finite")


def angular_distance(a: float, b: float) -> float:
    """Smallest angle between two directions, in [0, 180]. ValueError if not finite."""
    _finite(a, b)
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def classify_direction(wind_from_deg: float, shore_normal_deg: float) -> DirClass:
    """Class from angular_distance(wind_from_deg, shore_normal_deg) and the *_MAX_DEG bounds
    (upper bound inclusive). Both arguments are taken modulo 360. ValueError if not finite."""
    d = angular_distance(
        wind_from_deg % 360 if math.isfinite(wind_from_deg) else wind_from_deg,
        shore_normal_deg % 360 if math.isfinite(shore_normal_deg) else shore_normal_deg,
    )
    if d <= ONSHORE_MAX_DEG:
        return DirClass.ONSHORE
    if d <= SIDE_ONSHORE_MAX_DEG:
        return DirClass.SIDE_ONSHORE
    if d <= SIDESHORE_MAX_DEG:
        return DirClass.SIDESHORE
    if d <= SIDE_OFFSHORE_MAX_DEG:
        return DirClass.SIDE_OFFSHORE
    return DirClass.OFFSHORE


def in_ranges(deg: float, ranges: Sequence[DirRange]) -> bool:
    """True if deg (mod 360) lies in any clockwise, inclusive range; from > to wraps north."""
    _finite(deg)
    x = deg % 360
    for r in ranges:
        if r.from_deg <= r.to_deg:
            if r.from_deg <= x <= r.to_deg:
                return True
        elif x >= r.from_deg or x <= r.to_deg:
            return True
    return False


def compass_label(deg: float) -> str:
    """Dutch 16-point compass label; a boundary (e.g. 11.25) belongs to the next point clockwise."""
    _finite(deg)
    return COMPASS_POINTS_NL[int(((deg % 360) + 11.25) // 22.5) % 16]
