"""PF9 -- backends and platforms: the Modal extra's floor and its plan, the Burla extra and its
label, and the refusal on Windows (*Prove -- Spec Front Door*, sections 3.2, 3.3, 8.6, 8.7
and PF9.1 to PF9.4; Q31 and Q34, ruled yes 2026-10-13; the Burla pin moved to exactly 1.8.2 and its
relay line rewritten by the pin fix of 2026-10-14; the PF0 freeze's yes/no 5, ruled yes 2026-10-14,
which gives PF9 the Burla install line).

**What is pinned is public behaviour.** The command line in this process (``cli.main`` with string
streams, as every frozen command-line test drives it), the package's declared extras (read from
``pyproject.toml``, the file the wheel's metadata is built from), the store, the ledger file a
Burla run writes. Facts are pinned, never prose: the price table's date, that the estimate is of
compute and not of model tokens, the switch ``DISABLE_BURLA_RELAY=True``, the pin, the install line.

**Fakes sit at the backend boundary only.** Modal and Burla are never imported for real here.
A test that needs one present puts a package of that name, with a ``dist-info`` giving its version,
first on ``sys.path``; it is findable and its version readable, and nothing of it runs. A test that
needs ``burla`` missing puts a finder first on ``sys.meta_path`` that refuses to find or import it,
so the case holds where the real client is installed: missing means not importable in Prove's
interpreter, which is what the launcher needs (reading r2). Burla's launcher is the backend's own
seam, ``executor_burla._launcher_argv``, pointed at ``tests/bu_fixtures/launch.py`` with the fake
client of ``tests/bu_fixtures/burla``, as ``test_bu_burla_backend.py`` points it. The fake reports
the version a test writes into its ``script.json`` and refuses any call it gets, so no worker pool
is needed and a launcher that reaches Burla ends at once, with the call on record.

**Sockets are blocked** in this module and in every module that drives a remote backend offline
(PF9.4), by ``conftest.py``'s guard; the fake's own interpreters arm their tripwire as before.

**Readings this file freezes** (each owed as one yes/no in the project's
the freeze's records; the build is written against them unedited):

- **r1** The ``[burla]`` extra pins exactly the client the backend runs, ``burla==1.8.2`` (the spec's
  ``==1.8.1`` predates the 2026-10-14 pin): the extra admits a version exactly when the backend
  runs it. Under the alternative, a floor, the 1.8.3 and 1.9.0 cases flip.
- **r2** A ``burla`` that Prove's interpreter cannot import is refused before the plan, as a missing
  ``modal`` is (sections 3.2 and PF1.2; "one line" read as the look's refusal: one ``error:`` line,
  then ``next:`` lines): exit 1, the next line ``pip install "poisson-prove[burla]"``, nothing on
  stdout, no launcher, no ledger, no run stored, before the ``[burla]`` table is read. The
  launcher's own check stays as the backstop and names the extra too.
- **r3** Every Modal plan names the price table's date and says the estimate covers compute, not
  model tokens, also with no estimate (no ``--est-seconds``, or a GPU the price table lacks).
- **r4** On Windows the Burla refusal comes before anything else a Burla sweep does (the spec file,
  the store, the flags, the extra, the ``[burla]`` table, the target), names burla and Windows in
  its ``error:`` line, and offers no install line; local and Modal are not refused.
- **r5** The Burla plan's relay line names the switch ``DISABLE_BURLA_RELAY=True``, says relay and
  says where the store stays (the corrected message of 2026-10-14, pinned by its facts).
- **r6** Real-backend tests carry ``slow`` and ``backend`` (section 10.6's names) and are skipped
  unless their own opt-in variable is set, so a plain ``pytest`` never makes a paid call.
- **r7** PF9.4's "offline Modal and Burla tests" are every module that drives a remote backend
  offline (``conftest.NETWORK_BLOCKED_MODULES``); one that must serve on a local socket is exempt,
  named with its reason (``conftest.NETWORK_EXEMPT_MODULES``).
- **r13** The price table's date is pinned as printed today, ``2026-09-03``: re-reading Modal's
  prices is a deliberate change that moves this test with it.

**Seams with PF3 and PF7, tested only on PF9's side:** PF3's ``prove.toml`` default spec and
``init`` (a Burla sweep with no spec argument on Windows meets the same first check, pinned here
with a spec named, a missing one included); PF7's measured floors (section 3.4, Q16) and its
``all`` extra (this file pins only that ``all`` carries the ``modal`` and ``burla`` requirements
their own extras carry, and that no other extra names ``burla``).
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import io
import json
import os
import pathlib
import re
import socket
import sys
import tomllib
import types
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

import conftest
from poisson_prove import cli, executor_burla
from poisson_prove.store import Store

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"
FIXTURES = REPO / "tests" / "bu_fixtures"
LAUNCH = FIXTURES / "launch.py"
SUBMIT = Path(executor_burla.__file__).resolve().with_name("_burla_submit.py")
MOCK = "poisson_prove.examples.mock_agent:rollout"
UNRESOLVABLE = "poisson_prove.examples.no_such_module_pf9:rollout"
BURLA_HINT = 'pip install "poisson-prove[burla]"'
OLD_BURLA_HINT = "pip install burla=="
PIN = "1.8.2"
NEVER_RUN = "0.0.0"
PRICE_DATE = "2026-09-03"
NEGATION = re.compile(r"\b(not|no|excludes?|excluding|without)\b")
BACKENDS = ("local", "modal", "burla")

BURLA_TABLE: dict[str, Any] = {
    "nodes": 1, "machine_type": "m7i.2xlarge", "slots_per_node": 2, "usd_per_node_hour": 0.403,
    "price_asof": "fixture price, 2026-09-27", "ledger": "ledgers/step.jsonl",
    "head_url": "http://localhost:5001", "stop_cost": 5.0, "max_cost": 5.0,
    "est_seconds_per_episode": 0.01,
}


# ---------- helpers: never assert ----------


def _toml(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml(v) for v in value) + "]"
    return json.dumps(value)


def write_spec(root: Path, *, burla: dict[str, Any] | None = None, modal_gpu: str | None = None,
               modal: bool = False, name: str = "sweep.toml") -> Path:
    """Two cells, two replicates, the keyless mock agent's design; ``--max-mde 1`` passes it."""
    text = ('target_id = "pf9@v0"\nt_unit = "steps"\nreplicates = 2\n\n'
            '[axes.cell]\ntype = "categorical"\nvalues = ["a", "b"]\n')
    if modal:
        text += '\n[modal.image]\npython = "3.11"\n'
        if modal_gpu is not None:
            text += f"gpu = {_toml(modal_gpu)}\n"
    if burla is not None:
        text += "\n[burla]\n" + "".join(f"{k} = {_toml(v)}\n" for k, v in burla.items())
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(text, encoding="utf-8")
    return path


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=io.StringIO())
    return code, out.getvalue(), err.getvalue()


