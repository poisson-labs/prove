"""PF10 -- Prove's workers at numpy's floor (the must-fix before release, spec §14).

A Modal container and a Burla worker each run one batch at a time, and a run uses many of them at
once. At numpy's floor (1.24, OpenBLAS) a process whose environment names no thread count starts a
BLAS thread on every core, so a machine running several workers runs several times as many busy
threads as it has cores. The invariant: **a worker process runs its rollout's BLAS on one thread
when its environment sets no thread count.**

**Both backends, through their own boundary.** Burla runs through the fake client of
``tests/bu_fixtures/burla``, whose workers are long-lived interpreters started with an empty
environment, as ``test_bu_burla_backend.py`` drives it. Modal runs through ``run_modal`` with a fake
``modal`` whose ``map`` does what Modal does: the function Prove hands ``app.function`` is pickled
and run in a fresh interpreter, here one started with an empty environment. The target,
``bu_targets.blas``, does linear algebra and reports the thread pools ``threadpoolctl`` sees in its
own process.

**Where it bites.** Only a BLAS a thread cap can reach is checked: OpenBLAS (numpy and SciPy wheels
on Linux, and on macOS below numpy 2.0), MKL and BLIS. The macOS wheels of numpy 2 and SciPy 1.13
and later use Accelerate, which has no such pool; there the test skips and says so. The floors
lane (numpy 1.24) and any Linux machine run it.
"""

from __future__ import annotations

import pickle
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from poisson_prove.executor import plan
from poisson_prove.executor_modal import ImageSpec, ModalOptions, ModalTarget, run_modal
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store

from test_bu_burla_backend import TARGETS, assert_complete, burla_run, fake, pool, stored  # noqa: F401
from test_m3_modal_launch import FakeApp, FakeFunction, FakeModal

BLAS = "bu_targets.blas:rollout"
CAPPABLE = ("openblas", "mkl", "blis")

#: A container's interpreter: the function and its item arrive pickled on stdin, as Modal ships them.
CONTAINER = (
    "import pickle, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "fn, item = pickle.load(sys.stdin.buffer)\n"
    "sys.stdout.buffer.write(pickle.dumps(fn(item)))\n"
)


class ContainerFunction(FakeFunction):
    """``map`` runs the wrapped function on each item in a fresh interpreter with an empty environment."""

    def map(self, items: Any, **kwargs: Any) -> Iterator[Any]:
        self.records.map_calls.append(dict(kwargs))
        for item in items:
            done = subprocess.run([sys.executable, "-I", "-c", CONTAINER, str(TARGETS)], input=pickle.dumps((self.fn, item)),
                                  capture_output=True, env={}, timeout=300)
            assert done.returncode == 0, done.stderr.decode(errors="replace")
            yield pickle.loads(done.stdout)


class ContainerApp(FakeApp):
    def function(self, **kwargs: Any) -> Any:
        self.records.function_kwargs.append(dict(kwargs))
        return lambda fn: ContainerFunction(fn, self.records)


class ContainerModal(FakeModal):
    def App(self, name: str, *args: Any, **kwargs: Any) -> ContainerApp:
        return ContainerApp(self.records, name, *args, **kwargs)


def modal_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    monkeypatch.setitem(sys.modules, "modal", ContainerModal())
    monkeypatch.syspath_prepend(str(TARGETS))
    store = Store(tmp_path / "store")
    spec = SweepSpec.build([{"cell": "a"}, {"cell": "b"}], replicates=2, target_id="blas@test", t_unit="steps")
    p = plan(spec, store, backend="modal", run_salt="pf10-blas")
    summary = run_modal(p, ModalTarget(import_path=BLAS, image=ImageSpec()), store, options=ModalOptions(batch_size=2))
    assert summary.complete, summary
    rows = stored(store, p.run_id)
    assert len(rows) == len(p.pairs), rows
    return rows


@pytest.mark.parametrize("backend", ["modal", "burla"])
def test_pf10_a_worker_runs_its_rollouts_blas_on_one_thread(
    backend: str, request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if backend == "modal":
        rows = modal_rows(tmp_path, monkeypatch)
    else:
        p, store, _, outcome = burla_run(request.getfixturevalue("fake"), tmp_path, BLAS)
        assert_complete(outcome, store, p)
        rows = stored(store, p.run_id)
    assert len({row["meta"]["pid"] for row in rows}) >= 1
    for row in rows:
        assert row["meta"]["set"] == [], f"the worker's environment named a thread count: {row['meta']['set']}"
    pools = [p for row in rows for p in row["meta"]["pools"] if p[0] == "blas" and p[1] in CAPPABLE]
    if not pools:
        seen = sorted({tuple(p) for row in rows for p in row["meta"]["pools"]})
        pytest.skip(f"no BLAS a thread cap reaches in the worker (pools seen: {seen}); this numpy uses Accelerate")
    wide = [p for p in pools if p[2] != 1]
    assert wide == [], f"BLAS pools running more than one thread in a worker: {wide}"
