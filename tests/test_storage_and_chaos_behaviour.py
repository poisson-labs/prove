"""Storage, cut and chaos behaviour, read off public routes only.

Each test here checks a fact through what a user can reach: a real run stored by ``run_local``,
the container code ``executor_modal.worker_batch`` and the result it hands to the host, the
library ``multi_diff``, the command line, and the chaos seam's public ``install`` / ``injecting``
/ ``position``. Nothing here calls or reads a private name of the package.

- The declared observation cap is the cap in force for a stored row, whichever route the trace
  took: cut in the child (``worker_batch``'s result), cut in the child and passed through the
  host's funnel (a stored captured run), or cut by the funnel alone (a rollout's own trace).
  A value between the module's routing constant (8,192 bytes) and the declared 16,384 is kept whole.
- A captured span carries its OpenTelemetry trace id.
- An observation is already cut in what ``worker_batch`` returns, before it crosses to the host.
- ``multi_diff`` re-censors rows past the common horizon: they count as no event.
- ``poisson-prove diff`` prints ``None`` as the coverage cause of a comparable cell, never
  ``nan``.
- A report prints an empty declaration list as ``none``.
- Whether a chaos fault fires is a pure function of the episode seed and the position: the same
  in two interpreters with different hash seeds, and nested across rates.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import sys
import time
import traceback
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import cli
from poisson_prove.diff import UnpairedAnalysis, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.executor import plan, run_local
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import Span, Trace

MODULE = __name__
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
SALT = "storage-behaviour-salt"
TARGET_ID = "storage-behaviour@v0"
HORIZON = 10.0
EPOCH = 1_756_900_000_000_000_000
TRUNCATED_KEY = "poisson_prove.truncated"

#: The non-monotone pair: one value between the routing constant and the declared cap, one
#: above both.
DECLARED_CAP = 16384
MID_VALUE = "m" * 10000
BIG_VALUE = "y" * 20000

#: The cut before transport: a declared cap far under the routing constant, and two values three times
#: it, one under an observation key and one under a key nobody named.
WIRE_CAP = 1024
WIRE_RESULT = "z" * (3 * WIRE_CAP)
WIRE_PLAIN = "p" * (3 * WIRE_CAP)


# ---------- helpers ----------


def expected_wrapper(value: str, limit: int) -> dict[str, Any]:
    """The cut, restated: head ``limit - limit // 4`` bytes, tail ``limit // 4``, the whole size."""
    raw = value.encode("utf-8")
    head, tail = limit - limit // 4, limit // 4
    return {TRUNCATED_KEY: {"head": raw[:head].decode("utf-8"), "tail": raw[len(raw) - tail:].decode("utf-8"), "bytes_original": len(raw)}}


def sweep_toml(capture: Mapping[str, Any] | None, *, replicates: int = 1, values: Sequence[float] = (0.1,), declare: Mapping[str, Any] | None = None) -> str:
    lines = [
        f'target_id = "{TARGET_ID}"', 't_unit = "steps"', f"replicates = {replicates}", "",
        "[axes.x]", 'type = "continuous"', f"values = {json.dumps(list(values))}", "",
    ]
    if capture is not None:
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
        lines.append("")
    if declare is not None:
        lines.append("[declare]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in declare.items()]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def capture_payload(limit: int) -> dict[str, Any]:
    """The ``[capture]`` table as the host ships it to ``worker_batch``, plus the run id."""
    return {"run_id": "r-behaviour", "instrument": [], "content": False, "max_observation_bytes": limit, "max_spans": None}


def jobs_for(toml: Path, root: Path) -> list[Any]:
    p = plan(SweepSpec.load(toml), Store(root), run_salt=SALT)
    return [(dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index) for i, pair in enumerate(p.pairs)]


def only_span(trace: Mapping[str, Any], name: str) -> Span:
    (span,) = [s for s in Trace.from_dict(trace).spans if s.name == name]
    return span


# ---------- child processes (module-level, so a forked child resolves them by import path) ----------


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
    """Run ``fn(*args)`` in a child process: capture installs a provider once per process, so
    nothing that installs runs in pytest's."""
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
                # The child may have sent its result and exited since the poll above.
                outcome = parent_conn.recv() if parent_conn.poll() else (
                    "error", f"child exited with code {proc.exitcode} before reporting")
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


def child_run_local(store_root: str, toml_path: str, target: str, salt: str) -> str:
    import importlib

    module_name, attr = target.split(":", 1)
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
    run_local(p, getattr(importlib.import_module(module_name), attr), store)
    return str(p.run_id)


def child_worker_batch(jobs: list[Any], import_path: str, capture: dict[str, Any]) -> list[Any]:
    from poisson_prove.executor_modal import worker_batch

    return json.loads(json.dumps(worker_batch(jobs, import_path, None, capture=capture)))


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("storage.behaviour", "0.1.0")


def mid_and_big_otel_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The pair as two attributes of one span, through the real OTel API and the recorder."""
    with _tracer().start_as_current_span("execute_tool lookup") as sp:
        sp.set_attribute("gen_ai.operation.name", "execute_tool")
        sp.set_attribute("mid.attribute", MID_VALUE)
        sp.set_attribute("big.attribute", BIG_VALUE)
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={})


def mid_and_big_own_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The pair as the attributes of a rollout's own trace, which never passes the recorder."""
    span = Span(
        span_id="0000000000000001", parent_id=None, kind="tool", name="execute_tool lookup",
        start_ns=EPOCH, end_ns=EPOCH + 1_000, attrs={"mid.attribute": MID_VALUE, "big.attribute": BIG_VALUE},
    )
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={"trace": Trace(spans=(span,), source="record").to_dict()})


