"""The Burla backend: a sweep on a small fixed cluster in the user's own cloud, through Burla.

Burla 1.8.4 ships only the ``.py`` files of the local modules a caller has imported, and refuses
a call whose shipped code imports a local package inside a function. Prove as it stands trips
that rule, and a target package may read data files beside its own source. So this backend ships its
own bundle -- a deterministic tarball of the real package folders, data files included -- from a
small launcher (``_burla_submit.py``) that imports none of them. The launcher calls
``remote_parallel_map`` on its own main thread and forwards every result over a pipe; each
worker unpacks the bundle into a real folder and runs Prove's ``_container_batch``, the function
Modal's containers run.

Spend is capped by the tool, not only stated: every run declares its nodes, price, stop, cap
and ledger; a per-step JSON-lines ledger is checked before anything starts; the launcher stops
the job itself when the ledger total plus the run's accrued charge reaches the stop; and a
backstop kills the launcher's process group if it ever stops reporting.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
import pickle
import select
import signal
import struct
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import threading
import time
import tomllib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import MISSING, dataclass, fields
from pathlib import Path
from typing import Any

from poisson_prove._resolve import split_import_path
from poisson_prove.executor import (
    ExecutorError,
    Plan,
    RunSummary,
    _capture_line,
)
from poisson_prove.executor_modal import (
    Job,
    ModalOptions,
    Result,
    _capture_payload,
    _chaos_payload,
    _jobs,
    run_with_mapper,
)
from poisson_prove.store import Store

__all__ = [
    "BurlaBackendError",
    "BurlaCostGuard",
    "BurlaNotInstalled",
    "BurlaOptions",
    "BurlaSpendStop",
    "estimate_burla_cost",
    "preflight_burla",
    "run_burla",
]

_BACKEND = "burla"
_BURLA_PIN = "1.8.4"
_INSTALL_HINT = 'pip install "poisson-prove[burla]"'
#: After the stop's deadline, how long the launcher has to report before the parent sends it
#: SIGINT, and how long after that before its whole process group is killed.
_BACKSTOP_S = 60.0
_KILL_GRACE_S = 30.0
#: How long a forwarded Ctrl-C waits for the launcher's cancel report.
_CANCEL_WAIT_S = 30.0
_POLL_S = 0.2


class BurlaBackendError(ExecutorError):
    """The Burla backend cannot run as requested."""


class BurlaNotInstalled(BurlaBackendError):
    """``burla==1.8.4`` is not importable by the launcher. ``nexts`` holds the install line."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.nexts = [_INSTALL_HINT]


class BurlaCostGuard(BurlaBackendError):
    """Refused before anything starts: the ledger total plus the estimate is over the cap."""


class BurlaSpendStop(BurlaBackendError):
    """The stop fired mid-run; the run is partial and resumable."""


# ---------- options ----------


def _is_local_head(url: str) -> bool:
    scheme, sep, rest = url.partition("://")
    host = rest.split("/", 1)[0].rsplit("@", 1)[-1].split(":", 1)[0]
    if not sep or not host:
        return False
    return scheme == "https" or (scheme == "http" and host in ("localhost", "127.0.0.1"))


