"""M3 I19: live parity between ``run_modal`` and ``run_local``.

Opt-in only. Runs when ``PROOFLOAD_MODAL_LIVE=1`` and Modal credentials are present
(``MODAL_TOKEN_ID`` in the environment or ``~/.modal.toml``); skipped otherwise, never failed
for missing credentials or a missing ``modal`` package. A 2-cell x 3-replicate sweep of a
tiny CPU rollout, so container time stays well under a minute once the image is built.

The rollout is the ``proofload_live_rollout`` fixture package next to this file; pytest puts
this directory on ``sys.path`` (no ``__init__.py`` here), so the package is importable locally
and shippable through ``ImageSpec.local_packages``.

L15 (the S19 modal launch amendment) lives here too, behind a third gate:
``PROOFLOAD_MODAL_LIVE_SECRET=1``, set by whoever created the Modal secret
``proofload-live-test`` with ``PROOFLOAD_LIVE_SECRET=present``. No session creates that
secret. The rollout is ``rollout_secret`` in the same fixture package.
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
LIVE_SECRET = os.environ.get("PROOFLOAD_MODAL_LIVE_SECRET") == "1"
SECRET_NAME = "proofload-live-test"
SECRET_SALT = "live-secret-salt"

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


# ---------- L15: live mount (opt-in, third gate) ----------


def _l15_gate() -> str | None:
    """The first unmet gate, in order, so the skip reason names what to set next."""
    if not LIVE:
        return "set PROOFLOAD_MODAL_LIVE=1 to run the live Modal test"
    if not HAS_CREDENTIALS:
        return "no Modal credentials (MODAL_TOKEN_ID or ~/.modal.toml)"
    if not LIVE_SECRET:
        return (
            f"set PROOFLOAD_MODAL_LIVE_SECRET=1 once the Modal secret {SECRET_NAME} exists "
            "(created by hand with PROOFLOAD_LIVE_SECRET=present)"
        )
    return None


L15_SKIP = _l15_gate()


@pytest.mark.skipif(L15_SKIP is not None, reason=L15_SKIP or "")
def test_l15_named_secret_is_mounted_on_the_function(tmp_path: Path) -> None:
    pytest.importorskip("modal")
    from proofload.executor_modal import ImageSpec, ModalOptions, ModalTarget, run_modal

    spec = SweepSpec.build([{"x": 0.1}], replicates=2, target_id="live@test", t_unit="steps")
    assert spec.total_rollouts() == 2

    store = Store(tmp_path / "modal")
    p = plan(spec, store, run_salt=SECRET_SALT, backend="modal")
    image = ImageSpec(
        python="3.11",
        pip=("numpy", "pandas", "scipy", "pyarrow"),
        local_packages=("proofload_live_rollout",),
    )
    target = ModalTarget(import_path="proofload_live_rollout:rollout_secret", image=image)
    options = ModalOptions(
        concurrency=2,
        batch_size=2,
        episode_timeout=None,
        app_name="proofload-live-test",
        secrets=(SECRET_NAME,),
    )
    t0 = time.perf_counter()
    summary = run_modal(p, target, store, options=options)
    print(f"run_modal wall time: {time.perf_counter() - t0:.1f}s")

    assert summary.complete is True
    df = store.read(p.run_id)
    assert len(df) == 2
    assert df["outcome"].tolist() == ["present", "present"]
    assert store.manifest(p.run_id).environment["secrets"] == [SECRET_NAME]
