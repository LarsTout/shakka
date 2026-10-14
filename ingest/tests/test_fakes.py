"""FakeSupabase: PostgREST filter, order and write semantics shared with SupabaseRest."""

import inspect
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from fake_cases import FILTER_CASES, PARITY_ROWS, FilterCase
from fakes import FakeSupabase
from shakka.db import DatabaseError, SupabaseRest, iso_utc

T0 = datetime(2026, 1, 1, tzinfo=UTC)
HOUR = "2026-10-14T12:00:00Z"


@pytest.mark.parametrize("case", FILTER_CASES, ids=[c.name for c in FILTER_CASES])
def test_filter_cases(case: FilterCase):
    fake = FakeSupabase()
    fake.seed("spots", PARITY_ROWS)
    rows = fake.select("spots", filters=case.filters, order=case.order or "id", limit=case.limit)
    assert [r["id"] for r in rows] == case.expected


def test_select_columns_projection():
    fake = FakeSupabase()
    fake.seed("spots", PARITY_ROWS)
    rows = fake.select("spots", columns="id,region", limit=1)
    assert rows == [{"id": "zzp-a", "region": "noord"}]


def test_select_without_order_uses_primary_key():
    fake = FakeSupabase()
    fake.seed("spots", list(reversed(PARITY_ROWS)))
    assert [r["id"] for r in fake.select("spots")] == [r["id"] for r in PARITY_ROWS]


def test_writes_recorded():
    fake = FakeSupabase()
    fake.seed("spots", [{"id": "s-one", "name": "One"}])
    fake.select("spots")
    assert fake.writes == []
    assert fake.upserts == []

    fake.upsert("spots", [{"id": "s-one", "name": "One"}], on_conflict="id")
    fake.insert("spots", [{"id": "s-two", "name": "Two"}])
    fake.update("spots", {"name": "Zwei"}, filters={"id": "eq.s-two"})
    fake.delete("spots", filters={"id": "eq.s-two"})
    assert fake.writes == [
        ("upsert", "spots"),
        ("insert", "spots"),
        ("update", "spots"),
        ("delete", "spots"),
    ]
    assert fake.upserts == [("spots", "id")]

    fake.upsert("spots", [], on_conflict="id")
    fake.insert("spots", [])
    assert len(fake.writes) == 4
    assert fake.upserts == [("spots", "id")]

    fake.register_rpc("purge", lambda args: 1)
    fake.rpc("purge", {"x": 1})
    assert len(fake.writes) == 4
    assert fake.rpc_calls == [("purge", {"x": 1})]


def test_upsert_merges_columns():
    fake = FakeSupabase()
    fake.seed(
        "spots",
        [
            {
                "id": "s-one",
                "name": "One",
                "region": "x",
                "notes": "n",
                "updated_at": "2020-01-01T00:00:00Z",
            }
        ],
    )
    fake.upsert("spots", [{"id": "s-one", "name": "One", "region": "y"}], on_conflict="id")
    (row,) = fake.rows("spots")
    assert row["region"] == "y"
    assert row["notes"] == "n"
    assert row["updated_at"] == iso_utc(T0)

    fake.upsert("spots", [{"id": "s-two", "name": "Two"}], on_conflict="id")
    new = fake.rows("spots")[1]
    assert new["verified"] is False
    assert new["season"] == []
    assert new["tide_sensitive"] == "none"

    with pytest.raises(DatabaseError) as info:
        fake.upsert("spots", [{"id": "s-one", "name": "One"}], on_conflict="name")
    assert info.value.code == "42P10"


def _forecast(spot: str, model: str, valid_at: str) -> dict:
    return {"spot_id": spot, "model": model, "valid_at": valid_at, "fetched_at": HOUR}


def test_upsert_duplicate_pk_in_batch():
    fake = FakeSupabase()
    rows = [
        _forecast("s-one", "knmi", "2026-10-14T12:00:00Z"),
        _forecast("s-one", "knmi", "2026-10-14T12:00:00+00:00"),
    ]
    with pytest.raises(DatabaseError) as info:
        fake.upsert("forecast_hours", rows, on_conflict="spot_id,model,valid_at")
    assert info.value.code == "21000"
    assert info.value.status == 400
    assert fake.rows("forecast_hours") == []


