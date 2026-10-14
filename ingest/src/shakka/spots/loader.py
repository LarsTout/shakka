"""Load data/spots.yaml and validate every profile, collecting all errors."""

import collections.abc
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from shakka.domain.spot import SpotProfile, SpotProfileBase, spot_rule_violations


class SpotValidationError(Exception):
    """One or more problems in the spots file. Each entry in `errors` is a single line."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__(f"{len(self.errors)} spot validation error(s):\n" + "\n".join(self.errors))


class UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys."""

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, yaml.MappingNode):
            seen: set[object] = set()
            for key_node, _value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    continue
                key = self.construct_object(key_node, deep=False)
                if not isinstance(key, collections.abc.Hashable):
                    # leave it to super(): it raises ConstructorError("found unhashable key")
                    continue
                if key in seen:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key {key!r}",
                        key_node.start_mark,
                    )
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _loc(loc: tuple[int | str, ...]) -> str:
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        elif out:
            out += f".{part}"
        else:
            out = part
    return out or "(spot)"


def load_spots(path: Path) -> list[SpotProfile]:
    """Load and validate all spot profiles; raise SpotValidationError with every error found."""
    name = path.name
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SpotValidationError([f"{path}: file not found"]) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise SpotValidationError([f"{path}: cannot read file ({type(exc).__name__})"]) from None

    try:
        data = yaml.load(text, Loader=UniqueKeySafeLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.MarkedYAMLError as exc:
        problem = exc.problem or "invalid YAML"
        mark = exc.problem_mark
        if mark is not None:
            msg = f"{name}: line {mark.line + 1}, column {mark.column + 1}: {problem}"
        else:
            msg = f"{name}: {problem}"
        raise SpotValidationError([msg]) from None
    except yaml.YAMLError as exc:
        raise SpotValidationError([f"{name}: invalid YAML ({type(exc).__name__})"]) from None

    shape_error = f"{name}: top level must be a mapping with a 'spots' list"
    if data is None:
        raise SpotValidationError([f"{name}: file is empty"])
    if not isinstance(data, dict) or "spots" not in data:
        raise SpotValidationError([shape_error])
    extra = [key for key in data if key != "spots"]
    if extra:
        raise SpotValidationError([f"{name}: unknown top-level key {key!r}" for key in extra])
    items = data["spots"]
    if not isinstance(items, list):
        raise SpotValidationError([shape_error])

    errors: list[str] = []
    profiles: list[SpotProfile] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"spots[{i}]: expected a mapping")
            continue
        raw_id = item.get("id")
        label = f"spots[{i}]"
        if isinstance(raw_id, str) and raw_id.isprintable():
            label = f"spots[{i}] ({raw_id})"
        if isinstance(raw_id, str):
            if raw_id in seen:
                errors.append(f"{label}: id: duplicate of spots[{seen[raw_id]}]")
            else:
                seen[raw_id] = i

        try:
            base = SpotProfileBase.model_validate(item)
        except ValidationError as exc:
            for err in exc.errors(include_url=False, include_input=False):
                errors.append(f"{label}: {_loc(err['loc'])}: {err['msg']}")
            continue
        violations = spot_rule_violations(base)
        for violation in violations:
            errors.append(f"{label}: {violation.field}: {violation.message}")
        if violations:
            continue
        profiles.append(SpotProfile.model_validate(item))

    if errors:
        raise SpotValidationError(errors)
    return profiles
