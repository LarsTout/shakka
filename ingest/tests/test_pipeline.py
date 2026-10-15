"""Tests for the hourly pipeline (WP-11): lifecycle, statuses, annotations, steps."""

import logging
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Literal

import pytest
import pywebpush

import shakka.pipeline as pipeline
from evaluation_fixtures import make_spot
from fakes import FakeSupabase
from job_fixtures import NOW, USER_A, WINDS, seed_favorite, seed_forecasts, seed_profile
from pipeline_fixtures import (
    PIPELINE_SPOT,
    blocked_http,
    failing_forecast_fetch,
    failing_marine_fetch,
    fake_forecast_fetch,
    fake_marine_fetch,
    make_settings,
    no_tides,
    seed_user,
    write_spots_yaml,
)
from push_fixtures import DOWN, KEYS, SUBJECT, FakeNotifier, seed_subs, sub_row
from shakka.config import Settings
from shakka.db import DatabaseError, iso_utc
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


# -- real steps -------------------------------------------------------------------------------


def run_real(tmp_path, db, *, spots=(PIPELINE_SPOT,), settings=None, **kw) -> RunReport:
    settings = settings or make_settings(write_spots_yaml(tmp_path, spots))
    kw.setdefault("forecast_fetch", fake_forecast_fetch)
    kw.setdefault("marine_fetch", fake_marine_fetch)
    kw.setdefault("tide_fetch", no_tides)
    return run_hourly(settings, now=NOW, db=db, http=blocked_http(), **kw)


def step(report: RunReport, name: str) -> StepReport:
    return next(s for s in report.steps if s.name == name)


def test_steps_contract_order():
    assert [n for n, _ in pipeline.STEPS] == [
        "spots_sync", "forecast", "marine", "tides", "evaluate", "alerts", "sessions_cleanup",
    ]  # fmt: skip
    assert [n for n, _ in pipeline.STEPS] == list(pipeline.STEP_NAMES)


