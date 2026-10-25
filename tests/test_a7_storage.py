"""A7 oracle: invariants P7-1 to P7-12 of [[Proofload - Spec A7 Storage Split]] section 4, written
before ``Store.read(trace=)``, the two Parquet columns, ``split``, ``assemble``, ``OBSERVATION_KEYS``
and ``LOGPROBS_KEY`` exist, against ``93bfa13`` -- the M11a merge, A7's dispatch commit.

**The register, built to as answered at dispatch (spec section 10):** Q1 (a) P7-12's fixture is
A28's crossed shape stored twice, and it discriminates *layout*, not scale; Q2 (a) two cells,
pandas 2.3.3 and pandas 3.0.5, A22's recipe; Q3 (c) ``meta=`` stays orthogonal to ``trace=`` --
``meta=False, trace="envelope"`` is twelve columns, ``meta=True, trace="envelope"`` fourteen with
``meta`` decoded and its ``"trace"`` key removed; Q4 (a) ``read(meta=False, trace="full")`` is
refused with a ``ValueError`` naming both arguments; Q5 (a) no ``environment.code_root``; Q6 (a)
C28 is measured and deferred, ``append`` stays refuse-on-overlap; Q7 (b) ``trace="none"`` strips a
pre-A7 row's ``meta["trace"]``.

**Two cells, and the invariant set does not partition between them** (Master Action List section
18 standing rule 15). The packet's claim spans pandas 2 and pandas 3 because six invariants --
P7-2, P7-3, P7-7, P7-8, P7-9, P7-11 -- have null halves that **cannot disagree on pandas 2.3.3**:
pyarrow gives an ``object`` column with ``None`` there whether or not the build registered the two
columns in ``store._NULLABLE_STRING_COLUMNS``. Every invariant here is asserted in both cells;
twelve tests, **12 + 12 = 24 ids over the two cells against the oracle's own 12**. No invariant is
cell-specific, and none could be asserted in one cell only. **Nullness is by identity throughout**
(spec S5): ``is None`` / ``is not None`` on every column in every clause, never ``pd.isna`` and never
a bare truth test, and the on-disk ``trace_obs`` column -- which no read mode presents as a frame
column -- is read raw through ``pyarrow`` and ``to_pylist()``, where a null is ``None`` on every
pandas.

**Standing rule 12 -- this is a retrofit packet, and the retrofit is seven sites in five files,
not the spec's five in four.** R7's schema clause and R9's parameter list (``test_m4_read.py``) and
the three ``TRACE_EXPORTS`` copies (``test_m3_crash_trace.py``, ``test_m3_timeout_trace.py`` and
one more test module's) are the spec's. The sixth is ``test_m3_crash_trace.py``'s
``S16_ORACLE_SHA256``, which pins ``test_m3_timeout_trace.py`` whole-file and moves the moment that
file's export list is amended, so it is re-minted in the same commit after the edit (A22's
``FROZEN_ORACLE_SHA256`` cascade, one packet over). The seventh was found by the shadow shim's
whole-suite control and not by any grep the spec asked for:
``test_m3_capture.py::test_c7_rule_zero_the_mock_agent_trace_is_byte_identical_with_capture_on_and_off``
reads the raw ``meta`` cell of every part and does ``json.loads(...)["trace"]`` on it -- a
``KeyError`` once the trace leaves ``meta`` (P7-2). Its trace clause now reads through the store's
full read; its raw byte-identity clause, rule zero's own claim, is untouched, and the test is
green before and after. Spec section 7.2's "no test in ``test_m3_capture.py`` is red" was wrong by
that one test.

**The classified red set on the retrofit commit, measured on two pristine ``git archive`` copies of
``93bfa13`` before any source edit, venvs from the repo venv's freeze closure differing in exactly
pandas, collection verified 1913 = 1913 = 1913 and then 1925 with this file, baselines 1908 passed /
5 skipped / 0 failed in both cells: 17 failed / 1903 passed / 5 skipped, identically in both
cells.** The seventeen: all twelve tests here (P7-1 … P7-12), R7's schema clause, R9, K8, E12 and
P12. **The same set in both cells** -- the pandas 3 cell adds nothing, because A22's port is shipped
and the bare tree's reds are the four new names, the two new columns and the one new keyword, none
of which pandas can see. Nothing outside the set is red. Every reference to a name the build has
not created yet sits **inside** a test body or a fixture that runs at test time, never at module
level, so ``--collect-only`` gives an exact count on the retrofit commit. **Green before and after,
named so their green is not read as evidence:** C7 above; R7's third clause (the manifest key set,
A23/A26's); R9's other three tests and ``PUBLIC_STORE_SYMBOLS`` with its twin in
``test_s21_errors.py`` (A7 adds no public symbol to ``store.py``); A22's V5 (red only transiently
inside Session B's build, between ``_SCHEMA`` gaining the fields and ``_NULLABLE_STRING_COLUMNS``
gaining them); and A28's G17 with every other ``G`` -- its stored pair is a pre-A7 store that is
never rewritten, so the split never runs on it.

**What the freeze showed the spec to be wrong about, beyond the retrofit count.** (1) **A22's V7
decides a composition the spec gets backwards.** Spec section 3.3 says retention "nulls both columns
instead of popping ``meta``"; V7 (``test_a22_pandas3.py``) stores an *invalid* ``meta["trace"]`` on
an unretained row and asserts the key is gone from the read-back ``meta``. P7-7 and P7-9 as written
are neutral on that composition -- P7-7's trace is valid and leaves ``meta`` through the split, P7-9
has no retention policy -- so V7 is the frozen test that settles it: **the build keeps the pop on an
unretained row whether or not the trace was valid**, and nulls the columns beside it. The shadow
shim was red on V7 until it did. (2) ``OBSERVATION_KEYS`` typed as a frozenset cannot carry A6
section 3.3's four prefix rows; pinned behaviourally here (see below).

**Mutants, measured over the whole suite on ``rsync`` copies of the shadow shim at
``/private/tmp/claude-501/proofload-a7/mutants/<row>``, seven rows in parallel under the thread
caps, pandas 2.3.3 unless named.** Measurement order: rows 1-6 ran before C7's amendment and carry
its pre-amendment red in every row, not counted below; the control was re-run after the amendment
and is **1922 passed / 3 skipped / 0 failed**; rows 7-12 and the pandas 3 row ran after it.
Twelve mutants, twelve caught, no survivor.

| Row | Mutation | Caught by, measured |
|---|---|---|
| 1 | split but forget to pop ``meta["trace"]`` | **P7-2 alone** |
| 2 | the two names added to ``_META_COLUMNS``, old one-line projection | P7-1, P7-3 |
| 3 | ``split`` returns ``(trace.to_dict(), {})`` | **P7-11**, and P7-3, P7-7 (their envelope and ``trace_obs`` clauses) |
| 4 | ``_NULLABLE_STRING_COLUMNS`` not extended -- pandas 2.3.3 | **V5 alone**, as section 3.7 predicts: no null half can disagree here |
| 4 | the same -- pandas 3.0.5 cell | 125 failed / 220 errors: V1-V5, V7, V8, P7-1, P7-2, P7-3, P7-7, P7-8, P7-9, P7-10, P7-11 and every reader of a stored run -- the unregistered column is a float ``NaN`` and the read path's own ``is not None`` dereferences it |
| 5 | retention drops the errored row's trace too | P7-7, and K6 x2, E8 x2 -- the exemption was already pinned |
| 6 | retention nulls ``trace`` and leaves ``trace_obs`` | **P7-7 alone** (its raw ``trace_obs`` clause) |
| 7 | no empty envelope attached under active capture | **P7-8 alone** |
| 8 | an invalid ``meta["trace"]`` raises in ``append`` | P7-9 (fixture error), and 13 older tests plus 10 fixture errors across K6, E8, C7, T30, I19, R1-R4, the M4 store oracle and V7 |
| 9 | ``trace="none"`` keeps a pre-A7 row's ``meta["trace"]`` (Q7 refused) | **P7-3 alone** |
| 10 | ``read(meta=False, trace="full")`` silently ``"none"`` (Q4 (c)) | **P7-1 alone** |
| 11 | the envelope read decodes ``trace_obs`` | **P7-5 alone** |
| 12 | the read path nulls ``outcome`` on a post-A7 row whose ``trace_obs`` is non-null and outcome is ``"crash"`` | **P7-12 alone -- and A28's G17 stays green**, which is section 3.8's claim measured: a pre-A7 pair cannot see a change that reaches only the new layout |

**Why every test here is red on the bare tree, including the two preservation invariants.**
P7-10 (every verb's bytes unchanged) and P7-12 (the digest unchanged) are claims about a store in
the **post-A7 layout**; on the bare tree ``Store.append`` writes the old layout and both would be
green for nothing. So each asserts its precondition first -- the parts it wrote carry the two
columns -- the S29 W11 lesson (assert the flag exists before asserting how it refuses), and P7-1
asserts ``trace`` is a parameter of ``Store.read`` before asserting how Q4's refusal reads.

**Step zero, measured at ``93bfa13`` on pyarrow 25.0.1, pandas 2.3.3 (spec section 7.4).**
(1) ``pq.read_table(part, schema=<thirteen + trace + trace_obs>)`` on both parts of the pre-A7 pair then committed
**fills the two missing columns with nulls and does not raise**, in every projection form the
reader uses -- no ``columns=``, all fifteen, the eleven non-meta, ``["trace"]`` alone, and with a
``config_hash in`` filter -- and the reverse read of a fifteen-column part under the thirteen-field
schema drops the extras; the per-schema fallback the spec's trap 1 names is **not needed**, and
P7-3's mixed run is the guard that this holds beyond that pair. (2) The agreement digest on A28's
crossed P shape (5 cells, N = 32, ``(4, 20, 2)``), stored once through the shipped writer and once
in a hand-written post-A7 layout and read through the **shipped** reader, is **identical by string
identity** in all four cells -- ``b6daa2f1...`` at K = 1 and ``83dcc3d9...`` at K = 2, the same value
under ``fisher_bh`` and ``mcnemar_bh`` -- and both renderers accept a tree grown on one layout
against a diff computed on the other; those are ``CROSSED_AGREEMENT`` below, pinned so P7-12 asserts
a value and not only an equality. (3) C28: ``append`` of the same batch twice is refused whole with
``DuplicateEpisode`` and the run gains no duplicate key; ``append`` of a batch overlapping the run on
two of four keys is refused whole and **the two fresh keys are lost**; no ``.tmp`` part is left
behind. Filed to C28's row, not to an invariant here.

**Fixture limits, stated rather than left to be rediscovered** (spec section 6):

- **The lattice pair** (``tests/lattice.py``, generated by the suite in the pre-A7 layout and
  checked by digest on every use) is never rewritten. It carries P7-1's thirteen and eleven,
  P7-10's verbs and P7-12's reference digests through the fallback read only; it can say nothing
  about the split.
- **F1**, ``write_pre_a7_part`` -- the checked-in pre-A7 writer, emitting the lattice part's own on-disk schema
  through ``pyarrow`` -- is the load-bearing helper: P7-3's mixed run and P7-12's first copy are
  both built on it, and it is the only thing in the repo that can write the old layout once
  ``_SCHEMA`` has moved. It cannot express the post-A7 layout, by construction.
- **The observation trace** (``observation_trace``) carries every class of A6 section 3.3's table
  -- prompt/completion under the GenAI, Traceloop, OpenInference-flattened and older-GenAI
  spellings, ``input.value``/``output.value`` on an ``llm`` span and on a ``tool`` span, the two
  tool-call keys, and ``proofload.logprobs`` -- beside non-observation attributes on every span and
  one span with no observation at all. It cannot express truncation or the over-limit class: both
  are A8b's and do not exist at A7.
- **The mock quickstart pair** is stored at test time and its run ids are minted from the clock, so
  its bytes cannot be pinned here; P7-10 checks the **lattice pair's** verbs as facts and asserts the mock pair's verbs exit
  0 with the shapes the M4 and M10 oracles pin. The mock pair's byte identity against the dispatch
  commit is Session B's by-hand acceptance item (spec section 9, section 11).
- **The capture-active runs** (F3) run ``run_local`` in a forked child, as the M3 capture oracle
  does, because ``install()`` is once per process and claims the global provider. They cannot
  express the Modal row builder; A9's P9-6 fixture does.
- **P7-5's poisoned run** is a post-A7 run whose ``meta`` and ``trace_obs`` cells were rewritten in
  place after ``Store.append`` wrote them; it says nothing about a pre-A7 part, where the envelope
  can only come from ``meta`` (spec section 3.5).

**What the spec types and A6 lists disagree on, pinned behaviourally.** Spec section 2 types
``OBSERVATION_KEYS`` as ``frozenset[str]``; A6 section 3.3's table has four **prefix** rows
(``gen_ai.prompt.*``, ``gen_ai.completion.*``, ``llm.input_messages.*``, ``llm.output_messages.*``)
that no membership test can express. This oracle pins the eight exact keys and ``LOGPROBS_KEY`` as
members, and pins the prefixed keys **by what the split does to them** -- moved to ``trace_obs``
under the same key, absent from the envelope -- leaving the representation to the build. Reported
as a finding in the freeze's devlog entry.

Restated rather than imported, as every frozen oracle's helpers are: the M4 record shape, the M3
capture oracle's forked child, A28's crossed cells and store writer, the CLI runner.
"""

