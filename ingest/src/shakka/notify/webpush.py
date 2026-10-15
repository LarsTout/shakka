"""Web Push channel: pywebpush with VAPID (WP-17).

The notifier never puts an endpoint, key, subject, user id or message text in an exception,
a result or a log line. `str(exc)` of a pywebpush or requests error is never used: it carries
the response body or the URL.
"""

import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

import pywebpush
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid
from pywebpush import WebPushException

from shakka.config import Settings
from shakka.domain.messages import AlertMessage
from shakka.domain.push import PushPayload, build_push_payload
from shakka.notify.base import WEBPUSH_CHANNEL, DeliveryResult, Notifier, PushTarget

logger = logging.getLogger(__name__)

PUSH_TTL_S: Final = 12 * 60 * 60  # contract: TTL 12 hours
PUSH_TIMEOUT_S: Final = 10.0  # passed to requests.post via pywebpush
VAPID_PROBE_AUD: Final = "https://push.example.invalid"  # aud of the trial signature in __init__
INCOMPLETE_ERROR: Final = (
    "incomplete VAPID configuration: "
    "set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and VAPID_SUBJECT together"
)
SUBJECT_ERROR: Final = (
    "invalid VAPID_SUBJECT: expected mailto:<address> with a domain, "
    "or https://<host> without a path"
)
PRIVATE_KEY_ERROR: Final = (
    "invalid VAPID_PRIVATE_KEY: expected the base64url key from 'shakka alerts vapid-keys'"
)
PUBLIC_KEY_ERROR: Final = "VAPID_PUBLIC_KEY does not belong to VAPID_PRIVATE_KEY"
_PLACEHOLDER_SUBJECT: Final = "mailto:"  # the value in .env.example


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class VapidKeys:
    public_key: str = field(repr=True)  # base64url, 65-byte uncompressed point, no "="
    private_key: str = field(repr=False)  # base64url, 32 bytes, no "="


def generate_vapid_keys() -> VapidKeys:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return VapidKeys(public_key=_b64url(public), private_key=_b64url(private))


class WebPushNotifier:
    channel: str = WEBPUSH_CHANNEL

    def __init__(
        self,
        vapid_private_key: str,
        vapid_subject: str,
        *,
        ttl_s: int = PUSH_TTL_S,
        timeout_s: float = PUSH_TIMEOUT_S,
        webpush_fn: Callable[..., Any] | None = None,
    ) -> None:
        subject = vapid_subject.strip() if isinstance(vapid_subject, str) else ""
        if not subject or any(c.isspace() for c in subject):  # quick pre-check only
            raise ValueError(SUBJECT_ERROR)
        key = vapid_private_key.strip() if isinstance(vapid_private_key, str) else ""
        try:
            vapid = Vapid.from_string(private_key=key)  # parsed once, reused per send
        except Exception:
            raise ValueError(PRIVATE_KEY_ERROR) from None
        try:
            # Trial signature: the library decides what a valid subject is. Same instance
            # (same conf, strict check) as the one passed to webpush() later.
            vapid.sign({"sub": subject, "aud": VAPID_PROBE_AUD})
        except Exception:
            raise ValueError(SUBJECT_ERROR) from None
        self._vapid = vapid
        self._subject = subject
        self._ttl_s = ttl_s
        self._timeout_s = timeout_s
        self._webpush_fn = webpush_fn

    @property
    def public_key(self) -> str:
        point = self._vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        return _b64url(point)

    def __repr__(self) -> str:
        return "WebPushNotifier()"

    def send(self, target: PushTarget, message: AlertMessage, *, tag: str) -> DeliveryResult:
        try:
            payload = build_push_payload(message, tag=tag)
        except ValueError:
            return DeliveryResult(False, False, "ValueError")
        return self.send_payload(target, payload)

    def send_payload(self, target: PushTarget, payload: PushPayload) -> DeliveryResult:
        fn = self._webpush_fn or pywebpush.webpush  # looked up at call time (tests patch it)
        try:
            fn(
                subscription_info={
                    "endpoint": target.endpoint,
                    "keys": {"p256dh": target.p256dh, "auth": target.auth},
                },
                data=payload.to_json(),
                vapid_private_key=self._vapid,  # parsed py_vapid.Vapid instance
                vapid_claims={"sub": self._subject},  # NEW dict per call: webpush() adds aud/exp
                content_encoding="aes128gcm",
                ttl=self._ttl_s,
                timeout=self._timeout_s,
            )
        except WebPushException as exc:
            status = exc.status_code
            if status in (404, 410):
                return DeliveryResult(False, True, f"HTTP {status}")
            detail = "WebPushException" if status is None else f"HTTP {status}"
            return DeliveryResult(False, False, detail)
        except Exception as exc:
            return DeliveryResult(False, False, type(exc).__name__)
        return DeliveryResult(True, False, "ok")


def _absent(value: str | None, *, placeholder: str | None = None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or stripped == placeholder


def notifiers_from_settings(settings: Settings) -> dict[str, Notifier]:
    """The configured channels. {} if no VAPID variable is set; ValueError if incomplete."""
    private = (
        settings.vapid_private_key.get_secret_value()
        if settings.vapid_private_key is not None
        else None
    )
    public = settings.vapid_public_key
    subject = settings.vapid_subject
    absent = (
        _absent(public),
        _absent(private),
        _absent(subject, placeholder=_PLACEHOLDER_SUBJECT),
    )
    if all(absent):
        return {}
    if any(absent):
        raise ValueError(INCOMPLETE_ERROR)
    assert private is not None and public is not None and subject is not None
    notifier = WebPushNotifier(private, subject)
    if public.strip().rstrip("=") != notifier.public_key:
        raise ValueError(PUBLIC_KEY_ERROR)
    return {WEBPUSH_CHANNEL: notifier}
