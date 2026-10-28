"""BU -- the Burla backend: ``poisson-prove sweep … --backend burla`` on a fixed cluster, through Burla.

The frozen tests for the Burla backend: the invariants R1-R7 (the shared runner), M1-M11 (the
host-side mapper), S1-S7 (the launcher), W1-W6 (the bundle and the worker), C1-C5 (chaos and
capture), $1-$9 (cost, caps and the ledger), P1-P7 (pre-flight and CLI) and I1-I6 (imports and
surface).

**No Burla, no network.** Burla is replaced by a fake of the 1.8.1 client, ``tests/bu_fixtures/
burla``, which cites the tag's lines and runs each call over a pool of local fake workers:
long-lived ``python -I -S`` interpreters with an empty environment and the venv's
``site-packages`` appended without ``.pth`` processing, so an editable install is invisible to
them, as it is to a node. The launcher seam, ``executor_burla._launcher_argv``, is pointed at
``tests/bu_fixtures/launch.py``, which puts the fake first on the launcher's path and runs the
real ``_burla_submit.py`` as ``__main__``. Every interpreter the fake or a test starts arms a
network tripwire (a socket other than a Unix one raises); the pytest process never does.

**What the tests fix that the invariants leave open:**

- The ledger is JSON lines. An open line carries ``event="open"``, ``run_id``, ``start`` (Unix
  seconds), ``estimate``, ``nodes``, ``machine_type``, ``usd_per_node_hour``, ``price_asof``,
  ``stop_cost`` and ``max_cost``; a close line carries ``event="close"``, ``run_id``, ``end``,
  ``charge`` and ``ended``, one of ``complete``, ``stopped``, ``cancelled`` and ``error``.
- A Burla manifest's ``environment`` carries ``burla`` (at least ``nodes``, ``machine_type``,
  ``slots_per_node``, ``usd_per_node_hour``, ``price_asof``, ``estimate``, ``ledger_total``,
  ``stop_cost`` and ``max_cost``) and ``bundle`` (``sha256``, ``size`` and ``packages``, each
  package's ``version``, ``commit`` and ``dirty``).
- ``_build_bundle(packages) -> _Bundle`` with ``.data`` (the gzip'd tar) and ``.sha256``;
  ``_Ledger(path)`` with ``.total()`` and ``.unclosed()``; ``_BACKSTOP_S`` and ``_KILL_GRACE_S``.
- ``BurlaOptions`` refuses a bad value, and ``from_sweep_file`` a missing or unknown field, with
  ``ValueError``; a bundle version is ``importlib.metadata.version`` of the package's name or of
  the distribution that provides it, else ``None``; a bundle's ``commit`` and ``dirty`` are what
  ``git rev-parse HEAD`` and ``git status --porcelain -- .`` say in the package's folder, and
  ``None`` outside a checkout.
- The venv check reads the distributions ``importlib.metadata.distributions()`` finds.
- The backstop holds when the launcher never reads its input.

Timing-bound tests (M11 at 15 s, $4 at 5 s, S6 at 10 s, $5 at shortened intervals) wait real
time; the file takes a few minutes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.metadata
import importlib.util
import inspect
import io
import json
import math
import multiprocessing
import os
import shutil
import signal
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import time
import tomllib
import traceback
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

import poisson_prove
from poisson_prove import _burla_submit, cli, executor_burla, executor_modal
from poisson_prove.executor import ExecutorError, plan, run_local
from poisson_prove.executor_modal import ModalBackendError, ModalOptions, run_with_mapper
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store, StoreError
from isolated_support import isolated as run_isolated

eb = executor_burla
_ORIGINAL_ARGV = eb._launcher_argv
REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "bu_fixtures"
TARGETS = FIXTURES / "targets"
LAUNCH = FIXTURES / "launch.py"
DEAF = FIXTURES / "deaf_launcher.py"
WORKER = FIXTURES / "worker.py"
PACKAGE = Path(poisson_prove.__file__).resolve().parent
SUBMIT = Path(eb.__file__).resolve().with_name("_burla_submit.py")
SITE_PACKAGES = sysconfig.get_paths()["purelib"]
PIN = "1.8.2"
# PF9: Burla's install line names Prove's extra.
INSTALL_HINT = 'pip install "poisson-prove[burla]"'
HEAD = "http://localhost:5001"
SALT = "bu-oracle-salt"
PLAIN = "bu_targets.plain:rollout"
VIEW = "bu_targets.view:rollout"
PROBE = "bu_targets.probe:rollout"
HOSTONLY = "bu_targets.hostonly:rollout"
DRIFTING = "bu_targets.drifting:rollout"
USES_HELPER = "bu_targets.uses_helper:rollout"
WATCH = ["poisson_prove", "bu_targets", "bu_version", "bu_helper", "bu_dirty"]
CHAOS = {"fault": "llm_empty_single", "rate": 1.0, "steps": ["solve"]}
RECORD_KEYS = frozenset({"requested", "fault", "rate", "steps", "engine_version", "hooks"})
FAULTED_HOOKS = ["sync", "async"]
BURLA_ALL = [
    "BurlaBackendError", "BurlaCostGuard", "BurlaNotInstalled", "BurlaOptions",
    "BurlaSpendStop", "estimate_burla_cost", "preflight_burla", "run_burla",
]
# BurlaOptions' fields, in order: (name, default or REQUIRED).
REQUIRED = object()
OPTION_FIELDS = [
    ("nodes", REQUIRED), ("machine_type", REQUIRED), ("slots_per_node", REQUIRED),
    ("usd_per_node_hour", REQUIRED), ("price_asof", REQUIRED), ("ledger", REQUIRED),
    ("head_url", REQUIRED), ("stop_cost", REQUIRED), ("max_cost", REQUIRED),
    ("est_seconds_per_episode", REQUIRED), ("packages", ()), ("func_cpu", 1), ("func_ram", 4),
    ("boot_minutes", 5.0), ("idle_minutes", 5.0), ("batch_size", 256), ("episode_timeout", None),
    ("infra_retries", 2), ("max_rollouts", None),
]
MODAL_ENV_KEYS = frozenset({
    "python", "platform", "poisson_prove_version", "sweep", "image", "modal_app", "concurrency",
    "infra_retries", "import_path", "secrets", "max_mde_accepted",
})
SHARED_KEYS = ("python", "platform", "poisson_prove_version", "sweep", "infra_retries", "import_path",
               "max_mde_accepted")
MODAL_ONLY_KEYS = ("image", "modal_app", "concurrency", "secrets")
# The capture reason a Modal run records, byte for byte.
MODAL_CAPTURE_REASON = (
    "the host installs nothing for a Modal run; the container may not even "
    "hold the packages. Each batch records what happened at "
    "backend_meta['capture']"
)
# run_with_mapper's shared parameters, then the three the Burla backend adds.
RUNNER_PARAMS = [
    ("p", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty),
    ("mapper", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty),
    ("store", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty),
    ("options", "KEYWORD_ONLY", inspect.Parameter.empty),
    ("image", "KEYWORD_ONLY", None),
    ("on_progress", "KEYWORD_ONLY", None),
    ("backend", "KEYWORD_ONLY", "modal"),
    ("placement", "KEYWORD_ONLY", None),
    ("cost_check", "KEYWORD_ONLY", None),
]
BOOTSTRAP_PARAMS = ["k", "jobs", "import_path", "episode_timeout", "capture", "chaos"]
ARM_DEADLINE_S = 240.0
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()


# ---------- sweeps, plans and options ----------


def _toml(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml(v) for v in value) + "]"
    if isinstance(value, Path):
        return json.dumps(str(value))
    return json.dumps(value)


def write_sweep(
    root: Path,
    *,
    cells: Sequence[str] = ("a", "b"),
    replicates: int = 2,
    chaos: dict[str, Any] | None = None,
    capture: bool = False,
    burla: dict[str, Any] | None = None,
    name: str = "sweep.toml",
) -> Path:
    text = (
        'target_id = "bu-oracle@v0"\nt_unit = "steps"\n'
        f"replicates = {replicates}\n\n[axes.cell]\ntype = \"categorical\"\n"
        f"values = {_toml(list(cells))}\n"
    )
    if chaos is not None:
        text += (
            f'\n[chaos]\nfault = "{chaos["fault"]}"\nrate = {chaos["rate"]}\n'
            f"steps = {_toml(chaos['steps'])}\n"
        )
    if capture:
        text += '\n[capture]\ninstrument = []\nmax_observation_bytes = "none"\n'
    if burla is not None:
        text += "\n[burla]\n" + "".join(f"{key} = {_toml(value)}\n" for key, value in burla.items())
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(text, encoding="utf-8")
    return path


def burla_table(**over: Any) -> dict[str, Any]:
    table: dict[str, Any] = {
        "nodes": 1, "machine_type": "m7i.2xlarge", "slots_per_node": 2, "usd_per_node_hour": 0.403,
        "price_asof": "fixture price, 2026-09-27", "ledger": "ledgers/step.jsonl", "head_url": HEAD,
        "stop_cost": 5.0, "max_cost": 5.0, "est_seconds_per_episode": 0.01,
        "packages": ["bu_targets"], "batch_size": 2, "boot_minutes": 0.0, "idle_minutes": 0.0,
    }
    table.update(over)
    return table


def options(root: Path, **over: Any) -> eb.BurlaOptions:
    values: dict[str, Any] = {
        "nodes": 1, "machine_type": "m7i.2xlarge", "slots_per_node": 2, "usd_per_node_hour": 0.403,
        "price_asof": "fixture price, 2026-09-27", "ledger": root / "ledger.jsonl", "head_url": HEAD,
        "stop_cost": 5.0, "max_cost": 5.0, "est_seconds_per_episode": 0.01,
        "packages": ("bu_targets",), "batch_size": 2, "boot_minutes": 0.0, "idle_minutes": 0.0,
    }
    values.update(over)
    return eb.BurlaOptions(**values)


def make_plan(
    spec_path: Path, store: Store, target: str, *, backend: str = "burla", salt: str | None = SALT,
    resume: str | None = None,
) -> Any:
    spec = SweepSpec.load(spec_path)
    if resume is not None:
        return plan(spec, store, backend=backend, resume=resume, import_path=target)
    return plan(spec, store, backend=backend, run_salt=salt, import_path=target)


def stored(store: Store, run_id: str) -> list[dict[str, Any]]:
    try:
        frame = store.read(run_id)
    except StoreError:
        return []
    out = []
    for row in frame.itertuples():
        out.append({
            "config": dict(row.config), "config_hash": row.config_hash,
            "replicate_index": int(row.replicate_index), "seed": int(row.seed),
            "outcome": row.outcome if isinstance(row.outcome, str) else None,
            "t": None if row.t is None or (isinstance(row.t, float) and math.isnan(row.t)) else float(row.t),
            "meta": row.meta if isinstance(row.meta, dict) else {},
            "error": row.error if isinstance(row.error, str) else None,
            "backend_meta": row.backend_meta if isinstance(row.backend_meta, dict) else {},
        })
    return sorted(out, key=lambda r: (r["config_hash"], r["replicate_index"]))


def key_of(row: dict[str, Any]) -> tuple[str, int]:
    return (row["config"]["cell"], row["replicate_index"])


def status(store: Store, run_id: str) -> str | None:
    try:
        return store.manifest(run_id).status
    except StoreError:
        return None


def ledger_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def close_of(path: Path, run_id: str) -> dict[str, Any]:
    closes = [e for e in ledger_lines(path) if e.get("event") == "close" and e.get("run_id") == run_id]
    assert len(closes) == 1, ledger_lines(path)
    return closes[0]


def open_of(path: Path, run_id: str) -> dict[str, Any]:
    opens = [e for e in ledger_lines(path) if e.get("event") == "open" and e.get("run_id") == run_id]
    assert len(opens) == 1, ledger_lines(path)
    return opens[0]


def batches_of(p: Any, size: int) -> list[list[list[Any]]]:
    jobs = [
        [dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index]
        for i, pair in enumerate(p.pairs)
    ]
    return [jobs[k : k + size] for k in range(0, len(jobs), size)]


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_gone(pid: int, within: float) -> float | None:
    """Seconds until ``pid`` is gone, or None if it outlives ``within``."""
    t0 = time.time()
    while time.time() - t0 < within:
        if not alive(pid):
            return time.time() - t0
        time.sleep(0.05)
    return None


# ---------- the fake: its worker pool, its state folder, its records ----------


class Pool:
    """Fake Burla workers, each a long-lived ``python -I -S`` interpreter serving one call at a
    time on a Unix socket. Started and stopped by pid, by this harness only."""

    def __init__(self, n: int = 2) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="bu", dir="/tmp"))
        self.procs: list[subprocess.Popen[bytes]] = []
        self.workers: list[dict[str, Any]] = []
        for i in range(n):
            sock = str(self.dir / f"w{i}.sock")
            cwd = tempfile.mkdtemp(prefix="bu-worker-")
            proc = subprocess.Popen(
                [sys.executable, "-I", "-S", str(WORKER), sock, SITE_PACKAGES], env={}, cwd=cwd
            )
            self.procs.append(proc)
            self.workers.append({"socket": sock, "pid": proc.pid, "cwd": cwd})
        deadline = time.time() + 60
        for worker in self.workers:
            while not os.path.exists(worker["socket"] + ".ready"):
                assert time.time() < deadline, "a fake worker did not start"
                time.sleep(0.02)

    @property
    def pids(self) -> set[int]:
        return {proc.pid for proc in self.procs}

    def stop(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=30)
        shutil.rmtree(self.dir, ignore_errors=True)
        for worker in self.workers:
            shutil.rmtree(worker["cwd"], ignore_errors=True)


@pytest.fixture(scope="module")
def pool() -> Iterator[Pool]:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def fresh_pool() -> Iterator[Pool]:
    own = Pool(2)
    yield own
    own.stop()


class Fake:
    def __init__(self, state: Path, pool: Pool) -> None:
        self.state = state
        self.pool = pool
        state.mkdir(parents=True, exist_ok=True)
        (state / "workers.json").write_text(json.dumps(pool.workers), encoding="utf-8")
        self.script()

    def script(self, attempts: Sequence[dict[str, Any]] = (), default: dict[str, Any] | None = None,
               **top: Any) -> None:
        body = {"watch": WATCH, "attempts": list(attempts), "default": dict(default or {}), **top}
        (self.state / "script.json").write_text(json.dumps(body), encoding="utf-8")

    def use_pool(self, pool: Pool) -> None:
        self.pool = pool
        (self.state / "workers.json").write_text(json.dumps(pool.workers), encoding="utf-8")

    def watch_ledger(self, ledger: Path) -> None:
        (self.state / "ledger.path").write_text(str(ledger), encoding="utf-8")

    def argv(self, mode: str = "fake") -> list[str]:
        return [sys.executable, "-I", str(LAUNCH), str(self.state), mode, str(SUBMIT)]

    def _lines(self, name: str) -> list[dict[str, Any]]:
        path = self.state / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def starts(self) -> list[dict[str, Any]]:
        return [e for e in self._lines("calls.jsonl") if e["event"] == "start"]

    def ends(self) -> list[dict[str, Any]]:
        return [e for e in self._lines("calls.jsonl") if e["event"] == "end"]

    def heartbeats(self) -> list[dict[str, Any]]:
        return [e for e in self._lines("calls.jsonl") if e["event"] == "heartbeat"]

    def served(self) -> list[dict[str, Any]]:
        return self._lines("served.jsonl")

    def launchers(self) -> list[str]:
        path = self.state / "launchers.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


@pytest.fixture
def fake(tmp_path: Path, pool: Pool, monkeypatch: pytest.MonkeyPatch) -> Fake:
    monkeypatch.syspath_prepend(str(TARGETS))
    # PF9: a Burla sweep refuses a missing ``burla`` before the plan, as a Modal sweep
    # refuses a missing ``modal``. The fake client stays importable only in the launcher; here an
    # empty package of that name, at the pin, is findable, and nothing imports it.
    findable = tmp_path / "findable-burla"
    (findable / "burla").mkdir(parents=True)
    (findable / "burla" / "__init__.py").write_text("", encoding="utf-8")
    (findable / f"burla-{PIN}.dist-info").mkdir()
    (findable / f"burla-{PIN}.dist-info" / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: burla\nVersion: {PIN}\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(findable))
    made = Fake(tmp_path / "fake-state", pool)
    monkeypatch.setattr(eb, "_launcher_argv", made.argv)
    return made


def burla_run(fake: Fake, root: Path, target: str = PLAIN, *, sweep: dict[str, Any] | None = None,
              **over: Any) -> tuple[Any, Store, eb.BurlaOptions, Any]:
    """One ``run_burla`` in this process. Returns (plan, store, options, summary or exception)."""
    spec_path = write_sweep(root, **(sweep or {}))
    store = Store(root / "store")
    p = make_plan(spec_path, store, target)
    opts = options(root, **over)
    try:
        outcome: Any = eb.run_burla(p, target, store, options=opts)
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - the tests read it
        outcome = exc
    return p, store, opts, outcome


def assert_complete(outcome: Any, store: Store, p: Any) -> None:
    assert not isinstance(outcome, BaseException), "".join(
        traceback.format_exception(type(outcome), outcome, outcome.__traceback__)
    )
    assert outcome.complete, outcome
    rows = stored(store, p.run_id)
    assert len(rows) == len(p.pairs), rows
    assert len({(r["config_hash"], r["replicate_index"]) for r in rows}) == len(rows)
    assert status(store, p.run_id) == "complete"


# ---------- running an arm in its own interpreter (chaos arms once per process) ----------


def _arm_tripwire() -> None:
    import socket

    real = socket.socket.connect

    def connect(self: Any, address: Any) -> Any:
        if self.family != socket.AF_UNIX:
            raise RuntimeError("network tripwire: a network connection was attempted")
        return real(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]


def isolated(fn: Callable[..., Any], *args: Any) -> Any:
    """Run ``fn(*args)`` in a fresh spawned interpreter with the tripwire armed; return its result."""
    return run_isolated(fn, *args, timeout=ARM_DEADLINE_S, method="spawn", prepare=_arm_tripwire)


def child_local(root: str, target: str, chaos: dict[str, Any] | None, episode_timeout: float | None,
                capture: bool) -> dict[str, Any]:
    """``run_local`` on the sweep a Burla arm runs, in a fresh interpreter."""
    sys.path.insert(0, str(TARGETS))
    from poisson_prove._resolve import resolve

    spec_path = write_sweep(Path(root), chaos=chaos, capture=capture)
    store = Store(Path(root) / "store")
    p = make_plan(spec_path, store, target, backend="local")
    summary = run_local(p, resolve(target), store, episode_timeout=episode_timeout)
    return {"run_id": p.run_id, "complete": summary.complete}


def child_burla(root: str, argv: list[str], target: str, sweep: dict[str, Any],
                over: dict[str, Any], report: str) -> dict[str, Any]:
    """``run_burla`` in a fresh interpreter, which a test may interrupt or kill (M9, S6)."""
    sys.path.insert(0, str(TARGETS))
    eb._launcher_argv = lambda: list(argv)
    rootp = Path(root)
    spec_path = write_sweep(rootp, **sweep)
    store = Store(rootp / "store")
    p = make_plan(spec_path, store, target)
    Path(report).write_text(json.dumps({"run_id": p.run_id, "pid": os.getpid()}), encoding="utf-8")
    opts = options(rootp, **over)
    try:
        summary = eb.run_burla(p, target, store, options=opts)
        result = {"run_id": p.run_id, "complete": summary.complete}
    except KeyboardInterrupt:
        result = {"run_id": p.run_id, "raised": "KeyboardInterrupt"}
    except Exception as exc:  # noqa: BLE001
        result = {"run_id": p.run_id, "raised": type(exc).__name__, "message": str(exc)}
    Path(report).write_text(json.dumps(result), encoding="utf-8")
    return result


# ---------- R: hand-built results, no worker, nothing armed ----------


def ok_result(i: int, chaos_record: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"i": i}
    if chaos_record is not None:
        meta["chaos"] = dict(chaos_record)
    return {"outcome": "survived", "t": 1.0, "horizon": 1.0, "meta": {}, "wall_time": 0.0,
            "backend_meta": meta}


def chaos_record(spec_chaos: dict[str, Any]) -> dict[str, Any]:
    return {"requested": True, "fault": spec_chaos["fault"], "rate": float(spec_chaos["rate"]),
            "steps": list(spec_chaos["steps"]), "engine_version": "e", "hooks": FAULTED_HOOKS}


class RecordingMapper:
    """A mapper that hands back built results and notes when it is first called."""

    import_path = PLAIN

    def __init__(self, record: dict[str, Any] | None = None, events: list[str] | None = None) -> None:
        self.record = record
        self.events = events if events is not None else []
        self.calls = 0

    def __call__(self, batches: Sequence[Sequence[Any]]) -> Iterator[tuple[int, list[Any]]]:
        self.calls += 1
        self.events.append("mapper")
        for k, jobs in enumerate(batches):
            yield k, [ok_result(job[2], self.record) for job in jobs]


def r_plan(root: Path, *, chaos: dict[str, Any] | None = None, capture: bool = False) -> tuple[Any, Store]:
    spec_path = write_sweep(root, chaos=chaos, capture=capture)
    store = Store(root / "store")
    return make_plan(spec_path, store, PLAIN, backend="modal"), store


PLACEMENT = {"burla": {"nodes": 3, "machine_type": "m7i.2xlarge"}, "bundle": {"sha256": "ab" * 32},
             "cluster_note": "fixture"}


def test_r1_without_the_new_keywords_the_modal_manifest_and_cost_guard_are_mains(tmp_path: Path) -> None:
    """Without the Burla keywords, a Modal run through the shared runner keeps the Modal manifest
    keys and capture reason, and its cost guard refuses before the mapper is called."""
    p, store = r_plan(tmp_path / "plain", capture=True)
    run_with_mapper(p, RecordingMapper(), store, options=ModalOptions(batch_size=2))
    m = store.manifest(p.run_id)
    assert m.backend == "modal"
    # PF4.4: every backend records the design detection limit as design_mde
    # ({"mde", "base_rate"}) beside max_mde_accepted; every other key is a Modal run's.
    assert set(m.environment) == MODAL_ENV_KEYS | {"capture", "design_mde"}, sorted(m.environment)
    # PF4.30: design_mde also records which test, level and family the gate used and
    # whether a lone condition can be flagged, beside mde and base_rate.
    assert set(m.environment["design_mde"]) == {
        "mde", "base_rate", "direction", "test", "level", "family", "conditions", "events", "q", "power",
        "flaggable"}, m.environment["design_mde"]
    assert m.environment["capture"]["reason"] == MODAL_CAPTURE_REASON
    pc, cstore = r_plan(tmp_path / "chaos", chaos=CHAOS)
    run_with_mapper(pc, RecordingMapper(chaos_record(CHAOS)), cstore, options=ModalOptions(batch_size=2))
    # PF4.4: design_mde is recorded on a chaos run too.
    assert set(cstore.manifest(pc.run_id).environment) == MODAL_ENV_KEYS | {"chaos", "design_mde"}
    pg, gstore = r_plan(tmp_path / "guard")
    mapper = RecordingMapper()
    with pytest.raises(executor_modal.CostGuard):
        run_with_mapper(pg, mapper, gstore, options=ModalOptions(max_cost=1e-9, est_seconds_per_episode=60.0))
    assert mapper.calls == 0 and gstore.runs() == []


def test_r2_another_backends_manifest_carries_its_placement_and_the_shared_fields(tmp_path: Path) -> None:
    pm, mstore = r_plan(tmp_path / "modal", capture=True)
    run_with_mapper(pm, RecordingMapper(), mstore, options=ModalOptions(batch_size=2))
    pb, bstore = r_plan(tmp_path / "burla", capture=True)
    run_with_mapper(pb, RecordingMapper(), bstore, options=ModalOptions(batch_size=2),
                    backend="burla", placement=PLACEMENT, cost_check=lambda plan: None)
    modal_env = mstore.manifest(pm.run_id).environment
    burla = bstore.manifest(pb.run_id)
    assert burla.backend == "burla"
    env = burla.environment
    for key in MODAL_ONLY_KEYS:
        assert key not in env, key
    for key, value in PLACEMENT.items():
        assert env[key] == value, key
    for key in SHARED_KEYS:
        assert env[key] == modal_env[key], key
    shared_capture = {k: v for k, v in env["capture"].items() if k != "reason"}
    assert shared_capture == {k: v for k, v in modal_env["capture"].items() if k != "reason"}


def _refused_before_anything(tmp_path: Path, name: str, **kwargs: Any) -> None:
    p, store = r_plan(tmp_path / name)
    mapper = RecordingMapper()
    with pytest.raises(ModalBackendError):
        run_with_mapper(p, mapper, store, options=ModalOptions(batch_size=2), **kwargs)
    assert store.runs() == [] and mapper.calls == 0 and stored(store, p.run_id) == []


def _accepted(tmp_path: Path, name: str, **kwargs: Any) -> None:
    p, store = r_plan(tmp_path / name)
    summary = run_with_mapper(p, RecordingMapper(), store, options=ModalOptions(batch_size=2), **kwargs)
    assert summary.complete and store.manifest(p.run_id).backend == kwargs.get("backend", "modal")


def test_r3_another_backend_without_placement_or_cost_check_is_refused(tmp_path: Path) -> None:
    check = lambda plan: None  # noqa: E731
    _refused_before_anything(tmp_path, "no-placement", backend="burla", placement=None, cost_check=check)
    _refused_before_anything(tmp_path, "no-cost-check", backend="burla", placement=PLACEMENT, cost_check=None)
    _accepted(tmp_path, "both", backend="burla", placement=PLACEMENT, cost_check=check)


@pytest.mark.parametrize("field", ["python", "platform", "poisson_prove_version", "sweep", "infra_retries",
                                   "import_path", "max_mde_accepted", "capture", "chaos"])
def test_r3_a_placement_key_naming_a_shared_field_is_refused(tmp_path: Path, field: str) -> None:
    check = lambda plan: None  # noqa: E731
    _refused_before_anything(tmp_path, "clash", backend="burla", placement={**PLACEMENT, field: "x"},
                             cost_check=check)
    _accepted(tmp_path, "control", backend="burla", placement=PLACEMENT, cost_check=check)


class HookFailed(Exception):
    pass


def test_r4_the_cost_hook_runs_once_first_and_replaces_modals_check(tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    modal_checks: list[Any] = []
    monkeypatch.setattr(executor_modal, "_check_cost", lambda *a, **k: modal_checks.append(a))
    p, store = r_plan(tmp_path / "hook")
    events: list[str] = []
    seen: list[Any] = []

    def check(plan_: Any) -> None:
        seen.append(plan_)
        events.append("cost_check")
        assert store.runs() == [], "the manifest was written before the cost hook"

    run_with_mapper(p, RecordingMapper(events=events), store, options=ModalOptions(batch_size=2),
                    backend="burla", placement=PLACEMENT, cost_check=check)
    assert len(seen) == 1 and seen[0] is p
    assert events[0] == "cost_check" and events.count("cost_check") == 1
    assert modal_checks == []
    pf, fstore = r_plan(tmp_path / "raises")
    mapper = RecordingMapper()

    def refuse(plan_: Any) -> None:
        raise HookFailed("fixture")

    with pytest.raises(HookFailed):
        run_with_mapper(pf, mapper, fstore, options=ModalOptions(batch_size=2), backend="burla",
                        placement=PLACEMENT, cost_check=refuse)
    assert fstore.runs() == [] and mapper.calls == 0


def test_r5_a_burla_manifests_capture_reason_names_burla_and_its_workers(tmp_path: Path) -> None:
    p, store = r_plan(tmp_path / "burla", capture=True)
    run_with_mapper(p, RecordingMapper(), store, options=ModalOptions(batch_size=2), backend="burla",
                    placement=PLACEMENT, cost_check=lambda plan: None)
    reason = store.manifest(p.run_id).environment["capture"]["reason"]
    assert "Burla" in reason and "worker" in reason and "Modal" not in reason, reason


def test_r6_a_burla_chaos_run_whose_rows_lack_the_record_is_refused_before_storing(tmp_path: Path) -> None:
    p, store = r_plan(tmp_path / "bare", chaos=CHAOS)
    with pytest.raises(ModalBackendError):
        run_with_mapper(p, RecordingMapper(None), store, options=ModalOptions(batch_size=100),
                        backend="burla", placement=PLACEMENT, cost_check=lambda plan: None)
    assert stored(store, p.run_id) == [] and status(store, p.run_id) != "complete"
    pc, cstore = r_plan(tmp_path / "kept", chaos=CHAOS)
    summary = run_with_mapper(pc, RecordingMapper(chaos_record(CHAOS)), cstore,
                              options=ModalOptions(batch_size=100), backend="burla",
                              placement=PLACEMENT, cost_check=lambda plan: None)
    assert summary.complete


def test_r7_the_runners_surface_gains_three_keyword_only_parameters_and_nothing_else() -> None:
    params = [(n, p.kind.name, p.default) for n, p in inspect.signature(run_with_mapper).parameters.items()]
    assert params == RUNNER_PARAMS, params


# ---------- M: the host-side mapper, through the fake ----------


def test_m1_one_call_per_round_with_the_declared_shape(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path, nodes=3, slots_per_node=5, func_cpu=2, func_ram=3)
    assert_complete(outcome, store, p)
    (call,) = fake.starts()
    assert call["function"]["module"] == "__main__" and call["function"]["qualname"] == "_bootstrap"
    assert call["kwargs"] == {
        "func_cpu": 2, "func_ram": 3, "func_gpu": None, "image": None, "grow": False,
        "max_parallelism": 15, "detach": False, "generator": True, "raise_errors": False,
        "spinner": False, "region": None, "disk_gb": None,
    }


def test_m2_one_item_per_batch_carrying_six_fields_in_order(fake: Fake, tmp_path: Path) -> None:
    sweep = {"chaos": {"fault": "none", "rate": 1.0, "steps": []}, "capture": True, "replicates": 3}
    p, store, opts, outcome = burla_run(fake, tmp_path, PROBE, sweep=sweep, episode_timeout=45.0)
    assert_complete(outcome, store, p)
    (call,) = fake.starts()
    # What the sweep file declares, spelled out: ``[capture]`` with ``instrument = []`` and no
    # cap, and the ``[chaos]`` table above.
    want_capture = {"run_id": p.run_id, "instrument": [], "content": False, "max_observation_bytes": None,
                    "max_spans": None}
    want_chaos = {"fault": "none", "rate": 1.0, "steps": []}
    expected = [
        {"type": "tuple", "arity": 6, "k": k, "jobs": jobs, "import_path": PROBE,
         "episode_timeout": 45.0, "capture": want_capture, "chaos": want_chaos}
        for k, jobs in enumerate(batches_of(p, opts.batch_size))
    ]
    assert json.loads(json.dumps(call["items"])) == json.loads(json.dumps(expected))
    names = [n for n, prm in inspect.signature(_burla_submit._bootstrap).parameters.items()
             if prm.kind in (prm.POSITIONAL_ONLY, prm.POSITIONAL_OR_KEYWORD)]
    assert names == BOOTSTRAP_PARAMS


def local_rows(root: Path, target: str) -> list[dict[str, Any]]:
    spec_path = write_sweep(root, replicates=3)
    store = Store(root / "store")
    p = make_plan(spec_path, store, target, backend="local")
    from poisson_prove._resolve import resolve

    run_local(p, resolve(target), store)
    return stored(store, p.run_id)


def comparable(rows: Sequence[dict[str, Any]]) -> set[tuple[Any, ...]]:
    return {(r["config_hash"], r["replicate_index"], r["seed"], r["outcome"], r["t"],
             json.dumps(r["meta"], sort_keys=True)) for r in rows}


def test_m3_a_shuffled_burla_run_stores_what_run_local_stores(fake: Fake, tmp_path: Path) -> None:
    fake.script(default={"shuffle": 7})
    p, store, opts, outcome = burla_run(fake, tmp_path / "burla", sweep={"replicates": 3}, batch_size=1)
    assert_complete(outcome, store, p)
    assert fake.ends()[0]["yielded"] != sorted(fake.ends()[0]["yielded"]), "the fake did not shuffle"
    here = local_rows(tmp_path / "local", PLAIN)
    assert comparable(stored(store, p.run_id)) == comparable(here)


def test_m4_a_batch_returned_twice_is_stored_once_and_the_run_completes(fake: Fake, tmp_path: Path) -> None:
    fake.script(attempts=[{"duplicate": [0]}])
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3})
    assert_complete(outcome, store, p)
    assert len(fake.starts()) == 2, "the result the duplicate pushed out was not resubmitted"


def test_m5_a_missing_batch_is_resubmitted_in_a_new_call(fake: Fake, tmp_path: Path) -> None:
    fake.script(attempts=[{"withhold": [1]}])
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3})
    assert_complete(outcome, store, p)
    first, second = fake.starts()
    assert [item["jobs"] for item in second["items"]] == [batches_of(p, 2)[1]]


def test_m5_a_batch_never_returned_is_stored_as_infra_rows_after_the_retries(fake: Fake, tmp_path: Path) -> None:
    fake.script(attempts=[{"withhold": [1]}], default={"withhold": [0]})
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3}, infra_retries=2)
    assert not isinstance(outcome, BaseException), outcome
    missing = {tuple(job[3:5]) for job in batches_of(p, 2)[1]}
    rows = stored(store, p.run_id)
    assert len(rows) == len(p.pairs)
    for row in rows:
        infra = (row["config_hash"], row["replicate_index"]) in missing
        assert (row["error"] or "").startswith("infra: ") == infra, row
    assert len(fake.starts()) == 3  # the first call, then two retries of the missing batch


@pytest.mark.parametrize("with_index", [True, False], ids=["indexed", "unindexed"])
def test_m6_an_exception_value_is_attributed_and_retried_as_an_infra_failure(fake: Fake, tmp_path: Path,
                                                                             with_index: bool) -> None:
    fake.script(attempts=[{"exceptions": [{"index": 2, "with_index": with_index}]}])
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3})
    assert_complete(outcome, store, p)
    first, second = fake.starts()
    assert [item["jobs"] for item in second["items"]] == [batches_of(p, 2)[2]]


def test_m6_each_exception_is_charged_to_its_own_batch(fake: Fake, tmp_path: Path) -> None:
    """Two exception values arrive in the reverse of their batches' order; with no retry left,
    each batch's infra rows carry its own input's exception, not the other's."""
    fake.script(default={"order": [2, 1, 0], "exceptions": [{"index": 0, "with_index": True},
                                                            {"index": 2, "with_index": True}]})
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3}, infra_retries=0)
    assert not isinstance(outcome, BaseException), outcome
    batches = batches_of(p, 2)
    for k, other in ((0, 2), (2, 0)):
        keys = {tuple(job[3:5]) for job in batches[k]}
        for row in stored(store, p.run_id):
            if (row["config_hash"], row["replicate_index"]) in keys:
                error = row["error"] or ""
                assert error.startswith("infra: ") and f"input {k}" in error and f"input {other}" not in error, (k, error)


