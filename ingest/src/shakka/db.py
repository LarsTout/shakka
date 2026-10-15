"""Thin client for the Supabase REST API (PostgREST). The only module that talks to the database."""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time
from enum import Enum
from types import TracebackType
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import httpx

from shakka.http import make_client

if TYPE_CHECKING:
    from shakka.config import Settings

PAGE_SIZE: Final = 1000  # equals PostgREST max_rows (config.toml, hosted default)
BATCH_SIZE: Final = 500  # rows per upsert/insert request
MAX_ERROR_MESSAGE: Final = 300  # chars of PostgREST message kept in DatabaseError
SUPPORTED_OPERATORS: Final = frozenset({"eq", "neq", "lt", "lte", "gt", "gte", "in", "is"})
# PostgREST query parameters that can never be used as a filter column.
RESERVED_PARAMS: Final = frozenset(
    {"select", "order", "limit", "offset", "on_conflict", "columns", "or", "and", "not"}
)

# Primary key per table, in key order. Used for default ordering, for counting rows on
# update/delete, and by FakeSupabase. Later WPs add their tables here (marine_hours, ...).
TABLE_KEYS: Final[Mapping[str, tuple[str, ...]]] = {
    "spots": ("id",),
    "forecast_hours": ("spot_id", "model", "valid_at"),
    "marine_hours": ("spot_id", "valid_at"),
    "tide_extremes": ("station", "at"),
    "evaluations": ("spot_id", "valid_at"),
    "profiles": ("user_id",),
    "favorites": ("user_id", "spot_id"),
    "alert_rules": ("user_id", "spot_id"),
    "alert_state": ("id",),
    "push_subscriptions": ("id",),
    "sessions": ("id",),
    "rsvps": ("id",),
    "api_usage": ("day", "source"),
    "ingest_runs": ("id",),
}

Filters = Mapping[str, str | Sequence[str]]

_IDENT = re.compile(r"[a-z_][a-z0-9_]*")
_ORDER_TERM = re.compile(
    r"(?P<col>[a-z_][a-z0-9_]*)(?:\.(?P<dir>asc|desc))?(?:\.(?P<nulls>nullsfirst|nullslast))?"
)


class DatabaseError(Exception):
    """A failed database call. `status` is the HTTP status (None for transport errors)."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class OrderTerm(NamedTuple):
    column: str
    descending: bool
    nulls_first: bool  # resolved: explicit .nullsfirst/.nullslast, else descending


def iso_utc(value: datetime) -> str:
    """Aware datetime -> 'YYYY-MM-DDTHH:MM:SS[.ffffff]Z'. ValueError if naive."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat().removesuffix("+00:00") + "Z"


def in_filter(values: Iterable[str | int]) -> str:
    """Build 'in.(a,b)'. Values containing , ( ) or leading/trailing space are double-quoted.

    ValueError on empty input or on values containing '"' or '\\'.
    """
    parts: list[str] = []
    for value in values:
        text = str(value)
        if '"' in text or "\\" in text:
            raise ValueError("in_filter values must not contain '\"' or backslash")
        if any(ch in text for ch in ",()") or text != text.strip():
            text = f'"{text}"'
        parts.append(text)
    if not parts:
        raise ValueError("in_filter needs at least one value")
    return "in.(" + ",".join(parts) + ")"


def parse_in_list(rest: str) -> list[str]:
    """Split the '(a,"b, c")' part of an in-filter into its (unquoted) values."""
    if not (rest.startswith("(") and rest.endswith(")")):
        raise ValueError("in filter must look like in.(a,b)")
    inner = rest[1:-1]
    values: list[str] = []
    current: list[str] = []
    quoted = False
    for ch in inner:
        if ch == '"':
            quoted = not quoted
        elif ch == "," and not quoted:
            values.append("".join(current))
            current = []
        else:
            current.append(ch)
    values.append("".join(current))
    return values


def _json_default(value: object) -> Any:
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, set | frozenset):
        try:
            return sorted(value)
        except TypeError:
            raise ValueError("cannot sort set for JSON encoding") from None
    if isinstance(value, Enum):
        return value.value
    raise ValueError(f"cannot encode {type(value).__name__} as JSON")


def to_json(payload: Any) -> str:
    """json.dumps with allow_nan=False and a default that encodes aware datetime (iso_utc),
    date/time (isoformat), set/frozenset (sorted list) and Enum (.value).

    Naive datetime, NaN/inf or unknown types raise ValueError.
    """
    try:
        return json.dumps(payload, allow_nan=False, default=_json_default)
    except TypeError as exc:
        raise ValueError(f"cannot encode payload as JSON: {exc}") from None


def validate_table(table: str) -> str:
    if not isinstance(table, str) or not _IDENT.fullmatch(table):
        raise ValueError("invalid table or function name")
    return table