@dataclass(frozen=True)
class BurlaOptions:
    nodes: int
    machine_type: str
    slots_per_node: int
    usd_per_node_hour: float
    price_asof: str
    ledger: Path
    head_url: str
    stop_cost: float
    max_cost: float
    est_seconds_per_episode: float
    packages: tuple[str, ...] = ()
    func_cpu: int = 1
    func_ram: int = 4
    boot_minutes: float = 5.0
    idle_minutes: float = 5.0
    batch_size: int = 256
    episode_timeout: float | None = None
    infra_retries: int = 2
    max_rollouts: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger", Path(self.ledger))
        object.__setattr__(self, "packages", tuple(self.packages))
        checks: list[tuple[bool, str]] = [
            (_int(self.nodes) and self.nodes >= 1, "nodes must be an integer >= 1"),
            (bool(self.machine_type), "machine_type must be named"),
            (_int(self.slots_per_node) and self.slots_per_node >= 1, "slots_per_node must be >= 1"),
            (
                _num(self.usd_per_node_hour) and self.usd_per_node_hour > 0,
                "usd_per_node_hour must be > 0",
            ),
            (bool(self.price_asof), "price_asof must say where and when the price was read"),
            (bool(str(self.ledger)) and str(self.ledger) != ".", "ledger must name a file"),
            (
                isinstance(self.head_url, str) and _is_local_head(self.head_url),
                "head_url must be a local http URL or an https one",
            ),
            (_num(self.stop_cost) and self.stop_cost > 0, "stop_cost must be > 0"),
            (
                _num(self.max_cost) and _num(self.stop_cost) and self.max_cost >= self.stop_cost,
                "max_cost must be at least stop_cost",
            ),
            (
                _num(self.est_seconds_per_episode) and self.est_seconds_per_episode > 0,
                "est_seconds_per_episode must be > 0",
            ),
            (_int(self.func_cpu) and self.func_cpu >= 1, "func_cpu must be an integer >= 1"),
            (_int(self.func_ram) and self.func_ram >= 1, "func_ram must be an integer >= 1"),
            (_num(self.boot_minutes) and self.boot_minutes >= 0, "boot_minutes must be >= 0"),
            (_num(self.idle_minutes) and self.idle_minutes >= 0, "idle_minutes must be >= 0"),
            (_int(self.batch_size) and self.batch_size >= 1, "batch_size must be >= 1"),
            (_int(self.infra_retries) and self.infra_retries >= 0, "infra_retries must be >= 0"),
        ]
        for ok, message in checks:
            if not ok:
                raise ValueError(f"BurlaOptions: {message}")
        if self.episode_timeout is not None and not (
            _num(self.episode_timeout) and self.episode_timeout > 0
        ):
            raise ValueError("BurlaOptions: episode_timeout must be > 0 when given")
        if self.max_rollouts is not None and not (
            _int(self.max_rollouts) and self.max_rollouts >= 1
        ):
            raise ValueError("BurlaOptions: max_rollouts must be >= 1 when given")

    @classmethod
    def from_sweep_file(cls, path: Path) -> BurlaOptions:
        """The sweep file's ``[burla]`` table. An unknown field is refused by name, and a
        relative ``ledger`` resolves against the sweep file's folder."""
        path = Path(path)
        with path.open("rb") as fh:
            table = tomllib.load(fh).get("burla")
        if not isinstance(table, Mapping):
            raise ValueError(f"{path} has no [burla] table")
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(table) - known)
        if unknown:
            raise ValueError(
                f"[burla] has unknown field(s): {', '.join(unknown)}; "
                f"the fields are {', '.join(sorted(known))}"
            )
        required = [
            f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING
        ]
        missing = [name for name in required if name not in table]
        if missing:
            raise ValueError(f"[burla] is missing required field(s): {', '.join(missing)}")
        values = dict(table)
        ledger = Path(str(values["ledger"]))
        if not ledger.is_absolute():
            ledger = Path(os.path.abspath(path.parent / ledger))
        values["ledger"] = ledger
        if "packages" in values:
            values["packages"] = tuple(values["packages"])
        return cls(**values)


def _int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# ---------- cost ----------


def _batches(p: Plan, options: BurlaOptions) -> int:
    return math.ceil(len(p.pairs) / options.batch_size) if p.pairs else 0


def estimate_burla_cost(p: Plan, options: BurlaOptions) -> float:
    """USD: the nodes, for as long as they are up, at the declared price.

    ``nodes × usd_per_node_hour × (boot + waves × batch_size × est_seconds / 60 + idle) / 60``,
    with ``waves = ceil(batches / (nodes × slots_per_node))`` and every duration in minutes.
    """
    waves = math.ceil(_batches(p, options) / (options.nodes * options.slots_per_node))
    minutes = (
        options.boot_minutes
        + waves * options.batch_size * options.est_seconds_per_episode / 60
        + options.idle_minutes
    )
    return options.nodes * options.usd_per_node_hour * minutes / 60


def _charge(options: BurlaOptions, elapsed_s: float) -> float:
    """A run's charge: its window plus both allowances in full, so the ledger reads high."""
    minutes = elapsed_s / 60 + options.boot_minutes + options.idle_minutes
    return options.nodes * options.usd_per_node_hour * minutes / 60


# ---------- the ledger ----------


