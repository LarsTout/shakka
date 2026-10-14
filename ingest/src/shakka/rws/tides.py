"""Rijkswaterstaat DDAPI20: astronomical tide extremes and the station catalogue.

The only place in ingest/src that knows the Rijkswaterstaat hosts.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from shakka.domain.tide import TideKind

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
