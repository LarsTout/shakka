"""Tests for the hourly pipeline (WP-11): lifecycle, statuses, annotations, steps."""

import logging
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Literal

import httpx
import pytest

from fakes import FakeSupabase
from job_fixtures import NOW
from shakka.config import Settings
from shakka.db import DatabaseError
from shakka.pipeline import (
    ABANDONED_SUMMARY,
    MAX_ANNOTATIONS,
    MAX_ERROR_SUMMARY,
    PipelineContext,
    RunReport,
    StepOutcome,
    StepReport,
    StepSkipped,
    build_annotations,
    error_summary,
    exit_code_for,
    run_hourly,
    run_status,
)

SECRET = "sb_secret_TESTVALUE"
SETTINGS = Settings(supabase_url="http://127.0.0.1:54321", supabase_secret_key=SECRET)


def blocked_http() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))


def rep(name="x", status="ok", **kw: Any) -> StepReport:
    return StepReport(name, status, 1, kw.pop("counts", {}), **kw)


def ok_step(ctx: PipelineContext) -> StepOutcome:
    return StepOutcome("ok", {"n": 1})


def boom_step(ctx: PipelineContext) -> StepOutcome:
    raise RuntimeError(f"boom {SECRET}")


IngestRunsCall = Literal["abandon", "insert", "progress", "final"]


class FlakyIngestRuns(FakeSupabase):
    def __init__(self, fail_on: frozenset[IngestRunsCall]) -> None:
        super().__init__()
        self.fail_on = fail_on

    def _maybe_fail(self, kind: IngestRunsCall) -> None:
        if kind in self.fail_on:
            raise DatabaseError("boom", status=503)

    def insert(self, table, rows, *, returning=False):
        if table == "ingest_runs":
            self._maybe_fail("insert")
        return super().insert(table, rows, returning=returning)

    def update(self, table, values, *, filters):
        if table == "ingest_runs":
            if "status" in filters:
                self._maybe_fail("abandon")
            elif "id" in filters and "finished_at" in values:
                self._maybe_fail("final")
            elif "id" in filters and set(values) == {"steps"}:
                self._maybe_fail("progress")
        return super().update(table, values, filters=filters)


def run(db, steps, **kw) -> RunReport:
    return run_hourly(SETTINGS, now=NOW, db=db, http=blocked_http(), steps=steps, **kw)


# -- pure functions ---------------------------------------------------------------------------


def test_run_status_rules():
    assert run_status([]) == "ok"
    assert run_status([rep(), rep("b")]) == "ok"
    assert run_status([rep(), rep("b", "failed")]) == "partial"
    assert run_status([rep("forecast", "failed"), rep("alerts")]) == "partial"
    assert run_status([rep(), rep("alerts", "failed")]) == "failed"
    assert run_status([rep("a", "failed"), rep("b", "failed")]) == "failed"
    assert run_status([rep("a", "failed"), rep("b", "skipped", reason="r")]) == "failed"
    assert run_status([rep("a", "partial")]) == "partial"


def test_exit_code_for():
    assert exit_code_for("ok", []) == 0
    assert exit_code_for("partial", [rep()]) == 0
    assert exit_code_for("failed", [rep()]) == 1
    stale = rep("alerts", "skipped", reason="stale_forecast")
    assert exit_code_for("partial", [stale]) == 1
    other = rep("alerts", "skipped", reason="other")
    assert exit_code_for("partial", [other]) == 0


def test_error_summary():
    assert error_summary([rep(), rep("b")]) is None
    reports = [
        rep("a", "failed", error="RuntimeError: x"),
        rep("b", "skipped", reason="stale_forecast"),
        rep("c", "partial"),
        rep("d"),
    ]
    assert error_summary(reports) == ("a: RuntimeError: x; b: skipped (stale_forecast); c: partial")
    long = error_summary([rep("a", "failed", error="e" * 3000)])
    assert long is not None and len(long) == MAX_ERROR_SUMMARY


def test_build_annotations():
    reports = [
        rep("forecast", "failed", error="secret text", error_type="RuntimeError"),
        rep("tides", "ok", warnings=("50% done\nnext",)),
        rep("alerts", "skipped", reason="stale_forecast"),
    ]
    lines = build_annotations(reports, run_id=7)
    assert lines[0] == "::error::step forecast failed (RuntimeError); details in ingest_runs id 7"
    assert lines[1] == "::warning::tides: 50%25 done next"
    assert lines[2].startswith("::error::alerts skipped (stale_forecast)")
    assert not any("secret text" in ln or "\n" in ln or "\r" in ln for ln in lines)
    many = [rep(f"s{i}", "ok", warnings=("w",)) for i in range(20)]
    assert len(build_annotations(many, run_id=1)) == MAX_ANNOTATIONS


# -- lifecycle --------------------------------------------------------------------------------


def test_naive_now_raises():
    with pytest.raises(ValueError):
        run_hourly(
            SETTINGS,
            now=NOW.replace(tzinfo=None),
            db=FakeSupabase(),
            http=blocked_http(),
            steps=[],
        )


