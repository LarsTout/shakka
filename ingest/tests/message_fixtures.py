"""Fixtures and golden messages for the alert message tests (WP-08; reused by WP-17 AC-3)."""

from datetime import UTC, datetime
from typing import NamedTuple

from evaluation_fixtures import make_spot
from shakka.domain.consensus import Confidence
from shakka.domain.dedup import AlertEvent, AlertEventKind, WindowSnapshot
from shakka.domain.direction import DirClass
from shakka.domain.kite import KiteAdvice
from shakka.domain.spot import SpotProfile
from shakka.domain.tide import TideExtreme


def at(y: int, m: int, d: int, h: int, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=UTC)


PLAIN_SPOT = make_spot()
LOW_TIDE_SPOT = make_spot(tide_sensitive="prefer_low", rws_station="teststation")
AVOID_LOW_SPOT = make_spot(tide_sensitive="avoid_low", rws_station="teststation")

S_SUMMER = WindowSnapshot(
    start=at(2026, 7, 18, 12),
    end=at(2026, 7, 18, 16),
    wind_min_kn=16.0,
    wind_max_kn=22.4,
    gust_max_kn=27.5,
    dir_deg=225,
    dir_class=DirClass.SIDE_ONSHORE,
    confidence=Confidence.HIGH,
)
P_SUMMER = WindowSnapshot(
    start=at(2026, 7, 18, 14),
    end=at(2026, 7, 18, 16),
    wind_min_kn=14.0,
    wind_max_kn=18.0,
    gust_max_kn=22.0,
    dir_deg=230,
    dir_class=DirClass.SIDE_ONSHORE,
    confidence=Confidence.MEDIUM,
)
S_WINTER = WindowSnapshot(
    start=at(2026, 11, 7, 11),
    end=at(2026, 11, 7, 14),
    wind_min_kn=18.0,
    wind_max_kn=24.0,
    gust_max_kn=None,
    dir_deg=270,
    dir_class=DirClass.ONSHORE,
    confidence=Confidence.MEDIUM,
)
P_WINTER = WindowSnapshot(
    start=at(2026, 11, 7, 11),
    end=at(2026, 11, 7, 16),
    wind_min_kn=18.0,
    wind_max_kn=25.0,
    gust_max_kn=30.0,
    dir_deg=265,
    dir_class=DirClass.ONSHORE,
    confidence=Confidence.MEDIUM,
)


def _tide(station: str, when: datetime, kind: str, level: int) -> TideExtreme:
    return TideExtreme.model_validate(
        {"station": station, "at": when, "kind": kind, "level_cm": level}
    )


TIDES_SUMMER = [
    _tide("teststation", at(2026, 7, 18, 4, 20), "high", 100),
    _tide("teststation", at(2026, 7, 18, 10, 30), "low", -85),
    _tide("anderstation", at(2026, 7, 18, 13, 0), "high", 120),
    _tide("teststation", at(2026, 7, 18, 16, 45), "high", 110),
    _tide("teststation", at(2026, 7, 18, 22, 55), "low", -80),
]
TIDES_WINTER = [
    _tide("teststation", at(2026, 11, 7, 9, 10), "high", 95),
    _tide("teststation", at(2026, 11, 7, 15, 40), "low", -70),
]

KITE_IDEAL = KiteAdvice(size_m2=9.0, fit="ideal", ideal_size_m2=8.8)
KITE_OVER = KiteAdvice(size_m2=12.0, fit="overpowered", ideal_size_m2=9.4)

BASE = "https://example.org"
URL_SUMMER = (
    "https://example.org/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z"
    "&end=2026-07-18T16%3A00%3A00Z"
)
URL_WINTER = (
    "https://example.org/go?spot=test-strand&start=2026-11-07T11%3A00%3A00Z"
    "&end=2026-11-07T14%3A00%3A00Z"
)


