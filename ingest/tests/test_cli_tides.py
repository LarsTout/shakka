from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner

import shakka.rws.tides as rws
from fakes import FakeSupabase
from shakka.cli import cli
from shakka.db import SupabaseRest
from shakka.domain.tide import TideExtreme

SECRET = "sb_secret_TESTVALUE"
STATIONS = [
    rws.StationInfo("hoekvanholland", "Hoek van Holland", 51.97867, 4.12),
    rws.StationInfo("vlissingen", "Vlissingen", 51.44, 3.596),
]


def run(*args):
    return CliRunner().invoke(cli, ["tides", *args])


def test_stations_output(monkeypatch):
    monkeypatch.setattr(rws, "list_tide_stations", lambda: STATIONS)
    result = run("stations")
    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "code\tname\tlat\tlon",
        "hoekvanholland\tHoek van Holland\t51.97867\t4.12000",
        "vlissingen\tVlissingen\t51.44000\t3.59600",
        "2 stations",
    ]


def test_stations_search(monkeypatch):
    monkeypatch.setattr(rws, "list_tide_stations", lambda: STATIONS)
    result = run("stations", "--search", "HOEK")
    assert result.exit_code == 0
    assert "hoekvanholland" in result.output
    assert "vlissingen" not in result.output
    assert "1 stations" in result.output


def test_stations_error(monkeypatch):
    def boom():
        raise rws.TideFetchError("catalogue: HTTP 500")

    monkeypatch.setattr(rws, "list_tide_stations", boom)
    result = run("stations")
    assert result.exit_code == 1
    assert "tides stations: catalogue: HTTP 500" in result.output


def test_fetch_without_config():
    result = run("fetch")
    assert result.exit_code == 1
    assert "configuration incomplete" in result.output


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://testref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    db = FakeSupabase()
    db.seed(
        "spots",
        [
            {"id": "a", "name": "A", "rws_station": "hoekvanholland"},
            {"id": "b", "name": "B", "rws_station": "vlissingen"},
        ],
    )
    monkeypatch.setattr(SupabaseRest, "from_settings", classmethod(lambda cls, settings: db))
    return db


def fake_fetch(failing=()):
    def fetch(station, start, end, *, http=None):
        if station in failing:
            raise rws.TideFetchError(f"{station}: HTTP 500")
        at = datetime.now(UTC) + timedelta(hours=3)
        return [TideExtreme(station=station, at=at, kind="high", level_cm=90)]

    return fetch


def test_fetch_ok(monkeypatch, configured):
    monkeypatch.setattr(rws, "fetch_tide_extremes", fake_fetch())
    result = run("fetch")
    assert result.exit_code == 0
    assert "tides: fetched 2 station(s), 2 row(s), deleted 0 old row(s)" in result.output
    assert SECRET not in result.output
    again = run("fetch")
    assert again.exit_code == 0
    assert "tides: skipped (fetched < 20h ago): hoekvanholland, vlissingen" in again.output
    forced = run("fetch", "--force")
    assert "fetched 2 station(s)" in forced.output


def test_fetch_failure(monkeypatch, configured):
    monkeypatch.setattr(rws, "fetch_tide_extremes", fake_fetch(failing={"vlissingen"}))
    result = run("fetch")
    assert result.exit_code == 1
    assert "tides: failed: vlissingen" in result.output
    assert "  vlissingen: TideFetchError" in result.output
    assert SECRET not in result.output


def test_fetch_database_error(monkeypatch, configured):
    from shakka.db import DatabaseError

    def broken(*args, **kwargs):
        raise DatabaseError("select spots: HTTP 500")

    monkeypatch.setattr(configured, "select", broken)
    result = run("fetch")
    assert result.exit_code == 1
    assert "tides fetch: database error: select spots: HTTP 500" in result.output