class _Ledger:
    """One JSON-lines file per step. ``open`` and ``close`` lines are appended and fsynced, and
    never rewritten. A run whose ``open`` has no ``close`` counts as having spent its stop."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError as exc:
                raise BurlaBackendError(
                    f"ledger {self.path} line {number} is not JSON: {exc}"
                ) from exc
            if not isinstance(entry, dict):
                raise BurlaBackendError(f"ledger {self.path} line {number} is not an object")
            out.append(entry)
        return out

    def unclosed(self, *, exclude: str | None = None) -> list[str]:
        opened: dict[str, dict[str, Any]] = {}
        closed: set[str] = set()
        for entry in self.entries():
            if entry.get("event") == "open":
                opened[str(entry.get("run_id"))] = entry
            elif entry.get("event") == "close":
                closed.add(str(entry.get("run_id")))
        return [run for run in opened if run not in closed and run != exclude]

    def total(self, *, exclude: str | None = None) -> float:
        entries = self.entries()
        total = sum(float(e.get("charge", 0.0)) for e in entries if e.get("event") == "close")
        open_lines = {str(e.get("run_id")): e for e in entries if e.get("event") == "open"}
        for run in self.unclosed(exclude=exclude):
            total += float(open_lines[run].get("stop_cost", 0.0))
        return total

    def _append(self, entry: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(entry), sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def open(self, **entry: Any) -> None:
        self._append({"event": "open", **entry})

    def close(self, **entry: Any) -> None:
        self._append({"event": "close", **entry})


def _usd(amount: float) -> str:
    return f"${amount:.2f}"


def _check_cap(
    ledger: _Ledger, estimate: float, options: BurlaOptions, *, exclude: str | None = None
) -> float:
    unclosed = ledger.unclosed(exclude=exclude)
    if unclosed:
        runs = ", ".join(unclosed)
        raise BurlaCostGuard(
            f"ledger {ledger.path} holds a run that never closed ({runs}); it counts as having "
            "spent its whole stop until it is closed by hand. Read its node-hours off "
            "`burla usage show` and append a close line such as "
            f'{{"event": "close", "run_id": "{unclosed[0]}", "charge": <usd>, "ended": "error"}}'
        )
    total = ledger.total(exclude=exclude)
    if total + estimate > options.max_cost:
        raise BurlaCostGuard(
            f"refused before anything starts: estimate {_usd(estimate)} plus ledger total "
            f"{_usd(total)} is over the cap {_usd(options.max_cost)} (ledger {ledger.path})"
        )
    return total


# ---------- the bundle ----------


@dataclass(frozen=True)
class _Bundle:
    """The gzip'd tar the workers unpack, and what the manifest records about it."""

    data: bytes
    sha256: str
    packages: Mapping[str, Mapping[str, Any]]

    @property
    def size(self) -> int:
        return len(self.data)

    def record(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "size": self.size,
            "packages": {name: dict(info) for name, info in self.packages.items()},
        }


def _package_folder(name: str) -> Path:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError) as exc:
        raise BurlaBackendError(f"cannot find package {name!r} to bundle: {exc}") from exc
    if spec is None or not spec.submodule_search_locations:
        raise BurlaBackendError(
            f"{name!r} is not an installed package folder, so it cannot be bundled"
        )
    return Path(next(iter(spec.submodule_search_locations))).resolve()


def _git(folder: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(folder), *args], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _version(name: str) -> str | None:
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


def _build_bundle(packages: Sequence[str]) -> _Bundle:
    """``poisson_prove`` and each named package, as a deterministic gzip'd tar: sorted entries,
    mtimes and owners zeroed, modes 0644 and 0755, gzip mtime zero, no caches.

    Each named package is recorded with its version, commit and whether it has uncommitted
    changes; ``poisson_prove`` with its version only, since a commit of the tool says nothing
    about the user's code."""
    names = ["poisson_prove", *[name for name in packages if name != "poisson_prove"]]
    raw = io.BytesIO()
    info: dict[str, dict[str, Any]] = {}
    members: list[tuple[str, Path]] = []
    for name in names:
        folder = _package_folder(name)
        if name == "poisson_prove":
            info[name] = {"version": _version(name)}
        else:
            commit = _git(folder, "rev-parse", "HEAD")
            status = _git(folder, "status", "--porcelain", "--", ".") if commit else None
            info[name] = {
                "version": _version(name),
                "commit": commit,
                "dirty": None if status is None else bool(status),
            }
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            rel_root = Path(root).relative_to(folder)
            members.append((os.path.normpath(str(Path(name) / rel_root)), Path(root)))
            for file in sorted(files):
                if file.endswith((".pyc", ".pyo")):
                    continue
                arcname = os.path.normpath(str(Path(name) / rel_root / file))
                members.append((arcname, Path(root) / file))
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for arcname, source in sorted(members):
            arcname = os.path.normpath(arcname)
            member = tarfile.TarInfo(arcname)
            member.mtime = 0
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            if source.is_dir():
                member.type = tarfile.DIRTYPE
                member.mode = 0o755
                tar.addfile(member)
            else:
                data = source.read_bytes()
                member.size = len(data)
                member.mode = 0o755 if os.access(source, os.X_OK) else 0o644
                tar.addfile(member, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw.getvalue())
    data = compressed.getvalue()
    return _Bundle(data=data, sha256=hashlib.sha256(data).hexdigest(), packages=info)


