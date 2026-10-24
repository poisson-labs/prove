"""A8b oracle: invariants P8-7 to P8-12, P8-17, P8-20 and P8-23 to P8-27 of
"Proofload -- Spec A8b Cut and Cap" -- the cut and the cap.

Frozen by Session A on 2026-09-18 off ``a626cd3``, after the retrofit commit. Session B builds
against this file and does not edit it. Every name A8b mints is imported inside the test that
needs it, so the bare tree fails test by test and never at collection.

**The answers this file is frozen against** (spec section 10, all Taylor's): Q1 (a) the head and
tail bounds are the limit's split, ``limit - limit // 4`` and ``limit // 4`` (ADR-082); Q2 (b)
``CONTENT_KEYS`` is the shipped set plus the two ``llm.*`` families (ADR-083); Q3 (a)
``CONTENT_KEYS`` is a ``frozenset`` whose ``in`` answers exact members and dotted descendants, the
six bare prefixes staying exact members so the shipped ``key == prefix`` match survives; Q4 (c)
``split`` routes a value to ``trace_obs`` when its key is an observation key, when it is already a
wrapper, or when it is uncut and over the module default; Q5 (a) a low limit is a supported
measure-without-storing configuration; Q6 ``t4.toml`` and its assertion were rewritten together in
the retrofit; Q8 (a) the wrapper has exactly three keys; Q9 (a) two cells.

**Invariant-to-test map** (38 functions, 63 collected ids; the id counts below sum to 63; CD
Session A deleted one P8-26 function and its one id, and moved none of the others):

| Invariant | Tests |
|---|---|
| section 2 / Q3 | ``test_section_2_*`` (3 functions, 3 ids) |
| P8-7 | ``test_p8_7_*`` (7 functions, 11 ids) |
| P8-8 | ``test_p8_8_*`` (3 functions, 4 ids) |
| P8-9 | ``test_p8_9_*`` (2 functions, 3 ids) |
| P8-10 | ``test_p8_10_*`` (3 functions, 4 ids) |
| P8-11 | ``test_p8_11_*`` (2 functions, 2 ids) |
| P8-12 | ``test_p8_12_*`` (4 functions, 8 ids) |
| P8-17 | ``test_p8_17_*`` (1 function, 1 id) |
| P8-20 | ``test_p8_20_*`` (2 functions, 5 ids) |
| P8-23 | ``test_p8_23_*`` (3 functions, 8 ids), ``test_q5_*`` (1 function, 1 id) |
| P8-24 | ``test_p8_24_*`` (3 functions, 4 ids) |
| P8-25 | ``test_p8_25_*`` (2 functions, 2 ids) |
| P8-26 | ``test_p8_26_*`` (2 functions, 5 ids) |
| P8-27 | ``test_p8_27_*`` (2 functions, 2 ids) |

**Cells (standing rule 15).** Every test here runs in both cells, pandas 2.3.3 and 3.0.5, and the
measured result is that **no A8b invariant is cell-specific**: A8b adds no Parquet column, and
everything it writes reaches disk inside the ``trace`` / ``trace_obs`` JSON strings A7 registered in
``store._NULLABLE_STRING_COLUMNS``. The one place a genuine split could appear is P8-11's and
P8-20's store clauses, which read the ``trace_obs`` column itself; they read it raw through
``pyarrow`` and test nullness with ``is None``, never ``pd.isna`` and never a truth test (A8a
section 3.10, A22 section 3.2).

**Green before and after -- eleven ids, named so their green is not read as coverage** (the other
fifty-two are red on the bare tree and green on the build): ``test_p8_25_*`` (every
symbol they digest is unchanged on the bare tree; they go red only when the build crosses the A7
line), the three invalid-trace ids of ``test_p8_26_the_funnel_never_raises_*`` (A7's P7-9 kept
green while a ``Trace.from_dict`` is added on its path), the ``content-on`` id of
``test_p8_10_through_the_recorder_*`` (nothing is stripped with content on, before or after), and the
five ids of ``test_p8_12_a_bad_value_is_refused_naming_the_field`` (the shipped parser already refuses
three of them, and refuses ``max_observation_bytes`` as an unknown field, naming it, for another reason).

**Amended 2026-09-20 by CD Session A** ("Proofload -- Spec CD Cap Declaration", section 0.2). Ten
A8b clauses move and each is named there; what changed in this file is: section 2's export list and
its two signatures (``limit`` keeps its name, place and keyword-only kind and loses its default,
widened to ``int | None``); P8-7's two-constant sentence, retired with the constants it described;
P8-7's "the default limit is 8192 when none is passed", inverted in place under a new name; P8-12's
``CaptureSpec()``, which now raises; both P8-26 funnel calls, which take the run's limit; and the
``cut``, ``sweep_toml`` and ``child_capture_spans`` helpers, which declare 8192 rather than
inheriting it. **One test is deleted**, not amended:
``test_p8_26_a_run_with_no_capture_table_still_stores_a_rollouts_own_trace_cut``, whose name states
the behaviour CD's D2 reverses; CD7 in ``tests/test_cd_cap_declaration.py`` replaces it.
**Untouched and still green:** P8-25 -- ``_is_observation`` is not among the symbols it digests, and
this packet changes only the constant that function reads.

**Beyond section 4's text, and said so:** ``test_p8_26_the_funnel_cuts_*`` and
``test_p8_26_a_run_with_no_capture_table_*`` assert that ``finalize`` is actually wired at the
funnel. Section 4 pins only that the site never raises; without these a build that never calls
``finalize`` passes every numbered invariant. **Named gaps, not pinned:** what ``finalize`` does
with a non-``None`` ``declaration`` (A10's), whether the funnel honours a sweep's non-default
limit for a rollout's own trace (it has only the record in hand), and the exception *type* of
P8-24's refusal.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import multiprocessing
import re
import time
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import poisson_prove
import poisson_prove.executor as executor
from poisson_prove.episode import Episode
from poisson_prove.executor import plan, run_local
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import OBSERVATION_KEYS, Span, Trace, assemble, from_otel, split
from conftest import code_of

pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")

MODULE = __name__
PACKAGE = Path(poisson_prove.__file__).resolve().parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trace"
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
needs_fork = pytest.mark.skipif(not FORK_AVAILABLE, reason="the timeout path needs the fork start method")

TRUNCATED_KEY_SPEC = "poisson_prove.truncated"
WRAPPER_KEYS = frozenset({"head", "tail", "bytes_original"})  # section 10 Q8 (a): exactly three
DEFAULT_LIMIT = 8192
RUN_ID_KEY = "poisson_prove.run_id"
EPISODE_KEY = "poisson_prove.episode"
RUN_ID = "r-2026-09-18-a8b"
SALT = "a8b-oracle-salt"
HORIZON = 10.0
EPOCH = 1_756_900_000_000_000_000
CAPTURE_FIELDS_SPEC = ("instrument", "content", "max_observation_bytes", "max_spans")
MANIFEST_KEYS_SPEC = frozenset({
    "requested", "active", "reason", "instrumented", "semconv", "alias_map_version", "content", "max_observation_bytes", "max_spans",
})
NEW_EXPORTS = (
    # CD (D8): OBSERVATION_HEAD_BYTES and OBSERVATION_TAIL_BYTES are deleted, and
    # OBSERVATION_LIMIT_BYTES is renamed OBSERVATION_ROUTING_BYTES -- same value, and a storage-layout
    # constant rather than a cap. The retired three are pinned absent by CD11.
    "CONTENT_KEYS", "OBSERVATION_ROUTING_BYTES", "TRUNCATED_KEY", "finalize", "truncate_observations",
)
RETIRED_CONSTANTS = ("OBSERVATION_LIMIT_BYTES", "OBSERVATION_HEAD_BYTES", "OBSERVATION_TAIL_BYTES")
CONTENT_FAMILIES = (
    "gen_ai.prompt", "gen_ai.completion", "traceloop.entity.input", "traceloop.entity.output",
    "llm.input_messages", "llm.output_messages",
)
CONTENT_EXACT = ("gen_ai.input.messages", "gen_ai.output.messages")
#: One dotted descendant per family, so P8-10 is neutral on the prefix spelling (section 10 Q3).
CONTENT_DESCENDANTS = tuple(f"{family}.0.message.content" for family in CONTENT_FAMILIES)
RETAINED_TOOL_KEYS = ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "input.value", "output.value")
RETIRED_NAMES = ("_TRUNCATION_MARKER", "_apply_budget", "_json_size", "max_span_bytes")

#: P8-25: sha256 of ``ast.get_source_segment`` per symbol, measured at the dispatch commit ``a626cd3``.
#: ``split`` is absent on purpose -- it is the one A7 symbol A8b edits -- and is pinned structurally.
# Re-minted 2026-10-24 (public hygiene, Q37): each digest is over the symbol's code with its comments and docstrings
# taken out (``code_of``), so the plain-words pass over src/ moves none of them and a change to the code still does.
# Read off main's unchanged code (56e6e69), every raw digest above matching first, not predicted.
HELD_SURFACE: dict[str, dict[str, str]] = {
    "trace.py": {
        # PF0 (Q4): LOGPROBS_KEY and OBSERVATION_KEYS are no longer pinned; the rename changes both
        # (the span key prefix), and no digest of them can be frozen honestly before the build exists.
        "_OBSERVATION_PREFIXES": "08fd8423badb0404b15168948cbc2f22baf07277aa6570e9f36d35e3bf71a40a",
        "_ObservationKeys": "27ead8ed01df19d6fdc2e1ec09a6ff70d40348074e9c62ae48c99f1bfd8a3502",
        "_OBSERVATION_FIELDS": "0285e490f26b99c0abb8ef52a382a509ec06efc65bdfa2e3d753af24ec4173fb",
        "assemble": "ff677667e7d4d35ab51f1b4a51fae804f4eaa80c7e19bc9188889fbf63d9cb61",
    },
    "store.py": {
        "_SCHEMA": "6860731a98d6b021322e8de25a4c5ff94ca4f3277925e784df05b43c238f52f9",
        "_NULLABLE_STRING_COLUMNS": "c7f3ae63b60a6d4216a9d9ebf8856d2d7151491f59903b447d775b25263a9fe0",
        "Store.append": "bd639c8521010aaa52c7baa2765a2feeb8c5f517143e42e3ed5fb5b2f73a2f56",
        "Store.read": "dbb913562835b7a20a900720cd9d8a94f7b403e513f8966751f4c5ffa52c48cb",
    },
}
SPLIT_DEF_LINE = "def split(trace: Trace) -> tuple[dict[str, Any], dict[str, Any]]:"
SPLIT_OUTSIDE_THE_LOOP = ["envelope = trace.to_dict()", "bodies: dict[str, Any] = {}", "return (envelope, bodies)"]


# ---------- helpers: data construction, never an assertion ----------


def byte_form(value: Any) -> bytes:
    """Section 3.3: a ``str`` is its UTF-8; anything else is the UTF-8 of its canonical JSON."""
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def longest_valid_prefix(raw: bytes, bound: int) -> str:
    for n in range(min(bound, len(raw)), -1, -1):
        try:
            return raw[:n].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""


def longest_valid_suffix(raw: bytes, bound: int) -> str:
    for n in range(min(bound, len(raw)), -1, -1):
        try:
            return raw[len(raw) - n :].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""


def expected_wrapper(value: Any, limit: int) -> dict[str, Any]:
    """ADR-082, computed independently of the build by brute force over the byte form."""
    raw = byte_form(value)
    return {
        TRUNCATED_KEY_SPEC: {
            "head": longest_valid_prefix(raw, limit - limit // 4),
            "tail": longest_valid_suffix(raw, limit // 4),
            "bytes_original": len(raw),
        }
    }


def span(i: int, *, kind: str = "tool", attrs: Mapping[str, Any] | None = None, input: Any = None, output: Any = None, **kw: Any) -> Span:
    return Span(
        span_id=f"{i:016x}", parent_id=None, kind=kind, name=f"step-{i}",
        start_ns=EPOCH + i * 1_000_000, end_ns=EPOCH + i * 1_000_000 + 500_000,
        input=input, output=output, attrs={} if attrs is None else dict(attrs), **kw,
    )


def trace_of(*spans: Span, **kw: Any) -> Trace:
    return Trace(spans=tuple(spans), source="record", **kw)


def canonical(trace: Trace) -> str:
    return json.dumps(trace.to_dict(), sort_keys=True)


def cut(trace: Trace, limit: int | None) -> Trace:
    """CD (D1): ``limit`` is required here because it is required there. The old ``limit=None``
    sentinel meant *use the module default*; under CD ``None`` means *cut nothing*, so a helper
    that spells one as the other would hide the very thing this packet is about."""
    from poisson_prove.trace import truncate_observations

    return truncate_observations(trace, limit=limit)


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def cut_fixture_spans() -> dict[int, Span]:
    tr = from_otel(load_fixture("otlp_cut.json"))
    assert tr.dropped == 0 and len(tr.spans) == 2, (tr.dropped, len(tr.spans))
    return {int(s.span_id, 16): s for s in tr.spans}


def function_source(path: Path, qualname: str) -> str:
    """``ast.get_source_segment`` of a top-level def / class / assignment, or ``Class.method``."""
    src = path.read_text(encoding="utf-8")
    head, _, tail = qualname.partition(".")
    for node in ast.parse(src).body:
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



# ---------- helpers: the store ----------


def manifest(run_id: str) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="policy@a8b", t_unit="steps", run_salt=SALT,
        axis_types={"x": "continuous"}, backend="local", environment={"note": "built by a8b session a"},
    )


def rec(run_id: str, *, k: int, meta: Mapping[str, Any]) -> EpisodeRecord:
    ep = Episode(outcome="fell", t=3.0, horizon=HORIZON, meta=dict(meta))
    return EpisodeRecord.from_episode(ep, run_id=run_id, config={"x": 0.1}, seed=100 + k, replicate_index=k, wall_time=0.1, backend_meta={"i": k})


def raw_column(store: Store, run_id: str, column: str) -> dict[int, Any]:
    """One stored column exactly as written, keyed by ``replicate_index``, read raw through
    ``pyarrow`` so a null is ``None`` on every pandas."""
    out: dict[int, Any] = {}
    for part in sorted((Path(store._root) / run_id / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part, columns=["replicate_index", column])
        for k, v in zip(table.column("replicate_index").to_pylist(), table.column(column).to_pylist(), strict=True):
            out[int(k)] = v
    return out


def envelope_traces(store: Store, run_id: str) -> dict[int, Any]:
    frame = store.read(run_id, trace="envelope")
    return {int(r.replicate_index): r.trace for r in frame.itertuples(index=False)}


def full_traces(store: Store, run_id: str) -> dict[int, Any]:
    frame = store.read(run_id, trace="full")
    return {int(r.replicate_index): r.meta.get("trace") for r in frame.itertuples(index=False)}


def sweep_toml(capture: dict[str, Any] | None) -> str:
    """CD (D1): a ``[capture]`` table must declare ``max_observation_bytes``, so the builder writes
    ``DEFAULT_LIMIT`` for a caller that named no cap -- which is the number those callers were
    silently getting before. A caller that names one, including a bad one, is left alone, so the
    refusal tests below still reach the parser with what they wrote."""
    lines = ['target_id = "a8b-oracle@v0"', 't_unit = "steps"', "replicates = 1", "", "[axes.x]", 'type = "continuous"', "values = [0.1]", ""]
    if capture is not None:
        if "max_observation_bytes" not in capture and "max_span_bytes" not in capture:
            capture = {**capture, "max_observation_bytes": DEFAULT_LIMIT}
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# ---------- helpers: child processes (module-level, so they pickle by reference) ----------


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
    """Run ``fn(*args)`` in a child process, so no OTel provider is ever installed in pytest's."""
    ctx = multiprocessing.get_context("fork" if FORK_AVAILABLE else "spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_entry, args=(child_conn, fn, args))
    proc.start()
    child_conn.close()
    deadline = time.perf_counter() + timeout
    outcome: tuple[str, Any] | None = None
    try:
        while outcome is None:
            if parent_conn.poll(0.05):
                outcome = parent_conn.recv()
            elif not proc.is_alive():
                outcome = ("error", f"child exited with code {proc.exitcode} before reporting")
            elif time.perf_counter() > deadline:
                outcome = ("error", f"child produced nothing within {timeout}s")
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(10.0)
    kind, payload = outcome
    if kind != "ok":
        pytest.fail(f"isolated {fn.__name__} failed:\n{payload}")
    return payload


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("a8b.oracle", "0.1.0")


def child_capture_spans(spec_kwargs: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    """``install(CaptureSpec(**spec_kwargs))``, then one capture block emitting ``spans`` in order
    through the real recorder -- the only path ``_is_content`` and the child's cut run on."""
    from poisson_prove.capture import CaptureSpec, capture, install

    # CD (D1): CaptureSpec has no default cap, so the harness supplies the one these callers
    # were getting from the dataclass. A caller that names a cap is left alone.
    spec_kwargs = {"max_observation_bytes": DEFAULT_LIMIT, **spec_kwargs}
    status = install(CaptureSpec(**spec_kwargs))
    tracer = _tracer()
    with capture(RUN_ID, "cfg-8b:1") as recorder:
        for spec in spans:
            with tracer.start_as_current_span(spec["name"]) as sp:
                for key, value in spec.get("attrs", {}).items():
                    sp.set_attribute(key, value)
    return {"active": status.active, "meta": recorder.to_meta()}


SWEEP_LIMIT = 1024
BIG_RESULT = "z" * (3 * SWEEP_LIMIT)
BIG_PLAIN = "p" * (3 * SWEEP_LIMIT)


def oversized_otel_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """One ``execute_tool`` span carrying a 3 x limit observation and a 3 x limit attribute nobody named."""
    with _tracer().start_as_current_span("execute_tool lookup") as sp:
        sp.set_attribute("gen_ai.operation.name", "execute_tool")
        sp.set_attribute("gen_ai.tool.call.result", BIG_RESULT)
        sp.set_attribute("app.payload", BIG_PLAIN)
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={})


OWN_OUTPUT = "w" * (3 * DEFAULT_LIMIT)


def own_trace_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """A rollout's own ``record()``-shaped trace, which never passes through the recorder."""
    own = trace_of(span(1, output=OWN_OUTPUT, attrs={"tries": 1}))
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={"trace": own.to_dict()})


