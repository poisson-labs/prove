"""The job that runs Poisson Tasks' own Prove check against Prove built from the tree under test.

Our tools depend on Prove with a floor only, so Prove checks its users before it ships: this job
runs on every pull request and, in ``release.yml``, before the publish job, and a failure stops the
release. It sits beside ``test_pf10_ci.py`` and reads the workflows the same way.

**What is pinned.** The parsed workflows, and ``.github/lanes/tasks_check.py``, which is run on
made-up inputs: a made-up ``git``, a made-up copy of the check, and a copy of this repository's
version files. Whether the job really goes green on a hosted runner is not something a test here
can see; the pull request that adds it is that check.

**The one trap this file exists for.** Tasks' check makes a fresh environment and installs
``poisson-prove`` from PyPI, on purpose: it scrubs every ``PIP_*`` setting. Prove installed beforehand
is not used, and a wheel beside a version PyPI already holds loses to PyPI's. Either way the check
goes green against the release already out, and says nothing about the tree. So the wheel is built
under a local version label, ``X.Y.Z+tree.<commit>``, which PyPI refuses to hold, and the job fails
unless the check's own last line names that version.

**Readings this file fixes.**

- **r1** The job is ``tasks-check`` in both workflows, and it is one more need of ``gate``, so a red
  check closes the one check main requires.
- **r2** The latest release tag is the highest ``vX.Y.Z`` that ``git ls-remote`` lists, read with no
  token. Not lexical, no pre-release, no other tag. No such tag is a failure, never a fall back to main.
- **r3** The job needs no virtual environment of its own: the check makes one. So it adds no row to
  the count ``test_pf10_6`` keeps, and no lane, since it runs no test of this repository.
"""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_pf10_ci import ROOT, SCRIPTS, env_of, import_script, jobs, runs, triggers

JOB = "tasks-check"
SCRIPT = SCRIPTS / "tasks_check.py"
BOTH = ("ci.yml", "release.yml")
TASKS = "poisson-labs/tasks"
SHA = "b4f5d58c0d3a9e1f2a7b6c5d4e3f2a1b0c9d8e7f"
LABELLED = "0.1.2+tree.b4f5d58"
OK_LINE = "PROVE E2E OK: poisson-tasks 0.3.1 + poisson-prove {}"


def job(name: str) -> dict[str, Any]:
    return jobs(name)[JOB]


def steps(name: str) -> list[dict[str, Any]]:
    return list(job(name)["steps"])


def tasks_checkout(name: str) -> dict[str, Any]:
    (step,) = [s for s in steps(name) if s.get("uses", "").startswith("actions/checkout@") and "repository" in s.get("with", {})]
    return step


def tag_step(name: str) -> dict[str, Any]:
    (step,) = [s for s in steps(name) if "tasks_check.py tag" in s.get("run", "")]
    return step


# ---------- the job, its trigger, its Python ----------


@pytest.mark.parametrize("name", BOTH)
def test_the_job_is_in_both_workflows_on_a_hosted_runner_with_a_time_limit(name: str) -> None:
    spec = job(name)
    assert spec["runs-on"] == "ubuntu-latest"
    assert isinstance(spec["timeout-minutes"], int) and spec["timeout-minutes"] <= 30


def test_the_job_runs_on_every_pull_request_whatever_it_changes() -> None:
    assert "pull_request" in triggers("ci.yml") and triggers("ci.yml")["pull_request"] in (None, {})
    assert "if" not in job("ci.yml"), "it is not one of the lanes a change may skip"
    assert "changes" not in str(job("ci.yml").get("needs", []))


@pytest.mark.parametrize("name", BOTH)
def test_the_job_runs_on_python_3_11(name: str) -> None:
    (setup,) = [s for s in steps(name) if s.get("uses", "").startswith("actions/setup-python@")]
    assert setup["with"]["python-version"] == "3.11"
    assert "--python" not in runs(name, JOB), "the check takes the job's Python"