def test_upsert_same_pk_in_different_offsets_merges():
    fake = FakeSupabase()
    on_conflict = "spot_id,model,valid_at"
    fake.upsert(
        "forecast_hours", [_forecast("s", "knmi", "2026-10-14T12:00:00Z")], on_conflict=on_conflict
    )
    again = {**_forecast("s", "knmi", "2026-10-14T14:00:00+02:00"), "wind_kn": 12}
    fake.upsert("forecast_hours", [again], on_conflict=on_conflict)
    (row,) = fake.rows("forecast_hours")
    assert row["wind_kn"] == 12


def test_order_tiebreak_matches_client():
    fake = FakeSupabase()
    rows = [
        _forecast(spot, model, HOUR)
        for spot, model in [
            ("s-c", "icon"),
            ("s-a", "knmi"),
            ("s-b", "icon"),
            ("s-a", "icon"),
            ("s-c", "knmi"),
            ("s-b", "knmi"),
        ]
    ]
    fake.seed("forecast_hours", rows)
    result = fake.select("forecast_hours", order="valid_at.desc")
    assert [(r["spot_id"], r["model"]) for r in result] == sorted(
        (r["spot_id"], r["model"]) for r in rows
    )


def test_insert_duplicate_pk_is_atomic():
    fake = FakeSupabase()
    fake.seed("spots", [{"id": "s-one", "name": "One"}])
    with pytest.raises(DatabaseError) as info:
        fake.insert("spots", [{"id": "s-two", "name": "Two"}, {"id": "s-one", "name": "Dup"}])
    assert info.value.code == "23505"
    assert info.value.status == 409
    assert [r["id"] for r in fake.rows("spots")] == ["s-one"]


def test_insert_missing_pk():
    fake = FakeSupabase()
    with pytest.raises(DatabaseError) as info:
        fake.insert("spots", [{"name": "No id"}])
    assert info.value.code == "23502"


def test_generated_defaults():
    fake = FakeSupabase()
    run = {"started_at": T0, "status": "running"}
    assert fake.insert("ingest_runs", [run], returning=True)[0]["id"] == 1
    assert fake.insert("ingest_runs", [run], returning=True)[0]["id"] == 2
    with pytest.raises(DatabaseError) as info:
        fake.insert("ingest_runs", [{**run, "id": 9}])
    assert info.value.code == "428C9"

    state = {
        "user_id": "u1",
        "spot_id": "s1",
        "window_start": HOUR,
        "window_end": HOUR,
        "status": "active",
        "snapshot": {},
    }
    (stored,) = fake.insert("alert_state", [state], returning=True)
    uuid.UUID(stored["id"])
    assert stored["created_at"] == iso_utc(T0)


def test_update_sets_updated_at():
    now = [T0]
    fake = FakeSupabase(clock=lambda: now[0])
    fake.seed("profiles", [{"user_id": "u1"}, {"user_id": "u2"}])
    assert fake.rows("profiles")[0]["updated_at"] == iso_utc(T0)
    now[0] = T0 + timedelta(hours=3)
    assert fake.update("profiles", {"weight_kg": 80}, filters={"user_id": "eq.u1"}) == 1
    first, second = fake.rows("profiles")
    assert first["updated_at"] == iso_utc(now[0])
    assert first["weight_kg"] == 80
    assert second["updated_at"] == iso_utc(T0)


