"""Oracle for the M3 modal launch amendment (S19): invariants L1-L14.

The two things the S18 pilot could not do: launch a Modal sweep for a target that only
imports inside its container, and let a credential reach that container by name. Nothing here
touches the network. ``run_modal`` is exercised offline for the first time, through a fake
``modal`` module installed in ``sys.modules`` for the test's duration (L11, L12); everything
else goes through the mapper seam or ``cli.main`` in-process. Every store lives under
``tmp_path``.

Conventions this oracle fixes for the implementation session:

- The deterministic rollout is the M3 oracle's, formula included, so L11 compares the fake
  ``run_modal`` run with ``run_with_mapper`` like with like under a shared salt.
- The M10 oracle's ``MODAL_TABLES`` text and its ``run_modal`` capture are restated below;
  test modules never import each other.
- The L1 refusing module is written to ``tmp_path`` and appended to ``sys.path`` by the test
  that needs it. It is never a real module under ``tests/``.
- The L4 mapper runs ``worker_batch`` in-process, catches the worker's exception and yields
  ``(k, exc)``; it never raises from the generator. Calls are counted per batch by the tuple
  of plan indices, the M3 oracle's convention.
- The fake ``modal`` exposes exactly the surface spec section 3 pins and records every call
  it receives; ``Secret.from_dict`` and ``Secret.from_local_environ`` record rather than
  raise, so L11 reports a violation instead of crashing on it. Its ``map`` yields outputs in
  reversed order so completion order is exercised.
- The canary is a fresh ``secrets.token_hex(16)`` per test, placed in ``os.environ`` through
  ``monkeypatch.setenv`` and never handed to Proofload on purpose.
- L3 and L13 read source files through ``proofload.__file__``, never the working directory.
- Helpers build plans, stores, sweep files and fakes. They never assert.
"""

import ast
import contextlib
import dataclasses
import importlib
import importlib.machinery
import importlib.util
import json
import re
import sys
import types
from collections.abc import Iterator, Sequence
from io import StringIO
from pathlib import Path
from secrets import token_hex
from typing import Any

import pandas as pd
import pytest

import poisson_prove
import poisson_prove.cli as cli
import poisson_prove.executor_modal as executor_modal
from poisson_prove.episode import Episode
from poisson_prove.executor import Plan, RunSummary, plan, run_local
from poisson_prove.executor_modal import (
    ImageSpec,
    Job,
    ModalOptions,
    ModalTarget,
    Result,
    preflight_modal,
    run_modal,
    run_with_mapper,
    worker_batch,
)
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store

HORIZON = 10.0
CELLS = ({"x": 0.1}, {"x": 0.2}, {"x": 0.3})
REPLICATES = 4
TOTAL = len(CELLS) * REPLICATES
BATCH = 5
SALT = "launch-salt"
TARGET_ID = "policy@test"
T_UNIT = "steps"

DET_PATH = f"{__name__}:deterministic_rollout"
MOCK_MODULE = "poisson_prove.examples.mock_agent"
WELL_SHAPED = f"{MOCK_MODULE}:rollout"  # any well-shaped path; the modal branch never imports it
MISSING_MODULE_PATH = "poisson_prove.examples.no_such_module_xyz:rollout"
MISSING_ATTR_PATH = f"{MOCK_MODULE}:no_such_attr"

REFUSING_MODULE = "proofload_oracle_refusing_target"
BOUNDARY_VAR = "PROOFLOAD_TEST_BOUNDARY"
CANARY_VAR = "PROOFLOAD_ORACLE_CANARY"

PACKAGE = Path(poisson_prove.__file__).resolve().parent
CLI_SOURCE = PACKAGE / "cli.py"
MODAL_SOURCE = PACKAGE / "executor_modal.py"

PRE_AMENDMENT_FIELDS = frozenset({
    "concurrency", "batch_size", "episode_timeout", "infra_retries", "max_rollouts",
    "max_cost", "est_seconds_per_episode", "app_name",
})
FUNCTION_KWARGS = frozenset({
    "image", "gpu", "timeout", "retries", "max_containers", "serialized", "secrets",
})
IMAGE_KEYS = frozenset({"python", "pip", "apt", "dockerfile", "local_packages", "gpu"})
# S18 P12's pins, restated: the __all__ list and the public names executor_modal defines itself.
MODAL_EXPORTS = [
    "CostGuard", "ImageSpec", "Job", "Mapper", "ModalBackendError", "ModalNotInstalled",
    "ModalOptions", "ModalTarget", "Result", "estimate_cost", "preflight_modal", "run_modal",
    "run_with_mapper", "worker_batch",
]
MODAL_PUBLIC = frozenset({
    "CostGuard", "ImageSpec", "ModalBackendError", "ModalNotInstalled", "ModalOptions",
    "ModalTarget", "estimate_cost", "preflight_modal", "run_modal", "run_with_mapper",
    "worker_batch",
})
CLI_PUBLIC = frozenset({"main"})

