"""Tests for the Open-Meteo forecast parameter builder and parser (WP-03, AC-1 and AC-2).

Weather data by Open-Meteo.com (https://open-meteo.com/), licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/).

The fixture was recorded with CAPTURE_URL on CAPTURE_DATE; see tests/fixtures/openmeteo/README.md.
"""

import copy
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from openmeteo_payloads import make_forecast_payload
from shakka.domain.forecast import ForecastHour, ModelKey, SpotLocation
from shakka.openmeteo.forecast import (
    CELL_SELECTION,
    DEFAULT_FORECAST_DAYS,
    HOURLY_VARIABLES,
    ForecastFetchError,
    ForecastParseError,
    build_forecast_params,
    fetch_forecast,
    parse_forecast_response,
)
from shakka.openmeteo.models import OPEN_METEO_MODELS

CAPTURE_DATE = "2026-10-14"
CAPTURE_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700"
    "&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m"
    "&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless"
    "&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea"
)
FIXTURE = Path(__file__).parent / "fixtures" / "openmeteo" / "forecast_2loc_4models.json"
FIXTURE_LOCATIONS = [
    SpotLocation(spot_id="fixture-a", lat=52.47, lon=4.57),
    SpotLocation(spot_id="fixture-b", lat=52.10, lon=4.27),
]
T0 = datetime(2026, 10, 14, 0, tzinfo=UTC)
KNMI_ID = OPEN_METEO_MODELS[ModelKey.KNMI]
ICON_ID = OPEN_METEO_MODELS[ModelKey.ICON]


def loc(n: int = 1) -> list[SpotLocation]:
    return [SpotLocation(spot_id=f"s{i}", lat=52.0 + i / 100, lon=4.0) for i in range(n)]


def by_model(rows: list[ForecastHour], spot: str, model: ModelKey) -> list[ForecastHour]:
    return [r for r in rows if r.spot_id == spot and r.model == model]


@pytest.fixture(scope="module")
def raw() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parsed(raw: list[dict[str, Any]]) -> list[ForecastHour]:
    return parse_forecast_response(raw, FIXTURE_LOCATIONS)


# -- helpers that clean raw values like parser rule 5, but independently of the parser ----------


def expected_speed(x: float | None) -> float | None:
    if x is None or not math.isfinite(x) or x < 0:
        return None
    return float(x)


def expected_dir(x: float | None) -> int | None:
    if x is None or not math.isfinite(x):
        return None
    return int(round(x)) % 360


def expected_rows(
    raw: list[dict[str, Any]], loc_idx: int, model_id: str
) -> dict[int, tuple[float | None, float | None, int | None]]:
    """index -> (wind, gust, dir) for every hour that must produce a row."""
    hourly = raw[loc_idx]["hourly"]
    times = hourly["time"]
    speed = hourly[f"wind_speed_10m_{model_id}"]
    direction = hourly[f"wind_direction_10m_{model_id}"]
    gust = hourly[f"wind_gusts_10m_{model_id}"]
    n = len(times)
    out = {}
    for i in range(n):
        values = (
            expected_speed(speed[i]),
            expected_speed(gust[i + 1]) if i + 1 < n else None,
            expected_dir(direction[i]),
        )
        if any(v is not None for v in values):
            out[i] = values
    return out


# -- AC-1: fixture ---------------------------------------------------------------------------


def test_fixture_all_valid_at_utc(parsed: list[ForecastHour]) -> None:
    assert parsed
    for row in parsed:
        assert row.valid_at.utcoffset() == timedelta(0)
        assert row.valid_at.tzinfo is UTC


def test_fixture_values_match_raw_json(
    raw: list[dict[str, Any]], parsed: list[ForecastHour]
) -> None:
    total = 0
    for loc_idx, location in enumerate(FIXTURE_LOCATIONS):
        times = raw[loc_idx]["hourly"]["time"]
        for model, model_id in OPEN_METEO_MODELS.items():
            rows = {r.valid_at: r for r in by_model(parsed, location.spot_id, model)}
            expected = expected_rows(raw, loc_idx, model_id)
            assert len(rows) == len(expected)
            for i, (wind, gust, direction) in expected.items():
                row = rows[datetime.fromtimestamp(times[i], UTC)]
                assert (row.wind_kn, row.gust_kn, row.dir_deg) == (wind, gust, direction)
            total += len(expected)
    assert total == len(parsed)


