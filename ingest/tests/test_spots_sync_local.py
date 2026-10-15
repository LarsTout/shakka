"""Optional: spot sync against the local Supabase stack (never the remote project).

Skipped unless SHAKKA_TEST_SUPABASE_URL (localhost only) and
SHAKKA_TEST_SUPABASE_SECRET_KEY are set.
"""

import os
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
import yaml

from shakka.db import SupabaseRest, in_filter
from shakka.domain.spot import SPOT_COLUMNS, SpotProfile
from shakka.spots.sync import sync_spots
from spot_fixtures import FULL_SPOT_YAML, MIN_SPOT_YAML

SKIP_REASON = "set SHAKKA_TEST_SUPABASE_URL (localhost only) and SHAKKA_TEST_SUPABASE_SECRET_KEY"
IDS = ["zzs-full", "zzs-min"]


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
        client.delete("spots", filters={"id": in_filter(IDS)})
        yield client
    finally:
        client.delete("spots", filters={"id": in_filter(IDS)})
        client.close()


def test_sync_against_local_stack(db: SupabaseRest):
    full = SpotProfile.model_validate(
        {**yaml.safe_load(FULL_SPOT_YAML)["spots"][0], "id": "zzs-full"}
    )
    minimal = SpotProfile.model_validate(
        {**yaml.safe_load(MIN_SPOT_YAML)["spots"][0], "id": "zzs-min"}
    )
    first = sync_spots(db, [full, minimal])
    assert first.upserted == 2
    assert "zzs-full" not in first.orphaned
    assert sync_spots(db, [full, minimal]).upserted == 0
    rows = db.select(
        "spots", columns=",".join(SPOT_COLUMNS), filters={"id": in_filter(IDS)}, order="id"
    )
    assert [SpotProfile.from_row(r) for r in rows] == [full, minimal]
