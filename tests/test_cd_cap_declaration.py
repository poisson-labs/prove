"""CD frozen tests: invariants CD1 to CD12 of the cap declaration -- the observation
cap becomes a required per-target declaration with no default, and the store funnel is fixed to
honour it in the same change.

Frozen off ``1f5491b``, after the update commit. The code is written
against this file and does not edit it. Every name CD mints is imported inside the test that needs
it, so the bare tree fails test by test and never at collection.

**The two things this change ships, and why they are one change.** First: a sweep that asks for
capture must say how large an observation it keeps whole, and the tool supplies no number of its
own. And the live defect underneath it -- **a declared cap above 8192 is not the cap in force**:
the sweep declares it, the manifest records it, the receipt prints it, and the store cuts at the
module default anyway. Both reproduced on the base tree before
these tests were written: a sweep declaring 131072 stored a
value above 8,192 bytes as head 6144 + tail 2048, and at a declared 16384 a 10,000-byte value kept 8,192
bytes while a 20,000-byte value kept 16,384. A mandatory declaration over a store that ignores it
is the very failure the declaration exists to prevent, with a receipt attached, so CD5 and CD6 are as much this file's
centre as CD1 is.

**The answers this file is frozen against** (D1 to D14):
D1 there is no default anywhere in ``src/``; D2 a sweep file with no ``[capture]`` table declares
nothing, is not refused, and its rows are stored **uncut**; D3 "no cap" is declarable and its
spelling is the string ``"none"``, and exactly that spelling; D4 the missing declaration and the
malformed one are two refusals; D5 the funnel takes the run's limit as ``int | None``; D6 one
``_declared_limit`` helper; D7 the cut's arithmetic does not move; D8 one constant renamed, two
deleted; D9 the manifest records the declaration as declared; D10 the container refuses a payload
short of a field; D11 the migration is a hard error with no warning release; D12 ``CaptureSpec``
becomes ``kw_only``; D13 ``t4.toml``'s value stays 8192 and only its comment moves; D14 ``--resume``
is gated on the cap and ``--pair-with`` is not.

**Invariant-to-test map** (28 functions, 59 collected ids; the id counts below sum to 59):

| Invariant | Tests |
|---|---|
| CD1 | ``test_cd1_*`` (3 functions, 3 ids) |
| CD2 | ``test_cd2_*`` (3 functions, 14 ids) |
| CD3 | ``test_cd3_*`` (1 function, 1 id) |
| CD4 | ``test_cd4_*`` (3 functions, 4 ids; the fourth retired into A10's P10-9, see below) |
| CD5 | ``test_cd5_*`` (1 function, 3 ids) |
| CD7 | ``test_cd7_*`` (1 function, 1 id) |
| CD8 | ``test_cd8_*`` (3 functions, 9 ids) |
| CD9 | ``test_cd9_*`` (6 functions, 10 ids) |
| CD10 | ``test_cd10_*`` (2 functions, 8 ids) |
| CD11 | ``test_cd11_*`` (4 functions, 4 ids) |
| CD12 | ``test_cd12_*`` (1 function, 2 ids) |

**Cells.** Every test here runs in both cells, pandas 2.3.3 and pandas 3.0.5, and
the measured result is that **no CD invariant is cell-specific**: this change adds no Parquet column
and no store read path. Every stored byte it moves travels inside the ``trace`` / ``trace_obs`` JSON
strings A7 registered in ``store._NULLABLE_STRING_COLUMNS``. Where a test reads a trace column
directly (CD7) it reads it raw through ``pyarrow`` and tests nullness with ``is None``,
never ``pd.isna`` and never a truth test (as in A8a and A22). The map above is
therefore **59 + 59 = 118 over two cells against the eleven invariants it lists**, and none of
them is missing from either cell.

**Named gaps, not pinned.** The host/container version handshake : a new
host declaring ``"none"`` against a pre-CD image sends ``null``, which raises inside the child in the
wrong place with the wrong words, and nothing here catches it because nothing can from either side.
The Modal path is asserted at the transport functions only (CD8) and never through a container.
``diff``'s ``truncated`` is still the horizon count and still owed from the truncation-surfacing change.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import multiprocessing
import re
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

import poisson_prove
from poisson_prove import cli
from poisson_prove.episode import Episode
from poisson_prove.executor import NotResumable, plan, run_local
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.store import RunManifest, Store
from poisson_prove.trace import Span, Trace, assemble, split

pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")

MODULE = __name__
PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parent.parent
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()

RUN_SALT = "cd-oracle-salt"
HORIZON = 10.0
EPOCH = 1_756_900_000_000_000_000
TRUNCATED_KEY = "poisson_prove.truncated"

#: D8: the value does not move, only the name and the job the name claims.
ROUTING_BYTES = 8192
RETIRED_CONSTANTS = ("OBSERVATION_LIMIT_BYTES", "OBSERVATION_HEAD_BYTES", "OBSERVATION_TAIL_BYTES")
CAPTURE_FIELDS_SPEC = ("instrument", "content", "max_observation_bytes", "max_spans")
MANIFEST_CAPTURE_KEYS = frozenset({
    "requested", "active", "reason", "instrumented", "semconv", "alias_map_version",
    "content", "max_observation_bytes", "max_spans",
})

#: CD-E1's first line, pinned byte for byte.
CD_E1_FIRST_LINE = "[capture].max_observation_bytes is required and has no default."
#: What the rest of CD-E1 must contain, and what it must not. The second list is the whole of
#: what it must never say: an error message that hands out one number to everyone who meets it has
#: restored the removed default, by another route.
CD_E1_MUST_CONTAIN = ("max_observation_bytes", '"none"', "1024", "8192", "64", "docs/what-capture-stores.md")
CD_E1_MUST_NOT_CONTAIN = ("65536", "measured", "airline", "8 KB", "50 KB")

#: A value between the funnel's old constant (8,192 bytes) and twice it: kept whole under a
#: raised cap, cut under a lowered one.
BIG_VALUE = "x" * 12000
BIG_BYTES = 12000
#: A value above the old constant and any limit the tests here declare, and one far above both.
HUGE_VALUE, HUGE_BYTES = "y" * 20000, 20000
NONE_VALUE, NONE_BYTES = "n" * 200000, 200000

#: CD12, as a rule over what ships: every sweep spec under ``examples/`` and the packaged one.
#: PF8: the pilot specs this named left the repository,
#: so the files are found, not listed; a ``.toml`` there with no ``target_id`` is not a sweep spec.
SHIPPED_SWEEP_FILES = tuple(
    str(path.relative_to(REPO))
    for path in sorted([*REPO.glob("examples/**/*.toml"), *(REPO / "src" / "poisson_prove" / "examples").glob("*.toml")])
    if re.search(r"(?m)^target_id\s*=", path.read_text(encoding="utf-8"))
)
assert SHIPPED_SWEEP_FILES, "the packaged quickstart spec at least ships"

#: CD11: ``split``'s envelope/bodies partition over the fixture below, at the base commit.
SPLIT_PARTITION_SHA256 = "7b1cc5c99c397fd66e3aade809701df3a4f0e01d8cf155ffbaec0c9fa779db19"


# ---------- helpers: never an assertion ----------


def expected_wrapper(value: str, limit: int) -> dict[str, Any]:
    """The cut, restated rather than imported: head ``limit - limit // 4``, tail ``limit // 4``."""
    head, tail = limit - limit // 4, limit // 4
    raw = value.encode("utf-8")
    return {TRUNCATED_KEY: {
        "head": raw[:head].decode("utf-8"), "tail": raw[len(raw) - tail:].decode("utf-8"),
        "bytes_original": len(raw),
    }}


