"""Guards on supabase/migrations: TABLE_KEYS in sync, RLS everywhere, rsvps and functions locked."""

import re
from datetime import timedelta

from shakka.config import REPO_ROOT
from shakka.db import TABLE_KEYS
from shakka.jobs.sessions import SESSION_RETENTION

MIGRATIONS = sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql"))
CREATE_TABLE = re.compile(r"create table (?:if not exists )?public\.(\w+)", re.I)


def _sql() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)


def _tables() -> set[str]:
    return set(CREATE_TABLE.findall(_sql()))


def test_migrations_exist():
    assert MIGRATIONS


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


def test_session_retention_matches_migration():
    parts = re.split(r"create (?:or replace )?function", _sql(), flags=re.I)
    purge = [p for p in parts if p.lstrip().startswith("public.purge_expired_sessions")]
    assert len(purge) == 1
    assert "ends_at < p_now - interval '7 days'" in purge[0]
    assert timedelta(days=7) == SESSION_RETENTION


def test_no_grants_on_rsvps():
    # TABLE is optional in GRANT ... ON, so match with and without it (WP-19 review N-6).
    sql = _sql()
    assert re.search(r"grant\s[^;]*\bon\s+(?:table\s+)?[^;]*\bpublic\.rsvps\b", sql, re.I) is None
    assert re.search(r"grant\s[^;]*\bon\s+all\s+tables\b", sql, re.I) is None


def test_security_definer_functions_pin_search_path():
    parts = re.split(r"create (?:or replace )?function", _sql(), flags=re.I)[1:]
    definers = 0
    for part in parts:
        header = part.split("$$", 1)[0]
        if re.search(r"security\s+definer", header, re.I):
            definers += 1
            assert "set search_path = ''" in header, header[:80]
    assert definers >= 5
