"""Session retention (WP-19): sessions, and by cascade their RSVPs, are removed 7 days after
ends_at through the service-only RPC purge_expired_sessions. Never reads sessions or RSVPs."""

import logging
from datetime import datetime, timedelta
from typing import Final

from shakka.db import SupabaseRest
from shakka.jobs.inputs import require_aware

PURGE_RPC: Final = "purge_expired_sessions"
SESSION_RETENTION: Final = timedelta(days=7)  # mirrors interval '7 days' in the migration

logger = logging.getLogger("shakka.jobs.sessions")


def purge_expired_sessions(db: SupabaseRest, *, now: datetime) -> int:
    """Call the RPC with p_now = now; returns the number of sessions removed.

    ValueError for a naive `now` (before any request) or a response that is not an int >= 0.
    DatabaseError from the client propagates.
    """
    require_aware(now)
    result = db.rpc(PURGE_RPC, {"p_now": now})
    if isinstance(result, bool) or not isinstance(result, int) or result < 0:
        raise ValueError("purge_expired_sessions: unexpected response")
    logger.info("sessions: purged=%d", result)
    return result
