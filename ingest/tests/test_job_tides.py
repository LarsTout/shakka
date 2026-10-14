from datetime import UTC, datetime, timedelta

import pytest

from fakes import FakeSupabase
from shakka.db import iso_utc
from shakka.domain.tide import TideExtreme
from shakka.jobs.tides import delete_old_tides, run_tide_ingest
from shakka.rws.tides import TideFetchError

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
H = timedelta(hours=1)


def ext(station, at, kind="high", level=100):
    return TideExtreme(station=station, at=at, kind=kind, level_cm=level)


def default_extremes(station):
    return [
        ext(station, NOW + 3 * H, "high", 100),
        ext(station, NOW + 9 * H, "low", -80),
    ]


class FakeFetch:
    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    def __call__(self, station, start, end):
        self.calls.append((station, start, end))
        result = self.results.get(station, default_extremes(station))
        if isinstance(result, Exception):
            raise result
        return result


class SpyDb(FakeSupabase):
    def __init__(self):
        super().__init__()
        self.delete_filters = []

    def delete(self, table, *, filters):
        self.delete_filters.append((table, dict(filters)))
        return super().delete(table, filters=filters)


def make_db(stations, cls=FakeSupabase):
    db = cls()
    db.seed(
        "spots",
        [{"id": f"s{i}", "name": f"S{i}", "rws_station": s} for i, s in enumerate(stations)],
    )
    return db


def stored(db, station=None):
    rows = db.rows("tide_extremes")
    return [r for r in rows if station is None or r["station"] == station]


def seed_row(db, station, at, fetched_at, level=1):
    db.seed(
        "tide_extremes",
        [
            {
                "station": station,
                "at": at,
                "kind": "high",
                "level_cm": level,
                "fetched_at": fetched_at,
            }
        ],
    )


def test_unique_nonempty_stations():
    db = make_db(["hoekvanholland", " hoekvanholland ", None, "", "   ", "vlissingen"])
    fetch = FakeFetch()
    result = run_tide_ingest(db, now=NOW, fetch=fetch)
    assert [c[0] for c in fetch.calls] == ["hoekvanholland", "vlissingen"]
    assert all(
        c[1] == NOW - timedelta(days=1) and c[2] == NOW + timedelta(days=8) for c in fetch.calls
    )
    assert result.stations == 2
    assert result.rows == 4


@pytest.mark.parametrize(("age", "fetched"), [(19, False), (20, True), (21, True)])
def test_fresh_station_skipped(age, fetched):
    db = make_db(["hoekvanholland"])
    seed_row(db, "hoekvanholland", NOW + 2 * H, NOW - age * H)
    fetch = FakeFetch()
    result = run_tide_ingest(db, now=NOW, fetch=fetch)
    assert bool(fetch.calls) is fetched
    assert result.skipped == ([] if fetched else ["hoekvanholland"])


def test_force_ignores_freshness():
    db = make_db(["hoekvanholland"])
    seed_row(db, "hoekvanholland", NOW + 2 * H, NOW - 19 * H)
    fetch = FakeFetch()
    result = run_tide_ingest(db, now=NOW, force=True, fetch=fetch)
    assert len(fetch.calls) == 1
    assert result.skipped == []


@pytest.mark.parametrize("error", [TideFetchError("nope"), RuntimeError("bang")])
def test_failure_isolated(error):
    db = make_db(["hoekvanholland", "vlissingen"])
    old = NOW + 2 * H
    seed_row(db, "vlissingen", old, NOW - 30 * H)
    fetch = FakeFetch({"vlissingen": error})
    result = run_tide_ingest(db, now=NOW, fetch=fetch)
    assert result.failed == ["vlissingen"]
    assert result.errors[0].startswith(f"vlissingen: {type(error).__name__}")
    assert len(stored(db, "hoekvanholland")) == 2
    assert len(stored(db, "vlissingen")) == 1


