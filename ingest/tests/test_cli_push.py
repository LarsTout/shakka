"""CLI: `alerts run` with push, `alerts test-push`, `alerts vapid-keys` (WP-17)."""

import re

import pytest
import pywebpush
from click.testing import CliRunner
from pywebpush import WebPushException

import shakka.jobs.runtime
from fakes import FakeSupabase
from job_fixtures import NOW, USER_A, seed_favorite, seed_forecasts, seed_spot
from push_fixtures import KEYS, SUBJECT, FakeResponse, RecordingWebpush, seed_subs
from shakka.cli import cli
from shakka.notify.webpush import WebPushNotifier


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


def vapid_env(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", KEYS.public_key)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", KEYS.private_key)
    monkeypatch.setenv("VAPID_SUBJECT", SUBJECT)


def run(*args):
    result = CliRunner().invoke(cli, list(args))
    return result.exit_code, result.output.splitlines(), result.output


def push_db():
    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_forecasts(db)
    seed_favorite(db, USER_A, min_kn=12)
    eps = seed_subs(db, USER_A, 1)
    db.writes.clear()
    return db, eps


def patch_webpush(monkeypatch, rec):
    monkeypatch.setattr(pywebpush, "webpush", rec)


def test_alerts_run_push_disabled(setup):
    db, _ = push_db()
    setup(db)
    code, lines, _ = run("alerts", "run")
    assert code == 0
    assert lines[-3].startswith("alerts: users=1")
    assert lines[-2] == "push: disabled (no VAPID configuration)"
    assert lines[-1] == "alerts: ok"


def test_alerts_run_push_enabled(setup, monkeypatch):
    vapid_env(monkeypatch)
    db, eps = push_db()
    setup(db)
    rec = RecordingWebpush()
    patch_webpush(monkeypatch, rec)
    code, lines, output = run("alerts", "run")
    assert code == 0
    assert "push: sent=1 failed=0 no_target=0 deferred=0 removed=0" in lines
    assert len(rec.calls) == 1
    assert eps[0] not in output
    assert USER_A not in output


def test_alerts_run_deferred_exit_1(setup, monkeypatch):
    vapid_env(monkeypatch)
    db, _ = push_db()
    setup(db)
    patch_webpush(
        monkeypatch,
        RecordingWebpush(raises=WebPushException("x", response=FakeResponse(503))),
    )
    code, lines, _ = run("alerts", "run")
    assert code == 1
    assert "push: sent=0 failed=1 no_target=0 deferred=1 removed=0" in lines
    assert lines[-1] == "alerts: failed"
    assert db.rows("alert_state") == []


def test_alerts_run_dry_run_push_line(setup, monkeypatch):
    vapid_env(monkeypatch)
    db, _ = push_db()
    setup(db)
    rec = RecordingWebpush()
    patch_webpush(monkeypatch, rec)
    code, lines, _ = run("alerts", "run", "--dry-run")
    assert code == 0
    assert "push: nothing sent (dry run)" in lines
    assert rec.calls == []


def test_alerts_run_invalid_vapid(setup, monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", KEYS.private_key)
    db, _ = push_db()
    state = setup(db)
    code, lines, output = run("alerts", "run")
    assert code == 1
    assert lines[0].startswith(
        "alerts: invalid VAPID configuration: incomplete VAPID configuration"
    )
    assert state["opened"] == 0
    assert KEYS.private_key not in output


def test_test_push_cli(setup, monkeypatch):
    vapid_env(monkeypatch)
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 3)
    setup(db)
    rec = RecordingWebpush(
        per_endpoint={
            eps[1]: WebPushException("x", response=FakeResponse(503)),
            eps[2]: WebPushException("x", response=FakeResponse(410)),
        }
    )
    patch_webpush(monkeypatch, rec)
    code, lines, output = run("alerts", "test-push", "--user-id", USER_A)
    assert code == 0
    assert lines == [
        "test-push: device 1: ok",
        "test-push: device 2: failed (HTTP 503)",
        "test-push: device 3: gone (HTTP 410); subscription removed",
        "test-push: sent=1 failed=2 removed=1",
        "test-push: ok",
    ]
    for secret in (*eps, KEYS.private_key, SUBJECT, USER_A):
        assert secret not in output


def test_test_push_cli_errors(setup, monkeypatch):
    db = FakeSupabase()
    state = setup(db)
    code, lines, _ = run("alerts", "test-push", "--user-id", USER_A)
    assert code == 1
    assert lines[0].startswith("test-push: push is disabled")
    assert state["opened"] == 0

    vapid_env(monkeypatch)
    code, lines, _ = run("alerts", "test-push", "--user-id", USER_A)
    assert code == 1
    assert lines == [
        "test-push: no push subscriptions for this user; turn on notifications in the app first"
    ]

    eps = seed_subs(db, USER_A, 1)
    patch_webpush(
        monkeypatch,
        RecordingWebpush(per_endpoint={eps[0]: WebPushException("x", response=FakeResponse(503))}),
    )
    code, lines, _ = run("alerts", "test-push", "--user-id", USER_A)
    assert code == 1
    assert lines[-1] == "test-push: failed"

    code, _, _ = run("alerts", "test-push", "--user-id", "not-a-uuid")
    assert code == 2


def test_vapid_keys_cli(setup):
    state = setup(FakeSupabase())
    code, lines, _ = run("alerts", "vapid-keys")
    assert code == 0
    assert len(lines) == 3
    assert re.fullmatch(r"VAPID_PUBLIC_KEY=[A-Za-z0-9_-]{87}", lines[0])
    assert re.fullmatch(r"VAPID_PRIVATE_KEY=[A-Za-z0-9_-]{43}", lines[1])
    public = lines[0].split("=", 1)[1]
    private = lines[1].split("=", 1)[1]
    assert WebPushNotifier(private, SUBJECT).public_key == public
    assert state["opened"] == 0


def test_help_lists_push_commands():
    code, _, output = run("alerts", "--help")
    assert code == 0
    for name in ("run", "test-push", "vapid-keys"):
        assert name in output
