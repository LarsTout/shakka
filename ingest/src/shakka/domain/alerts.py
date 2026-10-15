"""Alert rules and go windows (PROJECT_PLAN section 5). Pure.

An alert rule is assembled from the user's rule, profile defaults, spot and system defaults.
Offshore and side-offshore can never be part of a rule: AlertRuleOverride and AlertRule both
refuse them, and Window refuses any hour that is not a ridable go.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from shakka.domain.defaults import DEFAULT_MAX_KN, DEFAULT_MIN_KN, LOCAL_TZ, MIN_LIMIT_SPAN_KN
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass
from shakka.domain.evaluation import HourEvaluation, RiderLimits, Verdict
from shakka.domain.spot import SpotProfile

DEFAULT_MIN_GO_HOURS: Final = 2
DEFAULT_DAYS_AHEAD: Final = 3
ISO_WEEKDAYS: Final[frozenset[int]] = frozenset(range(1, 8))
DEFAULT_WEEKDAYS: Final[frozenset[int]] = ISO_WEEKDAYS
DEFAULT_DIR_CLASSES: Final[frozenset[DirClass]] = RIDABLE_DIR_CLASSES
# Mirrors of the CHECK constraints on alert_rules and profiles (WP-01), inclusive.
ALERT_KN_RANGE: Final = (5, 60)
MIN_GO_HOURS_RANGE: Final = (1, 24)
DAYS_AHEAD_RANGE: Final = (0, 7)
# Postgres `time` allows 24:00:00; Python `time` does not. latest_local 24:00 -> None.
END_OF_DAY_TIME_STRINGS: Final[frozenset[str]] = frozenset({"24:00", "24:00:00"})

_IsoWeekday = Annotated[StrictInt, Field(ge=1, le=7)]  # strict per element, list input OK


class RuleSource(StrEnum):  # declaration order = priority, highest first
    RULE = "rule"
    PROFILE = "profile"
    SPOT = "spot"
    SYSTEM = "system"


RULE_FIELDS: Final[tuple[str, ...]] = (
    "enabled",
    "min_kn",
    "max_kn",
    "dir_classes",
    "weekdays",
    "earliest_local",
    "latest_local",
    "min_go_hours",
    "days_ahead",
)
FIELD_SOURCES: Final[dict[str, tuple[RuleSource, ...]]] = {
    "enabled": (RuleSource.RULE, RuleSource.SYSTEM),
    "min_kn": (RuleSource.RULE, RuleSource.PROFILE, RuleSource.SPOT, RuleSource.SYSTEM),
    "max_kn": (RuleSource.RULE, RuleSource.PROFILE, RuleSource.SYSTEM),
    "dir_classes": (RuleSource.RULE, RuleSource.SYSTEM),
    "weekdays": (RuleSource.RULE, RuleSource.SYSTEM),
    "earliest_local": (RuleSource.RULE, RuleSource.SYSTEM),
    "latest_local": (RuleSource.RULE, RuleSource.SYSTEM),
    "min_go_hours": (RuleSource.RULE, RuleSource.SYSTEM),
    "days_ahead": (RuleSource.RULE, RuleSource.SYSTEM),
}
FIELD_LABEL_NL: Final[dict[str, str]] = {
    "enabled": "Alert aan",
    "min_kn": "Minimale wind (kn)",
    "max_kn": "Maximale wind (kn)",
    "dir_classes": "Windrichtingen",
    "weekdays": "Dagen",
    "earliest_local": "Vanaf (lokale tijd)",
    "latest_local": "Tot (lokale tijd)",
    "min_go_hours": "Minimaal aantal go-uren achter elkaar",
    "days_ahead": "Dagen vooruit (na vandaag)",
}


class _RevalidatingModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Re-validated copy, so the invariants cannot be bypassed. `deep` is accepted for API
        compatibility; the result is always a freshly validated instance."""
        data = dict(self)
        if update:
            data.update(update)
        return type(self).model_validate(data)


def _check_dir_classes(value: frozenset[DirClass] | None) -> frozenset[DirClass] | None:
    if value is None:
        return None
    if not value:
        raise ValueError("dir_classes must not be empty")
    if not value <= RIDABLE_DIR_CLASSES:
        raise ValueError("dir_classes may only contain onshore, side_onshore and sideshore")
    return value


def _check_weekdays(value: frozenset[int] | None) -> frozenset[int] | None:
    if value is not None and not value:
        raise ValueError("weekdays must not be empty")
    return value


def _check_naive(value: time | None) -> time | None:
    if value is not None and value.tzinfo is not None:
        raise ValueError("local times must not carry a timezone")
    return value


def _check_time_window(earliest: time | None, latest: time | None) -> None:
    if earliest is not None and latest is not None and not earliest < latest:
        raise ValueError("earliest_local must be before latest_local")


def _missing(row: Mapping[str, Any], names: Sequence[str]) -> None:
    absent = [n for n in names if n not in row]
    if absent:
        raise ValueError(f"row is missing columns: {', '.join(absent)}")