# ---------- the pre-flight's checks ----------


def _stdlib_and_dist_prefixes() -> tuple[str, ...]:
    paths = sysconfig.get_paths()
    prefixes = {
        paths.get("stdlib"),
        paths.get("platstdlib"),
        paths.get("purelib"),
        paths.get("platlib"),
    }
    return tuple(sorted(os.path.realpath(p) + os.sep for p in prefixes if p))


def _local_imports(import_path: str) -> set[str]:
    """The target's top-level package, and every package its module imports whose code lies
    outside the standard library and the venv's site-packages."""
    module_name, _ = split_import_path(import_path)
    found = {module_name.split(".")[0]}
    spec = importlib.util.find_spec(module_name)
    if spec is None or not spec.origin or not os.path.isfile(spec.origin):
        return found
    known = _stdlib_and_dist_prefixes()
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names = [node.module]
        for name in names:
            top = name.split(".")[0]
            if top in sys.builtin_module_names:
                continue
            try:
                found_spec = importlib.util.find_spec(top)
            except (ImportError, ValueError):
                continue
            if found_spec is None:
                continue
            origin = found_spec.origin
            if origin in (None, "built-in", "frozen"):
                locations = list(found_spec.submodule_search_locations or [])
                if not locations:
                    continue
                directory = locations[0]
            else:
                directory = os.path.dirname(origin)
            if not (os.path.realpath(directory) + os.sep).startswith(known):
                found.add(top)
    return found


def _local_installs() -> list[str]:
    """Distributions a worker would lack: a non-editable local-folder or local-wheel install is
    importable here but never reaches a node."""
    found = []
    for dist in importlib.metadata.distributions():
        text = dist.read_text("direct_url.json")
        if not text:
            continue
        try:
            direct = json.loads(text)
        except ValueError:
            continue
        url = str(direct.get("url", ""))
        if not url.startswith("file:"):
            continue
        dir_info = direct.get("dir_info")
        if isinstance(dir_info, Mapping) and dir_info.get("editable"):
            continue
        if dir_info is not None or direct.get("archive_info") is not None:
            found.append(str(dist.metadata["Name"]))
    return sorted(set(found))


_REHEARSAL = r"""
import os, pickle, sys, tarfile, io
request = pickle.load(sys.stdin.buffer)
root = request["root"]
if root is None:
    sys.path[:] = request["paths"]
else:
    with tarfile.open(fileobj=io.BytesIO(request["bundle"]), mode="r:gz") as tar:
        tar.extractall(root, filter="data")
    sys.path[:] = [root, *request["stdlib"], *request["site"]]
module = __import__("poisson_prove.executor_modal", fromlist=["worker_batch"])
job, import_path, timeout, capture, chaos = request["args"]
try:
    result = module.worker_batch([job], import_path, timeout, capture=capture, chaos=chaos)[0]
    out = ("ok", result)
except BaseException as exc:
    name = exc.name if isinstance(exc, ModuleNotFoundError) else None
    out = ("raised", f"{type(exc).__name__}: {exc}", name)
sys.stdout.buffer.write(pickle.dumps(out))
"""


def _comparable(result: Result) -> Any:
    if isinstance(result, str):
        return ("error", result.strip().splitlines()[-1] if result.strip() else "")
    if "error" in result:
        return ("error", str(result["error"]).strip().splitlines()[-1:])
    return {key: value for key, value in result.items() if key != "wall_time"}


def _rehearse(p: Plan, import_path: str, bundle: _Bundle, options: BurlaOptions) -> tuple[Any, Any]:
    """Job 0 twice: in this machine's view, and in the worker's. Each runs in an interpreter
    started for it, so nothing is armed in this process. This machine's view is a plain
    interpreter with this process's ``sys.path``, environment and working directory. The
    worker's is started ``-I -S`` with the unpacked bundle, the standard library and the venv's
    ``site-packages`` (no ``.pth``) on its path, an empty environment and a fresh working
    directory. Returns both, as compared."""
    if not p.pairs:
        return None, None
    job = _jobs(p)[0]
    capture = _capture_payload(p.spec.capture, p.run_id)
    chaos = _chaos_payload(p.spec.chaos)
    args = (job, import_path, options.episode_timeout, capture, chaos)
    # The standard library is the base interpreter's: in a venv, ``platstdlib`` is the venv's own
    # ``lib/pythonX.Y``, which holds ``site-packages`` and no ``lib-dynload``.
    base = sysconfig.get_paths(vars={"base": sys.base_prefix, "platbase": sys.base_exec_prefix})
    paths = sysconfig.get_paths()
    with tempfile.TemporaryDirectory(prefix="poisson-prove-rehearsal-") as scratch:
        here = _rehearsal_run(
            {"root": None, "paths": list(sys.path), "args": args},
            argv=[sys.executable, "-c", _REHEARSAL],
            env=dict(os.environ),
            cwd=os.getcwd(),
            view="this machine's view",
        )
        there = _rehearsal_run(
            {
                "root": os.path.join(scratch, "bundle"),
                "bundle": bundle.data,
                "stdlib": [
                    base["stdlib"],
                    base["platstdlib"],
                    os.path.join(base["platstdlib"], "lib-dynload"),
                ],
                "site": sorted({paths["purelib"], paths["platlib"]}),
                "args": args,
            },
            argv=[sys.executable, "-I", "-S", "-c", _REHEARSAL],
            env={},
            cwd=scratch,
            view="the worker's view",
        )
    return _comparable(here), _comparable(there)


