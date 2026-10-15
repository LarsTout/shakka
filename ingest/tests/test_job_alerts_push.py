"""Alert job with push delivery (WP-17 AC-4, AC-5, AC-8, all-or-nothing, ids, last_notified_at)."""

import logging
import uuid
from datetime import timedelta

import pytest

import shakka.jobs.alerts
import shakka.jobs.push
from fakes import FakeSupabase
from job_fixtures import (
    NOW,
    USER_A,
    USER_B,
    WINDS,
    alert_rows,
    seed_favorite,
    seed_forecasts,
    seed_spot,
)
from push_fixtures import (
    DOWN,
    GONE,
    KEYS,
    OK,
    SUBJECT,
    FakeNotifier,
    endpoint,
    seed_subs,
)
from shakka.db import DatabaseError
from shakka.jobs.alerts import run_alerts
from shakka.notify.webpush import WebPushNotifier
from test_job_alerts import make_db

SPLIT_WINDS = WINDS | {13: 13.0}
FIXED_ID = "aaaaaaaa-0000-4000-8000-000000000001"


class Recording(FakeSupabase):
    def __init__(self):
        super().__init__()
        self.requests: list[tuple[str, str, dict | None]] = []

    def select(self, table, *, columns="*", filters=None, order=None, limit=None):
        self.requests.append(("select", table, filters))
        return super().select(table, columns=columns, filters=filters, order=order, limit=limit)

    def update(self, table, values, *, filters):
        self.requests.append(("update", table, filters))
        return super().update(table, values, filters=filters)

    def delete(self, table, *, filters):
        self.requests.append(("delete", table, filters))
        return super().delete(table, filters=filters)


def setup(cls=FakeSupabase, subs=1, **notifier_kwargs):
    db = make_db(cls)
    seed_favorite(db, USER_A, min_kn=12)
    eps = seed_subs(db, USER_A, subs) if subs else []
    notifier = FakeNotifier(**notifier_kwargs)
    return db, eps, notifier


def run(db, notifier, **kwargs):
    return run_alerts(db, now=NOW, base_url=None, notifiers={"webpush": notifier}, **kwargs)


def test_new_event_delivered_with_state_tag():
    db, _, n = setup()
    result = run(db, n)
    (row,) = alert_rows(db)
    (call,) = n.calls
    assert call.tag == f"alert-{row['id']}"
    assert call.kind == "new"
    assert row["last_notified_at"].startswith("2026-07-15T06:17:00")
    assert row["last_event"] == "new"
    assert result.sent == 1
    assert result.push_enabled is True
    assert result.messages[0].state_id == row["id"]
    uuid.UUID(row["id"])


def test_ids_assigned_before_insert(monkeypatch):
    monkeypatch.setattr(shakka.jobs.alerts, "_new_state_id", lambda: FIXED_ID)
    db, _, n = setup()
    run(db, n)
    assert alert_rows(db)[0]["id"] == FIXED_ID
    assert n.calls[0].tag == f"alert-{FIXED_ID}"
    db2 = make_db()
    seed_favorite(db2, USER_A, min_kn=12)
    run_alerts(db2, now=NOW, base_url=None)
    assert alert_rows(db2)[0]["id"] == FIXED_ID


def test_two_subscriptions_one_fails():
    db, eps, _ = setup(subs=2)
    n = FakeNotifier({eps[1]: DOWN})
    result = run(db, n)
    assert len(n.calls) == 2
    assert (result.sent, result.failed, result.deferred) == (1, 1, 0)
    assert alert_rows(db)[0]["last_notified_at"].startswith("2026-07-15T06:17:00")
    assert result.push_failures == {"HTTP 503": 1}
    rows = {r["endpoint"]: r for r in db.rows("push_subscriptions")}
    assert rows[eps[0]]["last_success_at"] is not None
    assert rows[eps[1]].get("last_success_at") is None


def test_no_subscriptions():
    db, _, n = setup(subs=0)
    result = run(db, n)
    assert result.no_target == 1
    assert result.sent == result.failed == 0
    (row,) = alert_rows(db)
    assert row["last_notified_at"] is None
    assert len(result.messages) == 1
    assert n.calls == []


def test_gone_subscription_removed():
    db, eps, _ = setup()
    n = FakeNotifier({eps[0]: GONE})
    result = run(db, n)
    assert (result.failed, result.removed) == (1, 1)
    assert db.rows("push_subscriptions") == []
    (row,) = alert_rows(db)
    assert (row["status"], row["last_event"], row["last_notified_at"]) == ("active", "new", None)
    n.calls.clear()
    second = run(db, n)
    assert second.events == 0
    assert n.calls == []


def test_retryable_failure_keeps_state():
    db, eps, _ = setup()
    n = FakeNotifier({eps[0]: DOWN})
    result = run(db, n)
    assert result.deferred == 1
    assert result.messages == []
    assert alert_rows(db) == []
    assert ("insert", "alert_state") not in db.writes
    n.set_result(eps[0], OK)
    again = run(db, n)
    assert len(n.calls) == 2
    assert again.deferred == 0
    (row,) = alert_rows(db)
    assert row["last_notified_at"].startswith("2026-07-15T06:17:00")


def split_setup():
    db, eps, n = setup()
    run(db, n)
    (first,) = alert_rows(db)
    seed_forecasts(db, winds=SPLIT_WINDS, fetched_at=NOW - timedelta(minutes=7))
    db.writes.clear()
    n.calls.clear()
    return db, eps, n, first


