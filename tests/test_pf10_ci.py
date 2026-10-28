"""PF10 -- CI: the workflow, its lanes and the markers that split them (PF10.1 to PF10.8).

**What is pinned.** The parsed ``.github/workflows/ci.yml`` and ``pyproject.toml``, and the three
scripts the workflow runs, each run on made-up inputs: ``lane.py`` (one lane of the suite and its
row in the job summary), ``math_lane.py`` (whether a pull request runs the math suite) and
``history.py`` (the release's history check). Whether a job really starts on the runner is not
something a test here can see; the pull request that adds the workflow is that check.

**The lanes.** The code lane runs on every pull request and every push to main. The math lane
runs on a pull request that changes the statistics, nightly, and before a release (the workflow
run by hand with lane ``release``). Slow tests, the floors run and the Linux container run nightly
and before a release; the history check before a release. No lane runs a test marked
``backend``.
"""

from __future__ import annotations

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
WORKFLOW = WORKFLOWS / "ci.yml"
SCRIPTS = ROOT / ".github" / "scripts"
PYPROJECT = ROOT / "pyproject.toml"
RUNNER = ["self-hosted", "macOS", "ARM64"]
FLOORS_TEST = "tests/test_pf7_packaging.py::test_pf7_5_the_code_suite_passes_with_every_requirement_at_its_floor"
NIGHTLY = ("schedule", "workflow_dispatch")


def workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def triggers() -> dict[str, Any]:
    data = workflow()
    return data["on"] if "on" in data else data[True]  # YAML 1.1 reads a bare ``on`` as true


def jobs() -> dict[str, dict[str, Any]]:
    return workflow()["jobs"]


def env_of(name: str) -> dict[str, str]:
    """A job's environment: the workflow's, then its own."""
    return {**workflow().get("env", {}), **jobs()[name].get("env", {})}


def runs(name: str) -> str:
    return "\n".join(step.get("run", "") for step in jobs()[name]["steps"])


def lanes() -> Iterator[tuple[str, list[str]]]:
    """``(job, the arguments after lane.py)`` for every lane a job runs, ``$CODE_SUITE`` and
    ``$FLOORS_TEST`` read from the job's environment."""
    for name in jobs():
        env = env_of(name)
        for line in runs(name).splitlines():
            if ".github/scripts/lane.py" not in line:
                continue
            line = line.replace("\\$", "$").replace('\\"', '"')
            for key, value in env.items():
                line = line.replace(f'"${key}"', f'"{value}"')
            words = line.split(".github/scripts/lane.py", 1)[1]
            yield name, re.findall(r'"[^"]*"|\S+', words)


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


# ---------- PF10.1: triggers ----------


def test_pf10_1_the_only_triggers_are_pull_requests_pushes_to_main_the_nightly_and_a_run_by_hand() -> None:
    assert sorted(p.name for p in WORKFLOWS.iterdir()) == ["ci.yml"]
    on = triggers()
    assert set(on) == {"pull_request", "push", "schedule", "workflow_dispatch"}
    assert on["pull_request"] in (None, {}), "a pull request into any base runs"
    assert on["push"] == {"branches": ["main"]}, "no other branch and no tag runs anything"
    assert len(on["schedule"]) == 1 and set(on["schedule"][0]) == {"cron"}
    assert on["workflow_dispatch"]["inputs"]["lane"]["options"] == ["release", "nightly"]


# ---------- PF10.2: the runner ----------


def test_pf10_2_every_job_runs_on_the_self_hosted_mac_and_none_on_a_hosted_runner() -> None:
    assert jobs()
    for name, job in jobs().items():
        assert job["runs-on"] == RUNNER, name
        assert "container" not in job and "services" not in job, name


# ---------- PF10.3: no secret, no publish ----------


def test_pf10_3_no_job_reads_a_secret_holds_an_id_token_or_publishes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text and "secrets[" not in text
    assert workflow()["permissions"] == {"contents": "read"}
    for name, job in jobs().items():
        assert "permissions" not in job and "environment" not in job, name
        for step in job["steps"]:
            assert "publish" not in step.get("uses", ""), (name, step)
            assert not re.search(r"\b(twine|uv publish|hatch publish|flit publish)\b", step.get("run", "")), (name, step)


# ---------- PF10.4: the lanes ----------


def test_pf10_4_each_lane_selects_its_tests_and_none_selects_a_backend_test() -> None:
    by_job = {name: marker_expression(arguments) for name, arguments in lanes() if "-m" in arguments}
    assert set(by_job) == {"code", "math", "slow", "floors", "linux"}
    code = by_job["code"]
    for marks in ({"math"}, {"calibration"}, {"slow"}, {"backend"}, {"math", "calibration"}):
        assert not selects(code, marks), (code, marks)
    assert selects(code, set())
    assert by_job["linux"] == code
    assert selects(by_job["math"], {"math"}) and selects(by_job["math"], {"calibration"}) and not selects(by_job["math"], set())
    assert selects(by_job["slow"], {"slow"}) and not selects(by_job["slow"], set())
    for name, expression in by_job.items():
        assert not selects(expression, {"backend"}) and not selects(expression, {"backend", "slow"}), name


