"""Rijkswaterstaat DDAPI20: astronomical tide extremes and the station catalogue.

The only place in ingest/src that knows the Rijkswaterstaat hosts.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

import httpx

from shakka.domain.tide import MAX_ABS_LEVEL_CM, TideExtreme, TideKind
from shakka.http import TransientError, make_client, with_retries

RWS_BASE_URL: Final = "https://ddapi20-waterwebservices.rijkswaterstaat.nl"
OBSERVATIONS_URL: Final = f"{RWS_BASE_URL}/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
CATALOGUE_URL: Final = f"{RWS_BASE_URL}/METADATASERVICES/OphalenCatalogus"

PROCES_TYPE: Final = "astronomisch"
GROEPERING: Final = "GETETBRKD2"
GROOTHEID: Final = "WATHTE"
HOEDANIGHEID: Final = "NAP"
EENHEID: Final = "cm"
TYPERING_EXTREME_TYPE: Final = "GETETTPE"
INVALID_QUALITY_CODE: Final = "99"
EXTREME_TYPE_KIND: Final[Mapping[str, TideKind | None]] = {
    "hoogwater": "high",
    "laagwater": "low",
    "laagwater 1": "low",
    "laagwater 2": "low",
    "topagger": None,  # None = valid type, not stored
}
OBSERVATIONS_TIMEOUT_S: Final = 30.0
CATALOGUE_TIMEOUT_S: Final = 60.0
MAX_ERROR_TEXT: Final = 200
RWS_ATTEMPTS: Final = 3
RWS_BACKOFF_S: Final = 1.0
STATION_CODE_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class TideFetchError(Exception):
    """A failed or unusable Rijkswaterstaat response."""


@dataclass(frozen=True, slots=True)
class StationInfo:
    code: str
    name: str
    lat: float
    lon: float


def format_rws_time(value: datetime) -> str:
    """Aware -> UTC 'YYYY-MM-DDTHH:MM:SS.mmm+00:00'. Naive -> ValueError."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def build_extremes_request(station: str, start: datetime, end: datetime) -> dict[str, Any]:
    """Request body for OphalenWaarnemingen (astronomical extremes with type)."""
    begin = format_rws_time(start)
    finish = format_rws_time(end)
    if start >= end:
        raise ValueError("start must be before end")
    return {
        "Locatie": {"Code": station},
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {"ProcesType": PROCES_TYPE, "Groepering": {"Code": GROEPERING}}
        },
        "Periode": {"Begindatumtijd": begin, "Einddatumtijd": finish},
    }


def build_catalogue_request() -> dict[str, Any]:
    """Request body for OphalenCatalogus."""
    return {
        "CatalogusFilter": {
            "Compartimenten": True,
            "Eenheden": True,
            "Grootheden": True,
            "Groeperingen": True,
            "Hoedanigheden": True,
            "ProcesTypes": True,
            "Typeringen": True,
        }
    }


def _code(obj: Any, key: str) -> str:
    """obj[key]["Code"] as a string, or "" when absent or not shaped like that."""
    if not isinstance(obj, dict):
        return ""
    inner = obj.get(key)
    if not isinstance(inner, dict):
        return ""
    value = inner.get("Code", "")
    return value if isinstance(value, str) else ""


def _unexpected(label: str) -> TideFetchError:
    return TideFetchError(f"{label}: unexpected response")


