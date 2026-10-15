"""Tests for the evaluation job (WP-10 AC-1)."""

import logging
from datetime import datetime, timedelta

import pytest

from fakes import FakeSupabase
from job_fixtures import NOW, SPOT, at, seed_forecasts, seed_spot
from shakka.domain.evaluation import HourEvaluation, Verdict
from shakka.jobs.evaluate import EvaluationJobResult, run_evaluation
from shakka.jobs.inputs import floor_hour


def tide(station, when, kind, level):
    return {"station": station, "at": when, "kind": kind, "level_cm": level}


def test_evaluates_only_spots_with_coords():
    db = FakeSupabase()
    seed_spot(db, rws_station="teststation")
    db.seed("spots", [{"id": "zonder-coords", "name": "Zonder coords"}])
    seed_forecasts(db)
    seed_forecasts(db, spot_id="zonder-coords")
    db.seed(
        "tide_extremes",
        [
            tide("teststation", at(7), "low", -80),
            tide("teststation", at(13).replace(minute=15), "high", 110),
            tide("teststation", at(19).replace(minute=30), "low", -70),
        ],
    )
    result = run_evaluation(db, now=NOW)
    assert result == EvaluationJobResult(spots=1, rows=9, deleted=0)
    rows = db.rows("evaluations")
    assert {r["spot_id"] for r in rows} == {SPOT}
    assert all(r["evaluated_at"] == "2026-07-15T06:17:00Z" for r in rows)
    assert sorted(datetime.fromisoformat(r["valid_at"]) for r in rows) == [
        at(h) for h in range(8, 17)
    ]
    by_hour = {datetime.fromisoformat(r["valid_at"]).hour: r for r in rows}
    assert by_hour[12]["tide_level_cm"] is not None


def old_eval_row(valid_at):
    ev = HourEvaluation(
        spot_id=SPOT,
        valid_at=valid_at,
        verdict=Verdict.GO,
        reasons=(),
        wind_kn=None,
        gust_kn=None,
        dir_deg=None,
        dir_class=None,
        confidence=None,
        tide_level_cm=None,
    )
    return ev.to_row(evaluated_at=valid_at)


def test_old_rows_deleted():
    db = FakeSupabase()
    seed_spot(db)
    base = floor_hour(NOW)
    gone, kept = base - timedelta(hours=49), base - timedelta(hours=47)
    db.seed("evaluations", [old_eval_row(gone), old_eval_row(kept)])
    result = run_evaluation(db, now=NOW)
    assert result.deleted == 1
    remaining = [datetime.fromisoformat(r["valid_at"]) for r in db.rows("evaluations")]
    assert remaining == [kept]


def test_spot_without_forecasts_is_not_a_failure():
    db = FakeSupabase()
    seed_spot(db, verified=True)
    result = run_evaluation(db, now=NOW)
    assert result == EvaluationJobResult(spots=1, rows=0, deleted=0)
    assert ("upsert", "evaluations") not in db.writes


def test_unverified_spot_is_evaluated():
    db = FakeSupabase()
    seed_spot(db, verified=False)
    seed_forecasts(db)
    assert run_evaluation(db, now=NOW).rows == 9


def test_upsert_is_idempotent():
    db = FakeSupabase()
    seed_spot(db)
    seed_forecasts(db)
    run_evaluation(db, now=NOW)
    run_evaluation(db, now=NOW)
    assert len(db.rows("evaluations")) == 9


def test_invalid_spot_reported(caplog):
    caplog.set_level(logging.DEBUG)
    db = FakeSupabase()
    seed_spot(db)
    seed_spot(db, id="kapot-strand")
    db.update("spots", {"lat": 10.0}, filters={"id": "eq.kapot-strand"})
    seed_forecasts(db)
    result = run_evaluation(db, now=NOW)
    assert result.failed == ("kapot-strand",)
    assert result.spots == 1
    assert result.rows == 9
    assert "evaluate: spot kapot-strand failed" in caplog.text


def test_naive_now():
    with pytest.raises(ValueError):
        run_evaluation(FakeSupabase(), now=datetime(2026, 7, 15, 6, 17))  # noqa: DTZ001