def span(i: int, *, attrs: Mapping[str, Any] | None = None, output: Any = None) -> Span:
    return Span(
        span_id=f"{i:016x}", parent_id=None, kind="tool", name=f"step-{i}",
        start_ns=EPOCH + i * 1_000_000, end_ns=EPOCH + i * 1_000_000 + 500_000,
        input=None, output=output, attrs={} if attrs is None else dict(attrs),
    )


def trace_of(*spans: Span) -> Trace:
    return Trace(spans=tuple(spans), source="record")


def canonical(trace: Trace) -> str:
    return json.dumps(trace.to_dict(), sort_keys=True)


def sweep_toml(capture: dict[str, Any] | None, *, replicates: int = 1, values: Sequence[float] = (0.1,)) -> str:
    """A sweep file. ``capture`` is written verbatim: this builder declares nothing of its own,
    because what a ``[capture]`` table does or does not say is the whole subject here."""
    lines = [
        'target_id = "cd-oracle@v0"', 't_unit = "steps"', f"replicates = {replicates}", "",
        "[axes.x]", 'type = "continuous"', f"values = {json.dumps(list(values))}", "",
    ]
    if capture is not None:
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def manifest(run_id: str, capture: Mapping[str, Any] | None) -> RunManifest:
    environment: dict[str, Any] = {"note": "built by these tests"}
    if capture is not None:
        environment["capture"] = dict(capture)
    return RunManifest(
        # The same target_id, t_unit and axis_types ``sweep_toml`` writes, so the three gates that
        # sit beside the cap gate (target, unit, axes) pass and the cap gate is what is measured.
        run_id=run_id, target_id="cd-oracle@v0", t_unit="steps", run_salt=RUN_SALT,
        axis_types={"x": "continuous"}, backend="local", environment=environment,
    )


def raw_column(root: Path, run_id: str, column: str) -> dict[int, Any]:
    """One stored column exactly as written, read raw through ``pyarrow`` from the store the test
    made at ``root``, so a null is ``None`` on every pandas (standing rule 15)."""
    out: dict[int, Any] = {}
    for part in sorted((root / run_id / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part, columns=["replicate_index", column])
        for k, v in zip(table.column("replicate_index").to_pylist(), table.column(column).to_pylist(), strict=True):
            out[int(k)] = v
    return out


def full_traces(store: Store, run_id: str) -> dict[int, Any]:
    frame = store.read(run_id, trace="full")
    return {int(r.replicate_index): r.meta.get("trace") for r in frame.itertuples(index=False)}


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


def isolated(fn: Callable[..., Any], *args: Any, timeout: float = 180.0) -> Any:
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

    return trace.get_tracer("cd.oracle", "0.1.0")


def child_run_local(store_root: str, toml_path: str, target: str, salt: str) -> str:
    import importlib

    module_name, attr = target.split(":", 1)
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
    run_local(p, getattr(importlib.import_module(module_name), attr), store)
    return str(p.run_id)


def _emit(value: str) -> Episode:
    """One llm-side observation of ``value``, through the real OTel API into the real recorder."""
    with _tracer().start_as_current_span("chat model") as sp:
        sp.set_attribute("gen_ai.operation.name", "chat")
        sp.set_attribute("gen_ai.input.messages", value)
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={})


