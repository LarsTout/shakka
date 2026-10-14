"""Domain tests for shakka.domain.spot (AC-4)."""

import re
from datetime import time
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from shakka.db import to_json
from shakka.domain.spot import (
    SPOT_COLUMNS,
    DirRange,
    Level,
    SeasonClosure,
    SpotProfile,
    SpotProfileBase,
    SpotStatus,
    TideSensitivity,
    spot_rule_violations,
)
from spot_fixtures import FULL_SPOT_ROW, FULL_SPOT_YAML, MIN_SPOT_YAML

MIGRATION = Path(__file__).resolve().parents[2] / "supabase/migrations/20261015090000_m1_schema.sql"

EXPECTED_COLUMNS = [
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
]


def full() -> SpotProfile:
    return SpotProfile.model_validate(yaml.safe_load(FULL_SPOT_YAML)["spots"][0])


def minimal() -> SpotProfile:
    return SpotProfile.model_validate(yaml.safe_load(MIN_SPOT_YAML)["spots"][0])


def test_full_fixture_row():
    assert full().to_row() == FULL_SPOT_ROW


def test_to_row_columns_match_migration():
    assert list(SPOT_COLUMNS) == EXPECTED_COLUMNS
    assert list(full().to_row()) == list(SPOT_COLUMNS)
    sql = MIGRATION.read_text(encoding="utf-8")
    block = sql.split("create table public.spots (", 1)[1].split("\n);", 1)[0]
    pattern = re.compile(
        r"^  ([a-z_]+) (text|double precision|smallint|jsonb|integer|boolean|timestamptz)\b"
    )
    cols = [m.group(1) for line in block.splitlines() if (m := pattern.match(line))]
    assert set(cols) - {"updated_at"} == set(SPOT_COLUMNS)


def test_roundtrip():
    two_seasons = SpotProfile(
        id="zz-seasons",
        name="Seasons",
        season=[
            {"start": "11-01", "end": "02-28"},
            {"start": "05-01", "end": "05-01", "note": "one day"},
        ],
    )
    two_ranges = SpotProfile(
        id="zz-ranges",
        name="Ranges",
        ridable_dirs=[{"from": 10, "to": 50}, {"from": 200, "to": 20}],
    )
    for s in (full(), minimal(), two_seasons, two_ranges):
        assert SpotProfile.from_row(s.to_row()) == s


def test_from_row_ignores_extra_and_updated_at():
    row = {**FULL_SPOT_ROW, "updated_at": "2026-01-01T00:00:00Z", "future_col": 1}
    assert SpotProfile.from_row(row) == full()


def test_from_row_missing_column():
    row = {k: v for k, v in FULL_SPOT_ROW.items() if k != "season"}
    with pytest.raises(ValueError, match="missing columns: season"):
        SpotProfile.from_row(row)


def test_from_row_int_lat():
    row = {**FULL_SPOT_ROW, "lat": 52, "lon": 4}
    spot = SpotProfile.from_row(row)
    assert spot.lat == 52.0 and isinstance(spot.lat, float)
    assert isinstance(spot.lon, float)


def test_to_row_is_json_encodable():
    for spot in (full(), minimal()):
        row = spot.to_row()
        to_json(row)

        def check(value: Any) -> None:
            assert not isinstance(value, (Enum, time))
            if isinstance(value, dict):
                for v in value.values():
                    check(v)
            elif isinstance(value, list):
                for v in value:
                    check(v)
            else:
                assert value is None or type(value) in (str, int, float, bool)

        check(row)


def test_frozen():
    spot = minimal()
    with pytest.raises(ValidationError):
        spot.name = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        full().season[0].note = "x"  # type: ignore[misc]


def test_extra_forbidden():
    with pytest.raises(ValidationError):
        SpotProfile(id="zz-a", name="A", parking=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        DirRange.model_validate({"from": 1, "to": 2, "x": 3})
    with pytest.raises(ValidationError):
        SeasonClosure.model_validate({"start": "05-01", "end": "06-01", "x": 3})


def test_dir_range_alias_and_name():
    a = DirRange(from_deg=1, to_deg=2)
    b = DirRange.model_validate({"from": 1, "to": 2})
    assert a == b


def test_season_time_rules():
    base = {"start": "05-01", "end": "09-30"}
    ok = SeasonClosure.model_validate({**base, "from_time": "09:00", "to_time": "10:00"})
    assert ok.from_time == time(9, 0)
    assert SeasonClosure.model_validate(base).from_time is None
    for extra in (
        {"from_time": "18:00", "to_time": "10:00"},
        {"from_time": "10:00", "to_time": "10:00"},
    ):
        with pytest.raises(ValidationError, match="from_time must be before to_time"):
            SeasonClosure.model_validate({**base, **extra})
    for extra in ({"from_time": "10:00"}, {"to_time": "10:00"}):
        with pytest.raises(ValidationError, match="both be set or both be empty"):
            SeasonClosure.model_validate({**base, **extra})


def test_rule_violations_order():
    def v(**kw: Any) -> list[tuple[str, str]]:
        return [tuple(x) for x in spot_rule_violations(SpotProfileBase(id="zz-a", name="A", **kw))]

    assert v(lat=52.0) == [("lon", "required when lat is set")]
    assert v(lon=4.2) == [("lat", "required when lon is set")]
    assert v(tide_min_level_cm=-20) == [
        ("tide_min_level_cm", "only allowed when tide_sensitive is not none")
    ]
    assert v(verified=True) == [
        ("lat", "required when verified is true"),
        ("lon", "required when verified is true"),
        ("shore_normal_deg", "required when verified is true"),
        ("status", "required when verified is true"),
        ("level", "required when verified is true"),
    ]
    # E26: only lat set, rule 3 does not repeat lon
    assert v(lat=52.0, shore_normal_deg=1, status="allowed", level="beginner", verified=True) == [
        ("lon", "required when lat is set")
    ]
    # E24
    assert v(
        lat=52.0,
        lon=4.2,
        shore_normal_deg=1,
        status="allowed",
        level="beginner",
        verified=True,
        tide_sensitive="avoid_low",
    ) == [("rws_station", "required when verified is true and tide_sensitive is not none")]
    # fixed order: rule 1, 2, 3
    got = v(lat=52.0, tide_min_level_cm=0, verified=True, tide_sensitive="none")
    assert [f for f, _ in got] == [
        "lon",
        "tide_min_level_cm",
        "shore_normal_deg",
        "status",
        "level",
    ]


def test_direct_construction_enforces_rules():
    with pytest.raises(ValidationError, match="lon: required when lat is set"):
        SpotProfile(id="zz-a", name="A", lat=52.0)


def test_enum_values():
    assert {e.value for e in Level} == {"beginner", "intermediate", "advanced"}
    assert {e.value for e in SpotStatus} == {"allowed", "limited", "forbidden"}
    assert {e.value for e in TideSensitivity} == {
        "none",
        "prefer_low",
        "prefer_high",
        "avoid_low",
    }
