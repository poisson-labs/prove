from pathlib import Path

import pytest

from proofload.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures"


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

    from proofload._burla_submit import _PREFIX, _reap

    probe = subprocess.run(
        [sys.executable, "-I", "-S", "-c", "import tempfile; print(tempfile.gettempdir())"],
        env={}, capture_output=True, text=True, timeout=60,
    )
    tmp = probe.stdout.strip()
    if probe.returncode == 0 and tmp and any(
        entry.name.startswith(_PREFIX) for entry in Path(tmp).iterdir()
    ):
        _reap(tmp, None)