SWEEP_HEADER = """
target_id = "launch@test"
t_unit = "steps"
replicates = 2

[axes.x]
type = "continuous"
values = [0.1, 0.2]
"""

# The M10 oracle's fixture text, verbatim: a [modal] table with every scalar and no secrets key.
MODAL_TABLES = """
[modal]
concurrency = 4
batch_size = 32
episode_timeout = 12.5
infra_retries = 1
max_cost = 100.0
est_seconds_per_episode = 0.5
app_name = "from-table"

[modal.image]
python = "3.12"
pip = ["numpy", "pandas"]
gpu = "T4"

[modal.image-gpu]
python = "3.11"
pip = ["torch"]
gpu = "A10G"
"""

SECRETS_TABLE = '\n[modal]\nsecrets = ["golden-pilot", "second"]\n'
# A unique alphanumeric bare string: an implementation that tuple()s it gets ("a", "b", "c"),
# three names that pass every rule, so only a refusal of the bare str itself keeps this red.
BARE_STRING_TABLE = '\n[modal]\nsecrets = "abc"\n'

# The pilot's shape: a module that refuses to import outside its container.
REFUSING_SOURCE = f'''"""L1's target: importable only where {BOUNDARY_VAR}=container is set."""
import os

if os.environ.get("{BOUNDARY_VAR}") != "container":
    raise RuntimeError("{REFUSING_MODULE} imports only inside the container")


def rollout(cfg, seed):
    raise NotImplementedError("never called by this oracle")
'''


# ---------- the deterministic rollout (the M3 oracle's formula) ----------


def _outcome(cfg: dict[str, Any], seed: int) -> str:
    return "fell" if (seed + int(cfg["x"] * 10)) % 3 == 0 else "survived"


def deterministic_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    outcome = _outcome(cfg, seed)
    return Episode(outcome=outcome, t=3.0 if outcome == "fell" else HORIZON, horizon=HORIZON)


# ---------- mappers ----------

Batches = Sequence[Sequence[Job]]
Yielded = tuple[int, list[Result] | BaseException]


def _batch_key(jobs: Sequence[Job]) -> tuple[int, ...]:
    return tuple(job[2] for job in jobs)


def in_process_mapper(batches: Batches) -> Iterator[Yielded]:
    """Runs every batch through ``worker_batch`` locally, in submission order."""
    for index, jobs in enumerate(batches):
        yield index, worker_batch(jobs, DET_PATH, None)


class ResolveFailingMapper:
    """Runs ``worker_batch`` in-process against ``import_path``. A worker that raises becomes
    the batch's yielded exception; the generator itself never raises. Calls are counted per
    batch by the tuple of its jobs' plan indices."""

    def __init__(self, import_path: str) -> None:
        self.import_path = import_path
        self.calls: dict[tuple[int, ...], int] = {}

    def __call__(self, batches: Batches) -> Iterator[Yielded]:
        for index, jobs in enumerate(batches):
            key = _batch_key(jobs)
            self.calls[key] = self.calls.get(key, 0) + 1
            payload: list[Result] | BaseException
            try:
                payload = worker_batch(jobs, self.import_path, None)
            except Exception as exc:
                payload = exc
            yield index, payload


# ---------- the fake modal ----------


class FakeSecret:
    """What a ``Secret`` constructor returns: a distinct sentinel per call."""

    def __init__(self, origin: str, name: str) -> None:
        self.origin = origin
        self.name = name

    def __repr__(self) -> str:
        return f"FakeSecret({self.origin}, {self.name!r})"


@dataclasses.dataclass
class ModalRecords:
    """Everything the fake saw, in call order."""

    app_names: list[str] = dataclasses.field(default_factory=list)
    function_kwargs: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    from_name_calls: list[str] = dataclasses.field(default_factory=list)
    from_name_returned: list[FakeSecret] = dataclasses.field(default_factory=list)
    from_dict_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = dataclasses.field(default_factory=list)
    from_local_environ_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = dataclasses.field(default_factory=list)
    image_calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = dataclasses.field(default_factory=list)
    map_calls: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def secret_calls(self) -> tuple[Any, ...]:
        return (self.from_name_calls, self.from_dict_calls, self.from_local_environ_calls)


