import functools
import re
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from poisson_prove.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures"
#: PF3 (spec sections 8.8 and 14): the quickstart's one copy is the packaged spec.
PACKAGED_QUICKSTART = Path(__file__).resolve().parents[1] / "src" / "poisson_prove" / "examples" / "quickstart.toml"


@functools.cache
def quickstart_design(replicates: int = 100) -> Path:
    """The packaged quickstart's design (its target id, unit and axes) at ``replicates``, with no
    ``target`` and no ``[declare]``, written once per process to a temporary file.

    PF3 (spec sections 8.8 and 14): ``examples/quickstart.toml`` is gone and the packaged spec runs
    194 replicates (Q56). The frozen tests that swept the old file sweep this: the one copy's
    design at the 100 replicates their numbers were frozen at, the target typed as before, and
    nothing declared, as the old file declared nothing.
    """
    import json
    import tempfile
    import tomllib

    doc = tomllib.loads(PACKAGED_QUICKSTART.read_text(encoding="utf-8"))
    lines = [f"target_id = {json.dumps(doc['target_id'])}", f"t_unit = {json.dumps(doc['t_unit'])}", f"replicates = {replicates}"]
    for name, axis in doc["axes"].items():
        lines += ["", f"[axes.{name}]", f"type = {json.dumps(axis['type'])}", f"values = {json.dumps(axis['values'])}"]
    path = Path(tempfile.mkdtemp(prefix="quickstart-design-")) / "quickstart.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


#: PF3 (spec section 4.4, Q17's condition): each test's own name, which no output named before PF3.
METHOD_OWN_NAMES = ("Fisher", "McNemar", "log-rank")


def without_method_lines(text: str) -> str:
    """``text`` (``report.md``, ``receipt.html``, the served page) with the lines that name the test
    by its own name taken out, and in their place no second blank line.

    PF3 (spec section 4.4, PF3.6b, reading p): every surface names the method it used, on a line
    of its own; nothing before PF3 printed Fisher, McNemar or log-rank, so a frozen digest over one
    of these files holds over this. Removing a line never leaves two blank lines where it was:
    a paragraph of its own (the line and the blank line after it) goes as a whole.
    """
    out: list[str] = []
    removed = False
    for line in text.splitlines(keepends=True):
        if any(name in line for name in METHOD_OWN_NAMES):
            removed = True
            continue
        if removed and not line.strip() and out and not out[-1].strip():
            removed = False
            continue
        removed = False
        out.append(line)
    return "".join(out)



#: PF5 (spec section 4.3, the report header's ``NAME (ID)`` pairing; PF5's reading o): the header
#: of ``report.md`` and ``receipt.html`` names each run as ``before  NAME (ID)`` and ``after  NAME
#: (ID)``, and the provenance list no longer gives the ids, so each id is in each file once.
_RUN_LINE = re.compile(r"^(?:<p>)?(?:before|after)  .+ \([^()]+\)(?:</p>)?$")
_RUN_ID_ITEM = re.compile(r"<li>run id [ab]: [^<]*</li>")
_RUN_ID_LINE = re.compile(r"^- run id [ab]: .*$")


def without_run_lines(text: str) -> str:
    """``text`` (``report.md``, ``receipt.html``) with the header's two run lines and the
    provenance list's two run-id entries taken out, and in place of the run lines no second blank
    line: the bytes a file had before the pairing, and what the library's render gives without
    its run-id entries."""
    out: list[str] = []
    removed = False
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n")
        if _RUN_LINE.match(bare) or _RUN_ID_LINE.match(bare):
            removed = True
            continue
        if removed and not line.strip() and out and not out[-1].strip():
            removed = False
            continue
        removed = False
        out.append(_RUN_ID_ITEM.sub("", line))
    return "".join(out)

#: PF9.4 (spec section 13.1): every module that drives a remote backend offline runs with network
#: sockets blocked in the pytest process (the interpreters the Burla and Modal fakes start arm
#: their own tripwire). ``test_pf9_backends`` checks that no such module is left out.
NETWORK_BLOCKED_MODULES = frozenset({
    "test_a10_declared", "test_bu_burla_backend", "test_m10_cli", "test_m10_multi", "test_m11a_chaos",
    "test_m3_capture", "test_m3_crash_trace", "test_m3_modal", "test_m3_modal_launch",
    "test_m3_timeout_trace", "test_mc_modal_chaos", "test_pf1_look", "test_pf9_backends",
    "test_pr1_pair_assertion", "test_s23_power",
})
#: A module that drives a backend but must serve on a local socket, with its reason.
NETWORK_EXEMPT_MODULES = {
    "test_pf0_name": "test_pf0_12 serves the comparison page on a loopback socket and reads it back",
}