def sweep_argv(root: Path, spec: Path, backend: str, *extra: str, target: str = MOCK) -> list[str]:
    # PF4 re-freeze (PF4.30, reading R17): no lone condition of this 2-replicate design can be
    # flagged, which any accepted change below 1 refuses; --max-mde 1 admits it as 0.99 did.
    return ["--store", str(root / "store"), "sweep", str(spec), "--target", target,
            "--backend", backend, "--max-mde", "1", *extra]


def runs_in(root: Path) -> list[str]:
    store_root = root / "store"
    return Store(store_root).runs() if store_root.is_dir() else []


def extras() -> dict[str, list[Requirement]]:
    """Every extra ``pyproject.toml`` declares, its requirements parsed as pip parses them."""
    doc = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return {name: [Requirement(text) for text in reqs]
            for name, reqs in doc["project"]["optional-dependencies"].items()}


def named(requirements: Sequence[Requirement], name: str) -> list[Requirement]:
    return [r for r in requirements if r.name.lower() == name]


def burla_specifier() -> SpecifierSet | None:
    found = named(extras().get("burla", []), "burla")
    return found[0].specifier if len(found) == 1 else None


class _Refuse(importlib.abc.MetaPathFinder):
    """``name`` cannot be found or imported in this process, whatever is installed."""

    def __init__(self, name: str) -> None:
        self.name = name

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        if fullname == self.name or fullname.startswith(self.name + "."):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def make_findable(monkeypatch: pytest.MonkeyPatch, root: Path, name: str, version: str) -> None:
    """A package called ``name`` at ``version`` first on ``sys.path``: findable, its version
    readable through ``importlib.metadata``, and nothing of it runs."""
    folder = root / f"stub-{name}"
    (folder / name).mkdir(parents=True, exist_ok=True)
    (folder / name / "__init__.py").write_text("", encoding="utf-8")
    info = folder / f"{name}-{version}.dist-info"
    info.mkdir(exist_ok=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(folder))
    monkeypatch.delitem(sys.modules, name, raising=False)
    importlib.invalidate_caches()


