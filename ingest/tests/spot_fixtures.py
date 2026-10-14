"""Shared fixtures for the spot profile tests. Only fictional spots (test-strand, zz-*)."""

from pathlib import Path
from typing import Any

FULL_SPOT_YAML = """\
spots:
  - id: test-strand
    name: Teststrand
    region: Testregio
    lat: 52.0
    lon: 4.2
    shore_normal_deg: 290
    ridable_dirs: [{from: 200, to: 20}]
    tide_sensitive: avoid_low
    tide_min_level_cm: -20
    rws_station: hoekvanholland
    season: [{start: "05-01", end: "09-30", from_time: "10:00", to_time: "18:00",
              note: "badseizoen"}]
    status: allowed
    level: intermediate
    default_min_kn: 14
    hazards: null
    notes: null
    verified: true
"""

FULL_SPOT_ROW: dict[str, Any] = {
    "id": "test-strand",
    "name": "Teststrand",
    "region": "Testregio",
    "lat": 52.0,
    "lon": 4.2,
    "shore_normal_deg": 290,
    "ridable_dirs": [{"from": 200, "to": 20}],
    "hazards": None,
    "tide_sensitive": "avoid_low",
    "tide_min_level_cm": -20,
    "rws_station": "hoekvanholland",
    "season": [
        {
            "start": "05-01",
            "end": "09-30",
            "from_time": "10:00",
            "to_time": "18:00",
            "note": "badseizoen",
        }
    ],
    "status": "allowed",
    "level": "intermediate",
    "default_min_kn": 14,
    "notes": None,
    "verified": True,
}

MIN_SPOT_YAML = "spots:\n  - id: zz-min\n    name: Minimal\n    verified: false\n"


def write_spots(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "spots.yaml"
    path.write_text(text, encoding="utf-8")
    return path