def test_upsert_contract():
    db = make_db(["hoekvanholland"])
    result = run_tide_ingest(db, now=NOW, fetch=FakeFetch())
    assert ("tide_extremes", "station,at") in db.upserts
    rows = stored(db)
    assert result.rows == len(rows) == 2
    for row in rows:
        assert set(row) == {"station", "at", "kind", "level_cm", "fetched_at"}
        assert datetime.fromisoformat(row["fetched_at"]) == NOW


def test_cleanup_48h():
    db = make_db(["other"], SpyDb)
    for i, hours in enumerate((49, 48, 47)):
        seed_row(db, "other", NOW - hours * H, NOW - 1 * H, level=i)
    result = run_tide_ingest(db, now=NOW, fetch=FakeFetch())
    remaining = {datetime.fromisoformat(r["at"]) for r in stored(db, "other")}
    assert NOW - 49 * H not in remaining
    assert NOW - 48 * H in remaining
    assert result.deleted == 1
    expected = {"at": f"lt.{iso_utc(NOW - timedelta(hours=48))}"}
    assert ("tide_extremes", expected) in db.delete_filters


def test_window_replaced():
    db = make_db(["hoekvanholland"])
    shifted_old = NOW + timedelta(days=2, minutes=1)
    shifted_new = NOW + timedelta(days=2, minutes=2)
    outside = NOW - 30 * H
    seed_row(db, "hoekvanholland", shifted_old, NOW - 25 * H)
    seed_row(db, "hoekvanholland", outside, NOW - 25 * H)
    fetch = FakeFetch({"hoekvanholland": [ext("hoekvanholland", shifted_new)]})
    run_tide_ingest(db, now=NOW, fetch=fetch)
    ats = {datetime.fromisoformat(r["at"]) for r in stored(db, "hoekvanholland")}
    assert ats == {shifted_new, outside}


def test_idempotent():
    db = make_db(["hoekvanholland", "vlissingen"])
    run_tide_ingest(db, now=NOW, force=True, fetch=FakeFetch())
    first = len(stored(db))
    run_tide_ingest(db, now=NOW, force=True, fetch=FakeFetch())
    assert len(stored(db)) == first == 4


def test_wrong_station_or_conflict_fails():
    db = make_db(["a", "b", "c"])
    fetch = FakeFetch(
        {
            "a": [ext("zzz", NOW + H)],
            "b": [ext("b", NOW + H, level=1), ext("b", NOW + H, level=2)],
            "c": [ext("c", NOW + H, level=1), ext("c", NOW + H, level=1)],
        }
    )
    result = run_tide_ingest(db, now=NOW, fetch=fetch)
    assert result.failed == ["a", "b"]
    assert len(stored(db, "c")) == 1
    assert result.rows == 1


def test_empty_fetch_keeps_existing_window():
    # N-3: an empty result must fail the station and never wipe its window
    db = make_db(["a"])
    seed_row(db, "a", NOW + 2 * H, NOW - 25 * H)
    result = run_tide_ingest(db, now=NOW, fetch=FakeFetch({"a": []}))
    assert result.failed == ["a"]
    assert "no extremes" in result.errors[0]
    assert len(stored(db, "a")) == 1


def test_invalid_station_code_fails_only_that_station():
    # N-4: a bad code must not break the freshness query or the other stations
    db = make_db(['bad"code', "bad code", "good"])
    fetch = FakeFetch()
    result = run_tide_ingest(db, now=NOW, fetch=fetch)
    assert [c[0] for c in fetch.calls] == ["good"]
    assert result.failed == sorted(['bad"code', "bad code"])
    assert len(result.errors) == 2
    assert result.stations == 1


def test_no_stations():
    db = make_db([None, ""])
    seed_row(db, "old", NOW - 60 * H, NOW - 60 * H)
    fetch = FakeFetch()
    result = run_tide_ingest(db, now=NOW, fetch=fetch)
    assert fetch.calls == []
    assert result.stations == 0
    assert result.deleted == 1


def test_naive_now_rejected():
    naive = datetime(2026, 10, 14, 12)  # noqa: DTZ001
    with pytest.raises(ValueError):
        run_tide_ingest(make_db([]), now=naive, fetch=FakeFetch())
    with pytest.raises(ValueError):
        delete_old_tides(make_db([]), now=naive)
