import functools
from pathlib import Path

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


@pytest.fixture(scope="session")
def go1_store() -> Store:
    """The committed Go1 golden fixture at tests/fixtures/go1 (built by S3 Session B)."""
    return Store(FIXTURES / "go1")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove the bundle folders the Burla tests' fake workers unpacked and could not remove.

    A worker process holds its folder for its life and removes it at exit or when another bundle
    replaces it (``proofload._burla_submit``), but the fake pool ends its workers with SIGKILL, so
    the last pool's folders outlive them. Their temporary directory is what an interpreter with an
    empty environment gets, which is not this process's. Only a folder whose owner is gone is
    removed: a live worker of any other session still holds its lock.
    """
    import subprocess
    import sys

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
