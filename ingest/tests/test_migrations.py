"""Guards on supabase/migrations: no later-milestone tables, TABLE_KEYS in sync, RLS everywhere."""

import re

from shakka.config import REPO_ROOT
from shakka.db import TABLE_KEYS

MIGRATIONS = sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql"))
CREATE_TABLE = re.compile(r"create table (?:if not exists )?public\.(\w+)", re.I)


def _sql() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)


def _tables() -> set[str]:
    return set(CREATE_TABLE.findall(_sql()))


def test_migrations_exist():
    assert MIGRATIONS


def test_no_later_milestone_tables():
    pattern = re.compile(r"create table[^;]*(sessions|rsvps)", re.I)
    assert not pattern.search(_sql())


def test_table_keys_match_migrations():
    assert _tables() == set(TABLE_KEYS)


def test_every_migration_table_enables_rls():
    sql = _sql()
    for table in sorted(_tables()):
        pattern = rf"alter table public\.{table} enable row level security"
        assert re.search(pattern, sql, re.I), table


def test_migration_filenames():
    names = [path.name for path in MIGRATIONS]
    assert len(names) == len(set(names))
    for name in names:
        assert re.fullmatch(r"\d{14}_[a-z0-9_]+\.sql", name), name
