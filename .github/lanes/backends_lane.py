"""Whether a change runs the backend tests (the Burla and Modal fakes), and why.

    python .github/lanes/backends_lane.py BASE_SHA HEAD_SHA

The backend tests run when a change touches backend code: the Modal and Burla executors, the
shared runner they drive, the fake Burla client under ``tests/bu_fixtures/``, a test file of the
gate's ``backends`` entry (``$SHARDS``, read with ``shards.py``), or the version the requirements
resolve to of Modal or Burla. Versions are resolved the way ``math_lane.py`` resolves them, the
base's ``pyproject.toml`` and the head's at the same moment. The nightly run runs the backend tests
whatever changed, so a change that reaches a backend through another file is caught there.

Writes ``backends=true`` or ``backends=false`` to ``$GITHUB_OUTPUT`` and the reasons to the job
summary.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Mapping

from math_lane import git, resolved
from shards import BACKENDS, parse

#: The backend code, beside the backend tests themselves.
SOURCES = (
    "src/poisson_prove/executor.py",
    "src/poisson_prove/executor_burla.py",
    "src/poisson_prove/_burla_submit.py",
    "src/poisson_prove/executor_modal.py",
)
FAKES = "tests/bu_fixtures/"
LIBRARIES = ("modal", "burla")


def reasons(
    changed: Iterable[str],
    backend_tests: Iterable[str],
    base: Mapping[str, str],
    head: Mapping[str, str],
) -> list[str]:
    """Why this change runs the backend tests; empty when it does not."""
    changed = set(changed)
    out = [f"changes {path}" for path in sorted(changed & set(SOURCES))]
    fakes = sorted(path for path in changed if path.startswith(FAKES))
    out += [f"changes {path}, a fake backend" for path in fakes]
    out += [f"changes {path}, a backend test" for path in sorted(changed & set(backend_tests))]
    for library in LIBRARIES:
        if base.get(library) != head.get(library):
            here, there = head.get(library), base.get(library)
            out.append(f"{library} resolves to {here} here and {there} on the base")
    return out


def main(base_sha: str, head_sha: str) -> int:
    changed = git("diff", "--name-only", f"{base_sha}...{head_sha}").split()
    backend_tests = parse(os.environ["SHARDS"])[BACKENDS]
    base_pyproject, head_pyproject = (
        git("show", f"{base_sha}:pyproject.toml"),
        git("show", f"{head_sha}:pyproject.toml"),
    )
    why = reasons(changed, backend_tests, resolved(base_pyproject), resolved(head_pyproject))
    text = "### Backend tests\n\n" + (
        "".join(f"- runs: {r}\n" for r in why)
        if why
        else "- not run: no backend file, fake, backend test or resolved Modal or Burla changed\n"
    )
    print(text, end="")
    for name, value in (
        ("GITHUB_OUTPUT", f"backends={'true' if why else 'false'}\n"),
        ("GITHUB_STEP_SUMMARY", text),
    ):
        if os.environ.get(name):
            with open(os.environ[name], "a", encoding="utf-8") as out:
                out.write(value)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
