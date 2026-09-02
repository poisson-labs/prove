from pathlib import Path

import pytest

from momus.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def go1_store() -> Store:
    """The committed Go1 golden fixture at tests/fixtures/go1 (built by S3 Session B)."""
    return Store(FIXTURES / "go1")