def make_missing(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setattr(sys, "meta_path", [_Refuse(name), *sys.meta_path])
    monkeypatch.delitem(sys.modules, name, raising=False)
    importlib.invalidate_caches()


class Launches:
    """Burla's launcher seam, pointed at the fake client (or at none: ``mode="absent"``), with the
    fake's state in ``state``. The fake reports ``version`` (by default one no build runs) and
    refuses every call it receives at once, so no worker pool is needed; ``called()`` lists the
    calls that reached it."""

    def __init__(self, state: Path, *, mode: str = "fake", version: str = NEVER_RUN) -> None:
        self.state = state
        self.mode = mode
        state.mkdir(parents=True, exist_ok=True)
        (state / "workers.json").write_text("[]", encoding="utf-8")
        script = {"version": version, "watch": [], "attempts": [], "default": {"refuse": "NoNodes"}}
        (state / "script.json").write_text(json.dumps(script), encoding="utf-8")

    def argv(self) -> list[str]:
        return [sys.executable, "-I", str(LAUNCH), str(self.state), self.mode, str(SUBMIT)]

    def started(self) -> list[str]:
        path = self.state / "launchers.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def called(self) -> list[dict[str, Any]]:
        path = self.state / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def point_launcher(monkeypatch: pytest.MonkeyPatch, launches: Launches) -> None:
    monkeypatch.setattr(executor_burla, "_launcher_argv", launches.argv)


def simulate_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """``os.name == "nt"`` as the spec simulates it (PF9.3). The filesystem is still this one, so
    the module that defines ``pathlib.Path`` (``pathlib`` up to 3.12, ``pathlib._local`` from 3.13)
    keeps reading the real name; nothing else is changed."""
    defining = sys.modules[pathlib.Path.__module__]
    proxy = types.ModuleType("os")
    proxy.__getattr__ = lambda attr: getattr(os, attr)  # type: ignore[method-assign]
    proxy.name = os.name
    monkeypatch.setattr(defining, "os", proxy)
    monkeypatch.setattr(os, "name", "nt")


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    simulate_windows(monkeypatch)
    yield


def refusal_lines(err: str, root: Path) -> tuple[str, list[str]]:
    """The ``error:`` line and the lines after it, with the test's own folder taken out of the
    first: pytest names that folder after the test, so it holds the very words a check looks for."""
    lines = err.splitlines()
    return (lines[0].replace(str(root), "<tmp>") if lines else ""), lines[1:]


def nearest_backend(text: str, word: str) -> str | None:
    """The backend name nearest the first ``word`` in ``text``, by distance in characters."""
    at = text.find(word)
    if at < 0:
        return None
    best: tuple[int, str] | None = None
    for name in BACKENDS:
        for m in re.finditer(rf"\b{name}\b", text):
            gap = abs(m.start() - at)
            if best is None or gap < best[0]:
                best = (gap, name)
    return best[1] if best else None


# ---------- PF9.1: the modal extra has a floor; the plan dates its prices and says what they cover


def test_pf9_1_the_modal_extra_has_a_floor_and_no_ceiling() -> None:
    """Section 3.3: ``modal>=<measured floor>``; section 3.4: no upper bound where none exists today.
    The floor's value is measured (Q16; reading r8), so it is not pinned here; PF9's real-backend
    test runs Modal at it. ``all`` carries the same requirement (section 3.3's ``all`` row)."""
    found = named(extras()["modal"], "modal")
    assert len(found) == 1, extras()["modal"]
    (req,) = found
    assert [spec.operator for spec in req.specifier] == [">="], str(req)
    (floor,) = [Version(spec.version) for spec in req.specifier]
    assert floor > Version("0"), str(req)
    assert [str(r) for r in named(extras().get("all", []), "modal")] == [str(req)]


@pytest.mark.parametrize(
    ("gpu", "extra"),
    [(None, ("--est-seconds", "2")), (None, ()), ("PF9-NOT-A-GPU", ("--est-seconds", "2"))],
    ids=["an-estimate", "no-estimate-asked", "a-gpu-the-table-lacks"],
)
def test_pf9_1_the_modal_plan_dates_its_prices_and_covers_compute_not_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gpu: str | None, extra: tuple[str, ...],
) -> None:
    """PF9.1, readings r3 and r13: whatever the estimate, the plan names the price table's date and
    says the estimate covers compute and not model tokens; ``--json``'s plan lines say the same."""
    make_findable(monkeypatch, tmp_path, "modal", "99.0")
    spec = write_spec(tmp_path, modal=True, modal_gpu=gpu)
    for as_json in (False, True):
        argv = sweep_argv(tmp_path, spec, "modal", "--dry-run", *extra, *(["--json"] if as_json else []))
        code, out, err = run_cli(argv)
        assert code == 0, (as_json, out, err)
        if as_json:
            payload = json.loads(out)
            assert payload["verdict"] == "plan", payload
            lines = [str(line) for line in payload["plan"]["lines"]]
        else:
            lines = out.splitlines()[1:]
        assert any(PRICE_DATE in line for line in lines), (as_json, lines)
        tokens = [line.lower() for line in lines if "token" in line.lower()]
        assert tokens, (as_json, lines)
        assert all("compute" in line for line in tokens), tokens
        assert all(NEGATION.search(line.split("token")[0].rsplit("compute", 1)[-1]) for line in tokens), tokens
    assert runs_in(tmp_path) == []


