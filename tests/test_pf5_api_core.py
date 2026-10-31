"""PF5, the Python API and the core: the frozen tests (the code suite).

Covers the public surface and its docstrings, the core and its boundary (core, renderers, faces),
what the static UI and the terminal app read from the core, and invariants PF5.1 to PF5.11, with the
items earlier work left for PF5: ``POWER``'s place in ``stats.__all__``; the method
lines the command line adds to the rendered files and the notes ``diff --methods all`` keeps; the
report header's ``NAME (ID)`` pairing; the core's ``init_agent``; and everything the statistics now
return, which the API exposes and no face recomputes.

What PF5 promises, in one line: one core under every face. The plain commands, ``--json``, the
rendered report and the page, and later the terminal app, the static UI and a local server, all show
what the core returned, and the public ``compare`` and ``stats`` give a Python user the same numbers.

**The core's operations this file reaches** (``poisson_prove.core``, private):

| area | operation | returns |
|---|---|---|
| store | ``open_store(path=None)``; ``runs(store)``; ``resolve(store, text)``; ``run(store, ref, *, events=None, horizon=None)``; ``episodes(store, ref, *, event, condition=None, offset=0, limit=None)`` | a store; a sequence of ``RunInfo`` with its own ``to_json()``; a run id; ``RunDetail``; ``EpisodePage`` |
| setup | ``init(path, *, example=False, target=None, force=False)``; ``read_spec(path)`` | ``WrittenFiles``; a spec |
| sweeps | ``plan(spec, *, store, overrides=None)``; ``start(plan, *, on_event=None, cancel=None)``; ``resume(store, ref=None, *, on_event=None, cancel=None)`` | ``Plan``; ``RunResult`` |
| comparisons | ``compare(store, a=None, b=None, *, events=None, method=None, q=0.05, methods=None)``; ``check(store, a=None, b=None, *, events, fail_on="worse", method=None, q=0.05)``; ``paired(store, declaration, *, cap_check=False)``; ``inspect(store, ref=None, *, event, condition=None)`` | ``Comparison``; ``CheckResult``; ``PairedResult``; ``InspectResult`` |

A refusal is ``core.Refusal``: ``str()`` is the sentence the ``error:`` line prints, ``.next`` the
commands. ``overrides`` takes the sweep's options by their flag names with underscores
(``target``, ``replicates``, ``pair_with``, ``resume``, ``name``, ``max_mde``, ``salt``,
``max_rollouts``, ``backend``, ...). ``cancel`` is a ``threading.Event``.

**Readings, named here** (each a point the invariants leave open, read one way and
lettered so the tests below can cite it).

- (a) PF5 covers the store, setup, sweeps and comparisons areas of the table above. ``init_agent`` is
  PF11's core operation (PF11's tests drive it through ``init --agent``); ``save``,
  ``artifacts``, ``artifact`` and ``build_ui`` are PF12's; ``view`` is PF12's and PF6's. This
  file pins none of the view field names; PF12's and PF6's tests hold the views. Those
  operations may be in ``core.__all__``; this file requires only PF5's. PF5.11's ``save`` and "saved
  comparisons" are therefore checked by PF12; PF5.9's "and view" by PF6 and PF12.
- (b) PF5 writes each new run's ``events.jsonl`` (PF5.10 asks for it); PF12 documents it and adds
  the store descriptor. A resume of a run that has no ``events.jsonl`` (a 0.0.1 run) starts none.
- (c) ``plan`` takes the store as the keyword ``store``; ``overrides`` keys are the sweep's options.
- (d) ``resume(store, ref)`` continues a partial run from what its manifest recorded (conditions,
  replicates, target), on this machine, asking nothing; ``sweep --resume`` stays ``plan`` with
  ``overrides={"resume": ...}`` then ``start``, so a resume still reads the spec's replicates
  (``test_s23_power::test_w9``).
- (e) Every core refusal is a ``core.Refusal`` whose ``str()`` is the face's ``error:`` sentence
  exactly; an underpowered design's refusal comes from ``plan``, after which the face still shows
  the plan (rule 7). ``compare.Refusal`` is the public name of the same class.
- (f) Faces call operations as attributes of ``poisson_prove.core`` (``core.compare(...)``), so a
  test can see what the core returned to a face; a face imports from Prove only names in
  ``core.__all__``, renderer modules and its own modules, and reads on ``core`` only names in
  ``core.__all__``; ``core.__all__`` holds the table's operations, data and exception classes and
  constants, and no other function.
- (g) The classes: faces ``cli`` and ``__main__``; renderers the look and facts modules, ``plain``,
  ``report`` and ``viewer``; the core everything else, ``poisson_prove.core`` and its submodules
  among it. A new module is a submodule of ``poisson_prove.core`` (the core), or is named
  ``poisson_prove._cli_<name>`` (the face's own) or ``poisson_prove._render_<name>`` (a renderer).
  A class in ``core.__all__`` is a data class, a named tuple, an enum, an exception, a protocol or
  a class with ``to_json()`` (a result). A renderer imports from Prove only
  the look module, other renderers, and from core modules names that are types (data classes, named
  tuples, enums, exceptions, type aliases) or constants: no function, no module.
- (h) Each result's ``to_json()`` is one strict document: ``schema`` (``poisson-prove.<kind>/<n>``;
  the comparison's is ``poisson-prove.comparison/1``, the artifact format's name for it), then
  ``verdict`` and ``sentence``, its own keys, and ``next`` last. A verb's ``--json`` is that
  document with the verb's schema in place of the result's. ``runs`` returns a sequence of
  ``RunInfo`` whose ``to_json()`` is the runs document. ``report`` and ``serve`` render ``compare``'s
  result (``report RUN`` renders ``run``'s) and carry its facts under their own envelope. An
  ``EpisodePage`` lists ``episodes`` as ``inspect --json`` does, in its order.
- (i) ``compare``'s public set is ``diff``, ``check``, ``runs``, ``resolve``, ``Comparison``,
  ``CheckResult``, ``RunInfo`` and ``Refusal``; ``compare.diff`` returns the core's ``Comparison``
  (the documented ``DiffResult`` read as it); each takes the store as a path or a ``Store``.
- (j) ``stats.__all__`` holds ``POWER``, beside ``WILSON_LEVEL``.
- (k) ``stats.__all__`` holds ``KMCurve`` and ``CIFCurve``, the types two of its functions return.
- (l) ``stats.fisher_test(events_a, n_a, events_b, n_b)`` gives ``(odds_ratio, p)``,
  ``mcnemar_test(only_a, only_b)`` gives ``(only_a - only_b, p)`` and ``logrank_test(t_a,
  observed_a, t_b, observed_b)`` gives ``(chi_square, p)``. PF5.3's "what the private functions
  return" is checked against the numbers the comparison reports for every row of every fixture
  pair (never against an internal), and ``kaplan_meier`` and ``mde_two_proportion``, whose
  numbers no comparison reports, against lifelines and statsmodels.
- (m) ``Comparison`` exposes ``verdict``, ``sentence``, ``detail`` (the verdict block's
  ``(label, text)`` lines), ``next``, ``notes``, ``method``, ``method_chosen``, ``threshold``,
  ``threshold_source``, ``verdict_limit``, ``fragility``, ``fragility_flips``, ``fragility_note``,
  ``fragility_exact``, ``n_flagged_only``, ``peeking``, ``errors_differ`` and ``rows`` (every
  compared row, as its JSON cell with its ``event``), each equal to its JSON.
- (n) The method line, ``--methods all``'s pairing notes and the facts lines are the result's: the
  face prints ``detail``'s ``method`` text on every surface and ``notes`` as ``note:`` lines.
- (o) PF5 rewrites ``report.py`` (its imports, the method line), so it takes the header's
  ``before  NAME (ID)`` and ``after  NAME (ID)``: in ``report.md`` before the first ``##`` and in the
  receipt's header, each run's id exactly once in each file.
- (p) PF5 writes ``docs/python.md``: one section per public module headed by its import name, every
  public name in its section, every public constant with its meaning, the private modules named
  private, and an example for every function of ``compare`` and ``stats``; each example runs from a
  folder whose ``./prove-runs`` holds the quickstart pair. PF7's docs check later takes it in.
- (q) PF5.2's "plain words" in the public docstrings and ``docs/python.md`` is checked by the release
  plain-words test (``test_pf8_public_hygiene.py``, PF8.4), over the wheel and the docs.
- (r) ``mypy --strict`` over ``src/`` is the gate's lint job (``mypy src`` with ``strict = true`` in
  ``pyproject.toml``) on every pull request and push to main, not a case of the code suite.
- (s) PF5.8's scan: a read is ``os.environ.get(N)``, ``os.environ[N]``, ``N in os.environ`` or
  ``os.getenv(N)`` with ``N`` a string or a module constant; copying the environment whole for a
  child process is not a read; any other use of ``os.environ`` is a failure. The core may also
  read ``PROOFLOAD_STORE``, only to say it is retired (PF0).
- (t) PF5.10's "at most once a second" is measured by the test's own clock on ``on_event``'s calls;
  ``progress`` carries ``done``, ``kept``, ``errored`` and ``total``; what Ctrl-C leaves is the run
  interrupted at the start of rollout ``k + 1``, against ``cancel`` set during rollout ``k``.
- (u) PF5.11 sweeps with one ``--salt`` through both faces, so both draw the same episodes; "equal
  results" is the comparison and check documents equal, the runs equal but for ids and times.
- (v) PF5.8's "the quickstart fixtures" is the packaged quickstart pair at 194 replicates.
- (w) The face writes the report folder (``report.md``, ``heatmap.svg``, ``receipt.html``, and
  ``paired``'s files) with the renderers it imports: the folder is the person's, outside the store,
  and neither a store file nor an artifact, and other test files stand in for
  ``cli.build_multi_report``, ``cli.build_survival_report`` and ``cli.serve_page``. The rule
  "the core calls renderers when it writes a file (a report, ...)" is read as the saved artifact
  (PF12's), not this folder.
- (x) The two checks against an outside library (``kaplan_meier`` against lifelines,
  ``mde_two_proportion`` against statsmodels) are marked ``math``: agreement with
  an outside library belongs in the math suite. Every other case is in the code suite.
- (y) The core runs a remote backend through its module's attribute (``executor_modal.run_modal``,
  read when the plan runs), where four tests in other files put their stand-ins.
- (z) ``resume`` continues a run recorded on this machine's backend; a run recorded on Modal or
  Burla is refused, naming ``sweep --resume`` with its backend, since its image or bundle comes from
  the spec. No test here reaches a remote run.

**Suites.** The code suite, but for reading (x)'s two ``math`` cases. The shared stores and
the comparison documents PF5.3 reads are built once per test session, and once in all when the
suite runs on ``pytest-xdist`` workers (``_shared``).

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF5.1 each public module's ``__all__`` | ``test_pf5_1_*`` |
| PF5.2 docstrings, annotations, ``docs/python.md`` | ``test_pf5_2_*``; ``mypy``: the gate |
| PF5.3 the public statistics give the numbers comparisons report | ``test_pf5_3_*`` |
| PF5.4 ``compare`` returns what ``--json`` prints; ``resolve`` takes every form | ``test_pf5_4_*`` |
| PF5.5 ``from poisson_prove import step, record, Episode, Rollout`` | ``test_pf5_5_*`` |
| PF5.6 every example in ``docs/python.md`` runs | ``test_pf5_6_*`` |
| PF5.8 the core prints, asks, exits, opens and connects nothing; the environment it reads | ``test_pf5_8_*`` |
| PF5.9 each verb's ``--json`` is the core's result inside the envelope | ``test_pf5_9_*`` |
| PF5.10 events in order, ``events.jsonl``, cancel as Ctrl-C | ``test_pf5_10_*`` |
| PF5.11 the plain commands and the core give equal results on each other's stores | ``test_pf5_11_*`` |
| carried: the statistics' facts on the result; refusals; the method lines and notes; the header | ``test_pf5_carried_*`` |
"""