def big_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    return _emit(BIG_VALUE)


def huge_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    return _emit(NONE_VALUE)


def own_trace_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """A rollout's own ``record()``-shaped trace, which never passes through the recorder."""
    own = trace_of(span(1, output=HUGE_VALUE, attrs={"tries": 1}))
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={"trace": own.to_dict()})


def outcome_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """A small captured observation and an outcome that varies with the axis, so a pair of these
    runs is something ``report`` and ``serve`` will actually diff."""
    with _tracer().start_as_current_span("chat model") as sp:
        sp.set_attribute("gen_ai.operation.name", "chat")
        sp.set_attribute("gen_ai.input.messages", "ok")
    fell = float(cfg["x"]) > 0.15
    return Episode(outcome="fell" if fell else "survived", t=3.0 if fell else HORIZON, horizon=HORIZON, meta={})


def stored_run(tmp_path: Path, capture: dict[str, Any] | None, target: str, name: str = "store") -> tuple[Store, str]:
    """One real local run from a real sweep file, into a real store."""
    toml = write(tmp_path / f"{name}.toml", sweep_toml(capture))
    root = str(tmp_path / name)
    run_id = isolated(child_run_local, root, str(toml), f"{MODULE}:{target}", RUN_SALT)
    return Store(Path(root)), str(run_id)


def one_stored_span(store: Store, run_id: str) -> Span:
    (stored,) = full_traces(store, run_id).values()
    spans = [s for s in Trace.from_dict(stored).spans if s.attrs.get("gen_ai.input.messages") is not None]
    assert len(spans) == 1, [s.name for s in Trace.from_dict(stored).spans]
    return spans[0]


# ---------- CD1: a [capture] table with no cap is refused at parse, before the run exists ----------


def test_cd1_a_capture_table_with_no_cap_is_refused_with_cd_e1(tmp_path: Path) -> None:
    """D1 and D4. Sole catch for a build that defaults in the sampler and errors nowhere.

    The first line is pinned byte for byte; the rest by clause, in both directions -- what CD-E1
    must say and what it must never say."""
    toml = write(tmp_path / "sweep.toml", sweep_toml({"instrument": ["openai"], "content": False}))
    with pytest.raises(SamplerError) as excinfo:
        SweepSpec.load(toml)
    message = str(excinfo.value)
    assert message.splitlines()[0] == CD_E1_FIRST_LINE, message.splitlines()[0]
    for fragment in CD_E1_MUST_CONTAIN:
        assert fragment in message, (fragment, message)
    for forbidden in CD_E1_MUST_NOT_CONTAIN:
        assert forbidden not in message, (forbidden, message)


def test_cd1_the_cli_refuses_the_same_file_and_creates_no_run_directory(tmp_path: Path) -> None:
    """"Before the run exists" is a claim about the filesystem, so it is measured there."""
    toml = write(tmp_path / "sweep.toml", sweep_toml({"instrument": [], "max_spans": 1000}))
    root = tmp_path / "store"
    code, out, err = run_cli([
        "--store", str(root), "sweep", str(toml), "--target", f"{MODULE}:outcome_rollout", "--yes",
    ])
    assert code != 0, out
    assert CD_E1_FIRST_LINE in (out + err), (out, err)
    assert not root.exists() or list(root.iterdir()) == [], sorted(p.name for p in root.iterdir())


def test_cd1_a_sweep_file_with_no_capture_table_at_all_is_not_refused(tmp_path: Path) -> None:
    """D2's first half, and the reason CD-E1 is at ``_capture_table`` and not at ``load``: a sweep
    that never asked for capture is not made to declare a cap for capture it will not do."""
    spec = SweepSpec.load(write(tmp_path / "bare.toml", sweep_toml(None)))
    assert spec.capture is None


# ---------- CD2: "none" is the second spelling, and the only one ----------


def test_cd2_none_is_the_second_spelling(tmp_path: Path) -> None:
    """D3. ``"none"`` parses to ``None``, which means *store every value whole*."""
    spec = SweepSpec.load(write(tmp_path / "none.toml", sweep_toml({"instrument": [], "max_observation_bytes": "none"})))
    assert spec.capture is not None and spec.capture.max_observation_bytes is None


@pytest.mark.parametrize("value", ["None", "NONE", "None ", "unbounded", "", "8192", 0, -1, 1.0, True, [], {}])
def test_cd2_every_other_spelling_is_refused_with_cd_e2(tmp_path: Path, value: Any) -> None:
    """Exactly that spelling. ``"8192"`` is here because a person who quotes the number is the one
    D4 says already knows what the field is: one line, naming the field and both accepted forms."""
    with pytest.raises(SamplerError) as excinfo:
        SweepSpec.load(write(tmp_path / "bad.toml", sweep_toml({"instrument": [], "max_observation_bytes": value})))
    message = str(excinfo.value)
    assert len(message.splitlines()) == 1, message
    assert "max_observation_bytes" in message
    assert "int >= 1" in message and '"none"' in message, message


