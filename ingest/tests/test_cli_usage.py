"""`shakka usage show` (WP-22): prints the report, sends and writes nothing."""

import pytest
from click.testing import CliRunner

import shakka.jobs.runtime as runtime
from fakes import FakeSupabase
from shakka.cli import cli
from shakka.db import DatabaseError


def run():
    return CliRunner().invoke(cli, ["usage", "show"])


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://testref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_TESTVALUE")


def test_show_prints_report(configured, monkeypatch):
    db = FakeSupabase()
    monkeypatch.setattr(runtime, "open_db", lambda settings: db)
    result = run()
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0].startswith("Shakka gebruiksrapport tot ")
    assert "Database: 50 MB van 500 MB" in lines
    assert not any(line.startswith("error") for line in lines)
    assert db.writes == []


def test_show_error_line_and_exit_1(configured, monkeypatch):
    class NoRpc(FakeSupabase):
        def rpc(self, function, args=None):
            raise DatabaseError("x", status=404, code="PGRST202")

    monkeypatch.setattr(runtime, "open_db", lambda settings: NoRpc())
    result = run()
    assert result.exit_code == 1
    assert "error   db_usage: DatabaseError (HTTP 404, code PGRST202)" in result.output
    assert "Database: onbekend" in result.output


def test_show_without_configuration():
    result = run()
    assert result.exit_code == 1
    assert "usage show: configuration incomplete; run shakka doctor" in result.output
