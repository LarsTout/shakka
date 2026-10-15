"""Alert job: per favorite the effective rule, windows, deduplication, messages and state.

Events are delivered as Web Push (WP-17) when a notifier is given. The work per favorite is
split in steps: `load_alert_context` (all reads), `plan_favorite` (no I/O), `assign_new_ids`
and `deliver_plan` (the only network I/O; between planning and storing) and `store_plan` (only
writes to alert_state). Delivery is all-or-nothing per (user, spot): if no delivery of an
event succeeded and one failure was not permanent, nothing of that favorite is stored, so
the next run computes the same diff and delivers again.

Alerts exist only for spots with `verified: true`. A favorite whose planning raises a
ValueError is `skipped` and nothing is written for it; one broken row never stops the job.
That also holds for a favorite without forecast data: the rule, profile and state rows are
parsed before the "no forecast data" check, so a broken rule row plus no forecast gives
`skipped` (exit 1), not `ineligible`. A broken row must stand out.

Logging carries counts and exception types only: no user ids, no message texts and no spot
ids of favorites (a favorite is a user preference). `run_alerts` puts no user id in request
URLs either, because httpx logs every URL at INFO; spot ids of favorite spots do appear in
URLs (spots?id=in.(...), forecast_hours?spot_id=eq.<id>), which is aggregated public data and
is covered by WP-11 setting the httpx and httpcore loggers to WARNING.
"""

import logging
import uuid
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

from pydantic import ValidationError

from shakka.config import get_settings
from shakka.db import DatabaseError, SupabaseRest, iso_utc
from shakka.domain.alerts import (
    RULE_FIELDS,
    AlertRule,
    AlertRuleOverride,
    ProfileDefaults,
    Window,
    find_windows,
    resolve_rule,
    rider_limits,
)
from shakka.domain.dedup import (
    ALERT_STATE_COLUMNS,
    AlertEvent,
    AlertEventKind,
    AlertStateEntry,
    DiffResult,
    diff_windows,
)
from shakka.domain.direction import DirClass
from shakka.domain.evaluation import evaluate_spot
from shakka.domain.kite import KiteAdvice, RiderProfile, recommend_for_window
from shakka.domain.messages import AlertMessage, build_go_url, render_alert
from shakka.domain.push import push_tag
from shakka.domain.spot import SpotProfile
from shakka.jobs import runtime
from shakka.jobs.inputs import (
    MAX_FETCH_AGE,
    SpotInputs,
    db_error_summary,
    load_inputs,
    require_aware,
    short_error,
)
from shakka.jobs.push import (
    TargetsLoad,
    deliver_event,
    load_all_targets_checked,
    update_subscriptions,
)
from shakka.jobs.push import load_targets as load_targets  # explicit re-export (contract)
from shakka.notify.base import WEBPUSH_CHANNEL, DeliveryTarget, Notifier
from shakka.notify.webpush import notifiers_from_settings

logger = logging.getLogger(__name__)

ALERT_STATE_RETENTION: Final = timedelta(hours=48)
PROFILE_COLUMNS: Final = "user_id,weight_kg,level,quiver_m2,default_min_kn,default_max_kn"
RULE_COLUMNS: Final = "user_id,spot_id," + ",".join(RULE_FIELDS)
STATE_COLUMNS: Final = "user_id," + ",".join(ALERT_STATE_COLUMNS)
PROBE_START: Final = datetime(2026, 1, 1, tzinfo=UTC)
PlanOutcome = Literal["planned", "ineligible", "disabled", "skipped"]


@dataclass(frozen=True, slots=True)
class RenderedAlert:
    user_id: str
    state_id: str | None  # alert_state.id after storing; None in dry_run for new rows
    message: AlertMessage