from __future__ import annotations

import ast
import builtins
import gc
import html
import importlib
import inspect
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import webbrowser
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import lattice

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE = SRC / "poisson_prove"
DOCS_PYTHON = ROOT / "docs" / "python.md"
PACKAGED = PACKAGE / "examples" / "quickstart.toml"
MOCK = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK}:rollout"
PATCHED = f"{MOCK}:rollout_patched"
SALT = "5a1f0c3b9e7d2468"
SCHEMA = re.compile(r"^poisson-prove\.[a-z][a-z-]*/\d+$")
LOOSE = ("--max-mde", "1")
METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")

#: A small design of the keyless mock agent, its target in the spec: 2 x 2 conditions.
SMALL = f"""\
target = "{ROLLOUT}"
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = {{replicates}}

[axes.task_id]
type = "categorical"
values = ["search", "refund"]

[axes.tool_fail_rate]
type = "continuous"
values = [0.3, 0.55]

[declare]
failures = ["timeout", "violated"]
"""


# ---------- the public sets (readings i to k) ----------

PUBLIC: dict[str, frozenset[str]] = {
    "poisson_prove": frozenset({"Episode", "EpisodeValidationError", "Rollout", "record", "step", "__version__"}),
    "poisson_prove.trace": frozenset({
        "ALIAS_MAP_VERSION", "ATTRIBUTE_ALIASES", "CONTENT_KEYS", "Collector", "DROP_REASONS", "Declaration",
        "GATE", "KINDS", "LOGPROBS_KEY", "OBSERVATION_KEYS", "OBSERVATION_ROUTING_BYTES", "OTEL_KIND_MAP",
        "OTEL_SEMCONV_VERSION", "OUTCOME_BY", "SCHEMA", "SOURCES", "Span", "SpanHandle", "TRUNCATED_KEY",
        "Trace", "TraceValidationError", "assemble", "collect", "finalize", "from_litellm", "from_otel",
        "merge", "record", "split", "step", "truncate_observations",
    }),
    "poisson_prove.steps": frozenset({"DeclarationCheck", "declaration_check"}),
    "poisson_prove.store": frozenset({
        "Store", "RunManifest", "EpisodeRecord", "RunTally", "config_hash", "StoreError", "SchemaMismatch",
    }),
    "poisson_prove.stats": frozenset({
        "wilson", "WilsonInterval", "WILSON_LEVEL", "POWER", "kaplan_meier", "KMCurve", "aalen_johansen",
        "CIFCurve", "bh", "holm", "interval_rd", "interval_rd_paired", "mde_two_proportion", "fisher_test",
        "mcnemar_test", "logrank_test",
    }),
    "poisson_prove.compare": frozenset({
        "diff", "check", "runs", "resolve", "Comparison", "CheckResult", "RunInfo", "Refusal",
    }),
    "poisson_prove.chaos": frozenset({
        "ChaosError", "ChaosSpec", "ChaosStatus", "FaultRecord", "fault_names", "injecting", "install", "position",
    }),
    "poisson_prove.otel": frozenset({"EPISODE_KEY", "EpisodeStamper", "RUN_ID_KEY", "episode"}),
    "poisson_prove.examples.mock_agent": frozenset({"rollout", "rollout_patched"}),
}

#: The private modules (the core among them), each named private in
#: ``docs/python.md``.
PRIVATE_MODULES = (
    "executor", "executor_modal", "executor_burla", "sampler", "diff", "tree", "report", "viewer", "plain",
    "paired", "capture", "chaos_catalog", "survival", "cli", "_compat", "_resolve", "_burla_submit", "core",
)

#: The three classes, every module of ``src/`` in exactly one (reading g).
FACES = frozenset({"poisson_prove.cli", "poisson_prove.__main__"})
RENDERERS = frozenset({
    "poisson_prove._look", "poisson_prove._facts", "poisson_prove.plain", "poisson_prove.report",
    "poisson_prove.viewer",
})
CORE = frozenset({
    "poisson_prove", "poisson_prove._burla_submit", "poisson_prove._compat", "poisson_prove._limits",
    "poisson_prove._names", "poisson_prove._resolve", "poisson_prove._verdict", "poisson_prove.capture",
    "poisson_prove.chaos", "poisson_prove.chaos_catalog", "poisson_prove.compare", "poisson_prove.core",
    "poisson_prove.diff", "poisson_prove.episode", "poisson_prove.examples", "poisson_prove.examples.mock_agent",
    "poisson_prove.executor", "poisson_prove.executor_burla", "poisson_prove.executor_modal",
    "poisson_prove.otel", "poisson_prove.paired", "poisson_prove.sampler", "poisson_prove.stats",
    "poisson_prove.steps", "poisson_prove.store", "poisson_prove.survival", "poisson_prove.trace",
    "poisson_prove.tree",
})

#: The environment variables Prove's own code reads (PF5.8, reading s).
CORE_ENV = frozenset({"POISSON_PROVE_STORE", "PROOFLOAD_STORE"})
FACE_ENV = frozenset({"NO_COLOR", "CI", "TERM"})
#: PF10: a Modal or Burla worker reads the BLAS thread counts its environment names
#: (docs/backends.md) and takes out the ``KMP_DUPLICATE_LIB_OK`` threadpoolctl sets on import.
WORKER_ENV = {"poisson_prove.executor_modal": frozenset({
    "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS", "KMP_DUPLICATE_LIB_OK",
})}


# ---------- helpers ----------


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def doc(self) -> Any:
        assert self.code in (0, 3, 4), self
        return strict_json(self.out)

    @property
    def errors(self) -> list[str]:
        return [line for line in self.err.splitlines() if line.startswith("error: ")]

    @property
    def notes(self) -> list[str]:
        return [line for line in self.err.splitlines() if line.startswith("note: ")]


def strict_json(text: str) -> Any:
    def refuse(token: str) -> Any:
        raise ValueError(f"not strict JSON: {token}")

    return json.loads(text, parse_constant=refuse)


def as_json(value: Any) -> Any:
    """``value`` through a strict JSON round trip: what a face could print of it."""
    return strict_json(json.dumps(value, allow_nan=False))


@contextmanager
def inside(folder: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(before)


def cli(cwd: Path, *argv: str | Path) -> Result:
    """``poisson-prove ARGV`` in this process, in ``cwd``, stdin not a terminal."""
    from poisson_prove import cli as module

    out, err = StringIO(), StringIO()
    with inside(cwd):
        code = module.main([str(a) for a in argv], stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def core() -> Any:
    return importlib.import_module("poisson_prove.core")


@contextmanager
def spying(monkeypatch: pytest.MonkeyPatch, *names: str) -> Iterator[dict[str, list[Any]]]:
    """Each named core operation, wrapped: what it returned to the face, in order (reading f)."""
    module = core()
    seen: dict[str, list[Any]] = {name: [] for name in names}
    for name in names:
        real = getattr(module, name)

        def spy(*args: Any, _real: Callable[..., Any] = real, _name: str = name, **kwargs: Any) -> Any:
            result = _real(*args, **kwargs)
            seen[_name].append(result)
            return result

        monkeypatch.setattr(module, name, spy)
    yield seen


def inner(result: Any) -> dict[str, Any]:
    """A core result's document, checked to be one strict JSON document in the envelope's order (``schema``, ``verdict``, ``sentence``, its keys, ``next``)."""
    doc = as_json(result.to_json())
    assert isinstance(doc, dict)
    keys = list(doc)
    assert keys[:3] == ["schema", "verdict", "sentence"], keys[:5]
    assert keys[-1] == "next", keys[-3:]
    assert SCHEMA.match(doc["schema"]), doc["schema"]
    return doc


def assert_envelope(printed: Mapping[str, Any], result: Any, verb: str) -> None:
    """Reading h: the verb's ``--json`` is the result's document with the verb's schema."""
    doc = inner(result)
    assert printed["schema"] == f"poisson-prove.{verb}/1"
    assert list(printed)[1:] == list(doc)[1:]
    assert dict(printed) == {**doc, "schema": printed["schema"]}


def _shared(factory: pytest.TempPathFactory, name: str, build: Callable[[Path], None]) -> Path:
    """A folder built once per test session and shared between xdist workers: built beside, then
    renamed into place; a worker that loses the race uses the winner's."""
    base = factory.getbasetemp()
    root = base.parent if base.name.startswith("popen-gw") else base
    final = root / f"pf5-{name}"
    if final.is_dir():
        return final
    staging = Path(tempfile.mkdtemp(prefix=f".pf5-{name}-", dir=root))
    build(staging)
    try:
        os.rename(staging, final)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
    assert final.is_dir()
    return final


def copy_of(source: Path, into: Path) -> Path:
    shutil.copytree(source, into)
    return into


def write_spec(folder: Path, replicates: int, name: str = "prove.toml") -> Path:
    path = folder / name
    path.write_text(SMALL.format(replicates=replicates), encoding="utf-8")
    return path


def runs_doc(store: Path) -> list[dict[str, Any]]:
    r = cli(store.parent, "--store", store, "runs", "--json")
    assert r.code == 0, r
    return list(r.doc["runs"])


def visible(markup: str) -> str:
    markup = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup)).split())


def header_of(markdown: str) -> str:
    at = markdown.find("\n## ")
    return markdown if at < 0 else markdown[:at]


@pytest.fixture(autouse=True)
def _empty_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)


# ---------- the shared stores ----------