def test_records_run_ok():
    db = FakeSupabase()
    report = run(db, [("a", ok_step)], clock=lambda: NOW + timedelta(minutes=1))
    (row,) = db.rows("ingest_runs")
    assert row["status"] == "ok" and row["finished_at"] is not None
    assert row["error_summary"] is None
    assert report.run_id == row["id"] and report.exit_code == 0
    assert set(row["steps"][0]) == {
        "name", "status", "duration_ms", "counts", "error", "error_type", "reason", "warnings",
    }  # fmt: skip


def test_all_steps_failed():
    db = FakeSupabase()
    report = run(db, [("a", boom_step), ("b", boom_step)])
    assert report.status == "failed" and report.exit_code == 1
    (row,) = db.rows("ingest_runs")
    assert row["status"] == "failed"
    assert [s["status"] for s in row["steps"]] == ["failed", "failed"]


def test_error_text_is_redacted():
    db = FakeSupabase()
    report = run(db, [("a", boom_step)])
    step = report.steps[0]
    assert SECRET not in (step.error or "")
    assert (step.error or "").startswith("RuntimeError: boom ***")
    assert step.error_type == "RuntimeError"
    assert SECRET not in str(db.rows("ingest_runs"))


def test_step_skipped():
    def skip(ctx: PipelineContext) -> StepOutcome:
        raise StepSkipped("why")

    db = FakeSupabase()
    report = run(db, [("a", skip)])
    assert report.steps[0].status == "skipped" and report.steps[0].reason == "why"
    assert db.rows("ingest_runs")[0]["status"] == "failed"  # nothing ok


def test_cannot_start_run():
    called: list[int] = []

    def step(ctx: PipelineContext) -> StepOutcome:
        called.append(1)
        return StepOutcome("ok", {})

    report = run(FlakyIngestRuns(frozenset({"insert"})), [("a", step)])
    assert called == []
    assert report.status == "failed" and report.steps == [] and report.run_id is None
    assert report.exit_code == 1
    assert report.annotations[0].startswith("::error::run-hourly: cannot record the run")


def test_finish_update_failure_exit_1():
    db = FlakyIngestRuns(frozenset({"final"}))
    report = run(db, [("a", ok_step)])
    assert report.status == "ok" and report.exit_code == 1
    assert any("could not record the end of run" in a for a in report.annotations)


def test_progress_update_after_each_step():
    db = FakeSupabase()
    steps = [("a", ok_step), ("b", ok_step), ("c", ok_step)]
    run(db, steps)
    assert db.writes.count(("update", "ingest_runs")) == len(steps) + 2


def test_progress_update_failure_continues(caplog):
    db = FlakyIngestRuns(frozenset({"progress"}))
    with caplog.at_level(logging.INFO):
        report = run(db, [("a", ok_step), ("b", ok_step)])
    assert [s.status for s in report.steps] == ["ok", "ok"]
    assert report.exit_code == 0
    warnings = [r for r in caplog.records if "could not record progress" in r.getMessage()]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert db.rows("ingest_runs")[0]["status"] == "ok"


def test_abandon_failure_continues(caplog):
    db = FlakyIngestRuns(frozenset({"abandon"}))
    with caplog.at_level(logging.INFO):
        report = run(db, [("a", ok_step)])
    warnings = [r for r in caplog.records if "could not close abandoned runs" in r.getMessage()]
    assert len(warnings) == 1
    assert report.status == "ok"


def test_abandoned_runs_marked_failed():
    db = FakeSupabase()
    db.seed(
        "ingest_runs",
        [
            {"started_at": NOW - timedelta(hours=2), "status": "running"},
            {"started_at": NOW - timedelta(minutes=30), "status": "running"},
        ],
    )
    run(db, [("a", ok_step)])
    rows = sorted(db.rows("ingest_runs"), key=lambda r: r["id"])
    assert rows[0]["status"] == "failed" and rows[0]["error_summary"] == ABANDONED_SUMMARY
    assert rows[0]["finished_at"] is not None
    assert rows[1]["status"] == "running"


def test_counts_not_json_fails_step():
    def nan_step(ctx: PipelineContext) -> StepOutcome:
        return StepOutcome("ok", {"x": float("nan")})

    db = FakeSupabase()
    report = run(db, [("a", nan_step), ("b", ok_step)])
    first, second = report.steps
    assert first.status == "failed" and first.error_type == "ValueError" and first.counts == {}
    assert second.status == "ok"
    row = db.rows("ingest_runs")[0]
    assert row["finished_at"] is not None and row["status"] != "running"


def test_injected_clients_not_closed():
    http = blocked_http()
    run_hourly(SETTINGS, now=NOW, db=FakeSupabase(), http=http, steps=[])
    assert not http.is_closed


def test_steps_sequence_type():
    steps: Sequence[Any] = []
    assert run(FakeSupabase(), steps).status == "ok"
