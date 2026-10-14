"""Tests for the forecast ingest job (WP-03: AC-4, AC-5 and AC-6 at job level)."""

import functools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from fakes import FakeSupabase
from openmeteo_payloads import make_forecast_payload
from shakka.budget import SOURCE_OPEN_METEO_FORECAST, BudgetGuard
from shakka.db import DatabaseError
from shakka.domain.forecast import ForecastHour, ModelKey, SpotLocation
from shakka.jobs.forecast import (
    delete_old_forecasts,
    plan_forecast_ingest,
    run_forecast_ingest,
)
from shakka.openmeteo.forecast import fetch_forecast, parse_forecast_response
from shakka.openmeteo.models import OPEN_METEO_MODELS

NOW = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
T0 = datetime(2026, 10, 14, 0, tzinfo=UTC)
FIXTURE = Path(__file__).parent / "fixtures" / "openmeteo" / "forecast_2loc_4models.json"
NO_SLEEP = functools.partial(fetch_forecast, sleep=lambda s: None)


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
        return httpx.Response(200, json=make_forecast_payload(count, start=T0))

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
    return run_forecast_ingest(db, rec.client, BudgetGuard(db), now=NOW, **kwargs)  # type: ignore[arg-type]


# -- basic runs --------------------------------------------------------------------------------


def test_job_records_usage_after_success() -> None:
    db, rec = make_db(), Recorder()
    result = run(db, rec)
    assert result.errors == [] and result.skipped_budget is False
    assert result.spots == 1 and result.rows == 3 * len(OPEN_METEO_MODELS)
    assert result.calls == 1.2
    rows = usage(db)
    assert len(rows) == 1
    assert rows[0]["day"] == "2026-10-14" and rows[0]["source"] == SOURCE_OPEN_METEO_FORECAST
    assert rows[0]["calls"] == 1.2 and rows[0]["requests"] == 1
    assert len(rec.requests) == 1


def test_job_upsert_on_conflict() -> None:
    db, rec = make_db(), Recorder()
    run(db, rec)
    assert ("forecast_hours", "spot_id,model,valid_at") in db.upserts
    stored = db.rows("forecast_hours")
    assert len(stored) == 12
    for row in stored:
        assert set(row) == {
            "spot_id",
            "model",
            "valid_at",
            "wind_kn",
            "gust_kn",
            "dir_deg",
            "fetched_at",
        }
        assert datetime.fromisoformat(row["fetched_at"]) == NOW


def test_job_is_idempotent() -> None:
    db = make_db()
    run(db, Recorder())
    run(db, Recorder())
    assert len(db.rows("forecast_hours")) == 12


def test_job_skips_spots_without_coordinates() -> None:
    spots = spot_rows(3)
    spots[1]["lat"] = spots[1]["lon"] = None
    db, rec = make_db(spots), Recorder()
    result = run(db, rec)
    assert result.spots == 2
    assert len(rec.requests[0].url.params["latitude"].split(",")) == 2
    plan = plan_forecast_ingest(db, BudgetGuard(db), now=NOW)  # type: ignore[arg-type]
    assert plan.without_coords == ["s001"] and plan.spots == 2


def test_job_no_spots_no_requests() -> None:
    db, rec = make_db([]), Recorder()
    result = run(db, rec)
    assert (result.spots, result.rows, result.calls) == (0, 0, 0.0)
    assert rec.requests == [] and usage(db) == []
    assert ("delete", "forecast_hours") in db.writes


def test_job_chunks_by_50() -> None:
    db, rec = make_db(spot_rows(120)), Recorder()
    result = run(db, rec)
    sizes = [len(r.url.params["latitude"].split(",")) for r in rec.requests]
    assert sizes == [50, 50, 20]
    assert rec.requests[1].url.params["latitude"].startswith("50.0500")
    assert result.spots == 120 and result.calls == pytest.approx(144.0)
    assert usage(db)[0]["requests"] == 3
    assert len(db.rows("forecast_hours")) == 120 * 12


