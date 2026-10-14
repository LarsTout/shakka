"""Shared cases for FakeSupabase (always) and the local PostgREST stack (optional parity test).

Expected results are derived by hand from PostgREST and SQL semantics, not from the fake.
"""

from typing import Any, NamedTuple

from shakka.db import in_filter

PARITY_IDS = ["zzp-a", "zzp-b", "zzp-c", "zzp-d", "zzp-e"]


def _row(
    id_: str,
    region: str | None,
    lat: float | None,
    lon: float | None,
    shore_normal_deg: int | None,
    status: str | None,
    verified: bool,
    updated_at: str,
) -> dict[str, Any]:
    return {
        "id": id_,
        "name": id_,
        "region": region,
        "lat": lat,
        "lon": lon,
        "shore_normal_deg": shore_normal_deg,
        "status": status,
        "verified": verified,
        "updated_at": updated_at,
    }


PARITY_ROWS: list[dict[str, Any]] = [
    _row("zzp-a", "noord", 52.0, 4.5, 270, "allowed", True, "2026-10-14T12:00:00Z"),
    _row("zzp-b", "zuid", 51.5, 3.6, 300, "limited", False, "2026-10-14T14:00:00+02:00"),
    _row("zzp-c", None, None, None, None, None, False, "2026-10-13T23:30:00Z"),
    _row("zzp-d", "noord, holland", 53.0, 5.0, 0, "forbidden", True, "2026-10-15T00:00:00Z"),
    _row("zzp-e", "oost", 52.0, 6.0, 359, "allowed", False, "2026-10-14T12:00:01Z"),
]


class FilterCase(NamedTuple):
    name: str
    filters: dict[str, str | list[str]]
    order: str | None
    limit: int | None
    expected: list[str]


def _case(
    name: str,
    filters: dict[str, str | list[str]],
    expected: str,
    *,
    order: str | None = None,
    limit: int | None = None,
) -> FilterCase:
    return FilterCase(name, filters, order, limit, [f"zzp-{x}" for x in expected.split()])


FILTER_CASES: list[FilterCase] = [
    _case("eq_text", {"region": "eq.noord"}, "a"),
    _case("eq_number", {"lat": "eq.52"}, "a e"),
    _case("eq_bool", {"verified": "eq.true"}, "a d"),
    _case("eq_timestamp_offsets", {"updated_at": "eq.2026-10-14T12:00:00Z"}, "a b"),
    _case("neq_excludes_null", {"region": "neq.noord"}, "b d e"),
    _case("lt_number", {"shore_normal_deg": "lt.300"}, "a d"),
    _case("lte_number", {"shore_normal_deg": "lte.300"}, "a b d"),
    _case("gt_number", {"shore_normal_deg": "gt.300"}, "e"),
    _case("gte_timestamp", {"updated_at": "gte.2026-10-14T12:00:00Z"}, "a b d e"),
    _case("lt_timestamp_plus_offset", {"updated_at": "lt.2026-10-14T12:00:00+00:00"}, "c"),
    _case("in_text", {"id": in_filter(["zzp-a", "zzp-c"])}, "a c"),
    _case("in_quoted_comma", {"region": in_filter(["noord, holland", "oost"])}, "d e"),
    _case("is_null", {"region": "is.null"}, "c"),
    _case("and_two_columns", {"verified": "eq.false", "status": "eq.limited"}, "b"),
    _case("range_same_column", {"shore_normal_deg": ["gte.270", "lt.359"]}, "a b"),
    _case("order_desc_nulls_first", {}, "c e b a d", order="shore_normal_deg.desc"),
    _case("order_asc_nulls_last", {}, "d a b e c", order="shore_normal_deg"),
    _case("order_asc_nullsfirst", {}, "c d a b e", order="shore_normal_deg.asc.nullsfirst"),
    _case("order_multi", {}, "b e a d c", order="lat.asc,id.desc"),
    _case("order_ties_pk_tiebreak", {}, "c d a e b", order="lat.desc"),
    _case("order_ties_bool", {}, "b c e a d", order="verified"),
    _case("limit", {}, "a b", order="id", limit=2),
]
