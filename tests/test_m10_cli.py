"""M10 -- the command line's frozen tests.

Every test drives ``poisson_prove.cli.main(argv, stdout=, stderr=, stdin=)`` in-process with
``StringIO`` streams. The one exception is the entrypoint smoke test, which shells out to the
installed ``poisson-prove`` script and is skipped when that script is not on PATH (the same
environment dependency S0's entrypoint test carries).

Stores live under ``tmp_path``. Golden tests point ``--store`` at the generated lattice pair
(``tests/lattice.py``) read-only and write report output under ``tmp_path``. The mock agent
(``poisson_prove.examples.mock_agent``) is imported lazily, so collection does not depend on
it.

Two reading notes:

- I4 drives the prompt through a ``StringIO`` whose ``isatty()`` returns True, so the
  prompt path is exercised under either reading of the non-TTY rule (the general rule says any
  non-TTY stdin without ``--yes`` exits 2; I4 says a piped ``y`` proceeds). I5 uses a plain,
  empty ``StringIO``, which both readings refuse with a message naming ``--yes``.
- The local backend records ``environment["import_path"]`` like the Modal backend, so the
  reproduction snippet's import line is checked exactly on a local run, as the
  ``rollout(<config JSON>, seed=<seed>)`` line is.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import poisson_prove
import poisson_prove.cli as cli
from poisson_prove.episode import Episode
from poisson_prove.executor import RunSummary, plan, preflight
from poisson_prove.executor_modal import ImageSpec, ModalOptions, ModalTarget
from poisson_prove.report import NEUTRAL_FILL
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
import lattice
from conftest import quickstart_design

LATTICE_ROOT = lattice.root()
# The packaged spec's design at 100 replicates, the count this file's numbers are for.
QUICKSTART = quickstart_design()
# PF4.30, PF4.48a: the quickstart design at 100 replicates with nothing declared has a
# detection limit (0.262 at base rate 0.400) above the default accepted change of 0.20, so its
# sweep is refused; every sweep of it in this file accepts 0.3, the smallest round value above
# the limit.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")

MOCK_MODULE = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
RAISING = f"{__name__}:always_raises"

VERBS = ("sweep", "diff", "report", "check", "inspect", "runs")
METHODS = {"fisher_bh", "mcnemar_bh", "logrank_bh"}
REPORT_FILES = {"report.md", "heatmap.svg", "receipt.html"}
DIFF_JSON_ENVELOPE = {"schema", "verdict", "sentence", "next"}

QUICKSTART_CELLS = 9
QUICKSTART_REPLICATES = 100
QUICKSTART_ROWS = QUICKSTART_CELLS * QUICKSTART_REPLICATES
# PF3: the packaged spec's target id is mock-agent, where the old
# examples/quickstart.toml said mock-agent@v0.
QUICKSTART_TARGET_ID = "mock-agent"
QUICKSTART_T_UNIT = "tool_calls"
MOCK_HORIZON = 20.0
TRACE_SCHEMA = "poisson-prove.trace/1"
QUICKSTART_BUDGET_S = 30.0

HEADLINE_RE = re.compile(
    r"(\d+) of (\d+) cells safer, (\d+) worse \((\S+), BH q<([^,]+), (paired|unpaired)\)\."
)
STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")  # nine tab-delimited columns (A8a: step_name, attempt, outcome, gate after error)
STEP_LINE_SAMPLE = "  0\ttool\tsearch_catalog\t12.5\t-\t-\t-\t-\t-"  # nine columns: P8-21's positive control for every negative use
SNIPPET_CALL_RE = re.compile(r"(\w+)\((\{.*\}),\s*seed=(\d+)\)")
SNIPPET_MARKER = "# reproduce one episode"

MODAL_TABLES = """
[modal]
concurrency = 4
batch_size = 32
episode_timeout = 12.5
infra_retries = 1
max_cost = 100.0
est_seconds_per_episode = 0.5
app_name = "from-table"

[modal.image]
python = "3.12"
pip = ["numpy", "pandas"]
gpu = "T4"

[modal.image-gpu]
python = "3.11"
pip = ["torch"]
gpu = "A10G"
"""
TABLE_OPTIONS = ModalOptions(
    concurrency=4,
    batch_size=32,
    episode_timeout=12.5,
    infra_retries=1,
    max_cost=100.0,
    est_seconds_per_episode=0.5,
    app_name="from-table",
)
TABLE_IMAGE = ImageSpec(python="3.12", pip=("numpy", "pandas"), gpu="T4")
TABLE_IMAGE_GPU = ImageSpec(python="3.11", pip=("torch",), gpu="A10G")


# ---------- harness ----------


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        return self.out + self.err

    @property
    def lines(self) -> list[str]:
        return [line for line in self.out.splitlines() if line.strip()]


class TtyStringIO(StringIO):
    """A StringIO that claims to be a terminal, so the prompt path is reached for I4."""

    def isatty(self) -> bool:
        return True


def run_cli(argv: Sequence[str], stdin: StringIO | None = None) -> Result:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO() if stdin is None else stdin)
    return Result(code, out.getvalue(), err.getvalue())


def assert_clean_refusal(r: Result, code: int) -> None:
    assert r.code == code, r.text
    assert "Traceback" not in r.text, r.text


def new_run_id(root: Path, before: Sequence[str]) -> str:
    # A sweep's output no longer ends with a run_id line: the new run is
    # the one the store gained.
    added = set(Store(root).runs()) - set(before)
    assert len(added) == 1, (sorted(before), sorted(added))
    return added.pop()


def sweep(store: Path, target: str, *extra: str) -> str:
    before = Store(store).runs()
    r = run_cli(["--store", str(store), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", target, "--yes", *extra])
    assert r.code == 0, r.text
    return new_run_id(store, before)


def three_decimals(text: str) -> str:
    return re.sub(r"\d+\.\d+", lambda m: f"{float(m.group(0)):.3f}", text)


def mentions_path(text: str, path: Path) -> bool:
    return str(path) in text or str(path.resolve()) in text


def mock_agent() -> Any:
    import importlib

    return importlib.import_module(MOCK_MODULE)


def copy_lattice(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    for run_id in (lattice.RUN_A, lattice.RUN_B):
        shutil.copytree(LATTICE_ROOT / run_id, store / run_id)


def fisher_reference_counts() -> tuple[int, int]:
    """``(lower, higher)`` for the lattice's ``tripped`` under scipy's Fisher and one BH family
    over every condition at q 0.05 (``lattice.fisher``), never from Prove."""
    return lattice.directions(lattice.fisher(lattice.EVENT, 0.05))


def always_raises(cfg: dict[str, Any], seed: int) -> Episode:
    raise RuntimeError("this rollout always raises")


def write_run(
    store: Store,
    run_id: str,
    *,
    salt: str,
    fell_per_cell: dict[float, int],
    n: int = 32,
    t_unit: str = "seconds",
) -> None:
    """A complete synthetic run: one cell per ``x``, ``fell_per_cell[x]`` of ``n`` fell, no traces."""
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="synthetic@v0",
            t_unit=t_unit,
            run_salt=salt,
            axis_types={"x": "continuous"},
            backend="synthetic",
            environment={},
        )
    )
    records = []
    for x, fell in fell_per_cell.items():
        for k in range(n):
            episode = (
                Episode(outcome="fell", t=3.0, horizon=10.0)
                if k < fell
                else Episode(outcome="survived", t=10.0, horizon=10.0)
            )
            records.append(
                EpisodeRecord.from_episode(
                    episode,
                    run_id=run_id,
                    config={"x": x},
                    seed=1000 * int(x) + k,
                    replicate_index=k,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


def inspect_blocks(out: str, hashes: set[str]) -> tuple[list[list[str]], list[str]]:
    """Split inspect output into per-row blocks (each starting at a line naming a config_hash)
    and the trailing reproduction snippet."""
    body, marker, tail = out.partition(SNIPPET_MARKER)
    assert marker, f"no {SNIPPET_MARKER!r} snippet in inspect output:\n{out}"
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in body.splitlines():
        # Text output shows a config_hash at 12 hex characters.
        if any(h[:12] in line for h in hashes):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return blocks, (marker + tail).splitlines()


def assert_block_is_row(block: list[str], row: Any) -> None:
    text = "\n".join(block)
    assert row.config_hash[:12] in block[0], block[0]  # 12 hex characters in text (rule 10)
    assert re.search(rf"\b{row.seed}\b", text), f"seed {row.seed} missing from block:\n{text}"
    found = False
    for line in block:
        m = re.search(r"\{.*\}", line)
        if m is None:
            continue
        try:
            found = found or json.loads(m.group(0)) == row.config
        except json.JSONDecodeError:
            continue
    assert found, f"no JSON line equal to {row.config!r} in block:\n{text}"


def assert_trace_lines(block: list[str], row: Any) -> None:
    trace = row.meta["trace"]
    steps = trace["spans"]
    step_lines = [line for line in block if STEP_LINE_RE.match(line)]
    assert len(step_lines) == len(steps) == int(row.t), "\n".join(block)
    columns = [line.split("\t") for line in step_lines]
    for j, step in enumerate(steps):
        want = (str(step["kind"]), str(step["name"]))
        assert any(
            int(cols[0]) in (j, j + 1) and (cols[1], cols[2]) == want for cols in columns
        ), (j, step, step_lines)


# ---------- fixtures ----------


@dataclass(frozen=True)
class MockRuns:
    root: Path
    a: str  # rollout, fresh salt
    b: str  # rollout_patched, --pair-with a
    c: str  # rollout, fresh salt (unpaired with a)

    @property
    def store(self) -> Store:
        return Store(self.root)


@pytest.fixture(scope="module")
def mock_runs(tmp_path_factory: pytest.TempPathFactory) -> MockRuns:
    """Three mock-agent runs plus the lattice pair in one store. Never mutated by a test.

    The lattice runs were written on 2026-01-15, so they are older than the three mock runs and
    I17's newest-first order puts the mock runs first."""
    root = tmp_path_factory.mktemp("mock-store")
    copy_lattice(root)
    a = sweep(root, ROLLOUT)
    b = sweep(root, PATCHED, "--pair-with", a)
    c = sweep(root, ROLLOUT)
    return MockRuns(root=root, a=a, b=b, c=c)