def _parse_time(raw: Any, station: str) -> datetime:
    if not isinstance(raw, str):
        raise _unexpected(station)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise TideFetchError(f"{station}: invalid timestamp {raw[:40]!r}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TideFetchError(f"{station}: timestamp without offset {raw[:40]!r}")
    return parsed.astimezone(UTC)


def _quality(measurement: Mapping[str, Any]) -> Any:
    meta = measurement.get("WaarnemingMetadata")
    return meta.get("Kwaliteitswaardecode") if isinstance(meta, dict) else None


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def parse_extremes_response(payload: Any, station: str) -> list[TideExtreme]:
    """Merge the NAP level channel and the extreme type channel into TideExtreme objects."""
    try:
        return _parse_extremes(payload, station)
    except (KeyError, TypeError, AttributeError):
        raise _unexpected(station) from None


def _parse_extremes(payload: Any, station: str) -> list[TideExtreme]:
    if not isinstance(payload, dict):
        raise _unexpected(station)
    if payload.get("Succesvol") is False:
        text = str(payload.get("Foutmelding"))[:MAX_ERROR_TEXT]
        raise TideFetchError(f"{station}: RWS error: {text}")
    observations = payload.get("WaarnemingenLijst")
    if not isinstance(observations, list):
        raise _unexpected(station)

    level_channels: list[list[Any]] = []
    type_channels: list[list[Any]] = []
    for w in observations:
        meta = w.get("AquoMetadata") or {}
        proces = meta.get("ProcesType")
        if proces and proces != PROCES_TYPE:
            continue
        groepering = _code(meta, "Groepering")
        if groepering and groepering != GROEPERING:
            continue
        metingen = w.get("MetingenLijst")
        if _code(meta, "Typering") == TYPERING_EXTREME_TYPE:
            if not isinstance(metingen, list):
                raise _unexpected(station)
            type_channels.append(metingen)
        elif _code(meta, "Grootheid") == GROOTHEID and _code(meta, "Hoedanigheid") == HOEDANIGHEID:
            if _code(meta, "Eenheid") != EENHEID:
                raise TideFetchError(f"{station}: unexpected unit {_code(meta, 'Eenheid')[:20]!r}")
            if not isinstance(metingen, list):
                raise _unexpected(station)
            level_channels.append(metingen)
    if not level_channels:
        raise TideFetchError(f"{station}: no NAP water level channel")
    if not type_channels:
        raise TideFetchError(f"{station}: no extreme type channel")

    levels: dict[datetime, int] = {}
    for channel in level_channels:
        for m in channel:
            t = _parse_time(m["Tijdstip"], station)
            if _quality(m) == INVALID_QUALITY_CODE:
                continue
            value = _numeric(m["Meetwaarde"].get("Waarde_Numeriek"))
            if value is None or abs(value) > MAX_ABS_LEVEL_CM:
                continue
            level = math.floor(value + 0.5)
            if levels.setdefault(t, level) != level:
                raise TideFetchError(f"{station}: conflicting levels at {t.isoformat()}")

    types: dict[datetime, TideKind | None] = {}
    for channel in type_channels:
        for m in channel:
            t = _parse_time(m["Tijdstip"], station)
            if _quality(m) == INVALID_QUALITY_CODE:
                continue
            raw = m["Meetwaarde"].get("Waarde_Alfanumeriek")
            text = str(raw or "").strip().lower()
            if text not in EXTREME_TYPE_KIND:
                raise TideFetchError(f"{station}: unknown extreme type {text[:40]!r}")
            kind = EXTREME_TYPE_KIND[text]
            if t in types and types[t] != kind:
                raise TideFetchError(f"{station}: conflicting extreme types at {t.isoformat()}")
            types[t] = kind

    result: list[TideExtreme] = []
    for t in sorted(levels):
        if t not in types:
            raise TideFetchError(f"{station}: missing extreme type at {t.isoformat()}")
        kind = types[t]
        if kind is None:
            continue
        result.append(TideExtreme(station=station, at=t, kind=kind, level_cm=levels[t]))
    if not result:
        raise TideFetchError(f"{station}: no extremes")
    return result


def parse_stations(payload: Any) -> list[StationInfo]:
    """Stations in the catalogue with astronomical high/low water (NAP), sorted on code."""
    try:
        return _parse_stations(payload)
    except (KeyError, TypeError, AttributeError):
        raise _unexpected("catalogue") from None


def _parse_stations(payload: Any) -> list[StationInfo]:
    if not isinstance(payload, dict):
        raise _unexpected("catalogue")
    if payload.get("Succesvol") is False:
        text = str(payload.get("Foutmelding"))[:MAX_ERROR_TEXT]
        raise TideFetchError(f"catalogue: RWS error: {text}")
    metadata = payload.get("AquoMetadataLijst")
    locations = payload.get("LocatieLijst")
    links = payload.get("AquoMetadataLocatieLijst")
    if not (isinstance(metadata, list) and isinstance(locations, list) and isinstance(links, list)):
        raise _unexpected("catalogue")

    ids = {
        item.get("AquoMetadata_MessageID")
        for item in metadata
        if item.get("ProcesType") == PROCES_TYPE
        and _code(item, "Grootheid") == GROOTHEID
        and _code(item, "Groepering") == GROEPERING
        and _code(item, "Hoedanigheid") == HOEDANIGHEID
    }
    ids.discard(None)
    loc_ids = {
        link.get("Locatie_MessageID")
        for link in links
        if link.get("AquoMetaData_MessageID", link.get("AquoMetadata_MessageID")) in ids
    }
    found: dict[str, StationInfo] = {}
    for loc in locations:
        if loc.get("Locatie_MessageID") not in loc_ids:
            continue
        code = str(loc.get("Code") or "")
        if not code or code in found:
            continue
        lat, lon = _coordinate(loc.get("Lat")), _coordinate(loc.get("Lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        found[code] = StationInfo(code=code, name=str(loc.get("Naam") or ""), lat=lat, lon=lon)
    if not found:
        raise TideFetchError("catalogue: no stations with astronomical extremes")
    return sorted(found.values(), key=lambda s: s.code)


def _coordinate(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _post_json(client: httpx.Client, url: str, body: dict[str, Any], *, label: str) -> Any:
    """POST (idempotent) with retries on transport errors, 429 and 5xx. Nothing is logged."""

    def attempt() -> Any:
        try:
            response = client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise TransientError(f"{label}: {type(exc).__name__}") from None
        status = response.status_code
        if status == 204:
            raise TideFetchError(f"{label}: no data (HTTP 204)")
        if not 200 <= status < 300:
            text = f"{label}: HTTP {status}"
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and data.get("Foutmelding") is not None:
                text += f": {str(data['Foutmelding'])[:MAX_ERROR_TEXT]}"
            if status == 429 or status >= 500:
                raise TransientError(text)
            raise TideFetchError(text)
        try:
            return response.json()
        except ValueError:
            raise TideFetchError(f"{label}: invalid JSON") from None

    try:
        return with_retries(
            attempt,
            attempts=RWS_ATTEMPTS,
            backoff=RWS_BACKOFF_S,
            retry_if=lambda e: isinstance(e, TransientError),
        )
    except TransientError as exc:
        raise TideFetchError(f"{exc} (after {RWS_ATTEMPTS} attempts)") from None


def fetch_tide_extremes(
    station: str, start: datetime, end: datetime, *, http: httpx.Client | None = None
) -> list[TideExtreme]:
    """Fetch and parse the astronomical extremes of one station for [start, end]."""
    if not STATION_CODE_RE.fullmatch(station):
        raise TideFetchError(f"invalid station code {station!r}"[:70])
    body = build_extremes_request(station, start, end)  # ValueError on naive or start >= end
    if http is None:
        with make_client(timeout=OBSERVATIONS_TIMEOUT_S) as client:
            payload = _post_json(client, OBSERVATIONS_URL, body, label=station)
    else:
        payload = _post_json(http, OBSERVATIONS_URL, body, label=station)
    return parse_extremes_response(payload, station)


def list_tide_stations(*, http: httpx.Client | None = None) -> list[StationInfo]:
    """All stations with astronomical high/low water, from the RWS catalogue."""
    body = build_catalogue_request()
    if http is None:
        with make_client(timeout=CATALOGUE_TIMEOUT_S) as client:
            payload = _post_json(client, CATALOGUE_URL, body, label="catalogue")
    else:
        payload = _post_json(http, CATALOGUE_URL, body, label="catalogue")
    return parse_stations(payload)
