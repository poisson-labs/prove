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
the three ``TRACE_EXPORTS`` copies (``test_m3_crash_trace.py``, ``test_m3_timeout_trace.py``,
``test_pilot_golden.py``) are the spec's. The sixth is ``test_m3_crash_trace.py``'s
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
gaining them); and A28's G17 with every other ``G`` -- Go1 is a pre-A7 store that is never
rewritten, so the split never runs on it.

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
| 12 | the read path nulls ``outcome`` on a post-A7 row whose ``trace_obs`` is non-null and outcome is ``"crash"`` | **P7-12 alone -- and A28's G17 stays green**, which is section 3.8's claim measured: Go1 cannot see a change that reaches only the new layout |

**Why every test here is red on the bare tree, including the two preservation invariants.**
P7-10 (every verb's bytes unchanged) and P7-12 (the digest unchanged) are claims about a store in
the **post-A7 layout**; on the bare tree ``Store.append`` writes the old layout and both would be
green for nothing. So each asserts its precondition first -- the parts it wrote carry the two
columns -- the S29 W11 lesson (assert the flag exists before asserting how it refuses), and P7-1
asserts ``trace`` is a parameter of ``Store.read`` before asserting how Q4's refusal reads.

**Step zero, measured at ``93bfa13`` on pyarrow 25.0.1, pandas 2.3.3 (spec section 7.4).**
(1) ``pq.read_table(part, schema=<thirteen + trace + trace_obs>)`` on both committed Go1 parts
**fills the two missing columns with nulls and does not raise**, in every projection form the
reader uses -- no ``columns=``, all fifteen, the eleven non-meta, ``["trace"]`` alone, and with a
``config_hash in`` filter -- and the reverse read of a fifteen-column part under the thirteen-field
schema drops the extras; the per-schema fallback the spec's trap 1 names is **not needed**, and
P7-3's mixed run is the guard that this holds beyond Go1. (2) The agreement digest on A28's
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

- **Go1** (``tests/fixtures/go1``) is pre-A7 and never rewritten. It carries P7-1's thirteen and
  eleven, P7-10's byte pins and P7-12's two literals through the fallback read only; it can say
  nothing about the split.
- **F1**, ``write_pre_a7_part`` -- the checked-in pre-A7 writer, emitting Go1's own on-disk schema
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
  its bytes cannot be pinned here; P7-10 pins **Go1's** bytes and asserts the mock pair's verbs exit
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
import importlib
import inspect
import json
import multiprocessing
import re
import traceback
import warnings
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
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
GO1_ROWS = 12_800
GO1_PART = GO1_ROOT / GO1_A / "episodes" / "part-00000.parquet"

# ---------- the literals (spec sections 2, 3.1, 3.3, 3.8, 7.4) ----------

THIRTEEN = [
    "run_id", "config_hash", "config", "seed", "replicate_index", "outcome", "t", "horizon",
    "confidence", "meta", "error", "wall_time", "backend_meta",
]
ELEVEN = [c for c in THIRTEEN if c not in ("meta", "backend_meta")]
TRACE_COLUMNS = ["trace", "trace_obs"]
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

#: G17's two Go1 literals, restated from ``test_a28_agreement.py``: the same value under both
#: methods at each K, through the fallback read of a pre-A7 store.
# Re-minted by PF0 Session A (Q4): the agreement form is hashed behind its schema string, which is now
# ``poisson-prove.agreement/1``. Computed on the 0.0.1 tree (98dc6af) with that one string changed and
# nothing else; the 0.0.1 values are kept below as ``GO1_AGREEMENT_0_0_1``.
GO1_AGREEMENT = {
    1: "ed536c0213e9a9e7942807ec525738d1ca1373544e0b47fc93a8640879ef1087",
    2: "ceecf72a0f87fbdb0c74758a4554c8a9427f0a6ecba08504c5dc5fad36e04c33",
}
GO1_AGREEMENT_0_0_1 = {
    1: "360aaa320c675c40fa8dc7b2b3d5288aa42468c16facc7209264f975cb13e92d",
    2: "988b1dd2c3b30b4f21007de26b1c04520d030c91ec809c3df696a8a5445b33af",
}
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
#: P7-10. Every verb on Go1 at ``93bfa13``, in-process through ``cli.main``, stdout digested after
#: the store root (``runs``, ``serve --json``'s ``pair.store_root``) and the ``--out`` directory
#: (``report``) are normalised. ``inspect`` and ``diff`` echo no path. Measured by
#: ``go1_verb_digests`` below on the dispatch commit; a later commit that moves one of these has
#: changed what a consumer sees.
# Re-minted 2026-09-20 (truncation surfacing): five values move -- report A/report.md, report A/receipt.html, report A B/report.md,
# report A B/receipt.html and serve --json -- because the provenance list gains the horizon rename and the observation
# lines and the structure is proofload.viewpair/5. Each is the baseline's output plus that change, byte for byte; the
# other nine are unchanged.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): three of the fourteen move: both 'report A B' files, whose Cells section prints LS16's respelled sentence ('MDE is the smallest detectable increase', no ADR number), and 'serve --json', which is proofload.viewpair/6 with the summary key and each panel's mde_unchanged. The other eleven are unchanged. Read through this test's own measurement on the built tree, not predicted.
GO1_VERB_SHA256 = {
    "runs": "0c9a8e63beb07be3c4b370e02d93ac33672b77430fe7381da5063f91c182a4b1",
    "diff": "7849924e1ff36e6a9a2afc338a876bf312d3a5188f069e3e6cdb40693e226d8a",
    "diff --format json": "fd2a622c4bfc75bd768b5fcc2c6453e97e8b552a603cfb8ac7717af89ce8be43",
    "check": "dc3d8acc89864cdb69eda671d931c492e3e81c1d74eb1393b37d789f8c2d3417",
    "report A": "13976b7c8ba0022d285fc6d882901a209e9df8004cc0a42c072d75df20661615",
    "report A/report.md": "32d2431a784e4703a5a88270678bb160bb93ae75a66e8933a0b434d5534dec5f",
    "report A/heatmap.svg": "e6020ec87eae771a66d8847888de06f2355cd810209e39c25d1c7a6584400851",
    "report A/receipt.html": "c0ac15e72e730f3cb134de862a3ba67a74b0623c07a12571ea0be4642f9fefa1",
    "report A B": "a597669edbcba109c45e2cf02299c397e30d2033ba79e92f298d274c0a06436d",
    "report A B/report.md": "69324de1b24bdcf561501e313561ea481e243249a982a3b274e727445a15c370",
    "report A B/heatmap.svg": "2e0dfe4e27314d30f1514104a60d0a566a75f4c032fa1b25f92b779f70c324de",
    "report A B/receipt.html": "f5b7342aeb67f1214140bb486b388e9e7a521ffb1d07e2972191b350fa5eb6eb",
    "serve --json": "725d60142c4322fcdb26242e515636ff9353394c51f61e5b05c8ee240b4e32a7",
    "inspect": "5e2905ec3c2c8e87e6a0032b82a3ed544fc5bd68557688896c1fa717b648d052",
}
GO1_EVENT = "fell"
GO1_X, GO1_Y = "mu", "push_pct_bw"
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
    """F1: the checked-in pre-A7 writer. Emits one part in Go1's own on-disk schema -- thirteen
    fields, read off the committed golden part rather than spelled here -- with ``meta["trace"]``
    left inside ``meta`` exactly as the record carries it. The run must already exist; the part
    is numbered after any part already present so ``Store._parts`` sees it."""
    schema = pq.read_schema(GO1_PART)
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
    """PF0 (Q4, section 2.3): the one line of a rendered Go1 report the rename changes is the version
    in its provenance list, which now names Prove (and, for runs 0.0.1 wrote, says so). It is put back
    as 0.0.1 wrote it before the frozen digest is taken, so the digest still guards every other byte."""
    text = re.sub(r"(?m)^- [^:\n]*\bversion: [^\n]*$", "- proofload version: 0.0.1", text)
    return re.sub(r"<li>[^<:]*\bversion: [^<]*</li>", "<li>proofload version: 0.0.1</li>", text)


def structure_as_0_0_1_wrote_it(structure: dict[str, Any]) -> dict[str, Any]:
    """PF0 (Q4, Q10): the page structure's schema string and its version key, in both arms and in the
    provenance block, put back as 0.0.1 wrote them before the frozen digest is taken."""
    arms = {
        arm: {("proofload_version" if key == "poisson_prove_version" else key): value for key, value in structure["pair"][arm].items()}
        for arm in ("a", "b")
    }
    diff = {key: value for key, value in structure["diff"].items() if key != "poisson_prove_version"}
    return {
        **structure, "schema": "proofload.viewpair/6", "pair": {**structure["pair"], **arms},
        "diff": {**diff, "proofload_version": "0.0.1"},
    }


def verb_digests(root: Path, a: str, b: str, *, event: str, x: str, y: str, out_dir: Path) -> tuple[dict[str, str], dict[str, Result]]:
    """Every verb the spec names, on one stored pair, exit codes kept and stdout digested with the
    store root and the ``--out`` directory normalised."""
    store_arg = str(root)
    results: dict[str, Result] = {}
    digests: dict[str, str] = {}

    def norm(text: str, out: Path | None = None) -> str:
        text = text.replace(store_arg, STORE_PLACEHOLDER)
        return text if out is None else text.replace(str(out), OUT_PLACEHOLDER)

    results["runs"] = r = run_cli(["--store", store_arg, "runs"]); digests["runs"] = sha256_text(norm(r.out))
    results["diff"] = r = run_cli(["--store", store_arg, "diff", a, b, "--event", event]); digests["diff"] = sha256_text(norm(r.out))
    results["diff --format json"] = r = run_cli(["--store", store_arg, "diff", a, b, "--event", event, "--format", "json"])
    # PF0 (Q4): the tree's agreement digest is hashed behind the renamed schema string; the 0.0.1 value
    # is put back before the frozen digest is taken.
    as_0_0_1 = norm(r.out)
    for k, digest in GO1_AGREEMENT.items():
        as_0_0_1 = as_0_0_1.replace(digest, GO1_AGREEMENT_0_0_1[k])
    digests["diff --format json"] = sha256_text(as_0_0_1)
    results["check"] = r = run_cli(["--store", store_arg, "check", a, b, "--event", event]); digests["check"] = sha256_text(norm(r.out))
    for label, runs in (("report A", [a]), ("report A B", [a, b])):
        out = out_dir / label.replace(" ", "_")
        results[label] = r = run_cli(["--store", store_arg, "report", *runs, "--event", event, "--x", x, "--y", y, "--out", str(out)])
        digests[label] = sha256_text(norm(r.out, out))
        for name in ("report.md", "heatmap.svg", "receipt.html"):
            text = (out / name).read_text(encoding="utf-8") if (out / name).is_file() else None
            digests[f"{label}/{name}"] = "" if text is None else sha256_text(as_0_0_1_wrote_it(text))
    results["serve --json"] = r = run_cli(["--store", store_arg, "serve", a, b, "--event", event, "--x", x, "--y", y, "--json"])
    try:
        structure = json.loads(r.out)
        structure["pair"]["store_root"] = STORE_PLACEHOLDER
        as_0_0_1 = json.dumps(structure_as_0_0_1_wrote_it(structure), sort_keys=True)
        for k, digest in GO1_AGREEMENT.items():
            as_0_0_1 = as_0_0_1.replace(digest, GO1_AGREEMENT_0_0_1[k])
        digests["serve --json"] = sha256_text(as_0_0_1)
    except (ValueError, KeyError, TypeError):
        digests["serve --json"] = ""
    results["inspect"] = r = run_cli(["--store", store_arg, "inspect", a, "--event", event]); digests["inspect"] = sha256_text(norm(r.out))
    return digests, results


def go1_verb_digests(out_dir: Path) -> tuple[dict[str, str], dict[str, Result]]:
    return verb_digests(GO1_ROOT, GO1_A, GO1_B, event=GO1_EVENT, x=GO1_X, y=GO1_Y, out_dir=out_dir)


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


@pytest.fixture(scope="session")
def go1_store() -> Store:
    return Store(GO1_ROOT)


# ---------- P7-1: the schema and the three read modes project exactly ----------


def test_p7_1_the_schema_gains_two_nullable_strings_and_every_mode_projects_exactly(post_a7_run: tuple[Store, list[EpisodeRecord]], go1_store: Store) -> None:
    schema = store_module._SCHEMA
    assert schema.names == THIRTEEN + TRACE_COLUMNS, schema.names
    for name in TRACE_COLUMNS:
        field = schema.field(name)
        assert field.type == pa.string() and field.nullable, field
    assert "trace" in inspect.signature(Store.read).parameters
    store, records = post_a7_run
    n = len(records)
    for run_store, run_id, rows in ((store, POST_RUN, n), (go1_store, GO1_A, GO1_ROWS)):
        assert list(run_store.read(run_id).columns) == THIRTEEN
        assert list(run_store.read(run_id, meta=True).columns) == THIRTEEN
        assert list(run_store.read(run_id, meta=False).columns) == ELEVEN
        assert list(run_store.read(run_id, trace="full").columns) == THIRTEEN
        assert list(run_store.read(run_id, trace="none").columns) == THIRTEEN
        assert list(run_store.read(run_id, meta=False, trace="none").columns) == ELEVEN
        envelope = run_store.read(run_id, trace="envelope")
        assert list(envelope.columns) == THIRTEEN + ["trace"] and len(envelope) == rows
        narrow = run_store.read(run_id, meta=False, trace="envelope")
        assert list(narrow.columns) == ELEVEN + ["trace"] and len(narrow) == rows
        assert "trace_obs" not in envelope.columns and "trace_obs" not in narrow.columns
        empty = run_store.read(run_id, keys=[], trace="envelope")
        assert list(empty.columns) == THIRTEEN + ["trace"] and len(empty) == 0
        assert list(run_store.read(run_id, keys=[], meta=False, trace="envelope").columns) == ELEVEN + ["trace"]
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
    assert len(parts) == 2 and pq.read_schema(parts[0]).names == THIRTEEN and pq.read_schema(parts[1]).names == THIRTEEN + TRACE_COLUMNS
    expected = {(r.config_hash, r.replicate_index): r for r in old + new}
    full = store.read(MIXED_RUN, trace="full")
    assert list(full.columns) == THIRTEEN and set(keys_of(full)) == set(expected)
    for key, row in rows_by_key(full).items():
        assert row.meta["trace"] is not None and isinstance(row.meta["trace"], dict), key
        assert canonical(row.meta["trace"]) == canonical(expected[key].meta["trace"]), key
    envelope = store.read(MIXED_RUN, trace="envelope")
    assert list(envelope.columns) == THIRTEEN + ["trace"] and set(keys_of(envelope)) == set(expected)
    for key, row in rows_by_key(envelope).items():
        assert row.trace is not None and isinstance(row.trace, dict), key
        assert row.trace["spans"] and all(s["input"] is None and s["output"] is None for s in row.trace["spans"]), key
        # Q3 (c): the decoded ``meta`` of a pre-A7 row has its ``"trace"`` key removed too.
        assert isinstance(row.meta, dict) and "trace" not in row.meta and row.meta["k"] == expected[key].meta["k"], key
    narrow = store.read(MIXED_RUN, meta=False, trace="envelope")
    assert list(narrow.columns) == ELEVEN + ["trace"]
    assert all(row.trace is not None for row in narrow.itertuples(index=False))
    # Q7 (b): ``"none"`` strips a pre-A7 row's ``meta["trace"]`` so the layouts stay indistinguishable.
    none = store.read(MIXED_RUN, trace="none")
    assert list(none.columns) == THIRTEEN
    for key, row in rows_by_key(none).items():
        assert isinstance(row.meta, dict) and "trace" not in row.meta and row.meta["k"] == expected[key].meta["k"], key
    assert list(store.read(MIXED_RUN, meta=False, trace="none").columns) == ELEVEN


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
        assert pq.read_schema(part).names == THIRTEEN + TRACE_COLUMNS
    assert all(v == POISON for v in raw_column(store, POISONED_RUN, "meta").values())
    assert all(v == POISON for v in raw_column(store, POISONED_RUN, "trace_obs").values())
    narrow = store.read(POISONED_RUN, meta=False, trace="envelope")
    assert list(narrow.columns) == ELEVEN + ["trace"] and len(narrow) == len(records)
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
    assert store_module._SCHEMA.names[-2:] == TRACE_COLUMNS
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


# ---------- P7-10: every verb exits 0 on Go1 and the mock pair; Go1's bytes are the dispatch commit's ----------


def test_p7_10_every_verb_exits_0_on_go1_and_the_mock_pair_and_go1s_bytes_are_unchanged(go1_store: Store, mock_pair: MockPair, tmp_path: Path) -> None:
    # The precondition: the mock pair was written in the post-A7 layout, or this asserts nothing.
    store = Store(mock_pair.root)
    for run_id in (mock_pair.a, mock_pair.b):
        for part in parts_of(store, run_id):
            assert pq.read_schema(part).names == THIRTEEN + TRACE_COLUMNS, part
        frame = store.read(run_id, meta=False, trace="envelope")
        assert all(row.trace is not None and isinstance(row.trace, dict) for row in frame.itertuples(index=False))
    for part in (GO1_ROOT / GO1_A / "episodes" / "part-00000.parquet", GO1_ROOT / GO1_B / "episodes" / "part-00000.parquet"):
        assert pq.read_schema(part).names == THIRTEEN, part
    digests, results = go1_verb_digests(tmp_path / "go1")
    for verb, r in results.items():
        assert r.code == 0 and r.err == "", (verb, r.code, r.err)
    assert digests == GO1_VERB_SHA256, {k: (digests[k], GO1_VERB_SHA256.get(k)) for k in digests if digests[k] != GO1_VERB_SHA256.get(k)}
    mock_digests, mock_results = verb_digests(mock_pair.root, mock_pair.a, mock_pair.b, event=MOCK_EVENT, x="tool_fail_rate", y="task_id", out_dir=tmp_path / "mock")
    for verb, r in mock_results.items():
        assert r.code == 0 and r.err == "", (verb, r.code, r.err)
    assert all(len(d) == HEX64_LEN for d in mock_digests.values()), mock_digests
    r = mock_results["runs"]
    assert [line.split()[0] for line in r.out.splitlines()[2:]] == sorted((mock_pair.a, mock_pair.b))
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


def test_p7_12_the_split_does_not_move_the_agreement_digest_across_layouts_and_go1s_literals_hold(crossed_twice: Store, go1_store: Store) -> None:
    store = crossed_twice
    for run_id in ("pre-a", "pre-b"):
        assert [pq.read_schema(p).names for p in parts_of(store, run_id)] == [THIRTEEN]
    for run_id in ("post-a", "post-b"):
        assert all(pq.read_schema(p).names == THIRTEEN + TRACE_COLUMNS for p in parts_of(store, run_id))
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
    for k, events in ((1, ("fell",)), (2, ("fell", "survived"))):
        fa, fb = go1_store.read(GO1_A, meta=False), go1_store.read(GO1_B, meta=False)
        ma, mb = go1_store.manifest(GO1_A), go1_store.manifest(GO1_B)
        for method in ("fisher_bh", "mcnemar_bh"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
                multi = multi_diff(fa, fb, events=list(events), method=method, q=Q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]
            assert agreement_digest(multi) == GO1_AGREEMENT[k], (k, method)
        assert grow_tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, n_permutations=PERMUTATIONS, seed=SEED).agreement == GO1_AGREEMENT[k]
