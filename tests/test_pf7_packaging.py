"""PF7 -- packaging: the metadata, the extras and their floors, and what the wheel and the sdist
hold (PF7.4 to PF7.6; Q14, Q15, Q16, Q31, Q40, Q45 and Q49; the Modal floor measured by the
backends module).

**What is pinned is what ships.** ``pyproject.toml`` as the build reads it, and the wheel and the
sdist built from this checkout once per test run (hatchling in a child process, over a copy of the
files a commit of this checkout would hold, as the hygiene tests build them), read back member by
member. The sets are rules over the tree, not lists: the wheel holds every file of the package
folder and nothing else, so a module or a data file a later change adds is in it by being in the
package.

**Readings this file freezes** (the build follows them):

- **k1** The PyPI short description is this sentence exactly: "Did your change to the agent
  really change how often it fails? Replays the same cases before and after, and says per
  condition, with stated error bounds and detection limits." It is the one description, so it is
  pinned whole.
- **k2** The "MIT" classifier is left out: with an SPDX ``license = "MIT"`` the packaging
  standard (PEP 639) forbids a ``License ::`` classifier beside it, and hatchling refuses the
  pair. No classifier claims Windows or "OS Independent", nor a Python outside 3.11 to 3.14.
- **k3** ``Documentation`` and ``Changelog`` point at a file or folder of the repository on
  ``main`` that exists in this tree; ``Source`` is the repository and ``Issues`` its issues page.
- **k4** Every requirement has a lower bound: the core, every extra, ``dev`` included (the floors
  run resolves ``[dev]`` at its lowest too), and the build backend. An upper bound only on
  ``openai`` (``openai<3``), and an exact pin only for ``burla==1.8.2``.
- **k5** ``[dev]`` carries what the contributors' lanes need that this file and the docs check
  read: ``pytest-xdist`` (Q40), ``hypothesis`` (the property tests), ``hatchling`` (the archives built
  here), ``markdown-it-py`` (the docs check reads pages with it) and ``pyyaml`` (it parses YAML
  blocks). Other modules' test tools are theirs to pin.
- **k6** PF7.5 is one slow test: on Python 3.11 it installs every requirement at exactly its
  stated floor (a constraints file of ``name==floor`` over the core and every extra; uv resolves
  what they bring), checks each is installed at its floor, then runs the code suite in that
  environment. ``--resolution lowest-direct`` is how the build finds the floors; it
  is not the check, because it takes what the floors bring at their newest and then backtracks a
  direct requirement above its floor to fit them (Modal 1.6.1 for a floor of 0.73.76 that installs
  when asked). It needs the package index, so it is the main lane's, never a pull request's.
- **k7** The wheel holds exactly the files of ``src/poisson_prove/`` (byte code left out) and the
  ``dist-info`` with ``METADATA``, ``WHEEL``, ``RECORD``, ``entry_points.txt`` and the two licence
  files. The sdist holds exactly ``PKG-INFO``, ``pyproject.toml``, ``.gitignore``, ``README.md``,
  ``CHANGELOG.md``, ``CONTRIBUTING.md``, ``LICENSE``, ``NOTICE``, and the tree's files under
  ``src/``, ``tests/``, ``docs/`` and ``examples/``, each folder matched whole: which examples are
  left is the hygiene module's (Q35), so the sdist follows the tree.
- **k8** The PyPI page is the README: the wheel's long description is ``README.md`` byte for byte,
  as Markdown.

**Seams, tested on the other side:** the core dependency list (``test_s0_scaffold``,
``test_a22_pandas3``; the terminal app adds ``rich`` and ``textual``); the pandas floor, which
``test_a22_pandas3::test_v15`` holds to admit 2.3.3 and 3.0.5, so the measured floor is at most
2.3.3; the Modal floor and the Burla
pin themselves (``test_pf9_backends``, which this file reads the same way); the files removed
before release (the hygiene tests); the version, set by the release.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF7.4 the release metadata, Q45's description | ``test_pf7_4_pyproject_carries_the_release_metadata`` (one case per field) |
| PF7.4 the extras (Q14, Q15, Q31, Q40) | ``test_pf7_4_the_extras_are_section_3_3s`` (one case per extra) |
| PF7.4 a floor on every dependency (Q16) | ``test_pf7_4_every_requirement_has_a_floor_and_no_ceiling_but_section_3_3s`` (one case per group) |
| PF7.5 the code suite passes with every dependency at its floor | ``test_pf7_5_the_code_suite_passes_with_every_requirement_at_its_floor`` (slow) |
| PF7.6 the wheel and the sdist hold exactly their sets; the example spec ships | ``test_pf7_6_each_archive_holds_exactly_its_set`` (wheel, sdist) |
| PF7.6 the PyPI page is the README | ``test_pf7_6_the_pypi_page_is_the_readme`` |
"""