def test_cd2_one_is_one(tmp_path: Path) -> None:
    """The bound at its floor is a number and not a spelling of *nothing*."""
    spec = SweepSpec.load(write(tmp_path / "one.toml", sweep_toml({"instrument": [], "max_observation_bytes": 1})))
    assert spec.capture is not None and spec.capture.max_observation_bytes == 1


# ---------- CD3: there is no default in src/ ----------


def test_cd3_capture_spec_has_no_default_cap_and_is_kw_only() -> None:
    """D1 and D12. Sole catch for a build that moves the default from three places to one."""
    from poisson_prove.capture import CaptureSpec

    assert tuple(f.name for f in dataclasses.fields(CaptureSpec)) == CAPTURE_FIELDS_SPEC
    (field,) = [f for f in dataclasses.fields(CaptureSpec) if f.name == "max_observation_bytes"]
    assert field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
    assert field.kw_only is True
    with pytest.raises(TypeError):
        CaptureSpec()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        CaptureSpec(("openai",), False, 8192, None)  # type: ignore[misc]
    spec = CaptureSpec(max_observation_bytes=None)
    assert (spec.instrument, spec.content, spec.max_observation_bytes, spec.max_spans) == ((), False, None, None)


# ---------- CD4: the two cut functions take a required limit: int | None ----------


def test_cd4_neither_cut_function_has_a_default_limit() -> None:
    """D1: a keyword default is a default. Both are public, and both now raise without one."""
    from poisson_prove.trace import finalize, truncate_observations

    big = trace_of(span(1, output=BIG_VALUE))
    with pytest.raises(TypeError):
        truncate_observations(big)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        finalize(big, declaration=None)  # type: ignore[call-arg]


def test_cd4_limit_none_returns_the_trace_itself_at_both() -> None:
    """D3 and D2 share this code path, and ``is`` rather than ``==`` is the point: a trace that is
    not cut is stored byte for byte as it arrived, and ``replace(trace)`` would not be."""
    from poisson_prove.trace import finalize, truncate_observations

    big = trace_of(span(1, output=HUGE_VALUE, attrs={"app.big": HUGE_VALUE}))
    assert truncate_observations(big, limit=None) is big
    assert finalize(big, declaration=None, limit=None) is big


@pytest.mark.parametrize("limit", [0, -1])
def test_cd4_a_limit_below_one_is_refused_naming_the_parameter(limit: int) -> None:
    """``None`` is *no cut*; ``0`` is not a spelling of it (D3), and neither function may read it as one."""
    from poisson_prove.trace import finalize, truncate_observations

    big = trace_of(span(1, output=BIG_VALUE))
    for call in (lambda: truncate_observations(big, limit=limit), lambda: finalize(big, declaration=None, limit=limit)):
        with pytest.raises(ValueError) as excinfo:
            call()
        assert "limit" in str(excinfo.value), str(excinfo.value)


# ``test_cd4_finalizes_a10_guard_is_unchanged`` retired into A10's P10-9, as a recorded
# A10 update (A10 W2). Reason: it pinned
# that ``finalize`` refuses any non-``None`` declaration with a message naming A10, which was the
# clause's job while A10 was unbuilt; A10 builds that half, so ``match="A10"`` is false by design.
# Owner: A10. Cover: ``tests/test_a10_declared.py`` P10-9, which keeps the guard and re-aims it --
# ``declaration=object()`` and ``declaration="verify"`` each still raise ``TypeError``, now naming
# ``Declaration``, and a real ``Declaration`` does not raise. Body at retirement:
# ``with pytest.raises(TypeError, match="A10"): finalize(trace_of(span(1)), declaration=object(), limit=64)``.


# ---------- CD5: what is declared is what the store does, read back through the store ----------


@pytest.mark.parametrize(
    ("declared", "target", "value_bytes", "whole"),
    [
        (131072, "big_rollout", BIG_BYTES, True),
        (4096, "big_rollout", BIG_BYTES, False),
        ("none", "huge_rollout", NONE_BYTES, True),
    ],
    ids=["raised-131072", "lowered-4096", "declared-none"],
)
def test_cd5_the_declared_limit_is_the_limit_in_force(
    tmp_path: Path, declared: Any, target: str, value_bytes: int, whole: bool
) -> None:
    """**The defect this change exists to fix.** Measured at ``1f5491b``: the raised case stores
    6144 + 2048 under a manifest reading 131072. Sole catch for the shipped funnel, and the one leg
    A8b's P8-23 does not reach -- its raised-limit case stops at the recorder.

    A real sweep file, a real local run, a real ``Store.append``, and the value read back through
    ``Store.read``. Nothing here is hand-built (standing rule 14)."""
    store, run_id = stored_run(tmp_path, {"instrument": [], "content": True, "max_observation_bytes": declared}, target)
    s = one_stored_span(store, run_id)
    got = s.attrs["gen_ai.input.messages"]
    if whole:
        assert got == (BIG_VALUE if target == "big_rollout" else NONE_VALUE)
        assert s.truncated is None and s.bytes_original is None
    else:
        assert got == expected_wrapper(BIG_VALUE, 4096)
        assert got[TRUNCATED_KEY]["bytes_original"] == value_bytes
        assert len(got[TRUNCATED_KEY]["head"]) == 3072 and len(got[TRUNCATED_KEY]["tail"]) == 1024
        assert s.truncated == "observation"


