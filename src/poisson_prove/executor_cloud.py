"""The cloud backend: a sweep on a cluster Prove starts in the reader's own cloud account and stops
when the sweep ends, through the cluster software Burla (1.8.4, pinned exactly).

Burla 1.8.4 ships only the ``.py`` files of the local modules a caller has imported, and refuses
a call whose shipped code imports a local package inside a function. Prove as it stands trips
that rule, and a target package may read data files beside its own source. So this backend ships its
own bundle -- a deterministic tarball of the real package folders, data files included -- from a
small launcher (``_cloud_submit.py``) that imports none of them. The launcher calls
``remote_parallel_map`` on its own main thread and forwards every result over a pipe; each
worker unpacks the bundle into a real folder and runs Prove's ``_container_batch``, the function
Modal's containers run.

The cluster's life is Prove's: the coordinator (Burla's head) is started on this machine through
``_cloud_head.py`` (Burla's private start function, in a process of its own), the cluster's
settings, start, status and stop go through Burla's CLI and its JSON envelope, and every ending
of the sweep stops the nodes and the coordinator Prove started. An ownership record per account
(``_cloud_record.py``) says what Prove owns, so a sweep that died is found and stopped by the
next one.

Spend is capped by the tool, not only stated: every run declares its nodes, price, stop, cap
and ledger; a per-step JSON-lines ledger is checked before anything starts; the launcher stops
the job itself when the ledger total plus the run's accrued charge reaches the stop; and a
backstop kills the launcher's process group if it ever stops reporting.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import gzip
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
import pickle
import re
import select
import shutil
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poisson_prove import _look, _prices_cloud
from poisson_prove._cloud_record import Record
from poisson_prove._resolve import split_import_path
from poisson_prove.executor import (
    ExecutorError,
    Plan,
    RunSummary,
    _capture_line,
)
from poisson_prove.executor_modal import (
    FIRST_BATCH_ERRORED,
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
    "CloudBackendError",
    "CloudCostGuard",
    "CloudNotInstalled",
    "CloudOptions",
    "CloudSpendStop",
    "estimate_cloud_cost",
    "preflight_cloud",
    "run_cloud",
]

_BACKEND = "cloud"
_PIN = "1.8.4"
_ENGINE = {"name": "burla", "version": _PIN}
_INSTALL_HINT = 'pip install "poisson-prove[cloud]"'
#: After the stop's deadline, how long the launcher has to report before the parent sends it
#: SIGINT, and how long after that before its whole process group is killed.
_BACKSTOP_S = 60.0
_KILL_GRACE_S = 30.0
#: How long a forwarded Ctrl-C waits for the launcher's cancel report.
_CANCEL_WAIT_S = 30.0
_POLL_S = 0.2
#: The record's heartbeat while the job runs, and how long the stop polls the cluster's status.
_ALIVE_S = 30.0
_STOP_POLL_S = 120.0
#: How often the progress line asks the cluster's status while it starts.
_STATUS_S = 10.0
#: The software's orphan rule: a node that cannot reach the coordinator stops itself after this.
_ORPHAN_MINUTES = 3.0


class CloudBackendError(ExecutorError):
    """The cloud backend cannot run as requested."""


class CloudRefusal(CloudBackendError):
    """Refused before anything is spent, in words given back exactly (no number respelled)."""

    verbatim = True

    def __init__(self, message: str, nexts: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.nexts = list(nexts)


class CloudNotInstalled(CloudBackendError):
    """``burla==1.8.4`` is not importable by the launcher. ``nexts`` holds the install line."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.nexts = [_INSTALL_HINT]


class CloudCostGuard(CloudBackendError):
    """Refused before anything starts: the ledger total plus the estimate is over the cap."""


class CloudSpendStop(CloudBackendError):
    """The stop fired mid-run; the run is partial and resumable."""


class CloudStartError(CloudBackendError):
    """The cluster could not start; ``started`` says whether any node did (exit 3) or not (1)."""

    def __init__(self, message: str, nexts: Sequence[str] = (), *, started: bool = False) -> None:
        super().__init__(message)
        self.nexts = list(nexts)
        self.started = started


class CloudStopUnconfirmed(CloudBackendError):
    """The stop could not be confirmed; the record stays ``stopping``. Its one next is ``where``,
    which shows what was left and stops it, so no resume line follows it. ``spent`` says the
    nodes were this sweep's own (work started, money spent) and not an earlier sweep's."""

    unstopped = True
    only_nexts = True

    def __init__(self, message: str, *, spent: bool) -> None:
        super().__init__(message)
        self.nexts = ["poisson-prove where"]
        self.spent = spent


class _LeftDuringStop(KeyboardInterrupt):
    """The third Ctrl-C: Prove leaves the stop to the next cloud sweep."""


# ---------- options ----------


