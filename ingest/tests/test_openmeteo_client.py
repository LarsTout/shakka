"""Tests for the Open-Meteo request helper (retries)."""

import logging

import httpx
import pytest

from shakka.openmeteo.client import OpenMeteoRequestError, request_json

URL = "https://api.open-meteo.com/v1/forecast"


def client(responses: list) -> tuple[httpx.Client, list[httpx.Request]]:
    """Each item is an httpx.Response or an Exception, served in order."""
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_request_returns_json_and_passes_params() -> None:
    http, seen = client([httpx.Response(200, json={"a": 1})])
    assert request_json(http, URL, {"x": "1,2"}, sleep=lambda s: None) == {"a": 1}
    assert seen[0].url.params["x"] == "1,2"


def test_request_429_then_200() -> None:
    http, seen = client([httpx.Response(429), httpx.Response(200, json=[1])])
    sleeps: list[float] = []
    assert request_json(http, URL, {}, sleep=sleeps.append) == [1]
    assert sleeps == [1.0] and len(seen) == 2


def test_request_three_500_raises(caplog: pytest.LogCaptureFixture) -> None:
    http, seen = client([httpx.Response(500)] * 3)
    sleeps: list[float] = []
    with (
        caplog.at_level(logging.WARNING, logger="shakka.openmeteo"),
        pytest.raises(OpenMeteoRequestError) as info,
    ):
        request_json(http, URL, {}, sleep=sleeps.append)
    assert str(info.value) == "failed after 3 attempts: HTTP 500"
    assert len(seen) == 3 and sleeps == [1.0, 2.0]
    assert len(caplog.records) == 2


def test_request_transport_error_then_ok() -> None:
    http, _ = client([httpx.ConnectError("boom"), httpx.Response(200, json={})])
    assert request_json(http, URL, {}, sleep=lambda s: None) == {}


def test_request_transport_error_message() -> None:
    http, _ = client([httpx.ConnectError("boom")] * 3)
    with pytest.raises(OpenMeteoRequestError, match="failed after 3 attempts: ConnectError"):
        request_json(http, URL, {}, sleep=lambda s: None)


def test_request_400_no_retry() -> None:
    body = {"error": True, "reason": "Cannot initialize model"}
    http, seen = client([httpx.Response(400, json=body)])
    sleeps: list[float] = []
    with pytest.raises(OpenMeteoRequestError, match="HTTP 400: Cannot initialize model") as info:
        request_json(http, URL, {}, sleep=sleeps.append)
    assert info.value.status == 400 and len(seen) == 1 and sleeps == []


def test_request_400_without_reason_and_long_reason() -> None:
    http, _ = client([httpx.Response(400, text="nope")])
    with pytest.raises(OpenMeteoRequestError) as info:
        request_json(http, URL, {}, sleep=lambda s: None)
    assert str(info.value) == "HTTP 400"
    http, _ = client([httpx.Response(400, json={"reason": "x" * 500})])
    with pytest.raises(OpenMeteoRequestError) as info:
        request_json(http, URL, {}, sleep=lambda s: None)
    assert str(info.value) == "HTTP 400: " + "x" * 200


def test_request_redirect_fails_at_once() -> None:
    http, seen = client([httpx.Response(302, headers={"Location": "https://evil.example/"})])
    with pytest.raises(OpenMeteoRequestError, match="HTTP 302"):
        request_json(http, URL, {}, sleep=lambda s: None)
    assert len(seen) == 1


@pytest.mark.parametrize(("header", "expected"), [("5", 5.0), ("100", 30.0), ("0", 1.0)])
def test_request_429_honours_retry_after(header: str, expected: float) -> None:
    http, _ = client(
        [httpx.Response(429, headers={"Retry-After": header}), httpx.Response(200, json=1)]
    )
    sleeps: list[float] = []
    request_json(http, URL, {}, sleep=sleeps.append)
    assert sleeps == [expected]


def test_request_429_ignores_unparsable_retry_after() -> None:
    http, _ = client(
        [httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct"}), httpx.Response(200, json=1)]
    )
    sleeps: list[float] = []
    request_json(http, URL, {}, sleep=sleeps.append)
    assert sleeps == [1.0]


def test_request_invalid_json() -> None:
    http, seen = client([httpx.Response(200, text="<html>")])
    with pytest.raises(OpenMeteoRequestError, match="invalid JSON response"):
        request_json(http, URL, {}, sleep=lambda s: None)
    assert len(seen) == 1


def test_error_message_has_no_url() -> None:
    for responses in ([httpx.Response(500)] * 3, [httpx.Response(400, json={"reason": "bad"})]):
        http, _ = client(list(responses))
        with pytest.raises(OpenMeteoRequestError) as info:
            request_json(http, URL, {"latitude": "52.47"}, sleep=lambda s: None)
        assert "open-meteo" not in str(info.value) and "52.47" not in str(info.value)