from __future__ import annotations

import ast
import hashlib
import html
import importlib
import inspect
import json
import math
import multiprocessing
import re
import traceback
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import lattice
import poisson_prove
import poisson_prove.cli as cli
import poisson_prove.store as store_module
import poisson_prove.trace as trace_module
from poisson_prove import diff as diff_mod
from poisson_prove.diff import MultiDiffResult, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.examples.mock_agent import rollout, rollout_patched
from poisson_prove.executor import plan, run_local
from poisson_prove.report import ReportSpec, build_multi_report
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import OTEL_SEMCONV_VERSION, Span, Trace
from poisson_prove.tree import agreement_digest
from poisson_prove.tree import tree as grow_tree

MODULE = __name__
PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parents[1]
SRC = REPO / "src" / "poisson_prove"
LATTICE_ROOT = lattice.root()
# PF2 (spec section 4.3): every run has a name (target id up to its first "/", the UTC date of
# created_at, a letter); serve names the lattice runs by these (``lattice.NAME_A``, ``lattice.NAME_B``).
LATTICE_PART = LATTICE_ROOT / lattice.RUN_A / "episodes" / "part-00000.parquet"

# ---------- the literals (spec sections 2, 3.1, 3.3, 3.8, 7.4) ----------

THIRTEEN = [
    "run_id", "config_hash", "config", "seed", "replicate_index", "outcome", "t", "horizon",
    "confidence", "meta", "error", "wall_time", "backend_meta",
]
ELEVEN = [c for c in THIRTEEN if c not in ("meta", "backend_meta")]
TRACE_COLUMNS = ["trace", "trace_obs"]
# PF4 re-freeze (PF4.38, reading R5): the store copies a rollout's meta["case_id"] into its own
# nullable string column, appended after trace_obs (schema_version stays 1; older parts read it as
# null), and Store.read returns it by default, so every read frame gains it at the end (before the
# envelope's decoded trace) and every part written now carries it last.
CASE_COLUMN = ["case_id"]
READ_THIRTEEN = THIRTEEN + CASE_COLUMN
READ_ELEVEN = ELEVEN + CASE_COLUMN
POST_A7_PART = THIRTEEN + TRACE_COLUMNS + CASE_COLUMN
MODES = ("full", "envelope", "none")
#: A6 section 3.3's exact members. ``input.value``/``output.value`` are members whatever the span's
#: ``kind``; the kind decides the *class* (prompt/completion on ``llm``, tool observation
#: otherwise), not the membership.
OBSERVATION_KEY_LITERALS = frozenset({
    "gen_ai.input.messages", "gen_ai.output.messages",
    "traceloop.entity.input", "traceloop.entity.output",
    "input.value", "output.value",
    "gen_ai.tool.call.arguments", "gen_ai.tool.call.result",
    "poisson_prove.logprobs",
})
LOGPROBS_KEY_SPEC = "poisson_prove.logprobs"
#: A6 section 3.3's four prefix rows; a key under any of them is an observation value.
OBSERVATION_PREFIXES = ("gen_ai.prompt.", "gen_ai.completion.", "llm.input_messages.", "llm.output_messages.")
PREFIXED_KEYS = tuple(prefix + "0.content" for prefix in OBSERVATION_PREFIXES)
#: Attributes that are not observation content and must stay in the envelope.
PLAIN_KEYS = ("attempts", "otel.trace_id", "poisson_prove.run_id", "tool.retries")
TRACE_KEYS = frozenset({"schema", "source", "source_version", "dropped", "spans", "truncated", "alias_map_version"})  # A8a: the seventh key
SPAN_KEYS = frozenset({
    "span_id", "parent_id", "kind", "name", "start_ns", "end_ns",
    "input", "output", "tokens", "confidence", "error", "code", "attrs",
    # A8a: the eight verdict fields (spec A8a section 3.1)
    "operation", "step_name", "outcome", "outcome_by", "attempt", "gate", "truncated", "bytes_original",
})
KINDS_SPEC = ("llm", "tool", "retrieval", "db", "http", "agent", "other")
SCHEMA_SPEC = "poisson-prove.trace/1"
EPOCH = 1_756_900_000_000_000_000
POISON = "not json"

#: G17's schema tag (``tree.AGREEMENT_SCHEMA``, A28 section 3.2), and the one the 0.0.1 builds
#: hashed behind before PF0 Session A (Q4) renamed it.
AGREEMENT_SCHEMA = "poisson-prove.agreement/1"
OLD_AGREEMENT_SCHEMA = "proofload.agreement/1"
#: The lattice pair's events at K = 1 and K = 2.
LATTICE_EVENTS = {1: (lattice.EVENT,), 2: (lattice.EVENT, lattice.OTHER)}


