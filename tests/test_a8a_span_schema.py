"""A8a oracle: invariants P8-1 to P8-6, P8-13 to P8-19, P8-21 and P8-22 of
[[Proofload - Spec A8a Span Schema]] section 4, written before the eight span fields, the seventh
trace key, ``OUTCOME_BY``, ``GATE``, ``ALIAS_MAP_VERSION``, the lifts, ``record()``'s three kwargs,
``inspect``'s four columns and the two renames exist, against ``0ef8c3c`` -- T.4 prep's closing
commit, A8a's dispatch commit (the spec was written at ``afc1f3b`` and the probes first ran at
``3bf4083``; ``src/`` and the nine retrofitted test files are byte-identical across all three,
measured by ``git diff --name-only``).

**The register, built to as decided at dispatch (spec section 10):** Q1 (c) the alias map stays
GenAI-only and one real OpenInference payload went through ``from_otel`` at step zero -- 21 keys
on a chat span, 0 aliased, 0 lifted, 10 routed as observation content, ``tokens`` and the model
name lost for fields that already exist, none of A8a's eight carriers present; (b) is triggered
for ``tokens`` and reported, not taken. Q2 (a) no ``graph.node.*`` identity entries in
``ATTRIBUTE_ALIASES``; T20 is untouched. Q3 (b)/(c): ``FAULT_KEY`` and ``FAULT_POSITION_KEY`` are
not A8a's and ``TRACE_EXPORTS`` is 25 names. Q4 (a) ``ALIAS_MAP_VERSION == "1"`` and P8-13 asserts
the **binding**, not the literal (the string ``"1"`` appears 0 times in ``src/`` at ``3bf4083``,
measured). Q5 (a) two cells. Q6 (a) ``EVALUATOR`` is not a gate marker. Q7 (a)
``_ORIGINAL_ERROR_TYPE`` survives. Q8 (a) the four columns, after ``error``.

**Two cells, and no invariant is cell-specific -- a result, not an assumption** (Master Action
List section 18 standing rule 15, spec T7). pandas 2.3.3 and pandas 3.0.5, A22's recipe. Every
one of A8a's nine fields reaches disk inside the ``trace`` / ``trace_obs`` JSON columns, never as
a Parquet column, so the pandas major cannot see any of them; the cell that could disagree is the
mutation table, not the red set. Every test here is asserted in both cells: **42 tests,
42 + 42 = 84 ids over the two cells against the oracle's own 42.** Nullness is by identity in
every clause (spec section 3.10): ``is None`` / ``is not None``, never ``pd.isna`` and never a bare
truth test.

**Standing rule 12 -- the classified red set on the retrofit commits (``9996ce3`` + ``268b64a``) with
this file and its fixture added, measured on two pristine ``git archive`` copies before any source
edit, venvs from the repo venv's freeze closure differing in exactly pandas, collection verified
1941 = 1941 = 1941 and then 1983 with this file, baselines 1934 passed / 7 skipped / 0 failed in
both cells at ``0ef8c3c``: 90 failed / 1886 passed / 7 skipped, identical test by test in both
cells.** The ninety: the **39** tests here that are not P8-21's two or P8-22 (every one for its
expected cause -- the eight fields, the seventh key, ``OUTCOME_BY`` / ``GATE`` / ``ALIAS_MAP_VERSION``,
``record()``'s kwargs, the lifts, the nine columns, the manifest key and the two renames do not exist
yet); and **51** retrofit reds -- ``test_m12_trace.py`` 19 (fifteen tests reading the 21-key ``SPAN_A``
/ ``SPAN_B`` through a 13-key ``from_dict``: T1 x2, T2 x2, T3 x2, T5 x3, T6, T7, T9, T11, T26 x2; T23
on ``span.operation``; T29 on ``tries``; T30 on the nine-column regex), ``test_m3_timeout_trace.py`` 12
(E7, E8 x3, E11 and E1's round trip, field-order, seven-key and eighth-key tests on the seven-key
dicts; E12 on 25 exports; E9 x2 on the regex), ``test_m3_crash_trace.py`` 10 (K1 x2, K3, K5 x3, K6 x2
on the 21-key dicts; K7 on the regex; K8 on 25 exports), ``test_m4_read.py`` 3 (R6 on the regex),
``test_m10_cli.py`` 2 (I15 on the regex, I18 on 21 keys), ``test_a7_storage.py`` 2 (P7-4 on 21 keys,
P7-10 on eight tabs), ``test_m3_capture.py`` 1 (C4 on nine manifest keys), ``test_m12_kinds.py`` 1
(T37), ``test_pilot_golden.py`` 1 (P12 on 25 exports). **Nothing else is red.** The pandas 3 cell adds
nothing: every A8a field reaches disk inside a JSON string. The copies skip 7 where the repo skips 5,
the two extra being ``test_pilot_golden.py``'s real-suite pair (the gitignored ``HumanEval.jsonl.gz``);
the other five are T.4's ``tau2 is not installed`` pair and the three the repo always skips.

**What step zero measured at ``3bf4083`` (spec section 7.4), so the oracle rests on runs and not
on reads.** (1) The kind-ladder guard fires: adding ``openinference.span.kind`` to ``_LIFTED_KEYS``
and nothing else turns nine tests in ``test_m12_kinds.py`` red (the seven T36 OpenInference
parametrisations, the case-insensitive test, and T37's vendor-keys test); both vendor keys, thirteen.
(2) The ``STEP_LINE_RE`` census, run by widening ``cli.py``'s line to nine columns in a pristine copy
with the regex unamended: **six positive assertion sites, eight tests red** (``test_m10_cli.py:273``
via I15; ``test_m3_crash_trace.py:945`` K7; ``test_m12_trace.py:1512`` T30;
``test_m3_timeout_trace.py:1165`` E9 and ``:1199`` via ``step_columns``; ``test_m4_read.py:286`` via
three R6 tests) and **six negative sites, four of them unpaired and silently green**
(``test_m10_cli.py:1072`` I16, ``test_m12_trace.py:1469`` T30, ``test_m3_timeout_trace.py:1224`` E9,
and ``test_m3_timeout_trace.py:1214`` E9 -- reached through the ``step_columns`` helper and named in
no document). The spec's "five" counts ``test_m3_crash_trace.py:951`` and
``test_m3_timeout_trace.py:1164``, which sit inside K7 and E9 beside a positive count on the same
block and went red with them, and misses ``:1214``. The retrofit pairs all six with an explicit
control and P8-21 scans for it. (3) ``split`` and ``assemble`` **do** name ``span_id``, ``attrs``
and ``spans`` as literals, so P8-19's grep clause as the spec words it is false at ``3bf4083``; the
clause asserted here is the one that catches the mutant -- no literal from the field set outside
the navigation keys, and none of A8a's nine names. (4) ``ALIAS_MAP_VERSION`` has zero bindings and
``"1"`` zero literal sites in ``src/``. (5) ``test_a7_storage.py:933`` used ``alias_map_version`` as
its example of a key ``from_dict`` rejects; A8a makes it a valid key, so that row is retrofitted to
an unknown key -- a site in no inventory.

**Mutation pass, eighteen rows plus control, whole suite on rsync copies of the shadow shim under the
thread caps (harness fact 6), pandas 2.3.3.** Measurement order: the control, rows 2-5 and the two
oracle self-checks ran on the shim **before** the second retrofit commit and carry its three reds
(P7-10, E1 x2 -- the sites that commit fixes) in every row, not counted below; the control is
**3 failed / 1977 passed / 7 skipped** for exactly those three and the amended tests are green on
the shim; rows 6-17 and 4b ran after. Eighteen caught, **no survivor**. Spelling recorded where a
sole catch is claimed.

| Row | Mutation (spelling) | Caught by, measured |
|---|---|---|
| 1 | control, no edit | -- |
| 2 | ``from_otel`` post-pass numbers ``attempt`` by ``step_name`` repetition under one parent | **P8-5 alone** |
| 3 | ``split`` rebuilds ``envelope["spans"]`` from the twenty-one keys enumerated literally | P8-19 grep half **and** P8-22 (any edit to ``split`` moves its digest) |
| 4 | ``split`` reads ``span["truncated"]`` / ``span["bytes_original"]`` in a no-op branch | P8-19 grep half and P8-22 -- the spelling names a field literal |
| 4b | ``split``: ``bodies = dict()`` for ``{}`` (no key named, behaviour identical) | **P8-22 alone** |
| 5 | the ``gate=gate`` kwarg dropped at the hand-written ``Span(...)`` in ``_span`` | **P8-3 contrapositive alone** |
| 6 | ``merge`` takes the first non-None ``alias_map_version`` instead of the agreed one | **P8-13 merge test alone** |
| 7 | ``gate = "emitted"`` when the span *name* is ``guardrail`` | **P8-6 named-guardrail test alone** |
| 8 | the unrecognised operation still stashed under ``proofload.original_operation`` | P8-16, T23 (amended) |
| 9 | ``graph.node.id`` added to ``_LIFTED_KEYS`` (Q2 crossed) | **P8-4 alone** |
| 10 | ``_vendor_kind(attrs)`` after the lift (section 8 trap 1) | T36 x11, T37, P8-4, P8-6 -- 15 |
| 11 | ``_span_mapping`` emits no ``traceId`` | **P8-14 alone** |
| 12 | ``_capture_record`` without ``alias_map_version`` | P8-17, C4 |
| 13 | the mock emits ``attrs={"attempts": ...}`` again | P8-15, T29 |
| 14 | ``inspect`` prints ``attempt`` before ``step_name`` | **P8-18 columns test alone** |
| 15 | the ``bytes_original``-without-``truncated`` clause dropped from ``Span.__post_init__`` | **P8-2 (that parametrisation) alone** |
| 16 | a second ``ALIAS_MAP_VERSION = "1"`` binding in ``executor.py`` | **P8-13 binding test alone** |
| 17 | ``record()`` defaults ``gate`` to ``"emitted"`` | P8-3 producer test, P8-3 contrapositive |
| s1 | *(oracle self-check, four files)* one ``STEP_LINE_RE`` copy back to five columns | P8-21 copy test, I15, **and I16 -- the control line turns the vacuous negative red** |
| s2 | *(oracle self-check, four files)* the control removed from I16 | **P8-21 pairing test alone** |

**Green-before-and-after, named so its green is not read as evidence** (standing rule 12): P8-19's
grep half (``split`` / ``assemble`` already pass it); P8-22 in its entirety (per-symbol digests of
A7's surface at ``3bf4083``); the six negative ``STEP_LINE_RE`` uses (they pass on the unamended
regex vacuously and on the amended one for the right reason; the control makes the difference
visible); E1's renamed six-key rejection test, green on the bare tree because the rejection message
lists the expected keys and ``"truncated"`` is among them, and green after the build because the key
is then genuinely missing; A22's V5; T36's four tests in ``test_m12_kinds.py``, which are the guard that goes red if
the build lifts the vendor keys before the ladder reads them.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import poisson_prove.cli as cli
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import Span, Trace, TraceValidationError
from conftest import quickstart_design

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "poisson_prove"
TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures" / "trace"
# PF3 (spec sections 8.8 and 14): the one copy is the packaged spec; this is its design at
# the 100 replicates this file was frozen at.
QUICKSTART = quickstart_design()
LOGGER_NAME = "poisson_prove.trace"
EPOCH = 1_756_900_000_000_000_000

# ---------- spec constants (section 2), spelled here so the file collects before the build ----------

SPAN_FIELDS_SPEC: tuple[str, ...] = (
    "span_id", "parent_id", "kind", "name", "start_ns", "end_ns",
    "input", "output", "tokens", "confidence", "error", "code", "attrs",
    "operation", "step_name", "outcome", "outcome_by", "attempt", "gate", "truncated", "bytes_original",
)
NEW_FIELDS: tuple[str, ...] = SPAN_FIELDS_SPEC[13:]
TRACE_KEYS_SPEC: tuple[str, ...] = ("schema", "source", "source_version", "dropped", "spans", "truncated", "alias_map_version")
OUTCOME_BY_SPEC = ("code", "llm", "self", "human")
GATE_SPEC = ("emitted", "declared")
ALIAS_MAP_VERSION_SPEC = "1"  # section 10 Q4 (a)
STATUS_CODES = frozenset({"OK", "UNSET", "ERROR"})
LIFTED_CARRIERS = (
    "openinference.span.kind", "traceloop.span.kind", "graph.node.name",
    "poisson_prove.step_name", "poisson_prove.outcome", "poisson_prove.outcome_by", "poisson_prove.attempt", "poisson_prove.gate",
)
MANIFEST_CAPTURE_KEYS = frozenset({
    "requested", "active", "reason", "instrumented", "semconv", "alias_map_version", "content", "max_observation_bytes", "max_spans",  # A8b: the key's second move (A8a T4)
})
OTLP_FIXTURES = ("otlp_agent_chat.json", "otlp_kinds.json", "otlp_aliases.json", "otlp_dropped.json")
STEP_LINE_FILES = ("test_m10_cli.py", "test_m12_trace.py", "test_m3_crash_trace.py", "test_m3_timeout_trace.py", "test_m4_read.py")
NINE_COLUMNS = "  3\tllm\tchat gpt-4o\t0.5\t-\tplan\t2\tpass\temitted"
FIVE_COLUMNS = "  3\tllm\tchat gpt-4o\t0.5\t-"

#: P8-22: sha256 of ``ast.get_source_segment`` for each symbol A7 owns, measured at ``3bf4083``.
A7_SURFACE: dict[str, dict[str, str]] = {
    "trace.py": {
        # PF0 (Q4): LOGPROBS_KEY and OBSERVATION_KEYS are no longer pinned; the rename changes both
        # (the span key prefix), and no digest of them can be frozen honestly before the build exists.
        "_OBSERVATION_PREFIXES": "08fd8423badb0404b15168948cbc2f22baf07277aa6570e9f36d35e3bf71a40a",
        "_ObservationKeys": "234e6e2bf19ab9d167fb4a9fd108c6c6e5843ee0730abde04a2b92e5688b7f41",
        # ``split`` retired from this table by A8b Session A, narrowed and never re-minted (ADR-077 / C19):
        # A8b widens its loop body, which is the one A7 symbol A8b may edit. Owner: A8b. Cover:
        # tests/test_a8b_cut_and_cap.py P8-25, which re-asserts every other symbol here byte-identical,
        # pins split's signature line and confines its edit to the loop. Digest at retirement: a63f24ba...13df24.
        "assemble": "89ec3fc90530156b4a35bfedd2d5fd5da32412bc70b9d66f80be089716e5a1fe",
    },
    "store.py": {
        "_SCHEMA": "7a667ffbc1067dce738a839266851ba6c11dacf989e1fd58a66775490a80c02a",
        "_NULLABLE_STRING_COLUMNS": "c7f3ae63b60a6d4216a9d9ebf8856d2d7151491f59903b447d775b25263a9fe0",
        "Store.append": "8bdf8983f500500c1f33b16039d0d018085de9f9649561f10d257f09a8e87bb7",
        "Store.read": "a853c1b49fbf43c0e65038b9620e668ff180acf68601dcef4cb3eace63c834cb",
    },
}

# ---------- helpers: data construction, never an assertion ----------


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def loop_spans() -> dict[int, Span]:
    """``otlp_loop.json`` through ``from_otel``, keyed by the span id as an integer (1..16)."""
    from poisson_prove.trace import from_otel

    tr = from_otel(load_fixture("otlp_loop.json"))
    assert tr.dropped == 0 and len(tr.spans) == 16, (tr.dropped, len(tr.spans))
    return {int(s.span_id, 16): s for s in tr.spans}


def plain_span(**overrides: Any) -> Span:
    base: dict[str, Any] = {"span_id": "00000000000000a1", "parent_id": None, "kind": "tool", "name": "x", "start_ns": EPOCH, "end_ns": EPOCH + 1_000}
    base.update(overrides)
    return Span(**base)


def span_dict(**overrides: Any) -> dict[str, Any]:
    d: dict[str, Any] = {name: None for name in SPAN_FIELDS_SPEC}
    d.update({"span_id": "00000000000000a1", "parent_id": None, "kind": "tool", "name": "x", "start_ns": EPOCH, "end_ns": EPOCH + 1_000, "attrs": {}})
    d.update(overrides)
    return d


def trace_dict(*spans: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "schema": "poisson-prove.trace/1", "source": "otel", "source_version": "1.42.0", "dropped": 0,
        "spans": [dict(s) for s in spans], "truncated": None, "alias_map_version": None,
    }
    d.update(overrides)
    return d


def flat_span(n: int, name: str, **attrs: Any) -> dict[str, Any]:
    """One flat OTLP span mapping (the second input form), string attributes."""
    return {
        "spanId": f"{n:016x}", "name": name, "startTimeUnixNano": str(EPOCH), "endTimeUnixNano": str(EPOCH + 1_000_000),
        "attributes": [{"key": k, "value": {"stringValue": str(v)}} for k, v in attrs.items()],
    }


def function_source(path: Path, qualname: str) -> str:
    """``ast.get_source_segment`` of a top-level def / class / assignment, or ``Class.method``."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    head, _, tail = qualname.partition(".")
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name == head:
            if not tail:
                return ast.get_source_segment(src, node) or ""
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == tail:
                    return ast.get_source_segment(src, member) or ""
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == head for t in targets):
                return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{qualname} not found at top level of {path.name}")


