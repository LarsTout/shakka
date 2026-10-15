"""Tests for the admin commands (WP-10 AC-8, AC-9)."""

import pytest
from click.testing import CliRunner

import shakka.jobs.runtime
from fakes import FakeSupabase
from job_fixtures import (
    NOW,
    SPOT,
    USER_A,
    seed_favorite,
    seed_forecasts,
    seed_profile,
    seed_spot,
)
from shakka.cli import cli
from shakka.db import DatabaseError
from shakka.domain.alerts import AlertRuleOverride
from shakka.jobs.admin import AdminError, parse_quiver, quiver_comma_note
from shakka.jobs.alerts import RULE_COLUMNS, run_alerts

USER_C_UNKNOWN = "99999999-9999-4999-8999-999999999999"


class Counting(FakeSupabase):
    def __init__(self) -> None:
        super().__init__()
        self.selects = 0

    def select(self, *args, **kwargs):
        self.selects += 1
        return super().select(*args, **kwargs)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret-key")

    def install(db):
        monkeypatch.setattr(shakka.jobs.runtime, "open_db", lambda settings: db)
        monkeypatch.setattr(shakka.jobs.runtime, "utcnow", lambda: NOW)
        return db

    return install


def run(*args):
    result = CliRunner().invoke(cli, list(args))
    return result.exit_code, result.output.splitlines(), result.output


def profile_db(**cols):
    db = FakeSupabase()
    base = {
        "weight_kg": 70,
        "level": "advanced",
        "quiver_m2": [9.0, 12.0],
        "default_min_kn": 14,
        "default_max_kn": None,
    }
    seed_profile(db, USER_A, **(base | cols))
    return db


# -- AC-9 -------------------------------------------------------------------------------------


def test_profile_set_weight_only(setup):
    db = setup(profile_db())
    before = db.rows("profiles")[0]
    code, lines, _ = run("admin", "profile", "set", "--user-id", USER_A, "--weight", "80")
    assert code == 0
    assert lines[0] == "profile set: saved"
    after = db.rows("profiles")[0]
    assert after["weight_kg"] == 80
    assert {k: v for k, v in after.items() if k not in ("weight_kg", "updated_at")} == {
        k: v for k, v in before.items() if k not in ("weight_kg", "updated_at")
    }
    assert db.writes == [("update", "profiles")]


def test_profile_set_unknown_option(setup):
    db = setup(profile_db())
    code, _, out = run("admin", "profile", "set", "--user-id", USER_A, "--telegram-chat-id", "1")
    assert code != 0
    assert "No such option" in out
    assert db.writes == []


@pytest.mark.parametrize("value", ["offshore", "side_offshore", "onshore,offshore"])
def test_rule_set_offshore_rejected(setup, value):
    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_favorite(db, USER_A)
    setup(db)
    code, _, out = run(
        "admin", "rule", "set", "--user-id", USER_A, "--spot", SPOT, "--dir-classes", value
    )
    assert code == 1
    assert "not allowed" in out
    assert "never ridable" in out
    assert db.writes == []


def test_favorite_add_unknown_spot(setup):
    db = setup(FakeSupabase())
    code, lines, _ = run("admin", "favorite", "add", "--user-id", USER_A, "--spot", "bestaat-niet")
    assert code == 1
    assert lines == ["favorite add: unknown spot 'bestaat-niet'"]
    assert db.writes == []


def test_profile_set_validation(setup):
    db = setup(profile_db(default_max_kn=20))
    base = ["admin", "profile", "set", "--user-id", USER_A]

    code, lines, _ = run(*base, "--min-kn", "25")
    assert code == 1 and "invalid profile" in lines[0]
    code, _, _ = run("admin", "profile", "set", "--user-id", USER_C_UNKNOWN, "--weight", "70")
    assert code == 1
    code, _, _ = run(*base, "--quiver", "2,9")
    assert code == 1
    code, _, _ = run(*base, "--weight", "20")
    assert code == 1
    code, lines, _ = run(*base, "--level", "expert")
    assert code == 1
    assert lines == ["profile set: level must be one of beginner, intermediate, advanced"]
    code, lines, _ = run(*base)
    assert code == 1 and lines == ["profile set: nothing to change"]
    assert db.writes == []

    assert run(*base, "--quiver", "")[0] == 0
    assert db.rows("profiles")[0]["quiver_m2"] == []
    assert run(*base, "--quiver", "12,9,9")[0] == 0
    assert db.rows("profiles")[0]["quiver_m2"] == [9.0, 12.0]
    assert run(*base, "--level", "Advanced")[0] == 0
    assert db.rows("profiles")[0]["level"] == "advanced"


