import pytest
import pywebpush

import shakka.config
import shakka.http


def _blocked_webpush(*args, **kwargs):
    # Failed is a BaseException: no `except Exception` swallows it, so the test really fails.
    pytest.fail("real web push in a test", pytrace=False)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Never read the developer's real environment or .env in tests."""
    for field in shakka.config.Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.setattr(shakka.config, "ENV_FILE", tmp_path / "absent.env")


@pytest.fixture(autouse=True)
def _no_real_webpush(monkeypatch: pytest.MonkeyPatch):
    """Make a real network push impossible in any test."""
    monkeypatch.setattr(pywebpush, "webpush", _blocked_webpush)


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch):
    """Retries never really wait in tests."""
    monkeypatch.setattr(shakka.http, "_sleep", lambda s: None)
