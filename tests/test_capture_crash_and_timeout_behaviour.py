"""What capture records when an episode crashes or times out, read through public entry points only.

Every test drives ``worker_batch`` with a capture payload or ``run_local`` with a ``[capture]``
table and an episode timeout, and reads what comes back: the result list, or the stored rows. A
test that installs capture runs it in a child forked from this process (``isolated``), because
installing a provider is permanent; the pytest process never installs. OpenTelemetry objects are
imported inside function bodies.

The rollouts below are module-level so ``worker_batch`` can resolve them by import path and a
forked episode child can run them.
"""

from __future__ import annotations

import dataclasses
import json
import multiprocessing
import time
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from poisson_prove.episode import Episode
from poisson_prove.executor import plan, run_local
from poisson_prove.executor_modal import Job, worker_batch
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store
from poisson_prove.trace import Span, Trace

try:
    import opentelemetry.sdk  # noqa: F401
except ImportError:  # pragma: no cover - the [agent] extra is absent
    HAS_OTEL_SDK = False
else:
    HAS_OTEL_SDK = True

MODULE = __name__
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
needs_capture = pytest.mark.skipif(not HAS_OTEL_SDK, reason="capture lives behind the [agent] extra")
needs_fork = pytest.mark.skipif(not FORK_AVAILABLE, reason="the timeout path needs the fork start method")

RUN_ID_KEY = "poisson_prove.run_id"
EPISODE_KEY = "poisson_prove.episode"
RUN_ID = "r-capture-behaviour"
SALT = "capture-behaviour-salt"
HORIZON = 10.0
EXCEPTION = "RuntimeError"
MESSAGE = "boom"
NON_EPISODE_TEXT = "rollout returned dict, expected Episode"
POISON = "this child broke Trace.to_dict"
DECLARED_LIMIT = 8192
TIMEOUT_S = 0.5  # the episode deadline
NO_HANG_TIMEOUT_S = 30.0  # the fork path with nothing to kill: every rollout here returns at once
HANG_S = 30.0  # far past every bound below: only a kill ends a hung child in time
DRAIN_GRACE_S = 2.0  # the executor's documented wait for the drained snapshot
JOIN_GRACE_S = 5.0  # the executor's documented wait before it kills
BEFORE_KEY = "behaviour.before"
TICK_KEY = "behaviour.tick"
CONTENT_ATTRS = {
    "gen_ai.input.messages": json.dumps([{"role": "user", "content": "plan the refund"}]),
    "server.address": "api.example",
}


# ---------- module-level rollouts ----------


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("behaviour.instrumentation", "0.1.0")


def _episode(seed: int) -> Episode:
    return Episode(outcome="survived", t=HORIZON, horizon=HORIZON)


def _tick() -> None:
    """Wait for the wall clock to tick, so consecutive span starts are strictly increasing."""
    tick = time.time_ns()
    while time.time_ns() == tick:
        pass


def spanless_raising_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Raises before its first span: capture holds nothing."""
    raise RuntimeError(f"{MESSAGE} {seed}")


def _raise_at_to_dict(self: Any) -> dict[str, Any]:
    raise RuntimeError(POISON)


def to_meta_poisoning_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """One span, then ``Trace.to_dict`` broken on the class in this child, then the raise: the
    recorder's ``to_meta()`` raises after the rollout's own exception."""
    with _tracer().start_as_current_span(f"invoke_agent {seed}"):
        Trace.to_dict = _raise_at_to_dict  # type: ignore[method-assign]
        raise RuntimeError(f"{MESSAGE} {seed}")


def dict_returning_rollout(cfg: Mapping[str, Any], seed: int) -> Any:
    """Two closed spans, then a dict where an ``Episode`` was expected."""
    tracer = _tracer()
    with tracer.start_as_current_span(f"invoke_agent {seed}") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        with tracer.start_as_current_span(f"chat {seed}") as chat:
            chat.set_attribute("gen_ai.operation.name", "chat")
    return {"outcome": "fell", "t": 1.0, "horizon": HORIZON}


def capped_then_hanging_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Three closed spans in start order, then one opened and left open at the kill."""
    tracer = _tracer()
    for name in ("s0", "s1", "s2"):
        _tick()
        with tracer.start_as_current_span(name) as span:
            span.set_attribute("gen_ai.operation.name", "chat")
    _tick()
    with tracer.start_as_current_span("open-0"):
        time.sleep(HANG_S)
    return _episode(seed)


