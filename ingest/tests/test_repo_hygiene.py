"""Secret hygiene and repo contract checks."""

import subprocess

from shakka.config import REPO_ROOT

# The JWT fragment is concatenated so this file does not match its own pattern.
PATTERN = r"sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|" + "eyJhbGci" + "Oi"

ENV_KEYS = [
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "APP_BASE_URL",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
]


def test_env_example_exact():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    pairs = [
        line.split("=", 1) for line in lines if line.strip() and not line.lstrip().startswith("#")
    ]
    assert [k for k, _ in pairs] == ENV_KEYS
    for key, value in pairs:
        assert value == ("mailto:" if key == "VAPID_SUBJECT" else ""), key


def test_no_keys_in_repo():
    result = subprocess.run(
        ["git", "grep", "--untracked", "-nE", PATTERN, "--", ".", ":!docs"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 1:
        return
    # Do not echo matched content for a secret scan: only file:line locations.
    if result.returncode == 0:
        locations = [":".join(m.split(":", 2)[:2]) for m in result.stdout.splitlines()]
        raise AssertionError("possible secret in: " + ", ".join(locations))
    raise AssertionError(f"git grep failed: {result.stderr}")


def test_supabase_config_exists():
    assert (REPO_ROOT / "supabase" / "config.toml").is_file()


def test_gitignore_has_supabase_entries():
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "supabase/.temp/" in lines
    assert "supabase/.branches/" in lines


def test_ci_workflow_contract():
    lines = {
        line.strip()
        for line in (REPO_ROOT / ".github" / "workflows" / "ci.yml")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    for expected in (
        "push:",
        "pull_request:",
        "ingest:",
        "working-directory: ingest",
        "- run: uv sync",
        "- run: uv run ruff check .",
        "- run: uv run ruff format --check .",
        "- run: uv run pytest",
        "db:",
        "- run: supabase test db",
    ):
        assert expected in lines, expected


def test_supabase_config_disables_auto_expose():
    text = (REPO_ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    start = lines.index("[api]")
    section: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("["):
            break
        section.append(line)
    assert "auto_expose_new_tables = false" in section