def _rehearsal_run(
    request: Mapping[str, Any], *, argv: list[str], env: Mapping[str, str], cwd: str, view: str
) -> Result:
    done = subprocess.run(
        argv, input=pickle.dumps(dict(request)), capture_output=True, env=env, cwd=cwd, timeout=600
    )
    if done.returncode != 0 or not done.stdout:
        raise BurlaBackendError(
            f"the rehearsal of job 0 in {view} failed to run:\n"
            + done.stderr.decode("utf-8", "replace")[-4000:]
        )
    kind, *rest = pickle.loads(done.stdout)
    if kind != "ok":
        missing = rest[1] if len(rest) > 1 else None
        detail = f"; the bundle does not carry {missing!r}" if missing else ""
        raise BurlaBackendError(f"job 0 does not run in {view}: {rest[0]}{detail}")
    result: Result = rest[0]
    return result


def _head_line(options: BurlaOptions, bundle: _Bundle) -> str:
    parts = []
    for name, info in bundle.packages.items():
        version = info.get("version") or "unversioned"
        if "commit" not in info:
            parts.append(f"{name} {version}")
            continue
        commit = info.get("commit")
        tag = "no git" if commit is None else str(commit)[:7]
        if info.get("dirty"):
            tag += ", uncommitted changes"
        parts.append(f"{name} {version} ({tag})")
    size_mb = bundle.size / 1e6
    return f"Bundle: {', '.join(parts)} · {size_mb:.1f} MB · sha256 {bundle.sha256}"


def preflight_burla(p: Plan, import_path: str, options: BurlaOptions) -> str:
    """Build the bundle, check it covers the target, rehearse job 0 in the worker's view, read
    the ledger and estimate. Any refusal happens here; returns the block the caller prints. The cap
    refusal is raised last and carries the block as its ``plan`` attribute, so the command line
    can keep the plan on screen when it refuses."""
    spec = p.spec
    bundle = _build_bundle(options.packages)
    carried = set(bundle.packages)
    uncovered = sorted(_local_imports(import_path) - carried)
    if uncovered:
        raise BurlaBackendError(
            f"the bundle does not carry {', '.join(uncovered)}, which the target needs; add them "
            "to [burla] packages"
        )
    installs = _local_installs()
    if installs:
        raise BurlaBackendError(
            "this venv holds non-editable local installs a worker would lack: "
            f"{', '.join(installs)}; install them editable and add them to [burla] packages, "
            "or install them from an index"
        )
    here, there = _rehearse(p, import_path, bundle, options)
    if here != there:
        raise BurlaBackendError(
            f"job 0 differs between this machine and the worker's view:\n  here:   {here!r}\n"
            f"  worker: {there!r}"
        )
    ledger = _Ledger(options.ledger)
    estimate = estimate_burla_cost(p, options)
    total = ledger.total()
    slots = options.nodes * options.slots_per_node
    chaos = spec.chaos
    chaos_line = (
        "Chaos: none"
        if chaos is None
        else f"Chaos: fault {chaos.fault} · rate {chaos.rate:g} · "
        f"steps {', '.join(chaos.steps) or '-'} · armed in each worker; "
        "every ok row carries what it armed"
    )
    lines = [
        f"Sweep: {len(spec.axis_types)} axes · {len(spec.configs)} cells · "
        f"N={spec.replicates} → {spec.total_rollouts()} rollouts",
        f"Backend: {_BACKEND} · target: {spec.target_id} · t_unit: {spec.t_unit}",
        f"Target: {import_path} · resolved here; workers run this machine's code from the bundle",
        f"Cluster: {options.nodes} × {options.machine_type} · "
        f"{options.slots_per_node} slots each · {slots} at once · grow off · "
        f"idle allowance {options.idle_minutes:g} min · head {options.head_url}",
        _head_line(options, bundle),
        "Worker view: job 0 matches this machine",
        "Traffic: code, inputs and results go through Burla's relay unless the head runs with "
        "BURLA_PRIVATE=True, and then directly between this machine and the nodes; Prove cannot "
        "tell from the head which; the store stays on this machine",
        f"Cost: ~{_usd(estimate)} this run ({options.nodes} × "
        f"${options.usd_per_node_hour:g}/node-hour, {options.price_asof}) · "
        f"ledger {options.ledger} {_usd(total)} so far · "
        f"stop {_usd(options.stop_cost)} · cap {_usd(options.max_cost)}",
        chaos_line,
    ]
    capture_line = _capture_line(spec.capture)
    if capture_line is not None:
        lines.append(capture_line)
    if p.resumed:
        lines.append(f"Resuming {p.run_id}: {p.already_stored} stored, {len(p.pairs)} to run")
    text = "\n".join(lines) + "\n"
    try:
        _check_cap(ledger, estimate, options)
    except BurlaCostGuard as exc:
        exc.plan = text  # type: ignore[attr-defined]
        raise
    return text