@pytest.mark.parametrize("model", list(OPEN_METEO_MODELS))
def test_fixture_sample_per_model(
    raw: list[dict[str, Any]], parsed: list[ForecastHour], model: ModelKey
) -> None:
    model_id = OPEN_METEO_MODELS[model]
    hourly = raw[0]["hourly"]
    rows = {r.valid_at: r for r in by_model(parsed, "fixture-a", model)}
    for i in (0, 12, 24):
        for key in ("wind_speed_10m", "wind_direction_10m"):
            assert hourly[f"{key}_{model_id}"][i] is not None
        assert hourly[f"wind_gusts_10m_{model_id}"][i + 1] is not None
        row = rows[datetime.fromtimestamp(hourly["time"][i], UTC)]
        assert row.wind_kn == hourly[f"wind_speed_10m_{model_id}"][i]
        assert row.dir_deg == int(round(hourly[f"wind_direction_10m_{model_id}"][i])) % 360
        assert row.gust_kn == hourly[f"wind_gusts_10m_{model_id}"][i + 1]


@pytest.mark.parametrize("model", [ModelKey.ICON, ModelKey.ECMWF, ModelKey.GFS])
def test_fixture_last_hour_gust_is_none(
    raw: list[dict[str, Any]], parsed: list[ForecastHour], model: ModelKey
) -> None:
    model_id = OPEN_METEO_MODELS[model]
    for loc_idx, location in enumerate(FIXTURE_LOCATIONS):
        hourly = raw[loc_idx]["hourly"]
        last = hourly[f"wind_speed_10m_{model_id}"][-1]
        assert last is not None
        row = {r.valid_at: r for r in by_model(parsed, location.spot_id, model)}[
            datetime.fromtimestamp(hourly["time"][-1], UTC)
        ]
        assert row.gust_kn is None
        assert row.wind_kn == last


def test_fixture_no_all_none_rows(parsed: list[ForecastHour]) -> None:
    for row in parsed:
        assert not (row.wind_kn is None and row.gust_kn is None and row.dir_deg is None)


def test_fixture_knmi_horizon(raw: list[dict[str, Any]], parsed: list[ForecastHour]) -> None:
    for loc_idx, location in enumerate(FIXTURE_LOCATIONS):
        n = len(raw[loc_idx]["hourly"]["time"])
        for model, model_id in OPEN_METEO_MODELS.items():
            count = len(by_model(parsed, location.spot_id, model))
            assert count == len(expected_rows(raw, loc_idx, model_id))
            if model is ModelKey.KNMI:
                speeds = raw[loc_idx]["hourly"][f"wind_speed_10m_{model_id}"]
                assert any(v is None for v in speeds) and any(v is not None for v in speeds)
                assert 0 < count < n
            else:
                assert count > 0


def test_fixture_is_list_of_two_locations(raw: list[dict[str, Any]]) -> None:
    assert len(raw) == 2
    assert "location_id" not in raw[0]
    assert raw[1]["location_id"] == 1


# -- AC-2: parameters ------------------------------------------------------------------------


def test_build_params_exact() -> None:
    params = build_forecast_params(FIXTURE_LOCATIONS)
    assert params == {
        "latitude": "52.4700,52.1000",
        "longitude": "4.5700,4.2700",
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "models": "knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless",
        "wind_speed_unit": "kn",
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": "7",
        "cell_selection": "sea",
    }
    assert list(params) == [
        "latitude",
        "longitude",
        "hourly",
        "models",
        "wind_speed_unit",
        "timezone",
        "timeformat",
        "forecast_days",
        "cell_selection",
    ]
    assert DEFAULT_FORECAST_DAYS == 7 and CELL_SELECTION == "sea"
    assert HOURLY_VARIABLES == ("wind_speed_10m", "wind_direction_10m", "wind_gusts_10m")


