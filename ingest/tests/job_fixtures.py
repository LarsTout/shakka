"""Seed helpers and the fixed scenario for the job tests (WP-10)."""

from datetime import UTC, datetime
from typing import Any

from evaluation_fixtures import make_spot
from fakes import FakeSupabase
from shakka.domain.alerts import RULE_FIELDS
from shakka.domain.forecast import ModelKey
from shakka.domain.spot import SpotProfile

NOW = datetime(2026, 7, 15, 6, 17, tzinfo=UTC)  # 08:17 local (CEST)
FETCHED = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
USER_C = "33333333-3333-4333-8333-333333333333"
SPOT = "test-strand"
MODELS3 = (ModelKey.KNMI, ModelKey.ICON, ModelKey.ECMWF)
# Scenario winds (kn) per UTC hour on 2026-07-15; gust = wind + 4, dir 270.
WINDS = {8: 6.0, 9: 6.0, 10: 14.0, 11: 18.0, 12: 24.0, 13: 25.0, 14: 24.0, 15: 18.0, 16: 6.0}


def at(h: int) -> datetime:
    return datetime(2026, 7, 15, h, tzinfo=UTC)


def seed_spot(db: FakeSupabase, **overrides: Any) -> SpotProfile:
    spot = make_spot(**overrides)
    db.seed("spots", [spot.to_row()])
    return spot


def seed_forecasts(
    db: FakeSupabase,
    spot_id: str = SPOT,
    winds: dict[int, float] = WINDS,
    *,
    dir_deg: int = 270,
    models: tuple[ModelKey, ...] = MODELS3,
    fetched_at: datetime = FETCHED,
    gust_delta: float = 4.0,
) -> None:
    rows = [
        {
            "spot_id": spot_id,
            "model": m.value,
            "valid_at": at(h),
            "wind_kn": wind,
            "gust_kn": wind + gust_delta,
            "dir_deg": dir_deg,
            "fetched_at": fetched_at,
        }
        for h, wind in winds.items()
        for m in models
    ]
    db.upsert("forecast_hours", rows, on_conflict="spot_id,model,valid_at")


def seed_profile(db: FakeSupabase, user_id: str, **cols: Any) -> None:
    db.seed("profiles", [{"user_id": user_id, **cols}])


def seed_favorite(db: FakeSupabase, user_id: str, spot_id: str = SPOT, **rule: Any) -> None:
    db.seed("favorites", [{"user_id": user_id, "spot_id": spot_id}])
    if rule:
        row: dict[str, Any] = {"user_id": user_id, "spot_id": spot_id}
        row.update({name: None for name in RULE_FIELDS})
        row.update(rule)
        db.seed("alert_rules", [row])


def alert_rows(db: FakeSupabase) -> list[dict[str, Any]]:
    return db.rows("alert_state")
