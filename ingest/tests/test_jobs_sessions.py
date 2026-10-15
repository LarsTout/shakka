"""shakka.jobs.sessions: the retention RPC call (WP-19)."""

from datetime import timedelta

import pytest

from fakes import FakeSupabase
from job_fixtures import NOW
from shakka.db import DatabaseError, iso_utc
from shakka.jobs.sessions import SESSION_RETENTION, purge_expired_sessions


def test_purge_calls_rpc_with_iso_now():
    db = FakeSupabase()
    db.register_rpc("purge_expired_sessions", lambda args: 3)
    assert purge_expired_sessions(db, now=NOW) == 3
    assert db.rpc_calls == [("purge_expired_sessions", {"p_now": iso_utc(NOW)})]


def test_purge_naive_now_raises():
    db = FakeSupabase()
    with pytest.raises(ValueError):
        purge_expired_sessions(db, now=NOW.replace(tzinfo=None))
    assert db.rpc_calls == []


@pytest.mark.parametrize("response", [None, "3", True, -1, 1.5])
def test_purge_rejects_unexpected_response(response):
    db = FakeSupabase()
    db.register_rpc("purge_expired_sessions", lambda args: response)
    with pytest.raises(ValueError):
        purge_expired_sessions(db, now=NOW)


def test_purge_database_error_propagates():
    def boom(args):
        raise DatabaseError("boom", status=503)

    db = FakeSupabase()
    db.register_rpc("purge_expired_sessions", boom)
    with pytest.raises(DatabaseError):
        purge_expired_sessions(db, now=NOW)


def test_purge_with_builtin_fake():
    db = FakeSupabase()
    db.seed(
        "sessions",
        [
            {"id": "s-old", "ends_at": iso_utc(NOW - timedelta(days=8))},
            {"id": "s-edge", "ends_at": iso_utc(NOW - timedelta(days=7))},
            {"id": "s-new", "ends_at": iso_utc(NOW - timedelta(days=6))},
        ],
    )
    db.seed(
        "rsvps",
        [
            {"id": "r1", "session_id": "s-old"},
            {"id": "r2", "session_id": "s-old"},
            {"id": "r3", "session_id": "s-new"},
        ],
    )
    assert purge_expired_sessions(db, now=NOW) == 1
    assert {r["id"] for r in db.rows("sessions")} == {"s-edge", "s-new"}
    assert {r["id"] for r in db.rows("rsvps")} == {"r3"}


def test_retention_constant():
    assert timedelta(days=7) == SESSION_RETENTION
