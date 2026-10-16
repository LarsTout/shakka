"""Usage report and threshold warnings for the operator (WP-22).

Reads Open-Meteo usage (`api_usage`), the database size (RPC `db_usage`) and, when a report is
due, the run history (`ingest_runs`). Sends a short push to the operator and stores the full
report in the step counts. Logs and notes carry counts and statuses only: never an endpoint,
the operator's user id or a subscription.
"""

import logging
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, Literal

from pydantic import ValidationError

from shakka.budget import OPEN_METEO_PREFIX
from shakka.config import get_settings
from shakka.db import DatabaseError, SupabaseRest, iso_utc
from shakka.domain.push import PushPayload
from shakka.domain.usage import (
    REPORT_DAYS,
    UsageStats,
    build_usage_report,
    in_operator_window,
    local_day_start,
    report_due_time,
    usage_push_text,
    usage_warnings,
    warning_push_text,
    week_start,
)
from shakka.jobs import runtime
from shakka.jobs.inputs import db_error_summary, require_aware
from shakka.jobs.push import load_targets, update_subscriptions
from shakka.notify.base import DeliveryResult, Notifier

logger = logging.getLogger("shakka.jobs.usage")

USAGE_STEP: Final = "usage_report"
DB_USAGE_RPC: Final = "db_usage"
INGEST_RUNS_RETENTION: Final = timedelta(days=90)
REPORT_TAG: Final = "shakka-usage-report"
WARNING_TAG: Final = "shakka-usage-warning"
OPERATOR_PUSH_URL: Final = "/"
DeliveryStatus = Literal[
    "sent", "failed", "no_operator", "invalid_operator", "push_disabled", "no_target"
]

NOTE_NO_OPERATOR: Final = (
    "OPERATOR_USER_ID not set: usage push not sent (report stored in ingest_runs)"
)
NOTE_INVALID_OPERATOR: Final = "OPERATOR_USER_ID is not a valid UUID: usage push not sent"
NOTE_PUSH_DISABLED: Final = "push disabled or misconfigured: usage push not sent"
NOTE_NO_TARGET: Final = "no push subscription for the operator: usage push not sent"
NOTE_PUSH_CONFIG: Final = "push configuration invalid: usage push not sent"


@dataclass(frozen=True, slots=True)
class OpenMeteoUsage:
    today: float
    max_day: float
    month: float


@dataclass(frozen=True, slots=True)
class DbUsage:
    database_bytes: int
    table_rows: dict[str, int]


@dataclass(frozen=True, slots=True)
class RunHistory:
    ok: int
    partial: int
    failed: int
    step_issues: dict[str, int]
    push_sent: int
    push_failed: int


@dataclass(frozen=True, slots=True)
class OperatorDelivery:
    status: DeliveryStatus
    sent: int = 0
    failed: int = 0
    removed: int = 0
    retryable: bool = False  # status == "failed" and a retry next run makes sense
    push_failures: dict[str, int] = field(default_factory=dict)  # detail -> count


@dataclass(frozen=True, slots=True)
class UsageReportResult:
    stats: UsageStats
    warnings: tuple[str, ...]  # usage_warnings(stats), Dutch
    report_due: bool
    report: str | None  # build_usage_report(stats) when due
    report_done: bool
    warning_notified: bool
    delivery: OperatorDelivery | None  # None if no push was due
    runs_deleted: int
    errors: tuple[str, ...]  # "<source>: DatabaseError (HTTP n, code c)" | "db_usage: ..."
    notes: tuple[str, ...]  # English, public, without values

    @property
    def status(self) -> Literal["ok", "partial"]:
        if self.errors:
            return "partial"
        if self.delivery is not None and self.delivery.status in ("failed", "invalid_operator"):
            return "partial"
        return "ok"


# -- readers ---------------------------------------------------------------------------------


def _utc_date(now: datetime) -> date:
    return now.astimezone(UTC).date()


