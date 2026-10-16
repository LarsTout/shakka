from pathlib import Path

import httpx
import pytest

import shakka.http
from shakka.http import (
    RETRY_MAX_DELAY_S,
    USER_AGENT,
    TransientError,
    make_client,
    with_retries,
)


def _timeouts(client):
    t = client.timeout
    return (t.connect, t.read, t.write, t.pool)


def test_default_timeout():
    with make_client() as client:
        assert _timeouts(client) == (30.0,) * 4


def test_custom_timeout():
    with make_client(timeout=5.0) as client:
        assert _timeouts(client) == (5.0,) * 4


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_invalid_timeout(value):
    with pytest.raises(ValueError):
        make_client(timeout=value)


def test_user_agent():
    with make_client() as client:
        ua = client.headers["User-Agent"]
    assert ua == USER_AGENT
    assert ua.startswith("shakka-ingest/")
    assert "Mozilla" not in ua
    assert "@" not in ua


def test_no_redirect_follow():
    with make_client() as client:
        assert client.follow_redirects is False


def test_only_http_module_creates_clients():
    src = Path(shakka.http.__file__).parent
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p.name != "http.py" and "httpx.Client(" in p.read_text()
    ]
    assert offenders == []


@pytest.mark.parametrize("kwargs", [{}, {"timeout": 5}])
def test_make_client_timeouts_are_finite(kwargs):
    import math

    with make_client(**kwargs) as client:
        for value in _timeouts(client):
            assert value is not None and math.isfinite(value) and value > 0


class _Flaky:
    def __init__(self, failures, result="ok", exc=None):
        self.calls = 0
        self.failures = failures
        self.result = result
        self.exc = exc or TransientError("boom")

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc
        return self.result


def test_with_retries_success_without_retry():
    waits: list[float] = []
    fn = _Flaky(0)
    assert with_retries(fn, sleep=waits.append) == "ok"
    assert fn.calls == 1 and waits == []


def test_with_retries_backoff_then_success():
    waits: list[float] = []
    fn = _Flaky(2)
    assert with_retries(fn, sleep=waits.append) == "ok"
    assert waits == [1.0, 2.0]
    waits2: list[float] = []
    assert with_retries(_Flaky(2), backoff=0.5, sleep=waits2.append) == "ok"
    assert waits2 == [0.5, 1.0]


def test_with_retries_exhausted_raises_same_exception():
    exc = TransientError("boom")
    fn = _Flaky(5, exc=exc)
    with pytest.raises(TransientError) as info:
        with_retries(fn, sleep=lambda s: None)
    assert info.value is exc
    assert fn.calls == 3
    assert info.value.__context__ is None


def test_with_retries_non_retryable_goes_through_at_once():
    waits: list[float] = []
    seen: list[object] = []
    fn = _Flaky(5, exc=KeyError("x"))
    with pytest.raises(KeyError):
        with_retries(fn, sleep=waits.append, on_retry=lambda *a: seen.append(a))
    assert fn.calls == 1 and waits == [] and seen == []


def test_with_retries_transport_error_is_transient():
    fn = _Flaky(1, exc=httpx.ConnectError("x"))
    assert with_retries(fn, sleep=lambda s: None) == "ok"


def test_with_retries_retry_after_applied_and_capped():
    waits: list[float] = []
    with_retries(_Flaky(1, exc=TransientError("x", retry_after=7)), sleep=waits.append)
    assert waits == [7]
    waits = []
    with_retries(_Flaky(1, exc=TransientError("x", retry_after=100)), sleep=waits.append)
    assert waits == [RETRY_MAX_DELAY_S]
    waits = []
    with_retries(_Flaky(1, exc=TransientError("x", retry_after=-5)), sleep=waits.append)
    assert waits == [0]


@pytest.mark.parametrize("kwargs", [{"attempts": 0}, {"backoff": -1}, {"backoff": float("nan")}])
def test_with_retries_invalid_arguments(kwargs):
    with pytest.raises(ValueError):
        with_retries(lambda: 1, **kwargs)


def test_with_retries_single_attempt():
    waits: list[float] = []
    fn = _Flaky(5)
    with pytest.raises(TransientError):
        with_retries(fn, attempts=1, sleep=waits.append)
    assert fn.calls == 1 and waits == []


def test_with_retries_on_retry_arguments():
    exc = TransientError("x")
    calls: list[tuple] = []
    with_retries(_Flaky(1, exc=exc), sleep=lambda s: None, on_retry=lambda *a: calls.append(a))
    assert calls == [(1, exc, 1.0)]


def test_with_retries_keyboard_interrupt_not_caught():
    fn = _Flaky(1, exc=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        with_retries(fn, sleep=lambda s: None)
    assert fn.calls == 1


def test_with_retries_uses_module_sleep(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(shakka.http, "_sleep", waits.append)
    with_retries(_Flaky(1))
    assert waits == [1.0]