@dataclass(frozen=True)
class CloudOptions:
    provider: str
    region: str
    machine_type: str
    nodes: int
    ledger: Path
    stop_cost: float
    max_cost: float
    est_seconds_per_episode: float
    max_vcpus: int | None = None
    slots_per_node: int | None = None
    image: str | None = None
    idle_minutes: float = 5.0
    boot_minutes: float = 5.0
    usd_per_node_hour: float | None = None
    price_asof: str | None = None
    disk_gb: int | None = None
    packages: tuple[str, ...] = ()
    func_cpu: int = 1
    func_ram: int = 4
    batch_size: int = 256
    episode_timeout: float | None = None
    infra_retries: int = 2
    max_rollouts: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger", Path(self.ledger))
        object.__setattr__(self, "packages", tuple(self.packages))
        checks: list[tuple[bool, str]] = [
            (
                self.provider in _prices_cloud.PROVIDERS,
                f"provider must be one of {', '.join(_prices_cloud.PROVIDERS)}",
            ),
            (isinstance(self.region, str) and bool(self.region), "region must be named"),
            (
                isinstance(self.machine_type, str) and bool(self.machine_type),
                "machine_type must be named",
            ),
            (_int(self.nodes) and self.nodes >= 1, "nodes must be an integer >= 1"),
            (bool(str(self.ledger)) and str(self.ledger) != ".", "ledger must name a file"),
            (_num(self.stop_cost) and self.stop_cost > 0, "stop_cost must be > 0"),
            (
                _num(self.max_cost) and _num(self.stop_cost) and self.max_cost >= self.stop_cost,
                "max_cost must be at least stop_cost",
            ),
            (
                _num(self.est_seconds_per_episode) and self.est_seconds_per_episode > 0,
                "est_seconds_per_episode must be > 0",
            ),
            (
                self.max_vcpus is None or (_int(self.max_vcpus) and self.max_vcpus >= 1),
                "max_vcpus must be an integer >= 1",
            ),
            (
                self.slots_per_node is None
                or (_int(self.slots_per_node) and self.slots_per_node >= 1),
                "slots_per_node must be an integer >= 1",
            ),
            (
                self.image is None or (isinstance(self.image, str) and bool(self.image)),
                "image must name a container image",
            ),
            (
                _num(self.idle_minutes) and 2 <= self.idle_minutes <= 60,
                "idle_minutes must be 2 to 60",
            ),
            (_num(self.boot_minutes) and self.boot_minutes >= 0, "boot_minutes must be >= 0"),
            (
                (self.usd_per_node_hour is None) == (self.price_asof is None),
                "usd_per_node_hour and price_asof are given together or not at all",
            ),
            (
                self.usd_per_node_hour is None
                or (_num(self.usd_per_node_hour) and self.usd_per_node_hour > 0),
                "usd_per_node_hour must be > 0",
            ),
            (
                self.price_asof is None
                or (isinstance(self.price_asof, str) and bool(self.price_asof)),
                "price_asof must say where and when the price was read",
            ),
            (
                self.disk_gb is None or (_int(self.disk_gb) and 10 <= self.disk_gb <= 2000),
                "disk_gb must be 10 to 2,000",
            ),
            (_int(self.func_cpu) and self.func_cpu >= 1, "func_cpu must be an integer >= 1"),
            (_int(self.func_ram) and self.func_ram >= 1, "func_ram must be an integer >= 1"),
            (_int(self.batch_size) and self.batch_size >= 1, "batch_size must be >= 1"),
            (_int(self.infra_retries) and self.infra_retries >= 0, "infra_retries must be >= 0"),
        ]
        for ok, message in checks:
            if not ok:
                raise ValueError(message)
        if self.episode_timeout is not None and not (
            _num(self.episode_timeout) and self.episode_timeout > 0
        ):
            raise ValueError("episode_timeout must be > 0 when given")
        if self.max_rollouts is not None and not (
            _int(self.max_rollouts) and self.max_rollouts >= 1
        ):
            raise ValueError("max_rollouts must be >= 1 when given")

    @classmethod
    def from_sweep_file(cls, path: Path) -> CloudOptions:
        """The sweep file's ``[cloud]`` table. A missing field is refused by name, and a relative
        ``ledger`` resolves against the sweep file's folder; an unknown one the strict spec
        refused already."""
        path = Path(path)
        with path.open("rb") as fh:
            table = tomllib.load(fh).get("cloud")
        if not isinstance(table, Mapping):
            raise ValueError(f"{path} has no [cloud] table")
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(table) - known)
        if unknown:
            raise ValueError(f"[cloud] has unknown field(s): {', '.join(unknown)}")
        required = [
            f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING
        ]
        missing = [name for name in required if name not in table]
        if missing:
            raise ValueError(f"[cloud] is missing required field(s): {', '.join(missing)}")
        values = dict(table)
        shown = str(values["ledger"])
        ledger = Path(shown)
        if not ledger.is_absolute():
            ledger = Path(os.path.abspath(path.parent / ledger))
        values["ledger"] = ledger
        if "packages" in values:
            values["packages"] = tuple(values["packages"])
        made = cls(**values)
        _SHOWN_LEDGER[made.ledger] = shown
        return made


#: The ledger as the spec names it, for the plan's lines (the path stays absolute in the options).
_SHOWN_LEDGER: dict[Path, str] = {}


def _shown_ledger(options: CloudOptions) -> str:
    return _SHOWN_LEDGER.get(options.ledger, str(options.ledger))


@dataclass(frozen=True)
class Resolved:
    """The options with Prove's table applied: the price, its source, the disk it prices and the
    machine's size."""

    usd_per_node_hour: float
    price_source: str
    vcpus: int
    slots_per_node: int
    max_vcpus: int
    image: str
    #: Each node's disk in GB as Prove's price counts it (the size the cluster software boots);
    #: None when the reader gives the price.
    disk_gb_priced: int | None = None


