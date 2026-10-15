"""Permanent checks on data/spots.yaml (A9). Never assert exact counts, names or fields."""

from shakka.config import DEFAULT_SPOTS_PATH
from shakka.spots.loader import load_spots

CONTRACT_IDS = [
    "wijk-aan-zee",
    "ijmuiden",
    "zandvoort",
    "bloemendaal",
    "noordwijk",
    "langevelderslag",
    "katwijk",
    "scheveningen",
    "kijkduin",
    "oostvoorne",
    "brouwersdam",
    "neeltje-jans",
    "vrouwenpolder",
    "domburg",
    "workum",
    "makkum",
    "hindeloopen",
    "lemmer",
    "den-helder",
    "callantsoog",
    "petten",
    "camperduin",
    "schellinkhout",
    "muiderberg",
    "lauwersmeer",
]


def test_data_file_is_valid():
    load_spots(DEFAULT_SPOTS_PATH)


def test_contract_ids_present():
    ids = {s.id for s in load_spots(DEFAULT_SPOTS_PATH)}
    assert set(CONTRACT_IDS) <= ids