def test_pf10_4_the_code_lane_runs_in_parallel_on_every_pull_request_and_push_to_main() -> None:
    code = jobs()["code"]
    assert "if" not in code
    (arguments,) = [a for name, a in lanes() if name == "code"]
    assert "-n" in arguments
    assert "ruff check ." in runs("code") and "ruff format --check src" in runs("code") and "mypy src" in runs("code")
    assert '-e ".[all,dev]"' in runs("code")
    matrix = code["strategy"]["matrix"]["python"]
    assert '["3.11", "3.14"]' in matrix and '["3.11", "3.12", "3.13", "3.14"]' in matrix


def test_pf10_4_slow_floors_linux_run_nightly_and_before_a_release_and_history_before_a_release() -> None:
    for name in ("slow", "floors", "linux"):
        condition = jobs()[name]["if"]
        assert all(event in condition for event in NIGHTLY) and "pull_request" not in condition and "push" not in condition, name
    assert jobs()["history"]["if"] == "github.event_name == 'workflow_dispatch' && inputs.lane == 'release'"
    assert "history.py" in runs("history")
    assert jobs()["history"]["steps"][0]["with"]["fetch-depth"] == 0


def test_pf10_4_the_floors_run_is_alone_at_its_own_thread_cap_and_keeps_its_whole_output() -> None:
    (floors,) = [a for name, a in lanes() if name == "floors"]
    assert FLOORS_TEST in " ".join(floors)
    (slow,) = [a for name, a in lanes() if name == "slow"]
    assert slow[slow.index("--deselect") + 1].strip('"') == FLOORS_TEST
    assert env_of("floors")["OPENBLAS_NUM_THREADS"] == "1"
    (upload,) = [s for s in jobs()["floors"]["steps"] if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert upload["if"] == "always()" and upload["with"]["path"].endswith("floors-suite-output.txt")
    source = (ROOT / "tests" / "test_pf7_packaging.py").read_text(encoding="utf-8")
    assert '"-n", "8"' in source and "floors-suite-output.txt" in source


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


# ---------- PF10.6: uv finds only the runner's own Pythons ----------


def test_pf10_6_every_job_sets_uv_python_preference_only_system() -> None:
    for name in jobs():
        assert env_of(name)["UV_PYTHON_PREFERENCE"] == "only-system", name
        assert "setup-python" not in str(jobs()[name]["steps"]), name


# ---------- PF10.7: when a pull request runs the math suite ----------


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


def test_pf10_7_the_math_job_follows_that_decision_on_a_pull_request_and_runs_nightly_and_before_a_release() -> None:
    condition = jobs()["math"]["if"]
    assert "needs.math-changes.outputs.math == 'true'" in condition
    assert all(event in condition for event in NIGHTLY)
    assert jobs()["math"]["needs"] == ["math-changes"]
    assert jobs()["math-changes"]["if"] == "github.event_name == 'pull_request'"
    assert "math_lane.py" in runs("math-changes")


# ---------- PF10.8: each lane's count, time and load in the job summary ----------


def test_pf10_8_a_lane_writes_its_count_wall_time_budget_and_load_to_the_job_summary(tmp_path: Path) -> None:
    (tmp_path / "test_two.py").write_text("def test_passes():\n    pass\n\n\ndef test_fails():\n    assert False\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    done = subprocess.run([sys.executable, str(SCRIPTS / "lane.py"), "demo", "300", "-q", "-p", "no:cacheprovider", "test_two.py"],
                          cwd=tmp_path, env={"GITHUB_STEP_SUMMARY": str(summary), "PATH": "/usr/bin:/bin"},
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 1, done.stdout + done.stderr
    header, _, row = summary.read_text(encoding="utf-8").splitlines()
    cells = dict(zip([c.strip() for c in header.strip("|").split("|")], [c.strip() for c in row.strip("|").split("|")], strict=True))
    assert cells["lane"] == "demo" and cells["ran"] == "2" and cells["passed"] == "1" and cells["failed"] == "1"
    assert re.fullmatch(r"\d+:\d\d", cells["wall"]) and cells["budget"] == "5:00 (within)" and cells["exit"] == "1"
    assert re.fullmatch(r"[\d.]+ / [\d.]+ / [\d.]+", cells["load min / median / max"])


def test_pf10_8_every_job_that_runs_tests_runs_them_through_the_lane_script() -> None:
    for name in jobs():
        text = runs(name)
        assert "pytest" not in text.replace("-p no:cacheprovider", ""), name
    assert {name for name, _ in lanes()} == {"code", "math", "slow", "floors", "linux"}


# ---------- the release's history check ----------


@pytest.mark.parametrize(("commit", "flagged"), [
    (("a" * 40, "taylor@poissonlabs.ai", "taylor@poissonlabs.ai", "fix: a thing\n"), False),
    (("b" * 40, "taylor@poissonlabs.ai", "noreply@github.com", "Merge pull request #1\n"), False),
    (("c" * 40, "someone@gmail.com", "taylor@poissonlabs.ai", "fix: a thing\n"), True),
    (("d" * 40, "taylor@poissonlabs.ai", "taylor@poissonlabs.ai", "fix: a thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"), True),
    (("e" * 40, "taylor@poissonlabs.ai", "taylor@poissonlabs.ai", "docs: thing\n\nGenerated with Claude Code\n"), True),
], ids=["work-address", "a-github-merge", "a-personal-address", "an-assistant-trailer", "an-assistant-line"])
def test_the_history_check_flags_a_personal_address_or_an_assistant_and_nothing_else(commit: tuple[str, str, str, str], flagged: bool) -> None:
    history = import_script("history")
    assert bool(history.problems([commit])) is flagged
