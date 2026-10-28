"""Enforces that shakka.domain stays pure: no I/O, no clock, no randomness."""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

import shakka.domain

FORBIDDEN_MODULES = frozenset(
    {
        # contract
        "httpx",
        "ddlpy",
        "pywebpush",
        "yaml",
        "os",
        "socket",
        "subprocess",
        "urllib",
        "http",
        "pathlib",
        # I/O, process state or non-determinism
        "io",
        "shutil",
        "tempfile",
        "glob",
        "sqlite3",
        "ssl",
        "asyncio",
        "threading",
        "multiprocessing",
        "concurrent",
        "signal",
        "ctypes",
        "importlib",
        "sys",
        "time",
        "random",
        "secrets",
    }
)
ALLOWED_THIRD_PARTY = frozenset({"pydantic", "astral"})
DOMAIN_PACKAGE = "shakka.domain"
FORBIDDEN_BUILTIN_CALLS = frozenset({"open", "__import__", "eval", "exec"})
FORBIDDEN_CALL_ATTRS = frozenset({"now", "today", "utcnow"})
CLOCK_ATTRS = frozenset({"now", "today"})
GETATTR_CLOCK = frozenset({"now", "today", "utcnow"})
CLOCK_CLASSES = frozenset({"datetime", "date"})


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str  # "forbidden_import" | "forbidden_call" | "syntax_error"
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


def _name_allowed(name: str) -> bool:
    top = name.split(".")[0]
    if name == DOMAIN_PACKAGE or name.startswith(DOMAIN_PACKAGE + "."):
        return True
    if top in ALLOWED_THIRD_PARTY:
        return True
    return top in sys.stdlib_module_names and top not in FORBIDDEN_MODULES


def _resolve_relative(module: str, is_package: bool, level: int, target: str | None) -> str | None:
    parts = module.split(".")
    base = parts if is_package else parts[:-1]
    drop = level - 1
    if drop > len(base) - 1:  # would go past the top-level "shakka" package
        return None
    base = base[: len(base) - drop]
    if target:
        base = [*base, target]
    return ".".join(base)


def check_source(
    source: str,
    *,
    module: str = "shakka.domain.probe",
    is_package: bool = False,
    path: str = "<string>",
) -> list[Violation]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Violation(path, exc.lineno or 0, "syntax_error", exc.msg)]

    violations: list[Violation] = []
    class_aliases, module_aliases = _datetime_aliases(tree)
    call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}

    def bad_import(line: int, name: str) -> None:
        violations.append(Violation(path, line, "forbidden_import", name))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _name_allowed(alias.name):
                    bad_import(node.lineno, alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = _resolve_relative(module, is_package, node.level, node.module)
                if base is None:
                    bad_import(node.lineno, "." * node.level + (node.module or ""))
                    continue
            else:
                base = node.module or ""
            if base == "shakka":
                for alias in node.names:
                    full = f"{base}.{alias.name}"
                    if not _name_allowed(full):
                        bad_import(node.lineno, full)
            elif not _name_allowed(base):
                bad_import(node.lineno, base)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_BUILTIN_CALLS:
                violations.append(Violation(path, node.lineno, "forbidden_call", func.id))
            elif isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CALL_ATTRS:
                violations.append(Violation(path, node.lineno, "forbidden_call", func.attr))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in GETATTR_CLOCK
        ):
            violations.append(
                Violation(path, node.lineno, "forbidden_call", f"getattr {node.args[1].value}")
            )
        if isinstance(node, ast.Attribute):
            owner = _clock_owner(node, class_aliases, module_aliases)
            if owner and id(node) not in call_funcs:
                violations.append(
                    Violation(path, node.lineno, "forbidden_call", f"{owner}.{node.attr}")
                )
            if node.attr == "utcnow" and not _is_call_func(tree, node):
                violations.append(Violation(path, node.lineno, "forbidden_call", "utcnow"))
            elif (
                node.attr == "time" and isinstance(node.value, ast.Name) and node.value.id == "time"
            ):
                violations.append(Violation(path, node.lineno, "forbidden_call", "time.time"))
    return violations