def wire_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """A parent span and, inside it, a tool span carrying two values three times ``WIRE_CAP``."""
    with _tracer().start_as_current_span("invoke_agent planner") as parent:
        parent.set_attribute("gen_ai.operation.name", "invoke_agent")
        with _tracer().start_as_current_span("execute_tool lookup") as sp:
            sp.set_attribute("gen_ai.operation.name", "execute_tool")
            sp.set_attribute("gen_ai.tool.call.result", WIRE_RESULT)
            sp.set_attribute("app.payload", WIRE_PLAIN)
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON, meta={})


# ---------- fixtures ----------


@dataclass(frozen=True)
class CapRoutes:
    root: Path
    captured_run: str
    own_run: str
    child_only: list[Any]


@pytest.fixture(scope="module")
def cap_routes(tmp_path_factory: pytest.TempPathFactory) -> CapRoutes:
    """The pair under ``[capture] max_observation_bytes = 16384`` by the three routes."""
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    root = tmp_path_factory.mktemp("cap-routes")
    toml = write(root / "capture.toml", sweep_toml({"instrument": [], "max_observation_bytes": DECLARED_CAP}))
    captured = isolated(child_run_local, str(root / "store"), str(toml), f"{MODULE}:mid_and_big_otel_rollout", SALT)
    own = isolated(child_run_local, str(root / "store"), str(toml), f"{MODULE}:mid_and_big_own_rollout", SALT + "-own")
    child_only = isolated(child_worker_batch, jobs_for(toml, root / "plan"), f"{MODULE}:mid_and_big_otel_rollout", capture_payload(DECLARED_CAP))
    return CapRoutes(root / "store", captured, own, child_only)


@pytest.fixture(scope="module")
def wire_results(tmp_path_factory: pytest.TempPathFactory) -> list[Any]:
    """What ``worker_batch`` returns for two episodes of ``wire_rollout`` under a 1,024-byte cap."""
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    root = tmp_path_factory.mktemp("wire")
    toml = write(root / "wire.toml", sweep_toml({"instrument": [], "max_observation_bytes": WIRE_CAP}, replicates=2))
    return isolated(child_worker_batch, jobs_for(toml, root / "plan"), f"{MODULE}:wire_rollout", capture_payload(WIRE_CAP))


# ---------- the declared cap is the cap in force, by every route ----------


def stored_trace(root: Path, run_id: str) -> Mapping[str, Any]:
    frame = Store(root).read(run_id, trace="full")
    (trace,) = [meta["trace"] for meta in frame["meta"]]
    return trace


def test_a_declared_cap_above_the_old_constant_keeps_the_smaller_value_whole_and_cuts_the_larger_at_the_cap(cap_routes: CapRoutes) -> None:
    """A funnel that cut at the 8,192-byte routing constant, or at ``min(declared, 8192)``, cuts the
    10,000-byte value; at the declared 16,384 it is kept whole and only the 20,000-byte value is
    cut, at 16,384."""
    for run_id in (cap_routes.captured_run, cap_routes.own_run):
        span = only_span(stored_trace(cap_routes.root, run_id), "execute_tool lookup")
        assert span.attrs["mid.attribute"] == MID_VALUE, (run_id, str(span.attrs["mid.attribute"])[:80])
        assert span.attrs["big.attribute"] == expected_wrapper(BIG_VALUE, DECLARED_CAP), (run_id, str(span.attrs["big.attribute"])[:80])
        assert span.truncated == "observation" and span.bytes_original == len(BIG_VALUE), run_id


