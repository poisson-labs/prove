"""The ``next:`` chain has no dead ends: the sweep, report, diff and runs on an all-errored run.

**What is pinned.** Real commands in processes of their own, over stores real sweeps wrote, in the
plain rendering, with the store typed as a relative folder so that no output carries a test's own
temporary path.

- A sweep in which every rollout errored suggests ``inspect`` with ``--limit 3``, so a first-time
  user is not flooded with every failing episode. Grouping identical errors is not in this release.
- ``report`` ends with a ``next:`` line, and ``--json`` carries the same command.
- ``diff`` on a run where every episode errored names the run, says so in plain words and gives a
  ``next:`` line that works, in the one ``error:`` line then ``next:`` lines shape.
- ``runs`` shows an all-errored run as ``stopped``, as the sweep already does.

**Readings this file fixes.**

- **r1** The ``next:`` line of ``report`` is the dashboard, ``ui``: a command with a result that
  runs from any shell, carrying the store only when one was typed.
- **r2** ``diff``'s ``next:`` is ``inspect`` of the errored run on its commonest error, with
  ``--limit 3`` for the same reason as the sweep's. When both runs errored, one line for each.
- **r3** ``report`` and ``check`` of an all-errored run stop at the same dead end as ``diff`` today,
  so they answer as ``diff`` does.
- **r4** What ``runs`` calls ``stopped`` is a run the store holds as complete, with rows, none of
  them with an outcome. A partial run stays ``partial``, since it can still be resumed, and a run
  with some outcomes stays ``complete``.
- **r5** The manifest and ``runs --json`` keep the stored status: the sweep's own ``--json`` has
  ``status`` beside its verdict in the same way, and a change to output a tool reads waits for a
  minor release. ``rows`` and ``no_outcome`` carry the fact there.
- **r6** The dashboard and the terminal app read one view of a run, and the app shows what the
  command prints, so that view says ``stopped`` too.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import core

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
COMMAND = "poisson-prove"
#: What a person cannot type: the placeholders a command line must not carry.
PLACEHOLDER = re.compile(r"(?<![\w-])(A|B|RUN|NAME|AXIS|EVENT)(?![\w-])")
#: The internal words a plain error must not use.
NOT_PLAIN = re.compile(r"null|NaN|\bNone\b|infer|outcome counts|Traceback", re.IGNORECASE)

TARGETS = """\
import time

from poisson_prove import Episode


def good(cfg, seed):
    # Two outcomes, one the commonest, whatever the salt: anything else is a refusal of its own.
    return Episode(outcome="violated" if cfg["cell"] == "c" else "completed", t=1, horizon=10, meta={})


def broken(cfg, seed):
    raise ValueError("this rollout always raises")


def broken_otherwise(cfg, seed):
    raise RuntimeError("this rollout always raises")


def mostly_type_error(cfg, seed):
    if cfg["cell"] == "a":
        raise KeyError("this rollout always raises")
    raise TypeError("this rollout always raises")


def some_errored(cfg, seed):
    if cfg["cell"] == "a":
        raise ValueError("half of this rollout's cells raise")
    return good(cfg, seed)


def wrong_return(cfg, seed):
    return {"outcome": "completed", "t": 1}


def sleeps(cfg, seed):
    time.sleep(30)
"""

SPEC = """\
target_id = "agent"
t_unit = "tool_calls"
replicates = 3

