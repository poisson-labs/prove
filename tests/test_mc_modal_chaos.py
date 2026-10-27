"""MC -- the Modal backend hands a sweep's ``[chaos]`` table to its containers, and the shared
orchestration refuses a chaos run whose rows come back without the per-row chaos record.

What goes wrong without them: if ``run_modal`` does not pass ``[chaos]`` into its containers,
every episode of a faulted Modal arm runs with no fault while its manifest records the fault as
requested, so the arm is a second control arm that reads as a clean measurement.

- **MC1, MC2** (the hand-off): the chaos settings travel into the containers the way the capture
  settings already do, and ``worker_batch`` receives them. Driven through the real
  ``run_modal``, ``_ModalMapper`` and ``_container_batch``: a chaos sweep's rollouts see the
  same chaos settings on the Modal path as on ``run_local``, and every ok Modal row carries
  ``backend_meta["chaos"]``, the record of what its container armed.
- **MC3, MC4** (the refusal): ``run_with_mapper`` is the orchestration every mapper backend shares
  (Modal's, and the seam a Burla backend plugs into). It refuses a chaos run whose ok rows come
  back without ``backend_meta["chaos"]``, loudly, naming the run and the missing record, whichever
  mapper produced them. MC4 is its scope: a run without ``[chaos]``, and a chaos run's errored
  rows (which carry no ``backend_meta`` from a container), are not refused.

**The harness.** Only the ``modal``
package is replaced: a stub placed in ``sys.modules`` before ``run_modal`` imports it, whose
``Function.map`` pickles the map items across a process boundary and calls the shipped function
on each in a fresh spawned interpreter, which is what a Modal container does with it. Everything
else is the backend as built. A network tripwire is armed in every interpreter the harness
starts, so any socket connect raises: nothing here reaches Modal or the internet. The pytest
process itself never arms it (other files serve on a local socket).

**Isolation.** ``chaos.install()`` is once per process and memoised, so every arm runs in its own
spawned interpreter and hands JSON-native results back through a pipe, and the pytest process
never installs. Spawn rather than fork, so an arm inherits nothing the pytest process holds.

**The target** is in this file, not under ``examples/``: one chat completion at the declared
position ``solve`` over ``httpx.MockTransport`` (no socket). It records the content it received.
A faulted episode falls; an untouched one survives.
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import json
import multiprocessing
import pickle
import socket
import sys
import traceback
import types
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

from poisson_prove import chaos
from poisson_prove.episode import Episode
from poisson_prove.store import Store, StoreError
from isolated_support import isolated as run_isolated

MODULE = __name__
TARGET = f"{MODULE}:rollout"
ERRING_TARGET = f"{MODULE}:rollout_raising_on_b"
SALT = "mc-oracle-salt"
CHAOS = {"fault": "llm_empty_single", "rate": 1.0, "steps": ["solve"]}
RECORD_KEYS = frozenset({"requested", "fault", "rate", "steps", "engine_version", "hooks"})
FAULTED_HOOKS = ["sync", "async"]
N_ROWS = 4  # two cells x two replicates
SCRIPTED = "SCRIPTED-OK"
HORIZON = 10.0
BODY = {
    "id": "chatcmpl-scripted",
    "object": "chat.completion",
    "created": 0,
    "model": "scripted-model",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": SCRIPTED}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}
STUB_FILE = "<mc stub: no network, no account>"
ARM_DEADLINE_S = 240.0
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
TIMEOUTS = pytest.mark.parametrize(
    "episode_timeout",
    [None, pytest.param(30.0, marks=pytest.mark.skipif(not FORK_AVAILABLE, reason="needs fork"))],
    ids=["inproc", "fork"],
)


# ---------- the target ----------


def _handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=BODY)


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    with httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://scripted.invalid") as client:
        with chaos.position("solve", 1):
            response = client.post("/v1/chat/completions", json={"model": "scripted-model", "messages": [{"role": "user", "content": "hi"}]})
    content = response.json()["choices"][0]["message"]["content"]
    injected = content != SCRIPTED
    return Episode(
        outcome="fell" if injected else "survived",
        t=1.0 if injected else HORIZON,
        horizon=HORIZON,
        meta={"content": content},
    )


def rollout_raising_on_b(cfg: dict[str, Any], seed: int) -> Episode:
    if cfg["body"] == "b":
        raise RuntimeError("the b cell always crashes")
    return rollout(cfg, seed)


# ---------- guards ----------


def _arm_tripwire() -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("network tripwire: a socket connect was attempted")

    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.socket.connect_ex = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]


# ---------- the modal stub: the package, not the backend ----------


def _container_main(conn: Any, fn_module: str, fn_name: str, wire: bytes, strip_record: bool) -> None:
    """One 'container': a fresh interpreter that unpickles the map items and calls the shipped
    function on each, as Modal's runtime does. ``strip_record`` stands for a container that ran
    the batch without arming chaos: it takes ``backend_meta["chaos"]`` off every result."""
    _arm_tripwire()
    try:
        fn = getattr(importlib.import_module(fn_module), fn_name)
        outputs = [fn(item) for item in pickle.loads(wire)]
        if strip_record:
            for _k, results, _failure in outputs:
                for result in results or []:
                    if isinstance(result, dict):
                        (result.get("backend_meta") or {}).pop("chaos", None)
        conn.send(("ok", pickle.dumps(outputs)))
    except BaseException:  # noqa: BLE001 - shipped back to the parent
        conn.send(("error", traceback.format_exc()))
    finally:
        conn.close()


class _StubImage:
    @classmethod
    def debian_slim(cls, python_version: str | None = None) -> _StubImage:
        return cls()

    @classmethod
    def from_dockerfile(cls, path: str) -> _StubImage:
        return cls()

    def apt_install(self, *_a: Any) -> _StubImage:
        return self

    def pip_install(self, *_a: Any) -> _StubImage:
        return self

    def add_local_python_source(self, *_a: Any) -> _StubImage:
        return self


class _StubFunction:
    def __init__(self, fn: Any, strip_record: bool, shipped: list[str]) -> None:
        self.fn = fn
        self.strip_record = strip_record
        self.shipped = shipped

    def map(self, items: Any, order_outputs: bool = True, return_exceptions: bool = False) -> Iterator[Any]:
        self.shipped.append(f"{self.fn.__module__}.{self.fn.__qualname__}")
        wire = pickle.dumps(list(items))
        ctx = multiprocessing.get_context("spawn")
        parent, child = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_container_main, args=(child, self.fn.__module__, self.fn.__qualname__, wire, self.strip_record))
        proc.start()
        child.close()
        try:
            status, payload = parent.recv()
        finally:
            parent.close()
            proc.join(30.0)
        if status != "ok":
            raise RuntimeError(f"stub container failed: {payload}")
        yield from pickle.loads(payload)


class _StubApp:
    def __init__(self, name: str, *, strip_record: bool, shipped: list[str]) -> None:
        self.name = name
        self.strip_record = strip_record
        self.shipped = shipped

    def function(self, **kwargs: Any) -> Callable[[Any], _StubFunction]:
        def decorate(fn: Any) -> _StubFunction:
            return _StubFunction(fn, self.strip_record, self.shipped)

        return decorate

    @contextlib.contextmanager
    def run(self) -> Iterator[_StubApp]:
        yield self


class _StubSecret:
    @staticmethod
    def from_name(name: str) -> str:
        return name


def _install_modal_stub(strip_record: bool) -> list[str]:
    """Put the stub in ``sys.modules["modal"]``; returns the list the shipped function's name lands in."""
    shipped: list[str] = []
    stub = types.ModuleType("modal")
    stub.App = functools.partial(_StubApp, strip_record=strip_record, shipped=shipped)  # type: ignore[attr-defined]
    stub.Image = _StubImage  # type: ignore[attr-defined]
    stub.Secret = _StubSecret  # type: ignore[attr-defined]
    stub.__file__ = STUB_FILE
    sys.modules["modal"] = stub
    return shipped


