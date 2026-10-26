"""CD frozen tests: invariants CD1 to CD12 of "Proofload -- Spec CD Cap Declaration" -- the observation
cap becomes a required per-target declaration with no default, and the store funnel is fixed to
honour it in the same packet.

Frozen on 2026-09-20 off ``1f5491b``, after the update commit. The build is written
against this file and does not edit it. Every name CD mints is imported inside the test that needs
it, so the bare tree fails test by test and never at collection.

**The two things this packet ships, and why they are one packet.** ADR-096: a sweep that asks for
capture must say how large an observation it keeps whole, and the tool supplies no number of its
own. And the live defect underneath it -- **a declared cap above 8192 is not the cap in force**:
the sweep declares it, the manifest records it, the receipt prints it, and the store cuts at the
module default anyway. Both reproduced on the base tree at step zero
(``log/proofload-cap-declaration/10-step-zero-cd-session-a.md``): a sweep declaring 131072 stored a
value above 8,192 bytes as head 6144 + tail 2048, and at a declared 16384 a 10,000-byte value kept 8,192
bytes while a 20,000-byte value kept 16,384. A mandatory declaration over a store that ignores it
is ADR-096's own failure mode with a receipt attached, so CD5 and CD6 are as much this file's
centre as CD1 is.

**The answers this file is frozen against** (spec section 0, D1 to D14; D1 and D3 are rulings):
D1 there is no default anywhere in ``src/``; D2 a sweep file with no ``[capture]`` table declares
nothing, is not refused, and its rows are stored **uncut**; D3 "no cap" is declarable and its
spelling is the string ``"none"``, and exactly that spelling; D4 the missing declaration and the
malformed one are two refusals; D5 the funnel takes the run's limit as ``int | None``; D6 one
``_declared_limit`` helper; D7 ADR-082's arithmetic does not move; D8 one constant renamed, two
deleted; D9 the manifest records the declaration as declared; D10 the container refuses a payload
short of a field; D11 the migration is a hard error with no warning release; D12 ``CaptureSpec``
becomes ``kw_only``; D13 ``t4.toml``'s value stays 8192 and only its comment moves; D14 ``--resume``
is gated on the cap and ``--pair-with`` is not.

**Invariant-to-test map** (41 functions, 75 collected ids; the id counts below sum to 75):

| Invariant | Tests |
|---|---|
| CD1 | ``test_cd1_*`` (3 functions, 3 ids) |
| CD2 | ``test_cd2_*`` (3 functions, 14 ids) |
| CD3 | ``test_cd3_*`` (4 functions, 4 ids) |
| CD4 | ``test_cd4_*`` (3 functions, 4 ids; the fourth retired into A10's P10-9, see below) |
| CD5 | ``test_cd5_*`` (1 function, 3 ids) |
| CD6 | ``test_cd6_*`` (2 functions, 2 ids) |
| CD7 | ``test_cd7_*`` (3 functions, 5 ids) |
| CD8 | ``test_cd8_*`` (3 functions, 9 ids) |
| CD9 | ``test_cd9_*`` (8 functions, 12 ids) |
| CD10 | ``test_cd10_*`` (3 functions, 9 ids) |
| CD11 | ``test_cd11_*`` (4 functions, 4 ids) |
| CD12 | ``test_cd12_*`` (4 functions, 6 ids) |

**Cells (standing rule 15).** Every test here runs in both cells, pandas 2.3.3 and pandas 3.0.5, and
the measured result is that **no CD invariant is cell-specific**: this packet adds no Parquet column
and no store read path. Every stored byte it moves travels inside the ``trace`` / ``trace_obs`` JSON
strings A7 registered in ``store._NULLABLE_STRING_COLUMNS``. Where a test reads a trace column
directly (CD7's P7-9 half) it reads it raw through ``pyarrow`` and tests nullness with ``is None``,
never ``pd.isna`` and never a truth test (A8a section 3.10, A22 section 3.2). The map above is
therefore **75 + 75 = 150 over two cells against twelve invariants**, and no invariant is
missing from either cell.

**Green before and after -- named so their green is not read as coverage.** ``test_cd9_report_py_and_viewer_py_are_byte_untouched``
(D9's claim is that nothing downstream is edited, so it is green on the bare tree and its job is to
stay green), and ``test_cd12_t4_still_declares_8192_and_its_config_hashes_do_not_move`` (D13:
``t4.toml`` already declares, and only its comment moves). Both sit alone rather than inside a test
whose other clauses are red, because what they assert is *absence of change*; neither is counted as
evidence that the build did anything.

**Two digests are restated here rather than imported** (ADR-077's shape, as ``test_fr_first_run.py``
does it): ``report.py`` and ``viewer.py``, whose byte-identity is D9's "with no change to them".
``tests/test_fr_first_run.py``'s ``UNTOUCHED_FILE_SHA256`` carries the same two values for its own
reason; they are two carriers of one fact and both move together or neither does.

**Named gaps, not pinned.** The host/container version handshake (spec section 3.6, section 5): a new
host declaring ``"none"`` against a pre-CD image sends ``null``, which raises inside the child in the
wrong place with the wrong words, and nothing here catches it because nothing can from either side.
The Modal path is asserted at the transport functions only (CD8) and never through a container.
``diff``'s ``truncated`` is still the horizon count and still owed from the surfacing packet.
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
import poisson_prove.executor as executor
from poisson_prove import cli
from poisson_prove.episode import Episode
from poisson_prove.executor import NotResumable, plan, run_local
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
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

#: CD-E1's first line, pinned byte for byte (spec section 3.2).
CD_E1_FIRST_LINE = "[capture].max_observation_bytes is required and has no default."
#: What the rest of CD-E1 must contain, and what it must not. The second list is the whole of
#: section 0.1's first row: an error message that hands out one number to everyone who meets it has
#: restored the default ADR-096 rejected, by another route.
CD_E1_MUST_CONTAIN = ("max_observation_bytes", '"none"', "1024", "8192", "64", "docs/what-capture-stores.md")
CD_E1_MUST_NOT_CONTAIN = ("65536", "measured", "airline", "8 KB", "50 KB")

#: A value between the funnel's old constant (8,192 bytes) and twice it: kept whole under a
#: raised cap, cut under a lowered one.
BIG_VALUE = "x" * 12000
BIG_BYTES = 12000
#: CD6's non-monotone pair: one value between the funnel's old constant and the declared limit, one
#: above both. At 16384 the shipped funnel keeps 8,192 bytes of the first and 16,384 of the second.
MID_VALUE, MID_BYTES = "m" * 10000, 10000
HUGE_VALUE, HUGE_BYTES = "y" * 20000, 20000
NONE_VALUE, NONE_BYTES = "n" * 200000, 200000

#: CD12, as a rule over what ships: every sweep spec under ``examples/`` and the packaged one.
#: PF8 (Q35, front-door spec sections 8.8 and 14): the pilot specs this named left the repository,
#: so the files are found, not listed; a ``.toml`` there with no ``target_id`` is not a sweep spec.
SHIPPED_SWEEP_FILES = tuple(
    str(path.relative_to(REPO))
    for path in sorted([*REPO.glob("examples/**/*.toml"), *(REPO / "src" / "poisson_prove" / "examples").glob("*.toml")])
    if re.search(r"(?m)^target_id\s*=", path.read_text(encoding="utf-8"))
)
assert SHIPPED_SWEEP_FILES, "the packaged quickstart spec at least ships"

#: D9: nothing downstream of the manifest is edited. Minted at the base commit ``1f5491b``.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): viewer.py is the build's (_LAYOUT's inert rule, the summary key, SCHEMA /6 and both refusals, the page order, the holes block, the unverified tail); the whole-file sha256 of the built file. Read through this test's own measurement on the built tree, not predicted.
# PF0 (Q4): no longer asserted. The rename changes viewer.py, and no digest of a file this module
# changes can be frozen honestly before its build exists (front-door spec section 14).
UNTOUCHED_FILE_SHA256 = {
    "viewer.py": "6ed29eb6e77244d7b9d41de3004d08d89cb25f8af9e3cdfd98ba8f0ac22918ba",
}
#: ``report.py`` with ``_observation_cap`` removed, whole lines, at the base commit (CD9). The
#: whole-file value is ``5cfdf03b...`` and is **not** pinned here: D9's "no change to them" does not
#: survive D3's ``"none"``, and this is the one region that moves.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): report.py outside _observation_cap is the build's (the wrap, the complement, mde_unchanged, LS16's Cells sentence); _observation_cap itself is byte-identical to the bare tree's, checked. Read through this test's own measurement on the built tree, not predicted.
# Re-minted 2026-09-26 (A10 declared expectations, phase two, off the build at 662ceff): report.py outside _observation_cap: report.py gains DeclarationCheck under TYPE_CHECKING, _run_declarations and _run_declaration, the declarations keyword on the three builders, and _provenance_lines printing an empty list as none (spec A10 W8); _observation_cap itself is byte-identical to the bare tree's, checked. Read through this test's own measurement on the built tree, not predicted.
# PF0 (Q4): no longer asserted. The rename changes report.py, and no digest of a file this module
# changes can be frozen honestly before its build exists (front-door spec section 14).
REPORT_OUTSIDE_OBSERVATION_CAP_SHA256 = "2e35cd3468dd170503d4ad3d7ec9fe1846d6349b84a577fc6de5bb60b74e8724"
#: CD11: ``split``'s envelope/bodies partition over the fixture below, at the base commit.
SPLIT_PARTITION_SHA256 = "7b1cc5c99c397fd66e3aade809701df3a4f0e01d8cf155ffbaec0c9fa779db19"


# ---------- helpers: never an assertion ----------


def expected_wrapper(value: str, limit: int) -> dict[str, Any]:
    """ADR-082's cut, restated rather than imported: head ``limit - limit // 4``, tail ``limit // 4``."""
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
    environment: dict[str, Any] = {"note": "built by cd session a"}
    if capture is not None:
        environment["capture"] = dict(capture)
    return RunManifest(
        # The same target_id, t_unit and axis_types ``sweep_toml`` writes, so the three gates that
        # sit beside the cap gate (target, unit, axes) pass and the cap gate is what is measured.
        run_id=run_id, target_id="cd-oracle@v0", t_unit="steps", run_salt=RUN_SALT,
        axis_types={"x": "continuous"}, backend="local", environment=environment,
    )


