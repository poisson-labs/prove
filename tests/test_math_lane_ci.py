"""The math lane after the rulings of 2026-11-04: where the statistics and calibration run.

The gate's math lane ran all 689 tests marked ``math`` or ``calibration`` in one job, 25 to 67
minutes on a hosted runner; calibration was nine tenths of that time. After the rulings:

1. Nothing marked ``slow`` runs in the gate's math lane (``test_pf10_4_nothing_slow_runs_in_the_gate_or_at_a_release``
   asks about ``slow`` together with ``math`` or ``calibration``). The four slow math tests still run
   nightly, in the math lane and in the slow lane.
2. Calibration leaves the ordinary pull request: the gate's math lane runs ``math`` and not
   ``calibration`` and not ``slow``. The ``calibration`` marker's words stay to the letter.
3. The gate's math lane runs in two jobs, by file, through the shard table: ``tests/test_pf4_stats.py``
   in one, the other files that hold math tests in the other.
4. Calibration runs on the release pull request, the one that changes ``project.version``, cut by
   test into eight jobs; every calibration test is in exactly one of them.
5. Calibration also runs on the push to main when the change ran the math lane, in the same eight
   jobs. Nobody waits on that run; a failure turns main's badge (the push runs of ``ci.yml``) red.
8. ``--dist worksteal`` on the nightly math lane and the calibration jobs is a trial, kept only if a
   hosted run shows the gain with 689 passed: the tests here pass with it and without it.
9. The math lanes list their tests over 10 s, keep their JUnit file a week as the code shards do,
   and the lane's row names the processor.
10. The gate's math lane reports against 300 s with a 20-minute limit; the calibration jobs against
    900 s with a 30-minute limit; nightly's are unchanged.

Not done, as ruled no: 6 and 7, narrowing the math lane's triggers. ``test_pf10_7_a_pull_request_runs_the_math_suite_only_when_the_statistics_change``
holds them as they are: a whole statistics file and a whole math test file each run the lane.
Also, by a ruling of 2026-11-05: ``tests/test_json_stdout.py`` leaves the code shards' ``rest``.

**Readings this file fixes**, each put as a yes/no when these tests were frozen.

- **r1** The math lane's two entries in the shard table are named ``math1`` and ``math2``; a name
  ``math`` and a number is a math entry. They are a second cut of the same files: a file may be in a
  code shard and in a math entry, the math entries take nothing from the code shards' ``rest``, and
  among the math entries ``rest`` means every test file no other math entry names.
- **r2** The cut by test is a pytest plugin, ``.github/lanes/cut.py``, loaded as ``-p cut`` with
  ``PYTHONPATH=.github/lanes`` (as ``use_built`` is), and told its part as ``--cut INDEX/TOTAL``. It
  cuts what the marker expression selected, never the whole collection, through one pure function
  ``part(ids, index, total)``, so the proof can run on the ids a collection prints. How it balances
  the parts is the build's to choose.
- **r3** The calibration jobs are one job, ``calibration``, with an eight-way matrix, run on
  ``tests`` whole, so a calibration test in any file runs. It needs only ``changes`` and is one more
  need of ``gate``: on the release pull request the gate waits for it; on a push nobody waits on the
  gate. A matrix that cuts a lane does not fail fast, so one red part does not hide the others.
- **r4** ``changes`` gains the output ``calibration``, written by ``math_lane.py`` beside ``math``
  from ``calibration(event, base_pyproject, head_pyproject, math)``: on a pull request, when
  ``project.version`` differs; on a push, when the math lane runs. ``main`` reads the event from
  ``GITHUB_EVENT_NAME``, which Actions sets in every job.
- **r5** The lane's row gains a column ``processor``: on Linux, the first ``model name`` of
  ``/proc/cpuinfo``; elsewhere whatever ``lane.py`` can read, unpinned.
"""

from __future__ import annotations

import fnmatch
import itertools
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_pf10_ci import (
    PYPROJECT,
    ROOT,
    SCRIPTS,
    env_of,
    import_script,
    jobs,
    lane,
    lanes,
    marker_expression,
    runs,
    selects,
)