def string_literals(node: ast.AST) -> set[str]:
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def synthetic_run_with_trace(root: Path, run_id: str, trace: Mapping[str, Any]) -> None:
    """One violated row carrying ``trace`` in ``meta`` -- the shape T30's rejected-trace test stores."""
    store = Store(root)
    store.create_run(RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="tool_calls", run_salt="syn",
        axis_types={"x": "continuous"}, backend="synthetic", environment={},
    ))
    ep = Episode(outcome="violated", t=1.0, horizon=20.0, meta={"trace": dict(trace)})
    rec = EpisodeRecord.from_episode(ep, run_id=run_id, config={"x": 1.0}, seed=1, replicate_index=0, wall_time=0.0)
    store.append(run_id, [rec])
    store.mark_complete(run_id)


def inspect_lines(root: Path, run_id: str, event: str) -> list[str]:
    out, err = StringIO(), StringIO()
    code = cli.main(["--store", str(root), "inspect", run_id, "--event", event], stdout=out, stderr=err, stdin=StringIO())
    assert code == 0 and err.getvalue() == "", out.getvalue() + err.getvalue()
    return out.getvalue().splitlines()


STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")


# ---------- P8-1: the twenty-one-key span and the seven-key trace ----------


def test_p8_1_span_to_dict_has_exactly_the_twenty_one_keys_in_order_none_where_unset() -> None:
    d = plain_span().to_dict()
    assert list(d) == list(SPAN_FIELDS_SPEC), list(d)
    for name in NEW_FIELDS:
        assert d[name] is None, name
    assert tuple(f.name for f in dataclasses.fields(Span)) == SPAN_FIELDS_SPEC
    full = Span.from_dict(span_dict(operation="chat", step_name="plan", outcome="pass", outcome_by="code", attempt=2, gate="emitted", truncated="observation", bytes_original=9)).to_dict()
    assert [full[name] for name in NEW_FIELDS] == ["chat", "plan", "pass", "code", 2, "emitted", "observation", 9]
    assert Span.from_dict(full).to_dict() == full


