"""I/O side of the usage report (WP-22): readers, operator push and run_usage_report."""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from fakes import FakeSupabase
from job_fixtures import USER_A, USER_C
from push_fixtures import DOWN, GONE, OK, FakeNotifier, endpoint, seed_subs
from shakka.db import DatabaseError
from shakka.domain.push import PushPayload
from shakka.domain.usage import BYTES_PER_MB
from shakka.jobs.usage import (
    OperatorDelivery,
    collect_usage_stats,
    delete_old_ingest_runs,
    deliver_operator_push,
    earlier_usage_counts,
    read_db_usage,
    read_open_meteo_usage,
    read_run_history,
    resolve_operator,
    run_usage_report,
)
from shakka.notify.base import DeliveryResult

MONDAY = datetime(2026, 7, 20, 6, 17, tzinfo=UTC)  # 08:17 local
WEDNESDAY = datetime(2026, 7, 15, 8, 17, tzinfo=UTC)  # 10:17 local
PAYLOAD = PushPayload(title="T", body="B", url="/", tag="shakka-usage-report")


def usage_row(day, source, calls):
    return {"day": day, "source": source, "calls": calls, "requests": 1}


def seed_usage(db, rows):
    db.seed("api_usage", [usage_row(*r) for r in rows])


def factory_for(notifier):
    return lambda: notifier


def run(db, now, notifier, operator=USER_A):
    return run_usage_report(
        db, now=now, operator_user_id=operator, notifier_factory=factory_for(notifier)
    )


def store_run(db, started_at, *, status="ok", steps=()):
    db.seed(
        "ingest_runs",
        [{"started_at": started_at, "status": status, "steps": list(steps)}],
    )


def usage_step(**counts):
    return {"name": "usage_report", "status": "ok", "counts": counts}


# -- readers ---------------------------------------------------------------------------------


def test_read_open_meteo_usage_sources_and_days():
    db = FakeSupabase()
    seed_usage(
        db,
        [
            ("2026-07-20", "open_meteo_forecast", 100.0),
            ("2026-07-20", "open_meteo_marine", 20.5),
            ("2026-07-20", "rws", 999.0),
            ("2026-07-18", "open_meteo_forecast", 300.0),
            ("2026-07-10", "open_meteo_forecast", 50.0),
            ("2026-06-30", "open_meteo_forecast", 7000.0),
        ],
    )
    usage = read_open_meteo_usage(db, now=MONDAY)
    assert usage.today == 120.5
    assert usage.max_day == 300.0
    assert usage.month == 470.5


def test_read_open_meteo_usage_month_boundary():
    db = FakeSupabase()
    seed_usage(
        db,
        [
            ("2026-07-29", "open_meteo_forecast", 900.0),
            ("2026-07-31", "open_meteo_forecast", 100.0),
            ("2026-08-01", "open_meteo_forecast", 40.0),
        ],
    )
    usage = read_open_meteo_usage(db, now=datetime(2026, 8, 1, 6, 17, tzinfo=UTC))
    assert usage.max_day == 900.0  # the week reaches into July
    assert usage.month == 40.0  # the month is August only
    assert usage.today == 40.0


def test_read_open_meteo_usage_empty():
    usage = read_open_meteo_usage(FakeSupabase(), now=MONDAY)
    assert (usage.today, usage.max_day, usage.month) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "response",
    [None, [], {"database_bytes": True, "tables": {}}, {"database_bytes": 1}, {"tables": {}},
     {"database_bytes": -1, "tables": {}}, {"database_bytes": 1, "tables": {"a": "x"}},
     {"database_bytes": 1, "tables": {"a": True}}],
)  # fmt: skip
def test_read_db_usage_bad_shape(response):
    db = FakeSupabase()
    db.register_rpc("db_usage", lambda args: response)
    with pytest.raises(ValueError, match="unexpected response"):
        read_db_usage(db)


def test_read_db_usage_builtin():
    db = FakeSupabase()
    db.database_bytes = 77
    usage = read_db_usage(db)
    assert usage.database_bytes == 77 and usage.table_rows["spots"] == 0


