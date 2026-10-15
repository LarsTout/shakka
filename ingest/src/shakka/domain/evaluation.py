"""Hourly spot evaluation: verdict plus all reasons (PROJECT_PLAN section 4). Pure.

Offshore and side-offshore are always no_go. No function here has a parameter that can
change that, and HourEvaluation refuses to exist in an inconsistent state.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shakka.domain.consensus import Confidence, Consensus, compute_consensus
from shakka.domain.daylight import is_daylight
from shakka.domain.defaults import (
    DEFAULT_MAX_KN,
    DEFAULT_MIN_KN,
    GUST_MIN_DELTA_KN,
    GUSTY_RATIO,
    MIN_LIMIT_SPAN_KN,
    TIDE_HIGH_BAND,
    TIDE_LOW_BAND,
    TIDE_SAMPLE_OFFSET,
    TOO_GUSTY_RATIO,
    WIND_BORDERLINE_KN,
)
from shakka.domain.direction import (
    RIDABLE_DIR_CLASSES,
    DirClass,
    classify_direction,
    in_ranges,
)
from shakka.domain.forecast import ForecastHour
from shakka.domain.season import is_season_closed
from shakka.domain.spot import SpotProfile, SpotStatus, TideSensitivity
from shakka.domain.tide import TideExtreme, estimate_tide_level, relative_tide_position


class Verdict(StrEnum):
    GO = "go"
    MARGINAL = "marginal"
    NO_GO = "no_go"


VERDICT_SEVERITY: Final[dict[Verdict, int]] = {
    Verdict.GO: 0,
    Verdict.MARGINAL: 1,
    Verdict.NO_GO: 2,
}


class ReasonCode(StrEnum):  # declaration order = canonical reason order
    NO_DATA = "no_data"
    WIND_TOO_LIGHT = "wind_too_light"
    WIND_TOO_STRONG = "wind_too_strong"
    WIND_BORDERLINE = "wind_borderline"
    TOO_GUSTY = "too_gusty"
    GUSTY = "gusty"
    OFFSHORE = "offshore"
    SIDE_OFFSHORE = "side_offshore"
    DIRECTION_UNKNOWN = "direction_unknown"
    DIRECTION_NOT_RIDABLE = "direction_not_ridable"
    DARK = "dark"
    SEASON_CLOSED = "season_closed"
    SPOT_FORBIDDEN = "spot_forbidden"
    SPOT_LIMITED = "spot_limited"
    STATUS_UNKNOWN = "status_unknown"
    TIDE_TOO_LOW = "tide_too_low"
    TIDE_UNFAVORABLE = "tide_unfavorable"
    TIDE_UNKNOWN = "tide_unknown"
    LOW_CONFIDENCE = "low_confidence"


_R = ReasonCode
_V = Verdict
REASON_EFFECT: Final[dict[ReasonCode, Verdict]] = {
    _R.NO_DATA: _V.NO_GO,
    _R.WIND_TOO_LIGHT: _V.NO_GO,
    _R.WIND_TOO_STRONG: _V.NO_GO,
    _R.WIND_BORDERLINE: _V.MARGINAL,
    _R.TOO_GUSTY: _V.NO_GO,
    _R.GUSTY: _V.MARGINAL,
    _R.OFFSHORE: _V.NO_GO,
    _R.SIDE_OFFSHORE: _V.NO_GO,
    _R.DIRECTION_UNKNOWN: _V.NO_GO,
    _R.DIRECTION_NOT_RIDABLE: _V.NO_GO,
    _R.DARK: _V.NO_GO,
    _R.SEASON_CLOSED: _V.NO_GO,
    _R.SPOT_FORBIDDEN: _V.NO_GO,
    _R.SPOT_LIMITED: _V.MARGINAL,
    _R.STATUS_UNKNOWN: _V.MARGINAL,
    _R.TIDE_TOO_LOW: _V.NO_GO,
    _R.TIDE_UNFAVORABLE: _V.MARGINAL,
    _R.TIDE_UNKNOWN: _V.MARGINAL,
    _R.LOW_CONFIDENCE: _V.MARGINAL,
}
REASON_LABEL_NL: Final[dict[ReasonCode, str]] = {
    ReasonCode.NO_DATA: "Geen voorspelling beschikbaar",
    ReasonCode.WIND_TOO_LIGHT: "Te weinig wind",
    ReasonCode.WIND_TOO_STRONG: "Te veel wind",
    ReasonCode.WIND_BORDERLINE: "Wind op het randje",
    ReasonCode.TOO_GUSTY: "Te vlagerig",
    ReasonCode.GUSTY: "Vlagerig",
    ReasonCode.OFFSHORE: "Aflandige wind: niet kiten",
    ReasonCode.SIDE_OFFSHORE: "Schuin aflandige wind: niet kiten",
    ReasonCode.DIRECTION_UNKNOWN: "Windrichting of kustrichting onbekend",
    ReasonCode.DIRECTION_NOT_RIDABLE: "Windrichting niet geschikt voor deze spot",
    ReasonCode.DARK: "Donker",
    ReasonCode.SEASON_CLOSED: "Seizoenssluiting",
    ReasonCode.SPOT_FORBIDDEN: "Kiten verboden op deze spot",
    ReasonCode.SPOT_LIMITED: "Kiten beperkt toegestaan",
    ReasonCode.STATUS_UNKNOWN: "Status van de spot onbekend",
    ReasonCode.TIDE_TOO_LOW: "Waterstand te laag",
    ReasonCode.TIDE_UNFAVORABLE: "Ongunstig getij",
    ReasonCode.TIDE_UNKNOWN: "Getij onbekend",
    ReasonCode.LOW_CONFIDENCE: "Weermodellen zijn het oneens",
}
_REASON_ORDER: Final[dict[ReasonCode, int]] = {r: i for i, r in enumerate(ReasonCode)}


def worst_verdict(reasons: Iterable[ReasonCode]) -> Verdict:
    """Most severe REASON_EFFECT; Verdict.GO for no reasons."""
    worst = Verdict.GO
    for r in reasons:
        effect = REASON_EFFECT[r]
        if VERDICT_SEVERITY[effect] > VERDICT_SEVERITY[worst]:
            worst = effect
    return worst


class RiderLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_kn: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    max_kn: Annotated[float, Field(ge=0, allow_inf_nan=False)]

    @model_validator(mode="after")
    def _min_below_max(self) -> Self:
        if not self.min_kn < self.max_kn:
            raise ValueError("max_kn must be greater than min_kn")
        return self


class HourEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spot_id: str = Field(min_length=1)
    valid_at: datetime
    verdict: Verdict
    reasons: tuple[ReasonCode, ...]
    wind_kn: float | None = Field(ge=0, allow_inf_nan=False)
    gust_kn: float | None = Field(ge=0, allow_inf_nan=False)
    dir_deg: int | None = Field(ge=0, le=359)
    dir_class: DirClass | None
    confidence: Confidence | None
    tide_level_cm: int | None

    @field_validator("valid_at")
    @classmethod
    def _whole_utc_hour(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("valid_at must be timezone-aware")
        value = value.astimezone(UTC)
        if value.minute or value.second or value.microsecond:
            raise ValueError("valid_at must be a whole hour")
        return value

    @model_validator(mode="after")
    def _invariants(self) -> Self:
        reasons = self.reasons
        if len(set(reasons)) != len(reasons):
            raise ValueError("reasons must be unique")
        if list(reasons) != sorted(reasons, key=_REASON_ORDER.__getitem__):
            raise ValueError("reasons must be in ReasonCode order")
        if self.verdict != worst_verdict(reasons):
            raise ValueError("verdict must equal the worst effect of the reasons")
        if (self.dir_class == DirClass.OFFSHORE) != (ReasonCode.OFFSHORE in reasons):
            raise ValueError("dir_class offshore requires the reason offshore, and vice versa")
        if (self.dir_class == DirClass.SIDE_OFFSHORE) != (ReasonCode.SIDE_OFFSHORE in reasons):
            raise ValueError(
                "dir_class side_offshore requires the reason side_offshore, and vice versa"
            )
        if (
            self.dir_class in (DirClass.OFFSHORE, DirClass.SIDE_OFFSHORE)
            and self.verdict != Verdict.NO_GO
        ):
            raise ValueError("offshore and side_offshore are always no_go")
        return self

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Re-validated copy, so the invariants cannot be bypassed. `deep` is accepted for API
        compatibility; the result is always a freshly validated instance."""
        data = self.model_dump()
        if update:
            data.update(update)
        return type(self).model_validate(data)

    def to_row(self, *, evaluated_at: datetime) -> dict[str, Any]:
        """Row for public.evaluations. Keys exactly: spot_id, valid_at, verdict, reasons
        (list[str]), wind_kn, gust_kn, dir_deg, dir_class (str | None), confidence (str | None),
        tide_level_cm, evaluated_at. Naive evaluated_at -> ValueError."""
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return {
            "spot_id": self.spot_id,
            "valid_at": self.valid_at,
            "verdict": self.verdict.value,
            "reasons": [r.value for r in self.reasons],
            "wind_kn": self.wind_kn,
            "gust_kn": self.gust_kn,
            "dir_deg": self.dir_deg,
            "dir_class": None if self.dir_class is None else self.dir_class.value,
            "confidence": None if self.confidence is None else self.confidence.value,
            "tide_level_cm": self.tide_level_cm,
            "evaluated_at": evaluated_at,
        }


