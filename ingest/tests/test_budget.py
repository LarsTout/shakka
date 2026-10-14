"""Tests for the Open-Meteo call weight and the budget guard (WP-03, AC-3 and AC-4)."""

from datetime import UTC, date, datetime

import pytest

from fakes import FakeSupabase
from shakka.budget import (
    DEFAULT_DAILY_LIMIT,
    DEFAULT_MONTHLY_LIMIT,
    GUARD_FRACTION,
    OPEN_METEO_DAILY_LIMIT,
    OPEN_METEO_MONTHLY_LIMIT,
    SOURCE_OPEN_METEO_FORECAST,
    SOURCE_OPEN_METEO_MARINE,
    SOURCE_RWS,
    BudgetGuard,
    estimate_call_weight,
)

NOW = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
TODAY = "2026-10-14"


def usage_row(day: str, source: str, calls: float, requests: int = 1) -> dict:
    return {"day": day, "source": source, "calls": calls, "requests": requests}


def guard_with(rows: list[dict]) -> tuple[BudgetGuard, FakeSupabase]:
    db = FakeSupabase()
    db.seed("api_usage", rows)
    return BudgetGuard(db), db  # type: ignore[arg-type]


# -- AC-3 --------------------------------------------------------------------------------------


def test_weight_single() -> None:
    assert estimate_call_weight(1, 3, 1, 7) == 1.0


def test_weight_multi_model() -> None:
    weight = estimate_call_weight(1, 3, 4, 7)
    assert weight == pytest.approx(1.2)
    assert weight >= 1.2


def test_weight_scales_with_locations() -> None:
    assert estimate_call_weight(25, 3, 4, 7) == pytest.approx(25 * estimate_call_weight(1, 3, 4, 7))


def test_weight_long_range() -> None:
    weight = estimate_call_weight(1, 3, 1, 21)
    assert weight >= 1.5
    assert weight == pytest.approx(1.5)


@pytest.mark.parametrize("v", [1, 3, 12, 30])
@pytest.mark.parametrize("d", [1, 7, 14, 15, 16])
def test_weight_matches_open_meteo_up_to_14_days(v: int, d: int) -> None:
    open_meteo = max(1, max(v / 10, d / 14 * v / 10))
    weight = estimate_call_weight(1, v, 1, d)
    if d <= 14:
        assert weight == pytest.approx(open_meteo)
    else:
        assert weight >= open_meteo - 1e-4  # weight is rounded to 4 decimals


@pytest.mark.parametrize("d", [7, 16])
def test_weight_models_times_variables(d: int) -> None:
    assert estimate_call_weight(1, 3, 4, d) == estimate_call_weight(1, 12, 1, d)


@pytest.mark.parametrize("args", [(0, 3, 4, 7), (1, 0, 4, 7), (1, 3, 0, 7), (1, 3, 4, 0)])
def test_weight_rejects_zero(args: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValueError):
        estimate_call_weight(*args)


def test_limits_are_80_percent() -> None:
    assert DEFAULT_DAILY_LIMIT == GUARD_FRACTION * OPEN_METEO_DAILY_LIMIT == 8000.0
    assert DEFAULT_MONTHLY_LIMIT == GUARD_FRACTION * OPEN_METEO_MONTHLY_LIMIT == 240000.0
    guard, _ = guard_with([])
    assert guard.daily_limit == 8000.0 and guard.monthly_limit == 240000.0


