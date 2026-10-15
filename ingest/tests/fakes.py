"""In-memory stand-in for SupabaseRest with the filter, order and write semantics of PostgREST.

Validation and JSON encoding come from shakka.db, so error cases are identical to the real
client. NOT imitated: foreign keys, CHECK and unique constraints (except the primary key),
numeric(10,2) rounding, Postgres collation (text sorts by codepoint) and the notation of
timestamps in responses (the fake returns them as sent; PostgREST normalizes to +00:00).
Parse timestamps from select() with datetime.fromisoformat, never compare them as strings.
"""

import copy
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from shakka.db import (
    BATCH_SIZE,
    TABLE_KEYS,
    DatabaseError,
    Filters,
    check_rows,
    effective_order,
    filter_params,
    iso_utc,
    parse_columns,
    parse_in_list,
    parse_on_conflict,
    parse_order,
    split_filter,
    to_json,
    validate_table,
)
from shakka.jobs.sessions import PURGE_RPC, SESSION_RETENTION

_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T")
_UPDATED_AT_TABLES = frozenset({"spots", "profiles", "alert_rules", "alert_state"})
_FIXED_CLOCK = datetime(2026, 1, 1, tzinfo=UTC)


def _parse_ts(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _norm(value: Any) -> Any:
    """Comparable form of a stored value (None stays None)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and _TIMESTAMP.match(value):
        return _parse_ts(value)
    if isinstance(value, list | dict):
        raise ValueError("FakeSupabase: comparing array/json columns is not supported")
    return value


def _norm_filter(stored: Any, text: str) -> Any:
    """The filter text converted to the type of the stored value."""
    if isinstance(stored, bool):
        if text not in ("true", "false"):
            raise ValueError("boolean filter must be true or false")
        return float(text == "true")
    if isinstance(stored, int | float):
        return float(text)
    if isinstance(stored, str) and _TIMESTAMP.match(stored):
        return _parse_ts(text)
    return text


def _matches(row: Mapping[str, Any], column: str, value: str) -> bool:
    op, rest = split_filter(value)
    stored = row.get(column)
    if op == "is":
        return stored is None
    if stored is None:
        return False
    left = _norm(stored)
    if op == "in":
        return any(left == _norm_filter(stored, item) for item in parse_in_list(rest))
    right = _norm_filter(stored, rest)
    return {
        "eq": left == right,
        "neq": left != right,
        "lt": left < right,
        "lte": left <= right,
        "gt": left > right,
        "gte": left >= right,
    }[op]


class FakeSupabase:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        """`clock` defaults to a fixed 2026-01-01T00:00:00Z; used for now()-defaults/updated_at."""
        self._clock = clock or (lambda: _FIXED_CLOCK)
        self._tables: dict[str, list[dict[str, Any]]] = {t: [] for t in TABLE_KEYS}
        self._alert_state_seq = 0
        self._ingest_run_seq = 0
        self._push_subscription_seq = 0
        self.writes: list[tuple[str, str]] = []
        self.upserts: list[tuple[str, str]] = []
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []
        self._rpcs: dict[str, Callable[[dict[str, Any]], Any]] = {}

    # -- helpers for tests -------------------------------------------------------------------

    def seed(self, table: str, rows: Sequence[Mapping[str, Any]]) -> None:
        """Like insert, but not recorded in `writes`."""
        self._insert(table, rows, record=False)

    def rows(self, table: str) -> list[dict[str, Any]]:
        """Deep copy of the stored rows, in insertion order."""
        self._known(table)
        return copy.deepcopy(self._tables[table])

    def register_rpc(self, name: str, fn: Callable[[dict[str, Any]], Any]) -> None:
        self._rpcs[name] = fn

    # -- internals ---------------------------------------------------------------------------

    def _now(self) -> str:
        return iso_utc(self._clock())

    def _known(self, table: str) -> None:
        validate_table(table)
        if table not in TABLE_KEYS:
            raise ValueError("unknown table")

    def _encode(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [json.loads(to_json(dict(row))) for row in rows]

    def _defaults(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        defaults: dict[str, Any] = {}
        if table == "spots":
            defaults = {
                "tide_sensitive": "none",
                "season": [],
                "verified": False,
                "updated_at": now,
            }
        elif table == "evaluations":
            defaults = {"reasons": []}
        elif table == "profiles":
            defaults = {"quiver_m2": [], "created_at": now, "updated_at": now}
        elif table == "favorites":
            defaults = {"created_at": now}
        elif table == "alert_rules":
            defaults = {"enabled": True, "updated_at": now}
        elif table == "alert_state":
            self._alert_state_seq += 1
            defaults = {
                "id": f"00000000-0000-4000-8000-{self._alert_state_seq:012d}",
                "created_at": now,
                "updated_at": now,
            }
        elif table == "push_subscriptions":
            self._push_subscription_seq += 1
            defaults = {
                "id": f"00000000-0000-4000-9000-{self._push_subscription_seq:012d}",
                "created_at": now,
            }
        elif table == "api_usage":
            defaults = {"calls": 0, "requests": 0}
        elif table == "ingest_runs":
            self._ingest_run_seq += 1
            defaults = {"id": self._ingest_run_seq, "steps": []}
        full = {**row}
        for key, value in defaults.items():
            full.setdefault(key, value)
        return full

    def _pk(self, table: str, row: Mapping[str, Any]) -> tuple[Any, ...]:
        key = []
        for column in TABLE_KEYS[table]:
            if row.get(column) is None:
                raise DatabaseError(
                    f"null value in column {column} violates not-null constraint",
                    status=400,
                    code="23502",
                )
            key.append(_norm(row[column]))
        return tuple(key)

    def _find(self, table: str, pk: tuple[Any, ...]) -> dict[str, Any] | None:
        for existing in self._tables[table]:
            if self._pk(table, existing) == pk:
                return existing
        return None

    def _insert(
        self, table: str, rows: Sequence[Mapping[str, Any]], *, record: bool
    ) -> list[dict[str, Any]]:
        self._known(table)
        check_rows(rows)
        encoded = self._encode(rows)
        if not encoded:
            return []
        if record:
            self.writes.append(("insert", table))
        stored: list[dict[str, Any]] = []
        for start in range(0, len(encoded), BATCH_SIZE):
            batch = encoded[start : start + BATCH_SIZE]
            if table == "ingest_runs" and any("id" in row for row in batch):
                raise DatabaseError(
                    "cannot insert a non-DEFAULT value into column id", status=400, code="428C9"
                )
            full = [self._defaults(table, row) for row in batch]
            seen: set[tuple[Any, ...]] = set()
            for row in full:
                pk = self._pk(table, row)
                if pk in seen or self._find(table, pk) is not None:
                    raise DatabaseError(
                        "duplicate key value violates unique constraint", status=409, code="23505"
                    )
                seen.add(pk)
            self._tables[table].extend(full)
            stored.extend(copy.deepcopy(full))
        return stored

    def _select_rows(self, table: str, filters: Filters | None) -> list[dict[str, Any]]:
        pairs = filter_params(filters)
        return [
            row
            for row in self._tables[table]
            if all(_matches(row, column, value) for column, value in pairs)
        ]

    # -- same public API as SupabaseRest -----------------------------------------------------

    def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: Filters | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self._known(table)
        projection = parse_columns(columns)
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        terms = parse_order(effective_order(table, order))
        rows = self._select_rows(table, filters)
        for term in reversed(terms):
            # Sorting descending uses reverse=True, which also reverses the null placement.
            if term.descending:
                null_rank = 1 if term.nulls_first else 0
            else:
                null_rank = 0 if term.nulls_first else 1

            def sort_key(
                row: dict[str, Any], column: str = term.column, rank: int = null_rank
            ) -> Any:
                value = _norm(row.get(column))
                return (rank, 0) if value is None else (1 - rank, value)

            rows.sort(key=sort_key, reverse=term.descending)
        if limit is not None:
            rows = rows[:limit]
        if projection is None:
            return copy.deepcopy(rows)
        return [{column: copy.deepcopy(row.get(column)) for column in projection} for row in rows]

    def upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str) -> int:
        self._known(table)
        conflict = parse_on_conflict(on_conflict)
        check_rows(rows, conflict)
        encoded = self._encode(rows)
        if not encoded:
            return 0
        self.writes.append(("upsert", table))
        self.upserts.append((table, on_conflict))
        if set(conflict) != set(TABLE_KEYS[table]):
            raise DatabaseError(
                "there is no unique constraint matching the ON CONFLICT specification",
                status=400,
                code="42P10",
            )
        for start in range(0, len(encoded), BATCH_SIZE):
            batch = encoded[start : start + BATCH_SIZE]
            planned: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
            seen: set[tuple[Any, ...]] = set()
            for row in batch:
                full = self._defaults(table, row)
                pk = self._pk(table, full)
                if pk in seen:
                    raise DatabaseError(
                        "ON CONFLICT DO UPDATE command cannot affect row a second time",
                        status=400,
                        code="21000",
                    )
                seen.add(pk)
                planned.append((full, self._find(table, pk)))
            for (full, existing), given in zip(planned, batch, strict=True):
                if existing is None:
                    self._tables[table].append(full)
                else:
                    existing.update(given)
                    if table in _UPDATED_AT_TABLES:
                        existing["updated_at"] = self._now()
        return len(rows)

    def insert(
        self, table: str, rows: Sequence[Mapping[str, Any]], *, returning: bool = False
    ) -> list[dict[str, Any]]:
        stored = self._insert(table, rows, record=True)
        return stored if returning else []

    def update(self, table: str, values: Mapping[str, Any], *, filters: Filters) -> int:
        self._known(table)
        if not filter_params(filters):
            raise ValueError("update needs at least one filter")
        if not values:
            raise ValueError("update needs values")
        check_rows([values])
        (encoded,) = self._encode([values])
        self.writes.append(("update", table))
        matched = self._select_rows(table, filters)
        for row in matched:
            row.update(encoded)
            if table in _UPDATED_AT_TABLES:
                row["updated_at"] = self._now()
        return len(matched)

    def delete(self, table: str, *, filters: Filters) -> int:
        self._known(table)
        if not filter_params(filters):
            raise ValueError("delete needs at least one filter")
        self.writes.append(("delete", table))
        matched = self._select_rows(table, filters)
        ids = {id(row) for row in matched}
        self._tables[table] = [row for row in self._tables[table] if id(row) not in ids]
        if table == "spots":
            spot_ids = {row["id"] for row in matched}
            for child in (
                "forecast_hours",
                "marine_hours",
                "evaluations",
                "favorites",
                "alert_rules",
                "alert_state",
            ):
                self._tables[child] = [
                    row for row in self._tables[child] if row.get("spot_id") not in spot_ids
                ]
        elif table == "sessions":
            session_ids = {row["id"] for row in matched}
            self._tables["rsvps"] = [
                row for row in self._tables["rsvps"] if row.get("session_id") not in session_ids
            ]
        elif table == "favorites":
            gone = {(row["user_id"], row["spot_id"]) for row in matched}
            self._tables["alert_rules"] = [
                row
                for row in self._tables["alert_rules"]
                if (row.get("user_id"), row.get("spot_id")) not in gone
            ]
        return len(matched)

    def rpc(self, function: str, args: Mapping[str, Any] | None = None) -> Any:
        validate_table(function)
        payload = json.loads(to_json(dict(args or {})))
        self.rpc_calls.append((function, payload))
        handler = self._rpcs.get(function) or self._builtin_rpcs().get(function)
        if handler is None:
            raise DatabaseError(
                f"Could not find the function {function}", status=404, code="PGRST202"
            )
        return handler(payload)

    def _builtin_rpcs(self) -> dict[str, Callable[[dict[str, Any]], Any]]:
        return {PURGE_RPC: self._purge_expired_sessions}

    def _purge_expired_sessions(self, args: dict[str, Any]) -> int:
        """Same rule as the SQL function: ends_at < p_now - 7 days, RSVPs go with the session."""
        p_now = args.get("p_now")
        if p_now is None:
            raise DatabaseError("invalid_input", status=400, code="PT400")
        cutoff = _parse_ts(p_now) - SESSION_RETENTION
        gone = {row["id"] for row in self._tables["sessions"] if _parse_ts(row["ends_at"]) < cutoff}
        self._tables["sessions"] = [r for r in self._tables["sessions"] if r["id"] not in gone]
        self._tables["rsvps"] = [
            r for r in self._tables["rsvps"] if r.get("session_id") not in gone
        ]
        return len(gone)

    def close(self) -> None:
        return None

    def __enter__(self) -> "FakeSupabase":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
