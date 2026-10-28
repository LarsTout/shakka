"""Quiet hours: one daily period in Dutch local time without alerts (WP-30). Pure.

The period is half open, `[start, end)`, and runs past midnight when `start > end`. Only the
local wall-clock time counts, so around a daylight saving change nothing special happens: a
local time that does not exist (spring, 02:xx) is never inside the period; one that occurs
twice (autumn, 02:xx) is inside it both times.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Final

from shakka.domain.defaults import LOCAL_TZ

QUIET_COLUMNS: Final = ("quiet_from", "quiet_until")


@dataclass(frozen=True, slots=True)
class QuietHours:
    start: time  # naive local wall-clock time
    end: time

    def __post_init__(self) -> None:
        for value in (self.start, self.end):
            if not isinstance(value, time):
                raise ValueError("quiet hours: expected a time")
            if value.tzinfo is not None:
                raise ValueError("quiet hours: time must be naive")
        if self.start == self.end:
            raise ValueError("quiet hours: start equals end")


def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            raise ValueError("quiet hours: unreadable time") from None
    raise ValueError("quiet hours: unreadable time")


def quiet_hours_from_row(row: Mapping[str, Any]) -> QuietHours | None:
    """Both keys missing or None -> None. Exactly one None/missing -> ValueError.

    A value is a naive `datetime.time` or an ISO string 'HH:MM' / 'HH:MM:SS'; any other type,
    an unparsable string or a time with an offset gives ValueError.
    """
    start, end = row.get("quiet_from"), row.get("quiet_until")
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise ValueError("quiet hours: only one of the two is set")
    return QuietHours(_parse_time(start), _parse_time(end))


def in_quiet_hours(now: datetime, quiet: QuietHours | None) -> bool:
    """True if `now` falls in the quiet hours. ValueError if `now` is naive (checked first)."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if quiet is None:
        return False
    t = now.astimezone(LOCAL_TZ).time()
    if quiet.start < quiet.end:
        return quiet.start <= t < quiet.end
    return t >= quiet.start or t < quiet.end