def test_parse_quiver():
    assert parse_quiver("7 9 12") == [7.0, 9.0, 12.0]
    assert parse_quiver("9;12") == [9.0, 12.0]
    assert parse_quiver(" 10,5 ; 12 ") == [10.5, 12.0]
    assert parse_quiver("10,5 12") == [10.5, 12.0]
    assert parse_quiver("7,9,12") == [7.0, 9.0, 12.0]
    assert parse_quiver("7, 9, 12") == [7.0, 9.0, 12.0]
    assert parse_quiver("10,5") == [5.0, 10.0]
    for bad in ("10.5.5", "a", "9,,12", "1,2,5 9", "inf", "7,2"):
        with pytest.raises(AdminError):
            parse_quiver(bad)
    with pytest.raises(AdminError, match="at most 10 kites"):
        parse_quiver(" ".join(str(n) for n in range(3, 14)))


def test_quiver_comma_note(setup):
    note = quiver_comma_note("10,5")
    assert note is not None
    assert "read as 5, 10 m2" in note
    assert note.startswith("note: commas separate sizes")
    for text in ("9,12", "10,5; 12", "12", "2,9"):
        assert quiver_comma_note(text) is None
    db = setup(profile_db())
    code, lines, _ = run("admin", "profile", "set", "--user-id", USER_A, "--quiver", "10,5")
    assert code == 0
    assert lines[0].startswith("note: commas separate sizes")
    assert db.rows("profiles")[0]["quiver_m2"] == [5.0, 10.0]


def test_profile_show(setup):
    db = profile_db()
    db.update("profiles", {"telegram_chat_id": "12345"}, filters={"user_id": f"eq.{USER_A}"})
    setup(db)
    code, lines, out = run("admin", "profile", "show", "--user-id", USER_A)
    assert code == 0
    assert lines == [
        "weight_kg: 70",
        "level: advanced",
        "quiver_m2: 9,12",
        "default_min_kn: 14",
        "default_max_kn: -",
    ]
    assert "telegram" not in out.lower()
    assert "12345" not in out


def test_favorite_add_remove_list(setup):
    db = FakeSupabase()
    seed_spot(db, verified=False)
    setup(db)
    base = ["--user-id", USER_A]
    code, lines, _ = run("admin", "favorite", "add", *base, "--spot", SPOT)
    assert code == 0
    assert lines[0] == "favorite add: added test-strand"
    assert lines[1].startswith(f"note: {SPOT} is not verified")
    db.writes.clear()
    code, lines, _ = run("admin", "favorite", "add", *base, "--spot", SPOT)
    assert code == 0
    assert lines[0] == "favorite add: test-strand is already a favorite"
    assert db.writes == []
    code, lines, _ = run("admin", "favorite", "list", *base)
    assert lines == ["test-strand\tTeststrand\tnot verified\tdefault rule", "1 favorite(s)"]
    code, lines, _ = run("admin", "favorite", "remove", *base, "--spot", SPOT)
    assert (code, lines) == (0, ["favorite remove: removed test-strand (and its alert rule)"])
    code, lines, _ = run("admin", "favorite", "remove", *base, "--spot", SPOT)
    assert (code, lines) == (0, ["favorite remove: test-strand was not a favorite"])


def test_favorite_add_unknown_user(setup):
    class FkFail(FakeSupabase):
        def insert(self, table, rows, *, returning=False):
            raise DatabaseError("fk", status=409, code="23503")

    db = FkFail()
    seed_spot(db)
    setup(db)
    code, lines, _ = run("admin", "favorite", "add", "--user-id", USER_A, "--spot", SPOT)
    assert code == 1
    assert "unknown user id" in lines[0]