@dataclass(frozen=True, slots=True)
class AlertJobResult:
    users: int  # distinct user_ids with at least one favorite
    events: int  # == len(messages)
    messages: list[RenderedAlert]  # by (user_id, spot_id), then state_index
    favorites: int = 0
    ineligible: int = 0  # spot not loaded, not verified, or no forecast data
    disabled: int = 0
    skipped: int = 0  # ValueError while planning (bad rule/profile/state row)
    write_errors: int = 0
    deleted: int = 0  # alert_state rows removed (window_end < now - 48h)
    errors: tuple[str, ...] = ()  # "spot <id>: ..." -- never a user id
    sent: int = 0  # successful deliveries (event x subscription)
    failed: int = 0  # failed deliveries, permanent or not
    no_target: int = 0  # events of users without a live subscription
    deferred: int = 0  # favorites not stored because of a retryable failure
    removed: int = 0  # push subscriptions deleted after 404/410
    push_enabled: bool = False  # webpush notifier given and not a dry run
    push_failures: Mapping[str, int] = field(default_factory=dict)  # detail -> count
    blocked_targets: int = 0  # subscriptions skipped: push service host not allowed
    push_non_retryable: int = 0  # deliveries that failed without retry; event lost for the device


@dataclass(frozen=True, slots=True)
class FavoriteRows:
    user_id: str
    spot_id: str
    profile_row: dict[str, Any] | None
    rule_row: dict[str, Any] | None
    state_rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class AlertContext:
    favorites: list[FavoriteRows]  # sorted by (user_id, spot_id)
    inputs: dict[str, SpotInputs]


@dataclass(frozen=True, slots=True)
class FavoritePlan:
    user_id: str
    spot_id: str
    outcome: PlanOutcome
    detail: str | None = None  # reason for ineligible / skipped
    spot: SpotProfile | None = None
    rule: AlertRule | None = None
    windows: tuple[Window, ...] = ()
    previous: tuple[AlertStateEntry, ...] = ()
    diff: DiffResult | None = None  # set iff outcome == "planned"
    messages: tuple[tuple[int, AlertMessage], ...] = ()  # (state_index, message)


def normalize_base_url(value: str | None) -> str | None:
    """None or blank -> None; otherwise the stripped URL, checked with build_go_url.

    ValueError for an invalid URL (a configuration error that must be noticed). Idempotent.
    """
    if value is None or not value.strip():
        return None
    base = value.strip()
    try:
        build_go_url(base, "probe", PROBE_START, PROBE_START + timedelta(hours=1))
    except ValueError:
        raise ValueError(
            "invalid APP_BASE_URL: expected http(s)://host[/path] without query, fragment or spaces"
        ) from None
    return base


def rider_from_profile(row: Mapping[str, Any] | None) -> RiderProfile | None:
    """A RiderProfile, or None without profile, weight or level (no kite line then)."""
    if row is None or row.get("weight_kg") is None or row.get("level") is None:
        return None
    return RiderProfile(
        weight_kg=row["weight_kg"], level=row["level"], quiver_m2=row.get("quiver_m2") or []
    )


def window_for(event: AlertEvent, windows: Sequence[Window]) -> Window:
    """The window an event describes; ValueError if there is none."""
    if event.current is None:
        raise ValueError("event has no current window")
    for w in windows:
        if w.start == event.current.start and w.end == event.current.end:
            return w
    raise ValueError("no window matches the event")


def load_alert_context(
    db: SupabaseRest, *, now: datetime, user_id: str | None = None
) -> AlertContext:
    """All database reads of an alert run. With `user_id` (preview) only that user's rows.

    Without `user_id` (the hourly run) no user id is put in any request URL.
    """
    require_aware(now)
    user_filter = None if user_id is None else {"user_id": f"eq.{user_id}"}
    fav_rows = db.select(
        "favorites", columns="user_id,spot_id", filters=user_filter, order="user_id,spot_id"
    )
    if not fav_rows:
        return AlertContext([], {})

    rules = {
        (r["user_id"], r["spot_id"]): r
        for r in db.select("alert_rules", columns=RULE_COLUMNS, filters=user_filter)
    }
    profiles = {
        r["user_id"]: r for r in db.select("profiles", columns=PROFILE_COLUMNS, filters=user_filter)
    }
    states: dict[tuple[str, str], list[dict[str, Any]]] = {}
    state_queries: list[dict[str, str]] = [
        {"status": "eq.active"},
        {"status": "eq.cancelled", "window_end": f"gt.{iso_utc(now)}"},
    ]
    for extra in state_queries:
        rows = db.select(
            "alert_state", columns=STATE_COLUMNS, filters={**(user_filter or {}), **extra}
        )
        for r in rows:
            states.setdefault((r["user_id"], r["spot_id"]), []).append(r)

    favorites = [
        FavoriteRows(
            user_id=f["user_id"],
            spot_id=f["spot_id"],
            profile_row=profiles.get(f["user_id"]),
            rule_row=rules.get((f["user_id"], f["spot_id"])),
            state_rows=states.get((f["user_id"], f["spot_id"]), []),
        )
        for f in fav_rows
    ]
    inputs = load_inputs(
        db, now=now, spot_ids={f.spot_id for f in favorites}, max_fetch_age=MAX_FETCH_AGE
    )
    return AlertContext(favorites, inputs)


