"""WP-07 AC-1 and AC-2: alert rule resolution and validation."""

import inspect
from datetime import time
from typing import Any

import pytest
from pydantic import ValidationError

import shakka.domain.alerts as alerts
from alert_fixtures import (
    migration_int_array,
    migration_range,
    migration_text_array,
    rule,
)
from evaluation_fixtures import make_spot
from shakka.domain.alerts import (
    ALERT_KN_RANGE,
    DAYS_AHEAD_RANGE,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_DIR_CLASSES,
    DEFAULT_MIN_GO_HOURS,
    DEFAULT_WEEKDAYS,
    FIELD_SOURCES,
    ISO_WEEKDAYS,
    MIN_GO_HOURS_RANGE,
    RULE_FIELDS,
    AlertRule,
    AlertRuleOverride,
    ProfileDefaults,
    RuleSource,
    resolve_rule,
    rider_limits,
)
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass
from shakka.domain.evaluation import RiderLimits, default_limits

RIDABLE = RIDABLE_DIR_CLASSES
ALL_DAYS = frozenset(range(1, 8))

FULL_OVERRIDE: dict[str, Any] = {
    "enabled": False,
    "min_kn": 18,
    "max_kn": 24,
    "dir_classes": frozenset({DirClass.SIDESHORE}),
    "weekdays": frozenset({6, 7}),
    "earliest_local": time(17, 0),
    "latest_local": time(21, 0),
    "min_go_hours": 3,
    "days_ahead": 5,
}
SYSTEM: dict[str, Any] = {
    "enabled": True,
    "min_kn": 12.0,
    "max_kn": 30.0,
    "dir_classes": RIDABLE,
    "weekdays": ALL_DAYS,
    "earliest_local": None,
    "latest_local": None,
    "min_go_hours": 2,
    "days_ahead": 3,
}
PROFILE = ProfileDefaults(default_min_kn=14, default_max_kn=26)
SPOT16 = make_spot(default_min_kn=16, ridable_dirs=[{"from": 200, "to": 340}])


def _expected(field: str, level: str) -> Any:
    if level == "rule":
        v = FULL_OVERRIDE[field]
        return float(v) if field in ("min_kn", "max_kn") else v
    if level == "profile":
        return {"min_kn": 14.0, "max_kn": 26.0}.get(field, SYSTEM[field])
    if level == "spot":
        return {"min_kn": 16.0}.get(field, SYSTEM[field])
    return SYSTEM[field]


@pytest.mark.parametrize("level", ["rule", "profile", "spot", "system"])
@pytest.mark.parametrize("field", RULE_FIELDS)
def test_priority(field: str, level: str) -> None:
    if level == "rule":
        result = resolve_rule(SPOT16, PROFILE, AlertRuleOverride(**FULL_OVERRIDE))
    elif level == "profile":
        data = {k: v for k, v in FULL_OVERRIDE.items() if k != field}
        result = resolve_rule(SPOT16, PROFILE, AlertRuleOverride(**data))
    elif level == "spot":
        result = resolve_rule(SPOT16, ProfileDefaults(), None)
    else:
        result = resolve_rule(make_spot(), None, None)
    assert getattr(result, field) == _expected(field, level)


def test_priority_spot_level_derived_max() -> None:
    r = resolve_rule(make_spot(default_min_kn=28), ProfileDefaults(), None)
    assert (r.min_kn, r.max_kn) == (28.0, 33.0)
    assert resolve_rule(SPOT16, ProfileDefaults(), None).max_kn == 30.0


def test_field_sources_table() -> None:
    R, P, S, Y = RuleSource.RULE, RuleSource.PROFILE, RuleSource.SPOT, RuleSource.SYSTEM
    assert FIELD_SOURCES == {
        "enabled": (R, Y),
        "min_kn": (R, P, S, Y),
        "max_kn": (R, P, Y),
        "dir_classes": (R, Y),
        "weekdays": (R, Y),
        "earliest_local": (R, Y),
        "latest_local": (R, Y),
        "min_go_hours": (R, Y),
        "days_ahead": (R, Y),
    }
    assert tuple(AlertRuleOverride.model_fields) == RULE_FIELDS
    assert tuple(AlertRule.model_fields) == RULE_FIELDS


@pytest.mark.parametrize("min_kn", [None, 5, 14, 26, 35, 40])
def test_default_rule_matches_default_limits(min_kn: int | None) -> None:
    spot = make_spot(default_min_kn=min_kn)
    assert rider_limits(resolve_rule(spot, None, None)) == default_limits(spot)


def test_rider_limits() -> None:
    assert rider_limits(rule(min_kn=15, max_kn=25)) == RiderLimits(min_kn=15, max_kn=25)


def test_defaults_values() -> None:
    assert DEFAULT_MIN_GO_HOURS == 2
    assert DEFAULT_DAYS_AHEAD == 3
    assert frozenset(range(1, 8)) == DEFAULT_WEEKDAYS
    assert DEFAULT_DIR_CLASSES == RIDABLE_DIR_CLASSES