def test_the_three_routes_store_the_same_cut(cap_routes: CapRoutes) -> None:
    """Cut in the child alone (``worker_batch``'s result), in the child and then the host's funnel
    (a stored captured run), and by the funnel alone (a rollout's own trace): one rule."""
    (result,) = cap_routes.child_only
    routes = {
        "child": only_span(result["meta"]["trace"], "execute_tool lookup"),
        "child-then-funnel": only_span(stored_trace(cap_routes.root, cap_routes.captured_run), "execute_tool lookup"),
        "funnel": only_span(stored_trace(cap_routes.root, cap_routes.own_run), "execute_tool lookup"),
    }
    seen = {
        name: json.dumps([span.attrs["mid.attribute"], span.attrs["big.attribute"], span.truncated, span.bytes_original], sort_keys=True)
        for name, span in routes.items()
    }
    assert len(set(seen.values())) == 1, {name: text[:120] for name, text in seen.items()}


# ---------- a captured span carries its trace id ----------


def test_a_captured_span_carries_its_open_telemetry_trace_id(wire_results: list[Any], cap_routes: CapRoutes) -> None:
    """Every span of one captured episode carries the same 32-hex, non-zero trace id, and two
    episodes carry two different ones; a stored captured run carries it too."""
    ids = []
    for result in wire_results:
        spans = Trace.from_dict(result["meta"]["trace"]).spans
        assert {s.name for s in spans} == {"invoke_agent planner", "execute_tool lookup"}, [s.name for s in spans]
        found = {s.attrs.get("otel.trace_id") for s in spans}
        assert len(found) == 1, found
        (trace_id,) = found
        assert isinstance(trace_id, str) and len(trace_id) == 32 and set(trace_id) <= set("0123456789abcdef") and set(trace_id) != {"0"}, trace_id
        ids.append(trace_id)
    assert len(set(ids)) == len(wire_results) == 2, ids
    stored = only_span(stored_trace(cap_routes.root, cap_routes.captured_run), "execute_tool lookup")
    assert len(stored.attrs.get("otel.trace_id") or "") == 32, stored.attrs.get("otel.trace_id")


# ---------- the cut happens before transport ----------


def test_what_worker_batch_returns_to_the_host_is_already_cut(wire_results: list[Any]) -> None:
    """The container's result is what crosses to the host. It carries the wrapper for both values,
    and no run of either value longer than the cap; the host's funnel never has to cut it."""
    wire = json.dumps(wire_results)
    assert "z" * (WIRE_CAP + 1) not in wire and "p" * (WIRE_CAP + 1) not in wire, "an uncut observation crossed to the host"
    for result in wire_results:
        span = only_span(result["meta"]["trace"], "execute_tool lookup")
        assert span.attrs["gen_ai.tool.call.result"] == expected_wrapper(WIRE_RESULT, WIRE_CAP)
        assert span.attrs["app.payload"] == expected_wrapper(WIRE_PLAIN, WIRE_CAP)
        assert span.truncated == "observation" and span.bytes_original == len(WIRE_RESULT) + len(WIRE_PLAIN)


# ---------- multi_diff re-censors rows past the common horizon ----------


def horizon_run(store: Store, run_id: str, horizon: float, rows: Sequence[tuple[str, float]], salt: str) -> None:
    store.create_run(RunManifest(
        run_id=run_id, target_id=TARGET_ID, t_unit="steps", run_salt=salt,
        axis_types={"x": "continuous"}, backend="local", environment={},
    ))
    store.append(run_id, [
        EpisodeRecord.from_episode(
            Episode(outcome=outcome, t=t, horizon=horizon, meta={}), run_id=run_id, config={"x": 0.1},
            seed=k, replicate_index=k, wall_time=0.0,
        )
        for k, (outcome, t) in enumerate(rows)
    ])
    store.mark_complete(run_id)


