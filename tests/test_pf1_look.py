"""PF1, the look and the errors (plain): the frozen tests.

Covers invariants PF1.1 to PF1.15, under the four decisions listed below.

What PF1 promises, in one line: every verb behaves as the lab's other tools do. Exit codes mean
one thing each (0 done, 1 refused, 2 a wrong command line, 3 stopped or failed after work started,
4 a check that did not pass, 130 interrupted); a problem is one ``error:`` line on stderr followed
only by ``  next:`` lines; a warning is one ``note:`` line; an unexpected failure names a log
instead of printing a traceback; help, ``--version``, ``--json``, numbers, pipes and encodings
read the same everywhere.

**The decisions this file is written under.**

- PF1.15's first-line shape covers what PF1 gives words to: ``sweep`` (its plan comes
  first), ``check`` (``passed``/``failed``), ``paired --cap-check`` (``under cap``/``at cap``),
  Ctrl-C's ``stopped`` line, and the three refusals that keep a plan. The other verbs' first
  lines are PF2's (PF2.9). PF1.15's rule for stderr lines covers the whole corpus.
- PF1.2's refusal corpus is the refusals in ``CORPUS``. The ambiguous run name and the pair
  with no comparable condition are refused under the same assertions in PF2's and PF4's tests.
- A sweep in which every rollout errored names its commonest error by what ``inspect
  --event`` matches: ``timeout`` for timeouts, otherwise the exception's type name (the last line
  of the stored traceback, up to its colon); ``inspect --event TYPE`` selects the errored rows of
  that type.
- Rule 10 prints rates, shares, deltas and minimum detectable effects as fractions to three
  decimals, in every verb's text output and in ``report.md``, ``receipt.html`` and the heatmap's
  labels. The served page and the prose inside JSON structures keep their wording (the look
  rules are for the terminal only).

**Two readings, named here.** PF1.7's "help text on every option with its default or 'no
default'" is read this way: every argument and option has
help text, and every option that takes a value states its default; a flag that takes no value
(``--yes``, ``--json``) needs only its help text. PF1.2's last sentence covers ``inspect``'s
``--event`` as well as ``check``'s and ``serve``'s: shown required in the usage line, refused
with exit 1 when missing.

**The corpus.** ``CORPUS`` below is the list of invocations PF1.1, PF1.2, PF1.3, PF1.5, PF1.10,
PF1.11, PF1.14 and PF1.15 read: every verb on a store holding one paired pair of the keyless mock
agent (1,080 rollouts each, so counts carry separators), every refusal PF1.2 reads, every
kind of wrong command line, every ``--help``, ``--version`` and every ``--json``. Each runs once
per module as ``python -m poisson_prove`` in a process of its own, with this checkout's ``src``
first on its path, ``HOME`` pointed at an empty folder and no store variable set. Ctrl-C, the
unexpected failure, the pseudo-terminal and the encodings have tests of their own.

**Suites.** Every test here is in the code suite by the project's rule (ten seconds of setup and
call on the runner decides it; a test over that is marked ``slow``).

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF1.1 every exit code is one of 0, 1, 2, 3, 4, 130 | ``test_pf1_1_*`` |
| PF1.2 a refusal: exit 1, one ``error:`` line, only ``next:`` lines, stdout empty or the plan | ``test_pf1_2_*`` |
| PF1.3 a wrong command line: exit 2, one ``error:`` line, stdout empty | ``test_pf1_3_*`` |
| PF1.4 an unexpected failure: exit 3, one line naming the log, the log appended | ``test_pf1_4_*`` |
| PF1.5 no traceback, repr, path or source line on stderr; a warning is one ``note:`` | ``test_pf1_5_*`` |
| PF1.6 Ctrl-C exits 130 on every verb and leaves nothing half written | ``test_pf1_6_*`` |
| PF1.7 help: description, every option with its default, required shown, an example | ``test_pf1_7_*`` |
| PF1.8 ``--version`` | ``test_pf1_8_*`` |
| PF1.9 the tool's own options before or after the verb; abbreviations refused | ``test_pf1_9_*`` |
| PF1.10 rule 10 in text, unformatted values in JSON | ``test_pf1_10_*`` |
| PF1.11 ``--json`` on every verb; with PF0.12 carried: ``runs --json`` names an old run's writer | ``test_pf1_11_*`` |
| PF1.12 ASCII stdout, a closed pipe, UTF-8 files | ``test_pf1_12_*`` |
| PF1.13 the sweep's plan, its three refusals, and the two ways a sweep stops short | ``test_pf1_13_*`` |
| PF1.14 ``check`` and ``paired --cap-check`` words and exit 4 | ``test_pf1_14_*`` |
| PF1.15 the first stdout line and every stderr line | ``test_pf1_15_*`` |
"""

from __future__ import annotations

import json
import os
import platform
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from test_pf4_surfaces import _ref_gate

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
OLD = TESTS / "fixtures" / "stores-0.0.1"
OLD_RUNS: dict[str, str] = json.loads((OLD / "runs.json").read_text(encoding="utf-8"))
BU_TARGETS = TESTS / "bu_fixtures" / "targets"
MOCK = "poisson_prove.examples.mock_agent"

RUN_ID = re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{4}\b")
#: Rule 3: a lowercase verdict word or phrase, two spaces, then the sentence.
FIRST_LINE = re.compile(r"^[a-z][a-z ]*  \S")
#: A progress line on stderr: ``<n>/<total>``, counts with separators.
PROGRESS = re.compile(r"^\d{1,3}(?:,\d{3})*/\d{1,3}(?:,\d{3})*$")
ERRORS_LOG = "~/.cache/poisson-prove/errors.log"
TRACEBACK = "Traceback (most recent call last)"

#: 9 conditions x 120 replicates = 1,080 rollouts.
#: PF4.30: this is the quickstart's design at 120 replicates with no kind declared. Its exact
#: limit at level q / 9 is 0.240 at base rate 0.400, over the default accepted change of
#: 0.200, so N=120 does not clear the gate on its own: every sweep of it
#: accepts ``MAX_MDE``, the smallest round value above that limit.
SPEC = """\
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 120

[axes.task_id]
type = "categorical"
values = ["search", "checkout", "refund"]

[axes.tool_fail_rate]
type = "continuous"
values = [0.0, 0.3, 0.55]
"""
MAX_MDE = "0.3"
#: The same design at N=10: its smallest detectable change is over the default 0.200.
LOW_SPEC = SPEC.replace("replicates = 120", "replicates = 10")
#: PF4.30, PF4.48a: the gate's limit for LOW_SPEC is the exact Fisher limit at level q / 9 at
#: its worst base rate, computed from the stats file's references.
LOW_LIMIT = _ref_gate(10, 9, 0.2)[2]
#: Three cells of three replicates for the targets that never return an episode.
TRIPLE_SPEC = """\
target_id = "pf1-errors"
t_unit = "steps"
replicates = 3

[axes.cell]
type = "categorical"
values = ["a", "b", "c"]
"""
#: A spec the sampler refuses for an unknown field in a table it validates.
BAD_CAPTURE_SPEC = SPEC + "\n[capture]\nnot_a_field = true\n"

#: Targets for the sweeps that stop short. ``interrupted`` raises KeyboardInterrupt on its 300th
#: call; ``mostly_value_error`` raises KeyError in cell a (the first to run, and its message
#: names the other type) and ValueError in cells b and c, so ValueError is the commonest error;
#: ``sleeps`` outlives any episode timeout.
TARGETS = """\
import time

from poisson_prove.examples.mock_agent import rollout as _mock

_calls = 0


def interrupted(cfg, seed):
    global _calls
    _calls += 1
    if _calls == 300:
        raise KeyboardInterrupt
    return _mock(cfg, seed)


def mostly_value_error(cfg, seed):
    if cfg["cell"] == "a":
        raise KeyError("not a ValueError")
    raise ValueError("the commoner error")


def sleeps(cfg, seed):
    time.sleep(30)
"""

#: Makes ``import modal`` fail as if the package were not installed, whatever the environment has.
NO_MODAL_SITECUSTOMIZE = "import sys\nsys.modules['modal'] = None\n"
#: A stand-in modal package: importable, and loud if anything reaches into it.
FAKE_MODAL = """\
__version__ = "99.0.0"


class StandInUsed(AttributeError):
    pass


def __getattr__(name):
    raise StandInUsed(f"the stand-in modal package was used: modal.{name}")
"""
#: A stand-in burla package, importable so a missing extra is never the refusal a test reads.
FAKE_BURLA = FAKE_MODAL.replace('"99.0.0"', '"1.8.2"').replace("modal", "burla")

PAIRED_DECLARATION = """\
value_key = "answers.q1.score"
cluster_key = "item"
stratum_key = "cut"
request_span = "scorer.request"
model_key = "model"
model_pin = "scorer-1.13.0"
exemptions = ["x-request-id"]
headers = "not_recorded"
retries = "not_recorded"
bootstrap_b = 200
bootstrap_seed = 20260922
{cap}
[[cuts]]
name = "c60"
threshold = 0.60
comparison = "ge"

[[sweeps]]
name = "S1"
a = "S1-a"
b = "S1-b"
"""


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: list[str]) -> Result:
    """``poisson-prove ARGV`` in this process, reading the environment and cwd as they are."""
    from poisson_prove import cli

    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def child_env(home: Path, *paths: Path, **extra: str) -> dict[str, str]:
    """The environment of a ``poisson-prove`` process: this checkout's ``src`` first on its path,
    then ``paths``; ``HOME`` empty; no store variable; UTF-8 streams unless ``extra`` says not."""
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "PYTHONIOENCODING", "NO_COLOR", "CI")
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(PYTHONPATH=os.pathsep.join([str(SRC), *(str(p) for p in paths)]), HOME=str(home), COLUMNS="100", PYTHONIOENCODING="utf-8")
    env.update(extra)
    return env


