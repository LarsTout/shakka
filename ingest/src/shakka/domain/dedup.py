"""Alert deduplication (PROJECT_PLAN section 5). Pure: no I/O, no clock.

Match the stored alert state of one user and one spot to the current go windows and decide
which windows deserve a message: new, improved, worsened or cancelled, at most one per
window. Loading and storing alert_state is WP-10, delivery is WP-17.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shakka.domain.alerts import Window
from shakka.domain.consensus import Confidence, circular_mean_deg
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass

EDGE_SHIFT_THRESHOLD: Final = timedelta(hours=2)  # proposal (A3)
WIND_CHANGE_THRESHOLD_KN: Final = 4.0  # proposal (A3)
SNAPSHOT_KEYS: Final[tuple[str, ...]] = (
    "start",
    "end",
    "wind_min_kn",
    "wind_max_kn",
    "gust_max_kn",
    "dir_deg",
    "dir_class",
    "confidence",
)
ALERT_STATE_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "spot_id",
    "window_start",
    "window_end",
    "status",
    "snapshot",
    "last_event",
    "last_notified_at",
)
AlertStatus = Literal["active", "cancelled", "expired"]

_HOUR: Final = timedelta(hours=1)
_ZERO: Final = timedelta(0)
# Tie-break order for the direction class: least favourable (closest to offshore) wins.
_DIR_CLASS_TIE_ORDER: Final[tuple[DirClass, ...]] = (
    DirClass.ONSHORE,
    DirClass.SIDE_ONSHORE,
    DirClass.SIDESHORE,
)
_CONFIDENCE_RANK: Final[dict[Confidence, int]] = {
    Confidence.LOW: 0,
    Confidence.MEDIUM: 1,
    Confidence.HIGH: 2,
}


class AlertEventKind(StrEnum):
    NEW = "new"
    IMPROVED = "improved"
    WORSENED = "worsened"
    CANCELLED = "cancelled"


class _RevalidatingModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Re-validated copy, so the invariants cannot be bypassed. `deep` is accepted for API
        compatibility; the result is always a freshly validated instance."""
        data = dict(self)
        if update:
            data.update(update)
        return type(self).model_validate(data)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetimes must be timezone-aware")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _floor_hour(value: datetime) -> datetime:
    """Floor an UTC datetime to the hour."""
    return value.replace(minute=0, second=0, microsecond=0)


def _overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> timedelta:
    return max(_ZERO, min(a_end, b_end) - max(a_start, b_start))


def _missing(row: Mapping[str, Any], names: Sequence[str]) -> None:
    absent = [n for n in names if n not in row]
    if absent:
        raise ValueError(f"missing keys: {', '.join(absent)}")


