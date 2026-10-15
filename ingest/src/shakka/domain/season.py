"""Season closures in local time (WP-02 A4). Pure."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from shakka.domain.defaults import LOCAL_TZ
from shakka.domain.spot import SeasonClosure


def _md(value: str) -> tuple[int, int]:
    return int(value[:2]), int(value[3:])


def in_period(start: str, end: str, day: date) -> bool:
    """Inclusive MM-DD period, compared as (month, day) tuples; start > end wraps the year."""
    s, e, md = _md(start), _md(end), (day.month, day.day)
    if s <= e:
        return s <= md <= e
    return md >= s or md <= e


def closure_applies(closure: SeasonClosure, valid_at: datetime) -> bool:
    """True if the hour [valid_at, valid_at + 1h) falls in the closure (see blueprint,
    Ontwerp/Seizoen). ValueError if valid_at is naive."""
    if valid_at.tzinfo is None or valid_at.utcoffset() is None:
        raise ValueError("valid_at must be timezone-aware")
    t = valid_at.astimezone(UTC)
    day = t.astimezone(LOCAL_TZ).date()
    if not in_period(closure.start, closure.end, day):
        return False
    if closure.from_time is None or closure.to_time is None:
        return True
    ws = datetime.combine(day, closure.from_time, tzinfo=LOCAL_TZ).astimezone(UTC)
    we = datetime.combine(day, closure.to_time, tzinfo=LOCAL_TZ).astimezone(UTC)
    return t < we and ws < t + timedelta(hours=1)


def is_season_closed(closures: Sequence[SeasonClosure], valid_at: datetime) -> bool:
    """any(closure_applies(c, valid_at) for c in closures)."""
    return any(closure_applies(c, valid_at) for c in closures)
