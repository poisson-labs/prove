"""What the tests of the reading surfaces share: the stores ``diff``, ``inspect`` and the dashboard are
read over, built once per test session by real sweeps in processes of their own.

The stores use a fixed salt, so what they hold is the same on every run. Nothing a test does may
change them: every read here writes nothing, and a test that saves copies a store first.

Reading is done in this process through ``pf12_support.cli`` (streams that are not terminals, so the
plain rendering), and compared with what ``--json`` says of the same store.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pf12_support import OLD, QS_A, QS_B, SRC, Result, cli, copy_fixture, doc, shared_world

__all__ = [
    "QS_A", "QS_B", "Result", "cli", "doc", "reading_world", "sweep_in", "words_of",
]

SALT = "0123456789abcdef"

TARGETS = '''\
import time

from opentelemetry import trace

from poisson_prove import Episode


def holds(cfg, seed):
    return Episode(outcome="violated" if (seed % 3 == 0) else "completed", t=1, horizon=10, meta={})


def moved(cfg, seed):
    hit = cfg["load"] >= 2 and cfg["mode"] == "a"
    return Episode(outcome="violated" if (hit or seed % 3 == 0) else "completed", t=1, horizon=10, meta={})


def plain_pair(cfg, seed):
    return Episode(outcome="violated" if seed % 2 == 0 else "completed", t=1, horizon=10, meta={})


def some_error(cfg, seed):
    if seed % 5 == 0:
        raise ValueError("one in five of these rollouts raises")
    return Episode(outcome="violated" if seed % 2 == 0 else "completed", t=1, horizon=10, meta={})


def both_ways(cfg, seed):
    # A low rate has room to rise and little to show a fall; a high rate the other way.
    share = {"a": 5, "b": 90, "c": 50}[cfg["cell"]]
    return Episode(outcome="violated" if seed % 100 < share else "completed", t=1, horizon=10, meta={})


def long_horizon(cfg, seed):
    return Episode(outcome="violated" if seed % 2 == 0 else "completed", t=7, horizon=20, meta={})


def short_horizon(cfg, seed):
    return Episode(outcome="violated" if seed % 2 == 0 else "completed", t=3, horizon=5, meta={})


def broken(cfg, seed):
    raise ValueError("this rollout always raises")


def _deeper(cfg):
    raise ValueError("this rollout always raises")


def two_places(cfg, seed):
    if cfg["cell"] == "b":
        raise ValueError("this rollout always raises")
    _deeper(cfg)


def names_its_seed(cfg, seed):
    raise ValueError(f"this rollout raises at seed {seed}")


def sleeps(cfg, seed):
    time.sleep(30)


def traced_then_raises(cfg, seed):
    tracer = trace.get_tracer("reading")
    with tracer.start_as_current_span("invoke_agent") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        raise ValueError("this rollout always raises")
'''

ORDER_SPEC = """\
target_id = "agent"
t_unit = "tool_calls"
replicates = 6

[axes.load]
type = "continuous"
values = [10, 2, 0.5, -1]

[axes.mode]
type = "categorical"
values = ["b", "a"]
"""

CELLS_SPEC = """\
target_id = "agent"
t_unit = "tool_calls"
replicates = {replicates}