@pytest.mark.parametrize("name", BOTH)
def test_a_red_check_is_never_let_through(name: str) -> None:
    assert "continue-on-error" not in job(name)
    assert not any("continue-on-error" in step for step in steps(name))
    assert not re.search(r"\|\|\s*(true|exit 0|:)", runs(name, JOB)), runs(name, JOB)


def test_a_red_or_skipped_check_closes_the_gate() -> None:
    assert JOB in jobs("ci.yml")["gate"]["needs"]
    gate = import_script("gate")
    passed = {"changes": {"result": "success", "outputs": {"math": "false", "backends": "false", "calibration": "false"}},
              "math": {"result": "skipped"}, "backends": {"result": "skipped"}, "calibration": {"result": "skipped"}}
    assert gate.problems({**passed, JOB: {"result": "success"}}) == []
    assert gate.problems({**passed, JOB: {"result": "failure"}}) != []
    assert gate.problems({**passed, JOB: {"result": "skipped"}}) != [], "not a job a change may skip"


# ---------- the release: publish needs it ----------


def test_publish_needs_the_job_and_runs_only_when_it_passed() -> None:
    publish = jobs("release.yml")["publish"]
    assert sorted(publish["needs"]) == sorted(["build", JOB])
    assert "if" not in publish, "the default: every need passed"


def test_the_release_job_reads_nothing_and_publishes_nothing() -> None:
    spec = job("release.yml")
    assert "permissions" not in spec and "environment" not in spec
    assert not any(s.get("uses", "").startswith("pypa/gh-action-pypi-publish@") for s in spec["steps"])


@pytest.mark.parametrize("name", BOTH)
def test_the_job_holds_no_key_and_no_token(name: str) -> None:
    body = json.dumps(job(name))
    assert not re.search(r"secrets|github\.token|GITHUB_TOKEN|API_KEY", body), body
    assert not re.search(r"(OPENAI|ANTHROPIC|MODAL|BURLA)", " ".join(env_of(name, JOB)))


# ---------- the Tasks ref: its latest release tag, read at run time ----------


@pytest.mark.parametrize("name", BOTH)
def test_the_tasks_checkout_is_the_tag_read_at_run_time_never_main(name: str) -> None:
    read = tag_step(name)
    checkout = tasks_checkout(name)
    assert checkout["with"]["repository"] == TASKS
    assert checkout["with"]["ref"] == "${{ steps." + read["id"] + ".outputs.tag }}"
    assert checkout["with"]["path"], "beside the tree, never over it"
    assert checkout["with"]["persist-credentials"] is False
    assert steps(name).index(read) < steps(name).index(checkout)
    assert "main" not in json.dumps(checkout["with"])


@pytest.mark.parametrize("name", BOTH)
def test_the_tree_is_checked_out_too(name: str) -> None:
    trees = [s for s in steps(name) if s.get("uses", "").startswith("actions/checkout@") and "repository" not in s.get("with", {})]
    assert len(trees) == 1


def ls_remote(*tags: str) -> str:
    return "".join(f"{i:040x}\trefs/tags/{tag}\n" for i, tag in enumerate(tags))


@pytest.mark.parametrize(("listing", "latest"), [
    (ls_remote("v0.3.0", "v0.3.0^{}", "v0.3.1", "v0.3.1^{}"), "v0.3.1"),
    (ls_remote("v0.9.0", "v0.10.0", "v0.2.0"), "v0.10.0"),
    (ls_remote("v0.3.1", "v0.4.0rc1", "v0.4.0a1", "v0.4.0.dev1"), "v0.3.1"),
    (ls_remote("backup/pre-public-rewrite", "v0.3.1", "nightly", "z-latest"), "v0.3.1"),
    (ls_remote("v0.3.1", "v1.0.0-beta", "v1", "v1.0"), "v0.3.1"),
], ids=["peeled-entries", "numbers-not-letters", "no-pre-release", "only-release-tags", "only-three-numbers"])
def test_the_latest_release_tag_is_the_highest_vxyz(listing: str, latest: str) -> None:
    assert import_script("tasks_check").latest_tag(listing) == latest