@pytest.fixture
def store_root(tmp_path: Path) -> Path:
    return tmp_path / "store"


@pytest.fixture
def modal_toml(tmp_path: Path) -> Path:
    path = tmp_path / "quickstart-modal.toml"
    path.write_text(QUICKSTART.read_text() + MODAL_TABLES)
    return path


class CapturedRunModal:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ModalTarget, Store, ModalOptions | None]] = []

    def __call__(
        self,
        p: Any,
        target: ModalTarget,
        store: Store,
        *,
        options: ModalOptions | None = None,
        on_progress: Any = None,
    ) -> RunSummary:
        self.calls.append((p, target, store, options))
        return RunSummary(
            run_id=p.run_id,
            n_ok=len(p.pairs),
            n_errored=0,
            n_timeout=0,
            wall_time=0.0,
            stopped_by=None,
            complete=True,
        )


@pytest.fixture
def captured_run_modal(monkeypatch: pytest.MonkeyPatch) -> CapturedRunModal:
    # A missing modal package is refused before the plan, so the patched
    # launch seam is reached only when modal imports.
    monkeypatch.setitem(
        sys.modules, "modal", importlib.util.module_from_spec(importlib.machinery.ModuleSpec("modal", None))
    )
    captured = CapturedRunModal()
    # PF5 (PF5.7): the face runs no backend; the core calls the Modal runner, so
    # the stand-in replaces it where it is defined, which the core reads when it runs a plan.
    monkeypatch.setattr(importlib.import_module("poisson_prove.executor_modal"), "run_modal", captured)
    return captured