class NetworkBlocked(OSError):
    """A network connection or name lookup was attempted in a module that runs offline."""


def network_blocked_for(module: str) -> bool:
    return module.rsplit(".", 1)[-1] in NETWORK_BLOCKED_MODULES


@pytest.fixture(autouse=True)
def blocked_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """In a guarded module: every socket other than a Unix one refuses to connect or send, and every
    name lookup refuses, with ``NetworkBlocked``; each attempt is recorded, and a test that made one
    fails at teardown even if the code under test swallowed the error. Elsewhere: nothing."""
    attempts: list[str] = []
    if not network_blocked_for(request.module.__name__):
        yield attempts
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refuse(what: str) -> NetworkBlocked:
        attempts.append(what)
        return NetworkBlocked(f"network blocked in an offline backend test: {what}")

    def connect(self: socket.socket, address: Any) -> None:
        if self.family != socket.AF_UNIX:
            raise refuse(f"connect {address!r}")
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if self.family != socket.AF_UNIX:
            raise refuse(f"connect_ex {address!r}")
        return real_connect_ex(self, address)

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        raise refuse(f"create_connection {address!r}")

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> list[Any]:
        raise refuse(f"getaddrinfo {host!r}")

    def lookup(host: Any) -> Any:
        raise refuse(f"name lookup {host!r}")

    real_sendto = socket.socket.sendto

    def sendto(self: socket.socket, data: Any, *args: Any) -> int:
        if self.family != socket.AF_UNIX:
            raise refuse(f"sendto {args[-1]!r}")
        return real_sendto(self, data, *args)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", lookup)
    monkeypatch.setattr(socket, "gethostbyname_ex", lookup)
    monkeypatch.setattr(socket.socket, "sendto", sendto)
    yield attempts
    assert attempts == [], f"network attempted in an offline backend test: {attempts}"


@functools.cache
def writable_copy(fixture: Path) -> Path:
    """A copy, made once per test process, of a committed fixture folder, for the tests that run a
    verb which writes into the store it reads.

    PF12 (spec section 18.2, Q59): ``report`` and ``serve`` save the comparison they show into the
    store's ``.poisson/``. Run on a committed fixture in place, under ``-n`` one worker's save would
    land while another digests or copies the same folder; so those tests read a copy, named as the
    fixture is, and the committed folders are never written. The copy is removed when the process
    ends.
    """
    import atexit
    import shutil
    import tempfile

    base = Path(tempfile.mkdtemp(prefix="prove-fixture-"))
    atexit.register(shutil.rmtree, base, True)
    copy = base / fixture.name
    shutil.copytree(fixture, copy, symlinks=True)
    return copy


@pytest.fixture(scope="session")
def lattice_store() -> Store:
    """The generated lattice pair (``tests/lattice.py``), built once per machine and version, checked before
    any test runs, when a process first asks for it and again when the session ends."""
    import lattice

    return Store(lattice.root())