def _validate_column(column: str) -> str:
    if not isinstance(column, str) or not _IDENT.fullmatch(column):
        raise ValueError("invalid column name")
    return column


def parse_columns(columns: str) -> list[str] | None:
    """'*' -> None; 'a,b' -> ['a', 'b']; anything else raises ValueError."""
    if columns == "*":
        return None
    return [_validate_column(part) for part in columns.split(",")]


def parse_order(order: str) -> list[OrderTerm]:
    """Parse 'a.desc,b,c.asc.nullsfirst'. Anything else raises ValueError."""
    terms: list[OrderTerm] = []
    for part in order.split(","):
        match = _ORDER_TERM.fullmatch(part)
        if match is None:
            raise ValueError("invalid order")
        descending = match["dir"] == "desc"
        nulls = match["nulls"]
        nulls_first = descending if nulls is None else nulls == "nullsfirst"
        terms.append(OrderTerm(match["col"], descending, nulls_first))
    return terms


def default_order(table: str) -> str:
    """The primary key of `table` as an order string. Unknown table raises ValueError."""
    keys = TABLE_KEYS.get(table)
    if keys is None:
        raise ValueError("unknown table: pass an explicit unique order")
    return ",".join(keys)


def effective_order(table: str, order: str | None) -> str:
    """The order used for paging: always deterministic for tables in TABLE_KEYS.

    Without `order` the primary key is used. With an `order`, primary key columns that do not
    occur in it are appended as an ascending tiebreaker, so limit/offset pages never overlap.
    For a table outside TABLE_KEYS an explicit `order` is returned unchanged: the caller is
    then responsible for making it unique.
    """
    if order is None:
        return default_order(table)
    terms = parse_order(order)
    keys = TABLE_KEYS.get(table)
    if keys is None:
        return order
    present = {term.column for term in terms}
    missing = [key for key in keys if key not in present]
    return order + "," + ",".join(missing) if missing else order


def split_filter(value: str) -> tuple[str, str]:
    """Split '<op>.<rest>' and validate the operator. ValueError otherwise."""
    op, dot, rest = value.partition(".") if isinstance(value, str) else ("", "", "")
    if not dot or op not in SUPPORTED_OPERATORS:
        raise ValueError("unsupported filter operator")
    if op == "is" and rest != "null":
        raise ValueError("only is.null is supported")
    if op == "in" and not (rest.startswith("(") and rest.endswith(")")):
        raise ValueError("in filter must look like in.(a,b)")
    return op, rest


def filter_params(filters: Filters | None) -> list[tuple[str, str]]:
    """Flatten filters to (column, '<op>.<rest>') pairs, validating columns and operators.

    A list value gives the same column several times (combined with AND by PostgREST).
    """
    pairs: list[tuple[str, str]] = []
    for column, raw in (filters or {}).items():
        _validate_column(column)
        if column in RESERVED_PARAMS:
            raise ValueError("reserved query parameter cannot be used as a filter column")
        values = [raw] if isinstance(raw, str) else list(raw)
        for value in values:
            split_filter(value)
            pairs.append((column, value))
    return pairs