# ---------- CD7: no [capture] table stores a rollout's own trace uncut, and the funnel never raises ----------


def test_cd7_a_run_with_no_capture_table_stores_a_rollouts_own_trace_uncut(tmp_path: Path) -> None:
    """D2, **inverting** A8b's ``test_p8_26_a_run_with_no_capture_table_still_stores_a_rollouts_own_trace_cut``,
    which this replaces. What reaches the funnel on that path is a rollout's own ``record()`` trace,
    which the tool never promised to bound; uncut loses nothing, and its cost is disk, which is loud.

    ``split`` has still routed the value out of the envelope -- by ``OBSERVATION_ROUTING_BYTES`` and
    not by any cap, because the store's layout is not a property of the run that wrote it."""
    store, run_id = stored_run(tmp_path, None, "own_trace_rollout")
    (stored,) = full_traces(store, run_id).values()
    (s,) = Trace.from_dict(stored).spans
    assert s.output == HUGE_VALUE
    assert s.truncated is None and s.bytes_original is None
    assert raw_column(tmp_path / "store", run_id, "trace_obs")[0] is not None, "split did not route the value"


# ---------- CD8: the transport refuses what it cannot default ----------


@pytest.mark.parametrize("missing", list(CAPTURE_FIELDS_SPEC))
def test_cd8_a_payload_missing_a_field_is_refused_naming_it(missing: str) -> None:
    """D10, CD-E3. A ``ValueError`` in the shipped shape and **not** a ``TypeError`` out of the
    dataclass constructor: a ``TypeError`` inside a container names Python's contract, not the tool's.

    Under D1 there is no default to fall back to, so an intersection over a short payload would
    build a spec with no cap -- which is the same silent skew the unknown-field check exists for."""
    from poisson_prove.capture import CaptureSpec
    from poisson_prove.executor_modal import _capture_payload, _capture_request

    full = _capture_payload(CaptureSpec(instrument=("openai",), content=True, max_observation_bytes=8192, max_spans=7), "r-cd")
    assert full is not None
    short = {k: v for k, v in full.items() if k != missing}
    with pytest.raises(ValueError) as excinfo:
        _capture_request(short)
    message = str(excinfo.value)
    assert missing in message and "missing" in message, message
    for name in CAPTURE_FIELDS_SPEC:
        assert name in message, (name, message)


@pytest.mark.parametrize(
    "spec_kwargs",
    [
        {"max_observation_bytes": 8192},
        {"max_observation_bytes": None},
        {"max_observation_bytes": 4096, "max_spans": 1000},
        {"instrument": ("openai",), "content": True, "max_observation_bytes": None, "max_spans": None},
    ],
    ids=["int", "none", "int-with-max-spans", "none-instrumented"],
)
def test_cd8_the_round_trip_reconstructs_the_spec_exactly(spec_kwargs: dict[str, Any]) -> None:
    """``None`` crosses as JSON ``null`` and comes back as ``None``."""
    from poisson_prove.capture import CaptureSpec
    from poisson_prove.executor_modal import _capture_payload, _capture_request

    spec = CaptureSpec(**spec_kwargs)
    payload = _capture_payload(spec, "r-cd")
    assert payload is not None
    assert json.loads(json.dumps(payload)) == payload, "the payload is not JSON-native"
    back, run_id = _capture_request(json.loads(json.dumps(payload)))
    assert back == spec and run_id == "r-cd"


def test_cd8_the_shipped_refusals_are_unchanged_and_both_field_tuples_are_equal() -> None:
    """A8b's P8-24, carried through: an unknown key and the retired spelling are still refused, and
    the sampler's copy of the field names still equals the transport's."""
    from poisson_prove.executor_modal import _CAPTURE_FIELDS as TRANSPORT_FIELDS
    from poisson_prove.executor_modal import _capture_request
    from poisson_prove.sampler import _CAPTURE_FIELDS as SAMPLER_FIELDS

    assert tuple(TRANSPORT_FIELDS) == tuple(SAMPLER_FIELDS) == CAPTURE_FIELDS_SPEC
    full = {"run_id": "r-cd", "instrument": [], "content": False, "max_observation_bytes": 8192, "max_spans": None}
    with pytest.raises(ValueError, match="unknown") as excinfo:
        _capture_request({**full, "nonsense": 1})
    assert "nonsense" in str(excinfo.value), str(excinfo.value)
    with pytest.raises(ValueError, match="max_span_bytes"):
        _capture_request({**full, "max_span_bytes": 8192})
    # The retired spelling in place of the field, as an old host sends it: refused, naming it.
    old = {"run_id": "r-cd", "instrument": [], "content": False, "max_span_bytes": 1024, "max_spans": 1000}
    with pytest.raises(ValueError, match="max_span_bytes"):
        _capture_request(old)
    assert _capture_request(None) == (None, "")