def test_p8_1_from_dict_rejects_thirteen_keys_naming_the_first_missing_and_a_twenty_second_naming_it() -> None:
    thirteen = {k: v for k, v in span_dict().items() if k not in NEW_FIELDS}
    assert len(thirteen) == 13
    with pytest.raises(TraceValidationError) as info:
        Span.from_dict(thirteen)
    assert "missing" in str(info.value) and "attempt" in str(info.value), str(info.value)
    with pytest.raises(TraceValidationError) as info:
        Span.from_dict({**span_dict(), "latency_ms": 3})
    assert "latency_ms" in str(info.value), str(info.value)


def test_p8_1_trace_to_dict_has_exactly_seven_keys_and_from_dict_rejects_six_and_eight() -> None:
    d = Trace(spans=(), source="record").to_dict()
    assert list(d) == list(TRACE_KEYS_SPEC), list(d)
    assert d["alias_map_version"] is None
    assert tuple(f.name for f in dataclasses.fields(Trace)) == ("spans", "source", "source_version", "dropped", "truncated", "alias_map_version")
    six = {k: v for k, v in trace_dict().items() if k != "alias_map_version"}
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(six)
    assert "alias_map_version" in str(info.value), str(info.value)
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict({**trace_dict(), "steps": []})
    assert "steps" in str(info.value), str(info.value)
    stamped = Trace.from_dict(trace_dict(span_dict(), alias_map_version="1"))
    assert stamped.alias_map_version == "1" and stamped.to_dict()["alias_map_version"] == "1"