def resolve(options: CloudOptions) -> Resolved:
    """Prove's price for the region and machine type, or the override; the defaults that follow
    from the machine's vCPUs. Refuses a pair the table does not hold without the override."""
    provider = options.provider
    name = _prices_cloud.NAMES.get(provider, provider)
    row = _prices_cloud.price(provider, options.region, options.machine_type, options.disk_gb)
    vcpus = _prices_cloud.vcpus(provider, options.machine_type)
    if options.usd_per_node_hour is not None:
        if vcpus is None and (options.slots_per_node is None or options.max_vcpus is None):
            raise CloudRefusal(
                f"{options.machine_type} is not a machine type Prove knows the vCPUs of; give "
                "slots_per_node and max_vcpus in [cloud] with the price"
            )
        price = float(options.usd_per_node_hour)
        source = str(options.price_asof)
        disk = None
    elif row is None:
        types = _prices_cloud.machine_types(provider, options.region)
        if not types:
            raise CloudRefusal(
                f"{options.region} is not in Prove's {name} prices; the regions are "
                f"{', '.join(_prices_cloud.regions(provider))} (or give usd_per_node_hour and "
                "price_asof in [cloud])"
            )
        raise CloudRefusal(
            f"{options.machine_type} is not in Prove's {name} prices for {options.region}; "
            f"the machine types are {', '.join(types)}"
        )
    else:
        price = row.usd_per_node_hour
        source = f"Prove's {name} prices for {options.region} of {row.asof}"
        disk = row.disk_gb
    size = vcpus if vcpus is not None else int(options.max_vcpus or 1) // options.nodes
    slots = options.slots_per_node or max(1, size // options.func_cpu)
    ceiling = options.max_vcpus if options.max_vcpus is not None else options.nodes * size
    image = options.image or f"python:3.{sys.version_info.minor}"
    return Resolved(price, source, size, slots, ceiling, image, disk)


def _int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _bound_minutes(idle_minutes: float) -> float:
    """The larger of the nodes' own idle stop and the software's orphan rule."""
    return max(float(idle_minutes), _ORPHAN_MINUTES)


# ---------- cost ----------


def _batches(p: Plan, options: CloudOptions) -> int:
    return math.ceil(len(p.pairs) / options.batch_size) if p.pairs else 0


def estimate_cloud_cost(p: Plan, options: CloudOptions) -> float:
    """USD: the nodes, for as long as they are up, at Prove's price (or the override).

    ``nodes × usd_per_node_hour × (boot + waves × batch_size × est_seconds / 60 + idle) / 60``,
    with ``waves = ceil(batches / (nodes × slots_per_node))`` and every duration in minutes.
    """
    r = resolve(options)
    waves = math.ceil(_batches(p, options) / (options.nodes * r.slots_per_node))
    minutes = (
        options.boot_minutes
        + waves * options.batch_size * options.est_seconds_per_episode / 60
        + options.idle_minutes
    )
    return options.nodes * r.usd_per_node_hour * minutes / 60


def _charge(options: CloudOptions, elapsed_s: float) -> float:
    """A run's charge: its window plus both allowances in full, so the ledger reads high."""
    minutes = elapsed_s / 60 + options.boot_minutes + options.idle_minutes
    return options.nodes * resolve(options).usd_per_node_hour * minutes / 60


# ---------- the ledger ----------


class _Ledger:
    """One JSON-lines file per step. ``open`` and ``close`` lines are appended and fsynced, and
    never rewritten. A run whose ``open`` has no ``close`` counts as having spent its stop until
    it is closed; Prove closes one it finds left (``lost``)."""

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
                raise CloudBackendError(
                    f"ledger {self.path} line {number} is not JSON: {exc}"
                ) from exc
            if not isinstance(entry, dict):
                raise CloudBackendError(f"ledger {self.path} line {number} is not an object")
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

    def opened(self, run_id: str) -> dict[str, Any] | None:
        for entry in self.entries():
            if entry.get("event") == "open" and str(entry.get("run_id")) == run_id:
                return entry
        return None

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
    ledger: _Ledger, estimate: float, options: CloudOptions, *, exclude: str | None = None
) -> float:
    total = ledger.total(exclude=exclude)
    if total + estimate > options.max_cost:
        raise CloudCostGuard(
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
        raise CloudBackendError(f"cannot find package {name!r} to bundle: {exc}") from exc
    if spec is None or not spec.submodule_search_locations:
        raise CloudBackendError(
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


#: The reply is a pickle on the child's stdout, so the child keeps a copy of that pipe for the
#: reply alone and points file descriptor 1 at its stderr before anything of the target's runs:
#: what a rollout writes to stdout, at any level, cannot land in the reply.
_REHEARSAL = r"""
import os, pickle, sys, tarfile, io
reply = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)
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
reply.write(pickle.dumps(out))
reply.flush()
"""


def _comparable(result: Result) -> Any:
    if isinstance(result, str):
        return ("error", result.strip().splitlines()[-1] if result.strip() else "")
    if "error" in result:
        return ("error", str(result["error"]).strip().splitlines()[-1:])
    return {key: value for key, value in result.items() if key != "wall_time"}


def _rehearse(p: Plan, import_path: str, bundle: _Bundle, options: CloudOptions) -> tuple[Any, Any]:
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
        raise CloudBackendError(
            f"the rehearsal of job 0 in {view} failed to run:\n"
            + done.stderr.decode("utf-8", "replace")[-4000:]
        )
    kind, *rest = pickle.loads(done.stdout)
    if kind != "ok":
        missing = rest[1] if len(rest) > 1 else None
        detail = f"; the bundle does not carry {missing!r}" if missing else ""
        raise CloudBackendError(f"job 0 does not run in {view}: {rest[0]}{detail}")
    result: Result = rest[0]
    return result


def _head_line(options: CloudOptions, bundle: _Bundle) -> str:
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
    return f"Bundle: {', '.join(parts)} · {size_mb:.1f} MB · sha256 {bundle.sha256[:12]}…"


def preflight_cloud(p: Plan, import_path: str, options: CloudOptions, *, masked: str) -> str:
    """Build the bundle, check it covers the target, rehearse job 0 in the worker's view, read
    the ledger and estimate. Any refusal happens here; returns the block the caller prints. The cap
    refusal is raised last and carries the block as its ``plan`` attribute, so the command line
    can keep the plan on screen when it refuses."""
    spec = p.spec
    resolved = resolve(options)
    name = _prices_cloud.NAMES.get(options.provider, options.provider)
    bundle = _build_bundle(options.packages)
    carried = set(bundle.packages)
    uncovered = sorted(_local_imports(import_path) - carried)
    if uncovered:
        raise CloudBackendError(
            f"the bundle does not carry {', '.join(uncovered)}, which the target needs; add them "
            "to [cloud] packages"
        )
    installs = _local_installs()
    if installs:
        raise CloudBackendError(
            "this venv holds non-editable local installs a worker would lack: "
            f"{', '.join(installs)}; install them editable and add them to [cloud] packages, "
            "or install them from an index"
        )
    here, there = _rehearse(p, import_path, bundle, options)
    if here != there:
        raise CloudBackendError(
            f"job 0 differs between this machine and the worker's view:\n  here:   {here!r}\n"
            f"  worker: {there!r}"
        )
    ledger = _Ledger(options.ledger)
    estimate = estimate_cloud_cost(p, options)
    total = ledger.total()
    n = options.nodes
    chaos = spec.chaos
    chaos_line = (
        "Chaos: none"
        if chaos is None
        else f"Chaos: fault {chaos.fault} · rate {chaos.rate:g} · "
        f"steps {', '.join(chaos.steps) or '-'} · armed in each worker; "
        "every ok row carries what it armed"
    )
    source = (
        f"{n} × {options.machine_type} at ${resolved.usd_per_node_hour:g}/node-hour, "
        f"{resolved.price_source}"
    )
    lines = [
        f"Sweep: {len(spec.axis_types)} axes · {len(spec.configs)} cells · "
        f"N={spec.replicates} → {spec.total_rollouts()} rollouts",
        f"Backend: {_BACKEND} · {name} · target: {spec.target_id} · t_unit: {spec.t_unit}",
        f"Account: {name} {masked}, signed in with the {name} CLI",
        f"Cluster: Prove starts {n} × {options.machine_type} in {options.region} "
        f"({resolved.vcpus} vCPU each, {n * resolved.vcpus} in all, ceiling {resolved.max_vcpus}) "
        f"running {resolved.image}, and stops them when the sweep ends · "
        f"{resolved.slots_per_node} slots each · {n * resolved.slots_per_node} at once · "
        f"if this machine stops first, the nodes stop themselves within "
        f"{_bound_minutes(options.idle_minutes):g} min · this machine is kept from idle sleep "
        "while they run",
        _head_line(options, bundle),
        "Worker view: job 0 matches this machine",
        "Traffic: your code, its inputs and its results go between this machine and the nodes "
        "through Burla's relay (the cluster software Prove uses); the store stays on this machine",
        f"Cost: ~{_look.fmt_dollars(estimate)} this run ({source}) · "
        f"ledger {_shown_ledger(options)} {_look.fmt_dollars(total)} so far · "
        f"stop {_look.fmt_dollars(options.stop_cost)} · cap {_look.fmt_dollars(options.max_cost)}",
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
    except CloudCostGuard as exc:
        exc.plan = text  # type: ignore[attr-defined]
        raise
    return text


def plan_object(options: CloudOptions, *, masked: str, estimate: float) -> dict[str, Any]:
    """The plan's ``cloud`` object under ``--json``."""
    resolved = resolve(options)
    return {
        "provider": options.provider,
        "region": options.region,
        "machine_type": options.machine_type,
        "nodes": options.nodes,
        "max_vcpus": resolved.max_vcpus,
        "slots_per_node": resolved.slots_per_node,
        "image": resolved.image,
        "account": masked,
        "usd_per_node_hour": resolved.usd_per_node_hour,
        "price_asof": resolved.price_source,
        "disk_gb_priced": resolved.disk_gb_priced,
        "estimate": estimate,
        "idle_minutes": options.idle_minutes,
        "stop_cost": options.stop_cost,
        "max_cost": options.max_cost,
    }


# ---------- the launcher and the mapper ----------


def _launcher_argv() -> list[str]:
    """The command that starts the launcher. Tests point it at a fake."""
    return [sys.executable, "-I", str(Path(__file__).with_name("_cloud_submit.py"))]


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
    "JobStalled": "the job ended short; a Python mismatch shows up this way (the image must run "
    "this machine's 3.<minor>)",
    "NodesFailedToBoot": "the nodes failed to boot; the details are in the cluster software's log",
    "NoNodes": "no node of the cluster was ready when the job started",
    "NoCompatibleNodes": "no node fits func_cpu and func_ram; lower them in [cloud] or choose a "
    "larger machine_type",
    "UnsupportedLocalImport": "the cluster software refused the shipped code; the launcher must "
    "import nothing local",
    "FunctionTooBig": "the bundle is over the cluster software's 0.1 GB function limit",
}


class _CloudMapper:
    """A ``Mapper`` over the launcher: one launcher process, and one job call, per round."""

    def __init__(
        self,
        p: Plan,
        import_path: str,
        options: CloudOptions,
        resolved: Resolved,
        bundle: _Bundle,
        deadline: float,
        head_url: str,
        log: Path,
        cancel: threading.Event | None = None,
    ) -> None:
        self.p = p
        self.import_path = import_path
        self.options = options
        self.resolved = resolved
        self.bundle = bundle
        self.deadline = deadline
        self.head_url = head_url
        self.cancel = cancel
        self.software_log = log
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
                raise CloudBackendError(
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
            "pin": _PIN,
            "call": {
                "func_cpu": self.options.func_cpu,
                "func_ram": self.options.func_ram,
                "max_parallelism": self.options.nodes * self.resolved.slots_per_node,
            },
        }
        msg_r, msg_w = os.pipe()
        watch_r, watch_w = os.pipe()
        env = dict(os.environ)
        env["DISABLE_BURLA_TELEMETRY"] = "True"
        env["BURLA_CLUSTER_DASHBOARD_URL"] = self.head_url
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
                    if self.cancel is not None and self.cancel.is_set():
                        # A face with no terminal signal (the app) asked to stop: the job in
                        # flight is cancelled now, as a Ctrl-C cancels it, not waited for.
                        raise KeyboardInterrupt
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
                            yield k, CloudBackendError(f"worker failed: {failure}")
                        else:
                            self._agree(results)
                            yield k, results
                    elif kind == "exception":
                        _, name, text, index = message
                        exc = CloudBackendError(f"{name}: {text}")
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
                    raise CloudSpendStop(
                        f"run {self.p.run_id!r}: the launcher did not report after the stop and "
                        "was killed with its process group; the cluster is stopped next "
                        f"(ledger {self.options.ledger})"
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
            raise CloudNotInstalled(
                "the launcher cannot import the cluster software in this environment"
            )
        how = done[1]
        if how in ("complete", "interrupted"):
            for k in range(len(items)):
                if k not in seen:
                    yield k, stray.pop(0) if stray else CloudBackendError("no result returned")
            return
        if how == "stopped":
            raise CloudSpendStop(
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
            raise CloudBackendError(
                f"the launcher found the cluster software at {text}, and this backend is pinned "
                f"to {_PIN}: {_INSTALL_HINT}"
            )
        self._log(f"{name}: {text}")
        raise CloudBackendError(
            f"the cluster refused the run ({name}): "
            + (fix or f"the details are in {self.software_log}")
        )

    def _log(self, text: str) -> None:
        with contextlib.suppress(OSError):
            self.software_log.parent.mkdir(parents=True, exist_ok=True)
            with self.software_log.open("a", encoding="utf-8") as fh:
                fh.write(text.rstrip() + "\n")

    def _forward_ctrl_c(self, proc: subprocess.Popen[bytes], pipe: _Pipe) -> None:
        _signal(proc, signal.SIGINT)
        until = time.time() + _CANCEL_WAIT_S
        while time.time() < until:
            if any(m[0] == "done" for m in pipe.poll(_POLL_S)) or pipe.eof:
                return


class _ExternalCancel(CloudBackendError):
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


# ---------- the cluster software: the coordinator launcher and the CLI ----------


def _head_argv() -> list[str]:
    """The command that starts Prove's coordinator launcher (and the readiness probe). Tests
    point it at a fake."""
    return [sys.executable, "-I", str(Path(__file__).with_name("_cloud_head.py"))]


def _cli_argv() -> list[str]:
    """The cluster software's management CLI. Tests point it at a fake."""
    return [sys.executable, "-I", "-m", "burla"]


class _SoftwareError(Exception):
    """The cluster software answered an error: its code and its own text (for the log only)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _last_json(text: str) -> dict[str, Any] | None:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                loaded = json.loads(line)
            except ValueError:
                continue
            return loaded if isinstance(loaded, dict) else None
    return None


class _Software:
    """The cluster software for one account. Every process is started in a session of its own,
    so a terminal's Ctrl-C reaches Prove alone; the software's own text goes to ``log``."""

    def __init__(self, provider: str, account: str, region: str, log: Path) -> None:
        self.provider = provider
        self.account = account
        self.region = region
        self.log = log
        #: Whether the sweep was asked to stop by something other than a signal (the app's
        #: Ctrl-C, which is a key there). Asked while a call waits, and an interrupt then.
        self.interrupted: Callable[[], bool] | None = None

    def asked_to_stop(self) -> bool:
        return self.interrupted is not None and self.interrupted()

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("BURLA_PRIVATE", None)
        env["BURLA_CLOUD"] = self.provider
        if self.provider == "aws":
            env["AWS_REGION"] = self.region
        env["DISABLE_BURLA_TELEMETRY"] = "True"
        return env

    def note(self, text: str) -> None:
        try:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as fh:
                stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                fh.write(f"{stamp}  {text.rstrip()}\n")
        except OSError:
            pass

    def _run(self, argv: list[str], *, kill_on_interrupt: bool, timeout: float | None) -> str:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("ab") as log:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=log,
                start_new_session=True,
                env=self.env(),
            )
        out = b""
        until = None if timeout is None else time.time() + timeout
        try:
            assert proc.stdout is not None
            while True:
                ready, _, _ = select.select([proc.stdout], [], [], 0.1)
                if ready:
                    chunk = os.read(proc.stdout.fileno(), 1 << 16)
                    if not chunk:
                        break
                    out += chunk
                if until is not None and time.time() > until:
                    _killpg(proc)
                    raise _SoftwareError("TIMEOUT", f"{' '.join(argv[-3:])} did not answer")
                if self.asked_to_stop():
                    raise KeyboardInterrupt
            proc.wait()
        except KeyboardInterrupt:
            if kill_on_interrupt:
                _killpg(proc)
            raise
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
        text = out.decode("utf-8", "replace")
        self.note(text)
        return text

    def head(self, *args: str, timeout: float | None = 300) -> dict[str, Any]:
        text = self._run([*_head_argv(), *args], kill_on_interrupt=True, timeout=timeout)
        doc = _last_json(text)
        if doc is None:
            raise _SoftwareError(
                "HEAD_UNREACHABLE", f"the coordinator launcher said: {text[-2000:]}"
            )
        if doc.get("error"):
            raise _SoftwareError(
                str(doc.get("code") or "HEAD_UNREACHABLE"), str(doc.get("message"))
            )
        return doc

    def cli(
        self, url: str, *args: str, kill_on_interrupt: bool = True, timeout: float | None = 600
    ) -> dict[str, Any]:
        argv = [*_cli_argv(), "--head", url, *args]
        text = self._run(argv, kill_on_interrupt=kill_on_interrupt, timeout=timeout)
        doc = _last_json(text)
        if doc is None:
            raise _SoftwareError("TRANSPORT_ERROR", f"no answer from {' '.join(args)}")
        if not doc.get("ok"):
            error = doc.get("error") or {}
            raise _SoftwareError(str(error.get("code", "UNKNOWN")), str(error.get("message", "")))
        data = doc.get("data")
        return data if isinstance(data, dict) else {}

    def start_cli(self, url: str, *args: str) -> subprocess.Popen[bytes]:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("ab") as log:
            return subprocess.Popen(
                [*_cli_argv(), "--head", url, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=log,
                start_new_session=True,
                env=self.env(),
            )


def _listed(status: Mapping[str, Any]) -> int:
    counts = status.get("node_counts") or {}
    return int(sum(int(v) for v in counts.values())) if isinstance(counts, Mapping) else 0


def _alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _words(code: str, message: str, options: CloudOptions, log: Path) -> tuple[str, list[str]]:
    """The software's error in Prove's words, and the one next."""
    name = _prices_cloud.NAMES.get(options.provider, options.provider)
    region, machine = options.region, options.machine_type
    if code == "HEAD_UNREACHABLE" or "HEAD_UNREACHABLE" in message:
        return f"the cluster software did not start on this machine; the details are in {log}", []
    if "MissingDependency" in message or "botocore[crt]" in message:
        return (
            "the cloud extra is incomplete: signing in with aws login needs a package it installs",
            [_INSTALL_HINT],
        )
    if f"Not signed in to {name}" in message:
        return (
            f"the cluster could not start: this machine's {name} sign-in has expired or is missing",
            ["aws login"],
        )
    if "VcpuLimitExceeded" in message:
        return (
            f"your {name} account's vCPU quota in {region} is too small for {options.nodes} × "
            f"{machine}; lower nodes, or ask {name} for more",
            [],
        )
    if "INSUFFICIENT_INSTANCE_CAPACITY" in message:
        return (
            f"{name} has no {machine} capacity in {region} right now; try another machine type "
            "or region",
            [],
        )
    if "UnauthorizedOperation" in message:
        return f"your {name} sign-in is not allowed to start instances in {region}", []
    if "OptInRequired" in message:
        return f"your {name} account is not opted in to {region}", []
    if "Nodes cannot reach the head" in message or "its relay tunnel" in message:
        # The second is the coordinator's own start: its relay did not open in 15 s.
        return (
            "the cluster could not open its connection to this machine; check this machine's "
            "network and run the sweep again",
            [],
        )
    return (
        f"an unexpected failure inside poisson-prove ({code}); the details are in {log}",
        [],
    )


# ---------- the run ----------


def _placement(
    p: Plan,
    options: CloudOptions,
    resolved: Resolved,
    bundle: _Bundle,
    estimate: float,
    total: float,
    masked: str,
) -> dict[str, Any]:
    return {
        "cloud": {
            "provider": options.provider,
            "region": options.region,
            "machine_type": options.machine_type,
            "nodes": options.nodes,
            "slots_per_node": resolved.slots_per_node,
            "image": resolved.image,
            "max_vcpus": resolved.max_vcpus,
            "idle_minutes": options.idle_minutes,
            "usd_per_node_hour": resolved.usd_per_node_hour,
            "price_asof": resolved.price_source,
            "estimate": estimate,
            "ledger": str(options.ledger),
            "ledger_total": total,
            "stop_cost": options.stop_cost,
            "max_cost": options.max_cost,
            "func_cpu": options.func_cpu,
            "func_ram": options.func_ram,
            "boot_minutes": options.boot_minutes,
            "account": masked,
            "engine": dict(_ENGINE),
        },
        "bundle": bundle.record(),
    }


def _tell(on_cluster: Callable[[dict[str, Any]], None] | None, event: dict[str, Any]) -> None:
    if on_cluster is None:
        return
    with contextlib.suppress(BrokenPipeError, OSError, ValueError):
        on_cluster(event)


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Presses:
    """Ctrl-C, SIGTERM and SIGHUP during a cloud sweep, on the main thread.

    Until the stop begins, the first of them is an interrupt, and from that press on the stop is
    under way: no later press can interrupt the way to it. While the cluster stops, one press
    says once that Prove is stopping it, and the next leaves at once (the nodes then stop
    themselves, and the next cloud sweep finishes the stop)."""

    _SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)

    def __init__(self, on_cluster: Callable[[dict[str, Any]], None] | None, bound: float) -> None:
        self.on_cluster = on_cluster
        self.bound = bound
        self.stopping = False
        self.presses = 0
        self.previous: dict[int, Any] = {}

    def __enter__(self) -> _Presses:
        if threading.current_thread() is threading.main_thread():
            for sig in self._SIGNALS:
                self.previous[sig] = signal.signal(sig, self._pressed)
        return self

    def __exit__(self, *exc: object) -> None:
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)

    def stop_begins(self) -> None:
        self.stopping = True

    def _pressed(self, signum: int, frame: Any) -> None:
        if not self.stopping:
            self.stopping = True
            raise KeyboardInterrupt
        self.presses += 1
        if self.presses > 1:
            raise _LeftDuringStop
        _tell(
            self.on_cluster,
            {
                "phase": "note",
                "sentence": "stopping the cluster; press Ctrl-C again to leave it, and the "
                f"nodes will stop themselves within {self.bound:g} min",
            },
        )


class _Heartbeat:
    def __init__(self, record: Record) -> None:
        self.record = record
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._beat, daemon=True)

    def _beat(self) -> None:
        while not self.done.wait(_ALIVE_S):
            with contextlib.suppress(OSError):
                self.record.update(last_alive=time.time())

    def __enter__(self) -> _Heartbeat:
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.done.set()
        self.thread.join(timeout=5)


def _poll_off(software: _Software, url: str) -> tuple[bool, int]:
    """Status until the cluster is off with no node listed, up to ``_STOP_POLL_S``."""
    until = time.time() + _STOP_POLL_S
    listed = 0
    while True:
        try:
            status = software.cli(url, "cluster", "status", kill_on_interrupt=False, timeout=60)
            listed = _listed(status)
            if status.get("status") == "off" and listed == 0:
                return True, 0
        except _SoftwareError:
            pass
        if time.time() >= until:
            return False, listed
        time.sleep(min(1.0, max(0.05, _STOP_POLL_S / 20)))


def _limit_words(seconds: float) -> str:
    if seconds >= 60 and seconds % 60 == 0:
        return f"{int(seconds // 60)} min"
    return _look.fmt_duration(seconds)


def _unconfirmed(region: str, listed: int, seconds: float, *, spent: bool) -> CloudStopUnconfirmed:
    return CloudStopUnconfirmed(
        f"the nodes may still be running in {region}; Prove could not confirm they stopped "
        f"({listed} listed after {_limit_words(seconds)})",
        spent=spent,
    )


def _foreign(name: str, pid: object) -> CloudRefusal:
    return CloudRefusal(
        f"a cluster coordinator Prove did not start is running for this {name} account "
        f"(process {pid}); Prove does not change or stop what it did not start"
    )


def _port(url: str) -> int | None:
    found = re.search(r":(\d+)(?:/|$)", url)
    return int(found[1]) if found else None


def _coordinator(url: str, pid: int) -> dict[str, Any]:
    """What the record says of the coordinator Prove started."""
    return {"pid": pid, "url": url, "port": _port(url), "started_at": time.time()}


def _keep_head_log(record: Record, source: object) -> None:
    """The coordinator's own log, copied beside the record when the coordinator stops."""
    if not isinstance(source, str) or not source:
        return
    with contextlib.suppress(OSError):
        record.head_log_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, record.head_log_path)


def _stop_coordinator(
    software: _Software,
    record: Record,
    pid: int,
    on_cluster: Callable[[dict[str, Any]], None] | None,
) -> bool:
    """Stop the coordinator Prove started and keep its log. Whether it is gone: one that is not
    is said once, and the record, left as it is, hands it to the next cloud sweep."""
    gone = False
    try:
        answer = software.head("stop", software.provider, software.account, str(pid))
    except _SoftwareError as exc:
        software.note(f"coordinator stop: {exc.code}: {exc.message}")
    else:
        _keep_head_log(record, answer.get("log"))
        gone = bool(answer.get("stopped", True))
    if gone or not _alive(pid):
        return True
    _tell(
        on_cluster,
        {
            "phase": "note",
            "sentence": "the cluster software Prove started on this machine did not stop "
            f"(process {pid}); the next cloud sweep stops it",
        },
    )
    return False


def _finish_leftover(
    found: Mapping[str, Any],
    software: _Software,
    record: Record,
    name_of: Callable[[str], str],
    on_cluster: Callable[[dict[str, Any]], None] | None,
) -> None:
    """A record not ``stopped`` is a sweep that died. Stop its nodes and its coordinator, close
    its ledger line ``lost`` at an upper bound, and say so once. When the stop cannot be
    confirmed the record is left as it is, and the sweep that found it is refused."""
    name = _prices_cloud.NAMES.get(software.provider, software.provider)
    run_id = str(found.get("run_id"))
    ledger = _Ledger(Path(str(found.get("ledger"))))
    opened = ledger.opened(run_id)
    region = str((opened or {}).get("region") or software.region)
    recorded = found.get("coordinator")
    pid = recorded.get("pid") if isinstance(recorded, Mapping) else None
    began = time.time()
    try:
        head = software.head("find", software.provider, software.account)
        if head.get("alive") and pid is not None and head.get("pid") == pid:
            # Its coordinator outlived it: the nodes are stopped through it.
            url = str(head["url"])
            software.cli(url, "cluster", "stop", kill_on_interrupt=False)
            confirmed, listed = _poll_off(software, url)
        elif head.get("alive"):
            raise _foreign(name, head.get("pid"))
        else:
            # Its coordinator is gone: one is started only to ask what is listed, and stop it.
            started = software.head("start", software.provider, software.account)
            url, pid = str(started["url"]), int(started["pid"])
            record.update(coordinator=_coordinator(url, pid))
            confirmed, listed = True, _listed(software.cli(url, "cluster", "status"))
            if listed:
                software.cli(url, "cluster", "stop", kill_on_interrupt=False)
                confirmed, listed = _poll_off(software, url)
    except _SoftwareError as exc:
        software.note(f"stopping what an earlier sweep left: {exc.code}: {exc.message}")
        raise _unconfirmed(region, 0, time.time() - began, spent=False) from None
    if not confirmed:
        raise _unconfirmed(region, listed, _STOP_POLL_S, spent=False)
    assert isinstance(pid, int)
    if not _stop_coordinator(software, record, pid, on_cluster):
        raise _unconfirmed(region, 0, time.time() - began, spent=False)
    since = float((opened or {}).get("start") or found.get("started_at") or began)
    if opened is not None and run_id in ledger.unclosed():
        last_alive = float(found.get("last_alive") or since)
        minutes = (
            (last_alive - since) / 60
            + _bound_minutes(float(opened.get("idle_minutes", 5.0)))
            + float(opened.get("boot_minutes", 5.0))
        )
        rate = int(opened.get("nodes", 1)) * float(opened.get("usd_per_node_hour", 0.0))
        charge = rate * minutes / 60
        ledger.close(run_id=run_id, end=time.time(), charge=charge, ended="lost")
        spent = f"charged {_look.fmt_dollars(charge)} to the ledger as an upper bound"
    else:
        spent = "its ledger line was closed when it ended"
    record.update(state="stopped")
    up_since = datetime.fromtimestamp(since, UTC).strftime("%H:%MZ")
    _tell(
        on_cluster,
        {
            "phase": "note",
            "sentence": f'the cluster from the sweep of "{name_of(run_id)}" had not stopped; '
            f"Prove stopped it (up since {up_since}, {spent})",
        },
    )


def finish_what_was_left(
    provider: str,
    account: str,
    region: str,
    *,
    name_of: Callable[[str], str],
    on_cluster: Callable[[dict[str, Any]], None] | None,
) -> None:
    """Stop what an earlier sweep left on this account, as the next cloud sweep would; for the
    verb that only says where sweeps run."""
    record = Record(provider, account)
    found = record.read()
    if not found or found.get("state") == "stopped":
        return
    owner = found.get("pid")
    name = _prices_cloud.NAMES.get(provider, provider)
    if _alive(owner) and owner != os.getpid():
        raise CloudRefusal(
            f"another sweep is running on this {name} account from this machine (process {owner})"
        )
    software = _Software(provider, account, region, record.log_path)
    _finish_leftover(found, software, record, name_of, on_cluster)


def _start_nodes(
    software: _Software,
    url: str,
    options: CloudOptions,
    booted_at: float,
    on_cluster: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    """``cluster start``, which answers when every node is ready, with the starting line's
    count asked of the status every ``_STATUS_S`` meanwhile. Returns the software's answer."""

    def starting(ready: int) -> None:
        _tell(
            on_cluster,
            {
                "phase": "starting",
                "nodes": options.nodes,
                "ready": ready,
                "machine_type": options.machine_type,
                "region": options.region,
                "seconds": time.time() - booted_at,
            },
        )

    starting(0)
    proc = software.start_cli(url, "cluster", "start")
    out = b""
    asked = time.time()
    try:
        assert proc.stdout is not None
        while True:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if ready:
                chunk = os.read(proc.stdout.fileno(), 1 << 16)
                if not chunk:
                    break
                out += chunk
            if software.asked_to_stop():
                raise KeyboardInterrupt  # the booting nodes are stopped by the stop that follows
            if time.time() - asked >= _STATUS_S:
                asked = time.time()
                with contextlib.suppress(_SoftwareError):
                    counts = software.cli(url, "cluster", "status", timeout=60).get("node_counts")
                    if isinstance(counts, Mapping):
                        starting(int(counts.get("ready", 0)) + int(counts.get("running", 0)))
        proc.wait()
    except BaseException:
        _killpg(proc)
        raise
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    text = out.decode("utf-8", "replace")
    software.note(text)
    return _last_json(text) or {}


def run_cloud(
    p: Plan,
    import_path: str,
    store: Store,
    *,
    options: CloudOptions,
    account: str,
    on_progress: Callable[[int, int], None] | None = None,
    on_cluster: Callable[[dict[str, Any]], None] | None = None,
    name_of: Callable[[str], str] | None = None,
    cancel: threading.Event | None = None,
) -> RunSummary:
    """Start the cluster, run the plan on it through the launcher into ``store``, and stop
    everything Prove started, however the sweep ends.

    ``on_cluster`` is told the cluster's phases (``starting``, ``ready``, ``stopping``,
    ``stopped``), each ``note`` for the reader, and once, after a confirmed stop, the
    ``summary`` the result shows. ``name_of`` gives a run's name for a note about an earlier
    sweep. ``cancel``, once set, is a Ctrl-C from a face that gets no signal (the terminal
    app): whatever is under way (the coordinator's start, the boot, the job) is interrupted at
    once, the cluster is stopped, and the ledger's line closes ``cancelled``."""
    resolved = resolve(options)
    name = _prices_cloud.NAMES.get(options.provider, options.provider)
    masked = mask(account)
    name_of = name_of or (lambda run: run)
    record = Record(options.provider, account)
    software = _Software(options.provider, account, options.region, record.log_path)
    ledger = _Ledger(options.ledger)
    estimate = estimate_cloud_cost(p, options)

    # One sweep per account at a time; then what an earlier sweep left; then what Prove did not
    # start. All of it before anything of this sweep is recorded or started.
    found = record.read()
    if found and found.get("state") != "stopped":
        owner = found.get("pid")
        if _alive(owner) and owner != os.getpid():
            raise CloudRefusal(
                f"another sweep is running on this {name} account from this machine "
                f"(process {owner})"
            )
        _finish_leftover(found, software, record, name_of, on_cluster)
    try:
        head = software.head("find", options.provider, account)
    except _SoftwareError as exc:
        software.note(f"coordinator find: {exc.code}: {exc.message}")
        line, nexts = _words(exc.code, exc.message, options, record.log_path)
        raise CloudStartError(line, nexts) from None
    if head.get("alive"):
        raise _foreign(name, head.get("pid"))
    total = _check_cap(ledger, estimate, options)
    bundle = _build_bundle(options.packages)
    if p.produced_by is not None:
        p = dataclasses.replace(
            p, produced_by={**p.produced_by, "bundle": {"sha256": bundle.sha256}}
        )

    start = time.time()
    rate = options.nodes * resolved.usd_per_node_hour / 3600
    allowances = (options.boot_minutes + options.idle_minutes) * 60
    deadline = start + max(0.0, (options.stop_cost - total) / rate - allowances)
    life = _Life()
    ended = "error"
    stop: CloudSpendStop | None = None
    summary: RunSummary | None = None
    failure: BaseException | None = None

    def worded(exc: _SoftwareError, *, started: bool = False) -> CloudStartError:
        line, nexts = _words(exc.code, exc.message, options, record.log_path)
        return CloudStartError(line, nexts, started=started)

    with _Presses(on_cluster, _bound_minutes(options.idle_minutes)) as presses:
        # ``cancel`` is the interrupt of a face that gets no signal. It interrupts the way a
        # press does: until the stop begins, and never the stop itself.
        software.interrupted = lambda: (
            cancel is not None and cancel.is_set() and not presses.stopping
        )
        try:
            try:
                if software.asked_to_stop():
                    raise KeyboardInterrupt
                # The record and the ledger, before anything is started.
                record.write(
                    state="starting",
                    pid=os.getpid(),
                    run_id=p.run_id,
                    ledger=str(options.ledger),
                    started_at=start,
                    last_alive=start,
                    nodes=options.nodes,
                    coordinator=None,
                    cluster_id=None,
                    software_version=_PIN,
                )
                life.recorded = True
                ledger.open(
                    run_id=p.run_id,
                    start=start,
                    estimate=estimate,
                    nodes=options.nodes,
                    machine_type=options.machine_type,
                    usd_per_node_hour=resolved.usd_per_node_hour,
                    price_asof=resolved.price_source,
                    stop_cost=options.stop_cost,
                    max_cost=options.max_cost,
                    provider=options.provider,
                    region=options.region,
                    account=masked,
                    idle_minutes=options.idle_minutes,
                    boot_minutes=options.boot_minutes,
                )
                life.opened = True
                # The coordinator.
                life.asked = True
                try:
                    started = software.head("start", options.provider, account)
                except _SoftwareError as exc:
                    software.note(f"coordinator start: {exc.code}: {exc.message}")
                    raise worded(exc) from None
                life.url, life.head_pid = str(started["url"]), int(started["pid"])
                record.update(coordinator=_coordinator(life.url, life.head_pid))
                # Nothing Prove did not ask for.
                try:
                    status = software.cli(life.url, "cluster", "status")
                except _SoftwareError as exc:
                    raise worded(exc) from None
                if _listed(status) or int(status.get("active_job_count") or 0):
                    life.leave_nodes = True
                    raise CloudRefusal(
                        f"the cluster on this {name} account has nodes or jobs Prove did not "
                        "start; Prove does not change or stop what it did not start"
                    )
                # The cluster's shape.
                shape = [
                    *("--region", options.region),
                    *("--machine-type", options.machine_type),
                    *("--quantity", str(options.nodes)),
                    *("--image", resolved.image),
                    *(() if options.disk_gb is None else ("--disk-gb", str(options.disk_gb))),
                    *("--inactivity-timeout-seconds", str(round(options.idle_minutes * 60))),
                    *("--max-vcpus", str(resolved.max_vcpus)),
                ]
                try:
                    software.cli(life.url, "settings", "update", *shape)
                except _SoftwareError as exc:
                    raise worded(exc) from None
                # The nodes: from here some may be up, and billed.
                life.booted_at = time.time()
                life.any_node = True
                answer = _start_nodes(software, life.url, options, life.booted_at, on_cluster)
                if not answer.get("ok"):
                    error = answer.get("error")
                    error = error if isinstance(error, Mapping) else {}
                    with contextlib.suppress(_SoftwareError):
                        now = software.cli(life.url, "cluster", "status")
                        life.any_node = _listed(now) > 0
                    raise worded(
                        _SoftwareError(
                            str(error.get("code", "UNKNOWN")), str(error.get("message", ""))
                        ),
                        started=life.any_node,
                    )
                record.update(state="running", last_alive=time.time())
                _tell(
                    on_cluster,
                    {
                        "phase": "ready",
                        "nodes": options.nodes,
                        "vcpus": options.nodes * resolved.vcpus,
                        "seconds": time.time() - life.booted_at,
                    },
                )
                # The job, at the coordinator Prove started.
                mapper = _CloudMapper(
                    p,
                    import_path,
                    options,
                    resolved,
                    bundle,
                    deadline,
                    life.url,
                    record.log_path,
                    cancel,
                )
                runner_options = ModalOptions(
                    batch_size=options.batch_size,
                    episode_timeout=options.episode_timeout,
                    infra_retries=options.infra_retries,
                    max_rollouts=options.max_rollouts,
                )

                def cost_check(plan: Plan) -> None:
                    _check_cap(ledger, estimate, options, exclude=plan.run_id)

                with _Heartbeat(record):
                    summary = run_with_mapper(
                        p,
                        mapper,
                        store,
                        options=runner_options,
                        on_progress=on_progress,
                        backend=_BACKEND,
                        placement=_placement(p, options, resolved, bundle, estimate, total, masked),
                        cost_check=cost_check,
                    )
                ended = "stopped" if summary.stopped_by == FIRST_BATCH_ERRORED else "complete"
            finally:
                # From here a press no longer interrupts: the stop below always runs.
                presses.stop_begins()
        except CloudSpendStop as exc:
            ended = "stopped"
            stop = exc
        except (KeyboardInterrupt, _ExternalCancel) as exc:
            ended = "cancelled"
            failure = exc
        except BaseException as exc:  # noqa: BLE001 - stopped below, then raised as it came
            failure = exc
            if cancel is not None and cancel.is_set():
                # The face's cancel reached the runner between two batches: the same ending.
                ended = "cancelled"
        # Always, whatever happened above.
        stopped_at = _stop_all(
            software, record, ledger, options, p.run_id, start, life, ended, on_cluster
        )
    if life.booted_at is not None and stopped_at is not None:
        _tell(
            on_cluster,
            {
                "phase": "summary",
                "provider": options.provider,
                "region": options.region,
                "machine_type": options.machine_type,
                "nodes": options.nodes,
                "started": _iso(life.booted_at),
                "stopped": _iso(stopped_at),
                "up_seconds": stopped_at - life.booted_at,
                "charge": _charge(options, stopped_at - start),
            },
        )
    if failure is not None:
        if life.any_node and isinstance(failure, ExecutorError):
            # Nodes were started: work started and money spent, whatever was stored.
            failure.spent = True  # type: ignore[attr-defined]
        raise failure
    if stop is not None:
        charge = _charge(options, (stopped_at or time.time()) - start)
        raise CloudSpendStop(
            f"run {p.run_id!r} stopped at {_usd(charge)} against the stop "
            f"{_usd(options.stop_cost)} (ledger {options.ledger}); the stored batches stay, and "
            f"--resume {p.run_id} continues it once the stop is raised in the sweep file. {stop}"
        ) from stop
    assert summary is not None
    return summary


@dataclass
class _Life:
    """What one sweep has started so far, for the stop that follows every ending."""

    recorded: bool = False
    opened: bool = False
    asked: bool = False
    url: str | None = None
    head_pid: int | None = None
    leave_nodes: bool = False
    booted_at: float | None = None
    any_node: bool = False


def _stop_all(
    software: _Software,
    record: Record,
    ledger: _Ledger,
    options: CloudOptions,
    run_id: str,
    start: float,
    life: _Life,
    ended: str,
    on_cluster: Callable[[dict[str, Any]], None] | None,
) -> float | None:
    """Stop the nodes, confirm it, stop the coordinator, mark the record, close the ledger.
    Returns when the stop was confirmed (None when no coordinator ever answered); raises when
    it could not be confirmed, with the record left ``stopping`` for the next cloud sweep."""

    def close(how: str, end: float) -> None:
        if life.opened:
            ledger.close(run_id=run_id, end=end, charge=_charge(options, end - start), ended=how)

    if life.url is None or life.head_pid is None:
        # No coordinator answered. One the launcher began before it failed or was interrupted
        # is still Prove's own: none was running for this account when the sweep began.
        left: Mapping[str, Any] = {}
        if life.asked:
            with contextlib.suppress(_SoftwareError):
                left = software.head("find", software.provider, software.account)
        pid = left.get("pid")
        gone = True
        if left.get("alive") and isinstance(pid, int):
            record.update(state="stopping", coordinator=_coordinator(str(left.get("url")), pid))
            gone = _stop_coordinator(software, record, pid, on_cluster)
        if life.recorded and gone:
            record.update(state="stopped")
        close(ended, time.time())
        return None
    record.update(state="stopping")
    if life.booted_at is not None:
        _tell(on_cluster, {"phase": "stopping"})
    began = time.time()
    confirmed, listed = True, 0
    if not life.leave_nodes:
        try:
            software.cli(life.url, "cluster", "stop", kill_on_interrupt=False, timeout=None)
            confirmed, listed = _poll_off(software, life.url)
        except _SoftwareError as exc:
            software.note(f"cluster stop: {exc.code}: {exc.message}")
            confirmed = False
            with contextlib.suppress(_SoftwareError):
                listed = _listed(
                    software.cli(life.url, "cluster", "status", kill_on_interrupt=False)
                )
    if not confirmed:
        close("error", time.time())
        seconds = _STOP_POLL_S if listed else time.time() - began
        raise _unconfirmed(options.region, listed, seconds, spent=True)
    if _stop_coordinator(software, record, life.head_pid, on_cluster):
        record.update(state="stopped")
    stopped_at = time.time()
    close(ended, stopped_at)
    if life.booted_at is not None:
        _tell(
            on_cluster,
            {"phase": "stopped", "nodes": options.nodes, "seconds": stopped_at - life.booted_at},
        )
    return stopped_at


def mask(account: str) -> str:
    """The account as the plan, the manifest and the ledger show it: first and last four."""
    return f"{account[:4]}…{account[-4:]}" if len(account) > 8 else account
