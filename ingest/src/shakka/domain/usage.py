"""Usage report for the operator (WP-22). Pure: statistics in, warnings and texts out.

Dutch texts, because they go to the operator's phone. Limits are the real free-tier limits;
the warning thresholds sit below them. `now` is always passed in.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Final

from shakka.domain.defaults import LOCAL_TZ
from shakka.domain.push import PUSH_BODY_MAX, PushText, shorten_words

OPEN_METEO_DAILY_LIMIT: Final = 10_000
OPEN_METEO_MONTHLY_LIMIT: Final = 300_000
OPEN_METEO_WARN_FRACTION: Final = 0.7
DATABASE_LIMIT_MB: Final = 500
DATABASE_WARN_MB: Final = 300
BYTES_PER_MB: Final = 1024 * 1024
REPORT_DAYS: Final = 7
REPORT_WEEKDAY: Final = 0  # Monday (date.weekday())
OPERATOR_PUSH_FROM: Final = time(8, 0)
OPERATOR_PUSH_UNTIL: Final = time(22, 0)
REPORT_TITLE: Final = "Shakka weekrapport"
REPORT_TITLE_WARN: Final = "Shakka weekrapport: let op"
WARNING_TITLE: Final = "Shakka: gebruik boven drempel"
UNKNOWN: Final = "onbekend"

_DAILY_WARN_AT: Final = round(OPEN_METEO_DAILY_LIMIT * OPEN_METEO_WARN_FRACTION)
_MONTHLY_WARN_AT: Final = round(OPEN_METEO_MONTHLY_LIMIT * OPEN_METEO_WARN_FRACTION)


def _check_number(name: str, value: object, *, integer: bool) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int if integer else int | float):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and not negative")


@dataclass(frozen=True, slots=True)
class UsageStats:
    now: datetime  # aware; end of the report period
    open_meteo_today: float | None = None  # UTC day of now, all open_meteo_* sources
    open_meteo_max_day: float | None = None  # highest UTC day of the last 7 (incl. today)
    open_meteo_month: float | None = None  # UTC month of now
    database_bytes: int | None = None
    table_rows: Mapping[str, int] = field(default_factory=dict)  # {} = unknown
    runs_ok: int | None = None  # finished runs in [now - 7 d, now)
    runs_partial: int | None = None
    runs_failed: int | None = None
    step_issues: Mapping[str, int] = field(default_factory=dict)  # step -> runs not ok
    push_sent: int | None = None  # sum of alerts.counts.sent in 7 days
    push_failed: int | None = None
    rws_requests_7d: int | None = (
        None  # sum of api_usage.requests, source rws, UTC days [today-6, today]
    )

    def __post_init__(self) -> None:
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        for name in ("open_meteo_today", "open_meteo_max_day", "open_meteo_month"):
            _check_number(name, getattr(self, name), integer=False)
        for name in (
            "database_bytes",
            "runs_ok",
            "runs_partial",
            "runs_failed",
            "push_sent",
            "push_failed",
            "rws_requests_7d",
        ):
            _check_number(name, getattr(self, name), integer=True)
        runs = (self.runs_ok, self.runs_partial, self.runs_failed)
        if any(r is None for r in runs) and not all(r is None for r in runs):
            raise ValueError("runs_ok, runs_partial and runs_failed are set together")
        for mapping in (self.table_rows, self.step_issues):
            for key, value in mapping.items():
                _check_number(str(key), value, integer=True)
                if value is None:
                    raise ValueError("counts must be integers")

    @property
    def users(self) -> int | None:
        return self.table_rows.get("profiles")

    @property
    def subscriptions(self) -> int | None:
        return self.table_rows.get("push_subscriptions")

    @property
    def runs_total(self) -> int | None:
        if self.runs_ok is None or self.runs_partial is None or self.runs_failed is None:
            return None
        return self.runs_ok + self.runs_partial + self.runs_failed


def _n(x: float) -> str:
    return f"{int(math.floor(x + 0.5)):,}".replace(",", ".")


def _mb(b: int) -> int:
    return math.ceil(b / BYTES_PER_MB)


def _pct(ok: int, total: int) -> int:
    return int(math.floor(100 * ok / total + 0.5))


def usage_warnings(stats: UsageStats) -> list[str]:
    warnings: list[str] = []
    if stats.database_bytes is not None and stats.database_bytes > DATABASE_WARN_MB * BYTES_PER_MB:
        warnings.append(f"Database {_mb(stats.database_bytes)} MB, boven {DATABASE_WARN_MB} MB")
    today, month = stats.open_meteo_today, stats.open_meteo_month
    if today is not None and today > _DAILY_WARN_AT:
        warnings.append(f"Open-Meteo vandaag {_n(today)} calls, boven {_n(_DAILY_WARN_AT)}")
    if month is not None and month > _MONTHLY_WARN_AT:
        warnings.append(f"Open-Meteo deze maand {_n(month)} calls, boven {_n(_MONTHLY_WARN_AT)}")
    return warnings


def build_usage_report(stats: UsageStats) -> str:
    local = stats.now.astimezone(LOCAL_TZ)
    lines = [f"Shakka gebruiksrapport tot {local:%Y-%m-%d %H:%M} (Europe/Amsterdam)"]

    warnings = usage_warnings(stats)
    if warnings:
        lines.append("Waarschuwingen:")
        lines.extend(f"- {w}" for w in warnings)
    else:
        lines.append("Waarschuwingen: geen")

    today, max_day, month = stats.open_meteo_today, stats.open_meteo_max_day, stats.open_meteo_month
    if today is None or max_day is None or month is None:
        lines.append(f"Open-Meteo: {UNKNOWN}")
    else:
        lines.append(
            f"Open-Meteo: vandaag {_n(today)} calls, hoogste dag ({REPORT_DAYS} dagen) "
            f"{_n(max_day)}, limiet {_n(OPEN_METEO_DAILY_LIMIT)} per dag; deze maand "
            f"{_n(month)}, limiet {_n(OPEN_METEO_MONTHLY_LIMIT)}"
        )

    rws = stats.rws_requests_7d
    if rws is None:
        lines.append(f"Rijkswaterstaat ({REPORT_DAYS} dagen): {UNKNOWN}")
    else:
        lines.append(f"Rijkswaterstaat ({REPORT_DAYS} dagen): {_n(rws)} requests")

    if stats.database_bytes is None:
        lines.append(f"Database: {UNKNOWN}")
    else:
        lines.append(f"Database: {_mb(stats.database_bytes)} MB van {DATABASE_LIMIT_MB} MB")

    if stats.table_rows:
        rows = ", ".join(f"{t} {_n(c)}" for t, c in sorted(stats.table_rows.items()))
        lines.append(f"Rijen: {rows}")
    else:
        lines.append(f"Rijen: {UNKNOWN}")

    total = stats.runs_total
    if total is None:
        lines.append(f"Runs ({REPORT_DAYS} dagen): {UNKNOWN}")
    elif total == 0:
        lines.append(f"Runs ({REPORT_DAYS} dagen): 0")
    else:
        assert stats.runs_ok is not None
        assert stats.runs_partial is not None and stats.runs_failed is not None
        lines.append(
            f"Runs ({REPORT_DAYS} dagen): {_n(total)}, waarvan {_n(stats.runs_ok)} ok, "
            f"{_n(stats.runs_partial)} partial, {_n(stats.runs_failed)} failed "
            f"({_pct(stats.runs_ok, total)}% ok)"
        )

    if total is None:
        lines.append(f"Stappen niet ok ({REPORT_DAYS} dagen): {UNKNOWN}")
    elif stats.step_issues:
        ordered = sorted(stats.step_issues.items(), key=lambda item: (-item[1], item[0]))
        steps = ", ".join(f"{name} {count}" for name, count in ordered)
        lines.append(f"Stappen niet ok ({REPORT_DAYS} dagen): {steps}")
    else:
        lines.append(f"Stappen niet ok ({REPORT_DAYS} dagen): geen")

    if stats.push_sent is None or stats.push_failed is None:
        lines.append(f"Push ({REPORT_DAYS} dagen): {UNKNOWN}")
    else:
        lines.append(
            f"Push ({REPORT_DAYS} dagen): {_n(stats.push_sent)} verstuurd, "
            f"{_n(stats.push_failed)} mislukt"
        )

    users = UNKNOWN if stats.users is None else _n(stats.users)
    subscriptions = UNKNOWN if stats.subscriptions is None else _n(stats.subscriptions)
    lines.append(f"Gebruikers: {users}, push-abonnementen: {subscriptions}")
    return "\n".join(lines)


def _fit_lines(lines: Sequence[str]) -> str:
    """Whole lines from the start while they fit; a first line that is too long is cut."""
    taken: list[str] = []
    for line in lines:
        if len("\n".join([*taken, line])) > PUSH_BODY_MAX:
            break
        taken.append(line)
    return "\n".join(taken) if taken else shorten_words(lines[0], PUSH_BODY_MAX)


def usage_push_text(stats: UsageStats) -> PushText:
    warnings = usage_warnings(stats)
    total = stats.runs_total
    pct = "?" if not total or stats.runs_ok is None else str(_pct(stats.runs_ok, total))
    db = "?" if stats.database_bytes is None else str(_mb(stats.database_bytes))
    peak = "?" if stats.open_meteo_max_day is None else _n(stats.open_meteo_max_day)
    users = "?" if stats.users is None else str(stats.users)
    subscriptions = "?" if stats.subscriptions is None else str(stats.subscriptions)
    lines = [
        *warnings,
        f"Runs {pct}% ok · DB {db} MB · Open-Meteo max {peak}/dag",
        f"{users} gebruikers, {subscriptions} abonnementen",
    ]
    title = REPORT_TITLE_WARN if warnings else REPORT_TITLE
    return PushText(title=title, body=_fit_lines(lines))


def warning_push_text(warnings: Sequence[str]) -> PushText:
    if not warnings:
        raise ValueError("no warnings to report")
    return PushText(title=WARNING_TITLE, body=_fit_lines(list(warnings)))


# -- local time ------------------------------------------------------------------------------


def _local_midnight_utc(now: datetime, days_back: int) -> datetime:
    local = now.astimezone(LOCAL_TZ)
    day = local.date() - timedelta(days=days_back)
    return datetime(day.year, day.month, day.day, tzinfo=LOCAL_TZ).astimezone(UTC)


def local_day_start(now: datetime) -> datetime:
    """00:00 Europe/Amsterdam of now's local date, as UTC."""
    return _local_midnight_utc(now, 0)


def week_start(now: datetime) -> datetime:
    """Monday 00:00 Europe/Amsterdam of now's local week, as UTC."""
    return _local_midnight_utc(now, now.astimezone(LOCAL_TZ).weekday())


def in_operator_window(now: datetime) -> bool:
    return OPERATOR_PUSH_FROM <= now.astimezone(LOCAL_TZ).time() < OPERATOR_PUSH_UNTIL


def report_due_time(now: datetime) -> bool:
    local = now.astimezone(LOCAL_TZ)
    return local.weekday() == REPORT_WEEKDAY and in_operator_window(now)
