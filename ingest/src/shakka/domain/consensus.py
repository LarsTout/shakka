"""Consensus over the forecast models for one spot and one hour. Pure."""

import math
import statistics
from collections.abc import Sequence
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from shakka.domain.defaults import (
    CONFIDENCE_HIGH_DIR_SPREAD_DEG,
    CONFIDENCE_HIGH_MIN_MODELS,
    CONFIDENCE_HIGH_SPEED_SPREAD_KN,
    CONFIDENCE_LOW_DIR_SPREAD_DEG,
    CONFIDENCE_LOW_SPEED_SPREAD_KN,
    DIR_MEAN_DECIMALS,
    DIR_MIN_RESULTANT,
)
from shakka.domain.direction import angular_distance
from shakka.domain.forecast import ForecastHour, ModelKey


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


CONFIDENCE_LABEL_NL: Final[dict[Confidence, str]] = {
    Confidence.HIGH: "Hoog",
    Confidence.MEDIUM: "Gemiddeld",
    Confidence.LOW: "Laag",
}


class Consensus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    wind_kn: float | None
    gust_kn: float | None
    dir_deg: int | None  # 0..359, whole degrees, informative
    confidence: Confidence
    models_used: tuple[ModelKey, ...]
    speed_spread_kn: float | None = None
    dir_spread_deg: float | None = None
    dir_mean_deg: float | None = None  # [0, 360), unrounded mean (DIR_MEAN_DECIMALS); class basis

    @model_validator(mode="after")
    def _check_direction(self) -> Self:
        if (self.dir_deg is None) != (self.dir_mean_deg is None):
            raise ValueError("dir_deg and dir_mean_deg must both be set or both be None")
        if self.dir_mean_deg is not None and self.dir_deg is not None:
            if not 0 <= self.dir_mean_deg < 360:
                raise ValueError("dir_mean_deg must be in [0, 360)")
            if self.dir_deg != int(round(self.dir_mean_deg)) % 360:
                raise ValueError("dir_deg must be int(round(dir_mean_deg)) % 360")
        return self


def circular_mean_deg(degrees: Sequence[float]) -> float | None:
    """Unweighted circular mean in [0, 360), rounded to DIR_MEAN_DECIMALS decimals and taken
    modulo 360 (float noise only); None if empty or the mean resultant length is below
    DIR_MIN_RESULTANT."""
    if not degrees:
        return None
    sx = sum(math.cos(math.radians(d)) for d in degrees)
    sy = sum(math.sin(math.radians(d)) for d in degrees)
    if math.hypot(sx, sy) / len(degrees) < DIR_MIN_RESULTANT:
        return None
    mean = math.degrees(math.atan2(sy, sx)) % 360
    return round(mean, DIR_MEAN_DECIMALS) % 360


def _confidence(
    n_wind: int,
    n_dir: int,
    speed_spread: float | None,
    dir_deg: int | None,
    dir_spread: float | None,
    gust: float | None,
) -> Confidence:
    if n_wind <= 1:
        return Confidence.LOW
    if dir_deg is None or speed_spread is None or dir_spread is None:
        return Confidence.LOW
    if speed_spread > CONFIDENCE_LOW_SPEED_SPREAD_KN or dir_spread > CONFIDENCE_LOW_DIR_SPREAD_DEG:
        return Confidence.LOW
    if (
        n_wind >= CONFIDENCE_HIGH_MIN_MODELS
        and n_dir >= CONFIDENCE_HIGH_MIN_MODELS
        and speed_spread <= CONFIDENCE_HIGH_SPEED_SPREAD_KN
        and dir_spread <= CONFIDENCE_HIGH_DIR_SPREAD_DEG
        and gust is not None
    ):
        return Confidence.HIGH
    return Confidence.MEDIUM


def compute_consensus(hours: Sequence[ForecastHour]) -> Consensus | None:
    """Consensus over the models of one spot and one valid_at.

    Wind and gust are medians over the models that have a value; the direction is the
    circular mean. A single model always gives confidence low: without a second model
    there is no spread to measure. None if no model has any value.
    ValueError on mixed spot_id/valid_at or a duplicate model."""
    if not hours:
        return None
    if len({h.spot_id for h in hours}) > 1:
        raise ValueError("hours from more than one spot")
    if len({h.valid_at for h in hours}) > 1:
        raise ValueError("hours with more than one valid_at")
    if len({h.model for h in hours}) != len(hours):
        raise ValueError("duplicate model in hours")
    used = [
        h for h in hours if h.wind_kn is not None or h.gust_kn is not None or h.dir_deg is not None
    ]
    if not used:
        return None
    order = list(ModelKey)
    models_used = tuple(sorted((h.model for h in used), key=order.index))
    winds = [h.wind_kn for h in used if h.wind_kn is not None]
    gusts = [h.gust_kn for h in used if h.gust_kn is not None]
    dirs = [h.dir_deg for h in used if h.dir_deg is not None]

    wind = round(statistics.median(winds), 1) if winds else None
    gust = round(statistics.median(gusts), 1) if gusts else None
    speed_spread = round(max(winds) - min(winds), 1) if winds else None
    mean = circular_mean_deg(dirs)
    dir_deg = None if mean is None else int(round(mean)) % 360
    dir_spread = None if mean is None else round(max(angular_distance(d, mean) for d in dirs), 1)
    confidence = _confidence(len(winds), len(dirs), speed_spread, dir_deg, dir_spread, gust)
    return Consensus(
        wind_kn=wind,
        gust_kn=gust,
        dir_deg=dir_deg,
        confidence=confidence,
        models_used=models_used,
        speed_spread_kn=speed_spread,
        dir_spread_deg=dir_spread,
        dir_mean_deg=mean,
    )