class SharedTrees:
    """The lattice pair's comparisons and trees, each computed once per test session and shared
    between xdist workers: the first worker to ask computes it under a lock and leaves a pickle,
    and every later request, in any worker, loads its own copy, so no test sees another's edits.
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._memo: dict[str, bytes] = {}
        self._kept: dict[str, Any] = {}

    def frames(self) -> tuple[Any, Any, Any, Any]:
        """``(a, b, manifest_a, manifest_b)``: both runs read with ``meta=False``."""
        import lattice

        store = Store(lattice.root())
        return (store.read(lattice.RUN_A, meta=False), store.read(lattice.RUN_B, meta=False),
                store.manifest(lattice.RUN_A), store.manifest(lattice.RUN_B))

    def multi(self, events: tuple[str, ...] | None, method: str, **knobs: Any) -> Any:
        """``multi_diff`` over the pair with both manifests, for ``events`` under ``method``."""
        return self._get(("multi", events, method, sorted(knobs.items())), lambda: self._multi(events, method, knobs))

    def tree(self, events: tuple[str, ...] | None, method: str, **knobs: Any) -> Any:
        """``tree.tree`` beside ``multi(events, method)``, with ``knobs`` (``by``,
        ``n_permutations``, ``seed``, ``max_group_mde``, ``depth``) as given."""
        def build() -> Any:
            from poisson_prove import tree as tree_mod

            a, b, ma, mb = self.frames()
            return tree_mod.tree(a, b, self.multi(events, method), manifest_a=ma, manifest_b=mb, **knobs)

        return self._get(("tree", events, method, sorted(knobs.items())), build)

    def _multi(self, events: tuple[str, ...] | None, method: str, knobs: dict[str, Any]) -> Any:
        import warnings

        from poisson_prove.diff import UnpairedAnalysis, multi_diff

        a, b, ma, mb = self.frames()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UnpairedAnalysis)
            return multi_diff(a, b, events=None if events is None else list(events), method=method,
                              manifest_a=ma, manifest_b=mb, **knobs)

    def _get(self, key: Any, build: Any) -> Any:
        import fcntl
        import hashlib
        import pickle

        import copy

        name = hashlib.sha256(repr(key).encode()).hexdigest()[:20]
        if name in self._kept:
            return copy.deepcopy(self._kept[name])
        if name not in self._memo:
            path = self.folder / f"{name}.pickle"
            with open(self.folder / f"{name}.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if not path.is_file():
                    value = build()
                    try:
                        data = pickle.dumps(value)
                    except (pickle.PicklingError, AttributeError, TypeError):
                        # A result this build cannot pickle is kept in this process alone, built
                        # once per worker, and every caller still gets a copy of its own.
                        self._kept[name] = value
                        return copy.deepcopy(value)
                    staging = path.with_name(f".{name}.{__import__('os').getpid()}")
                    staging.write_bytes(data)
                    staging.replace(path)
            self._memo[name] = path.read_bytes()
        return pickle.loads(self._memo[name])


@pytest.fixture(scope="session")
def lattice_trees(tmp_path_factory: pytest.TempPathFactory) -> SharedTrees:
    """The session's shared comparisons and trees over the lattice pair (``SharedTrees``)."""
    base = tmp_path_factory.getbasetemp()
    root = base.parent if base.name.startswith("popen-gw") else base
    folder = root / "lattice-trees"
    folder.mkdir(exist_ok=True)
    return SharedTrees(folder)