@pytest.mark.parametrize(
    ("n", "days"), [(0, 7), (51, 7), (1, 0), (1, 17)], ids=["zero", "fifty-one", "day0", "day17"]
)
def test_build_params_validation(n: int, days: int) -> None:
    with pytest.raises(ValueError):
        build_forecast_params(loc(n), forecast_days=days)


def test_build_params_accepts_bounds() -> None:
    build_forecast_params(loc(50), forecast_days=16)
    build_forecast_params(loc(1), forecast_days=1)


def test_fixture_matches_current_params() -> None:
    expected = dict(httpx.URL(CAPTURE_URL).params)
    assert build_forecast_params(FIXTURE_LOCATIONS) == expected


def test_models_mapping() -> None:
    assert OPEN_METEO_MODELS == {
        ModelKey.KNMI: "knmi_harmonie_arome_netherlands",
        ModelKey.ICON: "dwd_icon_seamless",
        ModelKey.ECMWF: "ecmwf_ifs",
        ModelKey.GFS: "ncep_gfs_seamless",
    }
    assert len(OPEN_METEO_MODELS) >= 2


@pytest.mark.parametrize(
    ("key", "unit"),
    [
        (f"wind_speed_10m_{KNMI_ID}", "km/h"),
        (f"wind_gusts_10m_{ICON_ID}", "m/s"),
        (f"wind_direction_10m_{KNMI_ID}", "deg"),
    ],
)
def test_parse_rejects_non_knots(key: str, unit: str) -> None:
    payload = make_forecast_payload(1, start=T0, units={key: unit})
    with pytest.raises(ForecastParseError, match=key):
        parse_forecast_response(payload, loc(1))


# -- parser: structure ------------------------------------------------------------------------


def test_parse_single_location_object() -> None:
    payload = make_forecast_payload(1, start=T0)
    assert isinstance(payload, dict)
    rows = parse_forecast_response(payload, loc(1))
    assert len(rows) == 3 * len(OPEN_METEO_MODELS)


def test_parse_order_and_two_locations() -> None:
    rows = parse_forecast_response(make_forecast_payload(2, start=T0), loc(2))
    keys = [(r.spot_id, r.model) for r in rows]
    expected = [(f"s{i}", m) for i in range(2) for m in OPEN_METEO_MODELS for _ in range(3)]
    assert keys == expected
    assert [r.valid_at for r in rows[:3]] == [T0 + timedelta(hours=h) for h in range(3)]


def test_parse_location_count_mismatch() -> None:
    with pytest.raises(ForecastParseError):
        parse_forecast_response(make_forecast_payload(2, start=T0), loc(3))
    with pytest.raises(ForecastParseError):
        parse_forecast_response(make_forecast_payload(1, start=T0), loc(2))


def test_parse_location_id_mismatch() -> None:
    payload = make_forecast_payload(2, start=T0)
    payload[1]["location_id"] = 5
    with pytest.raises(ForecastParseError, match="location 1"):
        parse_forecast_response(payload, loc(2))


def test_parse_requires_unixtime_utc() -> None:
    payload = make_forecast_payload(1, start=T0)
    payload["hourly_units"]["time"] = "iso8601"
    with pytest.raises(ForecastParseError):
        parse_forecast_response(payload, loc(1))
    payload = make_forecast_payload(1, start=T0)
    payload["utc_offset_seconds"] = 7200
    with pytest.raises(ForecastParseError):
        parse_forecast_response(payload, loc(1))


def test_parse_rejects_non_hour_time() -> None:
    payload = make_forecast_payload(1, start=T0 + timedelta(minutes=30))
    with pytest.raises(ForecastParseError):
        parse_forecast_response(payload, loc(1))