def default_limits(spot: SpotProfile) -> RiderLimits:
    min_kn = float(spot.default_min_kn) if spot.default_min_kn is not None else DEFAULT_MIN_KN
    return RiderLimits(min_kn=min_kn, max_kn=max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN))


def _station_tides(spot: SpotProfile, tides: Sequence[TideExtreme]) -> list[TideExtreme]:
    if spot.rws_station is None:
        return []
    station = spot.rws_station.strip()
    return [t for t in tides if t.station == station]


def _wind_reasons(c: Consensus | None, limits: RiderLimits) -> set[ReasonCode]:
    out: set[ReasonCode] = set()
    if c is None or c.wind_kn is None:
        return out
    w = c.wind_kn
    if w < limits.min_kn:
        out.add(ReasonCode.WIND_TOO_LIGHT)
    elif w > limits.max_kn:
        out.add(ReasonCode.WIND_TOO_STRONG)
    elif w < limits.min_kn + WIND_BORDERLINE_KN or w > limits.max_kn - WIND_BORDERLINE_KN:
        out.add(ReasonCode.WIND_BORDERLINE)
    g = c.gust_kn
    if g is not None and w > 0 and g - w >= GUST_MIN_DELTA_KN:
        if g >= TOO_GUSTY_RATIO * w:
            out.add(ReasonCode.TOO_GUSTY)
        elif g >= GUSTY_RATIO * w:
            out.add(ReasonCode.GUSTY)
    return out