class FakeImage:
    """Records ``apt_install``, ``pip_install`` and ``add_local_python_source``; each returns
    ``self``. Nothing else is defined, so any other method is an AttributeError."""

    def __init__(self, records: ModalRecords, origin: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.records = records
        self.records.image_calls.append((origin, args, dict(kwargs)))

    def apt_install(self, *args: Any, **kwargs: Any) -> "FakeImage":
        self.records.image_calls.append(("apt_install", args, dict(kwargs)))
        return self

    def pip_install(self, *args: Any, **kwargs: Any) -> "FakeImage":
        self.records.image_calls.append(("pip_install", args, dict(kwargs)))
        return self

    def add_local_python_source(self, *args: Any, **kwargs: Any) -> "FakeImage":
        self.records.image_calls.append(("add_local_python_source", args, dict(kwargs)))
        return self


class FakeImageFactory:
    """``modal.Image``."""

    def __init__(self, records: ModalRecords) -> None:
        self.records = records

    def debian_slim(self, *args: Any, **kwargs: Any) -> FakeImage:
        return FakeImage(self.records, "debian_slim", args, kwargs)

    def from_dockerfile(self, *args: Any, **kwargs: Any) -> FakeImage:
        return FakeImage(self.records, "from_dockerfile", args, kwargs)


class FakeSecretFactory:
    """``modal.Secret``. ``from_name`` records the name and returns a distinct sentinel; the
    two passthrough constructors record that they were called and return one too."""

    def __init__(self, records: ModalRecords) -> None:
        self.records = records

    def from_name(self, name: str, *args: Any, **kwargs: Any) -> FakeSecret:
        self.records.from_name_calls.append(name)
        secret = FakeSecret("from_name", name)
        self.records.from_name_returned.append(secret)
        return secret

    def from_dict(self, *args: Any, **kwargs: Any) -> FakeSecret:
        self.records.from_dict_calls.append((args, dict(kwargs)))
        return FakeSecret("from_dict", "")

    def from_local_environ(self, *args: Any, **kwargs: Any) -> FakeSecret:
        self.records.from_local_environ_calls.append((args, dict(kwargs)))
        return FakeSecret("from_local_environ", "")


class FakeFunction:
    """What ``app.function(...)`` wraps a function into. ``map`` runs it in-process on every
    item and yields the outputs in reversed order, so completion order is exercised."""

    def __init__(self, fn: Any, records: ModalRecords) -> None:
        self.fn = fn
        self.records = records

    def map(self, items: Any, **kwargs: Any) -> Iterator[Any]:
        self.records.map_calls.append(dict(kwargs))
        for item in reversed(list(items)):
            yield self.fn(item)


class FakeApp:
    """``modal.App(name)``; ``function(**kwargs)`` records the kwargs and returns a decorator;
    ``run()`` is a no-op context manager."""

    def __init__(self, records: ModalRecords, name: str, *args: Any, **kwargs: Any) -> None:
        self.records = records
        self.records.app_names.append(name)

    def function(self, **kwargs: Any) -> Any:
        self.records.function_kwargs.append(dict(kwargs))

        def decorate(fn: Any) -> FakeFunction:
            return FakeFunction(fn, self.records)

        return decorate

    def run(self) -> Any:
        return contextlib.nullcontext()


class FakeModal(types.ModuleType):
    """The ``modal`` module ``run_modal`` imports inside its body: ``App``, ``Image``,
    ``Secret``, and nothing else. Install with ``monkeypatch.setitem(sys.modules, "modal", fake)``."""

    def __init__(self) -> None:
        super().__init__("modal")
        self.records = ModalRecords()
        self.Image = FakeImageFactory(self.records)
        self.Secret = FakeSecretFactory(self.records)

    def App(self, name: str, *args: Any, **kwargs: Any) -> FakeApp:
        return FakeApp(self.records, name, *args, **kwargs)


def _secret_objects_in(value: Any) -> list[FakeSecret]:
    """Every ``FakeSecret`` reachable through lists, tuples, sets and dict values."""
    if isinstance(value, FakeSecret):
        return [value]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [s for item in value for s in _secret_objects_in(item)]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _secret_objects_in(item)]
    return []


def _image_secret_objects(records: ModalRecords) -> list[FakeSecret]:
    return [s for _, args, kwargs in records.image_calls for s in _secret_objects_in((args, kwargs))]


# ---------- the CLI harness (the M10 oracle's, restated) ----------


@dataclasses.dataclass(frozen=True)
class CliResult:
    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        return self.out + self.err


def run_cli(argv: Sequence[str]) -> CliResult:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return CliResult(code, out.getvalue(), err.getvalue())