def _build_quickstart(folder: Path) -> None:
    """The packaged quickstart pair at its 194 replicates (reading v), one salt, by the plain
    commands: ``previous`` the mock agent, ``latest`` its patched twin, paired."""
    first = cli(folder, "--store", folder / "prove-runs", "sweep", PACKAGED, "--yes", "--salt", SALT)
    assert first.code == 0, first
    second = cli(
        folder, "--store", folder / "prove-runs", "sweep", PACKAGED, "--yes", "--target", PATCHED,
        "--pair-with", "latest",
    )
    assert second.code == 0, second


@pytest.fixture(scope="session")
def quickstart(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The folder whose ``prove-runs`` holds the quickstart pair; read only."""
    return _shared(tmp_path_factory, "quickstart", _build_quickstart)


def _rollout_module(folder: Path) -> None:
    """A rollout module the tests steer: the mock agent, slowed, stopped, broken or mixed."""
    (folder / "pf5_rollouts.py").write_text(
        '''\
import time
from poisson_prove.episode import Episode
from poisson_prove.examples import mock_agent

CALLS = 0
SLEEP = 0.0
CANCEL = None
CANCEL_AT = None
INTERRUPT_AT = None


def reset(**settings):
    global CALLS, SLEEP, CANCEL, CANCEL_AT, INTERRUPT_AT
    CALLS, SLEEP, CANCEL, CANCEL_AT, INTERRUPT_AT = 0, 0.0, None, None, None
    globals().update(settings)


def steered(cfg, seed):
    global CALLS
    index = CALLS
    CALLS += 1
    if INTERRUPT_AT is not None and index == INTERRUPT_AT:
        raise KeyboardInterrupt
    if SLEEP:
        time.sleep(SLEEP)
    episode = mock_agent.rollout(cfg, seed)
    if CANCEL is not None and index == CANCEL_AT:
        CANCEL.set()
    return episode


def broken(cfg, seed):
    """The patched twin, with half the runs of one condition raising: errors that differ."""
    if cfg.get("task_id") == "refund" and cfg.get("tool_fail_rate") == 0.55 and seed % 2:
        raise RuntimeError("the tool server went away")
    return mock_agent.rollout_patched(cfg, seed)


def mixed(cfg, seed):
    """Three cases in every condition, reported by id: a mixed condition."""
    episode = mock_agent.rollout(cfg, seed)
    return Episode(
        outcome=episode.outcome, t=episode.t, horizon=episode.horizon,
        meta={"case_id": f"case-{seed % 3}"},
    )
''',
        encoding="utf-8",
    )


@pytest.fixture
def rollouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    folder = tmp_path / "rollouts"
    folder.mkdir()
    _rollout_module(folder)
    monkeypatch.syspath_prepend(str(folder))
    sys.modules.pop("pf5_rollouts", None)
    module = importlib.import_module("pf5_rollouts")
    module.reset()
    yield module
    sys.modules.pop("pf5_rollouts", None)


def _build_facts(folder: Path) -> None:
    """A pair whose comparison carries every fact non-empty: ``a`` complete, ``b`` its patched twin
    paired with it, stopped short (a peeking caveat, PF4.39) and erroring in one condition more
    than ``a`` (PF4.46)."""
    _rollout_module(folder)
    store = folder / "prove-runs"
    spec = write_spec(folder, 40)
    env_path = [str(folder), *sys.path]
    old = sys.path[:]
    sys.path[:] = env_path
    sys.modules.pop("pf5_rollouts", None)
    try:
        a = cli(folder, "--store", store, "sweep", spec, "--yes", *LOOSE, "--salt", SALT, "--name", "facts a")
        assert a.code == 0, a
        b = cli(
            folder, "--store", store, "sweep", spec, "--yes", *LOOSE, "--target", "pf5_rollouts:broken",
            "--pair-with", "facts a", "--name", "facts b", "--max-rollouts", "150",
        )
        assert b.code == 3, b
    finally:
        sys.path[:] = old
        sys.modules.pop("pf5_rollouts", None)


@pytest.fixture(scope="session")
def facts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _shared(tmp_path_factory, "facts", _build_facts)


def _build_named(folder: Path) -> None:
    """Four runs for the run forms: two complete, one named at sweep time, one
    partial, and a names file naming the first."""
    store = folder / "prove-runs"
    spec = write_spec(folder, 6)
    first = cli(folder, "--store", store, "sweep", spec, "--yes", *LOOSE, "--salt", SALT)
    assert first.code == 0, first
    named = cli(folder, "--store", store, "sweep", spec, "--yes", *LOOSE, "--name", "baseline")
    assert named.code == 0, named
    partial = cli(folder, "--store", store, "sweep", spec, "--yes", *LOOSE, "--max-rollouts", "3")
    assert partial.code == 3, partial
    ids = [entry["run_id"] for entry in sorted(runs_doc(store), key=lambda e: e["created_at"])]
    (store / "trace-names.toml").write_text(f'version = 1\n\n[names]\n"first" = "{ids[0]}"\n', encoding="utf-8")


@pytest.fixture(scope="session")
def named(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _shared(tmp_path_factory, "named", _build_named)


def _paired_fixture(folder: Path) -> tuple[Path, Path]:
    """``paired``'s store and declaration, as PR3's frozen tests build them."""
    from test_pr3_paired_output import default_rows, make_store, write_declaration

    make_store(folder, default_rows(), name="store")
    return folder / "store", write_declaration(folder / "declaration.toml")


def ids_by_age(store: Path) -> list[str]:
    return [entry["run_id"] for entry in sorted(runs_doc(store), key=lambda e: e["created_at"])]


# ---------- PF5.1 ----------


@pytest.mark.parametrize("module", sorted(PUBLIC))
def test_pf5_1_each_public_module_exports_exactly_its_public_set(module: str) -> None:
    """The public sets, with readings i, j and k: ``__all__`` is the set, and every name in it
    is reachable."""
    mod = importlib.import_module(module)
    assert frozenset(getattr(mod, "__all__", ())) == PUBLIC[module]
    assert len(mod.__all__) == len(set(mod.__all__))
    for name in mod.__all__:
        assert hasattr(mod, name), f"{module}.{name}"


# ---------- PF5.2 ----------


def _public_objects(module: str) -> list[tuple[str, Any]]:
    mod = importlib.import_module(module)
    return [(name, getattr(mod, name)) for name in sorted(PUBLIC[module])]


def _unannotated(fn: Any) -> list[str]:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    # Read off the signature, not resolved: a type imported only for type checking is an
    # annotation all the same.
    missing = [
        p.name for p in sig.parameters.values()
        if p.name not in ("self", "cls") and p.annotation is inspect.Parameter.empty
    ]
    if sig.return_annotation is inspect.Signature.empty:
        missing.append("return")
    return missing


@pytest.mark.parametrize("module", sorted(PUBLIC))
def test_pf5_2_every_public_name_has_a_plain_docstring_and_annotations(module: str) -> None:
    """PF5.2: every function and class in a public ``__all__`` has its own
    docstring (its words are the release plain-words test's, reading q); every
    function, and every public method a class defines, has every parameter and its return
    annotated."""
    problems: list[str] = []
    for name, obj in _public_objects(module):
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        doc = obj.__dict__.get("__doc__") if inspect.isclass(obj) else obj.__doc__
        if not doc or not doc.strip() or doc.startswith(f"{obj.__name__}("):
            # A data class or named tuple with no docstring of its own gets one generated from
            # its fields: that is no docstring.
            problems.append(f"{name}: no docstring")
        if inspect.isfunction(obj):
            if _unannotated(obj):
                problems.append(f"{name}: unannotated {_unannotated(obj)}")
        else:
            for attr, member in vars(obj).items():
                if attr.startswith("_") or not inspect.isfunction(member):
                    continue
                if _unannotated(member):
                    problems.append(f"{name}.{attr}: unannotated {_unannotated(member)}")
    assert not problems, problems


def _sections(text: str) -> dict[str, str]:
    """``docs/python.md``'s sections by heading, the heading's backticked import name first."""
    out: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^#{2,3} .*?`(poisson_prove[\w.]*)`", line)
        if m and m.group(1) in PUBLIC:
            current = m.group(1)
            out.setdefault(current, "")
        elif current is not None:
            out[current] += line + "\n"
    return out


def test_pf5_2_docs_python_lists_every_public_name_and_constant_and_marks_the_private_modules() -> None:
    """PF5.2 and reading p: one section per public module; every public name in its section in
    backticks; every public constant on a line that says what it means; every private module
    named in a paragraph that says it is private."""
    text = DOCS_PYTHON.read_text(encoding="utf-8")
    sections = _sections(text)
    problems: list[str] = []
    for module, names in PUBLIC.items():
        body = sections.get(module)
        if body is None:
            problems.append(f"no section for {module}")
            continue
        mod = importlib.import_module(module)
        for name in names:
            if f"`{name}" not in body:
                problems.append(f"{module}: {name} not listed")
                continue
            value = getattr(mod, name)
            if not (callable(value) or inspect.ismodule(value)):
                lines = [line for line in body.splitlines() if f"`{name}`" in line]
                meant = [line for line in lines if len(re.findall(r"[A-Za-z]{2,}", line.replace(name, ""))) >= 5]
                if not meant:
                    problems.append(f"{module}: the constant {name} has no meaning given")
    paragraphs = re.split(r"\n\s*\n", text)
    for private in PRIVATE_MODULES:
        found = [p for p in paragraphs if re.search(rf"`(poisson_prove\.)?{re.escape(private)}`", p)]
        if not any("private" in p.lower() for p in found):
            problems.append(f"{private} not named private")
    assert not problems, problems


# ---------- PF5.3 ----------


#: Where the comparison documents PF5.3 reads are kept for the session, shared between workers.
_DOC_CACHE: list[Path] = []


def _diff_doc(store: Path, method: str, *runs: str) -> dict[str, Any]:
    """``diff RUNS --method METHOD --json``, computed once per test session and shared."""
    cached = _DOC_CACHE[0] / f"{store.parent.name}-{store.name}-{method}-{'-'.join(runs)}.json" if _DOC_CACHE else None
    if cached is not None and cached.is_file():
        return dict(strict_json(cached.read_text(encoding="utf-8")))
    r = cli(store.parent, "--store", store, "diff", *runs, "--method", method, "--json")
    assert r.code == 0, r
    if cached is not None:
        staging = cached.with_name(f".{cached.name}.{os.getpid()}")
        staging.write_text(r.out, encoding="utf-8")
        os.replace(staging, cached)
    return dict(r.doc)


@pytest.fixture(scope="session")
def _doc_cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    _DOC_CACHE[:] = [_shared(tmp_path_factory, "docs", lambda folder: None)]
    yield
    _DOC_CACHE.clear()


def _rows(doc: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(event, cell) for event in doc["events"] for cell in doc["by_event"][event]["cells"]]


def _frames(store: Path, *runs: str) -> list[Any]:
    from poisson_prove.store import Store

    return [Store(store).read(run, meta=False) for run in runs]


def _pair_ids(store: Path) -> tuple[str, str]:
    """``previous`` and ``latest`` of a store, by id."""
    found = cli(store.parent, "--store", store, "inspect", "previous", "--event", "completed", "--json", "--limit", "1")
    latest = cli(store.parent, "--store", store, "inspect", "latest", "--event", "completed", "--json", "--limit", "1")
    return found.doc["run_id"], latest.doc["run_id"]


def _arms(frames: Sequence[Any], config_hash: str) -> list[Any]:
    """Each run's rows of one condition that ended in an outcome (the errored rows are in no
    share and no test)."""
    return [frame[(frame["config_hash"] == config_hash) & frame["outcome"].notna()] for frame in frames]


def _check_fisher(store: Path, runs: tuple[str, str]) -> int:
    from poisson_prove import stats

    doc = _diff_doc(store, "fisher_bh", *runs)
    for _, cell in _rows(doc):
        odds, p = stats.fisher_test(cell["events_a"], cell["n_a"], cell["events_b"], cell["n_b"])
        assert p == pytest.approx(cell["p"], rel=1e-9, abs=1e-12), cell["config_hash"]
        _same_statistic(odds, cell)
    return len(_rows(doc))


def _check_mcnemar(store: Path, runs: tuple[str, str]) -> int:
    from poisson_prove import stats

    doc = _diff_doc(store, "mcnemar_bh", *runs)
    fa, fb = _frames(store, *runs)
    horizon = doc["horizon"]
    for event, cell in _rows(doc):
        a, b = _arms((fa, fb), cell["config_hash"])
        joined = a.merge(b, on="replicate_index", suffixes=("_a", "_b"))
        hit_a = (joined["outcome_a"] == event) & (joined["t_a"].astype(float) <= horizon)
        hit_b = (joined["outcome_b"] == event) & (joined["t_b"].astype(float) <= horizon)
        only_a, only_b = int((hit_a & ~hit_b).sum()), int((~hit_a & hit_b).sum())
        assert len(joined) == cell["pairs"]
        statistic, p = stats.mcnemar_test(only_a, only_b)
        assert statistic == only_a - only_b
        assert p == pytest.approx(cell["p"], rel=1e-9, abs=1e-12), (event, cell["config_hash"])
    return len(_rows(doc))


def _check_logrank(store: Path, runs: tuple[str, str]) -> int:
    from poisson_prove import stats

    doc = _diff_doc(store, "logrank_bh", *runs)
    fa, fb = _frames(store, *runs)
    horizon = doc["horizon"]
    for event, cell in _rows(doc):
        arms = _arms((fa, fb), cell["config_hash"])
        assert [len(arm) for arm in arms] == [cell["n_a"], cell["n_b"]]
        times = [np.minimum(arm["t"].to_numpy(dtype=float), horizon) for arm in arms]
        hits = [((arm["outcome"] == event) & (arm["t"].astype(float) <= horizon)).to_numpy(dtype=bool) for arm in arms]
        chi_square, p = stats.logrank_test(times[0], hits[0], times[1], hits[1])
        assert p == pytest.approx(cell["p"], rel=1e-9, abs=1e-12), (event, cell["config_hash"])
        _same_statistic(chi_square, cell)
    return len(_rows(doc))


def _same_statistic(value: float, cell: Mapping[str, Any]) -> None:
    """The statistic the row reports beside its p: a number, or null where it is not a finite one
    (an odds ratio over an empty cell)."""
    if cell["stat"] is None:
        assert not math.isfinite(value), value
    else:
        assert value == pytest.approx(cell["stat"], rel=1e-9, abs=1e-12), (value, cell["stat"])


def _check_bh_and_holm(store: Path, runs: tuple[str, str]) -> int:
    from poisson_prove import stats

    count = 0
    for method in METHODS:
        doc = _diff_doc(store, method, *runs)
        rows = [cell for _, cell in _rows(doc) if cell["p"] is not None]
        p = np.array([cell["p"] for cell in rows], dtype=float)
        np.testing.assert_allclose(stats.bh(p, doc["q"]), [cell["q"] for cell in rows], rtol=1e-12)
        np.testing.assert_allclose(stats.holm(p, doc["q"]), [cell["q_holm"] for cell in rows], rtol=1e-12)
        count += len(rows)
    return count


def _check_wilson(store: Path, runs: tuple[str, str]) -> int:
    from poisson_prove import stats

    doc = _diff_doc(store, "fisher_bh", *runs)
    for _, cell in _rows(doc):
        for arm in ("a", "b"):
            share = cell[f"share_{arm}"]
            interval = stats.wilson(cell[f"events_{arm}"], cell[f"n_{arm}"], level=share["level"])
            assert (interval.lo, interval.hi, interval.level) == pytest.approx((share["lo"], share["hi"], share["level"]), abs=1e-12)
    return 2 * len(_rows(doc))


def _check_intervals(store: Path, runs: tuple[str, str], paired: bool) -> int:
    from poisson_prove import stats

    method = "mcnemar_bh" if paired else "fisher_bh"
    doc = _diff_doc(store, method, *runs)
    fa, fb = _frames(store, *runs)
    horizon = doc["horizon"]
    count = 0
    for event, cell in _rows(doc):
        if cell["ci_lo"] is None:
            continue
        alpha = 1.0 - cell["ci_level"]
        if paired:
            a, b = _arms((fa, fb), cell["config_hash"])
            joined = a.merge(b, on="replicate_index", suffixes=("_a", "_b"))
            hit_a = (joined["outcome_a"] == event) & (joined["t_a"].astype(float) <= horizon)
            hit_b = (joined["outcome_b"] == event) & (joined["t_b"].astype(float) <= horizon)
            lo, hi = stats.interval_rd_paired(int((hit_a & ~hit_b).sum()), int((~hit_a & hit_b).sum()), len(joined), alpha=alpha)
        else:
            lo, hi = stats.interval_rd(cell["events_a"], cell["n_a"], cell["events_b"], cell["n_b"], alpha=alpha)
        assert (lo, hi) == pytest.approx((cell["ci_lo"], cell["ci_hi"]), abs=1e-9), (event, cell["config_hash"])
        count += 1
    return count


def _check_aalen_johansen(store: Path, runs: tuple[str, str]) -> int:
    from poisson_prove import stats

    doc = _diff_doc(store, "fisher_bh", *runs)
    frames = _frames(store, *runs)
    horizon = doc["horizon"]
    for event, cell in _rows(doc):
        for arm, frame in zip(("a", "b"), frames, strict=True):
            rows = frame[(frame["config_hash"] == cell["config_hash"]) & frame["outcome"].notna()]
            # Every outcome present competes, the event among them even where it never happened.
            outcomes = sorted({str(o) for o in rows["outcome"]} | {event})
            curve = stats.aalen_johansen(rows["t"].to_numpy(dtype=float), rows["outcome"].to_numpy(dtype=object), outcomes)
            at = np.searchsorted(curve.times, horizon, side="right") - 1
            value = 0.0 if at < 0 else float(curve.cif[event][at])
            assert value == pytest.approx(cell[f"rate_{arm}"], abs=1e-12), (event, arm, cell["config_hash"])
    return 2 * len(_rows(doc))


def _check_kaplan_meier(store: Path, runs: tuple[str, str]) -> int:
    from lifelines import KaplanMeierFitter

    from poisson_prove import stats

    (frame,) = _frames(store, runs[0])
    event = _diff_doc(store, "fisher_bh", *runs)["events"][0]
    count = 0
    for _, rows in frame[frame["outcome"].notna()].groupby("config_hash"):
        t = rows["t"].to_numpy(dtype=float)
        observed = (rows["outcome"] == event).to_numpy(dtype=bool)
        if not observed.any():
            continue
        curve = stats.kaplan_meier(t, observed)
        fitter = KaplanMeierFitter().fit(t, observed)
        for time_, value in zip(curve.times, curve.survival, strict=True):
            assert value == pytest.approx(float(fitter.survival_function_at_times(time_).iloc[0]), abs=1e-12)
        count += 1
    return count


def _check_mde(store: Path, runs: tuple[str, str]) -> int:
    """No comparison prints this limit, so it is held to statsmodels on each condition's own
    baseline and sizes."""
    from statsmodels.stats.proportion import power_proportions_2indep

    from poisson_prove import stats

    count = 0
    doc = _diff_doc(store, "fisher_bh", *runs)
    cases = {(round(cell["rate_a"], 2), cell["n_a"], cell["n_b"]) for _, cell in _rows(doc) if 0.05 < cell["rate_a"] < 0.9}
    for p_a, n_a, n_b in sorted(cases)[:6]:
        delta = stats.mde_two_proportion(p_a, n_a, n_b, alpha=0.05, power=0.8)
        # statsmodels' sample 1 is the changed arm: diff, prop2 = the baseline, nobs1 = n_b.
        power = float(power_proportions_2indep(
            delta, p_a, n_b, ratio=n_a / n_b, alpha=0.05, alternative="two-sided", return_results=False,
        ))
        assert power == pytest.approx(0.8, abs=1e-6)
        count += 1
    return count


PF5_3_CHECKS: dict[str, Callable[[Path, tuple[str, str]], int]] = {
    "fisher_test": _check_fisher,
    "mcnemar_test": _check_mcnemar,
    "logrank_test": _check_logrank,
    "bh_and_holm": _check_bh_and_holm,
    "wilson": _check_wilson,
    "interval_rd": lambda store, runs: _check_intervals(store, runs, paired=False),
    "interval_rd_paired": lambda store, runs: _check_intervals(store, runs, paired=True),
    "aalen_johansen": _check_aalen_johansen,
    "kaplan_meier": _check_kaplan_meier,
    "mde_two_proportion": _check_mde,
}


#: Agreement with an outside library is the math suite's (reading x).
_LIBRARY_CHECKS = ("kaplan_meier", "mde_two_proportion")


@pytest.mark.parametrize(
    "function",
    [pytest.param(name, marks=pytest.mark.math) if name in _LIBRARY_CHECKS else name for name in sorted(PF5_3_CHECKS)],
)
def test_pf5_3_the_public_statistics_give_the_numbers_the_comparison_reports(function: str, quickstart: Path, _doc_cache: None) -> None:
    """PF5.3 and reading l: on every row of the two fixture pairs (the quickstart pair and the lattice pair),
    each public function given the row's counts or times gives the number and the statistic the
    comparison reports for it; ``kaplan_meier`` and ``mde_two_proportion``, whose numbers no
    comparison prints, agree with lifelines and statsmodels on the pairs' own conditions (those
    two in the math suite)."""
    store = quickstart / "prove-runs"
    checked = PF5_3_CHECKS[function](store, _pair_ids(store))
    checked += PF5_3_CHECKS[function](lattice.root(), (lattice.RUN_A, lattice.RUN_B))
    assert checked > 0


# ---------- PF5.4 ----------


def _compare_cases(store: Path) -> dict[str, tuple[list[str], Callable[[], Any]]]:
    from poisson_prove import compare
    from poisson_prove.store import Store

    return {
        "diff default": (["diff", "--json"], lambda: compare.diff(store)),
        "diff named": (["diff", "previous", "latest", "--method", "fisher_bh", "--json"],
                       lambda: compare.diff(Store(store), "previous", "latest", method="fisher_bh")),
        "diff log-rank": (["diff", "--method", "logrank_bh", "--event", "violated", "--json"],
                          lambda: compare.diff(str(store), events=["violated"], method="logrank_bh")),
        "check": (["check", "--event", "violated", "--event", "timeout", "--json"],
                  lambda: compare.check(store, events=["violated", "timeout"])),
        "check any": (["check", "--event", "violated", "--fail-on", "any", "--method", "fisher_bh", "--json"],
                      lambda: compare.check(Store(store), events=["violated"], fail_on="any", method="fisher_bh")),
    }


@pytest.mark.parametrize("case", ["diff default", "diff named", "diff log-rank", "check", "check any"])
def test_pf5_4_compare_diff_and_check_return_what_the_json_prints(case: str, quickstart: Path) -> None:
    """PF5.4: ``compare.diff`` and ``compare.check`` on the pair the command line compared return the
    document its ``--json`` prints, with the method and whether it was the default
    (``method_chosen``, ``named`` or ``default``); the store as a path, a string or a ``Store``."""
    from poisson_prove import compare

    store = quickstart / "prove-runs"
    argv, call = _compare_cases(store)[case]
    printed = cli(quickstart, "--store", store, *argv)
    assert printed.code in (0, 4), printed
    result = call()
    verb = argv[0]
    assert isinstance(result, compare.CheckResult if verb == "check" else compare.Comparison)
    assert_envelope(printed.doc, result, verb)
    named = "--method" in argv
    assert result.method == printed.doc["method"] == ("fisher_bh" if case in ("diff named", "check any") else
                                                     "logrank_bh" if case == "diff log-rank" else "mcnemar_bh")
    assert result.method_chosen == printed.doc["method_chosen"] == ("named" if named else "default")


def test_pf5_4_compare_runs_lists_what_runs_prints(named: Path) -> None:
    from poisson_prove import compare
    from poisson_prove.store import Store

    store = named / "prove-runs"
    printed = cli(named, "--store", store, "runs", "--json")
    for given in (store, str(store), Store(store)):
        listed = compare.runs(given)
        assert all(isinstance(run, compare.RunInfo) for run in listed)
        assert [run.run_id for run in listed] == [entry["run_id"] for entry in printed.doc["runs"]]
        assert [run.run_name for run in listed] == [entry["run_name"] for entry in printed.doc["runs"]]
        assert_envelope(printed.doc, listed, "runs")


RUN_FORMS = (
    "id", "computed name", "names-file name", "manifest name", "latest", "previous", "latest:mock-agent",
    "previous:mock-agent", "#1", "#2",
)


@pytest.mark.parametrize("form", RUN_FORMS)
def test_pf5_4_compare_resolve_resolves_every_run_form(form: str, named: Path) -> None:
    """PF5.4: every form a verb takes reaches the same run through
    ``compare.resolve``, given the store as a path or a ``Store``, as through the command line."""
    from poisson_prove import compare
    from poisson_prove.store import Store

    store = named / "prove-runs"
    entries = sorted(runs_doc(store), key=lambda e: e["created_at"])
    first, second = entries[0], entries[1]
    word, expected = {
        "id": (first["run_id"], first["run_id"]),
        "computed name": (_computed_name(store, first["run_id"]), first["run_id"]),
        "names-file name": ("first", first["run_id"]),
        "manifest name": ("baseline", second["run_id"]),
        "latest": ("latest", second["run_id"]),
        "previous": ("previous", first["run_id"]),
        "latest:mock-agent": ("latest:mock-agent", second["run_id"]),
        "previous:mock-agent": ("previous:mock-agent", first["run_id"]),
        "#1": ("#1", second["run_id"]),
        "#2": ("#2", first["run_id"]),
    }[form]
    assert compare.resolve(store, word) == expected
    assert compare.resolve(Store(store), word) == expected
    shown = cli(named, "--store", store, "inspect", word, "--event", "completed", "--json", "--limit", "1")
    assert shown.doc["run_id"] == expected


@pytest.mark.parametrize("word", ["a name no run has", "a bare 4-hex suffix", "a target with a slash"])
def test_pf5_4_compare_resolve_refuses_what_the_command_line_refuses(word: str, named: Path) -> None:
    """PF5.4: a word the command line refuses is ``compare.Refusal``, its text the
    command line's ``error:`` sentence."""
    from poisson_prove import compare

    store = named / "prove-runs"
    first = sorted(runs_doc(store), key=lambda e: e["created_at"])[0]["run_id"]
    typed = {"a name no run has": "no run has this name", "a bare 4-hex suffix": first[-4:],
             "a target with a slash": "latest:mock/agent"}[word]
    with pytest.raises(compare.Refusal) as refused:
        compare.resolve(store, typed)
    r = cli(named, "--store", store, "inspect", typed, "--event", "completed")
    assert r.code == 1, r
    assert r.errors == [f"error: {refused.value}"]