def reference_agreement(events: Sequence[str], schema: str = AGREEMENT_SCHEMA) -> str:
    """G17's digest of the lattice pair, restated from A28 section 3.2 and not from ``tree.py``:
    one line per ``(event, cell)``, ``[event, config_hash, n_a, n_b, events_a, events_b]`` from the
    design's counts (``lattice.counts``), the lines sorted, ``[schema, lines]`` as compact ASCII
    JSON, sha256, lowercase hex; the same under every method, through the fallback read of a
    pre-A7 store."""
    lines = sorted(
        [str(event), r["config_hash"], int(r["n_a"]), int(r["n_b"]), int(r["events_a"]), int(r["events_b"])]
        for event in events
        for r in lattice.counts(event)
    )
    return hashlib.sha256(json.dumps([schema, lines], separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


#: Step zero item 2: A28's crossed P shape at ``93bfa13`` through the shipped writer, K = 1 and
#: K = 2, the same value under both methods. P7-12 asserts both layouts equal these.
# Re-minted by PF0 Session A (Q4): the schema string behind the agreement form is renamed. Computed on
# the 0.0.1 tree (98dc6af) with that one string changed, through this file's own crossed-store
# fixture; the same code with the old string gives the old values (b6daa2f1..., 83dcc3d9...).
CROSSED_AGREEMENT = {
    1: "f57096cddf8e00b356ad1949f848e1e7e411aa22fa1b3885100e6fab43158cb1",
    2: "d45463a2d5c94fc6093134f80765949838f509f7a4d1857468e486e16195e93f",
}
HEX64_LEN = 64

# ---------- A28's crossed store, restated ----------

NON_EVENTS = frozenset({"ok"})
EVENT_T = 2.0
HORIZON = 5.0
SALT = "a28-salt"
TYPES = {"task": "categorical", "temp": "continuous"}
EVENTS = ("fail", "crash")
N = 32
PERMUTATIONS = 300
SEED = 0
Q = 0.05

# ---------- the mock quickstart pair for P7-10 ----------

MOCK_ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
MOCK_PATCHED = "poisson_prove.examples.mock_agent:rollout_patched"
MOCK_SALT = "a7-storage-oracle"
MOCK_CONFIGS = [
    {"task_id": task, "tool_fail_rate": rate}
    for task in ("search", "checkout")
    for rate in (0.0, 0.5)
]
MOCK_REPLICATES = 8
MOCK_BATCH = 5
MOCK_EVENT = "violated"
STORE_PLACEHOLDER = "<store>"
OUT_PLACEHOLDER = "<out>"
#: P7-10. Every verb on the pre-A7 pair at ``93bfa13``, in-process through ``cli.main``, stdout digested after
#: the store root (``runs``, ``serve --json``'s ``pair.store_root``) and the ``--out`` directory
#: (``report``) are normalised. ``inspect`` and ``diff`` echo no path. Measured by
#: ``lattice_verb_digests`` below on the dispatch commit; a later commit that moves one of these has
#: changed what a consumer sees.
# Re-minted 2026-09-20 (truncation surfacing): five values move -- report A/report.md, report A/receipt.html, report A B/report.md,
# report A B/receipt.html and serve --json -- because the provenance list gains the horizon rename and the observation
# lines and the structure is proofload.viewpair/5. Each is the baseline's output plus that change, byte for byte; the
# other nine are unchanged.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): three of the fourteen move: both 'report A B' files, whose Cells section prints LS16's respelled sentence ('MDE is the smallest detectable increase', no ADR number), and 'serve --json', which is proofload.viewpair/6 with the summary key and each panel's mde_unchanged. The other eleven are unchanged. Read through this test's own measurement on the built tree, not predicted.
# The front door's look (spec sections 5.3, 5.4 and 14) changes every other verb's output on the pre-A7 pair (rule 10 numbers,
# 12-hex hashes, check's verdict line, --json for --format json), so those thirteen digests are gone and
# ``assert_lattice_verb_facts`` checks the facts they guarded instead.
# PF4 (PF4.3, PF4.11, PF4.13 to PF4.20): the page structure inside serve --json changes too (no
# ``pair.store_root``, the cells' shares, directions and notes, the Summary's verdict and direction
# words), so its digest is no longer asserted either; ``assert_lattice_verb_facts`` checks the facts it
# guarded against ``diff --json`` and the store.
SNIPPET_MARKER = "# reproduce one episode"


# ---------- helpers: the M4 oracle's record shape ----------


def manifest(run_id: str, **kw: Any) -> RunManifest:
    base: dict[str, Any] = dict(
        run_id=run_id, target_id="policy@abc123", t_unit="steps", run_salt="a7-salt",
        axis_types={"x": "continuous"}, backend="local", environment={"note": "built by a7 session a"},
    )
    base.update(kw)
    return RunManifest(**base)


def rec(
    run_id: str,
    *,
    x: float,
    k: int,
    outcome: str = "fell",
    t: float = 3.0,
    meta: Mapping[str, Any] | None = None,
) -> EpisodeRecord:
    ep = Episode(outcome=outcome, t=t, horizon=10.0, meta={} if meta is None else dict(meta))
    return EpisodeRecord.from_episode(
        ep, run_id=run_id, config={"x": x}, seed=1000 * int(x * 10) + k, replicate_index=k,
        wall_time=0.1, backend_meta={"i": k},
    )


def errored(run_id: str, *, x: float, k: int, meta: Mapping[str, Any] | None = None) -> EpisodeRecord:
    return EpisodeRecord.errored(
        run_id=run_id, config={"x": x}, seed=1000 * int(x * 10) + k, replicate_index=k,
        error="boom", wall_time=0.2, backend_meta={"i": k}, meta=meta,
    )


def canonical(trace: Mapping[str, Any]) -> str:
    return json.dumps(trace, sort_keys=True)


# ---------- helpers: traces ----------


def span(
    i: int,
    *,
    kind: str = "tool",
    parent: str | None = None,
    input: Any = None,
    output: Any = None,
    attrs: Mapping[str, Any] | None = None,
) -> Span:
    return Span(
        span_id=f"{i:016x}", parent_id=parent, kind=kind, name=f"step-{i}",
        start_ns=EPOCH + i * 1_000_000, end_ns=EPOCH + i * 1_000_000 + 500_000,
        input=input, output=output, attrs={} if attrs is None else dict(attrs),
    )


def observation_trace(seed: int) -> Trace:
    """Every class of A6 section 3.3's table on some span, beside plain attributes, plus one span
    with no observation at all and one child span. What it cannot express: truncation and the
    over-limit class (A8b's)."""
    llm = span(
        0, kind="llm", input={"messages": [{"role": "user", "content": f"q{seed}"}]}, output={"text": f"a{seed}"},
        attrs={
            "gen_ai.input.messages": [{"role": "user", "content": f"q{seed}"}],
            "gen_ai.output.messages": [{"role": "assistant", "content": f"a{seed}"}],
            "gen_ai.prompt.0.content": f"prompt {seed}",
            "gen_ai.completion.0.content": f"completion {seed}",
            "llm.input_messages.0.content": f"in {seed}",
            "llm.output_messages.0.content": f"out {seed}",
            "input.value": f"iv {seed}",
            "output.value": f"ov {seed}",
            "poisson_prove.logprobs": [[-0.1, -2.3], [-0.5]],
            "attempts": 1,
            "otel.trace_id": f"{seed:032x}",
        },
    )
    tool = span(
        1, kind="tool", parent=llm.span_id, input={"query": seed}, output={"rows": [seed, seed + 1]},
        attrs={
            "gen_ai.tool.call.arguments": {"query": seed},
            "gen_ai.tool.call.result": {"rows": [seed, seed + 1]},
            "input.value": {"query": seed},
            "output.value": None,
            "traceloop.entity.input": f"ti {seed}",
            "traceloop.entity.output": f"to {seed}",
            "tool.retries": 0,
            "poisson_prove.run_id": "r",
        },
    )
    plain = span(2, kind="tool", attrs={"attempts": 2})
    return Trace(spans=(llm, tool, plain), source="record")


def mock_style_trace(k: int) -> Trace:
    """The mock quickstart's shape: root tool spans, no observation value, one plain attribute
    (the mock itself emits ``attrs={"tries": n}`` since A8a; this fixture's key is its own)."""
    return Trace(spans=tuple(span(i, attrs={"attempts": 1 + (i + k) % 2}) for i in range(3)), source="record")


def observation_values(trace: Trace) -> dict[str, dict[str, Any]]:
    """What the split must move, keyed by span id: ``input``, ``output`` and every observation
    attribute, exact members and prefixed keys alike."""
    out: dict[str, dict[str, Any]] = {}
    for s in trace.spans:
        body: dict[str, Any] = {}
        if s.input is not None:
            body["input"] = s.input
        if s.output is not None:
            body["output"] = s.output
        attrs = {k: v for k, v in s.attrs.items() if is_observation_key(k)}
        if attrs:
            body["attrs"] = attrs
        if body:
            out[s.span_id] = body
    return out


def is_observation_key(key: str) -> bool:
    return key in OBSERVATION_KEY_LITERALS or any(key.startswith(p) for p in OBSERVATION_PREFIXES)


# ---------- helpers: the on-disk layouts ----------


def parts_of(store: Store, run_id: str) -> list[Path]:
    return sorted((Path(store._root) / run_id / "episodes").glob("part-*.parquet"))


def raw_column(store: Store, run_id: str, column: str) -> dict[tuple[str, int], Any]:
    """One stored column exactly as written, keyed by ``(config_hash, replicate_index)``, read
    raw through ``pyarrow`` so a null is ``None`` on every pandas. A part lacking the column
    contributes ``None`` for every row."""
    out: dict[tuple[str, int], Any] = {}
    for part in parts_of(store, run_id):
        names = pq.read_schema(part).names
        wanted = ["config_hash", "replicate_index"] + ([column] if column in names else [])
        table = pq.read_table(part, columns=wanted)
        values = table.column(column).to_pylist() if column in names else [None] * table.num_rows
        for h, k, v in zip(table.column("config_hash").to_pylist(), table.column("replicate_index").to_pylist(), values, strict=True):
            out[(str(h), int(k))] = v
    return out


def raw_meta_keys(store: Store, run_id: str) -> dict[tuple[str, int], set[str]]:
    return {key: set(json.loads(text)) for key, text in raw_column(store, run_id, "meta").items()}


def write_pre_a7_part(store: Store, run_id: str, records: Sequence[EpisodeRecord]) -> Path:
    """F1: the checked-in pre-A7 writer. Emits one part in the lattice pair's own on-disk schema --
    thirteen fields, read off the generated pre-A7 part rather than spelled here -- with ``meta["trace"]``
    left inside ``meta`` exactly as the record carries it. The run must already exist; the part
    is numbered after any part already present so ``Store._parts`` sees it."""
    schema = pq.read_schema(LATTICE_PART)
    assert schema.names == THIRTEEN, schema.names
    rows = []
    for r in records:
        rows.append({
            "run_id": r.run_id, "config_hash": r.config_hash,
            "config": json.dumps({k: float(v) if isinstance(v, int | float) and not isinstance(v, bool) else v for k, v in r.config.items()}, sort_keys=True, separators=(",", ":")),
            "seed": int(r.seed), "replicate_index": int(r.replicate_index), "outcome": r.outcome,
            "t": None if r.t is None else float(r.t), "horizon": None if r.horizon is None else float(r.horizon),
            "confidence": None if r.confidence is None else float(r.confidence),
            "meta": json.dumps(dict(r.meta), sort_keys=True, separators=(",", ":")), "error": r.error,
            "wall_time": float(r.wall_time),
            "backend_meta": json.dumps(dict(r.backend_meta), sort_keys=True, separators=(",", ":")),
        })
    existing = parts_of(store, run_id)
    index = 0 if not existing else int(existing[-1].name[len("part-"):-len(".parquet")]) + 1
    path = Path(store._root) / run_id / "episodes" / f"part-{index:05d}.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    return path


def poison_cells(part: Path, columns: Sequence[str]) -> None:
    """Rewrite ``part`` in place with ``POISON`` in every cell of ``columns``, keeping the part's
    own schema (the M4 oracle's move, one column wider)."""
    table = pq.read_table(part)
    for column in columns:
        index = table.schema.get_field_index(column)
        table = table.set_column(index, table.schema.field(index), pa.array([POISON] * table.num_rows, pa.string()))
    pq.write_table(table, part)


def keys_of(frame: pd.DataFrame) -> list[tuple[str, int]]:
    return [(str(h), int(k)) for h, k in zip(frame["config_hash"], frame["replicate_index"], strict=True)]


def rows_by_key(frame: pd.DataFrame) -> dict[tuple[str, int], Any]:
    return dict(zip(keys_of(frame), frame.itertuples(index=False), strict=True))


# ---------- helpers: A28's crossed pair, restated ----------


def a28_manifest(run_id: str) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=SALT,
        axis_types=dict(TYPES), backend="synthetic", environment={"note": "built by a7 session a"},  # type: ignore[arg-type]
    )


def crossed_cells(n_fail_a: int, n_fail_b: int, n_crash: int, n_cells: int = 5) -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    a: dict[Any, list[str]] = {}
    b: dict[Any, list[str]] = {}
    for i in range(n_cells):
        key = (("task", f"t{i}"), ("temp", 0.0))
        a[key] = ["fail"] * n_fail_a + ["crash"] * n_crash + ["ok"] * (N - n_fail_a - n_crash)
        b[key] = ["fail"] * n_fail_b + ["crash"] * n_crash + ["ok"] * (N - n_fail_b - n_crash)
    return a, b


def crossed_records(run_id: str, cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]]) -> list[EpisodeRecord]:
    """One episode per outcome, each carrying an observation trace, so the second copy's split has
    something to move."""
    records = []
    for index, (key, outcomes) in enumerate(cells.items()):
        for k, outcome in enumerate(outcomes):
            t = HORIZON if outcome in NON_EVENTS else EVENT_T
            records.append(EpisodeRecord.from_episode(
                Episode(outcome=outcome, t=t, horizon=HORIZON, meta={"trace": observation_trace(1000 * index + k).to_dict(), "k": k}),
                run_id=run_id, config=dict(key), seed=1000 * index + k, replicate_index=k, wall_time=0.0,
            ))
    return records


@dataclass(frozen=True)
class Grown:
    a: str
    b: str
    frames: tuple[pd.DataFrame, pd.DataFrame]
    manifests: tuple[RunManifest, RunManifest]
    multi: MultiDiffResult
    result: Any


def grown(store: Store, a: str, b: str, *, events: Sequence[str], method: str) -> Grown:
    """``(multi, tree)`` the way the CLI reaches them: frames read ``meta=False``."""
    fa, fb = store.read(a, meta=False), store.read(b, meta=False)
    ma, mb = store.manifest(a), store.manifest(b)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        multi = multi_diff(fa, fb, events=list(events), method=method, q=Q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]
    result = grow_tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, n_permutations=PERMUTATIONS, seed=SEED)
    return Grown(a, b, (fa, fb), (ma, mb), multi, result)


def render_both(store: Store, g: Grown, tree: Any) -> None:
    """Both renderers' ``_check_tree`` through their public builders: a refusal raises."""
    import poisson_prove.viewer as viewer

    spec = ReportSpec(title=f"{g.a} vs {g.b}", x_axis="task", y_axis="temp", fixed={})
    report = build_multi_report(g.multi, spec, manifests=g.manifests, tree=tree)
    viewer.build_structure(
        report, g.multi, tree=tree, manifest_a=g.manifests[0], manifest_b=g.manifests[1],
        rows_a=store.count(g.a), rows_b=store.count(g.b), tally_a=store.tally(g.a), tally_b=store.tally(g.b),
        store_root=str(store._root),
    )


# ---------- helpers: the CLI ----------


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: Sequence[str]) -> Result:
    out, err = StringIO(), StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_0_0_1_wrote_it(text: str) -> str:
    """PF0 (Q4, section 2.3): the one field the rename changes in a rendered report, receipt or page
    is the version in its provenance list. First assert it is there as the rename writes it -- one
    ``Prove version:`` entry and no ``proofload version:`` -- then put it back as 0.0.1 wrote it and
    drop any separate ``written by proofload`` entry, so the frozen digest still guards every other
    byte."""
    found = re.findall(r"(?m)^- Prove version: [^\n]*$", text) + re.findall(r"<li>Prove version: [^<]*</li>", text)
    assert len(found) == 1 and "proofload version:" not in text, found
    text = re.sub(r"(?m)^- Prove version: [^\n]*$", "- proofload version: 0.0.1", text)
    text = re.sub(r"<li>Prove version: [^<]*</li>", "<li>proofload version: 0.0.1</li>", text)
    text = re.sub(r"(?m)^- [^\n]*written by proofload[^\n]*\n", "", text)
    return re.sub(r"<li>[^<]*written by proofload[^<]*</li>", "", text)


def structure_as_ids_named_it(structure: dict[str, Any], events: str) -> dict[str, Any]:
    """PF2 (spec section 4.3): ``serve --json`` on the lattice pair moves in two places only: ``run_name`` beside
    each arm's ``run_id``, and the default title, which names the runs by name (``view.title`` and
    the figure's title line). First assert each is there as PF2 writes it and nowhere else the
    digest reads, then put the structure back as it was before names (no ``run_name``, the title by
    id) so the frozen digest still guards everything else."""
    arms = {}
    for role, run_id, name in (("a", lattice.RUN_A, lattice.NAME_A), ("b", lattice.RUN_B, lattice.NAME_B)):
        arm = structure["pair"][role]
        keys = list(arm)
        assert (arm["run_id"], arm.get("run_name")) == (run_id, name), arm
        assert keys.index("run_name") == keys.index("run_id") + 1, keys
        arms[role] = {k: v for k, v in arm.items() if k != "run_name"}
    named, by_id = f"{lattice.NAME_A} vs {lattice.NAME_B}: {events}", f"{lattice.RUN_A} vs {lattice.RUN_B}: {events}"
    assert structure["view"]["title"] == named, structure["view"]["title"]
    line = f'font-size="13">{named}</text>'
    assert structure["heatmap_svg"].count(line) == 1, structure["heatmap_svg"][:600]
    return {
        **structure,
        "pair": {**structure["pair"], **arms},
        "view": {**structure["view"], "title": by_id},
        "heatmap_svg": structure["heatmap_svg"].replace(line, f'font-size="13">{by_id}</text>'),
    }


def structure_as_0_0_1_wrote_it(structure: dict[str, Any]) -> dict[str, Any]:
    """PF0 (Q4, Q10): the page structure's schema string and its version key, in both arms and in the
    provenance block. First assert they are there as the rename writes them, then put them back as
    0.0.1 wrote them before the frozen digest is taken."""
    assert structure["schema"] == "poisson-prove.viewpair/7", structure["schema"]
    for arm in ("a", "b"):
        assert "poisson_prove_version" in structure["pair"][arm] and "proofload_version" not in structure["pair"][arm], arm
    assert "poisson_prove_version" in structure["diff"] and "proofload_version" not in structure["diff"]
    arms = {
        arm: {("proofload_version" if key == "poisson_prove_version" else key): value for key, value in structure["pair"][arm].items()}
        for arm in ("a", "b")
    }
    diff = {key: value for key, value in structure["diff"].items() if key != "poisson_prove_version"}
    return {
        **structure, "schema": "proofload.viewpair/6", "pair": {**structure["pair"], **arms},
        "diff": {**diff, "proofload_version": "0.0.1"},
    }