class GoldenCase(NamedTuple):
    name: str
    event: AlertEvent
    spot: SpotProfile
    kite: KiteAdvice | None
    tides: list[TideExtreme]
    base_url: str | None
    title: str
    body: str
    go_url: str | None


def _event(
    kind: AlertEventKind, current: WindowSnapshot | None, previous: WindowSnapshot | None
) -> AlertEvent:
    return AlertEvent(
        kind=kind, spot_id="test-strand", current=current, previous=previous, state_index=0
    )


_NEW_SUMMER_LINES = (
    "za 18 jul 14:00–18:00 · 16–22 kn, vlagen tot 28 kn\n"
    "Wind uit ZW (225°) · Schuin aanlandig\n"
    "Betrouwbaarheid: Hoog"
)

GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        "new_summer_plain",
        _event(AlertEventKind.NEW, S_SUMMER, None),
        PLAIN_SPOT,
        None,
        [],
        BASE,
        "Go: Teststrand",
        _NEW_SUMMER_LINES,
        URL_SUMMER,
    ),
    GoldenCase(
        "new_summer_kite_tide",
        _event(AlertEventKind.NEW, S_SUMMER, None),
        LOW_TIDE_SPOT,
        KITE_IDEAL,
        TIDES_SUMMER,
        None,
        "Go: Teststrand",
        _NEW_SUMMER_LINES
        + "\nKite: 9 m² (past goed)"
        + "\nGetij (voorkeur laagwater): laag 12:30 (-85 cm), hoog 18:45 (+110 cm)",
        None,
    ),
    GoldenCase(
        "improved_summer",
        _event(AlertEventKind.IMPROVED, S_SUMMER, P_SUMMER),
        PLAIN_SPOT,
        KITE_OVER,
        [],
        "https://example.org/",
        "Beter: Teststrand",
        "za 18 jul 14:00–18:00 · 16–22 kn, vlagen tot 28 kn\n"
        "Was: za 18 jul 16:00–18:00 · 14–18 kn\n"
        "Wind uit ZW (225°) · Schuin aanlandig\n"
        "Betrouwbaarheid: Hoog\n"
        "Kite: 12 m² (aan de grote kant, ideaal 9,4 m²)",
        URL_SUMMER,
    ),
    GoldenCase(
        "new_winter_tide",
        _event(AlertEventKind.NEW, S_WINTER, None),
        AVOID_LOW_SPOT,
        None,
        TIDES_WINTER,
        None,
        "Go: Teststrand",
        "za 7 nov 12:00–15:00 · 18–24 kn, vlagen onbekend\n"
        "Wind uit W (270°) · Aanlandig\n"
        "Betrouwbaarheid: Gemiddeld\n"
        "Getij (liever geen laagwater): hoog 10:10 (+95 cm), laag 16:40 (-70 cm)",
        None,
    ),
    GoldenCase(
        "worsened_winter",
        _event(AlertEventKind.WORSENED, S_WINTER, P_WINTER),
        PLAIN_SPOT,
        None,
        [],
        BASE,
        "Slechter: Teststrand",
        "za 7 nov 12:00–15:00 · 18–24 kn, vlagen onbekend\n"
        "Was: za 7 nov 12:00–17:00 · 18–25 kn\n"
        "Wind uit W (270°) · Aanlandig\n"
        "Betrouwbaarheid: Gemiddeld",
        URL_WINTER,
    ),
    GoldenCase(
        "cancelled_winter",
        _event(AlertEventKind.CANCELLED, None, S_WINTER),
        AVOID_LOW_SPOT,
        KITE_IDEAL,
        TIDES_WINTER,
        BASE,
        "Gaat niet door: Teststrand",
        "Window za 7 nov 12:00–15:00 vervalt\n"
        "Verwacht was: 18–24 kn, vlagen onbekend\n"
        "Wind uit W (270°) · Aanlandig\n"
        "Betrouwbaarheid: Gemiddeld",
        None,
    ),
]
