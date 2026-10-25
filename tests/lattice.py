"""The lattice: a small pair of runs the suite generates itself and reads in place of a real study.

Two runs of one design, ``lattice-a`` (before) and ``lattice-b`` (after), over a grid of two
continuous knobs, ``gain`` (twelve values, first in the manifest's axis order) and ``load`` (six
values), 32 replicates in every condition, 2,304 episodes a run. Every episode ends in one of two outcomes:
``tripped`` at a time on a 0.02 s step before the 5.0 s horizon, or ``held`` at the horizon. The
two runs share one salt and one seed per ``(condition, replicate)``, so they are paired by
construction, and ``tripped`` is the more frequent outcome in each run and in the two together.

Nothing here is drawn from a distribution and hoped for: each condition's count of ``tripped`` in
each run, and how the two runs' episodes pair up, is written down in ``DESIGN``, and the generator
only places those counts on replicates and gives each ``tripped`` episode a time, both from SHA-256
draws on its seed (``draw``), so the runs depend on no library's random stream. Tests
read the design as the independent record of what the runs hold (``design_cells``) and compute
what a comparison must report from it with their own references, never from Prove.

What the design holds, and why (each is a property some test needs, named where it is used):

- ``load`` 50 and 100: every episode trips in both runs (ceiling cells, saturated, no room for a
  rise). At 100 the after run trips at 0.6 of the before run's time, so a log-rank test sees a
  rise there that a test on the share cannot; at 50 the times are the same, so nothing can see a change.
- ``load`` 40: ceiling cells too, except one condition (``gain`` 0.6) where one episode the
  before run tripped held in the after run: the group's only informative condition, one
  discordant pair.
- ``load`` 10 to 30: where the after run trips less, strongly at small ``gain`` and less so as it
  grows. ``gain`` 1.1 is the one column where nothing is lowered: its ``load`` 10 condition never
  trips in either run (as ``gain`` 1.2's does not), its ``load`` 30 condition moves two episodes
  each way (discordant pairs, no change in the share), and its ``load`` 20 condition trips two
  more times in the after run. ``gain`` 0.9 at ``load`` 30 rises by the same two, from another
  baseline, so the two largest changes tie and only the tiebreak after the change orders them.
  ``gain`` 1.0 at ``load`` 30 sits just past the edge of the BH family over every condition and
  inside the edge of one over the conditions with an event; ``gain`` 1.2 at ``load`` 20 is
  flagged by the flat family and by no family of its own group. At ``load`` 30, ``gain`` 0.5 and
  0.7 also trip twice, and 1.2 four times, on replicates the before run held: the share is the same
  as without them, but the paired test sees more discordant pairs both ways, so McNemar's flags
  differ from Fisher's and its per-group families differ from one family over their union. At
  ``load`` 20, ``gain`` 1.2 also trips twice on replicates the before run held, so under McNemar
  no condition of that column is flagged while the column, as a group, still rejects.
- No condition trips significantly more in the after run, except through time at ``load`` 100.

The runs are written the way the private 0.0.1 builds wrote them before the trace columns
existed (the thirteen columns of ``LEGACY_COLUMNS`` and a manifest with ``proofload_version``),
so every reader of them goes through the fallback for old parts, as a store a user kept would.
The generator imports nothing from ``poisson_prove``: the rows, the condition keys and the
canonical JSON are written here, so a defect in the package cannot change the runs it is tested
on.

``root()`` builds the store once per machine and version of this file into the system's
temporary folder, under a lock, and checks every file and folder against the digests it wrote
when a process first asks for it. The suite's controller checks both generated stores before any
test runs (``conftest.pytest_configure``), and rebuilds one that fails then (left by a crash, or a
session before it); from then on a store that fails was written by a test of this session, so
every process refuses it instead of rebuilding it, and the suite checks it once more when the
session ends (``unchanged``). A session in which a test wrote into it fails, rather than passing
on a store the next process or session silently rebuilds.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

#: The two runs: (run id, target id, created at). Same day, so each name ends in ``a``.
RUN_A, RUN_B = "lattice-a", "lattice-b"
TARGET_A, TARGET_B = "lattice-before", "lattice-after"
CREATED_A, CREATED_B = "2026-01-15T09:00:00.000000Z", "2026-01-15T09:00:00.250000Z"
#: What ``runs`` names them: the target id, the day it was written, and a letter.
NAME_A, NAME_B = f"{TARGET_A} 2026-01-15 a", f"{TARGET_B} 2026-01-15 a"
#: ``created_at`` of the after run minus that of the before run, in seconds.
CREATED_GAP_S = 0.25

EVENT, OTHER = "tripped", "held"
OUTCOMES = (EVENT, OTHER)
X, Y = "gain", "load"
GAIN: tuple[float, ...] = tuple(round(0.1 * k, 1) for k in range(1, 13))
#: Six values, the last of them 100.0, so the labels' text order is not their numeric order.
LOAD: tuple[float, ...] = (10.0, 20.0, 30.0, 40.0, 50.0, 100.0)
N = 32
HORIZON = 5.0
T_UNIT = "seconds"
STEP = 0.02
SALT = "lattice:seed=500000+32*condition+replicate"
SEED_BASE = 500_000
#: The generator's own seed: where each count lands among the replicates, and every time.
GENERATOR_SEED = 20260115
#: At ``load`` 100 the after run trips at this share of the before run's time.
SOONER = 0.6

CELLS = len(GAIN) * len(LOAD)
ROWS = CELLS * N

#: The thirteen columns, in order, of a part written before the trace columns were appended.
LEGACY_COLUMNS: tuple[str, ...] = (
    "run_id", "config_hash", "config", "seed", "replicate_index", "outcome", "t", "horizon",
    "confidence", "meta", "error", "wall_time", "backend_meta",
)
_LEGACY_SCHEMA = pa.schema(
    [
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("config_hash", pa.string(), nullable=False),
        pa.field("config", pa.string(), nullable=False),
        pa.field("seed", pa.int64(), nullable=False),
        pa.field("replicate_index", pa.int64(), nullable=False),
        pa.field("outcome", pa.string(), nullable=True),
        pa.field("t", pa.float64(), nullable=True),
        pa.field("horizon", pa.float64(), nullable=True),
        pa.field("confidence", pa.float64(), nullable=True),
        pa.field("meta", pa.string(), nullable=False),
        pa.field("error", pa.string(), nullable=True),
        pa.field("wall_time", pa.float64(), nullable=False),
        pa.field("backend_meta", pa.string(), nullable=False),
    ]
)
#: The manifest's twelve keys as the 0.0.1 builds wrote them (no ``declared``, no ``name``).
LEGACY_MANIFEST_KEYS = frozenset({
    "axis_types", "backend", "created_at", "environment", "proofload_version",
    "retain_traces_for", "run_id", "run_salt", "schema_version", "status", "t_unit", "target_id",
})
#: What each run's ``environment`` records: where the rows came from, nothing about a machine.
#: ``run`` is the one string the two runs' environments do not share.
ENVIRONMENT = {"generator": "tests/lattice.py", "generator_seed": GENERATOR_SEED, "design": "DESIGN"}
ENVIRONMENT_RUN = {RUN_A: "the before run of the lattice", RUN_B: "the after run of the lattice"}


@dataclass(frozen=True)
class Cell:
    """One condition: how many of its ``N`` episodes trip in each run, and how they pair.

    ``after_only`` is the number of replicates that trip in the after run and hold in the before
    run; the rest of the after run's trips are replicates that trip in both. ``timing`` is
    ``"same"`` (a replicate that trips in both runs trips at the same time), ``"sooner"`` (the
    after run trips at ``SOONER`` of the before run's time) or ``"own"`` (each run draws its own time).
    """
    gain: float
    load: float
    tripped_a: int
    tripped_b: int
    after_only: int = 0
    timing: str = "own"

    @property
    def both(self) -> int:
        return self.tripped_b - self.after_only

    @property
    def before_only(self) -> int:
        return self.tripped_a - self.both

    @property
    def config(self) -> dict[str, float]:
        return {X: self.gain, Y: self.load}


#: ``(tripped in before, tripped in after)`` at ``load`` 10, 20 and 30, one row per ``gain``.
_ACTIVE: Mapping[float, tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = {
    0.1: ((32, 14), (24, 10), (22, 6)),
    0.2: ((26, 8), (23, 9), (20, 10)),
    0.3: ((24, 6), (22, 8), (19, 9)),
    0.4: ((22, 5), (21, 7), (19, 10)),
    0.5: ((20, 4), (20, 7), (18, 9)),
    0.6: ((18, 3), (19, 6), (18, 10)),
    0.7: ((17, 3), (18, 6), (17, 9)),
    0.8: ((16, 2), (17, 6), (17, 10)),
    0.9: ((14, 2), (16, 5), (16, 18)),
    1.0: ((12, 1), (15, 5), (12, 3)),
    1.1: ((0, 0), (4, 6), (16, 16)),
    1.2: ((0, 0), (11, 2), (14, 8)),
}
#: Conditions whose after run also trips on replicates the before run held.
_AFTER_ONLY: Mapping[tuple[float, float], int] = {
    (0.5, 30.0): 2, (0.7, 30.0): 2, (0.9, 30.0): 2, (1.1, 20.0): 2, (1.1, 30.0): 2, (1.2, 20.0): 2, (1.2, 30.0): 4,
}


def _design() -> tuple[Cell, ...]:
    cells: list[Cell] = []
    for gain in GAIN:
        for load in LOAD:
            if load <= 30.0:
                a, b = _ACTIVE[gain][int(load // 10) - 1]
                cells.append(Cell(gain, load, a, b, _AFTER_ONLY.get((gain, load), 0)))
            elif load == 40.0:
                cells.append(Cell(gain, load, N, N - 1 if gain == 0.6 else N, timing="same"))
            elif load == 50.0:
                cells.append(Cell(gain, load, N, N, timing="same"))
            else:
                cells.append(Cell(gain, load, N, N, timing="sooner"))
    for cell in cells:
        assert 0 <= cell.after_only <= cell.tripped_b <= N and 0 <= cell.both <= cell.tripped_a
        assert cell.before_only + cell.both + cell.after_only <= N
    return tuple(cells)


DESIGN: tuple[Cell, ...] = _design()


# ---------- the canonical forms, written here and not imported ----------


def canonical_config(config: Mapping[str, Any]) -> str:
    """A condition as the store keys it: JSON, keys sorted, no spaces, every number a float,
    strings and booleans as they are."""
    def canonical(value: Any) -> Any:
        if isinstance(value, bool) or isinstance(value, str) or value is None:
            return value
        if isinstance(value, (int, float)):
            return float(value)
        raise TypeError(f"the lattice writes no {type(value).__name__} into a condition")

    return json.dumps({k: canonical(v) for k, v in config.items()}, sort_keys=True, separators=(",", ":"))


def config_hash(config: Mapping[str, Any]) -> str:
    """The condition's key: the first sixteen hex digits of the SHA-256 of its canonical JSON."""
    return hashlib.sha256(canonical_config(config).encode("utf-8")).hexdigest()[:16]


def _compact(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


# ---------- the rows ----------


def draw(*key: object) -> int:
    """A 64-bit integer from the SHA-256 of the generator's seed and ``key``: the generator's only
    source of arrangement, so the runs it writes depend on no library's random stream."""
    text = ":".join(str(part) for part in (GENERATOR_SEED, *key))
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _time(index: int, run: str, replicate: int) -> float:
    """A trip time on the 0.02 s step, from 0.50 s to 4.40 s."""
    return round((25 + draw("t", index, run, replicate) % 196) * STEP, 2)


def episodes() -> dict[str, list[dict[str, Any]]]:
    """Every episode of both runs, in condition order and then replicate order."""
    out: dict[str, list[dict[str, Any]]] = {RUN_A: [], RUN_B: []}
    for index_of_cell, cell in enumerate(DESIGN):
        order = sorted(range(N), key=lambda r: draw("order", index_of_cell, r))
        both = order[: cell.both]
        before_only = order[cell.both : cell.both + cell.before_only]
        after_only = order[cell.both + cell.before_only : cell.both + cell.before_only + cell.after_only]
        t_a = {r: _time(index_of_cell, "a", r) for r in both + before_only}
        t_b: dict[int, float] = {}
        for r in both + after_only:
            if r in t_a and cell.timing == "same":
                t_b[r] = t_a[r]
            elif r in t_a and cell.timing == "sooner":
                t_b[r] = round(round(t_a[r] * SOONER / STEP) * STEP, 2)
            else:
                t_b[r] = _time(index_of_cell, "b", r)
        config = cell.config
        key = config_hash(config)
        for run_id, times in ((RUN_A, t_a), (RUN_B, t_b)):
            for replicate in range(N):
                tripped = replicate in times
                out[run_id].append({
                    "run_id": run_id,
                    "config_hash": key,
                    "config": canonical_config(config),
                    "seed": SEED_BASE + index_of_cell * N + replicate,
                    "replicate_index": replicate,
                    "outcome": EVENT if tripped else OTHER,
                    "t": float(times[replicate]) if tripped else HORIZON,
                    "horizon": HORIZON,
                    "confidence": None,
                    "meta": _compact({"replicate": replicate}),
                    "error": None,
                    "wall_time": 0.0,
                    "backend_meta": _compact({"generated": True}),
                })
    return out


def manifest(run_id: str) -> dict[str, Any]:
    """The manifest of ``run_id`` as a 0.0.1 build wrote it."""
    target, created = {RUN_A: (TARGET_A, CREATED_A), RUN_B: (TARGET_B, CREATED_B)}[run_id]
    doc = {
        "axis_types": {X: "continuous", Y: "continuous"},
        "backend": "import",
        "created_at": created,
        "environment": {**ENVIRONMENT, "run": ENVIRONMENT_RUN[run_id]},
        "proofload_version": "0.0.1",
        "retain_traces_for": None,
        "run_id": run_id,
        "run_salt": SALT,
        "schema_version": 1,
        "status": "complete",
        "t_unit": T_UNIT,
        "target_id": target,
    }
    assert set(doc) == LEGACY_MANIFEST_KEYS
    return doc


def write(root: Path) -> dict[str, str]:
    """Write the two runs under ``root`` and return each file's SHA-256 by relative path."""
    rows = episodes()
    for run_id in (RUN_A, RUN_B):
        run_dir = root / run_id
        (run_dir / "episodes").mkdir(parents=True)
        (run_dir / "manifest.json").write_text(json.dumps(manifest(run_id), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        table = pa.Table.from_pylist(rows[run_id], schema=_LEGACY_SCHEMA)
        pq.write_table(table, run_dir / "episodes" / "part-00000.parquet")
    return _digests(root)


def _digests(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ---------- one store per machine and version of the generator ----------

#: Set by the suite's controller once it has checked both generated stores at the start of a
#: session (``conftest.pytest_configure``), and inherited by its workers.
CHECKED = "PROVE_GENERATED_STORES_CHECKED"


def _home(name: str, version: str) -> Path:
    return Path(tempfile.gettempdir()) / f"prove-{name}-{version}"


def _matches(home: Path) -> bool:
    """Whether ``home/store`` holds exactly the files ``home/SHA256SUMS.json`` lists, with those
    digests, and no folder but theirs."""
    store = home / "store"
    try:
        sums = json.loads((home / "SHA256SUMS.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not store.is_dir() or not isinstance(sums, dict) or sums != _digests(store):
        return False
    folders = {str(p.relative_to(store)) for p in store.rglob("*") if p.is_dir()}
    return folders == {str(parent) for rel in sums for parent in Path(rel).parents if parent != Path(".")}


def cached_store(name: str, version: str, write_to: Any) -> Path:
    """The store ``write_to(folder)`` writes, built once per machine and ``version`` under a lock.

    A store that fails its digests is rebuilt only while the session has not checked it yet
    (``CHECKED``); after that it was written by a test, and is refused, its bytes left in place.
    """
    home = _home(name, version)
    home.mkdir(parents=True, exist_ok=True)
    with open(home / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        store = home / "store"
        if not _matches(home):
            if os.environ.get(CHECKED):
                raise RuntimeError(
                    f"the generated store {store} changed during this test session: a test wrote into it"
                )
            shutil.rmtree(store, ignore_errors=True)
            staging = Path(tempfile.mkdtemp(prefix=".store-", dir=home))
            digests = write_to(staging)
            os.rename(staging, store)
            pending = home / ".SHA256SUMS.json.part"
            pending.write_text(json.dumps(digests, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(pending, home / "SHA256SUMS.json")
    return store


def store_unchanged(name: str, version: str) -> bool:
    """Whether the store is as written, without building one; a store the session checked and
    that is gone has changed."""
    home = _home(name, version)
    if not (home / "store").exists():
        return not os.environ.get(CHECKED)
    return _matches(home)


_VERSION = hashlib.sha256(Path(__file__).read_bytes() + pa.__version__.encode()).hexdigest()[:12]
_ROOT: list[Path] = []


def root() -> Path:
    """The store holding the two runs, built on first use and checked when a process first asks."""
    if not _ROOT:
        _ROOT.append(cached_store("lattice", _VERSION, write))
    return _ROOT[0]


def intact() -> bool:
    """Whether every file of the store is the one this module wrote, and no other file or folder exists."""
    return _matches(root().parent)


def unchanged() -> bool:
    """``intact()`` without building a store: the session-end check (``conftest.pytest_sessionfinish``)
    that fails a session in which a test wrote into it."""
    return store_unchanged("lattice", _VERSION)


# ---------- the design, read as the independent record ----------


def design_cells() -> Iterator[Cell]:
    """Every condition of the design, in the order the runs hold them."""
    return iter(DESIGN)


def cell_at(gain: float, load: float) -> Cell:
    return next(c for c in DESIGN if c.gain == gain and c.load == load)


def tripped_total(run_id: str) -> int:
    return sum(c.tripped_a if run_id == RUN_A else c.tripped_b for c in DESIGN)


# ---------- references, computed from the design and the rows, never from Prove ----------


def counts(event: str = EVENT) -> list[dict[str, Any]]:
    """Per condition, in design order: the condition, its key, each run's size and count of
    ``event``, and the discordant pairs (``a_only`` saw ``event`` in the before run only)."""
    out = []
    for cell in DESIGN:
        a_only, b_only = cell.before_only, cell.after_only
        events_a, events_b = cell.tripped_a, cell.tripped_b
        if event == OTHER:
            events_a, events_b = N - events_a, N - events_b
            a_only, b_only = b_only, a_only
        elif event != EVENT:
            raise ValueError(f"the lattice records {OUTCOMES}, not {event!r}")
        out.append({
            "config": cell.config, "config_hash": config_hash(cell.config), "n_a": N, "n_b": N,
            "events_a": events_a, "events_b": events_b, "a_only": a_only, "b_only": b_only,
        })
    return out


def bh(p: Any) -> np.ndarray:
    """Benjamini-Hochberg adjusted values, written out: ``min_{j >= i} p_(j) m / j``, capped at 1."""
    p = np.asarray(p, dtype=float)
    m = p.size
    order = np.argsort(p, kind="mergesort")
    ranked = p[order] * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def fisher(event: str = EVENT, q: float = 0.05) -> dict[str, dict[str, Any]]:
    """scipy's two-sided Fisher exact test per condition and one BH family over all of them."""
    from scipy.stats import fisher_exact

    rows = counts(event)
    ps = [fisher_exact([[r["events_a"], r["n_a"] - r["events_a"]], [r["events_b"], r["n_b"] - r["events_b"]]]).pvalue for r in rows]
    return _flagged(rows, ps, q)


def mcnemar(event: str = EVENT, q: float = 0.05) -> dict[str, dict[str, Any]]:
    """The exact McNemar test per condition (a binomial on its discordant pairs) and one BH family."""
    from scipy.stats import binomtest

    rows = counts(event)
    ps = [1.0 if r["a_only"] + r["b_only"] == 0 else binomtest(min(r["a_only"], r["b_only"]), r["a_only"] + r["b_only"], 0.5).pvalue for r in rows]
    return _flagged(rows, ps, q)


def _flagged(rows: list[dict[str, Any]], ps: list[float], q: float) -> dict[str, dict[str, Any]]:
    qs = bh(ps)
    out = {}
    for r, p, adj in zip(rows, ps, qs, strict=True):
        delta = r["events_b"] / r["n_b"] - r["events_a"] / r["n_a"]
        flagged = bool(adj < q)
        out[r["config_hash"]] = {
            **r, "p": float(p), "q": float(adj), "delta": delta,
            "direction": "unchanged" if not flagged else ("lower" if delta < 0 else "higher"),
        }
    return out


def directions(reference: Mapping[str, Mapping[str, Any]]) -> tuple[int, int]:
    """``(lower, higher)`` over a reference's flagged conditions."""
    values = [r["direction"] for r in reference.values()]
    return values.count("lower"), values.count("higher")


def rows(run_id: str) -> list[dict[str, Any]]:
    """The stored rows of ``run_id`` read back with pyarrow alone, ``config`` decoded."""
    table = pq.read_table(root() / run_id / "episodes" / "part-00000.parquet")
    out = table.to_pylist()
    for row in out:
        row["config"] = json.loads(row["config"])
    return out


def logrank(event: str = EVENT, q: float = 0.05) -> dict[str, dict[str, Any]]:
    """lifelines' two-sample log-rank test per condition on the stored times (``event`` observed,
    the other outcome censored at its time) and one BH family; ``direction`` follows the sign of
    observed minus expected events in the after run."""
    from lifelines.statistics import logrank_test

    by_cell: dict[str, dict[str, list[Any]]] = {}
    for run_id, side in ((RUN_A, "a"), (RUN_B, "b")):
        for row in rows(run_id):
            cell = by_cell.setdefault(config_hash(row["config"]), {"ta": [], "ea": [], "tb": [], "eb": []})
            cell["t" + side].append(row["t"])
            cell["e" + side].append(row["outcome"] == event)
    reference = {r["config_hash"]: r for r in counts(event)}
    ps, signs = [], []
    for r in reference.values():
        cell = by_cell[r["config_hash"]]
        result = logrank_test(cell["ta"], cell["tb"], cell["ea"], cell["eb"])
        ps.append(float(result.p_value) if np.isfinite(result.p_value) else 1.0)
        signs.append(_after_excess(cell))
    out = _flagged(list(reference.values()), ps, q)
    for r, sign in zip(out.values(), signs, strict=True):
        if r["direction"] != "unchanged":
            r["direction"] = "higher" if sign > 0 else "lower"
    return out


def _after_excess(cell: Mapping[str, list[Any]]) -> float:
    """Observed minus expected events in the after run over the pooled risk set."""
    times = sorted({t for t, e in zip(cell["ta"] + cell["tb"], cell["ea"] + cell["eb"], strict=True) if e})
    excess = 0.0
    for x in times:
        at_risk_a = sum(t >= x for t in cell["ta"])
        at_risk_b = sum(t >= x for t in cell["tb"])
        d_a = sum(t == x and e for t, e in zip(cell["ta"], cell["ea"], strict=True))
        d_b = sum(t == x and e for t, e in zip(cell["tb"], cell["eb"], strict=True))
        excess += d_b - (d_a + d_b) * at_risk_b / (at_risk_a + at_risk_b)
    return excess
