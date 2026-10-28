import ast
import functools
import io
import os
import re
import socket
import tokenize
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import settings

from poisson_prove.store import Store

#: Every property test is the same run every time and is never timed: its examples are drawn from
#: a fixed seed, no example has a deadline, and no database replays an earlier run's failures.
settings.register_profile("prove", derandomize=True, deadline=None, database=None)
settings.load_profile("prove")

FIXTURES = Path(__file__).resolve().parent / "fixtures"
#: PF3: the quickstart's one copy is the packaged spec.
PACKAGED_QUICKSTART = Path(__file__).resolve().parents[1] / "src" / "poisson_prove" / "examples" / "quickstart.toml"


@functools.cache
def quickstart_design(replicates: int = 100) -> Path:
    """The packaged quickstart's design (its target id, unit and axes) at ``replicates``, with no
    ``target`` and no ``[declare]``, written once per process to a temporary file that is removed
    when the process ends.

    PF3: the packaged spec runs 194 replicates. The tests whose numbers are pinned at 100
    replicates sweep this instead: the packaged design at 100 replicates, the target typed on
    the command line, and nothing declared.
    """
    import atexit
    import json
    import shutil
    import tempfile
    import tomllib

    doc = tomllib.loads(PACKAGED_QUICKSTART.read_text(encoding="utf-8"))
    lines = [f"target_id = {json.dumps(doc['target_id'])}", f"t_unit = {json.dumps(doc['t_unit'])}", f"replicates = {replicates}"]
    for name, axis in doc["axes"].items():
        lines += ["", f"[axes.{name}]", f"type = {json.dumps(axis['type'])}", f"values = {json.dumps(axis['values'])}"]
    base = Path(tempfile.mkdtemp(prefix="quickstart-design-"))
    atexit.register(shutil.rmtree, base, True)
    path = base / "quickstart.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


#: PF3: each statistical test's own name, which every surface prints on a line of its own.
METHOD_OWN_NAMES = ("Fisher", "McNemar", "log-rank")
#: A step row of ``inspect``'s text output: the step's index, then eight more tab-separated
#: columns.
STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")


def skip_if_still_writable(folder: Path) -> None:
    """Skip the test when ``folder``, whose mode now forbids writing, can still be written: root ignores
    a folder's mode, so as root no folder is one the test cannot write."""
    import tempfile

    try:
        handle, probe = tempfile.mkstemp(dir=folder)
    except PermissionError:
        return
    os.close(handle)
    os.unlink(probe)
    pytest.skip(f"{folder} can be written although its mode forbids it (as root can)")


def blas_thread_cap() -> dict[str, str]:
    """The BLAS thread cap the suite runs under, for a child whose environment is built from nothing:
    without it an old OpenBLAS (numpy at its floor) runs a thread on every core in every child."""
    return {name: os.environ[name] for name in ("OPENBLAS_NUM_THREADS",) if name in os.environ}


