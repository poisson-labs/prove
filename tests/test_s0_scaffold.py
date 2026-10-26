import ast
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
EXTRAS_BANNED_FROM_CORE = {"modal", "litellm", "matplotlib"}
NETWORK_CLIENT_MODULES = {"requests", "httpx", "urllib", "socket"}
LOOPBACK_SERVER_MODULE = "http.server"
LOOPBACK_SERVER_HOME = "viewer.py"


def test_import_and_version():
    import poisson_prove
    assert isinstance(poisson_prove.__version__, str) and poisson_prove.__version__


def test_core_import_pulls_no_extras():
    for name in list(sys.modules):
        if name.split(".")[0] in EXTRAS_BANNED_FROM_CORE:
            del sys.modules[name]
    import importlib
    import poisson_prove
    importlib.reload(poisson_prove)
    loaded = {n.split(".")[0] for n in sys.modules}
    assert not loaded & EXTRAS_BANNED_FROM_CORE


def test_cli_version_via_entrypoint():
    import poisson_prove
    r = subprocess.run(["poisson-prove", "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and poisson_prove.__version__ in r.stdout


def test_cli_version_via_module():
    import poisson_prove
    r = subprocess.run([sys.executable, "-m", "poisson_prove", "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and poisson_prove.__version__ in r.stdout


def test_pyproject_extras_exact():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = set(data["project"]["optional-dependencies"])
    # PF9 (Q31): the [burla] extra joins the set.
    assert extras == {"modal", "agent", "viz", "all", "dev", "burla"}


def test_pyproject_core_deps_are_math_only():
    """C13, closed by A22. The parser was ``d.split("[")[0].split(">")[0].split("=")[0]`` plus a
    ``.strip().lower()``, which strips neither ``<`` nor ``~=`` nor ``!=``: ``pandas>=2,<3``
    survived it only because ``>`` happens to come first, and the ``pandas<3`` half alone would
    not have. ``Requirement(d).name`` is the PEP 508 read, with ``packaging`` declared in
    ``[dev]`` rather than leaned on through pytest. **Green before and after** -- the assertion's
    value does not change under either parser for either spelling, so C13 has no build half. The
    negative that makes it non-vacuous is V13 in ``tests/test_a22_pandas3.py``, over a synthetic
    list the old parser fails."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    core = {Requirement(d).name.lower() for d in data["project"]["dependencies"]}
    # PF6 (Q20, Q60): Rich for the pretty rendering and Textual for the terminal app join the core.
    assert core == {"numpy", "pandas", "scipy", "pyarrow", "rich", "textual"}


def test_python_floor():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == ">=3.11"


def test_scope_md_exists_and_disclaims_telemetry():
    text = (ROOT / "SCOPE.md").read_text()
    assert "never phones home" in text


def test_license_is_mit():
    assert "MIT License" in (ROOT / "LICENSE").read_text()


def imported_modules(py: Path) -> set[str]:
    """Every module an ``import`` or ``from ... import`` names, as a full dotted path.

    ``from http import server`` has ``node.module == "http"``; the dotted name ``http.server``
    exists only once the module is joined with each alias, so the join is what makes the
    allowance below apply to the module wherever it is spelled.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(py.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def network_violations(py: Path) -> list[str]:
    """Imports that break the commitment: any client-module root anywhere, and the loopback
    server module in any file but its one permitted home."""
    names = imported_modules(py)
    server = sorted(
        n for n in names
        if n == LOOPBACK_SERVER_MODULE or n.startswith(LOOPBACK_SERVER_MODULE + ".")
    )
    bad = sorted(n for n in names if n.split(".")[0] in NETWORK_CLIENT_MODULES)
    if py.name != LOOPBACK_SERVER_HOME:
        bad.extend(server)
    return bad


def test_no_network_imports_in_core():
    """Proofload opens no outbound connection.

    Outbound client modules - urllib, requests, httpx, socket - are banned in every module
    under src/proofload. A listener bound to loopback, on request, is not an outbound
    connection: http.server is permitted in viewer.py and in no other module.

    Checked by an ast walk over full dotted import paths, not by substring: ``import
    socketserver`` is not ``import socket``, and ``from http import server`` is ``http.server``.
    """
    for py in (ROOT / "src" / "poisson_prove").rglob("*.py"):
        assert network_violations(py) == [], py


def test_socketserver_is_not_the_socket_client(tmp_path):
    scratch = tmp_path / "scratch.py"
    scratch.write_text("import socketserver\n")
    assert network_violations(scratch) == []


def test_from_http_import_server_trips_outside_viewer(tmp_path):
    scratch = tmp_path / "scratch.py"
    scratch.write_text("from http import server\n")
    assert network_violations(scratch) == [LOOPBACK_SERVER_MODULE]


def test_ci_workflow_exists():
    wf = ROOT / ".github" / "workflows" / "ci.yml"
    assert wf.exists()
    text = wf.read_text()
    assert "pytest" in text and "mypy" in text and "ruff" in text
