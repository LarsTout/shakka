"""Pure usage report (WP-22 AC-2): warnings, report text, push texts, local time helpers."""

import dataclasses
from datetime import UTC, datetime

import pytest

from shakka.budget import OPEN_METEO_DAILY_LIMIT as BUDGET_DAILY
from shakka.budget import OPEN_METEO_MONTHLY_LIMIT as BUDGET_MONTHLY
from shakka.domain.usage import (
    BYTES_PER_MB,
    OPEN_METEO_DAILY_LIMIT,
    OPEN_METEO_MONTHLY_LIMIT,
    REPORT_TITLE,
    REPORT_TITLE_WARN,
    WARNING_TITLE,
    UsageStats,
    build_usage_report,
    in_operator_window,
    local_day_start,
    report_due_time,
    usage_push_text,
    usage_warnings,
    warning_push_text,
    week_start,
)

MONDAY = datetime(2026, 7, 20, 6, 17, tzinfo=UTC)  # Monday 08:17 CEST

STATS_OK = UsageStats(
    now=MONDAY,
    open_meteo_today=1400.0,
    open_meteo_max_day=1420.5,
    open_meteo_month=26000.0,
    database_bytes=42 * BYTES_PER_MB,
    table_rows={
        "spots": 25,
        "forecast_hours": 14500,
        "marine_hours": 4000,
        "tide_extremes": 300,
        "evaluations": 4800,
        "profiles": 2,
        "favorites": 3,
        "alert_rules": 3,
        "alert_state": 2,
        "push_subscriptions": 2,
        "sessions": 0,
        "rsvps": 0,
        "api_usage": 40,
        "ingest_runs": 1000,
    },  # fmt: skip
    runs_ok=160,
    runs_partial=7,
    runs_failed=1,
    step_issues={"tides": 3, "marine": 5},
    push_sent=12,
    push_failed=1,
)
STATS_WARN = dataclasses.replace(
    STATS_OK,
    database_bytes=310 * BYTES_PER_MB,
    open_meteo_today=7100.0,
    open_meteo_max_day=7100.0,
)

GOLDEN = "\n".join(
    [
        "Shakka gebruiksrapport tot 2026-07-20 08:17 (Europe/Amsterdam)",
        "Waarschuwingen: geen",
        "Open-Meteo: vandaag 1.400 calls, hoogste dag (7 dagen) 1.421, limiet 10.000 per dag; deze maand 26.000, limiet 300.000",  # noqa: E501
        "Database: 42 MB van 500 MB",
        "Rijen: alert_rules 3, alert_state 2, api_usage 40, evaluations 4.800, favorites 3, forecast_hours 14.500, ingest_runs 1.000, marine_hours 4.000, profiles 2, push_subscriptions 2, rsvps 0, sessions 0, spots 25, tide_extremes 300",  # noqa: E501
        "Runs (7 dagen): 168, waarvan 160 ok, 7 partial, 1 failed (95% ok)",
        "Stappen niet ok (7 dagen): marine 5, tides 3",
        "Push (7 dagen): 12 verstuurd, 1 mislukt",
        "Gebruikers: 2, push-abonnementen: 2",
    ]
)


def test_build_usage_report_golden():
    assert build_usage_report(STATS_OK) == GOLDEN


def test_build_usage_report_with_warnings_golden():
    lines = build_usage_report(STATS_WARN).split("\n")
    assert lines[1:4] == [
        "Waarschuwingen:",
        "- Database 310 MB, boven 300 MB",
        "- Open-Meteo vandaag 7.100 calls, boven 7.000",
    ]
    assert lines[4] == (
        "Open-Meteo: vandaag 7.100 calls, hoogste dag (7 dagen) 7.100, limiet 10.000 per dag; "
        "deze maand 26.000, limiet 300.000"
    )
    assert lines[5] == "Database: 310 MB van 500 MB"


def test_build_usage_report_unknown():
    lines = build_usage_report(UsageStats(now=MONDAY)).split("\n")
    assert lines[1:] == [
        "Waarschuwingen: geen",
        "Open-Meteo: onbekend",
        "Database: onbekend",
        "Rijen: onbekend",
        "Runs (7 dagen): onbekend",
        "Stappen niet ok (7 dagen): onbekend",
        "Push (7 dagen): onbekend",
        "Gebruikers: onbekend, push-abonnementen: onbekend",
    ]
    no_runs = dataclasses.replace(UsageStats(now=MONDAY), runs_ok=0, runs_partial=0, runs_failed=0)
    lines = build_usage_report(no_runs).split("\n")
    assert "Runs (7 dagen): 0" in lines
    assert "Stappen niet ok (7 dagen): geen" in lines


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"database_bytes": 310 * BYTES_PER_MB}, ["Database 310 MB, boven 300 MB"]),
        ({"database_bytes": 300 * BYTES_PER_MB}, []),
        ({"database_bytes": 300 * BYTES_PER_MB + 1}, ["Database 301 MB, boven 300 MB"]),
        ({"open_meteo_today": 7100.0}, ["Open-Meteo vandaag 7.100 calls, boven 7.000"]),
        ({"open_meteo_today": 7000.0}, []),
        ({"open_meteo_month": 210001.0}, ["Open-Meteo deze maand 210.001 calls, boven 210.000"]),
        ({"open_meteo_month": 210000.0}, []),
        (
            {"database_bytes": 400 * BYTES_PER_MB, "open_meteo_today": 8000.0,
             "open_meteo_month": 250000.0},
            [
                "Database 400 MB, boven 300 MB",
                "Open-Meteo vandaag 8.000 calls, boven 7.000",
                "Open-Meteo deze maand 250.000 calls, boven 210.000",
            ],
        ),
    ],
)  # fmt: skip
def test_usage_warnings(changes, expected):
    assert usage_warnings(dataclasses.replace(STATS_OK, **changes)) == expected