def prove(argv: list[str], *, home: Path, cwd: Path, paths: tuple[Path, ...] = (), timeout: float = 300, **extra: str) -> Result:
    done = subprocess.run(
        [sys.executable, "-m", "poisson_prove", *argv], cwd=cwd, env=child_env(home, *paths, **extra),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
    )
    return Result(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


def prove_with(prelude: str, argv: list[str], *, home: Path, cwd: Path, paths: tuple[Path, ...] = (), timeout: float = 300, **extra: str) -> Result:
    """The command's own entry point, ``poisson_prove.cli:main``, after ``prelude`` ran."""
    script = prelude + "\nimport sys\nfrom poisson_prove.cli import main\nsys.exit(main(sys.argv[1:]))\n"
    done = subprocess.run(
        [sys.executable, "-c", script, *argv], cwd=cwd, env=child_env(home, *paths, **extra),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
    )
    return Result(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


def default_sigint() -> None:
    """A child started from a background shell inherits SIGINT ignored; Ctrl-C needs it live."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def run_ids(store: Path) -> set[str]:
    return {p.name for p in store.iterdir() if (p / "manifest.json").is_file()} if store.is_dir() else set()


def manifest(store: Path, run_id: str) -> dict[str, Any]:
    return json.loads((store / run_id / "manifest.json").read_text(encoding="utf-8"))


def listing(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def strict_json(text: str) -> Any:
    def refuse(token: str) -> Any:
        raise ValueError(f"not strict JSON: {token}")

    return json.loads(text, parse_constant=refuse)


def p_text(p: float) -> str:
    """Rule 10's p-value: three decimals, or ``2.3e-08`` below 0.001."""
    return f"{p:.3f}" if p >= 0.001 else f"{p:.1e}"


def write_paired_store(root: Path) -> None:
    """Two runs replaying one request per item (8 items, 400 input tokens each): the first three
    items flip between the arms. The same store PF0's tests write."""
    from poisson_prove.episode import Episode
    from poisson_prove.store import EpisodeRecord, RunManifest, Store
    from poisson_prove.trace import Span, Trace

    store = Store(root)
    epoch, second = 1_790_000_000_000_000_000, 1_000_000_000
    for arm_index, arm in enumerate(("a", "b")):
        run_id = f"S1-{arm}"
        store.create_run(RunManifest(
            run_id=run_id, target_id="scorer@v1", t_unit="steps", run_salt="9f4a1c62d08e5b37",
            axis_types={"item": "categorical", "cut": "categorical"}, backend="local",
            environment={"python": "3.11.7", "platform": "test", "capture": {"content": True, "max_observation_bytes": "none"}},
        ))
        records = []
        for i in range(8):
            value = "0.05" if (arm == "b" and i < 3) else "0.95"
            start = epoch + i * 2 * second + arm_index * 60 * second
            span = Span(
                span_id="0000000000000001", parent_id=None, kind="http", name="scorer.request",
                start_ns=start, end_ns=start + 400_000_000,
                input=f'{{"model": "scorer-1.13.0", "state": "state of item {i}", "temperature": 0.30, "max_tokens": 64}}',
                output='{"answers": {"q1": {"score": 0.62}}}', tokens={"in": 400, "out": 12},
                attrs={"url.full": "https://api.example.test/v1/evaluate", "http.request.method": "POST"},
            )
            episode = Episode(
                outcome="acted" if value == "0.95" else "declined", t=1.0, horizon=10.0,
                meta={"trace": Trace(spans=(span,), source="record").to_dict(), "answers": {"q1": {"score": value}}},
            )
            records.append(EpisodeRecord.from_episode(
                episode, run_id=run_id, config={"item": f"c60-i{i:03d}", "cut": "c60"}, seed=1000 + i,
                replicate_index=0, wall_time=0.1,
            ))
        store.append(run_id, records)
        store.mark_complete(run_id)


# ---------- the world every test reads ----------


@dataclass(frozen=True)
class World:
    base: Path
    home: Path
    store: Path
    a: str
    b: str
    paired_store: Path
    folders: dict[str, Path]

    def fill(self, text: str) -> str:
        return text.format(A=self.a, B=self.b, S=self.store, PS=self.paired_store, **{k: str(v) for k, v in self.folders.items()})


@pytest.fixture(autouse=True)
def _no_store_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The pair (the mock agent, then the patched one paired with it), the paired-replay store,
    the specs, the targets and the folders the corpus names."""
    base = tmp_path_factory.mktemp("pf1")
    home = base / "home"
    home.mkdir()
    folders: dict[str, Path] = {"base": base}
    for name, text in (("spec", SPEC), ("low", LOW_SPEC), ("triple", TRIPLE_SPEC), ("bad_capture", BAD_CAPTURE_SPEC)):
        folders[name] = base / f"{name}.toml"
        folders[name].write_text(text, encoding="utf-8")
    for name, cap in (("decl", ""), ("decl_under", "token_cap = 1000000000\n"), ("decl_at", "token_cap = 1000\n"), ("decl_equal", "token_cap = 6400\n")):
        folders[name] = base / f"{name}.toml"
        folders[name].write_text(PAIRED_DECLARATION.format(cap=cap), encoding="utf-8")
    folders["targets"] = base / "targets"
    folders["targets"].mkdir()
    (folders["targets"] / "pf1_targets.py").write_text(TARGETS, encoding="utf-8")
    folders["no_modal"] = base / "no-modal"
    folders["no_modal"].mkdir()
    (folders["no_modal"] / "sitecustomize.py").write_text(NO_MODAL_SITECUSTOMIZE, encoding="utf-8")
    folders["fake_modal"] = base / "fake-modal"
    (folders["fake_modal"] / "modal").mkdir(parents=True)
    (folders["fake_modal"] / "modal" / "__init__.py").write_text(FAKE_MODAL, encoding="utf-8")
    folders["fake_burla"] = base / "fake-burla"
    (folders["fake_burla"] / "burla").mkdir(parents=True)
    (folders["fake_burla"] / "burla" / "__init__.py").write_text(FAKE_BURLA, encoding="utf-8")
    folders["a_file"] = base / "a-file.txt"
    folders["a_file"].write_text("not a folder\n", encoding="utf-8")
    folders["old_cwd"] = base / "old-cwd"
    shutil.copytree(OLD / "store" / OLD_RUNS["quickstart_before"], folders["old_cwd"] / "proofload-runs" / OLD_RUNS["quickstart_before"])
    folders["full"] = base / "full-folder"
    folders["full"].mkdir()
    (folders["full"] / "keep.txt").write_text("already here\n", encoding="utf-8")
    folders["nowhere"] = base / "no-store-here"
    folders["empty"] = base / "empty-store"
    folders["empty"].mkdir()

    store = base / "store"
    # PF4.30: both sweeps of the 120-replicate design accept MAX_MDE.
    # A fixed salt, so the pair's episodes are the same on every run of the suite (the second
    # sweep shares it through --pair-with).
    first = run_cli(["--store", str(store), "sweep", str(folders["spec"]), "--target", f"{MOCK}:rollout", "--yes", "--max-mde", MAX_MDE, "--salt", "a1b2c3d4e5f60718"])
    assert first.code == 0, first
    (a,) = run_ids(store)
    second = run_cli(["--store", str(store), "sweep", str(folders["spec"]), "--target", f"{MOCK}:rollout_patched", "--pair-with", a, "--yes", "--max-mde", MAX_MDE])
    assert second.code == 0, second
    (b,) = run_ids(store) - {a}
    paired_store = base / "paired-store"
    write_paired_store(paired_store)
    return World(base, home, store, a, b, paired_store, folders)


# ---------- the corpus ----------


@dataclass(frozen=True)
class Call:
    name: str
    argv: str
    code: int
    #: result, json, help, version, stopped, refusal, plan (a refusal that keeps the plan), usage
    kind: str
    #: what the refusal's or the usage error's stderr must carry: values from the invocation
    facts: tuple[str, ...] = ()
    #: a folder of the world to run in, else its base
    cwd: str = ""
    #: folders of the world put on the path after ``src``
    paths: tuple[str, ...] = ()


S, PS = "--store {S}", "--store {PS}"
PAIR_X = "--x task_id --y tool_fail_rate"

CORPUS: tuple[Call, ...] = (
    # the result of every verb
    # PF4.30: every sweep of the 120-replicate design below accepts
    # MAX_MDE, so each refusal and each sweep that stops short is the one it names, not the gate's.
    Call("sweep-dry-run", "--store {base}/dry-store sweep {spec} --target " + MOCK + ":rollout --dry-run --max-mde " + MAX_MDE, 0, "result"),
    Call("sweep-yes", "--store {base}/sweep-store sweep {spec} --target " + MOCK + ":rollout --yes --max-mde " + MAX_MDE, 0, "result"),
    Call("diff", f"{S} diff {{A}} {{B}}", 0, "result"),
    Call("diff-fisher-named", f"{S} diff {{A}} {{B}} --method fisher_bh", 0, "result"),
    Call("diff-mcnemar-named", f"{S} diff {{A}} {{B}} --method mcnemar_bh", 0, "result"),
    # PF4 (PF4.20): neither event has a kind in these runs, so check's default --fail-on worse is
    # refused; --fail-on higher is the same gate on a failure event (fail when the rate rose).
    Call("check-passed", f"{S} check {{A}} {{B}} --event violated --fail-on higher", 0, "result"),
    Call("check-failed", f"{S} check {{A}} {{B}} --event timeout --fail-on higher", 4, "result"),
    Call("report-pair", f"{S} report {{A}} {{B}} {PAIR_X} --method fisher_bh --out {{base}}/out-report-pair", 0, "result"),
    Call("report-run", f"{S} report {{A}} {PAIR_X} --event violated --out {{base}}/out-report-run", 0, "result"),
    Call("inspect", f"{S} inspect {{A}} --event timeout --limit 2", 0, "result"),
    Call("runs", f"{S} runs", 0, "result"),
    Call("runs-empty-store", "--store {empty} runs", 0, "result"),
    Call("paired", f"{PS} paired --declaration {{decl}} --out {{base}}/out-paired", 0, "result"),
    Call("paired-under-cap", f"{PS} paired --declaration {{decl_under}} --cap-check", 0, "result"),
    Call("paired-at-cap", f"{PS} paired --declaration {{decl_at}} --cap-check", 4, "result"),
    #: 8 items x 400 input tokens x 2 arms = 6,400, exactly the declared cap: "at or above" (PF1.14).
    Call("paired-equal-cap", f"{PS} paired --declaration {{decl_equal}} --cap-check", 4, "result"),
    # the two ways a sweep stops short after work started
    # PF4.49: the 3-replicate design's limit is over 0.99 (no lone condition of it can be
    # flagged), so its sweep passes --max-mde 1.
    Call("sweep-max-rollouts", "--store {base}/capped-store sweep {spec} --target " + MOCK + ":rollout --yes --max-rollouts 100 --max-mde " + MAX_MDE, 3, "stopped"),
    Call("sweep-all-errored", "--store {base}/errored-store sweep {triple} --target pf1_targets:mostly_value_error --yes --max-mde 1", 3, "stopped", paths=("targets",)),
    # --json on every verb
    Call("json-sweep", "--store {base}/json-sweep-store sweep {spec} --target " + MOCK + ":rollout --yes --json --max-mde " + MAX_MDE, 0, "json"),
    Call("json-diff", f"{S} diff {{A}} {{B}} --method fisher_bh --json", 0, "json"),
    # PF4 (PF4.20): as check-passed and check-failed, the same gate named for an unknown kind.
    Call("json-check", f"{S} check {{A}} {{B}} --event violated --fail-on higher --json", 0, "json"),
    Call("json-check-failed", f"{S} check {{A}} {{B}} --event timeout --fail-on higher --json", 4, "json"),
    Call("json-report", f"{S} report {{A}} {{B}} {PAIR_X} --method fisher_bh --json --out {{base}}/out-report-json", 0, "json"),
    Call("json-paired", f"{PS} paired --declaration {{decl}} --json", 0, "json"),
    Call("json-serve", f"{S} serve {{A}} {{B}} {PAIR_X} --event violated --json", 0, "json"),
    Call("json-inspect", f"{S} inspect {{A}} --event timeout --limit 2 --json", 0, "json"),
    Call("json-runs", f"{S} runs --json", 0, "json"),
    # help and the version
    Call("version", "--version", 0, "version"),
    Call("help", "--help", 0, "help"),
    *(Call(f"help-{verb}", f"{verb} --help", 0, "help") for verb in ("sweep", "diff", "check", "report", "paired", "serve", "inspect", "runs")),
    # every refusal PF1.2 reads: exit 1
    Call("refuse-missing-store", "--store {nowhere} runs", 1, "refusal", ("{nowhere}",)),
    Call("refuse-old-store-only", "runs", 1, "refusal", ("proofload-runs",), cwd="old_cwd"),
    Call("refuse-unknown-run", f"{S} diff {{A}} 20991231T000000Z-dead", 1, "refusal", ("20991231T000000Z-dead",)),
    Call("refuse-check-without-event", f"{S} check {{A}} {{B}}", 1, "refusal", ("violated", "timeout")),
    Call("refuse-serve-without-event", f"{S} serve {{A}} {{B}} {PAIR_X}", 1, "refusal", ("violated", "timeout")),
    Call("refuse-inspect-without-event", f"{S} inspect {{A}}", 1, "refusal", ("violated", "timeout")),
    Call("refuse-report-without-x", f"{S} report {{A}} {{B}}", 1, "refusal", ("task_id", "tool_fail_rate")),
    Call("refuse-serve-without-x", f"{S} serve {{A}} {{B}} --event violated", 1, "refusal", ("task_id", "tool_fail_rate")),
    Call("refuse-report-free-axis", f"{S} report {{A}} --x task_id --event violated", 1, "refusal", ("tool_fail_rate",)),
    # PF4.30: the refusal states the design's exact limit, recomputed.
    Call("refuse-underpowered", "--store {base}/low-store sweep {low} --target " + MOCK + ":rollout --yes", 1, "plan", (f"{LOW_LIMIT:.3f}", "0.200")),
    Call("refuse-stdin-not-a-terminal", "--store {base}/tty-store sweep {spec} --target " + MOCK + ":rollout --max-mde " + MAX_MDE, 1, "plan", ("--yes",)),
    Call("refuse-over-max-cost", "--store {base}/cost-store sweep {spec} --target " + MOCK + ":rollout --backend modal --max-cost 0.5 --est-seconds 36000 --yes --max-mde " + MAX_MDE, 1, "plan", ("$0.50",), paths=("fake_modal",)),
    Call("refuse-existing-folder", f"{S} report {{A}} {{B}} {PAIR_X} --out {{full}}", 1, "refusal", ("{full}",)),
    Call("refuse-unknown-spec-key", "--store {base}/bad-store sweep {bad_capture} --target " + MOCK + ":rollout --yes --max-mde " + MAX_MDE, 1, "refusal", ("not_a_field",)),
    Call("refuse-missing-burla-table", "--store {base}/burla-store sweep {spec} --target " + MOCK + ":rollout --backend burla --yes --max-mde " + MAX_MDE, 1, "refusal", ("[burla]", "{spec}"), paths=("fake_burla",)),
    Call("refuse-empty-store", "--store {empty} diff {A} {B}", 1, "refusal", ("{empty}",)),
    Call("refuse-unresolvable-target", "--store {base}/target-store sweep {spec} --target poisson_prove.examples.no_such_module_xyz:rollout --yes --max-mde " + MAX_MDE, 1, "refusal", ("no_such_module_xyz",)),
    Call("refuse-unknown-event", f"{S} diff {{A}} {{B}} --event nope", 1, "refusal", ("violated", "timeout")),
    Call("refuse-resume-a-complete-run", f"{S} sweep {{spec}} --target " + MOCK + ":rollout --resume {A} --yes --max-mde " + MAX_MDE, 1, "refusal", ("{A}",)),
    Call("refuse-unknown-grouping", f"{S} diff {{A}} {{B}} --method mcnemar_bh --by nonsense", 1, "refusal", ("tool_fail_rate",)),
    Call("refuse-group-mde-out-of-range", f"{S} diff {{A}} {{B}} --method mcnemar_bh --max-group-mde 2", 1, "refusal", ("--max-group-mde",)),
    Call("refuse-no-permutations", f"{S} diff {{A}} {{B}} --method mcnemar_bh --permutations 0", 1, "refusal", ("--permutations",)),
    Call("refuse-out-is-a-file", f"{S} report {{A}} {{B}} {PAIR_X} --out {{a_file}}", 1, "refusal", ("{a_file}",)),
    Call("refuse-missing-extra", "--store {base}/modal-store sweep {spec} --target " + MOCK + ":rollout --backend modal --yes --max-mde " + MAX_MDE, 1, "refusal", ('pip install "poisson-prove[modal]"',), paths=("no_modal",)),
    # every kind of wrong command line: exit 2
    Call("usage-no-arguments", "", 2, "usage"),
    Call("usage-unknown-verb", "frobnicate", 2, "usage", ("frobnicate",)),
    Call("usage-unknown-option", f"{S} runs --frobnicate", 2, "usage", ("--frobnicate",)),
    Call("usage-abbreviated-option", f"{S} diff {{A}} {{B}} --even violated", 2, "usage", ("--even",)),
    Call("usage-abbreviated-global-option", "--sto {S} runs", 2, "usage", ("--sto",)),
    Call("usage-value-outside-choices", f"{S} diff {{A}} {{B}} --method nope", 2, "usage", ("nope",)),
    Call("usage-not-a-number", f"{S} diff {{A}} {{B}} --q abc", 2, "usage", ("abc",)),
    Call("usage-word-too-many", f"{S} runs extra", 2, "usage", ("extra",)),
    Call("usage-diff-one-run", f"{S} diff {{A}}", 2, "usage"),
    Call("usage-check-one-run", f"{S} check {{A}} --event violated", 2, "usage"),
    Call("usage-serve-one-run", f"{S} serve {{A}} {PAIR_X} --event violated", 2, "usage"),
    Call("usage-sweep-no-target", "--store {base}/no-target-store sweep {spec} --yes --max-mde " + MAX_MDE, 2, "usage", ("--target",)),
)
CALLS = {call.name: call for call in CORPUS}
assert len(CALLS) == len(CORPUS), "corpus names are unique"


def names(*kinds: str) -> list[str]:
    return [call.name for call in CORPUS if call.kind in kinds]


@dataclass(frozen=True)
class Ran:
    call: Call
    argv: list[str]
    code: int
    out: str
    err: str


@pytest.fixture(scope="module")
def corpus(world: World) -> dict[str, Ran]:
    def one(call: Call) -> Ran:
        argv = [world.fill(word) for word in call.argv.split()]
        cwd = world.folders[call.cwd] if call.cwd else world.base
        r = prove(argv, home=world.home, cwd=cwd, paths=tuple(world.folders[p] for p in call.paths))
        return Ran(call, argv, r.code, r.out, r.err)

    with ThreadPoolExecutor(max_workers=8) as pool:
        return {ran.call.name: ran for ran in pool.map(one, CORPUS)}


# ---------- PF1.1 exit codes ----------


def test_pf1_1_every_invocation_exits_with_its_own_code(corpus: dict[str, Ran]) -> None:
    wrong = {name: (r.code, r.call.code, r.err[-400:]) for name, r in corpus.items() if r.code != r.call.code}
    assert not wrong, wrong


# ---------- PF1.2 refusals ----------


@pytest.mark.parametrize("name", names("refusal", "plan"))
def test_pf1_2_a_refusal_exits_1_with_one_error_line_then_only_next_lines_and_says_what_it_refused(name: str, corpus: dict[str, Ran], world: World) -> None:
    r = corpus[name]
    assert r.code == 1, (r.out, r.err)
    # A note about a warning raised before the refusal is not part of it (PF1.5, PF1.15).
    lines = [line for line in r.err.splitlines() if not line.startswith("note: ")]
    assert lines and lines[0].startswith("error: "), r.err
    assert all(line.startswith("  next: ") for line in lines[1:]), r.err
    for fact in r.call.facts:
        # A plan refusal may state its numbers in the plan it keeps on stdout (rule 7).
        assert world.fill(fact) in (r.out + r.err if r.call.kind == "plan" else r.err), (fact, r.err)
    if name == "refuse-missing-burla-table":
        assert "pip install" not in r.err, "the table's refusal, not the missing extra's"
    if r.call.kind == "plan":
        # The plan, and nothing else: its verdict line, then its detail as lines indented two
        # spaces or as a block after one blank line (rule 3), and no error among them.
        out = r.out.splitlines()
        assert out and out[0].startswith("plan  "), r.out
        assert out[1:2] == [""] or all(line == "" or line.startswith("  ") for line in out[1:]), r.out
        assert not any(line.startswith("error:") for line in out), r.out
    else:
        assert r.out == "", r.out


# ---------- PF1.3 wrong command lines ----------


@pytest.mark.parametrize("name", names("usage"))
def test_pf1_3_a_wrong_command_line_exits_2_with_one_error_line_and_nothing_on_stdout(name: str, corpus: dict[str, Ran], world: World) -> None:
    r = corpus[name]
    assert r.code == 2, (r.out, r.err)
    assert r.out == "", r.out
    lines = r.err.splitlines()
    assert lines and lines[0].startswith("error: "), r.err
    assert all(line.startswith("  next: ") for line in lines[1:]), r.err
    for fact in r.call.facts:
        assert world.fill(fact) in r.err, (fact, r.err)


def test_pf1_3_no_arguments_says_no_verb_was_given_and_points_to_help(corpus: dict[str, Ran]) -> None:
    lines = corpus["usage-no-arguments"].err.splitlines()
    assert len(lines) == 2 and lines[0].startswith("error: "), lines
    assert lines[1] == "  next: poisson-prove --help", lines


# ---------- PF1.4 an unexpected failure ----------


#: One invocation per verb that succeeds on the world, run with ``Store``'s constructor made to
#: raise: the failure no verb expects. Each runs in a process of its own, so the log's place is
#: read from that process's ``HOME`` however the code looks it up.
VERB_CALLS = {
    # PF4.30: the sweep succeeds on the world only with MAX_MDE.
    "sweep": "--store {base}/failure-store sweep {spec} --target " + MOCK + ":rollout --yes --max-mde " + MAX_MDE,
    "diff": f"{S} diff {{A}} {{B}}",
    "check": f"{S} check {{A}} {{B}} --event violated",
    "report": f"{S} report {{A}} {{B}} {PAIR_X} --out {{base}}/failure-report",
    "paired": f"{PS} paired --declaration {{decl}} --out {{base}}/failure-paired",
    "serve": f"{S} serve {{A}} {{B}} {PAIR_X} --event violated --json",
    "inspect": f"{S} inspect {{A}} --event timeout",
    "runs": f"{S} runs",
}
MARK = "a failure no verb expects, 7f3a"
RAISE_IN_STORE = f"""\
import poisson_prove.store as _store


def _boom(self, *args, **kwargs):
    raise RuntimeError({MARK!r})


_store.Store.__init__ = _boom
"""
#: The failure arrives after the sweep has started: the second batch of rows cannot be stored.
RAISE_MID_SWEEP = f"""\
import poisson_prove.store as _store

_real_append = _store.Store.append
_calls = [0]


def _append(self, *args, **kwargs):
    _calls[0] += 1
    if _calls[0] == 2:
        raise RuntimeError({MARK!r})
    return _real_append(self, *args, **kwargs)


_store.Store.append = _append
"""


def errors_log(home: Path) -> Path:
    return home / ".cache" / "poisson-prove" / "errors.log"


@pytest.mark.parametrize("verb", list(VERB_CALLS))
def test_pf1_4_an_unexpected_failure_exits_3_naming_the_log_and_appends_the_command_and_traceback(verb: str, world: World, tmp_path: Path) -> None:
    home = tmp_path / "home"
    log = errors_log(home)
    log.parent.mkdir(parents=True)
    log.write_text("an earlier entry\n", encoding="utf-8")
    argv = [world.fill(word) for word in VERB_CALLS[verb].split()]
    r = prove_with(RAISE_IN_STORE, argv, home=home, cwd=tmp_path)
    assert r.code == 3, r
    lines = r.err.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: "), r.err
    assert ERRORS_LOG in lines[0] or str(log) in lines[0], lines[0]
    assert "RuntimeError" in lines[0], lines[0]
    assert MARK not in r.err and TRACEBACK not in r.err, r.err
    text = log.read_text(encoding="utf-8")
    assert text.startswith("an earlier entry\n"), text[:200]
    assert " ".join(argv) in text, text
    assert TRACEBACK in text and MARK in text, text
    again = prove_with(RAISE_IN_STORE, argv, home=home, cwd=tmp_path)
    assert again.code == 3
    later = log.read_text(encoding="utf-8")
    # One entry per failure, counted by its last line: from Python 3.13 a traceback also prints
    # the raising line of a ``-c`` script, which holds the marker too.
    assert later.startswith(text) and later.count(f"RuntimeError: {MARK}") == 2, later


def test_pf1_4_a_failure_after_the_sweep_started_still_names_only_the_log(world: World, tmp_path: Path) -> None:
    home = tmp_path / "home"
    # PF4.30: the 120-replicate design accepts MAX_MDE.
    argv = ["--store", str(tmp_path / "store"), "sweep", str(world.folders["spec"]), "--target", f"{MOCK}:rollout", "--yes", "--batch-size", "64",
            "--max-mde", MAX_MDE]
    r = prove_with(RAISE_MID_SWEEP, argv, home=home, cwd=tmp_path)
    assert r.code == 3, r
    errors = [line for line in r.err.splitlines() if not PROGRESS.match(line)]
    assert len(errors) == 1 and errors[0].startswith("error: "), r.err
    assert ERRORS_LOG in errors[0] or str(errors_log(home)) in errors[0], errors[0]
    assert MARK not in r.err and TRACEBACK not in r.err, r.err
    assert MARK in errors_log(home).read_text(encoding="utf-8")


@pytest.mark.parametrize("where", ["before", "after"])
def test_pf1_4_debug_before_or_after_the_verb_also_prints_the_traceback(where: str, world: World, tmp_path: Path) -> None:
    home = tmp_path / "home"
    argv = [world.fill(word) for word in VERB_CALLS["diff"].split()]
    argv = ["--debug", *argv] if where == "before" else [*argv, "--debug"]
    r = prove_with(RAISE_IN_STORE, argv, home=home, cwd=tmp_path)
    assert r.code == 3, r
    assert TRACEBACK in r.err and MARK in r.err, r.err
    assert errors_log(home).is_file()


# ---------- PF1.5 what never reaches stderr ----------


#: A traceback, a site-packages path, a source line, and the Python reprs a user should never
#: read: a quoted value (``'name'``), a list or dict printed as itself, an object or a path object.
RAW = (
    re.compile(re.escape(TRACEBACK)),
    re.compile(r"site-packages"),
    re.compile(r'File "[^"]*", line \d+'),
    re.compile(r"\.py:\d+"),
    re.compile(r"(?<![A-Za-z0-9])'[^'\s][^']*'(?![A-Za-z0-9])"),
    re.compile(r"\[\s*'|\{\s*'"),
    re.compile(r"<[\w.]+ object at 0x[0-9a-f]+>"),
    re.compile(r"\b(?:Posix|Windows)?Path\("),
)


def stderr_allowed(line: str) -> bool:
    """PF1.15's rule for one stderr line. The question has no newline of its own, so whatever
    follows it on the same line must itself be an allowed line."""
    if "[y/N]" in line:
        rest = line.split("[y/N]", 1)[1].strip()
        return rest == "" or stderr_allowed(rest)
    return line.startswith(("error: ", "note: ", "  ")) or bool(PROGRESS.match(line))


def assert_clean_stderr(err: str | bytes) -> None:
    """PF1.5 and PF1.15 for a run outside the corpus (never one with ``--debug``)."""
    text = err.decode("utf-8", "replace") if isinstance(err, bytes) else err
    assert not [p.pattern for p in RAW if p.search(text)], text
    assert all(stderr_allowed(line) for line in text.splitlines()), text


def test_pf1_5_no_traceback_repr_path_or_source_line_reaches_stderr_over_the_corpus(corpus: dict[str, Ran]) -> None:
    found = {name: [p.pattern for p in RAW if p.search(r.err)] for name, r in corpus.items()}
    found = {name: (patterns, corpus[name].err[-600:]) for name, patterns in found.items() if patterns}
    assert not found, found


def test_pf1_5_a_warning_prove_raises_reaches_the_user_as_one_note_line(corpus: dict[str, Ran]) -> None:
    """An unpaired method named on runs paired at sweep time raises Prove's own warning (section
    4.4): the user reads it as one ``note:`` line and nothing else on stderr."""
    r = corpus["diff-fisher-named"]
    assert r.code == 0, r.err
    lines = r.err.splitlines()
    assert len(lines) == 1 and lines[0].startswith("note: "), r.err


# ---------- PF1.6 Ctrl-C ----------


def test_pf1_6_ctrl_c_in_a_sweep_exits_130_keeps_what_was_stored_and_names_the_resume(world: World, tmp_path: Path) -> None:
    store = tmp_path / "store"
    # PF4.30: the 120-replicate design accepts MAX_MDE.
    r = prove(
        ["--store", str(store), "sweep", str(world.folders["spec"]), "--target", "pf1_targets:interrupted", "--yes", "--batch-size", "64",
         "--max-mde", MAX_MDE],
        home=world.home, cwd=tmp_path, paths=(world.folders["targets"],),
    )
    assert r.code == 130, (r.out, r.err)
    (run_id,) = run_ids(store)
    assert manifest(store, run_id)["status"] == "partial"
    from poisson_prove.store import Store

    kept = Store(store).count(run_id)
    assert 0 < kept < 1080
    stopped = [line for line in r.out.splitlines() if line.startswith("stopped  ")]
    assert len(stopped) == 1 and f"{kept:,}" in stopped[0], r.out
    # The next line resumes the sweep as it was typed, as a sweep stopped short does: this one
    # typed a spec path and --target, so the line carries the spec before --resume and that target.
    spec, target = str(world.folders["spec"]), "pf1_targets:interrupted"
    nexts = [line for line in r.out.splitlines() + r.err.splitlines() if line.startswith("  next: poisson-prove sweep ")]
    assert len(nexts) == 1, (r.out, r.err)
    words = shlex.split(nexts[0])[1:]
    assert words[:2] == ["poisson-prove", "sweep"] and spec in words and "--resume" in words, nexts
    assert words.index(spec) < words.index("--resume"), nexts
    assert "--target" in words and words[words.index("--target") + 1] == target, nexts
    assert_clean_stderr(r.err)


#: Ctrl-C arrives while a read verb reads its first manifest.
INTERRUPT_ON_READ = """\
import poisson_prove.store as _store


def _interrupted(self, *args, **kwargs):
    raise KeyboardInterrupt


_store.Store.manifest = _interrupted
"""


#: The read verbs, each writing (where it writes) into its default folder in the working folder.
READ_CALLS = {
    "diff": f"{S} diff {{A}} {{B}}",
    "check": f"{S} check {{A}} {{B}} --event violated",
    "report": f"{S} report {{A}} {{B}} {PAIR_X}",
    "serve": f"{S} serve {{A}} {{B}} {PAIR_X} --event violated",
    "inspect": f"{S} inspect {{A}} --event timeout",
    "runs": f"{S} runs",
    "paired": f"{PS} paired --declaration {{decl}}",
}


@pytest.mark.parametrize("verb", list(READ_CALLS))
def test_pf1_6_ctrl_c_in_a_read_verb_exits_130_and_says_it_stopped_with_nothing_written(verb: str, world: World, tmp_path: Path) -> None:
    store = world.paired_store if verb == "paired" else world.store
    before = listing(store)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    argv = [world.fill(word) for word in READ_CALLS[verb].split()]
    r = prove_with(INTERRUPT_ON_READ, argv, home=world.home, cwd=cwd)
    assert r.code == 130, (r.out, r.err)
    assert r.out.splitlines()[:1] and r.out.splitlines()[0].startswith("stopped  "), r.out
    assert_clean_stderr(r.err)
    assert list(cwd.iterdir()) == []
    assert listing(store) == before


#: Ctrl-C arrives as the second output file is opened for writing; the store is never counted.
INTERRUPT_ON_SECOND_WRITE = """\
import builtins as _builtins
import io as _io
import os as _os

_real_open = _io.open
_skip = _os.path.realpath(_os.environ["PF1_STORE"])
_writes = [0]


def _open(file, mode="r", *args, **kwargs):
    if any(flag in mode for flag in "wax"):
        counted = isinstance(file, int)
        if isinstance(file, (str, bytes, _os.PathLike)):
            counted = not _os.path.realpath(_os.fsdecode(file)).startswith(_skip)
        if counted:
            _writes[0] += 1
            if _writes[0] == 2:
                raise KeyboardInterrupt
    return _real_open(file, mode, *args, **kwargs)


_io.open = _builtins.open = _open
"""


@pytest.mark.parametrize("verb", ["report", "paired"])
def test_pf1_6_ctrl_c_while_report_or_paired_writes_leaves_no_output_folder_behind(verb: str, world: World, tmp_path: Path) -> None:
    store = world.paired_store if verb == "paired" else world.store
    cwd, scratch = tmp_path / "cwd", tmp_path / "tmp"
    cwd.mkdir()
    scratch.mkdir()
    argv = {
        "report": ["--store", str(store), "report", world.a, world.b, "--x", "task_id", "--y", "tool_fail_rate"],
        "paired": ["--store", str(store), "paired", "--declaration", str(world.folders["decl"])],
    }[verb]
    r = prove_with(INTERRUPT_ON_SECOND_WRITE, argv, home=world.home, cwd=cwd, PF1_STORE=str(store), TMPDIR=str(scratch))
    assert r.code == 130, (r.out, r.err)
    assert any(line.startswith("stopped  ") for line in r.out.splitlines()), r.out
    assert_clean_stderr(r.err)
    assert list(cwd.iterdir()) == [], listing(cwd)
    assert list(scratch.iterdir()) == [], listing(scratch)


def read_until(proc: subprocess.Popen[bytes], pattern: re.Pattern[str], deadline: float) -> list[str]:
    """Lines of the child's stdout up to the first that matches, within the deadline."""
    assert proc.stdout is not None
    lines: list[str] = []
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    while time.monotonic() < deadline:
        if not selector.select(timeout=max(0.0, deadline - time.monotonic())):
            break
        line = proc.stdout.readline().decode("utf-8", "replace")
        if not line:
            break
        lines.append(line)
        if pattern.search(line):
            return lines
    raise AssertionError(f"no line matching {pattern.pattern} on stdout: {lines}")


def test_pf1_6_ctrl_c_on_serve_exits_130_and_says_it_stopped(world: World, tmp_path: Path) -> None:
    argv = ["--store", str(world.store), "serve", world.a, world.b, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated"]
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", *argv], cwd=tmp_path, env=child_env(world.home),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=default_sigint,
    )
    try:
        seen = read_until(proc, re.compile(r"http://127\.0\.0\.1:\d+/"), time.monotonic() + 120)
        proc.send_signal(signal.SIGINT)
        rest, err = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    out = "".join(seen) + rest.decode("utf-8", "replace")
    assert proc.returncode == 130, (out, err)
    assert any(line.startswith("stopped  ") for line in out.splitlines()), out
    assert_clean_stderr(err)


# ---------- PF1.7 help ----------


#: Every help, in one process where modal, opentelemetry and burla cannot be imported and no
#: socket can connect, bind or look a name up.
HELP_PROBE = """\
import json
import socket
import sys
from io import StringIO

for name in ("modal", "opentelemetry", "burla"):
    sys.modules[name] = None


def _blocked(*args, **kwargs):
    raise OSError("sockets are blocked here")


for name in ("connect", "connect_ex", "bind", "sendto"):
    setattr(socket.socket, name, _blocked)
socket.getaddrinfo = socket.create_connection = _blocked

from poisson_prove.cli import main

results = {}
for words in json.loads(sys.argv[1]):
    out, err = StringIO(), StringIO()
    code = main([*words, "--help"], stdout=out, stderr=err, stdin=StringIO())
    results[" ".join(words)] = [code, out.getvalue(), err.getvalue()]
print(json.dumps(results))
"""
HELP_VERBS = ("", "sweep", "diff", "check", "report", "paired", "serve", "inspect", "runs")
#: The options each verb's usage line must show outside brackets.
REQUIRED_SHOWN = {"check": ("--event",), "report": ("--x",), "serve": ("--x", "--event"), "inspect": ("--event",), "paired": ("--declaration",)}


@pytest.fixture(scope="module")
def helps(world: World) -> dict[str, tuple[int, str, str]]:
    words = [[verb] if verb else [] for verb in HELP_VERBS]
    done = subprocess.run(
        [sys.executable, "-c", HELP_PROBE, json.dumps(words)], cwd=world.base, env=child_env(world.home),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300,
    )
    assert done.returncode == 0, done.stderr
    return {key: tuple(value) for key, value in json.loads(done.stdout.splitlines()[-1]).items()}  # type: ignore[misc]


def usage_of(text: str) -> str:
    return text.split("\n\n")[0]


def bracket_depth(text: str, at: int) -> int:
    return text[:at].count("[") - text[:at].count("]")


def help_entries(text: str) -> list[tuple[str, str]]:
    """``(invocation, help text)`` for every argument listed: an option, or a positional whose
    invocation is one word. Example command lines are not entries."""
    entries: list[list[str]] = []
    for line in text.split("\n\n", 1)[1].splitlines() if "\n\n" in text else []:
        if re.match(r"^\S", line):
            continue
        head = re.match(r"^  (\S(?:\S| (?! ))*)(?:\s{2,}(\S.*))?$", line)
        if head and not line.startswith("   "):
            invocation = head.group(1)
            if invocation.startswith("-") or " " not in invocation:
                entries.append([invocation, head.group(2) or ""])
            continue
        if line.startswith("   ") and entries:
            entries[-1][1] = (entries[-1][1] + " " + line.strip()).strip()
    return [(i, h) for i, h in entries]


@pytest.mark.parametrize("verb", HELP_VERBS, ids=[v or "poisson-prove" for v in HELP_VERBS])
def test_pf1_7_help_exits_0_with_a_description_every_option_with_its_default_and_an_example(verb: str, helps: dict[str, tuple[int, str, str]]) -> None:
    code, text, err = helps[verb]
    assert code == 0 and err == "", (code, err)
    blocks = text.split("\n\n")
    assert blocks[0].startswith("usage:"), text
    description = blocks[1] if len(blocks) > 1 else ""
    assert not re.match(r"^\S[^\n]*:\n", description + "\n"), "the block after usage is a description, not a list"
    assert len(description.split()) >= 8 and "." in description, description
    entries = help_entries(text)
    assert entries, text
    for invocation, words in entries:
        if invocation.startswith("-h"):
            continue
        assert words, f"{invocation} has no help text"
        takes_value = invocation.startswith("-") and " " in invocation.split(",")[-1].strip()
        if takes_value:
            assert "default" in words, f"{invocation}: {words}"
    assert not re.search(r"\b(?:None|True|False)\b|\[\]", text), "a Python value shown as a default"
    command = f"poisson-prove {verb}".strip()
    examples = [
        line.strip().removeprefix("$ ")
        for line in text.split("\n\n", 1)[1].splitlines()
        if line.strip().removeprefix("$ ") == command or line.strip().removeprefix("$ ").startswith(command + " ")
    ]
    assert examples, f"no example beginning {command!r}: {text}"
    assert not any(RUN_ID.search(example) for example in examples), examples


@pytest.mark.parametrize("verb", list(REQUIRED_SHOWN))
def test_pf1_7_required_options_are_shown_required_in_the_usage_line(verb: str, helps: dict[str, tuple[int, str, str]]) -> None:
    usage = usage_of(helps[verb][1])
    for flag in REQUIRED_SHOWN[verb]:
        at = [m.start() for m in re.finditer(re.escape(flag) + r" [A-Z]", usage)]
        assert at and all(bracket_depth(usage, i) == 0 for i in at), (flag, usage)


# ---------- PF1.8 --version ----------


def test_pf1_8_version_is_one_line_naming_the_command_its_version_and_python(corpus: dict[str, Ran]) -> None:
    import poisson_prove

    r = corpus["version"]
    assert r.code == 0 and r.err == "", r
    assert r.out == f"poisson-prove {poisson_prove.__version__} (Python {platform.python_version()})\n", r.out


# ---------- PF1.9 the tool's own options, and abbreviations ----------


def test_pf1_9_store_plain_and_debug_are_read_after_the_verb_as_before_it(world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # no default store here: only --store can name one
    before = run_cli(["--store", str(world.store), "runs"])
    assert before.code == 0 and world.a in before.out, before
    for argv in (
        ["runs", "--store", str(world.store)],
        ["--plain", "runs", "--store", str(world.store)],
        ["runs", "--store", str(world.store), "--plain"],
        ["--debug", "--store", str(world.store), "runs"],
        ["runs", "--debug", "--store", str(world.store)],
    ):
        r = run_cli(argv)
        assert (r.code, r.out) == (before.code, before.out), (argv, r)
    diff_before = run_cli(["--store", str(world.store), "diff", world.a, world.b, "--method", "mcnemar_bh"])
    diff_after = run_cli(["diff", world.a, world.b, "--method", "mcnemar_bh", "--store", str(world.store), "--plain", "--debug"])
    assert diff_before.code == diff_after.code == 0, (diff_before.err, diff_after.err)
    assert diff_after.out == diff_before.out


@pytest.mark.parametrize("argv", [
    ["--deb", "--store", "{S}", "runs"],
    ["--pla", "--store", "{S}", "runs"],
    ["--vers"],
    ["--store", "{S}", "runs", "--sto", "{S}"],
    ["--store", "{S}", "diff", "{A}", "{B}", "--meth", "fisher_bh"],
    ["--store", "{S}", "check", "{A}", "{B}", "--event", "violated", "--fail", "any"],
    # PF4.30: the 120-replicate design accepts MAX_MDE.
    ["--store", "{S}", "sweep", "{spec}", "--tar", MOCK + ":rollout", "--yes", "--max-mde", MAX_MDE],
], ids=lambda argv: " ".join(argv))
def test_pf1_9_an_abbreviated_option_exits_2(argv: list[str], world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = run_cli([world.fill(word) for word in argv])
    assert r.code == 2, r
    assert r.out == "" and r.err.startswith("error: "), r


# ---------- PF1.10 numbers ----------


def visible_text(markup: str) -> str:
    """The text a reader sees in an HTML or SVG file: no style, no script, no tags."""
    markup = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    return " ".join(re.findall(r">([^<]+)<", markup))


#: A hex id of the length Prove stores (config hashes, digests, comparison ids); text shows its
#: first twelve characters.
HEX_ID = re.compile(r"[0-9a-f]{16,}")


def ids_given(corpus: dict[str, Ran], world: World) -> frozenset[str]:
    """Every hex id in the corpus's JSON output and in the world's JSON files, whole and as the
    twelve characters text prints. An id that comes out all digits is still an id, not a count."""
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, str) and HEX_ID.fullmatch(value):
            found.update((value, value[:12]))
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(key)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for r in corpus.values():
        if r.call.kind == "json" and r.out.strip():
            walk(json.loads(r.out))
    for path in world.base.rglob("*.json"):
        walk(json.loads(path.read_text(encoding="utf-8")))
    return frozenset(found)


def number_problems(text: str, ids: frozenset[str] = frozenset()) -> list[str]:
    """Every number in ``text`` that rule 10 (as amended) does not allow.

    Not numbers in this sense: run ids, the hex ids in ``ids``, anything with a slash (paths, URLs,
    ``n_a/n_b``), dates, versions, a year cited in parentheses, a seed or a salt (no separators on
    seeds, as in Trace), and a UTC time with ``Z``."""
    problems: list[str] = []
    t = RUN_ID.sub(" ", text)
    if ids:
        t = re.sub(r"\b(?:" + "|".join(sorted(ids, key=len, reverse=True)) + r")\b", " ", t)
    t = re.sub(r"\S*/\S*", " ", t)
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z", " ", t)
    problems += [f"time not in UTC with Z: {m}" for m in re.findall(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}\S*", t)]
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", t)
    t = re.sub(r"\b\d+\.\d+\.\d+\b", " ", t)
    t = re.sub(r"\(\d{4}\)", " ", t)
    t = re.sub(r"(?:seed|salt)[s\"':= ]*[0-9a-f]+\b", " ", t, flags=re.I)
    problems += [f"hash longer than 12 hex: {m}" for m in re.findall(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{13,}\b", t)]
    t = re.sub(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{5,}\b", " ", t)
    for m in re.findall(r"\d(?:\.\d+)?[eE][+-]?\d+", t):
        if not re.fullmatch(r"\d\.\de-\d{2,3}", m):
            problems.append(f"scientific form other than 2.3e-08: {m}")
    t = re.sub(r"\d(?:\.\d+)?[eE][+-]?\d+", " ", t)
    problems += [f"more than three decimals: {m}" for m in re.findall(r"\d\.\d{4,}", t)]
    for m in re.findall(r"\$\d[\d,]*(?:\.\d+)?", t):
        if not re.fullmatch(r"\$0|\$\d{1,3}(?:,\d{3})*\.\d{2}|\$0\.0*[1-9]\d", m):
            problems.append(f"dollars: {m}")
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?) s\b", t):
        if float(m.group(1)) >= 60:
            problems.append(f"a duration of a minute or more in seconds: {m.group(0)}")
    problems += [f"count without separators: {m}" for m in re.findall(r"(?<![\d.,])\d{4,}(?![\d.,])", t)]
    problems += [f"a rate in points, not a fraction: {m}" for m in re.findall(r"\d(?:\.\d+)?\s?(?:pp|pts|points)\b|\(pp\)", t)]
    return problems


def test_pf1_10_every_number_in_text_output_and_in_the_reports_follows_rule_10(corpus: dict[str, Ran], world: World) -> None:
    texts = {
        f"{name} {stream}": text
        for name, r in corpus.items() if r.call.kind not in ("json", "help", "version")
        for stream, text in (("stdout", r.out), ("stderr", r.err))
    }
    for folder in ("out-report-pair", "out-report-run"):
        texts[f"{folder}/report.md"] = (world.base / folder / "report.md").read_text(encoding="utf-8")
        texts[f"{folder}/receipt.html"] = visible_text((world.base / folder / "receipt.html").read_text(encoding="utf-8"))
        texts[f"{folder}/heatmap.svg"] = visible_text((world.base / folder / "heatmap.svg").read_text(encoding="utf-8"))
    ids = ids_given(corpus, world)
    found = {where: number_problems(text, ids) for where, text in texts.items()}
    found = {where: problems for where, problems in found.items() if problems}
    assert not found, found


def cells_of(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(event, cell) for event, block in doc["by_event"].items() for cell in block["cells"]]


def cell_strings(cell: dict[str, Any]) -> list[str]:
    """The cell's numbers as rule 10 prints them: rates, delta and MDE to three decimals,
    p and q as p-values. A delta's sign may carry a plus; the substring is the same."""
    # PF4.27: a condition's limit may be null with its note; no text surface prints a
    # number for it and each says the reason in words, so a null limit is looked for as its note.
    limit = cell["mde_note"] if cell["mde"] is None else f"{cell['mde']:.3f}"
    return [f"{cell['rate_a']:.3f}", f"{cell['rate_b']:.3f}", f"{cell['delta']:.3f}", p_text(cell["p"]), p_text(cell["q"]), limit]


def test_pf1_10_diffs_text_cell_tables_print_each_cells_numbers_by_rule_10(corpus: dict[str, Ran]) -> None:
    doc = strict_json(corpus["json-diff"].out)
    lines = corpus["diff-fisher-named"].out.splitlines()
    for event, cell in cells_of(doc):
        values = [str(v) for v in cell["config"].values()]
        wanted = cell_strings(cell)
        assert any(all(v in line for v in values + wanted) for line in lines), (event, cell["config"], wanted)


def test_pf1_10_the_reports_cell_tables_and_heatmap_print_fractions_by_rule_10(corpus: dict[str, Ran], world: World) -> None:
    doc = strict_json(corpus["json-diff"].out)
    report = (world.base / "out-report-pair" / "report.md").read_text(encoding="utf-8").splitlines()
    receipt = visible_text((world.base / "out-report-pair" / "receipt.html").read_text(encoding="utf-8"))
    labels = visible_text((world.base / "out-report-pair" / "heatmap.svg").read_text(encoding="utf-8")).split()
    for event, cell in cells_of(doc):
        wanted = cell_strings(cell)
        coords = [re.compile(rf"(?<![\w.]){re.escape(f'{v:.10g}' if isinstance(v, float) else str(v))}(?![\w.])") for v in cell["config"].values()]
        assert any(all(c.search(line) for c in coords) and all(w in line for w in wanted) for line in report), (event, cell["config"], wanted)
        assert all(w in receipt for w in wanted), (event, cell["config"], wanted)
        assert any(label.lstrip("+") == f"{cell['delta']:.3f}".lstrip("+") for label in labels), (event, cell["config"], cell["delta"])


def test_pf1_10_json_carries_the_unformatted_values(corpus: dict[str, Ran]) -> None:
    cells = [cell for _, cell in cells_of(strict_json(corpus["json-diff"].out))]
    for cell in cells:
        for key in ("rate_a", "rate_b", "delta", "p", "q", "mde"):
            if key == "mde" and cell[key] is None:
                # PF4.27: a null limit carries its note from the closed list.
                assert cell["mde_note"] in {"no room", "none detectable", "cannot be flagged", "no matched pairs"}, cell
                continue
            assert isinstance(cell[key], (int, float)) and not isinstance(cell[key], bool), (key, cell[key])
        assert cell["n_a"] == 120 and isinstance(cell["n_a"], int)
    assert any(abs(cell["rate_a"] - round(cell["rate_a"], 3)) > 1e-9 for cell in cells), "rates are rounded in JSON"
    assert any(0 < cell["p"] < 1e-3 for cell in cells)


# ---------- PF1.11 --json ----------


#: Each --json invocation, its schema, and the text invocation whose exit code it must share.
JSON_CALLS = {
    "json-sweep": ("poisson-prove.sweep/1", "sweep-yes"),
    "json-diff": ("poisson-prove.diff/1", "diff-fisher-named"),
    "json-check": ("poisson-prove.check/1", "check-passed"),
    "json-check-failed": ("poisson-prove.check/1", "check-failed"),
    "json-report": ("poisson-prove.report/1", "report-pair"),
    "json-paired": ("poisson-prove.paired/1", "paired"),
    "json-serve": ("poisson-prove.viewpair/7", None),
    "json-inspect": ("poisson-prove.inspect/1", "inspect"),
    "json-runs": ("poisson-prove.runs/1", "runs"),
}


@pytest.mark.parametrize("name", list(JSON_CALLS))
def test_pf1_11_json_prints_one_strict_document_starting_schema_verdict_sentence_with_the_same_exit_code(name: str, corpus: dict[str, Ran]) -> None:
    schema, twin = JSON_CALLS[name]
    r = corpus[name]
    doc = strict_json(r.out)
    assert isinstance(doc, dict)
    assert list(doc)[:3] == ["schema", "verdict", "sentence"], list(doc)[:5]
    assert doc["schema"] == schema
    assert isinstance(doc["verdict"], str) and doc["verdict"] and isinstance(doc["sentence"], str) and doc["sentence"], doc
    if twin is not None:
        assert r.code == corpus[twin].code, (r.code, corpus[twin].code)


def test_pf1_11_a_non_finite_number_is_null_beside_a_note_saying_why(corpus: dict[str, Ran]) -> None:
    """The pair holds cells with no events in either arm, whose statistic is not a finite number."""
    cells = [cell for _, cell in cells_of(strict_json(corpus["json-diff"].out))]
    nulls = [cell for cell in cells if cell["stat"] is None]
    assert nulls, "no cell's statistic is null"
    for cell in nulls:
        assert any(key == "_note" or key.endswith("_note") for key in cell), cell


def run_entries(doc: Any) -> dict[str, dict[str, Any]]:
    """Every object in a document that names a run, by its run id."""
    found: dict[str, dict[str, Any]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("run_id"), str):
                found[node["run_id"]] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    return found


def test_pf1_11_runs_json_names_the_writer_of_a_0_0_1_run_as_proofload_and_a_new_runs_as_this_build(world: World, tmp_path: Path) -> None:
    """PF0.12, carried here because ``--json`` arrives in PF1: the old run's version key reads as
    the page and the report read it, ``0.0.1 (as proofload)``; a new run's is this build's."""
    import poisson_prove

    store = tmp_path / "store"
    for role in ("quickstart_before", "quickstart_after"):
        shutil.copytree(OLD / "store" / OLD_RUNS[role], store / OLD_RUNS[role])
    shutil.copytree(world.store / world.a, store / world.a)
    r = prove(["--store", str(store), "runs", "--json"], home=world.home, cwd=tmp_path)
    assert r.code == 0, r.err
    entries = run_entries(strict_json(r.out))
    for role in ("quickstart_before", "quickstart_after"):
        assert entries[OLD_RUNS[role]]["poisson_prove_version"] == "0.0.1 (as proofload)", entries[OLD_RUNS[role]]
    assert entries[world.a]["poisson_prove_version"] == poisson_prove.__version__, entries[world.a]
    assert "proofload" not in json.dumps(entries[world.a])


# ---------- PF1.12 ASCII, pipes and files ----------


@pytest.mark.parametrize("argv", [
    ["diff", "{A}", "{B}", "--method", "mcnemar_bh"],
    # PF4.30: the 120-replicate design accepts MAX_MDE.
    ["sweep", "{spec}", "--target", MOCK + ":rollout", "--dry-run", "--max-mde", MAX_MDE],
], ids=["diff", "sweep-dry-run"])
def test_pf1_12_an_ascii_only_stdout_gets_the_plain_rendering_in_ascii_line_for_line(argv: list[str], world: World, tmp_path: Path) -> None:
    full = ["--store", str(world.store), *(world.fill(word) for word in argv)]

    def run(encoding: str) -> tuple[int, bytes]:
        done = subprocess.run(
            [sys.executable, "-m", "poisson_prove", *full], cwd=tmp_path, env=child_env(world.home, PYTHONIOENCODING=encoding),
            stdin=subprocess.DEVNULL, capture_output=True, timeout=300,
        )
        return done.returncode, done.stdout

    code_utf8, utf8 = run("utf-8")
    code_ascii, ascii_ = run("ascii")
    assert code_utf8 == code_ascii == 0
    assert ascii_.isascii()
    wide, narrow = utf8.decode("utf-8").splitlines(), ascii_.decode("ascii").splitlines()
    assert len(wide) == len(narrow)
    for w, n in zip(wide, narrow):
        assert (n == w) if w.isascii() else (re.findall(r"\d+", n) == re.findall(r"\d+", w)), (w, n)


def test_pf1_12_a_closed_pipe_exits_0_with_nothing_on_stderr(world: World, tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", "--store", str(world.store), "diff", world.a, world.b, "--method", "mcnemar_bh"],
        cwd=tmp_path, env=child_env(world.home), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    proc.stdout.close()  # the reader is gone before the first byte is written
    _, err = proc.communicate(timeout=300)
    assert proc.returncode == 0, err
    assert err == b"", err


#: Every text file opened for writing without an encoding gets a non-UTF-8 one, as on a machine
#: whose locale is Latin-1. A file Prove writes in UTF-8 by explicit argument is unaffected.
LATIN1_LOCALE = """\
import builtins as _builtins
import io as _io
import os as _os

_real_open = _io.open


def _open(file, mode="r", buffering=-1, encoding=None, *args, **kwargs):
    if any(flag in mode for flag in "wax") and "b" not in mode and encoding in (None, "locale"):
        encoding = "latin-1"
    return _real_open(file, mode, buffering, encoding, *args, **kwargs)


_io.open = _builtins.open = _open
"""


def test_pf1_12_every_file_prove_writes_is_utf_8(world: World, tmp_path: Path) -> None:
    title = "Prüfung – ü"
    home = tmp_path / "home"
    home.mkdir()
    # The paired files carry the sweep's name, so a non-ASCII one puts non-ASCII bytes in each.
    sweep_name = "S1 – Prüfung"
    declaration = tmp_path / "decl.toml"
    declaration.write_text(PAIRED_DECLARATION.format(cap="").replace('name = "S1"', f'name = "{sweep_name}"'), encoding="utf-8")
    pair_out, run_out, store = tmp_path / "pair", tmp_path / "run", tmp_path / "store"
    for argv, code in (
        (["--store", str(world.store), "report", world.a, world.b, "--x", "task_id", "--y", "tool_fail_rate", "--title", title, "--out", str(pair_out)], 0),
        (["--store", str(world.store), "report", world.a, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--title", title, "--out", str(run_out)], 0),
        # PF4.30: the 120-replicate design accepts MAX_MDE.
        (["--store", str(store), "sweep", str(world.folders["spec"]), "--target", f"{MOCK}:rollout", "--yes", "--max-mde", MAX_MDE], 0),
        (["--store", str(world.paired_store), "paired", "--declaration", str(declaration), "--out", str(tmp_path / "paired")], 0),
    ):
        r = prove_with(LATIN1_LOCALE, argv, home=home, cwd=tmp_path)
        assert r.code == code, (argv, r)
    failing = LATIN1_LOCALE + "\nimport poisson_prove.store as _s\n\ndef _boom(self, *a, **k):\n    raise RuntimeError('Fehler ü')\n\n_s.Store.__init__ = _boom\n"
    assert prove_with(failing, ["--store", str(world.store), "runs"], home=home, cwd=tmp_path).code == 3
    written = [p for root in (pair_out, run_out, store, home, tmp_path / "paired") for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".html", ".svg", ".json", ".log", ".txt")]
    assert written
    for path in written:
        path.read_bytes().decode("utf-8")
    for out in (pair_out, run_out):
        for name in ("report.md", "receipt.html"):
            assert title in (out / name).read_text(encoding="utf-8"), out / name
    paired_files = [p for p in (tmp_path / "paired").rglob("*") if p.is_file()]
    assert paired_files
    for path in paired_files:
        assert sweep_name in path.read_text(encoding="utf-8"), path
    assert "Fehler ü" in (home / ".cache" / "poisson-prove" / "errors.log").read_text(encoding="utf-8")


# ---------- PF1.13 the sweep's plan ----------


def test_pf1_13_dry_run_prints_the_plan_first_and_exits_0_writing_nothing(corpus: dict[str, Ran], world: World) -> None:
    r = corpus["sweep-dry-run"]
    assert r.code == 0, r.err
    first = r.out.splitlines()[0]
    assert first.startswith("plan  ") and "1,080" in first, r.out
    assert FIRST_LINE.match(first), r.out
    assert not (world.base / "dry-store").exists()


@pytest.mark.parametrize("name,closing", [
    ("sweep-yes", "done"), ("sweep-max-rollouts", "stopped"), ("sweep-all-errored", "stopped"),
    ("refuse-underpowered", None), ("refuse-stdin-not-a-terminal", None), ("refuse-over-max-cost", None),
])
def test_pf1_13_every_sweep_prints_its_plan_first_and_a_finished_one_one_closing_verdict_line(name: str, closing: str | None, corpus: dict[str, Ran]) -> None:
    out = corpus[name].out.splitlines()
    assert out and out[0].startswith("plan  ") and FIRST_LINE.match(out[0]), corpus[name].out[:400]
    verdicts = [line for line in out[1:] if FIRST_LINE.match(line)]
    assert verdicts == [] if closing is None else (len(verdicts) == 1 and verdicts[0].startswith(f"{closing}  ")), out
    assert not any(line.startswith("run_id:") for line in out), out


def test_pf1_13_a_stdin_that_is_not_a_terminal_without_yes_prints_the_plan_then_refuses(world: World, tmp_path: Path) -> None:
    store = tmp_path / "store"
    # PF4.30: the 120-replicate design accepts MAX_MDE.
    done = subprocess.run(
        [sys.executable, "-m", "poisson_prove", "--store", str(store), "sweep", str(world.folders["spec"]), "--target", f"{MOCK}:rollout",
         "--max-mde", MAX_MDE],
        cwd=tmp_path, env=child_env(world.home), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300,
    )
    assert done.returncode == 1
    lines = done.stdout.decode("utf-8").splitlines()
    plan = next(i for i, line in enumerate(lines) if line.startswith("plan  "))
    error = next(i for i, line in enumerate(lines) if line.startswith("error: "))
    assert plan < error, lines
    assert run_ids(store) == set()


def test_pf1_13_on_modal_an_estimate_over_max_cost_is_refused_before_the_question(world: World, tmp_path: Path) -> None:
    def sweep(max_cost: str, answer: bytes) -> subprocess.CompletedProcess[bytes]:
        controller, terminal = os.openpty()
        try:
            os.write(controller, answer)
            return subprocess.run(
                # PF4.30: the 120-replicate design accepts MAX_MDE.
                [sys.executable, "-m", "poisson_prove", "--store", str(tmp_path / "store"), "sweep", str(world.folders["spec"]),
                 "--target", f"{MOCK}:rollout", "--backend", "modal", "--max-cost", max_cost, "--est-seconds", "36000", "--max-mde", MAX_MDE],
                cwd=tmp_path, env=child_env(world.home, world.folders["fake_modal"]), stdin=terminal,
                capture_output=True, timeout=300,
            )
        finally:
            os.close(terminal)
            os.close(controller)

    over = sweep("0.5", b"y\n")
    assert over.returncode == 1, over.stderr
    assert b"[y/N]" not in over.stderr, over.stderr
    assert over.stdout.decode("utf-8").startswith("plan  "), over.stdout
    assert over.stderr.decode("utf-8").startswith("error: ") and b"$0.50" in over.stdout + over.stderr, over.stderr
    assert_clean_stderr(over.stderr)
    control = sweep("1000000000", b"n\n")
    assert b"[y/N]" in control.stderr, control.stderr
    assert control.returncode == 1, control.stderr
    # The answer "no" is a refusal like any other: an error line after the question.
    assert b"error: " in control.stderr, control.stderr
    assert_clean_stderr(control.stderr)
    assert run_ids(tmp_path / "store") == set()


def test_pf1_13_burlas_cap_refusal_keeps_the_plan_on_screen(world: World, tmp_path: Path) -> None:
    folder = tmp_path / "sweep"
    folder.mkdir()
    spec = folder / "sweep.toml"
    spec.write_text(
        'target_id = "bu-test@v0"\nt_unit = "steps"\nreplicates = 2\n\n[axes.cell]\ntype = "categorical"\nvalues = ["a", "b"]\n\n'
        '[burla]\nnodes = 1\nmachine_type = "m7i.2xlarge"\nslots_per_node = 2\nusd_per_node_hour = 360.0\n'
        'price_asof = "fixture price, 2026-09-27"\nledger = "ledgers/step.jsonl"\nhead_url = "http://localhost:5001"\n'
        'stop_cost = 0.005\nmax_cost = 0.01\nest_seconds_per_episode = 0.01\npackages = ["bu_targets"]\nbatch_size = 2\n'
        "boot_minutes = 20.0\nidle_minutes = 0.0\n",
        encoding="utf-8",
    )
    store = tmp_path / "store"
    # PF4.49: the 2-replicate design's limit is over 0.99, so its sweep passes --max-mde 1.
    r = prove(
        ["--store", str(store), "sweep", str(spec), "--target", "bu_targets.plain:rollout", "--backend", "burla", "--max-mde", "1", "--yes"],
        home=world.home, cwd=tmp_path, paths=(BU_TARGETS, world.folders["fake_burla"]),
    )
    assert r.code == 1, (r.out, r.err)
    assert r.out.splitlines()[0].startswith("plan  "), r.out
    lines = r.err.splitlines()
    assert lines[0].startswith("error: ") and all(line.startswith("  next: ") for line in lines[1:]), r.err
    assert "$0.01" in r.err and str(folder / "ledgers" / "step.jsonl") in r.out + r.err, (r.out, r.err)
    assert_clean_stderr(r.err)
    assert not (folder / "ledgers" / "step.jsonl").exists()
    assert run_ids(store) == set()


def test_pf1_13_a_sweep_stopped_by_max_rollouts_exits_3_with_what_was_kept_and_the_resume(corpus: dict[str, Ran], world: World) -> None:
    from poisson_prove.store import Store

    r = corpus["sweep-max-rollouts"]
    assert r.code == 3, (r.out, r.err)
    store = world.base / "capped-store"
    (run_id,) = run_ids(store)
    assert manifest(store, run_id)["status"] == "partial"
    kept = Store(store).count(run_id)
    stopped = [line for line in r.out.splitlines() if line.startswith("stopped  ")]
    assert len(stopped) == 1 and f"{kept:,}" in stopped[0], r.out
    assert not any(line.startswith("done  ") for line in r.out.splitlines()), r.out
    # PF3: the next line resumes the sweep as it was typed. This
    # sweep typed a spec path and --target, so the line carries the spec before --resume and the --target typed.
    spec, target = r.argv[r.argv.index("sweep") + 1], r.argv[r.argv.index("--target") + 1]
    nexts = [line for line in r.out.splitlines() + r.err.splitlines() if line.startswith("  next: poisson-prove sweep ")]
    assert len(nexts) == 1, (r.out, r.err)
    words = nexts[0].split()[1:]
    assert words[:2] == ["poisson-prove", "sweep"] and spec in words and "--resume" in words, nexts
    assert words.index(spec) < words.index("--resume"), nexts
    assert "--target" in words and words[words.index("--target") + 1] == target, nexts


def test_pf1_13_a_sweep_in_which_every_rollout_raised_exits_3_naming_the_commonest_error_for_inspect(corpus: dict[str, Ran], world: World) -> None:
    from poisson_prove.store import Store

    r = corpus["sweep-all-errored"]
    assert r.code == 3, (r.out, r.err)
    assert len([line for line in r.out.splitlines() if line.startswith("stopped  ")]) == 1, r.out
    assert not any(line.startswith("done  ") for line in r.out.splitlines()), r.out
    # The next line acts on the store the sweep was typed with, so it carries that --store.
    store = world.base / "errored-store"
    assert f"  next: poisson-prove inspect latest --event ValueError --store {store}" in r.out.splitlines() + r.err.splitlines(), (r.out, r.err)
    (run_id,) = run_ids(store)
    rows = Store(store).read(run_id, meta=False)
    assert rows["error"].notna().all() and len(rows) == 9
    value_error = {str(seed) for seed, cfg in zip(rows["seed"], rows["config"]) if cfg["cell"] != "a"}
    key_error = {str(seed) for seed, cfg in zip(rows["seed"], rows["config"]) if cfg["cell"] == "a"}
    found = prove(["--store", str(store), "inspect", run_id, "--event", "ValueError"], home=world.home, cwd=world.base)
    assert found.code == 0, found.err
    shown = set(re.findall(r"\d+", found.out))
    assert value_error <= shown and not (key_error & shown), (value_error, key_error, found.out)


def test_pf1_13_a_sweep_in_which_every_rollout_timed_out_exits_3_naming_episode_timeout_for_inspect(world: World, tmp_path: Path) -> None:
    spec = tmp_path / "two.toml"
    spec.write_text(TRIPLE_SPEC.replace('["a", "b", "c"]', '["a", "b"]').replace("replicates = 3", "replicates = 2"), encoding="utf-8")
    store = tmp_path / "store"
    # PF4.49: the 2-replicate design's limit is over 0.99, so its sweep passes --max-mde 1.
    r = prove(
        ["--store", str(store), "sweep", str(spec), "--target", "pf1_targets:sleeps", "--yes", "--max-mde", "1", "--episode-timeout", "0.5"],
        home=world.home, cwd=tmp_path, paths=(world.folders["targets"],),
    )
    assert r.code == 3, (r.out, r.err)
    assert len([line for line in r.out.splitlines() if line.startswith("stopped  ")]) == 1, r.out
    # The next line acts on the store the sweep was typed with, so it carries that --store.
    assert f"  next: poisson-prove inspect latest --event episode_timeout --store {store}" in r.out.splitlines() + r.err.splitlines(), (r.out, r.err)
    assert_clean_stderr(r.err)


# ---------- PF1.14 check and the cap check ----------


@pytest.mark.parametrize("name,word,code", [
    ("check-passed", "passed", 0),
    ("check-failed", "failed", 4),
    ("paired-under-cap", "under cap", 0),
    ("paired-at-cap", "at cap", 4),
    ("paired-equal-cap", "at cap", 4),
])
def test_pf1_14_check_and_the_cap_check_say_their_verdict_first_and_a_check_that_did_not_pass_exits_4(name: str, word: str, code: int, corpus: dict[str, Ran]) -> None:
    r = corpus[name]
    assert r.code == code, (r.out, r.err)
    first = r.out.splitlines()[0]
    assert first.startswith(f"{word}  ") and FIRST_LINE.match(first), r.out
    if name.startswith("check"):
        event = r.argv[r.argv.index("--event") + 1]
        assert event in first, first


# ---------- PF1.15 the first stdout line and every stderr line ----------


def test_pf1_15_every_stderr_line_is_an_error_a_note_an_indented_line_the_question_or_progress(corpus: dict[str, Ran]) -> None:
    found = {name: [line for line in r.err.splitlines() if not stderr_allowed(line)] for name, r in corpus.items()}
    found = {name: lines for name, lines in found.items() if lines}
    assert not found, found
