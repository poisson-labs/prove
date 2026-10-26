"""Stored-trace read frozen tests: a run stored before A8a opens, and the tolerance is exactly that wide.

Frozen 2026-09-20 off ``1f5491b``. The build is written against this file and does not edit it. The
brief was the surfacing cleanup's first item: ``proofload inspect`` cannot open any stored run that
carries a trace.

**What is being fixed, measured at ``1f5491b`` on stored runs that carry a trace.**
A8a added one trace key (``alias_map_version``) and eight span keys, and ``Trace.from_dict`` demands the
exact key set, so a trace stored before it is rejected. Every trace stored before A8a is exactly the old
shape: six trace keys, spans of thirteen. A run written after A7 holds it in the ``trace`` column, and
``Store.read`` reassembles it through ``from_dict`` and raises, so ``inspect`` exits 3 on it. A run written
before A7 holds it in ``meta["trace"]``: ``Store.read`` hands it back as stored, ``inspect`` validates it,
rejects it and prints no trace lines and no error (the posture M12's T30 pins for a rejected dict), so
the older runs are silent where the newer are loud. Adding exactly those nine keys, each ``None``, makes
every such trace validate and changes nothing else.

**The fix is a read, at the store, and only the store.** ``from_dict`` stays strict: A8a's P8-1 pins that it
rejects thirteen-key spans and a six-key trace, and a stored dict that is *not* the old shape must keep
being rejected. The store knows what it wrote, so the store recognises the old shape and reads it as the
current one, the way A7's ``_legacy_envelope`` already reads the layout before the split. It is not a
migration: nothing stored is rewritten (R10), and a migration would need a verb, which is a public
symbol the spec has not given, and would leave every unmigrated store failing as before.

**What a read of an old trace means.** ``None`` on each of the nine fields is "not recorded", which is what
``Span``'s own comment says ``None`` means on A8a's eight, so a reader asks ``is None`` and reads the truth. It
is never a zero and never an empty string.

**Invariant-to-test map** (R-numbers are this file's; 64 collected ids):

| Invariant | Tests |
|---|---|
| R1 a run stored before A8a opens in full: every row reads as the trace it was | ``test_r1_*`` |
| R2 what the old shape lacked reads ``None``, field by field | ``test_r2_*`` |
| R3 a trace already in the current shape is not touched | ``test_r3_*`` |
| R4 the tolerance is exactly the old shape: near misses still raise | ``test_r4_*`` |
| R5 ``from_dict`` is unchanged: the fix is not there | ``test_r5_*`` |
| R6 the decision is per row: a run holding both shapes reads every row | ``test_r6_*`` |
| R7 ``inspect`` opens such a run and prints every span it holds | ``test_r7_*`` |
| R8 a trace stored in ``meta`` on a part written before A7 reads the same way, in full and as its envelope | ``test_r8_*`` |
| R9 the envelope read is untouched: the stored envelope comes back as stored | ``test_r9_*`` |
| R10 nothing is written: no stored byte or mtime moves | ``test_r10_*`` |

**Real frames, round-tripped.** Every store is written by ``Store.append`` and read back through ``Store.read``
and the CLI; nothing is hand-built at the read (standing rule 14). The old shape is made the way a build
before A8a stored it: the ``trace`` column of a written part is rewritten to six keys and thirteen-key spans
(``Store.append`` refuses to write that shape, and a fixture that was not the shape would prove nothing
about it; R1's first test asserts the fixture is what it claims). The part before A7 is made by moving the
trace back inside ``meta`` and dropping both trace columns. The expected trace of each row is built again
from the same recipe with ``make_trace``, never read off a store, so a broken twin cannot make a test
vacuous; and R7 counts the span lines it expects, because two silent outputs are equal.

**Green before and after -- 37 of the 64 ids**, named so their green is not read as coverage (the other 27 are
red on the bare tree: 17 raise ``missing trace key(s): alias_map_version`` from ``Store.read``, the defect itself, and 10
fail on what ``inspect`` does or on a ``meta`` or an envelope that comes back unread): R1's fixture precondition; both
R3 tests (the current shape round-trips today); all twenty-six R4 tests (a near miss raises today and must go on raising,
so they pin what must NOT change: six mixtures of the two shapes, and each of the six trace keys and thirteen span keys
the old shape had, missing in turn); both R5 tests (``from_dict`` is strict today and must stay so); R8's five (a
current-shape trace and something that is no trace, inside ``meta``, are returned as written today, ``inspect`` prints
no trace lines for the second, and the envelope of the first is the current writer's while the second has none); and
R9's one (the envelope read of a written column is raw today and must stay raw). R10's second test and every R1, R2,
R6 and R7 test that reads an old run are red.

**Named gaps, not pinned.** (1) ``inspect`` prints no ``observation:`` line on an old run, because its spans
carry no stamp: ``span.truncated`` is ``None`` and a pre-A8b marker is not read (A8b's P8-27 bars the text
from ``src/``, and a ruling of 2026-09-20 says no reader is written). Whether ``inspect`` should say
``not counted`` for such a row is a decision, not a fix, and nothing here decides it. (2) The write path is
unchanged: ``Store.append`` still stores a dict in the old shape as written, in ``meta``, with both columns
null (A7's P7-9); R8 reads that back, and does not ask ``append`` to accept it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import poisson_prove.cli as cli
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import Span, Trace, TraceValidationError

EPOCH = 1_756_900_000_000_000_000
TASKS = ("t0", "t1", "t2", "t3")
REPLICATES = 8
EVENT = "fail"

#: The shape a build before A8a stored, spelled out as history: six trace keys, thirteen span keys.
#: Not derived from ``proofload.trace``, so a change to the current schema cannot move it.
A7_TRACE_KEYS = ("schema", "source", "source_version", "dropped", "spans", "truncated")
A7_SPAN_KEYS = (
    "span_id", "parent_id", "kind", "name", "start_ns", "end_ns", "input", "output", "tokens",
    "confidence", "error", "code", "attrs",
)
#: What A8a added: one trace key and eight span keys.
A8A_TRACE_KEYS = ("alias_map_version",)
A8A_SPAN_KEYS = ("operation", "step_name", "outcome", "outcome_by", "attempt", "gate", "truncated", "bytes_original")


# ---------- helpers: data construction, never an assertion ----------


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def make_trace(i: int, k: int, *, stamped: bool = False) -> Trace:
    """The trace of replicate ``k`` in cell ``i``: a root, one to three llm spans with an input, an output
    and a content attribute, a tool span, one span that never closed and one with an error and a code
    location. Uneven on purpose. ``stamped`` fills every field A8a added; otherwise each is ``None``,
    which is what an old trace reads as."""
    added: dict[str, Any] = (
        {"operation": "chat", "step_name": "plan", "outcome": "pass", "outcome_by": "code", "attempt": 2,
         "gate": "emitted", "truncated": "observation", "bytes_original": 9}
        if stamped else {}
    )
    root_id = f"{1:016x}"
    spans = [Span(span_id=root_id, parent_id=None, kind="agent", name="run", start_ns=EPOCH, end_ns=EPOCH + 5_000, attrs={"episode": f"{i}.{k}"})]
    n_llm = 1 + (i + k) % 3
    for j in range(n_llm):
        n = 2 + j
        spans.append(Span(
            span_id=f"{n:016x}", parent_id=root_id, kind="llm", name=f"chat {j}", start_ns=EPOCH + 10 * n,
            end_ns=EPOCH + 10 * n + 7, input=f"prompt {i}.{k}.{j} " + "p" * 40, output=f"reply {i}.{k}.{j}",
            tokens={"input": 11 + j, "output": 5}, confidence=0.25 * (j + 1),
            attrs={"gen_ai.input.messages": "m" * (30 + j), "tries": 1 + j}, **added,
        ))
    n = 2 + n_llm
    spans.append(Span(span_id=f"{n:016x}", parent_id=root_id, kind="tool", name="lookup", start_ns=EPOCH + 10 * n,
                      end_ns=EPOCH + 10 * n + 3, input={"q": f"{i}.{k}"}, output=None))
    spans.append(Span(span_id=f"{n + 1:016x}", parent_id=root_id, kind="tool", name="never closed", start_ns=EPOCH + 10 * n + 4, end_ns=None))
    spans.append(Span(span_id=f"{n + 2:016x}", parent_id=root_id, kind="tool", name="failed", start_ns=EPOCH + 10 * n + 5,
                      end_ns=EPOCH + 10 * n + 6, error="ToolError", code={"filepath": "a.py", "function": "f", "lineno": 3}))
    return Trace(
        spans=tuple(spans), source="otel", source_version="1.42.0", dropped=k % 2,
        truncated="timeout" if k == 1 else None, alias_map_version="1" if stamped else None,
    )


def manifest(run_id: str) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt="salt-stored-trace-read",
        axis_types={"task": "categorical"}, backend="synthetic", environment={"note": "built by test_stored_trace_read"},
    )


def records(run_id: str, *, tasks: Sequence[str] = TASKS, stamped: bool = False) -> list[EpisodeRecord]:
    """Eight episodes per task, the first two failing at ``t = 3``, each carrying ``make_trace``."""
    out = []
    for task in tasks:
        i = TASKS.index(task)
        for k in range(REPLICATES):
            fail = k < 2
            episode = Episode(
                outcome=EVENT if fail else "ok", t=3.0 if fail else 10.0, horizon=10.0,
                meta={"trace": make_trace(i, k, stamped=stamped).to_dict()},
            )
            out.append(EpisodeRecord.from_episode(episode, run_id=run_id, config={"task": task}, seed=1000 * i + k, replicate_index=k, wall_time=0.0))
    return out


def parts(root: Path, run_id: str) -> list[Path]:
    return sorted((root / run_id / "episodes").glob("part-*.parquet"))


def rewrite_rows(root: Path, run_id: str, column: str, fn: Callable[[int, str | None], str | None], part: Path | None = None) -> None:
    """Rewrite ``column`` of one part (or of every part) in place; ``fn`` gets the row index in the part."""
    for path in [part] if part is not None else parts(root, run_id):
        table = pq.read_table(path)
        values = [fn(n, v) for n, v in enumerate(table[column].to_pylist())]
        table = table.set_column(table.schema.get_field_index(column), column, pa.array(values, type=pa.string()))
        tmp = path.with_name(path.name + ".tmp")
        pq.write_table(table, tmp)
        os.replace(tmp, path)


def a7_shape(envelope: dict[str, Any]) -> dict[str, Any]:
    """A trace dict or an envelope as a build before A8a wrote it: the keys of that shape and no others."""
    kept = {key: envelope[key] for key in A7_TRACE_KEYS}
    kept["spans"] = [{key: s[key] for key in A7_SPAN_KEYS} for s in envelope["spans"]]
    return kept


def to_a7(_: int, value: str | None) -> str | None:
    return None if value is None else json.dumps(a7_shape(json.loads(value)), sort_keys=True, separators=(",", ":"))


def write_run(root: Path, run_id: str, *, stamped: bool = False, old: bool = False) -> None:
    """One run through ``Store.append``; ``old`` rewrites its ``trace`` column to the shape before A8a."""
    store = Store(root)
    store.create_run(manifest(run_id))
    store.append(run_id, records(run_id, stamped=stamped))
    store.mark_complete(run_id)
    if old:
        rewrite_rows(root, run_id, "trace", to_a7)


def move_into_meta(root: Path, run_id: str, transform: Callable[[dict[str, Any]], Any]) -> None:
    """Put every row's trace back inside ``meta`` and drop both trace columns: a part written before A7.

    The trace is reassembled here from the envelope and the bodies by this file's own reading of the two
    columns, not by the store's, and ``transform`` then says what is left in ``meta`` (the old shape, the
    current one, or something that is no trace at all)."""
    for path in parts(root, run_id):
        table = pq.read_table(path)
        metas = []
        for meta_json, env_json, obs_json in zip(table["meta"].to_pylist(), table["trace"].to_pylist(), table["trace_obs"].to_pylist(), strict=True):
            meta = json.loads(meta_json)
            assert env_json is not None, "the fixture writes a trace on every row"
            envelope, bodies = json.loads(env_json), json.loads(obs_json) if obs_json else {}
            for span in envelope["spans"]:
                body = bodies.get(span["span_id"], {})
                for name in ("input", "output"):
                    if name in body:
                        span[name] = body[name]
                if "attrs" in body:
                    span["attrs"] = {**span["attrs"], **body["attrs"]}
            meta["trace"] = transform(envelope)
            metas.append(json.dumps(meta, sort_keys=True, separators=(",", ":")))
        table = table.set_column(table.schema.get_field_index("meta"), "meta", pa.array(metas, type=pa.string()))
        table = table.drop_columns(["trace", "trace_obs"])
        tmp = path.with_name(path.name + ".tmp")
        pq.write_table(table, tmp)
        os.replace(tmp, path)


def cell(row_config: dict[str, Any], replicate: int) -> tuple[int, int]:
    return TASKS.index(row_config["task"]), int(replicate)


def read_traces(root: Path, run_id: str) -> list[tuple[tuple[int, int], Any]]:
    """``((cell, replicate), meta["trace"])`` for every row, through the full read."""
    frame = Store(root).read(run_id)
    return [(cell(c, r), m.get("trace")) for c, r, m in zip(frame["config"], frame["replicate_index"], frame["meta"], strict=True)]


def read_envelopes(root: Path, run_id: str) -> list[tuple[tuple[int, int], Any]]:
    """``((cell, replicate), envelope)`` for every row, through the narrow envelope read."""
    frame = Store(root).read(run_id, meta=False, trace="envelope")
    return [(cell(c, r), e) for c, r, e in zip(frame["config"], frame["replicate_index"], frame["trace"], strict=True)]


def expected(key: tuple[int, int], *, stamped: bool = False) -> dict[str, Any]:
    return make_trace(*key, stamped=stamped).to_dict()


def snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def inspect_run(root: Path, run_id: str) -> tuple[int, str, str]:
    return run_cli(["--store", str(root), "inspect", run_id, "--event", EVENT])


SPAN_LINE = re.compile(r"^  \d+\t", re.M)


def fail_span_count() -> int:
    """The span lines ``inspect`` must print for ``--event fail``: every span of the two failing rows of each task."""
    return sum(len(make_trace(i, k).spans) for i in range(len(TASKS)) for k in range(2))


# ---------- fixtures: one store, every run built once ----------


@pytest.fixture(scope="module")
def root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stored-trace-read")
    write_run(root, "twin")                       # the current writer, every field A8a added None
    write_run(root, "old", old=True)              # the same traces, stored as a build before A8a stored them
    write_run(root, "current-stamped", stamped=True)  # the current writer, every field set
    write_run(root, "meta-old")                   # a part before A7: the old shape inside meta
    move_into_meta(root, "meta-old", a7_shape)
    write_run(root, "meta-current")               # a part before A7: the current shape inside meta
    move_into_meta(root, "meta-current", lambda envelope: envelope)
    write_run(root, "meta-garbage")               # a part before A7: not a trace (an unknown key)
    move_into_meta(root, "meta-garbage", lambda envelope: {**a7_shape(envelope), "steps": []})
    return root


@pytest.fixture(scope="module")
def mixed_parts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two parts of one run: the first stored before A8a, the second by the current writer, stamped."""
    root = tmp_path_factory.mktemp("stored-trace-read-mixed-parts")
    store = Store(root)
    store.create_run(manifest("mixed"))
    store.append("mixed", records("mixed", tasks=TASKS[:2]))
    rewrite_rows(root, "mixed", "trace", to_a7)
    store.append("mixed", records("mixed", tasks=TASKS[2:], stamped=True))
    store.mark_complete("mixed")
    return root