class CapturedRunModal:
    """Stands in for ``cli.run_modal``: records the call and returns a complete summary."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ModalTarget, Store, ModalOptions | None]] = []

    def __call__(
        self,
        p: Any,
        target: ModalTarget,
        store: Store,
        *,
        options: ModalOptions | None = None,
        on_progress: Any = None,
    ) -> RunSummary:
        self.calls.append((p, target, store, options))
        return RunSummary(
            run_id=p.run_id,
            n_ok=len(p.pairs),
            n_errored=0,
            n_timeout=0,
            wall_time=0.0,
            stopped_by=None,
            complete=True,
        )


@pytest.fixture
def captured_run_modal(monkeypatch: pytest.MonkeyPatch) -> CapturedRunModal:
    # A missing modal package is now refused before the plan, so modal must import here.
    monkeypatch.setitem(sys.modules, "modal", importlib.util.module_from_spec(importlib.machinery.ModuleSpec("modal", None)))
    captured = CapturedRunModal()
    # PF5 (spec section 17; PF5.7): the face runs no backend; the core calls the Modal runner, so
    # the stand-in replaces it where it is defined, which the core reads when it runs a plan.
    monkeypatch.setattr(importlib.import_module("poisson_prove.executor_modal"), "run_modal", captured)
    return captured


@pytest.fixture
def fake_modal(monkeypatch: pytest.MonkeyPatch) -> FakeModal:
    fake = FakeModal()
    monkeypatch.setitem(sys.modules, "modal", fake)
    return fake


# ---------- helpers: plans, stores, files ----------


def _spec() -> SweepSpec:
    return SweepSpec.build(
        [dict(c) for c in CELLS], replicates=REPLICATES, target_id=TARGET_ID, t_unit=T_UNIT
    )


def _store(tmp_path: Path, name: str = "store") -> Store:
    return Store(tmp_path / name)


def _modal_plan(spec: SweepSpec, store: Store, **kwargs: Any) -> Plan:
    return plan(spec, store, backend="modal", **kwargs)


def _jobs(p: Plan) -> list[Job]:
    return [
        (dict(q.config), q.seed, i, q.config_hash, q.replicate_index)
        for i, q in enumerate(p.pairs)
    ]


COMPARE_COLS = ["seed", "outcome", "t", "horizon", "config", "error"]


def _keyed(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index(["config_hash", "replicate_index"]).sort_index()


def _outcome_set(store: Store, run_id: str) -> set[tuple[str, int, int, str, float]]:
    df = store.read(run_id)
    return set(
        zip(df["config_hash"], df["replicate_index"], df["seed"], df["outcome"], df["t"], strict=True)
    )


def _reference_run(tmp_path: Path, spec: SweepSpec) -> tuple[Plan, Store]:
    """The in-process ``run_with_mapper`` run of ``spec`` under SALT."""
    store = _store(tmp_path, "reference")
    p = _modal_plan(spec, store, run_salt=SALT)
    run_with_mapper(p, in_process_mapper, store, options=ModalOptions(batch_size=BATCH))
    return p, store


def _lines_starting(text: str, prefix: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(prefix)]


def _first_line(text: str, prefix: str) -> str:
    lines = _lines_starting(text, prefix)
    return lines[0] if lines else ""


def _index_of(lines: Sequence[str], prefix: str) -> int:
    """Index of the first line starting with ``prefix``; -1 when there is none."""
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            return i
    return -1


def _sweep_file(tmp_path: Path, tables: str = "") -> Path:
    path = tmp_path / "sweep.toml"
    path.write_text(SWEEP_HEADER + tables)
    return path


def _with_modal_key(tables: str, line: str) -> str:
    """``tables`` with ``line`` inserted as the first key of its ``[modal]`` table."""
    return tables.replace("[modal]\n", f"[modal]\n{line}\n", 1)


#: These fixtures are two-cell plumbing grids, not powered designs: N is 1, 2 or 4 and
#: the MDE saturates at 0.5. S23 gates a sweep on that number, so every end-to-end
#: invocation here states what it accepts. The flag is the honest answer -- these runs
#: really can only see a fifty-point move -- and it is what the gate exists to make
#: people say out loud.
# PF4 re-freeze (PF4.30, reading R17): at 1, 2 or 4 replicates a side no lone condition of these
# grids can be flagged at q / M, so any accepted change below 1 refuses them (no fifty-point limit
# exists any more); --max-mde 1 admits any design, which is what 0.5 did here.
PLUMBING_MAX_MDE = ("--max-mde", "1")


def _modal_argv(tmp_path: Path, sweep_path: Path, *extra: str, target: str = WELL_SHAPED) -> list[str]:
    return [
        "--store", str(tmp_path / "store"), "sweep", str(sweep_path),
        "--target", target, "--backend", "modal", "--yes", *PLUMBING_MAX_MDE, *extra,
    ]


def _local_argv(tmp_path: Path, sweep_path: Path, target: str) -> list[str]:
    return [
        "--store", str(tmp_path / "store"), "sweep", str(sweep_path),
        "--target", target, "--backend", "local", "--yes", *PLUMBING_MAX_MDE,
    ]


def _install_refusing_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Write the refusing module to ``tmp_path``, append that directory to ``sys.path``, and
    make sure the boundary variable is unset and the module is not already imported."""
    (tmp_path / f"{REFUSING_MODULE}.py").write_text(REFUSING_SOURCE)
    monkeypatch.setattr(sys, "path", [*sys.path, str(tmp_path)])
    monkeypatch.delenv(BOUNDARY_VAR, raising=False)
    monkeypatch.delitem(sys.modules, REFUSING_MODULE, raising=False)
    importlib.invalidate_caches()
    return f"{REFUSING_MODULE}:rollout"


