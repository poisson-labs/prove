"""A8b frozen tests: invariants P8-7 to P8-12, P8-20, P8-23, P8-24 and P8-27 of
A8b -- the cut and the cap.

Every name these tests reach in ``poisson_prove`` is imported inside the test that needs it, so a
missing name fails that test and never the collection.

**What the tests hold the code to:** the head and
tail bounds are the limit's split, ``limit - limit // 4`` and ``limit // 4``;
``CONTENT_KEYS`` includes the two ``llm.*`` families;
``CONTENT_KEYS`` is a ``frozenset`` whose ``in`` answers exact members and dotted descendants, the
six bare prefixes staying exact members so a ``key == prefix`` match holds;
``split`` routes a value to ``trace_obs`` when its key is an observation key, when it is already a
wrapper, or when it is uncut and over the module default; a low limit is a supported
measure-without-storing configuration; the wrapper has exactly three keys.

**The cap is declared, never defaulted** (``tests/test_cd_cap_declaration.py``): ``limit`` on
``truncate_observations`` and ``finalize`` is keyword-only, typed ``int | None`` and has no
default, and ``None`` means cut nothing; ``CaptureSpec()`` with no ``max_observation_bytes``
raises; ``OBSERVATION_HEAD_BYTES`` and ``OBSERVATION_TAIL_BYTES`` do not exist; and the ``cut``,
``sweep_toml`` and ``child_capture_spans`` helpers declare 8192 rather than inheriting it.

**Test names carry their invariant** (``test_p8_7_*`` for P8-7, and so on). The public surface is
``test_trace_exports_*``, ``test_the_two_cut_functions_*`` and ``test_content_keys_*``;
``test_q5_*`` belongs with P8-23.

**No A8b invariant depends on the pandas version.** A8b adds no Parquet column, and
everything it writes reaches disk inside the ``trace`` / ``trace_obs`` JSON strings listed in
``store._NULLABLE_STRING_COLUMNS``. P8-11's and P8-20's store clauses, which read the
``trace_obs`` column itself, read it raw through ``pyarrow`` and test nullness with ``is None``,
never ``pd.isna`` and never a truth test, as in A8a and A22.

**Beyond the numbered invariants, and said so:** that ``finalize`` is actually wired at the funnel,
and that the funnel never raises on a trace it cannot read, is asserted through ``run_local`` by A7's
P7-9 (``tests/test_a7_storage.py``). **Named gap, not pinned:** what ``finalize`` does with a
non-``None`` ``declaration`` (A10's).
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import multiprocessing
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from poisson_prove.episode import Episode
from poisson_prove.executor import plan, run_local
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import OBSERVATION_KEYS, Span, Trace, assemble, from_otel, split
from isolated_support import isolated

pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")

MODULE = __name__
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trace"
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
needs_fork = pytest.mark.skipif(not FORK_AVAILABLE, reason="the timeout path needs the fork start method")

TRUNCATED_KEY_SPEC = "poisson_prove.truncated"
WRAPPER_KEYS = frozenset({"head", "tail", "bytes_original"})  # exactly three
DEFAULT_LIMIT = 8192
RUN_ID_KEY = "poisson_prove.run_id"
EPISODE_KEY = "poisson_prove.episode"
RUN_ID = "r-2026-09-18-a8b"
SALT = "a8b-oracle-salt"
HORIZON = 10.0
EPOCH = 1_756_900_000_000_000_000
CAPTURE_FIELDS_SPEC = ("instrument", "content", "max_observation_bytes", "max_spans")
NEW_EXPORTS = (
    # CD: OBSERVATION_HEAD_BYTES and OBSERVATION_TAIL_BYTES do not exist, and
    # OBSERVATION_ROUTING_BYTES (formerly OBSERVATION_LIMIT_BYTES, same value) is a storage-layout
    # constant rather than a cap. The retired three are pinned absent by CD11.
    "CONTENT_KEYS", "OBSERVATION_ROUTING_BYTES", "TRUNCATED_KEY", "finalize", "truncate_observations",
)
RETIRED_CONSTANTS = ("OBSERVATION_LIMIT_BYTES", "OBSERVATION_HEAD_BYTES", "OBSERVATION_TAIL_BYTES")
CONTENT_FAMILIES = (
    "gen_ai.prompt", "gen_ai.completion", "traceloop.entity.input", "traceloop.entity.output",
    "llm.input_messages", "llm.output_messages",
)
CONTENT_EXACT = ("gen_ai.input.messages", "gen_ai.output.messages")
#: One dotted descendant per family, so P8-10 is neutral on the prefix spelling.
CONTENT_DESCENDANTS = tuple(f"{family}.0.message.content" for family in CONTENT_FAMILIES)
RETAINED_TOOL_KEYS = ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "input.value", "output.value")

# ---------- helpers: data construction, never an assertion ----------


def byte_form(value: Any) -> bytes:
    """The byte form: a ``str`` is its UTF-8; anything else is the UTF-8 of its canonical JSON."""
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
    """The limit's split, ``limit - limit // 4`` and ``limit // 4``, computed independently of ``trace.py`` by brute force over the byte form."""
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
    """CD: ``limit`` is required here because it is required there. ``None`` means *cut nothing*,
    not *use a default*, so a helper that spelled one as the other would hide what CD checks."""
    from poisson_prove.trace import truncate_observations

    return truncate_observations(trace, limit=limit)


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def cut_fixture_spans() -> dict[int, Span]:
    tr = from_otel(load_fixture("otlp_cut.json"))
    assert tr.dropped == 0 and len(tr.spans) == 2, (tr.dropped, len(tr.spans))
    return {int(s.span_id, 16): s for s in tr.spans}