def ticking_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """One open span whose attribute keeps changing until the kill."""
    with tracer_span("ticking") as span:
        span.set_attribute(BEFORE_KEY, "set before the hang")
        deadline = time.perf_counter() + HANG_S
        i = 0
        while time.perf_counter() < deadline:
            i += 1
            span.set_attribute(TICK_KEY, i)
            time.sleep(0.01)
    return _episode(seed)


def tracer_span(name: str) -> Any:
    return _tracer().start_as_current_span(name)


def content_hanging_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """One open span carrying a content attribute and a plain one, hung at the kill."""
    with tracer_span("chat") as span:
        for key, value in CONTENT_ATTRS.items():
            span.set_attribute(key, value)
        time.sleep(HANG_S)
    return _episode(seed)


def snapshot_failing_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """``Trace.to_dict`` broken on the class in this child, then a hang: the snapshot at the kill
    cannot become a payload."""
    with tracer_span(f"invoke_agent {seed}"):
        Trace.to_dict = _raise_at_to_dict  # type: ignore[method-assign]
        time.sleep(HANG_S)
    return _episode(seed)


def sigterm_ignoring_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Ignores SIGTERM and hangs: only the executor's kill ends it."""
    import signal

    with tracer_span(f"invoke_agent {seed}"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(HANG_S)
    return _episode(seed)


# ---------- helpers (copied from the M3 capture tests) ----------


def sweep_toml(*, capture: dict[str, Any] | None, roles: tuple[str, ...] = ("a",)) -> str:
    """A one-axis sweep over ``role`` with one replicate; ``capture`` is its ``[capture]`` table."""
    lines = ['target_id = "capture-behaviour@v0"', 't_unit = "steps"', "replicates = 1", "",
             "[axes.role]", 'type = "categorical"', f"values = {json.dumps(list(roles))}", ""]
    if capture is not None:
        capture = {"max_observation_bytes": DECLARED_LIMIT, **capture}
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def jobs_of(p: Any) -> list[Job]:
    return [(dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index) for i, pair in enumerate(p.pairs)]


def capture_payload(run_id: str) -> dict[str, Any]:
    return {"run_id": run_id, "instrument": [], "content": False, "max_observation_bytes": DECLARED_LIMIT, "max_spans": 1000}


def _resolve(import_path: str) -> Any:
    import importlib

    module_name, attr = import_path.split(":", 1)
    return getattr(importlib.import_module(module_name), attr)


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
    """Run ``fn(*args)`` in a child process and return its (pickle-native) result."""
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


def child_worker_batch(jobs: list[Job], import_path: str, episode_timeout: float | None) -> list[Any]:
    return worker_batch(jobs, import_path, episode_timeout, capture=capture_payload(RUN_ID))


def child_run_local(store_root: str, toml_path: str, target: str, episode_timeout: float | None) -> dict[str, Any]:
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=SALT, import_path=target)
    t0 = time.perf_counter()
    summary = run_local(p, _resolve(target), store, episode_timeout=episode_timeout)
    return {"run_id": p.run_id, "summary": dataclasses.asdict(summary), "elapsed": time.perf_counter() - t0}


def one_job(tmp_path: Path) -> list[Job]:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    return jobs_of(p)


