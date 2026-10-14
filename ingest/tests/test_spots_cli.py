"""CLI tests for `shakka spots validate` and `shakka spots sync` (AC-1, AC-3, AC-5)."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

import shakka.spots.commands
from fakes import FakeSupabase
from shakka.cli import cli
from shakka.db import DatabaseError
from spot_fixtures import FULL_SPOT_YAML, MIN_SPOT_YAML, write_spots

SECRET = "sb_secret_TESTVALUE"
TWO_SPOTS = (
    "spots:\n  - id: zz-one\n    name: One\n    verified: false\n  - id: zz-two\n    name: Two\n"
)
THREE_ERRORS = (
    "spots:\n"
    "  - id: Bad_Id\n    name: X\n    status: open\n"
    "  - id: zz-ok\n    name: Y\n    lat: 52.0\n"
)


def run(*args: str):
    return CliRunner().invoke(cli, list(args))


def test_validate_counts_on_tmp_file(tmp_path: Path):
    r = run("spots", "validate", "--path", str(write_spots(tmp_path, MIN_SPOT_YAML)))
    assert r.exit_code == 0
    assert r.output.splitlines() == ["ok      1 spots valid (0 verified)", "spots validate: ok"]
    r = run("spots", "validate", "--path", str(write_spots(tmp_path, FULL_SPOT_YAML)))
    assert r.exit_code == 0
    assert r.output.splitlines() == ["ok      1 spots valid (1 verified)", "spots validate: ok"]


def test_validate_three_errors(tmp_path: Path):
    r = run("spots", "validate", "--path", str(write_spots(tmp_path, THREE_ERRORS)))
    assert r.exit_code == 1
    lines = r.output.splitlines()
    assert sum(line.startswith("error   ") for line in lines) == 3
    assert lines[-1] == "spots validate: failed (3 errors)"


def test_validate_missing_file(tmp_path: Path):
    r = run("spots", "validate", "--path", str(tmp_path / "nope.yaml"))
    assert r.exit_code == 1
    assert "file not found" in r.output


def test_validate_needs_no_env(tmp_path: Path):
    # conftest removes all settings variables; validate must still work
    r = run("spots", "validate", "--path", str(write_spots(tmp_path, MIN_SPOT_YAML)))
    assert r.exit_code == 0


# -- sync ------------------------------------------------------------------------------------


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://testref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, env) -> FakeSupabase:
    db = FakeSupabase()
    monkeypatch.setattr(shakka.spots.commands, "open_db", lambda settings: db)
    return db


def no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(settings: Any):
        raise AssertionError("open_db must not be called")

    monkeypatch.setattr(shakka.spots.commands, "open_db", fail)


def assert_clean(output: str) -> None:
    assert SECRET not in output
    assert "testref" not in output


def test_sync_ok(tmp_path: Path, fake: FakeSupabase):
    r = run("spots", "sync", "--path", str(write_spots(tmp_path, TWO_SPOTS)))
    assert r.exit_code == 0
    assert "ok      2 of 2 spots upserted (0 unchanged)" in r.output
    assert r.output.splitlines()[-1] == "spots sync: ok"
    assert_clean(r.output)
    again = run("spots", "sync", "--path", str(tmp_path / "spots.yaml"))
    assert "ok      0 of 2 spots upserted (2 unchanged)" in again.output


def test_sync_orphan_warns(tmp_path: Path, fake: FakeSupabase):
    fake.seed("spots", [{"id": "zz-orphan", "name": "Orphan"}])
    r = run("spots", "sync", "--path", str(write_spots(tmp_path, TWO_SPOTS)))
    assert r.exit_code == 0
    assert "warn    1 spots in database but not in YAML (not deleted): zz-orphan" in r.output
    assert_clean(r.output)


def test_sync_missing_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    no_db(monkeypatch)
    r = run("spots", "sync", "--path", str(write_spots(tmp_path, TWO_SPOTS)))
    assert r.exit_code == 1
    assert "run 'shakka doctor'" in r.output
    assert r.output.splitlines()[-1] == "spots sync: failed"
    assert_clean(r.output)


def test_sync_invalid_yaml_writes_nothing(tmp_path: Path, env, monkeypatch: pytest.MonkeyPatch):
    no_db(monkeypatch)
    r = run("spots", "sync", "--path", str(write_spots(tmp_path, THREE_ERRORS)))
    assert r.exit_code == 1
    assert "nothing written" in r.output
    assert "spots sync: failed (3 validation errors, nothing written)" in r.output
    assert_clean(r.output)


def test_sync_database_error(tmp_path: Path, env, monkeypatch: pytest.MonkeyPatch):
    class Broken(FakeSupabase):
        def select(self, *args: Any, **kwargs: Any):
            raise DatabaseError("select spots: HTTP 500", status=500)

    monkeypatch.setattr(shakka.spots.commands, "open_db", lambda settings: Broken())
    r = run("spots", "sync", "--path", str(write_spots(tmp_path, TWO_SPOTS)))
    assert r.exit_code == 1
    assert "error   database: select spots: HTTP 500" in r.output
    assert r.output.splitlines()[-1] == "spots sync: failed"
    assert_clean(r.output)


def test_help_lists_spots():
    assert "spots" in run("--help").output
    out = run("spots", "--help").output
    assert "validate" in out and "sync" in out