@pytest.mark.parametrize("case", ["gap", "duplicate", "descending"])
def test_parse_rejects_non_hourly_time(case: str) -> None:
    payload = make_forecast_payload(1, start=T0)
    times = payload["hourly"]["time"]
    if case == "gap":
        times[2] += 3600
    elif case == "duplicate":
        times[1] = times[0]
    else:
        times.reverse()
    with pytest.raises(ForecastParseError, match="not hourly at index"):
        parse_forecast_response(payload, loc(1))


def test_parse_error_object() -> None:
    payload = {"error": True, "reason": "Cannot initialize model"}
    with pytest.raises(ForecastParseError, match="Cannot initialize model"):
        parse_forecast_response(payload, loc(1))


def test_parse_missing_model_key() -> None:
    payload = make_forecast_payload(1, start=T0)
    key = f"wind_gusts_10m_{ICON_ID}"
    del payload["hourly"][key]
    with pytest.raises(ForecastParseError, match=key):
        parse_forecast_response(payload, loc(1))


def test_parse_length_mismatch() -> None:
    payload = make_forecast_payload(1, start=T0)
    payload["hourly"][f"wind_speed_10m_{ICON_ID}"].pop()
    with pytest.raises(ForecastParseError, match=f"wind_speed_10m_{ICON_ID}"):
        parse_forecast_response(payload, loc(1))


def test_parse_not_a_response() -> None:
    with pytest.raises(ForecastParseError):
        parse_forecast_response("nope", loc(1))
    with pytest.raises(ForecastParseError):
        parse_forecast_response([1], loc(1))


# -- parser: values ----------------------------------------------------------------------------


def test_parse_partial_null_is_none() -> None:
    rows = parse_forecast_response(make_forecast_payload(1, start=T0, gust=None), loc(1))
    assert all(r.gust_kn is None for r in rows)
    assert all(r.wind_kn == 12.0 for r in rows)
    rows = parse_forecast_response(
        make_forecast_payload(1, start=T0, speed=[None, 12.0, 12.0]), loc(1)
    )
    first = [r for r in rows if r.valid_at == T0]
    assert first and all(r.wind_kn is None for r in first)


def test_parse_non_finite_is_none() -> None:
    payload = make_forecast_payload(
        1,
        start=T0,
        speed=[math.nan, math.inf, 5.0],
        direction=[-math.inf, 90.0, 90.0],
        gust=[1.0, math.nan, 9.0],
    )
    rows = by_model(parse_forecast_response(payload, loc(1)), "s0", ModelKey.ICON)
    assert [r.valid_at for r in rows] == [T0 + timedelta(hours=1), T0 + timedelta(hours=2)]
    assert (rows[0].wind_kn, rows[0].gust_kn, rows[0].dir_deg) == (None, 9.0, 90)
    assert (rows[1].wind_kn, rows[1].gust_kn, rows[1].dir_deg) == (5.0, None, 90)


def test_parse_negative_speed_is_none() -> None:
    payload = make_forecast_payload(1, start=T0, speed=[-1.0, 4.0, 4.0], gust=[0, -2.0, 7.0])
    rows = by_model(parse_forecast_response(payload, loc(1)), "s0", ModelKey.GFS)
    assert rows[0].wind_kn is None and rows[0].gust_kn is None
    assert rows[1].wind_kn == 4.0 and rows[1].gust_kn == 7.0


def test_parse_direction_normalized() -> None:
    payload = make_forecast_payload(1, start=T0, hours=4, direction=[360.0, 359.6, -1.0, 0.4])
    rows = by_model(parse_forecast_response(payload, loc(1)), "s0", ModelKey.ECMWF)
    assert [r.dir_deg for r in rows] == [0, 0, 359, 0]


@pytest.mark.parametrize("bad", ["12", True])
@pytest.mark.parametrize("field", ["speed", "gust", "direction"])
def test_parse_non_numeric_value(field: str, bad: object) -> None:
    kwargs: dict[str, Any] = {field: [12.0, bad, 12.0]}
    with pytest.raises(ForecastParseError):
        parse_forecast_response(make_forecast_payload(1, start=T0, **kwargs), loc(1))