def test_rows_past_the_common_horizon_count_as_no_event(tmp_path: Path) -> None:
    """Run ``a`` stops at t = 5, run ``b`` at t = 10. Compared at 5, ``b``'s eight failures at t = 8
    and its eight survivors at t = 10 are censored at 5: ``b`` has 4 failures in 20 by the horizon,
    as ``a`` has, and not 12."""
    store = Store(tmp_path / "store")
    horizon_run(store, "a", 5.0, [("fail", 2.0)] * 4 + [("ok", 5.0)] * 16, SALT)
    horizon_run(store, "b", 10.0, [("fail", 2.0)] * 4 + [("fail", 8.0)] * 8 + [("ok", 10.0)] * 8, SALT + "-b")
    multi = multi_diff(
        store.read("a"), store.read("b"), events=["fail"], method="fisher_bh",
        manifest_a=store.manifest("a"), manifest_b=store.manifest("b"),
    )
    assert multi.horizon == 5.0 and multi.truncated == 16, (multi.horizon, multi.truncated)
    (row,) = multi.by_event["fail"].cells.to_dict(orient="records")
    assert (row["n_a"], row["n_b"], row["events_a"], row["events_b"]) == (20, 20, 4, 4), row
    assert row["rate_b"] == pytest.approx(0.2) and row["rate_a"] == pytest.approx(0.2), row


# ---------- diff prints None as a comparable cell's coverage cause ----------

#: Per cell, ``(rows with an outcome in a, errored rows in a, rows with an outcome in b, errored in b)``:
#: two comparable cells (one with errored rows in both arms) beside one hole of each cause.
COVERAGE_CELLS: dict[str, tuple[int, int, int, int]] = {
    "base": (8, 0, 8, 0),
    "mixed": (6, 2, 5, 3),
    "only-a": (8, 0, 0, 0),
    "only-b": (0, 0, 8, 0),
    "err-a": (0, 8, 8, 0),
    "err-b": (8, 0, 0, 8),
    "err-both": (0, 8, 0, 8),
}
HOLE_CAUSES = {"only-a": "only_a", "only-b": "only_b", "err-a": "no_outcome_a", "err-b": "no_outcome_b", "err-both": "no_outcome_both"}


def coverage_store(root: Path) -> Store:
    store = Store(root)
    for run_id, index, salt in (("cov-a", 0, SALT), ("cov-b", 2, SALT + "-b")):
        store.create_run(RunManifest(
            run_id=run_id, target_id=TARGET_ID, t_unit="steps", run_salt=salt,
            axis_types={"task": "categorical"}, backend="local", environment={},
        ))
        records = []
        for task, counts in COVERAGE_CELLS.items():
            with_outcome, errored = counts[index], counts[index + 1]
            for k in range(with_outcome):
                records.append(EpisodeRecord.from_episode(
                    Episode(outcome="fell" if k % 2 == 0 else "survived", t=3.0, horizon=HORIZON, meta={}),
                    run_id=run_id, config={"task": task}, seed=k, replicate_index=k, wall_time=0.0,
                ))
            for k in range(with_outcome, with_outcome + errored):
                records.append(EpisodeRecord.errored(run_id=run_id, config={"task": task}, seed=k, replicate_index=k, error="boom", wall_time=0.0))
        store.append(run_id, records)
        store.mark_complete(run_id)
    return store


def test_diff_prints_none_as_a_comparable_cells_coverage_cause_and_never_nan(tmp_path: Path) -> None:
    coverage_store(tmp_path / "store")
    code, out, err = run_cli(["--store", str(tmp_path / "store"), "diff", "cov-a", "cov-b", "--event", "fell", "--method", "fisher_bh", "--permutations", "50"])
    assert code == 0, err
    lines = out.splitlines()
    at = lines.index("## coverage")
    header = [c.strip() for c in lines[at + 2].strip("|").split("|")]
    rows = []
    for line in lines[at + 4:]:
        if not line.startswith("|"):
            break
        rows.append(dict(zip(header, (c.strip() for c in line.strip("|").split("|")), strict=True)))
    section = "\n".join(lines[at:at + 4 + len(rows)])
    assert "nan" not in section.lower(), section
    by_task = {json.loads(row["config"])["task"]: row for row in rows}
    assert set(by_task) == set(COVERAGE_CELLS), sorted(by_task)
    for task in ("base", "mixed"):
        assert (by_task[task]["comparable"], by_task[task]["cause"]) == ("True", "None"), by_task[task]
    for task, cause in HOLE_CAUSES.items():
        assert (by_task[task]["comparable"], by_task[task]["cause"]) == ("False", cause), by_task[task]


# ---------- a report prints an empty declaration list as none ----------


