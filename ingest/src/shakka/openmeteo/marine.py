"""Open-Meteo Marine API (waves): request parameters, response parser and fetch (WP-12).

Display only: wave data never feeds evaluations or alerts.
"""

import math
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Final

import httpx
from pydantic import ValidationError

from shakka.domain.forecast import SpotLocation
from shakka.domain.marine import MarineHour
from shakka.openmeteo.client import OpenMeteoRequestError, request_json

MARINE_URL: Final = "https://marine-api.open-meteo.com/v1/marine"
MARINE_VARIABLES: Final = ("wave_height", "wave_period", "wave_direction")
MARINE_MODELS: Final = ("ewam", "ecmwf_wam")  # priority order per hour (A1, A7), choice for Lars
DEFAULT_MARINE_DAYS: Final = 7
MAX_MARINE_DAYS: Final = 8
MAX_LOCATIONS_PER_REQUEST: Final = 50
CELL_SELECTION: Final = "sea"
HEIGHT_UNIT: Final = "m"
PERIOD_UNIT: Final = "s"
DIRECTION_UNIT: Final = "°"

_HEIGHT, _PERIOD, _DIRECTION = MARINE_VARIABLES
_UNITS: Final = {_HEIGHT: HEIGHT_UNIT, _PERIOD: PERIOD_UNIT, _DIRECTION: DIRECTION_UNIT}


class MarineFetchError(Exception):
    """The wave forecast could not be fetched or understood."""


class MarineParseError(MarineFetchError):
    """The response does not have the expected structure."""


def build_marine_params(
    locations: Sequence[SpotLocation], *, forecast_days: int = DEFAULT_MARINE_DAYS
) -> dict[str, str]:
    """ValueError if locations is empty or longer than MAX_LOCATIONS_PER_REQUEST,
    or forecast_days is not in 1..MAX_MARINE_DAYS."""
    if not 1 <= len(locations) <= MAX_LOCATIONS_PER_REQUEST:
        raise ValueError(f"locations must contain 1..{MAX_LOCATIONS_PER_REQUEST} items")
    if not 1 <= forecast_days <= MAX_MARINE_DAYS:
        raise ValueError(f"forecast_days must be in 1..{MAX_MARINE_DAYS}")
    return {
        "latitude": ",".join(f"{loc.lat:.4f}" for loc in locations),
        "longitude": ",".join(f"{loc.lon:.4f}" for loc in locations),
        "hourly": ",".join(MARINE_VARIABLES),
        "models": ",".join(MARINE_MODELS),
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": str(forecast_days),
        "cell_selection": CELL_SELECTION,
    }


def _clean_value(value: Any, *, where: str, variable: str) -> float | int | None:
    """Structure errors raise, odd values become None (A8)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MarineParseError(f"{where}: non-numeric value in {variable}")
    number = float(value)
    if not math.isfinite(number):
        return None
    if variable.startswith(_DIRECTION):
        return int(round(number)) % 360
    if number < 0:
        return None
    return number


def _series(
    element: dict[str, Any], variable: str, model: str, n: int, where: str
) -> list[float | int | None]:
    key = f"{variable}_{model}"
    units = element["hourly_units"]
    hourly = element["hourly"]
    if key not in units or key not in hourly:
        raise MarineParseError(f"{where}: missing key {key}")
    if units[key] != _UNITS[variable]:
        raise MarineParseError(
            f"{where}: unit for {key} is {units[key]!r}, expected {_UNITS[variable]!r}"
        )
    values = hourly[key]
    if not isinstance(values, list) or len(values) != n:
        raise MarineParseError(f"{where}: {key} does not have {n} values")
    return [_clean_value(v, where=where, variable=key) for v in values]


def parse_marine_response(payload: Any, locations: Sequence[SpotLocation]) -> list[MarineHour]:
    """Pure. Order: per location (input order), per time. Per hour the first model in
    MARINE_MODELS whose (height, period, direction) is not all None supplies the whole row;
    values of different models are never mixed. Hours without any value give no row.
    Raises MarineParseError on any structural problem."""
    if isinstance(payload, dict):
        if payload.get("error") is True:
            reason = str(payload.get("reason", ""))[:200]
            raise MarineParseError(f"open-meteo returned an error: {reason}")
        payload = [payload]
    if not isinstance(payload, list):
        raise MarineParseError("response is not an object or list")
    if len(payload) != len(locations):
        raise MarineParseError(
            f"expected {len(locations)} locations in response, got {len(payload)}"
        )

    result: list[MarineHour] = []
    for index, (element, location) in enumerate(zip(payload, locations, strict=True)):
        where = f"location {index}"
        if not isinstance(element, dict):
            raise MarineParseError(f"{where}: not an object")
        if element.get("error") is True:
            reason = str(element.get("reason", ""))[:200]
            raise MarineParseError(f"{where}: open-meteo returned an error: {reason}")
        if "location_id" in element and element["location_id"] != index:
            raise MarineParseError(f"{where}: location_id mismatch")
        if element.get("utc_offset_seconds") != 0:
            raise MarineParseError(f"{where}: utc_offset_seconds is not 0")
        if not isinstance(element.get("hourly_units"), dict) or not isinstance(
            element.get("hourly"), dict
        ):
            raise MarineParseError(f"{where}: hourly or hourly_units missing")
        if element["hourly_units"].get("time") != "unixtime":
            raise MarineParseError(f"{where}: hourly_units.time is not 'unixtime'")
        times = element["hourly"].get("time")
        if not isinstance(times, list) or any(
            isinstance(t, bool) or not isinstance(t, int) for t in times
        ):
            raise MarineParseError(f"{where}: time is not a list of integers")
        for k in range(1, len(times)):
            if times[k] - times[k - 1] != 3600:
                raise MarineParseError(f"{where}: time is not hourly at index {k}")
        n = len(times)

        triples: list[tuple[list[Any], list[Any], list[Any]]] = []
        for model in MARINE_MODELS:
            mwhere = f"{where} model {model}"
            triples.append(
                (
                    _series(element, _HEIGHT, model, n, mwhere),
                    _series(element, _PERIOD, model, n, mwhere),
                    _series(element, _DIRECTION, model, n, mwhere),
                )
            )
        for i in range(n):
            for height, period, direction in triples:
                h, p, d = height[i], period[i], direction[i]
                if h is None and p is None and d is None:
                    continue
                try:
                    result.append(
                        MarineHour(
                            spot_id=location.spot_id,
                            valid_at=datetime.fromtimestamp(times[i], tz=UTC),
                            wave_height_m=h,
                            wave_period_s=p,
                            wave_dir_deg=d,
                        )
                    )
                except (ValidationError, OverflowError, OSError, ValueError) as exc:
                    raise MarineParseError(f"{where}: invalid hour at index {i}") from exc
                break
    return result


def fetch_marine(
    http: httpx.Client,
    locations: Sequence[SpotLocation],
    *,
    forecast_days: int = DEFAULT_MARINE_DAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> list[MarineHour]:
    """[] without a request for empty locations. OpenMeteoRequestError -> MarineFetchError
    (same message, prefixed "open-meteo marine: "). MarineParseError propagates."""
    if not locations:
        return []
    params = build_marine_params(locations, forecast_days=forecast_days)
    try:
        payload = request_json(http, MARINE_URL, params, sleep=sleep)
    except OpenMeteoRequestError as exc:
        raise MarineFetchError(f"open-meteo marine: {exc}") from None
    return parse_marine_response(payload, locations)
