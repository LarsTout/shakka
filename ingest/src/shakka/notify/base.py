"""Channel interface for alert delivery (WP-17).

Nothing in here ever holds a message, endpoint, key or user id in an error text or repr.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from shakka.domain.messages import AlertMessage

WEBPUSH_CHANNEL: Final = "webpush"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    ok: bool
    permanent_failure: bool
    detail: str  # "ok", "HTTP <status>", "WebPushException" or an exception type name

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