def without_method_lines(text: str) -> str:
    """``text`` (``report.md``, ``receipt.html``, the served page) with the lines that name the test
    by its own name taken out, and in their place no second blank line.

    PF3.6b: every surface names the method it used, on a line of its own; a digest pinned over
    one of these files is taken over this, so it guards everything but those lines. Removing a
    line never leaves two blank lines where it was: a paragraph of its own (the line and the blank
    line after it) goes as a whole.
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



#: PF5 (the report header's ``NAME (ID)`` pairing): the header
#: of ``report.md`` and ``receipt.html`` names each run as ``before  NAME (ID)`` and ``after  NAME
#: (ID)``, and the provenance list does not give the ids, so each id is in each file once.
_RUN_LINE = re.compile(r"^(?:<p>)?(?:before|after)  .+ \([^()]+\)(?:</p>)?$")
_RUN_ID_ITEM = re.compile(r"<li>run id [ab]: [^<]*</li>")
_RUN_ID_LINE = re.compile(r"^- run id [ab]: .*$")


def without_run_lines(text: str) -> str:
    """``text`` (``report.md``, ``receipt.html``) with the header's two run lines and the
    provenance list's two run-id entries taken out, and in place of the run lines no second blank
    line: what a pinned digest of the file is taken over, and what the library's render gives
    without its run-id entries."""
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

#: Every test runs with network sockets blocked in the pytest process (PF9.4 for the modules that
#: drive a remote backend offline; PF10 for all the rest). The interpreters the Burla and Modal fakes
#: start arm their own tripwire. A module whose tests serve on a loopback socket and read it back is
#: listed here with its reason; its tests may reach 127.0.0.1, ::1 and localhost, and nothing else.
LOOPBACK_MODULES = {
    "test_m13_viewer": "the viewer's tests serve the page on a loopback port and request it",
    "test_pf0_name": "test_pf0_12 serves the comparison page on a loopback socket and reads it back",
    "test_pf2_names": "serve's tests read the page they serve on a loopback port",
    "test_pf3_first_run": "pf3_6 reads the page serve puts up on a loopback port",
    "test_pf8_public_hygiene": "pf8_4 reads the quickstart's served page on a loopback port",
}
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _importable(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


#: A test that runs OpenTelemetry's SDK (capture, the stamper): skipped, saying so, where the
#: ``[agent]`` extra is not installed. Only the tests that need it carry it.
needs_otel = pytest.mark.skipif(not _importable("opentelemetry.sdk"), reason="capture lives behind the [agent] extra")


class NetworkBlocked(OSError):
    """A network connection or name lookup was attempted in a test."""


def loopback_allowed_for(module: str) -> bool:
    return module.rsplit(".", 1)[-1] in LOOPBACK_MODULES


@pytest.fixture(autouse=True)
def blocked_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """In every test: every socket other than a Unix one refuses to connect or send, and every name
    lookup refuses, with ``NetworkBlocked``, except to a loopback host in a module listed in
    ``LOOPBACK_MODULES``; each attempt is recorded, and a test that made one fails at teardown even if
    the code under test swallowed the error."""
    attempts: list[str] = []
    loopback = loopback_allowed_for(request.module.__name__)
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo
    real_gethostbyname = socket.gethostbyname
    real_gethostbyname_ex = socket.gethostbyname_ex
    real_sendto = socket.socket.sendto

    def local(address: Any) -> bool:
        return loopback and isinstance(address, tuple) and bool(address) and address[0] in LOOPBACK_HOSTS

    def refuse(what: str) -> NetworkBlocked:
        attempts.append(what)
        return NetworkBlocked(f"network blocked in a test: {what}")

    def connect(self: socket.socket, address: Any) -> None:
        if self.family != socket.AF_UNIX and not local(address):
            raise refuse(f"connect {address!r}")
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if self.family != socket.AF_UNIX and not local(address):
            raise refuse(f"connect_ex {address!r}")
        return real_connect_ex(self, address)

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        if not local(address):
            raise refuse(f"create_connection {address!r}")
        return real_create_connection(address, *args, **kwargs)

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if not (loopback and host in LOOPBACK_HOSTS):
            raise refuse(f"getaddrinfo {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    def gethostbyname(host: Any) -> Any:
        if not (loopback and host in LOOPBACK_HOSTS):
            raise refuse(f"name lookup {host!r}")
        return real_gethostbyname(host)

    def gethostbyname_ex(host: Any) -> Any:
        if not (loopback and host in LOOPBACK_HOSTS):
            raise refuse(f"name lookup {host!r}")
        return real_gethostbyname_ex(host)

    def sendto(self: socket.socket, data: Any, *args: Any) -> int:
        if self.family != socket.AF_UNIX and not local(args[-1]):
            raise refuse(f"sendto {args[-1]!r}")
        return real_sendto(self, data, *args)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", gethostbyname)
    monkeypatch.setattr(socket, "gethostbyname_ex", gethostbyname_ex)
    monkeypatch.setattr(socket.socket, "sendto", sendto)
    yield attempts
    assert attempts == [], f"network attempted in a test: {attempts}"


@pytest.fixture(autouse=True)
def _a_capture_install_ends_with_its_test() -> Iterator[None]:
    """Prove's capture installs once per process. A test that runs a capture sweep in the pytest
    worker itself leaves that install behind, and a child a later test forks from the worker
    inherits it and records no trace (test_defaults_refusals_and_faces's missing-instrumentor test,
    then the storage tests' capture routes). An install the test itself made is undone after it;
    one a module fixture made before the test stays."""
    import poisson_prove.capture as capture

    before = (capture._STATUS, capture._BUCKET)
    yield
    if before[0] is None and capture._STATUS is not None:
        capture._STATUS, capture._BUCKET = before


def shared(tmp_path_factory: pytest.TempPathFactory, name: str, build: Callable[[Path], Any]) -> Any:
    """``build(folder)`` once per test session, however many ``-n`` workers ask: the first to ask
    builds into a folder of the session's own base and pickles what ``build`` returns, and every
    other worker waits for it and reads the pickle. ``build`` writes every file it makes under
    ``folder``; what it returns names paths there, which every worker can read. For a module
    fixture whose tests only read what it built."""
    import fcntl
    import pickle
    import shutil

    base = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        base = base.parent
    folder, value = base / f"shared-{name}", base / f"shared-{name}.pickle"
    with open(base / f"shared-{name}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not value.exists():
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True)
            built = build(folder)
            staged = value.with_suffix(".staged")
            staged.write_bytes(pickle.dumps(built))
            staged.replace(value)
            return built
    return pickle.loads(value.read_bytes())


@functools.cache
def writable_copy(fixture: Path) -> Path:
    """A copy, made once per test process, of a committed fixture folder, for the tests that run a
    verb which writes into the store it reads.

    PF12: ``report`` and ``serve`` save the comparison they show into the
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


def _a_home_of_its_own() -> None:
    """The suite runs with ``HOME`` in a folder of its own, made once for the session and shared
    with its workers, so what a test provokes (the errors log and the record of compared runs
    under ``~/.cache/poisson-prove``) never reaches the user's own. The tools the slow tests run
    keep their folders: uv's cache and Pythons, pyenv's, and Playwright's browsers, and the opt-in
    backend tests still find the user's Modal credentials. A suite this one starts (the floors run)
    keeps the folder it was given."""
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    if os.environ.get("PROVE_TESTS_HOME"):
        return
    real = os.environ.get("HOME")
    if real:
        caches = "Library/Caches" if sys.platform == "darwin" else ".cache"
        keep = {"PLAYWRIGHT_BROWSERS_PATH": Path(real) / caches / "ms-playwright", "PYENV_ROOT": Path(real) / ".pyenv"}
        uv = shutil.which("uv")
        for var, args in (("UV_CACHE_DIR", ("cache", "dir")), ("UV_PYTHON_INSTALL_DIR", ("python", "dir"))):
            found = subprocess.run([uv, *args], capture_output=True, text=True, timeout=60) if uv else None
            if found is not None and found.returncode == 0 and found.stdout.strip():
                keep[var] = Path(found.stdout.strip())
        for var, path in keep.items():
            if var not in os.environ and path.exists():
                os.environ[var] = str(path)
    os.environ["HOME"] = os.environ["PROVE_TESTS_HOME"] = tempfile.mkdtemp(prefix="prove-tests-home-")
    _MADE_HOME.append(os.environ["HOME"])
    # The opt-in backend tests read the user's Modal credentials from ``~/.modal.toml``.
    credentials = Path(real) / ".modal.toml" if real else None
    if credentials is not None and credentials.is_file():
        (Path(os.environ["HOME"]) / ".modal.toml").symlink_to(credentials)


#: The ``HOME`` this process made, which only it removes.
_MADE_HOME: list[str] = []
#: Hypothesis's folder in this process, which only it removes.
_MADE_HYPOTHESIS: list[str] = []


def _a_hypothesis_folder_of_its_own() -> None:
    """Hypothesis keeps what it learns from the source in a folder of this process's own, removed
    with the process, not in ``.hypothesis/`` in the working directory."""
    import tempfile

    from hypothesis.configuration import set_hypothesis_home_dir

    _MADE_HYPOTHESIS.append(tempfile.mkdtemp(prefix="prove-hypothesis-"))
    set_hypothesis_home_dir(_MADE_HYPOTHESIS[-1])


def pytest_configure(config: pytest.Config) -> None:
    """Check both generated stores before any test runs, rebuilding one that fails (a crash or an
    earlier session left it), then mark them checked for this session and its workers: from here
    on a store that fails was written by a test, and ``lattice.cached_store`` refuses it. First,
    the session's own ``HOME`` (``_a_home_of_its_own``). Every process, worker or not, gets its own
    Hypothesis folder."""
    _a_hypothesis_folder_of_its_own()
    if hasattr(config, "workerinput"):
        return
    _a_home_of_its_own()
    import os

    import lattice
    import replay_arms

    os.environ.pop(lattice.CHECKED, None)
    lattice.root()
    replay_arms.root()
    os.environ[lattice.CHECKED] = "1"


def pytest_unconfigure(config: pytest.Config) -> None:
    """The session's own ``HOME`` goes with the session that made it, and each process's Hypothesis
    folder with that process."""
    import shutil

    for home in (*_MADE_HOME, *_MADE_HYPOTHESIS):
        shutil.rmtree(home, ignore_errors=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the session if a test wrote into a generated store; then remove the bundle folders the
    Burla tests' fake workers unpacked and could not remove.

    The lattice pair and the replay arms are shared by every test and every worker, so a test
    that writes into one changes what every later test reads. Each store's files are checked
    against the digests written with it, in every process, worker or not.

    A worker process holds its folder for its life and removes it at exit or when another bundle
    replaces it (``poisson_prove._burla_submit``), but the fake pool ends its workers with SIGKILL, so
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
    them (PF6.14 and PF12.13; the one documented command is in ``CONTRIBUTING.md``)."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="rewrite the snapshot files the snapshot tests compare against, instead of comparing",
    )


def _lattice_through_its_copy() -> None:
    """PF12: ``report`` and ``serve`` save into the store they read,
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
    """The generator's own frozen test (``test_s3_golden_fixture``) checks the store the generator wrote
    and how it rebuilds one, so its tests read the generator's ``root`` and ``intact`` themselves."""
    if request.module.__name__.rsplit(".", 1)[-1] == "test_s3_golden_fixture":
        import lattice

        monkeypatch.setattr(lattice, "root", _GENERATOR[0])
        monkeypatch.setattr(lattice, "intact", _GENERATOR[1])
def code_of(source: str) -> str:
    """``source`` with its comments and docstrings taken out and its blank lines dropped: the code
    a change to words alone leaves as it was.

    A digest pinned over a symbol's source or a test file's bytes is taken over this, so
    rewording a comment or docstring in ``src/`` or in a frozen test leaves it as it was; it moves
    only when code does."""
    lines = io.StringIO(source, newline="\n").readlines()

    def column(row: int, byte_col: int) -> int:
        return len(lines[row - 1].encode("utf-8")[:byte_col].decode("utf-8"))

    cuts = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                cuts.append((first.lineno, column(first.lineno, first.col_offset), first.end_lineno, column(first.end_lineno, first.end_col_offset)))
    cuts += [(*tok.start, *tok.end) for tok in tokenize.generate_tokens(io.StringIO(source).readline) if tok.type == tokenize.COMMENT]
    rows = [line.rstrip("\n") for line in lines]
    for r0, c0, r1, c1 in sorted(cuts, reverse=True):
        rows[r0 - 1:r1] = [rows[r0 - 1][:c0] + rows[r1 - 1][c1:]]
    return "\n".join(row.rstrip() for row in rows if row.strip())
