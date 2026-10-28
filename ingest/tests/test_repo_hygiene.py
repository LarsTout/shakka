"""Secret hygiene and repo contract checks."""

import re
import subprocess

import yaml

from shakka.config import REPO_ROOT

# The JWT fragment is concatenated so this file does not match its own pattern.
PATTERN = r"sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|" + "eyJhbGci" + "Oi"

DEPENDABOT_UPDATES = {("github-actions", "/"), ("npm", "/web"), ("uv", "/ingest")}

ENV_KEYS = [
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "APP_BASE_URL",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
    "OPERATOR_USER_ID",
]


def test_env_example_exact():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    pairs = [
        line.split("=", 1) for line in lines if line.strip() and not line.lstrip().startswith("#")
    ]
    assert [k for k, _ in pairs] == ENV_KEYS
    for key, value in pairs:
        assert value == ("mailto:" if key == "VAPID_SUBJECT" else ""), key


def test_no_telegram_in_ingest_src_and_env_example():
    paths = [*(REPO_ROOT / "ingest" / "src").rglob("*.py"), REPO_ROOT / ".env.example"]
    assert paths
    offenders = [str(p) for p in paths if "telegram" in p.read_text(encoding="utf-8").lower()]
    assert offenders == []


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
        "web:",
        "working-directory: web",
        "- run: npm ci",
        "- run: npm run check",
        "- run: npm test",
        "- run: npm run build",
        "- run: npm run verify:build",
        "- run: bash ../scripts/check-no-client-openmeteo.sh",
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


def test_actions_pinned_to_commit_sha():
    pattern = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
    uses = []
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        for match in re.finditer(r"^\s*-?\s*uses:\s*(\S+)", path.read_text(encoding="utf-8"), re.M):
            uses.append((path.name, match.group(1)))
    assert uses
    unpinned = [f"{name}: {ref}" for name, ref in uses if not pattern.fullmatch(ref)]
    assert unpinned == []


def test_dependabot_config() -> None:
    path = REPO_ROOT / ".github" / "dependabot.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    updates = data["updates"]
    assert len(updates) == 3
    assert {(u["package-ecosystem"], u["directory"]) for u in updates} == DEPENDABOT_UPDATES
    for u in updates:
        assert u["schedule"]["interval"] == "monthly", u["package-ecosystem"]
        assert u["target-branch"] == "develop", u["package-ecosystem"]
        assert u["open-pull-requests-limit"] == 3, u["package-ecosystem"]
        assert isinstance(u["groups"], dict) and u["groups"], u["package-ecosystem"]
        for name, group in u["groups"].items():
            assert group["patterns"] == ["*"], name


def test_actions_pins_have_version_comment() -> None:
    uses_line = re.compile(r"^\s*-?\s*uses:")
    valid = re.compile(r"^\s*-?\s*uses:\s*[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+(\.\d+){0,2}\s*$")
    seen = 0
    bad = []
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if not uses_line.match(line):
                continue
            seen += 1
            if not valid.fullmatch(line):
                bad.append(f"{path.name}:{number}")
    assert seen
    assert bad == []