def read_open_meteo_usage(db: SupabaseRest, *, now: datetime) -> OpenMeteoUsage:
    """Open-Meteo calls (all `open_meteo_*` sources): today, best of the last 7 days, month."""
    require_aware(now)
    today = _utc_date(now)
    first = today.replace(day=1)
    week_first = today - timedelta(days=REPORT_DAYS - 1)
    start = min(first, week_first)
    rows = db.select(
        "api_usage",
        columns="day,source,calls",
        filters={"day": [f"gte.{start.isoformat()}", f"lte.{today.isoformat()}"]},
    )
    per_day: Counter[date] = Counter()
    for row in rows:
        if not str(row["source"]).startswith(OPEN_METEO_PREFIX):
            continue
        per_day[date.fromisoformat(str(row["day"])[:10])] += float(row["calls"])
    week = [calls for day, calls in per_day.items() if week_first <= day <= today]
    return OpenMeteoUsage(
        today=float(per_day.get(today, 0.0)),
        max_day=float(max(week, default=0.0)),
        month=float(sum(calls for day, calls in per_day.items() if day >= first)),
    )


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def read_db_usage(db: SupabaseRest) -> DbUsage:
    """Database size and exact row counts from the service-only RPC. ValueError on a bad shape."""
    data = db.rpc(DB_USAGE_RPC)
    if not isinstance(data, dict):
        raise ValueError("db_usage: unexpected response")
    size, tables = data.get("database_bytes"), data.get("tables")
    if not _is_count(size) or not isinstance(tables, dict):
        raise ValueError("db_usage: unexpected response")
    if not all(isinstance(k, str) and _is_count(v) for k, v in tables.items()):
        raise ValueError("db_usage: unexpected response")
    return DbUsage(database_bytes=size, table_rows=dict(tables))


def _run_window(*, since: datetime, now: datetime) -> dict[str, list[str]]:
    return {"started_at": [f"gte.{iso_utc(since)}", f"lt.{iso_utc(now)}"]}


def _step_dicts(row: object) -> list[dict[str, Any]]:
    steps = row.get("steps") if isinstance(row, dict) else None
    return [s for s in steps if isinstance(s, dict)] if isinstance(steps, list) else []


def _count(value: object) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 0


def read_run_history(db: SupabaseRest, *, now: datetime) -> RunHistory:
    """Finished runs of the last 7 days: statuses, steps that were not ok, and alert pushes."""
    require_aware(now)
    rows = db.select(
        "ingest_runs",
        columns="started_at,status,steps",
        filters=_run_window(since=now - timedelta(days=REPORT_DAYS), now=now),
    )
    statuses: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    sent = failed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        statuses[str(row.get("status"))] += 1
        for step in _step_dicts(row):
            name = step.get("name")
            if not isinstance(name, str):
                continue
            if step.get("status") in ("partial", "failed", "skipped"):
                issues[name] += 1
            counts = step.get("counts")
            if name == "alerts" and isinstance(counts, dict):
                sent += _count(counts.get("sent", 0))
                failed += _count(counts.get("failed", 0))
    return RunHistory(
        ok=statuses["ok"],
        partial=statuses["partial"],
        failed=statuses["failed"],
        step_issues=dict(issues),
        push_sent=sent,
        push_failed=failed,
    )