def _direction(spot: SpotProfile, c: Consensus | None) -> tuple[DirClass | None, set[ReasonCode]]:
    out: set[ReasonCode] = set()
    if spot.shore_normal_deg is None or c is None or c.dir_mean_deg is None:
        out.add(ReasonCode.DIRECTION_UNKNOWN)
        return None, out
    # The class is decided on the unrounded mean (A15), never on the rounded dir_deg.
    dir_class = classify_direction(c.dir_mean_deg, spot.shore_normal_deg)
    if dir_class == DirClass.OFFSHORE:
        out.add(ReasonCode.OFFSHORE)
    elif dir_class == DirClass.SIDE_OFFSHORE:
        out.add(ReasonCode.SIDE_OFFSHORE)
    elif spot.ridable_dirs is not None and not in_ranges(c.dir_mean_deg, spot.ridable_dirs):
        assert dir_class in RIDABLE_DIR_CLASSES
        out.add(ReasonCode.DIRECTION_NOT_RIDABLE)
    return dir_class, out


def _tide(
    spot: SpotProfile, ext: Sequence[TideExtreme], sample: datetime
) -> tuple[int | None, set[ReasonCode]]:
    out: set[ReasonCode] = set()
    level = estimate_tide_level(ext, sample) if ext else None
    sensitivity = spot.tide_sensitive
    if sensitivity == TideSensitivity.NONE:
        return level, out
    if level is None:
        out.add(ReasonCode.TIDE_UNKNOWN)
        return level, out
    if spot.tide_min_level_cm is not None and level < spot.tide_min_level_cm:
        out.add(ReasonCode.TIDE_TOO_LOW)
        return level, out
    if sensitivity == TideSensitivity.AVOID_LOW and spot.tide_min_level_cm is not None:
        return level, out
    pos = relative_tide_position(ext, sample)
    if pos is None:
        out.add(ReasonCode.TIDE_UNKNOWN)
    else:
        unfavorable = (
            (sensitivity == TideSensitivity.PREFER_LOW and pos > TIDE_LOW_BAND)
            or (sensitivity == TideSensitivity.PREFER_HIGH and pos < TIDE_HIGH_BAND)
            or (sensitivity == TideSensitivity.AVOID_LOW and pos <= TIDE_LOW_BAND)
        )
        if unfavorable:
            out.add(ReasonCode.TIDE_UNFAVORABLE)
    return level, out