class TappedConnection:
    """The parent end of a pipe, with every object read off it kept."""

    def __init__(self, conn: Any, seen: list[Any]) -> None:
        self._conn = conn
        self._seen = seen

    def recv(self) -> Any:
        obj = self._conn.recv()
        self._seen.append(obj)
        return obj

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


class TappingContext:
    """The E-oracle's counting context, tapping what the parent reads instead of counting pipes."""

    def __init__(self, ctx: Any) -> None:
        self._ctx = ctx
        self.seen: list[Any] = []

    def Pipe(self, duplex: bool = True) -> Any:  # noqa: N802 - the multiprocessing spelling
        parent, child = self._ctx.Pipe(duplex=duplex)
        return TappedConnection(parent, self.seen), child

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ctx, name)


def child_tap_the_pipe(limit: int) -> dict[str, Any]:
    from poisson_prove.capture import CaptureSpec

    tapping = TappingContext(executor._mp_context())
    call = executor._CaptureCall(spec=CaptureSpec(max_observation_bytes=limit), run_id=RUN_ID, episode_id="cfg-8b:0")
    kind, _payload = executor._call_with_timeout(oversized_otel_rollout, {"x": 0.1}, 7, 30.0, tapping, call)
    return {"kind": kind, "wire": [repr(obj) for obj in tapping.seen]}