@pytest.fixture(scope="module")
def mixed_rows(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One part of one run in which every other row was stored before A8a."""
    root = tmp_path_factory.mktemp("stored-trace-read-mixed-rows")
    write_run(root, "mixed")
    rewrite_rows(root, "mixed", "trace", lambda n, v: to_a7(n, v) if n % 2 == 0 else v)
    return root


# ---------- R1: a run stored before A8a opens in full ----------


def test_r1_the_fixture_is_the_shape_a_build_before_a8a_stored(root: Path) -> None:
    table = pq.read_table(parts(root, "old")[0])
    assert table.num_rows == len(TASKS) * REPLICATES
    for value in table["trace"].to_pylist():
        envelope = json.loads(value)
        assert tuple(sorted(envelope)) == tuple(sorted(A7_TRACE_KEYS)), sorted(envelope)
        assert envelope["spans"], "every fixture trace has spans"
        for span in envelope["spans"]:
            assert tuple(sorted(span)) == tuple(sorted(A7_SPAN_KEYS)), sorted(span)
    twin = pq.read_table(parts(root, "twin")[0])
    assert {json.loads(v)["alias_map_version"] for v in twin["trace"].to_pylist()} == {None}, "the twin is the current shape"


def test_r1_a_run_stored_before_a8a_reads_in_full_and_every_row_is_the_trace_it_was(root: Path) -> None:
    got = read_traces(root, "old")
    assert len(got) == len(TASKS) * REPLICATES
    assert {key for key, _ in got} == {(i, k) for i in range(len(TASKS)) for k in range(REPLICATES)}
    for key, trace in got:
        assert trace == expected(key), key


def test_r1_the_run_reads_exactly_as_the_current_writer_stored_the_same_traces(root: Path) -> None:
    assert read_traces(root, "old") == read_traces(root, "twin")


def test_r1_every_stored_trace_validates_under_the_current_schema_once_read(root: Path) -> None:
    for key, trace in read_traces(root, "old"):
        assert Trace.from_dict(trace).to_dict() == expected(key), key


# ---------- R2: what the old shape lacked reads None, field by field ----------


@pytest.mark.parametrize("name", A8A_TRACE_KEYS)
def test_r2_each_trace_key_the_old_shape_lacked_reads_none(root: Path, name: str) -> None:
    for key, trace in read_traces(root, "old"):
        assert name in trace and trace[name] is None, (name, key, trace.get(name, "<absent>"))


@pytest.mark.parametrize("name", A8A_SPAN_KEYS)
def test_r2_each_span_key_the_old_shape_lacked_reads_none_and_never_a_zero_or_a_blank(root: Path, name: str) -> None:
    for key, trace in read_traces(root, "old"):
        for span in trace["spans"]:
            assert name in span and span[name] is None, (name, key, span.get(name, "<absent>"))


def test_r2_what_the_old_shape_had_is_where_it_was_and_the_read_trace_has_exactly_the_current_keys(root: Path) -> None:
    for key, trace in read_traces(root, "old"):
        assert set(trace) == {*A7_TRACE_KEYS, *A8A_TRACE_KEYS}, key
        for span in trace["spans"]:
            assert set(span) == {*A7_SPAN_KEYS, *A8A_SPAN_KEYS}, key


# ---------- R3: a trace already in the current shape is not touched ----------


def test_r3_a_current_trace_with_every_added_field_set_reads_back_with_every_one_of_them(root: Path) -> None:
    got = read_traces(root, "current-stamped")
    assert len(got) == len(TASKS) * REPLICATES
    for key, trace in got:
        assert trace == expected(key, stamped=True), key
        assert trace["alias_map_version"] == "1"
        assert any(s["truncated"] == "observation" and s["bytes_original"] == 9 and s["attempt"] == 2 for s in trace["spans"])


def test_r3_the_current_writer_reads_exactly_what_it_wrote(root: Path) -> None:
    for key, trace in read_traces(root, "twin"):
        assert trace == expected(key), key


# ---------- R4: the tolerance is exactly the old shape ----------

NEAR_MISSES: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "six trace keys but spans of twenty-one": lambda e: {k: v for k, v in e.items() if k != "alias_map_version"},
    "seven trace keys but spans of thirteen": lambda e: {**e, "spans": [{k: s[k] for k in A7_SPAN_KEYS} for s in e["spans"]]},
    "the old trace shape and one unknown key": lambda e: {**a7_shape(e), "steps": []},
    "old spans and one unknown span key": lambda e: {**a7_shape(e), "spans": [{**s, "latency_ms": 3} for s in a7_shape(e)["spans"]]},
    "old spans, one with a key the old shape lacked": lambda e: {**a7_shape(e), "spans": [{**a7_shape(e)["spans"][0], "gate": None}, *a7_shape(e)["spans"][1:]]},
    "old spans, one of them the current shape": lambda e: {**a7_shape(e), "spans": [e["spans"][0], *a7_shape(e)["spans"][1:]]},
}
# Every key the old shape had, missing in turn: rejected, including the ones a None would have filled
# validly (source_version, truncated; error, tokens, code, confidence). A reader that tolerated one of
# those would be wider than the shape A8a replaced, and only a case that drops exactly that key sees it.
def minus_trace_key(key: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda e: {n: v for n, v in a7_shape(e).items() if n != key}


def minus_span_key(key: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda e: {**a7_shape(e), "spans": [{n: v for n, v in s.items() if n != key} for s in a7_shape(e)["spans"]]}


for _trace_key in A7_TRACE_KEYS:
    NEAR_MISSES[f"the old trace shape minus {_trace_key}"] = minus_trace_key(_trace_key)
for _span_key in A7_SPAN_KEYS:
    NEAR_MISSES[f"old spans, every one minus {_span_key}"] = minus_span_key(_span_key)


@pytest.mark.parametrize("name", list(NEAR_MISSES))
def test_r4_a_stored_trace_that_is_not_exactly_the_old_shape_still_raises_from_the_read(tmp_path: Path, name: str) -> None:
    write_run(tmp_path, "near")
    rewrite_rows(tmp_path, "near", "trace", lambda n, v: None if v is None else json.dumps(NEAR_MISSES[name](json.loads(v)), sort_keys=True, separators=(",", ":")))
    with pytest.raises(TraceValidationError):
        Store(tmp_path).read("near")


def test_r4_the_refusal_names_what_is_wrong_and_the_read_of_a_current_run_beside_it_is_unaffected(tmp_path: Path) -> None:
    write_run(tmp_path, "near")
    rewrite_rows(tmp_path, "near", "trace", lambda n, v: None if v is None else json.dumps({**a7_shape(json.loads(v)), "steps": []}, sort_keys=True))
    with pytest.raises(TraceValidationError, match="steps"):
        Store(tmp_path).read("near")
    write_run(tmp_path, "fine")
    assert len(Store(tmp_path).read("fine")) == len(TASKS) * REPLICATES


# ---------- R5: from_dict is unchanged ----------


def test_r5_trace_from_dict_still_rejects_the_stored_shape_naming_the_missing_key(root: Path) -> None:
    old = a7_shape(make_trace(0, 0).to_dict())
    with pytest.raises(TraceValidationError, match="alias_map_version"):
        Trace.from_dict(old)


def test_r5_span_from_dict_still_rejects_a_thirteen_key_span(root: Path) -> None:
    old = a7_shape(make_trace(0, 0).to_dict())["spans"][0]
    assert len(old) == 13
    with pytest.raises(TraceValidationError, match="missing"):
        Span.from_dict(old)


# ---------- R6: the decision is per row ----------


def test_r6_a_run_of_two_parts_one_stored_before_a8a_reads_every_row_each_as_it_was(mixed_parts: Path) -> None:
    got = read_traces(mixed_parts, "mixed")
    assert len(got) == len(TASKS) * REPLICATES
    for key, trace in got:
        assert trace == expected(key, stamped=key[0] >= 2), key


def test_r6_a_part_in_which_every_other_row_was_stored_before_a8a_reads_every_row(mixed_rows: Path) -> None:
    got = read_traces(mixed_rows, "mixed")
    assert len(got) == len(TASKS) * REPLICATES
    for key, trace in got:
        assert trace == expected(key), key


# ---------- R7: inspect opens such a run and prints every span it holds ----------


def normalise(text: str, run_id: str) -> str:
    return text.replace(run_id, "RUN")


def computed_name(root: Path, run_id: str) -> str:
    """PF2 (spec section 4.3): the target id up to its first `/`, the UTC date of created_at, then
    a letter in creation order among that target's runs that day."""
    store = Store(root)
    manifests = sorted((store.manifest(r) for r in store.runs()), key=lambda m: m.created_at)
    stems = [f"{m.target_id.split('/')[0]} {m.created_at[:10]}" for m in manifests]
    i = [m.run_id for m in manifests].index(run_id)
    return f"{stems[i]} {'abcdefghijklmnopqrstuvwxyz'[stems[:i].count(stems[i])]}"


def split_verdict(text: str, root: Path, run_id: str) -> str:
    """PF2 (spec section 4.3): inspect's first line names the run by its name, which differs
    between two runs of one store; check it names this run, and return everything after it."""
    first, _, rest = text.partition("\n")
    rows = 2 * len(TASKS)  # the two failing rows of each task, as fail_span_count counts them
    assert first == (
        f'ok  {rows} of {rows} episodes with outcome or error "{EVENT}" '
        f'in run "{computed_name(root, run_id)}"'
    ), first
    return rest


def test_r7_inspect_opens_a_run_stored_before_a8a_and_prints_every_span_of_the_failing_rows(root: Path) -> None:
    code, out, err = inspect_run(root, "old")
    assert code == 0, err
    assert err == ""
    assert len(SPAN_LINE.findall(out)) == fail_span_count()
    assert out.count("trace: truncated (timeout)") == len(TASKS), "the k = 1 row of each task carries a trace-level reason"


def test_r7_what_it_prints_is_what_the_current_writers_run_of_the_same_traces_prints(root: Path) -> None:
    _, old, _ = inspect_run(root, "old")
    code, twin, err = inspect_run(root, "twin")
    assert code == 0, err
    assert len(SPAN_LINE.findall(twin)) == fail_span_count()
    # PF2 (spec section 4.3): the verdict line names each run by its own name; all after it agrees.
    assert normalise(split_verdict(old, root, "old"), "old") == normalise(split_verdict(twin, root, "twin"), "twin")


def test_r7_it_prints_no_observation_line_because_an_old_span_carries_no_stamp(root: Path) -> None:
    code, out, err = inspect_run(root, "old")
    assert code == 0, err
    assert len(SPAN_LINE.findall(out)) == fail_span_count(), "silence is not the same as no cut: the spans are printed"
    assert "observation:" not in out


def test_r7_a_span_line_of_an_old_run_shows_a_dash_for_each_field_it_never_recorded(root: Path) -> None:
    _, out, _ = inspect_run(root, "old")
    lines = [ln for ln in out.splitlines() if SPAN_LINE.match(ln)]
    assert lines
    for line in lines:
        columns = line.split("\t")
        assert len(columns) == 9, line
        assert columns[5:] == ["-", "-", "-", "-"], line  # step_name, attempt, outcome, gate


def test_r7_inspect_of_a_run_holding_both_shapes_prints_every_span(mixed_parts: Path) -> None:
    code, out, err = inspect_run(mixed_parts, "mixed")
    assert code == 0, err
    assert len(SPAN_LINE.findall(out)) == fail_span_count()


# ---------- R8: a trace stored in meta on a part written before A7 ----------


def test_r8_the_old_shape_inside_meta_reads_as_the_current_shape(root: Path) -> None:
    assert all("trace" not in pq.read_schema(p).names for p in parts(root, "meta-old")), "the fixture is a part before A7"
    got = read_traces(root, "meta-old")
    assert len(got) == len(TASKS) * REPLICATES
    for key, trace in got:
        assert trace == expected(key), key


def test_r8_and_reads_exactly_as_the_current_writers_run_of_the_same_traces(root: Path) -> None:
    assert read_traces(root, "meta-old") == read_traces(root, "twin")


def test_r8_the_current_shape_inside_meta_is_returned_as_written(root: Path) -> None:
    for key, trace in read_traces(root, "meta-current"):
        assert trace == expected(key), key


def test_r8_something_that_is_no_trace_inside_meta_is_returned_as_written(root: Path) -> None:
    for key, trace in read_traces(root, "meta-garbage"):
        assert trace == {**a7_shape(expected(key)), "steps": []}, key


def test_r8_inspect_prints_every_span_of_an_old_trace_inside_meta(root: Path) -> None:
    code, out, err = inspect_run(root, "meta-old")
    assert code == 0, err
    assert len(SPAN_LINE.findall(out)) == fail_span_count()
    _, twin, _ = inspect_run(root, "twin")
    # PF2 (spec section 4.3): the verdict line names each run by its own name; all after it agrees.
    assert normalise(split_verdict(out, root, "meta-old"), "meta-old") == normalise(split_verdict(twin, root, "twin"), "twin")


def test_r8_inspect_prints_no_trace_lines_and_no_error_for_what_is_no_trace_inside_meta(root: Path) -> None:
    code, out, err = inspect_run(root, "meta-garbage")
    assert code == 0, err
    assert err == ""
    assert SPAN_LINE.findall(out) == []


def test_r8_the_envelope_of_an_old_trace_inside_meta_is_the_one_the_current_writer_stores(root: Path) -> None:
    got = read_envelopes(root, "meta-old")
    assert len(got) == len(TASKS) * REPLICATES
    assert all(envelope is not None for _, envelope in got)
    assert got == read_envelopes(root, "twin")


def test_r8_a_span_count_over_those_envelopes_is_the_number_of_spans_stored(root: Path) -> None:
    spans = sum(len(envelope["spans"]) for _, envelope in read_envelopes(root, "meta-old"))
    assert spans == sum(len(make_trace(i, k).spans) for i in range(len(TASKS)) for k in range(REPLICATES))


def test_r8_the_envelope_of_the_current_shape_inside_meta_is_the_one_the_current_writer_stores(root: Path) -> None:
    assert read_envelopes(root, "meta-current") == read_envelopes(root, "twin")


def test_r8_something_that_is_no_trace_inside_meta_has_no_envelope(root: Path) -> None:
    got = read_envelopes(root, "meta-garbage")
    assert len(got) == len(TASKS) * REPLICATES
    assert all(envelope is None for _, envelope in got)


# ---------- R9: the envelope read is untouched ----------


def test_r9_the_envelope_read_returns_each_stored_envelope_as_stored(root: Path) -> None:
    frame = Store(root).read("old", meta=False, trace="envelope")
    assert len(frame) == len(TASKS) * REPLICATES
    for envelope in frame["trace"]:
        assert set(envelope) == set(A7_TRACE_KEYS)
        assert all(set(s) == set(A7_SPAN_KEYS) for s in envelope["spans"])


# ---------- R10: nothing is written ----------


def test_r10_reading_and_inspecting_the_old_runs_moves_no_stored_byte_and_no_mtime(root: Path) -> None:
    before = snapshot(root)
    for run_id in ("old", "meta-old", "twin", "meta-garbage"):
        Store(root).read(run_id)
        assert inspect_run(root, run_id)[0] == 0
    assert snapshot(root) == before


def test_r10_the_old_run_is_still_stored_in_the_old_shape_after_it_was_read(root: Path) -> None:
    Store(root).read("old")
    for value in pq.read_table(parts(root, "old")[0])["trace"].to_pylist():
        assert set(json.loads(value)) == set(A7_TRACE_KEYS)
