"""Tests for the Open-Meteo Marine parameter builder, parser and fetch (WP-12, AC-1).

Weather data by Open-Meteo.com (https://open-meteo.com/), licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Wave models: DWD EWAM and ECMWF WAM.

The fixture was recorded with CAPTURE_URL on CAPTURE_DATE; see tests/fixtures/openmeteo/README.md.
"""

import copy
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from openmeteo_payloads import make_marine_payload
from shakka.domain.forecast import SpotLocation
from shakka.domain.marine import MarineHour
from shakka.openmeteo.marine import (
    CELL_SELECTION,
    MARINE_MODELS,
    MARINE_VARIABLES,
    MarineFetchError,
    MarineParseError,
    build_marine_params,
    fetch_marine,
    parse_marine_response,
)

CAPTURE_DATE = "2026-10-15"
CAPTURE_URL = (
    "https://marine-api.open-meteo.com/v1/marine?latitude=52.4700,52.7500,52.0900"
    "&longitude=4.5700,5.3000,5.1200"
    "&hourly=wave_height,wave_period,wave_direction&models=ewam,ecmwf_wam"
    "&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea"
)
FIXTURE = Path(__file__).parent / "fixtures" / "openmeteo" / "marine_3loc_2models.json"
FIXTURE_LOCATIONS = [
    SpotLocation(spot_id="fixture-a", lat=52.47, lon=4.57),
    SpotLocation(spot_id="fixture-b", lat=52.75, lon=5.30),
    SpotLocation(spot_id="fixture-c", lat=52.09, lon=5.12),
]
T0 = datetime(2026, 10, 14, 0, tzinfo=UTC)


def loc(n: int = 1) -> list[SpotLocation]:
    return [SpotLocation(spot_id=f"s{i}", lat=52.0 + i / 100, lon=4.0) for i in range(n)]


def parse(payload: Any, n: int = 1) -> list[MarineHour]:
    return parse_marine_response(payload, loc(n))


@pytest.fixture(scope="module")
def raw() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(raw: list[dict[str, Any]]) -> list[MarineHour]:
    return parse_marine_response(raw, FIXTURE_LOCATIONS)


def triple(element: dict[str, Any], model: str, i: int) -> tuple[Any, Any, Any]:
    hourly = element["hourly"]
    return tuple(hourly[f"{v}_{model}"][i] for v in MARINE_VARIABLES)  # type: ignore[return-value]


def expected(element: dict[str, Any], i: int) -> tuple[Any, Any, Any] | None:
    for model in MARINE_MODELS:
        t = triple(element, model, i)
        if any(v is not None for v in t):
            h, p, d = t
            return (h, p, None if d is None else int(round(d)) % 360)
    return None


# -- parameters ---------------------------------------------------------------------------------


def test_build_params_exact() -> None:
    params = build_marine_params(FIXTURE_LOCATIONS)
    assert list(params) == [
        "latitude",
        "longitude",
        "hourly",
        "models",
        "timezone",
        "timeformat",
        "forecast_days",
        "cell_selection",
    ]
    assert params == {
        "latitude": "52.4700,52.7500,52.0900",
        "longitude": "4.5700,5.3000,5.1200",
        "hourly": "wave_height,wave_period,wave_direction",
        "models": "ewam,ecmwf_wam",
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": "7",
        "cell_selection": CELL_SELECTION,
    }
    assert CELL_SELECTION == "sea"


@pytest.mark.parametrize(
    ("n", "days"), [(0, 7), (51, 7), (1, 0), (1, 9)], ids=["none", "51", "days0", "days9"]
)
def test_build_params_validation(n: int, days: int) -> None:
    with pytest.raises(ValueError):
        build_marine_params(loc(n), forecast_days=days)


def test_models_tuple() -> None:
    assert MARINE_MODELS == ("ewam", "ecmwf_wam")
    assert len(MARINE_MODELS) >= 2


def test_fixture_matches_current_params() -> None:
    captured = dict(httpx.URL(CAPTURE_URL).params)
    assert build_marine_params(FIXTURE_LOCATIONS) == captured
    assert CAPTURE_DATE


# -- fixture (AC-1) -----------------------------------------------------------------------------


def test_fixture_all_valid_at_utc(rows: list[MarineHour]) -> None:
    assert rows
    assert all(r.valid_at.tzinfo is UTC for r in rows)


def test_fixture_values_match_raw_json(raw: list[dict[str, Any]], rows: list[MarineHour]) -> None:
    for index, element in enumerate(raw):
        spot_id = FIXTURE_LOCATIONS[index].spot_id
        times = element["hourly"]["time"]
        got = [r for r in rows if r.spot_id == spot_id]
        by_time = {r.valid_at: r for r in got}
        assert len(by_time) == len(got)
        for i, ts in enumerate(times):
            want = expected(element, i)
            at = datetime.fromtimestamp(ts, tz=UTC)
            if want is None:
                assert at not in by_time
            else:
                row = by_time[at]
                assert (row.wave_height_m, row.wave_period_s, row.wave_dir_deg) == want