def rec(run_id: str, *, k: int, meta: Mapping[str, Any]) -> EpisodeRecord:
    ep = Episode(outcome="fell", t=3.0, horizon=HORIZON, meta=dict(meta))
    return EpisodeRecord.from_episode(
        ep, run_id=run_id, config={"x": 0.1}, seed=100 + k, replicate_index=k, wall_time=0.1,
        backend_meta={"i": k},
    )


def raw_column(store: Store, run_id: str, column: str) -> dict[int, Any]:
    """One stored column exactly as written, read raw through ``pyarrow`` so a null is ``None`` on
    every pandas (standing rule 15)."""
    out: dict[int, Any] = {}
    for part in sorted((Path(store._root) / run_id / "episodes").glob("part-*.parquet")):
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
    must say and what section 0.1 forbids it to say."""
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
    """D3, the ruling. ``"none"`` parses to ``None``, which means *store every value whole*."""
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


def test_cd3_the_three_retired_constants_appear_nowhere_in_src() -> None:
    """A constant named for a limit that no longer exists is a default for the next reader who
    imports it, and this packet exists because a number nobody chose was doing work nobody saw."""
    hits = [
        f"{path.relative_to(PACKAGE)}:{n}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if any(name in line for name in RETIRED_CONSTANTS)
    ]
    assert hits == [], hits


#: The only phrases that may put ``default`` on a line that names ``max_observation_bytes``, and
#: each of them denies one.
#:
#: **The freeze corrected CD3's grep twice, and says so.** Section 4 words it "neither does the string
#: ``default`` within three lines of ``max_observation_bytes``". Taken literally that forbids CD-E1's
#: own first line -- which section 3.2 pins byte for byte, and which reads "is required and has no
#: default" -- and it also catches ``max_spans``'s neighbouring docstring, "the span cap, off by
#: default", which is a different field's default and is D6's, not this packet's. What the invariant
#: is for is that no line may *supply* a default for this field, so that is what is asserted: the
#: field's own lines, and the structural clause below that the sampler's fallback is gone.
DENIALS = ("has no default", "no default", "not a default", "never a default", "without a default")


def test_cd3_no_line_naming_the_cap_supplies_a_default() -> None:
    """D1. Every appearance of the word on a line that names the field is a denial, never a value."""
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if "max_observation_bytes" not in line or "default" not in line:
                continue
            if not any(d in line for d in DENIALS):
                offenders.append(f"{path.relative_to(PACKAGE)}:{n}: {line.strip()}")
    assert offenders == [], offenders


def test_cd3_the_samplers_fallback_is_gone() -> None:
    """The third of the three places the census found a default (``sampler.py:204``, ``:209``): a
    ``CaptureSpec()`` built to be read for its own field default, and a ``_positive_int`` call that
    took it. Neither survives -- the first cannot be built at all (D1), and the second is the call
    shape that let an absent key pass."""
    import ast

    source = (PACKAGE / "sampler.py").read_text()
    module = ast.parse(source)
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
        if name == "_positive_int":
            args = [a for a in node.args if isinstance(a, ast.Constant)]
            assert all(a.value != "max_observation_bytes" for a in args), ast.unparse(node)
    assert "defaults = CaptureSpec()" not in source


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


# ``test_cd4_finalizes_a10_guard_is_unchanged`` retired into A10's P10-9, 2026-09-25, as a recorded
# A10 update (spec A10 W2, section 7.1 group 2; ruling 2 of 2026-09-25). Reason: it pinned
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
    """**The defect this packet exists to fix.** Measured at ``1f5491b``: the raised case stores
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


