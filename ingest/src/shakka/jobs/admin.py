"""Admin operations for the M1 setup without a UI: profile, favorites, alert rules, preview.

Every user mistake becomes an `AdminError` (exit code 1 in the CLI), validated before any
write with the same bounds as the database CHECKs. Only the preview computes alerts, and it
never writes. These commands run locally: logging is not configured here, so user ids in
request filters are not logged.
"""

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Final

from pydantic import ValidationError

from shakka.config import Settings, get_settings
from shakka.db import DatabaseError, SupabaseRest, in_filter
from shakka.domain.alerts import (
    ALERT_KN_RANGE,
    DAYS_AHEAD_RANGE,
    MIN_GO_HOURS_RANGE,
    RULE_FIELDS,
    AlertRule,
    AlertRuleOverride,
    ProfileDefaults,
    resolve_rule,
)
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass
from shakka.domain.kite import MAX_QUIVER_KITES, QUIVER_SIZE_RANGE_M2, WEIGHT_RANGE_KG
from shakka.domain.messages import format_window_local
from shakka.domain.spot import SPOT_COLUMNS, SPOT_ID_PATTERN, Level, SpotProfile
from shakka.jobs import runtime
from shakka.jobs.alerts import (
    PROFILE_COLUMNS,
    RULE_COLUMNS,
    FavoritePlan,
    format_rule,
    load_alert_context,
    normalize_base_url,
    plan_favorite,
)
from shakka.jobs.inputs import short_error

QUIVER_ERROR: Final = (
    "quiver sizes must be numbers between 3 and 21 m2; separate sizes with ',', ';' or spaces, "
    "write decimals with a point (10.5)"
)
FK_VIOLATION: Final = "23503"
_TIME_RE: Final = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")
_FORBIDDEN_DIRS: Final = frozenset({"offshore", "side_offshore"})


class AdminError(Exception):
    """User-facing error; the CLI prints it and exits with 1."""


@dataclass(frozen=True, slots=True)
class FavoriteAdded:
    added: bool
    verified: bool


@dataclass(frozen=True, slots=True)
class FavoriteInfo:
    spot_id: str
    name: str
    verified: bool
    has_rule: bool


# -- parsers ----------------------------------------------------------------------------------


def parse_quiver(text: str) -> list[float]:
    """Kite sizes in m2. With ';' or whitespace those separate sizes and a comma inside a size
    is a decimal comma; with commas only, every comma separates sizes ("10,5" is 5 and 10)."""
    t = text.strip()
    if not t:
        return []
    if re.search(r"[;\s]", t):
        parts = []
        for part in (p for p in re.split(r"[;\s]+", t) if p):
            if part.count(",") == 1 and "." not in part:
                part = part.replace(",", ".")
            parts.append(part)
    else:
        parts = t.split(",")
    if len(parts) > MAX_QUIVER_KITES:
        raise AdminError(f"at most {MAX_QUIVER_KITES} kites")
    lo, hi = QUIVER_SIZE_RANGE_M2
    sizes: set[float] = set()
    for part in parts:
        try:
            size = float(part)
        except ValueError:
            raise AdminError(QUIVER_ERROR) from None
        if not math.isfinite(size) or not lo <= size <= hi:
            raise AdminError(QUIVER_ERROR)
        sizes.add(size)
    return sorted(sizes)


def quiver_comma_note(text: str) -> str | None:
    """Informative note when a comma-only quiver may not have been read as intended."""
    t = text.strip()
    if re.search(r"[;\s]", t):
        return None
    parts = t.split(",")
    if len(parts) < 2 or not any(re.fullmatch(r"[0-9]", p.strip()) for p in parts[1:]):
        return None
    try:
        parsed = parse_quiver(text)
    except AdminError:
        return None
    sizes = ", ".join(f"{s:g}" for s in parsed)
    return (
        f"note: commas separate sizes, so the quiver was read as {sizes} m2; "
        "for a decimal size write a point (10.5) or separate sizes with ';' or spaces "
        '("10,5; 12")'
    )