@pytest.fixture
def modal_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [n for n in sys.modules if n == "modal" or n.startswith("modal.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "modal", None)


# ---------- I1: help, version, unknown verb ----------


def test_i1_no_arguments_prints_an_error_and_exits_two() -> None:
    r = run_cli([])
    # No arguments is a wrong command line: exit 2, an error line pointing at --help, nothing
    # on stdout.
    assert r.code == 2, r.text
    assert r.out == "", r.out
    err = r.err.splitlines()
    assert err and err[0].startswith("error: "), r.err
    assert any(line.startswith("  next: ") and "poisson-prove --help" in line for line in err[1:]), r.err
    assert "Traceback" not in r.text


def test_i1_help_lists_the_six_verbs() -> None:
    r = run_cli(["--help"])
    assert r.code == 0, r.text
    assert "usage" in r.out.lower()
    for verb in VERBS:
        assert verb in r.out, verb


def test_i1_version_prints_package_version() -> None:
    r = run_cli(["--version"])
    assert r.code == 0, r.text
    assert poisson_prove.__version__ in r.out


def test_i1_unknown_verb_returns_two_with_message_on_stderr() -> None:
    r = run_cli(["frobnicate"])
    assert_clean_refusal(r, 2)
    assert r.err.strip(), "expected a message on stderr"


def test_i1_verb_help_returns_zero() -> None:
    for verb in VERBS:
        r = run_cli([verb, "--help"])
        assert r.code == 0, (verb, r.text)
        assert "usage" in r.out.lower(), verb


# ---------- I2: --store precedence ----------


def test_i2_store_flag_beats_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag, env = tmp_path / "flag-store", tmp_path / "env-store"
    flag.mkdir()  # E1: a root with no directory is refused; an empty one lists nothing
    monkeypatch.setenv("POISSON_PROVE_STORE", str(env))
    r = run_cli(["--store", str(flag), "runs"])
    assert r.code == 0, r.text
    assert mentions_path(r.out, flag)
    assert not mentions_path(r.out, env)


def test_i2_env_beats_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "env-store"
    env.mkdir()  # E1
    monkeypatch.setenv("POISSON_PROVE_STORE", str(env))
    monkeypatch.chdir(tmp_path)
    r = run_cli(["runs"])
    assert r.code == 0, r.text
    assert mentions_path(r.out, env)
    assert "prove-runs" not in r.out


def test_i2_default_is_prove_runs_in_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "prove-runs").mkdir()  # E1
    r = run_cli(["runs"])
    assert r.code == 0, r.text
    assert "prove-runs" in r.out


def test_i2_resolved_store_is_the_one_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag, env = tmp_path / "flag-store", tmp_path / "env-store"
    write_run(Store(flag), "only-in-flag", salt="s", fell_per_cell={1.0: 4})
    write_run(Store(env), "only-in-env", salt="s", fell_per_cell={1.0: 4})
    monkeypatch.setenv("POISSON_PROVE_STORE", str(env))
    via_flag = run_cli(["--store", str(flag), "runs"])
    via_env = run_cli(["runs"])
    assert "only-in-flag" in via_flag.out and "only-in-env" not in via_flag.out
    assert "only-in-env" in via_env.out and "only-in-flag" not in via_env.out


# ---------- I3: sweep, local, end to end ----------


def test_i3_sweep_local_end_to_end(store_root: Path) -> None:
    r = run_cli(["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--yes"])
    assert r.code == 0, r.text
    run_id = new_run_id(store_root, [])
    store = Store(store_root)
    assert store.runs() == [run_id]
    manifest = store.manifest(run_id)
    assert manifest.status == "complete"
    assert manifest.target_id == QUICKSTART_TARGET_ID
    assert manifest.t_unit == QUICKSTART_T_UNIT
    assert manifest.backend == "local"
    df = store.read(run_id)
    assert len(df) == QUICKSTART_ROWS
    assert df["config_hash"].nunique() == QUICKSTART_CELLS
    assert df["outcome"].notna().all(), "the mock agent must not error"
    # The end of a sweep is a verdict line plus detail lines, not RunSummary fields:
    # the summary's facts are read from the store and the verdict line by value.
    tally = store.tally(run_id)
    assert (tally.with_outcome, tally.no_outcome, tally.timed_out) == (QUICKSTART_ROWS, 0, 0)
    assert df["error"].isna().all()
    verdicts = [line for line in r.out.splitlines() if line.startswith("done  ")]
    assert len(verdicts) == 1 and f"{QUICKSTART_ROWS:,}" in verdicts[0], r.out


# ---------- I4: the pre-flight prompt ----------


def test_i4_declined_prompt_exits_one_and_creates_nothing(store_root: Path) -> None:
    expected = preflight(plan(SweepSpec.load(QUICKSTART), Store(store_root)))
    r = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT],
        stdin=TtyStringIO("n\n"),
    )
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    # The pre-flight lines follow the plan, not necessarily as one block, and
    # text prints fractions to three decimals (rule 10) where the library's pre-flight keeps full
    # precision, so both sides are compared with every decimal at three places.
    out = three_decimals(r.out)
    for line in expected.strip().splitlines():
        assert three_decimals(line.strip()) in out, (line, r.out)
    assert "[y/N]" in r.err  # The question goes to stderr.
    assert Store(store_root).runs() == []


@pytest.mark.parametrize("answer", ["", "maybe\n", "N\n"], ids=["empty-line", "other-word", "upper-n"])
def test_i4_anything_but_yes_is_a_decline(store_root: Path, answer: str) -> None:
    r = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT],
        stdin=TtyStringIO(answer),
    )
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert Store(store_root).runs() == []


@pytest.mark.parametrize("answer", ["y\n", "YES\n", "  yes  \n"], ids=["y", "upper-yes", "padded-yes"])
def test_i4_accepted_prompt_runs(store_root: Path, answer: str) -> None:
    r = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT],
        stdin=TtyStringIO(answer),
    )
    assert r.code == 0, r.text
    assert "[y/N]" in r.err  # The question goes to stderr.
    run_id = new_run_id(store_root, [])
    assert Store(store_root).manifest(run_id).status == "complete"


# ---------- I5: non-interactive stdin ----------


def test_i5_non_tty_stdin_without_yes_exits_one_naming_the_flag(store_root: Path) -> None:
    r = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT],
        stdin=StringIO(),
    )
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert "--yes" in r.text, r.text
    assert Store(store_root).runs() == []


# ---------- I6: pairing, resume, exclusivity ----------


def test_i6_pair_with_inherits_salt_and_seeds(mock_runs: MockRuns) -> None:
    store = mock_runs.store
    ma, mb = store.manifest(mock_runs.a), store.manifest(mock_runs.b)
    assert mock_runs.b != mock_runs.a
    assert mb.run_salt == ma.run_salt
    cols = ["config_hash", "replicate_index", "seed"]
    pd.testing.assert_frame_equal(store.read(mock_runs.a)[cols], store.read(mock_runs.b)[cols])


def test_i6_fresh_sweeps_get_distinct_salts(mock_runs: MockRuns) -> None:
    store = mock_runs.store
    assert store.manifest(mock_runs.c).run_salt != store.manifest(mock_runs.a).run_salt


def test_i6_explicit_salt_is_recorded(store_root: Path) -> None:
    run_id = sweep(store_root, ROLLOUT, "--salt", "0123456789abcdef")
    assert Store(store_root).manifest(run_id).run_salt == "0123456789abcdef"


def test_i6_resume_completes_a_partial_run(store_root: Path) -> None:
    partial = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--yes", "--max-rollouts", "40"]
    )
    # A sweep stopped by --max-rollouts exits 3.
    assert partial.code == 3, partial.text
    run_id = new_run_id(store_root, [])
    store = Store(store_root)
    assert store.manifest(run_id).status == "partial"
    assert len(store.read(run_id)) == 40

    resumed = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--yes", "--resume", run_id]
    )
    assert resumed.code == 0, resumed.text
    # The resumed run is the partial one: the store gained no run.
    assert set(store.runs()) - {run_id} == set()
    assert store.runs() == [run_id]
    assert store.manifest(run_id).status == "complete"
    df = store.read(run_id)
    assert len(df) == QUICKSTART_ROWS
    assert not df.duplicated(["config_hash", "replicate_index"]).any()