# ---------- helpers: the store ----------


def manifest(run_id: str) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="policy@a8b", t_unit="steps", run_salt=SALT,
        axis_types={"x": "continuous"}, backend="local", environment={"note": "built by these tests"},
    )


def rec(run_id: str, *, k: int, meta: Mapping[str, Any]) -> EpisodeRecord:
    ep = Episode(outcome="fell", t=3.0, horizon=HORIZON, meta=dict(meta))
    return EpisodeRecord.from_episode(ep, run_id=run_id, config={"x": 0.1}, seed=100 + k, replicate_index=k, wall_time=0.1, backend_meta={"i": k})


def raw_column(root: Path, run_id: str, column: str) -> dict[int, Any]:
    """One stored column exactly as written, keyed by ``replicate_index``, read raw through
    ``pyarrow`` from the store the test made at ``root``, so a null is ``None`` on every pandas."""
    out: dict[int, Any] = {}
    for part in sorted((root / run_id / "episodes").glob("part-*.parquet")):
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
    """CD: a ``[capture]`` table must declare ``max_observation_bytes``, so the builder writes
    ``DEFAULT_LIMIT`` for a caller that named no cap. A caller that names one, including a bad one, is left alone, so the
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


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("a8b.oracle", "0.1.0")


def child_capture_spans(spec_kwargs: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    """``install(CaptureSpec(**spec_kwargs))``, then one capture block emitting ``spans`` in order
    through the real recorder -- the only path ``_is_content`` and the child's cut run on."""
    from poisson_prove.capture import CaptureSpec, capture, install

    # CD: CaptureSpec has no default cap, so the harness supplies DEFAULT_LIMIT. A caller that
    # names a cap is left alone.
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


def child_run_local(store_root: str, toml_path: str, target: str, episode_timeout: float | None) -> str:
    import importlib

    module_name, attr = target.split(":", 1)
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=SALT, import_path=target)
    run_local(p, getattr(importlib.import_module(module_name), attr), store, episode_timeout=episode_timeout)
    return str(p.run_id)


# ---------- the public surface ----------


def test_trace_exports_the_five_names_and_the_routing_constant_is_not_a_cap() -> None:
    """CD: there is no default limit, so the two constants that described its split do not exist,
    and the third is named for the job it has, routing."""
    import poisson_prove.trace as trace_module

    assert set(NEW_EXPORTS) <= set(trace_module.__all__), sorted(set(NEW_EXPORTS) - set(trace_module.__all__))
    assert trace_module.TRUNCATED_KEY == TRUNCATED_KEY_SPEC
    assert trace_module.OBSERVATION_ROUTING_BYTES == DEFAULT_LIMIT
    for name in RETIRED_CONSTANTS:
        assert not hasattr(trace_module, name), name
        assert name not in trace_module.__all__, name


def test_the_two_cut_functions_keep_their_signatures() -> None:
    """CD: ``limit`` is keyword-only, comes after ``trace`` (and ``declaration``), has no default,
    and takes ``int | None``."""
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