[axes.cell]
type = "categorical"
values = [{values}]
{tail}"""


def cells_spec(values: str = '"a", "b", "c"', replicates: int = 3, tail: str = "") -> str:
    return CELLS_SPEC.format(values=values, replicates=replicates, tail=tail)


def _child_env(base: Path) -> dict[str, str]:
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "CI", "BROWSER")
    env = {key: value for key, value in os.environ.items() if key not in drop}
    home = base / "home"
    home.mkdir(exist_ok=True)
    env.update(PYTHONPATH=os.pathsep.join([str(SRC), str(base)]), HOME=str(home), NO_COLOR="1", PYTHONIOENCODING="utf-8")
    return env


def _prove(base: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "poisson_prove", "--plain", *argv], cwd=base, env=_child_env(base), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", timeout=600,
    )


def sweep_in(base: Path, spec: str, target: str, *more: str, code: int = 0) -> None:
    """One sweep of ``targets:<target>`` in ``base``, whose store is ``base/prove-runs``."""
    salt = () if "--pair-with" in more else ("--salt", SALT)
    done = _prove(base, "sweep", spec, "--target", f"reading_targets:{target}", "--yes", "--max-mde", "1", *salt, *more)
    assert done.returncode == code, (spec, target, done.stdout[-800:], done.stderr[-800:])


def _folder(root: Path, name: str, **specs: str) -> Path:
    base = root / name
    base.mkdir()
    (base / "reading_targets.py").write_text(TARGETS, encoding="utf-8")
    for spec, text in specs.items():
        (base / f"{spec}.toml").write_text(text, encoding="utf-8")
    return base


def _build(root: Path) -> dict[str, Any]:
    stores: dict[str, str] = {}

    # The example, with the kinds its spec declares: the verdict is in safer and worse.
    base = _folder(root, "kinds")
    done = _prove(base, "init", "--example")
    assert done.returncode == 0, done.stderr
    example = "poisson_prove.examples.mock_agent"
    for more in ((), ("--pair-with", "latest")):
        target = f"{example}:rollout_patched" if more else f"{example}:rollout"
        salt = () if more else ("--salt", SALT)
        done = _prove(base, "sweep", "prove.toml", "--target", target, "--yes", *salt, *more)
        assert done.returncode == 0, done.stderr[-800:]
    stores["kinds"] = str(base / "prove-runs")

    # The example as 0.0.1 wrote it: no kinds, so the verdict is in higher and lower.
    base = root / "old"
    base.mkdir()
    stores["old"] = str(copy_fixture(OLD / "store", base / "prove-runs"))

    # Two axes whose values neither the hash order nor the text order sorts.
    base = _folder(root, "order", spec=ORDER_SPEC)
    sweep_in(base, "spec.toml", "holds")
    sweep_in(base, "spec.toml", "moved", "--pair-with", "latest")
    stores["order"] = str(base / "prove-runs")

    # A condition only the baseline ran.
    base = _folder(root, "holes", abc=cells_spec(), ab=cells_spec('"a", "b"'))
    sweep_in(base, "abc.toml", "plain_pair")
    sweep_in(base, "ab.toml", "plain_pair")
    stores["holes"] = str(base / "prove-runs")

    # Some episodes of each run ended with no outcome.
    base = _folder(root, "no_outcome", spec=cells_spec(replicates=10))
    sweep_in(base, "spec.toml", "some_error")
    sweep_in(base, "spec.toml", "some_error", "--pair-with", "latest")
    stores["no_outcome"] = str(base / "prove-runs")

    # Runs with different horizons: the comparison cuts the longer run's episodes at the shorter's.
    base = _folder(root, "cut", spec=cells_spec(replicates=10))
    sweep_in(base, "spec.toml", "long_horizon")
    sweep_in(base, "spec.toml", "short_horizon", "--pair-with", "latest")
    stores["cut"] = str(base / "prove-runs")

    # A low rate and a high one, unchanged: one has no limit on its fall, the other on its rise.
    base = _folder(root, "both_ways", spec=cells_spec(replicates=30))
    sweep_in(base, "spec.toml", "both_ways")
    sweep_in(base, "spec.toml", "both_ways", "--pair-with", "latest")
    stores["both_ways"] = str(base / "prove-runs")

    # The low rate alone: one row with no limit on its fall.
    base = _folder(root, "one_limit", spec=cells_spec('"a", "c"', replicates=30))
    sweep_in(base, "spec.toml", "both_ways")
    sweep_in(base, "spec.toml", "both_ways", "--pair-with", "latest")
    stores["one_limit"] = str(base / "prove-runs")

    # Three replicates: too few for most conditions to have a limit in either direction.
    base = _folder(root, "small", spec=cells_spec())
    sweep_in(base, "spec.toml", "plain_pair")
    sweep_in(base, "spec.toml", "plain_pair", "--pair-with", "latest")
    stores["small"] = str(base / "prove-runs")

    # A good run and an all-errored one.
    base = _folder(root, "one_errored", spec=cells_spec())
    sweep_in(base, "spec.toml", "plain_pair")
    sweep_in(base, "spec.toml", "broken", code=3)
    stores["one_errored"] = str(base / "prove-runs")

    # For inspect: errors alike, errors from two places, errors each with its own text.
    for name, target, more in (
        ("same_error", "broken", ()),
        ("two_tracebacks", "two_places", ()),
        ("own_text", "names_its_seed", ()),
        ("timeouts", "sleeps", ("--episode-timeout", "0.2")),
    ):
        base = _folder(root, name, spec=cells_spec())
        sweep_in(base, "spec.toml", target, *more, code=3)
        stores[name] = str(base / "prove-runs")

    base = _folder(root, "many_errors", spec=cells_spec(replicates=400))
    sweep_in(base, "spec.toml", "broken", code=3)
    stores["many_errors"] = str(base / "prove-runs")

    base = _folder(root, "traced", spec=cells_spec(tail="\n[capture]\nmax_observation_bytes = 8192\n"))
    sweep_in(base, "spec.toml", "traced_then_raises", code=3)
    stores["traced"] = str(base / "prove-runs")

    return stores


@pytest.fixture(scope="session")
def reading_world(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Every store above by name, built once for the whole session."""
    _, stores = shared_world(tmp_path_factory, "reading", _build)
    return {name: Path(store) for name, store in stores.items()}


def words_of(config: dict[str, Any]) -> str:
    """A condition as its axes and values, each number as the look prints it."""
    parts = []
    for key, value in config.items():
        number = isinstance(value, (int, float)) and not isinstance(value, bool)
        parts.append(f"{key} {format(value, 'g') if number else value}")
    return " · ".join(parts)


def split_row(line: str) -> list[str]:
    """A plain table's line into its cells: a cell holds single spaces, and two or more part cells."""
    return re.split(r"\s{2,}", line.strip())