def child_run_local(store_root: str, toml_path: str, target: str, episode_timeout: float | None) -> str:
    import importlib

    module_name, attr = target.split(":", 1)
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=SALT, import_path=target)
    run_local(p, getattr(importlib.import_module(module_name), attr), store, episode_timeout=episode_timeout)
    return str(p.run_id)


# ---------- section 2 and section 10 Q3: the public surface ----------


def test_section_2_trace_exports_the_five_names_and_the_routing_constant_is_not_a_cap() -> None:
    """CD (D8), amending A8b section 2 and P8-7's last sentence: the two constants that described the
    default's split are deleted with the default, and the third is renamed to the job it still has."""
    import poisson_prove.trace as trace_module

    assert set(NEW_EXPORTS) <= set(trace_module.__all__), sorted(set(NEW_EXPORTS) - set(trace_module.__all__))
    assert trace_module.TRUNCATED_KEY == TRUNCATED_KEY_SPEC
    assert trace_module.OBSERVATION_ROUTING_BYTES == DEFAULT_LIMIT
    for name in RETIRED_CONSTANTS:
        assert not hasattr(trace_module, name), name
        assert name not in trace_module.__all__, name


def test_section_2_the_two_functions_keep_their_specced_signatures() -> None:
    """CD (D1) amends A8b section 2's two signatures: ``limit`` keeps its name, its place and its
    keyword-only kind, and loses its default. What it takes is widened to ``int | None``."""
    from poisson_prove.trace import finalize, truncate_observations

    t = inspect.signature(truncate_observations).parameters
    assert list(t) == ["trace", "limit"] and t["limit"].kind is inspect.Parameter.KEYWORD_ONLY
    assert t["limit"].default is inspect.Parameter.empty
    f = inspect.signature(finalize).parameters
    assert list(f) == ["trace", "declaration", "limit"]
    assert f["declaration"].kind is inspect.Parameter.KEYWORD_ONLY and f["limit"].kind is inspect.Parameter.KEYWORD_ONLY
    assert f["limit"].default is inspect.Parameter.empty
    big = trace_of(span(1, output="q" * (DEFAULT_LIMIT + 1)))
    assert canonical(finalize(big, declaration=None, limit=DEFAULT_LIMIT)) == canonical(truncate_observations(big, limit=DEFAULT_LIMIT))
    assert canonical(finalize(big, declaration=None, limit=64)) == canonical(truncate_observations(big, limit=64))


def test_section_2_content_keys_is_a_frozenset_whose_in_answers_members_and_descendants() -> None:
    """Section 10 Q3 (a): the ``_ObservationKeys`` shape. A plain ``frozenset`` loses the families."""
    from poisson_prove.trace import CONTENT_KEYS

    assert isinstance(CONTENT_KEYS, frozenset)
    for key in CONTENT_EXACT + CONTENT_DESCENDANTS:
        assert key in CONTENT_KEYS, key
    # The shipped rule matched ``key == prefix`` as well as a dotted descendant, and still does.
    for family in CONTENT_FAMILIES:
        assert family in CONTENT_KEYS, family
        assert family + "x" not in CONTENT_KEYS and family + "x.0" not in CONTENT_KEYS, family
    # Tool arguments and results are retained by default (A6 section 10 Q3); the kind-dependent row is owed.
    for key in RETAINED_TOOL_KEYS + ("server.address", RUN_ID_KEY, EPISODE_KEY):
        assert key not in CONTENT_KEYS, key
    assert 7 not in CONTENT_KEYS


