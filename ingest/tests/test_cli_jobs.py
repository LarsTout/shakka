"""CLI tests for `shakka evaluate` and `shakka alerts run` (WP-10)."""

import pytest
from click.testing import CliRunner

import shakka.jobs.runtime
from fakes import FakeSupabase
from job_fixtures import NOW, USER_A, seed_favorite, seed_forecasts, seed_spot
from shakka.cli import cli
from shakka.db import DatabaseError


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret-key")
    state = {"opened": 0}

    def install(db):
        def open_db(settings):
            state["opened"] += 1
            return db

        monkeypatch.setattr(shakka.jobs.runtime, "open_db", open_db)
        monkeypatch.setattr(shakka.jobs.runtime, "utcnow", lambda: NOW)
        return state

    return install


def run(*args):
    result = CliRunner().invoke(cli, list(args))
    return result.exit_code, result.output.splitlines()


def test_evaluate_cli(setup):
    db = FakeSupabase()
    seed_spot(db)
    seed_forecasts(db)
    setup(db)
    code, lines = run("evaluate")
    assert code == 0
    assert lines == ["evaluate: spots=1 rows=9 deleted=0 failed=0", "evaluate: ok"]


def test_evaluate_cli_invalid_spot(setup):
    db = FakeSupabase()
    seed_spot(db, id="kapot-strand")
    db.update("spots", {"lat": 10.0}, filters={"id": "eq.kapot-strand"})
    setup(db)
    code, lines = run("evaluate")
    assert code == 1
    assert any(line.startswith("error   spot ") for line in lines)
    assert lines[-1] == "evaluate: failed"


def test_evaluate_cli_without_forecasts(setup):
    db = FakeSupabase()
    seed_spot(db)
    setup(db)
    code, lines = run("evaluate")
    assert code == 0
    assert lines == ["evaluate: spots=1 rows=0 deleted=0 failed=0", "evaluate: ok"]


# -- alerts run -------------------------------------------------------------------------------


def alert_db(*, forecasts=True, **favorite):
    db = FakeSupabase()
    seed_spot(db, verified=True)
    if forecasts:
        seed_forecasts(db)
    seed_favorite(db, USER_A, **favorite)
    db.writes.clear()
    return db


def test_alerts_run_cli_without_forecasts(setup):
    db = alert_db(forecasts=False, min_kn=12)
    setup(db)
    code, lines = run("alerts", "run")
    assert code == 0
    assert "ineligible=1 disabled=0 skipped=0 write_errors=0" in lines[0]
    assert not any(line.startswith("error") for line in lines)
    assert lines[-1] == "alerts: ok"


def test_alerts_run_cli(setup):
    db = alert_db(min_kn=12)
    setup(db)
    code, lines = run("alerts", "run")
    assert code == 0
    assert lines[0] == "new test-strand: Go: Teststrand"
    assert lines[1] == "  wo 15 jul 12:00–18:00 · 14–25 kn, vlagen tot 29 kn"
    assert lines[-2] == (
        "alerts: users=1 favorites=1 events=1 (new=1 improved=0 worsened=0 cancelled=0) "
        "ineligible=0 disabled=0 skipped=0 write_errors=0 deleted=0"
    )
    assert lines[-1] == "alerts: ok"
    assert USER_A not in "\n".join(lines)


def test_alerts_run_dry_run_writes_nothing(setup):
    db = alert_db(min_kn=12)
    setup(db)
    code, lines = run("alerts", "run", "--dry-run")
    assert code == 0
    assert db.writes == []
    assert "alerts: dry run, nothing stored" in lines


def test_alerts_run_exit_1_on_skip(setup):
    db = alert_db(earliest_local="24:00:00")
    setup(db)
    code, lines = run("alerts", "run")
    assert code == 1
    assert lines[-1] == "alerts: failed"


def test_alerts_run_invalid_base_url(setup, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "example.org")
    state = setup(alert_db(min_kn=12))
    code, lines = run("alerts", "run")
    assert code == 1
    assert "alerts: invalid APP_BASE_URL" in lines
    assert "example.org" not in "\n".join(lines)
    assert state["opened"] == 0


@pytest.mark.parametrize("command", [["evaluate"], ["alerts", "run"]])
def test_missing_config(setup, monkeypatch, command):
    state = setup(FakeSupabase())
    monkeypatch.delenv("SUPABASE_URL")
    monkeypatch.delenv("SUPABASE_SECRET_KEY")
    code, lines = run(*command)
    assert code == 1
    assert lines[-1].endswith("configuration incomplete; run shakka doctor")
    assert state["opened"] == 0


def test_database_error(setup):
    class Broken(FakeSupabase):
        closed = False

        def select(self, *args, **kwargs):
            raise DatabaseError("boom", status=500)

        def close(self):
            self.closed = True

    db = Broken()
    setup(db)
    code, lines = run("alerts", "run")
    assert code == 1
    assert lines[-1].startswith("alerts: database error: ")
    assert db.closed


def test_help_lists_new_commands():
    code, lines = run("--help")
    text = "\n".join(lines)
    assert code == 0
    for name in ("evaluate", "alerts", "admin"):
        assert name in text
    assert "--dry-run" in "\n".join(run("alerts", "run", "--help")[1])