[axes.cell]
type = "categorical"
values = ["a", "b", "c"]
"""
#: The spec's three cells at three replicates.
ROLLOUTS = 9


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def nexts(self) -> list[str]:
        """Every ``next:`` command, from either stream, as a person would copy it."""
        found = re.findall(r"^  next: (.*)$", self.out + "\n" + self.err, flags=re.MULTILINE)
        return [str(line) for line in found]


def child_env(base: Path, **extra: str) -> dict[str, str]:
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "PYTHONIOENCODING", "CI", "BROWSER")
    env = {key: value for key, value in os.environ.items() if key not in drop}
    home = base / "home"
    home.mkdir(exist_ok=True)
    env.update(PYTHONPATH=os.pathsep.join([str(SRC), str(base)]), HOME=str(home), NO_COLOR="1", COLUMNS="200", PYTHONIOENCODING="utf-8")
    env.update(extra)
    return env


def prove(base: Path, *argv: str, **extra: str) -> Result:
    done = subprocess.run(
        [sys.executable, "-m", "poisson_prove", "--plain", *argv], cwd=base, env=child_env(base, **extra),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=300,
    )
    return Result(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


def sweep(base: Path, store: str, target: str, *more: str) -> Result:
    return prove(base, "--store", store, "sweep", "spec.toml", "--target", f"targets:{target}", "--yes", "--max-mde", "1", *more)


def follow(base: Path, command: str, *more: str, **extra: str) -> Result:
    """Run a printed ``next:`` command as a person would, word for word."""
    words = shlex.split(command)
    assert words[0] == COMMAND, command
    return prove(base, *words[1:], *more, **extra)


def listed(base: Path, store: str) -> list[dict[str, Any]]:
    result = prove(base, "--store", store, "runs", "--json")
    assert result.code == 0, result
    return list(json.loads(result.out)["runs"])


def run_of(base: Path, store: str, position: int) -> dict[str, Any]:
    """A run of the store by the order of its sweeps, the first being 0."""
    return sorted(listed(base, store), key=lambda run: str(run["created_at"]))[position]


def status_cell(base: Path, store: str, run: dict[str, Any]) -> list[str]:
    """The cells of the run's row in ``runs``: one space inside a name, two or more between cells."""
    result = prove(base, "--store", store, "runs")
    assert result.code == 0, result
    (row,) = [line for line in result.out.splitlines() if str(run["run_id"]) in line]
    return re.split(r"\s{2,}", row.strip())


def assert_one_error_then_nexts(result: Result) -> str:
    """The look's shape: one ``error:`` line, only ``next:`` lines after it, nothing on stdout, exit
    1. Returns the error line."""
    assert result.code == 1, result
    assert result.out == "", result
    lines = [line for line in result.err.splitlines() if not line.startswith("note: ")]
    assert lines and lines[0].startswith("error: "), result
    assert all(line.startswith("  next: ") for line in lines[1:]), result
    assert len(lines) > 1, f"no next: line: {result}"
    assert not PLACEHOLDER.search(" ".join(result.nexts)), result
    return lines[0]


def assert_plain(line: str, *errored_names: str) -> None:
    for name in errored_names:
        assert name in line, line
    assert "errored" in line, line
    assert not NOT_PLAIN.search(line), line


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("chain")
    (folder / "targets.py").write_text(TARGETS, encoding="utf-8")
    (folder / "spec.toml").write_text(SPEC, encoding="utf-8")
    # A good run first, then an all-errored one, then another good one.
    assert sweep(folder, "mixed", "good").code == 0
    assert sweep(folder, "mixed", "broken").code == 3
    assert sweep(folder, "mixed", "good").code == 0
    assert sweep(folder, "mixed", "some_errored").code == 0
    # The bare diff's two orders: the errored run is previous, then latest.
    assert sweep(folder, "errored-first", "broken").code == 3
    assert sweep(folder, "errored-first", "good").code == 0
    assert sweep(folder, "errored-last", "good").code == 0
    assert sweep(folder, "errored-last", "broken").code == 3
    # Both runs errored, each its own way.
    assert sweep(folder, "both", "broken").code == 3
    assert sweep(folder, "both", "broken_otherwise").code == 3
    # Stopped short with every kept row errored: still partial and resumable.
    assert sweep(folder, "partial", "broken", "--max-rollouts", "2").code == 3
    return folder


# ---------- the sweep's next: line carries --limit 3 ----------


def test_a_sweep_in_which_every_rollout_errored_suggests_inspect_with_limit_3(base: Path) -> None:
    result = sweep(base, "one-errored", "broken")
    assert result.code == 3, result
    assert any(line.startswith("stopped  ") for line in result.out.splitlines()), result
    (command,) = result.nexts
    words = shlex.split(command)
    assert words[:3] == [COMMAND, "inspect", "latest"], command
    assert words[words.index("--event") + 1] == "ValueError", command
    assert words[words.index("--limit") + 1] == "3", command
    assert words[words.index("--store") + 1] == "one-errored", command