def _defined(module: Any) -> set[str]:
    """The public names a module defines itself: S17's measure of its surface."""
    return {
        name
        for name, obj in vars(module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == module.__name__
    }


def _fake_run(tmp_path: Path, secrets: tuple[str, ...], name: str = "modal") -> tuple[Plan, Store, RunSummary]:
    """``run_modal`` through whatever ``modal`` is in ``sys.modules``, under SALT."""
    store = _store(tmp_path, name)
    p = _modal_plan(_spec(), store, run_salt=SALT)
    target = ModalTarget(import_path=DET_PATH, image=ImageSpec())
    options = ModalOptions(batch_size=BATCH, episode_timeout=None, secrets=secrets)
    summary = run_modal(p, target, store, options=options)
    return p, store, summary


# ---------- L1: local resolves, modal does not ----------


def test_l1_modal_branch_launches_a_target_that_refuses_to_import_here(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, captured_run_modal: CapturedRunModal
) -> None:
    target = _install_refusing_module(tmp_path, monkeypatch)
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path), target=target))
    assert r.code == 0, r.text
    assert len(captured_run_modal.calls) == 1
    _, modal_target, _, _ = captured_run_modal.calls[0]
    assert modal_target.import_path == target
    assert REFUSING_MODULE not in sys.modules


def test_l1_local_branch_still_resolves_and_refuses_the_same_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _install_refusing_module(tmp_path, monkeypatch)
    r = run_cli(_local_argv(tmp_path, _sweep_file(tmp_path), target))
    # A refusal exits 1 (spec section 5.2).
    assert r.code == 1, r.text
    assert target in r.text
    assert Store(tmp_path / "store").runs() == []


# ---------- L2: shape only on the modal branch ----------


@pytest.mark.parametrize(
    "target",
    [MOCK_MODULE, ":rollout", f"{MOCK_MODULE}:"],
    ids=["no-colon", "empty-module", "empty-attr"],
)
def test_l2_malformed_shape_is_refused_on_the_modal_branch(
    tmp_path: Path, captured_run_modal: CapturedRunModal, target: str
) -> None:
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path), target=target))
    # A refusal exits 1 (spec section 5.2).
    assert r.code == 1, r.text
    assert target in r.text
    assert Store(tmp_path / "store").runs() == []
    assert captured_run_modal.calls == []


@pytest.mark.parametrize(
    "target", [MISSING_MODULE_PATH, MISSING_ATTR_PATH], ids=["missing-module", "missing-attr"]
)
def test_l2_well_shaped_unresolvable_path_is_accepted_on_the_modal_branch(
    tmp_path: Path, captured_run_modal: CapturedRunModal, target: str
) -> None:
    """The loss of section 0 as a test: the container is the resolver, so the launcher accepts
    a path it cannot import. A test that expects a refusal here is wrong."""
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path), target=target))
    assert r.code == 0, r.text
    assert len(captured_run_modal.calls) == 1
    assert captured_run_modal.calls[0][1].import_path == target


# ---------- L3: one resolve site (ADR-029, structural) ----------


def test_l3_cli_resolves_in_exactly_one_place() -> None:
    # PF5 (spec section 17; PF5.7): the face resolves no target; the core plans the sweep, so the
    # one local resolve site of ADR-029 is in the core: outside ``_resolve`` itself and the remote
    # backends' container-side workers, ``_resolve.resolve`` is called in one function of
    # ``src/``, by any import of it, and that function is called from one line. ``cli.py`` does
    # not import ``_resolve`` in any form.
    remote = {"_resolve.py", "executor_modal.py", "executor_burla.py", "_burla_submit.py"}
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(PACKAGE.rglob("*.py"))}

    def resolve_names(tree: ast.Module) -> tuple[set[str], set[str]]:
        names: set[str] = set()
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "poisson_prove._resolve":
                names |= {a.asname or a.name for a in node.names if a.name == "resolve"}
            elif isinstance(node, ast.ImportFrom) and node.module == "poisson_prove":
                modules |= {a.asname or a.name for a in node.names if a.name == "_resolve"}
            elif isinstance(node, ast.Import):
                modules |= {a.asname or a.name for a in node.names if a.name == "poisson_prove._resolve"}
        return names, modules

    names, modules = resolve_names(trees[CLI_SOURCE])
    assert not names and not modules, "cli.py imports _resolve"
    sites: list[tuple[str, str]] = []
    for path, tree in trees.items():
        if path.name in remote:
            continue
        names, modules = resolve_names(tree)

        def visit(node: ast.AST, fn: str | None, names: set[str] = names, modules: set[str] = modules, path: Path = path) -> None:
            for child in ast.iter_child_nodes(node):
                inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
                if isinstance(child, ast.Call):
                    called = child.func
                    if (isinstance(called, ast.Name) and called.id in names) or (
                        isinstance(called, ast.Attribute) and called.attr == "resolve"
                        and ast.unparse(called.value) in modules | {"poisson_prove._resolve"}
                    ):
                        sites.append((path.name, fn or "<module>"))
                visit(child, inner, names, modules, path)

        visit(tree, None)
    assert len(sites) == 1, sites
    function = sites[0][1]
    calls = [
        line for path in trees for line in path.read_text(encoding="utf-8").splitlines()
        if re.search(rf"\b{re.escape(function)}\(", line) and not line.lstrip().startswith(f"def {function}(")
    ]
    assert len(calls) == 1, calls


