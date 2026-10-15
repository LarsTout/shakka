"""Tests for the alert job (WP-10 AC-2, AC-4 to AC-7, write order, error isolation)."""

import inspect
import logging
from datetime import datetime, timedelta
from typing import Any

import pytest

from fakes import FakeSupabase
from job_fixtures import (
    NOW,
    SPOT,
    USER_A,
    USER_B,
    USER_C,
    WINDS,
    alert_rows,
    at,
    seed_favorite,
    seed_forecasts,
    seed_profile,
    seed_spot,
)
from shakka.db import DatabaseError
from shakka.domain.dedup import AlertStateEntry
from shakka.jobs.alerts import (
    AlertJobResult,
    load_alert_context,
    plan_favorite,
    run_alerts,
    update_rank,
)
from shakka.jobs.inputs import floor_hour

FIRST_LINE_A = "wo 15 jul 12:00–18:00 · 14–25 kn, vlagen tot 29 kn"
FIRST_LINE_B = "wo 15 jul 14:00–17:00 · 24–25 kn, vlagen tot 29 kn"
SPLIT_WINDS = WINDS | {13: 13.0}


def snapshot(start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wind_min_kn": 14.0,
        "wind_max_kn": 25.0,
        "gust_max_kn": 29.0,
        "dir_deg": 270,
        "dir_class": "onshore",
        "confidence": "high",
    }


def state_row(user_id, start, end, status="active", spot_id=SPOT, snap=None) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "spot_id": spot_id,
        "window_start": start,
        "window_end": end,
        "status": status,
        "snapshot": snapshot(start, end) if snap is None else snap,
        "last_event": "new",
        "last_notified_at": None,
    }


def make_db(cls=FakeSupabase, *, verified=True, forecasts=True) -> FakeSupabase:
    db = cls()
    seed_spot(db, verified=verified)
    if forecasts:
        seed_forecasts(db)
    db.writes.clear()
    return db


def alert_writes(db) -> list[tuple[str, str]]:
    return [w for w in db.writes if w[1] == "alert_state"]


class Recording(FakeSupabase):
    def __init__(self) -> None:
        super().__init__()
        self.selects: list[str] = []
        self.requests: list[tuple[str, str, str]] = []
        self.update_calls: list[tuple[str, str]] = []
        self.zero_updates = False
        self.reject_insert_for: str | None = None

    def select(self, table, *, columns="*", filters=None, order=None, limit=None):
        self.selects.append(table)
        self.requests.append(("select", table, repr(filters)))
        return super().select(table, columns=columns, filters=filters, order=order, limit=limit)

    def update(self, table, values, *, filters):
        self.requests.append(("update", table, repr(filters)))
        if table == "alert_state":
            self.update_calls.append((filters["id"], values["status"]))
            if self.zero_updates:
                return 0
        return super().update(table, values, filters=filters)

    def delete(self, table, *, filters):
        self.requests.append(("delete", table, repr(filters)))
        return super().delete(table, filters=filters)

    def insert(self, table, rows, *, returning=False):
        if (
            table == "alert_state"
            and self.reject_insert_for is not None
            and rows[0].get("user_id") == self.reject_insert_for
        ):
            raise DatabaseError(
                f"insert alert_state: HTTP 409 23503: Key (user_id)=({self.reject_insert_for})"
                " is not present",
                status=409,
                code="23503",
            )
        return super().insert(table, rows, returning=returning)


# -- AC-2 -------------------------------------------------------------------------------------


def test_end_to_end_new_repeat_cancel():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    r1 = run_alerts(db, now=NOW, base_url=None)
    assert len(r1.messages) == 1
    m = r1.messages[0]
    assert m.message.kind == "new"
    assert "Teststrand" in m.message.title
    assert m.user_id == USER_A
    rows = alert_rows(db)
    assert len(rows) == 1
    assert rows[0]["status"] == "active"
    assert rows[0]["last_event"] == "new"
    assert rows[0]["last_notified_at"] is None
    assert rows[0]["user_id"] == USER_A
    assert m.state_id == rows[0]["id"]
    assert m.message.body.splitlines()[0] == FIRST_LINE_A

    before = alert_rows(db)
    db.writes.clear()
    r2 = run_alerts(db, now=NOW, base_url=None)
    assert r2.messages == []
    assert alert_rows(db) == before
    assert alert_writes(db) == [("delete", "alert_state")]

    seed_forecasts(db, winds={h: 6.0 for h in WINDS}, fetched_at=NOW + timedelta(minutes=-7))
    r3 = run_alerts(db, now=NOW, base_url=None)
    assert len(r3.messages) == 1
    assert r3.messages[0].message.kind == "cancelled"
    assert r3.messages[0].message.title == "Gaat niet door: Teststrand"
    rows = alert_rows(db)
    assert rows[0]["status"] == "cancelled"
    assert rows[0]["last_event"] == "cancelled"
    assert r3.messages[0].state_id == rows[0]["id"]


