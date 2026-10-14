"""Tests for `shakka forecast fetch`."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from click.testing import CliRunner

import shakka.jobs.forecast as job
from fakes import FakeSupabase
from openmeteo_payloads import make_forecast_payload
from shakka.budget import SOURCE_OPEN_METEO_FORECAST
from shakka.cli import cli
from shakka.db import DatabaseError

NOW = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
T0 = datetime(2026, 10, 14, 0, tzinfo=UTC)
SECRET = "test-secret-key"


class Transport:
    def __init__(self, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": True, "reason": "bad request"})
        count = len(request.url.params["latitude"].split(","))
        return httpx.Response(200, json=make_forecast_payload(count, start=T0))


class ClosingFake(FakeSupabase):
    def __init__(self) -> None:
        super().__init__()
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


class BrokenFake(ClosingFake):
    def select(self, table: str, **kwargs: Any):
        raise DatabaseError("select spots: HTTP 500")


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)


def install(
    monkeypatch: pytest.MonkeyPatch, db: FakeSupabase, transport: Transport
) -> list[httpx.Client]:
    clients: list[httpx.Client] = []

    def fake_open(settings: Any) -> tuple[FakeSupabase, httpx.Client]:
        client = httpx.Client(transport=httpx.MockTransport(transport))
        clients.append(client)
        return db, client

    monkeypatch.setattr(job, "_open_resources", fake_open)
    monkeypatch.setattr(job, "_utcnow", lambda: NOW)
    return clients


def make_db(cls: type[FakeSupabase] = ClosingFake) -> ClosingFake:
    db = cls()
    db.seed("spots", [{"id": "s1", "name": "S1", "lat": 52.0, "lon": 4.0}])
    db.seed("spots", [{"id": "s2", "name": "S2", "lat": None, "lon": None}])
    return db  # type: ignore[return-value]


def invoke(*args: str):
    return CliRunner().invoke(cli, ["forecast", "fetch", *args])


def test_help_lists_forecast_fetch() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0 and "forecast" in result.output
    for args in (["forecast", "--help"], ["forecast", "fetch", "--help"]):
        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0
    assert "--dry-run" in result.output


def test_fetch_success_output(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    db, transport = make_db(), Transport()
    install(monkeypatch, db, transport)
    result = invoke()
    lines = result.output.splitlines()
    assert result.exit_code == 0
    assert lines == [
        "forecast: spots=1 rows=12 calls=1.20 deleted=0 skipped_budget=no errors=0",
        "forecast: ok",
    ]
    assert SECRET not in result.output and "127.0.0.1" not in result.output
    assert len(transport.requests) == 1


def test_fetch_errors_exit_1(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, make_db(), Transport(status=400))
    result = invoke()
    assert result.exit_code == 1
    assert result.output.splitlines() == [
        "forecast: spots=1 rows=0 calls=1.20 deleted=0 skipped_budget=no errors=1",
        "error   chunk 1/1: open-meteo forecast: HTTP 400: bad request",
        "forecast: failed",
    ]


def test_fetch_budget_stop_exit_1(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    db, transport = make_db(), Transport()
    db.seed(
        "api_usage",
        [{"day": "2026-10-14", "source": SOURCE_OPEN_METEO_FORECAST, "calls": 7999, "requests": 1}],
    )
    install(monkeypatch, db, transport)
    result = invoke()
    assert result.exit_code == 1 and transport.requests == []
    assert "skipped_budget=yes" in result.output and result.output.endswith("forecast: failed\n")


def test_dry_run_makes_no_requests_and_no_writes(
    env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, transport = make_db(), Transport()
    install(monkeypatch, db, transport)
    result = invoke("--dry-run")
    assert result.exit_code == 0
    assert transport.requests == [] and db.writes == []
    assert result.output.splitlines() == [
        "forecast: dry run, no requests to Open-Meteo and no database writes",
        "spots with coordinates: 1, without coordinates: 1",
        "requests: 1, estimated weight: 1.20",
        "usage today: 0.00 / 8000, this month: 0.00 / 240000",
        "budget: ok",
    ]


def test_dry_run_budget_exceeded(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_db()
    db.seed(
        "api_usage",
        [{"day": "2026-10-14", "source": SOURCE_OPEN_METEO_FORECAST, "calls": 7999, "requests": 1}],
    )
    install(monkeypatch, db, Transport())
    result = invoke("--dry-run")
    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == "budget: exceeded"
    assert "usage today: 7999.00 / 8000" in result.output


def test_missing_config_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[Any] = []
    monkeypatch.setattr(job, "_open_resources", lambda s: called.append(s))
    result = invoke()
    assert result.exit_code == 1
    assert result.output == "forecast: configuration incomplete; run shakka doctor\n"
    assert called == []


@pytest.mark.parametrize("dry_run", [False, True])
def test_database_error_exit_1(env: None, monkeypatch: pytest.MonkeyPatch, dry_run: bool) -> None:
    db, transport = make_db(BrokenFake), Transport()
    install(monkeypatch, db, transport)
    result = invoke(*(["--dry-run"] if dry_run else []))
    assert result.exit_code == 1
    assert result.output == "forecast: database error: select spots: HTTP 500\n"
    assert transport.requests == []


@pytest.mark.parametrize("dry_run", [False, True])
def test_resources_closed_on_database_error(
    env: None, monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    db = make_db(BrokenFake)
    clients = install(monkeypatch, db, Transport())
    result = invoke(*(["--dry-run"] if dry_run else []))
    assert result.exit_code == 1
    assert clients[0].is_closed is True
    assert db.closed == 1


def test_resources_closed_on_success(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_db()
    clients = install(monkeypatch, db, Transport())
    assert invoke().exit_code == 0
    assert clients[0].is_closed is True and db.closed == 1
