"""Tide ingest: fetch astronomical extremes per used station and store them."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final

from shakka.db import SupabaseRest, in_filter, iso_utc
from shakka.domain.tide import TideExtreme
from shakka.rws.tides import STATION_CODE_RE, fetch_tide_extremes

logger = logging.getLogger(__name__)

TIDE_REFRESH_AFTER: Final = timedelta(hours=20)
TIDE_WINDOW_BEFORE: Final = timedelta(days=1)
TIDE_WINDOW_AFTER: Final = timedelta(days=8)
TIDE_RETENTION: Final = timedelta(hours=48)
MAX_ERROR_TEXT: Final = 200

TideFetcher = Callable[[str, datetime, datetime], Sequence[TideExtreme]]


@dataclass(frozen=True, slots=True)
class TideIngestResult:
    stations: int  # stations fetched and stored successfully in this run
    rows: int  # rows upserted
    skipped: list[str]  # fresh (< 20h), sorted
    failed: list[str]  # sorted
    errors: list[str] = field(default_factory=list)  # "<station>: <ExcType>: <msg[:200]>"
    deleted: int = 0  # rows removed by the 48h cleanup


def _require_aware(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")


def delete_old_tides(db: SupabaseRest, *, now: datetime) -> int:
    """Remove extremes older than TIDE_RETENTION; returns the number of rows removed."""
    _require_aware(now)
    return db.delete("tide_extremes", filters={"at": f"lt.{iso_utc(now - TIDE_RETENTION)}"})


def _dedupe(extremes: Sequence[TideExtreme], station: str) -> list[TideExtreme]:
    by_at: dict[datetime, TideExtreme] = {}
    for e in extremes:
        if e.station != station:
            raise ValueError("fetch returned another station")
        known = by_at.get(e.at)
        if known is not None and (known.level_cm, known.kind) != (e.level_cm, e.kind):
            raise ValueError("fetch returned conflicting duplicates")
        by_at[e.at] = e
    if not by_at:
        raise ValueError("fetch returned no extremes")
    return [by_at[at] for at in sorted(by_at)]


def run_tide_ingest(
    db: SupabaseRest,
    *,
    now: datetime,
    force: bool = False,
    fetch: TideFetcher = fetch_tide_extremes,
) -> TideIngestResult:
    """Fetch tide extremes for every station used by a spot (20-hour freshness rule)."""
    _require_aware(now)
    spots = db.select("spots", columns="id,rws_station")
    wanted = sorted(
        {
            str(r["rws_station"]).strip()
            for r in spots
            if r.get("rws_station") is not None and str(r["rws_station"]).strip()
        }
    )
    failed: list[str] = []
    errors: list[str] = []
    for code in wanted:
        if not STATION_CODE_RE.fullmatch(code):
            failed.append(code)
            text = f"{code[:70]!r}: ValueError: invalid station code"
            errors.append(text)
            logger.warning("tides: %s", text)
    stations = [c for c in wanted if STATION_CODE_RE.fullmatch(c)]

    fresh: set[str] = set()
    if stations and not force:
        recent = db.select(
            "tide_extremes",
            columns="station",
            filters={
                "station": in_filter(stations),
                "fetched_at": f"gt.{iso_utc(now - TIDE_REFRESH_AFTER)}",
            },
        )
        fresh = {r["station"] for r in recent}
    skipped = sorted(fresh.intersection(stations))

    stations_ok = 0
    rows = 0
    start, end = now - TIDE_WINDOW_BEFORE, now + TIDE_WINDOW_AFTER
    for station in stations:
        if station in fresh:
            continue
        try:
            deduped = _dedupe(list(fetch(station, start, end)), station)
            payload = [e.to_row() | {"fetched_at": now} for e in deduped]
            db.upsert("tide_extremes", payload, on_conflict="station,at")
            db.delete(
                "tide_extremes",
                filters={
                    "station": f"eq.{station}",
                    "at": [f"gte.{iso_utc(start)}", f"lte.{iso_utc(end)}"],
                    "fetched_at": f"lt.{iso_utc(now)}",
                },
            )
            stations_ok += 1
            rows += len(payload)
        except Exception as exc:
            text = f"{station}: {type(exc).__name__}: {str(exc)[:MAX_ERROR_TEXT]}"
            failed.append(station)
            errors.append(text)
            logger.warning("tides: %s", text)

    deleted = delete_old_tides(db, now=now)
    logger.info(
        "tides: fetched %d station(s), %d row(s), skipped %d, failed %d, deleted %d",
        stations_ok,
        rows,
        len(skipped),
        len(failed),
        deleted,
    )
    return TideIngestResult(stations_ok, rows, skipped, sorted(failed), errors, deleted)
