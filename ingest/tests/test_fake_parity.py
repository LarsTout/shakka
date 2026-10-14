"""Optional parity check: FILTER_CASES against real PostgREST on the local Supabase stack.

Skipped unless SHAKKA_TEST_SUPABASE_URL (localhost only) and SHAKKA_TEST_SUPABASE_SECRET_KEY are
set, so it can never touch the remote project.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest

from fake_cases import FILTER_CASES, PARITY_IDS, PARITY_ROWS, FilterCase
from shakka.db import SupabaseRest, in_filter

SKIP_REASON = "set SHAKKA_TEST_SUPABASE_URL (localhost only) and SHAKKA_TEST_SUPABASE_SECRET_KEY"


@pytest.fixture(scope="module")
def db() -> Iterator[SupabaseRest]:
    url = os.environ.get("SHAKKA_TEST_SUPABASE_URL")
    key = os.environ.get("SHAKKA_TEST_SUPABASE_SECRET_KEY")
    if not url or not key:
        pytest.skip(SKIP_REASON)
    if urlsplit(url).hostname not in ("127.0.0.1", "localhost"):
        pytest.skip(SKIP_REASON)
    client = SupabaseRest(url, key)
    try:
        client.delete("spots", filters={"id": in_filter(PARITY_IDS)})
        client.insert("spots", PARITY_ROWS)
        yield client
    finally:
        client.delete("spots", filters={"id": in_filter(PARITY_IDS)})
        client.close()


@pytest.mark.parametrize("case", FILTER_CASES, ids=[c.name for c in FILTER_CASES])
def test_filter_case_matches_postgrest(db: SupabaseRest, case: FilterCase):
    filters: dict[str, str | list[str]] = dict(case.filters)
    scope = in_filter(PARITY_IDS)
    existing = filters.get("id")
    if existing is None:
        filters["id"] = scope
    else:
        filters["id"] = [existing] if isinstance(existing, str) else list(existing)
        filters["id"].append(scope)
    rows = db.select("spots", filters=filters, order=case.order or "id", limit=case.limit)
    assert [row["id"] for row in rows] == case.expected


def test_timestamp_response_form(db: SupabaseRest):
    (row,) = db.select("spots", columns="id,updated_at", filters={"id": "eq.zzp-b"})
    assert datetime.fromisoformat(row["updated_at"]) == datetime(2026, 10, 14, 12, tzinfo=UTC)
