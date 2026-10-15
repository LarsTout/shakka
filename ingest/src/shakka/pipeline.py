"""Hourly orchestration: run all steps in a fixed order and record the run.

Steps: spots_sync, forecast, marine, tides, evaluate, alerts, sessions_cleanup (retention).

Every run is a row in `ingest_runs`. A step that raises never stops the others. Stdout and
logs carry counts and statuses only (the Actions logs are public); error texts and lists
(which may name favorite spots) live in `ingest_runs.steps` only.
"""

import dataclasses
import functools
import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final, Literal

import httpx
import pydantic

import shakka.jobs.runtime as runtime
import shakka.openmeteo.forecast as om_forecast
import shakka.openmeteo.marine as om_marine
import shakka.rws.tides as rws
from shakka.budget import BudgetGuard
from shakka.config import Settings, get_settings
from shakka.db import DatabaseError, SupabaseRest, iso_utc, to_json
from shakka.jobs.alerts import AlertJobResult, run_alerts
from shakka.jobs.evaluate import run_evaluation
from shakka.jobs.forecast import FetchForecast, run_forecast_ingest
from shakka.jobs.inputs import db_error_summary, require_aware, short_error
from shakka.jobs.marine import FetchMarine, run_marine_ingest
from shakka.jobs.sessions import purge_expired_sessions
from shakka.jobs.tides import TideFetcher, run_tide_ingest
from shakka.logsetup import configure_logging, github_annotation, redact, secret_values
from shakka.notify.base import Notifier
from shakka.notify.webpush import notifiers_from_settings
from shakka.spots.loader import load_spots
from shakka.spots.sync import sync_spots

logger = logging.getLogger(__name__)

StepStatus = Literal["ok", "partial", "failed", "skipped"]
RunStatus = Literal["ok", "partial", "failed"]  # "running" only exists in the database

INGEST_RUNS: Final = "ingest_runs"
STALE_FORECAST: Final = "stale_forecast"
STALE_FORECAST_AGE: Final = timedelta(hours=3)
BUDGET_WARN_FRACTION: Final = 0.8
ABANDONED_AFTER: Final = timedelta(hours=1)
ABANDONED_SUMMARY: Final = "abandoned: the run did not record its end (timeout or crash)"
MAX_ERROR_SUMMARY: Final = 1000
MAX_ANNOTATIONS: Final = 10
# Read from the module at every step_tides call (never as a default argument), so a test can
# monkeypatch it.
TIDE_STEP_BUDGET_S: Final = 240.0
# Budget for the whole run, checked before each step (read from the module at run time). The
# job timeout is 900 s; this way a slow run is recorded instead of killed halfway.
RUN_TIME_BUDGET_S: Final = 600.0
RUN_TIME_BUDGET: Final = "run_time_budget"
PUSH_DISABLED_WARNING: Final = (
    "push disabled: VAPID secrets not set; alerts are stored but not delivered"
)
MARINE_BUDGET_WARNING: Final = "Open-Meteo budget guard reached: marine request skipped"
STEP_NAMES: Final = (
    "spots_sync",
    "forecast",
    "marine",
    "tides",
    "evaluate",
    "alerts",
    "sessions_cleanup",
)

_monotonic: Callable[[], float] = time.monotonic  # looked up at call time; tests monkeypatch it