def plan_favorite(
    fav: FavoriteRows, inputs: SpotInputs | None, *, now: datetime, base_url: str | None
) -> FavoritePlan:
    """Rule, evaluation, windows, diff and messages for one favorite. No I/O.

    `base_url` must already be normalized. Order matters: the rule, profile and state rows are
    parsed before the forecast check, so a broken row is `skipped` even without forecasts.
    """
    require_aware(now)
    uid, sid = fav.user_id, fav.spot_id
    if inputs is None:
        return FavoritePlan(
            uid,
            sid,
            "ineligible",
            "spot not loaded (unknown, invalid or without coordinates)",
        )
    spot = inputs.spot
    if not spot.verified:
        return FavoritePlan(uid, sid, "ineligible", "spot not verified", spot=spot)
    try:
        profile = None if fav.profile_row is None else ProfileDefaults.from_row(fav.profile_row)
        override = None if fav.rule_row is None else AlertRuleOverride.from_row(fav.rule_row)
        rule = resolve_rule(spot, profile, override)
        rider = rider_from_profile(fav.profile_row)
        previous = [AlertStateEntry.from_row(r) for r in fav.state_rows]
        if rule.enabled is False:
            return FavoritePlan(uid, sid, "disabled", spot=spot, rule=rule)
        if not inputs.forecasts:
            return FavoritePlan(uid, sid, "ineligible", "no forecast data", spot=spot, rule=rule)
        evaluations = evaluate_spot(spot, inputs.forecasts, inputs.tides, rider_limits(rule))
        windows = find_windows(evaluations, rule, now=now)
        diff = diff_windows(previous, windows, now=now)
        messages: list[tuple[int, AlertMessage]] = []
        for event in diff.events:
            kite: KiteAdvice | None = None
            if event.kind != AlertEventKind.CANCELLED and rider is not None:
                w = window_for(event, windows)
                kite = recommend_for_window(
                    rider, [h.wind_kn for h in w.hours if h.wind_kn is not None]
                )
            message = render_alert(event, spot, kite=kite, tides=inputs.tides, base_url=base_url)
            messages.append((event.state_index, message))
    except ValueError as exc:
        return FavoritePlan(
            uid, sid, "skipped", f"{type(exc).__name__}: {short_error(exc)}", spot=spot
        )
    return FavoritePlan(
        uid,
        sid,
        "planned",
        spot=spot,
        rule=rule,
        windows=tuple(windows),
        previous=tuple(previous),
        diff=diff,
        messages=tuple(messages),
    )


def update_rank(old: AlertStateEntry, new: AlertStateEntry) -> int:
    """Write order of updates: 0 expired/cancelled, 1 active and not longer, 2 the rest."""
    if new.status in ("expired", "cancelled"):
        return 0
    if (
        new.status == "active"
        and new.window_start >= old.window_start
        and new.window_end <= old.window_end
    ):
        return 1
    return 2


def store_plan(db: SupabaseRest, user_id: str, plan: FavoritePlan) -> list[str | None]:
    """Write a planned favorite to alert_state: updates first (shortest first), then inserts.

    Returns the id per index of `new_state`. Updates filter on `id` only (primary key; no user
    id in the URL). A DatabaseError goes to the caller; remaining writes are not done.
    """
    if plan.outcome != "planned" or plan.diff is None:
        raise ValueError("only a planned favorite can be stored")
    new_state = plan.diff.new_state
    previous = plan.previous
    ids: list[str | None] = [e.id for e in new_state]
    n = len(previous)
    changed = sorted(
        (i for i in range(n) if new_state[i] != previous[i]),
        key=lambda i: (update_rank(previous[i], new_state[i]), i),
    )
    for i in changed:
        row = new_state[i].to_row()
        row.pop("id", None)
        count = db.update("alert_state", row, filters={"id": f"eq.{previous[i].id}"})
        if count != 1:
            raise DatabaseError(f"update alert_state: expected 1 row, got {count}")
    for i in range(n, len(new_state)):
        stored = db.insert(
            "alert_state", [new_state[i].to_row() | {"user_id": user_id}], returning=True
        )
        ids[i] = str(stored[0]["id"])
    return ids