def test_read_run_history():
    db = FakeSupabase()
    alerts_ok = {"name": "alerts", "status": "ok", "counts": {"sent": 3, "failed": 1}}
    alerts_partial = {"name": "alerts", "status": "partial", "counts": {"sent": 2, "failed": 2}}
    tides_bad = {"name": "tides", "status": "partial", "counts": {}}
    skipped = {"name": "marine", "status": "skipped", "counts": {}}
    store_run(db, MONDAY - timedelta(days=1), steps=[alerts_ok, tides_bad])
    store_run(db, MONDAY - timedelta(days=2), status="partial", steps=[alerts_partial, skipped])
    store_run(db, MONDAY - timedelta(days=3), status="failed", steps=["junk", {"name": 5}])
    store_run(db, MONDAY - timedelta(days=4), status="running")
    store_run(db, MONDAY - timedelta(days=8), steps=[alerts_ok])  # outside the window
    store_run(db, MONDAY, steps=[alerts_ok])  # the current run: lt.now
    history = read_run_history(db, now=MONDAY)
    assert (history.ok, history.partial, history.failed) == (1, 1, 1)
    assert history.step_issues == {"tides": 1, "alerts": 1, "marine": 1}
    assert (history.push_sent, history.push_failed) == (5, 3)


def test_earlier_usage_counts_skips_current_run():
    db = FakeSupabase()
    store_run(db, MONDAY - timedelta(hours=1), steps=[usage_step(report_done=True)])
    store_run(db, MONDAY, steps=[usage_step(report_done=False)])
    store_run(db, MONDAY - timedelta(days=9), steps=[usage_step(report_done=True)])
    got = earlier_usage_counts(db, since=MONDAY - timedelta(days=1), now=MONDAY)
    assert got == [{"report_done": True}]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("{AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA}", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        (f" {USER_A} ", USER_A),
    ],
)
def test_resolve_operator(value, expected):
    assert resolve_operator(value) == expected


def test_resolve_operator_invalid():
    with pytest.raises(ValueError):
        resolve_operator("abc")


# -- operator push ---------------------------------------------------------------------------


def deliver(db, notifier, operator=USER_A):
    return deliver_operator_push(db, notifier, operator, PAYLOAD, now=MONDAY)


def test_deliver_no_operator_and_disabled():
    db = FakeSupabase()
    assert deliver(db, FakeNotifier(), None).status == "no_operator"
    assert deliver(db, None).status == "push_disabled"


def test_deliver_no_target():
    db = FakeSupabase()
    assert deliver(db, FakeNotifier(), USER_C).status == "no_target"


def test_deliver_sent_updates_last_success():
    db = FakeSupabase()
    seed_subs(db, USER_A, 2)
    seed_subs(db, USER_C, 1)
    notifier = FakeNotifier()
    delivery = deliver(db, notifier)
    assert delivery.status == "sent" and delivery.sent == 2
    assert {t.endpoint for t, _ in notifier.payload_calls} == {
        endpoint(USER_A, 1),
        endpoint(USER_A, 2),
    }
    stamped = [r for r in db.rows("push_subscriptions") if r.get("last_success_at")]
    assert len(stamped) == 2


def test_deliver_partial_failure_still_sent():
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 2)
    delivery = deliver(db, FakeNotifier({eps[1]: DOWN}))
    assert delivery.status == "sent" and (delivery.sent, delivery.failed) == (1, 1)
    assert delivery.push_failures == {"HTTP 503": 1}


def test_deliver_all_gone_is_no_target_and_removes():
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 2)
    delivery = deliver(db, FakeNotifier({eps[0]: GONE, eps[1]: GONE}))
    assert delivery.status == "no_target" and delivery.removed == 2
    assert db.rows("push_subscriptions") == []


def test_deliver_all_down_is_retryable():
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 2)
    delivery = deliver(db, FakeNotifier({eps[0]: DOWN, eps[1]: DOWN}))
    assert delivery.status == "failed" and delivery.retryable is True


def test_deliver_non_retryable_failure_is_final():
    db = FakeSupabase()
    (ep,) = seed_subs(db, USER_A, 1)
    forbidden = DeliveryResult(False, False, "HTTP 403", retryable=False)
    delivery = deliver(db, FakeNotifier({ep: forbidden}))
    assert delivery.status == "failed" and delivery.retryable is False


def test_deliver_notifier_raising_is_a_failure():
    db = FakeSupabase()
    seed_subs(db, USER_A, 1)
    delivery = deliver(db, FakeNotifier(raises=RuntimeError("boom")))
    assert delivery.status == "failed"
    assert delivery.push_failures == {"RuntimeError": 1}