def test_rule_set_insert_then_update(setup):
    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_favorite(db, USER_A)
    setup(db)
    base = ["admin", "rule", "set", "--user-id", USER_A, "--spot", SPOT]
    code, lines, _ = run(*base, "--weekdays", "6,7", "--after", "17:00")
    assert code == 0
    assert lines[0] == "rule set: saved for test-strand"
    assert "days 6,7, after 17:00," in lines[1]
    (row,) = db.select("alert_rules", columns=RULE_COLUMNS)
    assert row["weekdays"] == [6, 7]
    assert row["earliest_local"] == "17:00:00"
    assert row["enabled"] is True
    assert row["min_kn"] is None and row["dir_classes"] is None
    AlertRuleOverride.from_row(row)
    code, _, _ = run(*base, "--disable")
    assert code == 0
    assert db.writes[-1] == ("update", "alert_rules")
    (row2,) = db.select("alert_rules", columns=RULE_COLUMNS)
    assert row2["enabled"] is False
    assert {k: v for k, v in row2.items() if k != "enabled"} == {
        k: v for k, v in row.items() if k != "enabled"
    }


def test_rule_set_errors(setup):
    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_spot(db, id="ander-strand", verified=True)
    seed_favorite(db, USER_A, latest_local="16:00:00")
    seed_profile(db, USER_A, default_max_kn=20)
    setup(db)
    base = ["admin", "rule", "set", "--user-id", USER_A, "--spot", SPOT]
    cases = [
        ["admin", "rule", "set", "--user-id", USER_A, "--spot", "ander-strand", "--min-kn", "12"],
        [*base, "--after", "18:00", "--before", "17:00"],
        [*base, "--after", "17:00"],
        [*base, "--weekdays", "0"],
        [*base, "--min-kn", "25"],
        [*base, "--dir-classes", "onshore,bogus"],
        base,
    ]
    for args in cases:
        code, _, out = run(*args)
        assert code == 1, args
    assert "unknown dir class" in run(*cases[5])[2]
    assert db.writes == []


# -- AC-8 -------------------------------------------------------------------------------------


def scenario():
    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_forecasts(db)
    seed_favorite(db, USER_A, min_kn=12)
    db.writes.clear()
    return db


def test_alerts_preview_writes_nothing(setup):
    db = setup(scenario())
    code, lines, _ = run("admin", "alerts", "preview", "--user-id", USER_A)
    assert code == 0
    assert db.writes == []
    assert "alerts preview: 1 favorite(s)" in lines
    assert "spot test-strand" in lines
    assert "  windows: 1" in lines
    assert "  new: Go: Teststrand" in lines
    assert "    wo 15 jul 12:00–18:00 · 14–25 kn" in lines
    run_alerts(db, now=NOW, base_url=None)
    db.writes.clear()
    code, lines, _ = run("admin", "alerts", "preview", "--user-id", USER_A)
    assert "  no change" in lines
    assert "  state: 1 active, 0 cancelled (snapshot = last reported)" in lines
    assert db.writes == []


def test_alerts_preview_not_eligible(setup):
    db = FakeSupabase()
    seed_spot(db, verified=False)
    seed_favorite(db, USER_A)
    setup(db)
    code, lines, _ = run("admin", "alerts", "preview", "--user-id", USER_A)
    assert code == 0
    assert f"spot {SPOT}: not eligible (spot not verified)" in lines

    db = FakeSupabase()
    seed_spot(db, verified=True)
    seed_favorite(db, USER_A)
    setup(db)
    code, lines, _ = run("admin", "alerts", "preview", "--user-id", USER_A)
    assert code == 0
    assert f"spot {SPOT}: not eligible (no forecast data)" in lines


def test_alerts_preview_invalid_base_url(setup, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "example.org")
    db = Counting()
    seed_spot(db, verified=True)
    seed_favorite(db, USER_A)
    setup(db)
    code, lines, out = run("admin", "alerts", "preview", "--user-id", USER_A)
    assert code == 1
    assert lines == ["alerts preview: invalid APP_BASE_URL"]
    assert "example.org" not in out
    assert db.selects == 0


def test_invalid_user_id_rejected_by_click(setup):
    setup(FakeSupabase())
    code, _, _ = run("admin", "profile", "show", "--user-id", "geen-uuid")
    assert code == 2