# ---------- CD9: the manifest records the declaration as declared, and every surface reads it ----------


def read_capture_record(store: Store, run_id: str) -> dict[str, Any]:
    record = store.manifest(run_id).environment.get("capture")
    assert isinstance(record, Mapping), record
    return dict(record)


@pytest.mark.parametrize(
    ("declared", "recorded"),
    [(65536, 65536), ("none", "none"), (1, 1)],
    ids=["int", "none", "one"],
)
def test_cd9_the_manifest_records_the_declaration_as_declared(tmp_path: Path, declared: Any, recorded: Any) -> None:
    """D9: the manifest is a record of the *request*, so it carries what was requested in the words
    it was requested in. ``None`` maps back to the string at ``_capture_record`` and at that one site.

    Sole catch for a build that records JSON ``null`` for ``"none"`` -- which would reach the
    truncation-surfacing change's echo as the Python spelling ``None`` or be dropped by its ``*_bytes`` filter."""
    store, run_id = stored_run(
        tmp_path, {"instrument": [], "content": True, "max_observation_bytes": declared}, "outcome_rollout"
    )
    record = read_capture_record(store, run_id)
    assert set(record) == MANIFEST_CAPTURE_KEYS, sorted(record)
    got = record["max_observation_bytes"]
    assert got == recorded and type(got) is type(recorded), (got, type(got))


def test_cd9_a_run_with_no_capture_table_writes_no_capture_record(tmp_path: Path) -> None:
    """D2's manifest half, and the reason D9 mints no ``none declared`` spelling for it: there is
    no record at all, and the truncation-surfacing change's ``not recorded`` already says exactly that."""
    store, run_id = stored_run(tmp_path, None, "outcome_rollout")
    manifest = store.manifest(run_id) if hasattr(store, "manifest") else None
    assert manifest is not None
    assert "capture" not in manifest.environment, manifest.environment.get("capture")


@pytest.fixture(scope="module")
def declared_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Three real local runs in one store: one declaring an int, one declaring ``"none"``, one with
    no ``[capture]`` table at all. The three readings of a declaration, on real stored runs."""
    root = tmp_path_factory.mktemp("cd-surfaces")
    store_root = root / "store"
    ids: dict[str, str] = {}
    for name, capture in (
        ("int", {"instrument": [], "content": True, "max_observation_bytes": 65536}),
        ("none", {"instrument": [], "content": True, "max_observation_bytes": "none"}),
        ("bare", None),
    ):
        toml = write(root / f"{name}.toml", sweep_toml(capture, replicates=2, values=(0.1, 0.2)))
        ids[name] = str(isolated(
            child_run_local, str(store_root), str(toml), f"{MODULE}:outcome_rollout", f"{RUN_SALT}-{name}",
        ))
    return {"root": store_root, "ids": ids, "out": root / "out"}


def provenance_of(doc: str, html: bool) -> dict[str, str]:
    """``report.md``'s Provenance list, or a receipt's / the viewer page's, as label -> value.
    Restated from ``tests/test_cut_surfacing.py`` rather than imported."""
    import html as html_mod

    out: dict[str, str] = {}
    if html:
        found = re.search(r"<h2>Provenance</h2>\s*<ul>(.*?)</ul>", doc, re.S)
        assert found is not None, "no Provenance list"
        items = re.findall(r"<li>(.*?)</li>", found.group(1), re.S)
        for item in items:
            label, _, value = html_mod.unescape(item).partition(": ")
            out[label] = value
        return out
    for line in doc.split("## Provenance\n", 1)[1].splitlines():
        if line.startswith("- "):
            label, _, value = line[2:].partition(": ")
            out[label] = value
    return out


@pytest.fixture(scope="module")
def int_vs_none(declared_runs: dict[str, Any]) -> dict[str, str]:
    """``report`` and ``serve`` over the int-declaring run and the ``"none"``-declaring one, once.
    Three surfaces off one pair, because ``--out`` refuses a directory it has already written."""
    from poisson_prove.viewer import SCHEMA, render_html

    root, ids, out = declared_runs["root"], declared_runs["ids"], declared_runs["out"]
    base = ["--store", str(root)]
    knobs = ["--permutations", "50", "--seed", "0"]
    code, _, err = run_cli([*base, "report", ids["int"], ids["none"], "--event", "fell", "--x", "x",
                            "--out", str(out), *knobs])
    assert code == 0, err
    code, raw, err = run_cli([*base, "serve", ids["int"], ids["none"], "--event", "fell", "--x", "x",
                              "--json", *knobs])
    assert code == 0, err
    payload = json.loads(raw)
    assert payload["schema"] == SCHEMA, payload["schema"]
    return {
        "report.md": (out / "report.md").read_text(encoding="utf-8"),
        "receipt.html": (out / "receipt.html").read_text(encoding="utf-8"),
        "viewer page": render_html(payload),
    }


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_cd9_every_surface_reads_the_declaration_as_declared(int_vs_none: dict[str, str], surface: str) -> None:
    """D9, through the CLI on stored runs. The int reads as the number, and
    ``"none"`` reads as ``none`` -- **not** as ``not recorded``, which is what a run that never
    asked for capture reads and is a different fact.

    Measured at the base commit and reported as a finding: ``report._observation_cap`` keeps an
    entry only when its value ``isinstance(value, int)``, so the string ``"none"`` is dropped and
    this test reads ``not recorded`` on the shipped build. D9's "with no change to them" does not
    hold for the ``"none"`` spelling."""
    labels = provenance_of(int_vs_none[surface], html=surface != "report.md")
    assert labels["observation cap a"] == "max_observation_bytes=65536", labels
    assert labels["observation cap b"] == "max_observation_bytes=none", labels


def test_cd9_a_run_with_no_capture_table_still_reads_not_recorded(declared_runs: dict[str, Any]) -> None:
    """The fourth case, a run with no table, and the one the truncation-surfacing change already gets right."""
    root, ids, out = declared_runs["root"], declared_runs["ids"], declared_runs["out"] / "bare"
    code, _, err = run_cli(["--store", str(root), "report", ids["int"], ids["bare"], "--event", "fell",
                            "--x", "x", "--out", str(out), "--permutations", "50", "--seed", "0"])
    assert code == 0, err
    labels = provenance_of((out / "report.md").read_text(encoding="utf-8"), html=False)
    assert labels["observation cap a"] == "max_observation_bytes=65536", labels
    assert labels["observation cap b"] == "not recorded", labels


def test_cd9_inspect_names_the_limit_the_run_recorded(tmp_path: Path) -> None:
    """``poisson-prove inspect``'s cut line reads the run's own record of the limit, spelled as recorded.

    The line prints only for a row whose trace has a cut span, so this is measured on a run that cut:
    a 12,000-byte value under a declared 4096. The ``"none"`` case is the test below -- a run that
    declares no cap never cuts, so it has no cut line to name a limit on, and that is the reading."""
    store, run_id = stored_run(
        tmp_path, {"instrument": [], "content": True, "max_observation_bytes": 4096}, "big_rollout", "cut"
    )
    code, out, err = run_cli(["--store", str(tmp_path / "cut"), "inspect", run_id, "--event", "survived"])
    assert code == 0, err
    cut_lines = [line for line in out.splitlines() if line.startswith("observation: cut")]
    assert cut_lines, out[:3000]
    assert all("limit max_observation_bytes=4096" in line for line in cut_lines), cut_lines


def test_cd9_a_run_that_declared_none_has_nothing_to_report_cut(tmp_path: Path) -> None:
    """D3 end to end: ``"none"`` is *store every value whole*, so a 200,000-byte observation produces
    no cut line at all. Sole catch, with CD5's third id, for a build that reads ``"none"`` as a number."""
    store, run_id = stored_run(
        tmp_path, {"instrument": [], "content": True, "max_observation_bytes": "none"}, "huge_rollout", "uncut"
    )
    code, out, err = run_cli(["--store", str(tmp_path / "uncut"), "inspect", run_id, "--event", "survived"])
    assert code == 0, err
    assert [line for line in out.splitlines() if line.startswith("observation: cut")] == [], out[:3000]


