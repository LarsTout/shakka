"""Tests for logging setup, secret redaction and GitHub annotations (WP-11)."""

import io
import logging
import sys

import httpx
import pytest

from shakka.config import Settings
from shakka.db import SupabaseRest
from shakka.logsetup import (
    LOG_DATEFMT,
    LOG_FORMAT,
    QUIET_LOGGERS,
    RedactingFormatter,
    configure_logging,
    escape_command_data,
    github_annotation,
    redact,
    secret_values,
)

SECRET = "sb_secret_TESTVALUE"
USER = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    quiet = {n: logging.getLogger(n).level for n in QUIET_LOGGERS}
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    for name, lvl in quiet.items():
        logging.getLogger(name).setLevel(lvl)


def test_redact_replaces_secret():
    assert redact(f"key={SECRET}!", [SECRET]) == "key=***!"


def test_redact_ignores_short_values():
    assert redact("abc1234 here", ["abc1234", ""]) == "abc1234 here"


def test_secret_values():
    s = Settings(
        supabase_url="http://127.0.0.1:54321",
        supabase_secret_key=SECRET,
        vapid_private_key="v" * 10,
    )
    assert secret_values(s) == (SECRET, "v" * 10)
    s2 = Settings(supabase_url="http://127.0.0.1:54321", supabase_secret_key=SECRET)
    assert secret_values(s2) == (SECRET,)
    s3 = Settings(
        supabase_url="http://127.0.0.1:54321",
        supabase_secret_key=SECRET,
        vapid_subject=" mailto:test@example.org ",
    )
    assert secret_values(s3) == (SECRET, "mailto:test@example.org")
    s4 = Settings(
        supabase_url="http://127.0.0.1:54321",
        supabase_secret_key=SECRET,
        vapid_subject="mailto:",
    )
    assert "mailto:" in secret_values(s4)
    assert redact("x mailto: y", secret_values(s4)) == "x mailto: y"  # shorter than 8


def test_redacting_formatter():
    fmt = RedactingFormatter(LOG_FORMAT, LOG_DATEFMT, secrets=[SECRET])
    try:
        raise RuntimeError(f"boom {SECRET}")
    except RuntimeError:
        record = logging.LogRecord(
            "t", logging.ERROR, __file__, 1, f"leak {SECRET}", None, sys.exc_info()
        )
    out = fmt.format(record)
    assert SECRET not in out
    assert "***" in out
    assert " ERROR t leak ***" in out


def test_redacting_handler_output(restore_logging):
    stream = io.StringIO()
    configure_logging(stream=stream, secrets=[SECRET])
    logging.getLogger("x").info("value %s", SECRET)
    assert SECRET not in stream.getvalue()
    assert "***" in stream.getvalue()


def test_configure_logging_idempotent(restore_logging):
    configure_logging(stream=io.StringIO())
    configure_logging(stream=io.StringIO())
    ours = [h for h in logging.getLogger().handlers if getattr(h, "_shakka_handler", False)]
    assert len(ours) == 1


def test_httpx_and_httpcore_quiet(restore_logging, caplog):
    configure_logging(stream=io.StringIO())
    caplog.set_level(logging.DEBUG)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    db = SupabaseRest("http://127.0.0.1:54321", SECRET, client=client)
    db.select("profiles", filters={"user_id": f"eq.{USER}"})
    assert USER not in caplog.text
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("urllib3").level == logging.WARNING


def test_github_annotation_escapes():
    assert github_annotation("warning", "83% of\r\nthe guard") == "::warning::83%25 of  the guard"
    assert escape_command_data("%0A") == "%250A"
    assert github_annotation("error", "x") == "::error::x"