def test_fixture_inland_has_no_rows(raw: list[dict[str, Any]], rows: list[MarineHour]) -> None:
    for key, series in raw[2]["hourly"].items():
        if key != "time":
            assert all(v is None for v in series), key
    assert not [r for r in rows if r.spot_id == "fixture-c"]


def test_fixture_lake_uses_ewam_only(raw: list[dict[str, Any]], rows: list[MarineHour]) -> None:
    element = raw[1]
    times = element["hourly"]["time"]
    lake = [r for r in rows if r.spot_id == "fixture-b"]
    assert 0 < len(lake) < len(times)
    index = {datetime.fromtimestamp(t, tz=UTC): i for i, t in enumerate(times)}
    for row in lake:
        i = index[row.valid_at]
        assert (row.wave_height_m, row.wave_period_s) == triple(element, "ewam", i)[:2]


def test_fixture_coast_switches_to_ecmwf(raw: list[dict[str, Any]], rows: list[MarineHour]) -> None:
    element = raw[0]
    times = element["hourly"]["time"]
    index = {datetime.fromtimestamp(t, tz=UTC): i for i, t in enumerate(times)}
    from_ewam = from_ecmwf = 0
    for row in (r for r in rows if r.spot_id == "fixture-a"):
        i = index[row.valid_at]
        ewam = triple(element, "ewam", i)
        if all(v is None for v in ewam):
            assert row.wave_height_m == element["hourly"]["wave_height_ecmwf_wam"][i]
            from_ecmwf += 1
        else:
            assert row.wave_height_m == ewam[0]
            from_ewam += 1
    assert from_ewam > 0
    assert from_ecmwf > 0


def test_fixture_values_belong_to_spot(raw: list[dict[str, Any]], rows: list[MarineHour]) -> None:
    first = datetime.fromtimestamp(raw[0]["hourly"]["time"][0], tz=UTC)
    a = next(r for r in rows if r.spot_id == "fixture-a" and r.valid_at == first)
    b = next(r for r in rows if r.spot_id == "fixture-b" and r.valid_at == first)
    assert a.wave_height_m == raw[0]["hourly"]["wave_height_ewam"][0]
    assert b.wave_height_m == raw[1]["hourly"]["wave_height_ewam"][0]
    assert (a.wave_height_m, a.wave_period_s, a.wave_dir_deg) != (
        b.wave_height_m,
        b.wave_period_s,
        b.wave_dir_deg,
    )


# -- synthetic ----------------------------------------------------------------------------------


def test_parse_single_location_object() -> None:
    payload = make_marine_payload(1, start=T0)
    assert isinstance(payload, dict)
    out = parse(payload)
    assert len(out) == 3
    assert out[0] == MarineHour(
        spot_id="s0", valid_at=T0, wave_height_m=1.2, wave_period_s=5.0, wave_dir_deg=250
    )


def test_parse_order_per_location() -> None:
    out = parse(make_marine_payload(2, start=T0, hours=2), 2)
    assert [(r.spot_id, r.valid_at.hour) for r in out] == [
        ("s0", 0),
        ("s0", 1),
        ("s1", 0),
        ("s1", 1),
    ]


def test_parse_partial_triple_not_mixed() -> None:
    out = parse(make_marine_payload(1, start=T0, ewam=(0.9, None, None)))
    assert {(r.wave_height_m, r.wave_period_s, r.wave_dir_deg) for r in out} == {(0.9, None, None)}


def test_parse_falls_back_to_second_model() -> None:
    out = parse(make_marine_payload(1, start=T0, ewam=(None, None, None)))
    assert {(r.wave_height_m, r.wave_period_s, r.wave_dir_deg) for r in out} == {(1.4, 6.0, 260)}


def test_parse_all_none_no_row() -> None:
    nothing = (None, None, None)
    assert parse(make_marine_payload(1, start=T0, ewam=nothing, ecmwf=nothing)) == []


def test_parse_negative_and_non_finite_are_none() -> None:
    payload = make_marine_payload(
        1,
        start=T0,
        hours=3,
        ewam=([-0.5, math.nan, 1.0], [math.inf, -1.0, 4.0], [10.0, 10.0, 10.0]),
    )
    out = parse(payload)
    assert [(r.wave_height_m, r.wave_period_s) for r in out] == [
        (None, None),
        (None, None),
        (1.0, 4.0),
    ]


def test_parse_zero_kept() -> None:
    out = parse(make_marine_payload(1, start=T0, ewam=(0.0, 0.0, 0.0)))
    assert all((r.wave_height_m, r.wave_period_s, r.wave_dir_deg) == (0.0, 0.0, 0) for r in out)


