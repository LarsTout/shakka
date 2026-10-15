"""Tests for shakka.jobs.inputs (WP-10)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from fakes import FakeSupabase
from job_fixtures import FETCHED, NOW, SPOT, at, seed_forecasts, seed_spot
from shakka.db import DatabaseError
from shakka.domain.forecast import ModelKey
from shakka.jobs.inputs import (
    db_error_summary,
    floor_hour,
    load_inputs,
    load_inputs_checked,
    short_error,
)


class Recording(FakeSupabase):
    def __init__(self) -> None:
        super().__init__()
        self.selects: list[str] = []

    def select(self, table, **kwargs):
        self.selects.append(table)
        return super().select(table, **kwargs)


def one_model_row(valid_at, fetched_at=FETCHED, model="knmi", spot_id=SPOT):
    return {
        "spot_id": spot_id,
        "model": model,
        "valid_at": valid_at,
        "wind_kn": 15.0,
        "gust_kn": 18.0,
        "dir_deg": 270,
        "fetched_at": fetched_at,
    }


def test_loads_spot_with_coords_only():
    db = Recording()
    seed_spot(db)
    db.seed("spots", [{"id": "zonder-coords", "name": "Zonder coords"}])
    seed_forecasts(db)
    load = load_inputs_checked(db, now=NOW)
    assert list(load.inputs) == [SPOT]
    assert load.without_coords == ["zonder-coords"]
    assert db.selects.count("forecast_hours") == 1


def test_forecast_range():
    db = FakeSupabase()
    seed_spot(db)
    times = [
        datetime(2026, 7, 15, 4, tzinfo=UTC),
        datetime(2026, 7, 15, 5, tzinfo=UTC),
        datetime(2026, 7, 23, 6, tzinfo=UTC),
        datetime(2026, 7, 23, 7, tzinfo=UTC),
    ]
    db.seed("forecast_hours", [one_model_row(t) for t in times])
    loaded = load_inputs(db, now=NOW)[SPOT].forecasts
    assert [f.valid_at for f in loaded] == [times[1], times[2]]


def test_spot_without_forecast_rows():
    db = FakeSupabase()
    seed_spot(db, rws_station="teststation")
    db.seed(
        "tide_extremes",
        [{"station": "teststation", "at": at(7), "kind": "low", "level_cm": -80}],
    )
    load = load_inputs_checked(db, now=NOW)
    assert load.inputs[SPOT].forecasts == []
    assert load.inputs[SPOT].tides
    assert load.invalid == []
    assert load.errors == []
    # variant: only rows outside the range
    db.seed("forecast_hours", [one_model_row(datetime(2026, 7, 15, 4, tzinfo=UTC))])
    load = load_inputs_checked(db, now=NOW)
    assert load.inputs[SPOT].forecasts == []
    assert load.invalid == []
    assert load.errors == []


def test_inputs_log_has_no_spot_ids(caplog):
    caplog.set_level(logging.DEBUG)
    db = FakeSupabase()
    seed_spot(db)
    bad = seed_spot(db, id="kapot-strand").to_row()
    db.update("spots", {"lat": 10.0}, filters={"id": f"eq.{bad['id']}"})
    seed_forecasts(db)
    load_inputs_checked(db, now=NOW)
    assert "kapot-strand" not in caplog.text
    assert "test-strand" not in caplog.text
    assert "inputs: spots=2 loaded=1 invalid=1 without_coords=0" in caplog.text


def test_stale_rows_dropped():
    db = FakeSupabase()
    seed_spot(db)
    t = at(10)
    db.seed(
        "forecast_hours",
        [
            one_model_row(t, FETCHED, "icon"),
            one_model_row(t, FETCHED, "ecmwf"),
            one_model_row(t, FETCHED - timedelta(hours=4), "knmi"),
            one_model_row(at(11), FETCHED - timedelta(hours=3), "knmi"),
        ],
    )
    loaded = load_inputs(db, now=NOW)[SPOT].forecasts
    assert [(f.valid_at, f.model) for f in loaded] == [
        (t, ModelKey.ECMWF),
        (t, ModelKey.ICON),
        (at(11), ModelKey.KNMI),
    ]
    assert all(not (f.valid_at == t and f.model == ModelKey.KNMI) for f in loaded)


def tide_row(station, when, kind="high", level=100):
    return {"station": station, "at": when, "kind": kind, "level_cm": level}


def test_tides_per_station_and_range():
    db = Recording()
    seed_spot(db, rws_station="teststation")
    seed_spot(db, id="tweede-strand", rws_station="teststation")
    seed_forecasts(db)
    seed_forecasts(db, spot_id="tweede-strand")
    low = datetime(2026, 7, 14, 17, tzinfo=UTC)  # floor(NOW) - 13 h
    inside = [
        datetime(2026, 7, 14, 18, tzinfo=UTC),
        datetime(2026, 7, 15, 13, tzinfo=UTC),
        datetime(2026, 7, 23, 18, tzinfo=UTC),
    ]
    outside = [low - timedelta(minutes=1), datetime(2026, 7, 23, 19, tzinfo=UTC)]
    rows = [tide_row("teststation", t) for t in [*inside[::-1], *outside]]
    rows.append(tide_row("anderstation", inside[1]))
    db.seed("tide_extremes", rows)
    inputs = load_inputs(db, now=NOW)
    assert [e.at for e in inputs[SPOT].tides] == inside
    assert inputs["tweede-strand"].tides == inputs[SPOT].tides
    assert db.selects.count("tide_extremes") == 1


def test_invalid_spot_isolated():
    db = FakeSupabase()
    seed_spot(db)
    seed_spot(db, id="kapot-strand")
    db.update("spots", {"lat": 10.0}, filters={"id": "eq.kapot-strand"})
    seed_forecasts(db)
    load = load_inputs_checked(db, now=NOW)
    assert list(load.inputs) == [SPOT]
    assert load.invalid == ["kapot-strand"]
    assert len(load.errors) == 1
    assert load.errors[0].startswith("spot kapot-strand: ValidationError")


def test_spot_ids_filter():
    db = Recording()
    seed_spot(db, id="a")
    seed_spot(db, id="b")
    assert list(load_inputs(db, now=NOW, spot_ids={"a"})) == ["a"]
    db.selects.clear()
    assert load_inputs(db, now=NOW, spot_ids=set()) == {}
    assert db.selects == []


def test_db_error_summary():
    exc = DatabaseError("x", status=409, code="23503")
    assert db_error_summary(exc) == "DatabaseError (HTTP 409, code 23503)"
    assert db_error_summary(DatabaseError("x", status=500)) == "DatabaseError (HTTP 500)"
    assert db_error_summary(DatabaseError("x")) == "DatabaseError"
    assert "x" not in db_error_summary(exc).replace("DatabaseError", "")


def test_short_error():
    text = short_error(ValueError("line one\n  line two\t" + "z" * 500))
    assert "\n" not in text
    assert len(text) == 200
    assert text.startswith("line one line two")


def test_floor_hour():
    assert floor_hour(NOW) == datetime(2026, 7, 15, 6, tzinfo=UTC)


def test_naive_now():
    with pytest.raises(ValueError):
        load_inputs_checked(FakeSupabase(), now=datetime(2026, 7, 15, 6, 17))  # noqa: DTZ001


MAX_AGE = timedelta(hours=3)


def _seed_aged(db, age):
    db.seed("forecast_hours", [one_model_row(at(10), NOW - age, "knmi")])


def test_max_fetch_age_boundary_is_fresh():
    db = FakeSupabase()
    seed_spot(db)
    _seed_aged(db, MAX_AGE)
    load = load_inputs_checked(db, now=NOW, max_fetch_age=MAX_AGE)
    assert len(load.inputs[SPOT].forecasts) == 1
    assert load.stale == []


def test_max_fetch_age_one_second_over_is_stale(caplog):
    caplog.set_level(logging.INFO)
    db = FakeSupabase()
    seed_spot(db)
    _seed_aged(db, MAX_AGE + timedelta(seconds=1))
    load = load_inputs_checked(db, now=NOW, max_fetch_age=MAX_AGE)
    assert load.inputs[SPOT].forecasts == []
    assert load.stale == [SPOT]
    assert "stale=1" in caplog.text and SPOT not in caplog.text


def test_max_fetch_age_keeps_only_fresh_model():
    db = FakeSupabase()
    seed_spot(db)
    db.seed(
        "forecast_hours",
        [
            one_model_row(at(10), NOW - timedelta(hours=1), "icon"),
            one_model_row(at(10), NOW - timedelta(hours=4), "knmi"),
        ],
    )
    load = load_inputs_checked(db, now=NOW, max_fetch_age=MAX_AGE)
    assert [f.model for f in load.inputs[SPOT].forecasts] == [ModelKey.ICON]
    assert load.stale == []


def test_without_max_fetch_age_old_rows_stay():
    db = FakeSupabase()
    seed_spot(db)
    _seed_aged(db, timedelta(hours=10))
    load = load_inputs_checked(db, now=NOW)
    assert len(load.inputs[SPOT].forecasts) == 1
    assert load.stale == []