#: The math lanes: the gate's (two jobs), the calibration jobs, and nightly's.
MATH_LANES = (("ci.yml", "math"), ("ci.yml", "calibration"), ("nightly.yml", "math"))
#: Where ``--dist worksteal`` may be tried (ruling 8).
WORKSTEAL = {("nightly.yml", "math"), ("ci.yml", "calibration")}
MATH_ENTRY = re.compile(r"math\d+")
STATS_FILE = "tests/test_pf4_stats.py"
PARTS = 8


def table() -> dict[str, list[str]]:
    return import_script("shards").parse(env_of("ci.yml", "tests")["SHARDS"])


def math_entries(parsed: dict[str, list[str]]) -> list[str]:
    return [name for name in parsed if MATH_ENTRY.fullmatch(name)]


def lane_step(name: str, job: str) -> dict[str, Any]:
    (step,) = [s for s in jobs(name)[job]["steps"] if ".github/lanes/lane.py" in s.get("run", "")]
    return step


def legs(name: str, job: str) -> list[dict[str, Any]]:
    """One ``{key: value}`` per leg of the job's matrix; ``[{}]`` for a job with none."""
    matrix = {k: v for k, v in jobs(name)[job].get("strategy", {}).get("matrix", {}).items() if isinstance(v, list)}
    return [dict(zip(matrix, values, strict=True)) for values in itertools.product(*matrix.values())]


def resolve(word: str, name: str, job: str, leg: dict[str, Any]) -> str:
    """``word`` as one leg of the job sees it: shell variables of the lane step's environment (the
    workflow's, the job's, the step's), then ``${{ matrix.X }}`` and ``${{ strategy.job-total }}``."""
    env = {**env_of(name, job), **lane_step(name, job).get("env", {})}
    word = re.sub(r"\$\{?([A-Za-z_]\w*)\}?", lambda m: str(env.get(m.group(1), m.group(0))), word)
    word = re.sub(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}", lambda m: str(leg[m.group(1)]), word)
    word = re.sub(r"\$\{\{\s*strategy\.job-total\s*\}\}", str(len(legs(name, job))), word)
    return word.replace('"', "")


def option(arguments: list[str], name: str) -> list[str]:
    """Every value of ``--name VALUE`` or ``--name=VALUE`` in a lane's arguments."""
    found = []
    for i, word in enumerate(arguments):
        if word == name and i + 1 < len(arguments):
            found.append(arguments[i + 1])
        elif word.startswith(name + "="):
            found.append(word.split("=", 1)[1])
    return found


