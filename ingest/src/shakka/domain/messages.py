"""Channel-independent Dutch alert messages and the "ik ga" link (WP-08). Pure.

The body is built in order of importance (time and wind first), so a channel can shorten it
by taking whole lines from the start. URL encoding is done here, without URL libraries.
"""

import math
import string
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shakka.domain.consensus import CONFIDENCE_LABEL_NL
from shakka.domain.dedup import AlertEvent, AlertEventKind, WindowSnapshot
from shakka.domain.defaults import LOCAL_TZ
from shakka.domain.direction import DIR_CLASS_LABEL_NL, compass_label
from shakka.domain.kite import KiteAdvice, KiteFit
from shakka.domain.spot import SpotProfile, TideSensitivity
from shakka.domain.tide import TideExtreme

TIDE_CONTEXT_MARGIN: Final = timedelta(hours=3)  # within the window or 3 h around
MAX_TIDE_EXTREMES_IN_MESSAGE: Final = 6
WEEKDAY_ABBR_NL: Final[tuple[str, ...]] = ("ma", "di", "wo", "do", "vr", "za", "zo")
MONTH_ABBR_NL: Final[tuple[str, ...]] = (
    "jan",
    "feb",
    "mrt",
    "apr",
    "mei",
    "jun",
    "jul",
    "aug",
    "sep",
    "okt",
    "nov",
    "dec",
)
EVENT_TITLE_NL: Final[dict[AlertEventKind, str]] = {
    AlertEventKind.NEW: "Go",
    AlertEventKind.IMPROVED: "Beter",
    AlertEventKind.WORSENED: "Slechter",
    AlertEventKind.CANCELLED: "Gaat niet door",
}
KITE_FIT_LABEL_NL: Final[dict[KiteFit, str]] = {
    KiteFit.IDEAL: "past goed",
    KiteFit.UNDERPOWERED: "aan de kleine kant",
    KiteFit.OVERPOWERED: "aan de grote kant",
}
TIDE_PREFERENCE_LABEL_NL: Final[dict[TideSensitivity, str]] = {
    TideSensitivity.PREFER_LOW: "voorkeur laagwater",
    TideSensitivity.PREFER_HIGH: "voorkeur hoogwater",
    TideSensitivity.AVOID_LOW: "liever geen laagwater",
}
TIDE_KIND_LABEL_NL: Final[dict[str, str]] = {"high": "hoog", "low": "laag"}
_URL_SAFE: Final[frozenset[str]] = frozenset(string.ascii_letters + string.digits + "-._~")
_HOUR: Final = timedelta(hours=1)


class AlertMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spot_id: str = Field(min_length=1)
    kind: AlertEventKind
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    go_url: str | None

    @field_validator("title")
    @classmethod
    def _single_line(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("title must not contain a newline")
        return value


def _check_aware(*values: datetime) -> None:
    for v in values:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("times must be timezone-aware")


def _day(d: datetime) -> str:
    return f"{WEEKDAY_ABBR_NL[d.isoweekday() - 1]} {d.day} {MONTH_ABBR_NL[d.month - 1]}"


def format_window_local(start: datetime, end: datetime) -> str:
    """'za 18 okt 14:00–18:00' in Europe/Amsterdam. ValueError if naive or start >= end."""
    _check_aware(start, end)
    if not start < end:
        raise ValueError("start must be before end")
    ls = start.astimezone(LOCAL_TZ)
    le = end.astimezone(LOCAL_TZ)
    if (end - timedelta(microseconds=1)).astimezone(LOCAL_TZ).date() == ls.date():
        return f"{_day(ls)} {ls:%H:%M}–{le:%H:%M}"
    return f"{_day(ls)} {ls:%H:%M} – {_day(le)} {le:%H:%M}"


def _quote(text: str) -> str:
    """Percent-encode like the standard-library quote with an empty safe set."""
    return "".join(c if c in _URL_SAFE else "".join(f"%{b:02X}" for b in c.encode()) for c in text)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if (
        not base
        or not base.startswith(("https://", "http://"))
        or any(c.isspace() or c in "?#" for c in base)
    ):
        raise ValueError("base_url must be an http(s) URL without whitespace, '?' or '#'")
    return base


def build_go_url(base_url: str, spot_id: str, start: datetime, end: datetime) -> str:
    """{base_url}/go?spot={spot_id}&start={start}&end={end}; start/end ISO 8601 UTC with Z,
    percent-encoded like the standard-library quote with an empty safe set. Trailing '/' of
    base_url is dropped.
    ValueError on an invalid base_url, naive or non-whole-hour times, or start >= end."""
    base = _check_base_url(base_url)
    _check_aware(start, end)
    for value in (start, end):
        u = value.astimezone(UTC)
        if u.minute or u.second or u.microsecond:
            raise ValueError("start and end must be whole hours")
    if not start < end:
        raise ValueError("start must be before end")
    return f"{base}/go?spot={_quote(spot_id)}&start={_quote(_iso(start))}&end={_quote(_iso(end))}"


def _kn(x: float) -> str:
    return str(math.floor(x + 0.5))


def _m2(x: float) -> str:
    t = math.floor(x * 10 + 0.5)
    return str(t // 10) if t % 10 == 0 else f"{t // 10},{t % 10}"


def _wind_range(s: WindowSnapshot) -> str:
    lo, hi = _kn(s.wind_min_kn), _kn(s.wind_max_kn)
    return f"{lo} kn" if lo == hi else f"{lo}–{hi} kn"


def _gusts(s: WindowSnapshot) -> str:
    return "vlagen onbekend" if s.gust_max_kn is None else f"vlagen tot {_kn(s.gust_max_kn)} kn"


def _window(s: WindowSnapshot) -> str:
    return format_window_local(s.start, s.end)


def _when_wind(s: WindowSnapshot) -> str:
    return f"{_window(s)} · {_wind_range(s)}, {_gusts(s)}"


def _was(p: WindowSnapshot) -> str:
    return f"Was: {_window(p)} · {_wind_range(p)}"


def _direction(s: WindowSnapshot) -> str:
    return f"Wind uit {compass_label(s.dir_deg)} ({s.dir_deg}°) · {DIR_CLASS_LABEL_NL[s.dir_class]}"


def _confidence(s: WindowSnapshot) -> str:
    return f"Betrouwbaarheid: {CONFIDENCE_LABEL_NL[s.confidence]}"


def _kite_line(kite: KiteAdvice) -> str:
    label = KITE_FIT_LABEL_NL[kite.fit]
    if kite.fit == KiteFit.IDEAL:
        return f"Kite: {_m2(kite.size_m2)} m² ({label})"
    return f"Kite: {_m2(kite.size_m2)} m² ({label}, ideaal {_m2(kite.ideal_size_m2)} m²)"


def _tide_line(s: WindowSnapshot, spot: SpotProfile, tides: Sequence[TideExtreme]) -> str | None:
    if spot.tide_sensitive == TideSensitivity.NONE or spot.rws_station is None:
        return None
    station = spot.rws_station.strip()
    lo, hi = s.start - TIDE_CONTEXT_MARGIN, s.end + TIDE_CONTEXT_MARGIN
    picked = sorted(
        (e for e in tides if e.station == station and lo <= e.at <= hi), key=lambda e: e.at
    )[:MAX_TIDE_EXTREMES_IN_MESSAGE]
    if not picked:
        return None
    start_date = s.start.astimezone(LOCAL_TZ).date()
    parts = []
    for e in picked:
        local = e.at.astimezone(LOCAL_TZ)
        when = f"{local:%H:%M}"
        if local.date() != start_date:
            when = f"{WEEKDAY_ABBR_NL[local.isoweekday() - 1]} {when}"
        level = "0" if e.level_cm == 0 else f"{e.level_cm:+d}"
        parts.append(f"{TIDE_KIND_LABEL_NL[e.kind]} {when} ({level} cm)")
    label = TIDE_PREFERENCE_LABEL_NL[spot.tide_sensitive]
    return f"Getij ({label}): " + ", ".join(parts)


def render_alert(
    event: AlertEvent,
    spot: SpotProfile,
    *,
    kite: KiteAdvice | None,
    tides: Sequence[TideExtreme],
    base_url: str | None,
) -> AlertMessage:
    """Plain-text Dutch message. ValueError if event.spot_id != spot.id."""
    if event.spot_id != spot.id:
        raise ValueError(f"event is for spot {event.spot_id!r}, not {spot.id!r}")
    kind = event.kind
    cancelled = kind == AlertEventKind.CANCELLED
    s = event.previous if cancelled else event.current
    assert s is not None  # guaranteed by AlertEvent

    lines: list[str] = []
    if cancelled:
        lines += [f"Window {_window(s)} vervalt", f"Verwacht was: {_wind_range(s)}, {_gusts(s)}"]
        lines += [_direction(s), _confidence(s)]
    else:
        lines.append(_when_wind(s))
        if kind in (AlertEventKind.IMPROVED, AlertEventKind.WORSENED):
            assert event.previous is not None
            lines.append(_was(event.previous))
        lines += [_direction(s), _confidence(s)]
        if kite is not None:
            lines.append(_kite_line(kite))
        tide = _tide_line(s, spot, tides)
        if tide is not None:
            lines.append(tide)

    go_url = None
    if not cancelled and base_url is not None and base_url.strip():
        go_url = build_go_url(base_url.strip(), spot.id, s.start, s.end)

    name = " ".join(spot.name.split())
    return AlertMessage(
        spot_id=spot.id,
        kind=kind,
        title=f"{EVENT_TITLE_NL[kind]}: {name}",
        body="\n".join(lines),
        go_url=go_url,
    )