def assert_traceback_of(text: Any, seed: int, frame: str) -> None:
    assert isinstance(text, str), text
    assert text.startswith("Traceback (most recent call last):"), text
    assert text.rstrip("\n").splitlines()[-1] == f"{EXCEPTION}: {MESSAGE} {seed}", text
    assert frame in text, text


def timed_out_run(tmp_path: Path, target: str, capture: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """One hung episode under ``run_local`` with a ``[capture]`` table and the deadline; returns the
    child's report and the stored row."""
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture=capture))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:{target}", TIMEOUT_S)
    summary = r["summary"]
    assert (summary["n_timeout"], summary["n_errored"], summary["complete"]) == (1, 1, True), summary
    df = Store(tmp_path / "store").read(r["run_id"])
    assert len(df) == 1, df
    row = df.iloc[0]
    assert row["outcome"] is None and row["error"] == "timeout", row
    return r, row


def by_name(trace: Trace) -> dict[str, Span]:
    return {span.name: span for span in trace.spans}


# ---------- a crashed episode with capture on: worker_batch's result forms ----------


@needs_capture
def test_a_capture_on_rollout_that_raises_before_any_span_returns_the_plain_traceback(tmp_path: Path) -> None:
    jobs = one_job(tmp_path)
    (result,) = isolated(child_worker_batch, jobs, f"{MODULE}:spanless_raising_rollout", None)
    assert isinstance(result, str), result  # nothing captured: no dict form, no empty trace
    assert_traceback_of(result, jobs[0][1], "spanless_raising_rollout")


@needs_capture
@needs_fork
def test_a_recorder_whose_to_meta_raises_returns_the_rollouts_own_traceback(tmp_path: Path) -> None:
    jobs = one_job(tmp_path)
    (result,) = isolated(child_worker_batch, jobs, f"{MODULE}:to_meta_poisoning_rollout", NO_HANG_TIMEOUT_S)
    assert isinstance(result, str), result
    assert_traceback_of(result, jobs[0][1], "to_meta_poisoning_rollout")
    assert POISON not in result, result


@needs_capture
def test_a_non_episode_return_after_spans_returns_the_dict_form_with_the_trace(tmp_path: Path) -> None:
    jobs = one_job(tmp_path)
    (result,) = isolated(child_worker_batch, jobs, f"{MODULE}:dict_returning_rollout", None)
    config, seed, _, config_hash, replicate_index = jobs[0]
    assert isinstance(result, dict) and set(result) == {"error", "meta"}, result
    assert result["error"] == NON_EPISODE_TEXT
    assert set(result["meta"]) == {"trace"}, result["meta"]
    trace = Trace.from_dict(result["meta"]["trace"])
    assert trace.truncated is None and trace.dropped == 0 and trace.source == "otel"
    spans = by_name(trace)
    assert set(spans) == {f"invoke_agent {seed}", f"chat {seed}"}, sorted(spans)
    assert spans[f"chat {seed}"].parent_id == spans[f"invoke_agent {seed}"].span_id
    for span in trace.spans:
        assert span.end_ns is not None and span.error is None, span
        assert span.attrs[RUN_ID_KEY] == RUN_ID and span.attrs[EPISODE_KEY] == f"{config_hash}:{replicate_index}", span.attrs


# ---------- a timed-out episode's stored trace ----------


@needs_capture
@needs_fork
def test_a_timed_out_trace_keeps_its_open_span_past_max_spans(tmp_path: Path) -> None:
    _, row = timed_out_run(tmp_path, "capped_then_hanging_rollout", {"instrument": [], "max_spans": 2})
    trace = Trace.from_dict(row["meta"]["trace"])
    assert trace.truncated == "timeout", trace.truncated
    assert [s.name for s in trace.ordered()] == ["s0", "s1", "open-0"], [s.name for s in trace.ordered()]
    assert trace.dropped == 1, trace.dropped  # the closed spans stay capped, earliest-started kept
    assert by_name(trace)["open-0"].end_ns is None


