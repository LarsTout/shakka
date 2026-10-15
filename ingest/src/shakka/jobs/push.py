"""Push delivery for the alert job (WP-17): targets, one event, subscription upkeep, test push.

Logging carries counts and exception types only: never an endpoint, key, user id, message or
the VAPID subject.
"""

import logging
from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from shakka.db import DatabaseError, SupabaseRest, in_filter, iso_utc
from shakka.domain.messages import AlertMessage
from shakka.domain.push import PushPayload
from shakka.jobs.inputs import db_error_summary, require_aware
from shakka.notify.base import DeliveryResult, DeliveryTarget, Notifier, PushTarget
from shakka.notify.webpush import WebPushNotifier

logger = logging.getLogger(__name__)

MAX_TARGETS_PER_USER: Final = 10
SUBSCRIPTION_COLUMNS: Final = "id,user_id,endpoint,p256dh,auth,created_at"
SUBSCRIPTION_BATCH: Final = 100
TEST_PUSH_TITLE: Final = "Shakka: testmelding"
TEST_PUSH_BODY: Final = "Meldingen werken op dit apparaat."
TEST_PUSH_URL: Final = "/"
TEST_PUSH_TAG: Final = "shakka-test"


def _target_or_none(row: dict) -> PushTarget | None:
    try:
        return PushTarget.from_row(row)
    except ValueError:
        return None  # no values in the log


def load_targets(db: SupabaseRest, user_id: str) -> list[DeliveryTarget]:
    """The newest `MAX_TARGETS_PER_USER` subscriptions of one user (local use: CLI, WP-22)."""
    rows = db.select(
        "push_subscriptions",
        columns=SUBSCRIPTION_COLUMNS,
        filters={"user_id": f"eq.{user_id}"},
        order="created_at.desc",
        limit=MAX_TARGETS_PER_USER,
    )
    return [t for t in map(_target_or_none, rows) if t is not None]


def load_all_targets(db: SupabaseRest) -> dict[str, list[DeliveryTarget]]:
    """All subscriptions in one select without a filter, so no user id is put in a URL."""
    rows = db.select(
        "push_subscriptions", columns=SUBSCRIPTION_COLUMNS, order="user_id,created_at.desc"
    )
    grouped: dict[str, list[DeliveryTarget]] = defaultdict(list)
    for row in rows:
        target = _target_or_none(row)
        user_id = row.get("user_id")
        if target is None or not isinstance(user_id, str):
            continue
        if len(grouped[user_id]) < MAX_TARGETS_PER_USER:
            grouped[user_id].append(target)
    return dict(grouped)


@dataclass(frozen=True, slots=True)
class EventDelivery:
    sent: int
    failed: int
    retryable: bool  # sent == 0 and at least one non-permanent failure
    ok_ids: frozenset[str]
    gone_ids: frozenset[str]  # permanent failure (404/410)
    failures: tuple[str, ...]  # DeliveryResult.detail of every failed delivery


def deliver_event(
    notifier: Notifier, targets: Sequence[DeliveryTarget], message: AlertMessage, *, tag: str
) -> EventDelivery:
    ok_ids: set[str] = set()
    gone_ids: set[str] = set()
    failures: list[str] = []
    transient = 0
    for target in targets:
        try:
            result = notifier.send(target, message, tag=tag)
        except Exception as exc:  # the interface promises not to raise; stay safe
            logger.warning("push: a notifier raised (%s)", type(exc).__name__)
            result = DeliveryResult(False, False, type(exc).__name__)
        if result.ok:
            ok_ids.add(target.subscription_id)
            continue
        failures.append(result.detail)
        if result.permanent_failure:
            gone_ids.add(target.subscription_id)
        else:
            transient += 1
    sent = len(ok_ids)
    return EventDelivery(
        sent=sent,
        failed=len(failures),
        retryable=sent == 0 and transient > 0,
        ok_ids=frozenset(ok_ids),
        gone_ids=frozenset(gone_ids),
        failures=tuple(failures),
    )


@dataclass(frozen=True, slots=True)
class SubscriptionUpdate:
    removed: int
    errors: tuple[str, ...]  # "push_subscriptions: <db_error_summary>"


def update_subscriptions(
    db: SupabaseRest, *, gone: Collection[str], ok: Collection[str], now: datetime
) -> SubscriptionUpdate:
    """Delete dead subscriptions and stamp last_success_at on the working ones."""
    require_aware(now)
    gone_set = set(gone)
    ok_only = set(ok) - gone_set
    removed = 0
    errors: list[str] = []

    def batches(ids: set[str]) -> list[list[str]]:
        ordered = sorted(ids)
        return [
            ordered[i : i + SUBSCRIPTION_BATCH] for i in range(0, len(ordered), SUBSCRIPTION_BATCH)
        ]

    for block in batches(gone_set):
        try:
            removed += db.delete("push_subscriptions", filters={"id": in_filter(block)})
        except DatabaseError as exc:
            errors.append(f"push_subscriptions: {db_error_summary(exc)}")
    for block in batches(ok_only):
        try:
            db.update(
                "push_subscriptions",
                {"last_success_at": iso_utc(now)},
                filters={"id": in_filter(block)},
            )
        except DatabaseError as exc:
            errors.append(f"push_subscriptions: {db_error_summary(exc)}")
    return SubscriptionUpdate(removed=removed, errors=tuple(errors))


@dataclass(frozen=True, slots=True)
class TestPushResult:
    __test__ = False  # not a pytest class

    device: int  # 1-based, in load_targets order
    result: DeliveryResult


def send_test_push(
    db: SupabaseRest, notifier: WebPushNotifier, user_id: str, *, now: datetime
) -> list[TestPushResult]:
    """Send the test payload to every device of a user and update the subscriptions."""
    require_aware(now)
    targets = load_targets(db, user_id)
    payload = PushPayload(
        title=TEST_PUSH_TITLE, body=TEST_PUSH_BODY, url=TEST_PUSH_URL, tag=TEST_PUSH_TAG
    )
    results: list[TestPushResult] = []
    ok_ids: set[str] = set()
    gone_ids: set[str] = set()
    for number, target in enumerate(targets, start=1):
        result = notifier.send_payload(target, payload)
        results.append(TestPushResult(number, result))
        if result.ok:
            ok_ids.add(target.subscription_id)
        elif result.permanent_failure:
            gone_ids.add(target.subscription_id)
    if targets:
        update = update_subscriptions(db, gone=gone_ids, ok=ok_ids, now=now)
        for _ in update.errors:
            logger.warning("test-push: updating push subscriptions failed (DatabaseError)")
    return results