# ---------- CD6: what is kept is a function of the value and the limit alone ----------


def test_cd6_the_non_monotone_pair_is_gone() -> None:
    """Today, at a declared 16384, the 10,000-byte value keeps 8,192 bytes and the 20,000-byte value
    keeps 16,384: the funnel re-cuts what the child left whole and skips what the child wrapped.
    Sole catch for a funnel that cuts at any constant, **including one that cuts at
    ``min(declared, OBSERVATION_ROUTING_BYTES)``** -- which would keep the smaller value's 8,192."""
    from poisson_prove.trace import truncate_observations

    limit = 16384
    child = truncate_observations(trace_of(span(1, attrs={"mid": MID_VALUE, "big": HUGE_VALUE})), limit=limit)
    out = executor._with_capture_envelope(rec("cd-6", k=0, meta={"trace": child.to_dict()}), True, limit)
    (s,) = Trace.from_dict(out.meta["trace"]).spans
    assert s.attrs["mid"] == MID_VALUE, "a value under the declared limit is kept whole"
    assert s.attrs["big"] == expected_wrapper(HUGE_VALUE, limit)
    assert s.bytes_original == HUGE_BYTES


def test_cd6_the_three_routes_agree_byte_for_byte() -> None:
    """Child then funnel, funnel alone (a rollout's own trace), and child alone. One rule, not three."""
    from poisson_prove.trace import truncate_observations

    limit = 16384
    before = trace_of(span(1, attrs={"mid": MID_VALUE, "big": HUGE_VALUE}))
    child_only = truncate_observations(before, limit=limit)
    both = Trace.from_dict(
        executor._with_capture_envelope(rec("cd-6", k=1, meta={"trace": child_only.to_dict()}), True, limit).meta["trace"]
    )
    funnel_only = Trace.from_dict(
        executor._with_capture_envelope(rec("cd-6", k=2, meta={"trace": before.to_dict()}), False, limit).meta["trace"]
    )
    assert canonical(both) == canonical(child_only) == canonical(funnel_only)


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
    assert raw_column(store, run_id, "trace_obs")[0] is not None, "split did not route the value"


