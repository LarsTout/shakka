"""Open-Meteo forecast API: request parameters, response parser and fetch."""

import math
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx
from pydantic import ValidationError

from shakka.domain.forecast import ForecastHour, SpotLocation
from shakka.openmeteo.client import OpenMeteoRequestError, request_json
from shakka.openmeteo.models import OPEN_METEO_MODELS

FORECAST_URL: Final = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARIABLES: Final = ("wind_speed_10m", "wind_direction_10m", "wind_gusts_10m")
DEFAULT_FORECAST_DAYS: Final = 8
MAX_LOCATIONS_PER_REQUEST: Final = 50
CELL_SELECTION: Final = "sea"  # A2, choice for Lars
SPEED_UNIT: Final = "kn"
DIRECTION_UNIT: Final = "°"

_SPEED, _DIRECTION, _GUST = HOURLY_VARIABLES
_UNITS: Final = {_SPEED: SPEED_UNIT, _DIRECTION: DIRECTION_UNIT, _GUST: SPEED_UNIT}
_MAX_FORECAST_DAYS: Final = 16


class ForecastFetchError(Exception):
    """The forecast could not be fetched or understood."""


class ForecastParseError(ForecastFetchError):
    """The response does not have the expected structure."""


def build_forecast_params(
    locations: Sequence[SpotLocation], *, forecast_days: int = DEFAULT_FORECAST_DAYS
) -> dict[str, str]:
    """ValueError if locations is empty or longer than MAX_LOCATIONS_PER_REQUEST,
    or forecast_days is not in 1..16."""
    if not 1 <= len(locations) <= MAX_LOCATIONS_PER_REQUEST:
        raise ValueError(f"locations must contain 1..{MAX_LOCATIONS_PER_REQUEST} items")
    if not 1 <= forecast_days <= _MAX_FORECAST_DAYS:
        raise ValueError(f"forecast_days must be in 1..{_MAX_FORECAST_DAYS}")
    return {
        "latitude": ",".join(f"{loc.lat:.4f}" for loc in locations),
        "longitude": ",".join(f"{loc.lon:.4f}" for loc in locations),
        "hourly": ",".join(HOURLY_VARIABLES),
        "models": ",".join(OPEN_METEO_MODELS.values()),
        "wind_speed_unit": SPEED_UNIT,
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": str(forecast_days),
        "cell_selection": CELL_SELECTION,
    }


