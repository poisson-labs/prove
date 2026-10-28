"""A10 frozen tests: invariants P10-1 to P10-22, declared expectations.

Every name A10 adds is imported inside the test that needs it (or inside a helper a test calls), so
a missing name fails test by test and never at collection.

**What A10 buys.** A run says in advance which steps it expects to execute, which outcome labels its
target can emit, and which of its steps are gates; the manifest records that declaration; a span
whose step is a declared gate is stamped ``gate="declared"`` on its way to the store; and ``report``
and ``inspect`` print ``never reached`` against the declaration, never against the absence of a span.

**Three behaviours this file settles.**
1. Unmatched declared steps or gates print in full under ``never_reached`` and are never refused in
   A10. P10-15 pins it; the refusal is
   A9's, once ``CaptureCheck`` can tell capture-off from unreached.
2. ``finalize``'s guard is P10-9's: ``declaration`` and ``limit`` are keyword-only with no default,
   and anything that is not a ``Declaration`` is refused. Source-file byte digests do not govern it.
3. The pairing check is unchanged. ``DeclaredSetMismatch`` is raised in ``diff`` just before the
   pairing check, not inside it. P10-6 pins what a caller sees of that: the refusal wins over
   ``UnitMismatch`` and ``NotPairable``, and fires after frame validation. Because
   ``DIFF_MODULE_NAMES`` is exact, the check adds no module-level helper: it sits in ``diff()``
   and ``multi_diff()`` themselves.

**Conventions these frozen tests fix:**
- ``Declaration`` refuses a malformed value with ``ValueError`` (``TraceValidationError`` qualifies);
  the sampler refuses the same shapes with ``SamplerError`` naming the field and, where there is one,
  the offending value. An all-empty table's message carries the words ``[declare] declares
  nothing``. ``Declaration.from_dict`` reads an absent list as empty.
- The eight provenance keys come from ``DeclarationCheck.provenance()``, in the provenance table's order,
  as sorted lists. On a two-run report each declaring side contributes its eight with the ``_a`` /
  ``_b`` suffix, in table order within the side; a side that declared nothing contributes no key
  (per run: "the report says one side declared" by carrying only that side's keys). Removing the
  eight leaves exactly the provenance built with no declaration, order included.
- The builders' new keyword is ``declarations``: a pair for ``build_report`` and
  ``build_multi_report``, one ``DeclarationCheck | None`` for ``build_survival_report``.
- ``inspect`` prints the eight before the first ``config_hash:`` line, once, in table order, each in
  the provenance renderer's own line form (``- never reached: search``; ``none`` when empty).
- The diff refusal reaches the CLI as a refusal: exit 2, ``error: ...`` on stderr, on ``diff``,
  ``check``, ``report`` and ``serve``, and no report file is written.
- The resume refusal names the run id and every member that differs between the two declarations
  (every member of the declaring side when the other declares nothing), as data, not as wording.
- ``poisson_prove.paired`` already defines an unrelated ``Declaration`` (``tests/test_pr1_pair_assertion.py``)
  and ``cli.py`` imports it by that name. P10-8 pins A10's class by module (``poisson_prove.trace``); the
  two never meet.

**The fixtures.** The main pair is two real local runs of ``main_rollout`` through the
recorder under one salt, declaring steps ``plan, review, search, verify``, outcomes ``fell,
survived`` and gates ``review, search, verify`` (written unsorted in the file). ``plan`` is reached;
``search`` never; ``verify`` only un-gated (the stamp alone gates it); ``review`` only as
``"emitted"`` (the stamp must leave it, and a ``gate == "declared"`` reading calls it unreached);
``retry`` and ``check`` are undeclared steps; ``check`` is an emitted gate the declaration does not
name; ``guard`` is an emitted marker with no step name; ``timed_out`` is an undeclared outcome on a
row with no trace; one config raises, so one row's outcome is null. Beside it: the same pair with no
``[declare]`` (``bare_pair``); a declaration that stamps nothing (``unmatched_runs``, hand-built and
byte-deterministic, with its non-declaring twin); capture off for the whole run with zero spans
(``silent_runs``, with its twin); a Modal-shaped store through ``run_with_mapper`` and the real
``worker_batch`` (``modal_run``); a declared gate over the cut in a child process
(``test_p10_10bc_*``); resumed runs; hand-built pairs for the diff refusal; three invalid traces
under a declaration (P10-22).

**Invariant-to-test map:**

| Invariant | Tests |
|---|---|
| P10-1 | ``test_p10_1_*`` (6 functions, 19 ids) |
| P10-2 | ``test_p10_2_*`` (4 functions, 4 ids) |
| P10-3 | ``test_p10_3_*`` (3 functions, 3 ids) |
| P10-4 | ``test_p10_4_*`` (3 functions, 3 ids) |
| P10-5 | ``test_p10_5_*`` (2 functions, 2 ids) |
| P10-6 | ``test_p10_6_*`` (5 functions, 19 ids) |
| P10-7 | ``test_p10_7_*`` (1 function, 1 id) |
| P10-8 | ``test_p10_8_*`` (2 functions, 2 ids) |
| P10-9 | ``test_p10_9_*`` (2 functions, 5 ids) |
| P10-10 | ``test_p10_10a_*``, ``test_p10_10b_*``, ``test_p10_10c_*``, ``test_p10_10bc_*`` (5 functions, 5 ids) |
| P10-11 | ``test_p10_11_*`` (4 functions, 4 ids) |
| P10-12 | ``test_p10_12_*`` (2 functions, 6 ids) |
| P10-13 | ``test_p10_13_*`` (1 function, 1 id) |
| P10-14 | ``test_p10_14_*`` (2 functions, 2 ids) |
| P10-15 | ``test_p10_15_*`` (1 function, 1 id) |
| P10-16 | ``test_p10_16_*`` (2 functions, 2 ids) |
| P10-17 | ``test_p10_17_*`` (2 functions, 2 ids) |
| P10-19 | ``test_p10_19_*`` (2 functions, 2 ids) |
| P10-20 | ``test_p10_20_*`` (1 function, 1 id) |
| P10-22 | ``test_p10_22_*`` (1 function, 1 id) |

**pandas versions.** No A10 invariant is expected to depend on the pandas major version: A10 adds
no Parquet column and no read mode. The one place a genuine split would appear is P10-14's
``observed_outcomes`` clause (``test_p10_14_observed_outcomes_are_strings_with_a_null_outcome_in_the_frame``):
``outcome`` is a nullable ``pa.string()`` column, and a null that read back as ``NaN`` under pandas 3
would enter the set as a float. It is green by construction while the store reads a null
``outcome`` back as ``None``, and is named so a later reader knows why. Nullness everywhere here
is ``is None``, as in A8a.

**A test that stays green by design.**
``test_p10_2_no_verb_on_a_pair_that_declares_nothing_prints_any_of_the_eight`` (no change for a pair
that declares nothing, on the non-declaring pair and on the generated lattice pair,
``tests/lattice.py``; it fails only if a verb prints one of the eight for such a pair). Every verb on a pre-A7 pair is A7's P7-10
(``test_a7_storage.py``);
``viewer.py`` and ``tree.py`` byte identity (P10-13's whole-file clause) is FR17's and CD9's. Neither is
restated here, so this file adds no output-digest or source-digest carrier.

**Named gaps.** (1) P10-2's byte identity on the **mock quickstart pair**: its runs are regenerated
per test with fresh run ids and timings, so no digest of them is stable across test runs; this file pins
instead that no verb on a non-declaring pair prints any of the eight. (2) P10-10 (a) at the store:
``Store.append`` re-reads every trace through ``Trace.from_dict`` and ``split`` before writing, so a
rebuilt-but-equal trace stores the same bytes and the stored-bytes clause cannot catch a stamp that
rebuilds an unchanged trace; the ``is`` clause is the only observable, and the stored clause is kept
because it states the same claim at the store.
(3) Commutation (P10-10 (c)) cannot tell the two orders apart, by design: no field is written by both.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import lattice
import poisson_prove
import poisson_prove.trace as trace_module
from poisson_prove import cli
from poisson_prove.diff import DiffError, NotPairable, UnitMismatch, diff, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.executor import NotResumable, plan, run_local
from poisson_prove.executor_modal import ModalOptions, run_with_mapper, worker_batch
from poisson_prove.report import ReportSpec, build_multi_report, build_report, build_survival_report
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.survival import cell_table, censor, competing_set
from poisson_prove.trace import Span, Trace, collect, finalize, record, truncate_observations
from isolated_support import isolated as run_isolated

MODULE = __name__
PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parent.parent

#: Every pair here shares a salt and a seed per row, so the unpaired methods warn; the warning is not
#: this file's subject, and P10-15 records warnings itself where it matters.
pytestmark = pytest.mark.filterwarnings("ignore::poisson_prove.diff.UnpairedAnalysis")

TARGET = "a10-test@v0"
T_UNIT = "steps"
RUN_SALT = "a10-test-salt"
OTHER_SALT = "a10-test-other-salt"
HORIZON = 10.0
EPOCH = 1_756_900_000_000_000_000
X_VALUES = (0.1, 0.2, 0.3, 0.4)
REPLICATES = 2
EVENT = "fell"

#: The declaration every declaring fixture carries, written **unsorted** in the sweep file so that
#: sorting at parse is exercised on every run, not only in P10-1.
DECLARE_TOML: dict[str, list[str]] = {
    "steps": ["verify", "plan", "search", "review"],
    "outcomes": ["survived", "fell"],
    "gates": ["verify", "search", "review"],
}
STEPS = ("plan", "review", "search", "verify")
OUTCOMES = ("fell", "survived")
GATES = ("review", "search", "verify")

#: The eight provenance keys, in the table's order.
EIGHT_KEYS = (
    "declared_steps", "never_reached", "undeclared_steps", "declared_outcomes",
    "undeclared_outcomes", "declared_gates", "gates_never_reached", "emitted_gates_not_declared",
)
#: ``DeclarationCheck``'s fields, in the order the dataclass declares them.
CHECK_FIELDS = (
    "declared_steps", "observed_steps", "never_reached", "undeclared_steps", "declared_outcomes",
    "observed_outcomes", "undeclared_outcomes", "declared_gates", "emitted_gates",
    "emitted_not_declared", "declared_never_reached",
)
#: ``RunManifest.to_dict()``'s twelve keys before A10 added ``declared`` (``store.py``'s manifest,
#: and a 0.0.1 manifest's twelve, such as the lattice pair's, with ``proofload_version`` in that slot).
TWELVE = frozenset({
    "run_id", "target_id", "t_unit", "run_salt", "axis_types", "backend", "environment",
    "retain_traces_for", "status", "created_at", "poisson_prove_version", "schema_version",
})
#: What ``declaration_check`` must find on the main declaring run (the main fixture). Every
#: set here can disagree with the invariant that reads it: one declared step reached (``plan``), one
#: declared step and gate never reached (``search``), one declared gate reached only un-gated
#: (``verify``, so only the stamp can gate it), one declared gate reached only as ``"emitted"``
#: (``review``, which the stamp must leave alone and which a reading of ``gate == "declared"`` would
#: call never reached, a known trap), two undeclared steps (``retry``, ``check``), one emitted
#: gate the declaration does not name (``check``), one emitted marker with no step name
#: (``guard``), one undeclared outcome on a row with no trace (``timed_out``), and one errored row
#: whose outcome is null.
MAIN_EXPECTED: dict[str, frozenset[str]] = {
    "declared_steps": frozenset({"plan", "review", "search", "verify"}),
    "observed_steps": frozenset({"plan", "verify", "retry", "check", "review"}),
    "never_reached": frozenset({"search"}),
    "undeclared_steps": frozenset({"retry", "check"}),
    "declared_outcomes": frozenset({"fell", "survived"}),
    "observed_outcomes": frozenset({"fell", "survived", "timed_out"}),
    "undeclared_outcomes": frozenset({"timed_out"}),
    "declared_gates": frozenset({"review", "search", "verify"}),
    "emitted_gates": frozenset({"check", "review"}),
    "emitted_not_declared": frozenset({"check"}),
    "declared_never_reached": frozenset({"search"}),
}
#: The main run's eight provenance values, as ``inspect`` and the report print them.
MAIN_LINES = {
    "declared_steps": "plan, review, search, verify", "never_reached": "search",
    "undeclared_steps": "check, retry", "declared_outcomes": "fell, survived",
    "undeclared_outcomes": "timed_out", "declared_gates": "review, search, verify",
    "gates_never_reached": "search", "emitted_gates_not_declared": "check",
}


# ---------- helpers: data construction, never an assertion ----------


class RootedStore(Store):
    """A ``Store`` that keeps the folder this file made it on, so the raw-part helpers and the CLI
    calls read the path the test chose."""

    def __init__(self, root: Path | str) -> None:
        super().__init__(root)
        self.root = Path(root)


def declaration(steps: Sequence[str] = STEPS, outcomes: Sequence[str] = OUTCOMES, gates: Sequence[str] = GATES) -> Any:
    from poisson_prove.trace import Declaration

    return Declaration(steps=tuple(steps), outcomes=tuple(outcomes), gates=tuple(gates))


def toml_value(value: Any) -> str:
    return json.dumps(value)


def sweep_toml(
    declare: Mapping[str, Any] | None,
    *,
    values: Sequence[float] = X_VALUES,
    replicates: int = REPLICATES,
    capture: Mapping[str, Any] | None = None,
    raw: str | None = None,
) -> str:
    """A sweep file. ``declare`` is written verbatim as a ``[declare]`` table (``None``: no table);
    ``raw`` is appended as written, for the shapes a mapping cannot express."""
    lines = [
        f'target_id = "{TARGET}"', f't_unit = "{T_UNIT}"', f"replicates = {replicates}", "",
        "[axes.x]", 'type = "continuous"', f"values = {json.dumps(list(values))}", "",
    ]
    if capture is not None:
        lines.append("[capture]")
        lines += [f"{key} = {toml_value(value)}" for key, value in capture.items()]
        lines.append("")
    if declare is not None:
        lines.append("[declare]")
        lines += [f"{key} = {toml_value(value)}" for key, value in declare.items()]
        lines.append("")
    if raw is not None:
        lines.append(raw)
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def span(i: int, *, step: str | None = None, gate: str | None = None, output: Any = None) -> Span:
    return Span(
        span_id=f"{i:016x}", parent_id=None, kind="tool", name=f"span-{i}",
        start_ns=EPOCH + i * 1_000_000, end_ns=EPOCH + i * 1_000_000 + 500_000,
        output=output, step_name=step, gate=gate,
    )


def trace_of(*spans: Span) -> Trace:
    return Trace(spans=tuple(spans), source="record")


def canonical(trace: Trace) -> str:
    return json.dumps(trace.to_dict(), sort_keys=True)


def label(key: str) -> str:
    """A provenance key as the report's provenance list prints it."""
    return key.replace("_", " ")


