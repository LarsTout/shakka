import pytest
from pydantic import ValidationError

import shakka.config
from shakka.config import DEFAULT_SPOTS_PATH, REPO_ROOT, Settings, get_settings


def _required(monkeypatch, url="https://testref.supabase.co"):
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_TESTVALUE")


def test_repo_root_points_to_repo():
    assert (REPO_ROOT / "ingest" / "pyproject.toml").is_file()


def test_defaults(monkeypatch):
    _required(monkeypatch)
    s = get_settings()
    assert s.supabase_publishable_key is None
    assert s.app_base_url is None
    assert s.vapid_public_key is None
    assert s.vapid_private_key is None
    assert s.vapid_subject is None
    assert s.spots_path == REPO_ROOT / "data" / "spots.yaml"
    assert s.spots_path == DEFAULT_SPOTS_PATH


def test_env_overrides_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SUPABASE_URL=https://aaaa.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_TESTVALUE\n"
    )
    monkeypatch.setattr(shakka.config, "ENV_FILE", env_file)
    monkeypatch.setenv("SUPABASE_URL", "https://bbbb.supabase.co")
    assert get_settings().supabase_url == "https://bbbb.supabase.co"


def test_unknown_keys_in_env_file_ignored(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SUPABASE_URL=https://aaaa.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_TESTVALUE\n"
        "SUPABASE_ANON_KEY=x\nPUBLIC_FOO=y\n"
    )
    monkeypatch.setattr(shakka.config, "ENV_FILE", env_file)
    assert get_settings().supabase_url == "https://aaaa.supabase.co"


def test_missing_env_file_is_fine(monkeypatch, tmp_path):
    monkeypatch.setattr(shakka.config, "ENV_FILE", tmp_path / "nope.env")
    _required(monkeypatch)
    assert get_settings().supabase_secret_key.get_secret_value() == "sb_secret_TESTVALUE"


def test_empty_string_counts_as_missing(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://testref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    with pytest.raises(ValidationError):
        get_settings()


def test_secrets_not_in_repr(monkeypatch):
    _required(monkeypatch)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "TESTVAPIDPRIV")
    s = get_settings()
    for text in (repr(s), str(s)):
        assert "sb_secret_TESTVALUE" not in text
        assert "TESTVAPIDPRIV" not in text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://testref.supabase.co", "https://testref.supabase.co"),
        ("https://testref.supabase.co/", "https://testref.supabase.co"),
        ("http://127.0.0.1:54321", "http://127.0.0.1:54321"),
        ("http://localhost:54321/", "http://localhost:54321"),
        ("http://[::1]:54321", "http://[::1]:54321"),
        ("ftp://x.supabase.co", None),
        ("http://testref.supabase.co", None),
        ("https://testref.supabase.co/rest/v1", None),
        ("https://testref.supabase.co?x=1", None),
        ("https://testref.supabase.co/#frag", None),
        ("https://", None),
        ("testref.supabase.co", None),
    ],
)
def test_supabase_url_validation(raw, expected):
    kwargs = {"supabase_url": raw, "supabase_secret_key": "sb_secret_TESTVALUE"}
    if expected is None:
        with pytest.raises(ValidationError):
            Settings(**kwargs)
    else:
        assert Settings(**kwargs).supabase_url == expected


def test_no_telegram_fields():
    assert [n for n in Settings.model_fields if n.lower().startswith("telegram")] == []


def test_old_telegram_env_is_ignored(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SUPABASE_URL=https://aaaa.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_TESTVALUE\n"
        "TELEGRAM_BOT_TOKEN=123:TESTTOKEN\nTELEGRAM_CHAT_ID=1\n"
    )
    monkeypatch.setattr(shakka.config, "ENV_FILE", env_file)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:TESTTOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    s = get_settings()
    assert s.supabase_url == "https://aaaa.supabase.co"
    assert not hasattr(s, "telegram_bot_token")
