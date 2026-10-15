"""WebPushNotifier, VAPID configuration and keys (WP-17 AC-2, AC-8 at notifier level)."""

import base64
import json
import logging
import re

import py_vapid
import pytest
import requests
from pywebpush import WebPushException

from message_fixtures import GOLDEN_CASES
from push_fixtures import KEYS, SUBJECT, FakeResponse, RecordingWebpush, make_target
from shakka.config import Settings
from shakka.domain.dedup import AlertEventKind
from shakka.domain.messages import AlertMessage, render_alert
from shakka.domain.push import build_push_payload, to_push_text
from shakka.notify.base import DeliveryResult, PushTarget
from shakka.notify.webpush import (
    INCOMPLETE_ERROR,
    PRIVATE_KEY_ERROR,
    PUBLIC_KEY_ERROR,
    SUBJECT_ERROR,
    WebPushNotifier,
    generate_vapid_keys,
    notifiers_from_settings,
)


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c.name)
def test_payload_contract(case):
    rec = RecordingWebpush()
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=rec)
    target = make_target()
    message = render_alert(
        case.event, case.spot, kite=case.kite, tides=case.tides, base_url=case.base_url
    )
    result = n.send(target, message, tag="alert-x")
    assert result == DeliveryResult(True, False, "ok")
    (call,) = rec.calls
    data = json.loads(call["data"])
    assert set(data) == {"title", "body", "url", "tag"}
    text = to_push_text(message)
    assert data["title"] == text.title
    assert data["body"] == text.body
    assert len(call["data"].encode()) <= 3000
    assert call["vapid_claims"]["sub"] == SUBJECT
    assert call["ttl"] == 43200
    assert call["timeout"] == 10.0
    assert call["content_encoding"] == "aes128gcm"
    assert call["subscription_info"] == {
        "endpoint": target.endpoint,
        "keys": {"p256dh": target.p256dh, "auth": target.auth},
    }
    assert isinstance(call["vapid_private_key"], py_vapid.Vapid)
    assert data["url"] == (message.go_url or "/spot/test-strand")
    assert data["tag"] == "alert-x"


def test_fresh_claims_per_call():
    rec = RecordingWebpush()
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=rec)
    message = AlertMessage(
        spot_id="s", kind=AlertEventKind.NEW, title="Go: S", body="b", go_url=None
    )
    t1 = PushTarget("a", "https://fcm.googleapis.com/x", "P", "A")
    t2 = PushTarget("b", "https://jmt17.google.com/y", "P", "A")
    n.send(t1, message, tag="alert-1")
    n.send(t2, message, tag="alert-1")
    first, second = rec.calls
    assert first["claims_obj"] is not second["claims_obj"]
    assert first["vapid_claims"] == {"sub": SUBJECT}
    assert second["vapid_claims"] == {"sub": SUBJECT}
    assert first["claims_obj"]["aud"] == "https://fcm.googleapis.com"
    assert second["claims_obj"]["aud"] == "https://jmt17.google.com"


def _payload():
    message = AlertMessage(
        spot_id="s", kind=AlertEventKind.NEW, title="Go: S", body="b", go_url=None
    )
    return build_push_payload(message, tag="alert-1")


@pytest.mark.parametrize("status", [404, 410])
def test_status_permanent(status):
    exc = WebPushException("Push failed: x", response=FakeResponse(status))
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=RecordingWebpush(raises=exc))
    assert n.send_payload(make_target(), _payload()) == DeliveryResult(
        False, True, f"HTTP {status}"
    )


@pytest.mark.parametrize("status", [400, 403, 413, 429, 500, 503])
def test_status_not_permanent(status):
    exc = WebPushException("Push failed: x", response=FakeResponse(status))
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=RecordingWebpush(raises=exc))
    retryable = status in (429, 500, 503)
    assert n.send_payload(make_target(), _payload()) == DeliveryResult(
        False, False, f"HTTP {status}", retryable=retryable
    )