def test_the_sweeps_json_next_is_the_same_command_as_its_text(base: Path) -> None:
    text = sweep(base, "json-errored", "broken")
    document = sweep(base, "json-errored", "broken", "--json")
    assert document.code == 3, document
    assert json.loads(document.out)["next"] == text.nexts, (document, text)
    assert "--limit" in text.nexts[0], text


def test_following_the_sweeps_next_line_shows_three_episodes_of_all_the_errored_ones(base: Path) -> None:
    result = sweep(base, "follow-errored", "broken")
    (command,) = result.nexts
    followed = follow(base, command, "--json")
    assert followed.code == 0, followed
    document = json.loads(followed.out)
    assert len(document["episodes"]) == 3, document
    assert listed(base, "follow-errored")[0]["no_outcome"] == ROLLOUTS


def test_a_sweep_of_timeouts_also_suggests_inspect_with_limit_3(base: Path) -> None:
    result = sweep(base, "timeouts", "sleeps", "--episode-timeout", "0.2")
    assert result.code == 3, result
    (command,) = result.nexts
    words = shlex.split(command)
    assert words[words.index("--event") + 1] == "episode_timeout", command
    assert words[words.index("--limit") + 1] == "3", command


def test_a_commonest_error_with_spaces_stays_one_word_of_a_command_that_runs(base: Path) -> None:
    result = sweep(base, "spaces", "wrong_return")
    assert result.code == 3, result
    (command,) = result.nexts
    assert shlex.split(command)[shlex.split(command).index("--limit") + 1] == "3", command
    followed = follow(base, command)
    assert followed.code == 0, followed


# ---------- report ends with a next: line ----------


def report_cases(base: Path) -> dict[str, list[str]]:
    first, second = run_of(base, "mixed", 0)["run_id"], run_of(base, "mixed", 2)["run_id"]
    return {"one run": [str(second)], "two runs": [str(first), str(second)]}


@pytest.mark.parametrize("case", ["one run", "two runs"])
def test_report_ends_with_a_next_line_for_the_dashboard(base: Path, tmp_path: Path, case: str) -> None:
    runs = report_cases(base)[case]
    result = prove(base, "--store", "mixed", "report", *runs, "--x", "cell", "--out", str(tmp_path / "out"))
    assert result.code == 0, result
    lines = [line for line in result.out.splitlines() if line.strip()]
    assert lines[-1].startswith(f"  next: {COMMAND} "), result.out
    (command,) = result.nexts
    words = shlex.split(command)
    assert words[:2] == [COMMAND, "ui"], command
    assert words[words.index("--store") + 1] == "mixed", "the next line acts on the store that was typed"
    assert not PLACEHOLDER.search(command), command


@pytest.mark.parametrize("case", ["one run", "two runs"])
def test_following_reports_next_line_works(base: Path, tmp_path: Path, case: str) -> None:
    runs = report_cases(base)[case]
    result = prove(base, "--store", "mixed", "report", *runs, "--x", "cell", "--out", str(tmp_path / "out"))
    (command,) = result.nexts
    # Should the line carry --open, the browser it opens is a command that does nothing.
    followed = follow(base, command, BROWSER="true")
    assert followed.code == 0, followed
    assert followed.out.startswith("ok  "), followed


@pytest.mark.parametrize("case", ["one run", "two runs"])
def test_reports_json_next_is_the_same_command_as_its_text(base: Path, tmp_path: Path, case: str) -> None:
    runs = report_cases(base)[case]
    text = prove(base, "--store", "mixed", "report", *runs, "--x", "cell", "--out", str(tmp_path / "text"))
    document = prove(base, "--store", "mixed", "report", *runs, "--x", "cell", "--out", str(tmp_path / "json"), "--json")
    assert document.code == 0, document
    assert text.nexts and json.loads(document.out)["next"] == text.nexts, (document.out[-400:], text.nexts)


