"""Logic behind `shakka spots validate` and `shakka spots sync`. Return exit codes."""

from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from shakka.config import DEFAULT_SPOTS_PATH, Settings, get_settings
from shakka.db import DatabaseError, SupabaseRest
from shakka.spots.loader import SpotValidationError, load_spots
from shakka.spots.sync import sync_spots


def open_db(settings: Settings) -> SupabaseRest:
    return SupabaseRest.from_settings(settings)


def run_validate(path: Path | None, *, echo: Callable[[str], None]) -> int:
    try:
        spots = load_spots(path or DEFAULT_SPOTS_PATH)
    except SpotValidationError as exc:
        for error in exc.errors:
            echo(f"error   {error}")
        echo(f"spots validate: failed ({len(exc.errors)} errors)")
        return 1
    verified = sum(1 for s in spots if s.verified)
    echo(f"ok      {len(spots)} spots valid ({verified} verified)")
    echo("spots validate: ok")
    return 0


def run_sync(path: Path | None, *, echo: Callable[[str], None]) -> int:
    try:
        settings = get_settings()
    except ValidationError:
        echo("error   configuration incomplete or invalid; run 'shakka doctor'")
        echo("spots sync: failed")
        return 1
    try:
        spots = load_spots(path or settings.spots_path)
    except SpotValidationError as exc:
        for error in exc.errors:
            echo(f"error   {error}")
        echo(f"spots sync: failed ({len(exc.errors)} validation errors, nothing written)")
        return 1
    try:
        with open_db(settings) as db:
            result = sync_spots(db, spots)
    except DatabaseError as exc:
        echo(f"error   database: {exc}")
        echo("spots sync: failed")
        return 1
    unchanged = len(spots) - result.upserted
    echo(f"ok      {result.upserted} of {len(spots)} spots upserted ({unchanged} unchanged)")
    if result.orphaned:
        echo(
            f"warn    {len(result.orphaned)} spots in database but not in YAML (not deleted): "
            + ", ".join(result.orphaned)
        )
    echo("spots sync: ok")
    return 0