@pytest.mark.parametrize(
    ("exc", "detail", "retryable"),
    [
        (WebPushException("Push failed", response=None), "WebPushException", True),
        (requests.exceptions.ConnectTimeout("slow"), "ConnectTimeout", True),
        (RuntimeError("boom"), "RuntimeError", False),
    ],
)
def test_other_failures(exc, detail, retryable):
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=RecordingWebpush(raises=exc))
    assert n.send_payload(make_target(), _payload()) == DeliveryResult(
        False, False, detail, retryable=retryable
    )


def test_blocked_host_is_not_posted():
    rec = RecordingWebpush()
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=rec)
    target = PushTarget("a", "https://evil.example.test/x", "P", "A")
    assert n.send_payload(target, _payload()) == DeliveryResult(
        False, False, "blocked host", retryable=False
    )
    assert rec.calls == []


def test_payload_value_error_is_not_retryable():
    rec = RecordingWebpush()
    n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=rec)
    message = AlertMessage(
        spot_id="s" * 4000, kind=AlertEventKind.NEW, title="Go", body="b", go_url=None
    )
    assert n.send(make_target(), message, tag="alert-1") == DeliveryResult(
        False, False, "ValueError", retryable=False
    )
    assert rec.calls == []


def test_invalid_key():
    with pytest.raises(ValueError) as info:
        WebPushNotifier("not-a-key", SUBJECT)
    assert str(info.value) == PRIVATE_KEY_ERROR
    assert "not-a-key" not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__


INVALID_SUBJECTS = [
    "https://shakka.nl/contact",
    "https://example.org/contact",
    "mailto:lars@example",
    "lars@example.org",
    "mailto:",
    "",
    "   ",
    "http://example.org",
    "mailto:a b@example.org",
]
VALID_SUBJECTS = [
    "mailto:test@example.org",
    "https://example.org",
    "https://shakka.nl",
    "  mailto:test@example.org\n",
]


@pytest.mark.parametrize("subject", INVALID_SUBJECTS)
def test_subject_invalid(subject):
    with pytest.raises(ValueError) as info:
        WebPushNotifier(KEYS.private_key, subject)
    assert str(info.value) == SUBJECT_ERROR
    assert "example" not in str(info.value)


@pytest.mark.parametrize("subject", VALID_SUBJECTS)
def test_subject_valid(subject):
    rec = RecordingWebpush()
    n = WebPushNotifier(KEYS.private_key, subject, webpush_fn=rec)
    n.send_payload(make_target(), _payload())
    assert rec.calls[0]["vapid_claims"]["sub"] == subject.strip()


def test_subject_check_matches_library():
    vapid = py_vapid.Vapid.from_string(private_key=KEYS.private_key)
    claims = {"aud": "https://fcm.googleapis.com"}
    for subject in VALID_SUBJECTS:
        vapid.sign({**claims, "sub": subject.strip()})
    for subject in [
        "https://shakka.nl/contact",
        "mailto:lars@example",
        "lars@example.org",
        "mailto:",
        "http://example.org",
    ]:
        with pytest.raises(py_vapid.VapidException):
            vapid.sign({**claims, "sub": subject})


def test_key_error_before_subject_error():
    with pytest.raises(ValueError) as info:
        WebPushNotifier("not-a-key", "mailto:lars@example")
    assert str(info.value) == PRIVATE_KEY_ERROR


def test_public_key_matches_generated():
    n = WebPushNotifier(KEYS.private_key, SUBJECT)
    assert n.public_key == KEYS.public_key
    text = repr(n)
    assert KEYS.private_key not in text
    assert KEYS.public_key not in text
    assert SUBJECT not in text


def test_generate_vapid_keys():
    a, b = generate_vapid_keys(), generate_vapid_keys()
    for keys in (a, b):
        assert re.fullmatch(r"[A-Za-z0-9_-]+", keys.public_key)
        assert re.fullmatch(r"[A-Za-z0-9_-]+", keys.private_key)
        public = b64d(keys.public_key)
        assert len(public) == 65
        assert public[0] == 0x04
        assert len(b64d(keys.private_key)) == 32
        assert keys.private_key not in repr(keys)
    assert a.public_key != b.public_key
    assert a.private_key != b.private_key