# ---------- the arms: each is the body of a spawned interpreter ----------


def _sweep(root: str, table: dict[str, Any] | None) -> Any:
    from poisson_prove.sampler import SweepSpec

    text = 'target_id = "mc-oracle@v0"\nt_unit = "steps"\nreplicates = 2\n\n[axes.body]\ntype = "categorical"\nvalues = ["a", "b"]\n'
    if table is not None:
        text += f'\n[chaos]\nfault = "{table["fault"]}"\nrate = {table["rate"]}\nsteps = {json.dumps(table["steps"])}\n'
    path = Path(root) / "sweep.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return SweepSpec.load(path)


def _summary(summary: Any) -> dict[str, Any]:
    return {"n_ok": summary.n_ok, "n_errored": summary.n_errored, "complete": summary.complete}


def child_local(root: str, episode_timeout: float | None) -> dict[str, Any]:
    from poisson_prove.executor import plan, run_local
    from poisson_prove._resolve import resolve

    store = Store(Path(root) / "store")
    p = plan(_sweep(root, CHAOS), store, backend="local", run_salt=SALT, import_path=TARGET)
    summary = run_local(p, resolve(TARGET), store, episode_timeout=episode_timeout)
    return {"run_id": p.run_id, "summary": _summary(summary)}


def child_modal(root: str, episode_timeout: float | None, strip_record: bool) -> dict[str, Any]:
    """``run_modal`` as built, with only the ``modal`` package stubbed."""
    shipped = _install_modal_stub(strip_record)
    from poisson_prove.executor import ExecutorError, plan
    from poisson_prove.executor_modal import ImageSpec, ModalOptions, ModalTarget, run_modal

    store = Store(Path(root) / "store")
    p = plan(_sweep(root, CHAOS), store, backend="modal", run_salt=SALT, import_path=TARGET)
    target = ModalTarget(import_path=TARGET, image=ImageSpec())
    options = ModalOptions(batch_size=2, concurrency=1, episode_timeout=episode_timeout)
    report: dict[str, Any] = {"run_id": p.run_id}
    try:
        report["summary"] = _summary(run_modal(p, target, store, options=options))
    except ExecutorError as exc:
        report["refused"] = {"type": type(exc).__name__, "message": str(exc)}
    report["modal_file"] = sys.modules["modal"].__file__
    report["shipped"] = list(shipped)
    return report