def provenance_section(markdown: str) -> tuple[list[str], list[str]]:
    """``report.md``'s ``## Provenance`` section, and every other line."""
    lines = markdown.splitlines()
    start = lines.index("## Provenance")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end], lines[:start] + lines[end:]


def any_label(text: str) -> list[str]:
    """Every rendered form of the eight keys found in ``text`` -- the words and the raw keys."""
    return [k for k in EIGHT_KEYS if label(k) in text or k in text]


def stored_spans(store: Store, run_id: str) -> list[Mapping[str, Any]]:
    """Every span of every stored envelope, as a mapping (the envelope read)."""
    frame = store.read(run_id, meta=False, trace="envelope")
    return [
        s
        for envelope in frame["trace"]
        if isinstance(envelope, Mapping)
        for s in envelope.get("spans", ())
        if isinstance(s, Mapping)
    ]


def gated_step_names(store: Store, run_id: str) -> set[str]:
    """P10-19's second side: step names carrying a non-``None`` ``gate`` on some stored span."""
    return {s["step_name"] for s in stored_spans(store, run_id) if s.get("step_name") is not None and s.get("gate") is not None}


def check_of(store: Store, run_id: str) -> Any:
    from poisson_prove.steps import declaration_check

    return declaration_check(store.manifest(run_id), store.read(run_id, meta=False, trace="envelope"))


def raw_column(store: RootedStore, run_id: str, column: str) -> list[Any]:
    """One stored column exactly as written, read raw through ``pyarrow`` (a null is ``None``)."""
    values: list[Any] = []
    for part in sorted((store.root / run_id / "episodes").glob("part-*.parquet")):
        values += pq.read_table(part, columns=[column]).column(column).to_pylist()
    return values


def keyed_raw(store: RootedStore, run_id: str, column: str) -> dict[tuple[str, int], Any]:
    out: dict[tuple[str, int], Any] = {}
    for part in sorted((store.root / run_id / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part, columns=["config_hash", "replicate_index", column])
        for h, k, v in zip(*(table.column(c).to_pylist() for c in ("config_hash", "replicate_index", column)), strict=True):
            out[(str(h), int(k))] = v
    return out


def snapshot(root: Path) -> dict[str, tuple[int, str]]:
    return {
        str(p.relative_to(root)): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ---------- rollouts (module-level: resolved by import path on the Modal path) ----------


def main_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The main fixture, through the recorder."""
    x = round(float(cfg["x"]), 1)
    if x == 0.4:
        raise RuntimeError("the fourth config always fails: an errored row, outcome null")
    if x == 0.3:
        return Episode(outcome="timed_out", t=5.0, horizon=HORIZON, meta={})
    with collect() as c:
        with record("agent", "plan", step_name="plan"):
            pass
        if x == 0.1:
            with record("tool", "verify", step_name="verify"):
                pass
            with record("tool", "retry", step_name="retry"):
                pass
        else:
            with record("tool", "check", step_name="check", gate="emitted"):
                pass
            with record("tool", "review", step_name="review", gate="emitted"):
                pass
            with record("tool", "guard", gate="emitted"):
                pass
    outcome, t = ("survived", HORIZON) if x == 0.1 else ("fell", 3.0)
    return Episode(outcome=outcome, t=t, horizon=HORIZON, meta={"trace": c.trace.to_dict()})


def unmatched_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The unmatched fixture: a hand-built trace whose step names are all undeclared, so a
    declaration stamps nothing. Byte-deterministic, so two runs can be compared byte for byte."""
    x = round(float(cfg["x"]), 1)
    own = trace_of(span(1, step="alpha"), span(2, step="beta", gate="emitted"), span(3))
    fell = x >= 0.3
    return Episode(outcome="fell" if fell else "survived", t=3.0 if fell else HORIZON, horizon=HORIZON, meta={"trace": own.to_dict()})


def silent_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Capture off for the whole run and no trace of its own: zero spans on every row."""
    fell = round(float(cfg["x"]), 1) >= 0.3
    return Episode(outcome="fell" if fell else "survived", t=3.0 if fell else HORIZON, horizon=HORIZON, meta={})


def cut_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The cut fixture: one span that is both a declared gate and over the cut."""
    own = trace_of(span(1, step="verify", output="v" * 300), span(2, step="plan", output="p" * 8))
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={"trace": own.to_dict()})


#: P10-22: three ``meta["trace"]`` values that are not a valid trace dict, one per config.
BAD_TRACES: dict[float, Any] = {
    0.1: "not a trace",
    0.2: ["a", "list"],
    0.3: {"schema": "poisson-prove.trace/1", "source": "record", "source_version": None, "dropped": 0},
}


def bad_trace_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={"trace": BAD_TRACES[round(float(cfg["x"]), 1)]})


