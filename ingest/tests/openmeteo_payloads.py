"""Synthetic Open-Meteo forecast responses for tests."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from shakka.openmeteo.forecast import DIRECTION_UNIT, HOURLY_VARIABLES, SPEED_UNIT
from shakka.openmeteo.models import OPEN_METEO_MODELS

Value = float | str | bool | None  # str/bool only to provoke parse errors

_UNITS = {
    "wind_speed_10m": SPEED_UNIT,
    "wind_direction_10m": DIRECTION_UNIT,
    "wind_gusts_10m": SPEED_UNIT,
}


def _expand(value: Value | Sequence[Value], hours: int) -> list[Value]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        assert len(value) == hours, "sequence must have one value per hour"
        return list(value)
    return [value] * hours


def make_forecast_payload(
    n_locations: int,
    *,
    start: datetime,
    hours: int = 3,
    speed: Value | Sequence[Value] = 12.0,
    gust: Value | Sequence[Value] = 18.0,
    direction: Value | Sequence[Value] = 270.0,
    units: Mapping[str, str] | None = None,
) -> Any:
    """All models of OPEN_METEO_MODELS; object for one location, list otherwise."""
    start_ts = int(start.timestamp())
    values = {
        "wind_speed_10m": _expand(speed, hours),
        "wind_direction_10m": _expand(direction, hours),
        "wind_gusts_10m": _expand(gust, hours),
    }
    elements: list[dict[str, Any]] = []
    for index in range(n_locations):
        hourly_units: dict[str, str] = {"time": "unixtime"}
        hourly: dict[str, Any] = {"time": [start_ts + k * 3600 for k in range(hours)]}
        for model_id in OPEN_METEO_MODELS.values():
            for variable in HOURLY_VARIABLES:
                key = f"{variable}_{model_id}"
                hourly_units[key] = _UNITS[variable]
                hourly[key] = list(values[variable])
        hourly_units.update(units or {})
        element: dict[str, Any] = {
            "latitude": 52.0,
            "longitude": 4.0,
            "utc_offset_seconds": 0,
            "timezone": "GMT",
            "hourly_units": hourly_units,
            "hourly": hourly,
        }
        if index >= 1:
            element["location_id"] = index
        elements.append(element)
    return elements[0] if n_locations == 1 else elements


# -- Marine ----------------------------------------------------------------------------------

Triple = tuple[
    Value | Sequence[Value], Value | Sequence[Value], Value | Sequence[Value]
]  # height, period, direction

_MARINE_UNITS = {"wave_height": "m", "wave_period": "s", "wave_direction": "°"}


def make_marine_payload(
    n_locations: int,
    *,
    start: datetime,
    hours: int = 3,
    ewam: Triple = (1.2, 5.0, 250.0),
    ecmwf: Triple = (1.4, 6.0, 260.0),
    units: Mapping[str, str] | None = None,
) -> Any:
    """Both models of MARINE_MODELS; object for one location, list otherwise."""
    from shakka.openmeteo.marine import MARINE_MODELS, MARINE_VARIABLES

    start_ts = int(start.timestamp())
    by_model = dict(zip(MARINE_MODELS, (ewam, ecmwf), strict=True))
    elements: list[dict[str, Any]] = []
    for index in range(n_locations):
        hourly_units: dict[str, str] = {"time": "unixtime"}
        hourly: dict[str, Any] = {"time": [start_ts + k * 3600 for k in range(hours)]}
        for model_id, triple in by_model.items():
            for variable, value in zip(MARINE_VARIABLES, triple, strict=True):
                key = f"{variable}_{model_id}"
                hourly_units[key] = _MARINE_UNITS[variable]
                hourly[key] = _expand(value, hours)
        hourly_units.update(units or {})
        element: dict[str, Any] = {
            "latitude": 52.0,
            "longitude": 4.0,
            "utc_offset_seconds": 0,
            "timezone": "GMT",
            "hourly_units": hourly_units,
            "hourly": hourly,
        }
        if index >= 1:
            element["location_id"] = index
        elements.append(element)
    return elements[0] if n_locations == 1 else elements