def child_mapper(root: str, table: dict[str, Any] | None, target: str, hands_over_chaos: bool) -> dict[str, Any]:
    """Another backend on the shared orchestration: a plain mapper that runs each batch through
    ``worker_batch`` in this process, handing it the chaos table or (the check's bug, in a new
    backend's shape) forgetting to."""
    from poisson_prove.executor import ExecutorError, plan
    from poisson_prove.executor_modal import Job, ModalOptions, run_with_mapper, worker_batch

    store = Store(Path(root) / "store")
    spec = _sweep(root, table)
    p = plan(spec, store, backend="modal", run_salt=SALT, import_path=target)
    payload = dict(table) if (hands_over_chaos and table is not None) else None

    def mapper(batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, list[Any]]]:
        for index, jobs in enumerate(batches):
            yield index, worker_batch(list(jobs), target, None, chaos=payload)

    report: dict[str, Any] = {"run_id": p.run_id}
    try:
        report["summary"] = _summary(run_with_mapper(p, mapper, store, options=ModalOptions(batch_size=N_ROWS)))
    except ExecutorError as exc:
        report["refused"] = {"type": type(exc).__name__, "message": str(exc)}
    return report


# ---------- running an arm in its own interpreter ----------


def isolated(fn: Callable[..., Any], *args: Any) -> Any:
    """Run ``fn(*args)`` in a fresh spawned interpreter with the tripwire armed; return its result."""
    return run_isolated(fn, *args, timeout=ARM_DEADLINE_S, method="spawn", prepare=_arm_tripwire)


def rows(root: Path, run_id: str) -> list[dict[str, Any]]:
    """The stored rows, read back in the pytest process, sorted by cell and replicate."""
    try:
        df = Store(root / "store").read(run_id)
    except StoreError:
        return []
    out = []
    for row in df.itertuples():
        meta = row.meta if isinstance(row.meta, dict) else {}
        backend_meta = row.backend_meta if isinstance(row.backend_meta, dict) else {}
        out.append(
            {
                "key": (row.config["body"], int(row.replicate_index)),
                "outcome": row.outcome if isinstance(row.outcome, str) else None,
                "error": row.error if isinstance(row.error, str) else None,
                "content": meta.get("content"),
                "record": backend_meta.get("chaos"),
            }
        )
    return sorted(out, key=lambda r: r["key"])


def status(root: Path, run_id: str) -> str | None:
    try:
        return Store(root / "store").manifest(run_id).status
    except StoreError:
        return None


@pytest.fixture(scope="module")
def arms(tmp_path_factory: pytest.TempPathFactory) -> Callable[..., tuple[Path, dict[str, Any]]]:
    """``arms(kind, episode_timeout)``, run once per module: MC1 and MC2 read the same Modal run."""
    cache: dict[tuple[str, float | None], tuple[Path, dict[str, Any]]] = {}

    def run(kind: str, episode_timeout: float | None) -> tuple[Path, dict[str, Any]]:
        key = (kind, episode_timeout)
        if key not in cache:
            root = tmp_path_factory.mktemp(f"{kind}-{'inproc' if episode_timeout is None else 'fork'}")
            if kind == "local":
                report = isolated(child_local, str(root), episode_timeout)
            else:
                report = isolated(child_modal, str(root), episode_timeout, False)
            cache[key] = (root, report)
        return cache[key]

    return run


# ---------- MC1: the Modal path's rollouts see the chaos settings local's do ----------


