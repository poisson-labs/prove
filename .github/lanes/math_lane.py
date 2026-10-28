"""Whether a pull request runs the math suite, and why.

    python .github/lanes/math_lane.py BASE_SHA HEAD_SHA

The math suite runs on a pull request that changes the statistics code, a test of the math suite,
or the version the requirements resolve to of a library the statistics rest on. The files and
libraries are the ones the ``math`` marker's own description in ``pyproject.toml`` names, so the
marker and this lane cannot drift apart. The resolved versions are compared by resolving the base's
``pyproject.toml`` and the head's at the same moment, so a change the index makes on its own is
not the pull request's; the nightly run catches that one.

Writes ``math=true`` or ``math=false`` to ``$GITHUB_OUTPUT`` and the reasons to the job summary.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path

PACKAGE = "src/poisson_prove/"


def marker_text(pyproject: str) -> str:
    markers = tomllib.loads(pyproject)["tool"]["pytest"]["ini_options"]["markers"]
    (text,) = [m for m in markers if m.startswith("math:")]
    return text


def trigger_files(pyproject: str) -> list[str]:
    """The statistics files the marker names: ``(src/poisson_prove/stats.py, survival.py, ...)``."""
    found = re.search(r"statistics code \(([^)]*)\)", marker_text(pyproject))
    assert found, "the math marker no longer names its statistics files"
    names = [name.strip() for name in found.group(1).split(",")]
    return [name if name.startswith(PACKAGE) else PACKAGE + name for name in names]


def trigger_libraries(pyproject: str) -> list[str]:
    """The libraries the marker names: ``the resolved numpy, scipy, ... or statsmodels``."""
    found = re.search(r"the resolved ([a-z, ]+?) or ([a-z]+)\b", marker_text(pyproject))
    assert found, "the math marker no longer names its libraries"
    return [name.strip() for name in found.group(1).split(",")] + [found.group(2)]


def reasons(
    changed: Iterable[str],
    math_tests: Iterable[str],
    base: Mapping[str, str],
    head: Mapping[str, str],
    pyproject: str,
) -> list[str]:
    """Why this pull request runs the math suite; empty when it does not."""
    changed = set(changed)
    out = [f"changes {path}" for path in sorted(changed & set(trigger_files(pyproject)))]
    out += [
        f"changes {path}, a test of the math suite" for path in sorted(changed & set(math_tests))
    ]
    for library in trigger_libraries(pyproject):
        if base.get(library) != head.get(library):
            here, there = head.get(library), base.get(library)
            out.append(f"{library} resolves to {here} here and {there} on the base")
    return out


def resolved(pyproject: str) -> dict[str, str]:
    """Every pinned version ``uv pip compile`` resolves the project with all its extras to, for
    Python 3.11, the lowest Python Prove supports."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "pyproject.toml"
        path.write_text(pyproject, encoding="utf-8")
        done = subprocess.run(
            [
                "uv",
                "pip",
                "compile",
                "--quiet",
                "--no-header",
                "--all-extras",
                "--python-version",
                "3.11",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    pins = {}
    for line in done.stdout.splitlines():
        if "==" in line and not line.lstrip().startswith("#"):
            name, version = line.split("==", 1)
            pins[re.sub(r"[-_.]+", "-", name.strip()).lower()] = version.split()[0]
    return pins


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main(base_sha: str, head_sha: str) -> int:
    changed = git("diff", "--name-only", f"{base_sha}...{head_sha}").split()
    math_tests = git(
        "grep", "-l", "-E", r"mark\.(math|calibration)", head_sha, "--", "tests"
    ).split()
    math_tests = [name.split(":", 1)[1] for name in math_tests]
    base_pyproject, head_pyproject = (
        git("show", f"{base_sha}:pyproject.toml"),
        git("show", f"{head_sha}:pyproject.toml"),
    )
    why = reasons(
        changed, math_tests, resolved(base_pyproject), resolved(head_pyproject), head_pyproject
    )
    text = "### Math suite\n\n" + (
        "".join(f"- runs: {r}\n" for r in why)
        if why
        else "- not run: no statistics file, math test or resolved version changed\n"
    )
    print(text, end="")
    for name, value in (
        ("GITHUB_OUTPUT", f"math={'true' if why else 'false'}\n"),
        ("GITHUB_STEP_SUMMARY", text),
    ):
        if os.environ.get(name):
            with open(os.environ[name], "a", encoding="utf-8") as out:
                out.write(value)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