# ---------- P8-2: the validators ----------


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"outcome": "pass", "outcome_by": "robot"}, id="outcome_by-not-in-OUTCOME_BY"),
        pytest.param({"gate": "maybe"}, id="gate-not-in-GATE"),
        pytest.param({"attempt": 0}, id="attempt-below-one"),
        pytest.param({"attempt": -1}, id="attempt-negative"),
        pytest.param({"attempt": True}, id="attempt-bool"),
        pytest.param({"attempt": "2"}, id="attempt-str"),
        pytest.param({"bytes_original": 3}, id="bytes_original-without-truncated"),
        pytest.param({"truncated": "observation", "bytes_original": 0}, id="bytes_original-below-one"),
        pytest.param({"truncated": "observation", "bytes_original": True}, id="bytes_original-bool"),
        pytest.param({"outcome_by": "code"}, id="outcome_by-without-outcome"),
        pytest.param({"operation": 3}, id="operation-not-str"),
        pytest.param({"step_name": 3}, id="step_name-not-str"),
        pytest.param({"outcome": 3}, id="outcome-not-str"),
        pytest.param({"truncated": 3}, id="truncated-not-str"),
    ],
)
def test_p8_2_each_invalid_value_raises_at_the_constructor_and_inside_from_dict(bad: dict[str, Any]) -> None:
    with pytest.raises(TraceValidationError):
        plain_span(**bad)
    with pytest.raises(TraceValidationError):
        Span.from_dict(span_dict(**bad))


def test_p8_2_the_vocabularies_and_the_free_fields() -> None:
    from poisson_prove import trace as trace_module
    from poisson_prove.trace import GATE, OUTCOME_BY

    assert OUTCOME_BY == OUTCOME_BY_SPEC and GATE == GATE_SPEC
    assert {"OUTCOME_BY", "GATE", "ALIAS_MAP_VERSION"} <= set(trace_module.__all__)
    for who in OUTCOME_BY:
        assert plain_span(outcome="x", outcome_by=who).outcome_by == who
    for gate in GATE:
        assert plain_span(gate=gate).gate == gate
    # operation is verbatim and never checked against a vocabulary (D7); outcome is a free label (ADR-039).
    for op in ("chat", "frobnicate", "CHAT", "guardrail", ""):
        assert plain_span(operation=op).operation == op
    assert plain_span(outcome="").outcome == "" and plain_span(outcome="whatever").outcome == "whatever"
    assert plain_span(truncated="observation", bytes_original=1).bytes_original == 1
    # A trace-level truncated reason is a different field: setting it never sets a span's.
    cut = Trace(spans=(plain_span(),), source="otel", truncated="timeout")
    assert cut.truncated == "timeout" and cut.spans[0].truncated is None and cut.spans[0].bytes_original is None
    with pytest.raises(TraceValidationError):
        Trace(spans=(), source="record", alias_map_version=1)  # type: ignore[arg-type]


# ---------- P8-3: every producer leaves the eight None; the recorder's contrapositive ----------


def all_eight_none(span: Span) -> bool:
    return all(getattr(span, name) is None for name in NEW_FIELDS)


OPERATION_CARRIERS = ("gen_ai.operation.name", "llm.request.type", "openinference.span.kind", "traceloop.span.kind")


def raw_spans_with_an_operation_carrier(payload: Any) -> int:
    """How many raw span mappings in an OTLP payload (nested or flat) carry an operation carrier."""
    count = 0
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            attributes = node.get("attributes")
            if "spanId" in node or "span_id" in node:
                keys = {a.get("key") for a in attributes} if isinstance(attributes, list) else set()
                count += any(k in keys for k in OPERATION_CARRIERS)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return count


def test_p8_3_every_producer_leaves_all_eight_fields_none_without_a_carrier() -> None:
    from poisson_prove.examples import mock_agent
    from poisson_prove.trace import collect, from_litellm, from_otel, record

    with collect() as c:
        with record("tool", "search") as h:
            h.output = {"hits": 3}
    assert len(c.trace.spans) == 1 and all_eight_none(c.trace.spans[0])

    # The seven committed OTLP payloads carry gen_ai.operation.name on most spans, so operation --
    # whose carrier that is -- is exempt exactly there: non-None on as many spans as carried one,
    # and the other seven fields None everywhere (no fixture carries their carriers).
    payloads = [load_fixture(name) for name in OTLP_FIXTURES] + list(load_fixture("otlp_encodings.json").values())
    assert len(payloads) == 7
    seen = 0
    for name, payload in zip(OTLP_FIXTURES + ("encodings",) * 3, payloads, strict=True):
        tr = from_otel(payload)
        with_operation = 0
        for span in tr.spans:
            seen += 1
            assert all(getattr(span, field) is None for field in NEW_FIELDS if field != "operation"), (name, span.span_id, span.to_dict())
            with_operation += span.operation is not None
        if name != "otlp_dropped.json":  # dropped spans never reach the count
            assert with_operation == raw_spans_with_an_operation_carrier(payload), name
    assert seen >= 20

    from datetime import datetime

    calls = load_fixture("litellm_calls.json")
    for call in calls:
        for key in ("start_time", "end_time"):
            if isinstance(call.get(key), str):
                call[key] = datetime.fromisoformat(call[key])
    lite = from_litellm(calls)
    assert len(lite.spans) >= 1 and all(all_eight_none(s) for s in lite.spans)

    for seed in range(5):
        ep = mock_agent.rollout({"task_id": "checkout", "tool_fail_rate": 0.3}, seed)
        tr = Trace.from_dict(ep.meta["trace"])
        assert len(tr.spans) >= 1 and all(all_eight_none(s) for s in tr.spans)


def test_p8_3_contrapositive_a_record_block_that_sets_each_field_sees_it_on_the_closed_span() -> None:
    from poisson_prove.trace import SpanHandle, collect, record, step

    assert {"outcome", "outcome_by"} <= {f.name for f in dataclasses.fields(SpanHandle)}
    with collect() as c:
        with record("tool", "search", step_name="lookup", attempt=2, gate="emitted") as h:
            h.outcome = "pass"
            h.outcome_by = "self"
        with record("tool", "plain"):
            pass
    by_name = {s.name: s for s in c.trace.spans}
    full = by_name["search"]
    assert (full.step_name, full.attempt, full.gate, full.outcome, full.outcome_by) == ("lookup", 2, "emitted", "pass", "self")
    assert full.operation is None and full.truncated is None and full.bytes_original is None
    assert all_eight_none(by_name["plain"])

    @step(name="verify", step_name="verify")
    def verify() -> int:
        return 1

    @step(name="bare")
    def bare() -> int:
        return 2

    with collect() as c:
        assert verify() == 1 and bare() == 2
    by_name = {s.name: s for s in c.trace.spans}
    assert by_name["verify"].step_name == "verify" and all(getattr(by_name["verify"], n) is None for n in NEW_FIELDS if n != "step_name")
    assert all_eight_none(by_name["bare"])