def earlier_usage_counts(
    db: SupabaseRest, *, since: datetime, now: datetime
) -> list[dict[str, Any]]:
    """The counts of the usage step in earlier runs in [since, now): the current run is excluded."""
    rows = db.select(
        "ingest_runs",
        columns="started_at,steps",
        filters=_run_window(since=since, now=now),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        for step in _step_dicts(row):
            counts = step.get("counts")
            if step.get("name") == USAGE_STEP and isinstance(counts, dict):
                out.append(counts)
    return out


# -- operator and push -----------------------------------------------------------------------


def resolve_operator(value: str | None) -> str | None:
    """Canonical UUID of the operator, None if unset. ValueError if it is not a UUID."""
    if value is None or not value.strip():
        return None
    return str(uuid.UUID(value.strip()))


def deliver_operator_push(
    db: SupabaseRest,
    notifier: Notifier | None,
    operator_id: str | None,
    payload: PushPayload,
    *,
    now: datetime,
) -> OperatorDelivery:
    """Send one payload to every device of the operator and tidy the subscriptions."""
    if operator_id is None:
        return OperatorDelivery("no_operator")
    if notifier is None:
        return OperatorDelivery("push_disabled")
    try:
        targets = load_targets(db, operator_id)
    except DatabaseError:
        return OperatorDelivery("failed", retryable=True, push_failures={"DatabaseError": 1})
    if not targets:
        return OperatorDelivery("no_target")
    ok_ids: set[str] = set()
    gone_ids: set[str] = set()
    failures: Counter[str] = Counter()
    results: list[DeliveryResult] = []
    for target in targets:
        try:
            result = notifier.send_payload(target, payload)
        except Exception as exc:  # the interface promises not to raise; stay safe
            result = DeliveryResult(False, False, type(exc).__name__)
        results.append(result)
        if result.ok:
            ok_ids.add(target.subscription_id)
            continue
        failures[result.detail] += 1
        if result.permanent_failure:
            gone_ids.add(target.subscription_id)
    removed = 0
    if ok_ids or gone_ids:
        update = update_subscriptions(db, gone=gone_ids, ok=ok_ids, now=now)
        removed = update.removed
        if update.errors:
            failures["update"] += len(update.errors)
    failed = sum(1 for r in results if not r.ok)
    if ok_ids:
        return OperatorDelivery("sent", len(ok_ids), failed, removed, False, dict(failures))
    if all(r.permanent_failure for r in results):
        return OperatorDelivery("no_target", 0, failed, removed, False, dict(failures))
    retryable = any(not r.ok and not r.permanent_failure and r.retryable for r in results)
    return OperatorDelivery("failed", 0, failed, removed, retryable, dict(failures))


def delete_old_ingest_runs(db: SupabaseRest, *, now: datetime) -> int:
    """Remove runs older than the retention (they hold no personal data)."""
    require_aware(now)
    return db.delete(
        "ingest_runs", filters={"started_at": f"lt.{iso_utc(now - INGEST_RUNS_RETENTION)}"}
    )


# -- orchestration ---------------------------------------------------------------------------


def collect_usage_stats(
    db: SupabaseRest, *, now: datetime, with_history: bool
) -> tuple[UsageStats, list[str]]:
    """Gather what can be read. A source that fails leaves its fields unknown and adds an error."""
    require_aware(now)
    errors: list[str] = []
    fields: dict[str, Any] = {}
    try:
        om = read_open_meteo_usage(db, now=now)
        fields.update(
            open_meteo_today=om.today, open_meteo_max_day=om.max_day, open_meteo_month=om.month
        )
    except DatabaseError as exc:
        errors.append(f"api_usage: {db_error_summary(exc)}")
    try:
        usage = read_db_usage(db)
        fields.update(database_bytes=usage.database_bytes, table_rows=usage.table_rows)
    except DatabaseError as exc:
        errors.append(f"db_usage: {db_error_summary(exc)}")
    except ValueError:
        errors.append("db_usage: unexpected response")
    if with_history:
        try:
            history = read_run_history(db, now=now)
            fields.update(
                runs_ok=history.ok,
                runs_partial=history.partial,
                runs_failed=history.failed,
                step_issues=history.step_issues,
                push_sent=history.push_sent,
                push_failed=history.push_failed,
            )
        except DatabaseError as exc:
            errors.append(f"ingest_runs: {db_error_summary(exc)}")
    return UsageStats(now=now, **fields), errors


def usage_stats_json(stats: UsageStats) -> dict[str, Any]:
    return {
        "now": iso_utc(stats.now),
        "open_meteo_today": stats.open_meteo_today,
        "open_meteo_max_day": stats.open_meteo_max_day,
        "open_meteo_month": stats.open_meteo_month,
        "database_bytes": stats.database_bytes,
        "table_rows": dict(stats.table_rows),
        "runs_ok": stats.runs_ok,
        "runs_partial": stats.runs_partial,
        "runs_failed": stats.runs_failed,
        "step_issues": dict(stats.step_issues),
        "push_sent": stats.push_sent,
        "push_failed": stats.push_failed,
    }


def _delivery_notes(delivery: OperatorDelivery) -> list[str]:
    match delivery.status:
        case "no_operator":
            return [NOTE_NO_OPERATOR]
        case "invalid_operator":
            return [NOTE_INVALID_OPERATOR]
        case "push_disabled":
            return [NOTE_PUSH_DISABLED]
        case "no_target":
            return [NOTE_NO_TARGET]
        case "failed":
            note = (
                f"usage push failed on all {delivery.failed} device(s); "
                "see push_failures in ingest_runs"
            )
            return [note + ("; retried next run" if delivery.retryable else "")]
    return []


def run_usage_report(
    db: SupabaseRest,
    *,
    now: datetime,
    operator_user_id: str | None,
    notifier_factory: Callable[[], Notifier | None],
) -> UsageReportResult:
    """Collect usage, decide whether a push is due, send it and clean up. See the blueprint."""
    require_aware(now)
    stats, errors = collect_usage_stats(db, now=now, with_history=False)
    warnings = usage_warnings(stats)
    notes: list[str] = []

    def send(payload: PushPayload) -> OperatorDelivery:
        try:
            operator = resolve_operator(operator_user_id)
        except ValueError:
            delivery = OperatorDelivery("invalid_operator")
        else:
            notifier: Notifier | None = None
            if operator is not None:
                try:
                    notifier = notifier_factory()
                except ValueError:
                    notes.append(NOTE_PUSH_CONFIG)
                    logger.warning(NOTE_PUSH_CONFIG)
            delivery = deliver_operator_push(db, notifier, operator, payload, now=now)
        for note in _delivery_notes(delivery):
            notes.append(note)
            logger.warning(note)
        return delivery

    report_due = False
    if report_due_time(now):
        try:
            earlier = earlier_usage_counts(db, since=week_start(now), now=now)
            report_due = not any(c.get("report_done") is True for c in earlier)
        except DatabaseError as exc:
            errors.append(f"ingest_runs: {db_error_summary(exc)}")

    report: str | None = None
    report_done = warning_notified = False
    delivery: OperatorDelivery | None = None
    runs_deleted = 0

    if report_due:
        try:
            history = read_run_history(db, now=now)
            stats = replace(
                stats,
                runs_ok=history.ok,
                runs_partial=history.partial,
                runs_failed=history.failed,
                step_issues=history.step_issues,
                push_sent=history.push_sent,
                push_failed=history.push_failed,
            )
        except DatabaseError as exc:
            errors.append(f"ingest_runs: {db_error_summary(exc)}")
        report = build_usage_report(stats)
        text = usage_push_text(stats)
        payload = PushPayload(**text.model_dump(), url=OPERATOR_PUSH_URL, tag=REPORT_TAG)
        delivery = send(payload)
        report_done = not (delivery.status == "failed" and delivery.retryable)
        warning_notified = bool(warnings) and report_done
        try:
            runs_deleted = delete_old_ingest_runs(db, now=now)
        except DatabaseError as exc:
            errors.append(f"ingest_runs: {db_error_summary(exc)}")
    elif warnings and in_operator_window(now):
        try:
            earlier = earlier_usage_counts(db, since=local_day_start(now), now=now)
        except DatabaseError as exc:
            errors.append(f"ingest_runs: {db_error_summary(exc)}")
        else:
            if not any(c.get("warning_notified") is True for c in earlier):
                text = warning_push_text(warnings)
                payload = PushPayload(**text.model_dump(), url=OPERATOR_PUSH_URL, tag=WARNING_TAG)
                delivery = send(payload)
                warning_notified = not (delivery.status == "failed" and delivery.retryable)

    return UsageReportResult(
        stats=stats,
        warnings=tuple(warnings),
        report_due=report_due,
        report=report,
        report_done=report_done,
        warning_notified=warning_notified,
        delivery=delivery,
        runs_deleted=runs_deleted,
        errors=tuple(errors),
        notes=tuple(notes),
    )


def run_usage_show_cli(*, echo: Callable[[str], None]) -> int:
    """`shakka usage show`: print the report. Reads only; sends and writes nothing."""
    try:
        settings = get_settings()
    except ValidationError:
        echo("usage show: configuration incomplete; run shakka doctor")
        return 1
    db = runtime.open_db(settings)
    try:
        stats, errors = collect_usage_stats(db, now=runtime.utcnow(), with_history=True)
    finally:
        db.close()
    for line in build_usage_report(stats).split("\n"):
        echo(line)
    for error in errors:
        echo(f"error   {error}")
    return 1 if errors else 0
