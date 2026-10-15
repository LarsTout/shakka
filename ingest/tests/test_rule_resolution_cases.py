"""WP-16 AC-2: shared rule resolution cases (the TypeScript side is web/test/rules.test.ts)."""

import json
from datetime import time
from typing import Any

import pytest
from pydantic import ValidationError

from evaluation_fixtures import make_spot
from shakka.config import REPO_ROOT
from shakka.domain.alerts import (
    FIELD_SOURCES,
    RULE_FIELDS,
    AlertRuleOverride,
    ProfileDefaults,
    RuleSource,
    resolve_rule,
)
from shakka.domain.direction import DirClass
from shakka.domain.spot import SpotProfile

CASES_PATH = REPO_ROOT / "data" / "contracts" / "rule_resolution_cases.json"
CASES: list[dict[str, Any]] = json.loads(CASES_PATH.read_text(encoding="utf-8"))
DIR_ORDER = [c.value for c in DirClass]  # onshore, side_onshore, sideshore, ... (= contract order)
CASE_KEYS = {"name", "spot", "profile", "override", "expected"}


def _fmt(t: time | None) -> str | None:
    """None -> None; 'HH:MM' when second and microsecond are 0, else t.isoformat() (A18)."""
    if t is None:
        return None
    if t.second == 0 and t.microsecond == 0:
        return t.strftime("%H:%M")
    return t.isoformat()


def _parse(case: dict[str, Any]) -> tuple[ProfileDefaults | None, AlertRuleOverride | None]:
    p, o = case["profile"], case["override"]
    profile = ProfileDefaults.from_row(p) if p is not None else None
    override = AlertRuleOverride.from_row(o) if o is not None else None
    return profile, override


def _expected_sources(
    spot: SpotProfile, profile: ProfileDefaults | None, override: AlertRuleOverride | None
) -> dict[str, str]:
    """Per field the first level in FIELD_SOURCES[field] whose PARSED input is not None:
    RULE -> getattr(override, field) (None if override is None; so latest_local 24:00, which
    from_row turns into None, counts as system, and enabled None too);
    PROFILE -> profile.default_min_kn / default_max_kn (min_kn / max_kn only);
    SPOT -> spot.default_min_kn (min_kn only); SYSTEM -> always."""
    out: dict[str, str] = {}
    for field in RULE_FIELDS:
        for source in FIELD_SOURCES[field]:
            if source is RuleSource.RULE:
                value = getattr(override, field) if override is not None else None
            elif source is RuleSource.PROFILE:
                value = getattr(profile, f"default_{field}") if profile is not None else None
            elif source is RuleSource.SPOT:
                value = spot.default_min_kn
            else:
                value = True  # SYSTEM always has a value
            if value is not None:
                out[field] = source.value
                break
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_rule_resolution_cases(case: dict[str, Any]) -> None:
    spot = make_spot(default_min_kn=case["spot"]["default_min_kn"])
    expected = case["expected"]
    if expected.get("error") == "invalid":
        with pytest.raises(ValidationError):
            _parse(case)
        return
    profile, override = _parse(case)
    if expected.get("error") == "conflict":
        with pytest.raises(ValueError, match="must be below") as exc:
            resolve_rule(spot, profile, override)
        assert not isinstance(exc.value, ValidationError)
        return
    rule = resolve_rule(spot, profile, override)
    actual = {
        "enabled": rule.enabled,
        "min_kn": rule.min_kn,  # float; == with the int in the file
        "max_kn": rule.max_kn,
        "dir_classes": [c.value for c in sorted(rule.dir_classes, key=DIR_ORDER.index)],
        "weekdays": sorted(rule.weekdays),
        "earliest_local": _fmt(rule.earliest_local),
        "latest_local": _fmt(rule.latest_local),
        "min_go_hours": rule.min_go_hours,
        "days_ahead": rule.days_ahead,
    }
    assert actual == {k: v for k, v in expected.items() if k != "sources"}
    assert _expected_sources(spot, profile, override) == expected["sources"]


def test_rule_resolution_cases_coverage() -> None:
    assert len(CASES) == 20
    names = [c["name"] for c in CASES]
    assert len(set(names)) == len(names)
    for case in CASES:
        assert set(case) == CASE_KEYS
        if case["override"] is not None:
            assert set(case["override"]) == set(RULE_FIELDS)
    used = {
        s for c in CASES if "sources" in c["expected"] for s in c["expected"]["sources"].values()
    }
    assert used == {s.value for s in RuleSource}
    errors = {c["expected"]["error"] for c in CASES if "error" in c["expected"]}
    assert errors == {"conflict", "invalid"}
