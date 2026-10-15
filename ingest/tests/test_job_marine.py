"""Tests for the marine (wave) ingest job (WP-12: AC-2 and the job-level edge cases)."""

import functools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from fakes import FakeSupabase
from openmeteo_payloads import make_marine_payload
from shakka.budget import SOURCE_OPEN_METEO_FORECAST, SOURCE_OPEN_METEO_MARINE, BudgetGuard
from shakka.db import DatabaseError
from shakka.domain.forecast import SpotLocation
from shakka.domain.marine import MarineHour
from shakka.jobs.marine import delete_old_marine, run_marine_ingest
from shakka.openmeteo.marine import fetch_marine, parse_marine_response

NOW = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
T0 = datetime(2026, 10, 14, 0, tzinfo=UTC)
FIXTURE = Path(__file__).parent / "fixtures" / "openmeteo" / "marine_3loc_2models.json"
NO_SLEEP = functools.partial(fetch_marine, sleep=lambda s: None)


class Recorder:
    """MockTransport handler that records requests and answers with synthetic payloads."""

    def __init__(self, responses: list[httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._responses = list(responses or [])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._responses:
            return self._responses.pop(0)
        count = len(request.url.params["latitude"].split(","))
        return httpx.Response(200, json=make_marine_payload(count, start=T0))

    @property
    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def spot_rows(n: int, *, offset: int = 0) -> list[dict[str, Any]]:
    return [
        {"id": f"s{i:03d}", "name": f"Spot {i}", "lat": 50 + i / 1000, "lon": 4 + i / 1000}
        for i in range(offset, offset + n)
    ]


def make_db(spots: list[dict[str, Any]] | None = None) -> FakeSupabase:
    db = FakeSupabase()
    db.seed("spots", spots if spots is not None else spot_rows(1))
    return db


def usage(db: FakeSupabase) -> list[dict[str, Any]]:
    return db.rows("api_usage")


def seed_usage(db: FakeSupabase, day: str, calls: float) -> None:
    db.seed(
        "api_usage",
        [{"day": day, "source": SOURCE_OPEN_METEO_FORECAST, "calls": calls, "requests": 1}],
    )


def run(db: FakeSupabase, rec: Recorder, **kwargs: Any):
    kwargs.setdefault("fetch", NO_SLEEP)
    return run_marine_ingest(db, rec.client, BudgetGuard(db), now=NOW, **kwargs)  # type: ignore[arg-type]


# -- basic runs ---------------------------------------------------------------------------------


def test_job_records_usage_under_marine_source() -> None:
    db, rec = make_db(), Recorder()
    result = run(db, rec)
    assert result.errors == [] and result.skipped_budget is False
    assert result.spots == 1 and result.rows == 3
    assert result.calls == 1.0
    rows = usage(db)
    assert len(rows) == 1
    assert rows[0]["day"] == "2026-10-14" and rows[0]["source"] == SOURCE_OPEN_METEO_MARINE
    assert rows[0]["calls"] == 1.0 and rows[0]["requests"] == 1
    assert not [r for r in rows if r["source"] == SOURCE_OPEN_METEO_FORECAST]
    assert len(rec.requests) == 1


def test_job_upsert_on_conflict() -> None:
    db, rec = make_db(), Recorder()
    run(db, rec)
    assert ("marine_hours", "spot_id,valid_at") in db.upserts
    stored = db.rows("marine_hours")
    assert len(stored) == 3
    for row in stored:
        assert set(row) == {
            "spot_id",
            "valid_at",
            "wave_height_m",
            "wave_period_s",
            "wave_dir_deg",
            "fetched_at",
        }
        assert datetime.fromisoformat(row["fetched_at"]) == NOW


def test_job_is_idempotent() -> None:
    db = make_db()
    run(db, Recorder())
    run(db, Recorder())
    assert len(db.rows("marine_hours")) == 3


def test_job_skips_spots_without_coordinates() -> None:
    spots = spot_rows(3)
    spots[1]["lat"] = spots[1]["lon"] = None
    db, rec = make_db(spots), Recorder()
    result = run(db, rec)
    assert result.spots == 2
    assert len(rec.requests[0].url.params["latitude"].split(",")) == 2


def test_job_no_spots_no_requests() -> None:
    db, rec = make_db([]), Recorder()
    result = run(db, rec)
    assert (result.spots, result.rows, result.calls) == (0, 0, 0.0)
    assert rec.requests == [] and usage(db) == []
    assert ("delete", "marine_hours") in db.writes


def test_job_chunks_by_50() -> None:
    db, rec = make_db(spot_rows(51)), Recorder()
    result = run(db, rec)
    sizes = [len(r.url.params["latitude"].split(",")) for r in rec.requests]
    assert sizes == [50, 1]
    assert result.calls == pytest.approx(51.0)
    assert usage(db)[0]["requests"] == 2


def test_job_rejects_naive_now() -> None:
    db = make_db()
    naive = datetime(2026, 10, 14, 12)  # noqa: DTZ001
    with pytest.raises(ValueError):
        run_marine_ingest(db, Recorder().client, BudgetGuard(db), now=naive)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        delete_old_marine(db, now=naive)  # type: ignore[arg-type]


def test_job_fixture_end_to_end() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spots = [
        {"id": "fixture-a", "name": "A", "lat": 52.47, "lon": 4.57},
        {"id": "fixture-b", "name": "B", "lat": 52.75, "lon": 5.30},
        {"id": "fixture-c", "name": "C", "lat": 52.09, "lon": 5.12},
    ]
    db = make_db(spots)
    # Rows far in the past would be cleaned up; the fixture was recorded on a fixed date.
    first = datetime.fromtimestamp(raw[0]["hourly"]["time"][0], tz=UTC)
    now = first + timedelta(hours=1)
    rec = Recorder([httpx.Response(200, json=raw)])
    result = run_marine_ingest(db, rec.client, BudgetGuard(db), now=now, fetch=NO_SLEEP)  # type: ignore[arg-type]
    locations = [SpotLocation(spot_id=s["id"], lat=s["lat"], lon=s["lon"]) for s in spots]
    expected = parse_marine_response(raw, locations)
    assert result.rows == len(expected) == len(db.rows("marine_hours"))
    assert not [r for r in db.rows("marine_hours") if r["spot_id"] == "fixture-c"]
    assert result.errors == []


# -- budget -------------------------------------------------------------------------------------


def test_job_budget_exceeded_no_request() -> None:
    db, rec = make_db(), Recorder()
    seed_usage(db, "2026-10-14", 7999.5)
    before = usage(db)
    result = run(db, rec)
    assert rec.requests == [] and result.skipped_budget is True and result.rows == 0
    assert usage(db) == before
    assert db.rows("marine_hours") == []


def test_job_budget_boundary_inclusive() -> None:
    db, rec = make_db(), Recorder()
    seed_usage(db, "2026-10-14", 7999.0)
    result = run(db, rec)
    assert len(rec.requests) == 1 and result.skipped_budget is False


def test_job_monthly_budget_exceeded_no_request() -> None:
    db, rec = make_db(), Recorder()
    seed_usage(db, "2026-10-01", 239999.5)
    before = usage(db)
    result = run(db, rec)
    assert rec.requests == [] and result.skipped_budget is True
    assert usage(db) == before


def test_job_database_error_propagates() -> None:
    class BrokenUsage(FakeSupabase):
        def select(self, table: str, **kwargs: Any):
            if table == "api_usage":
                raise DatabaseError("select api_usage: HTTP 500")
            return super().select(table, **kwargs)

    db = BrokenUsage()
    db.seed("spots", spot_rows(1))
    rec = Recorder()
    with pytest.raises(DatabaseError):
        run(db, rec)
    assert rec.requests == []


# -- errors -------------------------------------------------------------------------------------


def test_job_fetch_error_books_weight() -> None:
    db = make_db()
    body = {"error": True, "reason": "bad request"}
    rec = Recorder([httpx.Response(400, json=body)])
    result = run(db, rec)
    assert result.errors == ["chunk 1/1: open-meteo marine: HTTP 400: bad request"]
    assert result.rows == 0
    assert ("marine_hours", "spot_id,valid_at") not in db.upserts
    rows = usage(db)
    assert rows[0]["source"] == SOURCE_OPEN_METEO_MARINE
    assert rows[0]["calls"] == 1.0 and rows[0]["requests"] == 1


def test_job_three_500_reports_error() -> None:
    sleeps: list[float] = []
    fetch = functools.partial(fetch_marine, sleep=sleeps.append)
    db = make_db()
    rec = Recorder([httpx.Response(500)] * 3)
    result = run(db, rec, fetch=fetch)
    assert result.errors == ["chunk 1/1: open-meteo marine: failed after 3 attempts: HTTP 500"]
    assert len(rec.requests) == 3
    assert sleeps == [1.0, 2.0]


def test_job_deduplicates_before_upsert() -> None:
    db = make_db()

    def fake_fetch(http: httpx.Client, locations, **kwargs: Any) -> list[MarineHour]:
        def hour(height: float) -> MarineHour:
            return MarineHour(
                spot_id="s000",
                valid_at=T0,
                wave_height_m=height,
                wave_period_s=None,
                wave_dir_deg=None,
            )

        return [hour(1.0), hour(1.5)]

    result = run(db, Recorder(), fetch=fake_fetch)
    stored = db.rows("marine_hours")
    assert result.rows == 1 and len(stored) == 1 and stored[0]["wave_height_m"] == 1.5


def test_job_calls_fetch_without_forecast_days() -> None:
    seen: list[dict[str, Any]] = []

    def fake_fetch(http: httpx.Client, locations, **kwargs: Any) -> list[MarineHour]:
        seen.append(kwargs)
        return []

    db = make_db()
    result = run(db, Recorder(), fetch=fake_fetch)
    assert seen == [{}] and result.rows == 0
    assert ("marine_hours", "spot_id,valid_at") not in db.upserts


# -- cleanup ------------------------------------------------------------------------------------


def seed_hours(db: FakeSupabase, offsets_h: list[int]) -> None:
    db.seed(
        "marine_hours",
        [
            {
                "spot_id": "s000",
                "valid_at": (NOW.replace(minute=0) + timedelta(hours=h)).isoformat(),
                "wave_height_m": 1.0,
                "wave_period_s": None,
                "wave_dir_deg": None,
                "fetched_at": NOW.isoformat(),
            }
            for h in offsets_h
        ],
    )


def test_delete_old_marine_only_older_than_48h() -> None:
    db = make_db()
    seed_hours(db, [-72, -49, -48, -47, 1])
    now = NOW.replace(minute=0)
    assert delete_old_marine(db, now=now) == 2
    assert len(db.rows("marine_hours")) == 3


def test_delete_old_marine_boundary() -> None:
    db = make_db()
    seed_hours(db, [-48])
    assert delete_old_marine(db, now=NOW.replace(minute=0)) == 0
    assert len(db.rows("marine_hours")) == 1


def test_job_runs_cleanup() -> None:
    db = make_db()
    seed_hours(db, [-100, -60])
    result = run(db, Recorder())
    assert result.deleted == 2