def parse_dir_classes(text: str) -> list[DirClass]:
    values = [p.strip() for p in text.split(",")]
    if not text.strip() or any(not v for v in values):
        raise AdminError("dir classes must not be empty")
    chosen: set[DirClass] = set()
    allowed = ", ".join(c.value for c in DirClass if c in RIDABLE_DIR_CLASSES)
    for v in values:
        if v in _FORBIDDEN_DIRS:
            raise AdminError(
                f"dir class '{v}' is not allowed: offshore and side_offshore are never ridable; "
                f"choose from {allowed}"
            )
        try:
            cls = DirClass(v)
        except ValueError:
            raise AdminError(f"unknown dir class '{v}'; choose from {allowed}") from None
        chosen.add(cls)
    return [c for c in DirClass if c in chosen]


def parse_weekdays(text: str) -> list[int]:
    parts = [p.strip() for p in text.split(",")]
    if not parts or any(not re.fullmatch(r"[1-7]", p) for p in parts):
        raise AdminError("weekdays must be numbers 1-7 (1 = Monday)")
    return sorted({int(p) for p in parts})


def parse_local_time(text: str) -> time:
    t = text.strip()
    if not _TIME_RE.fullmatch(t):
        raise AdminError("times must be HH:MM (00:00-23:59)")
    return time(int(t[:2]), int(t[3:]))


def _check_range(name: str, value: int, bounds: tuple[int, int]) -> int:
    lo, hi = bounds
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise AdminError(f"{name} must be between {lo} and {hi}")
    return value


# -- profile ----------------------------------------------------------------------------------

NO_PROFILE: Final = "no profile for this user id; create the user in Supabase Authentication first"


def get_profile(db: SupabaseRest, user_id: str) -> dict[str, Any]:
    rows = db.select("profiles", columns=PROFILE_COLUMNS, filters={"user_id": f"eq.{user_id}"})
    if not rows:
        raise AdminError(NO_PROFILE)
    return rows[0]


def set_profile(
    db: SupabaseRest,
    user_id: str,
    *,
    weight_kg: int | None = None,
    level: str | None = None,
    quiver_m2: list[float] | None = None,
    min_kn: int | None = None,
    max_kn: int | None = None,
) -> dict[str, Any]:
    given = (weight_kg, level, quiver_m2, min_kn, max_kn)
    if all(v is None for v in given):
        raise AdminError("nothing to change")
    values: dict[str, Any] = {}
    if weight_kg is not None:
        values["weight_kg"] = _check_range("weight_kg", weight_kg, WEIGHT_RANGE_KG)
    if level is not None:
        try:
            values["level"] = Level(level.strip().lower()).value
        except ValueError:
            raise AdminError("level must be one of beginner, intermediate, advanced") from None
    if quiver_m2 is not None:
        values["quiver_m2"] = list(quiver_m2)
    if min_kn is not None:
        values["default_min_kn"] = _check_range("min_kn", min_kn, ALERT_KN_RANGE)
    if max_kn is not None:
        values["default_max_kn"] = _check_range("max_kn", max_kn, ALERT_KN_RANGE)
    current = get_profile(db, user_id)
    try:
        ProfileDefaults(
            default_min_kn=values.get("default_min_kn", current["default_min_kn"]),
            default_max_kn=values.get("default_max_kn", current["default_max_kn"]),
        )
    except ValueError as exc:
        raise AdminError(f"invalid profile: {short_error(exc)}") from None
    count = db.update("profiles", values, filters={"user_id": f"eq.{user_id}"})
    if count != 1:
        raise AdminError("profile not updated")
    return get_profile(db, user_id)


def format_profile(row: dict[str, Any]) -> list[str]:
    def show(value: Any) -> str:
        return "-" if value is None else str(value)

    quiver = row.get("quiver_m2") or []
    return [
        f"weight_kg: {show(row.get('weight_kg'))}",
        f"level: {show(row.get('level'))}",
        "quiver_m2: " + (",".join(f"{s:g}" for s in quiver) if quiver else "-"),
        f"default_min_kn: {show(row.get('default_min_kn'))}",
        f"default_max_kn: {show(row.get('default_max_kn'))}",
    ]


