import pytest

import shakka.config


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Never read the developer's real environment or .env in tests."""
    for field in shakka.config.Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.setattr(shakka.config, "ENV_FILE", tmp_path / "absent.env")
