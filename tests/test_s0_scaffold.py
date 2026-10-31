import ast
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
# PF7: the import names of what the extras bring; none may load in a core module.
EXTRAS_BANNED_FROM_CORE = {"modal", "burla", "openai", "opentelemetry"}
NETWORK_CLIENT_MODULES = {"requests", "httpx", "urllib", "socket"}
LOOPBACK_SERVER_MODULE = "http.server"
LOOPBACK_SERVER_HOME = "viewer.py"


def test_import_and_version():
    import poisson_prove
    assert isinstance(poisson_prove.__version__, str) and poisson_prove.__version__


#: The modules a bare install imports: the package, its public modules but ``otel`` (which needs the
#: ``agent`` extra), the core and the command line.
CORE_MODULES = (
    "poisson_prove", "poisson_prove.compare", "poisson_prove.stats", "poisson_prove.store",
    "poisson_prove.trace", "poisson_prove.steps", "poisson_prove.chaos",
    "poisson_prove.examples.mock_agent", "poisson_prove.core", "poisson_prove.cli",
)


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_import_pulls_no_extras(module):
    """Each core module, imported alone in a fresh interpreter, loads no extra's package."""
    r = subprocess.run([sys.executable, "-I", "-c", f"import sys, {module}; print(*sorted(sys.modules))"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    loaded = {n.split(".")[0] for n in r.stdout.split()}
    assert module in r.stdout.split(), r.stdout[-500:]
    assert not loaded & EXTRAS_BANNED_FROM_CORE, (module, sorted(loaded & EXTRAS_BANNED_FROM_CORE))


def test_cli_version_via_entrypoint():
    import poisson_prove
    r = subprocess.run(["poisson-prove", "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and poisson_prove.__version__ in r.stdout


def test_cli_version_via_module():
    import poisson_prove
    r = subprocess.run([sys.executable, "-m", "poisson_prove", "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and poisson_prove.__version__ in r.stdout


def test_python_floor():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == ">=3.11"


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
    """Prove opens no outbound connection.

    Outbound client modules - urllib, requests, httpx, socket - are banned in every module
    under src/poisson_prove. A listener bound to loopback, on request, is not an outbound
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