def _clean_value(value: Any, *, where: str, variable: str) -> float | int | None:
    """Parser rule 5: structure errors raise, odd values become None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ForecastParseError(f"{where}: non-numeric value in {variable}")
    number = float(value)
    if not math.isfinite(number):
        return None
    if variable == _DIRECTION:
        return int(round(number)) % 360
    if number < 0:
        return None
    return number


def _series(
    element: dict[str, Any], key: str, variable: str, n: int, where: str
) -> list[float | int | None]:
    units = element["hourly_units"]
    hourly = element["hourly"]
    if key not in units or key not in hourly:
        raise ForecastParseError(f"{where}: missing key {key}")
    if units[key] != _UNITS[variable]:
        raise ForecastParseError(
            f"{where}: unit for {key} is {units[key]!r}, expected {_UNITS[variable]!r}"
        )
    values = hourly[key]
    if not isinstance(values, list) or len(values) != n:
        raise ForecastParseError(f"{where}: {key} does not have {n} values")
    return [_clean_value(v, where=f"{where} {key}", variable=variable) for v in values]


def parse_forecast_response(payload: Any, locations: Sequence[SpotLocation]) -> list[ForecastHour]:
    """Pure. Order: per location (input order), per model (OPEN_METEO_MODELS order), per time.

    Gust semantics: Open-Meteo's wind_gusts_10m at timestamp T is the max over [T - 1h, T)
    ("Preceding hour max"); wind speed and direction are instantaneous at T. To follow the
    project convention (hourly values belong to [valid_at, valid_at + 1h)), the row for
    valid_at = T takes speed and direction from T and the gust from T + 1h. The last
    timestamp gets gust_kn = None. Requires `time` to step by exactly 3600 s.

    Raises ForecastParseError on any structural problem."""
    if isinstance(payload, dict):
        if payload.get("error") is True:
            reason = str(payload.get("reason", ""))[:200]
            raise ForecastParseError(f"open-meteo returned an error: {reason}")
        payload = [payload]
    if not isinstance(payload, list):
        raise ForecastParseError("response is not an object or list")
    if len(payload) != len(locations):
        raise ForecastParseError(
            f"expected {len(locations)} locations in response, got {len(payload)}"
        )

    result: list[ForecastHour] = []
    for index, (element, location) in enumerate(zip(payload, locations, strict=True)):
        where = f"location {index}"
        if not isinstance(element, dict):
            raise ForecastParseError(f"{where}: not an object")
        if element.get("error") is True:
            reason = str(element.get("reason", ""))[:200]
            raise ForecastParseError(f"{where}: open-meteo returned an error: {reason}")
        if "location_id" in element and element["location_id"] != index:
            raise ForecastParseError(f"{where}: location_id mismatch")
        if element.get("utc_offset_seconds") != 0:
            raise ForecastParseError(f"{where}: utc_offset_seconds is not 0")
        if not isinstance(element.get("hourly_units"), dict) or not isinstance(
            element.get("hourly"), dict
        ):
            raise ForecastParseError(f"{where}: hourly or hourly_units missing")
        if element["hourly_units"].get("time") != "unixtime":
            raise ForecastParseError(f"{where}: hourly_units.time is not 'unixtime'")
        times = element["hourly"].get("time")
        if not isinstance(times, list) or any(
            isinstance(t, bool) or not isinstance(t, int) for t in times
        ):
            raise ForecastParseError(f"{where}: time is not a list of integers")
        for k in range(1, len(times)):
            if times[k] - times[k - 1] != 3600:
                raise ForecastParseError(f"{where}: time is not hourly at index {k}")
        n = len(times)

        for model, model_id in OPEN_METEO_MODELS.items():
            mwhere = f"{where} model {model.value}"
            speed = _series(element, f"{_SPEED}_{model_id}", _SPEED, n, mwhere)
            direction = _series(element, f"{_DIRECTION}_{model_id}", _DIRECTION, n, mwhere)
            gust = _series(element, f"{_GUST}_{model_id}", _GUST, n, mwhere)
            for i in range(n):
                wind = speed[i]
                dir_deg = direction[i]
                gust_kn = gust[i + 1] if i + 1 < n else None
                if wind is None and gust_kn is None and dir_deg is None:
                    continue
                try:
                    result.append(
                        ForecastHour(
                            spot_id=location.spot_id,
                            model=model,
                            valid_at=datetime.fromtimestamp(times[i], tz=UTC),
                            wind_kn=wind,
                            gust_kn=gust_kn,
                            dir_deg=dir_deg,
                        )
                    )
                except (ValidationError, OverflowError, OSError, ValueError) as exc:
                    raise ForecastParseError(f"{mwhere}: invalid hour at index {i}") from exc
    return result


def fetch_forecast(
    http: httpx.Client,
    locations: Sequence[SpotLocation],
    *,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ForecastHour]:
    """[] without a request for empty locations. OpenMeteoRequestError -> ForecastFetchError
    (same message, prefixed "open-meteo forecast: "). ForecastParseError propagates."""
    if not locations:
        return []
    params = build_forecast_params(locations, forecast_days=forecast_days)
    try:
        payload = request_json(http, FORECAST_URL, params, sleep=sleep)
    except OpenMeteoRequestError as exc:
        raise ForecastFetchError(f"open-meteo forecast: {exc}") from None
    return parse_forecast_response(payload, locations)