# -- favorites --------------------------------------------------------------------------------


def add_favorite(db: SupabaseRest, user_id: str, spot_id: str) -> FavoriteAdded:
    unknown = AdminError(f"unknown spot '{spot_id}'")
    if not re.fullmatch(SPOT_ID_PATTERN, spot_id):
        raise unknown
    spots = db.select("spots", columns="id,name,verified", filters={"id": f"eq.{spot_id}"})
    if not spots:
        raise unknown
    verified = bool(spots[0]["verified"])
    existing = db.select(
        "favorites",
        columns="user_id,spot_id",
        filters={"user_id": f"eq.{user_id}", "spot_id": f"eq.{spot_id}"},
    )
    if existing:
        return FavoriteAdded(False, verified)
    try:
        db.insert("favorites", [{"user_id": user_id, "spot_id": spot_id}])
    except DatabaseError as exc:
        if exc.code == FK_VIOLATION:
            raise AdminError("unknown user id (no Supabase auth user with this id)") from None
        raise
    return FavoriteAdded(True, verified)


def remove_favorite(db: SupabaseRest, user_id: str, spot_id: str) -> bool:
    count = db.delete("favorites", filters={"user_id": f"eq.{user_id}", "spot_id": f"eq.{spot_id}"})
    return count > 0


def list_favorites(db: SupabaseRest, user_id: str) -> list[FavoriteInfo]:
    user = {"user_id": f"eq.{user_id}"}
    favorites = db.select("favorites", columns="user_id,spot_id", filters=user, order="spot_id")
    if not favorites:
        return []
    spot_ids = [f["spot_id"] for f in favorites]
    spots = {
        r["id"]: r
        for r in db.select("spots", columns="id,name,verified", filters={"id": in_filter(spot_ids)})
    }
    with_rule = {
        r["spot_id"] for r in db.select("alert_rules", columns="user_id,spot_id", filters=user)
    }
    return [
        FavoriteInfo(
            spot_id=sid,
            name=str(spots.get(sid, {}).get("name", sid)),
            verified=bool(spots.get(sid, {}).get("verified", False)),
            has_rule=sid in with_rule,
        )
        for sid in spot_ids
    ]


# -- rules ------------------------------------------------------------------------------------


def set_rule(
    db: SupabaseRest,
    user_id: str,
    spot_id: str,
    *,
    min_kn: int | None = None,
    max_kn: int | None = None,
    dir_classes: list[DirClass] | None = None,
    weekdays: list[int] | None = None,
    earliest_local: time | None = None,
    latest_local: time | None = None,
    min_go_hours: int | None = None,
    days_ahead: int | None = None,
    enabled: bool | None = None,
) -> AlertRule:
    given: dict[str, Any] = {}
    if min_kn is not None:
        given["min_kn"] = _check_range("min_kn", min_kn, ALERT_KN_RANGE)
    if max_kn is not None:
        given["max_kn"] = _check_range("max_kn", max_kn, ALERT_KN_RANGE)
    if dir_classes is not None:
        given["dir_classes"] = [c.value for c in dir_classes]
    if weekdays is not None:
        given["weekdays"] = sorted(set(weekdays))
    if earliest_local is not None:
        given["earliest_local"] = earliest_local
    if latest_local is not None:
        given["latest_local"] = latest_local
    if min_go_hours is not None:
        given["min_go_hours"] = _check_range("min_go_hours", min_go_hours, MIN_GO_HOURS_RANGE)
    if days_ahead is not None:
        given["days_ahead"] = _check_range("days_ahead", days_ahead, DAYS_AHEAD_RANGE)
    if enabled is not None:
        given["enabled"] = enabled
    if not given:
        raise AdminError("nothing to change")

    key = {"user_id": f"eq.{user_id}", "spot_id": f"eq.{spot_id}"}
    if not db.select("favorites", columns="user_id,spot_id", filters=key):
        raise AdminError(
            f"{spot_id} is not a favorite of this user; run 'shakka admin favorite add' first"
        )
    existing = db.select("alert_rules", columns=RULE_COLUMNS, filters=key)
    merged = {name: (existing[0].get(name) if existing else None) for name in RULE_FIELDS}
    merged.update(given)
    spot_rows = db.select("spots", columns=",".join(SPOT_COLUMNS), filters={"id": f"eq.{spot_id}"})
    profile_rows = db.select(
        "profiles", columns=PROFILE_COLUMNS, filters={"user_id": f"eq.{user_id}"}
    )
    try:
        override = AlertRuleOverride.from_row(merged)
        if not spot_rows:
            raise ValueError("spot not found")
        profile = ProfileDefaults.from_row(profile_rows[0]) if profile_rows else None
        rule = resolve_rule(SpotProfile.from_row(spot_rows[0]), profile, override)
    except ValueError as exc:
        raise AdminError(f"invalid rule: {short_error(exc)}") from None
    if existing:
        db.update("alert_rules", given, filters=key)
    else:
        db.insert("alert_rules", [{"user_id": user_id, "spot_id": spot_id, **given}])
    return rule