# ---------- L4: a container-side resolve failure is one batch failure, retried, then recorded ----------


def test_l4_worker_batch_raises_on_an_unresolvable_import_path(tmp_path: Path) -> None:
    job = _jobs(_modal_plan(_spec(), _store(tmp_path)))[0]
    with pytest.raises(ImportError):
        worker_batch([job], MISSING_MODULE_PATH, None)


def test_l4_resolve_failure_is_retried_then_stored_as_infra_rows(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    mapper = ResolveFailingMapper(MISSING_MODULE_PATH)
    summary = run_with_mapper(p, mapper, store, options=ModalOptions(infra_retries=2))
    df = store.read(p.run_id)
    assert len(df) == len(p.pairs)
    assert all(str(e).startswith("infra: ") for e in df["error"])
    assert mapper.calls[_batch_key(_jobs(p))] == 3
    assert summary.n_infra_failed == len(p.pairs)
    assert not (df["error"] == "timeout").any()
    assert summary.complete is True


# ---------- L5: the pre-flight names where resolution happens ----------


def test_l5_preflight_target_line_names_the_container(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    target = ModalTarget(import_path=DET_PATH, image=ImageSpec())
    text = preflight_modal(p, target, ModalOptions(batch_size=BATCH))
    target_lines = _lines_starting(text, "Target:")
    assert len(target_lines) == 1, text
    assert DET_PATH in target_lines[0]
    assert "inside the container" in target_lines[0]
    assert f"import: {DET_PATH}" in _first_line(text, "Image:")


# ---------- L6: the field ----------


def test_l6_secrets_is_a_defaulted_trailing_tuple_field() -> None:
    assert ModalOptions().secrets == ()
    built = ModalOptions(secrets=["a", "b"]).secrets
    assert built == ("a", "b")
    assert isinstance(built, tuple)
    assert ModalOptions(secrets=("a",)) == ModalOptions(secrets=["a"])
    assert dataclasses.replace(ModalOptions(), secrets=("a",)).secrets == ("a",)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ModalOptions().secrets = ("a",)  # type: ignore[misc]
    names = [f.name for f in dataclasses.fields(ModalOptions)]
    assert names[-1] == "secrets"
    assert set(names) - PRE_AMENDMENT_FIELDS == {"secrets"}


# ---------- L7: names, never values ----------


@pytest.mark.parametrize(
    "value",
    ["golden-pilot", [""], ["a b"], ["a=b"], ["-leading"], ["x" * 65], ["a", "a"]],
    ids=["bare-str", "empty", "whitespace", "equals", "leading-dash", "too-long", "duplicate"],
)
def test_l7_malformed_secret_entries_raise_value_error(value: Any) -> None:
    with pytest.raises(ValueError):
        ModalOptions(secrets=value)


def test_l7_pasted_key_value_refusal_shows_the_create_form_and_never_the_value() -> None:
    canary = token_hex(16)
    with pytest.raises(ValueError) as excinfo:
        ModalOptions(secrets=[f"OPENAI_API_KEY={canary}"])
    assert "modal secret create" in str(excinfo.value)
    assert canary not in str(excinfo.value)


def test_l7_whitespace_refusal_never_echoes_the_entry() -> None:
    canary = token_hex(16)
    with pytest.raises(ValueError) as excinfo:
        ModalOptions(secrets=[f"{canary} with spaces"])
    assert canary not in str(excinfo.value)


@pytest.mark.parametrize("value", [["golden-pilot", "a.b_c-d"], ["x" * 64]], ids=["two-names", "max-length"])
def test_l7_well_formed_names_construct(value: list[str]) -> None:
    assert ModalOptions(secrets=value).secrets == tuple(value)


# ---------- L8: TOML reaches options, refusals stay clean ----------


def test_l8_secrets_list_in_the_modal_table_reaches_options(
    tmp_path: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path, SECRETS_TABLE)))
    assert r.code == 0, r.text
    _, _, _, options = captured_run_modal.calls[0]
    assert options is not None and options.secrets == ("golden-pilot", "second")


