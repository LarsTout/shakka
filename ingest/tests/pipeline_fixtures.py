"""Scenario and helpers for the pipeline tests (WP-11)."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import httpx
import yaml

from evaluation_fixtures import LAT, LON
from fakes import FakeSupabase
from job_fixtures import MODELS3, USER_A, WINDS, at, seed_favorite, seed_profile
from shakka.config import Settings
from shakka.domain.forecast import ForecastHour, SpotLocation

PIPELINE_SPOT: dict[str, Any] = {
    "id": "test-strand",
    "name": "Teststrand",
    "lat": LAT,
    "lon": LON,
    "shore_normal_deg": 270,
    "status": "allowed",
    "level": "intermediate",
    "verified": True,
}


def write_spots_yaml(tmp_path: Path, spots: Sequence[dict[str, Any]] = (PIPELINE_SPOT,)) -> Path:
    path = tmp_path / "spots.yaml"
    path.write_text(yaml.safe_dump({"spots": list(spots)}), encoding="utf-8")
    return path


def make_settings(spots_path: Path, **overrides: Any) -> Settings:
    return Settings(
        supabase_url="http://127.0.0.1:54321",
        supabase_secret_key="sb_secret_TESTVALUE",
        spots_path=spots_path,
        **overrides,
    )


def fake_forecast_fetch(
    http: httpx.Client, locations: Sequence[SpotLocation], *, forecast_days: int = 7
) -> list[ForecastHour]:
    return [
        ForecastHour(
            spot_id=loc.spot_id,
            model=model,
            valid_at=at(h),
            wind_kn=w,
            gust_kn=w + 4,
            dir_deg=270,
        )
        for loc in locations
        for model in MODELS3
        for h, w in WINDS.items()
    ]


def failing_forecast_fetch(exc: Exception) -> Callable[..., list[ForecastHour]]:
    def fetch(http: httpx.Client, locations: Sequence[SpotLocation], **kw: Any) -> list:
        raise exc

    return fetch


def no_tides(station: str, start: Any, end: Any) -> list:
    return []


def seed_user(db: FakeSupabase) -> None:
    seed_profile(db, USER_A, level="intermediate")
    seed_favorite(db, USER_A, "test-strand", min_kn=12)


def blocked_http() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