def modal_mapper(batches: Sequence[Sequence[Any]]) -> Iterator[tuple[int, list[Any]]]:
    """The container's code run in-process, in submission order: ``worker_batch`` is what a Modal
    container runs, and the host stores what it returns."""
    for index, jobs in enumerate(batches):
        yield index, worker_batch(jobs, f"{MODULE}:main_rollout", None)


def local_run(root: Path, text: str, rollout: Callable[..., Episode], *, salt: str = RUN_SALT, name: str = "sweep", **kwargs: Any) -> tuple[RootedStore, str]:
    """One real local run from a real sweep file into ``root/store``."""
    path = write(root / f"{name}.toml", text)
    store = RootedStore(root / "store")
    p = plan(SweepSpec.load(path), store, run_salt=salt, import_path=f"{MODULE}:{rollout.__name__}")
    run_local(p, rollout, store, **kwargs)
    return store, str(p.run_id)


def manifest(run_id: str, *, declared: Any = None, t_unit: str = T_UNIT, salt: str = RUN_SALT, with_field: bool = True) -> RunManifest:
    kwargs: dict[str, Any] = dict(
        run_id=run_id, target_id=TARGET, t_unit=t_unit, run_salt=salt,
        axis_types={"x": "continuous"}, backend="local", environment={"note": "built by these tests"},
    )
    if with_field:
        kwargs["declared"] = declared
    return RunManifest(**kwargs)


def rows(run_id: str, outcomes: Mapping[float, str]) -> list[EpisodeRecord]:
    """Two replicates per config, the same seeds in every run, so any two runs built here pair."""
    out: list[EpisodeRecord] = []
    for x, outcome in outcomes.items():
        for k in range(REPLICATES):
            t = HORIZON if outcome == "survived" else 3.0
            out.append(EpisodeRecord.from_episode(
                Episode(outcome=outcome, t=t, horizon=HORIZON, meta={}), run_id=run_id, config={"x": x},
                seed=1000 + 10 * k + int(x * 10), replicate_index=k, wall_time=0.0, backend_meta={"i": k},
            ))
    return out


PAIR_OUTCOMES = {0.1: "survived", 0.2: "fell", 0.3: "fell"}
PAIR_OUTCOMES_WIDER = {0.1: "survived", 0.2: "fell", 0.3: "timed_out"}


def pair_store(root: Path, ma: RunManifest, mb: RunManifest, *, b_outcomes: Mapping[float, str] = PAIR_OUTCOMES) -> RootedStore:
    store = RootedStore(root)
    for m, outcomes in ((ma, PAIR_OUTCOMES), (mb, b_outcomes)):
        store.create_run(m)
        store.append(m.run_id, rows(m.run_id, outcomes))
        store.mark_complete(m.run_id)
    return store


# ---------- module fixtures: the stored runs every section reads ----------


@pytest.fixture(scope="module")
def main_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[RootedStore, str, str]:
    """Two declaring runs of the main rollout under one salt, one store: a pairable pair."""
    root = tmp_path_factory.mktemp("a10-main")
    store, a = local_run(root, sweep_toml(DECLARE_TOML), main_rollout, name="a")
    _, b = local_run(root, sweep_toml(DECLARE_TOML), main_rollout, name="b")
    return store, a, b


@pytest.fixture(scope="module")
def bare_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[RootedStore, str, str]:
    """The same two runs with no ``[declare]`` table."""
    root = tmp_path_factory.mktemp("a10-bare")
    store, a = local_run(root, sweep_toml(None), main_rollout, name="a")
    _, b = local_run(root, sweep_toml(None), main_rollout, name="b")
    return store, a, b


@pytest.fixture(scope="module")
def unmatched_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[RootedStore, str, RootedStore, str]:
    """The unmatched fixture declaring, and the same rollout declaring nothing, one salt."""
    declaring, run_d = local_run(tmp_path_factory.mktemp("a10-unmatched-d"), sweep_toml(DECLARE_TOML), unmatched_rollout)
    plain, run_n = local_run(tmp_path_factory.mktemp("a10-unmatched-n"), sweep_toml(None), unmatched_rollout)
    return declaring, run_d, plain, run_n


@pytest.fixture(scope="module")
def silent_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[RootedStore, str, RootedStore, str]:
    """The silent fixture: ``[declare]`` present, no ``[capture]`` table, zero spans; and its
    non-declaring twin."""
    declaring, run_d = local_run(tmp_path_factory.mktemp("a10-silent-d"), sweep_toml(DECLARE_TOML), silent_rollout)
    plain, run_n = local_run(tmp_path_factory.mktemp("a10-silent-n"), sweep_toml(None), silent_rollout)
    return declaring, run_d, plain, run_n


@pytest.fixture(scope="module")
def modal_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[RootedStore, str]:
    """The Modal-shaped store, built through ``run_with_mapper``: the host stores what the
    container code returned, so a stamp is present on a stored row only if it ran host-side."""
    root = tmp_path_factory.mktemp("a10-modal")
    store = RootedStore(root / "store")
    p = plan(SweepSpec.load(write(root / "modal.toml", sweep_toml(DECLARE_TOML))), store, run_salt=RUN_SALT, backend="modal")
    run_with_mapper(p, modal_mapper, store, options=ModalOptions(batch_size=4, episode_timeout=None))
    return store, str(p.run_id)


# ---------- P10-1: [declare] parses, sorted; every malformed shape is refused at parse ----------


def test_p10_1_declare_parses_to_a_sorted_declaration_minted_in_trace(tmp_path: Path) -> None:
    """The lists are sorted at construction, so the unsorted spelling in
    the file reads back sorted; and the object is ``poisson_prove.trace.Declaration``."""
    from poisson_prove.trace import Declaration

    spec = SweepSpec.load(write(tmp_path / "s.toml", sweep_toml(DECLARE_TOML)))
    assert type(spec.declare) is Declaration
    assert (spec.declare.steps, spec.declare.outcomes, spec.declare.gates) == (STEPS, OUTCOMES, GATES)
    assert spec.declare == declaration()
    assert SweepSpec.load(write(tmp_path / "none.toml", sweep_toml(None))).declare is None


