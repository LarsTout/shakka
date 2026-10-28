"""Alert job with quiet hours (WP-30 AC-3, AC-4): nothing delivered, nothing stored."""

import logging
from datetime import UTC, datetime

from job_fixtures import (
    SPOT,
    USER_A,
    USER_B,
    WINDS,
    alert_rows,
    seed_favorite,
    seed_forecasts,
    seed_profile,
)
from push_fixtures import FakeNotifier, seed_subs
from shakka.jobs.alerts import run_alerts
from test_job_alerts import make_db
from test_job_alerts_push import SPLIT_WINDS

T0 = datetime(2026, 7, 14, 19, 17, tzinfo=UTC)  # 21:17 local
T1 = datetime(2026, 7, 14, 21, 17, tzinfo=UTC)  # 23:17 local, quiet
T1B = datetime(2026, 7, 14, 22, 17, tzinfo=UTC)  # 00:17 local, quiet
T2 = datetime(2026, 7, 15, 5, 17, tzinfo=UTC)  # 07:17 local, quiet hours over
FLAT = {h: 6.0 for h in WINDS}


def quiet_profile(db, user_id=USER_A, **cols):
    values = {
        "default_min_kn": None,
        "default_max_kn": None,
        "quiet_from": "22:00:00",
        "quiet_until": "07:00:00",
    }
    seed_profile(db, user_id, **(values | cols))


def go(db, t, winds=WINDS, notifier=None, **kwargs):
    seed_forecasts(db, winds=winds, fetched_at=t.replace(minute=10))
    notifiers = None if notifier is None else {"webpush": notifier}
    return run_alerts(db, now=t, base_url=None, notifiers=notifiers, **kwargs)


def state_writes(db):
    return [w for w in db.writes if w[1] == "alert_state" and w[0] != "delete"]


def kinds(notifier):
    return [c.kind for c in notifier.calls]


def test_quiet_user_gets_nothing_then_one_new():
    db = make_db()
    quiet_profile(db)
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=12)
    (ep_a,) = seed_subs(db, USER_A, 1)
    (ep_b,) = seed_subs(db, USER_B, 1)
    n = FakeNotifier()
    r1 = go(db, T1, notifier=n)
    assert [c.endpoint for c in n.calls] == [ep_b]
    assert r1.quiet == 1
    assert {r["user_id"] for r in alert_rows(db)} == {USER_B}
    n.calls.clear()
    r2 = go(db, T2, notifier=n)
    assert [(c.endpoint, c.kind) for c in n.calls] == [(ep_a, "new")]
    assert r2.quiet == 0


def test_quiet_keeps_state_and_reports_improved_once():
    db = make_db()
    quiet_profile(db)
    seed_favorite(db, USER_A, min_kn=12)
    seed_subs(db, USER_A, 1)
    n = FakeNotifier()
    go(db, T0, winds=SPLIT_WINDS, notifier=n)
    assert kinds(n) == ["new", "new"]
    before = [dict(r) for r in alert_rows(db)]
    n.calls.clear()
    db.writes.clear()
    result = go(db, T1, winds=WINDS, notifier=n)
    assert n.calls == [] and result.events == 0 and result.quiet == 1
    assert alert_rows(db) == before
    assert state_writes(db) == []
    go(db, T2, winds=WINDS, notifier=n)
    assert kinds(n) == ["improved"]


def test_quiet_applies_in_dry_run_and_without_notifier():
    db = make_db()
    quiet_profile(db)
    seed_favorite(db, USER_A, min_kn=12)
    dry = go(db, T1, dry_run=True)
    assert dry.messages == [] and dry.quiet == 1
    plain = go(db, T1)
    assert plain.messages == [] and plain.quiet == 1
    assert alert_rows(db) == []
    assert state_writes(db) == []


def test_invalid_quiet_hours_skips_favorite():
    db = make_db()
    quiet_profile(db, quiet_until=None)
    seed_favorite(db, USER_A, min_kn=12)
    seed_subs(db, USER_A, 1)
    n = FakeNotifier()
    result = go(db, T1, notifier=n)
    assert result.skipped == 1 and result.quiet == 0
    assert result.errors == (f"spot {SPOT}: ValueError: invalid quiet hours",)
    assert all(USER_A not in e for e in result.errors)
    assert n.calls == [] and alert_rows(db) == []


def test_quiet_log_has_counts_only(caplog):
    db = make_db()
    quiet_profile(db)
    seed_favorite(db, USER_A, min_kn=12)
    with caplog.at_level(logging.INFO):
        go(db, T1)
    assert "quiet=1" in caplog.text
    assert USER_A not in caplog.text


def test_no_profile_or_no_quiet_hours_behaves_as_before():
    db = make_db()
    quiet_profile(db, quiet_from=None, quiet_until=None)
    seed_favorite(db, USER_A, min_kn=12)
    seed_favorite(db, USER_B, min_kn=12)
    result = go(db, T1)
    assert result.quiet == 0 and result.events == 2


def test_window_born_and_gone_in_quiet_gives_nothing():
    db = make_db()
    quiet_profile(db)
    seed_favorite(db, USER_A, min_kn=12)
    seed_subs(db, USER_A, 1)
    n = FakeNotifier()
    go(db, T1, winds=WINDS, notifier=n)
    go(db, T1B, winds=FLAT, notifier=n)
    go(db, T2, winds=FLAT, notifier=n)
    assert n.calls == [] and alert_rows(db) == []


def test_cancel_and_return_in_quiet_gives_nothing():
    db = make_db()
    quiet_profile(db)
    seed_favorite(db, USER_A, min_kn=12)
    seed_subs(db, USER_A, 1)
    n = FakeNotifier()
    go(db, T0, winds=WINDS, notifier=n)
    assert kinds(n) == ["new"]
    after_t0 = [dict(r) for r in alert_rows(db)]
    n.calls.clear()
    for t, winds in ((T1, FLAT), (T1B, WINDS)):
        result = go(db, t, winds=winds, notifier=n)
        assert result.messages == [] and n.calls == []
        assert alert_rows(db) == after_t0
    result = go(db, T2, winds=WINDS, notifier=n)
    assert result.events == 0 and n.calls == []