def test_p8_3_a_bad_handle_value_drops_the_span_with_a_warning_and_never_raises(caplog: pytest.LogCaptureFixture) -> None:
    from poisson_prove.trace import collect, record

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    with collect() as c:
        with record("tool", "judged") as h:
            h.outcome = "pass"
            h.outcome_by = "robot"
        with record("tool", "kept"):
            pass
    assert [s.name for s in c.trace.spans] == ["kept"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "judged" in r.getMessage()]
    assert len(warnings) == 1, [r.getMessage() for r in caplog.records]


# ---------- P8-4: the lifts on otlp_loop.json ----------


def test_p8_4_graph_node_name_and_proofload_attempt_are_lifted_and_leave_attrs() -> None:
    by = loop_spans()
    for sid, step_name in ((2, "lookup"), (3, "lookup"), (4, "lookup"), (6, "check"), (7, "check"), (8, "check"), (1, "plan"), (5, "verify")):
        assert by[sid].step_name == step_name, (sid, by[sid].step_name)
        assert "graph.node.name" not in by[sid].attrs, sid
    assert by[2].attempt == 1 and by[3].attempt == 2
    assert "poisson_prove.attempt" not in by[2].attrs and "poisson_prove.attempt" not in by[3].attrs
    assert (by[2].outcome, by[2].outcome_by) == ("pass", "code")
    assert (by[3].outcome, by[3].outcome_by) == ("fail", "llm")
    for sid in (2, 3):
        assert "poisson_prove.outcome" not in by[sid].attrs and "poisson_prove.outcome_by" not in by[sid].attrs
    for sid in (12, 13):
        assert "poisson_prove.step_name" not in by[sid].attrs and "poisson_prove.gate" not in by[sid].attrs
    assert by[12].step_name == "policy" and by[13].step_name == "hook"


def test_p8_4_guardrail_is_an_emitted_gate_and_evaluator_is_not_and_graph_node_ids_survive() -> None:
    by = loop_spans()
    assert (by[9].kind, by[9].operation, by[9].gate) == ("other", "guardrail", "emitted")
    assert (by[10].kind, by[10].operation, by[10].gate) == ("other", "evaluator", None)
    for sid in (9, 10, 11, 14):
        assert "openinference.span.kind" not in by[sid].attrs, sid
    assert "traceloop.span.kind" not in by[15].attrs and (by[15].kind, by[15].operation) == ("agent", "workflow")
    # Q2 (a): graph.node.id and graph.node.parent_id are neither lifted nor aliased; they survive in attrs.
    for sid, node, parent in ((2, "n2", "n1"), (3, "n3", "n1"), (4, "n4", "n1"), (6, "n6", "n5")):
        assert by[sid].attrs["graph.node.id"] == node and by[sid].attrs["graph.node.parent_id"] == parent, sid
    assert by[1].attrs["graph.node.id"] == "n1" and "graph.node.parent_id" not in by[1].attrs
    from poisson_prove.trace import ATTRIBUTE_ALIASES, _LIFTED_KEYS

    assert "graph.node.id" not in ATTRIBUTE_ALIASES and "graph.node.parent_id" not in ATTRIBUTE_ALIASES
    assert "graph.node.id" not in _LIFTED_KEYS and "graph.node.parent_id" not in _LIFTED_KEYS
    assert set(LIFTED_CARRIERS) <= set(_LIFTED_KEYS)


# ---------- P8-5: attempt is never derived ----------


def test_p8_5_attempt_is_never_derived_from_name_repetition_or_nesting() -> None:
    by = loop_spans()
    # Three spans of one step_name under one parent, no counter anywhere: all None.
    assert [by[sid].step_name for sid in (6, 7, 8)] == ["check"] * 3
    assert all(by[sid].attempt is None for sid in (6, 7, 8)), [by[sid].attempt for sid in (6, 7, 8)]
    # The third lookup, beside siblings carrying 1 and 2, is still None: a counter is read, never inferred.
    assert by[4].attempt is None
    # And the same shape through the recorder: three same-named spans in one block.
    from poisson_prove.trace import collect, record

    with collect() as c:
        for _ in range(3):
            with record("tool", "retry_me", step_name="retry"):
                pass
    assert [s.attempt for s in c.trace.spans] == [None, None, None]


# ---------- P8-6: gate is never inferred ----------


def test_p8_6_a_span_named_guardrail_with_kind_tool_has_no_gate() -> None:
    by = loop_spans()
    assert by[11].name == "guardrail" and (by[11].kind, by[11].operation, by[11].gate) == ("tool", "tool", None)


def test_p8_6_declared_on_the_wire_is_dropped_with_one_warning_and_emitted_is_taken(caplog: pytest.LogCaptureFixture) -> None:
    from poisson_prove.trace import from_otel

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    tr = from_otel([
        flat_span(21, "policy_check", **{"poisson_prove.gate": "declared"}),
        flat_span(22, "hook", **{"poisson_prove.gate": "emitted"}),
        flat_span(23, "junk", **{"poisson_prove.gate": "sometimes"}),
    ])
    assert tr.dropped == 0
    by = {int(s.span_id, 16): s for s in tr.spans}
    assert by[21].gate is None and by[22].gate == "emitted" and by[23].gate is None
    assert all("poisson_prove.gate" not in s.attrs for s in tr.spans)
    warned = [r for r in caplog.records if r.levelno == logging.WARNING and "declared" in r.getMessage()]
    assert len(warned) == 1, [r.getMessage() for r in caplog.records]
    assert loop_spans()[12].gate is None and loop_spans()[13].gate == "emitted"


# ---------- P8-13: ALIAS_MAP_VERSION ----------


def alias_map_version_bindings() -> list[str]:
    sites = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign | ast.AnnAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "ALIAS_MAP_VERSION" for t in targets):
                    value = node.value
                    literal = value.value if isinstance(value, ast.Constant) else None
                    sites.append(f"{path.relative_to(SRC)}:{node.lineno}={literal!r}")
    return sites


def test_p8_13_alias_map_version_is_bound_exactly_once_in_src_and_the_binding_is_the_value() -> None:
    from poisson_prove.trace import ALIAS_MAP_VERSION

    assert ALIAS_MAP_VERSION == ALIAS_MAP_VERSION_SPEC
    sites = alias_map_version_bindings()
    assert len(sites) == 1 and sites[0].startswith("trace.py:"), sites
    assert sites[0].endswith(f"={ALIAS_MAP_VERSION!r}"), sites


