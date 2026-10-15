"""Push text shortening and payload (WP-17 AC-3). Pure."""

import json

import pytest
from pydantic import ValidationError

from message_fixtures import GOLDEN_CASES, GoldenCase
from shakka.domain.dedup import AlertEventKind
from shakka.domain.messages import AlertMessage, render_alert
from shakka.domain.push import (
    FALLBACK_TITLE,
    PUSH_BODY_MAX,
    PUSH_TITLE_MAX,
    PushPayload,
    build_push_payload,
    payload_size,
    push_tag,
    shorten_words,
    spot_path,
    to_push_text,
)


def render(case: GoldenCase) -> AlertMessage:
    return render_alert(
        case.event, case.spot, kite=case.kite, tides=case.tides, base_url=case.base_url
    )


def make_message(*, title="Go: X", body="regel", go_url=None, spot_id="test-strand", kind=None):
    return AlertMessage(
        spot_id=spot_id,
        kind=kind or AlertEventKind.NEW,
        title=title,
        body=body,
        go_url=go_url,
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c.name)
def test_golden_lengths(case):
    t = to_push_text(render(case))
    assert len(t.title) <= PUSH_TITLE_MAX
    assert len(t.body) <= PUSH_BODY_MAX
    assert t.title == case.title


EXPECTED_LINES = {
    "new_summer_plain": (None, 110),
    "worsened_winter": (None, 142),
    "cancelled_winter": (None, 132),
    "new_summer_kite_tide": (4, 133),
    "improved_summer": (4, 148),
    "new_winter_tide": (3, 105),
}


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c.name)
def test_golden_bodies(case):
    if case.name not in EXPECTED_LINES:
        pytest.skip("no expectation for this case")
    lines, length = EXPECTED_LINES[case.name]
    t = to_push_text(render(case))
    if lines is None:
        assert t.body == case.body
    else:
        assert t.body == "\n".join(case.body.split("\n")[:lines])
    assert len(t.body) == length


def test_unchanged_when_fits():
    t = to_push_text(make_message(title="t" * 50, body="b" * 150))
    assert t.title == "t" * 50
    assert t.body == "b" * 150


def test_body_cut_on_line_boundary():
    body = "\n".join(["a" * 60] * 3)
    t = to_push_text(make_message(body=body))
    assert t.body == "\n".join(["a" * 60] * 2)
    assert len(t.body) == 121
    assert "…" not in t.body


def test_first_line_too_long():
    body = ("woord " * 40).strip() + "\nregel 2"
    t = to_push_text(make_message(body=body))
    assert t.body.endswith("…")
    assert len(t.body) <= 150
    assert set(t.body[:-1].split()) == {"woord"}
    assert body.split("\n")[0].startswith(t.body[:-1])


def test_single_long_word():
    t = to_push_text(make_message(body="x" * 200))
    assert t.body == "x" * 149 + "…"


def test_trailing_separator_stripped():
    text = "za 18 jul 14:00–18:00 · " + "a" * 140
    assert shorten_words(text, 150) == "za 18 jul 14:00–18:00…"


def test_title_shortened():
    t = to_push_text(make_message(title="Go: " + "Zeer lange spotnaam " * 5))
    assert len(t.title) <= 50
    assert t.title.endswith("…")
    assert set(t.title[:-1].replace("Go:", "").split()) <= {"Zeer", "lange", "spotnaam"}


def test_title_never_empty():
    assert to_push_text(make_message(title="   ")).title == FALLBACK_TITLE == "Shakka"
    for case in GOLDEN_CASES:
        assert to_push_text(render(case)).title.strip() != ""


def test_code_points():
    title = "ü🌊" * 25
    assert len(title) == 50
    assert to_push_text(make_message(title=title)).title == title


def test_shorten_words_limit():
    with pytest.raises(ValueError):
        shorten_words("abc", 1)


def test_build_payload():
    m = make_message(title="Go: A–B", go_url="https://shakka.test/go/x")
    p = build_push_payload(m, tag="alert-1")
    assert p.url == "https://shakka.test/go/x"
    cancelled = make_message(kind=AlertEventKind.CANCELLED, spot_id="test-strand")
    assert build_push_payload(cancelled, tag="alert-1").url == "/spot/test-strand"
    with pytest.raises(ValidationError):
        build_push_payload(m, tag="has space")
    raw = p.to_json()
    assert "–" in raw
    assert "\\u2013" not in raw
    assert list(json.loads(raw)) == ["title", "body", "url", "tag"]
    assert payload_size(p) == len(raw.encode("utf-8"))
    assert payload_size(p) > len(raw)  # the en dash is three bytes


def test_payload_fallback_url():
    long_url = "https://shakka.test/" + "p" * 2980
    m = make_message(go_url=long_url, spot_id="test-strand")
    p = build_push_payload(m, tag="alert-1")
    assert p.url == "/spot/test-strand"
    assert payload_size(p) <= 3000


def test_payload_too_large_raises():
    with pytest.raises(ValueError):
        build_push_payload(make_message(spot_id="s" * 4000), tag="alert-1")


def test_helpers():
    assert spot_path("abc") == "/spot/abc"
    assert push_tag("1234") == "alert-1234"
    assert isinstance(PushPayload(title="t", body="", url="/", tag="x"), PushPayload)


def test_payload_validation():
    for bad in (
        {"title": "a\nb", "body": "", "url": "/", "tag": "x"},
        {"title": "", "body": "", "url": "/", "tag": "x"},
        {"title": "t", "body": "", "url": "/a b", "tag": "x"},
        {"title": "t", "body": "", "url": "/", "tag": "x" * 65},
    ):
        with pytest.raises(ValidationError):
            PushPayload(**bad)