INVALID_TRACES: dict[str, Any] = {
    "a string": "not a trace",
    "a list": [{"span_id": "1"}],
    "no spans key": {"schema": "poisson-prove.trace/1", "source": "record"},
}


@pytest.mark.parametrize("name", list(INVALID_TRACES), ids=[n.replace(" ", "-") for n in INVALID_TRACES])
def test_cd7_the_funnel_still_never_raises_on_a_trace_it_cannot_read(tmp_path: Path, name: str) -> None:
    """A7's P7-9, re-asserted verbatim (spec section 0.2, U6's surviving clause). A ``limit``
    parameter does not reach that ``try``. Green before and after: keeping it green is the job."""
    garbage = INVALID_TRACES[name]
    store = Store(tmp_path / "store")
    store.create_run(manifest("cd-7", None))
    records = []
    for k, (active, limit) in enumerate(((True, 64), (False, None))):
        record = rec("cd-7", k=k, meta={"trace": garbage, "k": k})
        out = executor._with_capture_envelope(record, active, limit)
        assert out.meta == {"trace": garbage, "k": k}, (name, active, limit)
        records.append(out)
    assert store.append("cd-7", records) == 2
    frame = store.read("cd-7", trace="full")
    assert [r.meta for r in frame.sort_values("replicate_index").itertuples(index=False)] == [
        {"trace": garbage, "k": 0}, {"trace": garbage, "k": 1},
    ]
    assert all(v is None for v in raw_column(store, "cd-7", "trace").values())
    assert all(v is None for v in raw_column(store, "cd-7", "trace_obs").values())


