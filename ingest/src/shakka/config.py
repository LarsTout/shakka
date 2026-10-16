"""Settings loaded from the OS environment and, if present, REPO_ROOT/.env."""

from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
ENV_FILE: Path = REPO_ROOT / ".env"  # read at call time so tests can redirect it
DEFAULT_SPOTS_PATH: Final[Path] = REPO_ROOT / "data" / "spots.yaml"
REQUIRED_ENV_VARS: Final[tuple[str, ...]] = ("SUPABASE_URL", "SUPABASE_SECRET_KEY")

_LOCAL_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})
URL_ERROR: Final = (
    "expected https://<project-ref>.supabase.co (http only for localhost), without path"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    supabase_url: str
    supabase_publishable_key: str | None = None
    supabase_secret_key: SecretStr
    app_base_url: str | None = None
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str | None = None
    operator_user_id: str | None = None  # Supabase user id of the operator; not validated here
    spots_path: Path = DEFAULT_SPOTS_PATH

    @field_validator("supabase_url")
    @classmethod
    def _validate_supabase_url(cls, value: str) -> str:
        try:
            parts = urlsplit(value)
            host = parts.hostname or ""
        except ValueError:
            raise ValueError(URL_ERROR) from None
        ok = (
            bool(host)
            and (parts.scheme == "https" or (parts.scheme == "http" and host in _LOCAL_HOSTS))
            and parts.path in ("", "/")
            and not parts.query
            and not parts.fragment
            and "?" not in value
            and "#" not in value
        )
        if not ok:
            raise ValueError(URL_ERROR)
        return f"{parts.scheme}://{parts.netloc}"


def get_settings() -> Settings:
    """Load settings from the environment and, if it exists, REPO_ROOT/.env."""
    env_file = ENV_FILE if ENV_FILE.is_file() else None
    return Settings(_env_file=env_file)
