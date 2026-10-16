"""Fixtures for the Web Push tests (WP-17): dummy keys, fake notifier, recording webpush."""

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from fakes import FakeSupabase
from job_fixtures import NOW
from shakka.domain.messages import AlertMessage
from shakka.domain.push import PushPayload
from shakka.notify.base import DeliveryResult, PushTarget
from shakka.notify.webpush import generate_vapid_keys

KEYS = generate_vapid_keys()  # fresh dummy pair per test session
SUBJECT = "mailto:test@example.org"
OK = DeliveryResult(True, False, "ok")
GONE = DeliveryResult(False, True, "HTTP 410")
DOWN = DeliveryResult(False, False, "HTTP 503")


def endpoint(user_id: str, n: int) -> str:
    return f"https://fcm.googleapis.com/fcm/send/{user_id[:8]}-{n}"


def sub_row(user_id: str, n: int, *, created_at: datetime | None = None) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "endpoint": endpoint(user_id, n),
        "p256dh": f"BP256DH{n}",
        "auth": f"AUTH{n}",
        "created_at": created_at or NOW - timedelta(days=n),
    }


def seed_subs(db: FakeSupabase, user_id: str, n: int) -> list[str]:
    """Seed `n` subscriptions (numbered 1..n); returns the endpoints."""
    db.seed("push_subscriptions", [sub_row(user_id, i) for i in range(1, n + 1)])
    return [endpoint(user_id, i) for i in range(1, n + 1)]


def make_target(n: int = 1, user_id: str = "11111111-1111-4111-8111-111111111111") -> PushTarget:
    row = sub_row(user_id, n)
    return PushTarget(
        f"00000000-0000-4000-9000-{n:012d}", row["endpoint"], row["p256dh"], row["auth"]
    )


@dataclass
class Sent:
    subscription_id: str
    endpoint: str
    tag: str
    kind: str
    title: str


class FakeNotifier:
    channel = "webpush"

    def __init__(
        self,
        results: Mapping[str, DeliveryResult | list[DeliveryResult]] | None = None,
        raises: Exception | None = None,
    ) -> None:
        """Per endpoint a fixed result or a list consumed in order (last repeats); default OK."""
        self._results = {
            k: (list(v) if isinstance(v, list) else [v]) for k, v in (results or {}).items()
        }
        self._raises = raises
        self.calls: list[Sent] = []
        self.payload_calls: list[tuple[PushTarget, PushPayload]] = []

    def set_result(self, endpoint_: str, result: DeliveryResult | list[DeliveryResult]) -> None:
        self._results[endpoint_] = list(result) if isinstance(result, list) else [result]

    def send(self, target: PushTarget, message: AlertMessage, *, tag: str) -> DeliveryResult:
        self.calls.append(
            Sent(target.subscription_id, target.endpoint, tag, message.kind.value, message.title)
        )
        if self._raises is not None:
            raise self._raises
        return self._next(target)

    def send_payload(self, target: PushTarget, payload: PushPayload) -> DeliveryResult:
        self.payload_calls.append((target, payload))
        if self._raises is not None:
            raise self._raises
        return self._next(target)

    def _next(self, target: PushTarget) -> DeliveryResult:
        queue = self._results.get(target.endpoint)
        if not queue:
            return OK
        return queue.pop(0) if len(queue) > 1 else queue[0]


class FakeResponse:
    """For WebPushException(response=...)."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = "body with endpoint https://fcm.googleapis.com/fcm/send/ENDPOINT-SECRET-123"
        self.headers: dict[str, str] = {}


@dataclass
class RecordingWebpush:
    """A webpush_fn that simulates pywebpush: sets aud in the given claims dict."""

    raises: BaseException | None = None
    per_endpoint: Mapping[str, BaseException] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> object:
        claims = kwargs["vapid_claims"]
        copied = {
            **kwargs,
            "vapid_claims": copy.deepcopy(claims),
            "claims_id": id(claims),
            "claims_obj": claims,
        }  # keep alive: ids can be reused
        self.calls.append(copied)
        parts = urlsplit(kwargs["subscription_info"]["endpoint"])
        claims["aud"] = f"{parts.scheme}://{parts.netloc}"
        error = self.per_endpoint.get(kwargs["subscription_info"]["endpoint"], self.raises)
        if error is not None:
            raise error
        return object()