def test_cd7_declared_limit_maps_both_nothings_to_none() -> None:
    """D6: the mapping from *what the sweep said* to *what the funnel does* exists once, and the two
    ``None``s -- no ``[capture]`` table, and ``"none"`` declared -- are the same thing to it."""
    from poisson_prove.capture import CaptureSpec

    spec = SweepSpec.build(
        configs=({"x": 0.1},), axis_types={"x": "continuous"}, replicates=1,
        target_id="cd-oracle@v0", t_unit="steps",
    )
    assert executor._declared_limit(dataclasses.replace(spec, capture=None)) is None
    assert executor._declared_limit(dataclasses.replace(spec, capture=CaptureSpec(max_observation_bytes=None))) is None
    assert executor._declared_limit(dataclasses.replace(spec, capture=CaptureSpec(max_observation_bytes=4096))) == 4096


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
    with pytest.raises(ValueError, match="unknown"):
        _capture_request({**full, "nonsense": 1})
    with pytest.raises(ValueError, match="max_span_bytes"):
        _capture_request({**full, "max_span_bytes": 8192})
    assert _capture_request(None) == (None, "")


# ---------- CD9: the manifest records the declaration as declared, and every surface reads it ----------


def read_capture_record(store: Store, run_id: str) -> dict[str, Any]:
    manifest = store.manifest(run_id) if hasattr(store, "manifest") else None
    if manifest is not None:
        record = manifest.environment.get("capture")
        assert isinstance(record, Mapping), record
        return dict(record)
    (path,) = (Path(store._root) / run_id).glob("manifest.json")
    return dict(json.loads(path.read_text())["environment"]["capture"])


@pytest.mark.parametrize(
    ("declared", "recorded"),
    [(65536, 65536), ("none", "none"), (1, 1)],
    ids=["int", "none", "one"],
)
def test_cd9_the_manifest_records_the_declaration_as_declared(tmp_path: Path, declared: Any, recorded: Any) -> None:
    """D9: the manifest is a record of the *request*, so it carries what was requested in the words
    it was requested in. ``None`` maps back to the string at ``_capture_record`` and at that one site.

    Sole catch for a build that records JSON ``null`` for ``"none"`` -- which would reach the
    surfacing packet's echo as the Python spelling ``None`` or be dropped by its ``*_bytes`` filter."""
    store, run_id = stored_run(
        tmp_path, {"instrument": [], "content": True, "max_observation_bytes": declared}, "outcome_rollout"
    )
    record = read_capture_record(store, run_id)
    assert set(record) == MANIFEST_CAPTURE_KEYS, sorted(record)
    got = record["max_observation_bytes"]
    assert got == recorded and type(got) is type(recorded), (got, type(got))


def test_cd9_a_run_with_no_capture_table_writes_no_capture_record(tmp_path: Path) -> None:
    """D2's manifest half, and the reason D9 mints no ``none declared`` spelling for it: there is
    no record at all, and the surfacing packet's ``not recorded`` already says exactly that."""
    store, run_id = stored_run(tmp_path, None, "outcome_rollout")
    manifest = store.manifest(run_id) if hasattr(store, "manifest") else None
    assert manifest is not None
    assert "capture" not in manifest.environment, manifest.environment.get("capture")