def delete_old_alert_state(db: SupabaseRest, *, now: datetime) -> int:
    """Remove alert_state rows whose window ended more than 48 hours ago."""
    require_aware(now)
    return db.delete(
        "alert_state", filters={"window_end": f"lt.{iso_utc(now - ALERT_STATE_RETENTION)}"}
    )


def _new_state_id() -> str:
    return str(uuid.uuid4())


def assign_new_ids(plan: FavoritePlan, *, new_id: Callable[[], str] | None = None) -> FavoritePlan:
    """Give every not yet stored entry an id, so the push tag and the row match."""
    if plan.outcome != "planned" or plan.diff is None:
        raise ValueError("only a planned favorite can get ids")
    new_state = list(plan.diff.new_state)
    for i in range(len(plan.previous), len(new_state)):
        if new_state[i].id is None:
            new_state[i] = new_state[i].model_copy(update={"id": (new_id or _new_state_id)()})
    return replace(plan, diff=DiffResult(events=plan.diff.events, new_state=new_state))


@dataclass(frozen=True, slots=True)
class PlanDelivery:
    plan: FavoritePlan  # last_notified_at = now for notified events
    deferred: bool
    sent: int = 0
    failed: int = 0
    no_target: int = 0
    ok_ids: frozenset[str] = frozenset()
    gone_ids: frozenset[str] = frozenset()
    failures: tuple[str, ...] = ()
    non_retryable: int = 0


def deliver_plan(
    plan: FavoritePlan,
    notifier: Notifier,
    targets: Sequence[DeliveryTarget],
    *,
    now: datetime,
    gone: Collection[str] = (),
) -> PlanDelivery:
    """Deliver the events of a planned favorite, in order; stop at the first retryable one.

    `gone` are subscription ids already found dead in this run. Every entry with an event must
    have an id (`assign_new_ids`), because the tag is derived from it.
    """
    if plan.outcome != "planned" or plan.diff is None:
        raise ValueError("only a planned favorite can be delivered")
    new_state = plan.diff.new_state
    for index, _ in plan.messages:
        if new_state[index].id is None:
            raise ValueError("state id missing; call assign_new_ids first")
    gone_local = set(gone)
    gone_ids: set[str] = set()
    ok_ids: set[str] = set()
    failures: list[str] = []
    notified: set[int] = set()
    sent = failed = no_target = non_retryable = 0
    for index, message in plan.messages:  # sorted by state_index (WP-10)
        live = [t for t in targets if t.subscription_id not in gone_local]
        if not live:
            no_target += 1
            continue
        state_id = new_state[index].id
        assert state_id is not None
        d = deliver_event(notifier, live, message, tag=push_tag(state_id))
        sent += d.sent
        failed += d.failed
        non_retryable += d.non_retryable
        failures.extend(d.failures)
        ok_ids |= d.ok_ids
        gone_local |= d.gone_ids
        gone_ids |= d.gone_ids
        if d.sent:
            notified.add(index)
        if d.retryable:
            return PlanDelivery(
                plan,
                deferred=True,
                sent=sent,
                failed=failed,
                no_target=no_target,
                ok_ids=frozenset(ok_ids),
                gone_ids=frozenset(gone_ids),
                failures=tuple(failures),
                non_retryable=non_retryable,
            )
    stamped = [
        e.model_copy(update={"last_notified_at": now}) if i in notified else e
        for i, e in enumerate(new_state)
    ]
    return PlanDelivery(
        replace(plan, diff=DiffResult(events=plan.diff.events, new_state=stamped)),
        deferred=False,
        sent=sent,
        failed=failed,
        no_target=no_target,
        ok_ids=frozenset(ok_ids),
        gone_ids=frozenset(gone_ids),
        failures=tuple(failures),
        non_retryable=non_retryable,
    )


