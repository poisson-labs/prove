"""M3 I19: live parity between ``run_modal`` and ``run_local``.

Opt-in only. Runs when ``PROOFLOAD_MODAL_LIVE=1`` and Modal credentials are present
(``MODAL_TOKEN_ID`` in the environment or ``~/.modal.toml``); skipped otherwise, never failed
for missing credentials or a missing ``modal`` package. A 2-cell x 3-replicate sweep of a
tiny CPU rollout, so container time stays well under a minute once the image is built.

The rollout is the ``proofload_live_rollout`` fixture package next to this file; pytest puts
this directory on ``sys.path`` (no ``__init__.py`` here), so the package is importable locally
and shippable through ``ImageSpec.local_packages``.
"""

import os
import time
from pathlib import Path

import pytest

from proofload.executor import plan, run_local
from proofload.sampler import SweepSpec
from proofload.store import Store

LIVE = os.environ.get("PROOFLOAD_MODAL_LIVE") == "1"
HAS_CREDENTIALS = bool(os.environ.get("MODAL_TOKEN_ID")) or (Path.home() / ".modal.toml").is_file()
SALT = "live-parity-salt"

pytestmark = [
    pytest.mark.skipif(not LIVE, reason="set PROOFLOAD_MODAL_LIVE=1 to run the live Modal test"),
    pytest.mark.skipif(not HAS_CREDENTIALS, reason="no Modal credentials (MODAL_TOKEN_ID or ~/.modal.toml)"),
]


def _outcome_set(store: Store, run_id: str) -> set[tuple[str, int, int, str, float]]:
    df = store.read(run_id)
    return set(
        zip(df["config_hash"], df["replicate_index"], df["seed"], df["outcome"], df["t"], strict=True)
    )


def test_i19_run_modal_matches_run_local_under_shared_salt(tmp_path: Path) -> None:
    pytest.importorskip("modal")
    from proofload.executor_modal import ImageSpec, ModalOptions, ModalTarget, run_modal
    from proofload_live_rollout import rollout

    spec = SweepSpec.build(
        [{"x": 0.1}, {"x": 0.2}], replicates=3, target_id="live@test", t_unit="steps"
    )
    total = spec.total_rollouts()
    assert total == 6

    local_store = Store(tmp_path / "local")
    local_plan = plan(spec, local_store, run_salt=SALT)
    local_summary = run_local(local_plan, rollout, local_store)
    assert local_summary.complete is True and local_summary.n_ok == total

    modal_store = Store(tmp_path / "modal")
    modal_plan = plan(spec, modal_store, run_salt=SALT, backend="modal")
    image = ImageSpec(
        python="3.11",
        pip=("numpy", "pandas", "scipy", "pyarrow"),
        local_packages=("proofload_live_rollout",),
    )
    target = ModalTarget(import_path="proofload_live_rollout:rollout", image=image)
    options = ModalOptions(
        concurrency=2, batch_size=3, episode_timeout=None, app_name="proofload-live-test"
    )
    t0 = time.perf_counter()
    modal_summary = run_modal(modal_plan, target, modal_store, options=options)
    elapsed = time.perf_counter() - t0
    print(f"run_modal wall time: {elapsed:.1f}s (summary.wall_time={modal_summary.wall_time:.1f}s)")

    assert modal_summary.complete is True
    assert modal_summary.n_ok == total and modal_summary.n_errored == 0
    assert modal_summary.n_infra_failed == 0
    modal_set = _outcome_set(modal_store, modal_plan.run_id)
    assert len(modal_set) == total
    assert modal_set == _outcome_set(local_store, local_plan.run_id)
    manifest = modal_store.manifest(modal_plan.run_id)
    assert manifest.backend == "modal"
    assert manifest.run_salt == SALT
    assert manifest.status == "complete"
