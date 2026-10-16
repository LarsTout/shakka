"""SupabaseRest against httpx.MockTransport: headers, filters, pagination, batching, errors."""

import json
import math
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import httpx
import pytest

import shakka.db
import shakka.http
from shakka.db import (
    DatabaseError,
    SupabaseRest,
    effective_order,
    in_filter,
    to_json,
)

URL = "https://testref.supabase.co"
SECRET = "sb_secret_TESTVALUE"

Handler = Callable[[httpx.Request], httpx.Response]


def make_db(handler: Handler) -> tuple[SupabaseRest, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return SupabaseRest(URL, SECRET, client=client), seen


def ok_json(body, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


def empty_ok(request: httpx.Request) -> httpx.Response:
    return ok_json([])


def paged(rows: list[dict], *, max_per_page: int | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        limit = int(request.url.params["limit"])
        offset = int(request.url.params["offset"])
        if max_per_page is not None:
            limit = min(limit, max_per_page)
        return ok_json(rows[offset : offset + limit])

    return handler


def test_key_in_header_not_url():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.params["offset"] != "0":
            return ok_json([])
        return ok_json([{"id": 1}])

    db, seen = make_db(handler)
    db.select("spots")
    db.upsert("spots", [{"id": "a", "name": "A"}], on_conflict="id")
    db.insert("spots", [{"id": "b", "name": "B"}], returning=True)
    db.update("spots", {"name": "C"}, filters={"id": "eq.a"})
    db.delete("spots", filters={"id": "eq.a"})
    db.rpc("db_usage")
    assert len(seen) == 7  # select needs one extra request for the empty page
    for request in seen:
        assert request.headers["apikey"] == SECRET
        assert "authorization" not in request.headers
        assert SECRET not in str(request.url)


def test_select_serializes_filters():
    db, seen = make_db(empty_ok)
    db.select(
        "forecast_hours",
        filters={
            "spot_id": "eq.wijk-aan-zee",
            "valid_at": ["gte.2026-10-14T00:00:00Z", "lt.2026-10-15T00:00:00+00:00"],
        },
    )
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == "/rest/v1/forecast_hours"
    items = request.url.params.multi_items()
    assert ("spot_id", "eq.wijk-aan-zee") in items
    assert ("valid_at", "gte.2026-10-14T00:00:00Z") in items
    assert ("valid_at", "lt.2026-10-15T00:00:00+00:00") in items
    assert "%2B00%3A00" in str(request.url)
    assert ("select", "*") in items
    assert ("limit", "1000") in items
    assert ("offset", "0") in items


ORDER_CASES = [
    ("forecast_hours", None, "spot_id,model,valid_at"),
    ("forecast_hours", "valid_at.desc", "valid_at.desc,spot_id,model"),
    ("forecast_hours", "model,valid_at.desc", "model,valid_at.desc,spot_id"),
    ("forecast_hours", "spot_id.desc,model,valid_at", "spot_id.desc,model,valid_at"),
    ("spots", "lat.asc,id.desc", "lat.asc,id.desc"),
    ("unknown_table", "x.desc", "x.desc"),
]


@pytest.mark.parametrize(("table", "order", "expected"), ORDER_CASES)
def test_select_default_order(table, order, expected):
    db, seen = make_db(empty_ok)
    db.select(table, order=order)
    assert seen[0].url.params["order"] == expected


def test_select_unknown_table_without_order():
    db, seen = make_db(empty_ok)
    with pytest.raises(ValueError):
        db.select("unknown_table")
    assert seen == []


@pytest.mark.parametrize(("table", "order", "expected"), ORDER_CASES)
def test_effective_order(table, order, expected):
    assert effective_order(table, order) == expected


def test_effective_order_rejects_bad_input():
    with pytest.raises(ValueError):
        effective_order("forecast_hours", "valid_at.sideways")
    with pytest.raises(ValueError):
        effective_order("unknown_table", None)


def test_select_paginates():
    rows = [{"n": i} for i in range(2500)]
    db, seen = make_db(paged(rows))
    result = db.select("spots")
    assert result == rows
    assert [int(r.url.params["offset"]) for r in seen] == [0, 1000, 2000, 2500]
    assert [int(r.url.params["limit"]) for r in seen] == [1000] * 4


def test_select_exact_page_multiple():
    rows = [{"n": i} for i in range(2000)]
    db, seen = make_db(paged(rows))
    assert db.select("spots") == rows
    assert len(seen) == 3
    db, seen = make_db(paged([]))
    assert db.select("spots") == []
    assert len(seen) == 1


def test_select_short_pages():
    rows = [{"n": i} for i in range(1000)]
    db, seen = make_db(paged(rows, max_per_page=400))
    assert db.select("spots") == rows
    assert [int(r.url.params["offset"]) for r in seen] == [0, 400, 800, 1000]


def test_select_limit():
    rows = [{"n": i} for i in range(3000)]
    db, seen = make_db(paged(rows))
    assert db.select("spots", limit=1500) == rows[:1500]
    assert [int(r.url.params["limit"]) for r in seen] == [1000, 500]
    assert [int(r.url.params["offset"]) for r in seen] == [0, 1000]

    db, seen = make_db(paged([{"n": i} for i in range(10)]))
    assert len(db.select("spots", limit=5)) == 5
    assert len(seen) == 1

    db, seen = make_db(empty_ok)
    with pytest.raises(ValueError):
        db.select("spots", limit=0)
    assert seen == []


def test_upsert_on_conflict_and_prefer():
    db, seen = make_db(lambda request: httpx.Response(201))
    at = datetime(2026, 10, 14, 14, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    count = db.upsert(
        "forecast_hours",
        [{"spot_id": "a", "model": "knmi", "valid_at": at}],
        on_conflict="spot_id,model,valid_at",
    )
    assert count == 1
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path == "/rest/v1/forecast_hours"
    assert request.url.params["on_conflict"] == "spot_id,model,valid_at"
    prefer = {token.strip() for token in request.headers["prefer"].split(",")}
    assert prefer == {"resolution=merge-duplicates", "return=minimal"}
    assert request.headers["content-type"] == "application/json"
    body = json.loads(request.content)
    assert isinstance(body, list)
    assert body[0]["valid_at"] == "2026-10-14T12:00:00Z"


def test_upsert_batches():
    db, seen = make_db(lambda request: httpx.Response(201))
    rows = [{"id": f"s{i}", "name": "x"} for i in range(1201)]
    assert db.upsert("spots", rows, on_conflict="id") == 1201
    assert [len(json.loads(r.content)) for r in seen] == [500, 500, 201]


def test_upsert_empty_no_request():
    db, seen = make_db(lambda request: httpx.Response(201))
    assert db.upsert("spots", [], on_conflict="id") == 0
    assert seen == []


def test_upsert_mismatched_keys():
    db, seen = make_db(lambda request: httpx.Response(201))
    with pytest.raises(ValueError):
        db.upsert("spots", [{"id": "a", "name": "A"}, {"id": "b"}], on_conflict="id")
    with pytest.raises(ValueError):
        db.upsert("spots", [{"name": "A"}], on_conflict="id")
    assert seen == []


def test_insert_returning():
    db, seen = make_db(lambda request: ok_json([{"id": "a"}], 201))
    assert db.insert("spots", [{"id": "a", "name": "A"}], returning=True) == [{"id": "a"}]
    assert seen[0].headers["prefer"] == "return=representation"
    assert db.insert("spots", [{"id": "a", "name": "A"}]) == []
    assert seen[1].headers["prefer"] == "return=minimal"
    assert db.insert("spots", []) == []
    assert len(seen) == 2


@pytest.mark.parametrize("filters", [None, {}, {"id": []}])
def test_update_and_delete_require_filters(filters):
    db, seen = make_db(empty_ok)
    with pytest.raises(ValueError):
        db.update("spots", {"name": "x"}, filters=filters)
    with pytest.raises(ValueError):
        db.delete("spots", filters=filters)
    assert seen == []


def test_update_empty_values():
    db, seen = make_db(empty_ok)
    with pytest.raises(ValueError):
        db.update("spots", {}, filters={"id": "eq.a"})
    assert seen == []


def test_update_counts_rows():
    db, seen = make_db(lambda request: ok_json([{"id": 1}, {"id": 2}]))
    assert db.update("ingest_runs", {"status": "ok"}, filters={"id": "in.(1,2)"}) == 2
    request = seen[0]
    assert request.method == "PATCH"
    assert request.headers["prefer"] == "return=representation"
    assert request.url.params["select"] == "id"
    assert request.url.params["id"] == "in.(1,2)"
    assert json.loads(request.content) == {"status": "ok"}


def test_delete_counts_rows():
    rows = [{"spot_id": "a", "model": "knmi", "valid_at": f"t{i}"} for i in range(3)]
    db, seen = make_db(lambda request: ok_json(rows))
    cutoff = "lt.2026-10-14T00:00:00Z"
    assert db.delete("forecast_hours", filters={"valid_at": cutoff}) == 3
    request = seen[0]
    assert request.method == "DELETE"
    assert request.headers["prefer"] == "return=representation"
    assert request.url.params["select"] == "spot_id,model,valid_at"
    assert request.url.params["valid_at"] == cutoff


def test_update_unknown_table_selects_star():
    db, seen = make_db(empty_ok)
    assert db.delete("unknown_table", filters={"x": "eq.1"}) == 0
    assert seen[0].url.params["select"] == "*"


def test_rpc():
    responses = iter([ok_json({"calls": 3}), httpx.Response(204)])
    db, seen = make_db(lambda request: next(responses))
    assert db.rpc("db_usage") == {"calls": 3}
    assert db.rpc("db_usage") is None
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/rest/v1/rpc/db_usage"
    assert json.loads(seen[0].content) == {}


def test_http_error_becomes_database_error():
    db, _ = make_db(lambda r: ok_json({"code": "23505", "message": "duplicate key value"}, 409))
    with pytest.raises(DatabaseError) as info:
        db.insert("spots", [{"id": "a"}])
    assert info.value.status == 409
    assert info.value.code == "23505"
    assert "HTTP 409 23505" in str(info.value)

    db, _ = make_db(lambda r: ok_json({"code": "401", "message": f"bad key {SECRET} here"}, 401))
    with pytest.raises(DatabaseError) as info:
        db.select("spots")
    assert SECRET not in str(info.value)
    assert "***" in str(info.value)

    db, _ = make_db(lambda r: httpx.Response(500, text="<html><body>boom page</body></html>"))
    with pytest.raises(DatabaseError) as info:
        db.select("spots")
    assert "<html>" not in str(info.value)
    assert info.value.status == 500

    db, _ = make_db(lambda r: httpx.Response(302, headers={"location": "https://evil.test/"}))
    with pytest.raises(DatabaseError) as info:
        db.select("spots")
    assert info.value.status == 302


def test_long_error_message_is_truncated():
    db, _ = make_db(lambda r: ok_json({"code": "XX000", "message": "m" * 1000}, 400))
    with pytest.raises(DatabaseError) as info:
        db.select("spots")
    assert len(str(info.value)) < 400


def test_unexpected_response_shape():
    db, _ = make_db(lambda r: ok_json({"not": "a list"}))
    with pytest.raises(DatabaseError, match="unexpected response"):
        db.select("spots")


def test_transport_error():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom testref")

    db, _ = make_db(boom)
    with pytest.raises(DatabaseError) as info:
        db.select("spots")
    message = str(info.value)
    assert "ConnectError" in message
    for forbidden in ("boom", "testref", SECRET):
        assert forbidden not in message
    assert info.value.__cause__ is None
    assert info.value.status is None


def _select_with_filter(key: str):
    return lambda db: db.select("spots", filters={key: "eq.1"})


VALIDATION_CASES = [
    lambda db: db.select("spots?x=1"),
    lambda db: db.select("../auth"),
    lambda db: db.select("Spots"),
    lambda db: db.select("spots", columns="id; drop"),
    lambda db: db.select("spots", order="id.sideways"),
    lambda db: db.select("spots", filters={"a b": "eq.1"}),
    *[
        _select_with_filter(key)
        for key in (
            "order",
            "select",
            "limit",
            "offset",
            "on_conflict",
            "columns",
            "or",
            "and",
            "not",
        )
    ],
    lambda db: db.select("spots", filters={"id": "like.*x*"}),
    lambda db: db.select("spots", filters={"id": "not.is.null"}),
    lambda db: db.select("spots", filters={"id": "is.true"}),
    lambda db: db.select("spots", filters={"id": "in.a,b"}),
    lambda db: db.select("spots", filters={"id": "noop"}),
    lambda db: db.upsert("spots", [{"id": "a"}], on_conflict="id; x"),
    lambda db: db.rpc("Bad-Name"),
]


@pytest.mark.parametrize("call", VALIDATION_CASES)
def test_validation_errors(call):
    db, seen = make_db(empty_ok)
    with pytest.raises(ValueError):
        call(db)
    assert seen == []


def test_to_json():
    with pytest.raises(ValueError):
        to_json({"at": datetime(2026, 10, 14, 12, 0)})  # noqa: DTZ001
    with pytest.raises(ValueError):
        to_json({"x": math.nan})
    with pytest.raises(ValueError):
        to_json({"x": math.inf})
    with pytest.raises(ValueError):
        to_json({"x": object()})
    amsterdam = datetime(2026, 10, 14, 14, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    assert json.loads(to_json({"at": amsterdam})) == {"at": "2026-10-14T12:00:00Z"}
    payload = {"d": date(2026, 10, 14), "t": time(17, 0), "s": frozenset({"b", "a"})}
    assert json.loads(to_json(payload)) == {"d": "2026-10-14", "t": "17:00:00", "s": ["a", "b"]}
    micro = datetime(2026, 10, 14, 12, 0, 0, 5, tzinfo=UTC)
    assert json.loads(to_json([micro])) == ["2026-10-14T12:00:00.000005Z"]


def test_in_filter():
    assert in_filter(["a", "b"]) == "in.(a,b)"
    assert in_filter(["noord, holland", "oost"]) == 'in.("noord, holland",oost)'
    assert in_filter([1, 2]) == "in.(1,2)"
    with pytest.raises(ValueError):
        in_filter([])
    with pytest.raises(ValueError):
        in_filter(['a"b'])
    with pytest.raises(ValueError):
        in_filter(["a\\b"])


def test_repr_hides_secret_and_url():
    db, _ = make_db(empty_ok)
    text = repr(db)
    assert SECRET not in text
    assert "testref" not in text


def test_from_settings_uses_make_client(monkeypatch):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok_json([])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(shakka.db, "make_client", lambda: client)
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    from shakka.config import get_settings

    db = SupabaseRest.from_settings(get_settings())
    db.select("spots")
    assert str(seen[0].url).startswith(f"{URL}/rest/v1/spots")
    assert seen[0].headers["apikey"] == SECRET
    db.close()
    assert client.is_closed


def test_close_leaves_injected_client_open():
    client = httpx.Client(transport=httpx.MockTransport(empty_ok))
    with SupabaseRest(URL, SECRET, client=client):
        pass
    assert not client.is_closed
    client.close()


# -- retries (WP-22) ---------------------------------------------------------------------------


def _sequence(*answers):
    queue = list(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    return handler


def test_retry_statuses():
    assert set(shakka.db.DB_RETRY_STATUSES) == {429, 502, 503, 504, 520, 521, 522, 523, 524}
    assert 500 not in shakka.db.DB_RETRY_STATUSES


def test_select_retried_with_backoff(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(shakka.http, "_sleep", waits.append)
    page = ok_json([{"id": "a"}])
    db, seen = make_db(_sequence(httpx.Response(503), httpx.Response(503), page, ok_json([])))
    assert db.select("spots") == [{"id": "a"}]
    assert len(seen) == 4  # two failures, the page and the empty closing page
    assert waits == [0.5, 1.0]


def test_cloudflare_status_retried():
    db, seen = make_db(_sequence(httpx.Response(522), ok_json([])))
    assert db.select("spots") == []
    assert len(seen) == 2


def test_insert_and_rpc_not_retried():
    db, seen = make_db(_sequence(httpx.Response(503)))
    with pytest.raises(DatabaseError) as info:
        db.insert("ingest_runs", [{"status": "running"}])
    assert info.value.status == 503
    assert len(seen) == 1
    with pytest.raises(DatabaseError):
        db.rpc("db_usage")
    assert len(seen) == 2


@pytest.mark.parametrize("status", [500, 409])
def test_non_retryable_status_single_request(status):
    db, seen = make_db(_sequence(httpx.Response(status)))
    with pytest.raises(DatabaseError):
        db.select("spots")
    assert len(seen) == 1


@pytest.mark.parametrize("op", ["update", "delete", "upsert"])
def test_idempotent_writes_retried(op):
    db, seen = make_db(_sequence(httpx.Response(503), ok_json([])))
    if op == "update":
        db.update("spots", {"name": "x"}, filters={"id": "eq.a"})
    elif op == "delete":
        db.delete("spots", filters={"id": "eq.a"})
    else:
        db.upsert("spots", [{"id": "a"}], on_conflict="id")
    assert len(seen) == 2


def test_circuit_breaker_after_exhaustion():
    db, seen = make_db(_sequence(httpx.ConnectError("x")))
    assert db.retries_disabled is False
    with pytest.raises(DatabaseError):
        db.select("spots")
    assert len(seen) == 3
    assert db.retries_disabled is True
    with pytest.raises(DatabaseError):
        db.select("spots")
    assert len(seen) == 4


def test_attempts_one_disables_retries():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    db = SupabaseRest(URL, SECRET, client=client, attempts=1)
    with pytest.raises(DatabaseError):
        db.select("spots")
    with pytest.raises(ValueError):
        SupabaseRest(URL, SECRET, client=client, attempts=0)


def test_retry_log_has_no_filter_values(caplog):
    caplog.set_level("WARNING", logger="shakka.db")
    user = "11111111-2222-3333-4444-555555555555"
    db, _ = make_db(_sequence(httpx.Response(503), ok_json([])))
    db.select("favorites", filters={"user_id": f"eq.{user}"})
    text = caplog.text
    assert "db: select favorites attempt 1/3 failed (HTTP 503); retrying in 0.5s" in text
    assert user not in text and SECRET not in text