def run_alerts(
    db: SupabaseRest,
    *,
    now: datetime,
    base_url: str | None,
    dry_run: bool = False,
    notifiers: Mapping[str, Notifier] | None = None,
) -> AlertJobResult:
    """Compute, deliver and record alerts for all favorites. Returns the stored messages.

    Delivery needs a "webpush" notifier and is never done with `dry_run`; without a notifier
    the state is stored without delivery (as in M1). With `dry_run` nothing is written (not
    even the cleanup). ValueError for a naive `now` or an invalid `base_url`, before any read
    or write; DatabaseError while loading propagates. Never writes to stdout or stderr.
    """
    require_aware(now)
    base = normalize_base_url(base_url)
    ctx = load_alert_context(db, now=now)
    push = None if dry_run else (notifiers or {}).get(WEBPUSH_CHANNEL)
    # One select without a user filter: no user id in a request URL (WP-10 A9).
    loaded = (
        load_all_targets_checked(db) if push is not None and ctx.favorites else TargetsLoad({}, 0)
    )
    targets = loaded.targets

    messages: list[RenderedAlert] = []
    errors: list[str] = []
    counts: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    gone_all: set[str] = set()
    ok_all: set[str] = set()
    for fav in ctx.favorites:
        plan = plan_favorite(fav, ctx.inputs.get(fav.spot_id), now=now, base_url=base)
        if plan.outcome == "skipped":
            counts["skipped"] += 1
            errors.append(f"spot {fav.spot_id}: {plan.detail}")
            logger.warning("alerts: skipped a favorite (%s)", (plan.detail or "").split(":", 1)[0])
            continue
        if plan.outcome in ("ineligible", "disabled"):
            counts[plan.outcome] += 1
            continue
        assert plan.diff is not None
        if dry_run:
            ids: list[str | None] = [e.id for e in plan.diff.new_state]
        else:
            plan = assign_new_ids(plan)
            if push is not None and plan.messages:
                d = deliver_plan(plan, push, targets.get(fav.user_id, []), now=now, gone=gone_all)
                counts["sent"] += d.sent
                counts["failed"] += d.failed
                counts["no_target"] += d.no_target
                gone_all |= d.gone_ids
                ok_all |= d.ok_ids
                failures.update(d.failures)
                counts["push_non_retryable"] += d.non_retryable
                if d.deferred:
                    counts["deferred"] += 1
                    logger.warning(
                        "alerts: no delivery succeeded for a favorite; state kept for a retry"
                    )
                    continue
                plan = d.plan
            try:
                ids = store_plan(db, fav.user_id, plan)
            except DatabaseError as exc:
                counts["write_errors"] += 1
                errors.append(f"spot {fav.spot_id}: {db_error_summary(exc)}")
                logger.warning("alerts: storing alert state failed for a favorite (DatabaseError)")
                continue
        for index, message in plan.messages:
            messages.append(RenderedAlert(fav.user_id, ids[index], message))

    removed = 0
    if push is not None and (gone_all or ok_all):
        update = update_subscriptions(db, gone=gone_all, ok=ok_all, now=now)
        removed = update.removed
        for line in update.errors:
            counts["write_errors"] += 1
            errors.append(line)
        if update.errors:
            logger.warning("alerts: updating push subscriptions failed (DatabaseError)")

    deleted = 0 if dry_run else delete_old_alert_state(db, now=now)
    kinds = Counter(m.message.kind for m in messages)
    users = len({f.user_id for f in ctx.favorites})
    logger.info(
        "alerts: users=%d favorites=%d events=%d new=%d improved=%d worsened=%d cancelled=%d "
        "ineligible=%d disabled=%d skipped=%d write_errors=%d deleted=%d dry_run=%s "
        "sent=%d failed=%d no_target=%d deferred=%d removed=%d blocked=%d non_retryable=%d push=%s",
        users,
        len(ctx.favorites),
        len(messages),
        kinds[AlertEventKind.NEW],
        kinds[AlertEventKind.IMPROVED],
        kinds[AlertEventKind.WORSENED],
        kinds[AlertEventKind.CANCELLED],
        counts["ineligible"],
        counts["disabled"],
        counts["skipped"],
        counts["write_errors"],
        deleted,
        dry_run,
        counts["sent"],
        counts["failed"],
        counts["no_target"],
        counts["deferred"],
        removed,
        loaded.blocked,
        counts["push_non_retryable"],
        push is not None,
    )
    return AlertJobResult(
        users=users,
        events=len(messages),
        messages=messages,
        favorites=len(ctx.favorites),
        ineligible=counts["ineligible"],
        disabled=counts["disabled"],
        skipped=counts["skipped"],
        write_errors=counts["write_errors"],
        deleted=deleted,
        errors=tuple(errors),
        sent=counts["sent"],
        failed=counts["failed"],
        no_target=counts["no_target"],
        deferred=counts["deferred"],
        removed=removed,
        push_enabled=push is not None,
        push_failures=dict(failures),
        blocked_targets=loaded.blocked,
        push_non_retryable=counts["push_non_retryable"],
    )