def test_reports_next_line_names_no_store_when_none_was_typed(base: Path, tmp_path: Path) -> None:
    folder = tmp_path / "default-store"
    folder.mkdir()
    (folder / "targets.py").write_text(TARGETS, encoding="utf-8")
    (folder / "spec.toml").write_text(SPEC, encoding="utf-8")
    assert prove(folder, "sweep", "spec.toml", "--target", "targets:good", "--yes", "--max-mde", "1").code == 0
    result = prove(folder, "report", "latest", "--x", "cell", "--out", "out")
    assert result.code == 0, result
    (command,) = result.nexts
    assert shlex.split(command)[:2] == [COMMAND, "ui"] and "--store" not in command, command


# ---------- diff on an all-errored run ----------


@pytest.mark.parametrize("store,errored,good", [("errored-first", 0, 1), ("errored-last", 1, 0)], ids=["errored-is-previous", "errored-is-latest"])
def test_the_bare_diff_names_the_errored_run_in_plain_words_and_gives_a_next_line(base: Path, store: str, errored: int, good: int) -> None:
    bad_run, good_run = run_of(base, store, errored), run_of(base, store, good)
    result = prove(base, "--store", store, "diff")
    line = assert_one_error_then_nexts(result)
    assert_plain(line, str(bad_run["run_name"]))
    assert str(good_run["run_name"]) not in line, line


@pytest.mark.parametrize("more", [[], ["--event", "violated"]], ids=["event-inferred", "event-given"])
def test_diff_of_two_named_runs_answers_the_same(base: Path, more: list[str]) -> None:
    bad_run, good_run = run_of(base, "mixed", 1), run_of(base, "mixed", 0)
    for pair in ([good_run, bad_run], [bad_run, good_run]):
        result = prove(base, "--store", "mixed", "diff", str(pair[0]["run_id"]), str(pair[1]["run_id"]), *more)
        line = assert_one_error_then_nexts(result)
        assert_plain(line, str(bad_run["run_name"]))
        assert str(good_run["run_name"]) not in line, line


def test_diffs_next_line_inspects_the_errored_run_on_its_commonest_error_with_limit_3(base: Path) -> None:
    bad_run = run_of(base, "errored-first", 0)
    result = prove(base, "--store", "errored-first", "diff")
    (command,) = result.nexts
    words = shlex.split(command)
    assert words[:2] == [COMMAND, "inspect"], command
    assert words[words.index("--event") + 1] == "ValueError", command
    assert words[words.index("--limit") + 1] == "3", command
    assert words[words.index("--store") + 1] == "errored-first", command
    followed = follow(base, command, "--json")
    assert followed.code == 0, followed
    document = json.loads(followed.out)
    assert document["run_id"] == bad_run["run_id"] and len(document["episodes"]) == 3, document


def test_diff_when_both_runs_errored_names_both_and_gives_a_next_line_for_each(base: Path) -> None:
    first, second = run_of(base, "both", 0), run_of(base, "both", 1)
    result = prove(base, "--store", "both", "diff")
    line = assert_one_error_then_nexts(result)
    assert_plain(line, str(first["run_name"]), str(second["run_name"]))
    assert len(result.nexts) == 2, result
    seen = {}
    for command in result.nexts:
        followed = follow(base, command, "--json")
        assert followed.code == 0, followed
        document = json.loads(followed.out)
        seen[document["run_id"]] = document["event"]
    assert seen == {first["run_id"]: "ValueError", second["run_id"]: "RuntimeError"}, seen


def test_diff_with_json_still_answers_on_stderr_and_exits_1(base: Path) -> None:
    bad_run = run_of(base, "errored-first", 0)
    result = prove(base, "--store", "errored-first", "diff", "--json")
    line = assert_one_error_then_nexts(result)
    assert_plain(line, str(bad_run["run_name"]))


def test_diff_with_a_run_that_has_some_outcomes_is_not_called_errored(base: Path) -> None:
    good_run, some = run_of(base, "mixed", 0), run_of(base, "mixed", 3)
    assert 0 < some["no_outcome"] < some["rows"], some
    result = prove(base, "--store", "mixed", "diff", str(good_run["run_id"]), str(some["run_id"]))
    assert result.code == 0, result
    assert "error: " not in result.err, result


