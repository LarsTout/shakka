"""The autouse fixture must make a real push impossible, even through `except Exception`."""

import pytest

from push_fixtures import KEYS, SUBJECT, make_target
from shakka.domain.dedup import AlertEventKind
from shakka.domain.messages import AlertMessage
from shakka.domain.push import build_push_payload
from shakka.jobs.push import deliver_event
from shakka.notify.webpush import WebPushNotifier

MESSAGE = AlertMessage(spot_id="s", kind=AlertEventKind.NEW, title="Go", body="b", go_url=None)


def test_real_webpush_is_blocked():
    n = WebPushNotifier(KEYS.private_key, SUBJECT)
    with pytest.raises(pytest.fail.Exception):
        n.send_payload(make_target(), build_push_payload(MESSAGE, tag="alert-x"))
    with pytest.raises(pytest.fail.Exception):
        deliver_event(n, [make_target()], MESSAGE, tag="alert-x")
