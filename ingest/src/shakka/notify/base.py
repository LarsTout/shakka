"""Channel interface for alert delivery (WP-17).

Nothing in here ever holds a message, endpoint, key or user id in an error text or repr.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Protocol
from urllib.parse import urlsplit

from shakka.domain.messages import AlertMessage
from shakka.domain.push import PushPayload

WEBPUSH_CHANNEL: Final = "webpush"

# Push services we deliver to. jmt17.google.com is Chromium's FCM staging endpoint (Chrome Beta,
# Dev and Canary). Legacy GCM (android.googleapis.com) is switched off and stays out.
PUSH_SERVICE_HOSTS: Final = frozenset({"fcm.googleapis.com", "jmt17.google.com"})
PUSH_SERVICE_HOST_SUFFIXES: Final = (
    ".push.services.mozilla.com",
    ".push.apple.com",
    ".notify.windows.com",
)
BLOCKED_HOST_DETAIL: Final = "blocked host"


def endpoint_allowed(endpoint: str) -> bool:
    """https, no port, no userinfo, host in PUSH_SERVICE_HOSTS or a proper subdomain of a suffix."""
    try:
        parts = urlsplit(endpoint)
        if parts.scheme != "https" or parts.port is not None:
            return False
        if parts.username is not None or parts.password is not None or "@" in parts.netloc:
            return False
        host = parts.hostname
    except ValueError:
        return False
    if not host:
        return False
    if host in PUSH_SERVICE_HOSTS:
        return True
    return any(len(host) > len(sfx) and host.endswith(sfx) for sfx in PUSH_SERVICE_HOST_SUFFIXES)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    ok: bool
    permanent_failure: bool
    detail: str  # "ok", "HTTP <status>", "WebPushException" or an exception type name
    retryable: bool = True  # only meaningful when not ok and not permanent_failure

    def __post_init__(self) -> None:
        if self.ok and self.permanent_failure:
            raise ValueError("a delivery cannot be both ok and a permanent failure")
        if not self.detail:
            raise ValueError("detail must not be empty")


@dataclass(frozen=True, slots=True)
class PushTarget:
    subscription_id: str
    endpoint: str = field(repr=False)
    p256dh: str = field(repr=False)
    auth: str = field(repr=False)

    def __post_init__(self) -> None:
        for value in (self.subscription_id, self.endpoint, self.p256dh, self.auth):
            if not isinstance(value, str) or not value:
                raise ValueError("push target fields must be non-empty strings")

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "PushTarget":
        return cls(
            subscription_id=row.get("id"),  # type: ignore[arg-type]
            endpoint=row.get("endpoint"),  # type: ignore[arg-type]
            p256dh=row.get("p256dh"),  # type: ignore[arg-type]
            auth=row.get("auth"),  # type: ignore[arg-type]
        )


DeliveryTarget = PushTarget  # a later channel can widen this to a union


class Notifier(Protocol):
    channel: str

    def send(
        self, target: DeliveryTarget, message: AlertMessage, *, tag: str
    ) -> DeliveryResult: ...

    def send_payload(self, target: DeliveryTarget, payload: PushPayload) -> DeliveryResult: ...