def verb_digests(root: Path, a: str, b: str, *, event: str, x: str, y: str, out_dir: Path, method: tuple[str, ...] = ()) -> tuple[dict[str, str], dict[str, Result]]:
    """Every verb the spec names, on one stored pair, exit codes kept and stdout digested with the
    store root and the ``--out`` directory normalised."""
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): ``method`` is appended to every verb that compares the
    # two runs (diff, check, report A B, serve), so a caller can name the method its numbers were frozen under.
    store_arg = str(root)
    results: dict[str, Result] = {}
    digests: dict[str, str] = {}

    def norm(text: str, out: Path | None = None) -> str:
        text = text.replace(store_arg, STORE_PLACEHOLDER)
        return text if out is None else text.replace(str(out), OUT_PLACEHOLDER)

    results["runs"] = r = run_cli(["--store", store_arg, "runs"]); digests["runs"] = sha256_text(norm(r.out))
    results["diff"] = r = run_cli(["--store", store_arg, "diff", a, b, "--event", event, *method]); digests["diff"] = sha256_text(norm(r.out))
    # diff's --format json is now --json (spec section 5.3).
    results["diff --json"] = r = run_cli(["--store", store_arg, "diff", a, b, "--event", event, "--json", *method])
    # PF0 (Q4): the tree's agreement digest is hashed behind the renamed schema string; the 0.0.1 value
    # is put back before the frozen digest is taken.
    as_0_0_1 = norm(r.out)
    if root == LATTICE_ROOT:
        assert reference_agreement(LATTICE_EVENTS[1]) in as_0_0_1
        assert reference_agreement(LATTICE_EVENTS[1], OLD_AGREEMENT_SCHEMA) not in as_0_0_1
        for events in LATTICE_EVENTS.values():
            as_0_0_1 = as_0_0_1.replace(reference_agreement(events), reference_agreement(events, OLD_AGREEMENT_SCHEMA))
    digests["diff --json"] = sha256_text(as_0_0_1)
    # PF4 (PF4.20): neither pair's event carries a kind, so check's default --fail-on worse is refused;
    # --fail-on higher is the same gate (fail when a rate rose).
    results["check"] = r = run_cli(["--store", store_arg, "check", a, b, "--event", event, "--fail-on", "higher", *method]); digests["check"] = sha256_text(norm(r.out))
    for label, runs in (("report A", [a]), ("report A B", [a, b])):
        out = out_dir / label.replace(" ", "_")
        results[label] = r = run_cli(["--store", store_arg, "report", *runs, "--event", event, "--x", x, "--y", y, "--out", str(out), *(method if len(runs) == 2 else ())])
        digests[label] = sha256_text(norm(r.out, out))
        for name in ("report.md", "heatmap.svg", "receipt.html"):
            if not (out / name).is_file():
                digests[f"{label}/{name}"] = ""
            elif name == "heatmap.svg":
                digests[f"{label}/{name}"] = sha256_file(out / name)
            else:
                digests[f"{label}/{name}"] = sha256_text(as_0_0_1_wrote_it((out / name).read_text(encoding="utf-8")))
    results["serve --json"] = r = run_cli(["--store", store_arg, "serve", a, b, "--event", event, "--x", x, "--y", y, "--json", *method])
    try:
        # serve --json now leads with verdict and sentence before the page structure (spec section 5.6).
        # PF3 (spec section 4.4, R3): it also adds method and method_chosen right after sentence; neither
        # is the page structure the kept digest guards, so they are dropped as verdict and sentence are.
        structure = {k: v for k, v in json.loads(r.out).items() if k not in ("verdict", "sentence", "method", "method_chosen")}
        # PF4 (PF4.11): the structure no longer carries the store's absolute path, so there is nothing to
        # normalise.
        assert "store_root" not in structure["pair"], structure["pair"]
        if root == LATTICE_ROOT:
            # PF2 (spec section 4.3): run_name beside each arm's run_id and the title by name are
            # asserted, then put back as before names, so the kept digest still guards the rest.
            structure = structure_as_ids_named_it(structure, event)
        as_0_0_1 = json.dumps(structure_as_0_0_1_wrote_it(structure), sort_keys=True)
        if root == LATTICE_ROOT:
            assert reference_agreement(LATTICE_EVENTS[1]) in as_0_0_1
            assert reference_agreement(LATTICE_EVENTS[1], OLD_AGREEMENT_SCHEMA) not in as_0_0_1
            for events in LATTICE_EVENTS.values():
                as_0_0_1 = as_0_0_1.replace(reference_agreement(events), reference_agreement(events, OLD_AGREEMENT_SCHEMA))
        digests["serve --json"] = sha256_text(as_0_0_1)
    except (ValueError, KeyError, TypeError):
        digests["serve --json"] = ""
    results["inspect"] = r = run_cli(["--store", store_arg, "inspect", a, "--event", event]); digests["inspect"] = sha256_text(norm(r.out))
    return digests, results


def lattice_verb_digests(out_dir: Path) -> tuple[dict[str, str], dict[str, Result]]:
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the lattice runs share a salt, so the default is the paired
    # test; the facts are the unpaired test's, named.
    return verb_digests(LATTICE_ROOT, lattice.RUN_A, lattice.RUN_B, event=lattice.EVENT, x=lattice.X, y=lattice.Y, out_dir=out_dir, method=("--method", "fisher_bh"))


# ---------- helpers: the facts the verb output digests guarded, on the lattice pair ----------

REPORT_NAMES = ("report.md", "heatmap.svg", "receipt.html")
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:e[-+]?\d+)?")
PAIR_RE = re.compile(r"(\w+)=(-?\d+(?:\.\d+)?)")


def err_lines(r: Result) -> list[str]:
    """stderr without the ``note: `` lines Prove's own warnings become (spec section 5.4)."""
    return [line for line in r.err.splitlines() if not line.startswith("note: ")]


