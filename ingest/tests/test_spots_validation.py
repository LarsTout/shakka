"""Loader tests (AC-3): every error is collected, with spot id and field name."""

from pathlib import Path

import pytest

from shakka.domain.spot import TideSensitivity
from shakka.spots.loader import SpotValidationError, load_spots
from spot_fixtures import write_spots


def spots_yaml(*items: str) -> str:
    return "spots:\n" + "".join(items)


def item(body: str) -> str:
    """One list item; body lines are given without indentation (first line is the id)."""
    lines = body.strip("\n").split("\n")
    return "  - " + lines[0] + "\n" + "".join(f"    {line}\n" for line in lines[1:])


def errors_of(tmp_path: Path, text: str) -> list[str]:
    with pytest.raises(SpotValidationError) as info:
        load_spots(write_spots(tmp_path, text))
    return info.value.errors


CASES = [
    (
        spots_yaml(item("id: zz-dup\nname: A"), item("id: zz-dup\nname: B")),
        "zz-dup",
        "id",
    ),
    (spots_yaml(item("id: Bad_Id\nname: X")), "Bad_Id", "id"),
    (spots_yaml(item("id: zz-a\nname: X\nlat: 52.0")), "zz-a", "lon"),
    (spots_yaml(item("id: zz-b\nname: X\nlat: 48.0\nlon: 2.0")), "zz-b", "lat"),
    (spots_yaml(item("id: zz-b\nname: X\nlat: 48.0\nlon: 2.0")), "zz-b", "lon"),
    (spots_yaml(item("id: zz-c\nname: X\nshore_normal_deg: 360")), "zz-c", "shore_normal_deg"),
    (
        spots_yaml(item("id: zz-d\nname: X\nridable_dirs: [{from: 400, to: 20}]")),
        "zz-d",
        "ridable_dirs",
    ),
    (
        spots_yaml(item('id: zz-e\nname: X\nseason: [{start: "02-30", end: "03-31"}]')),
        "zz-e",
        "season",
    ),
    (
        spots_yaml(
            item('id: zz-f\nname: X\nseason: [{start: "05-01", end: "09-30", from_time: "10:00"}]')
        ),
        "zz-f",
        "season",
    ),
    (
        spots_yaml(
            item('id: zz-f\nname: X\nseason: [{start: "05-01", end: "09-30", from_time: "10:00"}]')
        ),
        "zz-f",
        "to_time",
    ),
    (spots_yaml(item("id: zz-g\nname: X\nstatus: open")), "zz-g", "status"),
    (spots_yaml(item("id: zz-h\nname: X\nparking: true")), "zz-h", "parking"),
    (
        spots_yaml(
            item(
                "id: zz-i\nname: X\nlat: 52.0\nlon: 4.2\nstatus: allowed\n"
                "level: beginner\nverified: true"
            )
        ),
        "zz-i",
        "shore_normal_deg",
    ),
]


@pytest.mark.parametrize(("text", "spot_id", "field"), CASES)
def test_invalid_spot(tmp_path: Path, text: str, spot_id: str, field: str):
    errors = errors_of(tmp_path, text)
    assert any(spot_id in e and field in e for e in errors), errors


def test_three_errors_in_one_exception(tmp_path: Path):
    text = spots_yaml(
        item("id: Bad_Id\nname: X\nstatus: open"), item("id: zz-ok\nname: Y\nlat: 52.0")
    )
    errors = errors_of(tmp_path, text)
    assert len(errors) == 3
    assert "id" in errors[0] and "status" in errors[1] and "lon" in errors[2]
    assert "zz-ok" in errors[2]


def S(season: str) -> str:
    return spots_yaml(item(f"id: zz-s\nname: X\nseason: {season}"))