# ---------- report and check of an all-errored run answer as diff does ----------


def test_report_of_two_runs_one_all_errored_answers_as_diff_does(base: Path, tmp_path: Path) -> None:
    bad_run, good_run = run_of(base, "mixed", 1), run_of(base, "mixed", 0)
    out = tmp_path / "out"
    result = prove(base, "--store", "mixed", "report", str(good_run["run_id"]), str(bad_run["run_id"]), "--x", "cell", "--out", str(out))
    line = assert_one_error_then_nexts(result)
    assert_plain(line, str(bad_run["run_name"]))
    assert "inspect" in result.nexts[0] and "--limit 3" in result.nexts[0], result
    assert not out.exists(), "a refusal writes nothing"


def test_report_of_one_all_errored_run_answers_as_diff_does(base: Path, tmp_path: Path) -> None:
    bad_run = run_of(base, "mixed", 1)
    out = tmp_path / "out"
    result = prove(base, "--store", "mixed", "report", str(bad_run["run_id"]), "--x", "cell", "--out", str(out))
    line = assert_one_error_then_nexts(result)
    assert_plain(line, str(bad_run["run_name"]))
    assert "inspect" in result.nexts[0] and "--limit 3" in result.nexts[0], result
    assert not out.exists(), "a refusal writes nothing"


def test_check_of_an_all_errored_run_answers_as_diff_does(base: Path) -> None:
    bad_run, good_run = run_of(base, "mixed", 1), run_of(base, "mixed", 0)
    result = prove(base, "--store", "mixed", "check", str(good_run["run_id"]), str(bad_run["run_id"]), "--event", "violated")
    line = assert_one_error_then_nexts(result)
    assert_plain(line, str(bad_run["run_name"]))
    assert "inspect" in result.nexts[0] and "--limit 3" in result.nexts[0], result


# ---------- runs shows an all-errored run as stopped ----------


def test_runs_shows_an_all_errored_run_as_stopped(base: Path) -> None:
    bad_run = run_of(base, "mixed", 1)
    cells = status_cell(base, "mixed", bad_run)
    assert "stopped" in cells and "complete" not in cells, cells


def test_runs_keeps_complete_for_a_good_run_and_for_a_run_with_some_outcomes(base: Path) -> None:
    for position in (0, 2, 3):
        run = run_of(base, "mixed", position)
        cells = status_cell(base, "mixed", run)
        assert "complete" in cells and "stopped" not in cells, (position, cells)


def test_runs_keeps_partial_for_a_run_that_stopped_short_with_every_kept_row_errored(base: Path) -> None:
    (run,) = listed(base, "partial")
    assert run["rows"] == run["no_outcome"] > 0, run
    cells = status_cell(base, "partial", run)
    assert "partial" in cells and "stopped" not in cells, cells


def test_the_stored_status_and_runs_json_stay_complete_for_an_all_errored_run(base: Path) -> None:
    bad_run = run_of(base, "mixed", 1)
    assert prove(base, "--store", "mixed", "runs").code == 0
    manifest = json.loads((base / "mixed" / str(bad_run["run_id"]) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete", "listing a run changes nothing in the store"
    assert bad_run["status"] == "complete" and bad_run["rows"] == bad_run["no_outcome"] == ROLLOUTS, bad_run
    assert "stopped" in status_cell(base, "mixed", bad_run), "the fact the text shows is the fact the numbers carry"


def test_the_dashboard_and_the_apps_view_of_an_all_errored_run_say_stopped(base: Path) -> None:
    bad_run, good_run = run_of(base, "mixed", 1), run_of(base, "mixed", 0)
    opened = core.open_store(str(base / "mixed"))
    rows = {row["run_id"]: row for row in core.view(opened, "index.html").document["runs"]}
    assert rows[bad_run["run_id"]]["status"] == "stopped", rows[bad_run["run_id"]]
    assert rows[good_run["run_id"]]["status"] == "complete", rows[good_run["run_id"]]
    assert core.view(opened, f"runs/{bad_run['run_id']}.html").document["status"] == "stopped"
    assert core.view(opened, f"runs/{good_run['run_id']}.html").document["status"] == "complete"
