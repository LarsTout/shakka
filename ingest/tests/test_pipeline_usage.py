"""Usage step in the hourly pipeline (WP-22 AC-3)."""

from datetime import UTC, datetime, timedelta

import pytest

from fakes import FakeSupabase
from job_fixtures import USER_A, USER_B, USER_C
from pipeline_fixtures import (
    blocked_http,
    fake_forecast_fetch,
    fake_marine_fetch,
    make_settings,
    no_tides,
    seed_user,
    write_spots_yaml,
)
from push_fixtures import DOWN, OK, FakeNotifier, seed_subs
from shakka.db import DatabaseError
from shakka.domain.usage import BYTES_PER_MB
from shakka.pipeline import RunReport, run_hourly

MONDAY = datetime(2026, 7, 20, 6, 17, tzinfo=UTC)
WEDNESDAY = datetime(2026, 7, 15, 8, 17, tzinfo=UTC)


@pytest.fixture
def world(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    eps_a = seed_subs(db, USER_A, 2)
    seed_subs(db, USER_B, 1)
    notifier = FakeNotifier()
    return db, notifier, eps_a, tmp_path


def go(world, now, *, operator=USER_A, db=None, notifier=None) -> RunReport:
    base_db, base_notifier, _, tmp_path = world
    settings = make_settings(write_spots_yaml(tmp_path), operator_user_id=operator)
    return run_hourly(
        settings,
        now=now,
        db=db or base_db,
        http=blocked_http(),
        notifiers={"webpush": notifier or base_notifier},
        forecast_fetch=fake_forecast_fetch,
        marine_fetch=fake_marine_fetch,
        tide_fetch=no_tides,
    )


def usage_step(report):
    return next(s for s in report.steps if s.name == "usage_report")


def report_calls(notifier):
    return [(t, p) for t, p in notifier.payload_calls if p.tag == "shakka-usage-report"]


def test_report_sent_on_monday_to_operator_only(world):
    db, notifier, eps_a, _ = world
    report = go(world, MONDAY)
    calls = report_calls(notifier)
    assert len(calls) == 2
    assert {t.endpoint for t, _ in calls} == set(eps_a)
    for _, payload in calls:
        assert len(payload.title) <= 50 and len(payload.body) <= 150
    step = usage_step(report)
    assert step.status == "ok"
    assert step.counts["report_done"] is True
    assert step.counts["report"].startswith("Shakka gebruiksrapport tot 2026-07-20 08:17")
    assert step.counts["stats"] is not None


def test_report_once_per_week(world):
    _, notifier, _, _ = world
    go(world, MONDAY)
    before = len(notifier.payload_calls)
    report = go(world, MONDAY + timedelta(hours=1))
    assert len(notifier.payload_calls) == before
    assert usage_step(report).counts["due"] is False


def test_no_report_on_tuesday(world):
    _, notifier, _, _ = world
    report = go(world, MONDAY + timedelta(days=1))
    assert notifier.payload_calls == []
    assert usage_step(report).counts["due"] is False


def test_no_operator_still_stores_report(world):
    _, notifier, _, _ = world
    report = go(world, MONDAY, operator=None)
    step = usage_step(report)
    assert step.status == "ok" and step.counts["report"] is not None
    assert step.counts["delivery"] == "no_operator"
    assert report_calls(notifier) == []
    assert any(
        a.startswith("::warning::usage_report: OPERATOR_USER_ID not set")
        for a in report.annotations
    )


def test_operator_without_subscription(world):
    report = go(world, MONDAY, operator=USER_C)
    step = usage_step(report)
    assert step.counts["delivery"] == "no_target" and step.counts["report"] is not None


def test_invalid_operator_id_is_partial_and_not_leaked(world):
    db = world[0]
    report = go(world, MONDAY, operator="not-a-uuid-12345")
    assert usage_step(report).status == "partial"
    assert "not-a-uuid-12345" not in str(db.rows("ingest_runs"))
    assert "not-a-uuid-12345" not in "\n".join(report.annotations)


def test_threshold_warning_pushed_once_a_day(world):
    db, notifier, _, _ = world
    db.database_bytes = 310 * BYTES_PER_MB
    report = go(world, WEDNESDAY)
    warning_calls = [p for _, p in notifier.payload_calls if p.tag == "shakka-usage-warning"]
    assert len(warning_calls) == 2  # two devices
    assert any(
        a.startswith("::warning::usage_report: usage threshold: Database 310 MB")
        for a in report.annotations
    )
    again = go(world, WEDNESDAY + timedelta(hours=1))
    assert len([p for _, p in notifier.payload_calls if p.tag == "shakka-usage-warning"]) == 2
    assert any(
        a.startswith("::warning::usage_report: usage threshold: Database 310 MB")
        for a in again.annotations
    )


def test_retry_after_transient_failure(world):
    db, notifier, eps_a, _ = world
    for ep in eps_a:
        notifier.set_result(ep, DOWN)
    report = go(world, MONDAY)
    step = usage_step(report)
    assert step.counts["report_done"] is False and step.status == "partial"
    for ep in eps_a:
        notifier.set_result(ep, OK)
    later = go(world, MONDAY + timedelta(hours=1))
    assert usage_step(later).counts["report_done"] is True
    assert len(report_calls(notifier)) == 4


def test_old_ingest_runs_deleted_on_report(world):
    db = world[0]
    db.seed(
        "ingest_runs",
        [
            {"started_at": MONDAY - timedelta(days=91), "status": "ok", "steps": []},
            {"started_at": MONDAY - timedelta(days=89), "status": "ok", "steps": []},
        ],
    )
    report = go(world, MONDAY)
    assert usage_step(report).counts["runs_deleted"] == 1
    starts = [r["started_at"] for r in db.rows("ingest_runs")]
    assert len(starts) == 2  # the run of 89 days and the current run


def test_missing_db_usage_function_is_partial_not_a_crash(world):
    class NoRpc(FakeSupabase):
        def rpc(self, function, args=None):
            raise DatabaseError("x", status=404, code="PGRST202")

    db = NoRpc()
    seed_user(db)
    report = go(world, WEDNESDAY, db=db)
    step = usage_step(report)
    assert step.status == "partial"
    assert step.counts["errors"] == ["db_usage: DatabaseError (HTTP 404, code PGRST202)"]