def test_all_or_nothing_on_split():
    db, eps, n, first = split_setup()
    n.set_result(eps[0], [OK, DOWN])
    result = run(db, n)
    assert len(n.calls) == 2
    assert result.deferred == 1
    assert not [w for w in db.writes if w[1] == "alert_state" and w[0] != "delete"]
    assert alert_rows(db) == [first]
    n.set_result(eps[0], OK)
    n.calls.clear()
    db.writes.clear()
    run(db, n)
    kinds = {c.kind: c for c in n.calls}
    assert kinds["worsened"].tag == f"alert-{first['id']}"
    assert kinds["new"].tag != f"alert-{first['id']}"
    assert [w for w in db.writes if w[1] == "alert_state"] == [
        ("update", "alert_state"),
        ("insert", "alert_state"),
        ("delete", "alert_state"),
    ]


def test_stop_after_first_retryable_event():
    db, eps, n, _ = split_setup()
    n.set_result(eps[0], DOWN)
    run(db, n)
    assert len(n.calls) == 1


def test_cancelled_reuses_tag():
    db, _, n = setup()
    run(db, n)
    (first,) = alert_rows(db)
    seed_forecasts(db, winds={h: 6.0 for h in WINDS}, fetched_at=NOW - timedelta(minutes=7))
    run(db, n)
    last = n.calls[-1]
    assert last.kind == "cancelled"
    assert last.tag == f"alert-{first['id']}"
    (row,) = alert_rows(db)
    assert row["status"] == "cancelled"
    assert row["last_notified_at"].startswith("2026-07-15T06:17:00")


def test_dry_run_with_notifiers():
    db, _, n = setup(Recording)
    db.writes.clear()
    db.requests.clear()
    result = run(db, n, dry_run=True)
    assert n.calls == []
    assert db.writes == []
    assert result.push_enabled is False
    assert not [r for r in db.requests if r[1] == "push_subscriptions"]
    assert result.messages[0].state_id is None


@pytest.mark.parametrize("notifiers", [None, {}, {"other": FakeNotifier()}])
def test_without_notifier_is_m1(notifiers):
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    seed_subs(db, USER_A, 1)
    db.requests.clear()
    result = run_alerts(db, now=NOW, base_url=None, notifiers=notifiers)
    assert result.push_enabled is False
    assert (result.sent, result.failed, result.no_target, result.deferred, result.removed) == (
        0,
        0,
        0,
        0,
        0,
    )
    assert result.push_failures == {}
    assert not [r for r in db.requests if r[1] == "push_subscriptions"]
    (row,) = alert_rows(db)
    assert (row["status"], row["last_event"], row["last_notified_at"]) == ("active", "new", None)
    assert len(result.messages) == 1
    assert result.messages[0].message.kind == "new"


def test_targets_loaded_once_without_user_filter():
    db = make_db(Recording)
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=20)
    seed_subs(db, USER_A, 1)
    seed_subs(db, USER_B, 1)
    db.requests.clear()
    run(db, FakeNotifier())
    selects = [r for r in db.requests if r[:2] == ("select", "push_subscriptions")]
    assert len(selects) == 1
    assert selects[0][2] is None
    for _, _, filters in db.requests:
        assert USER_A not in repr(filters)
        assert USER_B not in repr(filters)


def test_notifier_exception_retryable(caplog):
    caplog.set_level(logging.DEBUG)
    db, eps, _ = setup()
    n = FakeNotifier(raises=RuntimeError(eps[0]))
    result = run(db, n)
    assert result.deferred == 1
    assert eps[0] not in caplog.text


def test_max_targets():
    db, _, n = setup(subs=12)
    run(db, n)
    assert len(n.calls) == 10


def test_subscription_update_error():
    class Failing(FakeSupabase):
        def delete(self, table, *, filters):
            if table == "push_subscriptions":
                raise DatabaseError("x", status=503)
            return super().delete(table, filters=filters)

    db, eps, _ = setup(Failing)
    n = FakeNotifier({eps[0]: GONE})
    result = run(db, n)
    assert result.write_errors == 1
    assert "push_subscriptions: DatabaseError (HTTP 503)" in result.errors
    assert len(alert_rows(db)) == 1


def test_success_then_gone_same_run():
    db = FakeSupabase()
    for spot in ("test-strand", "tweede-strand"):
        seed_spot(db, id=spot, verified=True)
        seed_forecasts(db, spot_id=spot)
        seed_favorite(db, USER_A, spot_id=spot, min_kn=12)
    (ep,) = seed_subs(db, USER_A, 1)
    n = FakeNotifier({ep: [OK, GONE]})
    result = run(db, n)
    assert len(n.calls) == 2
    assert (result.sent, result.failed, result.removed) == (1, 1, 1)
    assert db.rows("push_subscriptions") == []
    assert not [w for w in db.writes if w == ("update", "push_subscriptions")]


def test_load_targets_reexported():
    assert shakka.jobs.alerts.load_targets is shakka.jobs.push.load_targets


def test_no_endpoints_keys_or_user_ids_in_logs(caplog, capsys):
    caplog.set_level(logging.DEBUG)
    db = make_db()
    seed_favorite(db, USER_A, min_kn=12)
    ep = endpoint(USER_A, 1)
    db.seed(
        "push_subscriptions",
        [
            {
                "user_id": USER_A,
                "endpoint": ep,
                "p256dh": "P256DH-SECRET-456",
                "auth": "AUTH-SECRET-789",
            }
        ],
    )
    secrets = [ep, "P256DH-SECRET-456", "AUTH-SECRET-789", KEYS.private_key, SUBJECT, USER_A]

    def failing(**kwargs):
        raise Exception(f"{ep} P256DH-SECRET-456 AUTH-SECRET-789 {KEYS.private_key}")

    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=failing)
    result = run(db, n)
    out = capsys.readouterr()
    haystacks = [caplog.text, out.out, out.err, "\n".join(result.errors), str(result.push_failures)]
    for text in haystacks:
        for secret in secrets:
            assert secret not in text
    assert result.deferred == 1