def _computed_name(store: Path, run_id: str) -> str:
    """The run's computed name: what it went by before the names file named it."""
    from poisson_prove.store import Store

    manifest = Store(store).manifest(run_id)
    day = manifest.created_at[:10]
    return f"{manifest.target_id.split('/')[0]} {day} a"


# ---------- PF5.5 ----------


def test_pf5_5_step_record_episode_and_rollout_import_from_the_top() -> None:
    namespace: dict[str, Any] = {}
    exec("from poisson_prove import step, record, Episode, Rollout", namespace)  # noqa: S102
    from poisson_prove import episode, trace

    assert namespace["step"] is trace.step
    assert namespace["record"] is trace.record
    assert namespace["Episode"] is episode.Episode
    assert namespace["Rollout"] is episode.Rollout


# ---------- PF5.6 ----------


def test_pf5_6_every_python_example_in_docs_python_runs(quickstart: Path, tmp_path: Path) -> None:
    """PF5.6 and reading p: every ``python`` block of ``docs/python.md`` runs, in order, each in a
    fresh namespace, from a folder whose ``./prove-runs`` holds the quickstart pair; every function
    of ``compare`` and ``stats`` is called in one."""
    text = DOCS_PYTHON.read_text(encoding="utf-8")
    blocks = re.findall(r"^```python\n(.*?)^```", text, flags=re.M | re.S)
    assert blocks
    copy_of(quickstart / "prove-runs", tmp_path / "prove-runs")
    with inside(tmp_path):
        for block in blocks:
            out = StringIO()
            namespace: dict[str, Any] = {"__name__": "__docs__"}
            with warnings.catch_warnings(record=True) as caught, _redirected(out):
                warnings.simplefilter("always")
                exec(compile(block, "docs/python.md", "exec"), namespace)  # noqa: S102
            assert [str(w.message) for w in caught if _provess(w)] == [], block
    for module in ("poisson_prove.compare", "poisson_prove.stats"):
        mod = importlib.import_module(module)
        for name in mod.__all__:
            if inspect.isfunction(getattr(mod, name)):
                assert any(re.search(rf"\b{name}\(", block) for block in blocks), f"{module}.{name} has no example"