# ---------- PF9.2: the burla extra and its label


@pytest.mark.parametrize(("version", "runs"), [("1.8.1", False), (PIN, True), ("1.8.3", False), ("1.9.0", False)])
def test_pf9_2_the_burla_extra_admits_exactly_the_client_the_backend_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str, runs: bool,
) -> None:
    """Section 3.3 under Q31 and the 2026-10-14 pin, reading r1: ``[burla]`` declares one ``burla``
    requirement, ``all`` carries the same, no other extra names ``burla``, and it admits a version
    exactly when the backend runs that client. A client the backend refuses is refused before
    Burla is called, naming the client's version, the pin and the install line. (The pinned client
    running is every test of ``test_bu_burla_backend.py``.)"""
    spec_set = burla_specifier()
    assert spec_set is not None, extras().get("burla")
    assert spec_set.contains(version, prereleases=True) is runs, (str(spec_set), version)
    declared = extras()
    assert [str(r) for r in named(declared["all"], "burla")] == [str(r) for r in named(declared["burla"], "burla")]
    assert {name for name, reqs in declared.items() if named(reqs, "burla")} == {"burla", "all"}
    if runs:
        return
    make_findable(monkeypatch, tmp_path, "burla", version)
    launches = Launches(tmp_path / "fake-state", version=version)
    point_launcher(monkeypatch, launches)
    spec = write_spec(tmp_path, burla=BURLA_TABLE)
    code, out, err = run_cli(sweep_argv(tmp_path, spec, "burla", "--yes"))
    assert code != 0, (out, err)
    assert launches.called() == [], "Burla was called with a client the backend does not run"
    assert version in err and PIN in err and BURLA_HINT in err, err


def test_pf9_2_the_help_calls_the_burla_backend_experimental() -> None:
    """PF9.2: ``--backend``'s help line calls burla, and only burla, experimental (section 8.7)."""
    code, out, err = run_cli(["sweep", "--help"])
    assert code == 0, err
    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.lstrip().startswith("--backend"))
    entry = [lines[start]]
    for line in lines[start + 1:]:
        if line.lstrip().startswith("-") or not line.strip():
            break
        entry.append(line)
    prose = " ".join(" ".join(entry).split()).replace("{local,modal,burla}", " ").lower()
    assert prose.count("experimental") == 1, prose
    assert nearest_backend(prose, "experimental") == "burla", prose