def test_m6_an_unindexed_exception_is_paired_with_the_batch_that_never_came_back(fake: Fake, tmp_path: Path) -> None:
    fake.script(default={"exceptions": [{"index": 2, "with_index": False}]})
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3}, infra_retries=0)
    assert not isinstance(outcome, BaseException), outcome
    keys = {tuple(job[3:5]) for job in batches_of(p, 2)[2]}
    for row in stored(store, p.run_id):
        paired = (row["config_hash"], row["replicate_index"]) in keys
        error = row["error"] or ""
        assert (error.startswith("infra: ") and "input 2" in error) == paired, row


@pytest.mark.parametrize("fault", ["disconnect_after", "heartbeat_fails_after"])
def test_m7_a_job_level_failure_keeps_what_arrived_and_resubmits_the_rest(fake: Fake, tmp_path: Path,
                                                                          fault: str) -> None:
    fake.script(attempts=[{fault: 1}])
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3})
    assert_complete(outcome, store, p)
    first_end = fake.ends()[0]
    delivered = set(first_end["yielded"])
    assert len(delivered) == 1 and first_end["type"] in ("NodeDisconnected", "Exception"), first_end
    second = fake.starts()[1]
    batches = batches_of(p, 2)
    assert [item["jobs"] for item in second["items"]] == [b for k, b in enumerate(batches) if k not in delivered]