def test_usage_warnings_ok_and_unknown():
    assert usage_warnings(STATS_OK) == []
    assert usage_warnings(UsageStats(now=MONDAY)) == []


def test_usage_push_text_golden():
    text = usage_push_text(STATS_OK)
    assert text.title == "Shakka weekrapport"
    assert (
        text.body
        == "Runs 95% ok · DB 42 MB · Open-Meteo max 1.421/dag\n2 gebruikers, 2 abonnementen"
    )
    warn = usage_push_text(STATS_WARN)
    assert warn.title == "Shakka weekrapport: let op"
    assert warn.body == (
        "Database 310 MB, boven 300 MB\n"
        "Open-Meteo vandaag 7.100 calls, boven 7.000\n"
        "Runs 95% ok · DB 310 MB · Open-Meteo max 7.100/dag"
    )


def test_usage_push_text_unknown():
    text = usage_push_text(UsageStats(now=MONDAY))
    assert text.body == "Runs ?% ok · DB ? MB · Open-Meteo max ?/dag\n? gebruikers, ? abonnementen"


def test_push_text_bounds():
    big = dict(database_bytes=10**12, open_meteo_today=1e7, open_meteo_max_day=1e7,
               open_meteo_month=1e7)  # fmt: skip
    grid = [
        UsageStats(now=MONDAY),
        dataclasses.replace(
            UsageStats(now=MONDAY),
            runs_ok=0,
            runs_partial=0,
            runs_failed=0,
            database_bytes=0,
            open_meteo_today=0,
            open_meteo_max_day=0,
            open_meteo_month=0,
            table_rows={"profiles": 0},
        ),  # fmt: skip
        dataclasses.replace(STATS_OK, **big),
        dataclasses.replace(
            STATS_OK, **big, table_rows={"profiles": 10**9, "push_subscriptions": 10**9}
        ),
    ]
    for stats in grid:
        text = usage_push_text(stats)
        assert 0 < len(text.title) <= 50 and len(text.body) <= 150
        warnings = usage_warnings(stats)
        if warnings:
            assert text.body.startswith(warnings[0][:20])


def test_warning_push_text():
    text = warning_push_text(
        ["Database 310 MB, boven 300 MB", "Open-Meteo vandaag 7.100 calls, boven 7.000"]
    )
    assert text.title == WARNING_TITLE
    assert text.body == (
        "Database 310 MB, boven 300 MB\nOpen-Meteo vandaag 7.100 calls, boven 7.000"
    )
    with pytest.raises(ValueError):
        warning_push_text([])


def test_titles():
    assert REPORT_TITLE == "Shakka weekrapport" and REPORT_TITLE_WARN.startswith(REPORT_TITLE)


def test_time_helpers():
    assert week_start(datetime(2026, 7, 15, 6, 17, tzinfo=UTC)) == datetime(
        2026, 7, 12, 22, tzinfo=UTC
    )
    assert week_start(datetime(2026, 10, 26, 7, 17, tzinfo=UTC)) == datetime(
        2026, 10, 25, 23, tzinfo=UTC
    )
    assert local_day_start(datetime(2026, 7, 15, 6, 17, tzinfo=UTC)) == datetime(
        2026, 7, 14, 22, tzinfo=UTC
    )
    assert not in_operator_window(datetime(2026, 7, 20, 5, 59, tzinfo=UTC))
    assert in_operator_window(datetime(2026, 7, 20, 6, 0, tzinfo=UTC))
    assert in_operator_window(datetime(2026, 7, 20, 19, 59, tzinfo=UTC))
    assert not in_operator_window(datetime(2026, 7, 20, 20, 0, tzinfo=UTC))
    assert report_due_time(MONDAY)
    assert not report_due_time(datetime(2026, 7, 20, 5, 17, tzinfo=UTC))
    assert not report_due_time(datetime(2026, 7, 21, 6, 17, tzinfo=UTC))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"now": datetime(2026, 7, 20, 6, 17)},  # noqa: DTZ001
        {"open_meteo_today": -1.0},
        {"open_meteo_today": float("nan")},
        {"database_bytes": True},
        {"database_bytes": -1},
        {"runs_ok": 1},
        {"table_rows": {"spots": -1}},
        {"step_issues": {"tides": 1.5}},
    ],
)
def test_usage_stats_validation(kwargs):
    base = {"now": MONDAY}
    with pytest.raises(ValueError):
        UsageStats(**{**base, **kwargs})


def test_limits_match_budget():
    assert OPEN_METEO_DAILY_LIMIT == BUDGET_DAILY
    assert OPEN_METEO_MONTHLY_LIMIT == BUDGET_MONTHLY
