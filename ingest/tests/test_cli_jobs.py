"""CLI tests for `shakka evaluate` and `shakka alerts run` (WP-10)."""

import pytest
from click.testing import CliRunner

import shakka.jobs.runtime
from fakes import FakeSupabase
from job_fixtures import NOW, seed_forecasts, seed_spot
from shakka.cli import cli


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
