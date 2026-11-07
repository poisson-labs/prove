"""Remote backends, C9 invariant F5: no test is retried. A flaky test is read for its cause and fixed;
nothing in the suite, its configuration or CI reruns a failure, marks a test flaky or installs a
plugin that does.

The scan reads every Python file under ``tests/``, ``pyproject.toml`` and every workflow and lane
script under ``.github/``, and looks for the rerun plugins' names, their options and their markers.
This file is the one place the words appear, so it is left out of its own scan.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
#: The rerun plugins (pytest-rerunfailures, flaky, pytest-retry, pytest-flakefinder's rerun) by
#: their distribution and import names, their command-line options and their markers.
RETRY = re.compile(
    r"rerunfailures|pytest[-_]retry|flakefinder|--reruns|--only-rerun|--retries|--retry-delay"
    r"|mark\.flaky|mark\.retry|^\s*(?:from|import)\s+flaky\b|[\"']flaky[\"'<>=~! ]"
    r"|-p\s+(?:flaky|rerunfailures|retry)\b",
    re.MULTILINE,
)


def _scanned() -> list[Path]:
    files = sorted((REPO / "tests").rglob("*.py"))
    files += [REPO / "pyproject.toml"]
    files += sorted(p for p in (REPO / ".github").rglob("*") if p.is_file() and p.suffix in (".py", ".yml", ".yaml"))
    me = Path(__file__).resolve()
    return [p for p in files if p.resolve() != me]


def test_f5_no_retry_rerun_or_flaky_marker_anywhere_in_the_suite() -> None:
    found = []
    for path in _scanned():
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in RETRY.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            found.append(f"{path.relative_to(REPO)}:{line}: {match.group(0).strip()}")
    assert found == [], found


def test_f5_the_scan_finds_what_it_looks_for() -> None:
    """The pattern catches each way a retry gets in, so an empty scan means something."""
    planted = [
        "@pytest.mark.flaky(reruns=3)",
        "import flaky",
        "from flaky import flaky",
        '"pytest-rerunfailures>=14"',
        '"flaky>=3"',
        "addopts = --reruns 2",
        "pytest -p rerunfailures",
        "@pytest.mark.retry(2)",
        '"pytest-retry"',
    ]
    for line in planted:
        assert RETRY.search(line), line
    for innocent in ("the flake's cause", "a flaky test is read for its cause", "retries = 2", "infra_retries=0"):
        assert not RETRY.search(innocent), innocent