# ---------- P8-7: the truncation rule ----------


@pytest.mark.parametrize("limit", [64, 1023, DEFAULT_LIMIT])
def test_p8_7_a_value_at_or_under_the_limit_is_stored_whole_and_both_span_fields_stay_none(limit: int) -> None:
    at_limit = "a" * limit
    under = {"rows": ["b" * (limit // 4)]}
    assert len(byte_form(at_limit)) == limit and len(byte_form(under)) <= limit
    before = trace_of(span(1, input=under, output=at_limit, attrs={"gen_ai.tool.call.result": at_limit, "app.note": under}))
    after = cut(before, limit)
    assert canonical(after) == canonical(before)
    (s,) = after.spans
    assert s.truncated is None and s.bytes_original is None and after.truncated is None


@pytest.mark.parametrize("limit", [64, 1023, DEFAULT_LIMIT])
def test_p8_7_a_value_over_the_limit_is_stored_as_the_wrapper_and_the_span_records_the_sum(limit: int) -> None:
    text = "h" * (limit + 1)
    blob = {"rows": ["d" * limit, 7, None], "ok": True}
    field = ["o" * (2 * limit)]
    small = "fine"
    before = trace_of(span(1, output=field, attrs={"gen_ai.tool.call.result": text, "app.blob": blob, "app.small": small}))
    (s,) = cut(before, limit).spans
    for got, original in ((s.attrs["gen_ai.tool.call.result"], text), (s.attrs["app.blob"], blob), (s.output, field)):
        assert got == expected_wrapper(original, limit), (limit, str(got)[:120])
        assert set(got) == {TRUNCATED_KEY_SPEC} and set(got[TRUNCATED_KEY_SPEC]) == WRAPPER_KEYS
        inner = got[TRUNCATED_KEY_SPEC]
        raw = byte_form(original)
        assert raw.startswith(inner["head"].encode("utf-8")) and raw.endswith(inner["tail"].encode("utf-8"))
        assert len(inner["head"].encode("utf-8")) <= limit - limit // 4 and len(inner["tail"].encode("utf-8")) <= limit // 4
        assert inner["bytes_original"] == len(raw) and type(inner["bytes_original"]) is int
    assert s.attrs["app.small"] == small and s.input is None
    assert s.truncated == "observation"
    assert s.bytes_original == len(byte_form(text)) + len(byte_form(blob)) + len(byte_form(field))


@settings(max_examples=120, deadline=None)
@given(
    text=st.text(alphabet=st.sampled_from(["a", "Z", " ", "é", "ß", "€", "中", "𝄞", "🙂"]), min_size=0, max_size=400),
    limit=st.sampled_from([5, 64, 99, 257]),
)
def test_p8_7_property_the_head_and_tail_are_the_longest_valid_utf8_within_the_limits_split(text: str, limit: int) -> None:
    before = trace_of(span(1, attrs={"app.text": text}))
    (s,) = cut(before, limit).spans
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        assert s.attrs["app.text"] == text and s.truncated is None and s.bytes_original is None
        return
    assert s.attrs["app.text"] == expected_wrapper(text, limit), (limit, text)
    inner = s.attrs["app.text"][TRUNCATED_KEY_SPEC]
    assert len(inner["head"].encode("utf-8")) + len(inner["tail"].encode("utf-8")) <= limit < len(raw)
    assert s.truncated == "observation" and s.bytes_original == len(raw)


@settings(max_examples=60, deadline=None)
@given(
    value=st.recursive(
        st.one_of(st.none(), st.booleans(), st.integers(-9, 9), st.text(alphabet="ab€", max_size=30)),
        lambda inner: st.one_of(st.lists(inner, max_size=6), st.dictionaries(st.text(alphabet="kq", min_size=1, max_size=3), inner, max_size=6)),
        max_leaves=25,
    ).filter(lambda v: isinstance(v, (list, dict))),
    limit=st.sampled_from([16, 64, 99]),
)
def test_p8_7_property_a_non_str_value_is_cut_on_its_canonical_json(value: Any, limit: int) -> None:
    if isinstance(value, dict) and set(value) == {TRUNCATED_KEY_SPEC}:
        return
    (s,) = cut(trace_of(span(1, attrs={"app.value": value})), limit).spans
    raw = byte_form(value)
    if len(raw) <= limit:
        assert s.attrs["app.value"] == value and s.truncated is None
    else:
        assert s.attrs["app.value"] == expected_wrapper(value, limit)
        assert s.bytes_original == len(raw)


def test_p8_7_a_multibyte_character_straddling_either_cut_point_is_backed_off_not_split() -> None:
    """Spec section 8 trap 2, on the committed fixture at the default limit: a three-byte character
    sits across byte 6144 and another across byte ``L - 2048``."""
    original = cut_fixture_spans()[1].attrs["gen_ai.tool.call.result"]
    assert len(original.encode("utf-8")) == 3 * DEFAULT_LIMIT
    (s,) = cut(trace_of(cut_fixture_spans()[1]), DEFAULT_LIMIT).spans
    inner = s.attrs["gen_ai.tool.call.result"][TRUNCATED_KEY_SPEC]
    assert inner == {"head": "r" * 6143, "tail": "t" * 2046, "bytes_original": 3 * DEFAULT_LIMIT}
    # And the mirror, at a small limit, for two-, three- and four-byte characters at both cut points.
    for ch in ("é", "€", "𝄞"):
        width = len(ch.encode("utf-8"))
        text = "a" * 47 + ch + "b" * 200 + ch + "c" * 15
        raw = text.encode("utf-8")
        assert raw[47 : 47 + width] == ch.encode("utf-8") and raw[len(raw) - 15 - width : len(raw) - 15] == ch.encode("utf-8")
        got = cut(trace_of(span(1, attrs={"u": text})), 64).spans[0].attrs["u"][TRUNCATED_KEY_SPEC]
        assert got == {"head": "a" * 47, "tail": "c" * 15, "bytes_original": len(raw)}, (ch, got["head"][-3:], got["tail"][:3])


def test_p8_7_a_span_cut_sets_the_span_field_and_leaves_the_trace_field_alone() -> None:
    """ADR-028's trace-level ``truncated`` is a different field: a reason the forest stops early."""
    over = "v" * 300
    drained = trace_of(span(1, attrs={"app.big": over}), span(2, attrs={"app.small": "ok"}), truncated="timeout")
    after = cut(drained, 64)
    assert after.truncated == "timeout"
    first, second = after.spans
    assert first.truncated == "observation" and first.bytes_original == 300
    assert second.truncated is None and second.bytes_original is None
    quiet = trace_of(span(1, attrs={"app.small": "ok"}), truncated="timeout")
    assert canonical(cut(quiet, 64)) == canonical(quiet)
    assert cut(trace_of(span(1, attrs={"app.big": over})), 64).truncated is None


def test_p8_7_there_is_no_default_limit_and_the_ratio_holds_at_a_declared_8192() -> None:
    """CD (D1) inverts this test's shipped half: there is no limit when none is passed, there is a
    ``TypeError``. What P8-7 says about the cut at 8192 is re-asserted with 8192 declared."""
    from poisson_prove.trace import truncate_observations

    at, over = "k" * DEFAULT_LIMIT, "k" * (DEFAULT_LIMIT + 1)
    before = trace_of(span(1, attrs={"app.at": at, "app.over": over}))
    with pytest.raises(TypeError):
        truncate_observations(before)  # type: ignore[call-arg]
    (s,) = cut(before, DEFAULT_LIMIT).spans
    assert s.attrs["app.at"] == at and s.attrs["app.over"] == expected_wrapper(over, DEFAULT_LIMIT)
    assert s.bytes_original == DEFAULT_LIMIT + 1


# ---------- P8-8: idempotence, and detection on the key ----------


@pytest.mark.parametrize("limit", [64, DEFAULT_LIMIT])
def test_p8_8_twice_is_once_byte_for_byte_including_both_span_fields(limit: int) -> None:
    """Sole catch for the accumulate spelling -- ``(span.bytes_original or 0) + n`` -- which is
    byte-identical on the first pass and doubles on the second (measured at step zero: 500, 1000)."""
    before = trace_of(
        span(1, output="o" * (limit + 9), attrs={"app.a": "x" * (3 * limit), "app.b": "y" * (2 * limit), "app.small": "ok"}),
        span(2, attrs={"app.small": "ok"}),
    )
    once = cut(before, limit)
    twice = cut(once, limit)
    assert canonical(twice) == canonical(once)
    assert once.spans[0].bytes_original == (limit + 9) + 3 * limit + 2 * limit == twice.spans[0].bytes_original
    assert canonical(cut(twice, limit)) == canonical(once)


def test_p8_8_a_trace_already_carrying_wrappers_is_left_alone_and_its_span_sum_is_recomputed() -> None:
    """``bytes_original`` is the sum over the wrappers present after the pass, never an accumulation:
    a span carrying a wrapper with both fields unset gets the sum, once."""
    wrapper = {TRUNCATED_KEY_SPEC: {"head": "x" * 48, "tail": "x" * 16, "bytes_original": 300}}
    bare = trace_of(span(1, attrs={"app.a": wrapper, "app.small": "ok"}))
    once = cut(bare, 64)
    assert once.spans[0].attrs["app.a"] == wrapper
    assert once.spans[0].truncated == "observation" and once.spans[0].bytes_original == 300
    assert canonical(cut(once, 64)) == canonical(once)
    # A wrapper is never cut again, even at a limit its own byte form exceeds.
    wide = cut(trace_of(span(1, attrs={"app.a": "w" * 9000})), DEFAULT_LIMIT)
    assert len(byte_form(wide.spans[0].attrs["app.a"])) > 64
    assert canonical(cut(wide, 64)) == canonical(wide)
    # And a span already stamped with the right sum plus a fresh oversized value gets the new sum.
    grown = dataclasses.replace(once.spans[0], attrs={**once.spans[0].attrs, "app.b": "n" * 100})
    assert cut(trace_of(grown), 64).spans[0].bytes_original == 400


def test_p8_8_a_wrapper_is_detected_on_its_sole_key_never_on_its_shape() -> None:
    """Spec section 8 trap 4: a user's dict with ``head`` / ``tail`` / ``bytes_original`` keys is not
    a wrapper and is cut like anything else; a dict whose sole key is ``TRUNCATED_KEY`` is one."""
    lookalike = {"head": "H" * 200, "tail": "T" * 200, "bytes_original": 5}
    two_keys = {TRUNCATED_KEY_SPEC: {"head": "x" * 300, "tail": "", "bytes_original": 900}, "also": 1}
    wrapper = {TRUNCATED_KEY_SPEC: {"head": "x" * 300, "tail": "", "bytes_original": 900}}
    (s,) = cut(trace_of(span(1, attrs={"app.lookalike": lookalike, "app.two": two_keys, "app.wrapper": wrapper})), 64).spans
    assert s.attrs["app.lookalike"] == expected_wrapper(lookalike, 64)
    assert s.attrs["app.two"] == expected_wrapper(two_keys, 64)
    assert s.attrs["app.wrapper"] == wrapper
    assert s.bytes_original == len(byte_form(lookalike)) + len(byte_form(two_keys)) + 900


# ---------- P8-9: the cut runs in the child, before transport, with content off ----------


@needs_fork
def test_p8_9_the_bytes_read_off_the_childs_pipe_already_carry_the_wrapper_with_content_off() -> None:
    r = isolated(child_tap_the_pipe, SWEEP_LIMIT)
    assert r["kind"] == "ok", r["kind"]
    wire = "".join(r["wire"])
    assert TRUNCATED_KEY_SPEC in wire, wire[:400]
    assert "z" * (SWEEP_LIMIT + 1) not in wire and "p" * (SWEEP_LIMIT + 1) not in wire, "an uncut observation crossed the pipe"
    assert "z" * (SWEEP_LIMIT - SWEEP_LIMIT // 4) in wire and str(3 * SWEEP_LIMIT) in wire


@pytest.mark.parametrize("episode_timeout", [None, pytest.param(30.0, marks=needs_fork)], ids=["no-timeout", "fork"])
def test_p8_9_the_stored_row_carries_the_wrapper_and_a_value_cut_below_the_default_still_leaves_the_envelope(tmp_path: Path, episode_timeout: float | None) -> None:
    """The second half is section 10 Q4 (c): whatever the child cut is an observation in the store
    at any limit -- ``app.payload``'s wrapper is about 1.1 KB, far under the module default."""
    toml = write(tmp_path / "sweep.toml", sweep_toml({"instrument": [], "max_observation_bytes": SWEEP_LIMIT}))
    run_id = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:oversized_otel_rollout", episode_timeout)
    store = Store(tmp_path / "store")
    (stored,) = full_traces(store, run_id).values()
    (s,) = Trace.from_dict(stored).spans
    assert s.attrs["gen_ai.tool.call.result"] == expected_wrapper(BIG_RESULT, SWEEP_LIMIT)
    assert s.attrs["app.payload"] == expected_wrapper(BIG_PLAIN, SWEEP_LIMIT)
    assert s.truncated == "observation" and s.bytes_original == 2 * 3 * SWEEP_LIMIT
    (envelope,) = envelope_traces(store, run_id).values()
    assert "app.payload" not in envelope["spans"][0]["attrs"] and "gen_ai.tool.call.result" not in envelope["spans"][0]["attrs"]
    assert envelope["spans"][0]["truncated"] == "observation"
    (obs,) = raw_column(store, run_id, "trace_obs").values()
    assert obs is not None
    moved = json.loads(obs)[s.span_id]["attrs"]
    assert moved["app.payload"] == expected_wrapper(BIG_PLAIN, SWEEP_LIMIT)


# ---------- P8-10: the stamps, and what content = false strips ----------


def test_p8_10_the_routing_stamps_are_never_cut_or_moved_whatever_their_size() -> None:
    """Asserted with stamps **over** the limit -- one under it proves nothing."""
    fixture_span = cut_fixture_spans()[2]
    assert len(fixture_span.attrs[RUN_ID_KEY].encode("utf-8")) > DEFAULT_LIMIT
    huge = {RUN_ID_KEY: "s" * 9000, EPISODE_KEY: "e" * 9000, "app.big": "b" * 9000}
    for before in (trace_of(fixture_span), trace_of(span(1, attrs=huge))):
        after = cut(before, DEFAULT_LIMIT)
        (s,) = after.spans
        assert s.attrs[RUN_ID_KEY] == before.spans[0].attrs[RUN_ID_KEY] and s.attrs[EPISODE_KEY] == before.spans[0].attrs[EPISODE_KEY]
        for t in (before, after):
            envelope, obs = split(t)
            kept = envelope["spans"][0]["attrs"]
            assert kept[RUN_ID_KEY] == before.spans[0].attrs[RUN_ID_KEY] and kept[EPISODE_KEY] == before.spans[0].attrs[EPISODE_KEY]
            assert not any(RUN_ID_KEY in body.get("attrs", {}) or EPISODE_KEY in body.get("attrs", {}) for body in obs.values())
    (s,) = cut(trace_of(span(1, attrs=huge)), 64).spans
    assert s.attrs[RUN_ID_KEY] == "s" * 9000 and s.bytes_original == 9000


CAPTURE_PATH_ATTRS = {
    "gen_ai.operation.name": "execute_tool",
    **{key: f"content of {key}" for key in CONTENT_EXACT + CONTENT_DESCENDANTS},
    **{key: f"kept {key}" for key in RETAINED_TOOL_KEYS},
    "server.address": "api.example",
}


@pytest.mark.parametrize("content", [False, True], ids=["content-off", "content-on"])
def test_p8_10_through_the_recorder_content_off_strips_all_eight_and_keeps_the_tool_observation(content: bool) -> None:
    """ADR-083. Through the recorder, because ``_is_content`` runs only in ``_span_mapping`` and a
    hand-built ``Span`` never reaches it. ``input.value`` / ``output.value`` on an ``llm``-kind span
    are the owed kind-dependent row, and nothing here asserts them either way."""
    r = isolated(child_capture_spans, {"content": True} if content else {}, [{"name": "execute_tool lookup", "attrs": CAPTURE_PATH_ATTRS}])
    assert r["active"] is True
    (s,) = Trace.from_dict(r["meta"]).spans
    assert s.kind == "tool", s.kind
    for key in CONTENT_EXACT + CONTENT_DESCENDANTS:
        if content:
            assert s.attrs[key] == CAPTURE_PATH_ATTRS[key], key
        else:
            assert key not in s.attrs, (key, sorted(s.attrs))
    for key in RETAINED_TOOL_KEYS:
        assert s.attrs[key] == CAPTURE_PATH_ATTRS[key], key
    assert s.attrs["server.address"] == "api.example"


def test_p8_10_a_bare_family_key_is_stripped_as_the_shipped_rule_stripped_it() -> None:
    attrs = {family: f"bare {family}" for family in CONTENT_FAMILIES}
    attrs["gen_ai.promptx"] = "not content"
    r = isolated(child_capture_spans, {}, [{"name": "chat", "attrs": attrs}])
    (s,) = Trace.from_dict(r["meta"]).spans
    assert not any(family in s.attrs for family in CONTENT_FAMILIES), sorted(s.attrs)
    assert s.attrs["gen_ai.promptx"] == "not content"


# ---------- P8-11: an attribute nobody named is an observation if it is over the limit ----------


def test_p8_11_an_over_limit_attribute_outside_the_key_set_leaves_the_envelope_and_one_at_the_limit_stays(tmp_path: Path) -> None:
    """The packet's centre, and the sole catch for the shipped ``split``, which classifies by key
    alone. Through ``Store.read(trace="envelope")`` and the raw ``trace_obs`` column."""
    fixture = cut_fixture_spans()
    assert not any(k in OBSERVATION_KEYS for k in fixture[2].attrs), sorted(fixture[2].attrs)
    uncut = trace_of(fixture[1], fixture[2])
    quiet = trace_of(span(3, attrs={"app.note.small": "fine"}))
    store = Store(tmp_path / "store")
    store.create_run(manifest("p8-11"))
    store.append("p8-11", [rec("p8-11", k=0, meta={"trace": uncut.to_dict()}), rec("p8-11", k=1, meta={"trace": cut(uncut, DEFAULT_LIMIT).to_dict()}), rec("p8-11", k=2, meta={"trace": quiet.to_dict()})])
    envelopes = envelope_traces(store, "p8-11")
    obs = raw_column(store, "p8-11", "trace_obs")
    for k in (0, 1):
        by_id = {s["span_id"]: s for s in envelopes[k]["spans"]}
        plain = by_id[fixture[2].span_id]["attrs"]
        assert "app.debug.dump" not in plain and "app.note.over_by_one" not in plain, sorted(plain)
        assert plain["app.note.at_limit"] == "a" * DEFAULT_LIMIT and plain["app.note.small"] == "fine"
        assert plain[RUN_ID_KEY] == fixture[2].attrs[RUN_ID_KEY] and plain[EPISODE_KEY] == "cfg-cut:0"
        assert obs[k] is not None
        moved = json.loads(obs[k])[fixture[2].span_id]["attrs"]
        assert set(moved) == {"app.debug.dump", "app.note.over_by_one"}, sorted(moved)
    assert json.loads(obs[0])[fixture[2].span_id]["attrs"]["app.debug.dump"] == "d" * (2 * DEFAULT_LIMIT)
    assert json.loads(obs[1])[fixture[2].span_id]["attrs"]["app.debug.dump"] == expected_wrapper("d" * (2 * DEFAULT_LIMIT), DEFAULT_LIMIT)
    # Nothing over the limit and no observation key: the column is null, and null is ``None``.
    assert obs[2] is None and envelopes[2]["spans"][0]["attrs"] == {"app.note.small": "fine"}


def test_p8_11_a_wrapper_is_an_observation_at_any_size_and_the_split_never_cuts() -> None:
    """Section 10 Q4 (c). A value cut at a sweep limit far under the module default is a small
    wrapper; it leaves the envelope because it carries ``TRUNCATED_KEY``. An uncut value between
    the two limits stays: ``split`` reads the module default and nothing else."""
    low = cut(trace_of(span(1, attrs={"app.cut_low": "c" * 300, "app.mid": "m" * 60})), 64)
    assert len(byte_form(low.spans[0].attrs["app.cut_low"])) < DEFAULT_LIMIT
    envelope, obs = split(low)
    assert "app.cut_low" not in envelope["spans"][0]["attrs"]
    assert obs[low.spans[0].span_id]["attrs"] == {"app.cut_low": expected_wrapper("c" * 300, 64)}
    between = trace_of(span(1, attrs={"app.between": "b" * 5000}))
    envelope, obs = split(between)
    assert envelope["spans"][0]["attrs"] == {"app.between": "b" * 5000} and obs == {}
    over = trace_of(span(1, attrs={"app.over": "o" * 9000}))
    envelope, obs = split(over)
    assert obs[over.spans[0].span_id]["attrs"] == {"app.over": "o" * 9000}, "split moves an oversized value; it never cuts one"


# ---------- P8-12: the [capture] table ----------


def test_p8_12_capture_spec_fields_and_the_cap_that_has_no_default() -> None:
    """CD (D1, D12) amends P8-12: the field-name tuple is unchanged and in ``_CAPTURE_FIELDS`` order,
    and ``CaptureSpec()`` no longer builds. The other three defaults stand."""
    from poisson_prove.capture import CaptureSpec

    assert tuple(f.name for f in dataclasses.fields(CaptureSpec)) == CAPTURE_FIELDS_SPEC
    with pytest.raises(TypeError):
        CaptureSpec()  # type: ignore[call-arg]
    spec = CaptureSpec(max_observation_bytes=DEFAULT_LIMIT)
    assert (spec.instrument, spec.content, spec.max_observation_bytes, spec.max_spans) == ((), False, 8192, None)


def test_p8_12_the_retired_field_is_refused_naming_it_and_an_absent_max_spans_is_none(tmp_path: Path) -> None:
    with pytest.raises(SamplerError, match="max_span_bytes"):
        SweepSpec.load(write(tmp_path / "old.toml", sweep_toml({"instrument": [], "max_span_bytes": 4096})))
    absent = SweepSpec.load(write(tmp_path / "absent.toml", sweep_toml({"instrument": [], "max_observation_bytes": 4096}))).capture
    assert absent is not None and absent.max_spans is None and absent.max_observation_bytes == 4096
    capped = SweepSpec.load(write(tmp_path / "capped.toml", sweep_toml({"instrument": [], "max_spans": 3}))).capture
    # CD (D1): DEFAULT_LIMIT here is what the builder *declared*, not what the parser supplied.
    assert capped is not None and capped.max_spans == 3 and capped.max_observation_bytes == DEFAULT_LIMIT


@pytest.mark.parametrize("table", [{"max_spans": 0}, {"max_spans": True}, {"max_spans": 2.5}, {"max_observation_bytes": 0}, {"max_observation_bytes": True}])
def test_p8_12_a_bad_value_is_refused_naming_the_field(tmp_path: Path, table: dict[str, Any]) -> None:
    (name,) = table
    with pytest.raises(SamplerError, match=name):
        SweepSpec.load(write(tmp_path / "bad.toml", sweep_toml({"instrument": [], **table})))


def test_p8_12_with_no_cap_every_closed_span_is_kept() -> None:
    """D6: the cap is off by default. 1,001 spans is one more than the shipped default kept."""
    r = isolated(child_capture_spans, {}, [{"name": f"s{i}"} for i in range(1001)])
    trace = Trace.from_dict(r["meta"])
    assert len(trace.spans) == 1001 and trace.dropped == 0


# ---------- P8-17: the manifest, in A8b's spelling ----------


def test_p8_17_environment_capture_has_the_nine_keys_and_the_value_round_trips_from_the_sweep_file(tmp_path: Path) -> None:
    from poisson_prove.capture import CaptureStatus

    spec = SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml({"instrument": [], "max_observation_bytes": 4096}))).capture
    record = executor._capture_record(spec, CaptureStatus(requested=True, active=True, reason=None, instrumented=()))
    assert set(record) == MANIFEST_KEYS_SPEC, sorted(record)
    assert record["max_observation_bytes"] == 4096 and record["max_spans"] is None
    assert json.loads(json.dumps(record)) == record


# ---------- P8-20: the round trip over the widened classification ----------


ROUND_TRIP_TRACES: dict[str, Callable[[], Trace]] = {
    "under-at-over": lambda: trace_of(span(1, attrs={"app.under": "u" * (DEFAULT_LIMIT - 1), "app.at": "a" * DEFAULT_LIMIT, "app.over": "o" * (DEFAULT_LIMIT + 1), "gen_ai.tool.call.result": "r" * 10, "tries": 2})),
    "fixture": lambda: trace_of(*cut_fixture_spans().values()),
    "wrappers": lambda: cut(trace_of(span(1, input={"q": "i" * 200}, output="o" * 200, attrs={"app.cut": "c" * 300, "app.small": "ok"}), span(2, attrs={"tries": 1})), 64),
    "stamps-over": lambda: trace_of(span(1, attrs={RUN_ID_KEY: "s" * 9000, EPISODE_KEY: "e" * 9000, "app.over": "o" * 9000})),
}


@pytest.mark.parametrize("name", list(ROUND_TRIP_TRACES))
def test_p8_20_assemble_of_split_round_trips_under_at_and_over_the_limit_and_over_wrappers(name: str) -> None:
    t = ROUND_TRIP_TRACES[name]()
    assert assemble(*split(t)).to_dict() == t.to_dict()
    tc = cut(t, DEFAULT_LIMIT)
    # The cut runs before the split, and the round trip is over the **cut** trace.
    assert assemble(*split(tc)).to_dict() == tc.to_dict()
    assert canonical(cut(assemble(*split(tc)), DEFAULT_LIMIT)) == canonical(tc)


def test_p8_20_the_round_trip_holds_through_the_store(tmp_path: Path) -> None:
    store = Store(tmp_path / "store")
    store.create_run(manifest("p8-20"))
    traces = [cut(build(), DEFAULT_LIMIT) for build in ROUND_TRIP_TRACES.values()]
    store.append("p8-20", [rec("p8-20", k=k, meta={"trace": t.to_dict()}) for k, t in enumerate(traces)])
    full = full_traces(store, "p8-20")
    obs = raw_column(store, "p8-20", "trace_obs")
    for k, t in enumerate(traces):
        assert full[k] == t.to_dict(), k
        assert obs[k] is not None, k


# ---------- P8-23: the cut is a reduction, at every limit ----------


@pytest.mark.parametrize(
    ("limit", "size", "head", "tail"),
    [(DEFAULT_LIMIT, 9000, 6144, 2048), (DEFAULT_LIMIT, 20000, 6144, 2048), (64, 300, 48, 16), (16384, 20000, 12288, 4096), (1023, 5000, 768, 255)],
    ids=["default-9000", "default-20000", "lowered-64", "raised-16384", "1023"],
)
def test_p8_23_on_an_ascii_value_both_bounds_are_met_exactly(limit: int, size: int, head: int, tail: int) -> None:
    """Sole catch for A6 section 3.4's rule as written, which stores ``"y" * 300`` twice at limit 64
    with every clause of A6's P8-7 holding. The ``1023`` row separates ``limit - limit // 4`` from
    ``3 * limit // 4`` and ``round(limit * 0.75)``: both give 767, and both agree with the rule at
    every multiple of four."""
    value = "y" * size
    (s,) = cut(trace_of(span(1, attrs={"big.attribute": value})), limit).spans
    inner = s.attrs["big.attribute"][TRUNCATED_KEY_SPEC]
    assert inner == {"head": "y" * head, "tail": "y" * tail, "bytes_original": size}
    assert head == limit - limit // 4 and tail == limit // 4
    assert len(inner["head"]) + len(inner["tail"]) <= limit < size
    assert s.truncated == "observation" and s.bytes_original == size


@pytest.mark.parametrize("limit", [1, 3])
def test_p8_23_below_four_the_tail_bound_is_zero_and_the_tail_is_empty(limit: int) -> None:
    (s,) = cut(trace_of(span(1, attrs={"big.attribute": "y" * 50})), limit).spans
    assert s.attrs["big.attribute"] == {TRUNCATED_KEY_SPEC: {"head": "y" * limit, "tail": "", "bytes_original": 50}}


def test_p8_23_a_raised_limit_through_the_recorder_stores_the_raised_split() -> None:
    value = "y" * 20000
    r = isolated(child_capture_spans, {"max_observation_bytes": 16384}, [{"name": "chat", "attrs": {"big.attribute": value, "mid.attribute": "m" * 10000}}])
    (s,) = Trace.from_dict(r["meta"]).spans
    assert s.attrs["big.attribute"] == {TRUNCATED_KEY_SPEC: {"head": "y" * 12288, "tail": "y" * 4096, "bytes_original": 20000}}
    assert s.attrs["mid.attribute"] == "m" * 10000 and s.bytes_original == 20000


def test_q5_a_low_limit_measures_every_value_and_stores_almost_nothing() -> None:
    """Section 10 Q5 (a): measure-without-storing is a limit setting, not a second mechanism. At
    limit 4 a run records every value's true length and keeps four bytes of each."""
    sizes = {"app.a": 8225, "app.b": 300, "app.c": 5}
    (s,) = cut(trace_of(span(1, attrs={key: "q" * n for key, n in sizes.items()})), 4).spans
    assert {key: s.attrs[key][TRUNCATED_KEY_SPEC]["bytes_original"] for key in sizes} == sizes
    assert all(s.attrs[key][TRUNCATED_KEY_SPEC] == {"head": "qqq", "tail": "q", "bytes_original": n} for key, n in sizes.items())
    assert s.bytes_original == sum(sizes.values())


# ---------- P8-24: the Modal transport ----------


@pytest.mark.parametrize("max_spans", [None, 3])
def test_p8_24_the_transport_round_trips_the_spec_through_json(max_spans: int | None) -> None:
    from poisson_prove.capture import CaptureSpec
    from poisson_prove.executor_modal import _capture_payload, _capture_request

    spec = CaptureSpec(instrument=("openai",), content=True, max_observation_bytes=4096, max_spans=max_spans)
    payload = _capture_payload(spec, RUN_ID)
    assert payload is not None and set(payload) == {"run_id", *CAPTURE_FIELDS_SPEC}, sorted(payload or {})
    assert _capture_request(json.loads(json.dumps(payload))) == (spec, RUN_ID)


def test_p8_24_a_payload_carrying_the_retired_field_or_an_unknown_one_is_refused_naming_it() -> None:
    """Sole catch for the shipped intersection, which drops a retired key silently and runs the whole
    batch at the default with no error on either side of the process boundary (measured at step
    zero: the three frozen payload literals stayed green under the rename alone). Built as literal
    dicts: ``_capture_payload`` cannot carry the retired key."""
    from poisson_prove.executor_modal import _capture_request

    old = {"run_id": RUN_ID, "instrument": [], "content": False, "max_span_bytes": 1024, "max_spans": 1000}
    with pytest.raises(Exception, match="max_span_bytes"):
        _capture_request(old)
    with pytest.raises(Exception, match="bogus_field"):
        _capture_request({"run_id": RUN_ID, "instrument": [], "content": False, "max_observation_bytes": 1024, "bogus_field": 1})
    assert _capture_request(None) == (None, "")


def test_p8_24_the_two_field_lists_are_one_list() -> None:
    import poisson_prove.executor_modal as modal
    import poisson_prove.sampler as sampler

    assert tuple(modal._CAPTURE_FIELDS) == tuple(sampler._CAPTURE_FIELDS) == CAPTURE_FIELDS_SPEC


# ---------- P8-25: A8b edits split's loop and nothing else A7 or A8a owns ----------


def test_p8_25_every_other_symbol_a7_owns_is_byte_identical_to_the_dispatch_commits() -> None:
    """The narrowed P8-22 (ADR-077 / C19). Sole catch for the build that "helps" by adding a
    size-selected key to ``OBSERVATION_KEYS`` or teaching ``_ObservationKeys.__contains__`` a value
    rule -- both satisfy P8-11 and P8-20 and silently move A7's boundary."""
    for file, symbols in HELD_SURFACE.items():
        for qualname, expected in symbols.items():
            actual = hashlib.sha256(code_of(function_source(PACKAGE / file, qualname)).encode("utf-8")).hexdigest()
            assert actual == expected, f"{file} {qualname} moved: {actual}"


def test_p8_25_splits_signature_is_unchanged_and_its_edit_is_confined_to_the_loop() -> None:
    """The docstring is free to move -- it describes the routing rule A8b widens. Everything else
    outside the ``for`` is pinned, and so are the loop's first two statements (the body dict and
    the ``_OBSERVATION_FIELDS`` sweep), which A8b has no reason to touch."""
    src = function_source(PACKAGE / "trace.py", "split")
    assert src.splitlines()[0] == SPLIT_DEF_LINE
    (fn,) = ast.parse(src).body
    assert isinstance(fn, ast.FunctionDef) and [a.arg for a in fn.args.args] == ["trace"]
    assert not fn.args.kwonlyargs and fn.args.vararg is None and fn.args.kwarg is None
    loops = [n for n in fn.body if isinstance(n, ast.For)]
    assert len(loops) == 1
    outside = [ast.unparse(n) for n in fn.body if not isinstance(n, ast.For) and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert outside == SPLIT_OUTSIDE_THE_LOOP, outside
    (loop,) = loops
    assert ast.unparse(loop.target) == "span" and ast.unparse(loop.iter) == "envelope['spans']"
    assert ast.unparse(loop.body[0]) == "body: dict[str, Any] = {}"
    assert ast.unparse(loop.body[1]).startswith("for name in _OBSERVATION_FIELDS:")
    assert inspect.signature(split).parameters.keys() == {"trace"}


# ---------- P8-26: finalize's site never raises, and it does cut ----------


INVALID_TRACES: dict[str, Any] = {
    "string": "step-a then step-b",
    "list": ["step-a", "step-b"],
    "dict-missing-spans": {"schema": "poisson-prove.trace/1", "source": "record", "source_version": None, "dropped": 0},
}


@pytest.mark.parametrize("name", list(INVALID_TRACES))
def test_p8_26_the_funnel_never_raises_on_a_trace_it_cannot_read_and_a7s_p7_9_holds(tmp_path: Path, name: str) -> None:
    """Sole catch for the ``Trace.from_dict`` that runs one frame before the guard written for it.
    Green on the bare tree by design: A8b's job is to keep it green."""
    garbage = INVALID_TRACES[name]
    store = Store(tmp_path / "store")
    store.create_run(manifest("p8-26"))
    records = []
    for k, active in enumerate((True, False)):
        record = rec("p8-26", k=k, meta={"trace": garbage, "k": k})
        out = executor._with_capture_envelope(record, active, DEFAULT_LIMIT)
        assert out.meta == {"trace": garbage, "k": k}, (name, active)
        records.append(out)
    assert store.append("p8-26", records) == 2
    frame = store.read("p8-26", trace="full")
    assert [r.meta for r in frame.sort_values("replicate_index").itertuples(index=False)] == [{"trace": garbage, "k": 0}, {"trace": garbage, "k": 1}]
    assert all(v is None for v in raw_column(store, "p8-26", "trace").values())
    assert all(v is None for v in raw_column(store, "p8-26", "trace_obs").values())


@pytest.mark.parametrize("active", [True, False], ids=["capture-active", "capture-inactive"])
def test_p8_26_the_funnel_cuts_a_valid_trace_and_leaves_a_small_one_exactly_as_written(active: bool) -> None:
    """Beyond section 4's text (module docstring): ``finalize`` is wired, on the branch the shipped
    funnel returns early from. Rule zero (C7) on the other side: nothing over the limit, nothing moves."""
    own = trace_of(span(1, output=OWN_OUTPUT, attrs={"tries": 1}))
    out = executor._with_capture_envelope(rec("p8-26", k=0, meta={"trace": own.to_dict(), "k": 0}), active, DEFAULT_LIMIT)
    assert out.meta["k"] == 0
    (s,) = Trace.from_dict(out.meta["trace"]).spans
    assert s.output == expected_wrapper(OWN_OUTPUT, DEFAULT_LIMIT) and s.truncated == "observation" and s.bytes_original == 3 * DEFAULT_LIMIT
    small = trace_of(span(1, output="fine", attrs={"tries": 1})).to_dict()
    kept = executor._with_capture_envelope(rec("p8-26", k=1, meta={"trace": small}), active, DEFAULT_LIMIT)
    assert json.dumps(kept.meta["trace"]) == json.dumps(small)


# CD (D2) deletes ``test_p8_26_a_run_with_no_capture_table_still_stores_a_rollouts_own_trace_cut``
# from this slot. Its name states the behaviour the packet reverses -- a run with no ``[capture]``
# table now stores a rollout's own trace *uncut* -- and A8b's own rule is that such a test is
# rewritten under a new name rather than amended in place. Its replacement is CD7, in
# ``tests/test_cd_cap_declaration.py``. ``own_trace_rollout`` above is still used from there.


# ---------- P8-27: the retired mechanism leaves nothing behind ----------


def test_p8_27_the_retired_names_appear_nowhere_in_src() -> None:
    hits = [
        f"{path.relative_to(PACKAGE)}:{n}: {name}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for name in RETIRED_NAMES
        if name in line
    ]
    assert not hits, hits
    # C30: no string describes a byte count as *over* a limit.
    over = [str(path.relative_to(PACKAGE)) for path in sorted(PACKAGE.rglob("*.py")) if re.search(r"bytes over\b", path.read_text(encoding="utf-8"))]
    assert not over, over


def test_p8_27_bytes_original_is_the_whole_size_and_not_the_overage() -> None:
    """Against a value whose overage and whose size are different numbers: 300 and 236 at limit 64."""
    (s,) = cut(trace_of(span(1, attrs={"big.attribute": "y" * 300})), 64).spans
    assert s.attrs["big.attribute"][TRUNCATED_KEY_SPEC]["bytes_original"] == 300 != 300 - 64
    assert s.bytes_original == 300
