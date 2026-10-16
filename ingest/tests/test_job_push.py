"""Loading targets, delivering one event, subscription upkeep, test push (WP-17)."""

import json
import logging
from datetime import datetime

import pytest
from pywebpush import WebPushException

from fakes import FakeSupabase
from job_fixtures import NOW, USER_A, USER_B
from push_fixtures import (
    DOWN,
    GONE,
    KEYS,
    OK,
    SUBJECT,
    FakeNotifier,
    FakeResponse,
    RecordingWebpush,
    endpoint,
    seed_subs,
    sub_row,
)
from shakka.db import DatabaseError
from shakka.domain.dedup import AlertEventKind
from shakka.domain.messages import AlertMessage
from shakka.jobs.push import (
    EventDelivery,
    deliver_event,
    load_all_targets,
    load_all_targets_checked,
    load_targets,
    send_test_push,
    update_subscriptions,
)
from shakka.notify.base import DeliveryResult, PushTarget
from shakka.notify.webpush import WebPushNotifier

MESSAGE = AlertMessage(spot_id="s", kind=AlertEventKind.NEW, title="Go: S", body="b", go_url=None)


class Recording(FakeSupabase):
    def __init__(self):
        super().__init__()
        self.selects: list[tuple[str, dict | None]] = []

    def select(self, table, **kwargs):
        self.selects.append((table, kwargs.get("filters")))
        return super().select(table, **kwargs)


def test_load_targets_order_and_cap():
    db = Recording()
    seed_subs(db, USER_A, 12)
    seed_subs(db, USER_B, 1)
    targets = load_targets(db, USER_A)
    assert len(targets) == 10
    assert [t.endpoint for t in targets] == [endpoint(USER_A, n) for n in range(1, 11)]
    db.selects.clear()
    grouped = load_all_targets(db)
    assert {u: len(t) for u, t in grouped.items()} == {USER_A: 10, USER_B: 1}
    assert db.selects == [("push_subscriptions", None)]


def test_from_row_skips_invalid():
    db = FakeSupabase()
    seed_subs(db, USER_A, 1)
    db.seed("push_subscriptions", [{**sub_row(USER_A, 2), "auth": ""}])
    assert [t.endpoint for t in load_targets(db, USER_A)] == [endpoint(USER_A, 1)]
    assert [len(v) for v in load_all_targets(db).values()] == [1]


def targets(n):
    return [PushTarget(f"sub-{i}", endpoint(USER_A, i), f"P{i}", f"A{i}") for i in range(1, n + 1)]


def notifier(results):
    return FakeNotifier({endpoint(USER_A, i): r for i, r in enumerate(results, start=1)})


def test_deliver_event_mixed():
    d = deliver_event(notifier([OK, DOWN]), targets(2), MESSAGE, tag="alert-1")
    assert d == EventDelivery(
        sent=1,
        failed=1,
        retryable=False,
        ok_ids=frozenset({"sub-1"}),
        gone_ids=frozenset(),
        failures=("HTTP 503",),
    )


def test_deliver_event_retryable_rules():
    assert deliver_event(notifier([DOWN, DOWN]), targets(2), MESSAGE, tag="t").retryable
    d = deliver_event(notifier([GONE, GONE]), targets(2), MESSAGE, tag="t")
    assert not d.retryable
    assert d.gone_ids == {"sub-1", "sub-2"}
    assert deliver_event(notifier([GONE, DOWN]), targets(2), MESSAGE, tag="t").retryable


def test_deliver_event_notifier_raises(caplog):
    caplog.set_level(logging.DEBUG)
    n = FakeNotifier(raises=RuntimeError(endpoint(USER_A, 1)))
    d = deliver_event(n, targets(1), MESSAGE, tag="t")
    assert d.failures == ("RuntimeError",)
    assert d.retryable
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "RuntimeError" in caplog.text
    assert "fcm.googleapis.com" not in caplog.text