def test_parse_non_numeric_first_gust() -> None:
    payload = make_forecast_payload(1, start=T0, gust=["x", 18.0, 18.0])
    with pytest.raises(ForecastParseError):
        parse_forecast_response(payload, loc(1))


# -- parser: gust shift (A14) ----------------------------------------------------------------


def test_parse_gust_shifted_one_hour() -> None:
    payload = make_forecast_payload(
        1,
        start=T0,
        speed=[10.0, 11.0, 12.0],
        gust=[10.0, 20.0, 30.0],
        direction=[180.0, 190.0, 200.0],
    )
    rows = parse_forecast_response(payload, loc(1))
    for model in OPEN_METEO_MODELS:
        got = [(r.valid_at, r.wind_kn, r.gust_kn, r.dir_deg) for r in by_model(rows, "s0", model)]
        assert got == [
            (T0, 10.0, 20.0, 180),
            (T0 + timedelta(hours=1), 11.0, 30.0, 190),
            (T0 + timedelta(hours=2), 12.0, None, 200),
        ]


def test_parse_last_hour_gust_is_none() -> None:
    rows = parse_forecast_response(make_forecast_payload(1, start=T0), loc(1))
    for model in OPEN_METEO_MODELS:
        gusts = [r.gust_kn for r in by_model(rows, "s0", model)]
        assert gusts == [18.0, 18.0, None]


def test_parse_gust_only_row_kept() -> None:
    payload = make_forecast_payload(
        1,
        start=T0,
        speed=[None, 12.0, 12.0],
        direction=[None, 270.0, 270.0],
        gust=[None, 25.0, 18.0],
    )
    rows = by_model(parse_forecast_response(payload, loc(1)), "s0", ModelKey.KNMI)
    first = next(r for r in rows if r.valid_at == T0)
    assert (first.wind_kn, first.gust_kn, first.dir_deg) == (None, 25.0, None)


def test_parse_all_none_after_shift_dropped() -> None:
    payload = make_forecast_payload(
        1,
        start=T0,
        speed=[12.0, None, None],
        direction=[270.0, None, None],
        gust=[18.0, 25.0, None],
    )
    rows = by_model(parse_forecast_response(payload, loc(1)), "s0", ModelKey.KNMI)
    assert [(r.valid_at, r.gust_kn) for r in rows] == [(T0, 25.0)]


def test_parse_single_hour() -> None:
    rows = parse_forecast_response(make_forecast_payload(1, start=T0, hours=1), loc(1))
    assert len(rows) == len(OPEN_METEO_MODELS)
    assert all(r.gust_kn is None for r in rows)


def test_parse_empty_time_gives_no_rows() -> None:
    rows = parse_forecast_response(make_forecast_payload(1, start=T0, hours=0), loc(1))
    assert rows == []


def test_parse_does_not_mutate_payload() -> None:
    payload = make_forecast_payload(2, start=T0)
    before = copy.deepcopy(payload)
    parse_forecast_response(payload, loc(2))
    assert payload == before


def test_fetch_error_hierarchy() -> None:
    assert issubclass(ForecastParseError, ForecastFetchError)


# -- fetch_forecast ----------------------------------------------------------------------------


def test_fetch_forecast_parses_mocked_response() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=make_forecast_payload(2, start=T0))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    rows = fetch_forecast(http, loc(2), sleep=lambda s: None)
    assert len(rows) == 2 * len(OPEN_METEO_MODELS) * 3
    assert len(seen) == 1
    assert dict(seen[0].url.params) == build_forecast_params(loc(2))
    assert seen[0].url.host == "api.open-meteo.com"


def test_fetch_forecast_empty_locations_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_forecast(http, []) == []


def test_fetch_forecast_wraps_request_errors() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(ForecastFetchError) as info:
        fetch_forecast(http, loc(1), sleep=lambda s: None)
    assert str(info.value) == "open-meteo forecast: failed after 3 attempts: HTTP 500"
    assert not isinstance(info.value, ForecastParseError)


def test_fetch_forecast_parse_error_propagates() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ForecastParseError):
        fetch_forecast(http, loc(1), sleep=lambda s: None)