def test_p8_13_from_otel_stamps_it_and_record_and_litellm_leave_it_none() -> None:
    from poisson_prove.trace import ALIAS_MAP_VERSION, collect, from_litellm, from_otel, record

    for name in OTLP_FIXTURES + ("otlp_loop.json",):
        assert from_otel(load_fixture(name)).alias_map_version == ALIAS_MAP_VERSION, name
    assert from_otel([]).alias_map_version == ALIAS_MAP_VERSION
    with collect() as c:
        with record("tool", "x"):
            pass
    assert c.trace.alias_map_version is None
    assert from_litellm([]).alias_map_version is None
    # The recorder's capture path reaches it for free: Recorder._trace builds through from_otel.
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    from poisson_prove.capture import CaptureSpec, Recorder

    rec = Recorder(CaptureSpec(max_observation_bytes=8192), "r-a8a", "cfg:1")  # CD (D1): the cap has no default
    empty = rec._trace([], None)
    assert empty is None  # D9: nothing captured, no envelope from _trace itself
    stamped = rec._trace([flat_span(0x31, "captured")], None)
    assert stamped is not None and stamped["alias_map_version"] == ALIAS_MAP_VERSION


def test_p8_13_merge_mirrors_source_version_keeps_agreement_and_erases_disagreement() -> None:
    from poisson_prove.trace import ALIAS_MAP_VERSION, collect, from_otel, merge, record

    a = from_otel([flat_span(0x41, "a")])
    b = from_otel([flat_span(0x42, "b")])
    assert merge(a, b).alias_map_version == ALIAS_MAP_VERSION
    with collect() as c:
        with record("tool", "r"):
            pass
    assert merge(a, c.trace).alias_map_version == ALIAS_MAP_VERSION
    assert merge(c.trace, a).alias_map_version == ALIAS_MAP_VERSION
    one = Trace(spans=(plain_span(span_id="00000000000000c1"),), source="otel", alias_map_version="1")
    two = Trace(spans=(plain_span(span_id="00000000000000c2"),), source="otel", alias_map_version="2")
    assert merge(one, two).alias_map_version is None
    assert merge(c.trace, c.trace.__class__(spans=(), source="record")).alias_map_version is None


# ---------- P8-14: the trace id and the status code ----------


def test_p8_14_span_mapping_emits_trace_id_and_from_otel_keeps_it_with_the_status_code_unlifted() -> None:
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.trace import Status, StatusCode

    from poisson_prove.capture import _span_mapping
    from poisson_prove.trace import _LIFTED_KEYS, from_otel

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("a8a")
    with tracer.start_as_current_span("ok") as ok:
        ok.set_status(Status(StatusCode.OK))
    with tracer.start_as_current_span("unset"):
        pass
    with tracer.start_as_current_span("error") as bad:
        bad.set_status(Status(StatusCode.ERROR, "boom"))
    finished = exporter.get_finished_spans()
    assert len(finished) == 3
    mappings = [_span_mapping(s, content=False) for s in finished]
    for raw, sdk in zip(mappings, finished, strict=True):
        assert raw["traceId"] == format(sdk.get_span_context().trace_id, "032x"), raw
    tr = from_otel(mappings)
    assert tr.dropped == 0
    by_name = {s.name: s for s in tr.spans}
    assert {by_name[n].attrs["otel.status_code"] for n in ("ok", "unset", "error")} == STATUS_CODES
    assert by_name["ok"].attrs["otel.status_code"] == "OK" and by_name["error"].attrs["otel.status_code"] == "ERROR"
    assert by_name["unset"].attrs["otel.status_code"] == "UNSET"
    for span in tr.spans:
        assert span.attrs["otel.trace_id"] == mappings[0]["traceId"] or span.attrs["otel.trace_id"] in {m["traceId"] for m in mappings}
    assert "otel.trace_id" not in _LIFTED_KEYS and "otel.status_code" not in _LIFTED_KEYS
    assert by_name["error"].error == "boom" and by_name["ok"].error is None and by_name["unset"].error is None


def test_p8_14_on_the_fixtures_every_span_carries_both_and_error_keeps_the_shipped_rule() -> None:
    from poisson_prove.trace import from_otel

    by = loop_spans()
    assert by[1].attrs["otel.status_code"] == "UNSET" and by[2].attrs["otel.status_code"] == "OK"
    assert by[3].attrs["otel.status_code"] == "ERROR" and by[4].attrs["otel.status_code"] == "UNSET"
    for span in by.values():
        assert span.attrs["otel.trace_id"] == "7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a", span.span_id
        assert span.attrs["otel.status_code"] in STATUS_CODES, span.span_id
    assert by[3].error == "lookup failed" and by[2].error is None
    # otlp_kinds.json's two error spans, exactly as 3bf4083 reads them: status.message first, then error.type.
    kinds = {s.span_id: s for s in from_otel(load_fixture("otlp_kinds.json")).spans}
    assert kinds["0000000000000001"].error == "boom" and kinds["000000000000000e"].error == "TimeoutError"
    assert all(s.error is None for sid, s in kinds.items() if sid not in ("0000000000000001", "000000000000000e"))
    assert all(s.attrs["otel.status_code"] in STATUS_CODES and "otel.trace_id" in s.attrs for s in kinds.values())


# ---------- P8-15: the two renames ----------


def test_p8_15_modal_backend_meta_carries_infra_attempt_and_no_attempt() -> None:
    from poisson_prove import executor_modal

    source = (SRC / "executor_modal.py").read_text(encoding="utf-8")
    literals = string_literals(ast.parse(source))
    assert "attempt" not in literals and "infra_attempt" in literals
    job = ({"x": 1.0}, 7, 3, "hash", 0)
    record = executor_modal._infra_record(SimpleNamespace(run_id="r-modal"), job, RuntimeError("boom"), 2)
    assert record.backend_meta.get("infra_attempt") == 2 and "attempt" not in record.backend_meta, record.backend_meta
    assert record.backend_meta.get("i") == 3


def test_p8_15_the_mock_emits_tries_and_never_attempt() -> None:
    from poisson_prove.examples import mock_agent

    source = (SRC / "examples" / "mock_agent.py").read_text(encoding="utf-8")
    assert "attempts" not in string_literals(ast.parse(source))
    seen = set()
    for seed in range(20):
        for fn in (mock_agent.rollout, mock_agent.rollout_patched):
            tr = Trace.from_dict(fn({"task_id": "checkout", "tool_fail_rate": 0.55}, seed).meta["trace"])
            for span in tr.spans:
                assert set(span.attrs) == {"tries"} and span.attrs["tries"] in (1, 2), span.attrs
                assert span.attempt is None and span.step_name is None
                seen.add(span.attrs["tries"])
    assert seen == {1, 2}


# ---------- P8-16: operation is verbatim ----------


def test_p8_16_operation_is_the_source_operation_name_stripped_and_lowercased_including_unrecognised() -> None:
    from poisson_prove.trace import from_otel

    raw = load_fixture("otlp_kinds.json")
    expected = {}
    for span in raw:
        for a in span["attributes"]:
            if a["key"] == "gen_ai.operation.name":
                expected[span["spanId"]] = a["value"]["stringValue"].strip().lower()
    assert "frobnicate" in expected.values() and len(expected) >= 10
    for span in from_otel(raw).spans:
        assert span.operation == expected.get(span.span_id), (span.span_id, span.operation)
        assert "poisson_prove.original_operation" not in span.attrs and "gen_ai.operation.name" not in span.attrs
    by = loop_spans()
    assert (by[16].operation, by[16].kind) == ("frobnicate", "other")
    assert (by[14].operation, by[14].kind, by[14].name) == ("chat", "llm", "gpt-4o")
    from poisson_prove import trace as trace_module

    assert not hasattr(trace_module, "_ORIGINAL_OPERATION")
    assert getattr(trace_module, "_ORIGINAL_ERROR_TYPE", None) == "poisson_prove.error_type"  # section 10 Q7 (a): survives