# -- preview ----------------------------------------------------------------------------------


def preview_alerts(
    db: SupabaseRest, user_id: str, *, now: datetime, base_url: str | None
) -> list[FavoritePlan]:
    """What an alert run would do for this user. Never writes."""
    try:
        base = normalize_base_url(base_url)
    except ValueError:
        raise AdminError("invalid APP_BASE_URL") from None
    ctx = load_alert_context(db, now=now, user_id=user_id)
    return [
        plan_favorite(fav, ctx.inputs.get(fav.spot_id), now=now, base_url=base)
        for fav in ctx.favorites
    ]


def format_preview(plans: Sequence[FavoritePlan]) -> list[str]:
    lines = [f"alerts preview: {len(plans)} favorite(s)"]
    for plan in plans:
        if plan.outcome == "ineligible":
            lines.append(f"spot {plan.spot_id}: not eligible ({plan.detail})")
            continue
        if plan.outcome == "disabled":
            lines.append(f"spot {plan.spot_id}: disabled")
            continue
        if plan.outcome == "skipped":
            lines.append(f"spot {plan.spot_id}: skipped ({plan.detail})")
            continue
        assert plan.rule is not None
        lines.append(f"spot {plan.spot_id}")
        lines.append(f"  rule: {format_rule(plan.rule)}")
        if plan.windows:
            lines.append(f"  windows: {len(plan.windows)}")
            for w in plan.windows:
                winds = [h.wind_kn for h in w.hours if h.wind_kn is not None]
                lo, hi = math.floor(min(winds) + 0.5), math.floor(max(winds) + 0.5)
                lines.append(f"    {format_window_local(w.start, w.end)} · {lo}–{hi} kn")
        else:
            lines.append("  windows: none")
        active = sum(1 for e in plan.previous if e.status == "active")
        cancelled = sum(1 for e in plan.previous if e.status == "cancelled")
        lines.append(f"  state: {active} active, {cancelled} cancelled (snapshot = last reported)")
        if not plan.messages:
            lines.append("  no change")
        for _, message in plan.messages:
            lines.append(f"  {message.kind.value}: {message.title}")
            lines.extend(f"    {line}" for line in message.body.splitlines())
            if message.go_url is not None:
                lines.append(f"    link: {message.go_url}")
    return lines


# -- runner -----------------------------------------------------------------------------------


def run_admin(
    label: str,
    action: Callable[[SupabaseRest, datetime, Settings], list[str]],
    *,
    echo: Callable[[str], None],
) -> int:
    """Run one admin action. Only AdminError and DatabaseError are caught; anything else is a
    programming error and fails with a traceback."""
    try:
        settings = get_settings()
    except ValidationError:
        echo("admin: configuration incomplete; run shakka doctor")
        return 1
    db = runtime.open_db(settings)
    try:
        lines = action(db, runtime.utcnow(), settings)
    except AdminError as exc:
        echo(f"{label}: {exc}")
        return 1
    except DatabaseError as exc:
        echo(f"{label}: database error: {exc}")
        return 1
    finally:
        db.close()
    for line in lines:
        echo(line)
    return 0
