"""Capture real DDAPI20 responses as test fixtures (network needed, not run by pytest).

Usage: cd ingest && uv run python scripts/capture_rws_fixtures.py
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from shakka.http import make_client
from shakka.rws.tides import (
    CATALOGUE_URL,
    OBSERVATIONS_URL,
    build_catalogue_request,
    build_extremes_request,
)

STATION = "hoekvanholland"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "rws"
MAX_CATALOGUE_BYTES = 500_000


def code(obj: Any, key: str) -> str:
    inner = obj.get(key) if isinstance(obj, dict) else None
    return str(inner.get("Code", "")) if isinstance(inner, dict) else ""


def dump(payload: Any) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=False) + "\n"


def link_key(item: dict[str, Any]) -> Any:
    return item.get("AquoMetaData_MessageID", item.get("AquoMetadata_MessageID"))


def shorten_catalogue(catalogue: dict[str, Any]) -> tuple[dict[str, Any], str]:
    meta_items = catalogue["AquoMetadataLijst"]
    good_ids = {
        m.get("AquoMetadata_MessageID")
        for m in meta_items
        if m.get("ProcesType") == "astronomisch"
        and code(m, "Grootheid") == "WATHTE"
        and code(m, "Groepering") == "GETETBRKD2"
        and code(m, "Hoedanigheid") == "NAP"
    }
    links = catalogue["AquoMetadataLocatieLijst"]
    good_locs = {x["Locatie_MessageID"] for x in links if link_key(x) in good_ids}
    locations = sorted(catalogue["LocatieLijst"], key=lambda loc: str(loc.get("Code")))
    negative = next(loc for loc in locations if loc["Locatie_MessageID"] not in good_locs)
    wanted_codes = {STATION, "vlissingen", negative["Code"]}
    kept_locs = [loc for loc in catalogue["LocatieLijst"] if loc.get("Code") in wanted_codes]
    kept_ids = {loc["Locatie_MessageID"] for loc in kept_locs}
    kept_links = [x for x in links if x["Locatie_MessageID"] in kept_ids]
    kept_meta_ids = {link_key(x) for x in kept_links}
    kept_meta = [m for m in meta_items if m.get("AquoMetadata_MessageID") in kept_meta_ids]
    short = dict(catalogue)
    short["LocatieLijst"] = kept_locs
    short["AquoMetadataLocatieLijst"] = kept_links
    short["AquoMetadataLijst"] = kept_meta
    return short, str(negative["Code"])


def main() -> int:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start, end = now - timedelta(days=1), now + timedelta(days=8)
    req_obs = build_extremes_request(STATION, start, end)
    req_cat = build_catalogue_request()
    with make_client(timeout=60.0) as client:
        r_obs = client.post(OBSERVATIONS_URL, json=req_obs)
        r_cat = client.post(CATALOGUE_URL, json=req_cat)
    for name, resp in (("waarnemingen", r_obs), ("catalogus", r_cat)):
        print(f"{name}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            print(f"FAILED: {name} returned HTTP {resp.status_code}: {resp.text[:300]}")
            return 1
    obs, cat = r_obs.json(), r_cat.json()
    for name, payload in (("waarnemingen", obs), ("catalogus", cat)):
        if isinstance(payload, dict) and payload.get("Succesvol") is False:
            print(f"FAILED: {name} Succesvol=false: {str(payload.get('Foutmelding'))[:300]}")
            return 1

    for w in obs.get("WaarnemingenLijst", []):
        meta = w.get("AquoMetadata") or {}
        metingen = w.get("MetingenLijst") or []
        print(
            "channel:",
            "ProcesType=", meta.get("ProcesType"),
            "Grootheid=", code(meta, "Grootheid"),
            "Hoedanigheid=", code(meta, "Hoedanigheid"),
            "Eenheid=", code(meta, "Eenheid"),
            "Groepering=", code(meta, "Groepering"),
            "Typering=", code(meta, "Typering"),
            "metingen=", len(metingen),
        )  # fmt: skip
        if code(meta, "Typering") == "GETETTPE":
            texts = {m.get("Meetwaarde", {}).get("Waarde_Alfanumeriek") for m in metingen}
            print("  type texts:", sorted(str(t) for t in texts))

    try:
        from shakka.rws.tides import TideFetchError, parse_stations
    except ImportError:  # parsers do not exist yet (first capture, before step 3)
        stations = []
        in_catalogue = [x for x in cat["LocatieLijst"] if x.get("Code") == STATION]
        print(
            "hoekvanholland in LocatieLijst:", in_catalogue[0].get("Naam") if in_catalogue else "NO"
        )
    else:
        try:
            stations = parse_stations(cat)
        except TideFetchError as exc:
            print(f"parse_stations failed: {exc}")
            stations = []
        hvh = [s for s in stations if s.code == STATION]
        print("hoekvanholland in parse_stations:", hvh[0].name if hvh else "NO")

    short, negative = shorten_catalogue(cat)
    text = dump(short)
    if len(text.encode()) > MAX_CATALOGUE_BYTES:
        print(f"FAILED: catalogue subset is {len(text.encode())} bytes (> {MAX_CATALOGUE_BYTES})")
        return 1
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "waarnemingen_hoekvanholland.json").write_text(dump(obs), encoding="utf-8")
    (FIXTURES / "catalogus_subset.json").write_text(text, encoding="utf-8")
    info = {
        "captured_at": datetime.now(UTC).isoformat(),
        "station": STATION,
        "begin": start.isoformat(),
        "end": end.isoformat(),
        "request_waarnemingen": req_obs,
        "request_catalogus": req_cat,
        "catalogue_station_count": len(stations),
        "negative_location": negative,
    }
    (FIXTURES / "capture_info.json").write_text(dump(info), encoding="utf-8")
    print("fixtures written to", FIXTURES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