class AlertRuleOverride(_RevalidatingModel):
    enabled: bool | None = Field(default=None, strict=True)
    min_kn: int | None = Field(default=None, strict=True, ge=5, le=60)
    max_kn: int | None = Field(default=None, strict=True, ge=5, le=60)
    dir_classes: frozenset[DirClass] | None = None
    weekdays: frozenset[_IsoWeekday] | None = None
    earliest_local: time | None = None
    latest_local: time | None = None
    min_go_hours: int | None = Field(default=None, strict=True, ge=1, le=24)
    days_ahead: int | None = Field(default=None, strict=True, ge=0, le=7)

    @field_validator("earliest_local", mode="before")
    @classmethod
    def _earliest_not_end_of_day(cls, value: Any) -> Any:
        if isinstance(value, str) and value in END_OF_DAY_TIME_STRINGS:
            raise ValueError("earliest_local 24:00 matches no hour; use null or an earlier time")
        return value

    @field_validator("latest_local", mode="before")
    @classmethod
    def _latest_end_of_day_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value in END_OF_DAY_TIME_STRINGS:
            return None
        return value

    @field_validator("earliest_local", "latest_local")
    @classmethod
    def _naive(cls, value: time | None) -> time | None:
        return _check_naive(value)

    @field_validator("dir_classes")
    @classmethod
    def _ridable(cls, value: frozenset[DirClass] | None) -> frozenset[DirClass] | None:
        return _check_dir_classes(value)

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, value: frozenset[int] | None) -> frozenset[int] | None:
        return _check_weekdays(value)

    @model_validator(mode="after")
    def _cross_checks(self) -> Self:
        if self.min_kn is not None and self.max_kn is not None and not self.min_kn < self.max_kn:
            raise ValueError("min_kn must be below max_kn")
        _check_time_window(self.earliest_local, self.latest_local)
        return self

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """From an alert_rules row: exactly the RULE_FIELDS columns. Missing columns raise
        ValueError (names listed); user_id, spot_id, updated_at and other keys are ignored.
        Invalid values raise ValidationError (a ValueError)."""
        _missing(row, RULE_FIELDS)
        return cls.model_validate({name: row[name] for name in RULE_FIELDS})


class ProfileDefaults(_RevalidatingModel):
    default_min_kn: int | None = Field(default=None, strict=True, ge=5, le=60)
    default_max_kn: int | None = Field(default=None, strict=True, ge=5, le=60)

    @model_validator(mode="after")
    def _min_below_max(self) -> Self:
        lo, hi = self.default_min_kn, self.default_max_kn
        if lo is not None and hi is not None and not lo < hi:
            raise ValueError("default_min_kn must be below default_max_kn")
        return self

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """From a profiles row: default_min_kn and default_max_kn (missing -> ValueError);
        other columns are ignored."""
        names = ("default_min_kn", "default_max_kn")
        _missing(row, names)
        return cls.model_validate({name: row[name] for name in names})


class AlertRule(_RevalidatingModel):
    enabled: bool = Field(strict=True)
    min_kn: float = Field(ge=0, allow_inf_nan=False)
    max_kn: float = Field(allow_inf_nan=False)
    dir_classes: frozenset[DirClass]
    weekdays: frozenset[_IsoWeekday]
    earliest_local: time | None
    latest_local: time | None
    min_go_hours: int = Field(strict=True, ge=1, le=24)
    days_ahead: int = Field(strict=True, ge=0, le=7)

    @field_validator("earliest_local", "latest_local")
    @classmethod
    def _naive(cls, value: time | None) -> time | None:
        return _check_naive(value)

    @field_validator("dir_classes")
    @classmethod
    def _ridable(cls, value: frozenset[DirClass]) -> frozenset[DirClass]:
        checked = _check_dir_classes(value)
        assert checked is not None
        return checked

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, value: frozenset[int]) -> frozenset[int]:
        checked = _check_weekdays(value)
        assert checked is not None
        return checked

    @model_validator(mode="after")
    def _cross_checks(self) -> Self:
        if not self.min_kn < self.max_kn:
            raise ValueError("max_kn must be greater than min_kn")
        _check_time_window(self.earliest_local, self.latest_local)
        return self


