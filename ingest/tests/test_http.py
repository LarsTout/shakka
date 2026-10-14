import pytest

from shakka.http import USER_AGENT, make_client


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
