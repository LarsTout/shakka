"""Helpers for the alert tests (WP-07)."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from evaluation_fixtures import make_spot
from shakka.config import REPO_ROOT
from shakka.domain.alerts import AlertRule, AlertRuleOverride, resolve_rule
from shakka.domain.consensus import Confidence
from shakka.domain.direction import DirClass
from shakka.domain.evaluation import HourEvaluation, ReasonCode

SPOT_ID = "test-strand"
H = timedelta(hours=1)


def utc(y: int, m: int, d: int, h: int) -> datetime:
    return datetime(y, m, d, h, tzinfo=UTC)


def hour(
    at: datetime,
    verdict: str = "go",
    dir_class: DirClass | None = DirClass.SIDESHORE,
    spot_id: str = SPOT_ID,
) -> HourEvaluation:
    """Valid HourEvaluation via the normal constructor; reasons follow from the arguments."""
    reasons: tuple[ReasonCode, ...]
    if verdict == "go":
        reasons = ()
    elif verdict == "marginal":
        reasons = (ReasonCode.WIND_BORDERLINE,)
    elif dir_class == DirClass.OFFSHORE:
        reasons = (ReasonCode.OFFSHORE,)
    elif dir_class == DirClass.SIDE_OFFSHORE:
        reasons = (ReasonCode.SIDE_OFFSHORE,)
    elif dir_class is None:
        reasons = (ReasonCode.DIRECTION_UNKNOWN,)
    else:
        reasons = (ReasonCode.WIND_TOO_LIGHT,)
    return HourEvaluation(
        spot_id=spot_id,
        valid_at=at,
        verdict=verdict,
        reasons=reasons,
        wind_kn=20.0,
        gust_kn=None,
        dir_deg=None if dir_class is None else 270,
        dir_class=dir_class,
        confidence=Confidence.MEDIUM,
        tide_level_cm=None,
    )


def go_run(start: datetime, n: int, **kw: Any) -> list[HourEvaluation]:
    """n consecutive go hours from start."""
    return [hour(start + i * H, **kw) for i in range(n)]


def rule(**overrides: Any) -> AlertRule:
    return resolve_rule(make_spot(), None, AlertRuleOverride(**overrides))


def migration_sql() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql"))
    )


def _chunk(constraint: str) -> str:
    sql = migration_sql()
    start = sql.index(constraint)
    return sql[start : start + 1500]


def migration_range(constraint: str) -> tuple[int, int]:
    m = re.search(r"between (\d+) and (\d+)", _chunk(constraint))
    assert m is not None, constraint
    return int(m.group(1)), int(m.group(2))


def _array_content(constraint: str) -> str:
    m = re.search(r"array\[(.*?)\]", _chunk(constraint), re.S)
    assert m is not None, constraint
    return m.group(1)


def migration_text_array(constraint: str) -> set[str]:
    return set(re.findall(r"'([a-z_]+)'", _array_content(constraint)))


def migration_int_array(constraint: str) -> set[int]:
    return {int(x) for x in re.findall(r"(\d+)", _array_content(constraint))}
