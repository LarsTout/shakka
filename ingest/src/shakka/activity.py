"""Warn before GitHub disables the hourly schedule (60 days without repository activity)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

import shakka.jobs.runtime as runtime
from shakka.logsetup import github_annotation

WARN_AFTER_DAYS: Final = 45
FAIL_AFTER_DAYS: Final = 53
DISABLE_AFTER_DAYS: Final = 60  # GitHub's rule, for messages only

ActivityLevel = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class ActivityCheck:
    level: ActivityLevel
    days: int


def parse_commit_date(text: str) -> datetime | None:
    """Aware UTC datetime, or None for empty, invalid or timezone-less input."""
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def check_activity(last_commit_at: datetime, *, now: datetime) -> ActivityCheck:
    for value in (last_commit_at, now):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetimes must be timezone-aware")
    days = max(0, (now - last_commit_at) // timedelta(days=1))
    level: ActivityLevel = "ok"
    if days >= FAIL_AFTER_DAYS:
        level = "fail"
    elif days >= WARN_AFTER_DAYS:
        level = "warn"
    return ActivityCheck(level, days)


def run_check_activity_cli(last_commit_at: str, *, echo: Callable[[str], None]) -> int:
    last = parse_commit_date(last_commit_at)
    if last is None:
        echo(
            github_annotation(
                "warning",
                "Could not determine the date of the last commit; "
                "repository activity was not checked.",
            )
        )
        return 0
    check = check_activity(last, now=runtime.utcnow())
    if check.level == "ok":
        echo(f"activity: last commit on the default branch {check.days} day(s) ago; ok")
        return 0
    message = (
        f"No commits on the default branch for {check.days} days. GitHub disables the hourly "
        f"schedule after {DISABLE_AFTER_DAYS} days without activity; merge a commit into "
        "develop (docs/RUNBOOK.md, section 13)."
    )
    if check.level == "warn":
        echo(github_annotation("warning", message))
        return 0
    echo(github_annotation("error", message))
    return 1