@contextmanager
def _redirected(out: StringIO) -> Iterator[None]:
    before = sys.stdout
    sys.stdout = out
    try:
        yield
    finally:
        sys.stdout = before


# ---------- PF5.8 ----------


class Hazard(AssertionError):
    pass


def _provess(w: warnings.WarningMessage) -> bool:
    """A warning Prove raised (its category is Prove's or it was raised in Prove's code): the kind
    a face prints as a ``note:``. A library's own warnings are the library's."""
    module = getattr(w.category, "__module__", "") or ""
    return module.startswith("poisson_prove") or str(Path(w.filename).resolve()).startswith(str(PACKAGE))


@contextmanager
def hazards(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """``input``, ``sys.exit``, ``os._exit``, ``webbrowser.open`` and network sockets each fail and
    are recorded; Unix sockets and pipes stay open (multiprocessing uses them)."""
    used: list[str] = []

    def trip(what: str) -> Callable[..., Any]:
        def fail(*args: Any, **kwargs: Any) -> Any:
            used.append(what)
            raise Hazard(f"{what} used inside the core")

        return fail

    def guarded(name: str) -> Callable[..., Any]:
        real = getattr(socket.socket, name)

        def call(self: socket.socket, *args: Any) -> Any:
            if self.family != socket.AF_UNIX:
                used.append(f"socket.{name}")
                raise Hazard(f"socket.{name} used inside the core")
            return real(self, *args)

        return call

    monkeypatch.setattr(builtins, "input", trip("input"))
    monkeypatch.setattr(sys, "exit", trip("sys.exit"))
    monkeypatch.setattr(os, "_exit", trip("os._exit"))
    monkeypatch.setattr(webbrowser, "open", trip("webbrowser.open"))
    monkeypatch.setattr(webbrowser, "open_new_tab", trip("webbrowser.open_new_tab"))
    for name in ("connect", "connect_ex", "bind", "sendto"):
        monkeypatch.setattr(socket.socket, name, guarded(name))
    monkeypatch.setattr(socket, "getaddrinfo", trip("socket.getaddrinfo"))
    monkeypatch.setattr(socket, "create_connection", trip("socket.create_connection"))
    yield used


def _op_open_store(c: Any, qs: Path, tmp: Path) -> Any:
    return c.runs(c.open_store(qs / "prove-runs"))


def _op_plan_start(c: Any, qs: Path, tmp: Path) -> Any:
    spec = c.read_spec(write_spec(tmp, 4))
    p = c.plan(spec, store=c.open_store(tmp / "prove-runs"), overrides={"max_mde": 1})
    return c.start(p)


def _op_resume(c: Any, qs: Path, tmp: Path) -> Any:
    spec = c.read_spec(write_spec(tmp, 4))
    store = c.open_store(tmp / "prove-runs")
    first = c.start(c.plan(spec, store=store, overrides={"max_mde": 1, "max_rollouts": 5}))
    return c.resume(store, first.run_id)


PF5_8_OPERATIONS: dict[str, Callable[[Any, Path, Path], Any]] = {
    "open_store and runs": _op_open_store,
    "resolve": lambda c, qs, tmp: c.resolve(c.open_store(qs / "prove-runs"), "latest"),
    "run": lambda c, qs, tmp: c.run(c.open_store(qs / "prove-runs"), "previous"),
    "episodes": lambda c, qs, tmp: c.episodes(c.open_store(qs / "prove-runs"), "latest", event="violated", limit=5),
    "init": lambda c, qs, tmp: c.init(tmp / "prove.toml", example=True),
    "read_spec": lambda c, qs, tmp: c.read_spec(PACKAGED),
    "plan and start": _op_plan_start,
    "resume": _op_resume,
    "compare": lambda c, qs, tmp: c.compare(c.open_store(qs / "prove-runs")),
    "compare, a test named on paired runs": lambda c, qs, tmp: c.compare(c.open_store(qs / "prove-runs"), method="fisher_bh", methods="all"),
    "check": lambda c, qs, tmp: c.check(c.open_store(qs / "prove-runs"), events=["violated"]),
    "inspect": lambda c, qs, tmp: c.inspect(c.open_store(qs / "prove-runs"), "latest", event="violated"),
    "paired": lambda c, qs, tmp: c.paired(c.open_store(_paired_fixture(tmp)[0]), _paired_fixture(tmp / "again")[1]),
    "a refusal": lambda c, qs, tmp: c.resolve(c.open_store(qs / "prove-runs"), "no run has this name"),
}


@pytest.mark.parametrize("operation", sorted(PF5_8_OPERATIONS))
def test_pf5_8_core_operations_print_ask_exit_open_and_connect_nothing(
    operation: str, quickstart: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """PF5.8 on the quickstart pair (reading v): each operation in process writes nothing to stdout
    or stderr (the file descriptors, so a child process counts too), lets no warning out (Python
    prints those to stderr), and never asks, exits, opens a browser or connects; a refusal is
    ``core.Refusal`` and prints nothing either."""
    c = core()
    (tmp_path / "again").mkdir()
    gc.collect()  # what an earlier test left behind is not this operation's
    capfd.readouterr()
    with hazards(monkeypatch) as used, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with inside(tmp_path):
            try:
                PF5_8_OPERATIONS[operation](c, quickstart, tmp_path)
            except c.Refusal:
                assert operation == "a refusal"
            else:
                assert operation != "a refusal"
    out, err = capfd.readouterr()
    assert (out, err) == ("", ""), (out, err)
    assert used == []
    assert [str(w.message) for w in caught if _provess(w)] == []


def _modules() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = path.relative_to(SRC).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        found[".".join(parts)] = path
    return found


def _class_of(module: str) -> str | None:
    """A module's class: as listed, or for a module PF5 adds, by where it sits or what it is named
    (reading g): under ``poisson_prove.core`` the core, ``poisson_prove._cli_*`` the face's own,
    ``poisson_prove._render_*`` a renderer."""
    if module in FACES or module.startswith("poisson_prove._cli_"):
        return "face"
    if module in RENDERERS or module.startswith("poisson_prove._render_"):
        return "renderer"
    if module in CORE or module.startswith("poisson_prove.core."):
        return "core"
    return None


def _env_reads(path: Path) -> tuple[set[str], list[str]]:
    """The variables a module reads (reading s) and every use of the environment that is not one;
    a name is a string, or a string constant the module defines or imports from Prove."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = {
        target.id: node.value.value
        for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and isinstance(getattr(node, "value", None), ast.Constant)
        and isinstance(node.value.value, str)
    }
    aliases: dict[str, set[str]] = {"environ": set(), "getenv": set(), "os": {"os"}}
    package = ".".join(path.relative_to(SRC).with_suffix("").parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases["os"] |= {alias.asname for alias in node.names if alias.name == "os" and alias.asname}
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name in aliases:
                    aliases[alias.name].add(alias.asname or alias.name)
        module = node.module if isinstance(node, ast.ImportFrom) else None
        if isinstance(node, ast.ImportFrom) and node.level:
            # A relative import of a constant, ``from .<module> import ENV_STORE``.
            anchor = package.split(".")[: len(package.split(".")) - node.level + 1]
            module = ".".join([*anchor, *([node.module] if node.module else [])])
        if isinstance(node, ast.ImportFrom) and (module or "").startswith("poisson_prove"):
            source = importlib.import_module(module or "")
            for alias in node.names:
                value = getattr(source, alias.name, None)
                if isinstance(value, str):
                    constants[alias.asname or alias.name] = value

    def is_environ(node: ast.AST) -> bool:
        return (
            (isinstance(node, ast.Attribute) and node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id in aliases["os"])
            or (isinstance(node, ast.Name) and node.id in aliases["environ"])
        )

    def name_of(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and node.id in constants:
            return constants[node.id]
        return None

    reads: set[str] = set()
    explained: set[int] = set()
    problems: list[str] = []
    for node in ast.walk(tree):
        found: ast.AST | None = None
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get" and is_environ(func.value) and node.args:
                found = node.args[0]
                explained.add(id(func.value))
            elif (isinstance(func, ast.Attribute) and func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id in aliases["os"]) or (isinstance(func, ast.Name) and func.id in aliases["getenv"]):
                found = node.args[0] if node.args else None
                if found is None:
                    problems.append(f"line {node.lineno}: getenv with no name")
            elif isinstance(func, ast.Attribute) and func.attr == "copy" and is_environ(func.value):
                explained.add(id(func.value))
            elif isinstance(func, ast.Name) and func.id == "dict" and node.args and is_environ(node.args[0]):
                explained.add(id(node.args[0]))
        elif isinstance(node, ast.Subscript) and is_environ(node.value):
            found = node.slice
            explained.add(id(node.value))
        elif isinstance(node, ast.Compare) and any(is_environ(c) for c in node.comparators):
            found = node.left
            explained |= {id(c) for c in node.comparators if is_environ(c)}
        elif isinstance(node, ast.Dict) and any(k is None and is_environ(v) for k, v in zip(node.keys, node.values, strict=True)):
            explained |= {id(v) for k, v in zip(node.keys, node.values, strict=True) if k is None}
        if found is not None:
            name = name_of(found)
            if name is None:
                problems.append(f"line {node.lineno}: reads a variable whose name is not written out")
            else:
                reads.add(name)
    for node in ast.walk(tree):
        if is_environ(node) and id(node) not in explained and not (isinstance(node, ast.Name) and isinstance(getattr(node, "ctx", None), ast.Store)):
            problems.append(f"line {getattr(node, 'lineno', '?')}: uses the environment other than to read a named variable")
    return reads, problems


def test_pf5_8_prove_reads_only_the_environment_variables_it_documents() -> None:
    """PF5.8's one source check (reading s): the core reads ``POISSON_PROVE_STORE`` (and the
    retired ``PROOFLOAD_STORE``, to say so), the faces and renderers ``NO_COLOR``, ``CI`` and
    ``TERM``, the Modal and Burla workers' batch the BLAS thread counts (PF10), and nothing else
    reads any."""
    problems: list[str] = []
    for module, path in _modules().items():
        reads, odd = _env_reads(path)
        allowed = (CORE_ENV if _class_of(module) == "core" else FACE_ENV) | WORKER_ENV.get(module, frozenset())
        problems += [f"{module}: {p}" for p in odd]
        if reads - allowed:
            problems.append(f"{module} reads {sorted(reads - allowed)}")
    assert not problems, problems


# ---------- PF5.9 ----------


def _sweep_folder(tmp_path: Path) -> Path:
    write_spec(tmp_path, 6)
    return tmp_path


def _verb_case(verb: str, tmp_path: Path, quickstart: Path) -> tuple[Path, list[Any], str, str]:
    """(the folder, the command, the core operation it calls, the verb's schema name)."""
    qs = quickstart / "prove-runs"
    if verb.startswith("paired"):
        paired_store, declaration = _paired_fixture(tmp_path)
        cap = ["--cap-check"] if verb.endswith("--cap-check") else []
        return tmp_path, ["--store", paired_store, "paired", "--declaration", declaration, *cap, "--json"], "paired", "paired"
    if verb.startswith("sweep"):
        _sweep_folder(tmp_path)
        how = ["--dry-run"] if verb.endswith("the plan") else ["--yes"]
        return tmp_path, ["sweep", *how, *LOOSE, "--json"], "plan" if how == ["--dry-run"] else "start", "sweep"
    return {
        "init": (tmp_path, ["init", "--out", "spec.toml", "--json"], "init", "init"),
        "diff": (quickstart, ["--store", qs, "diff", "--json"], "compare", "diff"),
        "check": (quickstart, ["--store", qs, "check", "--event", "violated", "--json"], "check", "check"),
        "inspect": (quickstart, ["--store", qs, "inspect", "latest", "--event", "violated", "--json"], "inspect", "inspect"),
        "runs": (quickstart, ["--store", qs, "runs", "--json"], "runs", "runs"),
    }[verb]


@pytest.mark.parametrize("verb", [
    "init", "sweep, the plan", "sweep, done", "diff", "check", "inspect", "runs", "paired", "paired --cap-check",
])
def test_pf5_9_each_verbs_json_is_the_core_result_inside_the_envelope(
    verb: str, quickstart: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PF5.9 and reading h: the operation the verb called returned one result, whose ``to_json()``
    is strict, carries a schema, and is what the verb printed, the verb's schema in place."""
    cwd, argv, operation, schema = _verb_case(verb, tmp_path, quickstart)
    with spying(monkeypatch, operation) as seen:
        printed = cli(cwd, *argv)
    assert printed.code in (0, 4), printed
    assert len(seen[operation]) == 1
    assert_envelope(printed.doc, seen[operation][0], schema)


@pytest.mark.parametrize("verb", ["report, two runs", "report, one run", "serve"])
def test_pf5_9_report_and_serve_carry_the_core_results_facts(
    verb: str, quickstart: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reading h: ``report`` and ``serve`` render what ``compare`` (``report RUN``: ``run``) returned
    and say it in their own envelope: every key the comparison's document shares with theirs holds
    the same value, and the page's Summary carries its facts."""
    # A writing verb runs on a copy: the shared store stays as it was built.
    qs = copy_of(quickstart / "prove-runs", tmp_path / "store")
    if verb == "report, one run":
        with spying(monkeypatch, "run") as seen:
            printed = cli(tmp_path, "--store", qs, "report", "latest", "--x", "task_id", "--y", "tool_fail_rate", "--json", "--out", tmp_path / "r")
        assert printed.code == 0, printed
        (detail,) = seen["run"]
        doc = inner(detail)
        for key in ("run_id", "run_name", "events", "non_event", "horizon", "by_event", "design_mde"):
            assert printed.doc[key] == doc[key], key
        return
    argv = (["report", "--x", "task_id", "--y", "tool_fail_rate", "--out", tmp_path / "r"] if verb != "serve"
            else ["serve", "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--event", "timeout"])
    with spying(monkeypatch, "compare") as seen:
        printed = cli(tmp_path, "--store", qs, *argv, "--json")
    assert printed.code == 0, printed
    (comparison,) = seen["compare"]
    doc = inner(comparison)
    if verb == "serve":
        assert printed.doc["method"] == doc["method"] and printed.doc["method_chosen"] == doc["method_chosen"]
        summary = printed.doc["summary"]
        for key in ("verdict", "verdict_limit", "fragility", "peeking", "errors_differ"):
            assert summary[key] == doc[key], key
        return
    shared = set(doc) & set(printed.doc) - {"schema", "verdict", "sentence", "next"}
    assert {"method", "method_chosen", "by_event", "fragility", "verdict_limit", "intervals"} <= shared
    for key in shared:
        assert printed.doc[key] == doc[key], key
    assert printed.doc["comparison_verdict"] == doc["verdict"]


def test_pf5_9_the_episodes_and_the_run_are_documents_that_agree_with_inspect(quickstart: Path) -> None:
    """PF5.9 for the two results no verb prints whole (reading h): ``episodes`` and ``run`` are strict
    documents with a schema; an episode page holds the episodes ``inspect`` lists, in its order,
    from ``offset``, ``limit`` of them, in one condition when it is given; the run's document names
    the run as ``inspect`` does."""
    c = core()
    qs = quickstart / "prove-runs"
    store = c.open_store(qs)
    printed = cli(quickstart, "--store", qs, "inspect", "latest", "--event", "violated", "--json")
    listed = printed.doc["episodes"]
    assert len(listed) > 5
    assert inner(c.episodes(store, "latest", event="violated", limit=5))["episodes"] == listed[:5]
    assert inner(c.episodes(store, "latest", event="violated", offset=2, limit=3))["episodes"] == listed[2:5]
    condition = listed[-1]["config_hash"]
    page = inner(c.episodes(store, "latest", event="violated", condition=condition))
    assert page["episodes"] == [e for e in listed if e["config_hash"] == condition]
    detail = inner(c.run(store, "latest"))
    assert (detail["run_id"], detail["run_name"]) == (printed.doc["run_id"], printed.doc["run_name"])


# ---------- PF5.10 ----------


def _events_file(store: Path, run_id: str) -> list[dict[str, Any]]:
    lines = (store / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [strict_json(line) for line in lines]


GRAMMAR_FIRST = re.compile(r"^planned started (progress |note )*(finished|interrupted)$")
GRAMMAR_AGAIN = re.compile(r"^resumed (progress |note )*(finished|interrupted)$")


def _events_so_far(store: Path) -> list[dict[str, Any]]:
    """The one run's event log as it stands, whole lines only."""
    (log,) = list(store.glob("*/events.jsonl"))
    text = log.read_text(encoding="utf-8")
    return [strict_json(line) for line in text.splitlines(keepends=True) if line.endswith("\n")]


def _kinds(events: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(str(e["kind"]) for e in events)


def _assert_progress(events: Sequence[Mapping[str, Any]], clock: Sequence[float]) -> None:
    progress = [i for i, e in enumerate(events) if e["kind"] == "progress"]
    assert progress, _kinds(events)
    for e in (events[i] for i in progress):
        assert {"done", "kept", "errored", "total"} <= set(e["detail"]), e
    # The last progress comes just before the end; every earlier one is at least a second after
    # the one before it.
    assert progress[-1] == len(events) - 2 or all(events[j]["kind"] == "note" for j in range(progress[-1] + 1, len(events) - 1))
    # A tolerance of 0.2 s for a face that is handed its events through a queue.
    earlier = progress[:-1]
    for before, after in zip(earlier, earlier[1:], strict=False):
        assert clock[after] - clock[before] >= 0.8, (clock[before], clock[after])


def test_pf5_10_start_reports_its_events_in_order_and_writes_them_to_the_run(
    rollouts: Any, tmp_path: Path
) -> None:
    """PF5.10 and reading t: ``planned``, ``started``, ``progress`` at most once a second plus once
    just before ``finished``; every event is a strict ``poisson.run-event/1`` document; the run's
    ``events.jsonl`` holds the same events, in order."""
    c = core()
    rollouts.reset(SLEEP=0.035)
    spec = c.read_spec(write_spec(tmp_path, 15))
    store = c.open_store(tmp_path / "prove-runs")
    p = c.plan(spec, store=store, overrides={"max_mde": 1, "target": "pf5_rollouts:steered"})
    received: list[dict[str, Any]] = []
    clock: list[float] = []

    lagging: list[str] = []

    def on_event(event: Any) -> None:
        clock.append(time.monotonic())
        doc = as_json(event.to_json())
        if doc["kind"] == "progress" and received:
            # Appended line by line: by the time a progress event reaches the face, the run's log
            # holds every event before it, so a live view can tail it.
            logged = _events_so_far(tmp_path / "prove-runs")
            if logged[: len(received)] != received:
                lagging.append(doc["kind"])
        received.append(doc)

    result = c.start(p, on_event=on_event)
    assert lagging == [], lagging
    assert GRAMMAR_FIRST.match(_kinds(received)), _kinds(received)
    for e in received:
        assert list(e)[:4] == ["schema", "at", "kind", "detail"] and e["schema"] == "poisson.run-event/1"
        assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z$", e["at"])
    _assert_progress(received, clock)
    last = [e for e in received if e["kind"] == "progress"][-1]["detail"]
    assert last["done"] == last["total"] == 60 and last["kept"] == 60 and last["errored"] == 0
    assert received[-1]["detail"]["status"] == "complete"
    assert _events_file(tmp_path / "prove-runs", result.run_id) == received


def _kept_keys(store: Path, run_id: str) -> list[tuple[str, int]]:
    frame = _frames(store, run_id)[0]
    return sorted(zip(frame["config_hash"].astype(str), frame["replicate_index"].astype(int), strict=True))


def test_pf5_10_cancel_leaves_what_ctrl_c_leaves_and_resume_finishes_the_run(
    rollouts: Any, tmp_path: Path
) -> None:
    """PF5.10 and reading t: ``cancel`` set during rollout 8 stops the run at the next boundary,
    ``partial`` and resumable, with exactly the rows a Ctrl-C at the start of rollout 9 leaves under
    ``sweep``, whose run also ends its log with ``interrupted``; ``resume`` then appends
    ``resumed`` ... ``finished`` to the same log and completes the run."""
    c = core()
    cancelled_root, interrupted_root = tmp_path / "cancelled", tmp_path / "interrupted"
    for folder in (cancelled_root, interrupted_root):
        folder.mkdir()
        write_spec(folder, 5)

    token = threading.Event()
    rollouts.reset(CANCEL=token, CANCEL_AT=7)
    spec = c.read_spec(cancelled_root / "prove.toml")
    store = c.open_store(cancelled_root / "prove-runs")
    p = c.plan(spec, store=store, overrides={"max_mde": 1, "target": "pf5_rollouts:steered", "salt": SALT})
    first: list[dict[str, Any]] = []
    first_clock: list[float] = []

    def on_first(event: Any) -> None:
        first_clock.append(time.monotonic())
        first.append(as_json(event.to_json()))

    stopped = c.start(p, on_event=on_first, cancel=token)
    assert stopped.verdict == "stopped"
    assert GRAMMAR_FIRST.match(_kinds(first)) and first[-1]["kind"] == "interrupted", _kinds(first)
    _assert_progress(first, first_clock)

    rollouts.reset(INTERRUPT_AT=8)
    r = cli(interrupted_root, "sweep", "--yes", *LOOSE, "--target", "pf5_rollouts:steered", "--salt", SALT)
    assert r.code == 130, r
    (other,) = [e["run_id"] for e in runs_doc(interrupted_root / "prove-runs")]
    logged = _events_file(interrupted_root / "prove-runs", other)
    assert GRAMMAR_FIRST.match(_kinds(logged)) and logged[-1]["kind"] == "interrupted", _kinds(logged)

    kept = _kept_keys(cancelled_root / "prove-runs", stopped.run_id)
    assert len(kept) == 8
    assert kept == _kept_keys(interrupted_root / "prove-runs", other)
    statuses = {e["run_id"]: e["status"] for e in [*runs_doc(cancelled_root / "prove-runs"), *runs_doc(interrupted_root / "prove-runs")]}
    assert statuses == {stopped.run_id: "partial", other: "partial"}

    rollouts.reset()
    again: list[dict[str, Any]] = []
    again_clock: list[float] = []

    def on_again(event: Any) -> None:
        again_clock.append(time.monotonic())
        again.append(as_json(event.to_json()))

    finished = c.resume(store, stopped.run_id, on_event=on_again)
    assert finished.run_id == stopped.run_id and finished.verdict == "done"
    assert GRAMMAR_AGAIN.match(_kinds(again)), _kinds(again)
    _assert_progress(again, again_clock)
    assert _events_file(cancelled_root / "prove-runs", stopped.run_id) == [*first, *again]
    assert len(_kept_keys(cancelled_root / "prove-runs", stopped.run_id)) == 20
    assert runs_doc(cancelled_root / "prove-runs")[0]["status"] == "complete"


# ---------- PF5.11 ----------


def test_pf5_11_the_plain_commands_and_the_core_give_equal_results_and_see_each_others_runs(tmp_path: Path) -> None:
    """PF5.11 and reading u: sweep, sweep paired, compare and check, once by the plain commands in
    child processes and once through the core in this process, from one salt: the comparison and
    the check are the same documents, the runs the same but for their ids and times; and each
    face, on the other's store, sees its runs and gives the same comparison."""
    c = core()
    plain_root, core_root = tmp_path / "plain", tmp_path / "core"
    for folder in (plain_root, core_root):
        folder.mkdir()
        write_spec(folder, 20)
    env = {k: v for k, v in os.environ.items() if k not in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE")}

    def child(*argv: str) -> Any:
        done = subprocess.run(
            [sys.executable, "-m", "poisson_prove", *argv], cwd=plain_root, env=env,
            capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
        )
        assert done.returncode in (0, 4), done.stderr
        return strict_json(done.stdout)

    child("sweep", "--yes", *LOOSE, "--salt", SALT, "--json")
    child("sweep", "--yes", *LOOSE, "--target", PATCHED, "--pair-with", "latest", "--json")
    plain_diff = child("diff", "--json")
    plain_check = child("check", "--event", "violated", "--json")

    with inside(core_root):
        spec = c.read_spec(core_root / "prove.toml")
        store = c.open_store(core_root / "prove-runs")
        c.start(c.plan(spec, store=store, overrides={"max_mde": 1, "salt": SALT}))
        c.start(c.plan(spec, store=store, overrides={"max_mde": 1, "target": PATCHED, "pair_with": "latest"}))
        core_diff = inner(c.compare(store))
        core_check = inner(c.check(store, events=["violated"]))
        plain_store_seen = c.runs(c.open_store(plain_root / "prove-runs"))
        crossed = inner(c.compare(c.open_store(plain_root / "prove-runs")))

    assert plain_diff == {**core_diff, "schema": "poisson-prove.diff/1"}
    assert plain_check == {**core_check, "schema": "poisson-prove.check/1"}
    assert crossed == core_diff

    def without_identity(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in e.items() if k not in ("run_id", "created_at")} for e in entries]

    plain_runs = child("runs", "--json")["runs"]
    core_runs = runs_doc(core_root / "prove-runs")
    assert without_identity(plain_runs) == without_identity(core_runs)
    assert [run.run_id for run in plain_store_seen] == [e["run_id"] for e in plain_runs]
    seen_by_plain = subprocess.run(
        [sys.executable, "-m", "poisson_prove", "--store", str(core_root / "prove-runs"), "diff", "--json"],
        cwd=plain_root, env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
    )
    assert seen_by_plain.returncode == 0, seen_by_plain.stderr
    assert strict_json(seen_by_plain.stdout) == plain_diff


# ---------- carried items ----------

COMPARISON_FACTS = (
    "verdict", "sentence", "next", "method", "method_chosen", "threshold", "threshold_source", "verdict_limit",
    "fragility", "fragility_flips", "fragility_note", "fragility_exact", "n_flagged_only", "peeking",
    "errors_differ",
)


def test_pf5_carried_the_comparison_exposes_every_fact_the_statistics_return(facts: Path) -> None:
    """Item 5 and reading m: the word Holm's rows make, each row's Benjamini-Hochberg flag and Holm
    count, its limits both ways, its interval on the change, the fragility, the peeking caveat
    and the errors that differ are attributes of ``compare.diff``'s result, each the value its
    JSON carries, on a pair where none of them is empty."""
    from poisson_prove import compare

    store = facts / "prove-runs"
    by_name = {e["run_name"]: e["run_id"] for e in runs_doc(store)}
    result = compare.diff(store, "facts a", "facts b")
    doc = inner(result)
    for key in COMPARISON_FACTS:
        assert as_json(getattr(result, key)) == doc[key], key
    rows = as_json(list(result.rows))
    assert rows == [{**cell, "event": event} for event, cell in _rows(doc)]
    for row in rows:
        assert {"p", "q", "q_holm", "holm", "mde_rise", "mde_fall", "ci_lo", "ci_hi", "ci_level", "ci_method"} <= set(row)
    assert result.peeking and {p["run_id"] for p in result.peeking} == {by_name["facts b"]}
    assert result.errors_differ
    assert result.fragility is not None and len(result.fragility_flips) == result.fragility
    assert result.verdict == doc["comparison_verdict"]


def _mixed_store(rollouts: Any, tmp_path: Path) -> Path:
    write_spec(tmp_path, 6)
    for target in ("pf5_rollouts:mixed", "pf5_rollouts:mixed"):
        r = cli(tmp_path, "sweep", "--yes", *LOOSE, "--target", target)
        assert r.code == 0, r
    return tmp_path / "prove-runs"


REFUSALS = ("an unknown run", "a condition that ran several cases", "an unknown key in the spec", "an underpowered design")


@pytest.mark.parametrize("refusal", REFUSALS)
def test_pf5_carried_a_core_refusal_is_the_error_line_the_face_prints(
    refusal: str, rollouts: Any, quickstart: Path, tmp_path: Path
) -> None:
    """Item 5 (the case-axis refusal) and reading e: the core refuses with ``core.Refusal`` and the
    plain command prints its sentence as the ``error:`` line, exit 1; the underpowered design's
    plan stays on stdout."""
    c = core()
    qs = quickstart / "prove-runs"
    if refusal == "an unknown run":
        call = lambda: c.compare(c.open_store(qs), "latest", "not a run")  # noqa: E731
        r = cli(quickstart, "--store", qs, "diff", "latest", "not a run")
    elif refusal == "a condition that ran several cases":
        store = _mixed_store(rollouts, tmp_path)
        call = lambda: c.compare(c.open_store(store))  # noqa: E731
        r = cli(tmp_path, "diff")
    elif refusal == "an unknown key in the spec":
        spec = write_spec(tmp_path, 6, "broken.toml")
        spec.write_text(spec.read_text(encoding="utf-8").replace("replicates =", "replicate ="), encoding="utf-8")
        call = lambda: c.read_spec(spec)  # noqa: E731
        r = cli(tmp_path, "sweep", spec, "--dry-run")
    else:
        spec = write_spec(tmp_path, 30)
        call = lambda: c.plan(c.read_spec(spec), store=c.open_store(tmp_path / "prove-runs"))  # noqa: E731
        r = cli(tmp_path, "sweep", spec, "--dry-run")
    with pytest.raises(c.Refusal) as refused:
        call()
    assert r.code == 1, r
    assert r.errors == [f"error: {refused.value}"]
    nexts = [line for line in r.err.splitlines() if line.startswith("  next: ")]
    if refusal == "an underpowered design":
        # Its offers are the command as typed with --replicates or --max-mde set, which only the
        # face knows; the core's are the same offers for the words it was given.
        assert r.out.startswith("plan  ")
        assert len(nexts) == len(refused.value.next) > 0
    else:
        assert r.out == ""
        assert nexts == [f"  next: {command}" for command in refused.value.next]
    from poisson_prove import compare

    assert compare.Refusal is c.Refusal
    if refusal == "a condition that ran several cases":
        with pytest.raises(compare.Refusal):
            compare.diff(tmp_path / "prove-runs")


def test_pf5_carried_the_method_line_and_the_notes_come_from_the_result(
    quickstart: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Items 2 and 5, reading n: the ``method`` line of the comparison's ``detail`` is the one
    ``diff`` prints and the one ``report.md``, ``receipt.html``, the page and its Summary carry; its
    facts lines are in every one of them; ``diff --methods all``'s pairing notes are the result's
    ``notes``."""
    from poisson_prove import cli as face

    # A writing verb runs on a copy: the shared store stays as it was built.
    qs = copy_of(quickstart / "prove-runs", tmp_path / "store")
    pages: list[str] = []
    # The page the face would serve, taken where it hands it to the server; nothing binds.
    monkeypatch.setattr(face, "serve_page", lambda page, on_bind: pages.append(page))
    with spying(monkeypatch, "compare") as seen:
        shown = cli(quickstart, "--store", qs, "diff", "--methods", "all")
        written = cli(tmp_path, "--store", qs, "report", "--x", "task_id", "--y", "tool_fail_rate", "--out", tmp_path / "r")
        served = cli(tmp_path, "--store", qs, "serve", "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--event", "timeout")
    assert shown.code == written.code == served.code == 0, (shown, written, served)
    diffed, reported, _ = seen["compare"][:3]
    assert diffed.notes and shown.notes == [f"note: {n}" for n in diffed.notes]
    assert any("seed" in n for n in diffed.notes)
    detail = list(diffed.detail)
    assert shown.out.splitlines()[0] == f"{diffed.verdict}  {diffed.sentence}"
    assert shown.out.splitlines()[1 : 1 + len(detail)] == [f"  {label}  {text}" for label, text in detail]
    (method,) = [text for label, text in detail if label == "method"]
    markdown = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    receipt = visible((tmp_path / "r" / "receipt.html").read_text(encoding="utf-8"))
    (page,) = pages
    found = re.search(r"<h2\b[^>]*>\s*Summary\s*</h2>(.*?)(?=<h2\b|$)", page, flags=re.S | re.I)
    assert found, "the page has no Summary section"
    summary = visible(found.group(1))
    assert method in header_of(markdown)
    for surface in (receipt, visible(page), summary):
        assert " ".join(method.split()) in surface
    for label, text in reported.detail:
        if label in ("method", "before", "after", "trade", "threshold", "comparison"):
            continue
        assert " ".join(text.split()) in " ".join(markdown.split()), label
        assert " ".join(text.split()) in receipt, label


@pytest.mark.parametrize("verb", ["check", "sweep"])
def test_pf5_carried_the_plain_text_is_the_results_lines(
    verb: str, quickstart: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Items 2 and 5, reading n, for the other verbs whose text is a verdict block: ``check``
    prints the result's verdict line and its ``detail`` lines, ``sweep`` its verdict line, its
    ``details`` and its ``next`` commands, as the result carries them (``diff`` is the method-line
    test's)."""
    if verb == "check":
        with spying(monkeypatch, "check") as seen:
            r = cli(quickstart, "--store", quickstart / "prove-runs", "check", "--event", "violated")
        (result,) = seen["check"]
        lines = r.out.splitlines()
        assert lines[0] == f"{result.verdict}  {result.sentence}"
        assert lines[1 : 1 + len(result.detail)] == [f"  {label}  {text}" for label, text in result.detail]
        return
    write_spec(tmp_path, 6)
    with spying(monkeypatch, "start") as seen:
        r = cli(tmp_path, "sweep", "--yes", *LOOSE)
    assert r.code == 0, r
    (result,) = seen["start"]
    lines = r.out.splitlines()
    at = lines.index(f"{result.verdict}  {result.sentence}")
    expected = [f"  {label}  {value}" for label, value in result.details] + [f"  next: {n}" for n in result.next]
    assert lines[at + 1 :] == expected


def test_pf5_carried_the_report_header_names_each_run_with_its_id_once(quickstart: Path, tmp_path: Path) -> None:
    """Item 3, reading o: ``report.md``'s header and the receipt's carry ``before  NAME (ID)`` and
    ``after  NAME (ID)``, and each run's id is in each file exactly once."""
    # A writing verb runs on a copy: the shared store stays as it was built.
    qs = copy_of(quickstart / "prove-runs", tmp_path / "store")
    r = cli(tmp_path, "--store", qs, "report", "--x", "task_id", "--y", "tool_fail_rate", "--out", tmp_path / "r")
    assert r.code == 0, r
    entries = {e["run_id"]: e["run_name"] for e in runs_doc(qs)}
    before, after = _pair_ids(qs)
    markdown = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    receipt = visible((tmp_path / "r" / "receipt.html").read_text(encoding="utf-8"))
    head = header_of(markdown).splitlines()
    assert f"before  {entries[before]} ({before})" in head
    assert f"after  {entries[after]} ({after})" in head
    assert f"before {entries[before]} ({before})" in receipt
    assert f"after {entries[after]} ({after})" in receipt
    for run_id in (before, after):
        assert markdown.count(run_id) == 1, run_id
        assert receipt.count(run_id) == 1, run_id
