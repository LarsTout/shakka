"""Tests for shakka.domain.messages (WP-08)."""

import inspect
import urllib.parse
from datetime import UTC, datetime, timedelta

import pytest

from evaluation_fixtures import make_spot
from message_fixtures import (
    AVOID_LOW_SPOT,
    GOLDEN_CASES,
    KITE_IDEAL,
    LOW_TIDE_SPOT,
    PLAIN_SPOT,
    S_SUMMER,
    TIDES_SUMMER,
    URL_SUMMER,
    GoldenCase,
    _event,
    _tide,
    at,
)
from shakka.domain.consensus import CONFIDENCE_LABEL_NL
from shakka.domain.dedup import AlertEventKind
from shakka.domain.defaults import LOCAL_TZ
from shakka.domain.direction import DIR_CLASS_LABEL_NL, compass_label
from shakka.domain.kite import KiteAdvice
from shakka.domain.messages import (
    MAX_TIDE_EXTREMES_IN_MESSAGE,
    _quote,
    build_go_url,
    format_window_local,
    render_alert,
)

K = AlertEventKind


def render(case: GoldenCase):
    return render_alert(
        case.event, case.spot, kite=case.kite, tides=case.tides, base_url=case.base_url
    )


def new_summer(spot=PLAIN_SPOT, kite=None, tides=(), base_url=None):
    return render_alert(
        _event(K.NEW, S_SUMMER, None), spot, kite=kite, tides=list(tides), base_url=base_url
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c.name)
def test_golden(case):
    msg = render(case)
    assert msg.title == case.title
    assert msg.body == case.body
    assert msg.go_url == case.go_url
    assert msg.spot_id == "test-strand"
    assert msg.kind == case.event.kind
    assert len(case.title) <= 26


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c.name)
def test_required_parts_present(case):
    s = case.event.current or case.event.previous
    msg = render(case)
    text = msg.title + "\n" + msg.body
    for part in (
        "Teststrand",
        format_window_local(s.start, s.end),
        " kn",
        "vlagen",
        compass_label(s.dir_deg),
        f"({s.dir_deg}°)",
        DIR_CLASS_LABEL_NL[s.dir_class],
        CONFIDENCE_LABEL_NL[s.confidence],
    ):
        assert part in text, part
    assert "flandig" not in text.replace("aanlandig", "").replace("Aanlandig", "")
    assert "Aflandig" not in text
    assert "aflandig" not in text


def _tide_line(msg):
    lines = [x for x in msg.body.split("\n") if x.startswith("Getij")]
    return lines[0] if lines else None


def test_tide_line_rules():
    assert _tide_line(new_summer(PLAIN_SPOT, tides=TIDES_SUMMER)) is None
    far = [_tide("teststation", at(2026, 7, 18, 4, 0), "high", 100)]
    assert _tide_line(new_summer(LOW_TIDE_SPOT, tides=far)) is None
    no_station = make_spot(tide_sensitive="prefer_low")
    assert _tide_line(new_summer(no_station, tides=TIDES_SUMMER)) is None
    edge = [
        _tide("teststation", at(2026, 7, 18, 9, 0), "low", -10),
        _tide("teststation", at(2026, 7, 18, 19, 0), "high", 10),
    ]
    line = _tide_line(new_summer(LOW_TIDE_SPOT, tides=edge))
    assert line == "Getij (voorkeur laagwater): laag 11:00 (-10 cm), hoog 21:00 (+10 cm)"
    out = [
        _tide("teststation", at(2026, 7, 18, 8, 59), "low", -10),
        _tide("teststation", at(2026, 7, 18, 19, 1), "high", 10),
    ]
    assert _tide_line(new_summer(LOW_TIDE_SPOT, tides=out)) is None
    # other local date -> weekday abbreviation
    ev = _event(K.NEW, _snap(at(2026, 7, 18, 18), at(2026, 7, 18, 20)), None)
    late = [_tide("teststation", at(2026, 7, 18, 22, 30), "high", 0)]
    msg = render_alert(ev, LOW_TIDE_SPOT, kite=None, tides=late, base_url=None)
    assert _tide_line(msg) == "Getij (voorkeur laagwater): hoog zo 00:30 (0 cm)"
    spaced = make_spot(tide_sensitive="prefer_low", rws_station=" teststation ")
    assert _tide_line(new_summer(spaced, tides=TIDES_SUMMER)) is not None


def _snap(start, end):
    return S_SUMMER.model_copy(update={"start": start, "end": end})


