"""Structure and secret hygiene of .github/workflows/hourly.yml (WP-11 AC-4)."""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
HOURLY = WORKFLOWS / "hourly.yml"


@pytest.fixture(scope="module")
def doc() -> dict:
    return yaml.safe_load(HOURLY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def job(doc) -> dict:
    return doc["jobs"]["run"]


def test_triggers(doc):
    triggers = doc.get("on", doc.get(True))
    assert triggers["schedule"] == [{"cron": "17 * * * *"}]
    assert "workflow_dispatch" in triggers


def test_concurrency_and_permissions(doc):
    assert doc["concurrency"] == {"group": "hourly", "cancel-in-progress": False}
    assert doc["permissions"] == {"contents": "read"}


def test_job_settings(job):
    assert job["timeout-minutes"] == 15
    assert job["defaults"]["run"]["working-directory"] == "ingest"
    assert "vars.HOURLY_ENABLED == 'true'" in job["if"]


def test_pipeline_step_env(job):
    (step,) = [s for s in job["steps"] if s.get("run") == "uv run shakka run-hourly"]
    assert step["env"] == {
        "SUPABASE_URL": "${{ secrets.SUPABASE_URL }}",
        "SUPABASE_SECRET_KEY": "${{ secrets.SUPABASE_SECRET_KEY }}",
        "VAPID_PUBLIC_KEY": "${{ secrets.VAPID_PUBLIC_KEY }}",
        "VAPID_PRIVATE_KEY": "${{ secrets.VAPID_PRIVATE_KEY }}",
        "VAPID_SUBJECT": "${{ secrets.VAPID_SUBJECT }}",
        "OPERATOR_USER_ID": "${{ secrets.OPERATOR_USER_ID }}",
        "APP_BASE_URL": "${{ vars.APP_BASE_URL }}",
    }
    assert "env" not in job or not any("secrets." in str(v) for v in job["env"].values())


def test_checkout_uses_main(job):
    checkout = next(
        s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")
    )
    assert "'main'" in checkout["with"]["ref"]


def test_activity_step_skipped_when_sync_fails(job):
    sync = next(s for s in job["steps"] if s.get("run") == "uv sync")
    activity = next(s for s in job["steps"] if "shakka check-activity" in s.get("run", ""))
    assert f"steps.{sync['id']}.outcome == 'success'" in activity["if"]
    assert "!cancelled()" in activity["if"]


def test_only_known_secrets():
    names = set(re.findall(r"secrets\.([A-Z_]+)", HOURLY.read_text(encoding="utf-8")))
    assert names == {
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "VAPID_PUBLIC_KEY",
        "VAPID_PRIVATE_KEY",
        "VAPID_SUBJECT",
        "OPERATOR_USER_ID",
    }


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_no_literal_secrets_or_telegram(path):
    text = path.read_text(encoding="utf-8")
    assert "sb_secret_" not in text
    assert "telegram" not in text.lower()
