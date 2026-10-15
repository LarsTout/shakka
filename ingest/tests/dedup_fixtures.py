"""Helpers for the dedup tests (WP-08)."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from alert_fixtures import SPOT_ID, H, hour, rule, utc
from shakka.domain.alerts import Window, find_windows
from shakka.domain.consensus import Confidence
from shakka.domain.dedup import (
    AlertEventKind,
    AlertStateEntry,
    AlertStatus,
    WindowSnapshot,
    snapshot_window,
)
from shakka.domain.direction import DirClass
from shakka.domain.evaluation import HourEvaluation

__all__ = [
    "H",
    "NOW",
    "SPOT_ID",
    "entry",
    "go_hour",
    "make_window",
    "persist",
    "utc",
    "windows_from_pattern",
]

NOW = utc(2026, 7, 15, 6)


def go_hour(
    at: datetime,
    *,
    wind: float | None = 20.0,
    gust: float | None = None,
    dir_deg: int | None = 270,
    dir_class: DirClass | None = DirClass.ONSHORE,
    confidence: Confidence | None = Confidence.HIGH,
    spot_id: str = SPOT_ID,
) -> HourEvaluation:
    """Valid go hour via the normal constructor (verdict go, reasons ())."""
    return HourEvaluation(
        spot_id=spot_id,
        valid_at=at,
        verdict="go",
        reasons=(),
        wind_kn=wind,
        gust_kn=gust,
        dir_deg=dir_deg,
        dir_class=dir_class,
        confidence=confidence,
        tide_level_cm=None,
    )


def make_window(
    start: datetime,
    n: int,
    *,
    winds: Sequence[float] | None = None,
    gusts: Sequence[float | None] | None = None,
    dirs: Sequence[int] | None = None,
    classes: Sequence[DirClass] | None = None,
    confidences: Sequence[Confidence] | None = None,
    spot_id: str = SPOT_ID,
) -> Window:
    """Window of n go hours from start; per-hour lists override the go_hour defaults."""
    hours = []
    for i in range(n):
        kw: dict = {"spot_id": spot_id}
        if winds is not None:
            kw["wind"] = winds[i]
        if gusts is not None:
            kw["gust"] = gusts[i]
        if dirs is not None:
            kw["dir_deg"] = dirs[i]
        if classes is not None:
            kw["dir_class"] = classes[i]
        if confidences is not None:
            kw["confidence"] = confidences[i]
        hours.append(go_hour(start + i * H, **kw))
    return Window(spot_id=spot_id, start=start, end=start + n * H, hours=tuple(hours))


def entry(
    start: datetime,
    end: datetime,
    *,
    status: AlertStatus = "active",
    snapshot: WindowSnapshot | None = None,
    id: str | None = None,
    last_event: AlertEventKind | None = AlertEventKind.NEW,
    spot_id: str = SPOT_ID,
    last_notified_at: datetime | None = None,
) -> AlertStateEntry:
    """snapshot defaults to snapshot_window(make_window(start, hours(end - start)))."""
    if snapshot is None:
        n = int((end - start) / timedelta(hours=1))
        snapshot = snapshot_window(make_window(start, n, spot_id=spot_id))
    return AlertStateEntry(
        id=id,
        spot_id=spot_id,
        window_start=start,
        window_end=end,
        status=status,
        snapshot=snapshot,
        last_event=last_event,
        last_notified_at=last_notified_at,
    )


def persist(state: list[AlertStateEntry], prefix: str = "id") -> list[AlertStateEntry]:
    """Give entries with id None the id f'{prefix}-{index}' (simulates the database insert)."""
    return [
        e if e.id is not None else e.model_copy(update={"id": f"{prefix}-{i}"})
        for i, e in enumerate(state)
    ]


def windows_from_pattern(
    day_start: datetime, pattern: str, *, now: datetime, min_go_hours: int = 1
) -> list[Window]:
    """pattern like 'GG.GGG' (G = go hour, . = marginal) from day_start; uses
    alert_fixtures.hour and find_windows(..., rule(min_go_hours=...), now=now)."""
    evaluations = [
        hour(day_start + i * H, verdict="go" if ch == "G" else "marginal")
        for i, ch in enumerate(pattern)
    ]
    return find_windows(evaluations, rule(min_go_hours=min_go_hours), now=now)
