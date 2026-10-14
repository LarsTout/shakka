from datetime import UTC, datetime, timedelta

import pytest

from shakka.rws.tides import (
    build_catalogue_request,
    build_extremes_request,
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_build_extremes_request_exact():
    body = build_extremes_request("hoekvanholland", NOW - timedelta(days=1), NOW)
    assert body == {
        "Locatie": {"Code": "hoekvanholland"},
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {"ProcesType": "astronomisch", "Groepering": {"Code": "GETETBRKD2"}}
        },
        "Periode": {
            "Begindatumtijd": "2026-10-13T12:00:00.000+00:00",
            "Einddatumtijd": "2026-10-14T12:00:00.000+00:00",
        },
    }


def test_build_extremes_request_invalid():
    with pytest.raises(ValueError):
        build_extremes_request("x", datetime(2026, 1, 1), NOW)  # noqa: DTZ001
    with pytest.raises(ValueError):
        build_extremes_request("x", NOW, NOW)
    with pytest.raises(ValueError):
        build_extremes_request("x", NOW, NOW - timedelta(hours=1))


def test_build_catalogue_request_exact():
    assert build_catalogue_request() == {
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
