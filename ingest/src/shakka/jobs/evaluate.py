"""Evaluation job: evaluate every spot with the spot defaults and store hourly rows."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from pydantic import ValidationError

from shakka.config import get_settings
from shakka.db import DatabaseError, SupabaseRest, iso_utc
from shakka.domain.evaluation import default_limits, evaluate_spot
from shakka.jobs import runtime
from shakka.jobs.inputs import MAX_FETCH_AGE, load_inputs_checked, require_aware, short_error

logger = logging.getLogger(__name__)

EVALUATION_RETENTION: Final = timedelta(hours=48)
EVALUATIONS_ON_CONFLICT: Final = "spot_id,valid_at"


@dataclass(frozen=True, slots=True)
class EvaluationJobResult:
    spots: int  # spots evaluated (with coordinates, valid)
    rows: int  # rows upserted
    deleted: int  # rows removed (valid_at < now - 48h)
    failed: tuple[str, ...] = ()  # spot ids: invalid rows plus evaluation errors, sorted
    errors: tuple[str, ...] = ()  # one line per failed spot
    stale: tuple[str, ...] = ()  # spots whose forecast rows were all older than MAX_FETCH_AGE


def run_evaluation(db: SupabaseRest, *, now: datetime) -> EvaluationJobResult:
    """Evaluate all spots with coordinates, upsert `evaluations`, remove rows older than 48 h.

    A spot without forecast rows evaluates to nothing and is not a failure. Unverified spots
    are evaluated too (the app labels them); only the alert job requires `verified`.
    """
    require_aware(now)
    load = load_inputs_checked(db, now=now, max_fetch_age=MAX_FETCH_AGE)
    rows: list[dict] = []
    failed = list(load.invalid)
    errors = list(load.errors)
    evaluated = 0
    for spot_id, item in load.inputs.items():
        try:
            evals = evaluate_spot(item.spot, item.forecasts, item.tides, default_limits(item.spot))
            rows.extend(e.to_row(evaluated_at=now) for e in evals)
        except ValueError as exc:
            failed.append(spot_id)
            errors.append(f"spot {spot_id}: {type(exc).__name__}: {short_error(exc)}")
            continue
        evaluated += 1
    if rows:
        db.upsert("evaluations", rows, on_conflict=EVALUATIONS_ON_CONFLICT)
    deleted = db.delete(
        "evaluations", filters={"valid_at": f"lt.{iso_utc(now - EVALUATION_RETENTION)}"}
    )
    failed.sort()
    for spot_id in failed:  # spot ids are public data here (data/spots.yaml)
        logger.warning("evaluate: spot %s failed", spot_id)
    logger.info(
        "evaluate: spots=%d rows=%d deleted=%d failed=%d stale=%d",
        evaluated,
        len(rows),
        deleted,
        len(failed),
        len(load.stale),
    )
    return EvaluationJobResult(
        evaluated, len(rows), deleted, tuple(failed), tuple(errors), tuple(load.stale)
    )


def run_evaluate_cli(*, echo: Callable[[str], None]) -> int:
    """Run the evaluation job from the CLI. Returns the exit code (0 or 1)."""
    try:
        settings = get_settings()
    except ValidationError:
        echo("evaluate: configuration incomplete; run shakka doctor")
        return 1
    db = runtime.open_db(settings)
    try:
        result = run_evaluation(db, now=runtime.utcnow())
    except DatabaseError as exc:
        echo(f"evaluate: database error: {exc}")
        return 1
    finally:
        db.close()
    echo(
        f"evaluate: spots={result.spots} rows={result.rows} deleted={result.deleted} "
        f"failed={len(result.failed)}"
    )
    for line in result.errors:
        echo(f"error   {line}")
    echo("evaluate: failed" if result.failed else "evaluate: ok")
    return 1 if result.failed else 0
