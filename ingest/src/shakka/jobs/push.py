"""Push delivery for the alert job (WP-17): targets, one event, subscription upkeep, test push.

Logging carries counts and exception types only: never an endpoint, key, user id, message or
the VAPID subject.
"""

import logging
from collections import defaultdict
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pydantic import ValidationError

from shakka.config import get_settings
from shakka.db import DatabaseError, SupabaseRest, in_filter, iso_utc
from shakka.domain.messages import AlertMessage
from shakka.domain.push import PushPayload
from shakka.jobs import runtime
from shakka.jobs.inputs import db_error_summary, require_aware
from shakka.notify.base import (
    WEBPUSH_CHANNEL,
    DeliveryResult,
    DeliveryTarget,
    Notifier,
    PushTarget,
)
from shakka.notify.webpush import WebPushNotifier, generate_vapid_keys, notifiers_from_settings

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


def run_test_push_cli(user_id: str, *, echo: Callable[[str], None]) -> int:
    """`shakka alerts test-push`. Never prints an endpoint, key, user id or the subject."""
    try:
        settings = get_settings()
    except ValidationError:
        echo("test-push: configuration incomplete; run shakka doctor")
        return 1
    try:
        notifiers = notifiers_from_settings(settings)
    except ValueError as exc:  # a fixed text without values
        echo(f"test-push: invalid VAPID configuration: {exc}")
        return 1
    notifier = notifiers.get(WEBPUSH_CHANNEL)
    if not isinstance(notifier, WebPushNotifier):
        echo(
            "test-push: push is disabled; set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and "
            "VAPID_SUBJECT (docs/RUNBOOK.md, section 14)"
        )
        return 1
    db = runtime.open_db(settings)
    try:
        results = send_test_push(db, notifier, user_id, now=runtime.utcnow())
    except DatabaseError as exc:
        echo(f"test-push: database error: {exc}")
        return 1
    finally:
        db.close()
    if not results:
        echo(
            "test-push: no push subscriptions for this user; turn on notifications in the app first"
        )
        return 1
    sent = failed = removed = 0
    for item in results:
        result = item.result
        if result.ok:
            sent += 1
            echo(f"test-push: device {item.device}: ok")
        elif result.permanent_failure:
            failed += 1
            removed += 1
            echo(f"test-push: device {item.device}: gone ({result.detail}); subscription removed")
        else:
            failed += 1
            echo(f"test-push: device {item.device}: failed ({result.detail})")
    echo(f"test-push: sent={sent} failed={failed} removed={removed}")
    echo("test-push: ok" if sent else "test-push: failed")
    return 0 if sent else 1


def run_vapid_keys_cli(*, echo: Callable[[str], None]) -> int:
    """`shakka alerts vapid-keys`: prints a new key pair. Reads no settings, no database."""
    keys = generate_vapid_keys()
    echo(f"VAPID_PUBLIC_KEY={keys.public_key}")
    echo(f"VAPID_PRIVATE_KEY={keys.private_key}")
    echo(
        "note: put both in .env and in the GitHub Secrets (docs/RUNBOOK.md, section 14). "
        "The web app uses the same public key as PUBLIC_VAPID_PUBLIC_KEY. "
        "Never commit or share the private key."
    )
    return 0