REFUSALS = ["JobStalled", "NodesFailedToBoot", "NoNodes", "NoCompatibleNodes", "UnsupportedLocalImport",
            "FunctionTooBig", "Unnamed"]
ENDINGS = ["ClusterShutdown", "ClusterRestarted", "JobCanceled"]


def _first_line(message: str) -> str:
    return next(line.strip() for line in message.splitlines() if line.strip())


@pytest.mark.parametrize("name", REFUSALS + ENDINGS)
def test_m8_a_refusal_or_an_ending_is_not_retried(fake: Fake, tmp_path: Path, name: str) -> None:
    fake.script(default={"refuse": name})
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert isinstance(outcome, eb.BurlaBackendError), outcome
    assert not isinstance(outcome, (eb.BurlaSpendStop, eb.BurlaCostGuard, eb.BurlaNotInstalled)), outcome
    assert len(fake.starts()) == 1, "a refusal was retried"
    (end,) = fake.ends()
    assert _first_line(end["message"]) in str(outcome), (end["message"], str(outcome))
    ended = close_of(opts.ledger, p.run_id)["ended"]
    assert ended == ("cancelled" if name in ENDINGS else "error"), ended
    assert status(store, p.run_id) != "complete"


def test_m8_delivered_batches_stay_stored_when_a_refusal_ends_the_call(fake: Fake, tmp_path: Path) -> None:
    fake.script(default={"refuse": "JobStalled", "refuse_after": 1})
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3})
    assert isinstance(outcome, eb.BurlaBackendError), outcome
    assert len(fake.starts()) == 1
    (delivered,) = fake.ends()[0]["yielded"]
    rows = stored(store, p.run_id)
    assert {(r["config_hash"], r["replicate_index"]) for r in rows} == {
        tuple(job[3:5]) for job in batches_of(p, 2)[delivered]
    }