# ---------- P8-17: the manifest's capture record ----------


def test_p8_17_environment_capture_has_the_nine_keys_and_alias_map_version_is_the_constant() -> None:
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    from poisson_prove.capture import CaptureSpec, CaptureStatus
    from poisson_prove.executor import _capture_record
    from poisson_prove.trace import ALIAS_MAP_VERSION, OTEL_SEMCONV_VERSION

    record = _capture_record(CaptureSpec(max_observation_bytes=8192), CaptureStatus(requested=False, active=False, reason=None, instrumented=()))  # CD (D1)
    assert set(record) == MANIFEST_CAPTURE_KEYS, sorted(record)
    assert record["alias_map_version"] == ALIAS_MAP_VERSION and record["semconv"] == OTEL_SEMCONV_VERSION
    assert record["max_observation_bytes"] == 8_192  # A8b: the renamed key; A8a kept the shipped spelling


# ---------- P8-18: inspect's nine columns ----------


def test_p8_18_inspect_prints_nine_columns_the_first_five_unchanged_and_dashes_for_none(tmp_path: Path) -> None:
    root = tmp_path / "store"
    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(root), "sweep", str(QUICKSTART), "--target", "poisson_prove.examples.mock_agent:rollout", "--yes"],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    assert code == 0, out.getvalue() + err.getvalue()
    # A sweep now ends with a verdict line, not 'run_id: <id>' (spec section 5.3); the run is
    # the one the empty store gained.
    (run_id,) = Store(root).runs()
    df = Store(root).read(run_id)
    rows = df[df["outcome"] == "violated"]
    # Text output shows a config_hash at 12 hex characters (spec section 5.4, rule 10).
    by_key = {(row.config_hash[:12], int(row.seed)): row for row in rows.itertuples(index=False)}
    lines = inspect_lines(root, run_id, "violated")
    blocks: list[list[str]] = []
    for line in lines:
        if line.startswith("config_hash: "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    assert len(blocks) == len(rows) >= 1
    checked = 0
    for block in blocks:
        config_hash = block[0].split(": ", 1)[1][:12]
        seed = int(next(line for line in block if line.startswith("seed: ")).split(": ", 1)[1])
        spans = Trace.from_dict(by_key[(config_hash, seed)].meta["trace"]).ordered()
        step_lines = [line for line in block if STEP_LINE_RE.match(line)]
        assert len(step_lines) == len(spans) >= 1, "\n".join(block)
        for j, (line, span) in enumerate(zip(step_lines, spans, strict=True)):
            # Byte-identical to 3bf4083's five columns, then four dashes: every new field is None on the mock.
            assert line == f"  {j}\t{span.kind}\t{span.name}\t{span.duration_ms}\t{'-' if span.error is None else span.error}\t-\t-\t-\t-", line
            checked += 1
    assert checked >= 1


def test_p8_18_the_four_new_columns_carry_step_name_attempt_outcome_and_gate(tmp_path: Path) -> None:
    root = tmp_path / "store"
    spans = (
        span_dict(span_id="00000000000000d1", name="plan", kind="agent", step_name="plan", attempt=None, outcome=None, gate=None),
        span_dict(span_id="00000000000000d2", name="lookup", start_ns=EPOCH + 10, end_ns=EPOCH + 20, step_name="lookup", attempt=2, outcome="pass", outcome_by="code", gate="emitted", operation="execute_tool"),
    )
    synthetic_run_with_trace(root, "nine", trace_dict(*spans, source="record", source_version=None))
    lines = inspect_lines(root, "nine", "violated")
    step_lines = [line for line in lines if STEP_LINE_RE.match(line)]
    assert len(step_lines) == 2, "\n".join(lines)
    first, second = (line.split("\t") for line in step_lines)
    assert first[1:3] == ["agent", "plan"] and first[5:] == ["plan", "-", "-", "-"], first
    assert second[1:3] == ["tool", "lookup"] and second[5:] == ["lookup", "2", "pass", "emitted"], second
    assert all(len(cols) == 9 for cols in (first, second))
    # operation, outcome_by, truncated and bytes_original are not printed anywhere in the block.
    assert not any("execute_tool" in line or "code" == line.strip() for line in lines)


# ---------- P8-19: the round trip over the widened span, and the grep half ----------

hex_ids = st.text(alphabet="0123456789abcdef", min_size=16, max_size=16)
json_scalars = st.none() | st.booleans() | st.integers(min_value=-(2**63), max_value=2**63) | st.floats(allow_nan=False, allow_infinity=False) | st.text(max_size=8)
json_values = st.recursive(json_scalars, lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=4), inner, max_size=3), max_leaves=8)
observation_attr_keys = st.sampled_from(["gen_ai.input.messages", "gen_ai.tool.call.result", "input.value", "poisson_prove.logprobs", "gen_ai.prompt.0.content", "llm.output_messages.0.message.content"])
plain_attr_keys = st.sampled_from(["tries", "otel.trace_id", "otel.status_code", "poisson_prove.run_id", "graph.node.id", "graph.node.parent_id"])
attr_maps = st.dictionaries(plain_attr_keys | observation_attr_keys, json_values, max_size=5)
text1 = st.text(min_size=1, max_size=8)


@st.composite
def verdicts(draw: st.DrawFn) -> dict[str, Any]:
    """The eight new fields, each None or non-None, under the two pair rules."""
    outcome = draw(st.none() | text1 | st.just(""))
    truncated = draw(st.none() | st.just("observation"))
    return {
        "operation": draw(st.none() | text1),
        "step_name": draw(st.none() | text1),
        "outcome": outcome,
        "outcome_by": None if outcome is None else draw(st.none() | st.sampled_from(OUTCOME_BY_SPEC)),
        "attempt": draw(st.none() | st.integers(min_value=1, max_value=10**6)),
        "gate": draw(st.none() | st.sampled_from(GATE_SPEC)),
        "truncated": truncated,
        "bytes_original": None if truncated is None else draw(st.none() | st.integers(min_value=1, max_value=10**9)),
    }