EDGE_CASES = [
    ("E1", S('[{start: "05-01", end: "09-30", from_time: 10:00, to_time: "18:00"}]'), "from_time"),
    (
        "E1q",
        S('[{start: "05-01", end: "09-30", from_time: 10:00, to_time: "18:00"}]'),
        "expected a quoted 'HH:MM' time",
    ),
    ("E3a", S('[{start: "02-30", end: "03-01"}]'), "season[0].start"),
    ("E3b", S('[{start: "13-01", end: "03-01"}]'), "season[0].start"),
    ("E3c", S('[{start: "5-1", end: "03-01"}]'), "season[0].start"),
    ("E3d", S('[{start: "00-10", end: "03-01"}]'), "season[0].start"),
    ("E4", S('[{start: 2026-05-01, end: "03-01"}]'), "expected a quoted 'MM-DD' date"),
    (
        "E6a",
        S('[{start: "05-01", end: "09-30", from_time: "18:00", to_time: "10:00"}]'),
        "from_time must be before to_time",
    ),
    (
        "E6b",
        S('[{start: "05-01", end: "09-30", from_time: "10:00", to_time: "10:00"}]'),
        "from_time must be before to_time",
    ),
    ("E8", spots_yaml(item("id: zz-a\nname: X\nridable_dirs: []")), "ridable_dirs"),
    ("E9", spots_yaml(item("id: zz-a\nname: X\nridable_dirs: [{from: 10}]")), "ridable_dirs[0].to"),
    ("E10a", spots_yaml(item("id: zz-a\nname: X\nshore_normal_deg: yes")), "expected an integer"),
    ("E10b", spots_yaml(item('id: zz-a\nname: X\nshore_normal_deg: "290"')), "expected an integer"),
    ("E10c", spots_yaml(item("id: zz-a\nname: X\nshore_normal_deg: 290.0")), "expected an integer"),
    ("E11a", spots_yaml(item("id: zz-a\nname: X\nlat: .nan\nlon: 4.0")), "lat"),
    ("E11b", spots_yaml(item('id: zz-a\nname: X\nlat: "52.0"\nlon: 4.0')), "lat"),
    ("E11c", spots_yaml(item("id: zz-a\nname: X\nlat: true\nlon: 4.0")), "lat"),
    ("E14a", spots_yaml(item('id: zz-a\nname: "  "')), "must not be blank"),
    ("E14b", spots_yaml(item('id: zz-a\nname: X\nregion: ""')), "must not be blank"),
    ("E15", spots_yaml(item("id: 123\nname: X")), "spots[0]: id"),
    ("E16", spots_yaml(item("name: X")), "spots[0]: id: Field required"),
    (
        "E17",
        spots_yaml(item("id: zz-a\nname: X\nlat: 52.0\nlat: 52.1")),
        "found duplicate key 'lat'",
    ),
    ("E18a", "", "file is empty"),
    ("E18b", "# only a comment\n", "file is empty"),
    ("E18c", "- a\n- b\n", "top level must be a mapping"),
    ("E18d", "spots: {}\n", "top level must be a mapping"),
    ("E18e", "spots: []\nextra: 1\n", "unknown top-level key 'extra'"),
    ("E20", "spots: [\n  - id: a\n", "line"),
    ("E22", spots_yaml(item('id: zz-a\nname: X\nverified: "true"')), "expected true or false"),
    ("E23", spots_yaml(item("id: zz-a\nname: X\ntide_min_level_cm: -20")), "tide_min_level_cm"),
    (
        "E24",
        spots_yaml(
            item(
                "id: zz-a\nname: X\nlat: 52.0\nlon: 4.2\nshore_normal_deg: 1\nstatus: allowed\n"
                "level: beginner\ntide_sensitive: avoid_low\nverified: true"
            )
        ),
        "rws_station",
    ),
    ("E39", "spots:\n  - id: zz-a\n    name: X\n    ? [a, b]\n    : x\n", "found unhashable key"),
    ("E40a", S(r'[{start: "05-01\n", end: "09-30"}]'), "season[0].start"),
    ("E40b", S(r'[{start: "０５-01", end: "09-30"}]'), "expected a quoted 'MM-DD' date"),
    (
        "E40c",
        S(r'[{start: "05-01", end: "09-30", from_time: "10:00\n", to_time: "18:00"}]'),
        "expected a quoted 'HH:MM' time",
    ),
    ("E40d", 'spots:\n  - id: "zz-a\\n"\n    name: X\n', "id"),
    ("E41a", 'spots:\n  - id: zz-a\n    name: "a\\0b"\n', "must not contain NUL characters"),
    (
        "E41b",
        'spots:\n  - id: zz-a\n    name: X\n    notes: "x\\0"\n',
        "must not contain NUL characters",
    ),
    ("E41c", S(r'[{start: "05-01", end: "09-30", note: "\0"}]'), "must not contain NUL characters"),
]