def pytest_configure(config: pytest.Config) -> None:
    """Check both generated stores before any test runs, rebuilding one that fails (a crash or an
    earlier session left it), then mark them checked for this session and its workers: from here
    on a store that fails was written by a test, and ``lattice.cached_store`` refuses it."""
    if hasattr(config, "workerinput"):
        return
    import os

    import lattice
    import replay_arms

    os.environ.pop(lattice.CHECKED, None)
    lattice.root()
    replay_arms.root()
    os.environ[lattice.CHECKED] = "1"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the session if a test wrote into a generated store; then remove the bundle folders the
    Burla tests' fake workers unpacked and could not remove.

    The lattice pair and the replay arms are shared by every test and every worker, so a test
    that writes into one changes what every later test reads. Each store's files are checked
    against the digests written with it, in every process, worker or not.

    A worker process holds its folder for its life and removes it at exit or when another bundle
    replaces it (``proofload._burla_submit``), but the fake pool ends its workers with SIGKILL, so
    the last pool's folders outlive them. Their temporary directory is what an interpreter with an
    empty environment gets, which is not this process's. Only a folder whose owner is gone is
    removed: a live worker of any other session still holds its lock.
    """
    import subprocess
    import sys

    import lattice
    import replay_arms

    changed = [module.__name__ for module in (lattice, replay_arms) if not module.unchanged()]
    if changed:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        message = f"a test wrote into the generated store of {', '.join(changed)}; see tests/lattice.py"
        if reporter is not None:
            reporter.write_line(f"ERROR {message}", red=True)
        else:
            print(f"ERROR {message}", file=sys.stderr)

    from poisson_prove._burla_submit import _PREFIX, _reap

    probe = subprocess.run(
        [sys.executable, "-I", "-S", "-c", "import tempfile; print(tempfile.gettempdir())"],
        env={}, capture_output=True, text=True, timeout=60,
    )
    tmp = probe.stdout.strip()
    if probe.returncode == 0 and tmp and any(
        entry.name.startswith(_PREFIX) for entry in Path(tmp).iterdir()
    ):
        _reap(tmp, None)


# ---------- PF12's shared stores (tests/pf12_support.py), built once per session when a test asks ----------


@pytest.fixture(scope="session")
def old_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """The 0.0.1 store with its quickstart pair saved and its UI built (PF12)."""
    from pf12_support import build_old, shared_world

    return shared_world(tmp_path_factory, "old", build_old)


@pytest.fixture(scope="session")
def stats_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """The hand-written pairs, each saved, and their UI (PF12)."""
    from pf12_support import build_stats, shared_world

    return shared_world(tmp_path_factory, "stats", build_stats)


@pytest.fixture(scope="session")
def sweep_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """Runs a 0.1.0 sweep wrote, with their event logs, and their UI (PF12)."""
    from pf12_support import build_sweep, shared_world

    return shared_world(tmp_path_factory, "sweep", build_sweep)


@pytest.fixture(scope="session")
def bytes_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """Every writing verb run in turn over a copy of the 0.0.1 store, with its digests (PF12.1)."""
    from pf12_support import build_bytes, shared_world

    return shared_world(tmp_path_factory, "bytes", build_bytes)


@pytest.fixture(scope="session")
def resume_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """A 0.0.1 partial run resumed by this build (PF12.1's one exception)."""
    from pf12_support import build_resume_old, shared_world

    return shared_world(tmp_path_factory, "resume-old", build_resume_old)


def pytest_addoption(parser: pytest.Parser) -> None:
    """``--update-snapshots``: the snapshot tests write the snapshots instead of comparing against
    them (section 10.6, PF12.13; the one documented command is in ``CONTRIBUTING.md``)."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="rewrite the snapshot files the snapshot tests compare against, instead of comparing",
    )


def _lattice_through_its_copy() -> None:
    """PF12 (spec section 18.2, Q59; R39): ``report`` and ``serve`` save into the store they read,
    so every test that reads the generated lattice pair (``tests/lattice.py``) reads this process's
    copy of it (``writable_copy``): ``lattice.root()`` hands out the copy, made on first use.
    ``lattice.intact()`` checks both stores: the one the generator wrote, which no test writes, and
    this process's copy, whose every file and folder outside ``.poisson/`` (where the verbs save)
    must still be the generator's."""
    import json

    import lattice

    generated, generated_intact = lattice.root, lattice.intact
    _GENERATOR[:] = [generated, generated_intact]
    copied = functools.cache(lambda: writable_copy(generated()))

    def intact() -> bool:
        home, copy = generated().parent, copied()
        sums = json.loads((home / "SHA256SUMS.json").read_text(encoding="utf-8"))
        outside = [p for p in copy.rglob("*") if p.relative_to(copy).parts[0] != ".poisson"]
        files = {rel: digest for rel, digest in lattice._digests(copy).items() if Path(rel).parts[0] != ".poisson"}
        folders = {str(p.relative_to(copy)) for p in outside if p.is_dir()}
        expected = {str(parent) for rel in sums for parent in Path(rel).parents if parent != Path(".")}
        return lattice._matches(home) and files == sums and folders == expected

    lattice.root = copied  # type: ignore[assignment]
    lattice.intact = intact  # type: ignore[assignment]


#: The generator's own ``root`` and ``intact``, for the tests of the generator itself.
_GENERATOR: list[Any] = []
_lattice_through_its_copy()


@pytest.fixture(autouse=True)
def _the_generator_reads_its_own_store(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """The generator's own oracle (``test_s3_golden_fixture``) checks the store the generator wrote
    and how it rebuilds one, so its tests read the generator's ``root`` and ``intact`` themselves."""
    if request.module.__name__.rsplit(".", 1)[-1] == "test_s3_golden_fixture":
        import lattice

        monkeypatch.setattr(lattice, "root", _GENERATOR[0])
        monkeypatch.setattr(lattice, "intact", _GENERATOR[1])
