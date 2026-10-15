"""Tests for the repository activity check (WP-11)."""

from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner

import shakka.jobs.runtime as runtime
from shakka.activity import ActivityCheck, check_activity, parse_commit_date
from shakka.cli import cli

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("days", "level"),
    [(0, "ok"), (44, "ok"), (45, "warn"), (52, "warn"), (53, "fail"), (70, "fail")],
)
def test_check_activity_thresholds(days, level):
    assert check_activity(NOW - timedelta(days=days), now=NOW) == ActivityCheck(level, days)


def test_check_activity_future_is_zero():
    assert check_activity(NOW + timedelta(days=3), now=NOW) == ActivityCheck("ok", 0)


def test_check_activity_naive_raises():
    with pytest.raises(ValueError):
        check_activity(datetime(2026, 1, 1), now=NOW)  # noqa: DTZ001


def test_parse_commit_date():
    assert parse_commit_date("2026-08-01T10:00:00Z") == datetime(2026, 8, 1, 10, tzinfo=UTC)
    assert parse_commit_date("") is None
    assert parse_commit_date("garbage") is None
    assert parse_commit_date("2026-08-01T10:00:00") is None


@pytest.mark.parametrize(
    ("days", "code", "prefix"),
    [(44, 0, "activity:"), (45, 0, "::warning::"), (53, 1, "::error::")],
)
def test_cli(monkeypatch, days, code, prefix):
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW)
    last = (NOW - timedelta(days=days)).isoformat()
    result = CliRunner().invoke(cli, ["check-activity", "--last-commit-at", last])
    assert result.exit_code == code
    assert result.output.startswith(prefix)


def test_cli_empty_input(monkeypatch):
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW)
    result = CliRunner().invoke(cli, ["check-activity"])
    assert result.exit_code == 0
    assert result.output.startswith("::warning::Could not determine")