def test_job_identical_coordinates() -> None:
    spots = spot_rows(2)
    spots[1]["lat"], spots[1]["lon"] = spots[0]["lat"], spots[0]["lon"]
    db = make_db(spots)
    result = run(db, Recorder())
    stored = db.rows("forecast_hours")
    assert result.rows == 24
    assert {r["spot_id"] for r in stored} == {"s000", "s001"}


def test_job_rejects_naive_now() -> None:
    db = make_db()
    naive = datetime(2026, 10, 14, 12)  # noqa: DTZ001
    with pytest.raises(ValueError):
        run_forecast_ingest(db, Recorder().client, BudgetGuard(db), now=naive)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        plan_forecast_ingest(db, BudgetGuard(db), now=naive)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        delete_old_forecasts(db, now=naive)  # type: ignore[arg-type]


def test_job_fixture_end_to_end() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spots = [
        {"id": "fixture-a", "name": "A", "lat": 52.47, "lon": 4.57},
        {"id": "fixture-b", "name": "B", "lat": 52.10, "lon": 4.27},
    ]
    db = make_db(spots)
    rec = Recorder([httpx.Response(200, json=raw)])
    result = run(db, rec)
    expected = parse_forecast_response(
        raw,
        [
            SpotLocation(spot_id="fixture-a", lat=52.47, lon=4.57),
            SpotLocation(spot_id="fixture-b", lat=52.10, lon=4.27),
        ],
    )
    assert result.rows == len(expected) == len(db.rows("forecast_hours"))
    assert result.errors == []
    assert usage(db)[0]["calls"] == pytest.approx(2.4)


# -- budget ------------------------------------------------------------------------------------


def test_job_budget_exceeded_no_request() -> None:
    db, rec = make_db(), Recorder()
    seed_usage(db, "2026-10-14", 7999)
    before = usage(db)
    result = run(db, rec)
    assert rec.requests == [] and result.skipped_budget is True and result.rows == 0
    assert usage(db) == before
    assert db.rows("forecast_hours") == []


def test_job_monthly_budget_exceeded_no_request() -> None:
    db, rec = make_db(), Recorder()
    seed_usage(db, "2026-10-01", 239999)
    before = usage(db)
    result = run(db, rec)
    assert rec.requests == [] and result.skipped_budget is True and result.rows == 0
    assert usage(db) == before


def test_job_budget_stops_mid_run() -> None:
    db, rec = make_db(spot_rows(51)), Recorder()
    seed_usage(db, "2026-10-14", 7939.9)
    result = run(db, rec)
    assert len(rec.requests) == 1
    assert result.skipped_budget is True
    assert result.rows == 50 * 12
    assert result.calls == 60.0
    assert {r["spot_id"] for r in db.rows("forecast_hours")} == {f"s{i:03d}" for i in range(50)}


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


# -- errors and retries ------------------------------------------------------------------------


def test_job_429_then_200_succeeds() -> None:
    db = make_db()
    ok = httpx.Response(200, json=make_forecast_payload(1, start=T0))
    rec = Recorder([httpx.Response(429), ok])
    result = run(db, rec)
    assert result.errors == [] and result.rows == 12
    assert len(rec.requests) == 2
    assert usage(db)[0]["calls"] == 1.2 and usage(db)[0]["requests"] == 1


def test_job_three_500_reports_error() -> None:
    db = make_db()
    rec = Recorder([httpx.Response(500)] * 3)
    result = run(db, rec)
    assert result.errors == ["chunk 1/1: open-meteo forecast: failed after 3 attempts: HTTP 500"]
    assert result.rows == 0 and result.skipped_budget is False
    assert len(rec.requests) == 3
    assert ("forecast_hours", "spot_id,model,valid_at") not in db.upserts
    rows = usage(db)
    assert rows[0]["calls"] == 1.2 and rows[0]["requests"] == 1
    assert result.calls == 1.2


def test_job_parse_error_is_reported_and_booked() -> None:
    db = make_db()
    rec = Recorder([httpx.Response(200, json={"unexpected": True})])
    result = run(db, rec)
    assert len(result.errors) == 1 and result.errors[0].startswith("chunk 1/1: ")
    assert usage(db)[0]["calls"] == 1.2 and db.rows("forecast_hours") == []