@pytest.mark.parametrize(
    ("text", "needle"), [(t, n) for _, t, n in EDGE_CASES], ids=[c[0] for c in EDGE_CASES]
)
def test_edge_cases(tmp_path: Path, text: str, needle: str):
    errors = errors_of(tmp_path, text)
    assert any(needle in e for e in errors), errors


def test_e19_missing_file(tmp_path: Path):
    path = tmp_path / "nope.yaml"
    with pytest.raises(SpotValidationError) as info:
        load_spots(path)
    assert info.value.errors == [f"{path}: file not found"]


def test_error_lines_are_single_line(tmp_path: Path):
    for _, text, _ in EDGE_CASES:
        if _.startswith(("E40", "E41")):
            for e in errors_of(tmp_path, text):
                assert "\n" not in e and "\x00" not in e
    errors = errors_of(tmp_path, 'spots:\n  - id: "zz-a\\n"\n    name: X\n')
    assert errors[0].startswith("spots[0]: id: ")


def test_e15_label_without_id(tmp_path: Path):
    errors = errors_of(tmp_path, spots_yaml(item("id: 123\nname: X")))
    assert errors[0].startswith("spots[0]: id: ")


def test_e17_format(tmp_path: Path):
    errors = errors_of(tmp_path, spots_yaml(item("id: zz-a\nname: X\nlat: 1\nlat: 2")))
    assert len(errors) == 1 and errors[0].startswith("spots.yaml: line ")


def test_e39_single_error(tmp_path: Path):
    errors = errors_of(tmp_path, "spots:\n  - id: zz-a\n    name: X\n    ? [a, b]\n    : x\n")
    assert len(errors) == 1


def test_valid_edge_cases(tmp_path: Path):
    text = spots_yaml(
        item(
            'id: zz-1\nname: X\nseason: [{start: "05-01", end: "09-30", from_time: 09:30, '
            'to_time: "18:00"}]'
        ),
        item('id: zz-2\nname: X\nseason: [{start: "02-29", end: "11-01"}]'),
        item('id: zz-3\nname: X\nseason: [{start: "11-01", end: "02-28"}]'),
        item("id: zz-4\nname: X\nridable_dirs: [{from: 200, to: 20}]"),
        item("id: zz-5\nname: X\nlat: 50.7\nlon: 7.3"),
        item("id: zz-6\nname: X\nlat: 52\nlon: 4"),
        item("id: zz-7\nname: X\nseason:\ntide_sensitive:\nverified:"),
    )
    spots = load_spots(write_spots(tmp_path, text))
    assert spots[0].season[0].from_time.strftime("%H:%M") == "09:30"  # type: ignore[union-attr]
    assert spots[1].season[0].start == "02-29"
    assert spots[2].season[0].start == "11-01" and spots[2].season[0].end == "02-28"
    assert spots[3].ridable_dirs is not None and spots[3].ridable_dirs[0].from_deg == 200
    assert (spots[4].lat, spots[4].lon) == (50.7, 7.3)
    assert spots[5].lat == 52.0 and isinstance(spots[5].lat, float)
    assert spots[6].season == ()
    assert spots[6].tide_sensitive is TideSensitivity.NONE
    assert spots[6].verified is False


def test_empty_spots_list_is_valid(tmp_path: Path):
    assert load_spots(write_spots(tmp_path, "spots: []\n")) == []


def test_error_format(tmp_path: Path):
    errors = errors_of(
        tmp_path, spots_yaml(item('id: zz-e\nname: X\nseason: [{start: "02-30", end: "03-31"}]'))
    )
    assert errors[0].startswith("spots[0] (zz-e): season[0].start: ")


def test_file_order_preserved(tmp_path: Path):
    text = spots_yaml(
        item("id: zz-c\nname: C"), item("id: zz-a\nname: A"), item("id: zz-b\nname: B")
    )
    assert [s.id for s in load_spots(write_spots(tmp_path, text))] == ["zz-c", "zz-a", "zz-b"]


def test_exception_message():
    exc = SpotValidationError(["a", "b"])
    assert str(exc) == "2 spot validation error(s):\na\nb"
