import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from shakka.rws.tides import (
    TideFetchError,
    build_catalogue_request,
    build_extremes_request,
    parse_extremes_response,
    parse_stations,
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "rws"

# Counted on the raw fixture with a plain Python one-liner: number of measurements in the
# WATHTE/NAP channel (35) minus the number of "topagger" types (0).
EXPECTED_EXTREMES = 35


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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


# -- AC-1: real fixture ------------------------------------------------------------------------


def raw_channels(payload):
    levels, types = [], []
    for w in payload["WaarnemingenLijst"]:
        meta = w["AquoMetadata"]
        if meta["Typering"]["Code"] == "GETETTPE":
            types.extend(w["MetingenLijst"])
        elif meta["Grootheid"]["Code"] == "WATHTE" and meta["Hoedanigheid"]["Code"] == "NAP":
            levels.extend(w["MetingenLijst"])
    return levels, types


@pytest.fixture(scope="module")
def fixture_result():
    return parse_extremes_response(load("waarnemingen_hoekvanholland.json"), "hoekvanholland")


def test_fixture_count(fixture_result):
    levels, types = raw_channels(load("waarnemingen_hoekvanholland.json"))
    tops = [
        t for t in types if t["Meetwaarde"]["Waarde_Alfanumeriek"].strip().lower() == "topagger"
    ]
    assert len(levels) - len(tops) == EXPECTED_EXTREMES
    assert len(fixture_result) == EXPECTED_EXTREMES


def test_fixture_kinds_alternate(fixture_result):
    _, types = raw_channels(load("waarnemingen_hoekvanholland.json"))
    raw = {
        datetime.fromisoformat(t["Tijdstip"]).astimezone(UTC): t["Meetwaarde"][
            "Waarde_Alfanumeriek"
        ]
        for t in types
    }
    for a, b in zip(fixture_result, fixture_result[1:], strict=False):
        if a.kind == b.kind:
            assert a.kind == "low"
            assert (raw[a.at], raw[b.at]) == ("laagwater 1", "laagwater 2")


def test_fixture_levels_are_int(fixture_result):
    assert all(type(e.level_cm) is int for e in fixture_result)


def test_fixture_times_utc(fixture_result):
    assert all(e.at.tzinfo is UTC for e in fixture_result)
    assert [e.at for e in fixture_result] == sorted(e.at for e in fixture_result)
    levels, _ = raw_channels(load("waarnemingen_hoekvanholland.json"))
    levels.sort(key=lambda m: datetime.fromisoformat(m["Tijdstip"]))
    first, last = levels[0], levels[-1]
    assert fixture_result[0].at == datetime.fromisoformat(first["Tijdstip"]).astimezone(UTC)
    assert fixture_result[0].level_cm == math.floor(first["Meetwaarde"]["Waarde_Numeriek"] + 0.5)
    assert fixture_result[-1].at == datetime.fromisoformat(last["Tijdstip"]).astimezone(UTC)
    assert fixture_result[-1].level_cm == math.floor(last["Meetwaarde"]["Waarde_Numeriek"] + 0.5)


def test_fixture_window(fixture_result):
    info = load("capture_info.json")
    begin = datetime.fromisoformat(info["begin"])
    end = datetime.fromisoformat(info["end"])
    assert all(begin <= e.at <= end for e in fixture_result)


# -- synthetic payloads ------------------------------------------------------------------------


def meas(t, numeric=None, text=None, quality="00"):
    return {
        "Tijdstip": t,
        "Meetwaarde": {"Waarde_Numeriek": numeric, "Waarde_Alfanumeriek": text},
        "WaarnemingMetadata": {"Kwaliteitswaardecode": quality},
    }


def channel(metingen, *, proces="astronomisch", groep="GETETBRKD2", **codes):
    meta = {"ProcesType": proces, "Groepering": {"Code": groep}}
    for key, value in codes.items():
        meta[key] = {"Code": value}
    return {"AquoMetadata": meta, "MetingenLijst": metingen}


def level_ch(metingen, unit="cm", hoed="NAP", **kw):
    return channel(metingen, Grootheid="WATHTE", Hoedanigheid=hoed, Eenheid=unit, **kw)


def type_ch(metingen, **kw):
    return channel(metingen, Grootheid="NVT", Hoedanigheid="NVT", Typering="GETETTPE", **kw)


def payload(levels, types, **kw):
    return {
        "Succesvol": True,
        "WaarnemingenLijst": [
            level_ch([meas(t, v, str(v), **({"quality": q} if q else {})) for t, v, q in levels]),
            type_ch([meas(t, 0.0, text) for t, text in types]),
        ],
        **kw,
    }


T1 = "2026-10-14T12:00:00.000+01:00"
T2 = "2026-10-14T18:00:00.000+01:00"
T3 = "2026-10-14T23:00:00.000+01:00"


def parse(p):
    return parse_extremes_response(p, "st")


def test_offset_plus_one_converted():
    for local, utc in (
        ("2026-10-14T12:00:00.000+01:00", datetime(2026, 10, 14, 11, 0, tzinfo=UTC)),
        ("2026-07-01T12:00:00.000+01:00", datetime(2026, 7, 1, 11, 0, tzinfo=UTC)),
    ):
        (e,) = parse(payload([(local, 50, None)], [(local, "Hoogwater")]))
        assert e.at == utc
        assert e.kind == "high"


def test_kinds_and_topagger():
    p = payload(
        [
            (T1, 10, None),
            (T2, -40, None),
            (T3, -30, None),
            ("2026-10-15T01:00:00.000+01:00", -35, None),
        ],
        [
            (T1, " HOOGWATER "),
            (T2, "Laagwater 1"),
            (T3, "topagger"),
            ("2026-10-15T01:00:00.000+01:00", "laagwater 2"),
        ],
    )
    result = parse(p)
    assert [(e.kind, e.level_cm) for e in result] == [("high", 10), ("low", -40), ("low", -35)]


def test_rounding_half_up():
    p = payload([(T1, 12.5, None), (T2, -12.5, None)], [(T1, "hoogwater"), (T2, "laagwater")])
    assert [e.level_cm for e in parse(p)] == [13, -12]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["WaarnemingenLijst"][1]["MetingenLijst"][0]["Meetwaarde"].update(
            Waarde_Alfanumeriek="dubbel hoogwater"
        ),
        lambda p: p["WaarnemingenLijst"][1]["MetingenLijst"].pop(),
        lambda p: p["WaarnemingenLijst"][0]["AquoMetadata"]["Eenheid"].update(Code="m"),
        lambda p: p["WaarnemingenLijst"].pop(0),
        lambda p: p["WaarnemingenLijst"].pop(1),
        lambda p: p["WaarnemingenLijst"][0]["MetingenLijst"][0].update(
            Tijdstip="2026-10-14T12:00:00"
        ),
        lambda p: p["WaarnemingenLijst"][0]["MetingenLijst"][0].update(Tijdstip="nonsense"),
        lambda p: p["WaarnemingenLijst"][0]["MetingenLijst"].append(meas(T1, 99, "99")),
        lambda p: p["WaarnemingenLijst"][0]["MetingenLijst"][0].pop("Tijdstip"),
        lambda p: p["WaarnemingenLijst"][0].update(MetingenLijst="x"),
        lambda p: p["WaarnemingenLijst"].append("not a dict"),
        lambda p: p["WaarnemingenLijst"][0]["MetingenLijst"].append(None),
        lambda p: p.update(WaarnemingenLijst={}),
    ],
)
def test_structural_errors(mutate):
    p = payload([(T1, 10, None), (T2, -40, None)], [(T1, "hoogwater"), (T2, "laagwater")])
    mutate(p)
    with pytest.raises(TideFetchError):
        parse(p)