def finite_number(text: str) -> float | None:
    try:
        value = float(text.strip().replace(",", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def printed_as(text: str, value: Any) -> bool:
    """Whether ``text`` is ``value`` as a text output prints it, whatever the number format: an int
    exactly (separators allowed), a float to the precision printed, a hash by a prefix of at least
    12 hex characters, a bool or string as itself, and a missing or non-finite number as anything
    but a finite number."""
    text = text.strip()
    if isinstance(value, bool):
        return text.lower() == str(value).lower()
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return finite_number(text) is None
    if isinstance(value, int):
        return text.replace(",", "") == str(value)
    if isinstance(value, float):
        number = finite_number(text)
        if number is None:
            return False
        mantissa, _, exponent = text.lower().replace(",", "").partition("e")
        half_unit = 0.5 * 10.0 ** -len(mantissa.partition(".")[2]) * 10.0 ** (int(exponent) if exponent else 0)
        return abs(number - value) <= half_unit * (1 + 1e-9) + 1e-12
    if isinstance(value, str):
        return text == value or (len(text) >= 12 and value.startswith(text))
    return False


def md_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every Markdown table as (header, data rows), cells stripped, separator rows dropped."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    block: list[list[str]] = []
    for line in [*text.splitlines(), ""]:
        if line.startswith("|"):
            block.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif block:
            rows = [row for row in block[1:] if not all(set(cell) <= set("-:") for cell in row)]
            tables.append((block[0], rows))
            block = []
    return tables


def html_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every HTML table as (header, data rows), tags inside cells removed and entities unescaped."""
    def cells(fragment: str, tag: str) -> list[str]:
        return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", fragment, re.S)]

    tables = []
    for table in re.findall(r"<table[^>]*>(.*?)</table>", text, re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
        header = cells(rows[0], "th") if rows else []
        tables.append((header, [cells(row, "td") for row in rows[1:]]))
    return tables


def config_of(pairs: str) -> dict[str, float]:
    return {k: float(v) for k, v in PAIR_RE.findall(pairs)}


def cell_by_config(cells: Mapping[str, Mapping[str, Any]], config: Mapping[str, float]) -> Mapping[str, Any]:
    (found,) = [c for c in cells.values() if {k: float(v) for k, v in c["config"].items()} == dict(config)]
    return found


def check_report_table(header: list[str], rows: list[list[str]], data: Mapping[str, Any]) -> str:
    """Check one table of the A B report (Markdown or receipt) against ``diff --json`` and say which
    table it was. Columns are matched by the names the report has always printed them under."""
    event_diff = data["by_event"][lattice.EVENT]
    cells = {c["config_hash"]: c for c in event_diff["cells"]}
    omnibus, fault_lines = data["omnibus"], data["tree"]["fault_lines"]
    assert rows, header
    if header and header[0] == "event" and "mean delta" in header:
        keys = ["event", "location", "p_location", "dispersion", "p_dispersion"]
        for row in rows:
            assert len(row) == len(keys) and row[0] == lattice.EVENT, row
            for text, key in zip(row[1:], keys[1:], strict=True):
                assert printed_as(text, omnibus[key][lattice.EVENT]), (key, text, omnibus[key])
        return "omnibus"
    if header and header[0] == data["tree"]["grouping"]["key"] and "units (a/b)" in header:
        groups = {g["label"]: g for g in fault_lines["groups"]}
        names = {"cells": "n_cells", "informative": "n_informative_cells", "unchanged by every exchange": "n_uninformative_cells",
                 "group MDE": "mde", "p": "p_group", "q": "q_group"}
        assert len(rows) == len(groups), rows
        for row in rows:
            printed = dict(zip(header, row, strict=True))
            group = groups[printed[header[0]]]
            for column, key in names.items():
                assert printed_as(printed[column], group[key]), (column, printed[column], group[key])
            units_a, units_b = printed["units (a/b)"].split("/")
            assert printed_as(units_a, group["n_a"]) and printed_as(units_b, group["n_b"]), printed
            assert (printed["verdict"] == "rejected") is group["rejects"], printed
        return "fault lines"
    if header[:2] == ["cell", "event"]:
        leaves = {c["config_hash"]: c for family in data["tree"]["leaves"]["families"] for c in family["cells"]}
        names = {"delta": "delta", "q": "q_within", "MDE": "mde"}
        assert set(names) <= set(header), header
        for row in rows:
            printed = dict(zip(header, row, strict=True))
            leaf = cell_by_config(leaves, config_of(printed["cell"]))
            assert printed["event"] == lattice.EVENT, printed
            for column, key in names.items():
                assert printed_as(printed[column], leaf[key]), (column, printed[column], leaf[key])
        return "cells"
    if lattice.X in header and lattice.Y in header:
        shared = [column for column in header if column.lower() in event_diff["cells"][0]]
        assert {"delta", "p", "q", "verdict"} <= set(shared), header
        for row in rows:
            printed = dict(zip(header, row, strict=True))
            cell = cell_by_config(cells, {lattice.X: float(printed[lattice.X]), lattice.Y: float(printed[lattice.Y])})
            for column in shared:
                if column.lower() == "mde":
                    # PF4 (PF4.15): a condition with no detection limit, or none detectable, prints its
                    # note in place of the number.
                    # PF4 re-freeze (PF4.27, PF4.32): or each direction's limit or note.
                    assert limit_printed_as(printed[column], cell), (column, printed[column], cell["mde_note"])
                    continue
                assert printed_as(printed[column], cell[column.lower()]), (column, printed[column], cell[column.lower()])
        return "worst cells"
    return "other"


def limit_printed_as(text: str, cell: Mapping[str, Any]) -> bool:
    """PF4 re-freeze (PF4.22, PF4.27, PF4.32): a printed limit is both directions, each its number or
    its note (``rise 0.568, fall: none detectable``); or one number, the condition's limit, when the
    two agree; or the condition's note alone where a table prints one figure per condition."""
    text = text.strip()
    parts = text.split(", ")
    if len(parts) == 2 and parts[0].startswith("rise") and parts[1].startswith("fall"):
        for way, part in zip(("rise", "fall"), parts, strict=True):
            value, note = cell[f"mde_{way}"], cell[f"mde_{way}_note"]
            if value is None:
                if part != f"{way}: {note}":
                    return False
            elif not (part.startswith(f"{way} ") and printed_as(part.removeprefix(f"{way} "), value)):
                return False
        return True
    if cell["mde_note"]:
        return text == cell["mde_note"]
    return printed_as(text, cell["mde"])


def check_heatmap(path: Path, cells: Mapping[str, Mapping[str, Any]], label_key: str) -> int:
    """The panel is the event; its cells are the diff's cells; each cell's label prints its value.
    Returns the number of significance markers."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    panels = [e for e in root.iter() if "data-panel" in e.attrib]
    assert [p.attrib["data-panel"] for p in panels] == [lattice.EVENT], path
    rects = [e for e in panels[0].iter() if e.tag.endswith("rect") and "data-cell" in e.attrib]
    assert sorted(r.attrib["data-cell"] for r in rects) == sorted(cells), path
    texts = [e for e in panels[0].iter() if e.tag.endswith("text")]
    for rect in rects:
        x, y, w, h = (float(rect.attrib[k]) for k in ("x", "y", "width", "height"))
        (label,) = [t for t in texts if float(t.attrib.get("x", "nan")) == x + w / 2 and y <= float(t.attrib.get("y", "nan")) <= y + h]
        value = cells[rect.attrib["data-cell"]][label_key]
        assert printed_as(label.text or "", value), (rect.attrib["data-cell"], label.text, value)
    return sum(1 for e in panels[0].iter() if "data-sig" in e.attrib)


def assert_lattice_verb_facts(results: Mapping[str, Result], out_dir: Path) -> None:
    """The facts the verb digests guarded, on the lattice pair, read against ``diff --json`` and the store: the runs and
    their counts, every cell of the diff with its numbers and verdict, check's verdict, the files
    report wrote, the report's tables, the bound and the honesty block's figure, the heatmaps' cells
    and labels, and inspect's rows."""
    store = Store(LATTICE_ROOT)
    data = json.loads(results["diff --json"].out)
    event_diff = data["by_event"][lattice.EVENT]
    cells = {c["config_hash"]: c for c in event_diff["cells"]}
    headline = data["headline"].splitlines()[0]
    # PF4 (PF4.20): the lattice's ``tripped`` carries no kind, so the JSON counts and verdicts are in direction
    # words (``lower``, ``higher``) and ``n_safer`` and ``n_worse`` are null.
    assert event_diff["kind"] is None and event_diff["n_safer"] is None and event_diff["n_worse"] is None, event_diff
    assert len(cells) == data["n_tests"] and event_diff["n_lower"] + event_diff["n_higher"] + event_diff["n_unchanged"] == len(cells)
    for verdict, key in (("lower", "n_lower"), ("higher", "n_higher"), ("unchanged", "n_unchanged")):
        assert sum(c["verdict"] == verdict for c in cells.values()) == event_diff[key], verdict

    # runs: one line per run with its status, backend, target, unit and row count.
    # PF2 (spec section 5.3): the table leads with the number and the name, so each run's row is
    # the one carrying its id, and it carries the name; the unit is no column of the table, so it
    # is read from runs --json, whose entries carry it beside the id.
    runs_lines = results["runs"].out.splitlines()
    names = {lattice.RUN_A: lattice.NAME_A, lattice.RUN_B: lattice.NAME_B}
    units = {entry["run_id"]: entry["t_unit"] for entry in json.loads(run_cli(["--store", str(LATTICE_ROOT), "runs", "--json"]).out)["runs"]}
    for run_id in (lattice.RUN_A, lattice.RUN_B):
        m = store.manifest(run_id)
        (line,) = [row for row in runs_lines if run_id in row.split()]
        assert store.count(run_id) == lattice.ROWS == 2_304
        assert names[run_id] in line and units[run_id] == m.t_unit, (line, units)
        for value in (m.status, m.backend, m.target_id, f"{lattice.ROWS:,}"):
            assert value in line.split(), (value, line)

    # diff: the headline, the method and event lines, and every cell row as the JSON has it.
    diff_lines = results["diff"].out.splitlines()
    assert headline in diff_lines, results["diff"].out
    for prefix, source in ((f"## {lattice.EVENT}: ", event_diff), ("method=", data)):
        (line,) = [row for row in diff_lines if row.startswith(prefix)]
        pairs = dict(part.split("=", 1) for part in line.removeprefix(f"## {lattice.EVENT}: ").split(", "))
        assert pairs and set(pairs) <= set(source), line
        for key, text in pairs.items():
            assert printed_as(text, source[key]), (key, text, source[key])
    (table,) = [t for t in md_tables(results["diff"].out) if "verdict" in t[0]]
    header, rows = table
    shared = [column for column in header if column in event_diff["cells"][0]]
    assert {"config_hash", "config", "verdict", "delta", "p", "q"} <= set(shared), header
    assert len(rows) == len(cells), len(rows)
    seen = set()
    for row in rows:
        printed = dict(zip(header, row, strict=True))
        (h,) = [h for h in cells if printed_as(printed["config_hash"], h)]
        seen.add(h)
        for column in shared:
            if column == "config":
                assert json.loads(printed[column]) == cells[h][column], printed
            elif column == "mde":
                # PF4 (PF4.15): a condition with no detection limit, or none detectable, prints its note
                # in place of the number.
                # PF4 re-freeze (PF4.27, PF4.32): the table prints each direction's limit or note.
                assert limit_printed_as(printed[column], cells[h]), (printed[column], cells[h]["mde_note"])
            else:
                assert printed_as(printed[column], cells[h][column]), (column, printed[column], cells[h][column])
    assert seen == set(cells)

    # check: passed, naming the event, with the same headline (spec section 5.3).
    check_lines = results["check"].out.splitlines()
    assert check_lines[0].startswith("passed") and lattice.EVENT in check_lines[0], results["check"].out
    assert headline in check_lines, results["check"].out

    # report: the files it names, the single run's incidences, the pair report's tables in both forms.
    for label in ("report A", "report A B"):
        out = out_dir / label.replace(" ", "_")
        for name in REPORT_NAMES:
            assert str(out / name) in results[label].out, (label, name)
    single = (out_dir / "report_A" / "report.md").read_text(encoding="utf-8")
    single_tables = [t for t in md_tables(single) if lattice.X in t[0] and lattice.Y in t[0]]
    assert single_tables, single
    for header, rows in single_tables:
        assert rows and header.index("n") == len(header) - 2, header
        for row in rows:
            printed = dict(zip(header, row, strict=True))
            cell = cell_by_config(cells, {lattice.X: float(printed[lattice.X]), lattice.Y: float(printed[lattice.Y])})
            assert printed_as(printed["n"], cell["n_a"]) and printed_as(row[-1], cell["rate_a"]), (row, cell)
    pair_md = (out_dir / "report_A_B" / "report.md").read_text(encoding="utf-8")
    pair_html = (out_dir / "report_A_B" / "receipt.html").read_text(encoding="utf-8")
    md_kinds = [check_report_table(h, r, data) for h, r in md_tables(pair_md)]
    html_kinds = [check_report_table(h, r, data) for h, r in html_tables(pair_html)]
    for kinds in (md_kinds, html_kinds):
        assert {"omnibus", "fault lines", "cells", "worst cells"} <= set(kinds), kinds
    md_lines = pair_md.splitlines()
    assert headline in md_lines and headline in html.unescape(pair_html)
    # The provenance list prints the diff's scalar fields.
    for line in md_lines:
        key, sep, text = line.removeprefix("- ").partition(": ")
        if line.startswith("- ") and sep and isinstance(data.get(key.replace(" ", "_")), (bool, int, float, str, type(None))) and key.replace(" ", "_") in data:
            assert printed_as(text, data[key.replace(" ", "_")]), line
    # The bound in its section, in both forms, and the honesty block's figure on the line naming its cell.
    bound = data["tree"]["bound"]
    worst = {k: float(v) for k, v in cells[event_diff["max_mde_unchanged_cell"]]["config"].items()}
    md_bound = pair_md.partition("## Bound")[2].partition("\n## ")[0]
    html_bound = pair_html.partition("<h2>Bound</h2>")[2].partition("<h2>")[0].partition("<svg")[0]
    for section, text in ((md_bound, pair_md), (html_bound, html.unescape(re.sub(r"<[^>]+>", " ", pair_html)))):
        assert any(printed_as(t, bound["bound"]) for t in NUMBER_RE.findall(section) if "." in t), section
        assert any(
            {k: v for k, v in config_of(line).items() if k in worst} == worst
            and any(printed_as(t, event_diff["max_mde_unchanged"]) for t in NUMBER_RE.findall(line.split(")", 1)[-1]) if "." in t)
            for line in text.splitlines()
        ), event_diff["max_mde_unchanged"]

    # heatmaps: one panel for the event, every cell labelled with its rate (one run) or delta (two).
    assert check_heatmap(out_dir / "report_A" / "heatmap.svg", cells, "rate_a") == 0
    # PF4 (PF4.20): the significant cells are counted in direction words.
    assert check_heatmap(out_dir / "report_A_B" / "heatmap.svg", cells, "delta") == event_diff["n_lower"] + event_diff["n_higher"]

    # PF4 (PF4.3, PF4.5, PF4.11, PF4.13 to PF4.20): the page structure, whose digest is gone, checked as
    # facts: both arms as the store has them, the headline, the diff block's fields, the one panel's
    # counts and every cell with the numbers, notes and verdict diff --json gives it, the tree's
    # agreement, and the Summary's verdict word and detection limit.
    page = json.loads(results["serve --json"].out)
    for arm, run_id in (("a", lattice.RUN_A), ("b", lattice.RUN_B)):
        assert page["pair"][arm]["run_id"] == run_id and page["pair"][arm]["rows_stored"] == store.count(run_id), arm
        assert page["pair"][arm]["tally"] == store.tally(run_id).to_dict(), arm
    assert page["headline"] == data["headline"] and page["trade_line"] == data["trade_line"]
    shared_diff = [key for key in page["diff"] if key in data]
    assert {"events", "method", "n_tests", "q", "horizon"} <= set(shared_diff), shared_diff
    for key in shared_diff:
        assert page["diff"][key] == data[key], key
    (panel,) = page["panels"]
    assert panel["event"] == lattice.EVENT
    for key in ("n_unchanged", "n_lower", "n_higher"):
        assert panel[key] == event_diff[key], key
    assert {c["config_hash"] for c in panel["cells"]} == set(cells)
    for c in panel["cells"]:
        mine = cells[c["config_hash"]]
        assert {"n_a", "n_b", "rate_a", "rate_b", "delta", "p", "q", "mde", "verdict", "mde_note"} <= set(c) & set(mine)
        for key in set(c) & set(mine):
            assert c[key] == mine[key], (c["config_hash"], key, c[key], mine[key])
    assert page["tree"]["agreement"] == data["tree"]["agreement"]
    assert page["summary"]["verdict"] == data["verdict"]
    (entry,) = page["summary"]["events"]
    assert entry["event"] == lattice.EVENT and printed_as(entry["limit"]["mde"], round(100 * event_diff["max_mde_unchanged"])), entry

    # inspect: the run's rows with the event, in store order, each with its hash, config, seed and t.
    frame = store.read(lattice.RUN_A)
    rows_with_event = frame[frame["outcome"] == lattice.EVENT].sort_values(["config_hash", "replicate_index"], kind="stable")
    body, marker, _ = results["inspect"].out.partition(SNIPPET_MARKER)
    assert marker, results["inspect"].out
    blocks: list[list[str]] = []
    for line in body.splitlines():
        if line.startswith("config_hash: "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    assert len(blocks) == len(rows_with_event) == lattice.tripped_total(lattice.RUN_A)
    for block, row in zip(blocks, rows_with_event.itertuples(index=False), strict=True):
        fields = dict(line.split(": ", 1) for line in block if ": " in line and not line.startswith(" "))
        assert printed_as(fields["config_hash"], row.config_hash), (block[0], row.config_hash)
        assert json.loads(fields["config"]) == row.config and fields["seed"] == str(row.seed), block
        assert printed_as(fields["replicate_index"], int(row.replicate_index)) and printed_as(fields["t"], float(row.t)), block


# ---------- helpers: the M3 capture oracle's forked child, restated ----------

FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
CAPTURE_SALT = "a7-capture-salt"
CAPTURE_AXES = {"x": [0.1, 0.2, 0.3]}
CAPTURE_REPLICATES = 2
RAISING_X = 0.3


def _outcome(cfg: Mapping[str, Any], seed: int) -> str:
    return "fell" if (seed + int(float(cfg.get("x", 0.0)) * 10)) % 3 == 0 else "survived"


def silent_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """No span emitted, no trace written, no ``meta`` at all; raises on one config so the run
    carries an errored row beside its ok rows (F3)."""
    if float(cfg.get("x", 0.0)) == RAISING_X:
        raise RuntimeError("the rollout that raises")
    outcome = _outcome(cfg, seed)
    return Episode(outcome=outcome, t=3.0 if outcome == "fell" else 10.0, horizon=10.0)


def sweep_toml(*, capture: dict[str, Any] | None, target_id: str, t_unit: str, axes: Mapping[str, Sequence[Any]], replicates: int) -> str:
    lines = [f'target_id = "{target_id}"', f't_unit = "{t_unit}"', f"replicates = {replicates}", ""]
    for name, values in axes.items():
        kind = "continuous" if all(isinstance(v, float) for v in values) else "categorical"
        lines += [f"[axes.{name}]", f'type = "{kind}"', f"values = {json.dumps(list(values))}", ""]
    if capture is not None:
        # CD (D1): a [capture] table declares its cap; 8192 is what the dataclass used to supply.
        if "max_observation_bytes" not in capture and "max_span_bytes" not in capture:
            capture = {**capture, "max_observation_bytes": 8192}
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
    return "\n".join(lines) + "\n"


def _resolve(import_path: str) -> Any:
    module_name, _, attr = import_path.partition(":")
    return getattr(importlib.import_module(module_name), attr)


def child_run_local(store_root: str, toml_path: str, target: str, salt: str) -> dict[str, Any]:
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
    summary = run_local(p, _resolve(target), store)
    return {"run_id": p.run_id, "n_ok": summary.n_ok, "n_errored": summary.n_errored}


def _child_entry(conn: Any, fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        outcome: tuple[str, Any] = ("ok", fn(*args))
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def isolated(fn: Callable[..., Any], *args: Any, timeout: float = 120.0) -> Any:
    """Run ``fn(*args)`` in a forked child: ``install()`` is once per process and claims the
    global provider, so nothing that installs runs in the test process."""
    ctx = multiprocessing.get_context("fork" if FORK_AVAILABLE else "spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_entry, args=(child_conn, fn, args))
    proc.start()
    child_conn.close()
    try:
        if not parent_conn.poll(timeout):
            pytest.fail(f"isolated {fn.__name__} produced nothing within {timeout}s")
        kind, payload = parent_conn.recv()
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(10.0)
    if kind != "ok":
        pytest.fail(f"isolated {fn.__name__} failed:\n{payload}")
    return payload


# ---------- helpers: source structure (P7-6) ----------


def source_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def module_assignments(tree: ast.Module, name: str) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            out.append(node)
    return out


def calls_named(tree: ast.AST, attr: str) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr
    ]


def enclosing_qualnames(tree: ast.Module, target: ast.AST) -> str:
    """``Class.method`` for the innermost function or class containing ``target``."""
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    names: list[str] = []
    node: ast.AST | None = target
    while node is not None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(node.name)
        node = parents.get(node)
    return ".".join(reversed(names))


def string_constants(tree: ast.AST) -> list[str]:
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


# ---------- hypothesis strategies: the M12 span strategy, extended with observation attributes ----------

hex_ids = st.text(alphabet="0123456789abcdef", min_size=16, max_size=16)
json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**63), max_value=2**63)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=8)
)
json_values = st.recursive(
    json_scalars,
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=4), inner, max_size=3),
    max_leaves=8,
)
plain_keys = st.text(min_size=1, max_size=6).filter(lambda k: not is_observation_key(k))
observation_keys = st.sampled_from(sorted(OBSERVATION_KEY_LITERALS)) | st.sampled_from(OBSERVATION_PREFIXES).flatmap(
    lambda p: st.text(min_size=1, max_size=6).map(lambda s: p + s)
)
attr_maps = st.dictionaries(plain_keys | observation_keys, json_values, max_size=5)
epoch_ns = st.integers(min_value=0, max_value=2**62)
token_maps = st.none() | st.dictionaries(st.text(min_size=1, max_size=4), st.integers(min_value=0, max_value=10**6), max_size=3)
code_dicts = st.none() | st.fixed_dictionaries({
    "filepath": st.text(min_size=1, max_size=10),
    "function": st.text(min_size=1, max_size=10),
    "lineno": st.none() | st.integers(min_value=1, max_value=10**6),
})


