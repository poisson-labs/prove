"""Two stored arms of one paired replay, generated: the suite's stand-in for a real study's arms.

Fifty items (``task_id`` ``item-0`` to ``item-49``, so their text order is not their numeric
order), four replicates each, the same request sent
twice: arm ``replay-a`` and arm ``replay-b``, 200 pairs, one salt, one seed per pair. Each episode
ends ``solved`` (``meta["reward"]`` the literal ``1.0``) or ``unsolved`` (``0.0``). The pairs fall
in the 2x2 ``TWO_BY_TWO``: 36 of them flip, 21 solved by ``a`` only and 15 by ``b`` only, and the
flips cluster by item (fourteen items carry one to four each, the rest none), so the
item-clustered interval is wider than one that ignores the item, and the design effect is above one.

As with ``lattice.py``, nothing is drawn and hoped for: the counts are written down, the
generator only places them on items and replicates by SHA-256 draws (``lattice.draw``), stores
the pairs in an order that is neither the items' text order nor their numeric one, and the module imports nothing from
``poisson_prove``. Tests compute what the analysis must report from ``pairs()`` with their own
reference implementations. ``root()`` builds the store once per machine and version of this
file, under a lock, and checks it on every later use.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from lattice import LEGACY_COLUMNS, _LEGACY_SCHEMA, canonical_config, config_hash, draw

ARM_A, ARM_B = "replay-a", "replay-b"
SALT = "replay:seed=700000+4*item+replicate"
SEED_BASE = 700_000
ITEMS = tuple(f"item-{i}" for i in range(50))
REPLICATES = 4
PAIRS = len(ITEMS) * REPLICATES
SOLVED, UNSOLVED = "solved", "unsolved"
#: ``(n11, n10, n01, n00)``: solved by both, by ``a`` only, by ``b`` only, by neither.
TWO_BY_TWO = (64, 21, 15, 100)
#: Fourteen items carry the 36 flips, four, three, two or one each; the other 36 carry none.
FLIPS_PER_ITEM = (4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 1, 1, 1, 1)
GENERATOR_SEED = 20260916
CREATED_A, CREATED_B = "2026-01-16T10:00:00.000000Z", "2026-01-16T10:30:00.000000Z"

assert sum(TWO_BY_TWO) == PAIRS and TWO_BY_TWO[1] + TWO_BY_TWO[2] == sum(FLIPS_PER_ITEM)
assert tuple(LEGACY_COLUMNS) == tuple(_LEGACY_SCHEMA.names)


def pairs() -> list[dict[str, Any]]:
    """Every pair, in the order the arms store them: its item, replicate, seed and each arm's
    outcome (1 solved, 0 not)."""
    n11, n10, n01, n00 = TWO_BY_TWO
    flips = sorted([(1, 0)] * n10 + [(0, 1)] * n01, key=_keyed("flip"))
    concordant = sorted([(1, 1)] * n11 + [(0, 0)] * n00, key=_keyed("concordant"))
    flipping = dict(zip(sorted(range(len(ITEMS)), key=lambda i: _draw("flipping", i)), FLIPS_PER_ITEM))
    out = []
    for i, item in enumerate(ITEMS):
        k = flipping.get(i, 0)
        kinds = [flips.pop() for _ in range(k)] + [concordant.pop() for _ in range(REPLICATES - k)]
        places = sorted(range(REPLICATES), key=lambda r: _draw("replicate", i, r))
        for replicate, index in enumerate(places):
            a, b = kinds[index]
            out.append({"item": item, "replicate": replicate, "seed": SEED_BASE + REPLICATES * i + replicate, "a": a, "b": b})
    assert not flips and not concordant
    # Stored in an order that is neither the items' text order nor their numeric order.
    return sorted(out, key=lambda pair: _draw("stored", pair["item"], pair["replicate"]))


def _draw(*key: object) -> int:
    return draw("replay", GENERATOR_SEED, *key)


def _keyed(name: str) -> Any:
    counter = iter(range(10**6))
    return lambda _value: _draw(name, next(counter))


def _compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def write(root: Path) -> dict[str, str]:
    """Write both arms under ``root`` and return each file's SHA-256 by relative path."""
    rows: dict[str, list[dict[str, Any]]] = {ARM_A: [], ARM_B: []}
    for pair in pairs():
        config = {"task_id": pair["item"]}
        for arm, solved in ((ARM_A, pair["a"]), (ARM_B, pair["b"])):
            rows[arm].append({
                "run_id": arm, "config_hash": config_hash(config), "config": canonical_config(config),
                "seed": pair["seed"], "replicate_index": pair["replicate"],
                "outcome": SOLVED if solved else UNSOLVED, "t": 1.0, "horizon": 1.0, "confidence": None,
                "meta": _compact({"reward": 1.0 if solved else 0.0}), "error": None, "wall_time": 0.0,
                "backend_meta": _compact({"generated": True}),
            })
    for arm, created in ((ARM_A, CREATED_A), (ARM_B, CREATED_B)):
        run_dir = root / arm
        (run_dir / "episodes").mkdir(parents=True)
        manifest = {
            "axis_types": {"task_id": "categorical"}, "backend": "import", "created_at": created,
            "environment": {"generator": "tests/replay_arms.py", "generator_seed": GENERATOR_SEED},
            "proofload_version": "0.0.1", "retain_traces_for": None, "run_id": arm, "run_salt": SALT,
            "schema_version": 1, "status": "complete", "t_unit": "episodes", "target_id": f"{arm}-target",
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pq.write_table(pa.Table.from_pylist(rows[arm], schema=_LEGACY_SCHEMA), run_dir / "episodes" / "part-00000.parquet")
    return _digests(root)


def _digests(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


_VERSION = hashlib.sha256(
    Path(__file__).read_bytes() + (Path(__file__).parent / "lattice.py").read_bytes() + pa.__version__.encode()
).hexdigest()[:12]
_ROOT: list[Path] = []


def root() -> Path:
    """The store holding both arms, built on first use and checked on every later one."""
    if _ROOT:
        return _ROOT[0]
    home = Path(tempfile.gettempdir()) / f"prove-replay-arms-{_VERSION}"
    home.mkdir(parents=True, exist_ok=True)
    with open(home / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        store, sums = home / "store", home / "SHA256SUMS.json"
        if not (store.is_dir() and sums.is_file() and json.loads(sums.read_text()) == _digests(store)):
            shutil.rmtree(store, ignore_errors=True)
            staging = Path(tempfile.mkdtemp(prefix=".store-", dir=home))
            digests = write(staging)
            os.rename(staging, store)
            sums.write_text(json.dumps(digests, indent=1, sort_keys=True), encoding="utf-8")
    _ROOT.append(store)
    return store


def unchanged() -> bool:
    """Whether a store this machine has built still holds exactly what was written (see ``lattice.unchanged``)."""
    home = Path(tempfile.gettempdir()) / f"prove-replay-arms-{_VERSION}"
    store, sums = home / "store", home / "SHA256SUMS.json"
    return not store.is_dir() or (sums.is_file() and json.loads(sums.read_text()) == _digests(store))