def test_l8_the_m10_tables_without_a_secrets_key_give_the_empty_tuple(
    tmp_path: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path, MODAL_TABLES)))
    assert r.code == 0, r.text
    _, _, _, options = captured_run_modal.calls[0]
    assert options is not None and options.secrets == ()


def test_l8_a_bare_string_is_refused_naming_the_table(
    tmp_path: Path, captured_run_modal: CapturedRunModal
) -> None:
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path, BARE_STRING_TABLE)))
    # A refusal exits 1 (spec section 5.2).
    assert r.code == 1, r.text
    assert "[modal]" in r.text
    assert "Traceback" not in r.text
    assert Store(tmp_path / "store").runs() == []


def test_l8_a_pasted_value_is_refused_with_the_create_form_and_never_echoed(
    tmp_path: Path, captured_run_modal: CapturedRunModal
) -> None:
    canary = token_hex(16)
    table = f'\n[modal]\nsecrets = ["KEY={canary}"]\n'
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path, table)))
    # A refusal exits 1 (spec section 5.2).
    assert r.code == 1, r.text
    assert "modal secret create" in r.text
    assert canary not in r.text
    assert Store(tmp_path / "store").runs() == []


def test_l8_flag_overrides_still_hold_with_secrets_present(
    tmp_path: Path, captured_run_modal: CapturedRunModal
) -> None:
    tables = _with_modal_key(MODAL_TABLES, 'secrets = ["golden-pilot", "second"]')
    r = run_cli(
        _modal_argv(
            tmp_path, _sweep_file(tmp_path, tables),
            "--concurrency", "9", "--infra-retries", "5", "--max-cost", "250",
            "--est-seconds", "1.5", "--app-name", "from-flag",
        )
    )
    assert r.code == 0, r.text
    _, _, _, options = captured_run_modal.calls[0]
    assert options == ModalOptions(
        concurrency=9,
        batch_size=32,
        episode_timeout=12.5,
        infra_retries=5,
        max_cost=250.0,
        est_seconds_per_episode=1.5,
        app_name="from-flag",
        secrets=("golden-pilot", "second"),
    )


# ---------- L9: the manifest records names ----------