def test_guard_rejects_bad_limits() -> None:
    with pytest.raises(ValueError):
        BudgetGuard(FakeSupabase(), daily_limit=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        BudgetGuard(FakeSupabase(), monthly_limit=-1)  # type: ignore[arg-type]


# -- AC-4: guard -------------------------------------------------------------------------------


def test_can_spend_empty() -> None:
    guard, _ = guard_with([])
    assert guard.can_spend(30, now=NOW) is True


def test_can_spend_daily_exceeded() -> None:
    guard, _ = guard_with([usage_row(TODAY, SOURCE_OPEN_METEO_FORECAST, 7999.5)])
    assert guard.can_spend(0.5, now=NOW) is True
    assert guard.can_spend(1.2, now=NOW) is False


def test_can_spend_monthly_exceeded() -> None:
    # Daily usage stays far below the daily limit; only the month total is the problem.
    guard, _ = guard_with(
        [usage_row(f"2026-10-{d:02d}", SOURCE_OPEN_METEO_FORECAST, 7999.9) for d in range(1, 14)]
        + [usage_row(f"2026-10-{d:02d}", SOURCE_OPEN_METEO_MARINE, 7999.9) for d in range(1, 14)]
    )
    assert guard.usage(now=NOW).monthly == pytest.approx(26 * 7999.9)
    big, _ = guard_with(
        [usage_row(f"2026-10-{d:02d}", SOURCE_OPEN_METEO_FORECAST, 8000) for d in range(1, 14)]
        + [usage_row(f"2026-09-{d:02d}", SOURCE_OPEN_METEO_FORECAST, 8000) for d in range(1, 30)]
        + [usage_row(f"2026-10-{d:02d}", SOURCE_OPEN_METEO_MARINE, 8000) for d in range(1, 14)]
    )
    assert big.can_spend(1, now=NOW) is True  # previous month does not count
    month, _ = guard_with(
        [usage_row("2026-10-01", SOURCE_OPEN_METEO_FORECAST, 120000)]
        + [usage_row("2026-10-02", SOURCE_OPEN_METEO_MARINE, 119999.5)]
    )
    assert month.can_spend(0.5, now=NOW) is True
    assert month.can_spend(1, now=NOW) is False


def test_can_spend_boundary_inclusive() -> None:
    guard, _ = guard_with([usage_row(TODAY, SOURCE_OPEN_METEO_FORECAST, 7970)])
    assert guard.can_spend(30, now=NOW) is True
    assert guard.can_spend(30.01, now=NOW) is False


def test_can_spend_rejects_bad_weight() -> None:
    guard, _ = guard_with([])
    for bad in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            guard.can_spend(bad, now=NOW)


def test_usage_sums_open_meteo_sources_only() -> None:
    guard, _ = guard_with(
        [
            usage_row(TODAY, SOURCE_OPEN_METEO_FORECAST, 10),
            usage_row(TODAY, SOURCE_OPEN_METEO_MARINE, 5),
            usage_row(TODAY, SOURCE_RWS, 100),
            usage_row("2026-10-02", SOURCE_OPEN_METEO_FORECAST, 20),
        ]
    )
    usage = guard.usage(now=NOW)
    assert usage.daily == 15 and usage.monthly == 35


def test_usage_ignores_previous_month() -> None:
    guard, _ = guard_with(
        [
            usage_row("2026-09-30", SOURCE_OPEN_METEO_FORECAST, 500),
            usage_row("2026-10-01", SOURCE_OPEN_METEO_FORECAST, 7),
        ]
    )
    usage = guard.usage(now=NOW)
    assert usage.monthly == 7 and usage.daily == 0


def test_usage_month_boundary() -> None:
    guard, _ = guard_with(
        [
            usage_row("2026-10-31", SOURCE_OPEN_METEO_FORECAST, 40),
            usage_row("2026-11-01", SOURCE_OPEN_METEO_FORECAST, 3),
        ]
    )
    before = guard.usage(now=datetime(2026, 10, 31, 23, 30, tzinfo=UTC))
    after = guard.usage(now=datetime(2026, 11, 1, 0, 30, tzinfo=UTC))
    assert (before.daily, before.monthly) == (40, 40)
    assert (after.daily, after.monthly) == (3, 3)


def test_usage_december_rolls_to_next_year() -> None:
    guard, _ = guard_with(
        [
            usage_row("2026-12-31", SOURCE_OPEN_METEO_FORECAST, 4),
            usage_row("2027-01-01", SOURCE_OPEN_METEO_FORECAST, 9),
        ]
    )
    assert guard.usage(now=datetime(2026, 12, 31, 22, tzinfo=UTC)).monthly == 4


def test_usage_uses_utc_day() -> None:
    from datetime import timedelta, timezone

    guard, _ = guard_with([usage_row("2026-10-14", SOURCE_OPEN_METEO_FORECAST, 8)])
    local = datetime(2026, 10, 15, 1, 30, tzinfo=timezone(timedelta(hours=3)))
    assert guard.usage(now=local).daily == 8


def test_record_creates_and_increments() -> None:
    guard, db = guard_with([])
    guard.record(SOURCE_OPEN_METEO_FORECAST, 1.2, now=NOW)
    guard.record(SOURCE_OPEN_METEO_FORECAST, 1.2, now=NOW)
    rows = db.rows("api_usage")
    assert len(rows) == 1
    assert rows[0]["day"] == date(2026, 10, 14).isoformat()
    assert rows[0]["calls"] == pytest.approx(2.4) and rows[0]["requests"] == 2
    assert db.upserts == [("api_usage", "day,source")] * 2


def test_record_requests_parameter() -> None:
    guard, db = guard_with([])
    guard.record(SOURCE_RWS, 0, now=NOW, requests=0)
    assert db.rows("api_usage")[0]["requests"] == 0


def test_record_rejects_unknown_source() -> None:
    guard, db = guard_with([])
    with pytest.raises(ValueError):
        guard.record("open_meteo_other", 1, now=NOW)
    with pytest.raises(ValueError):
        guard.record(SOURCE_OPEN_METEO_FORECAST, -1, now=NOW)
    with pytest.raises(ValueError):
        guard.record(SOURCE_OPEN_METEO_FORECAST, 1, now=NOW, requests=-1)
    assert db.writes == []


def test_budget_rejects_naive_now() -> None:
    guard, _ = guard_with([])
    naive = datetime(2026, 10, 14, 12)  # noqa: DTZ001
    with pytest.raises(ValueError):
        guard.usage(now=naive)
    with pytest.raises(ValueError):
        guard.can_spend(1, now=naive)
    with pytest.raises(ValueError):
        guard.record(SOURCE_OPEN_METEO_FORECAST, 1, now=naive)