@pytest.mark.parametrize("case", ["missing-here", "launcher-cannot-import"])
def test_pf9_2b_every_burla_install_line_names_the_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    """PF0's yes/no 5 (ruled 2026-10-14): Burla's install line is ``pip install "poisson-prove[burla]"``
    wherever Prove prints one, never ``pip install burla==``: when ``burla`` cannot be imported here,
    and from the launcher's backstop when it cannot import ``burla`` there. (A client the backend
    does not run is the r1 test's.)"""
    spec = write_spec(tmp_path, burla=BURLA_TABLE)
    if case == "missing-here":
        make_missing(monkeypatch, "burla")
        launches = Launches(tmp_path / "fake-state")
    else:
        make_findable(monkeypatch, tmp_path, "burla", PIN)
        launches = Launches(tmp_path / "fake-state", mode="absent")
    point_launcher(monkeypatch, launches)
    code, out, err = run_cli(sweep_argv(tmp_path, spec, "burla", "--yes"))
    assert code != 0, (case, out, err)
    assert BURLA_HINT in err, (case, err)
    assert OLD_BURLA_HINT not in out + err, (case, out, err)
    assert launches.called() == [], case


@pytest.mark.parametrize("table", [True, False], ids=["with-burla-table", "without-burla-table"])
def test_pf9_2c_a_missing_burla_is_refused_before_the_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, table: bool,
) -> None:
    """Reading r2 (sections 3.2 and PF1.2, as ``modal`` is today): with ``burla`` not importable, a
    Burla sweep exits 1 with one ``error:`` line naming burla and the install line as its one next
    line, prints nothing on stdout, starts no launcher, writes no ledger and stores no run, before
    the ``[burla]`` table is read. The control is the same command in the same kind of folder with
    ``burla`` importable: it does something else."""

    def attempt(root: Path, missing: bool) -> tuple[int, str, str, Launches]:
        spec = write_spec(root, burla=BURLA_TABLE if table else None)
        launches = Launches(root / "fake-state")
        with monkeypatch.context() as inner:
            point_launcher(inner, launches)
            if missing:
                make_missing(inner, "burla")
            else:
                make_findable(inner, root, "burla", PIN)
            code, out, err = run_cli(sweep_argv(root, spec, "burla", "--yes"))
        return code, out, err, launches

    code, out, err, launches = attempt(tmp_path / "missing", True)
    assert code == 1, (out, err)
    assert out == "", out
    first, rest = refusal_lines(err, tmp_path)
    assert first.startswith("error: ") and "burla" in first, err
    assert rest == [f"  next: {BURLA_HINT}"], err
    assert launches.started() == []
    assert not (tmp_path / "missing" / "ledgers").exists()
    assert runs_in(tmp_path / "missing") == []
    c_code, c_out, c_err, _ = attempt(tmp_path / "control", False)
    assert (c_code, c_out, c_err.splitlines()[1:]) != (code, out, rest), (c_code, c_out, c_err)
    if table:
        assert c_out.startswith("plan  "), (c_out, c_err)