# ---------- CD10: resume is gated on the cap, and pairing is not ----------


RESUME_ROWS: tuple[tuple[str, dict[str, Any] | None, dict[str, Any] | None, bool], ...] = (
    ("same-int", {"max_observation_bytes": 8192}, {"instrument": [], "max_observation_bytes": 8192}, True),
    ("raised", {"max_observation_bytes": 8192}, {"instrument": [], "max_observation_bytes": 65536}, False),
    ("retired-key-same", {"max_span_bytes": 8192}, {"instrument": [], "max_observation_bytes": 8192}, True),
    ("retired-key-none", {"max_span_bytes": 8192}, {"instrument": [], "max_observation_bytes": "none"}, False),
    ("both-absent", None, None, True),
    ("recorded-nothing-vs-declares", None, {"instrument": [], "max_observation_bytes": 8192}, False),
    ("recorded-none-vs-no-table", {"max_observation_bytes": "none"}, None, False),
)


@pytest.mark.parametrize(("name", "recorded", "declared", "resumes"), RESUME_ROWS, ids=[r[0] for r in RESUME_ROWS])
def test_cd10_resume_is_gated_on_the_cap(
    tmp_path: Path, name: str, recorded: dict[str, Any] | None, declared: dict[str, Any] | None, resumes: bool
) -> None:
    """D14, CD-E4, and the seven ``RESUME_ROWS``. One run directory whose rows were cut at two limits
    under a manifest naming one is this change's own failure mode, reachable by a flag.

    The retired spelling ``max_span_bytes`` is compared as the same field, and "recorded nothing"
    against "declares something" counts as a difference in **both** directions. Sole catch for a
    gate that compares only when both keys are ``max_observation_bytes``."""
    base = {"requested": True, "active": True, "reason": None, "instrumented": [],
            "semconv": "1.42.0", "alias_map_version": "1", "content": True, "max_spans": 1000}
    store = Store(tmp_path / "store")
    store.create_run(manifest("cd-10", None if recorded is None else {**base, **recorded}))
    spec = SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(declared, replicates=2, values=(0.1, 0.2))))
    if resumes:
        p = plan(spec, store, resume="cd-10")
        assert p.run_id == "cd-10"
        return
    with pytest.raises(NotResumable) as excinfo:
        plan(spec, store, resume="cd-10")
    message = str(excinfo.value)
    assert "cd-10" in message
    recorded_name = "max_observation_bytes" if recorded is None else next(iter(recorded))
    assert recorded_name in message or "no observation cap" in message, message