# -- AC-5 -------------------------------------------------------------------------------------


def test_users_get_different_windows():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=20)
    result = run_alerts(db, now=NOW, base_url=None)
    rows = {r["user_id"]: r for r in alert_rows(db)}
    assert len(rows) == 2
    assert datetime.fromisoformat(rows[USER_A]["window_start"]) == at(10)
    assert datetime.fromisoformat(rows[USER_A]["window_end"]) == at(16)
    assert datetime.fromisoformat(rows[USER_B]["window_start"]) == at(12)
    assert datetime.fromisoformat(rows[USER_B]["window_end"]) == at(15)
    bodies = {m.user_id: m.message.body.splitlines()[0] for m in result.messages}
    assert bodies == {USER_A: FIRST_LINE_A, USER_B: FIRST_LINE_B}


# -- AC-6 -------------------------------------------------------------------------------------


@pytest.mark.parametrize("dir_deg", [90, 135])
@pytest.mark.parametrize(
    "rule",
    [
        {"min_go_hours": None},
        {"dir_classes": ["sideshore"]},
        {"min_kn": 5},
        {"min_go_hours": 1, "days_ahead": 7},
    ],
)
def test_offshore_never_alerts(dir_deg, rule):
    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_forecasts(db, dir_deg=dir_deg)
    if rule == {"min_go_hours": None}:
        seed_favorite(db, USER_A)
    else:
        seed_favorite(db, USER_A, **rule)
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.messages == []
    assert alert_rows(db) == []


# -- AC-7 -------------------------------------------------------------------------------------


def test_unverified_spot_gives_no_alerts():
    db = make_db(verified=False)
    seed_favorite(db, USER_A, min_kn=12)
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.messages == []
    assert alert_rows(db) == []
    assert result.ineligible == 1
    db2 = make_db(verified=True)
    seed_favorite(db2, USER_A, min_kn=12)
    assert len(run_alerts(db2, now=NOW, base_url=None).messages) == 1


# -- AC-4 -------------------------------------------------------------------------------------


def test_logs_contain_no_user_ids_or_bodies(caplog, capsys):
    caplog.set_level(logging.DEBUG)
    db = make_db(Recording)
    seed_spot(db, id="tweede-strand", verified=True)
    seed_forecasts(db, spot_id="tweede-strand")
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=20)
    seed_favorite(db, USER_A, spot_id="tweede-strand", earliest_local="24:00:00")
    db.reject_insert_for = USER_B
    db.writes.clear()
    result = run_alerts(db, now=NOW, base_url=None)
    out = capsys.readouterr()
    for user in (USER_A, USER_B):
        assert user not in caplog.text
        assert user not in out.out + out.err
    assert out.out == "" and out.err == ""
    for m in result.messages:
        for line in m.message.body.splitlines():
            assert line not in caplog.text
    assert USER_A not in "\n".join(result.errors)
    assert USER_B not in "\n".join(result.errors)
    assert result.skipped == 1
    assert result.write_errors == 1
    assert "alerts: users=2 " in caplog.text


def test_write_error_isolated():
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=20)
    db.reject_insert_for = USER_B
    result = run_alerts(db, now=NOW, base_url=None)
    assert [m.user_id for m in result.messages] == [USER_A]
    assert result.write_errors == 1
    assert result.errors == ("spot test-strand: DatabaseError (HTTP 409, code 23503)",)


def test_update_count_mismatch():
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    run_alerts(db, now=NOW, base_url=None)
    seed_forecasts(db, winds=SPLIT_WINDS)
    db.zero_updates = True
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.write_errors == 1
    assert result.messages == []
    assert result.errors == ("spot test-strand: DatabaseError",)


# -- content ----------------------------------------------------------------------------------


def test_kite_line_from_profile():
    db = make_db()
    seed_profile(db, USER_A, weight_kg=75, level="intermediate", quiver_m2=[9.0, 12.0])
    seed_favorite(db, USER_A, min_kn=12)
    result = run_alerts(db, now=NOW, base_url=None)
    assert "Kite: 9 m² (aan de grote kant, ideaal 6,9 m²)" in result.messages[0].message.body

    db2 = make_db()
    seed_profile(db2, USER_A, level="intermediate", quiver_m2=[9.0, 12.0])
    seed_favorite(db2, USER_A, min_kn=12)
    body = run_alerts(db2, now=NOW, base_url=None).messages[0].message.body
    assert not any(line.startswith("Kite:") for line in body.splitlines())