@pytest.mark.parametrize("listing", ["", ls_remote("nightly", "backup/pre-public-rewrite")], ids=["no-tags", "no-release-tags"])
def test_no_release_tag_is_a_failure_never_a_fall_back(listing: str) -> None:
    with pytest.raises((ValueError, SystemExit)):
        import_script("tasks_check").latest_tag(listing)


def made_up_git(folder: Path, listing: str, code: int = 0) -> Path:
    """A ``git`` that records its arguments and prints ``listing``."""
    folder.mkdir(exist_ok=True)
    git = folder / "git"
    (folder / "listing.txt").write_text(listing, encoding="utf-8")
    git.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(folder / "argv.txt") + '"\ncat "' + str(folder / "listing.txt") + f'"\nexit {code}\n',
        encoding="utf-8")
    git.chmod(git.stat().st_mode | stat.S_IEXEC)
    return folder


def run_script(*arguments: str, path: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), "a test of a failure must not pass because the script is not there"
    search = os.pathsep.join([*([str(path)] if path else []), "/usr/bin", "/bin"])
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], env={"PATH": search, **env}, capture_output=True, text=True, timeout=120)


def test_the_tag_command_writes_the_tag_as_a_step_output_and_asks_git_with_no_token(tmp_path: Path) -> None:
    folder = made_up_git(tmp_path / "bin", ls_remote("v0.3.0", "v0.3.1", "v0.3.1^{}"))
    output = tmp_path / "output.txt"
    done = run_script("tag", path=folder, GITHUB_OUTPUT=str(output))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "tag=v0.3.1" in output.read_text(encoding="utf-8").splitlines()
    (call,) = (folder / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "ls-remote" in call and "--tags" in call and f"https://github.com/{TASKS}" in call
    assert "@github.com" not in call, "no credential in the address"


@pytest.mark.parametrize(("listing", "code"), [("", 0), (ls_remote("v0.3.1"), 128)], ids=["no-tags", "git-failed"])
def test_the_tag_command_fails_and_writes_no_tag_when_it_cannot_read_one(tmp_path: Path, listing: str, code: int) -> None:
    folder = made_up_git(tmp_path / "bin", listing, code)
    output = tmp_path / "output.txt"
    done = run_script("tag", path=folder, GITHUB_OUTPUT=str(output))
    assert done.returncode != 0, done.stdout + done.stderr
    assert not output.exists() or "tag=" not in output.read_text(encoding="utf-8")


# ---------- Prove built from the tree under test ----------


@pytest.mark.parametrize("name", BOTH)
def test_the_job_builds_the_tree_under_a_version_pypi_cannot_hold_and_then_runs_the_check(name: str) -> None:
    body = runs(name, JOB)
    assert "git archive --format=tar HEAD" in body, "the tree under test, as release.yml's build takes it"
    assert body.index("git archive --format=tar HEAD") < body.index("tasks_check.py label") < body.index("python -m build") < body.index("tasks_check.py run")
    assert re.search(r"tasks_check\.py label \S+", body), body
    called = re.search(r"tasks_check\.py run (.*)", body.replace("\\\n", " "))
    assert called, body
    for flag in ("--tasks", "--tasks-wheel", "--prove-wheel", "--work"):
        assert flag in called.group(1), (flag, called.group(1))


@pytest.mark.parametrize("name", BOTH)
def test_the_job_pins_its_build_tool_and_installs_no_prove_of_its_own(name: str) -> None:
    body = runs(name, JOB)
    assert 'build==$BUILD_VERSION' in body
    assert re.fullmatch(r"\d+\.\d+\.\d+", env_of(name, JOB)["BUILD_VERSION"])
    assert "uv venv" not in body, "the check makes its own environment"
    assert not re.search(r"pip install[^\n]*(-e|poisson-prove|\.\[|dist/)", body), "a Prove installed here would not be the one the check uses"


def test_the_script_uses_the_standard_library_alone() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    named = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    named |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert named - {"", "__future__"} <= set(sys.stdlib_module_names), named


def copy_of_the_version_files(folder: Path) -> Path:
    tree = folder / "tree"
    (tree / "src" / "poisson_prove").mkdir(parents=True)
    (tree / "pyproject.toml").write_text((ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8")
    init = ROOT / "src" / "poisson_prove" / "__init__.py"
    (tree / "src" / "poisson_prove" / "__init__.py").write_text(init.read_text(encoding="utf-8"), encoding="utf-8")
    (tree / "README.md").write_text("version = \"0.0.0\" stays\n", encoding="utf-8")
    return tree


def versions_of(tree: Path) -> tuple[str, str]:
    (project,) = re.findall(r'^version = "(.*)"$', (tree / "pyproject.toml").read_text(encoding="utf-8"), flags=re.MULTILINE)
    (package,) = re.findall(r'^__version__ = "(.*)"$', (tree / "src" / "poisson_prove" / "__init__.py").read_text(encoding="utf-8"), flags=re.MULTILINE)
    return project, package


def test_the_label_is_a_local_version_in_both_version_files_and_touches_nothing_else(tmp_path: Path) -> None:
    tree = copy_of_the_version_files(tmp_path)
    before, _ = versions_of(tree)
    done = run_script("label", str(tree), GITHUB_SHA=SHA)
    assert done.returncode == 0, done.stdout + done.stderr
    project, package = versions_of(tree)
    assert project == package, (project, package)
    assert re.fullmatch(re.escape(before) + r"\+tree\.[0-9a-f]{7,40}", project), project
    assert SHA.startswith(project.rsplit(".", 1)[1]), project
    assert (tree / "README.md").read_text(encoding="utf-8") == "version = \"0.0.0\" stays\n"


def test_the_label_refuses_a_tree_it_cannot_label(tmp_path: Path) -> None:
    tree = copy_of_the_version_files(tmp_path)
    assert run_script("label", str(tree)).returncode != 0, "no commit to name"
    assert versions_of(tree)[0] == versions_of(tree)[1] and "+" not in versions_of(tree)[0]
    assert run_script("label", str(tmp_path / "no-such-tree"), GITHUB_SHA=SHA).returncode != 0


FAKE_CHECK = """\
import argparse, os, pathlib, sys
parser = argparse.ArgumentParser()
parser.add_argument("--wheel", required=True, type=pathlib.Path)
parser.add_argument("--work", required=True, type=pathlib.Path)
arguments = parser.parse_args()
if arguments.work.exists() and any(arguments.work.iterdir()):
    sys.exit(2)
pathlib.Path(os.environ["CHECK_RAN"]).write_text(str(arguments.wheel), encoding="utf-8")
print("ok   a check")
print({last!r})
sys.exit({code})
"""


def tasks_with(folder: Path, last: str, code: int) -> Path:
    tasks = folder / "tasks"
    (tasks / "scripts" / "release").mkdir(parents=True)
    (tasks / "scripts" / "release" / "prove_e2e.py").write_text(FAKE_CHECK.format(last=last, code=code), encoding="utf-8")
    return tasks


def wheels(folder: Path, version: str = LABELLED) -> tuple[Path, Path]:
    made = folder / "wheels"
    made.mkdir(exist_ok=True)
    tasks_wheel, prove_wheel = made / "poisson_tasks-0.3.1-py3-none-any.whl", made / f"poisson_prove-{version}-py3-none-any.whl"
    tasks_wheel.write_bytes(b"")
    prove_wheel.write_bytes(b"")
    return tasks_wheel, prove_wheel


def run_check(folder: Path, tasks: Path, tasks_wheel: Path, prove_wheel: Path) -> subprocess.CompletedProcess[str]:
    return run_script("run", "--tasks", str(tasks), "--tasks-wheel", str(tasks_wheel), "--prove-wheel", str(prove_wheel),
                      "--work", str(folder / "work"), CHECK_RAN=str(folder / "ran.txt"))


def test_a_green_check_that_names_the_trees_version_passes(tmp_path: Path) -> None:
    tasks = tasks_with(tmp_path, OK_LINE.format(LABELLED), 0)
    tasks_wheel, prove_wheel = wheels(tmp_path)
    done = run_check(tmp_path, tasks, tasks_wheel, prove_wheel)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp_path / "ran.txt").read_text(encoding="utf-8") == str(tasks_wheel), "the check takes the Tasks wheel"
    assert "ok   a check" in done.stdout, "the check's own lines are the job's log"


def test_a_red_check_fails_the_job_and_its_lines_reach_the_log(tmp_path: Path) -> None:
    tasks = tasks_with(tmp_path, "PROVE E2E FAILED: 1 of 20 checks", 1)
    tasks_wheel, prove_wheel = wheels(tmp_path)
    done = run_check(tmp_path, tasks, tasks_wheel, prove_wheel)
    assert done.returncode != 0, done.stdout + done.stderr
    assert "PROVE E2E FAILED: 1 of 20 checks" in done.stdout


def test_the_checks_exit_code_counts_whatever_its_last_line_says(tmp_path: Path) -> None:
    tasks = tasks_with(tmp_path, OK_LINE.format(LABELLED), 1)
    tasks_wheel, prove_wheel = wheels(tmp_path)
    assert run_check(tmp_path, tasks, tasks_wheel, prove_wheel).returncode != 0


def test_a_green_check_that_ran_on_pypis_prove_fails_the_job(tmp_path: Path) -> None:
    tasks = tasks_with(tmp_path, OK_LINE.format("0.1.2"), 0)
    tasks_wheel, prove_wheel = wheels(tmp_path)
    done = run_check(tmp_path, tasks, tasks_wheel, prove_wheel)
    assert done.returncode != 0, "green, but against the release already out: " + done.stdout + done.stderr


@pytest.mark.parametrize("last", ["", "all good", OK_LINE.format(LABELLED + "x"), OK_LINE.format(LABELLED) + " and then some"],
                         ids=["silent", "another-line", "another-version", "more-after-it"])
def test_a_check_that_does_not_end_by_naming_the_trees_version_fails_the_job(tmp_path: Path, last: str) -> None:
    tasks = tasks_with(tmp_path, last, 0)
    tasks_wheel, prove_wheel = wheels(tmp_path)
    assert run_check(tmp_path, tasks, tasks_wheel, prove_wheel).returncode != 0


def test_a_wheel_without_the_label_is_refused_before_the_check_runs(tmp_path: Path) -> None:
    tasks = tasks_with(tmp_path, OK_LINE.format("0.1.2"), 0)
    tasks_wheel, prove_wheel = wheels(tmp_path, "0.1.2")
    done = run_check(tmp_path, tasks, tasks_wheel, prove_wheel)
    assert done.returncode != 0, done.stdout + done.stderr
    assert not (tmp_path / "ran.txt").exists(), "beside a version PyPI holds, the wheel would lose to PyPI's"


def test_a_tag_with_no_check_in_it_fails_the_job(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    tasks_wheel, prove_wheel = wheels(tmp_path)
    assert run_check(tmp_path, tasks, tasks_wheel, prove_wheel).returncode != 0


# ---------- a contributor reading a red job knows what it is ----------


def section(name: str) -> str:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    return text.split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("name", ["CI", "Releasing"])
def test_contributing_says_the_job_runs_in_each_place(name: str) -> None:
    assert JOB in section(name), name