from __future__ import annotations

import email
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

import pf7_docs_check as check

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/poisson-labs/prove"
DESCRIPTION = (
    "Did your change to the agent really change how often it fails? Replays the same cases before "
    "and after, and says per condition, with stated error bounds and detection limits."
)
PEOPLE = [{"name": "Poisson Labs", "email": "work@poissonlabs.ai"}]
PYTHONS = ("3.11", "3.12", "3.13", "3.14")
EXTRAS = {"modal", "agent", "burla", "all", "dev"}
MODAL_FLOOR = "modal>=0.73.76"
BURLA_PIN = "burla==1.8.2"
DEV_NEEDS = ("pytest-xdist", "hypothesis", "hatchling", "markdown-it-py", "pyyaml")
SDIST_FILES = {"PKG-INFO", "pyproject.toml", ".gitignore", "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "NOTICE"}
SDIST_FOLDERS = ("src", "tests", "docs", "examples")
DIST_INFO = {"METADATA", "WHEEL", "RECORD", "entry_points.txt", "licenses/LICENSE", "licenses/NOTICE"}
CODE_SUITE = "not math and not calibration and not slow and not backend"


def pyproject() -> dict:  # type: ignore[type-arg]
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def name_of(req: Requirement) -> str:
    return re.sub(r"[-_.]+", "-", req.name).lower()


def requirements(group: str) -> list[Requirement]:
    data = pyproject()
    if group == "core":
        texts = data["project"]["dependencies"]
    elif group == "build":
        texts = data["build-system"]["requires"]
    else:
        texts = data["project"]["optional-dependencies"].get(group, [])
    return [Requirement(text) for text in texts]


def tree_files() -> list[str]:
    """The paths a commit of this checkout would hold, tracked and untracked, ignored ones left out."""
    done = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                          capture_output=True, timeout=60)
    assert done.returncode == 0, done.stderr.decode()
    return sorted(p for p in done.stdout.decode().split("\0") if p and (ROOT / p).is_file() and not (ROOT / p).is_symlink())


# ---------- PF7.4 the metadata ----------


def _url_in_tree(url: str) -> bool:
    found = re.fullmatch(rf"{re.escape(REPO_URL)}/(?:blob|tree)/main/(.+?)/?", url)
    return bool(found) and (ROOT / found.group(1)).exists()


METADATA_CASES = {
    "name": lambda p: p["name"] == "poisson-prove",
    "description": lambda p: p.get("description") == DESCRIPTION,
    "readme": lambda p: p.get("readme") in ("README.md", {"file": "README.md", "content-type": "text/markdown"}),
    "license": lambda p: p.get("license") == "MIT" and sorted(p.get("license-files", [])) == ["LICENSE", "NOTICE"],
    "authors": lambda p: p.get("authors") == PEOPLE,
    "maintainers": lambda p: p.get("maintainers") == PEOPLE,
    "urls": lambda p: (set(p.get("urls", {})) == {"Homepage", "Source", "Documentation", "Changelog", "Issues"}
                       and p["urls"]["Homepage"] == "https://poissonlabs.ai/tools/prove"
                       and p["urls"]["Source"] == REPO_URL
                       and p["urls"]["Issues"] == f"{REPO_URL}/issues"
                       and _url_in_tree(p["urls"]["Documentation"])
                       and _url_in_tree(p["urls"]["Changelog"]) and p["urls"]["Changelog"].endswith("CHANGELOG.md")),
    "classifiers": lambda p: _classifiers_hold(p.get("classifiers", [])),
    "keywords": lambda p: bool(p.get("keywords")) and all(isinstance(k, str) and k.strip() == k and k for k in p["keywords"]),
    "script": lambda p: p.get("scripts") == {"poisson-prove": "poisson_prove.cli:main"},
}


def _classifiers_hold(found: list[str]) -> bool:
    need = {f"Programming Language :: Python :: {v}" for v in PYTHONS} | {
        "Operating System :: MacOS", "Operating System :: POSIX :: Linux", "Development Status :: 3 - Alpha"}
    if not need <= set(found):
        return False
    for item in found:
        version = re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", item)
        if version and version.group(1) not in PYTHONS:
            return False
        if item.startswith(("License ::", "Operating System :: Microsoft")) or item == "Operating System :: OS Independent":
            return False
    return True