# ---------- the launcher and the mapper ----------


def _launcher_argv() -> list[str]:
    """The command that starts the launcher. Tests point it at a fake."""
    return [sys.executable, "-I", str(Path(__file__).with_name("_burla_submit.py"))]


def _send(fh: Any, message: Any) -> None:
    data = pickle.dumps(message)
    fh.write(struct.pack(">Q", len(data)) + data)
    fh.flush()


class _Pipe:
    """Length-prefixed pickles from the launcher, read without blocking the caller."""

    def __init__(self, fd: int) -> None:
        self.fd = fd
        self.buffer = b""
        self.eof = False

    def poll(self, timeout: float) -> list[Any]:
        messages: list[Any] = []
        if self.eof:
            return messages
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if ready:
            chunk = os.read(self.fd, 1 << 20)
            if not chunk:
                self.eof = True
            self.buffer += chunk
        while len(self.buffer) >= 8:
            (size,) = struct.unpack(">Q", self.buffer[:8])
            if len(self.buffer) < 8 + size:
                break
            messages.append(pickle.loads(self.buffer[8 : 8 + size]))
            self.buffer = self.buffer[8 + size :]
        return messages


_JOB_LEVEL = ("NodeDisconnected",)
_ENDED = ("ClusterShutdown", "ClusterRestarted")
_FIXES = {
    "JobStalled": "the job ended short; a Python mismatch shows up this way (the workers must run "
    "this machine's 3.<minor>)",
    "NodesFailedToBoot": "the nodes failed to boot; check `burla nodes list` and the EC2 console",
    "NoNodes": "no node is running; start the cluster with `burla cluster start`, or, in private "
    "mode, through the coordinator's localhost API (POST /v1/settings, then "
    "POST /v1/management/cluster/start)",
    "NoCompatibleNodes": "no node fits func_cpu and func_ram; check `burla settings show`",
    "UnsupportedLocalImport": "Burla refused shipped code; the launcher must import nothing local",
    "FunctionTooBig": "the bundle is over Burla's 0.1 GB function limit",
}