def collected(*arguments: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> list[str]:
    """The test ids ``pytest --collect-only`` prints for these arguments."""
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-p", "no:warnings", *arguments],
                          cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    return [line.strip() for line in done.stdout.splitlines() if "::" in line and not line.startswith(" ")]


def section(name: str) -> str:
    return (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]


# ---------- 1: the slow math tests leave the gate and still run nightly ----------


def test_the_slow_math_tests_still_run_nightly_in_the_math_lane() -> None:
    expression = marker_expression(lane("nightly.yml", "math"))
    for marks in ({"math", "slow"}, {"math", "calibration", "slow"}, {"math", "calibration"}):
        assert selects(expression, marks), marks


# ---------- 3: the gate's math lane, two jobs by file, through the shard table ----------


def test_the_gate_runs_its_math_lane_as_two_jobs_named_in_the_shard_table() -> None:
    parsed = table()
    entries = math_entries(parsed)
    assert len(entries) == 2, entries
    spec = jobs("ci.yml")["math"]
    assert spec["strategy"]["fail-fast"] is False
    assert [list(leg.values()) for leg in legs("ci.yml", "math")] == [[entry] for entry in entries], "one job per math entry"
    (word,) = re.findall(r'shards\.py\s+("[^"]*"|\S+)', runs("ci.yml", "math"))
    for leg, entry in zip(legs("ci.yml", "math"), entries, strict=True):
        assert resolve(word, "ci.yml", "math", leg) == entry, "each job runs its own entry's files"


def test_every_file_holding_a_math_test_runs_in_exactly_one_math_job_and_the_stats_file_alone_in_one() -> None:
    shards = import_script("shards")
    parsed, tests = table(), shards.test_files()
    assert shards.problems(parsed, tests) == []
    entries = math_entries(parsed)
    files = {entry: shards.files(shards.paths(parsed, entry, tests)) for entry in entries}
    holding = [path for path in tests if re.search(r"mark\.(math|calibration)", (ROOT / path).read_text(encoding="utf-8"))]
    assert STATS_FILE in holding and len(holding) >= 2
    for path in holding:
        assert [entry for entry in entries if path in files[entry]] != [], f"{path} holds math tests and no math job runs it"
        assert len([entry for entry in entries if path in files[entry]]) == 1, path
    assert [STATS_FILE] in files.values(), "tests/test_pf4_stats.py runs alone in one job"


def test_the_math_entries_take_no_file_from_the_code_shards() -> None:
    shards = import_script("shards")
    parsed, tests = table(), shards.test_files()
    code = [name for name in parsed if name.isdigit()] + ["backends"]
    ran = [path for name in code for path in shards.files(shards.paths(parsed, name, tests))]
    assert sorted(ran) == sorted(tests), "every test file in exactly one code shard or the backends job"


def test_json_stdout_runs_in_a_code_shard_that_names_it_not_in_rest() -> None:
    shards = import_script("shards")
    parsed = table()
    named = [name for name in parsed if name.isdigit() and "tests/test_json_stdout.py" in shards.files(parsed[name])]
    assert len(named) == 1, "the ruling of 2026-11-05: out of rest, into one named shard"


# ---------- 4, 5: calibration, cut by test into eight jobs ----------


def test_the_calibration_job_is_eight_parts_of_the_whole_tree_cut_by_test() -> None:
    spec = jobs("ci.yml")["calibration"]
    assert spec["needs"] == ["changes"] and spec["if"] == "needs.changes.outputs.calibration == 'true'"
    assert spec["strategy"]["fail-fast"] is False
    assert len(legs("ci.yml", "calibration")) == PARTS
    assert "continue-on-error" not in spec and not any("continue-on-error" in step for step in spec["steps"]), \
        "a red calibration job turns the run, and main's badge, red"
    assert "calibration" in jobs("ci.yml")["gate"]["needs"]
    arguments = lane("ci.yml", "calibration")
    assert arguments[-1] == "tests", "every file: a calibration test anywhere runs"
    assert [arguments[i + 1] for i, w in enumerate(arguments[:-1]) if w == "-p"].count("cut") == 1
    assert lane_step("ci.yml", "calibration")["env"]["PYTHONPATH"] == ".github/lanes"
    (cut,) = option(arguments, "--cut")
    parts = [resolve(cut, "ci.yml", "calibration", leg) for leg in legs("ci.yml", "calibration")]
    assert sorted(parts) == sorted(f"{i}/{PARTS}" for i in range(1, PARTS + 1)), parts


@pytest.mark.parametrize(("count", "total"), [(0, 8), (1, 8), (7, 8), (8, 8), (9, 8), (40, 8), (166, 8), (10, 3), (5, 1)])
def test_the_parts_of_any_list_hold_each_id_exactly_once(count: int, total: int) -> None:
    cut = import_script("cut")
    ids = [f"tests/test_x.py::test_{i}[{i % 3}-a]" for i in range(count)]
    parts = [cut.part(list(ids), index, total) for index in range(1, total + 1)]
    assert sorted(itertools.chain.from_iterable(parts)) == sorted(ids)
    assert len(set(itertools.chain.from_iterable(parts))) == count
    assert parts == [cut.part(list(ids), index, total) for index in range(1, total + 1)], "the same list cuts the same way"
    if count >= total:
        assert all(parts), "no empty part"


@pytest.mark.parametrize(("index", "total"), [(0, 8), (9, 8), (-1, 8), (1, 0)])
def test_a_part_outside_one_to_total_is_refused(index: int, total: int) -> None:
    with pytest.raises(ValueError):
        import_script("cut").part(["tests/test_x.py::test_a"], index, total)


def test_every_calibration_test_is_in_exactly_one_of_the_eight_jobs() -> None:
    cut = import_script("cut")
    arguments = lane("ci.yml", "calibration")
    ids = collected("-m", marker_expression(arguments), arguments[-1])
    assert ids and all("::" in i for i in ids)
    (word,) = option(arguments, "--cut")
    parts = [resolve(word, "ci.yml", "calibration", leg) for leg in legs("ci.yml", "calibration")]
    held = [cut.part(list(ids), int(p.split("/")[0]), int(p.split("/")[1])) for p in parts]
    assert all(held), "every job runs something"
    every = list(itertools.chain.from_iterable(held))
    assert sorted(every) == sorted(ids), [i for i in ids if every.count(i) != 1]


def test_the_cut_plugin_runs_exactly_its_part_of_what_the_marker_selected(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n    calibration: a rate\n", encoding="utf-8")
    marked = [0, 1, 2, 4, 5, 7, 9]
    body = "import pytest\n\n" + "".join(
        ("@pytest.mark.calibration\n" if k in marked else "") + f"def test_{k}():\n    pass\n\n\n" for k in range(10))
    (tmp_path / "test_suite.py").write_text(body, encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(SCRIPTS)}
    selected = collected("-m", "calibration", "test_suite.py", cwd=tmp_path, env=env)
    assert selected == [f"test_suite.py::test_{k}" for k in marked]
    cut = import_script("cut")
    for index in (1, 2, 3):
        mine = collected("-p", "cut", "--cut", f"{index}/3", "-m", "calibration", "test_suite.py", cwd=tmp_path, env=env)
        assert mine == [i for i in selected if i in cut.part(list(selected), index, 3)], index
    for bad in ("0/3", "4/3", "x"):
        # A part that does not exist is a usage error and runs nothing, never an empty green part.
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "cut", "--cut", bad,
                               "-m", "calibration", "test_suite.py"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
        assert done.returncode == 4 and "passed" not in done.stdout, (bad, done.returncode, done.stdout + done.stderr)


# ---------- 4, 5: when calibration runs ----------

BASE = '[project]\nname = "poisson-prove"\nversion = "0.2.1"\ndependencies = ["numpy>=2.0"]\n'
BUMPED = BASE.replace('"0.2.1"', '"0.2.2"')
NEW_DEPENDENCY = BASE.replace('"numpy>=2.0"', '"numpy>=2.1"')


@pytest.mark.parametrize(("event", "base", "head", "math", "runs_it"), [
    ("pull_request", BASE, BASE, True, False),
    ("pull_request", BASE, BASE, False, False),
    ("pull_request", BASE, NEW_DEPENDENCY, True, False),
    ("pull_request", BASE, BUMPED, False, True),
    ("pull_request", BASE, BUMPED, True, True),
    ("push", BASE, BASE, True, True),
    ("push", BASE, BASE, False, False),
    ("push", BASE, BUMPED, False, False),
], ids=["a-statistics-pull-request", "an-ordinary-pull-request", "a-requirement-but-not-the-version", "the-release-pull-request",
        "a-release-that-changes-the-statistics", "a-push-that-ran-the-math-lane", "a-push-that-did-not", "the-release-merged-without-statistics"])
def test_calibration_runs_on_the_release_pull_request_and_on_a_push_that_ran_the_math_lane(
    event: str, base: str, head: str, math: bool, runs_it: bool
) -> None:
    why = import_script("math_lane").calibration(event, base, head, math)
    assert bool(why) is runs_it, why
    if runs_it and base != head:
        assert "0.2.2" in " ".join(why), "the reason names the version the release pull request sets"


def pyproject(version: str | None = None) -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    return text if version is None else re.sub(r'(?m)^version = "[^"]+"$', f'version = "{version}"', text, count=1)


@pytest.mark.parametrize(("event", "changed", "head_version", "math", "calibration"), [
    ("pull_request", ["CHANGELOG.md", "pyproject.toml", "src/poisson_prove/__init__.py"], "9.9.9", "false", "true"),
    ("pull_request", ["src/poisson_prove/stats.py"], None, "true", "false"),
    ("push", ["src/poisson_prove/stats.py"], None, "true", "true"),
    ("push", ["README.md"], None, "false", "false"),
], ids=["the-release-pull-request", "a-statistics-pull-request", "a-push-that-runs-the-math-lane", "a-push-that-does-not"])
def test_the_math_lane_script_writes_the_calibration_output_beside_math(
    event: str, changed: list[str], head_version: str | None, math: str, calibration: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    math_lane = import_script("math_lane")
    base_sha, head_sha = "a" * 40, "b" * 40
    shown = {f"{base_sha}:pyproject.toml": pyproject(), f"{head_sha}:pyproject.toml": pyproject(head_version)}

    def git(*args: str) -> str:
        if args[0] == "diff":
            return "\n".join(changed) + "\n"
        if args[0] == "grep":
            return f"{head_sha}:{STATS_FILE}\n"
        if args[0] == "show":
            return shown[args[1]]
        raise AssertionError(f"math_lane.py asked git for more than the diff, the math tests and the two pyproject files: {args}")

    monkeypatch.setattr(math_lane, "git", git)
    monkeypatch.setattr(math_lane, "resolved", lambda _pyproject: {"numpy": "2.4.6"})
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert math_lane.main(base_sha, head_sha) == 0
    written = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    assert written == {"math": math, "calibration": calibration}


# ---------- 8: worksteal, a trial either way ----------


def test_worksteal_is_tried_only_on_the_nightly_math_lane_and_the_calibration_jobs() -> None:
    # Ruling 8 is a trial: the build keeps --dist worksteal only if a hosted run shows the gain with
    # 689 passed. So this holds where it may be, and that nothing else is put there; it is not
    # required anywhere.
    for name, job, arguments in lanes():
        found = [value.strip('"') for value in option(arguments, "--dist")]
        if (name, job) in WORKSTEAL:
            assert set(found) <= {"worksteal"}, (name, job, found)
        else:
            assert "worksteal" not in found, (name, job)


# ---------- 9: what the math lanes measure, and keep ----------


@pytest.mark.parametrize(("name", "job"), [("ci.yml", "tests"), *MATH_LANES])
def test_the_lane_lists_its_tests_over_ten_seconds_and_keeps_its_junit_file_a_week(name: str, job: str) -> None:
    arguments = lane(name, job)
    assert arguments[2:4] == ["--over", "10"], (name, job)
    uploads = [s for s in jobs(name)[job]["steps"] if s.get("uses", "").startswith("actions/upload-artifact@")
               and "junit" in str(s.get("with", {}).get("path", ""))]
    assert len(uploads) == 1, (name, job)
    (upload,) = uploads
    assert upload["if"] == "always()" and upload["with"]["retention-days"] == 7, (name, job)
    for leg in legs(name, job) or [{}]:
        folder = f"/tmp/lane-{resolve(arguments[0], name, job, leg)}-k2j3h4/junit.xml"
        assert fnmatch.fnmatch(folder, resolve(upload["with"]["path"], name, job, leg)), (name, job, leg, folder)


@pytest.mark.parametrize("name", ["ci.yml", "nightly.yml"])
def test_no_two_jobs_of_a_run_keep_an_artifact_under_one_name(name: str) -> None:
    kept = [resolve(str(s["with"]["name"]), name, job, leg)
            for job, spec in jobs(name).items() if any(".github/lanes/lane.py" in s.get("run", "") for s in spec["steps"])
            for s in spec["steps"] if s.get("uses", "").startswith("actions/upload-artifact@")
            for leg in legs(name, job) or [{}]]
    assert len(kept) == len(set(kept)), kept


# ---------- 10: budgets and time limits ----------


def test_the_math_lanes_have_their_time_limits() -> None:
    # Their budgets are in test_pf10_8_each_lane_reports_against_its_hosted_budget.
    limits = {key: jobs(key[0])[key[1]]["timeout-minutes"] for key in MATH_LANES}
    assert limits == {("ci.yml", "math"): 20, ("ci.yml", "calibration"): 30, ("nightly.yml", "math"): 120}


# ---------- the words ----------


def test_contributing_names_the_calibration_jobs_in_ci() -> None:
    assert "calibration" in section("CI")