def test_parse_direction_normalized() -> None:
    out = parse(make_marine_payload(1, start=T0, ewam=(1.0, 1.0, [360.0, 359.6, -1.0])))
    assert [r.wave_dir_deg for r in out] == [0, 0, 359]


@pytest.mark.parametrize("bad", ["1.2", True])
def test_parse_non_numeric_value(bad: Any) -> None:
    with pytest.raises(MarineParseError, match="non-numeric value in wave_height_ewam"):
        parse(make_marine_payload(1, start=T0, ewam=([1.0, bad, 1.0], 5.0, 250.0)))


@pytest.mark.parametrize(
    ("key", "unit"), [("wave_height_ewam", "ft"), ("wave_direction_ecmwf_wam", "deg")]
)
def test_parse_rejects_wrong_units(key: str, unit: str) -> None:
    with pytest.raises(MarineParseError, match=key):
        parse(make_marine_payload(1, start=T0, units={key: unit}))


def test_parse_missing_model_key() -> None:
    payload = make_marine_payload(1, start=T0)
    del payload["hourly"]["wave_period_ecmwf_wam"]
    with pytest.raises(MarineParseError, match="missing key wave_period_ecmwf_wam"):
        parse(payload)
    payload = make_marine_payload(1, start=T0)
    del payload["hourly_units"]["wave_period_ewam"]
    with pytest.raises(MarineParseError, match="missing key wave_period_ewam"):
        parse(payload)


def test_parse_length_mismatch() -> None:
    payload = make_marine_payload(1, start=T0)
    payload["hourly"]["wave_height_ewam"].append(1.0)
    with pytest.raises(MarineParseError, match="wave_height_ewam"):
        parse(payload)


@pytest.mark.parametrize("times", [[0, 3600, 10800], [0, 3600, 3600], [7200, 3600, 0]])
def test_parse_rejects_non_hourly_time(times: list[int]) -> None:
    payload = make_marine_payload(1, start=T0)
    payload["hourly"]["time"] = times
    with pytest.raises(MarineParseError, match="not hourly at index"):
        parse(payload)


def test_parse_requires_unixtime_utc() -> None:
    payload = make_marine_payload(1, start=T0)
    payload["hourly_units"]["time"] = "iso8601"
    with pytest.raises(MarineParseError, match="unixtime"):
        parse(payload)
    payload = make_marine_payload(1, start=T0)
    payload["utc_offset_seconds"] = 3600
    with pytest.raises(MarineParseError, match="utc_offset_seconds"):
        parse(payload)


def test_parse_error_object() -> None:
    with pytest.raises(MarineParseError, match="open-meteo returned an error: nope"):
        parse({"error": True, "reason": "nope"})
    payload = make_marine_payload(2, start=T0)
    payload[1] = {"error": True, "reason": "bad"}
    with pytest.raises(MarineParseError, match="location 1: open-meteo returned an error: bad"):
        parse(payload, 2)


def test_parse_location_count_mismatch() -> None:
    with pytest.raises(MarineParseError, match="expected 2 locations"):
        parse(make_marine_payload(1, start=T0), 2)
    with pytest.raises(MarineParseError, match="not an object or list"):
        parse("x")


def test_parse_location_id_mismatch() -> None:
    payload = make_marine_payload(2, start=T0)
    payload[1]["location_id"] = 5
    with pytest.raises(MarineParseError, match="location 1: location_id mismatch"):
        parse(payload, 2)


def test_parse_empty_time_is_valid() -> None:
    assert (
        parse(make_marine_payload(1, start=T0, hours=0, ewam=([], [], []), ecmwf=([], [], [])))
        == []
    )


def test_parse_does_not_mutate_payload() -> None:
    payload = make_marine_payload(2, start=T0)
    before = copy.deepcopy(payload)
    parse(payload, 2)
    assert payload == before


def test_fetch_error_hierarchy() -> None:
    assert issubclass(MarineParseError, MarineFetchError)


# -- fetch_marine -------------------------------------------------------------------------------


def test_fetch_marine_parses_mocked_response() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=make_marine_payload(2, start=T0))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    out = fetch_marine(http, loc(2), sleep=lambda s: None)
    assert len(out) == 6
    assert len(seen) == 1
    assert dict(seen[0].url.params) == build_marine_params(loc(2))
    assert seen[0].url.host == "marine-api.open-meteo.com"
    assert seen[0].url.path == "/v1/marine"


def test_fetch_marine_empty_locations_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_marine(http, []) == []


def test_fetch_marine_wraps_request_error() -> None:
    body = {"error": True, "reason": "bad request"}
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json=body)))
    with pytest.raises(MarineFetchError) as info:
        fetch_marine(http, loc(1), sleep=lambda s: None)
    assert str(info.value).startswith("open-meteo marine: HTTP 400")
    assert "http" not in str(info.value).split("open-meteo marine: ", 1)[1]
    assert not isinstance(info.value, MarineParseError)
