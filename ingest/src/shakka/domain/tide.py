"""Tide extremes and water level interpolation. Pure: no I/O, no clock."""

import math
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shakka.domain.defaults import TIDE_NEIGHBOUR_WINDOW

TideKind = Literal["high", "low"]
MAX_EXTREME_GAP: Final = timedelta(hours=9)  # gap > this between two extremes -> no estimate
MAX_ABS_LEVEL_CM: Final = 1000  # sanity bound for NAP levels in cm


class TideExtreme(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    station: Annotated[str, Field(min_length=1, max_length=64)]
    at: datetime
    kind: TideKind
    level_cm: Annotated[int, Field(strict=True, ge=-MAX_ABS_LEVEL_CM, le=MAX_ABS_LEVEL_CM)]

    @field_validator("at")
    @classmethod
    def _aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        return value.astimezone(UTC)

    def to_row(self) -> dict[str, Any]:
        """{"station", "at" (aware UTC datetime), "kind", "level_cm"}; the job adds fetched_at."""
        return {
            "station": self.station,
            "at": self.at,
            "kind": self.kind,
            "level_cm": self.level_cm,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "TideExtreme":
        """Build from a tide_extremes row (PostgREST JSON); ignores other keys (fetched_at)."""
        at = row["at"]
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        return cls(station=row["station"], at=at, kind=row["kind"], level_cm=row["level_cm"])


def estimate_tide_level(extremes: Sequence[TideExtreme], at: datetime) -> int | None:
    """Estimate the water level (cm NAP) at `at` with a cosine between consecutive extremes.

    None when outside the extremes, or when the surrounding gap exceeds MAX_EXTREME_GAP.
    """
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("at must be timezone-aware")
    if not extremes:
        return None
    if len({e.station for e in extremes}) > 1:
        raise ValueError("extremes from more than one station")
    by_time: dict[datetime, TideExtreme] = {}
    for e in extremes:
        known = by_time.get(e.at)
        if known is not None and known.level_cm != e.level_cm:
            raise ValueError("conflicting levels at the same instant")
        by_time[e.at] = e
    times = sorted(by_time)
    t = at.astimezone(UTC)
    i = bisect_left(times, t)
    if i < len(times) and times[i] == t:
        return by_time[t].level_cm
    if i == 0 or i == len(times):
        return None
    t0, t1 = times[i - 1], times[i]
    if t1 - t0 > MAX_EXTREME_GAP:
        return None
    h0, h1 = by_time[t0].level_cm, by_time[t1].level_cm
    f = (t - t0) / (t1 - t0)
    h = h0 + (h1 - h0) * (1 - math.cos(math.pi * f)) / 2
    return math.floor(h + 0.5)


def relative_tide_position(extremes: Sequence[TideExtreme], at: datetime) -> float | None:
    """Position of the estimated level at `at` between the nearest low (0.0) and the nearest
    high (1.0) water within TIDE_NEIGHBOUR_WINDOW, clamped to [0, 1]. Ties: earliest wins.
    None if estimate_tide_level is None, a kind is missing in the window, or high <= low.
    Does not assume that high and low alternate (double low water is fine)."""
    level = estimate_tide_level(extremes, at)
    if level is None:
        return None
    t = at.astimezone(UTC)
    near = [e for e in extremes if abs(e.at - t) <= TIDE_NEIGHBOUR_WINDOW]
    lows = [e for e in near if e.kind == "low"]
    highs = [e for e in near if e.kind == "high"]
    if not lows or not highs:
        return None
    low = min(lows, key=lambda e: (abs(e.at - t), e.at))
    high = min(highs, key=lambda e: (abs(e.at - t), e.at))
    if high.level_cm <= low.level_cm:
        return None
    return min(1.0, max(0.0, (level - low.level_cm) / (high.level_cm - low.level_cm)))