@pytest.fixture(scope="module")
def declared_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Three real local runs in one store: one declaring an int, one declaring ``"none"``, one with
    no ``[capture]`` table at all. The three readings of section 3.5's table, on real stored runs."""
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
    """D9 and section 3.5's table, through the CLI on stored runs. The int reads as the number, and
    ``"none"`` reads as ``none`` -- **not** as ``not recorded``, which is what a run that never
    asked for capture reads and is a different fact.

    Measured at the base commit and reported as a finding: ``report._observation_cap`` keeps an
    entry only when its value ``isinstance(value, int)``, so the string ``"none"`` is dropped and
    this test reads ``not recorded`` on the shipped build. D9's "with no change to them" does not
    hold for the ``"none"`` spelling; the clause is named in the handoff."""
    labels = provenance_of(int_vs_none[surface], html=surface != "report.md")
    assert labels["observation cap a"] == "max_observation_bytes=65536", labels
    assert labels["observation cap b"] == "max_observation_bytes=none", labels


def test_cd9_a_run_with_no_capture_table_still_reads_not_recorded(declared_runs: dict[str, Any]) -> None:
    """The fourth row of section 3.5's table, and the one the surfacing packet already gets right."""
    root, ids, out = declared_runs["root"], declared_runs["ids"], declared_runs["out"] / "bare"
    code, _, err = run_cli(["--store", str(root), "report", ids["int"], ids["bare"], "--event", "fell",
                            "--x", "x", "--out", str(out), "--permutations", "50", "--seed", "0"])
    assert code == 0, err
    labels = provenance_of((out / "report.md").read_text(encoding="utf-8"), html=False)
    assert labels["observation cap a"] == "max_observation_bytes=65536", labels
    assert labels["observation cap b"] == "not recorded", labels


def test_cd9_inspect_names_the_limit_the_run_recorded(tmp_path: Path) -> None:
    """``proofload inspect``'s cut line reads the run's own record of the limit, spelled as recorded.

    The line prints only for a row whose trace has a cut span, so this is measured on a run that cut:
    a 12,000-byte value under a declared 4096. The ``"none"`` case is the test below -- a run that
    declares no cap never cuts, so it has no cut line to name a limit on, and that is the reading."""
    store, run_id = stored_run(
        tmp_path, {"instrument": [], "content": True, "max_observation_bytes": 4096}, "big_rollout", "cut"
    )
    code, out, err = run_cli(["--store", str(Path(store._root)), "inspect", run_id, "--event", "survived"])
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
    code, out, err = run_cli(["--store", str(Path(store._root)), "inspect", run_id, "--event", "survived"])
    assert code == 0, err
    assert [line for line in out.splitlines() if line.startswith("observation: cut")] == [], out[:3000]


# PF0 (Q4): test_cd9_viewer_py_is_byte_untouched removed. It pinned the bytes of src/poisson_prove/viewer.py, which the rename
# changes; no digest of a file this module changes can be frozen honestly before its build
# exists (front-door spec section 14).


# PF0 (Q4): test_cd9_report_py_outside_the_observation_cap_echo_is_the_dispatch_commits removed. It pinned the bytes of src/poisson_prove/report.py outside one function, which the rename
# changes; no digest of a file this module changes can be frozen honestly before its build
# exists (front-door spec section 14).


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
    """D14, CD-E4, and section 3.7's seven rows. One run directory whose rows were cut at two limits
    under a manifest naming one is this packet's own failure mode, reachable by a flag.

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


def test_cd10_the_gate_does_not_spell_the_retired_name_in_src() -> None:
    """**A collision found at the freeze, for review.** D14 says the gate compares the retired
    ``max_span_bytes`` as the same field; A8b's P8-27 pins that the string appears **nowhere** in
    ``src/``. Both cannot hold as written, and a stand-in that spelled the name turned P8-27 red.

    The resolution pinned here is the idiom the surfacing packet already chose one file over
    (``report._observation_cap``: "Echoed and never translated ... so no name is spelled here"): the
    gate reads the capture record by the ``_bytes`` suffix, which compares the retired spelling as
    the same field without naming it, and reads a third spelling too. P8-27 stays green and D14's
    behaviour -- the four retired-key rows above -- is unchanged."""
    hits = [
        f"{path.relative_to(PACKAGE)}:{n}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if "max_span_bytes" in line
    ]
    assert hits == [], hits


def test_cd10_pairing_is_not_gated_and_the_report_prints_both_caps(tmp_path: Path) -> None:
    """``diff`` does not read observations at all (CAP3 section 4.2), and the report has printed both
    runs' caps on separate lines since the surfacing packet, so a reader sees the difference rather
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