def _evaluate(
    spot: SpotProfile,
    valid_at: datetime,
    hours: Sequence[ForecastHour],
    ext: Sequence[TideExtreme],
    limits: RiderLimits,
) -> HourEvaluation:
    if valid_at.tzinfo is None or valid_at.utcoffset() is None:
        raise ValueError("valid_at must be timezone-aware")
    valid_at = valid_at.astimezone(UTC)
    if valid_at.minute or valid_at.second or valid_at.microsecond:
        raise ValueError("valid_at must be a whole hour")
    for h in hours:
        if h.spot_id != spot.id:
            raise ValueError("forecast hour belongs to another spot")
        if h.valid_at != valid_at:
            raise ValueError("forecast hour has another valid_at")
    if spot.lat is None or spot.lon is None:
        raise ValueError("spot has no coordinates; daylight cannot be determined")

    c = compute_consensus(hours)
    reasons: set[ReasonCode] = set()
    if c is None or c.wind_kn is None:
        reasons.add(ReasonCode.NO_DATA)
    reasons |= _wind_reasons(c, limits)
    dir_class, dir_reasons = _direction(spot, c)
    reasons |= dir_reasons
    if not is_daylight(spot.lat, spot.lon, valid_at):
        reasons.add(ReasonCode.DARK)
    if is_season_closed(spot.season, valid_at):
        reasons.add(ReasonCode.SEASON_CLOSED)
    if spot.status == SpotStatus.FORBIDDEN:
        reasons.add(ReasonCode.SPOT_FORBIDDEN)
    elif spot.status == SpotStatus.LIMITED:
        reasons.add(ReasonCode.SPOT_LIMITED)
    elif spot.status is None:
        reasons.add(ReasonCode.STATUS_UNKNOWN)
    level, tide_reasons = _tide(spot, ext, valid_at + TIDE_SAMPLE_OFFSET)
    reasons |= tide_reasons
    if c is not None and c.confidence == Confidence.LOW:
        reasons.add(ReasonCode.LOW_CONFIDENCE)

    ordered = tuple(sorted(reasons, key=_REASON_ORDER.__getitem__))
    return HourEvaluation(
        spot_id=spot.id,
        valid_at=valid_at,
        verdict=worst_verdict(ordered),
        reasons=ordered,
        wind_kn=None if c is None else c.wind_kn,
        gust_kn=None if c is None else c.gust_kn,
        dir_deg=None if c is None else c.dir_deg,
        dir_class=dir_class,
        confidence=None if c is None else c.confidence,
        tide_level_cm=level,
    )


def evaluate_hour(
    spot: SpotProfile,
    valid_at: datetime,
    hours: Sequence[ForecastHour],
    tides: Sequence[TideExtreme],
    limits: RiderLimits,
) -> HourEvaluation:
    """Verdict and all reasons for one spot and one hour [valid_at, valid_at + 1h).
    ValueError on a naive or non-whole-hour valid_at, forecast hours of another spot or hour,
    or a spot without coordinates."""
    return _evaluate(spot, valid_at, hours, _station_tides(spot, tides), limits)


def evaluate_spot(
    spot: SpotProfile,
    forecasts: Sequence[ForecastHour],
    tides: Sequence[TideExtreme],
    limits: RiderLimits,
) -> list[HourEvaluation]:
    """One evaluation per unique valid_at, ascending. [] without forecasts."""
    by_hour: dict[datetime, list[ForecastHour]] = defaultdict(list)
    for f in forecasts:
        if f.spot_id != spot.id:
            raise ValueError("forecast hour belongs to another spot")
        by_hour[f.valid_at].append(f)
    ext = _station_tides(spot, tides)
    return [_evaluate(spot, at, by_hour[at], ext, limits) for at in sorted(by_hour)]