@st.composite
def span_forests(draw: st.DrawFn) -> list[dict[str, Any]]:
    ids = draw(st.lists(hex_ids, min_size=0, max_size=5, unique=True))
    spans = []
    for i, sid in enumerate(ids):
        start = draw(st.integers(min_value=0, max_value=2**62))
        delta = draw(st.none() | st.integers(min_value=0, max_value=10**12))
        spans.append({
            "span_id": sid, "parent_id": draw(st.sampled_from([None, *ids[:i]])),
            "kind": draw(st.sampled_from(("llm", "tool", "retrieval", "db", "http", "agent", "other"))),
            "name": draw(text1), "start_ns": start, "end_ns": None if delta is None else start + delta,
            "input": draw(json_values), "output": draw(json_values),
            "tokens": draw(st.none() | st.dictionaries(st.text(min_size=1, max_size=4), st.integers(min_value=0, max_value=10**6), max_size=3)),
            "confidence": draw(st.none() | st.floats(min_value=0.0, max_value=1.0)),
            "error": draw(st.none() | text1), "code": None, "attrs": draw(attr_maps),
            **draw(verdicts()),
        })
    return spans


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(spans=span_forests(), source=st.sampled_from(("record", "otel", "litellm", "mixed")), alias=st.none() | st.sampled_from(["1", "2"]), truncated=st.none() | st.just("timeout"))
def test_p8_19_assemble_of_split_round_trips_the_twenty_one_key_span_and_the_seventh_trace_key(spans: list[dict[str, Any]], source: str, alias: str | None, truncated: str | None) -> None:
    from poisson_prove.trace import OBSERVATION_KEYS, assemble, split

    t = Trace.from_dict(trace_dict(*spans, source=source, source_version=None, alias_map_version=alias, truncated=truncated))
    envelope, obs = split(t)
    assert envelope["alias_map_version"] == alias and set(envelope) == set(TRACE_KEYS_SPEC)
    for raw, span in zip(envelope["spans"], t.spans, strict=True):
        assert set(raw) == set(SPAN_FIELDS_SPEC)
        # The eight ride in the envelope untouched: none of them is observation content.
        assert all(raw[name] == getattr(span, name) for name in NEW_FIELDS), raw
        assert raw["input"] is None and raw["output"] is None and not any(k in OBSERVATION_KEYS for k in raw["attrs"])
    assert assemble(envelope, obs).to_dict() == t.to_dict()
    if not obs:
        assert assemble(envelope, None).to_dict() == t.to_dict()


def test_p8_19_split_and_assemble_name_no_field_key_outside_the_navigation_set() -> None:
    """Green-before-and-after (spec section 7.2): measured at 3bf4083, both functions already
    satisfy this. The literals they do name -- ``span_id``, ``attrs``, ``spans`` -- are the keys
    needed to walk the structure, not the field set; the mutant this catches rebuilds the envelope
    from an enumerated key list, which puts ``kind``, ``name``, ``operation`` ... into the body."""
    from poisson_prove.trace import _OBSERVATION_FIELDS, _SPAN_FIELDS, _TRACE_FIELDS

    navigation = {"span_id", "attrs", "spans", *_OBSERVATION_FIELDS}
    assert set(_SPAN_FIELDS) == set(SPAN_FIELDS_SPEC) and set(_TRACE_FIELDS) == set(TRACE_KEYS_SPEC)
    forbidden = (set(_SPAN_FIELDS) | set(_TRACE_FIELDS)) - navigation
    for name in ("split", "assemble"):
        body = ast.parse(function_source(SRC / "trace.py", name))
        for node in ast.walk(body):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # the docstring
        literals = {n.value for n in ast.walk(body) if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 40}
        assert not (literals & forbidden), (name, sorted(literals & forbidden))
        assert not (literals & set(NEW_FIELDS)) and "alias_map_version" not in literals, name


# ---------- P8-21: the step-line regex, five copies, every negative use paired ----------


def step_line_re_of(path: Path) -> re.Pattern[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "STEP_LINE_RE" for t in node.targets):
            call = node.value
            assert isinstance(call, ast.Call) and isinstance(call.args[0], ast.Constant), path.name
            return re.compile(call.args[0].value)
    raise AssertionError(f"no STEP_LINE_RE in {path.name}")


def test_p8_21_every_copy_of_the_regex_reads_nine_columns() -> None:
    for name in STEP_LINE_FILES:
        pattern = step_line_re_of(TESTS / name)
        assert pattern.match(NINE_COLUMNS), name
        assert not pattern.match(FIVE_COLUMNS), name
        assert not pattern.match(NINE_COLUMNS + "\t-"), name
        assert not pattern.match("trace: truncated (timeout)"), name


def negative_and_positive_uses(fn: ast.FunctionDef, src: str) -> tuple[int, int]:
    """(negative uses, positive controls) of STEP_LINE_RE inside one function body."""
    negatives = positives = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            operand = ast.get_source_segment(src, node.operand) or ""
            if "STEP_LINE_RE.match(" in operand or "step_columns(" in operand:
                negatives += 1
        if isinstance(node, ast.Compare) and len(node.comparators) == 1:
            left = ast.get_source_segment(src, node.left) or ""
            right = node.comparators[0]
            if "STEP_LINE_RE.match(" in left and isinstance(right, ast.List) and not right.elts:
                negatives += 1
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Call):
            func = node.test.func
            if isinstance(func, ast.Attribute) and func.attr == "match" and isinstance(func.value, ast.Name) and func.value.id == "STEP_LINE_RE":
                positives += 1
    return negatives, positives


def test_p8_21_every_negative_use_is_paired_with_a_positive_control_in_the_same_test() -> None:
    paired: list[str] = []
    for name in STEP_LINE_FILES:
        src = (TESTS / name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
            negatives, positives = negative_and_positive_uses(fn, src)
            if negatives:
                assert positives >= 1, f"{name}::{fn.name} has {negatives} negative use(s) of STEP_LINE_RE and no positive control"
                paired.append(f"{name}::{fn.name}")
    # The census at 3bf4083: six functions carry a negative use. Pinned so the scan is known to see them.
    assert sorted(paired) == sorted([
        "test_m10_cli.py::test_i16_inspect_without_trace_prints_rows_and_no_step_lines",
        "test_m12_trace.py::test_t30_inspect_prints_no_trace_lines_and_no_error_for_a_rejected_trace_dict",
        "test_m3_crash_trace.py::test_k7_inspect_selects_the_crashed_row_by_its_exact_error_text_and_prints_its_complete_trace",
        "test_m3_timeout_trace.py::test_e9_inspect_selects_the_timed_out_row_by_error_and_prints_its_truncated_trace",
        "test_m3_timeout_trace.py::test_e9_a_timed_out_row_without_a_trace_prints_its_error_and_no_trace_lines",
        "test_m3_timeout_trace.py::test_e9_an_event_matching_neither_outcome_nor_error_prints_the_no_rows_message_naming_it",
    ]), paired


# ---------- P8-22: A7's surface is byte-identical ----------


def test_p8_22_a8a_edits_nothing_a7_owns() -> None:
    """Green-before-and-after by construction (spec section 7.2): it goes red only if the build
    crosses the A7/A8b line -- teaching ``split`` about ``truncated``, adding a span field to
    ``OBSERVATION_KEYS``, or touching the store's schema, its nullable columns, ``append`` or ``read``."""
    for file, symbols in A7_SURFACE.items():
        for qualname, expected in symbols.items():
            actual = hashlib.sha256(function_source(SRC / file, qualname).encode("utf-8")).hexdigest()
            assert actual == expected, f"{file} {qualname} moved: {actual}"