@TIMEOUTS
def test_mc1_a_chaos_sweep_on_the_modal_path_hands_each_rollout_the_chaos_settings_local_does(arms: Callable[..., tuple[Path, dict[str, Any]]], episode_timeout: float | None) -> None:
    local_root, local = arms("local", episode_timeout)
    modal_root, modal = arms("modal", episode_timeout)
    assert "refused" not in modal, modal
    assert modal["modal_file"] == STUB_FILE and modal["shipped"] and set(modal["shipped"]) == {"poisson_prove.executor_modal._container_batch"}, modal
    local_rows = rows(local_root, local["run_id"])
    modal_rows = rows(modal_root, modal["run_id"])
    assert len(local_rows) == N_ROWS and all(r["outcome"] == "fell" for r in local_rows), local_rows  # the reference arm
    assert len(modal_rows) == N_ROWS and all(r["error"] is None for r in modal_rows), modal_rows
    assert {r["key"]: (r["outcome"], r["content"]) for r in modal_rows} == {r["key"]: (r["outcome"], r["content"]) for r in local_rows}, "the Modal path's rollouts did not receive [chaos]"
    assert modal["summary"] == local["summary"] == {"n_ok": N_ROWS, "n_errored": 0, "complete": True}


# ---------- MC2: every ok Modal row carries what its container armed ----------


@TIMEOUTS
def test_mc2_every_ok_modal_row_of_a_chaos_run_carries_the_record_its_container_armed(arms: Callable[..., tuple[Path, dict[str, Any]]], episode_timeout: float | None) -> None:
    modal_root, modal = arms("modal", episode_timeout)
    assert "refused" not in modal, modal
    requested = Store(modal_root / "store").manifest(modal["run_id"]).environment["chaos"]
    assert requested["requested"] is True and (requested["fault"], requested["rate"], requested["steps"]) == (CHAOS["fault"], CHAOS["rate"], CHAOS["steps"]), requested
    ok = [r for r in rows(modal_root, modal["run_id"]) if r["error"] is None]
    assert len(ok) == N_ROWS, ok
    for r in ok:
        record = r["record"]
        assert isinstance(record, dict) and set(record) == RECORD_KEYS, r
        assert record["requested"] is True and record["hooks"] == FAULTED_HOOKS, record
        for key in ("fault", "rate", "steps", "engine_version"):
            assert record[key] == requested[key], (key, record, requested)


# ---------- MC3: the orchestration refuses a chaos run whose ok rows lack the record ----------


def _assert_refused(root: Path, report: dict[str, Any]) -> None:
    run_id = report["run_id"]
    assert "summary" not in report, f"a chaos run whose rows lack backend_meta['chaos'] was stored as {report.get('summary')}"
    refused = report["refused"]
    assert refused["type"] == "ModalBackendError", refused
    assert run_id in refused["message"], refused  # names the run
    assert 'backend_meta["chaos"]' in refused["message"], refused  # names the missing record
    assert rows(root, run_id) == [], "the refused batch was stored"
    assert status(root, run_id) != "complete"


def test_mc3_a_mapper_that_never_hands_over_chaos_is_refused_naming_the_run_and_the_record(tmp_path: Path) -> None:
    forgot = isolated(child_mapper, str(tmp_path / "forgot"), CHAOS, TARGET, False)
    _assert_refused(tmp_path / "forgot", forgot)
    # The control differs only in handing the table over, and is accepted.
    handed = isolated(child_mapper, str(tmp_path / "handed"), CHAOS, TARGET, True)
    assert handed.get("summary") == {"n_ok": N_ROWS, "n_errored": 0, "complete": True}, handed
    assert all(isinstance(r["record"], dict) and r["outcome"] == "fell" for r in rows(tmp_path / "handed", handed["run_id"]))


def test_mc3b_the_modal_path_is_refused_when_its_containers_return_rows_without_the_record(tmp_path: Path) -> None:
    stripped = isolated(child_modal, str(tmp_path / "stripped"), None, True)
    assert stripped["modal_file"] == STUB_FILE, stripped
    _assert_refused(tmp_path / "stripped", stripped)
    # The control differs only in the containers keeping the record, and is accepted.
    kept = isolated(child_modal, str(tmp_path / "kept"), None, False)
    assert kept.get("summary") == {"n_ok": N_ROWS, "n_errored": 0, "complete": True}, kept


# ---------- MC4: what the refusal does not reach ----------


def test_mc4_a_run_without_chaos_and_a_chaos_runs_errored_rows_are_not_refused(tmp_path: Path) -> None:
    """Passes with or without the refusal: it pins the refusal's reach, not the refusal."""
    bare = isolated(child_mapper, str(tmp_path / "bare"), None, TARGET, False)
    assert bare.get("summary") == {"n_ok": N_ROWS, "n_errored": 0, "complete": True}, bare
    assert "chaos" not in Store(tmp_path / "bare" / "store").manifest(bare["run_id"]).environment
    mixed = isolated(child_mapper, str(tmp_path / "mixed"), CHAOS, ERRING_TARGET, True)
    assert mixed.get("summary") == {"n_ok": 2, "n_errored": 2, "complete": True}, mixed
    stored = rows(tmp_path / "mixed", mixed["run_id"])
    assert [r["record"] is None for r in stored if r["error"] is not None] == [True, True], stored
    assert all(isinstance(r["record"], dict) for r in stored if r["error"] is None), stored
