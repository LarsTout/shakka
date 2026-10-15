"""Tests for `shakka run-hourly` (WP-11): exit code, secrets, privacy, configuration."""

import logging

import pytest
from click.testing import CliRunner

import shakka.jobs.runtime as runtime
import shakka.openmeteo.forecast as om_forecast
import shakka.pipeline as pipeline
from fakes import FakeSupabase
from job_fixtures import NOW, USER_A, seed_forecasts
from pipeline_fixtures import (
    blocked_http,
    fake_forecast_fetch,
    seed_user,
    write_spots_yaml,
)
from shakka.cli import cli
from shakka.jobs.alerts import run_alerts
from shakka.pipeline import RunReport, run_hourly_cli
from shakka.spots.loader import load_spots
from shakka.spots.sync import sync_spots

SECRET = "sb_secret_TESTVALUE"


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    quiet = {n: logging.getLogger(n).level for n in ("httpx", "httpcore")}
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    for name, lvl in quiet.items():
        logging.getLogger(name).setLevel(lvl)


def set_env(monkeypatch, spots_path=None):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    if spots_path is not None:
        monkeypatch.setenv("SPOTS_PATH", str(spots_path))


def patch_runtime(monkeypatch, db):
    monkeypatch.setattr(runtime, "open_db", lambda settings: db)
    monkeypatch.setattr(runtime, "open_http", blocked_http)
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW)


@pytest.mark.parametrize("code", [0, 1])
def test_cli_exit_code_follows_report(monkeypatch, code):
    set_env(monkeypatch)
    patch_runtime(monkeypatch, FakeSupabase())
    monkeypatch.setattr(
        pipeline, "run_hourly", lambda *a, **kw: RunReport("ok", [], exit_code=code)
    )
    result = CliRunner().invoke(cli, ["run-hourly"])
    assert result.exit_code == code
    assert f"exit_code={code} run_id=none" in result.output


def test_secret_not_in_log_output(monkeypatch, tmp_path, caplog, capsys, restore_logging):
    set_env(monkeypatch, write_spots_yaml(tmp_path))
    db = FakeSupabase()
    patch_runtime(monkeypatch, db)

    def leaking(http, locations, **kw):
        raise RuntimeError(f"leak {SECRET}")

    monkeypatch.setattr(om_forecast, "fetch_forecast", leaking)
    caplog.set_level(logging.DEBUG)
    run_hourly_cli(echo=print)
    captured = capsys.readouterr()
    assert SECRET not in caplog.text
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    forecast = db.rows("ingest_runs")[0]["steps"][1]
    assert forecast["status"] == "failed"
    assert "***" in forecast["error"] and SECRET not in forecast["error"]


def test_budget_warning_on_stdout(monkeypatch, tmp_path, capsys, restore_logging):
    set_env(monkeypatch, write_spots_yaml(tmp_path))
    db = FakeSupabase()
    db.seed(
        "api_usage",
        [{"day": "2026-07-15", "source": "open_meteo_forecast", "calls": 6500, "requests": 1}],
    )
    patch_runtime(monkeypatch, db)
    monkeypatch.setattr(om_forecast, "fetch_forecast", fake_forecast_fetch)
    code = run_hourly_cli(echo=print)
    out = capsys.readouterr().out
    assert code == 0
    assert any(line.startswith("::warning::") for line in out.splitlines())


def test_no_user_ids_or_message_texts_in_output(
    monkeypatch, tmp_path, caplog, capsys, restore_logging
):
    yaml_path = write_spots_yaml(tmp_path)
    db2 = FakeSupabase()
    sync_spots(db2, load_spots(yaml_path))
    seed_forecasts(db2, fetched_at=NOW)
    seed_user(db2)
    dry = run_alerts(db2, now=NOW, base_url=None, dry_run=True)
    assert len(dry.messages) == 1
    title = dry.messages[0].message.title
    body_lines = [ln for ln in dry.messages[0].message.body.splitlines() if ln.strip()]

    set_env(monkeypatch, yaml_path)
    db = FakeSupabase()
    seed_user(db)
    patch_runtime(monkeypatch, db)
    monkeypatch.setattr(om_forecast, "fetch_forecast", fake_forecast_fetch)
    caplog.set_level(logging.DEBUG)
    assert run_hourly_cli(echo=print) == 0
    alerts = db.rows("ingest_runs")[0]["steps"][-1]
    assert alerts["status"] == "ok" and alerts["counts"]["events"] == 1
    captured = capsys.readouterr()
    out = caplog.text + captured.out + captured.err
    assert USER_A not in out and title not in out
    for line in body_lines:
        assert line not in out


def test_missing_config():
    result = CliRunner().invoke(cli, ["run-hourly"])
    assert result.exit_code == 1
    assert "configuration incomplete" in result.output
    assert any(ln.startswith("::error::") for ln in result.output.splitlines())


def test_run_hourly_listed_in_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert "run-hourly" in result.output and "check-activity" in result.output