class WindowSnapshot(_RevalidatingModel):
    start: datetime
    end: datetime
    wind_min_kn: float = Field(ge=0, allow_inf_nan=False)
    wind_max_kn: float = Field(ge=0, allow_inf_nan=False)
    gust_max_kn: float | None = Field(ge=0, allow_inf_nan=False)  # None = unknown, never 0
    dir_deg: int = Field(strict=True, ge=0, le=359)  # informative only
    dir_class: DirClass
    confidence: Confidence

    @field_validator("start", "end")
    @classmethod
    def _whole_utc_hour(cls, value: datetime) -> datetime:
        value = _aware_utc(value)
        if value.minute or value.second or value.microsecond:
            raise ValueError("snapshot times must be whole hours")
        return value

    @field_validator("dir_class")
    @classmethod
    def _ridable(cls, value: DirClass) -> DirClass:
        if value not in RIDABLE_DIR_CLASSES:
            raise ValueError("dir_class may only be onshore, side_onshore or sideshore")
        return value

    @model_validator(mode="after")
    def _order(self) -> Self:
        if not self.start < self.end:
            raise ValueError("end must be after start")
        if self.wind_min_kn > self.wind_max_kn:
            raise ValueError("wind_min_kn must not exceed wind_max_kn")
        return self

    def to_json(self) -> dict[str, Any]:
        """JSON-ready dict with exactly SNAPSHOT_KEYS: start/end as 'YYYY-MM-DDTHH:MM:SSZ',
        floats, None, int and enum values (str)."""
        return {
            "start": _iso(self.start),
            "end": _iso(self.end),
            "wind_min_kn": self.wind_min_kn,
            "wind_max_kn": self.wind_max_kn,
            "gust_max_kn": self.gust_max_kn,
            "dir_deg": self.dir_deg,
            "dir_class": self.dir_class.value,
            "confidence": self.confidence.value,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        """Inverse of to_json. Missing keys -> ValueError naming them; extra keys are ignored;
        invalid values -> ValidationError (a ValueError)."""
        _missing(data, SNAPSHOT_KEYS)
        return cls.model_validate({k: data[k] for k in SNAPSHOT_KEYS})


def snapshot_window(window: Window) -> WindowSnapshot:
    """Summary of a go window. ValueError if an hour lacks wind_kn, dir_deg or confidence."""
    winds: list[float] = []
    gusts: list[float] = []
    dirs: list[int] = []
    classes: list[DirClass] = []
    confidences: list[Confidence] = []
    for h in window.hours:
        if h.wind_kn is None or h.dir_deg is None or h.confidence is None or h.dir_class is None:
            raise ValueError(
                f"go hour {h.valid_at.isoformat()} lacks wind, direction or confidence"
            )
        winds.append(h.wind_kn)
        if h.gust_kn is not None:
            gusts.append(h.gust_kn)
        dirs.append(h.dir_deg)
        classes.append(h.dir_class)
        confidences.append(h.confidence)

    mean = circular_mean_deg(dirs)
    dir_deg = dirs[0] if mean is None else int(round(mean)) % 360
    counts = Counter(classes)
    best = max(counts.values())
    dir_class = [c for c in _DIR_CLASS_TIE_ORDER if counts.get(c) == best][-1]
    return WindowSnapshot(
        start=window.start,
        end=window.end,
        wind_min_kn=min(winds),
        wind_max_kn=max(winds),
        gust_max_kn=max(gusts) if gusts else None,
        dir_deg=dir_deg,
        dir_class=dir_class,
        confidence=min(confidences, key=_CONFIDENCE_RANK.__getitem__),
    )


class AlertStateEntry(_RevalidatingModel):
    id: str | None = Field(min_length=1)  # None = not stored yet
    spot_id: str = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    status: AlertStatus
    snapshot: WindowSnapshot  # baseline: what the user was last told (A4)
    last_event: AlertEventKind | None
    last_notified_at: datetime | None  # never changed by diff_windows (A9)

    @field_validator("window_start", "window_end", "last_notified_at")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_utc(value)

    @model_validator(mode="after")
    def _order(self) -> Self:
        if not self.window_start < self.window_end:
            raise ValueError("window_end must be after window_start")
        return self

    def to_row(self) -> dict[str, Any]:
        """alert_state columns without user_id (WP-10 adds it): ALERT_STATE_COLUMNS, but
        'id' only when not None. Datetimes stay aware datetimes (shakka.db encodes them),
        snapshot is to_json(), status/last_event are str or None."""
        row: dict[str, Any] = {}
        if self.id is not None:
            row["id"] = self.id
        row.update(
            spot_id=self.spot_id,
            window_start=self.window_start,
            window_end=self.window_end,
            status=self.status,
            snapshot=self.snapshot.to_json(),
            last_event=None if self.last_event is None else self.last_event.value,
            last_notified_at=self.last_notified_at,
        )
        return row

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """From an alert_state row (PostgREST JSON): all ALERT_STATE_COLUMNS required
        (missing -> ValueError naming them); user_id, created_at, updated_at and other keys
        are ignored. Timestamps may be ISO strings; snapshot is a mapping (from_json)."""
        _missing(row, ALERT_STATE_COLUMNS)
        data = {k: row[k] for k in ALERT_STATE_COLUMNS}
        snap = data["snapshot"]
        if not isinstance(snap, Mapping):
            raise ValueError("snapshot must be a mapping")
        data["snapshot"] = WindowSnapshot.from_json(snap)
        return cls.model_validate(data)


class AlertEvent(_RevalidatingModel):
    kind: AlertEventKind
    spot_id: str = Field(min_length=1)
    current: WindowSnapshot | None
    previous: WindowSnapshot | None
    state_index: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def _by_kind(self) -> Self:
        k = AlertEventKind
        if self.kind == k.NEW:
            ok = self.current is not None and self.previous is None
        elif self.kind == k.CANCELLED:
            ok = self.current is None and self.previous is not None
        else:
            ok = self.current is not None and self.previous is not None
        if not ok:
            raise ValueError(f"current/previous do not fit event kind {self.kind.value}")
        return self


class DiffResult(_RevalidatingModel):
    events: list[AlertEvent]
    new_state: list[AlertStateEntry]