@pytest.mark.parametrize(
    "extra",
    [
        ("--salt", "0123456789abcdef", "--pair-with", "A"),
        ("--salt", "0123456789abcdef", "--resume", "A"),
        ("--pair-with", "A", "--resume", "A"),
        ("--salt", "0123456789abcdef", "--pair-with", "A", "--resume", "A"),
    ],
    ids=["salt+pair", "salt+resume", "pair+resume", "all-three"],
)
def test_i6_salt_pair_with_resume_are_mutually_exclusive(mock_runs: MockRuns, extra: tuple[str, ...]) -> None:
    argv = [a if a != "A" else mock_runs.a for a in extra]
    before = mock_runs.store.runs()
    r = run_cli(["--store", str(mock_runs.root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--yes", *argv])
    assert_clean_refusal(r, 2)
    assert mock_runs.store.runs() == before


# ---------- I7: modal wiring ----------


def test_i7_modal_absent_exits_one_with_install_hint(store_root: Path, modal_absent: None) -> None:
    r = run_cli(
        ["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--backend", "modal", "--yes"]
    )
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert "pip install \"poisson-prove[modal]\"" in r.text, r.text
    assert Store(store_root).runs() == []


def test_i7_table_only_reaches_options_and_image(
    store_root: Path, modal_toml: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(
        ["--store", str(store_root), "sweep", str(modal_toml), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--backend", "modal", "--yes"]
    )
    assert r.code == 0, r.text
    assert "Backend: modal" in r.out
    assert len(captured_run_modal.calls) == 1
    p, target, store, options = captured_run_modal.calls[0]
    assert p.backend == "modal" and p.spec.total_rollouts() == QUICKSTART_ROWS
    assert isinstance(store, Store)
    assert target == ModalTarget(import_path=ROLLOUT, image=TABLE_IMAGE)
    assert options == TABLE_OPTIONS
    # No run_id line ends the output now; the patched launch writes no run,
    # so the planned run's id is checked by value in the output.
    assert p.run_id in r.out, r.out


def test_i7_flags_only_reach_options_with_default_image(
    store_root: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(
        [
            "--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT,
            "--backend", "modal", "--yes",
            "--concurrency", "3", "--infra-retries", "0", "--max-cost", "50",
            "--est-seconds", "2.0", "--app-name", "flag-app",
            "--batch-size", "8", "--episode-timeout", "7", "--max-rollouts", "100",
        ]
    )
    assert r.code == 0, r.text
    _, target, _, options = captured_run_modal.calls[0]
    assert target == ModalTarget(import_path=ROLLOUT, image=ImageSpec())
    assert options == ModalOptions(
        concurrency=3,
        batch_size=8,
        episode_timeout=7.0,
        infra_retries=0,
        max_rollouts=100,
        max_cost=50.0,
        est_seconds_per_episode=2.0,
        app_name="flag-app",
    )


def test_i7_flags_override_table(
    store_root: Path, modal_toml: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(
        [
            "--store", str(store_root), "sweep", str(modal_toml), *QUICKSTART_MAX_MDE, "--target", ROLLOUT,
            "--backend", "modal", "--yes",
            "--concurrency", "9", "--infra-retries", "5", "--max-cost", "250",
            "--est-seconds", "1.5", "--app-name", "from-flag",
        ]
    )
    assert r.code == 0, r.text
    _, target, _, options = captured_run_modal.calls[0]
    assert target.image == TABLE_IMAGE
    assert options == ModalOptions(
        concurrency=9,
        batch_size=32,
        episode_timeout=12.5,
        infra_retries=5,
        max_cost=250.0,
        est_seconds_per_episode=1.5,
        app_name="from-flag",
    )


def test_i7_image_flag_selects_the_named_section(
    store_root: Path, modal_toml: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(
        [
            "--store", str(store_root), "sweep", str(modal_toml), *QUICKSTART_MAX_MDE, "--target", ROLLOUT,
            "--backend", "modal", "--yes", "--image", "image-gpu",
        ]
    )
    assert r.code == 0, r.text
    _, target, _, options = captured_run_modal.calls[0]
    assert target.image == TABLE_IMAGE_GPU
    assert options == TABLE_OPTIONS


def test_i7_local_backend_never_calls_run_modal(store_root: Path, captured_run_modal: CapturedRunModal) -> None:
    sweep(store_root, ROLLOUT)
    assert captured_run_modal.calls == []


# ---------- I8: target errors ----------


@pytest.mark.parametrize(
    "target",
    [MOCK_MODULE, "poisson_prove.examples.no_such_module_xyz:rollout", f"{MOCK_MODULE}:no_such_attr"],
    ids=["no-colon", "missing-module", "missing-attr"],
)
def test_i8_unresolvable_target_exits_one_naming_the_path(store_root: Path, target: str) -> None:
    r = run_cli(["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", target, "--yes"])
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert target in r.text, r.text
    assert Store(store_root).runs() == []


def test_i8_rollout_that_always_raises_exits_three(store_root: Path) -> None:
    r = run_cli(["--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", RAISING, "--yes"])
    # A sweep in which every rollout errored exits 3.
    assert r.code == 3, r.text
    run_id = new_run_id(store_root, [])
    store = Store(store_root)
    assert store.manifest(run_id).status == "complete"
    df = store.read(run_id)
    assert len(df) == QUICKSTART_ROWS
    assert df["error"].notna().all()
    # The errored and ok counts are read from the store, not from summary fields.
    tally = store.tally(run_id)
    assert (tally.no_outcome, tally.with_outcome) == (QUICKSTART_ROWS, 0)


# ---------- I9: diff golden ----------


def test_i9_diff_markdown_summary_line(lattice_store: Store) -> None:
    # PF3: the lattice's runs share a salt, so the default is now the paired
    # test; these numbers are the unpaired test's, named.
    r = run_cli(["--store", str(LATTICE_ROOT), "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--method", "fisher_bh"])
    assert r.code == 0, r.text
    # PF2: diff's first lines are now a verdict block ending at the first
    # blank line; the report that follows it is unchanged, so its summary line is read there.
    verdict, _, report = r.out.partition("\n\n")
    # PF3 (PF3.6b): the verdict line now also names the test in plain words.
    # PF4 (PF4.20): the lattice's runs declare no kind for tripped, so the counts read in direction
    # words: 22 conditions fell and none rose, as scipy's Fisher with one BH family gives.
    assert fisher_reference_counts() == (22, 0)
    assert verdict.splitlines()[0].startswith("lower  tripped: 22 lower, 0 higher"), r.out
    assert "separate samples" in verdict.splitlines()[0], r.out
    summary = [
        line for line in report.splitlines() if "22 lower" in line and "0 higher" in line
    ]
    assert summary, r.out
    assert summary[0].startswith("tripped:"), summary[0]
    assert "fisher_bh" in report, r.out


def test_i9_diff_json(lattice_store: Store) -> None:
    # PF3: the lattice's runs share a salt, so the default is now the paired
    # test; these numbers are the unpaired test's, named.
    r = run_cli(["--store", str(LATTICE_ROOT), "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--json", "--method", "fisher_bh"])  # --json replaces --format
    assert r.code == 0, r.text
    data = json.loads(r.out)
    assert data["events"] == [lattice.EVENT] and data["inferred"] is False
    tripped = data["by_event"][lattice.EVENT]
    # PF4 (PF4.20): tripped's kind is unknown, so n_safer and n_worse are null and the 22 and the 0
    # are carried as n_lower and n_higher beside them.
    assert tripped["n_safer"] is None and tripped["n_worse"] is None and tripped["kind"] is None
    assert (tripped["n_lower"], tripped["n_higher"]) == fisher_reference_counts() == (22, 0)
    assert data["method"] == "fisher_bh" and data["q"] == 0.05
    assert data["seed_identity_match"] is True and data["unpaired_analysis"] is True and "paired" not in data
    assert len(tripped["cells"]) == lattice_store.read(lattice.RUN_A)["config_hash"].nunique() == lattice.CELLS == 72


def test_i9_diff_json_honours_q(lattice_store: Store) -> None:
    r = run_cli(
        ["--store", str(LATTICE_ROOT), "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--json", "--q", "0.01"]  # --json replaces --format
    )
    assert r.code == 0, r.text
    assert json.loads(r.out)["q"] == 0.01


def test_i9_diff_methods_all_json_keys(lattice_store: Store) -> None:
    r = run_cli(
        ["--store", str(LATTICE_ROOT), "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--methods", "all", "--json"]  # --json replaces --format
    )
    assert r.code == 0, r.text
    data = json.loads(r.out)
    # diff --json adds schema, verdict, sentence, next and any *_note key around today's keys.
    # PF4 (PF4.8): it also carries the primary method's omnibus and tree, and the
    # threshold with its source, beside the three method keys.
    pf4_keys = {"omnibus", "tree", "threshold", "threshold_source"}
    assert pf4_keys <= set(data)
    assert {
        k for k in data if k not in DIFF_JSON_ENVELOPE | pf4_keys and not k.endswith("_note")
    } == METHODS
    tripped = data["fisher_bh"]["by_event"][lattice.EVENT]
    # PF4 (PF4.20): tripped's kind is unknown, so the 22 and the 0 are n_lower and n_higher.
    assert tripped["n_safer"] is None and tripped["n_worse"] is None
    assert (tripped["n_lower"], tripped["n_higher"]) == fisher_reference_counts() == (22, 0)
    for method in METHODS:
        assert data[method]["method"] == method


def test_i9_diff_methods_all_markdown_has_method_table(lattice_store: Store) -> None:
    r = run_cli(["--store", str(LATTICE_ROOT), "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--methods", "all"])
    assert r.code == 0, r.text
    for method in METHODS:
        assert method in r.out, method
    # The lattice declares no kind for its event, so the table's two count columns are named in
    # direction words, falls then rises.
    header = next(line for line in r.out.splitlines() if line.startswith("| method | event | pairing |"))
    assert [c.strip() for c in header.strip().strip("|").split("|")] == ["method", "event", "pairing", "lower", "higher", "unchanged", "max_mde"], header


# ---------- I10: diff refusals ----------


def test_i10_unknown_run_exits_one(lattice_store: Store) -> None:
    r = run_cli(["--store", str(LATTICE_ROOT), "diff", lattice.RUN_A, "no-such-run", "--event", lattice.EVENT])
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert "no-such-run" in r.text, r.text


def test_i10_t_unit_mismatch_exits_one_with_unit_mismatch_wording(mock_runs: MockRuns) -> None:
    r = run_cli(["--store", str(mock_runs.root), "diff", lattice.RUN_A, mock_runs.a, "--event", lattice.EVENT])
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert "t_unit differs" in r.text, r.text
    assert "seconds" in r.text and QUICKSTART_T_UNIT in r.text


def test_i10_mcnemar_on_unpaired_runs_exits_one_with_not_pairable_wording(mock_runs: MockRuns) -> None:
    r = run_cli(
        ["--store", str(mock_runs.root), "diff", mock_runs.a, mock_runs.c, "--event", "violated", "--method", "mcnemar_bh"]
    )
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert "mcnemar_bh" in r.text and "run_salt" in r.text, r.text


def test_i10_mcnemar_on_paired_runs_works(mock_runs: MockRuns) -> None:
    r = run_cli(
        [
            "--store", str(mock_runs.root), "diff", mock_runs.a, mock_runs.b, "--event", "violated",
            "--method", "mcnemar_bh", "--json",  # --json replaces --format
        ]
    )
    assert r.code == 0, r.text
    payload = json.loads(r.out)
    assert payload["seed_identity_match"] is True and payload["unpaired_analysis"] is False and "paired" not in payload


# ---------- I11: report files ----------


def report_argv(out: Path, *extra: str) -> list[str]:
    return [
        "--store", str(LATTICE_ROOT), "report", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT,
        "--x", lattice.Y, "--y", lattice.X, "--out", str(out), *extra,
    ]


def test_i11_report_writes_exactly_three_files(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "report"
    # PF3: the lattice's runs share a salt, so the default is now the paired
    # test; these numbers are the unpaired test's, named.
    r = run_cli(report_argv(out, "--method", "fisher_bh"))
    assert r.code == 0, r.text
    assert {p.name for p in out.iterdir()} == REPORT_FILES
    ET.fromstring((out / "heatmap.svg").read_text())
    md = (out / "report.md").read_text()
    # PF4 (PF4.20): the lattice's runs declare no kind for tripped, so the counts read in direction
    # words: 22 conditions fell and none rose, as scipy's Fisher with one BH family gives.
    assert fisher_reference_counts() == (22, 0)
    assert "tripped: 22 lower, 0 higher" in md and "fisher_bh" in md
    # PF2: report's stdout now opens with `ok  wrote <folder> (N files)` and
    # one `  wrote  <path>` line per file, then a blank line, then what it printed before.
    verdict, _, rest = r.out.partition("\n\n")
    lines = verdict.splitlines()
    assert lines[0] == f"ok  wrote {out} ({len(REPORT_FILES)} files)", r.out
    # PF12: report saves the comparison it shows and says so on one
    # detail line after its wrote lines, the id's first 12 hex.
    assert re.fullmatch(r"  saved  comparison [0-9a-f]{12}", lines[-1]), r.out
    assert sorted(lines[1:-1]) == sorted(f"  wrote  {out / name}" for name in REPORT_FILES), r.out
    assert "tripped: 22 lower, 0 higher" in rest
    for name in REPORT_FILES:
        assert name in r.out, name
    assert NEUTRAL_FILL["light"] in (out / "receipt.html").read_text()
    assert NEUTRAL_FILL["dark"] in (out / "heatmap.svg").read_text()


def test_i11_theme_light_governs_heatmap_only(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "report-light"
    r = run_cli(report_argv(out, "--theme", "light"))
    assert r.code == 0, r.text
    assert NEUTRAL_FILL["light"] in (out / "heatmap.svg").read_text()
    assert NEUTRAL_FILL["light"] in (out / "receipt.html").read_text()


def test_i11_title_flag_names_the_report(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "report-titled"
    r = run_cli(report_argv(out, "--title", "Lattice before vs after"))
    assert r.code == 0, r.text
    assert (out / "report.md").read_text().startswith("# Lattice before vs after\n")


def test_i11_out_dir_is_created_when_absent(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deeper" / "report"
    r = run_cli(report_argv(out))
    assert r.code == 0, r.text
    assert {p.name for p in out.iterdir()} == REPORT_FILES


# ---------- I12: report determinism ----------


def test_i12_identical_arguments_give_byte_identical_files(lattice_store: Store, tmp_path: Path) -> None:
    digests = []
    for k in range(2):
        out = tmp_path / f"report-{k}"
        r = run_cli(report_argv(out, "--methods", "all"))
        assert r.code == 0, r.text
        digests.append({name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in REPORT_FILES})
    assert digests[0] == digests[1]


def test_i12_no_generated_at_flag_in_v0_1(lattice_store: Store, tmp_path: Path) -> None:
    r = run_cli(report_argv(tmp_path / "report", "--generated-at", "2026-01-01"))
    assert_clean_refusal(r, 2)


# ---------- I13: report refusals ----------


def test_i13_existing_non_empty_out_refused_without_writing(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "occupied"
    out.mkdir()
    (out / "keep.txt").write_text("do not touch\n")
    r = run_cli(report_argv(out))
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert {p.name for p in out.iterdir()} == {"keep.txt"}
    assert (out / "keep.txt").read_text() == "do not touch\n"


def test_i13_existing_empty_out_is_fine(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "empty"
    out.mkdir()
    r = run_cli(report_argv(out))
    assert r.code == 0, r.text
    assert {p.name for p in out.iterdir()} == REPORT_FILES


def test_i13_force_overwrites_non_empty_out(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "occupied"
    out.mkdir()
    (out / "keep.txt").write_text("stale\n")
    r = run_cli(report_argv(out, "--force"))
    assert r.code == 0, r.text
    assert REPORT_FILES <= {p.name for p in out.iterdir()}


def test_i13_fix_on_unknown_key_exits_one_with_axis_error_message(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "report"
    r = run_cli(report_argv(out, "--fix", "bogus=1"))
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    # The refusal names the flag, not the parameter.
    # Errors show values bare, not as Python reprs, and prose is not pinned.
    assert "--fix" in r.err and "bogus" in r.err, r.text
    assert not out.exists() or not any(out.iterdir())


def test_i13_x_equal_to_y_exits_one(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "report"
    r = run_cli(
        [
            "--store", str(LATTICE_ROOT), "report", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT,
            "--x", lattice.X, "--y", lattice.X, "--out", str(out),
        ]
    )
    assert_clean_refusal(r, 1)  # A refusal exits 1.
    assert not out.exists() or not any(out.iterdir())


def test_i13_fix_parses_toml_scalars(lattice_store: Store, tmp_path: Path) -> None:
    out = tmp_path / "report-1d"
    # PF3: the lattice's runs share a salt, so the default is now the paired
    # test; these counts are the unpaired test's, named.
    r = run_cli(
        [
            "--store", str(LATTICE_ROOT), "report", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT,
            "--x", lattice.Y, "--fix", f"{lattice.X}=0.1", "--out", str(out), "--method", "fisher_bh",
        ]
    )
    assert r.code == 0, r.text
    md = (out / "report.md").read_text()
    # --fix restricts the report grid, not the diff: the panel covers the gain=0.1 row while
    # the diff line still covers all 72 cells. Pinning the row's own counts pins the parse: the
    # row's count is the reference's over that row (3 lower), which no other gain row has.
    # PF4 (PF4.20): the lattice's runs declare no kind for tripped, so the counts (whole and panel)
    # read in direction words: 22 conditions fell and none rose.
    reference = lattice.fisher(lattice.EVENT, 0.05)
    row = [r["direction"] for r in reference.values() if r["config"][lattice.X] == 0.1]
    assert len(row) == len(lattice.LOAD)
    assert (row.count("lower"), row.count("higher")) == (3, 0)
    assert fisher_reference_counts() == (22, 0)
    whole = re.search(r"^tripped: 22 lower, 0 higher$", md, re.MULTILINE)
    panel = re.search(r"^## tripped: (\d+) lower, (\d+) higher$", md, re.MULTILINE)
    assert whole and panel, md
    assert (int(panel.group(1)), int(panel.group(2))) == (row.count("lower"), row.count("higher")) == (3, 0), panel.group(0)


def test_i13_fix_with_bad_toml_scalar_exits_one(lattice_store: Store, tmp_path: Path) -> None:
    r = run_cli(report_argv(tmp_path / "report", "--fix", f"{lattice.X}=not a value"))
    assert_clean_refusal(r, 1)  # A refusal exits 1.


# ---------- I14: check exit codes ----------


def test_i14_check_fixture_passes(lattice_store: Store) -> None:
    # PF3: the lattice's runs share a salt, so the default is now the paired
    # test; these numbers are the unpaired test's, named.
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    r = run_cli(
        ["--store", str(LATTICE_ROOT), "check", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--method", "fisher_bh",
         "--fail-on", "higher"]
    )
    assert r.code == 0, r.text
    # check's first stdout line is "passed  ..." or "failed  ...".
    assert r.out.startswith("passed  ") and not r.out.startswith("failed"), r.out
    # PF4 (PF4.20): with tripped's kind unknown the counts read 22 lower, 0 higher, as the reference gives.
    assert fisher_reference_counts() == (22, 0)
    assert "tripped: 22 lower, 0 higher" in r.out, r.out
    assert "fisher_bh" in r.out and f"over {lattice.CELLS} tests" in r.out and "over 72 tests" in r.out, r.out


def test_i14_check_fail_on_any_fails_the_fixture(lattice_store: Store) -> None:
    r = run_cli(["--store", str(LATTICE_ROOT), "check", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--fail-on", "any"])
    assert_clean_refusal(r, 4)  # A failed check exits 4.
    assert r.out.startswith("failed  ") and not r.out.startswith("passed"), r.out


def test_i14_check_significantly_worse_cell_fails(tmp_path: Path) -> None:
    store = Store(tmp_path / "syn")
    write_run(store, "syn-a", salt="syn", fell_per_cell={1.0: 0, 2.0: 16})
    write_run(store, "syn-b", salt="syn", fell_per_cell={1.0: 32, 2.0: 16})
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    r = run_cli(
        ["--store", str(tmp_path / "syn"), "check", "syn-a", "syn-b", "--event", "fell", "--fail-on", "higher"]
    )
    assert_clean_refusal(r, 4)  # A failed check exits 4.
    assert r.out.startswith("failed  ") and not r.out.startswith("passed"), r.out
    # PF4 (PF4.20): with fell's kind unknown the count reads 0 lower, 1 higher (was 0 safer, 1 worse).
    assert "fell: 0 lower, 1 higher" in r.out, r.out
    assert "over 2 tests" in r.out, r.out


def test_i14_check_safer_direction_passes_by_default(tmp_path: Path) -> None:
    store = Store(tmp_path / "syn")
    write_run(store, "syn-a", salt="syn", fell_per_cell={1.0: 32, 2.0: 16})
    write_run(store, "syn-b", salt="syn", fell_per_cell={1.0: 0, 2.0: 16})
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    r = run_cli(
        ["--store", str(tmp_path / "syn"), "check", "syn-a", "syn-b", "--event", "fell", "--fail-on", "higher"]
    )
    assert r.code == 0, r.text
    assert r.out.startswith("passed  "), r.out  # The first line says passed.


# ---------- I15: inspect ----------


def violated_rows(mock_runs: MockRuns) -> pd.DataFrame:
    df = mock_runs.store.read(mock_runs.a)
    rows = df[df["outcome"] == "violated"].reset_index(drop=True)
    assert len(rows) > 0, "the mock agent produced no violated episodes on the quickstart grid"
    return rows


def inspect_argv(mock_runs: MockRuns, *extra: str) -> list[str]:
    return ["--store", str(mock_runs.root), "inspect", mock_runs.a, "--event", "violated", *extra]


def test_i15_inspect_prints_only_event_rows_in_sorted_order(mock_runs: MockRuns) -> None:
    rows = violated_rows(mock_runs)
    r = run_cli(inspect_argv(mock_runs))
    assert r.code == 0, r.text
    blocks, _ = inspect_blocks(r.out, set(rows["config_hash"]))
    assert len(blocks) == len(rows)
    for block, row in zip(blocks, rows.itertuples(index=False), strict=True):
        assert_block_is_row(block, row)
    keys = list(zip(rows["config_hash"], rows["replicate_index"], strict=True))
    assert keys == sorted(keys)


def test_i15_inspect_where_filters_to_the_cell_set(mock_runs: MockRuns) -> None:
    rows = violated_rows(mock_runs)
    rates = {cfg["tool_fail_rate"] for cfg in rows["config"]}
    assert 0.3 in rates, rates
    expected = rows[[cfg["tool_fail_rate"] == 0.3 for cfg in rows["config"]]].reset_index(drop=True)
    assert 0 < len(expected) < len(rows)
    r = run_cli(inspect_argv(mock_runs, "--where", "tool_fail_rate=0.3"))
    assert r.code == 0, r.text
    blocks, _ = inspect_blocks(r.out, set(rows["config_hash"]))
    assert len(blocks) == len(expected)
    for block, row in zip(blocks, expected.itertuples(index=False), strict=True):
        assert_block_is_row(block, row)


def test_i15_inspect_limit_prints_that_many(mock_runs: MockRuns) -> None:
    rows = violated_rows(mock_runs)
    assert len(rows) >= 2
    r = run_cli(inspect_argv(mock_runs, "--limit", "2"))
    assert r.code == 0, r.text
    blocks, _ = inspect_blocks(r.out, set(rows["config_hash"]))
    assert len(blocks) == 2
    for block, row in zip(blocks, rows.head(2).itertuples(index=False), strict=True):
        assert_block_is_row(block, row)


def test_i15_inspect_prints_one_trace_line_per_step(mock_runs: MockRuns) -> None:
    rows = violated_rows(mock_runs)
    r = run_cli(inspect_argv(mock_runs))
    assert r.code == 0, r.text
    blocks, _ = inspect_blocks(r.out, set(rows["config_hash"]))
    for block, row in zip(blocks, rows.itertuples(index=False), strict=True):
        assert row.meta["trace"]["schema"] == TRACE_SCHEMA
        assert_trace_lines(block, row)


def test_i15_snippet_round_trips_config_and_seed(mock_runs: MockRuns) -> None:
    rows = violated_rows(mock_runs)
    r = run_cli(inspect_argv(mock_runs, "--limit", "1"))
    assert r.code == 0, r.text
    blocks, snippet = inspect_blocks(r.out, set(rows["config_hash"]))
    assert len(blocks) == 1
    row = next(rows.itertuples(index=False))
    assert f"from {MOCK_MODULE} import rollout" in snippet, snippet
    assert "your_module" not in r.out, snippet
    calls = [m for line in snippet for m in [SNIPPET_CALL_RE.search(line)] if m]
    assert len(calls) == 1, snippet
    assert json.loads(calls[0].group(2)) == row.config
    assert int(calls[0].group(3)) == row.seed


def test_i15_snippet_matches_a_printed_row(mock_runs: MockRuns) -> None:
    rows = violated_rows(mock_runs)
    r = run_cli(inspect_argv(mock_runs))
    _, snippet = inspect_blocks(r.out, set(rows["config_hash"]))
    calls = [m for line in snippet for m in [SNIPPET_CALL_RE.search(line)] if m]
    assert len(calls) == 1, snippet
    printed = {(json.dumps(cfg, sort_keys=True), int(seed)) for cfg, seed in zip(rows["config"], rows["seed"], strict=True)}
    assert (json.dumps(json.loads(calls[0].group(2)), sort_keys=True), int(calls[0].group(3))) in printed


def test_i15_inspect_unknown_run_exits_one(mock_runs: MockRuns) -> None:
    r = run_cli(["--store", str(mock_runs.root), "inspect", "no-such-run", "--event", "violated"])
    assert_clean_refusal(r, 1)  # A refusal exits 1.


# ---------- I16: inspect on a run with no trace ----------


def test_i16_inspect_without_trace_prints_rows_and_no_step_lines(tmp_path: Path) -> None:
    store = Store(tmp_path / "syn")
    write_run(store, "no-trace", salt="syn", fell_per_cell={1.0: 5, 2.0: 0})
    df = store.read("no-trace")
    rows = df[df["outcome"] == "fell"].reset_index(drop=True)
    assert len(rows) == 5 and all("trace" not in meta for meta in rows["meta"])
    r = run_cli(["--store", str(tmp_path / "syn"), "inspect", "no-trace", "--event", "fell"])
    assert r.code == 0, r.text
    assert "Traceback" not in r.text and not r.err.strip()
    blocks, _ = inspect_blocks(r.out, set(rows["config_hash"]))
    assert len(blocks) == 5
    for block, row in zip(blocks, rows.itertuples(index=False), strict=True):
        assert_block_is_row(block, row)
        assert STEP_LINE_RE.match(STEP_LINE_SAMPLE), "STEP_LINE_RE matches nothing; a negative use below would be vacuous"
        assert not [line for line in block if STEP_LINE_RE.match(line)], block


# ---------- I17: runs ----------


def test_i17_runs_lists_every_run_sorted_with_nine_fields(mock_runs: MockRuns, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()  # E1
    empty = run_cli(["--store", str(tmp_path / "empty"), "runs"])
    assert empty.code == 0, empty.text
    # PF2: an empty store prints `ok  no runs in <store>` and a `next:` line,
    # both on stdout and nothing on stderr, where it used to print the header alone.
    assert not empty.err, empty.err
    assert len(empty.lines) == 2, empty.out
    assert empty.lines[0] == f"ok  no runs in {tmp_path / 'empty'}"
    assert empty.lines[1].lstrip().startswith("next:"), empty.out

    store = mock_runs.store
    expected = store.runs()
    assert len(expected) == 5
    r = run_cli(["--store", str(mock_runs.root), "runs"])
    assert r.code == 0, r.text
    # PF2: the verdict line, then a header with the columns #, name, id,
    # status, backend, target, rows, rows without an outcome, created (t_unit is no longer a
    # column). A name holds single spaces, so cells are split on runs of two or more spaces.
    assert r.lines[0] == f"ok  {len(expected)} runs in {mock_runs.root}"
    assert re.split(r"\s{2,}", r.lines[1].strip()) == [
        "#", "name", "id", "status", "backend", "target", "rows", "rows without an outcome",
        "created",
    ]
    assert len(r.lines) == 2 + len(expected)
    run_lines = r.lines[2:]
    manifests = {run_id: store.manifest(run_id) for run_id in expected}
    # PF2: newest first by created_at, where the old table was in id order.
    newest_first = sorted(expected, key=lambda run_id: manifests[run_id].created_at, reverse=True)
    # PF2: the computed name is the target id up to its first `/`, the UTC
    # date of created_at, then a letter in creation order among that target's runs that day.
    names: dict[str, str] = {}
    for run_id in sorted(expected, key=lambda run_id: manifests[run_id].created_at):
        stem = f"{manifests[run_id].target_id.split('/')[0]} {manifests[run_id].created_at[:10]}"
        letter = "abcdefghijklmnopqrstuvwxyz"[sum(n.startswith(stem + " ") for n in names.values())]
        names[run_id] = f"{stem} {letter}"
    for number, (line, run_id) in enumerate(zip(run_lines, newest_first, strict=True), start=1):
        fields = re.split(r"\s{2,}", line.rstrip())
        assert len(fields) == 9, line
        manifest = manifests[run_id]
        assert fields[0] == str(number)  # every mock run is complete, so every row is numbered
        assert fields[1] == names[run_id]
        assert fields[2] == run_id
        assert fields[3] == manifest.status
        assert fields[4] == manifest.backend
        assert fields[5] == manifest.target_id
        # Counts carry thousands separators in text (rule 10).
        assert fields[6] == f"{len(store.read(run_id)):,}"
        assert fields[7] == f"{store.tally(run_id).no_outcome:,}"
        assert fields[8] == f"{manifest.created_at[:19]}Z"
    assert [re.split(r"\s{2,}", line)[2] for line in run_lines] == newest_first
    assert newest_first[:3] == [mock_runs.c, mock_runs.b, mock_runs.a]


# ---------- I18: mock agent ----------


def quickstart_spec() -> SweepSpec:
    return SweepSpec.load(QUICKSTART)


def test_i18_quickstart_toml_shape() -> None:
    spec = quickstart_spec()
    assert len(spec.configs) == QUICKSTART_CELLS
    assert spec.replicates == QUICKSTART_REPLICATES
    assert spec.target_id == QUICKSTART_TARGET_ID
    assert spec.t_unit == QUICKSTART_T_UNIT
    assert dict(spec.axis_types) == {"task_id": "categorical", "tool_fail_rate": "continuous"}
    assert len({cfg["task_id"] for cfg in spec.configs}) == 3
    assert len({cfg["tool_fail_rate"] for cfg in spec.configs}) == 3


def test_i18_rollout_is_deterministic_in_cfg_and_seed() -> None:
    agent = mock_agent()
    for cfg in quickstart_spec().configs:
        for seed in (0, 7, 123456789):
            first, second = agent.rollout(dict(cfg), seed), agent.rollout(dict(cfg), seed)
            assert (first.outcome, first.t) == (second.outcome, second.t)
            patched_first, patched_second = agent.rollout_patched(dict(cfg), seed), agent.rollout_patched(dict(cfg), seed)
            assert (patched_first.outcome, patched_first.t) == (patched_second.outcome, patched_second.t)


def test_i18_episode_shape_and_trace() -> None:
    agent = mock_agent()
    for cfg in quickstart_spec().configs:
        for seed in range(QUICKSTART_REPLICATES):
            for fn in (agent.rollout, agent.rollout_patched):
                ep = fn(dict(cfg), seed)
                assert isinstance(ep, Episode)
                assert ep.outcome in {"completed", "violated", "timeout"}, ep.outcome
                assert ep.horizon == MOCK_HORIZON
                assert float(ep.t).is_integer() and 0 <= ep.t <= MOCK_HORIZON
                trace = ep.meta["trace"]
                assert trace["schema"] == TRACE_SCHEMA
                assert len(trace["spans"]) == int(ep.t)
                for step in trace["spans"]:
                    assert set(step) == {
                        "span_id", "parent_id", "kind", "name", "start_ns", "end_ns",
                        "input", "output", "tokens", "confidence", "error", "code", "attrs",
                        # A8a: the eight verdict fields
                        "operation", "step_name", "outcome", "outcome_by", "attempt", "gate", "truncated", "bytes_original",
                    }, step


def test_i18_patched_violates_less_in_every_cell_and_strictly_in_half() -> None:
    agent = mock_agent()
    cells = quickstart_spec().configs
    strictly_lower = 0
    for cfg in cells:
        base = sum(agent.rollout(dict(cfg), s).outcome == "violated" for s in range(QUICKSTART_REPLICATES))
        patched = sum(agent.rollout_patched(dict(cfg), s).outcome == "violated" for s in range(QUICKSTART_REPLICATES))
        assert patched <= base, (cfg, base, patched)
        strictly_lower += patched < base
    assert strictly_lower * 2 >= len(cells), strictly_lower


def test_i18_violations_rise_with_fail_rate_and_vanish_at_zero() -> None:
    agent = mock_agent()
    by_rate: dict[float, int] = {}
    for cfg in quickstart_spec().configs:
        count = sum(agent.rollout(dict(cfg), s).outcome == "violated" for s in range(QUICKSTART_REPLICATES))
        by_rate[cfg["tool_fail_rate"]] = by_rate.get(cfg["tool_fail_rate"], 0) + count
    if 0.0 in by_rate:
        assert by_rate[0.0] == 0, by_rate
    assert by_rate[max(by_rate)] > 0, by_rate


# ---------- I19: mock agent touches no network ----------


def test_i19_socket_is_never_touched(monkeypatch: pytest.MonkeyPatch) -> None:
    def tripwire(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the mock agent touched the network")

    for name in ("socket", "create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, tripwire)
    agent = mock_agent()
    for cfg in quickstart_spec().configs:
        agent.rollout(dict(cfg), 1)
        agent.rollout_patched(dict(cfg), 1)


# ---------- I20: quickstart golden ----------


def test_i20_quickstart_three_commands_under_thirty_seconds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.chdir(tmp_path)
    t0 = time.perf_counter()
    store_root = tmp_path / "prove-runs"
    first = run_cli(["sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--yes"])
    assert first.code == 0 and first.lines, first.text
    run_a = new_run_id(store_root, [])
    second = run_cli(["sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", PATCHED, "--pair-with", run_a, "--yes"])
    assert second.code == 0 and second.lines, second.text
    run_b = new_run_id(store_root, [run_a])
    third = run_cli(["report", run_a, run_b, "--event", "violated", "--x", "tool_fail_rate", "--y", "task_id"])
    assert third.code == 0, third.text
    elapsed = time.perf_counter() - t0
    assert elapsed < QUICKSTART_BUDGET_S, elapsed

    (out,) = [p for p in tmp_path.iterdir() if p.name.startswith("prove-report-")]
    assert re.fullmatch(r"prove-report-.+-vs-.+", out.name) and out.is_dir(), sorted(p.name for p in tmp_path.iterdir())
    assert {p.name for p in out.iterdir()} == REPORT_FILES
    md = (out / "report.md").read_text()
    # violated's kind is unknown, so the headline counts read lower/higher, and the one event
    # given draws one panel.
    assert re.search(r"^violated: \d+ lower, \d+ higher$", md, re.MULTILINE), md
    heatmap = ET.fromstring((out / "heatmap.svg").read_text())
    assert [e.attrib["data-panel"] for e in heatmap.iter() if "data-panel" in e.attrib] == ["violated"]
    # PF4 (PF4.20): the quickstart runs declare no kind for violated, so the panel counts read in
    # direction words: none rose and at least one fell (were "0 worse" and "at least one safer").
    panel = re.search(r"^## violated: (\d+) lower, (\d+) higher$", md, re.MULTILINE)
    assert panel, md
    lower, higher = int(panel.group(1)), int(panel.group(2))
    assert higher == 0 and lower >= 1, panel.group(0)
    tail = re.search(r"over (\d+) tests, (paired|unpaired)\)", md)
    assert tail, md
    assert int(tail.group(1)) == QUICKSTART_CELLS
    # The second sweep is --pair-with the first, so the two share a salt and the default
    # method is mcnemar_bh; the token states that request.
    assert tail.group(2) == "paired"
    assert "mcnemar_bh" in md, md
    assert Store(tmp_path / "prove-runs").runs() == sorted([run_a, run_b])


# ---------- entrypoint smoke (subprocess) ----------


@pytest.mark.skipif(
    shutil.which("poisson-prove") is None,
    reason="needs the installed `poisson-prove` console script on PATH (pip install -e .); "
    "the same environment dependency as S0's entrypoint test",
)
def test_entrypoint_help_via_subprocess() -> None:
    r = subprocess.run(["poisson-prove", "--help"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for verb in VERBS:
        assert verb in r.stdout, verb
