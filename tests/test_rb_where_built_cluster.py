"""C5 of 0.3.0, Remote backends: a cloud sweep's interrupts in the terminal app, beyond the
frozen tests.

Added by ruling (2026-11-11) from the build's own checks, with ``test_rb_where_built.py``; every
test here starts the fake coordinator, so the file runs with the cluster's other lifecycle
tests. Written by the builder, after the build; no mutation pass stands behind them.

- Ctrl-C while the nodes are still starting stops the ones that started, at once, closes the
  ledger's line ``cancelled`` and leaves with 130, with no run stored.
- SIGTERM and SIGHUP while the app runs a cloud sweep are Ctrl-C, and the app gives the signals
  back when the sweep ends.
- A second Ctrl-C while the cluster stops says so and does not leave; a third leaves at once.
- The sweep screen shows the cluster's lines while it starts and stops.
"""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import Session, says
from rb_cloud_support import CloudWorld, Pool, cloud_table, world
from test_rb_cloud_life import count, ended_clean, timeline
from test_rb_where_app import gone, in_app, leave


@pytest.fixture(autouse=True)
def _app_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME", "NO_COLOR", "CI", "TEXTUAL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fresh_pool() -> Any:
    own = Pool(2)
    yield own
    own.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_pool: Pool) -> Iterator[CloudWorld]:
    monkeypatch.setenv("COLUMNS", "250")
    with world(tmp_path, monkeypatch, fresh_pool) as made:
        made.store = made.root / "prove-runs"
        yield made


def _cloud_spec(w: CloudWorld, **over: Any) -> None:
    w.write_spec(table=cloud_table(max_cost=20.0, **over), cells=("a", "b"), replicates=130,
                 target="bu_targets.cloud:slow")


async def _start(s: Session) -> None:
    await s.wait_title("home")
    await s.press("s")
    await s.wait(lambda g: g.title() == "sweep" and says(g.text(), "[y/N]"), 120, "the plan")
    await s.press("y")


def test_ctrl_c_in_the_app_during_the_boot_stops_the_booting_nodes_at_once(w: CloudWorld) -> None:
    _cloud_spec(w)
    w.script_cluster(boot_s=60)

    async def scenario(s: Session) -> float:
        await _start(s)
        await s.wait(lambda g: says(g.text(), "of 1 ready"), 120, "the starting line")
        pressed = time.monotonic()
        await s.press("ctrl+c")
        await gone(s, 45)
        return time.monotonic() - pressed

    rc, took = in_app(w, scenario)
    assert rc == 130 and took < 45, (rc, took)
    assert count(w, "cluster stop") == 1 and ended_clean(w) == [], timeline(w)
    ledger = w.ledger()
    assert [e["event"] for e in ledger] == ["open", "close"] and ledger[-1]["ended"] == "cancelled", ledger
    assert w.runs() == [], "no rollout ran, so no run was stored"


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP])
def test_sigterm_and_sighup_while_the_app_runs_a_cloud_sweep_are_ctrl_c(w: CloudWorld, sig: int) -> None:
    _cloud_spec(w, batch_size=4)

    async def scenario(s: Session) -> None:
        await _start(s)
        await s.wait(lambda g: says(g.text(), "of 260"), 180, "the first batches")
        os.kill(os.getpid(), sig)
        await gone(s, 90)

    rc, _ = in_app(w, scenario)
    assert rc == 130, rc
    assert count(w, "cluster stop") == 1 and ended_clean(w) == [], timeline(w)
    assert w.ledger()[-1]["ended"] == "cancelled", w.ledger()
    assert signal.getsignal(sig) in (signal.SIG_DFL, signal.default_int_handler), "the handler was left on"


def test_a_second_ctrl_c_during_the_stop_says_so_and_a_third_leaves(w: CloudWorld) -> None:
    _cloud_spec(w, batch_size=4)
    w.script_cluster(stop_s=30)

    async def scenario(s: Session) -> tuple[str, float, Any]:
        await _start(s)
        await s.wait(lambda g: says(g.text(), "of 260"), 180, "the first batches")
        await s.press("ctrl+c")
        await s.wait(lambda g: says(g.text(), "stopping the cluster"), 60, "the stop to begin")
        await s.press("ctrl+c")
        noted = await s.wait(lambda g: says(g.text(), "press ctrl-c again to leave it"), 30, "the note")
        pressed = time.monotonic()
        await s.press("ctrl+c")
        await gone(s, 10)
        return noted.text(), time.monotonic() - pressed, s.app.after

    rc, (noted, took, after) = in_app(w, scenario)
    assert rc == 130 and took < 10, (rc, took)
    assert says(noted, "the nodes will stop themselves within 3 min"), noted
    assert after[0] == "stopped" and after[2] == ["poisson-prove where"], after
    assert "left while the cluster was stopping" in after[1], after
    # The stop the app left goes on beside it; wait it out so the fake is not left running.
    until = time.monotonic() + 90
    while (w.record() or {}).get("state") != "stopped" and time.monotonic() < until:
        time.sleep(0.5)


def test_the_app_shows_the_clusters_lines_while_it_starts_and_stops(w: CloudWorld) -> None:
    _cloud_spec(w, batch_size=64)
    w.script_cluster(boot_s=4, stop_s=4)

    async def scenario(s: Session) -> list[str]:
        seen = []
        await _start(s)
        seen.append((await s.wait(lambda g: says(g.text(), "starting 1 × m7i.2xlarge in us-east-2"), 120, "starting")).text())
        seen.append((await s.wait(lambda g: says(g.text(), "stopping the cluster"), 240, "stopping")).text())
        await s.wait(lambda g: any(row.strip().startswith("done ") for row in g.rows), 240, "the end")
        await leave(s)
        return seen

    rc, seen = in_app(w, scenario)
    assert rc == 0 and len(seen) == 2