def test_pf9_2d_the_burla_plan_names_the_relay_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading r5 (the pin fix's relay line, 2026-10-14; passes on main, a guard of that fix): the
    Burla plan has one line naming ``DISABLE_BURLA_RELAY=True`` that also says relay and store, in
    text and in ``--json``'s plan lines."""
    make_findable(monkeypatch, tmp_path, "burla", PIN)
    spec = write_spec(tmp_path, burla=BURLA_TABLE)
    code, out, err = run_cli(sweep_argv(tmp_path, spec, "burla", "--dry-run"))
    assert code == 0, err
    code_j, out_j, err_j = run_cli(sweep_argv(tmp_path, spec, "burla", "--dry-run", "--json"))
    assert code_j == 0, err_j
    for lines in (out.splitlines()[1:], [str(line) for line in json.loads(out_j)["plan"]["lines"]]):
        relay = [line for line in lines if "DISABLE_BURLA_RELAY=True" in line]
        assert len(relay) == 1, lines
        assert "relay" in relay[0].lower() and "store" in relay[0].lower(), relay
    assert runs_in(tmp_path) == [] and not (tmp_path / "ledgers").exists()


# ---------- PF9.3: Windows


@pytest.mark.parametrize(
    "case",
    ["burla-findable", "burla-missing", "no-burla-table", "dry-run", "unresolvable-target",
     "missing-spec-file", "stray-flag", "unknown-resume"],
)
def test_pf9_3_burla_on_windows_is_refused_before_any_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, windows: None, case: str,
) -> None:
    """PF9.3 under Q34, reading r4: with ``os.name == "nt"``, ``--backend burla`` exits 1 with one
    ``error:`` line naming burla and Windows, before the spec file, the flags, the store, the extra,
    the ``[burla]`` table or the target is looked at: nothing on stdout, no install line, no
    launcher, no ledger, no run stored."""
    if case == "burla-missing":
        make_missing(monkeypatch, "burla")
    else:
        make_findable(monkeypatch, tmp_path, "burla", PIN)
    launches = Launches(tmp_path / "fake-state")
    point_launcher(monkeypatch, launches)
    spec = write_spec(tmp_path, burla=None if case == "no-burla-table" else BURLA_TABLE)
    if case == "missing-spec-file":
        spec = tmp_path / "no-such-sweep.toml"
    extra = {"dry-run": ("--dry-run",), "stray-flag": ("--concurrency", "2", "--yes"),
             "unknown-resume": ("--resume", "20991231T000000Z-dead", "--yes")}.get(case, ("--yes",))
    target = UNRESOLVABLE if case == "unresolvable-target" else MOCK
    code, out, err = run_cli(sweep_argv(tmp_path, spec, "burla", *extra, target=target))
    assert code == 1, (case, out, err)
    assert out == "", (case, out)
    first, rest = refusal_lines(err, tmp_path)
    assert first.startswith("error: ") and "burla" in first.lower() and "windows" in first.lower(), (case, err)
    assert all(line.startswith("  next: ") for line in rest), (case, err)
    assert "pip install" not in err, (case, err)
    assert launches.started() == [], case
    assert not (tmp_path / "ledgers").exists(), case
    assert runs_in(tmp_path) == [], case


@pytest.mark.parametrize("backend", ["local", "modal", "burla-on-posix"])
def test_pf9_3_control_only_burla_on_windows_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str,
) -> None:
    """The controls for PF9.3: the same dry run plans on Windows for local and Modal, and for Burla
    when ``os.name`` is not ``nt``."""
    make_findable(monkeypatch, tmp_path, "modal", "99.0")
    make_findable(monkeypatch, tmp_path, "burla", PIN)
    name = "burla" if backend == "burla-on-posix" else backend
    spec = write_spec(tmp_path, modal=name == "modal", burla=BURLA_TABLE if name == "burla" else None)
    with monkeypatch.context() as inner:
        if backend != "burla-on-posix":
            simulate_windows(inner)
        code, out, err = run_cli(sweep_argv(tmp_path, spec, name, "--dry-run"))
    assert code == 0 and out.startswith("plan  "), (backend, out, err)
    assert "windows" not in (out + err).lower(), (backend, out, err)


# ---------- PF9.4: the offline backend tests run with sockets blocked


DRIVES_A_BACKEND = re.compile(
    r'"--backend", "(modal|burla)"|--backend (modal|burla)|backend=.(modal|burla).|run_modal\(|run_burla\(|run_with_mapper\('
)