def test_cd11_the_routing_constant_is_exported_and_read_by_is_observation_alone() -> None:
    """D8. The value stays 8192, so ``split`` classifies exactly as ADR-090 measured it and no stored
    byte moves; what changes is the name and the claim the name makes."""
    import poisson_prove.trace as trace_module

    assert trace_module.OBSERVATION_ROUTING_BYTES == ROUTING_BYTES
    assert "OBSERVATION_ROUTING_BYTES" in trace_module.__all__
    # Every ``Name`` node that loads the constant, by the function it sits in: ``_is_observation``
    # and nowhere else, in any module. A read anywhere else is a second routing rule.
    import ast

    readers: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        module = ast.parse(path.read_text())
        for node in ast.walk(module):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name) and inner.id == "OBSERVATION_ROUTING_BYTES" and isinstance(inner.ctx, ast.Load):
                    readers.append(f"{path.relative_to(PACKAGE)}::{node.name}")
    assert sorted(set(readers)) == ["trace.py::_is_observation"], sorted(set(readers))


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


def test_cd11_splits_classification_is_byte_identical_to_the_dispatch_commits() -> None:
    """Sole catch for a rename that changes the number with it. A build that "helpfully" threads the
    run's limit into ``split`` changes which column stored bytes live in and breaks ``Store.read`` on
    rows written by any other build (ADR-090, closed; spec section 8 trap 5)."""
    envelope, bodies = split(split_fixture())
    assert sorted(envelope["spans"][0]["attrs"]) == ["app.at", "app.under", "poisson_prove.episode", "poisson_prove.run_id"]
    assert sorted(next(iter(bodies.values()))["attrs"]) == ["app.over", "app.wrapped", "gen_ai.input.messages"]
    # PF0 (Q4, section 2.3): the trace schema string and the span key prefix are renamed; with the
    # two renames undone, the partition is the base commit's byte for byte.
    as_written = json.dumps([envelope, bodies], sort_keys=True)
    assert '"poisson-prove.trace/1"' in as_written and '"poisson_prove.' in as_written and "proofload" not in as_written
    as_0_0_1 = as_written.replace('"poisson-prove.trace/1"', '"proofload.trace/1"').replace('"poisson_prove.', '"proofload.')
    digest = hashlib.sha256(as_0_0_1.encode()).hexdigest()
    assert digest == SPLIT_PARTITION_SHA256, digest
    assert assemble(envelope, bodies).to_dict() == split_fixture().to_dict()


def test_cd11_split_does_not_take_a_limit() -> None:
    """ADR-090 is closed and the store's routing is not a property of the run that wrote it:
    ``Store.read`` reassembles a row without seeing the sweep file."""
    import inspect as inspect_mod

    assert list(inspect_mod.signature(split).parameters) == ["trace"]


# ---------- CD12: every sweep file the repo ships declares, and each one loads ----------


@pytest.mark.parametrize("relative", SHIPPED_SWEEP_FILES)
def test_cd12_every_shipped_sweep_file_declares_and_loads(relative: str) -> None:
    """Sole catch for a build that ships an example its own parser rejects: every sweep spec the
    repository ships loads, and one with a ``[capture]`` table declares its cap as a number.

    PF8 (Q35): the golden-pilot and tau2 files this read, and the three tests that pinned the tau2
    study's pre-registered cap, its config hashes and its comment, left with the pilots; the rule
    stays, over the files that ship."""
    spec = SweepSpec.load(REPO / relative)
    if spec.capture is not None:
        cap = spec.capture.max_observation_bytes
        assert isinstance(cap, int) and cap >= 1, (relative, cap)