@pytest.mark.parametrize(
    ("case", "bad", "good", "names"),
    [
        ("gate-outside-steps", {**DECLARE_TOML, "gates": ["verify", "deploy"]}, DECLARE_TOML, ("gates", "deploy")),
        ("non-string-entry", {**DECLARE_TOML, "steps": ["plan", 3, "search", "verify"]}, DECLARE_TOML, ("steps", "3")),
        ("empty-string", {**DECLARE_TOML, "outcomes": ["fell", ""]}, DECLARE_TOML, ("outcomes",)),
        ("duplicate-step", {**DECLARE_TOML, "steps": ["plan", "plan", "search", "verify"]}, DECLARE_TOML, ("steps", "plan")),
        ("duplicate-outcome", {**DECLARE_TOML, "outcomes": ["fell", "survived", "fell"]}, DECLARE_TOML, ("outcomes", "fell")),
        ("duplicate-gate", {**DECLARE_TOML, "gates": ["verify", "verify"]}, DECLARE_TOML, ("gates", "verify")),
        # PF3 (PF3.3): strict specs refuse the unknown key when the spec is read, before [declare]'s
        # own check, naming the key, its table and the nearest known key rather than every field.
        ("unknown-field", {**DECLARE_TOML, "stages": ["plan"]}, DECLARE_TOML, ('"stages"', "[declare]", '"steps"')),
        ("not-a-list", {**DECLARE_TOML, "steps": "plan"}, DECLARE_TOML, ("steps",)),
        ("three-empty-lists", {"steps": [], "outcomes": [], "gates": []}, {"steps": [], "outcomes": ["fell"], "gates": []}, ()),
        ("empty-table", {}, {"outcomes": ["fell"]}, ()),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_p10_1_a_malformed_declare_table_is_refused_naming_the_field_and_the_value(
    tmp_path: Path, case: str, bad: dict[str, Any], good: dict[str, Any], names: tuple[str, ...]
) -> None:
    """The five validation rules, each with a control document that differs only in the clause under
    test and is accepted (a refusal is not pinned on a word alone). A duplicate is refused, never
    collapsed: A6's de-duplication is gone."""
    control = SweepSpec.load(write(tmp_path / "good.toml", sweep_toml(good)))
    assert control.declare is not None
    with pytest.raises(SamplerError) as excinfo:
        SweepSpec.load(write(tmp_path / "bad.toml", sweep_toml(bad)))
    message = str(excinfo.value)
    for name in names:
        assert name in message, (case, name, message)
    if case in ("three-empty-lists", "empty-table"):
        assert "[declare] declares nothing" in message, message


def test_p10_1_declare_must_be_a_table(tmp_path: Path) -> None:
    """Rule 1's first clause: a top-level ``declare`` that is not a table is refused, not ignored."""
    text = sweep_toml(None).replace('t_unit = "steps"', 't_unit = "steps"\ndeclare = ["plan"]')
    with pytest.raises(SamplerError) as excinfo:
        SweepSpec.load(write(tmp_path / "s.toml", text))
    assert "declare" in str(excinfo.value), str(excinfo.value)


def test_p10_1_the_cli_refuses_a_malformed_table_before_the_run_exists(tmp_path: Path) -> None:
    """Refused at sweep-file parse, and "before the run exists" is a
    claim about the filesystem, so it is measured there."""
    # PF4.49: the control is a 2-replicate design, which no lone condition
    # can flag, so below 1 the gate refuses it; --max-mde 1 admits any design, where 0.5 admitted it
    # under the old normal approximation (which saturated at 0.5 for tiny designs).
    argv = ["sweep", "--target", f"{MODULE}:silent_rollout", "--yes", "--max-mde", "1"]
    good = write(tmp_path / "good.toml", sweep_toml(DECLARE_TOML))
    code, out, err = run_cli(["--store", str(tmp_path / "control"), argv[0], str(good), *argv[1:]])
    assert code == 0, (code, out, err)
    toml = write(tmp_path / "s.toml", sweep_toml({**DECLARE_TOML, "steps": ["plan", "plan", "search", "verify"]}))
    root = tmp_path / "store"
    code, out, err = run_cli(["--store", str(root), argv[0], str(toml), *argv[1:]])
    # A refusal exits 1.
    assert code == 1, (code, out, err)
    assert "steps" in err and "plan" in err, err
    assert not root.exists() or list(root.iterdir()) == [], sorted(p.name for p in root.iterdir())


@pytest.mark.parametrize(
    ("case", "kwargs"),
    [
        ("gate-outside-steps", {"steps": ("plan",), "gates": ("verify",)}),
        ("duplicate", {"steps": ("plan", "plan")}),
        ("empty-string", {"outcomes": ("",)}),
        ("non-string", {"steps": ("plan", 3)}),
        ("all-empty", {}),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_p10_1_declaration_validates_at_construction_and_from_dict_does_too(case: str, kwargs: dict[str, Any]) -> None:
    """``Declaration`` validates at construction (the ``Span`` posture), so a declaration
    read back from a manifest is held to the rules that refused the sweep file."""
    from poisson_prove.trace import Declaration

    assert Declaration(steps=("plan",)).steps == ("plan",)
    with pytest.raises(ValueError):
        Declaration(**kwargs)
    with pytest.raises(ValueError):
        Declaration.from_dict({key: list(value) for key, value in kwargs.items()})


def test_p10_1_declaration_sorts_serialises_and_reads_an_absent_list_as_empty() -> None:
    """Plain sorted lists out, sorted tuples in, and an absent key is an empty list."""
    from poisson_prove.trace import Declaration

    d = Declaration(steps=("verify", "plan", "search", "review"), outcomes=("survived", "fell"), gates=("verify", "search", "review"))
    assert (d.steps, d.outcomes, d.gates) == (STEPS, OUTCOMES, GATES)
    assert d.to_dict() == {"steps": list(STEPS), "outcomes": list(OUTCOMES), "gates": list(GATES)}
    assert all(type(v) is list for v in d.to_dict().values())
    assert Declaration.from_dict(d.to_dict()) == d
    assert Declaration.from_dict({"outcomes": ["survived", "fell"]}) == Declaration(outcomes=OUTCOMES)
    assert Declaration.from_dict({"outcomes": ["fell"]}).steps == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.steps = ()  # type: ignore[misc]


# ---------- P10-2: no declaration, no key, no line, no byte ----------


def test_p10_2_declaration_check_is_none_for_a_run_that_declares_nothing(bare_pair: tuple[RootedStore, str, str]) -> None:
    store, a, _ = bare_pair
    assert store.manifest(a).declared is None
    assert check_of(store, a) is None


def test_p10_2_the_builders_add_no_key_when_no_run_declares(bare_pair: tuple[RootedStore, str, str]) -> None:
    """Sole catch for builders that add the keys unconditionally. Given no declaration, every builder's provenance
    is the provenance it builds with the keyword absent: none of the eight keys, plain or suffixed,
    and absent -- not ``None``, not ``[]``. Order included, because the renderer walks the dict."""
    store, a, b = bare_pair
    ma, mb = store.manifest(a), store.manifest(b)
    fa, fb = store.read(a), store.read(b)
    spec = ReportSpec(title="a10", x_axis="x")
    multi = multi_diff(fa, fb, events=[EVENT], manifest_a=ma, manifest_b=mb)
    single = diff(censor(fa, EVENT), censor(fb, EVENT), event=EVENT, manifest_a=ma, manifest_b=mb)
    cells = cell_table(fa, EVENT, horizon=HORIZON, method="aj", events=list(competing_set(fa)))
    built = {
        "multi": (build_multi_report(multi, spec, manifests=(ma, mb)).provenance,
                  build_multi_report(multi, spec, manifests=(ma, mb), declarations=(None, None)).provenance),
        "single": (build_report(single, spec, manifests=(ma, mb)).provenance,
                   build_report(single, spec, manifests=(ma, mb), declarations=(None, None)).provenance),
        "survival": (build_survival_report(cells, spec, events=[EVENT], horizon=HORIZON, manifest=ma).provenance,
                     build_survival_report(cells, spec, events=[EVENT], horizon=HORIZON, manifest=ma, declarations=None).provenance),
    }
    for name, (without, given_none) in built.items():
        assert list(given_none.items()) == list(without.items()), name
        assert any_label(" ".join(given_none)) == [], (name, any_label(" ".join(given_none)))


def test_p10_2_one_declaring_side_adds_its_own_keys_and_none_for_the_other(main_pair: tuple[RootedStore, str, str], bare_pair: tuple[RootedStore, str, str]) -> None:
    """Per run, on a pair where only ``a`` declares: ``a``'s eight suffixed keys, and no ``_b`` key
    of any of the eight -- the report says one side declared by carrying only that side's."""
    from poisson_prove.steps import declaration_check

    store, a, _ = main_pair
    bstore, b, _ = bare_pair
    ma, mb = store.manifest(a), bstore.manifest(b)
    fa, fb = store.read(a), bstore.read(b)
    check_a = declaration_check(ma, store.read(a, meta=False, trace="envelope"))
    multi = multi_diff(fa, fb, events=[EVENT], manifest_a=ma, manifest_b=mb)
    prov = build_multi_report(multi, ReportSpec(title="a10", x_axis="x"), manifests=(ma, mb), declarations=(check_a, None)).provenance
    assert [k for k in prov if k.endswith("_a") and k[:-2] in EIGHT_KEYS] == [f"{k}_a" for k in EIGHT_KEYS]
    assert [k for k in prov if k.endswith("_b") and k[:-2] in EIGHT_KEYS] == []
    assert not any(k in EIGHT_KEYS for k in prov), list(prov)


def test_p10_2_no_verb_on_a_pair_that_declares_nothing_prints_any_of_the_eight(tmp_path: Path, bare_pair: tuple[RootedStore, str, str]) -> None:
    """Green by design: A6's narrower grep, widened to every verb,
    on the non-declaring twin of the main pair and on the generated lattice pair (``tests/lattice.py``,
    written before A10). Every verb on a pre-A7 pair is A7's P7-10 (``test_a7_storage.py``), which
    A10 must leave green."""
    store, a, b = bare_pair
    root = str(store.root)
    texts: list[str] = []
    for argv in (
        ["--store", root, "report", a, b, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "pair")],
        ["--store", root, "report", a, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "one")],
        ["--store", root, "inspect", a, "--event", EVENT],
        # PF4 (PF4.20): the bare pair declares no kind for the event, so the default --fail-on worse
        # is refused; --fail-on higher is the same gate on a failure event (fail when it rose).
        ["--store", root, "check", a, b, "--event", EVENT, "--fail-on", "higher"],
        ["--store", root, "runs"],
        ["--store", root, "diff", a, b, "--event", EVENT],
        # --json replaces --format json on diff.
        ["--store", root, "diff", a, b, "--event", EVENT, "--json"],
        ["--store", root, "serve", a, b, "--event", EVENT, "--x", "x", "--json"],
        ["--store", str(lattice.root()), "report", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--x", lattice.X, "--y", lattice.Y, "--out", str(tmp_path / "lattice")],
        ["--store", str(lattice.root()), "serve", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--x", lattice.X, "--y", lattice.Y, "--json"],
        ["--store", str(lattice.root()), "inspect", lattice.RUN_A, "--event", lattice.EVENT, "--limit", "1"],
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            code, out, err = run_cli(argv)
        # Done, or a check that did not pass, which exits 4 now.
        assert code in (0, 4), (argv, code, err)
        texts += [out, err]
    for d in ("pair", "one", "lattice"):
        texts += [(tmp_path / d / name).read_text() for name in ("report.md", "receipt.html")]
    for text in texts:
        assert any_label(text) == [], any_label(text)
        assert "never reached" not in text and "never_reached" not in text


# ---------- P10-3: never_reached is declared minus observed, exactly ----------


def test_p10_3_never_reached_and_undeclared_steps_are_set_differences(main_pair: tuple[RootedStore, str, str]) -> None:
    """On the main fixture: one declared step reached, one not, two observed undeclared."""
    store, a, _ = main_pair
    check = check_of(store, a)
    assert check.never_reached == check.declared_steps - check.observed_steps == MAIN_EXPECTED["never_reached"]
    assert check.undeclared_steps == check.observed_steps - check.declared_steps == MAIN_EXPECTED["undeclared_steps"]
    for name, expected in MAIN_EXPECTED.items():
        value = getattr(check, name)
        assert type(value) is frozenset and value == expected, (name, value)


def test_p10_3_declaration_check_is_a_frozen_dataclass_with_the_eleven_fields_and_eight_keys(main_pair: tuple[RootedStore, str, str]) -> None:
    from poisson_prove.steps import DeclarationCheck

    store, a, _ = main_pair
    check = check_of(store, a)
    assert type(check) is DeclarationCheck
    assert tuple(f.name for f in dataclasses.fields(DeclarationCheck)) == CHECK_FIELDS
    with pytest.raises(dataclasses.FrozenInstanceError):
        check.never_reached = frozenset()  # type: ignore[misc]
    prov = check.provenance()
    assert list(prov) == list(EIGHT_KEYS)
    assert all(type(v) is list and v == sorted(v) for v in prov.values()), prov
    assert {k: ", ".join(v) or "none" for k, v in prov.items()} == MAIN_LINES


def test_p10_3_inspect_prints_the_eight_as_one_block_before_the_rows(main_pair: tuple[RootedStore, str, str]) -> None:
    """``inspect`` prints the same eight as a block before the rows, once per run, in the
    table's order, each in the provenance block's own line form (``- words: a, b`` or ``none``)."""
    store, a, _ = main_pair
    code, out, err = run_cli(["--store", str(store.root), "inspect", a, "--event", EVENT])
    assert code == 0, err
    lines = out.splitlines()
    first_row = next(i for i, line in enumerate(lines) if line.startswith("config_hash: "))
    block = [line for line in lines[:first_row] if line.lstrip("- ").split(":")[0] in {label(k) for k in EIGHT_KEYS}]
    expected = [f"{label(k)}: {MAIN_LINES[k]}" for k in EIGHT_KEYS]
    assert [line.removeprefix("- ") for line in block] == expected, block
    for k in EIGHT_KEYS:
        assert sum(1 for line in lines if line.removeprefix("- ").startswith(f"{label(k)}: ")) == 1, k


# ---------- P10-4: the write-time stamp ----------


def test_p10_4_finalize_stamps_a_declared_gate_whose_gate_is_none_and_nothing_else() -> None:
    """The stamp's precedence: ``"emitted"`` is never overwritten; a span with no step name, a declared
    step that is not a gate, and an undeclared step are all untouched."""
    t = trace_of(
        span(1, step="verify"), span(2, step="verify", gate="emitted"), span(3), span(4, step="plan"),
        span(5, step="retry"), span(6, gate="emitted"),
    )
    out = finalize(t, declaration=declaration(), limit=None)
    assert [s.gate for s in out.spans] == ["declared", "emitted", None, None, None, "emitted"]
    assert [s.step_name for s in out.spans] == [s.step_name for s in t.spans]
    assert [dataclasses.replace(s, gate=None) for s in out.spans] == [dataclasses.replace(s, gate=None) for s in t.spans]


def test_p10_4_the_local_store_holds_the_stamp(main_pair: tuple[RootedStore, str, str]) -> None:
    store, a, _ = main_pair
    by_step: dict[str | None, set[str | None]] = {}
    for s in stored_spans(store, a):
        by_step.setdefault(s.get("step_name"), set()).add(s.get("gate"))
    assert by_step == {"plan": {None}, "verify": {"declared"}, "review": {"emitted"}, "retry": {None}, "check": {"emitted"}, None: {"emitted"}}, by_step


def test_p10_4_on_modal_the_stamp_is_on_the_stored_row_because_it_ran_on_the_host(modal_run: tuple[RootedStore, str]) -> None:
    """The container returns spans with ``verify`` un-gated (``worker_batch`` has no declaration); the
    stored row carries ``"declared"``, so the stamp ran host-side."""
    store, run_id = modal_run
    assert store.manifest(run_id).backend == "modal"
    gates = {s.get("gate") for s in stored_spans(store, run_id) if s.get("step_name") == "verify"}
    assert gates == {"declared"}, gates
    assert store.manifest(run_id).declared == declaration()


# ---------- P10-5: emitted gates the declaration does not name ----------


def test_p10_5_emitted_not_declared_is_exactly_the_emitted_names_outside_the_gates(main_pair: tuple[RootedStore, str, str]) -> None:
    store, a, _ = main_pair
    check = check_of(store, a)
    emitted = {s["step_name"] for s in stored_spans(store, a) if s.get("gate") == "emitted" and s.get("step_name") is not None}
    assert check.emitted_gates == emitted == {"check", "review"}
    assert check.emitted_not_declared == frozenset(emitted) - check.declared_gates == {"check"}


def test_p10_5_the_eight_print_in_the_provenance_block_and_nowhere_else(tmp_path: Path, main_pair: tuple[RootedStore, str, str]) -> None:
    """In ``report.md`` every line carrying one of the eight lies inside ``## Provenance``; Level 2 and
    every other section carry none. Each side's eight are present, in order."""
    store, a, b = main_pair
    code, _, err = run_cli(["--store", str(store.root), "report", a, b, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "r")])
    assert code == 0, err
    markdown = (tmp_path / "r" / "report.md").read_text()
    inside, outside = provenance_section(markdown)
    assert [line for line in outside if any_label(line)] == [], [line for line in outside if any_label(line)]
    for side in ("a", "b"):
        mine = [line for line in inside if line.startswith("- ") and line.split(":")[0][2:] in {f"{label(k)} {side}" for k in EIGHT_KEYS}]
        assert mine == [f"- {label(k)} {side}: {MAIN_LINES[k]}" for k in EIGHT_KEYS], mine
    receipt = (tmp_path / "r" / "receipt.html").read_text()
    at = receipt.index("Provenance</h2>")
    assert any_label(receipt[:at]) == [], any_label(receipt[:at])
    assert f"{label('emitted_gates_not_declared')} a: check" in receipt[at:]


# ---------- P10-6: the diff refusal (in diff, just before the pairing check) ----------


def _frames(store: Store, a: str, b: str, fn: str) -> tuple[Any, Any]:
    fa, fb = store.read(a), store.read(b)
    if fn == "diff":
        return censor(fa, EVENT), censor(fb, EVENT)
    return fa, fb


def _call(fn: str, fa: Any, fb: Any, method: str, ma: RunManifest | None, mb: RunManifest | None) -> Any:
    if fn == "diff":
        return diff(fa, fb, event=EVENT, method=method, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]
    return multi_diff(fa, fb, events=[EVENT], method=method, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]


METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")
FNS = ("diff", "multi_diff")


@pytest.mark.parametrize("fn", FNS)
@pytest.mark.parametrize("method", METHODS)
def test_p10_6_differing_declared_outcome_sets_are_refused_under_every_method(tmp_path: Path, fn: str, method: str) -> None:
    from poisson_prove.diff import DeclaredSetMismatch

    assert issubclass(DeclaredSetMismatch, DiffError)
    ma = manifest("a", declared=declaration(outcomes=("fell", "survived")))
    mb = manifest("b", declared=declaration(outcomes=("fell", "timed_out")))
    store = pair_store(tmp_path, ma, mb)
    fa, fb = _frames(store, "a", "b", fn)
    with pytest.raises(DeclaredSetMismatch):
        _call(fn, fa, fb, method, ma, mb)
    with pytest.raises(DeclaredSetMismatch):
        _call(fn, fb, fa, method, mb, ma)


@pytest.mark.parametrize("fn", FNS)
@pytest.mark.parametrize(
    ("case", "da", "db", "b_outcomes"),
    [
        ("one-side-declares", ("fell", "survived"), None, PAIR_OUTCOMES),
        ("other-side-declares", None, ("fell", "survived"), PAIR_OUTCOMES),
        ("one-side-declares-no-outcomes", ("fell", "survived"), (), PAIR_OUTCOMES),
        ("observed-differ-declared-match", ("fell", "survived"), ("fell", "survived"), PAIR_OUTCOMES_WIDER),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_p10_6_no_refusal_unless_both_declare_non_empty_differing_outcomes(
    tmp_path: Path, fn: str, case: str, da: tuple[str, ...] | None, db: tuple[str, ...] | None, b_outcomes: Mapping[float, str]
) -> None:
    """*Sole catch for a check that compares observed sets* (``observed-differ-declared-match``):
    refusing on the observed set fires on provider noise, which is why the declared sets are compared."""
    ma = manifest("a", declared=None if da is None else declaration(outcomes=da))
    mb = manifest("b", declared=None if db is None else declaration(steps=STEPS, outcomes=db, gates=GATES))
    store = pair_store(tmp_path, ma, mb, b_outcomes=b_outcomes)
    fa, fb = _frames(store, "a", "b", fn)
    for method in METHODS:
        _call(fn, fa, fb, method, ma, mb)


@pytest.mark.parametrize("fn", FNS)
def test_p10_6_the_refusal_wins_over_the_unit_and_salt_refusals(tmp_path: Path, fn: str) -> None:
    """A ``t_unit`` mismatch and a paired method on differing salts are each refused as they were
    on their own, and with differing declared outcome sets as well the declared-set refusal wins."""
    from poisson_prove.diff import DeclaredSetMismatch

    da, db = declaration(outcomes=("fell", "survived")), declaration(outcomes=("fell", "timed_out"))
    ma, mb = manifest("a", declared=da), manifest("b", declared=db, t_unit="seconds", salt=OTHER_SALT)
    store = pair_store(tmp_path, ma, mb)
    fa, fb = _frames(store, "a", "b", fn)
    with pytest.raises(UnitMismatch):
        _call(fn, fa, fb, "fisher_bh", manifest("a", declared=da), manifest("b", declared=da, t_unit="seconds"))
    with pytest.raises(NotPairable):
        _call(fn, fa, fb, "mcnemar_bh", manifest("a", declared=da), manifest("b", declared=da, salt=OTHER_SALT))
    with pytest.raises(DeclaredSetMismatch):
        _call(fn, fa, fb, "fisher_bh", ma, mb)
    with pytest.raises(DeclaredSetMismatch):
        _call(fn, fa, fb, "mcnemar_bh", ma, manifest("b", declared=db, salt=OTHER_SALT))


@pytest.mark.parametrize("fn", FNS)
def test_p10_6_frame_validation_still_comes_first(tmp_path: Path, fn: str) -> None:
    """"Just before the pairing check": a malformed frame is refused as it was, by the check that
    precedes the pairing check, and not as a declared-set mismatch."""
    from poisson_prove.diff import DeclaredSetMismatch

    ma = manifest("a", declared=declaration(outcomes=("fell", "survived")))
    mb = manifest("b", declared=declaration(outcomes=("fell", "timed_out")))
    store = pair_store(tmp_path, ma, mb)
    fa, fb = _frames(store, "a", "b", fn)
    with pytest.raises(DiffError) as excinfo:
        _call(fn, fa.iloc[0:0], fb, "fisher_bh", ma, mb)
    assert not isinstance(excinfo.value, DeclaredSetMismatch)


def test_p10_6_every_diffing_verb_refuses_the_pair(tmp_path: Path) -> None:
    """The library refusal reaches the CLI as a refusal (exit 1) on every verb that diffs, and no
    report directory is written."""
    ma = manifest("a", declared=declaration(outcomes=("fell", "survived")))
    mb = manifest("b", declared=declaration(outcomes=("fell", "timed_out")))
    root = str(pair_store(tmp_path / "store", ma, mb).root)
    out_dir = tmp_path / "report"
    for argv in (
        ["diff", "a", "b", "--event", EVENT],
        ["check", "a", "b", "--event", EVENT],
        ["report", "a", "b", "--event", EVENT, "--x", "x", "--out", str(out_dir)],
        ["serve", "a", "b", "--event", EVENT, "--x", "x", "--json"],
    ):
        code, out, err = run_cli(["--store", root, *argv])
        # A refusal exits 1.
        assert code == 1, (argv, code, out, err)
        assert err.startswith("error: "), err
    assert not (out_dir / "report.md").exists()


# ---------- P10-7: an undeclared outcome is stored, listed, printed, never refused ----------


def test_p10_7_an_undeclared_outcome_is_stored_listed_printed_and_refused_by_no_verb(tmp_path: Path, main_pair: tuple[RootedStore, str, str]) -> None:
    store, a, b = main_pair
    root = str(store.root)
    assert "timed_out" in set(raw_column(store, a, "outcome"))
    assert check_of(store, a).undeclared_outcomes == {"timed_out"}
    runs = {
        "report": ["report", a, b, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "r")],
        "report-one": ["report", a, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "one")],
        "inspect": ["inspect", a, "--event", "timed_out"],
        "diff": ["diff", a, b, "--event", EVENT],
        # PF4 (PF4.20): the runs declare outcomes but no kind, so the default --fail-on worse is
        # refused; --fail-on higher is the same gate on a failure event (fail when it rose).
        "check": ["check", a, b, "--event", EVENT, "--fail-on", "higher"],
        "serve": ["serve", a, b, "--event", EVENT, "--x", "x", "--json"],
    }
    results = {name: run_cli(["--store", root, *argv]) for name, argv in runs.items()}
    for name, (code, _, err) in results.items():
        assert code in ((0, 1) if name == "check" else (0,)), (name, code, err)
        assert "error:" not in err, (name, err)
    assert "timed_out" in results["inspect"][1]
    assert f"- {label('undeclared_outcomes')} a: timed_out" in (tmp_path / "r" / "report.md").read_text()
    assert f"- {label('undeclared_outcomes')}: timed_out" in (tmp_path / "one" / "report.md").read_text()
    served = json.loads(results["serve"][1])
    assert "undeclared_outcomes_a" in json.dumps(served)


# ---------- P10-8: the import graph ----------


def test_p10_8_a_fresh_interpreter_imports_trace_and_declaration() -> None:
    """A subprocess, not an in-process import: by the time a test body runs, ``tests/`` has already
    initialised half the package."""
    env = {**os.environ, "PYTHONPATH": str(PACKAGE.parent)}
    for code in ("import poisson_prove.trace", "from poisson_prove.trace import Declaration, finalize"):
        done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, (code, done.stderr)


def test_p10_8_declaration_is_minted_in_trace_and_exported_in_sort_order() -> None:
    """*Sole catch for A6's own spelling*, a ``Declaration`` defined in ``sampler.py``."""
    from poisson_prove.trace import Declaration

    assert Declaration.__module__ == "poisson_prove.trace"
    names = list(trace_module.__all__)
    classes = [n for n in names if n[:1].isupper() and not n.isupper()]
    assert "Declaration" in classes and classes == sorted(classes), classes


# ---------- P10-9: the CD guard, narrowed ----------


def test_p10_9_finalize_takes_declaration_and_limit_keyword_only_with_no_default() -> None:
    sig = inspect.signature(finalize)
    assert list(sig.parameters) == ["trace", "declaration", "limit"]
    kinds = {name: p.kind for name, p in sig.parameters.items()}
    assert kinds["declaration"] is kinds["limit"] is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["declaration"].default is inspect.Parameter.empty
    assert sig.parameters["limit"].default is inspect.Parameter.empty


@pytest.mark.parametrize("bad", [object(), "verify", ("verify",), {"gates": ["verify"]}], ids=["object", "str", "tuple", "dict"])
def test_p10_9_a_non_declaration_is_refused_naming_declaration(bad: Any) -> None:
    """*Sole catch for a ``finalize`` that widens the annotation and drops the guard.* Control: a real
    ``Declaration`` on the same trace does not raise."""
    t = trace_of(span(1, step="verify"))
    finalize(t, declaration=declaration(), limit=64)
    with pytest.raises(TypeError) as excinfo:
        finalize(t, declaration=bad, limit=64)
    assert "Declaration" in str(excinfo.value), str(excinfo.value)


# ---------- P10-10: identity, idempotence, commutation ----------


def test_p10_10a_finalize_returns_the_trace_itself_when_nothing_is_stamped_or_cut() -> None:
    """*Sole catch for the stamp that rebuilds unconditionally*: ``is``, not ``==``."""
    t = trace_of(span(1, step="plan"), span(2, step="retry"), span(3), span(4, step="verify", gate="emitted"))
    d = declaration()
    assert finalize(t, declaration=d, limit=None) is t
    assert finalize(t, declaration=d, limit=64) is t
    assert finalize(t, declaration=None, limit=None) is t
    stamped = finalize(trace_of(span(1, step="verify")), declaration=d, limit=None)
    assert stamped.spans[0].gate == "declared"


def test_p10_10a_a_declaring_run_that_stamps_nothing_stores_the_bytes_of_one_that_declares_nothing(unmatched_runs: tuple[RootedStore, str, RootedStore, str]) -> None:
    """The unmatched fixture, row for row. ``Store.append`` re-reads every trace through
    ``Trace.from_dict`` and ``split``, so this clause holds by construction and the ``is`` clause
    above is the only observable; kept because it states the same claim at the store."""
    declaring, run_d, plain, run_n = unmatched_runs
    assert declaring.manifest(run_d).declared == declaration()
    assert plain.manifest(run_n).declared is None
    for column in ("trace", "trace_obs", "meta"):
        assert keyed_raw(declaring, run_d, column) == keyed_raw(plain, run_n, column), column


def _stamp_and_cut() -> tuple[Trace, Any, int]:
    over = "v" * 300
    return (
        trace_of(span(1, step="verify", output=over), span(2, step="search", gate="emitted", output="s" * 10), span(3, step="plan", output=over)),
        declaration(),
        64,
    )


def test_p10_10b_finalize_is_idempotent_as_a_whole() -> None:
    t, d, limit = _stamp_and_cut()
    once = finalize(t, declaration=d, limit=limit)
    twice = finalize(once, declaration=d, limit=limit)
    assert canonical(twice) == canonical(once)
    assert [(s.gate, s.truncated, s.bytes_original) for s in once.spans] == [
        ("declared", "observation", 300), ("emitted", None, None), (None, "observation", 300),
    ]


def test_p10_10c_stamp_then_cut_equals_cut_then_stamp() -> None:
    t, d, limit = _stamp_and_cut()
    once = finalize(t, declaration=d, limit=limit)
    stamp_then_cut = truncate_observations(finalize(t, declaration=d, limit=None), limit=limit)
    cut_then_stamp = finalize(truncate_observations(t, limit=limit), declaration=d, limit=None)
    assert canonical(stamp_then_cut) == canonical(cut_then_stamp) == canonical(once)


def test_p10_10bc_both_halves_fire_on_one_stored_span(tmp_path: Path) -> None:
    """The cut fixture, through the funnel: the run's declared limit and its declared gate
    both reach the stored ``verify`` span. Run in a child, because ``[capture]`` installs a provider."""
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    toml = write(tmp_path / "cut.toml", sweep_toml(DECLARE_TOML, values=(0.1,), replicates=1, capture={"instrument": [], "max_observation_bytes": 64}))
    run_id = _isolated(_child_cut_run, str(tmp_path / "store"), str(toml))
    store = Store(tmp_path / "store")
    (envelope,) = [e for e in store.read(run_id, meta=False, trace="envelope")["trace"]]
    by_step = {s["step_name"]: s for s in envelope["spans"]}
    assert (by_step["verify"]["gate"], by_step["verify"]["truncated"], by_step["verify"]["bytes_original"]) == ("declared", "observation", 300)
    assert (by_step["plan"]["gate"], by_step["plan"]["truncated"]) == (None, None)


def _child_cut_run(store_root: str, toml_path: str) -> str:
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=RUN_SALT, import_path=f"{MODULE}:cut_rollout")
    run_local(p, cut_rollout, store)
    return str(p.run_id)


def _isolated(fn: Callable[..., Any], *args: Any, timeout: float = 180.0) -> Any:
    """Run ``fn(*args)`` in a child process, so no OTel provider is installed in pytest's."""
    return run_isolated(fn, *args, timeout=timeout)


# ---------- P10-11: the manifest field ----------


def test_p10_11_the_manifest_has_thirteen_keys_and_round_trips_both_ways() -> None:
    """``from_dict(to_dict(m)) == m`` for a declaring and a non-declaring manifest; ``declared``
    is three sorted lists or ``null``, byte-identical under ``json.dumps(sort_keys=True)``."""
    for declared in (None, declaration()):
        m = manifest("m", declared=declared)
        d = m.to_dict()
        assert set(d) == TWELVE | {"declared"}, sorted(set(d) ^ TWELVE)
        assert RunManifest.from_dict(d) == m
        again = RunManifest.from_dict(json.loads(json.dumps(d, sort_keys=True))).to_dict()
        assert json.dumps(again, sort_keys=True) == json.dumps(d, sort_keys=True)
    assert manifest("m").to_dict()["declared"] is None
    assert manifest("m", declared=declaration()).to_dict()["declared"] == {"steps": list(STEPS), "outcomes": list(OUTCOMES), "gates": list(GATES)}


def test_p10_11_a_manifest_json_with_no_declared_key_loads_as_none() -> None:
    """Every run written before A10, the generated lattice pair's 0.0.1 manifest first."""
    legacy = json.loads((lattice.root() / lattice.RUN_A / "manifest.json").read_text())
    assert "declared" not in legacy
    assert RunManifest.from_dict(legacy).declared is None
    assert Store(lattice.root()).manifest(lattice.RUN_A).declared is None


def test_p10_11_mark_complete_preserves_the_declaration(tmp_path: Path) -> None:
    """*Sole catch for the ``to_dict`` that writes the field and the ``from_dict`` that does not read
    it*: ``mark_complete`` is ``replace(self.manifest(run_id), status="complete")``."""
    store = Store(tmp_path)
    store.create_run(manifest("m", declared=declaration()))
    assert store.manifest("m").declared == declaration()
    store.mark_complete("m")
    assert store.manifest("m").status == "complete"
    assert store.manifest("m").declared == declaration()
    on_disk = json.loads((tmp_path / "m" / "manifest.json").read_text())
    assert on_disk["declared"] == {"steps": list(STEPS), "outcomes": list(OUTCOMES), "gates": list(GATES)}


def test_p10_11_a_real_run_records_its_sweep_s_declaration_and_one_with_none_records_null(main_pair: tuple[RootedStore, str, str], bare_pair: tuple[RootedStore, str, str]) -> None:
    store, a, _ = main_pair
    bstore, b, _ = bare_pair
    assert store.manifest(a).status == "complete" and store.manifest(a).declared == declaration()
    on_disk = json.loads((store.root / a / "manifest.json").read_text())
    assert on_disk["declared"] == {"steps": list(STEPS), "outcomes": list(OUTCOMES), "gates": list(GATES)}
    assert json.loads((bstore.root / b / "manifest.json").read_text())["declared"] is None


# ---------- P10-12: the resume gate ----------


def _partial(root: Path, declare: Mapping[str, Any] | None) -> tuple[Store, str]:
    return local_run(root, sweep_toml(declare), silent_rollout, name="first", max_rollouts=2)


@pytest.mark.parametrize(
    ("case", "recorded", "resumed_with", "refused"),
    [
        ("identical", DECLARE_TOML, DECLARE_TOML, False),
        ("respelled", DECLARE_TOML, {"steps": ["search", "verify", "review", "plan"], "outcomes": ["fell", "survived"], "gates": ["search", "review", "verify"]}, False),
        ("changed", DECLARE_TOML, {**DECLARE_TOML, "steps": ["plan", "verify"], "gates": ["verify"]}, True),
        ("declares-where-the-run-did-not", None, DECLARE_TOML, True),
        ("declares-nothing-where-the-run-did", DECLARE_TOML, None, True),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_p10_12_resume_is_gated_on_the_whole_declaration(
    tmp_path: Path, case: str, recorded: Mapping[str, Any] | None, resumed_with: Mapping[str, Any] | None, refused: bool
) -> None:
    """One value comparison, *declares nothing* against *declares something* a difference in both
    directions. *Sole catch for the gate that compares ``is None`` on each side* (``changed``)."""
    store, run_id = _partial(tmp_path, recorded)
    assert store.manifest(run_id).status == "partial"
    spec = SweepSpec.load(write(tmp_path / "again.toml", sweep_toml(resumed_with)))
    if not refused:
        p = plan(spec, store, resume=run_id)
        run_local(p, silent_rollout, store)
        assert store.manifest(run_id).status == "complete"
        assert store.manifest(run_id).declared == declaration()
        return
    with pytest.raises(NotResumable) as excinfo:
        plan(spec, store, resume=run_id)
    message = str(excinfo.value)
    assert run_id in message, message
    sides = [store.manifest(run_id).declared, spec.declare]
    members = set().union(*[set(d.steps) | set(d.outcomes) | set(d.gates) for d in sides if d is not None])
    differing = members if None in sides else (set(sides[0].steps) ^ set(sides[1].steps))
    for name in differing:
        assert name in message, (name, message)


def test_p10_12_pair_with_is_not_gated(tmp_path: Path) -> None:
    """``--pair-with`` inherits a salt from a run that declared nothing, and the new run records its
    own declaration."""
    store, first = local_run(tmp_path, sweep_toml(None), silent_rollout, name="first")
    spec = SweepSpec.load(write(tmp_path / "second.toml", sweep_toml(DECLARE_TOML)))
    p = plan(spec, store, pair_with=first)
    run_local(p, silent_rollout, store)
    assert store.manifest(p.run_id).declared == declaration()
    assert store.manifest(first).declared is None


# ---------- P10-13: the surfaces that do not move on a declaring run ----------


def test_p10_13_check_and_diff_print_the_same_bytes_for_a_declaring_pair(tmp_path: Path) -> None:
    """``check``, ``diff`` and ``diff --format json`` gain nothing. The same rows under the same
    run ids in two stores, one pair declaring (the same declaration on both sides) and one not.
    ``viewer.py`` and ``tree.py`` byte-identity is FR17's and CD9's, not restated here."""
    outputs = []
    for name, declared in (("declaring", declaration()), ("plain", None)):
        store = pair_store(tmp_path / name, manifest("a", declared=declared), manifest("b", declared=declared), b_outcomes=PAIR_OUTCOMES_WIDER)
        root = str(store.root)
        texts = []
        # PF4 (PF4.20): neither pair declares a kind for the event, so check's default --fail-on
        # worse is refused on both and would compare two refusals; --fail-on higher is the same gate
        # on a failure event, so check's own output is what is compared again.
        for argv in (["check", "a", "b", "--event", EVENT, "--fail-on", "higher"], ["diff", "a", "b", "--event", EVENT], ["diff", "a", "b", "--event", EVENT, "--format", "json"]):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                code, out, err = run_cli(["--store", root, *argv])
            texts.append((code, out.replace(root, "<root>"), err.replace(root, "<root>")))
        outputs.append(texts)
    assert outputs[0] == outputs[1]
    assert Store(tmp_path / "declaring").manifest("a").declared == declaration()


# ---------- P10-14: the read path ----------


def test_p10_14_the_check_succeeds_on_a_run_whose_meta_and_trace_obs_are_not_json(tmp_path: Path, main_pair: tuple[RootedStore, str, str]) -> None:
    """A7's P7-5 fixture shape: ``meta`` and ``trace_obs`` hold bytes that are not JSON. The check and
    the single-run report read the envelope only, so both succeed and the check is unchanged."""
    store, a, _ = main_pair
    root = tmp_path / "store"
    shutil.copytree(store.root / a, root / a)
    for part in sorted((root / a / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part)
        for column in ("meta", "trace_obs"):
            at = table.schema.get_field_index(column)
            table = table.set_column(at, table.schema.field(at), pa.array(["\xff{not json"] * table.num_rows, pa.string()))
        pq.write_table(table, part)
    poisoned = Store(root)
    assert check_of(poisoned, a) == check_of(store, a)
    code, out, err = run_cli(["--store", str(root), "report", a, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "r")])
    assert code == 0, err
    assert f"- {label('never_reached')}: search" in (tmp_path / "r" / "report.md").read_text()


def test_p10_14_observed_outcomes_are_strings_with_a_null_outcome_in_the_frame(main_pair: tuple[RootedStore, str, str]) -> None:
    """The one place a cell split would appear: ``outcome`` is a nullable string column, and
    under pandas 3 a null that read back as ``NaN`` would enter the set as a float."""
    store, a, _ = main_pair
    frame = store.read(a, meta=False, trace="envelope")
    assert any(o is None for o in frame["outcome"]), list(frame["outcome"])
    observed = check_of(store, a).observed_outcomes
    assert all(type(o) is str for o in observed), observed


# ---------- P10-15: a declaration that matches nothing ----------


def test_p10_15_capture_off_prints_every_declared_step_as_never_reached_and_nothing_refuses(tmp_path: Path, silent_runs: tuple[RootedStore, str, RootedStore, str]) -> None:
    """Printed in full, never refused. No verb exits non-zero and the declaration
    adds no warning: the warnings are those of the same verbs on the non-declaring twin."""
    declaring, run_d, plain, run_n = silent_runs
    check = check_of(declaring, run_d)
    assert check.observed_steps == frozenset() and check.never_reached == check.declared_steps == set(STEPS)
    seen: list[list[tuple[str, str]]] = []
    outs: list[str] = []
    for store, run_id, tag in ((declaring, run_d, "d"), (plain, run_n, "n")):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            r = run_cli(["--store", str(store.root), "report", run_id, "--event", EVENT, "--x", "x", "--out", str(tmp_path / tag)])
            i = run_cli(["--store", str(store.root), "inspect", run_id, "--event", EVENT])
        assert r[0] == 0 and i[0] == 0, (r, i)
        assert r[2] == "" and i[2] == "", (r[2], i[2])
        seen.append(sorted((w.category.__name__, str(w.message)) for w in caught))
        outs += [(tmp_path / tag / "report.md").read_text(), i[1]]
    assert seen[0] == seen[1], seen
    assert f"- {label('never_reached')}: plan, review, search, verify" in outs[0]
    assert f"{label('never_reached')}: plan, review, search, verify" in outs[1]


# ---------- P10-16: the sweep's identity ----------


def test_p10_16_two_specs_differing_only_in_declare_are_the_same_sweep(tmp_path: Path) -> None:
    """*Sole catch for the field that rides ``to_dict()``*, which breaks pairing between a
    declaring arm and a non-declaring one."""
    with_d = SweepSpec.load(write(tmp_path / "d.toml", sweep_toml(DECLARE_TOML)))
    without = SweepSpec.load(write(tmp_path / "n.toml", sweep_toml(None)))
    assert with_d.declare is not None and without.declare is None
    assert with_d.to_dict() == without.to_dict()
    assert with_d.cells() == without.cells()
    built = SweepSpec.build([{"x": 0.1}], replicates=1, target_id=TARGET, t_unit=T_UNIT, declare=declaration())
    assert built.declare == declaration()
    assert built.to_dict() == SweepSpec.build([{"x": 0.1}], replicates=1, target_id=TARGET, t_unit=T_UNIT).to_dict()
    store = Store(tmp_path / "store")
    seeds = [[q.seed for q in plan(s, store, run_salt=RUN_SALT).pairs] for s in (with_d, without)]
    assert seeds[0] == seeds[1]


def test_p10_16_the_manifest_s_sweep_record_carries_no_declaration(main_pair: tuple[RootedStore, str, str]) -> None:
    store, a, _ = main_pair
    env = store.manifest(a).environment
    assert "declare" not in env["sweep"] and "declared" not in env["sweep"]
    assert "declare" not in env and "declared" not in env
    assert store.manifest(a).declared == declaration()


# ---------- P10-17: nothing is persisted ----------


def test_p10_17_the_check_and_the_report_write_nothing_under_the_store(tmp_path: Path, main_pair: tuple[RootedStore, str, str]) -> None:
    """Sets computed at read time, nothing written back (mtime and bytes of every file)."""
    store, a, b = main_pair
    root = store.root
    before = snapshot(root)
    check_of(store, a)
    run_cli(["--store", str(root), "report", a, b, "--event", EVENT, "--x", "x", "--out", str(tmp_path / "r")])
    run_cli(["--store", str(root), "inspect", a, "--event", EVENT])
    # PF12: report saves the comparison it shows, under ``.poisson/``; no
    # stored file outside it is written (bytes and mtimes), and check without --save writes nothing:
    # the folder holds the store descriptor and that one comparison.
    after = snapshot(root)
    assert {k: v for k, v in after.items() if not k.startswith(".poisson")} == {k: v for k, v in before.items() if not k.startswith(".poisson")}
    added = sorted(k for k in after if k.startswith(".poisson") and k not in before)
    saved = [k for k in added if k != ".poisson/store.json"]
    assert all(k.startswith(".poisson/artifacts/comparison/") for k in saved), added
    assert len({k.split("/")[3] for k in saved}) <= 1, added
    assert any(k.startswith(".poisson/artifacts/comparison/") for k in after), sorted(after)


def test_p10_17_the_manifest_has_no_field_for_a_check_result() -> None:
    # PF2: RunManifest gains the field `name` (None unless given at sweep time).
    assert {f.name for f in dataclasses.fields(RunManifest)} == TWELVE | {"declared", "name"}


# ---------- P10-19: the two gate identities ----------


def _identities(store: Store, run_id: str) -> None:
    check = check_of(store, run_id)
    assert check.declared_never_reached == check.never_reached & check.declared_gates
    assert check.declared_gates - check.declared_never_reached == check.declared_gates & gated_step_names(store, run_id)


def test_p10_19_both_identities_hold_on_the_main_fixture(main_pair: tuple[RootedStore, str, str]) -> None:
    """*Sole catch for the stamp that silently did not run*: ``verify`` is reached only un-gated, so
    the second identity holds only if the stamp gated it; the first holds either way. ``review`` is
    reached only as ``"emitted"``, so a ``declared_never_reached`` read off ``gate == "declared"``
    calls it never reached and breaks the first."""
    store, a, _ = main_pair
    _identities(store, a)
    assert check_of(store, a).declared_gates - check_of(store, a).declared_never_reached == {"review", "verify"}


def test_p10_19_both_identities_hold_on_the_unmatched_capture_off_and_modal_fixtures(
    unmatched_runs: tuple[RootedStore, str, RootedStore, str], silent_runs: tuple[RootedStore, str, RootedStore, str], modal_run: tuple[RootedStore, str]
) -> None:
    _identities(unmatched_runs[0], unmatched_runs[1])
    _identities(silent_runs[0], silent_runs[1])
    _identities(*modal_run)
    assert check_of(unmatched_runs[0], unmatched_runs[1]).declared_never_reached == set(GATES)


# ---------- P10-20: a marker with no name ----------


def test_p10_20_an_emitted_marker_with_no_step_name_contributes_nothing(main_pair: tuple[RootedStore, str, str]) -> None:
    """Through the recorder: the stored ``guard`` span carries ``gate="emitted"`` and no step name, and
    reaches no set; the stored ``retry`` span carries a step name and no gate, and reaches
    ``observed_steps`` (and so ``undeclared_steps``) and no gate set."""
    store, a, _ = main_pair
    spans = stored_spans(store, a)
    assert any(s.get("name") == "guard" and s.get("step_name") is None and s.get("gate") == "emitted" for s in spans)
    assert any(s.get("name") == "retry" and s.get("step_name") == "retry" and s.get("gate") is None for s in spans)
    check = check_of(store, a)
    everything = [getattr(check, name) for name in CHECK_FIELDS]
    assert all(None not in s for s in everything)
    assert "guard" not in set().union(*everything)
    assert "retry" in check.observed_steps and "retry" in check.undeclared_steps
    assert "retry" not in check.emitted_gates | check.emitted_not_declared | check.declared_never_reached | check.never_reached


# ---------- P10-22: the funnel still never raises ----------


def test_p10_22_an_invalid_trace_is_stored_as_written_on_a_run_that_declares_gates(tmp_path: Path) -> None:
    """A7's P7-9 and A8b's P8-26 re-run under a declaration. *Sole catch for the stamp that runs
    ``Trace.from_dict`` one frame before the guard written for it*."""
    store, run_id = local_run(tmp_path, sweep_toml(DECLARE_TOML, values=tuple(BAD_TRACES), replicates=1), bad_trace_rollout)
    assert store.count(run_id) == len(BAD_TRACES)
    assert raw_column(store, run_id, "trace") == [None] * len(BAD_TRACES)
    assert raw_column(store, run_id, "trace_obs") == [None] * len(BAD_TRACES)
    frame = store.read(run_id)
    stored = {round(float(cfg["x"]), 1): meta["trace"] for cfg, meta in zip(frame["config"], frame["meta"], strict=True)}
    assert stored == BAD_TRACES
    assert store.manifest(run_id).declared == declaration()