def test_pf9_4_every_offline_backend_module_runs_with_sockets_blocked(blocked_network: list[str]) -> None:
    """PF9.4, reading r7: every test module that drives a remote backend (its source runs
    ``--backend modal`` or ``burla``, ``run_modal``, ``run_burla`` or ``run_with_mapper``) runs with
    network sockets blocked, unless it is exempt with its reason; this one is blocked. An attempt
    fails the test even when the code under test swallows the error. ``tests/live`` is not offline."""
    attempts = (
        lambda: socket.create_connection(("127.0.0.1", 9), timeout=1),
        lambda: socket.getaddrinfo("127.0.0.1", 443),
        lambda: socket.gethostbyname("localhost"),
    )
    for attempt in attempts:
        with pytest.raises(conftest.NetworkBlocked):
            attempt()
    for family, kind in ((socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_STREAM)):
        probe = socket.socket(family, kind)
        try:
            for call in (probe.connect, probe.connect_ex):
                with pytest.raises(conftest.NetworkBlocked):
                    call(("127.0.0.1", 9) if family == socket.AF_INET else ("::1", 9))
        finally:
            probe.close()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(conftest.NetworkBlocked):
            udp.sendto(b"x", ("127.0.0.1", 9))
    finally:
        udp.close()
    assert len(blocked_network) == 8, blocked_network
    blocked_network.clear()
    driving = sorted(p.stem for p in (REPO / "tests").glob("test_*.py")
                     if DRIVES_A_BACKEND.search(p.read_text(encoding="utf-8")))
    assert "test_bu_burla_backend" in driving and "test_m3_modal" in driving, driving
    uncovered = [m for m in driving if not conftest.network_blocked_for(m) and m not in conftest.NETWORK_EXEMPT_MODULES]
    assert uncovered == [], uncovered
    assert all(reason.strip() for reason in conftest.NETWORK_EXEMPT_MODULES.values())


# ---------- real backends: written, marked, never run on a pull request or in CI


@pytest.mark.slow
@pytest.mark.backend
@pytest.mark.skipif(os.environ.get("POISSON_PROVE_MODAL_FLOOR_LIVE") != "1",
                    reason="real Modal at the floor: set POISSON_PROVE_MODAL_FLOOR_LIVE=1 with a Modal account (a paid call)")
def test_pf9_backend_modal_runs_at_the_extras_floor(tmp_path: Path) -> None:
    """PF9.1 against the real Modal: the installed ``modal`` is the extra's floor
    (``pip install "modal==<floor>"`` first), and a two-cell sweep of the keyless mock agent runs on
    it to a complete run. Never reads a key: Modal's client finds its own credentials."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as dist_version

    (req,) = named(extras()["modal"], "modal")
    (floor,) = [spec.version for spec in req.specifier]
    try:
        installed = dist_version("modal")
    except PackageNotFoundError:
        pytest.fail(f'install the floor first: pip install "modal=={floor}"')
    assert Version(installed) == Version(floor), (installed, floor)
    spec = write_spec(tmp_path, modal=True)
    code, out, err = run_cli(sweep_argv(tmp_path, spec, "modal", "--yes", "--est-seconds", "1", "--max-cost", "1"))
    assert code == 0, (out, err)
    (run_id,) = runs_in(tmp_path)
    store = Store(tmp_path / "store")
    assert store.manifest(run_id).status == "complete"
    assert store.count(run_id) == 4


@pytest.mark.slow
@pytest.mark.backend
@pytest.mark.skipif(os.environ.get("POISSON_PROVE_BURLA_LIVE") != "1" or not os.environ.get("POISSON_PROVE_BURLA_TABLE"),
                    reason="real Burla: set POISSON_PROVE_BURLA_LIVE=1 and POISSON_PROVE_BURLA_TABLE to a TOML "
                           "file holding your cluster's [burla] table (a paid call)")
def test_pf9_backend_burla_runs_from_the_extra(tmp_path: Path) -> None:
    """PF9.2 against a real Burla cluster the user started: the installed client is one the extra
    admits, and a two-cell sweep of the keyless mock agent runs on it to a complete run, its plan
    naming the relay switch. The ``[burla]`` table (head, nodes, price, ledger, stop and cap) is
    the user's, read from the file the variable names; never a key."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as dist_version

    try:
        installed = dist_version("burla")
    except PackageNotFoundError:
        pytest.fail(f"install the extra first: {BURLA_HINT}")
    spec_set = burla_specifier()
    assert spec_set is not None and spec_set.contains(installed, prereleases=True), (installed, spec_set)
    table = tomllib.loads(Path(os.environ["POISSON_PROVE_BURLA_TABLE"]).read_text(encoding="utf-8"))["burla"]
    spec = write_spec(tmp_path, burla=table)
    code, out, err = run_cli(sweep_argv(tmp_path, spec, "burla", "--yes"))
    assert code == 0, (out, err)
    assert "DISABLE_BURLA_RELAY=True" in out, out
    (run_id,) = runs_in(tmp_path)
    store = Store(tmp_path / "store")
    assert store.manifest(run_id).status == "complete"
    assert store.count(run_id) == 4