def test_update_subscriptions():
    db = FakeSupabase()
    seed_subs(db, USER_A, 2)
    ids = [r["id"] for r in db.rows("push_subscriptions")]
    s1, s2 = ids
    result = update_subscriptions(db, gone={s1}, ok={s1, s2}, now=NOW)
    assert result.removed == 1
    assert result.errors == ()
    (row,) = db.rows("push_subscriptions")
    assert row["id"] == s2
    assert row["last_success_at"].startswith("2026-07-15T06:17:00")


def test_update_subscriptions_naive_now():
    with pytest.raises(ValueError):
        update_subscriptions(FakeSupabase(), gone=[], ok=[], now=datetime(2026, 1, 1))  # noqa: DTZ001


def test_update_subscriptions_batches():
    class Batches(FakeSupabase):
        def __init__(self):
            super().__init__()
            self.filters = []

        def delete(self, table, *, filters):
            self.filters.append(filters["id"])
            return 0

    db = Batches()
    update_subscriptions(db, gone={f"id-{n:03d}" for n in range(150)}, ok=(), now=NOW)
    assert [f.count(",") + 1 for f in db.filters] == [100, 50]


def test_update_subscriptions_error_continues():
    class Failing(FakeSupabase):
        def delete(self, table, *, filters):
            raise DatabaseError("x", status=503)

    db = Failing()
    seed_subs(db, USER_A, 2)
    s1, s2 = (r["id"] for r in db.rows("push_subscriptions"))
    result = update_subscriptions(db, gone={s1}, ok={s2}, now=NOW)
    assert result.errors == ("push_subscriptions: DatabaseError (HTTP 503)",)
    assert result.removed == 0
    rows = {r["id"]: r for r in db.rows("push_subscriptions")}
    assert rows[s2]["last_success_at"] is not None


def test_send_test_push():
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 3)
    ids = {r["endpoint"]: r["id"] for r in db.rows("push_subscriptions")}
    rec = RecordingWebpush(
        per_endpoint={
            eps[1]: WebPushException("x", response=FakeResponse(503)),
            eps[2]: WebPushException("x", response=FakeResponse(410)),
        }
    )
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=rec)
    results = send_test_push(db, n, USER_A, now=NOW)
    assert [(r.device, r.result.detail) for r in results] == [
        (1, "ok"),
        (2, "HTTP 503"),
        (3, "HTTP 410"),
    ]
    data = json.loads(rec.calls[0]["data"])
    assert data == {
        "title": "Shakka: testmelding",
        "body": "Meldingen werken op dit apparaat.",
        "url": "/",
        "tag": "shakka-test",
    }
    rows = {r["id"]: r for r in db.rows("push_subscriptions")}
    assert ids[eps[2]] not in rows
    assert rows[ids[eps[0]]]["last_success_at"] is not None
    assert rows[ids[eps[1]]].get("last_success_at") is None


def test_load_all_targets_checked_blocks_and_does_not_log_endpoint(caplog):
    caplog.set_level(logging.DEBUG)
    db = FakeSupabase()
    seed_subs(db, USER_A, 1)
    db.seed(
        "push_subscriptions",
        [{**sub_row(USER_A, 2), "endpoint": "https://evil.example.test/SECRET"}],
    )
    loaded = load_all_targets_checked(db)
    assert loaded.blocked == 1
    assert [len(v) for v in loaded.targets.values()] == [1]
    assert "evil.example.test" not in caplog.text and "SECRET" not in caplog.text
    assert "1 subscription(s) skipped" in caplog.text
    assert [t.endpoint for t in load_targets(db, USER_A)] == [endpoint(USER_A, 1)]


NO_RETRY = DeliveryResult(False, False, "HTTP 403", retryable=False)


def test_deliver_event_non_retryable_counts():
    d = deliver_event(notifier([NO_RETRY]), targets(1), MESSAGE, tag="t")
    assert d.retryable is False and d.non_retryable == 1
    d = deliver_event(notifier([DOWN]), targets(1), MESSAGE, tag="t")
    assert d.retryable is True and d.non_retryable == 0
    d = deliver_event(notifier([NO_RETRY, DOWN]), targets(2), MESSAGE, tag="t")
    assert d.retryable is True and d.non_retryable == 1