def test_cd10_pairing_is_not_gated_and_the_report_prints_both_caps(tmp_path: Path) -> None:
    """``diff`` does not read observations at all (CAP3), and the report has printed both
    runs' caps on separate lines since the truncation-surfacing change, so a reader sees the difference rather
    than being protected from it."""
    base = {"requested": True, "active": True, "reason": None, "instrumented": [],
            "semconv": "1.42.0", "alias_map_version": "1", "content": True, "max_spans": 1000}
    store = Store(tmp_path / "store")
    store.create_run(manifest("cd-10-a", {**base, "max_observation_bytes": 8192}))
    spec = SweepSpec.load(write(
        tmp_path / "sweep.toml",
        sweep_toml({"instrument": [], "max_observation_bytes": 65536}, replicates=2, values=(0.1, 0.2)),
    ))
    p = plan(spec, store, pair_with="cd-10-a")
    assert p.run_id != "cd-10-a" and p.run_salt == store.manifest("cd-10-a").run_salt


# ---------- CD11: the constants say what they do ----------


def test_cd11_the_routing_constant_is_exported_and_is_8192() -> None:
    """D8. The value stays 8192, so ``split`` classifies exactly as it did and no stored
    byte moves; what changes is the name and the claim the name makes."""
    import poisson_prove.trace as trace_module

    assert trace_module.OBSERVATION_ROUTING_BYTES == ROUTING_BYTES
    assert "OBSERVATION_ROUTING_BYTES" in trace_module.__all__


def test_cd11_the_three_retired_names_are_out_of_the_public_surface() -> None:
    import poisson_prove.trace as trace_module

    for name in RETIRED_CONSTANTS:
        assert name not in trace_module.__all__, name
        assert not hasattr(trace_module, name), name


def split_fixture() -> Trace:
    """Attribute values at 8191, 8192 and 8193 bytes, a 20,000-byte wrapper, a named observation key
    and both routing stamps far over the constant. Every clause of ``_is_observation``, once."""
    wrapper = {TRUNCATED_KEY: {"head": "h" * 100, "tail": "t" * 20, "bytes_original": HUGE_BYTES}}
    attrs = {
        "app.under": "u" * (ROUTING_BYTES - 1), "app.at": "a" * ROUTING_BYTES, "app.over": "o" * (ROUTING_BYTES + 1),
        "gen_ai.input.messages": "m" * 10, "poisson_prove.run_id": "r" * 9000, "poisson_prove.episode": "e" * 9000,
        "app.wrapped": wrapper,
    }
    return Trace(spans=(span(1, attrs=attrs),), source="record")


def test_cd11_splits_partition_of_the_fixture_is_unchanged() -> None:
    """Sole catch for a rename that changes the number with it. A build that "helpfully" threads the
    run's limit into ``split`` changes which column stored bytes live in and breaks ``Store.read`` on
    rows written by any other build."""
    envelope, bodies = split(split_fixture())
    assert sorted(envelope["spans"][0]["attrs"]) == ["app.at", "app.under", "poisson_prove.episode", "poisson_prove.run_id"]
    assert sorted(next(iter(bodies.values()))["attrs"]) == ["app.over", "app.wrapped", "gen_ai.input.messages"]
    # PF0: the trace schema string and the span key prefix are renamed; with the
    # two renames undone, the partition is the base commit's byte for byte.
    as_written = json.dumps([envelope, bodies], sort_keys=True)
    assert '"poisson-prove.trace/1"' in as_written and '"poisson_prove.' in as_written and "proofload" not in as_written
    as_0_0_1 = as_written.replace('"poisson-prove.trace/1"', '"proofload.trace/1"').replace('"poisson_prove.', '"proofload.')
    digest = hashlib.sha256(as_0_0_1.encode()).hexdigest()
    assert digest == SPLIT_PARTITION_SHA256, digest
    assert assemble(envelope, bodies).to_dict() == split_fixture().to_dict()


def test_cd11_split_does_not_take_a_limit() -> None:
    """The store's routing is not a property of the run that wrote it:
    ``Store.read`` reassembles a row without seeing the sweep file."""
    import inspect as inspect_mod

    assert list(inspect_mod.signature(split).parameters) == ["trace"]


# ---------- CD12: every sweep file the repo ships declares, and each one loads ----------


@pytest.mark.parametrize("relative", SHIPPED_SWEEP_FILES)
def test_cd12_every_shipped_sweep_file_declares_and_loads(relative: str) -> None:
    """Sole catch for a build that ships an example its own parser rejects: every sweep spec the
    repository ships loads, and one with a ``[capture]`` table declares its cap as a number.

    PF8: the two example studies' files this read, and the three tests that pinned one
    study's pre-registered cap, its config hashes and its comment, left with the pilots; the rule
    stays, over the files that ship."""
    spec = SweepSpec.load(REPO / relative)
    if spec.capture is not None:
        cap = spec.capture.max_observation_bytes
        assert isinstance(cap, int) and cap >= 1, (relative, cap)