def test_all_steps_ok_records_run(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    report = run_real(tmp_path, db, clock=lambda: NOW + timedelta(minutes=1))
    (row,) = db.rows("ingest_runs")
    assert row["status"] == "ok" and row["finished_at"] is not None
    assert row["error_summary"] is None
    assert [s["name"] for s in row["steps"]] == list(pipeline.STEP_NAMES)
    keys = set(rep().to_json())
    assert all(set(s) == keys for s in row["steps"])
    assert report.exit_code == 0 and report.run_id == row["id"]
    first_insert = next(i for i, (kind, _) in enumerate(db.writes) if kind == "insert")
    assert db.writes[first_insert] == ("insert", "ingest_runs")
    assert db.writes[:first_insert] == [("update", "ingest_runs")]
    alerts = next(s for s in row["steps"] if s["name"] == "alerts")
    assert alerts["counts"]["events"] == 1 and alerts["counts"]["new"] == 1
    last = row["steps"][-1]
    assert last["name"] == "sessions_cleanup" and last["status"] == "ok"
    assert last["counts"] == {"deleted": 0}


def test_sessions_cleanup_deletes_expired(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    db.seed("sessions", [{"id": "s-old", "ends_at": iso_utc(NOW - timedelta(days=8))}])
    db.seed("rsvps", [{"id": "r-old", "session_id": "s-old"}])
    report = run_real(tmp_path, db)
    cleanup = step(report, "sessions_cleanup")
    assert cleanup.status == "ok" and cleanup.counts == {"deleted": 1}
    assert db.rows("sessions") == [] and db.rows("rsvps") == []
    assert ("purge_expired_sessions", {"p_now": iso_utc(NOW)}) in db.rpc_calls


def _boom(args):
    raise DatabaseError("boom", status=503)


def test_sessions_cleanup_failure_is_partial(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    db.register_rpc("purge_expired_sessions", _boom)
    report = run_real(tmp_path, db)
    cleanup = step(report, "sessions_cleanup")
    assert cleanup.status == "failed" and (cleanup.error_type or "").startswith("DatabaseError")
    assert all(s.status == "ok" for s in report.steps if s.name != "sessions_cleanup")
    assert report.status == "partial" and report.exit_code == 0
    assert db.rows("ingest_runs")[0]["status"] == "partial"
    prefix = "::error::step sessions_cleanup failed (DatabaseError"
    assert any(a.startswith(prefix) for a in report.annotations)


def test_sessions_cleanup_value_error_is_failed(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    db.register_rpc("purge_expired_sessions", lambda args: None)
    report = run_real(tmp_path, db)
    cleanup = step(report, "sessions_cleanup")
    assert cleanup.status == "failed" and cleanup.error_type == "ValueError"
    assert report.status == "partial"


def _stale_db(hours: float) -> FakeSupabase:
    db = FakeSupabase()
    seed_user(db)
    db.seed("spots", [make_spot(verified=True).to_row()])
    seed_forecasts(db, fetched_at=NOW - timedelta(hours=hours))
    return db


def test_forecast_exception_with_stale_data_skips_alerts(tmp_path):
    db = _stale_db(4)
    db.writes.clear()
    report = run_real(tmp_path, db, forecast_fetch=failing_forecast_fetch(RuntimeError("boom")))
    assert [step(report, n).status for n in ("tides", "evaluate")] == ["ok", "ok"]
    alerts = step(report, "alerts")
    assert alerts.status == "skipped" and alerts.reason == "stale_forecast"
    forecast = step(report, "forecast")
    assert forecast.status == "failed" and (forecast.error or "").startswith("RuntimeError: ")
    assert forecast.error_type == "RuntimeError"
    assert report.status == "partial" and report.exit_code == 1
    assert ("insert", "alert_state") not in db.writes
    assert ("update", "alert_state") not in db.writes
    assert ("upsert", "alert_state") not in db.writes
    assert any(a.startswith("::error::alerts skipped") for a in report.annotations)


def test_forecast_exception_with_fresh_data_runs_alerts(tmp_path):
    db = _stale_db(2)
    report = run_real(tmp_path, db, forecast_fetch=failing_forecast_fetch(RuntimeError("boom")))
    assert step(report, "alerts").status == "ok"
    assert report.status == "partial" and report.exit_code == 0


def test_stale_boundary_exactly_three_hours_is_fresh(tmp_path):
    db = _stale_db(3)
    report = run_real(tmp_path, db, forecast_fetch=failing_forecast_fetch(RuntimeError("boom")))
    assert step(report, "alerts").status == "ok"


def test_forecast_failed_without_rows_is_stale(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    report = run_real(tmp_path, db, forecast_fetch=failing_forecast_fetch(RuntimeError("boom")))
    assert step(report, "alerts").reason == "stale_forecast"
    assert report.exit_code == 1


def test_forecast_partial_triggers_stale_check(tmp_path):
    from shakka.openmeteo.forecast import ForecastFetchError

    db = _stale_db(4)
    report = run_real(
        tmp_path, db, forecast_fetch=failing_forecast_fetch(ForecastFetchError("down"))
    )
    assert step(report, "forecast").status == "partial"
    assert step(report, "alerts").status == "skipped"


def test_forecast_ok_without_coordinates_runs_alerts(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    spot = {k: v for k, v in PIPELINE_SPOT.items() if k not in ("lat", "lon")}
    spot["verified"] = False
    report = run_real(tmp_path, db, spots=(spot,))
    assert report.status == "ok"
    assert step(report, "alerts").counts["ineligible"] == 1


def test_failed_run_exit_code_1(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    settings = make_settings(write_spots_yaml(tmp_path), app_base_url="not a url")
    report = run_real(tmp_path, db, settings=settings)
    assert step(report, "alerts").status == "failed"
    assert report.status == "failed" and report.exit_code == 1


def test_budget_warning_recorded(tmp_path):
    db = FakeSupabase()
    db.seed(
        "api_usage",
        [{"day": "2026-07-15", "source": "open_meteo_forecast", "calls": 6500, "requests": 1}],
    )
    report = run_real(tmp_path, db)
    forecast = step(report, "forecast")
    assert forecast.status == "ok"
    assert len(forecast.warnings) == 1
    assert forecast.warnings[0].startswith("Open-Meteo usage today is ")
    assert "% of the guard" in forecast.warnings[0]
    assert forecast.counts["usage_daily"] > 6400
    assert report.status == "ok" and report.exit_code == 0
    line = next(
        a for a in report.annotations if a.startswith("::warning::forecast: Open-Meteo usage today")
    )
    assert "%25 of the guard" in line


@pytest.mark.parametrize("calls", [6000, 6398.8])
def test_budget_below_threshold_no_warning(tmp_path, calls):
    db = FakeSupabase()
    db.seed(
        "api_usage",
        [{"day": "2026-07-15", "source": "open_meteo_forecast", "calls": calls, "requests": 1}],
    )
    report = run_real(tmp_path, db)
    assert step(report, "forecast").warnings == ()


# -- marine step (WP-12) -----------------------------------------------------------------------


def test_marine_step_ok_counts(tmp_path):
    db = FakeSupabase()
    report = run_real(tmp_path, db)
    marine = step(report, "marine")
    assert marine.status == "ok"
    assert marine.counts["rows"] == len(WINDS) and marine.counts["calls"] == 1.0
    assert len(db.rows("marine_hours")) == len(WINDS)
    assert {r["source"] for r in db.rows("api_usage")} == {
        "open_meteo_forecast",
        "open_meteo_marine",
    }


def test_marine_exception_is_partial_run(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    report = run_real(tmp_path, db, marine_fetch=failing_marine_fetch(RuntimeError("boom")))
    marine = step(report, "marine")
    assert marine.status == "failed" and marine.error_type == "RuntimeError"
    assert [step(report, n).status for n in ("tides", "evaluate", "alerts")] == ["ok"] * 3
    assert report.status == "partial" and report.exit_code == 0
    assert step(report, "alerts").counts["events"] == 1


def test_marine_fetch_error_is_partial_step(tmp_path):
    from shakka.openmeteo.marine import MarineFetchError

    db = FakeSupabase()
    report = run_real(tmp_path, db, marine_fetch=failing_marine_fetch(MarineFetchError("down")))
    marine = step(report, "marine")
    assert marine.status == "partial"
    assert marine.counts["errors"] == ["chunk 1/1: down"]
    assert report.status == "partial" and report.exit_code == 0
    assert db.rows("marine_hours") == []


def test_marine_budget_skipped_after_forecast(tmp_path):
    db = FakeSupabase()
    db.seed(
        "api_usage",
        [{"day": "2026-07-15", "source": "open_meteo_forecast", "calls": 7998.5, "requests": 1}],
    )
    report = run_real(tmp_path, db)
    assert step(report, "forecast").status == "ok"
    marine = step(report, "marine")
    assert marine.status == "partial" and marine.counts["skipped_budget"] is True
    assert marine.warnings == (pipeline.MARINE_BUDGET_WARNING,)
    assert (
        "::warning::marine: Open-Meteo budget guard reached: marine request skipped"
        in report.annotations
    )
    assert report.status == "partial" and report.exit_code == 0
    assert db.rows("marine_hours") == []


def test_marine_fallback_looks_up_module_function(tmp_path, monkeypatch):
    import shakka.openmeteo.marine as om_marine

    monkeypatch.setattr(om_marine, "fetch_marine", fake_marine_fetch)
    db = FakeSupabase()
    settings = make_settings(write_spots_yaml(tmp_path))
    report = run_hourly(
        settings,
        now=NOW,
        db=db,
        http=blocked_http(),
        forecast_fetch=fake_forecast_fetch,
        tide_fetch=no_tides,
    )
    assert step(report, "marine").status == "ok"


def test_spots_sync_failure_continues(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    db.seed("spots", [make_spot(verified=True).to_row()])
    settings = make_settings(tmp_path / "missing.yaml")
    report = run_real(tmp_path, db, settings=settings)
    sync = step(report, "spots_sync")
    assert sync.status == "failed" and sync.error_type == "SpotValidationError"
    assert len(report.steps) == 7
    assert all(s.status == "ok" for s in report.steps[1:])
    assert report.status == "partial" and report.exit_code == 0


def test_spots_sync_orphan_warning(tmp_path):
    db = FakeSupabase()
    db.seed("spots", [make_spot(id="old-spot").to_row()])
    report = run_real(tmp_path, db)
    sync = step(report, "spots_sync")
    assert sync.counts["orphaned"] == 1
    assert sync.warnings == ("spots in the database but not in the YAML: old-spot",)


def test_tides_partial(tmp_path):
    from shakka.rws.tides import TideFetchError

    spot = {**PIPELINE_SPOT, "rws_station": "hoekvanholland", "tide_sensitive": "none"}

    def failing(station, start, end):
        raise TideFetchError("down")

    db = FakeSupabase()
    report = run_real(tmp_path, db, spots=(spot,), tide_fetch=failing)
    tides = step(report, "tides")
    assert tides.status == "partial"
    assert tides.counts["failed"] == ["hoekvanholland"]


def _tide_ctx(db) -> tuple[PipelineContext, list[str], list[float]]:
    from shakka.budget import BudgetGuard
    from shakka.rws.tides import TideFetchError

    calls: list[str] = []

    def fetch(station, start, end):
        calls.append(station)
        clock[0] += pipeline.TIDE_STEP_BUDGET_S + 1
        raise TideFetchError("down")

    clock = [0.0]
    ctx = PipelineContext(
        SETTINGS, db, blocked_http(), NOW, BudgetGuard(db), fake_forecast_fetch, fetch
    )
    return ctx, calls, clock


def test_tide_budget_stops_fetching(monkeypatch):
    db = FakeSupabase()
    db.seed(
        "spots",
        [
            make_spot(id="spot-a", rws_station="station-a").to_row(),
            make_spot(id="spot-b", rws_station="station-b").to_row(),
        ],
    )
    ctx, calls, clock = _tide_ctx(db)
    monkeypatch.setattr(pipeline, "_monotonic", lambda: clock[0])
    outcome = pipeline.step_tides(ctx)
    assert calls == ["station-a"]
    assert outcome.status == "partial"
    assert outcome.counts["failed"] == ["station-a", "station-b"]
    assert outcome.counts["budget_skipped"] == 1
    assert any(
        e.startswith("station-b: TimeoutError: tide step time budget")
        for e in outcome.counts["errors"]
    )
    assert len(outcome.warnings) == 1
    assert outcome.warnings[0].startswith("time budget of 240 s reached; 1 station(s)")


def test_tide_budget_zero_still_runs_alerts(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "TIDE_STEP_BUDGET_S", 0.0)
    spot = {**PIPELINE_SPOT, "rws_station": "hoekvanholland", "tide_sensitive": "none"}

    def must_not_run(station, start, end):
        raise AssertionError("tide fetch must not be called")

    db = FakeSupabase()
    seed_user(db)
    report = run_real(tmp_path, db, spots=(spot,), tide_fetch=must_not_run)
    tides = step(report, "tides")
    assert tides.status == "partial" and tides.counts["budget_skipped"] == 1
    assert step(report, "evaluate").status == "ok" and step(report, "alerts").status == "ok"
    assert report.status == "partial" and report.exit_code == 0
    assert any(a.startswith("::warning::tides: time budget") for a in report.annotations)


def test_alert_counts_shape():
    from shakka.jobs.alerts import AlertJobResult

    counts = pipeline.alert_counts(AlertJobResult(users=1, events=0, messages=[]))
    assert set(counts) == {
        "users", "events", "favorites", "ineligible", "disabled", "skipped", "write_errors",
        "deleted", "new", "improved", "worsened", "cancelled", "errors",
        "sent", "failed", "no_target", "deferred", "removed", "push_enabled", "push_failures",
        "blocked_targets", "push_non_retryable",
    }  # fmt: skip
    assert "messages" not in counts


def test_alerts_errors_only_in_ingest_runs(tmp_path, caplog, capsys):
    from shakka.logsetup import configure_logging

    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        configure_logging()
        db = FakeSupabase()
        seed_profile(db, USER_A, level="intermediate")
        seed_favorite(db, USER_A, "test-strand", earliest_local="24:00:00")
        with caplog.at_level(logging.INFO):
            report = run_real(tmp_path, db)
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    alerts = step(report, "alerts")
    assert alerts.status == "partial"
    assert any("spot test-strand:" in e for e in alerts.counts["errors"])
    out = capsys.readouterr()
    assert "spot test-strand:" not in caplog.text + out.out + out.err


# -- push (WP-17) -----------------------------------------------------------------------------

PUSH_SECRETS = ("ENDPOINT-SECRET-123", "P256DH-SECRET-456", "AUTH-SECRET-789")


def vapid_settings(tmp_path, **overrides):
    values = {
        "vapid_public_key": KEYS.public_key,
        "vapid_private_key": KEYS.private_key,
        "vapid_subject": SUBJECT,
    }
    return make_settings(write_spots_yaml(tmp_path, (PIPELINE_SPOT,)), **{**values, **overrides})


def test_hourly_without_vapid(tmp_path, caplog):
    db = FakeSupabase()
    seed_user(db)
    with caplog.at_level(logging.INFO):
        report = run_real(tmp_path, db)
    alerts = step(report, "alerts")
    assert alerts.status == "ok"
    counts = alerts.counts
    assert counts["events"] == 1 and counts["new"] == 1
    assert counts["sent"] == counts["failed"] == counts["no_target"] == 0
    assert counts["deferred"] == counts["removed"] == 0
    assert counts["push_enabled"] is False
    assert any(
        r.levelno == logging.WARNING and "push disabled" in r.getMessage() for r in caplog.records
    )
    assert any(a.startswith("::warning::alerts: push disabled") for a in report.annotations)
    (row,) = db.rows("alert_state")
    assert (row["status"], row["last_event"], row["last_notified_at"]) == ("active", "new", None)


def test_hourly_incomplete_vapid(tmp_path, caplog):
    db = FakeSupabase()
    seed_user(db)
    settings = make_settings(
        write_spots_yaml(tmp_path, (PIPELINE_SPOT,)),
        vapid_private_key=KEYS.private_key,
        vapid_subject=SUBJECT,
    )
    with caplog.at_level(logging.DEBUG):
        report = run_real(tmp_path, db, settings=settings)
    alerts = step(report, "alerts")
    assert alerts.status == "failed" and alerts.error_type == "ValueError"
    assert report.status == "failed" and report.exit_code == 1
    for text in (str(db.rows("ingest_runs")), caplog.text):
        assert KEYS.private_key not in text
        assert SUBJECT not in text


def test_hourly_incomplete_vapid_fails_even_when_stale(tmp_path):
    """Review N-4: a configuration error also fails a run in which alerts would be stale."""
    db = FakeSupabase()
    seed_user(db)
    settings = make_settings(
        write_spots_yaml(tmp_path, (PIPELINE_SPOT,)), vapid_private_key=KEYS.private_key
    )
    report = run_real(
        tmp_path,
        db,
        settings=settings,
        forecast_fetch=failing_forecast_fetch(RuntimeError("down")),
    )
    assert step(report, "forecast").status == "failed"
    assert step(report, "alerts").status == "failed"
    stale = run_real(
        tmp_path,
        FakeSupabase(),
        forecast_fetch=failing_forecast_fetch(RuntimeError("down")),
    )
    assert step(stale, "alerts").status == "skipped"


def test_hourly_with_notifiers(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    seed_subs(db, USER_A, 1)
    report = run_real(tmp_path, db, notifiers={"webpush": FakeNotifier()})
    alerts = step(report, "alerts")
    assert alerts.counts["sent"] == 1 and alerts.counts["push_enabled"] is True
    assert not any("push disabled" in a for a in report.annotations)


def test_hourly_push_failure_leaks_nothing(tmp_path, caplog, capsys, monkeypatch):
    from shakka.logsetup import configure_logging, secret_values

    ep = "https://fcm.googleapis.com/fcm/send/ENDPOINT-SECRET-123"

    def failing(**kwargs):
        raise Exception(f"{ep} P256DH-SECRET-456 AUTH-SECRET-789 {KEYS.private_key}")

    monkeypatch.setattr(pywebpush, "webpush", failing)
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        settings = vapid_settings(tmp_path)
        configure_logging(secrets=secret_values(settings))
        db = FakeSupabase()
        seed_user(db)
        db.seed(
            "push_subscriptions",
            [
                {
                    "user_id": USER_A,
                    "endpoint": ep,
                    "p256dh": PUSH_SECRETS[1],
                    "auth": PUSH_SECRETS[2],
                }
            ],
        )
        with caplog.at_level(logging.DEBUG):
            report = run_real(tmp_path, db, settings=settings)
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    out = capsys.readouterr()
    haystacks = [
        caplog.text,
        out.out,
        out.err,
        "\n".join(report.annotations),
        str(db.rows("ingest_runs")),
    ]
    for text in haystacks:
        for secret in (*PUSH_SECRETS, KEYS.private_key, SUBJECT, USER_A):
            assert secret not in text
    alerts = step(report, "alerts")
    assert alerts.counts["push_failures"] == {"Exception": 1}
    assert alerts.status == "partial" and alerts.counts["push_non_retryable"] == 1


def test_hourly_deferred_warning(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    (ep,) = seed_subs(db, USER_A, 1)
    report = run_real(tmp_path, db, notifiers={"webpush": FakeNotifier({ep: DOWN})})
    alerts = step(report, "alerts")
    assert alerts.status == "partial" and report.exit_code == 0
    assert alerts.warnings == (pipeline.deferred_warning(1),)
    assert (
        "::warning::alerts: 1 favorite(s) deferred: no push delivery succeeded; "
        "retried next run (see push_failures in ingest_runs)"
    ) in report.annotations
    ok_db = FakeSupabase()
    seed_user(ok_db)
    seed_subs(ok_db, USER_A, 1)
    ok_report = run_real(tmp_path, ok_db, notifiers={"webpush": FakeNotifier()})
    assert not any(a.startswith("::warning::alerts:") for a in ok_report.annotations)


def test_non_retryable_push_is_partial_with_warning(tmp_path):
    from shakka.notify.base import DeliveryResult

    db = FakeSupabase()
    seed_user(db)
    (ep,) = seed_subs(db, USER_A, 1)
    forbidden = DeliveryResult(False, False, "HTTP 403", retryable=False)
    report = run_real(tmp_path, db, notifiers={"webpush": FakeNotifier({ep: forbidden})})
    alerts = step(report, "alerts")
    assert alerts.status == "partial"
    assert alerts.counts["push_non_retryable"] == 1
    assert alerts.counts["push_failures"] == {"HTTP 403": 1}
    assert alerts.counts["deferred"] == 0
    assert (
        "::warning::alerts: 1 push delivery(ies) failed without retry; the alert is lost for "
        "that device (see push_failures in ingest_runs)"
    ) in report.annotations
    assert report.exit_code == 0


def test_blocked_target_warning(tmp_path):
    db = FakeSupabase()
    seed_user(db)
    db.seed(
        "push_subscriptions",
        [{**sub_row(USER_A, 1), "endpoint": "https://evil.example.test/x"}],
    )
    report = run_real(tmp_path, db, notifiers={"webpush": FakeNotifier()})
    alerts = step(report, "alerts")
    assert alerts.counts["blocked_targets"] == 1
    assert (
        "::warning::alerts: 1 push subscription(s) skipped: push service host not allowed"
    ) in report.annotations


def test_per_spot_staleness_with_two_spots(tmp_path):
    other = {**PIPELINE_SPOT, "id": "oud-strand", "name": "Oud strand"}
    db = FakeSupabase()
    seed_user(db)
    old = NOW - timedelta(hours=4)
    db.seed(
        "forecast_hours",
        [
            {
                "spot_id": "oud-strand",
                "model": "knmi",
                "valid_at": NOW.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2),
                "wind_kn": 15.0,
                "gust_kn": 18.0,
                "dir_deg": 270,
                "fetched_at": old,
            }
        ],
    )

    def only_first(http, locations, **kw):
        return fake_forecast_fetch(http, [loc for loc in locations if loc.spot_id == "test-strand"])

    report = run_real(tmp_path, db, spots=(PIPELINE_SPOT, other), forecast_fetch=only_first)
    spots = {r["spot_id"] for r in db.rows("evaluations")}
    assert spots == {"test-strand"}
    assert step(report, "evaluate").status in ("ok", "partial")
    assert step(report, "alerts").status in ("ok", "partial")


def test_run_time_budget_skips_remaining_steps(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(pipeline, "_monotonic", lambda: clock[0])

    def evaluate(ctx):
        return pipeline.StepOutcome("ok", {})

    def slow(ctx):
        clock[0] += 601.0
        return pipeline.StepOutcome("ok", {})

    def never(ctx):
        raise AssertionError("must be skipped")

    db = FakeSupabase()
    steps = [
        ("evaluate", evaluate),
        ("slow", slow),
        ("alerts", never),
        ("sessions_cleanup", never),
        ("usage_report", never),
    ]
    report = run_hourly(SETTINGS, now=NOW, db=db, http=blocked_http(), steps=steps)
    by_name = {s.name: s for s in report.steps}
    assert by_name["slow"].status == "ok"
    for name in ("alerts", "sessions_cleanup", "usage_report"):
        assert by_name[name].status == "skipped"
        assert by_name[name].reason == "run_time_budget"
    assert report.status == "partial"
    assert report.exit_code == 1
    errors = [a for a in report.annotations if a.startswith("::error::")]
    assert len(errors) == 3
    assert "step alerts skipped: run time budget of 600 s reached" in errors[0]
