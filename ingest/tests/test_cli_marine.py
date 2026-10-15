"""Tests for `shakka marine fetch`."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from click.testing import CliRunner

from fakes import FakeSupabase
from openmeteo_payloads import make_marine_payload
from shakka.cli import cli
from shakka.db import DatabaseError
from shakka.jobs import runtime

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
        return httpx.Response(200, json=make_marine_payload(count, start=T0))


class ClosingFake(FakeSupabase):
    """FakeSupabase that counts close() calls (FakeSupabase itself does not)."""

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

    def open_http() -> httpx.Client:
        client = httpx.Client(transport=httpx.MockTransport(transport))
        clients.append(client)
        return client

    monkeypatch.setattr(runtime, "open_db", lambda settings: db)
    monkeypatch.setattr(runtime, "open_http", open_http)
    monkeypatch.setattr(runtime, "utcnow", lambda: NOW)
    return clients


def make_db(cls: type[ClosingFake] = ClosingFake) -> ClosingFake:
    db = cls()
    db.seed("spots", [{"id": "s1", "name": "S1", "lat": 52.0, "lon": 4.0}])
    db.seed("spots", [{"id": "s2", "name": "S2", "lat": None, "lon": None}])
    return db


def invoke(*args: str):
    return CliRunner().invoke(cli, ["marine", "fetch", *args])


def test_help_lists_marine_fetch() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0 and "marine" in result.output
    for args in (["marine", "--help"], ["marine", "fetch", "--help"]):
        assert CliRunner().invoke(cli, args).exit_code == 0


def test_fetch_success_output(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = Transport()
    install(monkeypatch, make_db(), transport)
    result = invoke()
    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "marine: spots=1 rows=3 calls=1.00 deleted=0 skipped_budget=no errors=0",
        "marine: ok",
    ]
    assert SECRET not in result.output and "127.0.0.1" not in result.output
    assert len(transport.requests) == 1


def test_fetch_errors_exit_1(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, make_db(), Transport(status=400))
    result = invoke()
    assert result.exit_code == 1
    assert result.output.splitlines() == [
        "marine: spots=1 rows=0 calls=1.00 deleted=0 skipped_budget=no errors=1",
        "error   chunk 1/1: open-meteo marine: HTTP 400: bad request",
        "marine: failed",
    ]


def test_missing_config_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[Any] = []
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setattr(runtime, "open_db", lambda s: called.append(s))
    result = invoke()
    assert result.exit_code == 1
    assert result.output == "marine: configuration incomplete; run shakka doctor\n"
    assert called == []


def test_database_error_exit_1(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = Transport()
    install(monkeypatch, make_db(BrokenFake), transport)
    result = invoke()
    assert result.exit_code == 1
    assert result.output == "marine: database error: select spots: HTTP 500\n"
    assert transport.requests == []


def test_resources_closed(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_db(BrokenFake)
    clients = install(monkeypatch, db, Transport())
    assert invoke().exit_code == 1
    assert clients[0].is_closed is True
    assert db.closed == 1