def test_job_continues_after_failed_chunk() -> None:
    db = make_db(spot_rows(51))
    ok = httpx.Response(200, json=make_forecast_payload(1, start=T0))
    rec = Recorder([httpx.Response(400, json={"reason": "bad"}), ok])
    result = run(db, rec)
    assert result.errors == ["chunk 1/2: open-meteo forecast: HTTP 400: bad"]
    assert result.rows == 12


def test_job_deduplicates_before_upsert() -> None:
    db = make_db()

    def fake_fetch(http: httpx.Client, locations, **kwargs: Any) -> list[ForecastHour]:
        def hour(wind: float) -> ForecastHour:
            return ForecastHour(
                spot_id="s000",
                model=ModelKey.ICON,
                valid_at=T0,
                wind_kn=wind,
                gust_kn=None,
                dir_deg=90,
            )

        return [hour(10.0), hour(11.0)]

    result = run(db, Recorder(), fetch=fake_fetch)
    stored = db.rows("forecast_hours")
    assert result.rows == 1 and len(stored) == 1 and stored[0]["wind_kn"] == 11.0


def test_job_calls_fetch_without_forecast_days() -> None:
    seen: list[dict[str, Any]] = []

    def fake_fetch(http: httpx.Client, locations, **kwargs: Any) -> list[ForecastHour]:
        seen.append(kwargs)
        return []

    db = make_db()
    result = run(db, Recorder(), fetch=fake_fetch)
    assert seen == [{}] and result.rows == 0
    assert ("forecast_hours", "spot_id,model,valid_at") not in db.upserts


# -- cleanup -----------------------------------------------------------------------------------


def seed_hours(db: FakeSupabase, offsets_h: list[int]) -> None:
    db.seed(
        "forecast_hours",
        [
            {
                "spot_id": "s000",
                "model": "icon",
                "valid_at": (NOW.replace(minute=0) + timedelta(hours=h)).isoformat(),
                "wind_kn": 10.0,
                "gust_kn": None,
                "dir_deg": 90,
                "fetched_at": NOW.isoformat(),
            }
            for h in offsets_h
        ],
    )


def test_delete_old_forecasts_only_older_than_48h() -> None:
    db = FakeSupabase()
    seed_hours(db, [-72, -49, -48, -47, 1])
    now = NOW.replace(minute=0)
    assert delete_old_forecasts(db, now=now) == 2  # type: ignore[arg-type]
    left = sorted(datetime.fromisoformat(r["valid_at"]) for r in db.rows("forecast_hours"))
    assert left == [now + timedelta(hours=h) for h in (-48, -47, 1)]
    assert ("delete", "forecast_hours") in db.writes


def test_delete_old_forecasts_boundary() -> None:
    db = FakeSupabase()
    seed_hours(db, [-48])
    assert delete_old_forecasts(db, now=NOW.replace(minute=0)) == 0  # type: ignore[arg-type]
    assert len(db.rows("forecast_hours")) == 1


def test_job_runs_cleanup() -> None:
    db = make_db()
    seed_hours(db, [-100, -60])
    result = run(db, Recorder())
    assert result.deleted == 2


def test_job_cleans_up_after_budget_stop() -> None:
    db = make_db()
    seed_hours(db, [-100])
    seed_usage(db, "2026-10-14", 7999)
    result = run(db, Recorder())
    assert result.skipped_budget is True and result.deleted == 1


# -- plan --------------------------------------------------------------------------------------


def test_plan_makes_no_requests_and_no_writes() -> None:
    db = make_db(spot_rows(51))
    plan = plan_forecast_ingest(db, BudgetGuard(db), now=NOW)  # type: ignore[arg-type]
    assert (plan.spots, plan.requests) == (51, 2)
    assert plan.weight == pytest.approx(61.2) and plan.within_budget is True
    assert plan.usage.daily == 0
    assert db.writes == []


def test_plan_over_budget() -> None:
    db = make_db()
    seed_usage(db, "2026-10-14", 7999)
    plan = plan_forecast_ingest(db, BudgetGuard(db), now=NOW)  # type: ignore[arg-type]
    assert plan.within_budget is False