@pytest.mark.parametrize("field", sorted(METADATA_CASES))
def test_pf7_4_pyproject_carries_the_release_metadata(field: str) -> None:
    project = pyproject()["project"]
    shown = {k: project.get(k) for k in (field, "license-files", "urls", "scripts") if k in project}
    assert METADATA_CASES[field](project), shown


# ---------- PF7.4 the extras ----------


def _same(reqs: list[Requirement], texts: list[str]) -> bool:
    return sorted((name_of(r), str(r.specifier), tuple(sorted(r.extras))) for r in reqs) == sorted(
        (name_of(Requirement(t)), str(Requirement(t).specifier), tuple(sorted(Requirement(t).extras))) for t in texts)


def _agent_holds(reqs: list[Requirement]) -> bool:
    by = {name_of(r): r for r in reqs}
    return (set(by) == {"openai", "opentelemetry-sdk"} and by["openai"].specifier == SpecifierSet(">=2.20,<3")
            and _floor_only(by["opentelemetry-sdk"]))


def _floor_only(req: Requirement) -> bool:
    return bool(req.specifier) and all(s.operator == ">=" for s in req.specifier)


def _all_holds(reqs: list[Requirement]) -> bool:
    union = [str(r) for group in ("modal", "agent", "burla") for r in requirements(group)]
    return _same(reqs, union)


EXTRA_CASES = {
    "the set": lambda: set(pyproject()["project"]["optional-dependencies"]) == EXTRAS,
    "modal": lambda: _same(requirements("modal"), [MODAL_FLOOR]),
    "burla": lambda: _same(requirements("burla"), [BURLA_PIN]),
    "agent": lambda: _agent_holds(requirements("agent")),
    "all": lambda: _all_holds(requirements("all")),
    "dev": lambda: set(DEV_NEEDS) <= {name_of(r) for r in requirements("dev")},
}


@pytest.mark.parametrize("case", list(EXTRA_CASES))
def test_pf7_4_the_extras_are_section_3_3s(case: str) -> None:
    assert EXTRA_CASES[case](), pyproject()["project"]["optional-dependencies"]


# ---------- PF7.4 the floors ----------


GROUPS = ["core", "build", *sorted(EXTRAS - {"all"}), "all"]


@pytest.mark.parametrize("group", GROUPS)
def test_pf7_4_every_requirement_has_a_floor_and_no_ceiling_but_section_3_3s(group: str) -> None:
    problems = []
    for req in requirements(group):
        name = name_of(req)
        operators = {s.operator for s in req.specifier}
        if name == "burla":
            if str(req.specifier) != "==1.8.2":
                problems.append(f"{req}: burla is pinned exactly to the client the backend runs")
            continue
        if ">=" not in operators:
            problems.append(f"{req}: no floor")
        allowed = {">="} | ({"<"} if name == "openai" else set())
        if operators - allowed:
            problems.append(f"{req}: a bound section 3.3 does not have")
        if name == "openai" and req.specifier != SpecifierSet(">=2.20,<3"):
            problems.append(f"{req}: openai keeps its own floor and ceiling")
    assert problems == [], problems


# ---------- PF7.5 the floors run ----------