def test_cascades():
    fake = FakeSupabase()
    for spot in ("s-one", "s-two"):
        fake.seed("spots", [{"id": spot, "name": spot}])
        fake.seed("forecast_hours", [_forecast(spot, "knmi", HOUR)])
        fake.seed(
            "evaluations",
            [{"spot_id": spot, "valid_at": HOUR, "verdict": "no_go", "evaluated_at": HOUR}],
        )
        fake.seed("favorites", [{"user_id": "u1", "spot_id": spot}])
        fake.seed("alert_rules", [{"user_id": "u1", "spot_id": spot}])
        fake.seed("alert_state", [{"user_id": "u1", "spot_id": spot}])

    assert fake.delete("favorites", filters={"user_id": "eq.u1", "spot_id": "eq.s-one"}) == 1
    assert [(r["user_id"], r["spot_id"]) for r in fake.rows("alert_rules")] == [("u1", "s-two")]
    assert len(fake.rows("favorites")) == 1

    fake.seed("favorites", [{"user_id": "u1", "spot_id": "s-one"}])
    fake.seed("alert_rules", [{"user_id": "u1", "spot_id": "s-one"}])
    assert fake.delete("spots", filters={"id": "eq.s-one"}) == 1
    for table in ("forecast_hours", "evaluations", "favorites", "alert_rules", "alert_state"):
        assert [r["spot_id"] for r in fake.rows(table)] == ["s-two"], table
    assert [r["id"] for r in fake.rows("spots")] == ["s-two"]
    assert fake.writes == [("delete", "favorites"), ("delete", "spots")]


def test_same_validation_as_client():
    fake = FakeSupabase()
    for filters in (None, {}, {"id": []}):
        with pytest.raises(ValueError):
            fake.update("spots", {"name": "x"}, filters=filters)
        with pytest.raises(ValueError):
            fake.delete("spots", filters=filters)
    with pytest.raises(ValueError):
        fake.select("spots", filters={"id": "like.*x*"})
    with pytest.raises(ValueError):
        fake.select("spots", filters={"order": "eq.1"})
    with pytest.raises(ValueError):
        fake.insert("spots", [{"id": "s-one", "name": "x", "updated_at": datetime(2026, 1, 1)}])  # noqa: DTZ001
    with pytest.raises(ValueError):
        fake.select("spots", limit=0)
    with pytest.raises(ValueError):
        fake.insert("spots", [{"id": "a"}, {"id": "b", "name": "x"}])
    with pytest.raises(ValueError):
        fake.select("not_a_table")
    with pytest.raises(ValueError):
        fake.select("spots", filters={"lat": "eq.1"}, order="id.sideways")
    assert fake.writes == []


def test_null_never_matches_comparisons():
    fake = FakeSupabase()
    fake.seed("spots", [{"id": "s-one", "name": "x", "region": None}])
    fake.seed("spots", [{"id": "s-two", "name": "x"}])
    for op in ("eq.a", "neq.a", "lt.a", "gt.a", "in.(a,b)"):
        assert fake.select("spots", filters={"region": op}) == []
    assert len(fake.select("spots", filters={"region": "is.null"})) == 2


def test_array_columns_cannot_be_filtered():
    fake = FakeSupabase()
    fake.seed("evaluations", [{"spot_id": "s", "valid_at": HOUR, "reasons": ["no_data"]}])
    with pytest.raises(ValueError, match="not supported"):
        fake.select("evaluations", filters={"reasons": "eq.x"})


def test_rpc():
    fake = FakeSupabase()
    fake.register_rpc("purge", lambda args: {"seen": args})
    assert fake.rpc("purge", {"x": 1}) == {"seen": {"x": 1}}
    with pytest.raises(DatabaseError) as info:
        fake.rpc("missing")
    assert info.value.code == "PGRST202"
    assert info.value.status == 404


def test_rows_returns_copies():
    fake = FakeSupabase()
    fake.seed("spots", [{"id": "s-one", "name": "x", "season": [1]}])
    fake.rows("spots")[0]["season"].append(2)
    fake.select("spots")[0]["name"] = "changed"
    assert fake.rows("spots")[0]["season"] == [1]
    assert fake.rows("spots")[0]["name"] == "x"


def test_context_manager():
    with FakeSupabase() as fake:
        assert fake.select("spots") == []


@pytest.mark.parametrize(
    "method", ["select", "upsert", "insert", "update", "delete", "rpc", "close"]
)
def test_signatures_match_client(method: str):
    def shape(func):
        return [
            (p.name, p.kind, p.default)
            for p in inspect.signature(func).parameters.values()
            if p.name != "self"
        ]

    assert shape(getattr(FakeSupabase, method)) == shape(getattr(SupabaseRest, method))
