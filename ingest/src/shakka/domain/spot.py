"""Spot profile model: one entry in data/spots.yaml and one row of `spots`."""

import math
import re
from collections.abc import Callable, Mapping
from datetime import date, time
from enum import StrEnum
from typing import Annotated, Any, Final, NamedTuple, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


class Level(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SpotStatus(StrEnum):
    ALLOWED = "allowed"
    LIMITED = "limited"
    FORBIDDEN = "forbidden"


class TideSensitivity(StrEnum):
    NONE = "none"
    PREFER_LOW = "prefer_low"
    PREFER_HIGH = "prefer_high"
    AVOID_LOW = "avoid_low"


SPOT_ID_PATTERN: Final = r"[a-z0-9]+(-[a-z0-9]+)*"  # always used with re.fullmatch
NL_LAT_RANGE: Final = (50.7, 53.7)  # inclusive
NL_LON_RANGE: Final = (3.2, 7.3)  # inclusive
TIDE_MIN_LEVEL_RANGE_CM: Final = (-300, 300)
DEFAULT_MIN_KN_RANGE: Final = (5, 40)
VERIFIED_REQUIRED_FIELDS: Final = ("lat", "lon", "shore_normal_deg", "status", "level")
# Columns of public.spots (WP-01) without updated_at, in table order.
SPOT_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "name",
    "region",
    "lat",
    "lon",
    "shore_normal_deg",
    "ridable_dirs",
    "hazards",
    "tide_sensitive",
    "tide_min_level_cm",
    "rws_station",
    "season",
    "status",
    "level",
    "default_min_kn",
    "notes",
    "verified",
)

_MONTH_DAY_MESSAGE: Final = "expected a quoted 'MM-DD' date, e.g. \"05-01\""
_TIME_MESSAGE: Final = "expected a quoted 'HH:MM' time (24h), e.g. \"10:00\""
_SLUG_MESSAGE: Final = 'expected a lowercase slug (a-z, 0-9, single hyphens), e.g. "wijk-aan-zee"'


def _strict_int(v: Any) -> Any:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError("expected an integer")
    return v


def _number(v: Any) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise ValueError("expected a number")
    if not math.isfinite(v):
        raise ValueError("expected a finite number")
    return float(v)


def _not_blank(v: str) -> str:
    if "\x00" in v:
        raise ValueError("must not contain NUL characters")
    if v.strip() == "":
        raise ValueError("must not be blank")
    return v


def _month_day(v: Any) -> Any:
    if not isinstance(v, str) or re.fullmatch(r"[0-9]{2}-[0-9]{2}", v) is None:
        raise ValueError(_MONTH_DAY_MESSAGE)
    try:
        date(2000, int(v[:2]), int(v[3:]))  # 2000 is a leap year, so 02-29 is allowed
    except ValueError:
        raise ValueError(_MONTH_DAY_MESSAGE) from None
    return v


def _local_time(v: Any) -> Any:
    if isinstance(v, time):
        if v.tzinfo is None and v.second == 0 and v.microsecond == 0:
            return v
        raise ValueError(_TIME_MESSAGE)
    if isinstance(v, str) and re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", v):
        return time(int(v[:2]), int(v[3:]))
    raise ValueError(_TIME_MESSAGE)


def _spot_id(v: Any) -> Any:
    if not isinstance(v, str) or re.fullmatch(SPOT_ID_PATTERN, v) is None:
        raise ValueError(_SLUG_MESSAGE)
    return v


def _none_to(default: Any) -> Callable[[Any], Any]:
    def convert(v: Any) -> Any:
        return default if v is None else v

    return convert


def _verified(v: Any) -> Any:
    if v is None:
        return False
    if not isinstance(v, bool):
        raise ValueError("expected true or false")
    return v


_StrictInt = BeforeValidator(_strict_int)
_Number = BeforeValidator(_number)
_NonBlankStr = Annotated[str, StringConstraints(strict=True), AfterValidator(_not_blank)]
_MonthDay = Annotated[str, BeforeValidator(_month_day)]
_LocalTime = Annotated[time, BeforeValidator(_local_time)]
_SpotId = Annotated[str, BeforeValidator(_spot_id)]


class DirRange(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", validate_by_name=True, validate_by_alias=True
    )

    from_deg: Annotated[int, _StrictInt, Field(ge=0, le=359)] = Field(alias="from")
    to_deg: Annotated[int, _StrictInt, Field(ge=0, le=359)] = Field(alias="to")


class SeasonClosure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start: _MonthDay
    end: _MonthDay
    from_time: _LocalTime | None = None
    to_time: _LocalTime | None = None
    note: _NonBlankStr | None = None

    @model_validator(mode="after")
    def _check_times(self) -> Self:
        if (self.from_time is None) != (self.to_time is None):
            raise ValueError("from_time and to_time must both be set or both be empty")
        if (
            self.from_time is not None
            and self.to_time is not None
            and (self.from_time >= self.to_time)
        ):
            raise ValueError("from_time must be before to_time")
        return self


class SpotProfileBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: _SpotId
    name: _NonBlankStr
    region: _NonBlankStr | None = None
    lat: Annotated[float, _Number, Field(ge=50.7, le=53.7)] | None = None
    lon: Annotated[float, _Number, Field(ge=3.2, le=7.3)] | None = None
    shore_normal_deg: Annotated[int, _StrictInt, Field(ge=0, le=359)] | None = None
    ridable_dirs: Annotated[tuple[DirRange, ...], Field(min_length=1)] | None = None
    hazards: _NonBlankStr | None = None
    tide_sensitive: Annotated[TideSensitivity, BeforeValidator(_none_to(TideSensitivity.NONE))] = (
        TideSensitivity.NONE
    )
    tide_min_level_cm: Annotated[int, _StrictInt, Field(ge=-300, le=300)] | None = None
    rws_station: _NonBlankStr | None = None
    season: Annotated[tuple[SeasonClosure, ...], BeforeValidator(_none_to(()))] = ()
    status: SpotStatus | None = None
    level: Level | None = None
    default_min_kn: Annotated[int, _StrictInt, Field(ge=5, le=40)] | None = None
    notes: _NonBlankStr | None = None
    verified: Annotated[bool, BeforeValidator(_verified)] = False


class SpotRuleViolation(NamedTuple):
    field: str
    message: str


def spot_rule_violations(spot: SpotProfileBase) -> list[SpotRuleViolation]:
    """Cross-field rules, each violation separately, in this fixed order:
    1. lat/lon must be set together;
    2. tide_min_level_cm only when tide_sensitive is not none;
    3. verified spots need the fields in VERIFIED_REQUIRED_FIELDS (and rws_station for tides).
    Rule 3 does not repeat a field already reported by rule 1."""
    out: list[SpotRuleViolation] = []
    reported: set[str] = set()
    if spot.lat is not None and spot.lon is None:
        out.append(SpotRuleViolation("lon", "required when lat is set"))
        reported.add("lon")
    if spot.lon is not None and spot.lat is None:
        out.append(SpotRuleViolation("lat", "required when lon is set"))
        reported.add("lat")
    if spot.tide_min_level_cm is not None and spot.tide_sensitive == TideSensitivity.NONE:
        out.append(
            SpotRuleViolation("tide_min_level_cm", "only allowed when tide_sensitive is not none")
        )
    if spot.verified:
        for name in VERIFIED_REQUIRED_FIELDS:
            if name not in reported and getattr(spot, name) is None:
                out.append(SpotRuleViolation(name, "required when verified is true"))
        if spot.tide_sensitive != TideSensitivity.NONE and spot.rws_station is None:
            out.append(
                SpotRuleViolation(
                    "rws_station",
                    "required when verified is true and tide_sensitive is not none",
                )
            )
    return out


def _hhmm(t: time | None) -> str | None:
    return None if t is None else f"{t.hour:02d}:{t.minute:02d}"


class SpotProfile(SpotProfileBase):
    @model_validator(mode="after")
    def _check_rules(self) -> Self:
        violations = spot_rule_violations(self)
        if violations:
            raise ValueError("; ".join(f"{v.field}: {v.message}" for v in violations))
        return self

    def to_row(self) -> dict[str, Any]:
        """JSON-ready dict with exactly the keys of SPOT_COLUMNS, in table order."""
        return {
            "id": self.id,
            "name": self.name,
            "region": self.region,
            "lat": self.lat,
            "lon": self.lon,
            "shore_normal_deg": self.shore_normal_deg,
            "ridable_dirs": (
                None
                if self.ridable_dirs is None
                else [{"from": d.from_deg, "to": d.to_deg} for d in self.ridable_dirs]
            ),
            "hazards": self.hazards,
            "tide_sensitive": self.tide_sensitive.value,
            "tide_min_level_cm": self.tide_min_level_cm,
            "rws_station": self.rws_station,
            "season": [
                {
                    "start": s.start,
                    "end": s.end,
                    "from_time": _hhmm(s.from_time),
                    "to_time": _hhmm(s.to_time),
                    "note": s.note,
                }
                for s in self.season
            ],
            "status": None if self.status is None else self.status.value,
            "level": None if self.level is None else self.level.value,
            "default_min_kn": self.default_min_kn,
            "notes": self.notes,
            "verified": self.verified,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "SpotProfile":
        """Build a profile from a `spots` row. Extra keys are ignored; missing columns raise."""
        missing = [c for c in SPOT_COLUMNS if c not in row]
        if missing:
            raise ValueError(f"spots row is missing columns: {', '.join(missing)}")
        return cls.model_validate({c: row[c] for c in SPOT_COLUMNS})
