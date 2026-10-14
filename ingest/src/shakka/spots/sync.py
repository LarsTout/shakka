"""Sync validated spot profiles to the `spots` table. Never deletes."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from shakka.db import SupabaseRest
from shakka.domain.spot import SPOT_COLUMNS, SpotProfile


@dataclass(frozen=True)
class SyncResult:
    upserted: int  # new + changed spots written
    orphaned: list[str]  # ids in the database but not in `spots`, sorted ascending


def _normalized(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return SpotProfile.from_row(row).to_row()
    except ValueError:
        return None  # unparsable database row counts as changed


def sync_spots(db: SupabaseRest, spots: Sequence[SpotProfile]) -> SyncResult:
    """Upsert new/changed spots on `id`. Never deletes. YAML wins over manual database edits."""
    ids = [s.id for s in spots]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate spot ids: {', '.join(duplicates)}")
    existing_rows = db.select("spots", columns=",".join(SPOT_COLUMNS))
    existing = {row["id"]: _normalized(row) for row in existing_rows}
    changed = [row for s in spots if existing.get(s.id) != (row := s.to_row())]
    upserted = db.upsert("spots", changed, on_conflict="id") if changed else 0
    orphaned = sorted(set(existing) - set(ids))
    return SyncResult(upserted=upserted, orphaned=orphaned)