def test_deliver_database_error_on_load():
    class Broken(FakeSupabase):
        def select(self, table, **kwargs):
            raise DatabaseError("x", status=503)

    delivery = deliver(Broken(), FakeNotifier())
    assert delivery == OperatorDelivery(
        "failed", retryable=True, push_failures={"DatabaseError": 1}
    )


# -- run_usage_report ------------------------------------------------------------------------


class Counting(FakeSupabase):
    def __init__(self):
        super().__init__()
        self.selected: list[str] = []

    def select(self, table, **kwargs):
        self.selected.append(table)
        return super().select(table, **kwargs)


def test_quiet_hour_reads_little_and_writes_nothing():  # E29
    db = Counting()
    seed_subs(db, USER_A, 1)
    notifier = FakeNotifier()
    result = run(db, WEDNESDAY, notifier)
    assert result.status == "ok" and result.report_due is False
    assert result.delivery is None and notifier.payload_calls == []
    assert db.writes == []
    assert "ingest_runs" not in db.selected


def test_monday_before_window_is_not_due():  # E30
    result = run(FakeSupabase(), datetime(2026, 7, 20, 5, 17, tzinfo=UTC), FakeNotifier())
    assert result.report_due is False


def test_report_sent_once(caplog):  # E31, E32
    caplog.set_level(logging.DEBUG)
    db = FakeSupabase()
    seed_subs(db, USER_A, 2)
    store_run(db, MONDAY - timedelta(days=90, hours=1))
    notifier = FakeNotifier()
    result = run(db, MONDAY, notifier)
    assert result.report_due and result.report_done and result.status == "ok"
    assert result.delivery is not None and result.delivery.sent == 2
    assert result.report is not None and result.report.startswith("Shakka gebruiksrapport")
    assert result.runs_deleted == 1
    assert len(notifier.payload_calls) == 2
    store_run(db, MONDAY, steps=[usage_step(report_done=True)])
    later = run(db, MONDAY + timedelta(hours=1), notifier)
    assert later.report_due is False
    assert len(notifier.payload_calls) == 2
    assert endpoint(USER_A, 1) not in caplog.text and USER_A not in caplog.text


def test_report_retried_after_transient_failure():  # E33
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 2)
    notifier = FakeNotifier({eps[0]: DOWN, eps[1]: DOWN})
    result = run(db, MONDAY, notifier)
    assert result.report_done is False and result.status == "partial"
    assert any("retried next run" in n for n in result.notes)
    store_run(db, MONDAY, steps=[usage_step(report_done=False)])
    notifier.set_result(eps[0], OK)
    again = run(db, MONDAY + timedelta(hours=1), notifier)
    assert again.report_due and again.report_done


def test_report_with_gone_devices():  # E34
    db = FakeSupabase()
    eps = seed_subs(db, USER_A, 2)
    result = run(db, MONDAY, FakeNotifier({eps[0]: GONE, eps[1]: GONE}))
    assert result.report_done and result.delivery.status == "no_target"
    assert db.rows("push_subscriptions") == []


def test_no_operator_stores_report():  # E35
    result = run(FakeSupabase(), MONDAY, FakeNotifier(), operator=None)
    assert result.status == "ok" and result.report_done
    assert result.report is not None
    assert result.delivery.status == "no_operator"
    assert result.notes == (
        "OPERATOR_USER_ID not set: usage push not sent (report stored in ingest_runs)",
    )


def test_invalid_operator_is_partial_without_echo(caplog):  # E36
    caplog.set_level(logging.DEBUG)
    result = run(FakeSupabase(), MONDAY, FakeNotifier(), operator="not-a-uuid-12345")
    assert result.status == "partial" and result.delivery.status == "invalid_operator"
    assert "not-a-uuid-12345" not in caplog.text
    assert all("not-a-uuid" not in n for n in result.notes)


def test_operator_without_subscription():  # E37
    result = run(FakeSupabase(), MONDAY, FakeNotifier(), operator=USER_C)
    assert result.status == "ok" and result.delivery.status == "no_target" and result.report_done


