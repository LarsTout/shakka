"""Kite size advice from rider weight, level, quiver and wind. Pure: no I/O, no clock."""

import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from shakka.domain.spot import Level

LEVEL_SIZE_FACTOR: Final[Mapping[Level, float]] = MappingProxyType(
    {Level.BEGINNER: 1.8, Level.INTERMEDIATE: 2.2, Level.ADVANCED: 2.2}
)
WEIGHT_RANGE_KG: Final = (30, 200)  # inclusive, equal to DB check profiles_weight_range
WIND_RANGE_KN: Final = (1.0, 100.0)  # inclusive
QUIVER_SIZE_RANGE_M2: Final = (3.0, 21.0)  # inclusive, equal to DB check profiles_quiver_valid
MAX_QUIVER_KITES: Final = 10  # counted before de-duplication, like the DB check
FIT_TOLERANCE: Final = 1.25  # size within [ideal / 1.25, ideal * 1.25] is "ideal"


class KiteFit(StrEnum):
    IDEAL = "ideal"
    UNDERPOWERED = "underpowered"
    OVERPOWERED = "overpowered"


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_wind(value: object) -> float:
    lo, hi = WIND_RANGE_KN
    if not _is_number(value) or not math.isfinite(value):  # type: ignore[arg-type]
        raise ValueError(f"wind_kn must be a finite number, got {value!r}")
    if not lo <= value <= hi:  # type: ignore[operator]
        raise ValueError(f"wind_kn must be between {lo} and {hi}, got {value!r}")
    return float(value)  # type: ignore[arg-type]


def _check_weight(value: object) -> int:
    lo, hi = WEIGHT_RANGE_KG
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"weight_kg must be an integer, got {value!r}")
    if not lo <= value <= hi:
        raise ValueError(f"weight_kg must be between {lo} and {hi}, got {value!r}")
    return value


def _check_positive(name: str, value: object) -> float:
    if not _is_number(value) or not math.isfinite(value) or value <= 0:  # type: ignore[arg-type,operator]
        raise ValueError(f"{name} must be a finite number > 0, got {value!r}")
    return float(value)  # type: ignore[arg-type]


def ideal_kite_size(weight_kg: int, level: Level, wind_kn: float) -> float:
    """Ideal kite size in m2, rounded half-up to 0.1."""
    weight = _check_weight(weight_kg)
    level = Level(level)
    wind = _check_wind(wind_kn)
    raw = LEVEL_SIZE_FACTOR[level] * weight / wind
    return math.floor(raw * 10 + 0.5) / 10


def pick_from_quiver(sizes_m2: Sequence[float], ideal_m2: float) -> float | None:
    """Nearest size by ratio; the boundary is the geometric mean, a tie picks the smaller."""
    sizes = sorted({_check_positive("quiver size", s) for s in sizes_m2})
    ideal = _check_positive("ideal_m2", ideal_m2)
    if not sizes:
        return None
    index = sum(1 for i in range(1, len(sizes)) if ideal * ideal > sizes[i - 1] * sizes[i])
    return sizes[index]


def classify_fit(size_m2: float, ideal_m2: float) -> KiteFit:
    size = _check_positive("size_m2", size_m2)
    ideal = _check_positive("ideal_m2", ideal_m2)
    if size * FIT_TOLERANCE < ideal:
        return KiteFit.UNDERPOWERED
    if size > ideal * FIT_TOLERANCE:
        return KiteFit.OVERPOWERED
    return KiteFit.IDEAL