class StepSkipped(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class StepOutcome:
    status: Literal["ok", "partial"]
    counts: Mapping[str, Any]
    warnings: tuple[str, ...] = ()  # public texts (stdout annotations)


@dataclass(frozen=True, slots=True)
class StepReport:
    name: str
    status: StepStatus
    duration_ms: int
    counts: dict[str, Any]  # JSON-ready
    error: str | None = None  # private: ingest_runs only, secrets redacted
    error_type: str | None = None  # public: exception type or db_error_summary
    reason: str | None = None  # iff status == "skipped"
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "counts": self.counts,
            "error": self.error,
            "error_type": self.error_type,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class RunReport:
    status: RunStatus
    steps: list[StepReport]
    exit_code: int
    run_id: int | None = None
    annotations: tuple[str, ...] = ()


@dataclass(slots=True)
class PipelineContext:
    settings: Settings
    db: SupabaseRest
    http: httpx.Client
    now: datetime
    budget: BudgetGuard
    forecast_fetch: FetchForecast
    tide_fetch: TideFetcher
    secrets: tuple[str, ...] = ()
    reports: list[StepReport] = field(default_factory=list)
    notifiers: Mapping[str, Notifier] | None = None  # None: build from Settings in step_alerts
    marine_fetch: FetchMarine | None = None  # None: om_marine.fetch_marine at call time

    def report(self, name: str) -> StepReport | None:
        return next((r for r in self.reports if r.name == name), None)


StepFn = Callable[[PipelineContext], StepOutcome]
Step = tuple[str, StepFn]


# -- steps ------------------------------------------------------------------------------------


def step_spots_sync(ctx: PipelineContext) -> StepOutcome:
    spots = load_spots(ctx.settings.spots_path)
    result = sync_spots(ctx.db, spots)
    counts = {"spots": len(spots), "upserted": result.upserted, "orphaned": len(result.orphaned)}
    warnings = ()
    if result.orphaned:
        warnings = (f"spots in the database but not in the YAML: {', '.join(result.orphaned)}",)
    return StepOutcome("ok", counts, warnings)


def step_forecast(ctx: PipelineContext) -> StepOutcome:
    result = run_forecast_ingest(
        ctx.db, ctx.http, ctx.budget, now=ctx.now, fetch=ctx.forecast_fetch
    )
    counts: dict[str, Any] = dataclasses.asdict(result)
    warnings: list[str] = []
    try:
        usage = ctx.budget.usage(now=ctx.now)
    except DatabaseError:
        warnings.append("Open-Meteo usage could not be read")
    else:
        counts["usage_daily"] = round(usage.daily, 2)
        counts["usage_monthly"] = round(usage.monthly, 2)
        for label, used, limit in (
            ("today", usage.daily, ctx.budget.daily_limit),
            ("this month", usage.monthly, ctx.budget.monthly_limit),
        ):
            if used > BUDGET_WARN_FRACTION * limit:
                pct = 100 * used / limit
                warnings.append(
                    f"Open-Meteo usage {label} is {used:.2f} of {limit:.0f} calls "
                    f"({pct:.0f}% of the guard)"
                )
    if result.skipped_budget:
        warnings.append("Open-Meteo budget guard reached: a request was skipped")
    partial = bool(result.errors) or result.skipped_budget
    return StepOutcome("partial" if partial else "ok", counts, tuple(warnings))


def step_marine(ctx: PipelineContext) -> StepOutcome:
    fetch = ctx.marine_fetch or om_marine.fetch_marine
    result = run_marine_ingest(ctx.db, ctx.http, ctx.budget, now=ctx.now, fetch=fetch)
    warnings = (MARINE_BUDGET_WARNING,) if result.skipped_budget else ()
    partial = bool(result.errors) or result.skipped_budget
    return StepOutcome("partial" if partial else "ok", dataclasses.asdict(result), warnings)


def step_tides(ctx: PipelineContext) -> StepOutcome:
    budget_s = TIDE_STEP_BUDGET_S  # module global, read now
    deadline = _monotonic() + budget_s
    budget_skipped = 0

    def bounded_fetch(station: str, start: datetime, end: datetime) -> Any:
        nonlocal budget_skipped
        if _monotonic() >= deadline:
            budget_skipped += 1
            raise TimeoutError(f"tide step time budget of {budget_s:.0f} s reached")
        return ctx.tide_fetch(station, start, end)

    result = run_tide_ingest(ctx.db, now=ctx.now, fetch=bounded_fetch)
    counts: dict[str, Any] = dataclasses.asdict(result)
    counts["budget_skipped"] = budget_skipped
    warnings = ()
    if budget_skipped:
        warnings = (
            f"time budget of {budget_s:.0f} s reached; "
            f"{budget_skipped} station(s) not fetched this run",
        )
    return StepOutcome("partial" if result.failed else "ok", counts, warnings)


def step_evaluate(ctx: PipelineContext) -> StepOutcome:
    result = run_evaluation(ctx.db, now=ctx.now)
    return StepOutcome("partial" if result.failed else "ok", dataclasses.asdict(result))


def newest_forecast_fetch(db: SupabaseRest) -> datetime | None:
    rows = db.select("forecast_hours", columns="fetched_at", order="fetched_at.desc", limit=1)
    if not rows:
        return None
    value = rows[0]["fetched_at"]
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def alert_counts(result: AlertJobResult) -> dict[str, Any]:
    """Counts only; never messages, user ids or message texts."""
    kinds = {"new": 0, "improved": 0, "worsened": 0, "cancelled": 0}
    for rendered in result.messages:
        kinds[str(rendered.message.kind)] += 1
    return {
        "users": result.users,
        "events": result.events,
        "favorites": result.favorites,
        "ineligible": result.ineligible,
        "disabled": result.disabled,
        "skipped": result.skipped,
        "write_errors": result.write_errors,
        "deleted": result.deleted,
        "sent": result.sent,
        "failed": result.failed,
        "no_target": result.no_target,
        "deferred": result.deferred,
        "blocked_targets": result.blocked_targets,
        "push_non_retryable": result.push_non_retryable,
        "removed": result.removed,
        "push_enabled": result.push_enabled,
        "push_failures": dict(result.push_failures),
        **kinds,
        "errors": list(result.errors),
    }


def deferred_warning(deferred: int) -> str:
    return (
        f"{deferred} favorite(s) deferred: no push delivery succeeded; "
        "retried next run (see push_failures in ingest_runs)"
    )


def non_retryable_warning(count: int) -> str:
    return (
        f"{count} push delivery(ies) failed without retry; the alert is lost for that "
        "device (see push_failures in ingest_runs)"
    )


def step_alerts(ctx: PipelineContext) -> StepOutcome:
    # A configuration error must stand out, also in a run where alerts are skipped as stale
    # (review N-4): building the notifiers has no side effects, so it comes first.
    notifiers = (
        ctx.notifiers if ctx.notifiers is not None else notifiers_from_settings(ctx.settings)
    )
    forecast = ctx.report("forecast")
    if forecast is not None and forecast.status != "ok":
        newest = newest_forecast_fetch(ctx.db)
        if newest is None or newest < ctx.now - STALE_FORECAST_AGE:
            raise StepSkipped(STALE_FORECAST)
    warnings: list[str] = []
    if not notifiers:
        logger.warning(
            "alerts: push disabled (no VAPID configuration); alert state is stored without delivery"
        )
        warnings.append(PUSH_DISABLED_WARNING)
    result = run_alerts(
        ctx.db, now=ctx.now, base_url=ctx.settings.app_base_url, notifiers=notifiers
    )
    if result.deferred:
        warnings.append(deferred_warning(result.deferred))
    if result.push_non_retryable:
        warnings.append(non_retryable_warning(result.push_non_retryable))
    if result.blocked_targets:
        warnings.append(
            f"{result.blocked_targets} push subscription(s) skipped: push service host not allowed"
        )
    partial = bool(
        result.skipped or result.write_errors or result.deferred or result.push_non_retryable
    )
    return StepOutcome(
        "partial" if partial else "ok", alert_counts(result), warnings=tuple(warnings)
    )


def step_sessions_cleanup(ctx: PipelineContext) -> StepOutcome:
    deleted = purge_expired_sessions(ctx.db, now=ctx.now)
    return StepOutcome("ok", {"deleted": deleted})


STEPS: Final[tuple[Step, ...]] = (
    ("spots_sync", step_spots_sync),
    ("forecast", step_forecast),
    ("marine", step_marine),
    ("tides", step_tides),
    ("evaluate", step_evaluate),
    ("alerts", step_alerts),
    ("sessions_cleanup", step_sessions_cleanup),
)


# -- step runner and run status ---------------------------------------------------------------


def run_step(name: str, fn: StepFn, ctx: PipelineContext) -> StepReport:
    start = _monotonic()
    counts: dict[str, Any] = {}
    warnings: tuple[str, ...] = ()
    error: str | None = None
    error_type: str | None = None
    reason: str | None = None
    status: StepStatus
    try:
        outcome = fn(ctx)
        counts = json.loads(to_json(dict(outcome.counts)))
        warnings = tuple(outcome.warnings)
        status = outcome.status
    except StepSkipped as skip:
        status, reason, counts, warnings = "skipped", skip.reason, {}, ()
    except Exception as exc:
        status, counts, warnings = "failed", {}, ()
        error = redact(f"{type(exc).__name__}: {short_error(exc)}", ctx.secrets)
        error_type = db_error_summary(exc) if isinstance(exc, DatabaseError) else type(exc).__name__
    duration_ms = int((_monotonic() - start) * 1000)
    return StepReport(name, status, duration_ms, counts, error, error_type, reason, warnings)


def run_status(reports: Sequence[StepReport]) -> RunStatus:
    if all(r.status == "ok" for r in reports):
        return "ok"
    alerts = next((r for r in reports if r.name == "alerts"), None)
    if alerts is not None and alerts.status == "failed":
        return "failed"
    if not any(r.status in ("ok", "partial") for r in reports):
        return "failed"
    return "partial"


def exit_code_for(status: RunStatus, reports: Sequence[StepReport]) -> int:
    if status == "failed":
        return 1
    stale = any(
        r.name == "alerts" and r.status == "skipped" and r.reason == STALE_FORECAST for r in reports
    )
    over_budget = any(r.status == "skipped" and r.reason == RUN_TIME_BUDGET for r in reports)
    return 1 if stale or over_budget else 0


def error_summary(reports: Sequence[StepReport]) -> str | None:
    parts: list[str] = []
    for r in reports:
        if r.status == "failed":
            parts.append(f"{r.name}: {r.error}")
        elif r.status == "skipped":
            parts.append(f"{r.name}: skipped ({r.reason})")
        elif r.status == "partial":
            parts.append(f"{r.name}: partial")
    if not parts:
        return None
    return "; ".join(parts)[:MAX_ERROR_SUMMARY]


def build_annotations(reports: Sequence[StepReport], *, run_id: int | None) -> tuple[str, ...]:
    lines: list[str] = []
    for r in reports:
        if r.status == "failed":
            lines.append(
                github_annotation(
                    "error",
                    f"step {r.name} failed ({r.error_type}); details in ingest_runs id {run_id}",
                )
            )
        elif r.status == "skipped" and r.reason == STALE_FORECAST:
            lines.append(
                github_annotation(
                    "error",
                    "alerts skipped (stale_forecast): the newest forecast is older than "
                    "3 hours; no alerts this run",
                )
            )
        elif r.status == "skipped" and r.reason == RUN_TIME_BUDGET:
            lines.append(
                github_annotation(
                    "error",
                    f"step {r.name} skipped: run time budget of {RUN_TIME_BUDGET_S:.0f} s reached",
                )
            )
        for warning in r.warnings:
            lines.append(github_annotation("warning", f"{r.name}: {warning}"))
    return tuple(lines[:MAX_ANNOTATIONS])


# -- the run ----------------------------------------------------------------------------------

_LEVELS = {"ok": logging.INFO, "partial": logging.WARNING, "skipped": logging.WARNING}


def _step_log_line(report: StepReport) -> str:
    parts = [
        f"pipeline: step={report.name} status={report.status} duration_ms={report.duration_ms}"
    ]
    for key, value in report.counts.items():
        if isinstance(value, bool | int | float):
            parts.append(f"{key}={value}")
    if report.status == "failed":
        parts.append(f"error_type={report.error_type}")
    if report.status == "skipped":
        parts.append(f"reason={report.reason}")
    if report.warnings:
        parts.append(f"warnings={len(report.warnings)}")
    return " ".join(parts)


def _close_abandoned(db: SupabaseRest, now: datetime) -> None:
    try:
        db.update(
            INGEST_RUNS,
            {"finished_at": now, "status": "failed", "error_summary": ABANDONED_SUMMARY},
            filters={"status": "eq.running", "started_at": f"lt.{iso_utc(now - ABANDONED_AFTER)}"},
        )
    except DatabaseError as exc:
        logger.warning("pipeline: could not close abandoned runs (%s)", db_error_summary(exc))


def run_hourly(
    settings: Settings,
    *,
    now: datetime,
    db: SupabaseRest | None = None,
    http: httpx.Client | None = None,
    steps: Sequence[Step] = STEPS,
    forecast_fetch: FetchForecast | None = None,
    tide_fetch: TideFetcher | None = None,
    clock: Callable[[], datetime] | None = None,
    notifiers: Mapping[str, Notifier] | None = None,
    marine_fetch: FetchMarine | None = None,
) -> RunReport:
    require_aware(now)
    own_db = db is None
    own_http = http is None
    if db is None:
        db = runtime.open_db(settings)
    try:
        if http is None:
            http = runtime.open_http()
        try:
            return _run(
                settings,
                now,
                db,
                http,
                steps,
                forecast_fetch,
                tide_fetch,
                clock,
                notifiers,
                marine_fetch,
            )
        finally:
            if own_http:
                http.close()
    finally:
        if own_db:
            db.close()


def _run(
    settings: Settings,
    now: datetime,
    db: SupabaseRest,
    http: httpx.Client,
    steps: Sequence[Step],
    forecast_fetch: FetchForecast | None,
    tide_fetch: TideFetcher | None,
    clock: Callable[[], datetime] | None,
    notifiers: Mapping[str, Notifier] | None = None,
    marine_fetch: FetchMarine | None = None,
) -> RunReport:
    _close_abandoned(db, now)
    try:
        rows = db.insert(
            INGEST_RUNS, [{"started_at": now, "status": "running", "steps": []}], returning=True
        )
        run_id = int(rows[0]["id"])
    except DatabaseError as exc:
        summary = db_error_summary(exc)
        logger.error("pipeline: cannot record the run (%s)", summary)
        return RunReport(
            "failed",
            [],
            1,
            None,
            (
                github_annotation(
                    "error", f"run-hourly: cannot record the run in ingest_runs ({summary})"
                ),
            ),
        )

    ctx = PipelineContext(
        settings,
        db,
        http,
        now,
        BudgetGuard(db),
        forecast_fetch or om_forecast.fetch_forecast,
        tide_fetch or functools.partial(rws.fetch_tide_extremes, http=http),
        secrets=secret_values(settings),
        notifiers=notifiers,
        marine_fetch=marine_fetch or om_marine.fetch_marine,
    )
    by_id = {"id": f"eq.{run_id}"}
    progress_warned = False
    started = _monotonic()
    for name, fn in steps:
        if _monotonic() - started >= RUN_TIME_BUDGET_S:
            report = StepReport(name, "skipped", 0, {}, reason=RUN_TIME_BUDGET)
        else:
            report = run_step(name, fn, ctx)
        ctx.reports.append(report)
        logger.log(_LEVELS.get(report.status, logging.ERROR), _step_log_line(report))
        try:
            db.update(INGEST_RUNS, {"steps": [r.to_json() for r in ctx.reports]}, filters=by_id)
        except DatabaseError as exc:
            if not progress_warned:
                progress_warned = True
                logger.warning(
                    "pipeline: could not record progress of run %d (%s)",
                    run_id,
                    db_error_summary(exc),
                )

    status = run_status(ctx.reports)
    exit_code = exit_code_for(status, ctx.reports)
    finished_at = max((clock or runtime.utcnow)(), now)
    extra: list[str] = []
    try:
        count = db.update(
            INGEST_RUNS,
            {
                "finished_at": finished_at,
                "status": status,
                "steps": [r.to_json() for r in ctx.reports],
                "error_summary": error_summary(ctx.reports),
            },
            filters=by_id,
        )
        failed_end = count != 1
    except DatabaseError:
        failed_end = True
    if failed_end:
        logger.error("pipeline: could not record the end of run %d", run_id)
        exit_code = 1
        extra.append(
            github_annotation(
                "error", f"run-hourly: could not record the end of run {run_id} in ingest_runs"
            )
        )
    annotations = (*build_annotations(ctx.reports, run_id=run_id), *extra)
    logger.log(
        logging.ERROR if exit_code else logging.INFO,
        "pipeline: run=%d status=%s exit_code=%d duration_ms=%d",
        run_id,
        status,
        exit_code,
        int((_monotonic() - started) * 1000),
    )
    return RunReport(status, ctx.reports, exit_code, run_id, annotations)


def run_hourly_cli(*, echo: Callable[[str], None]) -> int:
    try:
        settings = get_settings()
    except pydantic.ValidationError:
        echo("run-hourly: configuration incomplete; run shakka doctor")
        echo(
            github_annotation(
                "error",
                "run-hourly: configuration incomplete "
                "(check the GitHub Secrets SUPABASE_URL and SUPABASE_SECRET_KEY)",
            )
        )
        return 1
    configure_logging(secrets=secret_values(settings))
    db = runtime.open_db(settings)
    http = runtime.open_http()
    try:
        report = run_hourly(settings, now=runtime.utcnow(), db=db, http=http)
    finally:
        http.close()
        db.close()
    for line in report.annotations:
        echo(line)
    run_id = "none" if report.run_id is None else str(report.run_id)
    echo(f"run-hourly: status={report.status} exit_code={report.exit_code} run_id={run_id}")
    return report.exit_code
