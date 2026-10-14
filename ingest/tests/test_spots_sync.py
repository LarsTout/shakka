"""Sync tests (AC-5) against FakeSupabase."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
import yaml

from fakes import FakeSupabase
from shakka.domain.spot import SpotProfile
from shakka.spots.sync import sync_spots
from spot_fixtures import FULL_SPOT_YAML, MIN_SPOT_YAML


class RecordingFake(FakeSupabase):
    """FakeSupabase that also records the payload of every upsert."""

    def __init__(self) -> None:
        super().__init__()
        self.upsert_payloads: list[tuple[str, list[dict[str, Any]]]] = []

    def upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str) -> int:
        self.upsert_payloads.append((table, [dict(r) for r in rows]))
        return super().upsert(table, rows, on_conflict=on_conflict)


def spot(text: str) -> SpotProfile:
    return SpotProfile.model_validate(yaml.safe_load(text)["spots"][0])


FULL = spot(FULL_SPOT_YAML)
MINIMAL = spot(MIN_SPOT_YAML)


def row_of(db: FakeSupabase, spot_id: str) -> dict[str, Any]:
    return next(r for r in db.rows("spots") if r["id"] == spot_id)


def test_first_sync_upserts_all():
    db = RecordingFake()
    result = sync_spots(db, [FULL, MINIMAL])
    assert result.upserted == 2
    assert result.orphaned == []
    assert db.upserts == [("spots", "id")]
    assert db.upsert_payloads == [("spots", [FULL.to_row(), MINIMAL.to_row()])]
    assert all(kind != "delete" for kind, _ in db.writes)
    for s in (FULL, MINIMAL):
        stored = row_of(db, s.id)
        assert {k: stored[k] for k in s.to_row()} == s.to_row()


def test_orphan_reported_not_deleted():
    db = RecordingFake()
    db.seed("spots", [{"id": "zz-orphan", "name": "Orphan"}])
    result = sync_spots(db, [MINIMAL])
    assert result.orphaned == ["zz-orphan"]
    assert any(r["id"] == "zz-orphan" for r in db.rows("spots"))


def test_second_sync_is_noop():
    db = RecordingFake()
    sync_spots(db, [FULL, MINIMAL])
    writes, payloads = list(db.writes), list(db.upsert_payloads)
    result = sync_spots(db, [FULL, MINIMAL])
    assert result.upserted == 0
    assert db.writes == writes
    assert db.upsert_payloads == payloads


def test_only_changed_upserted():
    db = RecordingFake()
    sync_spots(db, [FULL, MINIMAL])
    changed = MINIMAL.model_copy(update={"notes": "changed"})
    result = sync_spots(db, [FULL, changed])
    assert result.upserted == 1
    assert db.writes.count(("upsert", "spots")) == 2
    assert db.upsert_payloads[-1] == ("spots", [changed.to_row()])


def test_removed_field_becomes_null():
    db = RecordingFake()
    sync_spots(db, [FULL])
    assert row_of(db, "test-strand")["region"] == "Testregio"
    result = sync_spots(db, [FULL.model_copy(update={"region": None})])
    assert result.upserted == 1
    assert row_of(db, "test-strand")["region"] is None


def test_invalid_db_row_overwritten():
    db = RecordingFake()
    db.seed("spots", [{"id": "zz-min", "name": "Minimal", "lat": 10.0, "lon": 4.0}])
    result = sync_spots(db, [MINIMAL])
    assert result.upserted == 1
    assert result.orphaned == []
    stored = row_of(db, "zz-min")
    assert stored["lat"] is None and stored["lon"] is None


def test_duplicate_ids_rejected():
    db = RecordingFake()
    with pytest.raises(ValueError, match="duplicate spot ids"):
        sync_spots(db, [MINIMAL, MINIMAL])
    assert db.writes == []


def test_empty_input():
    db = RecordingFake()
    db.seed("spots", [{"id": "zz-a", "name": "A"}, {"id": "zz-b", "name": "B"}])
    result = sync_spots(db, [])
    assert result.upserted == 0
    assert result.orphaned == ["zz-a", "zz-b"]
    assert db.writes == []
