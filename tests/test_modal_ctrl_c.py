"""Ctrl-C during a Modal sweep, when Modal's ``app.run()`` swallows it.

Modal's client from 1.0 catches a ``KeyboardInterrupt`` raised inside ``with app.run():``, stops
the app and returns without raising it again. A sweep stopped that way ends as any interrupted
sweep does: the batches already delivered are kept, the run is partial and resumable, its event
log ends with ``interrupted``, and the command exits 130. The ``modal`` here is a fake, offline:
its ``map`` delivers the first batch, then raises ``KeyboardInterrupt`` as a Ctrl-C would, and
its ``app.run()`` swallows it the way Modal's does.
"""

import contextlib
import importlib.machinery
import io
import json
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import cli
from poisson_prove.store import Store

MOCK = "poisson_prove.examples.mock_agent:rollout"
SPEC = """target_id = "ctrl-c@v0"
t_unit = "steps"
replicates = 4

[axes.cell]
type = "categorical"
values = ["a", "b"]

[modal]
concurrency = 1
batch_size = 2

[modal.image]
python = "3.11"
"""


class _Image:
    """Every image method returns the image, as Modal's builder does."""

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: self


class _Function:
    def __init__(self, fn: Any) -> None:
        self.fn = fn

    def map(self, items: Any, **kwargs: Any) -> Iterator[Any]:
        first, *_ = list(items)
        yield self.fn(first)
        raise KeyboardInterrupt


class _App:
    def __init__(self, name: str, *args: Any, **kwargs: Any) -> None:
        pass

    def function(self, **kwargs: Any) -> Any:
        return _Function

    @contextlib.contextmanager
    def run(self) -> Iterator["_App"]:
        try:
            yield self
        except KeyboardInterrupt:
            return  # Modal disconnects and returns here without raising it again


@pytest.fixture
def swallowing_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("modal")
    fake.__spec__ = importlib.machinery.ModuleSpec("modal", None)
    fake.Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image(), from_dockerfile=lambda *a, **k: _Image())  # type: ignore[attr-defined]
    fake.Secret = types.SimpleNamespace(from_name=lambda *a, **k: object())  # type: ignore[attr-defined]
    fake.App = _App  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "modal", fake)


def test_ctrl_c_that_modal_swallows_ends_the_sweep_interrupted(swallowing_modal: None, tmp_path: Path) -> None:
    spec = tmp_path / "sweep.toml"
    spec.write_text(SPEC, encoding="utf-8")
    store_root = tmp_path / "store"
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--store", str(store_root), "sweep", str(spec), "--target", MOCK, "--backend", "modal",
                     "--max-mde", "1", "--yes"], stdout=out, stderr=err, stdin=io.StringIO())
    assert code == 130, (code, out.getvalue(), err.getvalue())
    store = Store(store_root)
    (run_id,) = store.runs()
    assert store.manifest(run_id).status == "partial"
    assert store.count(run_id) == 2
    kinds = [json.loads(line)["kind"] for line in (store_root / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds[-1] == "interrupted", kinds