def test_threshold_warning_once_a_day():  # E38
    db = FakeSupabase()
    db.database_bytes = 310 * BYTES_PER_MB
    seed_subs(db, USER_A, 1)
    notifier = FakeNotifier()
    result = run(db, WEDNESDAY, notifier)
    assert result.warning_notified and result.report_due is False
    (call,) = notifier.payload_calls
    assert call[1].tag == "shakka-usage-warning"
    assert result.warnings == ("Database 310 MB, boven 300 MB",)
    store_run(db, WEDNESDAY, steps=[usage_step(warning_notified=True)])
    again = run(db, WEDNESDAY + timedelta(hours=1), notifier)
    assert len(notifier.payload_calls) == 1
    assert again.warnings and again.delivery is None
    next_day = run(db, WEDNESDAY + timedelta(days=1), notifier)
    assert len(notifier.payload_calls) == 2 and next_day.warning_notified


def test_warning_outside_window_is_not_pushed():  # E39
    db = FakeSupabase()
    db.database_bytes = 310 * BYTES_PER_MB
    seed_subs(db, USER_A, 1)
    notifier = FakeNotifier()
    result = run(db, datetime(2026, 7, 15, 21, 17, tzinfo=UTC), notifier)  # 23:17 local
    assert result.warnings and notifier.payload_calls == []
    assert result.warning_notified is False


def test_monday_with_warning_sends_one_push():  # E40
    db = FakeSupabase()
    db.database_bytes = 310 * BYTES_PER_MB
    seed_subs(db, USER_A, 1)
    notifier = FakeNotifier()
    result = run(db, MONDAY, notifier)
    assert len(notifier.payload_calls) == 1
    assert notifier.payload_calls[0][1].tag == "shakka-usage-report"
    assert result.warning_notified is True
    assert notifier.payload_calls[0][1].title == "Shakka weekrapport: let op"


def test_db_usage_missing_function():  # E41
    class NoRpc(FakeSupabase):
        def rpc(self, function, args=None):
            raise DatabaseError("x", status=404, code="PGRST202")

    result = run(NoRpc(), WEDNESDAY, FakeNotifier())
    assert result.status == "partial"
    assert result.errors == ("db_usage: DatabaseError (HTTP 404, code PGRST202)",)
    assert result.stats.database_bytes is None


def test_api_usage_unreadable():  # E42
    class Broken(FakeSupabase):
        def select(self, table, **kwargs):
            if table == "api_usage":
                raise DatabaseError("x", status=500)
            return super().select(table, **kwargs)

    db = Broken()
    db.database_bytes = 310 * BYTES_PER_MB
    result = run(db, WEDNESDAY, FakeNotifier())
    assert result.status == "partial" and result.stats.open_meteo_today is None
    assert result.errors == ("api_usage: DatabaseError (HTTP 500)",)
    assert result.warnings == ("Database 310 MB, boven 300 MB",)


def test_ingest_runs_unreadable_on_monday():  # E43
    class Broken(FakeSupabase):
        def select(self, table, **kwargs):
            if table == "ingest_runs":
                raise DatabaseError("x", status=500)
            return super().select(table, **kwargs)

    notifier = FakeNotifier()
    result = run(Broken(), MONDAY, notifier)
    assert result.report_due is False and result.status == "partial"
    assert notifier.payload_calls == []


def test_notifier_factory_value_error_disables_push():  # E44
    def broken():
        raise ValueError("incomplete")

    db = FakeSupabase()
    seed_subs(db, USER_A, 1)
    result = run_usage_report(db, now=MONDAY, operator_user_id=USER_A, notifier_factory=broken)
    assert result.delivery.status == "push_disabled"
    assert "push configuration invalid: usage push not sent" in result.notes
    assert result.status == "ok"


def test_operator_in_braces_works():  # E55
    db = FakeSupabase()
    seed_subs(db, USER_A, 1)
    notifier = FakeNotifier()
    result = run(db, MONDAY, notifier, operator="{" + USER_A.upper() + "}")
    assert result.delivery.status == "sent"


def test_collect_with_history_fills_runs():
    db = FakeSupabase()
    store_run(db, MONDAY - timedelta(hours=2))
    stats, errors = collect_usage_stats(db, now=MONDAY, with_history=True)
    assert errors == [] and stats.runs_ok == 1


def test_delete_old_ingest_runs_boundary():
    db = FakeSupabase()
    store_run(db, MONDAY - timedelta(days=91))
    store_run(db, MONDAY - timedelta(days=89))
    assert delete_old_ingest_runs(db, now=MONDAY) == 1
    assert len(db.rows("ingest_runs")) == 1
