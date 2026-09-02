import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRAS_BANNED_FROM_CORE = {"modal", "litellm", "matplotlib"}
NETWORK_MODULES = {"requests", "httpx", "urllib", "socket"}


def test_import_and_version():
    import momus
    assert isinstance(momus.__version__, str) and momus.__version__


def test_core_import_pulls_no_extras():
    for name in list(sys.modules):
        if name.split(".")[0] in EXTRAS_BANNED_FROM_CORE:
            del sys.modules[name]
    import importlib
    import momus
    importlib.reload(momus)
    loaded = {n.split(".")[0] for n in sys.modules}
    assert not loaded & EXTRAS_BANNED_FROM_CORE


def test_cli_version_via_entrypoint():
    import momus
    r = subprocess.run(["momus", "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and momus.__version__ in r.stdout


def test_cli_version_via_module():
    import momus
    r = subprocess.run([sys.executable, "-m", "momus", "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and momus.__version__ in r.stdout


def test_pyproject_extras_exact():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = set(data["project"]["optional-dependencies"])
    assert extras == {"modal", "agent", "viz", "all", "dev"}


def test_pyproject_core_deps_are_math_only():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    core = {d.split("[")[0].split(">")[0].split("=")[0].strip().lower()
            for d in data["project"]["dependencies"]}
    assert core == {"numpy", "pandas", "scipy", "pyarrow"}


def test_python_floor():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == ">=3.11"


def test_scope_md_exists_and_disclaims_telemetry():
    text = (ROOT / "SCOPE.md").read_text()
    assert "never phones home" in text


def test_license_is_mit():
    assert "MIT License" in (ROOT / "LICENSE").read_text()


def test_no_network_imports_in_core():
    for py in (ROOT / "src" / "momus").rglob("*.py"):
        src = py.read_text()
        for mod in NETWORK_MODULES:
            assert f"import {mod}" not in src and f"from {mod}" not in src, (py, mod)


def test_ci_workflow_exists():
    wf = ROOT / ".github" / "workflows" / "ci.yml"
    assert wf.exists()
    text = wf.read_text()
    assert "pytest" in text and "mypy" in text and "ruff" in text