def format_rule(rule: AlertRule) -> str:
    dirs = ",".join(d.value for d in DirClass if d in rule.dir_classes)
    days = ",".join(str(d) for d in sorted(rule.weekdays))
    after = "-" if rule.earliest_local is None else f"{rule.earliest_local:%H:%M}"
    before = "-" if rule.latest_local is None else f"{rule.latest_local:%H:%M}"
    return (
        f"min {rule.min_kn:g} kn, max {rule.max_kn:g} kn, dirs {dirs}, days {days}, "
        f"after {after}, before {before}, min {rule.min_go_hours} h, "
        f"{rule.days_ahead} days ahead, {'enabled' if rule.enabled else 'disabled'}"
    )


def run_alerts_cli(*, dry_run: bool, echo: Callable[[str], None]) -> int:
    """Run the alert job from the CLI. Shows message texts: for local use only."""
    try:
        settings = get_settings()
    except ValidationError:
        echo("alerts: configuration incomplete; run shakka doctor")
        return 1
    try:
        base = normalize_base_url(settings.app_base_url)
    except ValueError:
        echo("alerts: invalid APP_BASE_URL")
        return 1
    try:
        notifiers = notifiers_from_settings(settings)
    except ValueError as exc:  # a fixed text without values
        echo(f"alerts: invalid VAPID configuration: {exc}")
        return 1
    db = runtime.open_db(settings)
    try:
        result = run_alerts(
            db, now=runtime.utcnow(), base_url=base, dry_run=dry_run, notifiers=notifiers
        )
    except DatabaseError as exc:
        echo(f"alerts: database error: {exc}")
        return 1
    finally:
        db.close()
    for item in result.messages:
        message = item.message
        echo(f"{message.kind.value} {message.spot_id}: {message.title}")
        for line in message.body.splitlines():
            echo(f"  {line}")
        if message.go_url is not None:
            echo(f"  link: {message.go_url}")
    kinds = Counter(item.message.kind for item in result.messages)
    echo(
        f"alerts: users={result.users} favorites={result.favorites} events={result.events} "
        f"(new={kinds[AlertEventKind.NEW]} improved={kinds[AlertEventKind.IMPROVED]} "
        f"worsened={kinds[AlertEventKind.WORSENED]} cancelled={kinds[AlertEventKind.CANCELLED]}) "
        f"ineligible={result.ineligible} disabled={result.disabled} skipped={result.skipped} "
        f"write_errors={result.write_errors} deleted={result.deleted}"
    )
    if dry_run:
        echo("alerts: dry run, nothing stored")
    if dry_run:
        echo("push: nothing sent (dry run)")
    elif not notifiers:
        echo("push: disabled (no VAPID configuration)")
    else:
        echo(
            f"push: sent={result.sent} failed={result.failed} no_target={result.no_target} "
            f"deferred={result.deferred} non_retryable={result.push_non_retryable} "
            f"removed={result.removed}"
        )
    for line in result.errors:
        echo(f"error   {line}")
    failed = result.skipped > 0 or result.write_errors > 0 or result.deferred > 0
    failed = failed or result.push_non_retryable > 0
    echo("alerts: failed" if failed else "alerts: ok")
    return 1 if failed else 0