@needs_capture
@needs_fork
def test_a_timed_out_trace_carries_the_open_spans_attributes_as_they_stood_at_the_kill(tmp_path: Path) -> None:
    _, row = timed_out_run(tmp_path, "ticking_rollout", {"instrument": []})
    span = by_name(Trace.from_dict(row["meta"]["trace"]))["ticking"]
    assert span.end_ns is None, span
    assert span.attrs[BEFORE_KEY] == "set before the hang", span.attrs
    # Set again every 10 ms until the kill: read live, so a later value than the first.
    assert isinstance(span.attrs.get(TICK_KEY), int) and span.attrs[TICK_KEY] >= 2, span.attrs


@needs_capture
@needs_fork
def test_a_timed_out_trace_applies_the_content_policy_to_open_spans(tmp_path: Path) -> None:
    _, row = timed_out_run(tmp_path, "content_hanging_rollout", {"instrument": []})
    span = by_name(Trace.from_dict(row["meta"]["trace"]))["chat"]
    assert span.end_ns is None, span
    assert "gen_ai.input.messages" not in span.attrs, span.attrs
    assert span.attrs["server.address"] == "api.example", span.attrs
    assert span.attrs[RUN_ID_KEY] and span.attrs[EPISODE_KEY], span.attrs


# ---------- a child that never drains still times out, within a bound ----------

#: The snapshot-raises child exits from its SIGTERM handler at once; the bound is the deadline,
#: the drain grace and 1.5 s of slack for a loaded machine.
SNAPSHOT_RAISES_BOUND_S = TIMEOUT_S + DRAIN_GRACE_S + 1.5
#: The SIGTERM-ignoring child is killed after both graces (7.5 s by design); 3 s of slack on top.
IGNORES_SIGTERM_BOUND_S = TIMEOUT_S + DRAIN_GRACE_S + JOIN_GRACE_S + 3.0


@needs_capture
@needs_fork
@pytest.mark.parametrize(
    ("target", "bound"),
    [("snapshot_failing_rollout", SNAPSHOT_RAISES_BOUND_S), ("sigterm_ignoring_rollout", IGNORES_SIGTERM_BOUND_S)],
    ids=["snapshot-raises", "ignores-sigterm"],
)
def test_a_child_that_never_drains_still_yields_a_timed_out_row_within_the_bound(
    tmp_path: Path, target: str, bound: float
) -> None:
    r, row = timed_out_run(tmp_path, target, {"instrument": []})
    # Nothing drained: the row carries only the empty envelope an active capture stores for an
    # episode that delivered no trace -- no span, and no "timeout" cut.
    trace = Trace.from_dict(row["meta"]["trace"])
    assert trace.spans == () and trace.truncated is None, row["meta"]
    assert r["elapsed"] < bound, (r["elapsed"], bound)


# ---------- the mock agent's spans follow its task's steps ----------


@pytest.mark.parametrize("task_id", ["search", "checkout", "refund"])
def test_mock_agent_span_names_follow_the_tasks_steps(task_id: str) -> None:
    """The steps are read off the public output: at ``tool_fail_rate`` 0 the agent completes its
    task, one span per step. At 0.45 every span names the step it is on: a failed call repeats it,
    a succeeded one moves to the next."""
    from poisson_prove.examples.mock_agent import rollout

    done = rollout({"task_id": task_id, "tool_fail_rate": 0.0}, 0)
    assert done.outcome == "completed", done
    steps = [s.name for s in Trace.from_dict(done.meta["trace"]).ordered()]
    assert len(steps) == done.t and len(set(steps)) == len(steps), steps
    for seed in range(20):
        tr = Trace.from_dict(rollout({"task_id": task_id, "tool_fail_rate": 0.45}, seed).meta["trace"])
        at = 0
        for span in tr.ordered():
            assert span.name == steps[at], (task_id, seed, span.name, steps[at])
            at += span.error is None