def test_content_keys_is_a_frozenset_whose_in_answers_members_and_descendants() -> None:
    """``CONTENT_KEYS`` takes the ``_ObservationKeys`` shape. A plain ``frozenset`` loses the families."""
    from poisson_prove.trace import CONTENT_KEYS

    assert isinstance(CONTENT_KEYS, frozenset)
    for key in CONTENT_EXACT + CONTENT_DESCENDANTS:
        assert key in CONTENT_KEYS, key
    # A content family matches ``key == prefix`` as well as a dotted descendant.
    for family in CONTENT_FAMILIES:
        assert family in CONTENT_KEYS, family
        assert family + "x" not in CONTENT_KEYS and family + "x.0" not in CONTENT_KEYS, family
    # Tool arguments and results are retained by default; no rule here depends on the span's kind.
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
    """The multibyte trap, on the committed fixture at the default limit: a three-byte character
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
    """The trace-level ``truncated`` is a different field: a reason the forest stops early."""
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
    """CD: there is no limit when none is passed, there is a ``TypeError``. What P8-7 says about the
    cut at 8192 is asserted with 8192 declared."""
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
    byte-identical on the first pass and doubles on the second (500, then 1000)."""
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
    """The lookalike trap: a user's dict with ``head`` / ``tail`` / ``bytes_original`` keys is not
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


@pytest.mark.parametrize("episode_timeout", [None, pytest.param(30.0, marks=needs_fork)], ids=["no-timeout", "fork"])
def test_p8_9_the_stored_row_carries_the_wrapper_and_a_value_cut_below_the_default_still_leaves_the_envelope(tmp_path: Path, episode_timeout: float | None) -> None:
    """The second half is the routing rule: whatever the child cut is an observation in the store
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
    (obs,) = raw_column(tmp_path / "store", run_id, "trace_obs").values()
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
    """The two ``llm.*`` content families. Through the recorder, because ``_is_content`` runs only in ``_span_mapping`` and a
    hand-built ``Span`` never reaches it. ``input.value`` / ``output.value`` on an ``llm``-kind span
    are not classified by kind, and nothing here asserts them either way."""
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
    """A8b's centre, and the sole catch for a ``split`` that classifies by key
    alone. Through ``Store.read(trace="envelope")`` and the raw ``trace_obs`` column."""
    fixture = cut_fixture_spans()
    assert not any(k in OBSERVATION_KEYS for k in fixture[2].attrs), sorted(fixture[2].attrs)
    uncut = trace_of(fixture[1], fixture[2])
    quiet = trace_of(span(3, attrs={"app.note.small": "fine"}))
    store = Store(tmp_path / "store")
    store.create_run(manifest("p8-11"))
    store.append("p8-11", [rec("p8-11", k=0, meta={"trace": uncut.to_dict()}), rec("p8-11", k=1, meta={"trace": cut(uncut, DEFAULT_LIMIT).to_dict()}), rec("p8-11", k=2, meta={"trace": quiet.to_dict()})])
    envelopes = envelope_traces(store, "p8-11")
    obs = raw_column(tmp_path / "store", "p8-11", "trace_obs")
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
    """The routing rule. A value cut at a sweep limit far under the module default is a small
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
    """CD and P8-12: the field-name tuple is in ``_CAPTURE_FIELDS`` order, and ``CaptureSpec()``
    with no cap does not build. The other three fields have defaults."""
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
    # CD: DEFAULT_LIMIT here is what the builder *declared*, not what the parser supplied.
    assert capped is not None and capped.max_spans == 3 and capped.max_observation_bytes == DEFAULT_LIMIT


@pytest.mark.parametrize("table", [{"max_spans": 0}, {"max_spans": True}, {"max_spans": 2.5}, {"max_observation_bytes": 0}, {"max_observation_bytes": True}])
def test_p8_12_a_bad_value_is_refused_naming_the_field(tmp_path: Path, table: dict[str, Any]) -> None:
    (name,) = table
    with pytest.raises(SamplerError, match=name):
        SweepSpec.load(write(tmp_path / "bad.toml", sweep_toml({"instrument": [], **table})))


def test_p8_12_with_no_cap_every_closed_span_is_kept() -> None:
    """The span cap is off by default: all 1,001 closed spans are kept, none dropped."""
    r = isolated(child_capture_spans, {}, [{"name": f"s{i}"} for i in range(1001)])
    trace = Trace.from_dict(r["meta"])
    assert len(trace.spans) == 1001 and trace.dropped == 0


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
    obs = raw_column(tmp_path / "store", "p8-20", "trace_obs")
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
    """Sole catch for a cut rule that stores ``"y" * 300`` twice at limit 64 while every other
    clause of P8-7 holds. The ``1023`` row separates ``limit - limit // 4`` from
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
    """Measure-without-storing is a limit setting, not a second mechanism. At
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


# ---------- P8-27: the retired mechanism leaves nothing behind ----------


def test_p8_27_bytes_original_is_the_whole_size_and_not_the_overage() -> None:
    """Against a value whose overage and whose size are different numbers: 300 and 236 at limit 64."""
    (s,) = cut(trace_of(span(1, attrs={"big.attribute": "y" * 300})), 64).spans
    assert s.attrs["big.attribute"][TRUNCATED_KEY_SPEC]["bytes_original"] == 300 != 300 - 64
    assert s.bytes_original == 300