def _report(path: Path, within: float, key: str) -> dict[str, Any]:
    t0 = time.time()
    while time.time() - t0 < within:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
            if key in data:
                return data
        time.sleep(0.05)
    raise AssertionError(f"no {key!r} in {path} within {within}s")


def _start_child(fake: Fake, root: Path, target: str, sweep: dict[str, Any], over: dict[str, Any]) -> tuple[Any, Path]:
    ctx = multiprocessing.get_context("spawn")
    report = root / "child-report.json"
    root.mkdir(parents=True, exist_ok=True)
    proc = ctx.Process(target=child_burla, args=(str(root), fake.argv(), target, sweep, over, str(report)))
    proc.start()
    return proc, report


def _wait_stored(store_root: Path, run_id: str, n: int, within: float) -> None:
    t0 = time.time()
    while time.time() - t0 < within:
        try:
            if Store(store_root).count(run_id) >= n:
                return
        except (StoreError, OSError):
            pass
        time.sleep(0.05)
    raise AssertionError(f"{n} rows of {run_id} were not stored within {within}s")


def test_m9_ctrl_c_cancels_the_job_closes_the_ledger_and_reaches_the_caller(fake: Fake, tmp_path: Path) -> None:
    fake.script(attempts=[{"hang_after": 1}])
    root = tmp_path / "interrupted"
    proc, report = _start_child(fake, root, PLAIN, {"replicates": 3}, {})
    try:
        run_id = _report(report, 120, "run_id")["run_id"]
        _wait_stored(root / "store", run_id, 2, 120)
        os.kill(proc.pid, signal.SIGINT)
        result = _report(report, 60, "raised")
    finally:
        proc.join(60)
        if proc.is_alive():
            proc.kill()
            proc.join()
    assert result["raised"] == "KeyboardInterrupt", result
    (end,) = fake.ends()
    assert end["how"] == "cancelled" and [s for s, _ in end["signals"]] == [int(signal.SIGINT)], end
    closed = close_of(root / "ledger.jsonl", run_id)
    assert closed["ended"] == "cancelled" and closed["charge"] >= 0
    store = Store(root / "store")
    assert status(store, run_id) != "complete" and 0 < len(stored(store, run_id)) < 6
    p = make_plan(root / "sweep.toml", store, PLAIN, resume=run_id)
    summary = eb.run_burla(p, PLAIN, store, options=options(root))
    assert summary.complete and len(stored(store, run_id)) == 6


ALTERED = [{"fault": "llm_error_single"}, {"rate": 0.5}, {"steps": ["other"]}, {"hooks": []}]


@pytest.mark.parametrize("alter", ALTERED, ids=["fault", "rate", "steps", "hooks"])
def test_m10_a_record_that_disagrees_with_the_request_is_refused_before_storing(fake: Fake, tmp_path: Path,
                                                                                alter: dict[str, Any]) -> None:
    fake.script(default={"alter_record": alter})
    p, store, opts, outcome = burla_run(fake, tmp_path, PROBE, sweep={"chaos": CHAOS}, batch_size=4)
    assert isinstance(outcome, eb.BurlaBackendError), outcome
    assert p.run_id in str(outcome)
    assert stored(store, p.run_id) == []


def test_m10_control_an_agreeing_record_is_stored(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path, PROBE, sweep={"chaos": CHAOS}, batch_size=4)
    assert_complete(outcome, store, p)


def test_m11_busy_nodes_are_asked_again_every_15_s(fake: Fake, tmp_path: Path) -> None:
    fake.script(attempts=[{"busy": True}])
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert_complete(outcome, store, p)
    first, second = fake.starts()
    gap = second["time"] - first["time"]
    assert 14.5 <= gap <= 30.0, gap


def test_m11_busy_past_the_deadline_fires_the_stop(fake: Fake, tmp_path: Path) -> None:
    fake.script(default={"busy": True})
    p, store, opts, outcome = burla_run(fake, tmp_path, usd_per_node_hour=360.0, stop_cost=0.3, max_cost=1.0)
    assert isinstance(outcome, eb.BurlaSpendStop), outcome
    closed = close_of(opts.ledger, p.run_id)
    start = open_of(opts.ledger, p.run_id)["start"]
    assert closed["ended"] == "stopped" and closed["end"] - start <= 3.0 + 5.0 + 2.0, closed


# ---------- S: the launcher ----------