class _BurlaMapper:
    """A ``Mapper`` over the launcher: one launcher process, and one Burla call, per round."""

    def __init__(
        self,
        p: Plan,
        import_path: str,
        options: BurlaOptions,
        bundle: _Bundle,
        deadline: float,
    ) -> None:
        self.p = p
        self.import_path = import_path
        self.options = options
        self.bundle = bundle
        self.deadline = deadline
        self.capture = _capture_payload(p.spec.capture, p.run_id)
        self.chaos = _chaos_payload(p.spec.chaos)
        self.log = options.ledger.with_suffix(".launcher.log")

    def _agree(self, rows: Sequence[Result]) -> None:
        if self.chaos is None:
            return
        for row in rows:
            if not isinstance(row, Mapping) or "error" in row:
                continue
            record = (row.get("backend_meta") or {}).get("chaos")
            if not isinstance(record, Mapping):
                continue  # presence is the shared runner's refusal
            wanted = (self.chaos["fault"], float(self.chaos["rate"]), list(self.chaos["steps"]))
            got = (
                record.get("fault"),
                float(record.get("rate", -1)),
                list(record.get("steps") or []),
            )
            empty_hooks = self.chaos["fault"] != "none" and not record.get("hooks")
            if got != wanted or empty_hooks:
                raise BurlaBackendError(
                    f"run {self.p.run_id!r}: a worker armed {got} (hooks {record.get('hooks')}) "
                    f"where the run asked for {wanted}; refused before storing the batch"
                )

    def __call__(
        self, batches: Sequence[Sequence[Job]]
    ) -> Iterator[tuple[int, list[Result] | BaseException]]:
        items = [
            (
                k,
                [tuple(job) for job in jobs],
                self.import_path,
                self.options.episode_timeout,
                self.capture,
                self.chaos,
            )
            for k, jobs in enumerate(batches)
        ]
        request = {
            "items": items,
            "bundle": self.bundle.data,
            "bundle_sha256": self.bundle.sha256,
            "deadline": self.deadline,
            "pin": _BURLA_PIN,
            "call": {
                "func_cpu": self.options.func_cpu,
                "func_ram": self.options.func_ram,
                "max_parallelism": self.options.nodes * self.options.slots_per_node,
            },
        }
        msg_r, msg_w = os.pipe()
        watch_r, watch_w = os.pipe()
        env = dict(os.environ)
        env["DISABLE_BURLA_TELEMETRY"] = "True"
        env["BURLA_CLUSTER_DASHBOARD_URL"] = self.options.head_url
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("ab") as log:
            proc = subprocess.Popen(
                [*_launcher_argv(), str(msg_w), str(watch_r)],
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=log,
                pass_fds=(msg_w, watch_r),
                start_new_session=True,
                env=env,
            )
        os.close(msg_w)
        os.close(watch_r)

        def feed() -> None:
            try:
                assert proc.stdin is not None
                proc.stdin.write(pickle.dumps(request))
                proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

        threading.Thread(target=feed, daemon=True).start()
        pipe = _Pipe(msg_r)
        seen: set[int] = set()
        stray: list[BaseException] = []
        done: tuple[Any, ...] | None = None
        forwarded = False
        sigint_at: float | None = None
        try:
            while done is None:
                try:
                    messages = pipe.poll(_POLL_S)
                except KeyboardInterrupt:
                    forwarded = True
                    self._forward_ctrl_c(proc, pipe)
                    raise
                for message in messages:
                    kind = message[0]
                    if kind == "result":
                        value = message[1]
                        k, results, failure = value
                        if k in seen or not 0 <= k < len(items):
                            continue
                        seen.add(k)
                        if results is None:
                            yield k, BurlaBackendError(f"worker failed: {failure}")
                        else:
                            self._agree(results)
                            yield k, results
                    elif kind == "exception":
                        _, name, text, index = message
                        exc = BurlaBackendError(f"{name}: {text}")
                        if isinstance(index, int) and 0 <= index < len(items) and index not in seen:
                            seen.add(index)
                            yield index, exc
                        else:
                            stray.append(exc)
                    elif kind in ("done", "missing"):
                        done = message
                if done is None and pipe.eof:
                    done = (
                        "done",
                        "error",
                        "LauncherExited",
                        f"the launcher exited ({proc.poll()}) without reporting",
                    )
                now = time.time()
                if done is None and sigint_at is None and now > self.deadline + _BACKSTOP_S:
                    sigint_at = now
                    _signal(proc, signal.SIGINT)
                if done is None and sigint_at is not None and now > sigint_at + _KILL_GRACE_S:
                    _killpg(proc)
                    raise BurlaSpendStop(
                        f"run {self.p.run_id!r}: the launcher did not report after the stop and "
                        "was killed with its process group. Run `burla cluster stop` now, then "
                        "check `burla nodes list` shows no node and the EC2 console shows no "
                        f"Burla instance (ledger {self.options.ledger})"
                    )
        finally:
            if done is None and not forwarded and proc.poll() is None:
                # Leaving early (the runner raised, or this generator was closed): cancel the job
                # the way a Ctrl-C would, then make sure nothing is left running.
                self._forward_ctrl_c(proc, pipe)
            os.close(msg_r)
            os.close(watch_w)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                _killpg(proc)
        assert done is not None
        if done[0] == "missing":
            raise BurlaNotInstalled(
                f"the launcher cannot import burla in this environment: {done[1]}"
            )
        how = done[1]
        if how in ("complete", "interrupted"):
            for k in range(len(items)):
                if k not in seen:
                    yield k, stray.pop(0) if stray else BurlaBackendError("no result returned")
            return
        if how == "stopped":
            raise BurlaSpendStop(
                f"run {self.p.run_id!r}: the stop fired at {_usd(self.options.stop_cost)}"
            )
        if how == "canceled":
            if forwarded:
                raise KeyboardInterrupt
            raise _ExternalCancel(f"JobCanceled: {done[2]} (the job was cancelled outside Prove)")
        name, text = done[2], done[3]
        if how == "ended":
            raise _ExternalCancel(f"{name}: {text}")
        fix = _FIXES.get(name, "")
        if name == "version":
            raise BurlaBackendError(
                f"the launcher found burla {text}, and this backend is pinned to "
                f"burla=={_BURLA_PIN}: {_INSTALL_HINT}"
            )
        raise BurlaBackendError(
            f"Burla refused the run: {name}: {text}" + (f"\nfix: {fix}" if fix else "")
        )

    def _forward_ctrl_c(self, proc: subprocess.Popen[bytes], pipe: _Pipe) -> None:
        _signal(proc, signal.SIGINT)
        until = time.time() + _CANCEL_WAIT_S
        while time.time() < until:
            if any(m[0] == "done" for m in pipe.poll(_POLL_S)) or pipe.eof:
                return