def _batches(rows: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    return [list(rows[i : i + BATCH_SIZE]) for i in range(0, len(rows), BATCH_SIZE)]


def check_rows(rows: Sequence[Mapping[str, Any]], on_conflict: Sequence[str] = ()) -> None:
    """Shared row validation: equal key sets, identifier keys, on_conflict columns present."""
    if not rows:
        return
    keys = set(rows[0])
    for row in rows:
        if set(row) != keys:
            raise ValueError("all rows must have the same keys")
    for key in keys:
        _validate_column(key)
    for column in on_conflict:
        if column not in keys:
            raise ValueError("on_conflict column missing from rows")


def parse_on_conflict(on_conflict: str) -> list[str]:
    """A comma separated list of identifiers. ValueError otherwise."""
    return [_validate_column(part) for part in on_conflict.split(",")]


class SupabaseRest:
    """PostgREST client. Sends the secret key only in the `apikey` header."""

    def __init__(self, url: str, secret_key: str, *, client: httpx.Client | None = None) -> None:
        self._base = url.rstrip("/")
        self._secret = secret_key
        self._owns_client = client is None
        self._client = make_client() if client is None else client

    @classmethod
    def from_settings(cls, settings: "Settings") -> "SupabaseRest":
        return cls(settings.supabase_url, settings.supabase_secret_key.get_secret_value())

    def close(self) -> None:
        """Close the client, but only when this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "SupabaseRest":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return "SupabaseRest()"

    # -- internals ---------------------------------------------------------------------------

    def _clean(self, text: str) -> str:
        return text.replace(self._secret, "***")

    def _send(
        self,
        op: str,
        label: str,
        method: str,
        path: str,
        *,
        params: Sequence[tuple[str, str]] = (),
        body: str | None = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        headers = {"apikey": self._secret, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if prefer is not None:
            headers["Prefer"] = prefer
        try:
            response = self._client.request(
                method,
                f"{self._base}/rest/v1/{path}",
                params=list(params),
                content=body,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise DatabaseError(f"{op} {label}: {type(exc).__name__}") from None
        if not 200 <= response.status_code < 300:
            raise self._http_error(op, label, response)
        return response

    def _http_error(self, op: str, label: str, response: httpx.Response) -> DatabaseError:
        code: str | None = None
        message: str | None = None
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict):
            raw_code = data.get("code")
            raw_message = data.get("message")
            code = str(raw_code) if raw_code is not None else None
            message = str(raw_message) if raw_message is not None else None
        text = f"{op} {label}: HTTP {response.status_code}"
        if code:
            text += f" {code}"
        if message:
            text += f": {self._clean(message)[:MAX_ERROR_MESSAGE]}"
        return DatabaseError(
            self._clean(text),
            status=response.status_code,
            code=self._clean(code) if code else None,
        )

    def _rows(self, op: str, label: str, response: httpx.Response) -> list[dict[str, Any]]:
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, list):
            raise DatabaseError(f"{op} {label}: unexpected response", status=response.status_code)
        return data

    # -- public API --------------------------------------------------------------------------

    def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: Filters | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read rows, paging by PAGE_SIZE until an empty page (or `limit`) is reached.

        The order is always deterministic for known tables (see `effective_order`). For a table
        outside TABLE_KEYS the caller must pass a unique `order`.
        """
        validate_table(table)
        parse_columns(columns)
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        pairs = filter_params(filters)
        resolved = effective_order(table, order)
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            want = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - len(rows))
            params = [
                ("select", columns),
                *pairs,
                ("order", resolved),
                ("limit", str(want)),
                ("offset", str(offset)),
            ]
            response = self._send("select", table, "GET", table, params=params)
            page = self._rows("select", table, response)
            if not page:
                return rows
            rows.extend(page)
            if limit is not None and len(rows) >= limit:
                return rows[:limit]
            offset += len(page)

    def upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str) -> int:
        """Insert or merge rows in batches of BATCH_SIZE; returns len(rows).

        A failing later batch leaves earlier batches stored. Upserts are idempotent, so running
        again is safe.
        """
        validate_table(table)
        conflict = parse_on_conflict(on_conflict)
        check_rows(rows, conflict)
        bodies = [to_json(batch) for batch in _batches(rows)]
        for body in bodies:
            self._send(
                "upsert",
                table,
                "POST",
                table,
                params=[("on_conflict", on_conflict)],
                body=body,
                prefer="resolution=merge-duplicates, return=minimal",
            )
        return len(rows)

    def insert(
        self, table: str, rows: Sequence[Mapping[str, Any]], *, returning: bool = False
    ) -> list[dict[str, Any]]:
        """Insert rows in batches of BATCH_SIZE; returns the stored rows when `returning`."""
        validate_table(table)
        check_rows(rows)
        bodies = [to_json(batch) for batch in _batches(rows)]
        prefer = "return=representation" if returning else "return=minimal"
        stored: list[dict[str, Any]] = []
        for body in bodies:
            response = self._send("insert", table, "POST", table, body=body, prefer=prefer)
            if returning:
                stored.extend(self._rows("insert", table, response))
        return stored

    def _key_select(self, table: str) -> str:
        keys = TABLE_KEYS.get(table)
        return ",".join(keys) if keys else "*"

    def update(self, table: str, values: Mapping[str, Any], *, filters: Filters) -> int:
        """PATCH the rows matching `filters` (required); returns the number of rows touched."""
        validate_table(table)
        pairs = filter_params(filters)
        if not pairs:
            raise ValueError("update needs at least one filter")
        if not values:
            raise ValueError("update needs values")
        check_rows([values])
        body = to_json(dict(values))
        params = [*pairs, ("select", self._key_select(table))]
        response = self._send(
            "update",
            table,
            "PATCH",
            table,
            params=params,
            body=body,
            prefer="return=representation",
        )
        return len(self._rows("update", table, response))

    def delete(self, table: str, *, filters: Filters) -> int:
        """DELETE the rows matching `filters` (required); returns the number of rows removed."""
        validate_table(table)
        pairs = filter_params(filters)
        if not pairs:
            raise ValueError("delete needs at least one filter")
        params = [*pairs, ("select", self._key_select(table))]
        response = self._send(
            "delete", table, "DELETE", table, params=params, prefer="return=representation"
        )
        return len(self._rows("delete", table, response))

    def rpc(self, function: str, args: Mapping[str, Any] | None = None) -> Any:
        """Call a database function; returns the parsed JSON, or None for an empty response."""
        validate_table(function)
        body = to_json(dict(args or {}))
        response = self._send("rpc", function, "POST", f"rpc/{function}", body=body)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise DatabaseError(
                f"rpc {function}: unexpected response", status=response.status_code
            ) from None