def test_s1_the_launcher_runs_in_its_own_session(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert_complete(outcome, store, p)
    assert fake.starts()[0]["session_leader"] is True


def test_s1_the_launcher_seam_starts_this_file_under_python_i() -> None:
    assert _ORIGINAL_ARGV() == [sys.executable, "-I", str(SUBMIT)]


def test_s1_importing_the_launcher_imports_only_the_standard_library_and_runs_nothing() -> None:
    """The launcher file on its own, in a ``python -I`` interpreter as the backend starts it, loaded
    by path under a name other than ``__main__``: every module it brings in must come from the
    standard library. Loading it through ``import poisson_prove…`` would hide whatever the package's
    own ``__init__`` already imports (numpy, for one)."""
    probe = (
        "import json, os, runpy, sys, sysconfig\n"
        "before = set(sys.modules)\n"
        "runpy.run_path(sys.argv[1], run_name='bu_launcher_probe')\n"
        # The base interpreter's stdlib folder, never a venv's lib folder: that one holds site-packages.
        "std = os.path.realpath(sysconfig.get_path('stdlib')) + os.sep\n"
        "site = tuple(os.path.realpath(sysconfig.get_path(k)) + os.sep for k in ('purelib', 'platlib'))\n"
        "new = []\n"
        "for name in sorted(set(sys.modules) - before):\n"
        "    origin = getattr(getattr(sys.modules[name], '__spec__', None), 'origin', None)\n"
        "    if origin in (None, 'built-in', 'frozen'):\n"
        "        continue\n"
        "    real = os.path.realpath(origin)\n"
        "    if real.startswith(std) and not real.startswith(site):\n"
        "        continue\n"
        "    new.append([name, origin])\n"
        "print(json.dumps(new))\n"
    )
    done = subprocess.run([sys.executable, "-I", "-c", probe, str(SUBMIT)], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip().splitlines()[-1]) == []
    assert done.stderr == "" and len(done.stdout.strip().splitlines()) == 1, (done.stdout, done.stderr)


def test_s2_nothing_of_ours_is_imported_or_shipped_when_burla_is_called(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path, packages=("bu_targets", "bu_helper"))
    assert_complete(outcome, store, p)
    (call,) = fake.starts()
    assert call["watched_modules"] == [], call["watched_modules"]
    assert call["shipped"] == [], call["shipped"]


def test_s3_the_bootstrap_passes_burlas_rule(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert_complete(outcome, store, p)
    assert fake.starts()[0]["offenders"] == []


def test_s4_burla_is_called_on_the_launchers_main_thread(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert_complete(outcome, store, p)
    assert fake.starts()[0]["main_thread"] is True


def test_s5_telemetry_off_head_pinned_and_output_in_a_log_beside_the_ledger(fake: Fake, tmp_path: Path,
                                                                           capfd: pytest.CaptureFixture[str]) -> None:
    junk = '("done", "stopped") {"event": "close", "charge": 99.0} \\x00\\x08'
    fake.script(default={"print": junk})
    ledger = tmp_path / "ledgers" / "step.jsonl"
    p, store, opts, outcome = burla_run(fake, tmp_path, ledger=ledger, head_url="https://head.fixture.invalid")
    assert_complete(outcome, store, p)
    (call,) = fake.starts()
    assert call["env"] == {"DISABLE_BURLA_TELEMETRY": "True", "BURLA_CLUSTER_DASHBOARD_URL": "https://head.fixture.invalid"}
    token = call["token"]
    beside = [f for f in ledger.parent.iterdir() if f != ledger and f.is_file()]
    logged = [f for f in beside if f"fake burla stdout {token}" in f.read_text(encoding="utf-8", errors="replace")
              and f"fake burla stderr {token}" in f.read_text(encoding="utf-8", errors="replace")]
    assert logged, [f.name for f in beside]
    out, err = capfd.readouterr()
    assert token not in out and token not in err
    assert [e["event"] for e in ledger_lines(ledger)] == ["open", "close"]


def test_s6_when_the_parent_dies_the_launcher_cancels_and_exits_within_10_s(fake: Fake, tmp_path: Path) -> None:
    fake.script(attempts=[{"hang_after": 1}])
    root = tmp_path / "orphaned"
    proc, report = _start_child(fake, root, PLAIN, {"replicates": 3}, {})
    try:
        run_id = _report(report, 120, "run_id")["run_id"]
        _wait_stored(root / "store", run_id, 2, 120)
        (call,) = fake.starts()
        launcher = call["launcher_pid"]
        os.kill(proc.pid, signal.SIGKILL)
        proc.join(30)
        gone = wait_gone(launcher, 15.0)
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join()
        for start in fake.starts():  # a launcher this test left running dies with its group
            if alive(start["launcher_pid"]):
                os.killpg(start["launcher_pid"], signal.SIGKILL)
    assert gone is not None and gone <= 10.0, gone
    (end,) = fake.ends()
    assert end["how"] == "cancelled" and end["signals"], end
    assert not alive(fake.heartbeats()[0]["pid"])


def test_s7_a_client_other_than_1_8_2_is_refused_naming_the_pin(fake: Fake, tmp_path: Path) -> None:
    fake.script(version="1.8.1")
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert isinstance(outcome, eb.BurlaBackendError) and not isinstance(outcome, eb.BurlaNotInstalled), outcome
    assert PIN in str(outcome) and "1.8.1" in str(outcome)
    assert fake.starts() == [], "remote_parallel_map was called"


def test_s7_without_burla_importable_run_burla_raises_burla_not_installed(fake: Fake, tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eb, "_launcher_argv", lambda: fake.argv("absent"))
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert isinstance(outcome, eb.BurlaNotInstalled), outcome
    # The message says what failed, with no raw repr of the import error, and the install line is
    # its own next line, not inside the sentence.
    assert outcome.nexts == [INSTALL_HINT] and INSTALL_HINT not in str(outcome), (outcome.nexts, str(outcome))
    assert "burla" in str(outcome) and "Error(" not in str(outcome), str(outcome)
    assert fake.starts() == []



# ---------- W: the bundle and the worker ----------


def _source_files(folder: Path) -> dict[str, bytes]:
    out = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith((".pyc", ".pyo")):
                continue
            path = Path(root) / file
            out[str(Path(folder.name) / path.relative_to(folder))] = path.read_bytes()
    return out


def _expected_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        pass
    for dist in importlib.metadata.packages_distributions().get(name, []):
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def _git(folder: Path, *args: str) -> str | None:
    done = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def _expected_package(name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(name)
    assert spec is not None and spec.submodule_search_locations
    folder = Path(next(iter(spec.submodule_search_locations)))
    commit = _git(folder, "rev-parse", "HEAD")
    porcelain = _git(folder, "status", "--porcelain", "--", ".") if commit else None
    return {"version": _expected_version(name), "commit": commit,
            "dirty": None if porcelain is None else bool(porcelain)}


def test_w1_the_bundle_is_deterministic_and_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy = tmp_path / "pkgs" / "bu_w1pkg"
    shutil.copytree(TARGETS / "bu_targets", copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "tool.sh").write_text("#!/bin/sh\necho fixture\n", encoding="utf-8")
    (copy / "tool.sh").chmod(0o755)
    monkeypatch.syspath_prepend(str(copy.parent))
    importlib.import_module("bu_w1pkg.plain")
    assert (copy / "__pycache__").is_dir(), "the fixture has no cache folder to leave out"
    first = eb._build_bundle(("bu_w1pkg",))
    os.utime(copy / "plain.py", (1, 1))  # a new mtime, the same tree
    second = eb._build_bundle(("bu_w1pkg",))
    assert first.data == second.data and first.sha256 == second.sha256 == hashlib.sha256(first.data).hexdigest()
    assert first.data[:2] == b"\x1f\x8b" and first.data[4:8] == b"\x00\x00\x00\x00", "gzip mtime is not zero"
    with tarfile.open(fileobj=io.BytesIO(first.data), mode="r:gz") as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        assert names == sorted(names)
        files = {}
        for m in members:
            assert m.mtime == 0 and m.uid == 0 and m.gid == 0 and m.uname == "" and m.gname == "", m.name
            assert "__pycache__" not in Path(m.name).parts and not m.name.endswith((".pyc", ".pyo")), m.name
            if m.isdir():
                assert m.mode == 0o755, (m.name, oct(m.mode))
            else:
                assert m.isfile(), m.name
                assert m.mode == (0o755 if m.name.endswith("tool.sh") else 0o644), (m.name, oct(m.mode))
                files[m.name] = tar.extractfile(m).read()  # type: ignore[union-attr]
    want = {**_source_files(PACKAGE), **_source_files(copy)}
    assert files == want, sorted(set(files) ^ set(want))


def test_w1_the_manifest_records_the_bundle_prove_s_version_and_each_package_s_version_commit_and_dirty_flag(
    fake: Fake, tmp_path: Path
) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert_complete(outcome, store, p)
    record = store.manifest(p.run_id).environment["bundle"]
    rebuilt = eb._build_bundle(("bu_targets",))
    assert record["sha256"] == rebuilt.sha256 and record["size"] == len(rebuilt.data)
    assert record["packages"] == {"poisson_prove": {"version": _expected_version("poisson_prove")},
                                  "bu_targets": _expected_package("bu_targets")}


def _outside_repo(path: str) -> bool:
    """Not the project, its source or its tests. The venv's ``site-packages`` may sit under the
    checkout; it stands for the distributions a node installs, and is allowed."""
    real = os.path.realpath(path)
    project = str(REPO.resolve())
    if real == project:
        return False
    return not any((real + os.sep).startswith(str((REPO / part).resolve()) + os.sep) for part in ("src", "tests"))


def _empty_environment() -> set[str]:
    """What an interpreter started with an empty environment finds in it anyway: what the
    platform and Python's own locale coercion put there, which no host passed on."""
    done = subprocess.run([sys.executable, "-I", "-S", "-c", "import os, json; print(json.dumps(sorted(os.environ)))"],
                          env={}, capture_output=True, text=True, timeout=60)
    return set(json.loads(done.stdout))


def test_w2_a_worker_is_an_isolated_interpreter_that_reads_package_data_from_the_bundle(
    fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BU_HOST_MARKER", "only-on-the-host")
    baseline = _empty_environment()
    assert "BU_HOST_MARKER" not in baseline
    p, store, opts, outcome = burla_run(fake, tmp_path, VIEW)
    assert_complete(outcome, store, p)
    table = json.loads((TARGETS / "bu_targets" / "data" / "table.json").read_text(encoding="utf-8"))
    workers = fake.pool.pids
    for row in stored(store, p.run_id):
        meta = row["meta"]
        assert meta["pid"] in workers, meta["pid"]
        assert meta["isolated"] == 1 and meta["no_site"] == 1, meta
        assert set(meta["environ"]) <= baseline, sorted(set(meta["environ"]) - baseline)
        assert meta["table"] == table["value"]
        assert _outside_repo(meta["file"]) and _outside_repo(meta["cwd"]), meta
        assert not any(".pth" in entry for entry in meta["path"])


def test_w3_the_bundle_travels_inside_the_pickled_function_not_as_an_input(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path, VIEW)
    assert_complete(outcome, store, p)
    size = store.manifest(p.run_id).environment["bundle"]["size"]
    (beat,) = fake.heartbeats()
    assert beat["fn_bytes"] >= size, (beat["fn_bytes"], size)
    (call,) = fake.starts()
    for item in call["items"]:
        assert set(item) == {"type", "arity", "k", "jobs", "import_path", "episode_timeout", "capture", "chaos"}
    for row in stored(store, p.run_id):
        assert all(_outside_repo(entry) for entry in row["meta"]["path"] if entry), row["meta"]["path"]


def test_w4_a_warm_worker_unloads_the_last_bundle_before_loading_a_new_one(
    fake: Fake, fresh_pool: Pool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake.use_pool(fresh_pool)
    copy = tmp_path / "pkgs"
    shutil.copytree(TARGETS / "bu_version", copy / "bu_version")
    monkeypatch.syspath_prepend(str(copy))
    sweep = {"replicates": 3}
    p1, store1, _, out1 = burla_run(fake, tmp_path / "one", "bu_version:rollout", sweep=sweep, packages=("bu_version",))
    assert_complete(out1, store1, p1)
    init = copy / "bu_version" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace('VERSION = "one"', 'VERSION = "two"'), encoding="utf-8")
    importlib.invalidate_caches()
    p2, store2, _, out2 = burla_run(fake, tmp_path / "two", "bu_version:rollout", sweep=sweep, packages=("bu_version",))
    assert_complete(out2, store2, p2)
    assert {r["meta"]["version"] for r in stored(store1, p1.run_id)} == {"one"}
    assert {r["meta"]["version"] for r in stored(store2, p2.run_id)} == {"two"}
    served = fake.served()
    first = {s["worker"] for s in served if s["call"] == 0}
    second = {s["worker"] for s in served if s["call"] == 1}
    assert second and second <= first, (first, second)
    assert store1.manifest(p1.run_id).environment["bundle"]["sha256"] != store2.manifest(p2.run_id).environment["bundle"]["sha256"]


def _pid_by_batch(fake: Fake, call: int) -> dict[int, int]:
    return {s["index"]: s["worker"] for s in fake.served() if s["call"] == call}


@pytest.mark.parametrize("table", ["chaos", "capture", "neither"])
def test_w5_chaos_and_capture_batches_run_in_their_own_interpreter(fake: Fake, fresh_pool: Pool,
                                                                   tmp_path: Path, table: str) -> None:
    fake.use_pool(fresh_pool)
    sweep: dict[str, Any] = {"replicates": 2}
    if table == "chaos":
        sweep["chaos"] = {"fault": "none", "rate": 1.0, "steps": []}
    if table == "capture":
        sweep["capture"] = True
    p, store, opts, outcome = burla_run(fake, tmp_path, PROBE, sweep=sweep)
    assert_complete(outcome, store, p)
    workers = _pid_by_batch(fake, 0)
    pids_by_batch: dict[int, set[int]] = {}
    for row in stored(store, p.run_id):
        k = row["backend_meta"]["i"] // opts.batch_size
        pids_by_batch.setdefault(k, set()).add(row["meta"]["pid"])
    for k, pids in pids_by_batch.items():
        assert len(pids) == 1, pids
        (pid,) = pids
        if table == "neither":
            assert pid == workers[k], (pid, workers)
        else:
            assert pid not in fresh_pool.pids, (pid, workers)
    if table != "neither":
        batch_pids = [next(iter(v)) for v in pids_by_batch.values()]
        assert len(set(batch_pids)) == len(batch_pids), "two batches shared one interpreter"


def test_w6_a_target_that_does_not_import_in_the_worker_is_stored_as_infra_rows(
    fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BU_HOST_ONLY", "1")
    p, store, opts, outcome = burla_run(fake, tmp_path, HOSTONLY, infra_retries=1)
    assert not isinstance(outcome, BaseException), outcome
    rows = stored(store, p.run_id)
    assert len(rows) == len(p.pairs) and all((r["error"] or "").startswith("infra: ") for r in rows), rows
    assert len(fake.starts()) == 2
    assert {s["kind"] for s in fake.served()} == {"ok"}, "the bootstrap raised instead of returning (k, None, traceback)"


# ---------- C: chaos and capture on Burla ----------


def _chaos_rows(store: Store, run_id: str) -> dict[tuple[str, int], tuple[Any, ...]]:
    return {key_of(r): (r["meta"].get("chaos_block"), r["outcome"], r["meta"].get("content"))
            for r in stored(store, run_id)}


@pytest.fixture(scope="module")
def local_chaos(tmp_path_factory: pytest.TempPathFactory) -> Callable[[float | None], dict[tuple[str, int], tuple[Any, ...]]]:
    cache: dict[float | None, dict[tuple[str, int], tuple[Any, ...]]] = {}

    def get(episode_timeout: float | None) -> dict[tuple[str, int], tuple[Any, ...]]:
        if episode_timeout not in cache:
            root = tmp_path_factory.mktemp("local-chaos")
            report = isolated(child_local, str(root), PROBE, CHAOS, episode_timeout, False)
            assert report["complete"]
            cache[episode_timeout] = _chaos_rows(Store(root / "store"), report["run_id"])
        return cache[episode_timeout]

    return get


TIMEOUTS = pytest.mark.parametrize(
    "episode_timeout",
    [None, pytest.param(30.0, marks=pytest.mark.skipif(not FORK_AVAILABLE, reason="needs fork"))],
    ids=["inproc", "fork"],
)


@TIMEOUTS
def test_c1_a_chaos_sweep_on_burla_arms_its_fault_exactly_as_local_does(fake: Fake, tmp_path: Path,
                                                                        local_chaos: Any, episode_timeout: float | None) -> None:
    local = local_chaos(episode_timeout)
    assert len(local) == 4 and all(v[0] == CHAOS and v[1] == "fell" for v in local.values()), local
    p, store, opts, outcome = burla_run(fake, tmp_path, PROBE, sweep={"chaos": CHAOS}, episode_timeout=episode_timeout)
    assert_complete(outcome, store, p)
    assert _chaos_rows(store, p.run_id) == local


def test_c2_every_ok_row_carries_the_record_its_worker_armed(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path, PROBE, sweep={"chaos": CHAOS})
    assert_complete(outcome, store, p)
    requested = store.manifest(p.run_id).environment["chaos"]
    for row in stored(store, p.run_id):
        record = row["backend_meta"]["chaos"]
        assert set(record) == RECORD_KEYS and record["hooks"] == FAULTED_HOOKS, record
        for key in ("fault", "rate", "steps", "engine_version"):
            assert record[key] == requested[key], (key, record, requested)


def test_c3_a_worker_that_served_another_chaos_run_first_still_matches_local(
    fake: Fake, fresh_pool: Pool, tmp_path: Path, local_chaos: Any
) -> None:
    fake.use_pool(fresh_pool)
    other = {"fault": "llm_error_single", "rate": 1.0, "steps": ["solve"]}
    control = {"fault": "none", "rate": 1.0, "steps": []}
    for name, table in (("other", other), ("none", control)):
        p, store, opts, outcome = burla_run(fake, tmp_path / name, PROBE, sweep={"chaos": table})
        assert_complete(outcome, store, p)
    p, store, opts, outcome = burla_run(fake, tmp_path / "this", PROBE, sweep={"chaos": CHAOS})
    assert_complete(outcome, store, p)
    assert _chaos_rows(store, p.run_id) == local_chaos(None)
    served = fake.served()
    earlier = {s["worker"] for s in served if s["call"] in (0, 1)}
    assert {s["worker"] for s in served if s["call"] == 2} <= earlier


@pytest.mark.parametrize("strip", ["strip_chaos_field", "strip_chaos_record"])
def test_c4_a_dropped_chaos_table_or_record_is_refused_before_storing(fake: Fake, tmp_path: Path, strip: str) -> None:
    fake.script(default={strip: True})
    p, store, opts, outcome = burla_run(fake, tmp_path / strip, PROBE, sweep={"chaos": CHAOS}, batch_size=4)
    assert isinstance(outcome, ExecutorError), outcome
    assert stored(store, p.run_id) == [] and status(store, p.run_id) != "complete"
    fake.script()
    pc, cstore, _, control = burla_run(fake, tmp_path / "control", PROBE, sweep={"chaos": CHAOS}, batch_size=4)
    assert_complete(control, cstore, pc)


def test_c5_a_capture_sweeps_rows_carry_what_the_worker_saw(fake: Fake, tmp_path: Path) -> None:
    p, store, opts, outcome = burla_run(fake, tmp_path, PLAIN, sweep={"capture": True})
    assert_complete(outcome, store, p)
    capture = store.manifest(p.run_id).environment["capture"]
    assert capture["requested"] is True
    assert "Burla" in capture["reason"] and "worker" in capture["reason"] and "Modal" not in capture["reason"]
    for row in stored(store, p.run_id):
        seen = row["backend_meta"]["capture"]
        assert seen["requested"] is True and seen["active"] is True, seen


# ---------- $: cost, caps and the ledger ----------


def _table_file(root: Path, table: dict[str, Any]) -> Path:
    return write_sweep(root, burla=table)


def test_dollar1_the_options_declare_their_fields_and_hard_wire_grow_and_parallelism() -> None:
    got = [(f.name, REQUIRED if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            else (f.default if f.default is not dataclasses.MISSING else f.default_factory()))
           for f in dataclasses.fields(eb.BurlaOptions)]
    assert got == OPTION_FIELDS, got


REQUIRED_FIELDS = [name for name, default in OPTION_FIELDS if default is REQUIRED]
BAD_VALUES = [("nodes", 0), ("machine_type", ""), ("slots_per_node", 0), ("usd_per_node_hour", 0.0),
              ("price_asof", ""), ("head_url", "http://example.com:5001"), ("head_url", "ftp://localhost"),
              ("stop_cost", 0.0), ("max_cost", 1.0), ("est_seconds_per_episode", 0.0)]


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_dollar1_a_missing_declaration_is_refused_by_name(tmp_path: Path, field: str) -> None:
    table = burla_table(stop_cost=2.0, max_cost=3.0)
    del table[field]
    with pytest.raises(ValueError) as refused:
        eb.BurlaOptions.from_sweep_file(_table_file(tmp_path / "missing", table))
    assert field in str(refused.value)
    eb.BurlaOptions.from_sweep_file(_table_file(tmp_path / "control", burla_table(stop_cost=2.0, max_cost=3.0)))


@pytest.mark.parametrize("field,value", BAD_VALUES, ids=[f"{f}={v!r}" for f, v in BAD_VALUES])
def test_dollar1_a_bad_declaration_is_refused(tmp_path: Path, field: str, value: Any) -> None:
    good = options(tmp_path, stop_cost=2.0, max_cost=3.0)
    with pytest.raises(ValueError):
        dataclasses.replace(good, **{field: value})
    for ok in ("http://localhost:5001", "http://127.0.0.1:5001", "https://head.fixture.invalid"):
        dataclasses.replace(good, head_url=ok)


def test_dollar1_an_unknown_field_is_refused_by_name_and_a_relative_ledger_is_the_sweeps(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as refused:
        eb.BurlaOptions.from_sweep_file(_table_file(tmp_path / "unknown", burla_table(nodez=4)))
    assert "nodez" in str(refused.value)
    loaded = eb.BurlaOptions.from_sweep_file(_table_file(tmp_path / "known", burla_table()))
    assert loaded.ledger == tmp_path / "known" / "ledgers" / "step.jsonl"
    assert loaded.packages == ("bu_targets",)


def _formula(pairs: int, o: eb.BurlaOptions) -> float:
    batches = math.ceil(pairs / o.batch_size)
    waves = math.ceil(batches / (o.nodes * o.slots_per_node))
    minutes = o.boot_minutes + waves * o.batch_size * o.est_seconds_per_episode / 60 + o.idle_minutes
    return o.nodes * o.usd_per_node_hour * minutes / 60


@pytest.mark.parametrize("case", [
    {"cells": 40, "replicates": 1024, "over": {"nodes": 4, "slots_per_node": 8, "usd_per_node_hour": 0.403,
                                               "boot_minutes": 5.0, "idle_minutes": 5.0, "batch_size": 256,
                                               "est_seconds_per_episode": 0.05}},
    {"cells": 7, "replicates": 33, "over": {"nodes": 3, "slots_per_node": 5, "usd_per_node_hour": 1.37,
                                            "boot_minutes": 2.5, "idle_minutes": 4.0, "batch_size": 10,
                                            "est_seconds_per_episode": 1.9}},
], ids=["demo", "odd"])
def test_dollar2_the_estimate_is_the_formula_to_the_cent(tmp_path: Path, case: dict[str, Any]) -> None:
    spec_path = write_sweep(tmp_path, cells=[f"c{i:02d}" for i in range(case["cells"])], replicates=case["replicates"])
    p = make_plan(spec_path, Store(tmp_path / "store"), PLAIN)
    o = options(tmp_path, stop_cost=50.0, max_cost=50.0, **case["over"])
    got = eb.estimate_burla_cost(p, o)
    want = _formula(len(p.pairs), o)
    assert abs(got - want) < 0.005, (got, want)
    if case["cells"] == 40:
        assert round(got, 2) == 0.30


def _seed_ledger(path: Path, lines: Sequence[dict[str, Any]]) -> bytes:
    """Earlier lines in a spelling no serializer would produce (keys out of order, odd spacing),
    so any rewrite of the file, however faithful to the values, changes its bytes ($6)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    spelled = [json.dumps(dict(reversed(list(line.items()))), separators=(",  ", ":   ")) + "\n" for line in lines]
    body = "".join(spelled).encode()
    path.write_bytes(body)
    return body


PRIOR = [
    {"event": "open", "run_id": "prior-run", "start": 1.0, "estimate": 0.1, "nodes": 1, "machine_type": "m7i.2xlarge",
     "usd_per_node_hour": 0.403, "price_asof": "fixture", "stop_cost": 5.0, "max_cost": 5.0},
    {"event": "close", "run_id": "prior-run", "end": 2.0, "charge": 0.37, "ended": "complete"},
]


def test_dollar3_over_the_cap_is_refused_before_anything_starts(fake: Fake, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    before = _seed_ledger(ledger, PRIOR)
    over = {"boot_minutes": 20.0, "idle_minutes": 10.0, "stop_cost": 0.4, "max_cost": 0.5}
    spec_path = write_sweep(tmp_path)
    store = Store(tmp_path / "store")
    p = make_plan(spec_path, store, PLAIN)
    o = options(tmp_path, **over)
    estimate = eb.estimate_burla_cost(p, o)
    assert 0.37 + estimate > 0.5
    for call in (lambda: eb.preflight_burla(p, PLAIN, o), lambda: eb.run_burla(p, PLAIN, store, options=o)):
        with pytest.raises(eb.BurlaCostGuard) as refused:
            call()
        message = str(refused.value)
        for needle in (f"{estimate:.2f}", "0.37", "0.50", str(ledger)):
            assert needle in message, (needle, message)
    assert ledger.read_bytes() == before and store.runs() == [] and fake.launchers() == []
    control = options(tmp_path, **{**over, "stop_cost": 0.37 + estimate + 0.04, "max_cost": 0.37 + estimate + 0.05})
    assert_complete(eb.run_burla(p, PLAIN, store, options=control), store, p)


def test_dollar4_the_stop_fires_within_5_s_of_its_deadline_and_the_run_resumes(fake: Fake, tmp_path: Path) -> None:
    """A prior run already charged $0.10 against the $0.30 stop, so this run stops at its own
    charge of about $0.20 two seconds in, and the message's charge cannot be read off the stop."""
    fake.script(attempts=[{"hang_after": 1}])
    _seed_ledger(tmp_path / "ledger.jsonl", [{**PRIOR[0], "run_id": "prior-0-10"},
                                              {**PRIOR[1], "run_id": "prior-0-10", "charge": 0.10}])
    p, store, opts, outcome = burla_run(fake, tmp_path, sweep={"replicates": 3}, usd_per_node_hour=360.0,
                                        stop_cost=0.3, max_cost=1.0)
    raised_at = time.time()
    assert isinstance(outcome, eb.BurlaSpendStop), outcome
    start = open_of(opts.ledger, p.run_id)["start"]
    deadline = start + 2.0
    assert deadline - 0.5 <= raised_at <= deadline + 5.0, (raised_at - start)
    closed = close_of(opts.ledger, p.run_id)
    assert closed["ended"] == "stopped"
    charge = f"{closed['charge']:.2f}"
    assert charge not in ("0.10", "0.30"), charge  # the run's own charge, told apart from the prior and the stop
    for needle in (p.run_id, charge, str(opts.ledger)):
        assert needle in str(outcome), (needle, str(outcome))
    rows = stored(store, p.run_id)
    assert len(rows) == 2 and status(store, p.run_id) != "complete"
    resumed = make_plan(tmp_path / "sweep.toml", store, PLAIN, resume=p.run_id)
    summary = eb.run_burla(resumed, PLAIN, store, options=options(tmp_path, stop_cost=50.0, max_cost=50.0))
    assert summary.complete and len(stored(store, p.run_id)) == 6


def test_dollar5_the_backstop_kills_a_launcher_that_never_reports(fake: Fake, tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eb, "_BACKSTOP_S", 1.5)
    monkeypatch.setattr(eb, "_KILL_GRACE_S", 1.5)
    monkeypatch.setattr(eb, "_launcher_argv", lambda: [sys.executable, "-I", str(DEAF), str(fake.state)])
    notes = fake.state / "deaf.jsonl"
    try:
        p, store, opts, outcome = burla_run(fake, tmp_path, usd_per_node_hour=360.0, stop_cost=0.2, max_cost=1.0)
        raised_at = time.time()
        assert isinstance(outcome, eb.BurlaSpendStop), outcome
        assert "burla cluster stop" in str(outcome) and "burla nodes list" in str(outcome), str(outcome)
        entries = [json.loads(line) for line in notes.read_text(encoding="utf-8").splitlines()]
        (who,) = [e for e in entries if "pid" in e]
        sigints = [e["time"] for e in entries if e.get("signal") == int(signal.SIGINT)]
        start = open_of(opts.ledger, p.run_id)["start"]
        assert sigints and abs(sigints[0] - (start + 2.0 + 1.5)) <= 1.5, [s - start for s in sigints]
        assert 1.5 - 0.3 <= raised_at - sigints[0] <= 1.5 + 5.0, raised_at - sigints[0]
        assert [e["signal"] for e in entries if "signal" in e] == [int(signal.SIGINT)], entries
        assert wait_gone(who["pid"], 5.0) is not None and wait_gone(who["heartbeat"], 5.0) is not None
        assert close_of(opts.ledger, p.run_id)["ended"] == "stopped"
    finally:
        if notes.exists():
            for line in notes.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                for key in ("pid", "heartbeat"):
                    if key in entry and alive(entry[key]):
                        os.kill(entry[key], signal.SIGKILL)


def test_dollar6_open_before_the_launcher_close_after_and_earlier_lines_untouched(fake: Fake, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    before = _seed_ledger(ledger, PRIOR)
    fake.watch_ledger(ledger)
    p, store, opts, outcome = burla_run(fake, tmp_path)
    assert_complete(outcome, store, p)
    snapshots = sorted(fake.state.glob("ledger-at-launch-*"))
    assert len(snapshots) == 1
    at_launch = ledger_lines(snapshots[0])
    assert at_launch[-1]["event"] == "open" and at_launch[-1]["run_id"] == p.run_id
    assert not [e for e in at_launch if e.get("run_id") == p.run_id and e.get("event") == "close"]
    after = ledger.read_bytes()
    assert after.startswith(before)
    new = ledger_lines(ledger)[len(PRIOR):]
    assert [(e["event"], e["run_id"]) for e in new] == [("open", p.run_id), ("close", p.run_id)]
    opened, closed = new
    for key in ("start", "estimate", "nodes", "machine_type", "usd_per_node_hour", "price_asof", "stop_cost", "max_cost"):
        assert key in opened, key
    assert closed["ended"] == "complete" and closed["end"] >= opened["start"] and closed["charge"] >= 0


def test_dollar7_a_run_that_never_closed_blocks_the_next_preflight(fake: Fake, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    crashed = {**PRIOR[0], "run_id": "crashed-run-7e2", "stop_cost": 1.25}
    before = _seed_ledger(ledger, [*PRIOR, crashed])
    assert eb._Ledger(ledger).unclosed() == ["crashed-run-7e2"]
    assert abs(eb._Ledger(ledger).total() - (0.37 + 1.25)) < 1e-9
    spec_path = write_sweep(tmp_path)
    store = Store(tmp_path / "store")
    p = make_plan(spec_path, store, PLAIN)
    o = options(tmp_path, stop_cost=50.0, max_cost=100.0)
    for call in (lambda: eb.preflight_burla(p, PLAIN, o), lambda: eb.run_burla(p, PLAIN, store, options=o)):
        with pytest.raises(eb.BurlaBackendError) as refused:
            call()
        assert "crashed-run-7e2" in str(refused.value)
    assert ledger.read_bytes() == before and store.runs() == [] and fake.launchers() == []
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "close", "run_id": "crashed-run-7e2", "end": 3.0, "charge": 0.2,
                             "ended": "error"}) + "\n")
    assert eb._Ledger(ledger).unclosed() == []
    assert_complete(eb.run_burla(p, PLAIN, store, options=o), store, p)


def test_dollar8_the_ledger_reads_high_by_both_allowances_per_run(fake: Fake, tmp_path: Path) -> None:
    # A price at which a run's own window, a fraction of a second, shows in the charge, beside the allowances.
    over = {"nodes": 2, "usd_per_node_hour": 3600.0, "boot_minutes": 1.5, "idle_minutes": 2.5, "stop_cost": 5000.0,
            "max_cost": 5000.0}
    runs = []
    for name in ("first", "second"):
        p, store, opts, outcome = burla_run(fake, tmp_path / name, ledger=tmp_path / "ledger.jsonl", **over)
        assert_complete(outcome, store, p)
        runs.append(p.run_id)
    lines = ledger_lines(tmp_path / "ledger.jsonl")
    windows = []
    for run_id in runs:
        opened = next(e for e in lines if e["event"] == "open" and e["run_id"] == run_id)
        closed = next(e for e in lines if e["event"] == "close" and e["run_id"] == run_id)
        window = closed["end"] - opened["start"]
        windows.append(window)
        want = 2 * 3600.0 * (window / 3600 + (1.5 + 2.5) / 60)
        assert abs(closed["charge"] - want) < 0.005, (closed["charge"], want)
        assert 2 * 3600.0 * window / 3600 > 0.005, "the window is too short to show in the charge"
    total = eb._Ledger(tmp_path / "ledger.jsonl").total()
    floor = 2 * 3600.0 * (sum(windows) / 3600 + (1.5 + 2.5) / 60)
    assert total >= floor
    assert abs((total - floor) - 2 * 3600.0 * (1.5 + 2.5) / 60) < 0.005


def test_dollar9_the_preflight_shows_the_declaration_and_the_manifest_keeps_it(fake: Fake, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    _seed_ledger(ledger, PRIOR)
    over = {"nodes": 3, "slots_per_node": 7, "usd_per_node_hour": 0.417, "price_asof": "fixture desk, 2026-09-27",
            "stop_cost": 2.75, "max_cost": 4.25, "machine_type": "m7i.4xlarge"}
    spec_path = write_sweep(tmp_path)
    store = Store(tmp_path / "store")
    p = make_plan(spec_path, store, PLAIN)
    o = options(tmp_path, **over)
    estimate = eb.estimate_burla_cost(p, o)
    text = eb.preflight_burla(p, PLAIN, o)
    cluster = next(line for line in text.splitlines() if line.startswith("Cluster: "))
    cost = next(line for line in text.splitlines() if line.startswith("Cost: "))
    for needle in ("3", "m7i.4xlarge", "7"):
        assert needle in cluster, (needle, cluster)
    for needle in ("0.417", "fixture desk, 2026-09-27", f"{estimate:.2f}", "0.37", "2.75", "4.25", str(ledger)):
        assert needle in cost, (needle, cost)
    assert_complete(eb.run_burla(p, PLAIN, store, options=o), store, p)
    kept = store.manifest(p.run_id).environment["burla"]
    want = {"nodes": 3, "machine_type": "m7i.4xlarge", "slots_per_node": 7, "usd_per_node_hour": 0.417,
            "price_asof": "fixture desk, 2026-09-27", "stop_cost": 2.75, "max_cost": 4.25}
    for key, value in want.items():
        assert kept[key] == value, key
    assert abs(kept["estimate"] - estimate) < 1e-9 and abs(kept["ledger_total"] - 0.37) < 1e-9


# ---------- P: the pre-flight and the CLI ----------


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=io.StringIO())
    return code, out.getvalue(), err.getvalue()


def new_run(store_root: Path, before: set[str]) -> str:
    """The one run a sweep added. A sweep ends with a verdict line, not its run id, so the id is
    read from the store."""
    added = set(Store(store_root).runs()) - before
    assert len(added) == 1, added
    return added.pop()


def sweep_argv(root: Path, spec: Path, target: str = PLAIN, *extra: str, backend: str = "burla") -> list[str]:
    # PF4.30: no lone condition of these small designs can be flagged, which any accepted change
    # below 1 refuses; --max-mde 1 admits them.
    return ["--store", str(root / "store"), "sweep", str(spec), "--target", target, "--backend", backend,
            "--salt", "0123456789abcdef", "--max-mde", "1", "--yes", *extra]


def test_p1_the_flag_its_refusals_and_its_overrides(fake: Fake, tmp_path: Path) -> None:
    spec = write_sweep(tmp_path, replicates=3, burla=burla_table(stop_cost=5.0, max_cost=20.0))
    ledger = tmp_path / "ledgers" / "step.jsonl"
    for flag in (["--concurrency", "2"], ["--app-name", "x"], ["--image", "gpu"]):
        code, out, err = run_cli(sweep_argv(tmp_path, spec, PLAIN, *flag))
        # A refusal exits 1.
        assert code == 1, (flag, out, err)
    assert fake.launchers() == [] and not ledger.exists()
    code, out, err = run_cli(sweep_argv(tmp_path, spec, PLAIN, "--max-cost", "7.5", "--est-seconds", "0.002",
                                        "--infra-retries", "3", "--episode-timeout", "30", "--batch-size", "1"))
    assert code == 0, err
    run_id = new_run(tmp_path / "store", set())
    opened = open_of(ledger, run_id)
    assert opened["max_cost"] == 7.5
    p = make_plan(spec, Store(tmp_path / "other"), PLAIN)
    want = eb.estimate_burla_cost(p, dataclasses.replace(eb.BurlaOptions.from_sweep_file(spec),
                                                         est_seconds_per_episode=0.002, batch_size=1))
    assert abs(opened["estimate"] - want) < 1e-12
    assert Store(tmp_path / "store").manifest(run_id).environment["infra_retries"] == 3
    (call,) = fake.starts()
    assert {item["episode_timeout"] for item in call["items"]} == {30.0}
    assert {len(item["jobs"]) for item in call["items"]} == {1}
    code, out, err = run_cli(sweep_argv(tmp_path / "capped", spec, PLAIN, "--max-rollouts", "2"))
    # A sweep stopped by --max-rollouts exits 3 and ends with a stopped line instead of the
    # stopped_by field; the store holds the run, partial, with the two
    # rollouts it kept.
    assert code == 3, err
    assert any(line.startswith("stopped  ") for line in out.splitlines()), out
    capped = Store(tmp_path / "capped" / "store")
    (capped_run,) = capped.runs()
    assert capped.manifest(capped_run).status == "partial" and capped.count(capped_run) == 2
    code, out, err = run_cli(sweep_argv(tmp_path / "local", spec, PLAIN, "--max-cost", "1", backend="local"))
    # A refusal exits 1.
    assert code == 1, "--backend local changed"


def test_p1_an_unknown_burla_field_is_a_refusal(fake: Fake, tmp_path: Path) -> None:
    spec = write_sweep(tmp_path, burla=burla_table(nodez=4))
    code, out, err = run_cli(sweep_argv(tmp_path, spec))
    # A refusal exits 1.
    assert code == 1 and "nodez" in err, err


def test_p2_the_target_resolves_here_first_with_the_local_refusal(fake: Fake, tmp_path: Path) -> None:
    bad = "bu_targets.nope:rollout"
    good = write_sweep(tmp_path / "good", burla=burla_table())
    # PF3.3: an unknown key in [burla] is refused when the spec is read, before the target; the
    # [burla] table is broken here in a way strict key checking does not see (nodes, a known field,
    # out of range), so the test says the target resolves before the table's values are checked.
    broken = write_sweep(tmp_path / "broken", burla=burla_table(nodes=0))
    local = run_cli(sweep_argv(tmp_path / "good", good, bad, backend="local"))
    # A refusal exits 1.
    assert local[0] == 1
    for spec in (good, broken):
        code, out, err = run_cli(sweep_argv(spec.parent, spec, bad))
        assert (code, err) == (1, local[2]), err
    assert fake.launchers() == [] and not (tmp_path / "good" / "ledgers").exists()


def _dist_info(root: Path, name: str, direct_url: dict[str, Any]) -> None:
    info = root / f"{name}-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n", encoding="utf-8")
    (info / "direct_url.json").write_text(json.dumps(direct_url), encoding="utf-8")


def test_p3_the_bundle_must_carry_the_target_and_its_local_imports(fake: Fake, tmp_path: Path) -> None:
    spec_path = write_sweep(tmp_path)
    store = Store(tmp_path / "store")
    for target, packages, missing in ((PLAIN, (), "bu_targets"), (USES_HELPER, ("bu_targets",), "bu_helper")):
        p = make_plan(spec_path, store, target)
        with pytest.raises(eb.BurlaBackendError) as refused:
            eb.preflight_burla(p, target, options(tmp_path, packages=packages))
        assert missing in str(refused.value)
    p = make_plan(spec_path, store, USES_HELPER)
    eb.preflight_burla(p, USES_HELPER, options(tmp_path, packages=("bu_targets", "bu_helper")))
    assert fake.launchers() == []


@pytest.mark.parametrize("kind", ["folder", "wheel"])
def test_p3_a_venv_holding_a_local_install_a_worker_would_lack_is_refused(fake: Fake, tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    dists = tmp_path / "dists"
    name = f"bu-fixture-local-{kind}"
    direct = ({"url": f"file://{tmp_path}/src", "dir_info": {}} if kind == "folder"
              else {"url": f"file://{tmp_path}/x-1.0-py3-none-any.whl", "archive_info": {}})
    _dist_info(dists, name.replace("-", "_"), direct)
    _dist_info(dists, "bu_fixture_editable", {"url": f"file://{tmp_path}/src", "dir_info": {"editable": True}})
    monkeypatch.syspath_prepend(str(dists))
    spec_path = write_sweep(tmp_path)
    p = make_plan(spec_path, Store(tmp_path / "store"), PLAIN)
    with pytest.raises(eb.BurlaBackendError) as refused:
        eb.preflight_burla(p, PLAIN, options(tmp_path))
    message = str(refused.value)
    assert name.replace("-", "_") in message or name in message, message
    assert "bu_fixture_editable" not in message and "bu-fixture-editable" not in message
    shutil.rmtree(dists / f"{name.replace('-', '_')}-1.0.dist-info")
    importlib.invalidate_caches()
    eb.preflight_burla(p, PLAIN, options(tmp_path))


def test_p4_a_job_0_that_differs_in_the_workers_view_is_refused_and_printed(fake: Fake, tmp_path: Path,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BU_DRIFT_MARKER", "host-value-4c7e")
    spec = write_sweep(tmp_path / "drift", burla=burla_table())
    code, out, err = run_cli(sweep_argv(spec.parent, spec, DRIFTING))
    # A refusal exits 1.
    assert code == 1, (out, err)
    assert "host-value-4c7e" in out + err and "absent-in-the-worker-view" in out + err
    assert fake.launchers() == [] and not (spec.parent / "ledgers").exists()
    assert Store(spec.parent / "store").runs() == []
    monkeypatch.delenv("BU_DRIFT_MARKER")
    spec2 = write_sweep(tmp_path / "same", burla=burla_table())
    code, out, err = run_cli(sweep_argv(spec2.parent, spec2, DRIFTING))
    assert code == 0, err


# PF4.22: the preflight block prints no "MDE at N=..." line; the plan's one limit is the gate's
# line. The other lines keep this order.
PREFLIGHT_ORDER = ["Backend: burla", "Cluster: ", "Bundle: ", "Worker view: ", "Traffic: ", "Cost: ", "Chaos: "]


def _git_package(root: Path, name: str) -> Path:
    """A package in a throwaway git checkout of its own, committed, then edited: a dirty tree."""
    shutil.copytree(TARGETS / "bu_version", root / name)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
           "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run(["git", "-C", str(root), *args], check=True, env=env, capture_output=True)
    (root / name / "__init__.py").write_text((root / name / "__init__.py").read_text(encoding="utf-8") + "\n# edited\n",
                                             encoding="utf-8")
    return root


def test_p5_the_preflight_prints_its_lines_in_order(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(_git_package(tmp_path / "checkout", "bu_dirty")))
    spec_path = write_sweep(tmp_path, chaos={"fault": "none", "rate": 1.0, "steps": []})
    p = make_plan(spec_path, Store(tmp_path / "store"), PLAIN)
    text = eb.preflight_burla(p, PLAIN, options(tmp_path, packages=("bu_targets", "bu_dirty")))
    lines = text.splitlines()
    positions = [next(i for i, line in enumerate(lines) if line.startswith(prefix)) for prefix in PREFLIGHT_ORDER]
    assert positions == sorted(positions), lines
    cluster = lines[positions[1]]
    assert "grow off" in cluster, cluster
    bundle_line = lines[positions[2]]
    bundle = eb._build_bundle(("bu_targets", "bu_dirty"))
    for name in ("poisson_prove", "bu_targets", "bu_dirty"):
        assert name in bundle_line, (name, bundle_line)
    assert f"Bundle: poisson_prove {_expected_version('poisson_prove') or 'unversioned'}, " in bundle_line, bundle_line
    commit = _git(tmp_path / "checkout", "rev-parse", "HEAD")
    assert commit and commit[:7] in bundle_line and bundle.sha256 in bundle_line, bundle_line
    assert "uncommitted changes" in bundle_line
    # PF4.22: no "MDE at N=" line in the preflight block.
    assert not any(line.startswith("MDE at N=") for line in lines), lines
    plain = eb.preflight_burla(p, PLAIN, options(tmp_path, packages=("bu_targets",)))
    plain_bundle = next(line for line in plain.splitlines() if line.startswith("Bundle: "))
    dirty = bool(_expected_package("bu_targets")["dirty"])
    assert ("uncommitted changes" in plain_bundle) == dirty, (dirty, plain_bundle)


def test_p6_a_burla_run_is_read_like_any_run(fake: Fake, tmp_path: Path) -> None:
    spec = write_sweep(tmp_path, replicates=3, burla=burla_table())
    store_root = tmp_path / "store"
    code, out, err = run_cli(sweep_argv(tmp_path, spec, PLAIN, backend="local"))
    assert code == 0, err
    local = new_run(store_root, set())
    code, out, err = run_cli(sweep_argv(tmp_path, spec))
    assert code == 0, err
    remote = new_run(store_root, {local})
    code, out, err = run_cli(["--store", str(store_root), "runs"])
    # PF2: runs rows lead with # and the name, so the row is found by
    # the id, and the status and backend are the two cells after it.
    assert code == 0 and any(
        line.split()[line.split().index(remote):][:3] == [remote, "complete", "burla"]
        for line in out.splitlines() if remote in line.split()
    ), out
    assert run_cli(["--store", str(store_root), "diff", local, remote, "--event", "fell"])[0] == 0
    assert run_cli(["--store", str(store_root), "check", local, remote, "--event", "fell", "--fail-on", "any"])[0] == 0
    assert run_cli(["--store", str(store_root), "report", local, remote, "--event", "fell", "--x", "cell",
                    "--out", str(tmp_path / "report")])[0] == 0
    assert run_cli(["--store", str(store_root), "serve", local, remote, "--event", "fell", "--x", "cell", "--json"])[0] == 0
    # --json replaces --format json on diff.
    code, out, err = run_cli(["--store", str(store_root), "diff", local, remote, "--event", "fell", "--json"])
    fell = json.loads(out)["by_event"]["fell"]
    # PF4.20: "fell" has no declared kind, so the JSON gives direction counts and leaves the
    # safer/worse counts null; the fact pinned is that no condition moved and two are unchanged.
    assert fell["n_worse"] is None and fell["n_safer"] is None and fell["kind"] is None, fell
    assert fell["n_higher"] == 0 and fell["n_lower"] == 0 and fell["n_unchanged"] == 2, fell
    assert comparable(stored(Store(store_root), local)) == comparable(stored(Store(store_root), remote))


def test_p7_the_backends_refusals_exit_as_refusals(fake: Fake, tmp_path: Path) -> None:
    ledger = tmp_path / "guard" / "ledgers" / "step.jsonl"
    _seed_ledger(ledger, PRIOR)
    guard = write_sweep(tmp_path / "guard", burla=burla_table(stop_cost=0.3, max_cost=0.3))
    code, out, err = run_cli(sweep_argv(guard.parent, guard))
    # A refusal exits 1.
    assert code == 1 and str(ledger) in err, err
    fake.script(attempts=[{"hang_after": 1}])
    stop = write_sweep(tmp_path / "stop", replicates=3,
                       burla=burla_table(usd_per_node_hour=360.0, stop_cost=0.3, max_cost=1.0))
    code, out, err = run_cli(sweep_argv(stop.parent, stop))
    assert code == 3 and str(stop.parent / "ledgers" / "step.jsonl") in err, err
    fake.script(default={"refuse": "NoNodes"})
    refused = write_sweep(tmp_path / "refused", burla=burla_table())
    code, out, err = run_cli(sweep_argv(refused.parent, refused))
    # PF4.49: under --max-mde 1 this design, in which no lone condition can be flagged, gets the
    # gate's facts as a note: line first; the backend's refusal is the next.
    rest = "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))
    assert code == 3 and rest.startswith("error: "), err


# ---------- I: imports and surface ----------


def test_i1_nothing_imports_burla_at_import_time() -> None:
    probe = (
        "import importlib.util, sys\n"
        f"sys.path.insert(0, {str(FIXTURES)!r})\n"
        "assert importlib.util.find_spec('burla') is not None\n"
        "import poisson_prove, poisson_prove.cli, poisson_prove.executor_burla\n"
        "print('burla' in sys.modules)\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(PACKAGE.parent)}, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == "False"


def test_i3_the_public_surface_is_the_eight_names() -> None:
    assert executor_burla.__all__ == BURLA_ALL


def test_i5_the_burla_extra_joins_the_extras_and_cloudpickle_joins_dev() -> None:
    # PF9: Burla ships as an experimental backend with a [burla] extra
    # pinning the client the backend runs; what it pins is test_pf9_backends.py's.
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    extras = project["optional-dependencies"]
    assert "burla" in extras
    assert any(req.split("=")[0].split(">")[0].split("<")[0].strip().lower() == "cloudpickle" for req in extras["dev"])