class _ExternalCancel(BurlaBackendError):
    """Someone ended the job outside Prove; the ledger closes the run as cancelled."""


def _signal(proc: subprocess.Popen[bytes], sig: int) -> None:
    try:
        os.kill(proc.pid, sig)
    except ProcessLookupError:
        pass


def _killpg(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


# ---------- the run ----------


def _placement(
    p: Plan, options: BurlaOptions, bundle: _Bundle, estimate: float, total: float
) -> dict[str, Any]:
    return {
        "burla": {
            "nodes": options.nodes,
            "machine_type": options.machine_type,
            "slots_per_node": options.slots_per_node,
            "usd_per_node_hour": options.usd_per_node_hour,
            "price_asof": options.price_asof,
            "estimate": estimate,
            "ledger": str(options.ledger),
            "ledger_total": total,
            "stop_cost": options.stop_cost,
            "max_cost": options.max_cost,
            "head_url": options.head_url,
            "func_cpu": options.func_cpu,
            "func_ram": options.func_ram,
            "boot_minutes": options.boot_minutes,
            "idle_minutes": options.idle_minutes,
            "pin": _BURLA_PIN,
        },
        "bundle": bundle.record(),
    }


def run_burla(
    p: Plan,
    import_path: str,
    store: Store,
    *,
    options: BurlaOptions,
    on_progress: Callable[[int, int], None] | None = None,
) -> RunSummary:
    """Run the plan on the fixed cluster, through the launcher, into ``store``."""
    ledger = _Ledger(options.ledger)
    estimate = estimate_burla_cost(p, options)
    total = _check_cap(ledger, estimate, options)
    bundle = _build_bundle(options.packages)
    start = time.time()
    rate = options.nodes * options.usd_per_node_hour / 3600
    allowances = (options.boot_minutes + options.idle_minutes) * 60
    deadline = start + max(0.0, (options.stop_cost - total) / rate - allowances)
    ledger.open(
        run_id=p.run_id,
        start=start,
        estimate=estimate,
        nodes=options.nodes,
        machine_type=options.machine_type,
        usd_per_node_hour=options.usd_per_node_hour,
        price_asof=options.price_asof,
        stop_cost=options.stop_cost,
        max_cost=options.max_cost,
    )
    mapper = _BurlaMapper(p, import_path, options, bundle, deadline)
    runner_options = ModalOptions(
        batch_size=options.batch_size,
        episode_timeout=options.episode_timeout,
        infra_retries=options.infra_retries,
        max_rollouts=options.max_rollouts,
    )

    def cost_check(plan: Plan) -> None:
        _check_cap(ledger, estimate, options, exclude=plan.run_id)

    ended = "error"
    stop: BurlaSpendStop | None = None
    charge = 0.0
    try:
        summary = run_with_mapper(
            p,
            mapper,
            store,
            options=runner_options,
            on_progress=on_progress,
            backend=_BACKEND,
            placement=_placement(p, options, bundle, estimate, total),
            cost_check=cost_check,
        )
        ended = "complete"
        return summary
    except BurlaSpendStop as exc:
        ended = "stopped"
        stop = exc
    except (KeyboardInterrupt, _ExternalCancel):
        ended = "cancelled"
        raise
    finally:
        end = time.time()
        charge = _charge(options, end - start)
        ledger.close(run_id=p.run_id, end=end, charge=charge, ended=ended)
    raise BurlaSpendStop(
        f"run {p.run_id!r} stopped at {_usd(charge)} against the stop {_usd(options.stop_cost)} "
        f"(ledger {options.ledger}); the stored batches stay, and --resume {p.run_id} continues it "
        f"once the stop is raised in the sweep file. {stop}"
    ) from stop