def test_l9_modal_manifest_records_the_secret_names(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    options = ModalOptions(batch_size=BATCH, secrets=("golden-pilot",))
    run_with_mapper(p, in_process_mapper, store, options=options)
    env = dict(store.manifest(p.run_id).environment)
    assert "secrets" in env
    assert env["secrets"] == ["golden-pilot"]
    assert json.loads(json.dumps(env)) == env


def test_l9_modal_manifest_records_an_empty_list_without_secrets(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    run_with_mapper(p, in_process_mapper, store, options=ModalOptions())
    env = dict(store.manifest(p.run_id).environment)
    assert "secrets" in env
    assert env["secrets"] == []
    assert json.loads(json.dumps(env)) == env


def test_l9_local_manifest_has_no_secrets_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    run_local(p, deterministic_rollout, store)
    assert "secrets" not in store.manifest(p.run_id).environment


# ---------- L10: the pre-flight prints the mount list before the cost ----------


def test_l10_preflight_lists_the_mounts_between_containers_and_cost(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    target = ModalTarget(import_path=DET_PATH, image=ImageSpec())
    options = ModalOptions(batch_size=BATCH, secrets=("golden-pilot", "second"))
    text = preflight_modal(p, target, options)
    lines = text.splitlines()
    secrets_lines = _lines_starting(text, "Secrets:")
    assert len(secrets_lines) == 1, text
    assert "golden-pilot, second" in secrets_lines[0]
    assert "mounted by name" in secrets_lines[0]
    assert _index_of(lines, "Containers:") < _index_of(lines, "Secrets:")
    assert _index_of(lines, "Secrets:") < _index_of(lines, "Cost:")


def test_l10_preflight_says_none_without_secrets_in_the_same_place(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    target = ModalTarget(import_path=DET_PATH, image=ImageSpec())
    text = preflight_modal(p, target, ModalOptions(batch_size=BATCH))
    lines = text.splitlines()
    secrets_lines = _lines_starting(text, "Secrets:")
    assert len(secrets_lines) == 1, text
    assert secrets_lines[0] == "Secrets: none"
    assert _index_of(lines, "Containers:") < _index_of(lines, "Secrets:")
    assert _index_of(lines, "Secrets:") < _index_of(lines, "Cost:")


# ---------- L11: built by Secret.from_name, mounted on the function, nowhere else (ADR-030) ----------


def test_l11_run_modal_through_the_fake_matches_run_with_mapper_under_a_shared_salt(
    tmp_path: Path, fake_modal: FakeModal
) -> None:
    ref_plan, ref_store = _reference_run(tmp_path, _spec())
    p, store, summary = _fake_run(tmp_path, secrets=("a", "b"))
    assert summary.complete is True
    assert _outcome_set(store, p.run_id) == _outcome_set(ref_store, ref_plan.run_id)
    a = _keyed(ref_store.read(ref_plan.run_id))[COMPARE_COLS]
    b = _keyed(store.read(p.run_id))[COMPARE_COLS]
    pd.testing.assert_frame_equal(a, b)


def test_l11_secrets_are_built_by_from_name_and_mounted_on_the_function_only(
    tmp_path: Path, fake_modal: FakeModal
) -> None:
    _fake_run(tmp_path, secrets=("a", "b"))
    records = fake_modal.records
    assert records.from_name_calls == ["a", "b"]
    assert len(records.function_kwargs) == 1
    kwargs = records.function_kwargs[0]
    assert set(kwargs) == FUNCTION_KWARGS
    assert isinstance(kwargs["secrets"], list)
    assert len(kwargs["secrets"]) == 2
    assert all(got is built for got, built in zip(kwargs["secrets"], records.from_name_returned, strict=True))
    assert kwargs["retries"] == 0
    assert kwargs["serialized"] is True
    assert records.from_dict_calls == []
    assert records.from_local_environ_calls == []
    assert _image_secret_objects(records) == []


def test_l11_no_secrets_means_no_from_name_call_and_an_empty_list(
    tmp_path: Path, fake_modal: FakeModal
) -> None:
    _fake_run(tmp_path, secrets=())
    records = fake_modal.records
    assert records.from_name_calls == []
    assert records.function_kwargs[0]["secrets"] == []


# ---------- L12: no value in-process (canary) ----------


def test_l12_canary_never_reaches_the_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = token_hex(16)
    monkeypatch.setenv(CANARY_VAR, canary)
    p = _modal_plan(_spec(), _store(tmp_path))
    target = ModalTarget(import_path=DET_PATH, image=ImageSpec())
    text = preflight_modal(p, target, ModalOptions(batch_size=BATCH, secrets=("a", "b")))
    assert canary not in text


def test_l12_canary_never_reaches_the_manifest_or_the_fake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_modal: FakeModal
) -> None:
    canary = token_hex(16)
    monkeypatch.setenv(CANARY_VAR, canary)
    p, store, _ = _fake_run(tmp_path, secrets=("a", "b"))
    assert canary not in json.dumps(store.manifest(p.run_id).environment)
    assert canary not in repr(fake_modal.records.function_kwargs)
    assert canary not in repr(fake_modal.records.secret_calls())


def test_l12_canary_never_reaches_the_sweep_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, captured_run_modal: CapturedRunModal
) -> None:
    canary = token_hex(16)
    monkeypatch.setenv(CANARY_VAR, canary)
    r = run_cli(_modal_argv(tmp_path, _sweep_file(tmp_path, SECRETS_TABLE)))
    assert r.code == 0, r.text
    assert canary not in r.text


# ---------- L13: grep (ADR-030, structural) ----------


def test_l13_executor_modal_builds_secrets_with_from_name_and_nothing_else() -> None:
    source = MODAL_SOURCE.read_text(encoding="utf-8")
    assert source.count("from_name") == 1
    assert "Secret.from_dict" not in source
    assert "from_local_environ" not in source
    assert "os.environ" not in source
    assert re.search(r"\benv=", source) is None


def test_l13_no_other_core_file_mentions_secret() -> None:
    others = sorted(
        p for p in PACKAGE.rglob("*.py") if p != MODAL_SOURCE and "__pycache__" not in p.parts
    )
    assert others, PACKAGE
    offenders = [p.name for p in others if "Secret" in p.read_text(encoding="utf-8")]
    assert offenders == []


# ---------- L14: surface unchanged ----------


def test_l14_public_surface_is_what_s18_left_it() -> None:
    assert list(executor_modal.__all__) == MODAL_EXPORTS, executor_modal.__all__
    assert _defined(executor_modal) == MODAL_PUBLIC, sorted(_defined(executor_modal) ^ MODAL_PUBLIC)
    assert set(ImageSpec().to_dict()) == IMAGE_KEYS
    assert _defined(cli) == CLI_PUBLIC, sorted(_defined(cli) ^ CLI_PUBLIC)
    assert len(dataclasses.fields(ModalOptions)) == 9


# ---------- L15: live mount lives in tests/live/test_m3_modal_live.py ----------