def test_kite_line_rules():
    def kite_line(advice, kind=K.NEW):
        ev = (
            _event(K.CANCELLED, None, S_SUMMER)
            if kind == K.CANCELLED
            else _event(K.NEW, S_SUMMER, None)
        )
        msg = render_alert(ev, PLAIN_SPOT, kite=advice, tides=[], base_url=None)
        lines = [x for x in msg.body.split("\n") if x.startswith("Kite")]
        return lines[0] if lines else None

    assert kite_line(KITE_IDEAL) == "Kite: 9 m² (past goed)"
    under = KiteAdvice(size_m2=14.0, fit="underpowered", ideal_size_m2=15.8)
    assert kite_line(under) == "Kite: 14 m² (aan de kleine kant, ideaal 15,8 m²)"
    assert kite_line(KiteAdvice(size_m2=10.5, fit="ideal", ideal_size_m2=10.5)) == (
        "Kite: 10,5 m² (past goed)"
    )
    for size, text in ((9.25, "9,3"), (9.75, "9,8"), (9.96, "10"), (9.24, "9,2")):
        assert kite_line(KiteAdvice(size_m2=size, fit="ideal", ideal_size_m2=size)) == (
            f"Kite: {text} m² (past goed)"
        )
    assert kite_line(KITE_IDEAL, K.CANCELLED) is None
    assert kite_line(None) is None


def test_go_url_rules():
    for base in (None, "", "   "):
        assert new_summer(base_url=base).go_url is None
    assert new_summer(base_url="https://example.org/").go_url == URL_SUMMER
    assert new_summer(base_url="https://example.org").go_url == URL_SUMMER
    for bad in ("example.org", "https://example.org/?x=1", "https://exa mple.org"):
        with pytest.raises(ValueError):
            new_summer(base_url=bad)


def test_format_window_local():
    assert (
        format_window_local(at(2026, 7, 18, 20), at(2026, 7, 18, 23))
        == "za 18 jul 22:00 – zo 19 jul 01:00"
    )
    assert format_window_local(at(2026, 7, 18, 20), at(2026, 7, 18, 22)) == "za 18 jul 22:00–00:00"
    assert (
        format_window_local(at(2026, 10, 25, 10), at(2026, 10, 25, 12)) == "zo 25 okt 11:00–13:00"
    )
    with pytest.raises(ValueError):
        format_window_local(at(2026, 7, 18, 10).replace(tzinfo=None), at(2026, 7, 18, 12))
    with pytest.raises(ValueError):
        format_window_local(at(2026, 7, 18, 12), at(2026, 7, 18, 12))


def test_title_normalized():
    spot = make_spot(name="Wijk  aan\nZee")
    assert new_summer(spot).title == "Go: Wijk aan Zee"


def test_spot_mismatch():
    with pytest.raises(ValueError):
        render_alert(
            _event(K.NEW, S_SUMMER, None),
            make_spot(id="anders"),
            kite=None,
            tides=[],
            base_url=None,
        )


@pytest.mark.parametrize(
    ("spot_id", "start", "end"),
    [
        ("test-strand", at(2026, 7, 18, 12), at(2026, 7, 18, 16)),
        ("wijk-aan-zee", at(2026, 11, 7, 11), at(2026, 11, 7, 14)),
        (
            "test-strand",
            at(2026, 7, 18, 12).astimezone(LOCAL_TZ),
            at(2026, 7, 18, 16).astimezone(LOCAL_TZ),
        ),
    ],
)
def test_build_go_url_roundtrip(spot_id, start, end):
    url = build_go_url("https://example.org", spot_id, start, end)
    parts = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qs(parts.query)
    assert parts.path == "/go"
    assert qs["spot"] == [spot_id]
    assert datetime.fromisoformat(qs["start"][0]) == start
    assert datetime.fromisoformat(qs["end"][0]) == end
    assert [kv.split("=")[0] for kv in parts.query.split("&")] == ["spot", "start", "end"]


@pytest.mark.parametrize("s", ["2026-07-18T12:00:00Z", "a b+c/d?e&f=g#h", "é~._-", "Zoë"])
def test_quote_matches_urllib(s):
    assert _quote(s) == urllib.parse.quote(s, safe="")


def test_build_go_url_invalid():
    ok = (at(2026, 7, 18, 12), at(2026, 7, 18, 16))
    with pytest.raises(ValueError):
        build_go_url("https://x.org", "a", ok[0].replace(tzinfo=None), ok[1])
    with pytest.raises(ValueError):
        build_go_url("https://x.org", "a", ok[1], ok[0])
    with pytest.raises(ValueError):
        build_go_url("https://x.org", "a", ok[0] + timedelta(minutes=5), ok[1])


def test_no_bypass_parameters():
    for fn in (render_alert, build_go_url):
        for name in inspect.signature(fn).parameters:
            assert not any(w in name for w in ("offshore", "allow", "force", "unsafe")), name


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c.name)
def test_body_max_length(case):
    assert len(render(case).body) <= 1000


def test_body_max_length_stress():
    snap = S_SUMMER.model_copy(update={"start": at(2026, 7, 18, 4), "end": at(2026, 7, 18, 20)})
    tides = [
        _tide("teststation", at(2026, 7, 18, 1) + timedelta(hours=i), "high", 100 + i)
        for i in range(20)
    ]
    under = KiteAdvice(size_m2=14.0, fit="underpowered", ideal_size_m2=15.8)
    msg = render_alert(
        _event(K.NEW, snap, None), LOW_TIDE_SPOT, kite=under, tides=tides, base_url=None
    )
    line = _tide_line(msg)
    assert line is not None
    assert line.count("cm)") <= MAX_TIDE_EXTREMES_IN_MESSAGE
    assert len(msg.body) <= 1000


_ = (AVOID_LOW_SPOT, UTC)