def test_non_dict_payload():
    for bad in (None, [], "x", 3):
        with pytest.raises(TideFetchError):
            parse(bad)


def test_invalid_measurements_skipped():
    p = payload(
        [(T1, 99, "99"), (T2, None, None), (T3, 999999999, None)],
        [(T1, "hoogwater"), (T2, "laagwater"), (T3, "hoogwater")],
    )
    with pytest.raises(TideFetchError, match="no extremes"):
        parse(p)
    p = payload([(T1, 10, None), (T2, True, None)], [(T1, "hoogwater")])
    p["WaarnemingenLijst"][0]["MetingenLijst"][1]["Meetwaarde"]["Waarde_Numeriek"] = True
    assert len(parse(p)) == 1


def test_quality_99_type_skipped():
    # N-6: an invalid type measurement (even with a strange text) must not fail the station
    p = payload([(T1, 10, None)], [(T1, "hoogwater")])
    p["WaarnemingenLijst"][1]["MetingenLijst"].append(meas(T2, 0.0, "???", quality="99"))
    assert len(parse(p)) == 1


def test_conflicting_levels_and_duplicates():
    p = payload([(T1, 10, None), (T1, 11, None)], [(T1, "hoogwater")])
    with pytest.raises(TideFetchError):
        parse(p)
    p = payload([(T1, 10, None), (T1, 10, None)], [(T1, "hoogwater")])
    assert len(parse(p)) == 1
    p = payload([(T1, 10, None)], [(T1, "hoogwater"), (T1, "laagwater")])
    with pytest.raises(TideFetchError):
        parse(p)