def test_edge_cases_resolution() -> None:
    assert resolve_rule(make_spot(), None, AlertRuleOverride(min_kn=60)).max_kn == 65.0
    r = resolve_rule(make_spot(), ProfileDefaults(default_max_kn=25), AlertRuleOverride(min_kn=15))
    assert (r.min_kn, r.max_kn) == (15.0, 25.0)


# --- AC-2 ---


@pytest.mark.parametrize(
    "value",
    [["offshore"], ["side_offshore"], ["onshore", "offshore"], [DirClass.SIDE_OFFSHORE]],
)
def test_override_rejects_offshore(value: list) -> None:
    with pytest.raises(ValidationError):
        AlertRuleOverride(dir_classes=value)


def _base_rule(**kw: Any) -> AlertRule:
    data: dict[str, Any] = {**SYSTEM}
    data.update(kw)
    return AlertRule(**data)


@pytest.mark.parametrize(
    "classes",
    [
        frozenset({DirClass.OFFSHORE}),
        frozenset({DirClass.SIDESHORE, DirClass.SIDE_OFFSHORE}),
    ],
)
def test_rule_rejects_offshore(classes: frozenset) -> None:
    with pytest.raises(ValidationError):
        _base_rule(dir_classes=classes)


def test_resolve_rejects_offshore_even_if_override_bypassed() -> None:
    # Deliberate validation bypass: proves AlertRule is the last safety net (allowed in tests only).
    bad = AlertRuleOverride.model_construct(dir_classes=frozenset({DirClass.OFFSHORE}))
    with pytest.raises(ValueError):
        resolve_rule(make_spot(), None, bad)


def test_model_copy_revalidates() -> None:
    r = rule()
    with pytest.raises(ValidationError):
        r.model_copy(update={"dir_classes": frozenset({DirClass.OFFSHORE})})
    with pytest.raises(ValidationError):
        r.model_copy(update={"min_kn": 40.0})
    with pytest.raises(ValidationError):
        r.model_copy(update={"unknown": 1})
    assert r.model_copy(update={"min_go_hours": 4}).min_go_hours == 4
    o = AlertRuleOverride()
    with pytest.raises(ValidationError):
        o.model_copy(update={"dir_classes": frozenset({DirClass.SIDE_OFFSHORE})})


def test_min_ge_max_rejected() -> None:
    with pytest.raises(ValueError):
        _base_rule(min_kn=20.0, max_kn=20.0)
    with pytest.raises(ValueError):
        _base_rule(min_kn=25.0, max_kn=20.0)
    with pytest.raises(ValueError):
        AlertRuleOverride(min_kn=20, max_kn=20)
    with pytest.raises(ValueError):
        ProfileDefaults(default_min_kn=20, default_max_kn=15)
    with pytest.raises(ValueError) as e4:
        resolve_rule(
            make_spot(default_min_kn=22), ProfileDefaults(default_max_kn=20), AlertRuleOverride()
        )
    assert "22.0 (spot)" in str(e4.value)
    assert "20.0 (profile)" in str(e4.value)
    with pytest.raises(ValueError) as e5:
        resolve_rule(make_spot(), ProfileDefaults(default_max_kn=20), AlertRuleOverride(min_kn=25))
    assert "rule" in str(e5.value)
    assert "profile" in str(e5.value)


@pytest.mark.parametrize("days", [[0], [8], [1, 8], [], [True], [6.0]])
def test_weekday_out_of_range(days: list) -> None:
    with pytest.raises(ValidationError):
        AlertRuleOverride(weekdays=days)
    with pytest.raises(ValidationError):
        _base_rule(weekdays=days)


def test_weekdays_list_deduplicated() -> None:
    assert AlertRuleOverride(weekdays=[6, 6, 7]).weekdays == frozenset({6, 7})
    assert _base_rule(weekdays=[6, 6, 7]).weekdays == frozenset({6, 7})
    assert AlertRuleOverride(dir_classes=["onshore", "onshore"]).dir_classes == frozenset(
        {DirClass.ONSHORE}
    )


@pytest.mark.parametrize(
    "kw", [{"min_go_hours": True}, {"min_go_hours": 2.0}, {"days_ahead": True}, {"days_ahead": 3.0}]
)
def test_strict_ints_in_rule(kw: dict) -> None:
    with pytest.raises(ValidationError):
        _base_rule(**kw)


@pytest.mark.parametrize(
    "kw",
    [
        {"min_kn": 4},
        {"min_kn": 61},
        {"min_go_hours": 0},
        {"min_go_hours": 25},
        {"days_ahead": -1},
        {"days_ahead": 8},
        {"dir_classes": []},
        {"earliest_local": time(21, 0), "latest_local": time(20, 0)},
        {"earliest_local": time(20, 0), "latest_local": time(20, 0)},
        {"earliest_local": "17:00:00+02:00"},
        {"min_kn": True},
        {"min_kn": 12.5},
        {"min_go_hours": True},
        {"min_go_hours": 2.0},
        {"days_ahead": True},
        {"days_ahead": 3.0},
    ],
)
def test_other_ranges_override(kw: dict) -> None:
    with pytest.raises(ValidationError):
        AlertRuleOverride(**kw)


