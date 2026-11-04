"""Poisson Tasks' own Prove check, run against Prove built from the tree under test.

    python .github/lanes/tasks_check.py tag
    python .github/lanes/tasks_check.py label TREE
    python .github/lanes/tasks_check.py run --tasks DIR --tasks-wheel WHEEL --prove-wheel WHEEL \\
        --work DIR

Our tools depend on Prove with a floor only, so Prove checks its users before it ships. The job
``tasks-check`` runs this script on every pull request (``ci.yml``, one more need of ``gate``) and
before ``publish`` in ``release.yml``; a red check closes the gate and stops the release.

- ``tag`` asks ``git ls-remote`` for Tasks' tags, with no credential, and writes the latest release
  tag, the highest ``vX.Y.Z`` (no pre-release, no other tag), as the step output ``tag``. No such
  tag is a failure, never a fall back to main.
- ``label TREE`` rewrites the version in ``TREE``'s ``pyproject.toml`` and ``__init__.py`` to a
  local version, ``X.Y.Z+tree.<commit>``, from ``$GITHUB_SHA``. Both files or neither.
- ``run`` runs Tasks' ``scripts/release/prove_e2e.py`` from the checked-out tag, unedited, on the
  Tasks wheel, and passes only when the check exits 0 and its last line names the labelled
  version.

**The trap this script exists for.** Tasks' check makes a fresh environment and installs
``poisson-prove`` from PyPI on purpose: it drops every ``PIP_*`` setting and points pip at the
public index. A Prove installed beforehand is not the one it uses, and a wheel at a version PyPI
already holds loses the tie to PyPI's. Either way the check goes green against the release already
out and says nothing about the tree. So the wheel is built under a local version label, which PyPI
cannot hold, and offered through ``find-links`` in a pip config at ``$XDG_CONFIG_HOME``, which the
check's scrub leaves alone (the runner is Linux, where pip reads that file); the job then fails
unless the check's own last line, ``PROVE E2E OK: poisson-tasks A + poisson-prove B``, names that
version. Standard library only, so it runs from the job's Python with nothing installed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = "https://github.com/poisson-labs/tasks.git"
CHECK = Path("scripts") / "release" / "prove_e2e.py"
#: A release tag as ``git ls-remote --tags`` lists it; a peeled entry (``^{}``) does not match.
RELEASE_TAG = re.compile(r"[0-9a-f]{40}\trefs/tags/(v(\d+)\.(\d+)\.(\d+))\n?")
#: The version files the label rewrites, each with the one line it changes.
VERSION_LINES = (
    (Path("pyproject.toml"), re.compile(r'^(version = ")([^"+]+)(")$', re.MULTILINE)),
    (
        Path("src") / "poisson_prove" / "__init__.py",
        re.compile(r'^(__version__ = ")([^"+]+)(")$', re.MULTILINE),
    ),
)
#: What a green check's last line says, up to the Prove version, which must be the labelled one.
OK_LINE = re.compile(r"PROVE E2E OK: poisson-tasks \S+ \+ poisson-prove (\S+)")


def fail(message: str, code: int = 2) -> int:
    print(f"error: {message}", file=sys.stderr, flush=True)
    return code


# ---------- tag ----------


def latest_tag(listing: str) -> str:
    """The highest ``vX.Y.Z`` in a ``git ls-remote --tags`` listing, by number; a ``ValueError``
    when there is none."""
    found = []
    for line in listing.splitlines():
        match = RELEASE_TAG.fullmatch(line)
        if match:
            found.append((tuple(int(n) for n in match.groups()[1:]), match.group(1)))
    if not found:
        raise ValueError(f"no release tag vX.Y.Z at {TASKS}")
    return max(found)[1]


def tag() -> int:
    listed = subprocess.run(
        ["git", "ls-remote", "--tags", TASKS], capture_output=True, text=True, check=False
    )
    if listed.returncode != 0:
        return fail(f"git ls-remote failed ({listed.returncode}): {listed.stderr.strip()}")
    try:
        chosen = latest_tag(listed.stdout)
    except ValueError as exc:
        return fail(str(exc))
    print(f"tag  {chosen}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as out:
            out.write(f"tag={chosen}\n")
    return 0


# ---------- label ----------


def label(tree: Path) -> int:
    sha = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        return fail("no commit to name: $GITHUB_SHA is not set")
    if not tree.is_dir():
        return fail(f"no tree at {tree}")
    rewritten: list[tuple[Path, str]] = []
    versions = set()
    for name, pattern in VERSION_LINES:
        path = tree / name
        if not path.is_file():
            return fail(f"no {name} in {tree}")
        text = path.read_text(encoding="utf-8")
        found = pattern.findall(text)
        if len(found) != 1:
            return fail(f"{name} does not name one version")
        versions.add(found[0][1])
        rewritten.append((path, pattern.sub(rf"\g<1>\g<2>+tree.{sha[:7]}\g<3>", text, count=1)))
    if len(versions) != 1:
        return fail(f"the version files disagree: {', '.join(sorted(versions))}")
    for path, text in rewritten:
        path.write_text(text, encoding="utf-8")
    print(f"version  {versions.pop()}+tree.{sha[:7]}")
    return 0


# ---------- run ----------


def wheel_version(wheel: Path, project: str) -> str | None:
    match = re.fullmatch(rf"{project}-(.+?)-py3-none-any\.whl", wheel.name)
    return None if match is None else match.group(1)


def run(tasks: Path, tasks_wheel: Path, prove_wheel: Path, work: Path) -> int:
    version = wheel_version(prove_wheel, "poisson_prove")
    if version is None or not prove_wheel.is_file():
        return fail(f"{prove_wheel} is not a poisson_prove wheel")
    if "+tree." not in version:
        return fail(
            f"the wheel is {version}, a version PyPI may hold, so the check could install PyPI's "
            f"in its place; label the tree first"
        )
    if wheel_version(tasks_wheel, "poisson_tasks") is None or not tasks_wheel.is_file():
        return fail(f"{tasks_wheel} is not a poisson_tasks wheel")
    script = tasks / CHECK
    if not script.is_file():
        return fail(f"no check at {script}: the Tasks tag has no {CHECK}")
    print(f"check  {script}")
    print(f"prove  {prove_wheel.name}")
    print(f"tasks  {tasks_wheel.name}", flush=True)
    with tempfile.TemporaryDirectory(prefix="tasks-check-") as config:
        pip = Path(config) / "pip"
        pip.mkdir()
        (pip / "pip.conf").write_text(
            f"[global]\nfind-links = {prove_wheel.resolve().parent}\n", encoding="utf-8"
        )
        env = {**os.environ, "XDG_CONFIG_HOME": config}
        argv = [sys.executable, str(script), "--wheel", str(tasks_wheel), "--work", str(work)]
        with subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, text=True) as child:
            last = ""
            assert child.stdout is not None
            for line in child.stdout:
                print(line, end="", flush=True)
                if line.strip():
                    last = line.rstrip("\n")
            code = child.wait()
    if code != 0:
        return fail(f"the check exited {code}", 1)
    named = OK_LINE.fullmatch(last)
    if named is None or named.group(1) != version:
        return fail(
            f"the check did not end by naming poisson-prove {version}; its last line was {last!r}",
            1,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("tag", help="write Tasks' latest release tag as the step output tag")
    labelled = verbs.add_parser("label", help="give TREE a local version from $GITHUB_SHA")
    labelled.add_argument("tree", type=Path)
    running = verbs.add_parser("run", help="run Tasks' check on the labelled Prove wheel")
    running.add_argument("--tasks", required=True, type=Path, help="the Tasks checkout")
    running.add_argument("--tasks-wheel", required=True, type=Path, help="the wheel built from it")
    running.add_argument("--prove-wheel", required=True, type=Path, help="the labelled Prove wheel")
    running.add_argument("--work", required=True, type=Path, help="an empty folder for the check")
    a = parser.parse_args()
    if a.verb == "tag":
        return tag()
    if a.verb == "label":
        return label(a.tree)
    return run(a.tasks, a.tasks_wheel, a.prove_wheel, a.work)


if __name__ == "__main__":
    sys.exit(main())