def make_settings(**kwargs) -> Settings:
    return Settings(
        supabase_url="http://127.0.0.1:54321", supabase_secret_key="sb_secret_TESTVALUE", **kwargs
    )


def test_notifiers_from_settings_disabled():
    assert notifiers_from_settings(make_settings()) == {}
    assert notifiers_from_settings(make_settings(vapid_subject="mailto:")) == {}
    assert notifiers_from_settings(make_settings(vapid_subject="  ")) == {}
    assert notifiers_from_settings(make_settings(vapid_subject=" mailto: ")) == {}  # N-1


def test_notifiers_from_settings_incomplete():
    with pytest.raises(ValueError) as info:
        notifiers_from_settings(
            make_settings(vapid_private_key=KEYS.private_key, vapid_subject=SUBJECT)
        )
    assert str(info.value) == INCOMPLETE_ERROR
    for kwargs in ({"vapid_public_key": KEYS.public_key}, {"vapid_subject": SUBJECT}):
        with pytest.raises(ValueError, match="incomplete VAPID"):
            notifiers_from_settings(make_settings(**kwargs))


def full_settings(**overrides) -> Settings:
    values = {
        "vapid_public_key": KEYS.public_key,
        "vapid_private_key": KEYS.private_key,
        "vapid_subject": SUBJECT,
    }
    return make_settings(**{**values, **overrides})


def test_notifiers_from_settings_complete():
    result = notifiers_from_settings(full_settings())
    assert set(result) == {"webpush"}
    assert isinstance(result["webpush"], WebPushNotifier)
    padded = notifiers_from_settings(full_settings(vapid_public_key=f"  {KEYS.public_key}=  "))
    assert set(padded) == {"webpush"}


def test_notifiers_from_settings_errors_hold_no_values():
    other = generate_vapid_keys()
    with pytest.raises(ValueError) as info:
        notifiers_from_settings(full_settings(vapid_public_key=other.public_key))
    assert str(info.value) == PUBLIC_KEY_ERROR
    bad = full_settings(vapid_private_key="not-a-valid-key-value")
    with pytest.raises(ValueError) as info2:
        notifiers_from_settings(bad)
    assert str(info2.value) == PRIVATE_KEY_ERROR
    bad_subject = full_settings(vapid_subject="https://shakka.nl/contact")
    with pytest.raises(ValueError) as info3:
        notifiers_from_settings(bad_subject)
    for err, secret in (
        (info, other.public_key),
        (info2, "not-a-valid-key-value"),
        (info3, "shakka.nl/contact"),
    ):
        assert secret not in str(err.value)
    assert KEYS.private_key not in str(info.value)


def test_failure_detail_has_no_secrets(caplog, capsys):
    caplog.set_level(logging.DEBUG)
    ep = "https://fcm.googleapis.com/fcm/send/ENDPOINT-SECRET-123"
    target = PushTarget("sub-1", ep, "P256DH-SECRET-456", "AUTH-SECRET-789")
    secrets = [ep, "P256DH-SECRET-456", "AUTH-SECRET-789", KEYS.private_key]
    errors = [
        WebPushException(f"Push failed: 503 {ep}", response=FakeResponse(503)),
        Exception(f"{ep} P256DH-SECRET-456 AUTH-SECRET-789 {KEYS.private_key}"),
    ]
    for error in errors:
        n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=RecordingWebpush(raises=error))
        result = n.send_payload(target, _payload())
        for text in (result.detail, repr(result), repr(target)):
            for secret in secrets:
                assert secret not in text
    out = capsys.readouterr()
    for text in (caplog.text, out.out, out.err):
        for secret in secrets:
            assert secret not in text
