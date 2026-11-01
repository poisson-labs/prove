"""PF10 -- CI: the three workflows, their lanes and the markers that split them (PF10.1 to PF10.10).

**What is pinned.** The parsed ``.github/workflows/ci.yml`` (the gate), ``nightly.yml`` and
``release.yml``, ``pyproject.toml``, and the scripts the workflows run, each run on made-up inputs:
``lane.py`` (one lane of the suite and its row in the job summary), ``shards.py`` (the gate's shard
table), ``math_lane.py`` and ``backends_lane.py`` (whether a change runs the math suite or the
backend fakes), ``gate.py`` (the one required check), ``release_check.py`` (what a tag must agree
with) and ``history.py`` (the history check). Whether a job really starts on a GitHub-hosted
runner, or a run really takes under five minutes, is not something a test here can see; the pull
request that changes the workflows is that check.

**The lanes.** The gate runs on every pull request and every push to main: ruff, mypy and the code
suite on Linux and 3.11, sharded, with the math suite when the statistics change and the backend
fakes when backend code changes; its job ``gate`` always runs and is the check main requires.
Nightly runs everything slow and every supported Python on Linux and macOS, and keeps one issue
open while it fails. A tag ``v*`` builds, checks and publishes; nothing slow runs there. No lane
runs a test marked ``backend``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
NAMES = ("ci.yml", "nightly.yml", "release.yml")
SCRIPTS = ROOT / ".github" / "lanes"
PYPROJECT = ROOT / "pyproject.toml"
#: The GitHub-hosted runner labels a job may name: free on a public repository.
HOSTED = {"ubuntu-latest", "macos-latest"}
#: ``owner/name@<40 hex digits>``: an action pinned to one commit.
PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")
FLOORS_TEST = "tests/test_pf7_packaging.py::test_pf7_5_the_code_suite_passes_with_every_requirement_at_its_floor"
PYTHONS = ["3.11", "3.12", "3.13", "3.14"]
PUBLISH = "pypa/gh-action-pypi-publish@"


def workflow(name: str) -> dict[str, Any]:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def triggers(name: str) -> dict[str, Any]:
    data = workflow(name)
    return data["on"] if "on" in data else data[True]  # YAML 1.1 reads a bare ``on`` as true


def jobs(name: str) -> dict[str, dict[str, Any]]:
    return workflow(name)["jobs"]


def env_of(name: str, job: str) -> dict[str, str]:
    """A job's environment: the workflow's, then its own."""
    return {**workflow(name).get("env", {}), **jobs(name)[job].get("env", {})}


def runs(name: str, job: str) -> str:
    return "\n".join(step.get("run", "") for step in jobs(name)[job]["steps"])


def lanes() -> Iterator[tuple[str, str, list[str]]]:
    """``(workflow, job, the arguments after lane.py)`` for every lane a job runs, each ``"$VAR"``
    of the workflow's or the job's environment read in."""
    for name in NAMES:
        for job in jobs(name):
            env = env_of(name, job)
            for line in runs(name, job).splitlines():
                if ".github/lanes/lane.py" not in line:
                    continue
                line = line.replace("\\$", "$").replace('\\"', '"')
                for key, value in env.items():
                    line = line.replace(f'"${key}"', f'"{value}"')
                words = line.split(".github/lanes/lane.py", 1)[1]
                yield name, job, re.findall(r'"[^"]*"|\S+', words)


def lane(name: str, job: str) -> list[str]:
    (arguments,) = [a for n, j, a in lanes() if (n, j) == (name, job)]
    return arguments


def marker_expression(arguments: list[str]) -> str:
    return arguments[arguments.index("-m") + 1].strip('"')


def selects(expression: str, marks: set[str]) -> bool:
    """Whether ``-m expression`` selects a test carrying exactly ``marks``."""
    names = {"math", "calibration", "slow", "backend"}
    python = re.sub(r"\b(" + "|".join(names) + r")\b", lambda m: str(m.group(1) in marks), expression)
    return bool(eval(python, {"__builtins__": {}}))  # noqa: S307 -- True, False, and, or, not


def import_script(name: str) -> Any:
    sys.path.insert(0, str(SCRIPTS))
    try:
        return __import__(name)
    finally:
        sys.path.remove(str(SCRIPTS))


def is_code_suite(expression: str) -> bool:
    return selects(expression, set()) and not any(
        selects(expression, marks) for marks in ({"math"}, {"calibration"}, {"slow"}, {"backend"}, {"math", "calibration"}))


# ---------- PF10.1: triggers ----------


def test_pf10_1_the_gate_runs_on_pull_requests_and_pushes_to_main_nightly_on_a_schedule_and_release_on_a_tag() -> None:
    assert sorted(p.name for p in WORKFLOWS.iterdir()) == sorted(NAMES)
    gate = triggers("ci.yml")
    assert set(gate) == {"pull_request", "push"}
    assert gate["pull_request"] in (None, {}), "a pull request into any base runs"
    assert gate["push"] == {"branches": ["main"]}, "no other branch and no tag runs the gate"
    nightly = triggers("nightly.yml")
    assert set(nightly) == {"schedule", "workflow_dispatch"}
    assert len(nightly["schedule"]) == 1 and set(nightly["schedule"][0]) == {"cron"}
    assert triggers("release.yml") == {"push": {"tags": ["v*"]}}


# ---------- PF10.2: the runner, and the one required check ----------


def test_pf10_2_every_job_runs_on_a_github_hosted_runner_and_none_on_a_self_hosted_one() -> None:
    for name in NAMES:
        assert jobs(name), name
        for job, spec in jobs(name).items():
            runs_on = spec["runs-on"]
            options = set(spec["strategy"]["matrix"]["os"]) if runs_on == "${{ matrix.os }}" else {runs_on}
            assert options and options <= HOSTED, (name, job, options)
            assert "container" not in spec and "services" not in spec, (name, job)
        assert not re.search(r"self-hosted", yaml.safe_dump(workflow(name)), re.IGNORECASE), name


def test_pf10_2_the_gate_job_always_runs_and_depends_on_every_other_job_of_the_gate() -> None:
    gate = jobs("ci.yml")["gate"]
    assert "name" not in gate, "the check's name is the job's id, gate, which the ruleset requires"
    assert gate["if"] == "always()"
    assert sorted(gate["needs"]) == sorted(set(jobs("ci.yml")) - {"gate"})
    assert "gate.py" in runs("ci.yml", "gate")
    (step,) = [s for s in gate["steps"] if "gate.py" in s.get("run", "")]
    assert step["env"]["NEEDS"] == "${{ toJSON(needs) }}"


@pytest.mark.parametrize(("needs", "opens"), [
    ({"changes": {"result": "success", "outputs": {"math": "false", "backends": "false"}}, "lint": {"result": "success"},
      "tests": {"result": "success"}, "math": {"result": "skipped"}, "backends": {"result": "skipped"}}, True),
    ({"changes": {"result": "success", "outputs": {"math": "true", "backends": "false"}}, "lint": {"result": "success"},
      "tests": {"result": "success"}, "math": {"result": "success"}, "backends": {"result": "skipped"}}, True),
    ({"changes": {"result": "success", "outputs": {"math": "true", "backends": "false"}}, "lint": {"result": "success"},
      "tests": {"result": "success"}, "math": {"result": "skipped"}, "backends": {"result": "skipped"}}, False),
    ({"changes": {"result": "success", "outputs": {"math": "false", "backends": "false"}}, "lint": {"result": "success"},
      "tests": {"result": "failure"}, "math": {"result": "skipped"}, "backends": {"result": "skipped"}}, False),
    ({"changes": {"result": "success", "outputs": {"math": "false", "backends": "true"}}, "lint": {"result": "success"},
      "tests": {"result": "success"}, "math": {"result": "skipped"}, "backends": {"result": "cancelled"}}, False),
    ({"changes": {"result": "success", "outputs": {"math": "false", "backends": "false"}}, "lint": {"result": "skipped"},
      "tests": {"result": "success"}, "math": {"result": "skipped"}, "backends": {"result": "skipped"}}, False),
    ({"changes": {"result": "failure", "outputs": {}}, "lint": {"result": "success"},
      "tests": {"result": "success"}, "math": {"result": "skipped"}, "backends": {"result": "skipped"}}, False),
], ids=["nothing-called-for", "math-ran", "math-asked-but-skipped", "a-shard-failed", "backends-cancelled", "lint-skipped", "changes-failed"])
def test_pf10_2_the_gate_opens_only_when_every_job_passed_or_was_not_called_for(needs: dict[str, Any], opens: bool) -> None:
    gate = import_script("gate")
    assert (gate.problems(needs) == []) is opens
    done = subprocess.run([sys.executable, str(SCRIPTS / "gate.py")], env={"NEEDS": json.dumps(needs), "PATH": "/usr/bin:/bin"},
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == (0 if opens else 1), done.stdout + done.stderr


# ---------- PF10.3: a public repository: no secret, one publisher, a read-only token ----------


def test_pf10_3_no_job_reads_a_secret_and_only_the_release_publishes_with_an_id_token() -> None:
    for name in NAMES:
        body = text(name)
        assert "secrets." not in body and "secrets[" not in body, name
        assert workflow(name)["permissions"] == {"contents": "read"}, name
        assert not re.search(r"\b(twine upload|uv publish|hatch publish|flit publish)\b", body), name
    for name in ("ci.yml", "nightly.yml"):
        assert "id-token" not in text(name) and PUBLISH not in text(name), name
        for job, spec in jobs(name).items():
            assert "environment" not in spec, (name, job)
    assert all("permissions" not in spec for spec in jobs("ci.yml").values())
    held = {job: spec["permissions"] for job, spec in jobs("nightly.yml").items() if "permissions" in spec}
    assert held == {"report": {"actions": "read", "issues": "write"}}, "only the report may write, and only issues"
    release = jobs("release.yml")
    assert {job: spec.get("permissions") for job, spec in release.items()} == {"build": None, "publish": {"id-token": "write"}}
    assert release["publish"]["environment"]["name"] == "pypi" and "environment" not in release["build"]
    publishers = [(job, s) for job, spec in release.items() for s in spec["steps"] if s.get("uses", "").startswith(PUBLISH)]
    assert [job for job, _ in publishers] == ["publish"] and "with" not in publishers[0][1], "trusted publishing: no password"


def test_pf10_3_a_pull_request_runs_with_the_forks_own_read_only_token_never_pull_request_target() -> None:
    for name in NAMES:
        body = text(name)
        assert "pull_request_target" not in body and "workflow_run" not in body, name
        for job, spec in jobs(name).items():
            for step in spec["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False, (name, job, "the token stays out of .git/config")
    assert "pull_request" in triggers("ci.yml")
    assert "GITHUB_TOKEN" not in text("ci.yml") and "github.token" not in text("ci.yml")
    assert [job for job, spec in jobs("nightly.yml").items() if "github.token" in json.dumps(spec)] == ["report"]


def test_pf10_3_every_action_is_pinned_to_a_full_commit_sha_with_its_version_beside_it() -> None:
    for name in NAMES:
        lines = [line for line in text(name).splitlines() if re.match(r"\s*(- )?uses:", line)]
        assert lines, name
        for line in lines:
            _, _, reference = line.partition("uses:")
            action, _, comment = reference.strip().partition(" # ")
            assert PINNED.fullmatch(action), (name, line)
            assert re.fullmatch(r"v\d+\.\d+\.\d+", comment), (name, line)
        assert len(lines) == sum(1 for spec in jobs(name).values() for step in spec["steps"] if "uses" in step), name


# ---------- PF10.4: the lanes ----------


def test_pf10_4_each_lane_selects_its_tests_and_none_selects_a_backend_test() -> None:
    by_lane = {(name, job): marker_expression(arguments) for name, job, arguments in lanes() if "-m" in arguments}
    assert set(by_lane) == {("ci.yml", "tests"), ("ci.yml", "math"), ("ci.yml", "backends"), ("nightly.yml", "code"),
                            ("nightly.yml", "math"), ("nightly.yml", "slow"), ("nightly.yml", "floors"), ("nightly.yml", "linux"),
                            ("release.yml", "build")}
    for key in (("ci.yml", "tests"), ("ci.yml", "backends"), ("nightly.yml", "code"), ("nightly.yml", "linux")):
        assert is_code_suite(by_lane[key]), key
    for key in (("ci.yml", "math"), ("nightly.yml", "math")):
        assert selects(by_lane[key], {"math"}) and selects(by_lane[key], {"calibration"}) and not selects(by_lane[key], set()), key
    assert selects(by_lane[("nightly.yml", "slow")], {"slow"}) and not selects(by_lane[("nightly.yml", "slow")], set())
    for key, expression in by_lane.items():
        assert not selects(expression, {"backend"}) and not selects(expression, {"backend", "slow"}), key


def test_pf10_4_nothing_slow_runs_in_the_gate_or_at_a_release() -> None:
    for name, job, arguments in lanes():
        if name in ("ci.yml", "release.yml") and "-m" in arguments:
            assert not selects(marker_expression(arguments), {"slow"}), (name, job)
        if name in ("ci.yml", "release.yml"):
            assert FLOORS_TEST not in " ".join(arguments), (name, job)
    for name in ("ci.yml", "release.yml"):
        assert "playwright install" not in text(name) and "docker run" not in text(name), name


def test_pf10_4_the_gate_runs_lint_and_the_sharded_code_suite_on_linux_and_311() -> None:
    gate = jobs("ci.yml")
    for job in ("changes", "lint", "tests", "math", "backends"):
        assert gate[job]["runs-on"] == "ubuntu-latest", job
        (setup,) = [s for s in gate[job]["steps"] if s.get("uses", "").startswith("actions/setup-python@")]
        assert setup["with"]["python-version"] == "3.11", job
    lint = runs("ci.yml", "lint")
    assert "ruff check ." in lint and "ruff format --check src" in lint and "mypy src" in lint
    assert '-e ".[all,dev]"' in lint and '-e ".[all,dev]"' in runs("ci.yml", "tests")
    assert "if" not in gate["lint"] and "if" not in gate["tests"], "lint and the shards run on every change"
    shards = import_script("shards")
    table = shards.parse(env_of("ci.yml", "tests")["SHARDS"])
    numbered = [name for name in table if name.isdigit()]
    assert gate["tests"]["strategy"]["matrix"]["shard"] == [int(n) for n in numbered]
    assert shards.problems(table, shards.test_files(), len(numbered)) == []
    assert 'shards.py "$SHARD" --total "$SHARD_COUNT"' in runs("ci.yml", "tests")
    assert "shards.py backends" in runs("ci.yml", "backends")


@pytest.mark.parametrize(("table", "wrong"), [
    ("1: --dist=loadfile tests/test_a.py\n2: tests/test_b.py\n   tests/test_c.py\n3: rest\nbackends: tests/test_d.py\n", None),
    ("1: tests/test_a.py\n2: tests/test_a.py\n3: rest\nbackends: tests/test_d.py\n", "tests/test_a.py is in 1 and 2"),
    ("1: tests/test_a.py\n2: tests/test_b.py\nbackends: tests/test_d.py\n", "0 shards are rest; exactly one must be"),
    ("1: tests/test_a.py\n3: rest\nbackends: tests/test_d.py\n", "the numbered shards are ['1', '3'], not 1 to 2"),
    ("1: tests/test_a.py\n2: rest\nbackends: tests/test_d.py tests/test_z.py\n", "tests/test_z.py (backends) is not a test file"),
    ("1: tests/test_a.py\n2: rest\n", "no backends entry"),
], ids=["a-good-table", "a-file-twice", "no-rest", "a-gap", "not-a-test-file", "no-backends"])
def test_pf10_4_the_shard_table_puts_every_test_file_in_exactly_one_place(table: str, wrong: str | None) -> None:
    shards = import_script("shards")
    tests = ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py", "tests/test_d.py", "tests/test_e.py", "tests/test_f.py"]
    parsed = shards.parse(table)
    found = shards.problems(parsed, tests)
    if wrong is None:
        assert found == []
        assert shards.paths(parsed, "3", tests) == ["tests/test_e.py", "tests/test_f.py"], "rest leaves out every named file"
        assert shards.paths(parsed, "2", tests) == ["tests/test_b.py", "tests/test_c.py"]
        assert shards.paths(parsed, "1", tests) == ["--dist=loadfile", "tests/test_a.py"], "an option is the shard's own"
        assert shards.problems(parsed, tests, 4) == ["the table has 3 shards and the matrix runs 4"]
    else:
        assert wrong in found, found


def test_pf10_4_nightly_runs_the_code_suite_on_every_python_on_linux_and_macos_and_math_and_slow_on_every_python() -> None:
    nightly = jobs("nightly.yml")
    assert nightly["code"]["strategy"]["matrix"] == {"os": ["ubuntu-latest", "macos-latest"], "python": PYTHONS}
    assert nightly["code"]["name"] == "code (${{ matrix.os }}, ${{ matrix.python }})"
    for job in ("math", "slow"):
        assert nightly[job]["strategy"]["matrix"] == {"python": PYTHONS}, job
    assert lane("nightly.yml", "code")[-1] == "tests", "the whole code suite, the backend fakes included"
    for job, spec in nightly.items():
        assert "if" not in spec or job == "report", job
    assert "docker run --rm --init " in runs("nightly.yml", "linux"), "PID 1 in the container must reap orphans"


def test_pf10_4_the_floors_run_is_alone_at_its_own_thread_cap_and_keeps_its_whole_output() -> None:
    floors = lane("nightly.yml", "floors")
    assert FLOORS_TEST in " ".join(floors)
    slow = lane("nightly.yml", "slow")
    assert slow[slow.index("--deselect") + 1].strip('"') == FLOORS_TEST
    assert env_of("nightly.yml", "floors")["OPENBLAS_NUM_THREADS"] == "1"
    (upload,) = [s for s in jobs("nightly.yml")["floors"]["steps"] if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert upload["if"] == "always()" and upload["with"]["path"].endswith("floors-suite-output.txt")
    source = (ROOT / "tests" / "test_pf7_packaging.py").read_text(encoding="utf-8")
    assert '"-n", str(min(8, os.cpu_count() or 1))' in source and "floors-suite-output.txt" in source


def test_pf10_4_every_hosted_lane_runs_one_pytest_worker_per_core() -> None:
    for name, job in (("ci.yml", "tests"), ("ci.yml", "math"), ("ci.yml", "backends"),
                      ("nightly.yml", "code"), ("nightly.yml", "math"), ("nightly.yml", "slow")):
        arguments = lane(name, job)
        assert arguments[arguments.index("-n") + 1] == '"$WORKERS"', (name, job)
        assert 'echo "WORKERS=$(python -c \'import os; print(os.cpu_count())\')" >> "$GITHUB_ENV"' in runs(name, job), (name, job)
    container = lane("nightly.yml", "linux")
    assert container[container.index("-n") + 1] == '"$(nproc)"'
    assert "-n" not in lane("nightly.yml", "floors"), "the floors test sets its inner suite's workers itself"


# ---------- PF10.5: the markers ----------


def test_pf10_5_the_four_markers_are_declared_with_their_lane_in_plain_words() -> None:
    markers = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]["markers"]
    described = dict(m.split(": ", 1) for m in markers)
    assert {"math", "calibration", "slow", "backend"} <= set(described)
    assert "pull request" in described["math"] and "nightly" in described["math"] and "release" in described["math"]
    assert "nightly" in described["slow"] and "never on a pull request" in described["slow"]
    assert "never in CI" in described["backend"]
    math_lane = import_script("math_lane")
    for path in math_lane.trigger_files(PYPROJECT.read_text(encoding="utf-8")):
        assert (ROOT / path).is_file(), path


# ---------- PF10.6: uv finds only the Python the job installed ----------


def test_pf10_6_every_job_that_builds_a_venv_installs_its_python_and_uv_uses_only_that_one() -> None:
    built_any = []
    for name in NAMES:
        for job, spec in jobs(name).items():
            body = runs(name, job)
            if "uv venv" not in body or "docker run" in body:
                continue
            built_any.append((name, job))
            assert env_of(name, job)["UV_PYTHON_PREFERENCE"] == "only-system", (name, job)
            assert env_of(name, job)["UV_PYTHON_DOWNLOADS"] == "never", (name, job)
            (setup,) = [s for s in spec["steps"] if s.get("uses", "").startswith("actions/setup-python@")]
            (built,) = re.findall(r'uv venv --quiet --python (".*?"|\S+) \.venv', body)
            assert built.strip('"') == str(setup["with"]["python-version"]).strip('"'), (name, job)
            assert "uv==$UV_VERSION" in body and re.fullmatch(r"\d+\.\d+\.\d+", env_of(name, job)["UV_VERSION"]), (name, job)
    assert len(built_any) == 9, built_any


# ---------- PF10.7: when a change runs the math suite, and the backend fakes ----------


@pytest.mark.parametrize(("changed", "math_tests", "base", "head", "why"), [
    (["src/poisson_prove/executor.py", "README.md"], [], {"numpy": "2.4.6"}, {"numpy": "2.4.6"}, []),
    (["src/poisson_prove/paired.py"], [], {}, {}, ["changes src/poisson_prove/paired.py"]),
    (["tests/test_m6_diff.py"], ["tests/test_m6_diff.py"], {}, {}, ["changes tests/test_m6_diff.py, a test of the math suite"]),
    (["pyproject.toml"], [], {"scipy": "1.16.0"}, {"scipy": "1.17.1"}, ["scipy resolves to 1.17.1 here and 1.16.0 on the base"]),
    (["pyproject.toml"], [], {"rich": "14.2.0"}, {"rich": "15.0.0"}, []),
], ids=["no-statistics", "a-statistics-file", "a-math-test", "a-library-resolves-differently", "another-library"])
def test_pf10_7_a_pull_request_runs_the_math_suite_only_when_the_statistics_change(
    changed: list[str], math_tests: list[str], base: dict[str, str], head: dict[str, str], why: list[str]
) -> None:
    math_lane = import_script("math_lane")
    assert math_lane.reasons(changed, math_tests, base, head, PYPROJECT.read_text(encoding="utf-8")) == why


@pytest.mark.parametrize(("changed", "base", "head", "why"), [
    (["README.md", "CHANGELOG.md", "pyproject.toml", "src/poisson_prove/__init__.py"], {"burla": "1.8.4"}, {"burla": "1.8.4"}, []),
    (["src/poisson_prove/executor_burla.py"], {}, {}, ["changes src/poisson_prove/executor_burla.py"]),
    (["tests/bu_fixtures/burla/__init__.py"], {}, {}, ["changes tests/bu_fixtures/burla/__init__.py, a fake backend"]),
    (["tests/test_m3_modal.py"], {}, {}, ["changes tests/test_m3_modal.py, a backend test"]),
    (["pyproject.toml"], {"modal": "1.2.0"}, {"modal": "1.3.0"}, ["modal resolves to 1.3.0 here and 1.2.0 on the base"]),
    (["src/poisson_prove/stats.py"], {"numpy": "2.4.6"}, {"numpy": "2.5.0"}, []),
], ids=["docs-version-changelog", "a-backend-file", "a-fake", "a-backend-test", "modal-resolves-differently", "statistics"])
def test_pf10_7_a_change_runs_the_backend_fakes_only_when_backend_code_changes(
    changed: list[str], base: dict[str, str], head: dict[str, str], why: list[str]
) -> None:
    backends_lane = import_script("backends_lane")
    tests = ["tests/test_bu_burla_backend.py", "tests/test_m3_modal.py"]
    assert backends_lane.reasons(changed, tests, base, head) == why


def test_pf10_7_the_math_and_backend_jobs_follow_the_changes_job_and_nightly_runs_both_whatever_changed() -> None:
    gate = jobs("ci.yml")
    assert gate["math"]["if"] == "needs.changes.outputs.math == 'true'" and gate["math"]["needs"] == ["changes"]
    assert gate["backends"]["if"] == "needs.changes.outputs.backends == 'true'" and gate["backends"]["needs"] == ["changes"]
    assert 'math_lane.py "$BASE_SHA" "$HEAD_SHA"' in runs("ci.yml", "changes")
    assert 'backends_lane.py "$BASE_SHA" "$HEAD_SHA"' in runs("ci.yml", "changes")
    assert gate["changes"]["steps"][0]["with"]["fetch-depth"] == 0
    assert set(gate["changes"]["outputs"]) == {"math", "backends"}
    shards = import_script("shards")
    for path in shards.parse(env_of("ci.yml", "tests")["SHARDS"])["backends"]:
        assert (ROOT / path).is_file(), path
    for path in import_script("backends_lane").SOURCES:
        assert (ROOT / path).is_file(), path
    assert "if" not in jobs("nightly.yml")["math"] and lane("nightly.yml", "code")[-1] == "tests"


# ---------- PF10.8: each lane's count, time and load in the job summary ----------


def test_pf10_8_a_lane_writes_its_count_wall_time_budget_load_and_slow_tests_to_the_job_summary(tmp_path: Path) -> None:
    (tmp_path / "test_two.py").write_text(
        "import time\n\n\ndef test_passes():\n    time.sleep(1.2)\n\n\ndef test_fails():\n    assert False\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    done = subprocess.run([sys.executable, str(SCRIPTS / "lane.py"), "demo", "300", "--over", "1", "-q", "-p", "no:cacheprovider", "test_two.py"],
                          cwd=tmp_path, env={"GITHUB_STEP_SUMMARY": str(summary), "PATH": "/usr/bin:/bin"},
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 1, done.stdout + done.stderr
    header, _, row, *listed = summary.read_text(encoding="utf-8").splitlines()
    assert [line for line in listed if line] == ["1 tests over 1 s (setup, call and teardown):", listed[-1]]
    assert re.fullmatch(r"- 1\.\d s `test_two\.py::test_passes`", listed[-1]), listed
    cells = dict(zip([c.strip() for c in header.strip("|").split("|")], [c.strip() for c in row.strip("|").split("|")], strict=True))
    assert cells["lane"] == "demo" and cells["ran"] == "2" and cells["passed"] == "1" and cells["failed"] == "1"
    assert re.fullmatch(r"\d+:\d\d", cells["wall"]) and cells["budget"] == "5:00 (within)" and cells["exit"] == "1"
    assert re.fullmatch(r"[\d.]+ / [\d.]+ / [\d.]+", cells["load min / median / max"])


def test_pf10_8_every_job_that_runs_tests_runs_them_through_the_lane_script() -> None:
    for name in NAMES:
        for job in jobs(name):
            assert "pytest" not in runs(name, job).replace("-p no:cacheprovider", ""), (name, job)
    assert {(name, job) for name, job, _ in lanes()} == {
        ("ci.yml", "tests"), ("ci.yml", "math"), ("ci.yml", "backends"), ("nightly.yml", "code"), ("nightly.yml", "math"),
        ("nightly.yml", "slow"), ("nightly.yml", "floors"), ("nightly.yml", "linux"), ("release.yml", "build")}


def test_pf10_8_each_lane_reports_against_its_hosted_budget() -> None:
    # Report-only budgets for a hosted runner, in seconds: a gate shard has five minutes.
    budgets = {(name, job): arguments[1] for name, job, arguments in lanes()}
    assert budgets == {("ci.yml", "tests"): "300", ("ci.yml", "math"): "4200", ("ci.yml", "backends"): "600",
                       ("nightly.yml", "code"): "1800", ("nightly.yml", "linux"): "1800", ("nightly.yml", "floors"): "1800",
                       ("nightly.yml", "math"): "4200", ("nightly.yml", "slow"): "9000", ("release.yml", "build"): "600"}


# ---------- PF10.9: nightly keeps one issue while it fails ----------


def test_pf10_9_a_failed_nightly_opens_or_updates_one_issue_and_a_green_one_closes_it() -> None:
    report = jobs("nightly.yml")["report"]
    assert report["if"] == "always()"
    assert sorted(report["needs"]) == sorted(set(jobs("nightly.yml")) - {"report"})
    assert report["env"]["TITLE"] == "Nightly run failed"
    body = runs("nightly.yml", "report")
    assert "actions/runs/$RUN_ID/jobs" in body, "names each failed job, matrix legs included"
    assert body.index("gh issue list --state open") < body.index("gh issue comment") < body.index("gh issue create")
    assert "gh issue close" in body


# ---------- PF10.10: a release is a tag, checked and published, nothing slow ----------


@pytest.mark.parametrize(("tag", "version", "init", "heading", "wrong"), [
    ("v0.2.0", "0.2.0", "0.2.0", "## 0.2.0 — 2026-11-02", []),
    ("v0.2.0", "0.1.1", "0.2.0", "## 0.2.0 — 2026-11-02", ["pyproject.toml says 0.1.1, the tag v0.2.0"]),
    ("v0.2.0", "0.2.0", "0.1.1", "## 0.2.0 — 2026-11-02", ["__version__ is 0.1.1, the tag v0.2.0"]),
    ("v0.2.0", "0.2.0", "0.2.0", "## 0.1.1 — 2026-10-30", ["CHANGELOG.md has no entry headed '## 0.2.0 — YYYY-MM-DD'"]),
    ("v0.2.0", "0.2.0", "0.2.0", "## 0.2.0 — Unreleased", ["the CHANGELOG entry for 0.2.0 is dated Unreleased, not YYYY-MM-DD"]),
    ("release-1", "0.2.0", "0.2.0", "## 0.2.0 — 2026-11-02", ["the tag release-1 is not vX.Y.Z"]),
], ids=["agree", "pyproject-behind", "init-behind", "no-entry", "undated", "not-a-version-tag"])
def test_pf10_10_a_tag_must_name_the_version_and_a_dated_changelog_entry(tag: str, version: str, init: str, heading: str, wrong: list[str]) -> None:
    release_check = import_script("release_check")
    pyproject = f'[project]\nname = "poisson-prove"\nversion = "{version}"\n'
    assert release_check.problems(tag, pyproject, f'__version__ = "{init}"\n', f"# Changelog\n\n{heading}\n\nText.\n") == wrong


def test_pf10_10_the_release_checks_the_tag_builds_from_the_tagged_tree_and_tests_the_files_it_publishes() -> None:
    build = jobs("release.yml")["build"]
    order = [s.get("name", s.get("uses", "")) for s in build["steps"]]
    body = runs("release.yml", "build")
    assert 'release_check.py "$GITHUB_REF_NAME"' in body
    assert body.index("release_check.py") < body.index("python -m build") < body.index("use_built")
    assert "git archive --format=tar HEAD" in body and "twine check --strict dist/*" in body
    arguments = lane("release.yml", "build")
    assert "use_built" in arguments and "tests/test_pf7_packaging.py" in arguments and "tests/test_pf8_public_hygiene.py" in arguments
    step = [s for s in build["steps"] if "use_built" in s.get("run", "")][0]
    assert step["env"] == {"PROVE_DIST": "dist", "PYTHONPATH": ".github/lanes"}
    assert order[-1].startswith("actions/upload-artifact@")
    publish = jobs("release.yml")["publish"]
    assert publish["needs"] == ["build"]
    assert [s["uses"].split("@")[0] for s in publish["steps"]] == ["actions/download-artifact", "pypa/gh-action-pypi-publish"]


def test_pf10_10_the_readme_badge_shows_the_gates_push_runs_on_main() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    (badge,) = re.findall(r"\[!\[CI\]\(([^)]+)\)\]\(([^)]+)\)", readme)
    assert badge[0].startswith("https://img.shields.io/github/actions/workflow/status/poisson-labs/prove/ci.yml?")
    assert "branch=main" in badge[0] and "event=push" in badge[0]
    assert "workflows/ci.yml" in badge[1] and "branch%3Amain" in badge[1] and "event%3Apush" in badge[1]


# ---------- the history check ----------


@pytest.mark.parametrize(("commit", "flagged"), [
    (("a" * 40, "dev@poissonlabs.ai", "dev@poissonlabs.ai", "fix: a thing\n"), False),
    (("b" * 40, "dev@poissonlabs.ai", "noreply@github.com", "Merge pull request #1\n"), False),
    (("c" * 40, "someone@gmail.com", "dev@poissonlabs.ai", "fix: a thing\n"), True),
    (("d" * 40, "dev@poissonlabs.ai", "dev@poissonlabs.ai", "fix: a thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"), True),
    (("e" * 40, "dev@poissonlabs.ai", "dev@poissonlabs.ai", "docs: thing\n\nGenerated with Claude Code\n"), True),
], ids=["work-address", "a-github-merge", "a-personal-address", "an-assistant-trailer", "an-assistant-line"])
def test_the_history_check_flags_a_personal_address_or_an_assistant_and_nothing_else(commit: tuple[str, str, str, str], flagged: bool) -> None:
    history = import_script("history")
    assert bool(history.problems([commit])) is flagged