def test_other_ranges_rule_and_bounds() -> None:
    with pytest.raises(ValidationError):
        _base_rule(min_kn=float("nan"))
    with pytest.raises(ValidationError):
        _base_rule(min_kn=-1.0)
    with pytest.raises(ValidationError):
        _base_rule(earliest_local=time(21, 0), latest_local=time(20, 0))
    for kw in (
        {"min_kn": 5},
        {"max_kn": 60},
        {"min_go_hours": 1},
        {"min_go_hours": 24},
        {"days_ahead": 0},
        {"days_ahead": 7},
    ):
        assert AlertRuleOverride(**kw)
    assert AlertRuleOverride(min_kn=5, max_kn=60)


ROW: dict[str, Any] = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "spot_id": "test-strand",
    "enabled": True,
    "min_kn": 14,
    "max_kn": None,
    "dir_classes": ["onshore", "sideshore"],
    "weekdays": [6, 7],
    "earliest_local": "17:00:00",
    "latest_local": None,
    "min_go_hours": None,
    "days_ahead": 2,
    "updated_at": "2026-10-15T10:00:00+00:00",
}


def test_from_row() -> None:
    o = AlertRuleOverride.from_row(ROW)
    assert o == AlertRuleOverride(
        enabled=True,
        min_kn=14,
        dir_classes=frozenset({DirClass.ONSHORE, DirClass.SIDESHORE}),
        weekdays=frozenset({6, 7}),
        earliest_local=time(17, 0),
        days_ahead=2,
    )
    row = {k: v for k, v in ROW.items() if k != "days_ahead"}
    with pytest.raises(ValueError, match="days_ahead"):
        AlertRuleOverride.from_row(row)


def test_profile_from_row() -> None:
    prof = {
        "id": "00000000-0000-0000-0000-000000000001",
        "weight_kg": 80,
        "level": "intermediate",
        "quiver_m2": [9, 12],
        "default_min_kn": 14,
        "default_max_kn": 26,
        "created_at": "2026-10-15T10:00:00+00:00",
        "updated_at": "2026-10-15T10:00:00+00:00",
    }
    assert ProfileDefaults.from_row(prof) == ProfileDefaults(default_min_kn=14, default_max_kn=26)
    del prof["default_max_kn"]
    with pytest.raises(ValueError, match="default_max_kn"):
        ProfileDefaults.from_row(prof)


def test_end_of_day_time() -> None:
    row = {**ROW, "latest_local": "24:00:00"}
    o = AlertRuleOverride.from_row(row)
    assert o.latest_local is None
    assert o.earliest_local == time(17, 0)
    assert resolve_rule(make_spot(), None, o).latest_local is None
    assert AlertRuleOverride(latest_local="24:00").latest_local is None
    assert AlertRuleOverride(latest_local="24:00:00").latest_local is None
    bad = {**ROW, "earliest_local": "24:00:00", "latest_local": None}
    with pytest.raises(ValueError, match="earliest_local 24:00 matches no hour"):
        AlertRuleOverride.from_row(bad)
    with pytest.raises(ValueError, match="earliest_local 24:00 matches no hour"):
        AlertRuleOverride(earliest_local="24:00")
    assert AlertRuleOverride(latest_local="00:00:00").latest_local == time(0, 0)


def test_ranges_match_migration() -> None:
    for c in (
        "alert_rules_min_kn_range",
        "alert_rules_max_kn_range",
        "profiles_min_kn_range",
        "profiles_max_kn_range",
    ):
        assert migration_range(c) == ALERT_KN_RANGE
    assert migration_range("alert_rules_min_go_hours_range") == MIN_GO_HOURS_RANGE
    assert migration_range("alert_rules_days_ahead_range") == DAYS_AHEAD_RANGE
    assert migration_text_array("alert_rules_dir_classes_ridable") == {
        c.value for c in RIDABLE_DIR_CLASSES
    }
    assert migration_int_array("alert_rules_weekdays_iso") == ISO_WEEKDAYS


def test_no_bypass_parameters() -> None:
    assert list(inspect.signature(resolve_rule).parameters) == ["spot", "profile", "override"]
    assert list(inspect.signature(rider_limits).parameters) == ["rule"]
    # FIND_WINDOWS_SIGNATURE_CHECK
    for name, fn in inspect.getmembers(alerts, inspect.isfunction):
        if name.startswith("_") or fn.__module__ != alerts.__name__:
            continue
        for p in inspect.signature(fn).parameters:
            assert not any(w in p for w in ("offshore", "allow", "force", "unsafe")), (name, p)