def test_other_channels_ignored():
    p = payload([(T1, 10, None)], [(T1, "hoogwater")])
    p["WaarnemingenLijst"].append(level_ch([meas(T1, 999, "999")], hoed="MSL"))
    p["WaarnemingenLijst"].append(level_ch([meas(T2, 5, "5")], proces="meting"))
    p["WaarnemingenLijst"].append(level_ch([meas(T2, 5, "5")], groep="OTHER"))
    result = parse(p)
    assert [e.level_cm for e in result] == [10]


def test_rws_error_text_truncated():
    p = {"Succesvol": False, "Foutmelding": "x" * 500}
    with pytest.raises(TideFetchError) as info:
        parse(p)
    assert len(str(info.value)) <= 200 + len("st: RWS error: ")
    assert "x" * 200 in str(info.value)


# -- stations ----------------------------------------------------------------------------------


def test_parse_stations_fixture():
    stations = parse_stations(load("catalogus_subset.json"))
    by_code = {s.code: s for s in stations}
    hvh = by_code["hoekvanholland"]
    assert "Hoek van Holland" in hvh.name
    assert 51 < hvh.lat < 53
    assert 3 < hvh.lon < 5
    assert load("capture_info.json")["negative_location"] not in by_code


def catalogue(meta=None, links=None, locs=None, link_key="AquoMetaData_MessageID"):
    good = {
        "AquoMetadata_MessageID": 1,
        "ProcesType": "astronomisch",
        "Grootheid": {"Code": "WATHTE"},
        "Groepering": {"Code": "GETETBRKD2"},
        "Hoedanigheid": {"Code": "NAP"},
    }
    return {
        "Succesvol": True,
        "AquoMetadataLijst": [good] if meta is None else meta,
        "AquoMetadataLocatieLijst": (
            [{"Locatie_MessageID": 10, link_key: 1}] if links is None else links
        ),
        "LocatieLijst": (
            [{"Locatie_MessageID": 10, "Code": "b", "Naam": "B", "Lat": 52.0, "Lon": 4.0}]
            if locs is None
            else locs
        ),
    }


def test_parse_stations_variants():
    assert [s.code for s in parse_stations(catalogue())] == ["b"]
    assert [s.code for s in parse_stations(catalogue(link_key="AquoMetadata_MessageID"))] == ["b"]
    # duplicate links -> one station; sorted on code; bad coordinates skipped
    locs = [
        {"Locatie_MessageID": 10, "Code": "z", "Naam": "Z", "Lat": "52.5", "Lon": 4},
        {"Locatie_MessageID": 10, "Code": "a", "Naam": "A", "Lat": 52, "Lon": 4},
        {"Locatie_MessageID": 10, "Code": "far", "Naam": "F", "Lat": 200, "Lon": 4},
        {"Locatie_MessageID": 10, "Code": "none", "Naam": "N", "Lat": None, "Lon": 4},
        {"Locatie_MessageID": 10, "Code": "a", "Naam": "A2", "Lat": 53, "Lon": 4},
    ]
    links = [{"Locatie_MessageID": 10, "AquoMetaData_MessageID": 1}] * 2
    result = parse_stations(catalogue(locs=locs, links=links))
    assert [(s.code, s.name) for s in result] == [("a", "A"), ("z", "Z")]


@pytest.mark.parametrize(
    "change",
    [
        {"ProcesType": "meting"},
        {"Groepering": {"Code": ""}},
        {"Hoedanigheid": {"Code": "MSL"}},
    ],
)
def test_parse_stations_excluded(change):
    base = catalogue()["AquoMetadataLijst"][0] | change
    with pytest.raises(TideFetchError, match="no stations"):
        parse_stations(catalogue(meta=[base]))


def test_parse_stations_errors():
    for bad in (None, [], {"Succesvol": False, "Foutmelding": "x"}, {"LocatieLijst": []}):
        with pytest.raises(TideFetchError):
            parse_stations(bad)
    broken = catalogue(locs=["nope"])
    with pytest.raises(TideFetchError):
        parse_stations(broken)