def _datetime_aliases(tree: ast.AST) -> tuple[dict[str, str], set[str]]:
    """Names bound to the datetime/date classes, and names bound to the datetime module."""
    classes = {c: c for c in CLOCK_CLASSES}
    modules = {"datetime"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime" and not node.level:
            for alias in node.names:
                if alias.name in CLOCK_CLASSES:
                    classes[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime" and alias.asname:
                    modules.add(alias.asname)
    return classes, modules


def _clock_owner(
    node: ast.Attribute, class_aliases: dict[str, str], module_aliases: set[str]
) -> str | None:
    """'datetime' or 'date' if node is <class>.now/today, else None."""
    if node.attr not in CLOCK_ATTRS:
        return None
    value = node.value
    if isinstance(value, ast.Name) and value.id in class_aliases:
        return class_aliases[value.id]
    if (
        isinstance(value, ast.Attribute)
        and value.attr in CLOCK_CLASSES
        and isinstance(value.value, ast.Name)
        and value.value.id in module_aliases
    ):
        return value.attr
    return None


def _is_call_func(tree: ast.AST, attr: ast.Attribute) -> bool:
    """True if attr is the func of a Call (already reported by the call rule)."""
    return any(isinstance(n, ast.Call) and n.func is attr for n in ast.walk(tree))


def module_name_for(file: Path, src_root: Path) -> tuple[str, bool]:
    rel = file.relative_to(src_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        return ".".join(parts[:-1]), True
    return ".".join(parts), False


def test_domain_package_is_pure() -> None:
    domain_dir = Path(shakka.domain.__file__).parent
    src_root = domain_dir.parent.parent
    files = sorted(domain_dir.rglob("*.py"))
    assert files, f"no python files found under {domain_dir}"
    violations: list[Violation] = []
    for file in files:
        module, is_package = module_name_for(file, src_root)
        violations += check_source(
            file.read_text(encoding="utf-8"),
            module=module,
            is_package=is_package,
            path=str(file),
        )
    assert not violations, "\n".join(str(v) for v in violations)


@pytest.mark.parametrize(
    "source",
    [
        "import httpx",
        "from os import environ",
        "from datetime import datetime\nx = datetime.now()\n",
        'open("x")',
        "import os.path",
        "import yaml",
        "import pathlib",
        "from urllib.parse import urlsplit",
        "import http.client",
        "import requests",
        "import shakka",
        "from shakka import http",
        "from shakka.db import SupabaseRest",
        "from .. import db",
        "from ..jobs import evaluate",
        "from datetime import date\nd = date.today()\n",
        "from datetime import datetime\nx = datetime.utcnow()\n",
        "import time\nt = time.time()\n",
        '__import__("os")',
        "def f(:",
        "from datetime import datetime\nfrom pydantic import Field\n"
        "x = Field(default_factory=datetime.now)\n",
        "x = date.today\n",
        "f = datetime.today\n",
        "from datetime import datetime as dt\nf = dt.now\n",
        "from datetime import date as d\nf = d.today\n",
        "import datetime\nf = datetime.datetime.now\n",
        "import datetime as m\nf = m.date.today\n",
        "f = getattr(datetime, 'now')\n",
    ],
)
def test_checker_flags(source: str) -> None:
    assert check_source(source), source


@pytest.mark.parametrize(
    "source",
    [
        "from pydantic import BaseModel",
        "from pydantic import BaseModel, ConfigDict",
        "from datetime import UTC, datetime, time, timedelta",
        "from zoneinfo import ZoneInfo",
        "import math",
        "from astral.sun import sun",
        "from shakka.domain.spot import Level",
        "from . import spot",
        "from .spot import Level",
        "def f(now):\n    return now\n",
        "from datetime import datetime\n",
        "def f(stats):\n    return stats.now\n",
        "def f(self):\n    return self.now.tzinfo\n",
        "def f(x, name):\n    return getattr(x, name)\n",
    ],
)
def test_checker_allows(source: str) -> None:
    assert check_source(source) == [], source


def test_checker_reports_reference_once() -> None:
    assert len(check_source("x = datetime.now()\n")) == 1
