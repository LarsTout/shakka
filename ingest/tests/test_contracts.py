"""AC-10: generated contract files."""

import json
import re
from pathlib import Path

from click.testing import CliRunner

import shakka.contracts as contracts
from alert_fixtures import migration_range
from shakka.cli import cli
from shakka.config import REPO_ROOT
from shakka.contracts import CONTRACT_FILES, build_contracts, check_contracts, export_contracts
from shakka.domain.alerts import (
    DEFAULT_DAYS_AHEAD,
    DEFAULT_DIR_CLASSES,
    DEFAULT_MIN_GO_HOURS,
    DEFAULT_WEEKDAYS,
    FIELD_LABEL_NL,
    FIELD_SOURCES,
    RULE_FIELDS,
)
from shakka.domain.consensus import CONFIDENCE_LABEL_NL, Confidence
from shakka.domain.defaults import DEFAULT_MAX_KN, DEFAULT_MIN_KN
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass
from shakka.domain.evaluation import REASON_EFFECT, ReasonCode, Verdict


def test_repo_files_up_to_date() -> None:
    assert check_contracts() == [], "run: uv run shakka contracts export"


def _load(name: str) -> dict:
    return json.loads((contracts.CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def test_files_cover_all_codes() -> None:
    reasons = _load("reason_codes.json")["items"]
    assert [i["code"] for i in reasons] == [r.value for r in ReasonCode]
    for i in reasons:
        assert i["label_nl"]
        assert i["effect"] == REASON_EFFECT[ReasonCode(i["code"])].value
    classes = _load("dir_classes.json")["items"]
    assert [i["code"] for i in classes] == [c.value for c in DirClass]
    for i in classes:
        assert i["label_nl"]
        assert i["ridable"] == (DirClass(i["code"]) in RIDABLE_DIR_CLASSES)
    conf = _load("confidence.json")["items"]
    assert [i["code"] for i in conf] == [c.value for c in Confidence]
    assert [i["label_nl"] for i in conf] == [CONFIDENCE_LABEL_NL[c] for c in Confidence]
    for name in CONTRACT_FILES:
        assert "_generated" in _load(name)


def _sql_list(sql: str, constraint: str) -> set[str]:
    start = sql.index(constraint)
    chunk = sql[start : start + 1500]
    block = re.search(r"(?:in \(|array\[)(.*?)(?:\)|\])", chunk, re.S)
    assert block is not None, constraint
    return set(re.findall(r"'([a-z_]+)'", block.group(1)))


def test_codes_match_migration() -> None:
    sql = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql"))
    )
    assert _sql_list(sql, "evaluations_reasons_enum") == {r.value for r in ReasonCode}
    assert _sql_list(sql, "evaluations_dir_class_enum") == {c.value for c in DirClass}
    assert _sql_list(sql, "evaluations_confidence_enum") == {c.value for c in Confidence}
    assert _sql_list(sql, "evaluations_verdict_enum") == {v.value for v in Verdict}


def test_export_and_check_tmp(tmp_path: Path) -> None:
    target = tmp_path / "contracts"
    assert check_contracts(target) == list(CONTRACT_FILES)
    assert export_contracts(target) == list(CONTRACT_FILES)
    assert check_contracts(target) == []
    assert export_contracts(target) == []
    other = target / "other.json"
    other.write_text("{}", encoding="utf-8")
    (target / "confidence.json").write_text("changed", encoding="utf-8")
    assert check_contracts(target) == ["confidence.json"]
    assert export_contracts(target) == ["confidence.json"]
    assert other.read_text(encoding="utf-8") == "{}"
    assert build_contracts()["reason_codes.json"].endswith("}\n")


def test_cli_check_repo() -> None:
    res = CliRunner().invoke(cli, ["contracts", "export", "--check"])
    assert res.exit_code == 0
    assert "contracts export: check ok" in res.output


def test_cli_check_missing_and_export(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "c"
    monkeypatch.setattr(contracts, "CONTRACTS_DIR", target)
    res = CliRunner().invoke(cli, ["contracts", "export", "--check"])
    assert res.exit_code == 1
    assert "missing data/contracts/reason_codes.json" in res.output
    assert "check failed; run 'shakka contracts export'" in res.output
    assert not target.exists()
    res = CliRunner().invoke(cli, ["contracts", "export"])
    assert res.exit_code == 0
    assert res.output.count("wrote   data/contracts/") == len(CONTRACT_FILES)
    assert "contracts export: ok" in res.output
    res = CliRunner().invoke(cli, ["contracts", "export"])
    assert res.output.count("(unchanged)") == len(CONTRACT_FILES)


def test_help_lists_contracts() -> None:
    assert "contracts" in CliRunner().invoke(cli, ["--help"]).output


def test_alert_defaults_content() -> None:
    data = _load("alert_defaults.json")
    assert set(data) == {"_generated", "items"}
    items = data["items"]
    assert [i["field"] for i in items] == list(RULE_FIELDS)
    keys = {"field", "label_nl", "default", "sources", "min", "max", "allowed", "min_span_kn"}
    for i in items:
        assert set(i) == keys
        assert i["label_nl"] == FIELD_LABEL_NL[i["field"]] != ""
        assert i["sources"] == [s.value for s in FIELD_SOURCES[i["field"]]]
    defaults = {i["field"]: i["default"] for i in items}
    assert defaults == {
        "enabled": True,
        "min_kn": DEFAULT_MIN_KN,
        "max_kn": DEFAULT_MAX_KN,
        "dir_classes": [c.value for c in DirClass if c in DEFAULT_DIR_CLASSES],
        "weekdays": sorted(DEFAULT_WEEKDAYS),
        "earliest_local": None,
        "latest_local": None,
        "min_go_hours": DEFAULT_MIN_GO_HOURS,
        "days_ahead": DEFAULT_DAYS_AHEAD,
    }
    by_field = {i["field"]: i for i in items}
    assert by_field["dir_classes"]["allowed"] == ["onshore", "side_onshore", "sideshore"]
    text = (contracts.CONTRACTS_DIR / "alert_defaults.json").read_text(encoding="utf-8")
    assert "offshore" not in text


def test_alert_defaults_ranges_match_migration() -> None:
    by_field = {i["field"]: i for i in _load("alert_defaults.json")["items"]}
    for field, constraint in (
        ("min_kn", "alert_rules_min_kn_range"),
        ("max_kn", "alert_rules_max_kn_range"),
        ("min_go_hours", "alert_rules_min_go_hours_range"),
        ("days_ahead", "alert_rules_days_ahead_range"),
    ):
        assert (by_field[field]["min"], by_field[field]["max"]) == migration_range(constraint)