@pytest.mark.slow
def test_pf7_5_the_code_suite_passes_with_every_requirement_at_its_floor(tmp_path: Path) -> None:
    """With every requirement installed at exactly its stated floor on Python 3.11 (a constraints
    file of ``name==floor``; uv resolves what they bring), the install succeeds and the code suite
    passes in that environment (k6)."""
    uv = shutil.which("uv")
    assert uv is not None, "the floors run needs uv: https://docs.astral.sh/uv/"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env.update(UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never")
    venv = tmp_path / "floors"
    python311 = sys.executable if sys.version_info[:2] == (3, 11) else "3.11"
    made = subprocess.run([uv, "venv", "--quiet", "--python", python311, str(venv)], env=env, capture_output=True, text=True, timeout=300)
    assert made.returncode == 0, "no Python 3.11 on this machine for the floors run: " + made.stderr
    python = venv / "bin" / "python"
    floors = {}
    for group in ["core", *sorted(EXTRAS)]:
        for req in requirements(group):
            versions = [s.version for s in req.specifier if s.operator in (">=", "==")]
            assert versions, f"{req}: no floor to install at"
            floors[name_of(req)] = versions[0]
    constraints = tmp_path / "floors.txt"
    constraints.write_text("".join(f"{name}=={version}\n" for name, version in sorted(floors.items())), encoding="utf-8")
    put = subprocess.run([uv, "pip", "install", "--quiet", "--python", str(python), "-c", str(constraints),
                          "-e", f"{ROOT}[all,dev]"], env=env, capture_output=True, text=True, timeout=1800)
    assert put.returncode == 0, put.stderr[-4000:]
    listed = subprocess.run([uv, "pip", "freeze", "--python", str(python)], env=env, capture_output=True, text=True, timeout=300)
    installed = {}
    for line in listed.stdout.splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            installed[re.sub(r"[-_.]+", "-", name).lower()] = version.strip()
    off = [f"{name}: {installed.get(name)} installed, the floor is {version}" for name, version in floors.items()
           if installed.get(name) is None or Version(installed[name]) != Version(version)]
    assert off == [], off
    run_env = dict(env, PATH=f"{venv / 'bin'}:{env.get('PATH', '')}")
    run_env.pop("PYTHONDONTWRITEBYTECODE", None)
    suite = subprocess.run([str(python), "-m", "pytest", "-q", "-x", "-n", "auto", "-p", "no:cacheprovider", "-m", CODE_SUITE, "tests"],
                           cwd=ROOT, env=run_env, capture_output=True, text=True, timeout=3600)
    assert suite.returncode == 0, suite.stdout[-6000:] + suite.stderr[-2000:]


# ---------- PF7.6 the archives ----------


@dataclass(frozen=True)
class Archive:
    kind: str
    files: dict[str, bytes]  #: path inside the archive (the sdist's top folder stripped) -> bytes
    tree: tuple[str, ...]  #: the files the archives were built from, as listed when they were


def build_archives(folder: Path) -> None:
    source = folder / "source"
    files = tree_files()
    (folder / "tree.json").write_text(json.dumps(files), encoding="utf-8")
    for rel in files:
        (source / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, source / rel)
    script = ("import sys\nfrom hatchling.build import build_sdist, build_wheel\n"
              "print(build_wheel(sys.argv[1]))\nprint(build_sdist(sys.argv[1]))\n")
    done = subprocess.run([sys.executable, "-c", script, str(folder / "dist")], cwd=source, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr


@pytest.fixture(scope="module")
def archives(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Archive]:
    base = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        base = base.parent
    folder = check.once(base, "archives", build_archives)
    (wheel,) = (folder / "dist").glob("*.whl")
    (sdist,) = (folder / "dist").glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as z:
        wheel_files = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    with tarfile.open(sdist) as t:
        sdist_files = {}
        for m in t.getmembers():
            if m.isfile():
                extracted = t.extractfile(m)
                assert extracted is not None
                sdist_files[m.name.split("/", 1)[1]] = extracted.read()
    tree = tuple(json.loads((folder / "tree.json").read_text(encoding="utf-8")))
    return {"wheel": Archive("wheel", wheel_files, tree), "sdist": Archive("sdist", sdist_files, tree)}


def expected_wheel(names: set[str], tree: tuple[str, ...]) -> set[str]:
    (info,) = {n.split("/", 1)[0] for n in names if n.split("/", 1)[0].endswith(".dist-info")} or {"(no dist-info)"}
    package = {"poisson_prove/" + rel[len("src/poisson_prove/"):] for rel in tree
               if rel.startswith("src/poisson_prove/") and "__pycache__" not in rel and not rel.endswith(".pyc")}
    return package | {f"{info}/{n}" for n in DIST_INFO}


def expected_sdist(tree: tuple[str, ...]) -> set[str]:
    return SDIST_FILES | {rel for rel in tree if rel.split("/", 1)[0] in SDIST_FOLDERS and "/" in rel}


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_pf7_6_each_archive_holds_exactly_its_set(kind: str, archives: dict[str, Archive]) -> None:
    names = set(archives[kind].files)
    want = expected_wheel(names, archives[kind].tree) if kind == "wheel" else expected_sdist(archives[kind].tree)
    assert {"missing": sorted(want - names)[:40], "extra": sorted(names - want)[:40]} == {"missing": [], "extra": []}
    spec = "poisson_prove/examples/quickstart.toml" if kind == "wheel" else "src/poisson_prove/examples/quickstart.toml"
    assert archives[kind].files[spec] == (ROOT / "src/poisson_prove/examples/quickstart.toml").read_bytes()


def test_pf7_6_the_pypi_page_is_the_readme(archives: dict[str, Archive]) -> None:
    (metadata,) = [n for n in archives["wheel"].files if n.endswith(".dist-info/METADATA")]
    headers, _, body = archives["wheel"].files[metadata].decode("utf-8").partition("\n\n")
    message = email.message_from_string(headers + "\n")
    assert message["Description-Content-Type"] == "text/markdown", message["Description-Content-Type"]
    assert message["Summary"] == DESCRIPTION, message["Summary"]
    assert body.strip("\n") == (ROOT / "README.md").read_text(encoding="utf-8").strip("\n")