@st.composite
def span_forests(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Span dicts over the twenty-one keys (A7's thirteen plus A8a's eight at their ``None``
    default), parents drawn over earlier ids, ``input``/``output`` present or absent, attributes
    mixing observation keys (exact and prefixed) with plain ones."""
    ids = draw(st.lists(hex_ids, min_size=0, max_size=6, unique=True))
    spans: list[dict[str, Any]] = []
    for i, sid in enumerate(ids):
        start = draw(epoch_ns)
        delta = draw(st.none() | st.integers(min_value=0, max_value=10**12))
        spans.append({
            "span_id": sid,
            "parent_id": draw(st.sampled_from([None, *ids[:i]])),
            "kind": draw(st.sampled_from(KINDS_SPEC)),
            "name": draw(st.text(min_size=1, max_size=8)),
            "start_ns": start,
            "end_ns": None if delta is None else start + delta,
            "input": draw(json_values),
            "output": draw(json_values),
            "tokens": draw(token_maps),
            "confidence": draw(st.none() | st.floats(min_value=0.0, max_value=1.0)),
            "error": draw(st.none() | st.text(min_size=1, max_size=10)),
            "code": draw(code_dicts),
            "attrs": draw(attr_maps),
            "operation": None,
            "step_name": None,
            "outcome": None,
            "outcome_by": None,
            "attempt": None,
            "gate": None,
            "truncated": None,
            "bytes_original": None,
        })
    return spans


def trace_dict(spans: Sequence[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "schema": SCHEMA_SPEC, "source": "otel", "source_version": OTEL_SEMCONV_VERSION,
        "dropped": 0, "spans": [dict(s) for s in spans], "truncated": None, "alias_map_version": None,
    }
    d.update(overrides)
    return d


# ---------- fixtures: data construction only, never an assertion ----------

POST_RUN = "post"
#: ``(x, k, kind)``: what each row of the post-A7 run carries in ``meta["trace"]``.
POST_ROWS: tuple[tuple[float, int, str], ...] = (
    (0.1, 0, "observation"), (0.1, 1, "observation"), (0.2, 0, "mock"), (0.2, 1, "none"), (0.3, 0, "errored"),
)


def post_trace(x: float, k: int, kind: str) -> Mapping[str, Any] | None:
    if kind == "observation":
        return observation_trace(int(x * 10) * 10 + k).to_dict()
    if kind == "mock":
        return mock_style_trace(k).to_dict()
    if kind == "errored":
        return Trace(spans=(span(7, attrs={"attempts": 1}),), source="otel", source_version=OTEL_SEMCONV_VERSION, truncated="timeout").to_dict()
    return None


def post_a7_records(run_id: str = POST_RUN) -> list[EpisodeRecord]:
    out: list[EpisodeRecord] = []
    for x, k, kind in POST_ROWS:
        tr = post_trace(x, k, kind)
        if kind == "errored":
            out.append(errored(run_id, x=x, k=k, meta={"trace": tr, "k": k}))
        else:
            out.append(rec(run_id, x=x, k=k, meta={"k": k} if tr is None else {"trace": tr, "k": k}))
    return out


@pytest.fixture(scope="module")
def post_a7_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Store, list[EpisodeRecord]]:
    """F4 and P7-2's run: observation traces, a mock-shaped trace, a traceless row and an errored
    row with a truncated trace, through ``Store.append`` -- the post-A7 writer once it exists."""
    store = Store(tmp_path_factory.mktemp("a7-post"))
    store.create_run(manifest(POST_RUN))
    records = post_a7_records()
    store.append(POST_RUN, records[:3])
    store.append(POST_RUN, records[3:])
    store.mark_complete(POST_RUN)
    return store, records


MIXED_RUN = "mixed"


@pytest.fixture(scope="module")
def mixed_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Store, list[EpisodeRecord], list[EpisodeRecord]]:
    """F1: one pre-A7 part written by ``write_pre_a7_part`` and one post-A7 part written by
    ``Store.append``, in one run, every row carrying a valid ``meta["trace"]``."""
    store = Store(tmp_path_factory.mktemp("a7-mixed"))
    store.create_run(manifest(MIXED_RUN))
    old = [rec(MIXED_RUN, x=0.1, k=k, meta={"trace": observation_trace(k).to_dict(), "k": k, "layout": "pre"}) for k in range(3)]
    write_pre_a7_part(store, MIXED_RUN, old)
    new = [rec(MIXED_RUN, x=0.2, k=k, meta={"trace": observation_trace(10 + k).to_dict(), "k": k, "layout": "post"}) for k in range(3)]
    store.append(MIXED_RUN, new)
    return store, old, new


POISONED_RUN = "poisoned"


@pytest.fixture(scope="module")
def poisoned_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Store, list[EpisodeRecord]]:
    """F2: a post-A7 run through ``Store.append`` whose ``meta`` and ``trace_obs`` cells were then
    rewritten in place with bytes that are not JSON."""
    store = Store(tmp_path_factory.mktemp("a7-poisoned"))
    store.create_run(manifest(POISONED_RUN))
    records = [rec(POISONED_RUN, x=0.1, k=k, meta={"trace": observation_trace(20 + k).to_dict(), "k": k}) for k in range(3)]
    store.append(POISONED_RUN, records)
    for part in parts_of(store, POISONED_RUN):
        poison_cells(part, [c for c in ("meta", "trace_obs") if c in pq.read_schema(part).names])
    return store, records


RETENTION_RUN = "retained"


@pytest.fixture(scope="module")
def retention_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Store, dict[str, EpisodeRecord]]:
    """P7-7: ``retain_traces_for=("fell",)``; one retained ok row, one ok row whose outcome is not
    retained, one errored row, each carrying an observation trace."""
    store = Store(tmp_path_factory.mktemp("a7-retention"))
    store.create_run(manifest(RETENTION_RUN, retain_traces_for=("fell",)))
    records = {
        "retained": rec(RETENTION_RUN, x=0.1, k=0, outcome="fell", meta={"trace": observation_trace(30).to_dict(), "k": 0}),
        "dropped": rec(RETENTION_RUN, x=0.1, k=1, outcome="survived", t=10.0, meta={"trace": observation_trace(31).to_dict(), "k": 1}),
        "errored": errored(RETENTION_RUN, x=0.1, k=2, meta={"trace": observation_trace(32).to_dict(), "k": 2}),
    }
    store.append(RETENTION_RUN, list(records.values()))
    return store, records


@dataclass(frozen=True)
class Captured:
    root: Path
    on: str
    off: str
    mock_on: str


@pytest.fixture(scope="module")
def captured_runs(tmp_path_factory: pytest.TempPathFactory) -> Captured:
    """F3: the silent rollout under ``[capture] instrument = []`` and under no ``[capture]`` table,
    and the mock agent under capture, each in its own forked child."""
    root = tmp_path_factory.mktemp("a7-capture")
    on_toml = root / "on.toml"
    on_toml.write_text(sweep_toml(capture={"instrument": []}, target_id="silent@v0", t_unit="steps", axes=CAPTURE_AXES, replicates=CAPTURE_REPLICATES))
    off_toml = root / "off.toml"
    off_toml.write_text(sweep_toml(capture=None, target_id="silent@v0", t_unit="steps", axes=CAPTURE_AXES, replicates=CAPTURE_REPLICATES))
    mock_toml = root / "mock.toml"
    mock_toml.write_text(sweep_toml(capture={"instrument": []}, target_id="mock-agent@v0", t_unit="tool_calls", axes={"task_id": ["search", "checkout"], "tool_fail_rate": [0.0, 0.5]}, replicates=3))
    on = isolated(child_run_local, str(root / "store"), str(on_toml), f"{MODULE}:silent_rollout", CAPTURE_SALT)
    off = isolated(child_run_local, str(root / "store"), str(off_toml), f"{MODULE}:silent_rollout", CAPTURE_SALT + "-off")
    mock_on = isolated(child_run_local, str(root / "store"), str(mock_toml), MOCK_ROLLOUT, CAPTURE_SALT + "-mock")
    return Captured(root / "store", on["run_id"], off["run_id"], mock_on["run_id"])


GARBAGE_RUN = "garbage"
GARBAGE_TRACES: dict[str, Any] = {
    "list": ["step-a", "step-b"],
    "dict": {"schema": "not/proofload", "steps": []},
    # A8a: was a seven-key dict carrying ``alias_map_version``, which A8a makes a valid key; an unknown key stays garbage under both schemas.
    "unknown-key": {"schema": SCHEMA_SPEC, "source": "otel", "source_version": None, "dropped": 0, "spans": [], "truncated": None, "steps": []},
}


@pytest.fixture(scope="module")
def garbage_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Store, dict[int, Any]]:
    """P7-9: three rows whose ``meta["trace"]`` is present and not a valid trace dict -- a list, a
    dict under another schema, and a dict with an unknown key ``Trace.from_dict`` rejects."""
    store = Store(tmp_path_factory.mktemp("a7-garbage"))
    store.create_run(manifest(GARBAGE_RUN))
    by_k = dict(enumerate(GARBAGE_TRACES.values()))
    store.append(GARBAGE_RUN, [rec(GARBAGE_RUN, x=0.1, k=k, meta={"trace": tr, "k": k}) for k, tr in by_k.items()])
    return store, by_k


@pytest.fixture(scope="module")
def crossed_twice(tmp_path_factory: pytest.TempPathFactory) -> Store:
    """F5: A28's crossed P pair, the same episodes stored twice -- ``pre-a``/``pre-b`` through the
    pre-A7 writer, ``post-a``/``post-b`` through ``Store.append``."""
    store = Store(tmp_path_factory.mktemp("a7-crossed"))
    cells_a, cells_b = crossed_cells(4, 20, 2)
    for run_id, cells in (("pre-a", cells_a), ("pre-b", cells_b)):
        store.create_run(a28_manifest(run_id))
        write_pre_a7_part(store, run_id, crossed_records(run_id, cells))
        store.mark_complete(run_id)
    for run_id, cells in (("post-a", cells_a), ("post-b", cells_b)):
        store.create_run(a28_manifest(run_id))
        store.append(run_id, crossed_records(run_id, cells))
        store.mark_complete(run_id)
    return store


@dataclass(frozen=True)
class MockPair:
    root: Path
    a: str
    b: str


@pytest.fixture(scope="module")
def mock_pair(tmp_path_factory: pytest.TempPathFactory) -> MockPair:
    """The mock quickstart's shape at a small grid, stored through ``run_local`` with no capture
    table (so nothing installs in this process), the second arm paired with the first."""
    root = tmp_path_factory.mktemp("a7-mock")
    store = Store(root)
    spec = SweepSpec.build(MOCK_CONFIGS, replicates=MOCK_REPLICATES, target_id="mock-agent@v0", t_unit="tool_calls")
    pa_ = plan(spec, store, run_salt=MOCK_SALT, import_path=MOCK_ROLLOUT)
    run_local(pa_, rollout, store, batch_size=MOCK_BATCH)
    pb_ = plan(spec, store, pair_with=pa_.run_id, import_path=MOCK_PATCHED)
    run_local(pb_, rollout_patched, store, batch_size=MOCK_BATCH)
    return MockPair(root, pa_.run_id, pb_.run_id)


# ---------- P7-1: the schema and the three read modes project exactly ----------


def test_p7_1_the_schema_gains_two_nullable_strings_and_every_mode_projects_exactly(post_a7_run: tuple[Store, list[EpisodeRecord]], lattice_store: Store) -> None:
    schema = store_module._SCHEMA
    assert schema.names == POST_A7_PART, schema.names
    for name in TRACE_COLUMNS + CASE_COLUMN:
        field = schema.field(name)
        assert field.type == pa.string() and field.nullable, field
    assert "trace" in inspect.signature(Store.read).parameters
    store, records = post_a7_run
    n = len(records)
    for run_store, run_id, rows in ((store, POST_RUN, n), (lattice_store, lattice.RUN_A, lattice.ROWS)):
        assert list(run_store.read(run_id).columns) == READ_THIRTEEN
        assert list(run_store.read(run_id, meta=True).columns) == READ_THIRTEEN
        assert list(run_store.read(run_id, meta=False).columns) == READ_ELEVEN
        assert list(run_store.read(run_id, trace="full").columns) == READ_THIRTEEN
        assert list(run_store.read(run_id, trace="none").columns) == READ_THIRTEEN
        assert list(run_store.read(run_id, meta=False, trace="none").columns) == READ_ELEVEN
        envelope = run_store.read(run_id, trace="envelope")
        assert list(envelope.columns) == READ_THIRTEEN + ["trace"] and len(envelope) == rows
        narrow = run_store.read(run_id, meta=False, trace="envelope")
        assert list(narrow.columns) == READ_ELEVEN + ["trace"] and len(narrow) == rows
        assert "trace_obs" not in envelope.columns and "trace_obs" not in narrow.columns
        empty = run_store.read(run_id, keys=[], trace="envelope")
        assert list(empty.columns) == READ_THIRTEEN + ["trace"] and len(empty) == 0
        assert list(run_store.read(run_id, keys=[], meta=False, trace="envelope").columns) == READ_ELEVEN + ["trace"]
    # Q3 (c): ``meta=True`` with the envelope decodes ``meta`` and it carries no ``"trace"`` key.
    for row in store.read(POST_RUN, trace="envelope").itertuples(index=False):
        assert isinstance(row.meta, dict) and "trace" not in row.meta
    # Q4 (a): an explicit full read with no ``meta`` column to hold it is refused, naming both.
    with pytest.raises(ValueError, match="meta") as info:
        store.read(POST_RUN, meta=False, trace="full")
    assert "trace" in str(info.value)
    with pytest.raises(ValueError):
        store.read(POST_RUN, trace="wide")


# ---------- P7-2: meta never carries the key; the full read is byte-identical ----------


def test_p7_2_meta_on_disk_never_carries_the_key_and_the_full_read_presents_the_record_byte_for_byte(post_a7_run: tuple[Store, list[EpisodeRecord]]) -> None:
    store, records = post_a7_run
    for key, keys in raw_meta_keys(store, POST_RUN).items():
        assert "trace" not in keys, key
    full = rows_by_key(store.read(POST_RUN, trace="full"))
    envelope = rows_by_key(store.read(POST_RUN, trace="envelope"))
    assert set(full) == set(envelope) == {(r.config_hash, r.replicate_index) for r in records}
    for r in records:
        key = (r.config_hash, r.replicate_index)
        original = r.meta.get("trace")
        if original is None:
            assert "trace" not in full[key].meta
            assert envelope[key].trace is None
            continue
        assert envelope[key].trace is not None and isinstance(envelope[key].trace, dict)
        assert "trace" in full[key].meta
        assert canonical(full[key].meta["trace"]) == canonical(original), key
        rest = {k: v for k, v in full[key].meta.items() if k != "trace"}
        assert rest == {k: v for k, v in r.meta.items() if k != "trace"}


# ---------- P7-3: a mixed run reads as one frame, indistinguishable by origin ----------


def test_p7_3_a_pre_a7_part_and_a_post_a7_part_in_one_run_read_as_one_frame(mixed_run: tuple[Store, list[EpisodeRecord], list[EpisodeRecord]]) -> None:
    store, old, new = mixed_run
    parts = parts_of(store, MIXED_RUN)
    assert len(parts) == 2 and pq.read_schema(parts[0]).names == THIRTEEN and pq.read_schema(parts[1]).names == POST_A7_PART
    expected = {(r.config_hash, r.replicate_index): r for r in old + new}
    full = store.read(MIXED_RUN, trace="full")
    assert list(full.columns) == READ_THIRTEEN and set(keys_of(full)) == set(expected)
    for key, row in rows_by_key(full).items():
        assert row.meta["trace"] is not None and isinstance(row.meta["trace"], dict), key
        assert canonical(row.meta["trace"]) == canonical(expected[key].meta["trace"]), key
    envelope = store.read(MIXED_RUN, trace="envelope")
    assert list(envelope.columns) == READ_THIRTEEN + ["trace"] and set(keys_of(envelope)) == set(expected)
    for key, row in rows_by_key(envelope).items():
        assert row.trace is not None and isinstance(row.trace, dict), key
        assert row.trace["spans"] and all(s["input"] is None and s["output"] is None for s in row.trace["spans"]), key
        # Q3 (c): the decoded ``meta`` of a pre-A7 row has its ``"trace"`` key removed too.
        assert isinstance(row.meta, dict) and "trace" not in row.meta and row.meta["k"] == expected[key].meta["k"], key
    narrow = store.read(MIXED_RUN, meta=False, trace="envelope")
    assert list(narrow.columns) == READ_ELEVEN + ["trace"]
    assert all(row.trace is not None for row in narrow.itertuples(index=False))
    # Q7 (b): ``"none"`` strips a pre-A7 row's ``meta["trace"]`` so the layouts stay indistinguishable.
    none = store.read(MIXED_RUN, trace="none")
    assert list(none.columns) == READ_THIRTEEN
    for key, row in rows_by_key(none).items():
        assert isinstance(row.meta, dict) and "trace" not in row.meta and row.meta["k"] == expected[key].meta["k"], key
    assert list(store.read(MIXED_RUN, meta=False, trace="none").columns) == READ_ELEVEN


# ---------- P7-4: assemble(*split(t)) is the identity over A7's whole valid space ----------


@settings(max_examples=75, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    spans=span_forests(),
    source=st.sampled_from(("record", "otel", "litellm", "mixed")),
    source_version=st.none() | st.text(min_size=1, max_size=8),
    dropped=st.integers(min_value=0, max_value=100),
    truncated=st.none() | st.sampled_from(("timeout", "crash")),
)
def test_p7_4_assemble_of_split_round_trips_every_valid_trace(spans: list[dict[str, Any]], source: str, source_version: str | None, dropped: int, truncated: str | None) -> None:
    from poisson_prove.trace import assemble, split

    t = Trace.from_dict(trace_dict(spans, source=source, source_version=source_version, dropped=dropped, truncated=truncated))
    envelope, obs = split(t)
    assert isinstance(envelope, dict) and isinstance(obs, dict)
    assert set(envelope) == TRACE_KEYS and all(set(s) == SPAN_KEYS for s in envelope["spans"])
    assert set(obs) <= {s.span_id for s in t.spans}
    assert assemble(envelope, obs).to_dict() == t.to_dict()
    if not obs:
        assert assemble(envelope, None).to_dict() == t.to_dict()
        assert assemble(envelope, {}).to_dict() == t.to_dict()
    if not observation_values(t):
        assert obs == {}


# ---------- P7-5: the envelope read decodes neither trace_obs nor meta ----------


def test_p7_5_the_narrow_envelope_read_decodes_neither_trace_obs_nor_meta_on_a_post_a7_part(poisoned_run: tuple[Store, list[EpisodeRecord]]) -> None:
    store, records = poisoned_run
    for part in parts_of(store, POISONED_RUN):
        assert pq.read_schema(part).names == POST_A7_PART
    assert all(v == POISON for v in raw_column(store, POISONED_RUN, "meta").values())
    assert all(v == POISON for v in raw_column(store, POISONED_RUN, "trace_obs").values())
    narrow = store.read(POISONED_RUN, meta=False, trace="envelope")
    assert list(narrow.columns) == READ_ELEVEN + ["trace"] and len(narrow) == len(records)
    for row in narrow.itertuples(index=False):
        assert row.trace is not None and isinstance(row.trace, dict) and row.trace["schema"] == SCHEMA_SPEC
        assert len(row.trace["spans"]) == 3
    with pytest.raises(ValueError):
        store.read(POISONED_RUN)
    with pytest.raises(ValueError):
        store.read(POISONED_RUN, trace="full")
    with pytest.raises(ValueError):
        store.read(POISONED_RUN, trace="envelope")


# ---------- P7-6: a trace is never stored apart from its row (ADR-021's shape) ----------


def test_p7_6_store_append_is_the_only_writer_and_schema_the_only_declaration_of_the_two_columns() -> None:
    # PF4 re-freeze (PF4.38, reading R5): the case_id column is appended after the two.
    assert store_module._SCHEMA.names[-3:] == TRACE_COLUMNS + CASE_COLUMN
    declared: list[str] = []
    writers: list[str] = []
    obs_mentions: list[str] = []
    for path in source_files():
        tree = ast.parse(path.read_bytes())
        if module_assignments(tree, "_SCHEMA"):
            declared.append(path.name)
        for call in calls_named(tree, "write_table"):
            writers.append(f"{path.name}::{enclosing_qualnames(tree, call)}")
        if any("trace_obs" in s for s in string_constants(tree)):
            obs_mentions.append(path.name)
    assert declared == ["store.py"], declared
    assert writers == ["store.py::Store.append"], writers
    assert obs_mentions == ["store.py"], obs_mentions
    assert "trace" not in RunManifest.from_dict(manifest("r").to_dict()).to_dict()
    for name in ("trace", "trace_obs"):
        assert name not in RunManifest.__dataclass_fields__


# ---------- P7-7: retention nulls both columns, leaves meta, keeps the errored row ----------


def test_p7_7_retention_nulls_both_columns_on_an_unretained_ok_row_and_spares_the_errored_row(retention_run: tuple[Store, dict[str, EpisodeRecord]]) -> None:
    store, records = retention_run
    key = {name: (r.config_hash, r.replicate_index) for name, r in records.items()}
    envelope = rows_by_key(store.read(RETENTION_RUN, trace="envelope"))
    obs = raw_column(store, RETENTION_RUN, "trace_obs")
    raw_trace = raw_column(store, RETENTION_RUN, "trace")
    assert envelope[key["retained"]].trace is not None and isinstance(envelope[key["retained"]].trace, dict)
    assert raw_trace[key["retained"]] is not None and obs[key["retained"]] is not None
    assert envelope[key["dropped"]].trace is None
    assert raw_trace[key["dropped"]] is None and obs[key["dropped"]] is None
    assert envelope[key["errored"]].trace is not None and isinstance(envelope[key["errored"]].trace, dict)
    assert raw_trace[key["errored"]] is not None and obs[key["errored"]] is not None
    full = rows_by_key(store.read(RETENTION_RUN, trace="full"))
    assert full[key["dropped"]].meta == {"k": 1}
    assert canonical(full[key["retained"]].meta["trace"]) == canonical(records["retained"].meta["trace"])
    assert canonical(full[key["errored"]].meta["trace"]) == canonical(records["errored"].meta["trace"])
    assert {k: v for k, v in full[key["retained"]].meta.items() if k != "trace"} == {"k": 0}
    assert {k: v for k, v in full[key["errored"]].meta.items() if k != "trace"} == {"k": 2}


# ---------- P7-8: capture on with no spans is an empty envelope; capture off is null ----------


def test_p7_8_capture_active_with_no_spans_stores_the_empty_envelope_and_no_capture_stores_null(captured_runs: Captured) -> None:
    store = Store(captured_runs.root)
    assert store.manifest(captured_runs.on).environment["capture"]["active"] is True
    assert "capture" not in store.manifest(captured_runs.off).environment
    on = store.read(captured_runs.on, trace="envelope")
    assert len(on) == len(CAPTURE_AXES["x"]) * CAPTURE_REPLICATES
    assert (on["error"].map(lambda e: e is not None)).sum() == CAPTURE_REPLICATES
    on_obs = raw_column(store, captured_runs.on, "trace_obs")
    for key, row in rows_by_key(on).items():
        assert row.trace is not None and isinstance(row.trace, dict), key
        assert row.trace["spans"] == [] and row.trace["source"] == "otel", key
        assert Trace.from_dict(row.trace).spans == ()
        assert on_obs[key] is None, key
        assert isinstance(row.meta, dict) and "trace" not in row.meta
    off = store.read(captured_runs.off, trace="envelope")
    assert len(off) == len(on)
    off_obs = raw_column(store, captured_runs.off, "trace_obs")
    for key, row in rows_by_key(off).items():
        assert row.trace is None and off_obs[key] is None, key
    assert {row.trace is None for row in on.itertuples(index=False)} == {False}
    assert {row.trace is None for row in off.itertuples(index=False)} == {True}
    # C7 holds: the mock's own trace rides through the split and the full read byte for byte.
    assert store.manifest(captured_runs.mock_on).environment["capture"]["active"] is True
    mock = store.read(captured_runs.mock_on, trace="full")
    assert len(mock) == 4 * 3 and all(e is None for e in mock["error"])
    for row in mock.itertuples(index=False):
        own = rollout(dict(row.config), int(row.seed)).to_dict()["meta"]["trace"]
        assert canonical(row.meta["trace"]) == canonical(own), (row.config_hash, row.replicate_index)
        assert row.meta["trace"]["source"] == "record"


# ---------- P7-9: an invalid meta["trace"] is left as written, both columns null ----------


def test_p7_9_an_invalid_meta_trace_is_stored_as_written_with_both_columns_null_and_append_does_not_raise(garbage_run: tuple[Store, dict[int, Any]]) -> None:
    store, by_k = garbage_run
    full = rows_by_key(store.read(GARBAGE_RUN, trace="full"))
    envelope = rows_by_key(store.read(GARBAGE_RUN, trace="envelope"))
    raw_trace = raw_column(store, GARBAGE_RUN, "trace")
    obs = raw_column(store, GARBAGE_RUN, "trace_obs")
    raw_meta = raw_column(store, GARBAGE_RUN, "meta")
    assert len(full) == len(by_k) == 3
    for key, row in full.items():
        k = row.meta["k"]
        assert row.meta == {"trace": by_k[k], "k": k}, key
        assert json.loads(raw_meta[key]) == {"trace": by_k[k], "k": k}, key
        assert envelope[key].trace is None, key
        assert raw_trace[key] is None and obs[key] is None, key


# ---------- P7-10: every verb exits 0 on the lattice pair and the mock pair; the lattice pair is never rewritten ----------


def test_p7_10_every_verb_exits_0_on_the_lattice_and_the_mock_pair_and_the_lattices_bytes_are_unchanged(lattice_store: Store, mock_pair: MockPair, tmp_path: Path) -> None:
    # The precondition: the mock pair was written in the post-A7 layout, or this asserts nothing.
    store = Store(mock_pair.root)
    for run_id in (mock_pair.a, mock_pair.b):
        for part in parts_of(store, run_id):
            assert pq.read_schema(part).names == POST_A7_PART, part
        frame = store.read(run_id, meta=False, trace="envelope")
        assert all(row.trace is not None and isinstance(row.trace, dict) for row in frame.itertuples(index=False))
    for part in (LATTICE_ROOT / lattice.RUN_A / "episodes" / "part-00000.parquet", LATTICE_ROOT / lattice.RUN_B / "episodes" / "part-00000.parquet"):
        assert pq.read_schema(part).names == THIRTEEN, part
    digests, results = lattice_verb_digests(tmp_path / "lattice")
    # The pre-A7 pair's bytes: every file is the one the generator wrote, after every verb ran on it.
    assert lattice.intact()
    # A shared-salt pair now carries one note: line on stderr (spec section 5.4); nothing else.
    for verb, r in results.items():
        assert r.code == 0 and err_lines(r) == [], (verb, r.code, r.err)
    # PF4 (PF4.3, PF4.11, PF4.13 to PF4.20): no digest is kept; every verb, the page structure
    # included, is checked as facts (spec section 14).
    assert all(len(d) == HEX64_LEN for d in digests.values()), digests
    assert_lattice_verb_facts(results, tmp_path / "lattice")
    mock_digests, mock_results = verb_digests(mock_pair.root, mock_pair.a, mock_pair.b, event=MOCK_EVENT, x="tool_fail_rate", y="task_id", out_dir=tmp_path / "mock")
    for verb, r in mock_results.items():
        assert r.code == 0 and err_lines(r) == [], (verb, r.code, r.err)
    assert all(len(d) == HEX64_LEN for d in mock_digests.values()), mock_digests
    r = mock_results["runs"]
    # PF2 (spec section 5.3): the verdict line, a blank line and the header come first, and the rows
    # lead with the number and the name, newest first; each row is read by the id it carries.
    rows = r.out.splitlines()[3:]
    assert [[t for t in line.split() if t in (mock_pair.a, mock_pair.b)] for line in rows] == [[mock_pair.b], [mock_pair.a]], r.out
    r = mock_results["inspect"]
    assert SNIPPET_MARKER in r.out and "from poisson_prove.examples.mock_agent import rollout" in r.out
    rows = store.read(mock_pair.a, trace="full")
    violated = rows[rows["outcome"] == MOCK_EVENT]
    assert len(violated) >= 1
    step_lines = [line for line in r.out.splitlines() if line.startswith("  ") and line.count("\t") == 8]  # nine columns since A8a
    assert len(step_lines) == int(sum(len(row.meta["trace"]["spans"]) for row in violated.itertuples(index=False)))


# ---------- P7-11: the envelope is an envelope ----------


def test_p7_11_the_envelope_carries_no_observation_value_and_trace_obs_carries_every_one(post_a7_run: tuple[Store, list[EpisodeRecord]]) -> None:
    assert isinstance(trace_module.OBSERVATION_KEYS, frozenset)
    assert OBSERVATION_KEY_LITERALS <= trace_module.OBSERVATION_KEYS, sorted(OBSERVATION_KEY_LITERALS - trace_module.OBSERVATION_KEYS)
    assert trace_module.LOGPROBS_KEY == LOGPROBS_KEY_SPEC and trace_module.LOGPROBS_KEY in trace_module.OBSERVATION_KEYS
    assert not (set(PLAIN_KEYS) & trace_module.OBSERVATION_KEYS)
    store, records = post_a7_run
    envelope = rows_by_key(store.read(POST_RUN, trace="envelope"))
    obs = raw_column(store, POST_RUN, "trace_obs")
    seen_classes: set[str] = set()
    for r in records:
        key = (r.config_hash, r.replicate_index)
        original = r.meta.get("trace")
        if original is None:
            assert envelope[key].trace is None and obs[key] is None, key
            continue
        expected = observation_values(Trace.from_dict(original))
        env = envelope[key].trace
        assert env is not None and isinstance(env, dict), key
        by_id = {s["span_id"]: s for s in env["spans"]}
        assert set(by_id) == {s["span_id"] for s in original["spans"]}, key
        for s in env["spans"]:
            assert s["input"] is None and s["output"] is None, (key, s["span_id"])
            assert not (set(s["attrs"]) & trace_module.OBSERVATION_KEYS), (key, sorted(s["attrs"]))
            assert not any(is_observation_key(k) for k in s["attrs"]), (key, sorted(s["attrs"]))
            plain = {k: v for k, v in next(o for o in original["spans"] if o["span_id"] == s["span_id"])["attrs"].items() if not is_observation_key(k)}
            assert s["attrs"] == plain, (key, s["span_id"])
        if not expected:
            assert obs[key] is None, key
            continue
        assert obs[key] is not None, key
        stored = json.loads(obs[key])
        assert set(stored) == set(expected), (key, sorted(stored), sorted(expected))
        for span_id, body in expected.items():
            for field, value in body.items():
                assert stored[span_id][field] == value, (key, span_id, field)
        for s in original["spans"]:
            for k in s["attrs"]:
                if k in OBSERVATION_KEY_LITERALS:
                    seen_classes.add(k)
                elif is_observation_key(k):
                    seen_classes.add("prefix:" + k.split(".")[1])
    assert OBSERVATION_KEY_LITERALS <= seen_classes and {"prefix:prompt", "prefix:completion", "prefix:input_messages", "prefix:output_messages"} <= seen_classes, sorted(seen_classes)


# ---------- P7-12: the split does not move the agreement digest ----------


def test_p7_12_the_split_does_not_move_the_agreement_digest_across_layouts_and_the_lattice_reference_holds(crossed_twice: Store, lattice_store: Store) -> None:
    store = crossed_twice
    for run_id in ("pre-a", "pre-b"):
        assert [pq.read_schema(p).names for p in parts_of(store, run_id)] == [THIRTEEN]
    for run_id in ("post-a", "post-b"):
        assert all(pq.read_schema(p).names == POST_A7_PART for p in parts_of(store, run_id))
        assert all(row.trace is not None for row in store.read(run_id, meta=False, trace="envelope").itertuples(index=False))
    for k, events in ((1, ("fail",)), (2, EVENTS)):
        for method in ("fisher_bh", "mcnemar_bh"):
            pre = grown(store, "pre-a", "pre-b", events=events, method=method)
            post = grown(store, "post-a", "post-b", events=events, method=method)
            values = {
                pre.result.agreement, post.result.agreement,
                agreement_digest(pre.multi), agreement_digest(post.multi),
                pre.result.to_json()["agreement"], post.result.to_json()["agreement"],
            }
            assert values == {CROSSED_AGREEMENT[k]}, (k, method, values)
            render_both(store, post, pre.result)
            render_both(store, pre, post.result)
    for k, events in LATTICE_EVENTS.items():
        expected = reference_agreement(events)
        assert expected != reference_agreement(events, OLD_AGREEMENT_SCHEMA), k
        fa, fb = lattice_store.read(lattice.RUN_A, meta=False), lattice_store.read(lattice.RUN_B, meta=False)
        ma, mb = lattice_store.manifest(lattice.RUN_A), lattice_store.manifest(lattice.RUN_B)
        for method in ("fisher_bh", "mcnemar_bh"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
                multi = multi_diff(fa, fb, events=list(events), method=method, q=Q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]
            assert agreement_digest(multi) == expected, (k, method)
        assert grow_tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, n_permutations=PERMUTATIONS, seed=SEED).agreement == expected