def test_go_url():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    result = run_alerts(db, now=NOW, base_url="https://example.org")
    assert result.messages[0].message.go_url == (
        "https://example.org/go?spot=test-strand"
        "&start=2026-07-15T10%3A00%3A00Z&end=2026-07-15T16%3A00%3A00Z"
    )
    db2 = make_db()
    seed_favorite(db2, USER_A, min_kn=12)
    assert run_alerts(db2, now=NOW, base_url="  ").messages[0].message.go_url is None


def test_invalid_base_url_fails_before_db():
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    db.selects.clear()
    db.writes.clear()
    with pytest.raises(ValueError, match="invalid APP_BASE_URL"):
        run_alerts(db, now=NOW, base_url="example.org")
    assert db.writes == []
    assert db.selects == []


# -- write order ------------------------------------------------------------------------------


def test_write_order_split():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    run_alerts(db, now=NOW, base_url=None)
    seed_forecasts(db, winds=SPLIT_WINDS)
    db.writes.clear()
    result = run_alerts(db, now=NOW, base_url=None)
    assert alert_writes(db) == [
        ("update", "alert_state"),
        ("insert", "alert_state"),
        ("delete", "alert_state"),
    ]
    assert [m.message.kind for m in result.messages] == ["worsened", "new"]
    rows = alert_rows(db)
    assert len(rows) == 2
    new_row = next(r for r in rows if datetime.fromisoformat(r["window_start"]) == at(14))
    assert result.messages[1].state_id == new_row["id"]


def test_write_order_merge():
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    seed_forecasts(db, winds=SPLIT_WINDS)
    run_alerts(db, now=NOW, base_url=None)
    rows = {datetime.fromisoformat(r["window_start"]): r["id"] for r in alert_rows(db)}
    assert set(rows) == {at(10), at(14)}
    seed_forecasts(db)
    db.update_calls.clear()
    result = run_alerts(db, now=NOW, base_url=None)
    assert db.update_calls == [(f"eq.{rows[at(14)]}", "expired"), (f"eq.{rows[at(10)]}", "active")]
    assert [m.message.kind for m in result.messages] == ["improved"]


def entry(start_h, end_h, status="active") -> AlertStateEntry:
    return AlertStateEntry.from_row(
        {
            "id": "x",
            "spot_id": SPOT,
            "window_start": at(start_h),
            "window_end": at(end_h),
            "status": status,
            "snapshot": snapshot(at(start_h), at(end_h)),
            "last_event": "new",
            "last_notified_at": None,
        }
    )


def test_update_rank():
    old = entry(10, 16)
    assert update_rank(old, entry(10, 16, "expired")) == 0
    assert update_rank(old, entry(10, 16, "cancelled")) == 0
    assert update_rank(old, entry(10, 13)) == 1
    assert update_rank(old, entry(10, 16)) == 1
    assert update_rank(old, entry(10, 18)) == 2
    assert update_rank(old, entry(11, 17)) == 2
    assert update_rank(entry(12, 14, "cancelled"), entry(10, 16)) == 2


# -- isolation --------------------------------------------------------------------------------


def test_skipped_favorite_does_not_stop_job():
    db = make_db()
    seed_profile(db, USER_A, default_max_kn=20)
    seed_favorite(db, USER_A, min_kn=25)
    seed_favorite(db, USER_B, earliest_local="24:00:00")
    seed_favorite(db, USER_C, min_kn=12)
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.skipped == 2
    assert [m.user_id for m in result.messages] == [USER_C]
    assert {r["user_id"] for r in alert_rows(db)} == {USER_C}


def test_broken_state_row_is_skipped_and_unchanged():
    db = make_db()
    seed_favorite(db, USER_C, min_kn=12)
    db.seed("alert_state", [state_row(USER_C, at(10), at(16), snap={})])
    before = alert_rows(db)
    db.writes.clear()
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.skipped == 1
    assert alert_rows(db) == before
    assert alert_writes(db) == [("delete", "alert_state")]


def test_broken_rule_without_forecast_is_skipped_not_ineligible():
    db = make_db(forecasts=False)
    seed_favorite(db, USER_A, earliest_local="24:00:00")
    result = run_alerts(db, now=NOW, base_url=None)
    assert (result.skipped, result.ineligible) == (1, 0)


def test_disabled_rule():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    run_alerts(db, now=NOW, base_url=None)
    db.update("alert_rules", {"enabled": False}, filters={"user_id": f"eq.{USER_A}"})
    seed_forecasts(db, winds={h: 6.0 for h in WINDS})
    before = alert_rows(db)
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.messages == []
    assert result.disabled == 1
    assert alert_rows(db) == before
    assert before[0]["status"] == "active"


