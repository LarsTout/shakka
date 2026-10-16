"""Host allowlist for push endpoints (WP-22 A9)."""

import pytest

from shakka.notify.base import endpoint_allowed


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://jmt17.google.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://web.push.apple.com/abc",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
        "https://FCM.googleapis.com/fcm/send/abc",
    ],
)
def test_allowed(endpoint):
    assert endpoint_allowed(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com@evil.test/x",  # userinfo
        "https://user:pw@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:443/x",  # port
        "https://fcm.googleapis.com:99999/x",  # invalid port
        "http://fcm.googleapis.com/x",
        "https://push.apple.com/x",  # no subdomain
        "https://evilnotify.windows.com/x",
        "https://evil.push.apple.com.evil.test/x",
        "https://[::1]/x",
        "https://x.jmt17.google.com/x",
        "https://android.googleapis.com/gcm/send/abc",
        "https://example.test/x",
        "",
        "not a url",
    ],
)
def test_blocked(endpoint):
    assert not endpoint_allowed(endpoint)