def resolve_rule(
    spot: SpotProfile, profile: ProfileDefaults | None, override: AlertRuleOverride | None
) -> AlertRule:
    """Effective rule: per field the first non-None of rule, profile, spot, system (see the
    table in the blueprint). max_kn without rule/profile value is
    max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN). ValueError if an explicit max_kn is not
    above the effective min_kn (message names both values and sources), or if the result is
    invalid (e.g. an offshore class)."""
    o = override if override is not None else AlertRuleOverride()
    p = profile if profile is not None else ProfileDefaults()

    # min_kn: rule > profile > spot > system
    min_source: RuleSource
    if o.min_kn is not None:
        min_kn, min_source = float(o.min_kn), RuleSource.RULE
    elif p.default_min_kn is not None:
        min_kn, min_source = float(p.default_min_kn), RuleSource.PROFILE
    elif spot.default_min_kn is not None:
        min_kn, min_source = float(spot.default_min_kn), RuleSource.SPOT
    else:
        min_kn, min_source = DEFAULT_MIN_KN, RuleSource.SYSTEM

    # max_kn: rule > profile > derived system value (the spot only acts through min_kn)
    if o.max_kn is not None:
        max_kn, max_source = float(o.max_kn), RuleSource.RULE
    elif p.default_max_kn is not None:
        max_kn, max_source = float(p.default_max_kn), RuleSource.PROFILE
    else:
        max_kn, max_source = max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN), RuleSource.SYSTEM
    if max_source is not RuleSource.SYSTEM and not min_kn < max_kn:
        raise ValueError(
            f"min_kn {min_kn} ({min_source}) must be below max_kn {max_kn} ({max_source})"
        )

    return AlertRule(
        enabled=o.enabled if o.enabled is not None else True,
        min_kn=min_kn,
        max_kn=max_kn,
        dir_classes=o.dir_classes if o.dir_classes is not None else DEFAULT_DIR_CLASSES,
        weekdays=o.weekdays if o.weekdays is not None else DEFAULT_WEEKDAYS,
        earliest_local=o.earliest_local,
        latest_local=o.latest_local,
        min_go_hours=o.min_go_hours if o.min_go_hours is not None else DEFAULT_MIN_GO_HOURS,
        days_ahead=o.days_ahead if o.days_ahead is not None else DEFAULT_DAYS_AHEAD,
    )


def rider_limits(rule: AlertRule) -> RiderLimits:
    """RiderLimits(min_kn=rule.min_kn, max_kn=rule.max_kn)."""
    return RiderLimits(min_kn=rule.min_kn, max_kn=rule.max_kn)


class Window(_RevalidatingModel):
    spot_id: str = Field(min_length=1)
    start: datetime
    end: datetime
    hours: tuple[HourEvaluation, ...]

    @field_validator("start", "end")
    @classmethod
    def _aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("window times must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _invariants(self) -> Self:
        hours = self.hours
        if not hours:
            raise ValueError("a window needs at least one hour")
        if any(h.spot_id != self.spot_id for h in hours):
            raise ValueError("all hours must belong to the window's spot")
        if any(b.valid_at - a.valid_at != _HOUR for a, b in zip(hours, hours[1:], strict=False)):
            raise ValueError("window hours must be consecutive")
        if self.start != hours[0].valid_at or self.end != hours[-1].valid_at + _HOUR:
            raise ValueError("start and end must match the first and last hour")
        if any(h.verdict != Verdict.GO or h.dir_class not in RIDABLE_DIR_CLASSES for h in hours):
            raise ValueError("window hours must be go with a ridable direction class")
        return self


_HOUR: Final = timedelta(hours=1)


def _floor_hour(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def _qualifies(ev: HourEvaluation, rule: AlertRule, first_hour: datetime, last_day: Any) -> bool:
    local = ev.valid_at.astimezone(LOCAL_TZ)
    t = time(local.hour, local.minute)
    return (
        ev.verdict == Verdict.GO
        and ev.dir_class is not None
        and ev.dir_class in RIDABLE_DIR_CLASSES
        and ev.dir_class in rule.dir_classes
        and local.isoweekday() in rule.weekdays
        and (rule.earliest_local is None or t >= rule.earliest_local)
        and (rule.latest_local is None or t < rule.latest_local)
        and ev.valid_at >= first_hour
        and local.date() <= last_day
    )


def find_windows(
    evaluations: Sequence[HourEvaluation], rule: AlertRule, *, now: datetime
) -> list[Window]:
    """Maximal runs of consecutive qualifying hours with length >= rule.min_go_hours, sorted by
    start. [] if rule.enabled is False. ValueError on a naive now, mixed spot_ids or a
    duplicate valid_at. Input order is free and the input is not modified."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    if not rule.enabled:
        return []
    if len({ev.spot_id for ev in evaluations}) > 1:
        raise ValueError("evaluations belong to more than one spot")
    ordered = sorted(evaluations, key=lambda ev: ev.valid_at)
    if len({ev.valid_at for ev in ordered}) != len(ordered):
        raise ValueError("duplicate valid_at in evaluations")
    if not ordered:
        return []

    first_hour = _floor_hour(now) + _HOUR
    last_day = now.astimezone(LOCAL_TZ).date() + timedelta(days=rule.days_ahead)

    runs: list[list[HourEvaluation]] = []
    current: list[HourEvaluation] = []
    for ev in ordered:
        if not _qualifies(ev, rule, first_hour, last_day):
            current = []
            continue
        if current and ev.valid_at - current[-1].valid_at == _HOUR:
            current.append(ev)
        else:
            current = [ev]
            runs.append(current)
    return [
        Window(
            spot_id=run[0].spot_id,
            start=run[0].valid_at,
            end=run[-1].valid_at + _HOUR,
            hours=tuple(run),
        )
        for run in runs
        if len(run) >= rule.min_go_hours
    ]