def test_no_forecast_data_keeps_state():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    run_alerts(db, now=NOW, base_url=None)
    before = alert_rows(db)
    db.delete("forecast_hours", filters={"spot_id": f"eq.{SPOT}"})
    db.writes.clear()
    ctx = load_alert_context(db, now=NOW)
    assert ctx.inputs[SPOT].forecasts == []
    plan = plan_favorite(ctx.favorites[0], ctx.inputs.get(SPOT), now=NOW, base_url=None)
    assert plan.outcome == "ineligible"
    assert plan.detail == "no forecast data"
    result = run_alerts(db, now=NOW, base_url=None)
    assert (result.ineligible, result.skipped, result.write_errors) == (1, 0, 0)
    assert result.errors == ()
    assert result.messages == []
    assert alert_rows(db) == before
    assert alert_writes(db) == [("delete", "alert_state")]


def test_no_user_id_in_request_filters():
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=20)
    run_alerts(db, now=NOW, base_url=None)
    seed_forecasts(db, winds=SPLIT_WINDS)
    db.requests.clear()
    run_alerts(db, now=NOW, base_url=None)
    assert db.requests
    for op, table, filters in db.requests:
        assert USER_A not in filters
        assert USER_B not in filters
        if op == "select" and table == "profiles":
            assert filters == "None"
    state_ids = {r["id"] for r in alert_rows(db)}
    updates = [r for r in db.requests if r[:2] == ("update", "alert_state")]
    assert updates
    for _, _, filters in updates:
        (state_id,) = [i for i in state_ids if i in filters]
        assert filters == repr({"id": f"eq.{state_id}"})


# -- dry run, cleanup, loading ----------------------------------------------------------------


def test_dry_run():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    result = run_alerts(db, now=NOW, base_url=None, dry_run=True)
    assert len(result.messages) == 1
    assert result.messages[0].state_id is None
    assert db.writes == []

    run_alerts(db, now=NOW, base_url=None)
    old_id = alert_rows(db)[0]["id"]
    seed_forecasts(db, winds=SPLIT_WINDS)
    db.writes.clear()
    result = run_alerts(db, now=NOW, base_url=None, dry_run=True)
    assert [m.message.kind for m in result.messages] == ["worsened", "new"]
    assert [m.state_id for m in result.messages] == [old_id, None]
    assert db.writes == []


def test_cleanup_old_state():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    base = floor_hour(NOW)
    gone_end = base - timedelta(hours=49)
    kept_end = base - timedelta(hours=47)
    db.seed(
        "alert_state",
        [
            state_row(USER_A, gone_end - timedelta(hours=3), gone_end, "expired"),
            state_row(USER_A, kept_end - timedelta(hours=3), kept_end, "expired"),
        ],
    )
    result = run_alerts(db, now=NOW, base_url=None)
    assert result.deleted == 1
    ends = [
        datetime.fromisoformat(r["window_end"]) for r in alert_rows(db) if r["status"] == "expired"
    ]
    assert ends == [kept_end]


def test_no_favorites():
    db = make_db(Recording)
    db.selects.clear()
    result = run_alerts(db, now=NOW, base_url=None)
    assert result == AlertJobResult(users=0, events=0, messages=[])
    assert db.selects == ["favorites"]
    assert db.writes == [("delete", "alert_state")]


def test_state_loading():
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    rows = [
        state_row(USER_A, at(3), at(5), "active"),
        state_row(USER_A, at(4), at(6), "cancelled"),
        state_row(USER_A, at(10), at(16), "cancelled"),
        state_row(USER_A, at(10), at(16), "expired"),
    ]
    db.seed("alert_state", rows)
    ids = [r["id"] for r in alert_rows(db)]
    ctx = load_alert_context(db, now=NOW)
    assert [r["id"] for r in ctx.favorites[0].state_rows] == [ids[0], ids[2]]
    result = run_alerts(db, now=NOW, base_url=None)
    assert [m.message.kind for m in result.messages] == ["new"]
    assert result.messages[0].state_id == ids[2]
    assert len(alert_rows(db)) == 4


def test_no_bypass_parameters():
    for fn in (run_alerts, plan_favorite, load_alert_context):
        params = inspect.signature(fn).parameters
        assert not [
            n for n in params if any(w in n for w in ("offshore", "allow", "force", "unsafe"))
        ]
        assert params["now"].kind is inspect.Parameter.KEYWORD_ONLY
    from shakka.jobs.evaluate import run_evaluation

    params = inspect.signature(run_evaluation).parameters
    assert params["now"].kind is inspect.Parameter.KEYWORD_ONLY
    assert not [n for n in params if any(w in n for w in ("offshore", "allow", "force", "unsafe"))]


def test_naive_now():
    db = make_db()
    with pytest.raises(ValueError):
        run_alerts(db, now=datetime(2026, 7, 15, 6, 17), base_url=None)  # noqa: DTZ001