def silent_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """No span and no trace: every declared step is never reached, and nothing undeclared is seen."""
    fell = round(float(cfg["x"]), 1) >= 0.3
    return Episode(outcome="fell" if fell else "survived", t=3.0 if fell else HORIZON, horizon=HORIZON, meta={})


def test_a_report_prints_an_empty_declaration_list_as_none(tmp_path: Path) -> None:
    declare = {"steps": ["plan", "verify"], "outcomes": ["fell", "survived"], "gates": ["verify"]}
    spec = SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(None, replicates=2, values=(0.1, 0.2, 0.3, 0.4), declare=declare)))
    store = Store(tmp_path / "store")
    p = plan(spec, store, run_salt=SALT, import_path=f"{MODULE}:silent_rollout")
    run_local(p, silent_rollout, store)
    code, _, err = run_cli(["--store", str(tmp_path / "store"), "report", p.run_id, "--event", "fell", "--x", "x", "--out", str(tmp_path / "r")])
    assert code == 0, err
    lines = (tmp_path / "r" / "report.md").read_text().splitlines()
    for label in ("undeclared steps", "undeclared outcomes", "emitted gates not declared"):
        assert f"- {label}: none" in lines, (label, [line for line in lines if line.startswith("- ")])
    assert "- never reached: plan, verify" in lines
    assert "- gates never reached: verify" in lines


# ---------- chaos: firing is a pure function of the seed and the position ----------

CHAOS_POSITIONS = [
    ("plan", 1), ("plan", 2), ("solve", 1), ("solve", 2), ("solve", 3), ("verify", 1),
    ("verify", 2), ("submit", 1), ("a:b", 1), ("retry", 1), ("retry", 2), ("retry", 3),
]
CHAOS_SEEDS = (3, 7, 11, 20260913)
CHAOS_RATES = (0.0, 0.25, 0.5, 0.75, 1.0)
CHAOS_SCRIPT = """
import json, sys
import httpx
from poisson_prove.chaos import ChaosSpec, injecting, install, position

positions, seeds, rates = json.loads(sys.argv[1])
body = {"id": "c", "object": "chat.completion", "created": 1, "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "done"}, "finish_reason": "stop"}]}
client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)), base_url="http://chaos.invalid/v1")
install(ChaosSpec(fault="llm_error_single"))
fired = {}
for seed in seeds:
    for rate in rates:
        with injecting(ChaosSpec(fault="llm_error_single", rate=rate), seed) as records:
            for name, attempt in positions:
                with position(name, attempt):
                    client.post("/chat/completions", json={"model": "m", "messages": [{"role": "user", "content": "go"}]})
        fired[f"{seed}:{rate}"] = sorted(r.position for r in records if r.applied)
print(json.dumps(fired))
"""


@pytest.fixture(scope="module")
def fired_by_interpreter() -> list[dict[str, list[str]]]:
    """The fired positions per ``seed:rate``, from two fresh interpreters with different hash seeds."""
    pytest.importorskip("httpx", reason="the chaos seam hooks httpx")
    args = json.dumps([CHAOS_POSITIONS, list(CHAOS_SEEDS), list(CHAOS_RATES)])
    out = []
    for hash_seed in ("1", "271828"):
        done = subprocess.run(
            [sys.executable, "-c", CHAOS_SCRIPT, args], capture_output=True, text=True, timeout=60,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
        )
        assert done.returncode == 0, done.stderr
        out.append(json.loads(done.stdout))
    return out


def test_the_same_seed_fires_the_same_positions_in_two_interpreters(fired_by_interpreter: list[dict[str, list[str]]]) -> None:
    first, second = fired_by_interpreter
    assert first == second


def test_firing_is_nested_across_rates_and_neither_all_nor_none_at_a_half(fired_by_interpreter: list[dict[str, list[str]]]) -> None:
    fired = fired_by_interpreter[0]
    every = sorted(f"{name}:{attempt}" for name, attempt in CHAOS_POSITIONS)
    for seed in CHAOS_SEEDS:
        sets = [set(fired[f"{seed}:{rate}"]) for rate in CHAOS_RATES]
        assert sets[0] == set() and sets[-1] == set(every), seed
        assert all(lo <= hi for lo, hi in zip(sets, sets[1:], strict=False)), (seed, [sorted(s) for s in sets])
    halves = [len(fired[f"{seed}:0.5"]) for seed in CHAOS_SEEDS]
    assert 0 < sum(halves) < len(every) * len(CHAOS_SEEDS), halves
