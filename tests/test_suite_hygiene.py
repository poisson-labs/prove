"""The suite's own hygiene: every property test is the same run every time, is never timed and
writes nothing into the working directory, and what the test modules share leaves no folder behind.

The property tests take their settings from one profile, ``prove``, registered and loaded in
``conftest.py``; a test's own ``settings(...)`` may change how many examples it draws and which
health checks it suppresses, never the seed, the deadline or the database.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from hypothesis import settings
from hypothesis.configuration import storage_directory

TESTS = Path(__file__).resolve().parent
#: What the ``prove`` profile settles for every property test.
PROFILE_ONLY = frozenset({"derandomize", "deadline", "database"})


def settings_calls_naming(names: frozenset[str]) -> list[str]:
    """Every ``settings(...)`` call in the suite's source that passes one of ``names``, as
    ``file:line keyword``."""
    found = []
    for path in sorted(TESTS.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Name) and func.id == "settings") or (isinstance(func, ast.Attribute) and func.attr == "settings"):
                found += [f"{path.relative_to(TESTS)}:{node.lineno} {k.arg}" for k in node.keywords if k.arg in names]
    return found


def test_every_property_test_draws_from_a_fixed_seed_with_no_deadline_and_no_database() -> None:
    current = settings()
    assert current.derandomize is True
    assert current.deadline is None
    assert current.database is None
    assert settings_calls_naming(PROFILE_ONLY) == []


def test_hypothesis_writes_nothing_into_the_working_directory() -> None:
    home = storage_directory(intent_to_write=False).path.resolve()
    cwd = Path.cwd().resolve()
    assert home != cwd / ".hypothesis" and cwd not in home.parents, home


def test_the_quickstart_design_a_test_module_reads_is_gone_when_its_process_ends() -> None:
    script = (f"import sys; sys.path.insert(0, {str(TESTS)!r}); import conftest; path = conftest.quickstart_design(7); "
              "assert 'replicates = 7' in path.read_text(encoding='utf-8'); print(path)")
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120, env=dict(os.environ))
    assert done.returncode == 0, done.stderr
    path = Path(done.stdout.strip().splitlines()[-1])
    assert path.name == "quickstart.toml"
    assert not path.parent.exists(), path.parent
