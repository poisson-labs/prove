"""S25 -- the dual root: the frozen tests for O1-O13 and O18-O22.

Tests for the layered report's dual root (P4.1): ``src/poisson_prove/tree.py`` and the
``diff`` block in ``src/poisson_prove/cli.py``.

**``poisson_prove.tree`` is imported inside each test body**: a module-level import of a module
that fails to import is a *collection* error, and pytest abandons the whole run on one. Imported
lazily, this file collects, its own tests fail, and every other test in the repo still reports.

**Measured facts the tests rest on.** The numbers below are the lattice's (``tests/lattice.py``).
They are restated here because they are why several tests look the way they do.

1. **A pair-swap resample is not a sharp null for the arm-label test.** A uniform draw from the
   pair-swap orbit is not invariant under the larger arm-label group, so the arm-label test on
   it is not exact by theorem: measured, a pair-swap resample tested by arm label rejected far
   outside the band ``[0.020, 0.080]``, and the matched construction sat inside it. **The resample follows the scheme under test**, from a table that
   is *this file's own literal* and never ``root.scheme`` -- so a scheme choice that regresses to one
   scheme for both methods is resampled under the right scheme and tested under the wrong one, and
   O10 is written to see it. That is the sharpest guard in this file, and no other test
   catches that regression. ``B`` is 1000, what the measurement used.
2. **O7's byte-identical clause holds only under pair swap.** Under arm label a cell is
   informative when its pooled outcomes are not all identical, and ``b = a.copy()`` of the
   lattice's before run has 33 such cells. The clause is split: ``n_informative_cells == 0`` and ``n_discordant == 0``
   under ``mcnemar_bh``; under ``fisher_bh`` the count equals the arm-label recomputation and is
   greater than zero. Every statistic is ``0.0`` and every p ``1.0`` under both.
3. **The lattice's uniform n = 32 cannot catch n-weighting.** Its unequal rates catch a variance-weighted
   statistic, and only that. O1 is asserted on the unequal-n fixture (O22) as well, where an
   n-weighted mean differs from the unweighted one.
4. **No example count is pinned.** The lattice has 35 informative cells under either reading,
   and 38 cells with ``delta == 0``, one of which (``gain`` 1.1 at ``load`` 30) carries
   discordant pairs, so 34 have a nonzero delta. O7 recomputes the count, and the
   ``delta == 0`` count is asserted to differ from the informative count so a builder counting
   nonzero deltas fails.
5. **The mirrored lattice's numbers.** ``location`` is exactly ``0.0``, ``p_location`` ``1.0``, ``p_dispersion`` at the floor and ``p_omnibus`` at ``2 / (B + 1)`` at
   B=1000 and 4000 under both schemes (PF4.18's scale; O9 says why), and a location-only root reads
   ``p_omnibus == 1.0`` on it.

**Conventions these frozen tests fix.**

- ``to_json()`` "bytes" means ``json.dumps(payload, sort_keys=True)``. ``json.dumps`` refusing a
  NumPy scalar is a failure, not a test defect: the CLI's ``--format json`` serialises the same
  mapping and O18 exercises it.
- **O2 is scoped to designs where every replicate is matched and no row errored.** An errored row
  is dropped before pairing, so under ``pair_swap`` its replicate is unmatched; the holes fixture
  is asserted under ``fisher_bh`` and ``logrank_bh`` only, and the truncation fixture under all
  three. O21 pins the unmatched case.
- **O7's "informative" is the operational, outcome-level reading**: a cell is informative
  under ``pair_swap`` when some matched pair's two outcomes differ, and under ``arm_label`` when
  its pooled outcomes are not all identical. On a three-outcome vocabulary with a partial event set
  that is not "the statistics' permutation distribution is not a point mass" (a cell varying only
  among unrequested outcomes is outcome-informative and statistic-degenerate). Recorded, not
  resolved; O7 is asserted only on fixtures where no row is errored or truncated.
- **The informative line is pinned by its three numbers, not its wording.** A tail such as
  "identical across arms in every episode" is the pair-swap reading and is wrong under arm
  label. The regex captures the counts and leaves the tail free.
- **The CLI block is the ``omnibus:`` line plus every following line indented by two spaces.**
  Never the tail of stdout: a later change may append after it.
- **O12's three-outcome pair is built by hand.** S24's ``write_run`` takes a fail count and a
  fixed ``fail``/``ok`` vocabulary, not an outcome vocabulary.
- **O13's "before any permutation is drawn" is pinned by cost.** With ``n_permutations = 10**6``
  a refusal that validates first returns in milliseconds; one that draws first takes minutes or
  fails to allocate. The budget is ten seconds, a thousandfold margin over the honest path.
- **O4's tie fixture is the lattice at ``q = 0.25``, ``B = 3``.** ``p_omnibus`` is exactly ``1/4``
  when every permutation is strictly less extreme than the observed statistic, which on the
  lattice's 34 moved cells fails with negligible probability (the observed ``|sum delta|`` is 11.8;
  the largest of 4000 arm-label permutations was 2.5). ``q = 0.5`` at the same ``B`` gives
  ``rejects True`` and ``q = 0.2`` gives ``False`` on the same ``p``, which is what catches a
  builder comparing to ``0.05`` instead of ``multi.q``.

**Two guards no invariant numbers.** The mirrored lattice (O9) is the sole catch for a location-only
root; no numbered invariant catches a *dispersion-only* omnibus, because on every named fixture the
dispersion root rejects wherever the dual root does. The one-discordant-pair-per-cell fixture
below has ``p_dispersion == 1.0`` exactly (the sum of squares is invariant under every exchange)
and ``p_location`` at the floor, so it is the mirror image of O9. And the trap of
exchanging per-event indicators independently rather than whole outcomes is caught with
both complementary events requested: under a whole-outcome exchange the two events' statistics are
exact negatives and their p-values exact duplicates, which a whole-outcome exchange guarantees and which an
independent exchange breaks.

**Named non-observables.** ``units.delta`` versus ``cells.delta`` on censored data has no fixture:
``_truncate_raw`` censors at the horizon, so the Aalen-Johansen estimate equals the naive
proportion on every input. Under ``arm_label`` with unequal ``n``, a builder that
assigns the first ``n_b`` of the pool to arm a is a valid permutation of a mirrored design and is
not distinguishable from the surface. The ``--methods all --format json`` shape and the exit code
of ``diff`` on a pair with no comparable cell are not pinned here: ``test_i9`` fixes the
former's top-level key set to the three methods, and nothing pins the latter.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import subprocess
import sys
import time
import warnings
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from poisson_prove import cli
from poisson_prove import diff as diff_mod
from poisson_prove.diff import multi_diff
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

import lattice

#: The generated pair (``tests/lattice.py``): the before run and the after run.
LATTICE_ROOT = lattice.root()
RUN_A, RUN_B = lattice.RUN_A, lattice.RUN_B
EVENT, OTHER = lattice.EVENT, lattice.OTHER
METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")

#: Each method's permutation scheme and the root's defaults, stated as constants here.
EXPECTED_SCHEME_BY_METHOD = {"mcnemar_bh": "pair_swap", "fisher_bh": "arm_label", "logrank_bh": "arm_label"}
EXPECTED_DEFAULT_PERMUTATIONS = 4000
EXPECTED_DEFAULT_SEED = 0
EXPECTED_ROOT_STATISTICS = ("location", "dispersion")
EXPECTED_UNITS_COLUMNS = ("event", "config_hash", "config", "n_a", "n_b", "events_a", "events_b", "delta")

#: O8 and O9: the golden knobs. The floor is ``1 / (B + 1)``, computed where it is compared.
GOLDEN_PERMUTATIONS = 4000
GOLDEN_SEED = 0

#: O10. ``K = 200`` resamples at ``B = 1000`` (the measurement's own B), test seed ``1000 + k``.
#: The band is a literal; its derivation is in the O10 docstring.
CALIBRATION_RESAMPLES = 200
CALIBRATION_PERMUTATIONS = 1000
CALIBRATION_SEED_OFFSET = 1000
CALIBRATION_BAND = (0.020, 0.080)

#: O10's resample scheme is THIS FILE's literal and is never read from the module or from
#: ``root.scheme``. Item 1 of the module docstring says why.
RESAMPLE_SCHEME_BY_METHOD = {"mcnemar_bh": "pair_swap", "fisher_bh": "arm_label"}

#: O19 and O20, case-insensitive.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke",
    "failed at", "step",
)
NULL_PHRASE = '"no cell changed"'
FAMILY_PHRASE = re.compile(r"cells x (\d+)")
FORBIDDEN_NULL = "same shift"

#: The fields ``to_json()`` must carry (the root's fields plus ``headline``); a superset is fine.
EXPECTED_JSON_KEYS = {
    "events", "method", "scheme", "q", "n_cells", "n_informative_cells", "n_discordant",
    "n_permutations", "seed", "units", "location", "dispersion", "p_location", "p_dispersion",
    "p_omnibus", "rejects", "headline",
}
#: O5 and O11: the keys a different seed or a larger B may move.
P_DRIVEN_KEYS = ("p_location", "p_dispersion", "p_omnibus", "rejects", "headline")

#: The CLI's omnibus block, line by line. Numbers are captured and checked against the fields under
#: rule 10 (``:g`` before it); nothing is pinned as a typed literal. The informative line's tail is left free (see
#: the module docstring).
OMNIBUS_FIRST_LINE = re.compile(
    r'^omnibus: "no cell changed" is (rejected|not rejected) \(p = (\S+) (<|>=) q (\S+)\) '
    r"over (\d+) cells x (\d+) events?$",
    re.MULTILINE,
)
OMNIBUS_SECOND_LINE = re.compile(
    # A count carries thousands separators (rule 10).
    r"^  min-p of location and dispersion; ([\d,]+) within-cell permutations, (pair_swap|arm_label), "
    r"seed (-?\d+)$",
    re.MULTILINE,
)
OMNIBUS_LOCATION_LINE = re.compile(r"^  location\s+(\S+): mean delta (\S+), p = (\S+)$", re.MULTILINE)
OMNIBUS_DISPERSION_LINE = re.compile(r"^  dispersion\s+(\S+): rms delta (\S+), p = (\S+)$", re.MULTILINE)
OMNIBUS_INFORMATIVE_LINE = re.compile(r"^  informative cells: (\d+) of (\d+); (\d+) \S", re.MULTILINE)

#: Synthetic vocabularies. Non-events end at the horizon; events end at ``EVENT_T``.
NON_EVENTS = frozenset({"ok", "z"})
EVENT_T = 2.0
HORIZON = 5.0
SALT, OTHER_SALT = "s25-salt", "s25-other-salt"


# ---------- data builders: construction only, no assertions and no decisions ----------


def tree() -> Any:
    """``poisson_prove.tree``, imported at call time (see the module docstring)."""
    return importlib.import_module("poisson_prove.tree")


def quiet_multi_diff(
    a: pd.DataFrame,
    b: pd.DataFrame,
    ma: RunManifest,
    mb: RunManifest,
    *,
    events: Sequence[str] | None,
    method: str,
    q: float = 0.05,
) -> Any:
    """``multi_diff`` with the unpaired-analysis warning silenced. Every non-McNemar call on a
    shared-salt pair raises it and it is not what any test below is about."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(
            a, b,
            events=None if events is None else list(events),
            method=method,  # type: ignore[arg-type]
            q=q,
            manifest_a=ma,
            manifest_b=mb,
        )


def manifest(run_id: str, salt: str) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id="synthetic@v0",
        t_unit="steps",
        run_salt=salt,
        axis_types={"task": "categorical"},
        backend="synthetic",
        environment={"note": "built by test_s25_root"},
    )


def seed_of(config: Mapping[str, Any], replicate_index: int) -> int:
    """A seed that is a function of ``(config, replicate_index)`` and never of the cell's position
    in its dict, so O21's pair stores the same seed at the same ``(config_hash,
    replicate_index)`` in its two arms. A seed of ``1000 * index + k`` by dict position, with
    ``replicate_index`` counted from ``replicate_start``, disagrees on 16 of 48 matched rows of
    that pair. No test reads a stored seed, so no test fails if this regresses."""
    return 1000 * (int(config_hash(config)[:6], 16) % 100_000) + replicate_index


def raw_frame(
    run_id: str,
    cells: Mapping[str, Sequence[str | None]],
    *,
    horizon: float = HORIZON,
    event_t: float = EVENT_T,
    replicate_start: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """An in-memory frame with the eleven columns ``Store.read(meta=False)`` returns. One row per
    outcome in ``cells[task]``; ``None`` is an errored row (no outcome, no ``t``, no horizon).
    Replicate indices count from ``replicate_start[task]`` (default 0)."""
    starts = dict(replicate_start or {})
    rows: list[dict[str, Any]] = []
    for task, outcomes in cells.items():
        config = {"task": task}
        for k, outcome in enumerate(outcomes):
            errored = outcome is None
            replicate_index = starts.get(task, 0) + k
            rows.append(
                {
                    "run_id": run_id,
                    "config_hash": config_hash(config),
                    "config": config,
                    "seed": seed_of(config, replicate_index),
                    "replicate_index": replicate_index,
                    "outcome": outcome,
                    "t": math.nan if errored else (horizon if outcome in NON_EVENTS else event_t),
                    "horizon": math.nan if errored else horizon,
                    "confidence": math.nan,
                    "error": "boom" if errored else None,
                    "wall_time": 0.0,
                }
            )
    frame = pd.DataFrame.from_records(rows)
    frame["config"] = frame["config"].astype(object)
    frame["outcome"] = frame["outcome"].astype(object)
    frame["error"] = frame["error"].astype(object)
    return frame


def write_run(
    store: Store,
    run_id: str,
    *,
    salt: str,
    cells: Mapping[str, Sequence[str]],
    horizon: float = HORIZON,
) -> None:
    """A complete synthetic run over one categorical ``task``, one episode per outcome in
    ``cells[task]``. S24's ``write_run`` shape, restated rather than imported, widened to take an
    outcome list so a three-outcome pair can be written."""
    store.create_run(manifest(run_id, salt))
    records = []
    for index, (task, outcomes) in enumerate(cells.items()):
        for k, outcome in enumerate(outcomes):
            t = horizon if outcome in NON_EVENTS else EVENT_T
            records.append(
                EpisodeRecord.from_episode(
                    Episode(outcome=outcome, t=t, horizon=horizon),
                    run_id=run_id,
                    config={"task": task},
                    seed=1000 * index + k,
                    replicate_index=k,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


def three_outcome_cells() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Six cells of 32 over ``x``, ``y``, ``z``. ``x`` is 4 per cell in both arms at the same
    replicates, so it never moves; ``y`` goes 4 -> 20 per cell; ``z`` absorbs the difference."""
    a = {f"c{i}": ["x"] * 4 + ["y"] * 4 + ["z"] * 24 for i in range(6)}
    b = {f"c{i}": ["x"] * 4 + ["y"] * 20 + ["z"] * 8 for i in range(6)}
    return a, b


def mirrored(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every cell present twice, the second copy with its arms exchanged, every
    copied row's ``config`` gaining ``{"mirror": 1}`` and its hash suffixed so the hashes stay
    distinct. No RNG, no store, no committed file."""

    def copy(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["config"] = pd.Series([dict(c, mirror=1) for c in out["config"]], index=out.index, dtype=object)
        out["config_hash"] = out["config_hash"].astype(str) + "-m"
        return out

    return (
        pd.concat([a, copy(b)], ignore_index=True),
        pd.concat([b, copy(a)], ignore_index=True),
    )


def resampled(
    a: pd.DataFrame, b: pd.DataFrame, scheme: str, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One sharp-null exchange of a complete, aligned pair (both frames sorted by
    ``(config_hash, replicate_index)`` with the same cells and the same replicates). ``pair_swap``
    exchanges whole episodes -- outcome and ``t`` together -- between arms where a fair bit is
    set; ``arm_label`` pools each cell's ``2N`` episodes, permutes them uniformly and hands the
    first ``N`` to arm a. This is the test's own construction, on its own generator."""
    n_cells = a["config_hash"].nunique()
    n = len(a) // n_cells
    oa, ob = a["outcome"].to_numpy(dtype=object), b["outcome"].to_numpy(dtype=object)
    ta, tb = a["t"].to_numpy(dtype=float), b["t"].to_numpy(dtype=float)
    if scheme == "pair_swap":
        swap = (rng.random((n_cells, n)) < 0.5).ravel()
        new_oa, new_ob = np.where(swap, ob, oa), np.where(swap, oa, ob)
        new_ta, new_tb = np.where(swap, tb, ta), np.where(swap, ta, tb)
    else:
        pooled_o = np.concatenate([oa.reshape(n_cells, n), ob.reshape(n_cells, n)], axis=1)
        pooled_t = np.concatenate([ta.reshape(n_cells, n), tb.reshape(n_cells, n)], axis=1)
        order = rng.permuted(np.tile(np.arange(2 * n), (n_cells, 1)), axis=1)
        pooled_o = np.take_along_axis(pooled_o, order, axis=1)
        pooled_t = np.take_along_axis(pooled_t, order, axis=1)
        new_oa, new_ob = pooled_o[:, :n].ravel(), pooled_o[:, n:].ravel()
        new_ta, new_tb = pooled_t[:, :n].ravel(), pooled_t[:, n:].ravel()
    a2, b2 = a.copy(), b.copy()
    a2["outcome"] = pd.Series(new_oa, index=a2.index, dtype=object)
    b2["outcome"] = pd.Series(new_ob, index=b2.index, dtype=object)
    a2["t"], b2["t"] = new_ta, new_tb
    return a2, b2


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def without_notes(err: str) -> str:
    """Stderr with the ``note:`` lines removed. Prove's own warning (``UnpairedAnalysis``, on two
    runs sharing a salt) now reaches the CLI's stderr as one ``note:`` line."""
    return "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))


def rule_10_p(p: float) -> str:
    """A p-value or q as the command line prints it (rule 10): three decimals,
    or one decimal of mantissa in exponent form below 0.001."""
    return f"{p:.3f}" if p >= 0.001 else f"{p:.1e}"


def omnibus_block(out: str) -> str:
    """The ``omnibus:`` line and every following line indented by two spaces; ``""`` when there is
    no such line. Never the tail of stdout."""
    lines = out.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("omnibus: ")]
    if not starts:
        return ""
    end = starts[0] + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    return "\n".join(lines[starts[0] : end])


def json_bytes(root: Any) -> str:
    return json.dumps(root.to_json(), sort_keys=True)


def without(payload: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in keys}


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def pair(lattice_trees: Any) -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    """The lattice pair's frames (``meta=False``) and manifests, the session's shared read."""
    return lattice_trees.frames()


@pytest.fixture(scope="module")
def lattice_roots(pair: Any, lattice_trees: Any) -> dict[str, tuple[Any, Any]]:
    """``(multi, root)`` per method on the lattice at ``events=(EVENT,)``, the golden knobs. Shared
    by O1, O2, O3, O6, O7, O8, O11 and O19/O20. Each comparison is the session's shared one; the
    root is ``omnibus`` itself, the function these frozen tests cover."""
    a, b, _, _ = pair
    out = {}
    for method in METHODS:
        multi = lattice_trees.multi((EVENT,), method)
        out[method] = (
            multi,
            tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED),
        )
    return out


@pytest.fixture(scope="module")
def mirrored_lattice(pair: Any) -> dict[str, tuple[Any, Any]]:
    a, b, ma, mb = pair
    a_m, b_m = mirrored(a, b)
    out = {}
    for method in ("fisher_bh", "mcnemar_bh"):
        multi = quiet_multi_diff(a_m, b_m, ma, mb, events=(EVENT,), method=method)
        out[method] = (
            multi,
            tree().omnibus(a_m, b_m, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED),
        )
    return out


@pytest.fixture(scope="module")
def identical_lattice(pair: Any) -> dict[str, tuple[Any, Any]]:
    """O7's byte-identical pair: ``b = a.copy()`` of the lattice's before run, both manifests the same one."""
    a, _, ma, _ = pair
    b = a.copy()
    out = {}
    for method in ("fisher_bh", "mcnemar_bh"):
        multi = quiet_multi_diff(a, b, ma, ma, events=(EVENT,), method=method)
        out[method] = (multi, tree().omnibus(a, b, multi, n_permutations=500, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def three_outcome() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    cells_a, cells_b = three_outcome_cells()
    return raw_frame("tri-a", cells_a), raw_frame("tri-b", cells_b), manifest("tri-a", SALT), manifest("tri-b", SALT)


@pytest.fixture(scope="module")
def three_outcome_roots(three_outcome: Any) -> dict[str, tuple[Any, Any]]:
    a, b, ma, mb = three_outcome
    out = {}
    for method in ("fisher_bh", "mcnemar_bh"):
        multi = quiet_multi_diff(a, b, ma, mb, events=("x", "y"), method=method)
        out[method] = (
            multi,
            tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED),
        )
    return out


@pytest.fixture(scope="module")
def unequal_n() -> dict[str, tuple[Any, Any, pd.DataFrame, pd.DataFrame]]:
    """O22, two variants of one ``fisher_bh`` pair. Cell ``v`` has ``n_a = 32`` and ``n_b = 20``;
    ``w`` is 32 against 32 with a different delta; ``z`` is all ``ok`` in both arms. In
    ``"mixed"`` cell ``v``'s 52 outcomes vary; in ``"flat"`` they are all ``ok``."""
    out = {}
    for variant, v_a, v_b in (
        ("mixed", ["fail"] * 8 + ["ok"] * 24, ["fail"] * 10 + ["ok"] * 10),
        ("flat", ["ok"] * 32, ["ok"] * 20),
    ):
        a = raw_frame("uneq-a", {"v": v_a, "w": ["fail"] * 4 + ["ok"] * 28, "z": ["ok"] * 32})
        b = raw_frame("uneq-b", {"v": v_b, "w": ["fail"] * 12 + ["ok"] * 20, "z": ["ok"] * 32})
        multi = quiet_multi_diff(a, b, manifest("uneq-a", SALT), manifest("uneq-b", OTHER_SALT), events=("fail",), method="fisher_bh")
        out[variant] = (multi, tree().omnibus(a, b, multi, n_permutations=400, seed=GOLDEN_SEED), a, b)
    return out


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding: an identical pair (``same-a``/``same-b``), a moved pair
    (``moved-a``/``moved-b``), the moved candidate under another salt (``moved-b-unpaired``,
    S24's C12 twin restated), and the three-outcome pair (``tri-a``/``tri-b``)."""
    root = tmp_path_factory.mktemp("s25-synth")
    store = Store(root)
    same = {"t0": ["fail"] * 2 + ["ok"] * 6, "t1": ["fail"] * 4 + ["ok"] * 4, "t2": ["fail"] * 6 + ["ok"] * 2}
    write_run(store, "same-a", salt=SALT, cells=same)
    write_run(store, "same-b", salt=SALT, cells=same)
    moved_a = {"t0": ["ok"] * 32, "t1": ["fail"] * 2 + ["ok"] * 30, "t2": ["fail"] * 4 + ["ok"] * 28}
    moved_b = {"t0": ["fail"] * 32, "t1": ["fail"] * 26 + ["ok"] * 6, "t2": ["fail"] * 20 + ["ok"] * 12}
    write_run(store, "moved-a", salt=SALT, cells=moved_a)
    write_run(store, "moved-b", salt=SALT, cells=moved_b)
    write_run(store, "moved-b-unpaired", salt=OTHER_SALT, cells=moved_b)
    tri_a, tri_b = three_outcome_cells()
    write_run(store, "tri-a", salt=SALT, cells=tri_a)
    write_run(store, "tri-b", salt=SALT, cells=tri_b)
    return root


def store_root(root: Path, a: str, b: str, *, events: Sequence[str], method: str, **knobs: Any) -> tuple[Any, Any]:
    """``(multi, root)`` on a stored pair, the way the CLI reaches them."""
    store = Store(root)
    fa, fb = store.read(a, meta=False), store.read(b, meta=False)
    multi = quiet_multi_diff(fa, fb, store.manifest(a), store.manifest(b), events=events, method=method)
    return multi, tree().omnibus(fa, fb, multi, **knobs)


# ---------- hypothesis: small synthetic pairs, both schemes ----------


@st.composite
def small_pairs(draw: st.DrawFn) -> tuple[dict[str, list[str]], dict[str, list[str]], tuple[str, ...], str, int, int]:
    """``2..6`` cells, ``4..12`` replicates, two or three outcomes, both schemes, ``B`` in
    ``5..40``. Returns ``(cells_a, cells_b, events, method, B, seed)``."""
    n_cells = draw(st.integers(min_value=2, max_value=6))
    n_reps = draw(st.integers(min_value=4, max_value=12))
    vocab = draw(st.sampled_from((("ok", "fail"), ("ok", "fail", "crash"))))
    cells_a = {f"c{i}": draw(st.lists(st.sampled_from(vocab), min_size=n_reps, max_size=n_reps)) for i in range(n_cells)}
    cells_b = {f"c{i}": draw(st.lists(st.sampled_from(vocab), min_size=n_reps, max_size=n_reps)) for i in range(n_cells)}
    method = draw(st.sampled_from(("fisher_bh", "mcnemar_bh")))
    permutations = draw(st.integers(min_value=5, max_value=40))
    seed = draw(st.integers(min_value=0, max_value=10**6))
    return cells_a, cells_b, vocab[1:], method, permutations, seed


PROPERTY_SETTINGS = settings(deadline=None, max_examples=40, suppress_health_check=[HealthCheck.too_slow])


# ---------- O1: the unweighted forms ----------


@pytest.mark.parametrize("method", METHODS)
def test_o1_location_is_the_mean_and_dispersion_the_rms_of_units_delta_on_the_lattice(
    lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """Location and dispersion are the unweighted sum and unweighted sum of squares, in mean
    and RMS form. Recomputed from ``units`` rather than read back. **The lattice's unequal rates are the catch**
    for a variance-weighted or pooled statistic, so the test also says the rates are unequal.
    ``delta`` is the naive proportion difference, ``+ 0.0`` so zero is unsigned, exactly."""
    _, root = lattice_roots[method]
    for event in root.events:
        sub = root.units[root.units["event"] == event]
        deltas = sub["delta"].to_numpy(dtype=float)
        assert abs(root.location[event] - float(np.mean(deltas))) <= 1e-12, (event, method)
        assert abs(root.dispersion[event] - math.sqrt(float(np.mean(deltas * deltas)))) <= 1e-12, (event, method)
        assert len({ea / na for ea, na in zip(sub["events_a"], sub["n_a"], strict=True)}) > 1
    for row in root.units.itertuples(index=False):
        assert row.delta == row.events_b / row.n_b - row.events_a / row.n_a + 0.0, row


def test_o1_holds_where_n_differs_across_cells_so_n_weighting_is_caught(
    unequal_n: dict[str, tuple[Any, Any, pd.DataFrame, pd.DataFrame]]
) -> None:
    """Item 3 of the module docstring. The lattice's n is 32 everywhere, so an n-weighted mean equals the unweighted one
    there and only a variance-weighted statistic is caught. On the O22 fixture the cell sizes
    differ, and the test says the two means differ before asserting the unweighted one."""
    _, root, _, _ = unequal_n["mixed"]
    sub = root.units[root.units["event"] == "fail"]
    deltas = sub["delta"].to_numpy(dtype=float)
    weights = (sub["n_a"] + sub["n_b"]).to_numpy(dtype=float)
    assert abs(float(np.average(deltas, weights=weights)) - float(np.mean(deltas))) > 1e-6
    assert abs(root.location["fail"] - float(np.mean(deltas))) <= 1e-12
    assert abs(root.dispersion["fail"] - math.sqrt(float(np.mean(deltas * deltas)))) <= 1e-12
    for row in root.units.itertuples(index=False):
        assert row.delta == row.events_b / row.n_b - row.events_a / row.n_a + 0.0, row


@PROPERTY_SETTINGS
@given(case=small_pairs())
def test_o1_is_universal_over_small_synthetic_pairs(case: Any) -> None:
    cells_a, cells_b, events, method, permutations, seed = case
    a, b = raw_frame("p-a", cells_a), raw_frame("p-b", cells_b)
    multi = quiet_multi_diff(a, b, manifest("p-a", SALT), manifest("p-b", SALT), events=events, method=method)
    root = tree().omnibus(a, b, multi, n_permutations=permutations, seed=seed)
    for event in root.events:
        deltas = root.units[root.units["event"] == event]["delta"].to_numpy(dtype=float)
        assert abs(root.location[event] - float(np.mean(deltas))) <= 1e-12
        assert abs(root.dispersion[event] - math.sqrt(float(np.mean(deltas * deltas)))) <= 1e-12
    for row in root.units.itertuples(index=False):
        assert row.delta == row.events_b / row.n_b - row.events_a / row.n_a + 0.0


# ---------- O2: the rebuild agrees with the diff ----------


def test_o2_units_columns_are_the_spec_tuple() -> None:
    assert tuple(tree().UNITS_COLUMNS) == EXPECTED_UNITS_COLUMNS


@pytest.mark.parametrize("method", METHODS)
def test_o2_units_agree_with_cells_row_for_row_on_the_lattice(
    lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """**This file's most important invariant.** ``omnibus`` rebuilds the cell view from the raw
    frames with ``diff.py``'s own helpers -- a second construction of something ``multi_diff``
    already built -- and this is the check that makes that safe. The trap: the rebuild
    filters null outcomes, truncates at the minimum horizon, intersects hashes and sorts them, in
    that order; a builder who simplifies any step lands a different count here, on the
    truncation and holes fixtures below if not on the lattice."""
    multi, root = lattice_roots[method]
    assert list(root.units.columns) == list(EXPECTED_UNITS_COLUMNS)
    keys = list(zip(root.units["event"], root.units["config_hash"], strict=True))
    assert len(keys) == len(set(keys)) == root.n_cells * len(root.events)
    cols = ["config_hash", "n_a", "n_b", "events_a", "events_b"]
    for event in multi.events:
        cells = multi.by_event[event].cells
        sub = root.units[root.units["event"] == event]
        assert root.n_cells == len(cells)
        assert [tuple(r) for r in sub[cols].itertuples(index=False)] == [tuple(r) for r in cells[cols].itertuples(index=False)]
        assert list(sub["config"]) == list(cells["config"])


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_o2_units_agree_with_cells_on_the_three_outcome_pair(
    three_outcome_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """Two events, so ``n_cells`` is the per-event count and not ``len(units)``."""
    multi, root = three_outcome_roots[method]
    keys = list(zip(root.units["event"], root.units["config_hash"], strict=True))
    assert len(keys) == len(set(keys)) == root.n_cells * len(root.events) == 12
    cols = ["config_hash", "n_a", "n_b", "events_a", "events_b"]
    for event in multi.events:
        cells = multi.by_event[event].cells
        sub = root.units[root.units["event"] == event]
        assert root.n_cells == len(cells) == 6
        assert [tuple(r) for r in sub[cols].itertuples(index=False)] == [tuple(r) for r in cells[cols].itertuples(index=False)]


@pytest.mark.parametrize("method", ("fisher_bh", "logrank_bh"))
def test_o2_the_rebuild_drops_errored_rows_the_way_multi_diff_does(method: str) -> None:
    """The valid-row filter. Two errored rows in one cell of arm a and one in another cell of arm
    b; ``cells.n_a`` excludes them, so a rebuild that counts every row disagrees. Under the
    arm-label unit (an episode) the design is still fully matched, which is why this fixture is
    not asserted under ``mcnemar_bh``: there the errored replicate is unmatched (O21's case)."""
    a = raw_frame("holes-a", {"h0": ["fail"] * 6 + ["ok"] * 24 + [None, None], "h1": ["fail"] * 3 + ["ok"] * 29, "h2": ["ok"] * 32})
    b = raw_frame("holes-b", {"h0": ["fail"] * 12 + ["ok"] * 20, "h1": ["fail"] * 9 + ["ok"] * 22 + [None], "h2": ["fail"] * 2 + ["ok"] * 30})
    multi = quiet_multi_diff(a, b, manifest("holes-a", SALT), manifest("holes-b", OTHER_SALT), events=("fail",), method=method)
    root = tree().omnibus(a, b, multi, n_permutations=200, seed=GOLDEN_SEED)
    cells = multi.by_event["fail"].cells
    assert sorted(cells["n_a"]) == [30, 32, 32] and sorted(cells["n_b"]) == [31, 32, 32]
    cols = ["config_hash", "n_a", "n_b", "events_a", "events_b"]
    sub = root.units[root.units["event"] == "fail"]
    assert [tuple(r) for r in sub[cols].itertuples(index=False)] == [tuple(r) for r in cells[cols].itertuples(index=False)]


@pytest.mark.parametrize("method", METHODS)
def test_o2_the_rebuild_truncates_at_the_minimum_horizon_the_way_multi_diff_does(method: str) -> None:
    """The rebuild trap's hardest case: the lattice cannot express truncation. Arm a's horizon is 5 and
    carries events at t=4.5; arm b's horizon is 3, so ``multi.horizon`` is 3 and every t=4.5 event
    in a is re-censored -- still in ``n_a``, no longer in ``events_a``. A rebuild that skips
    ``_truncate_raw`` counts them as events and disagrees with ``cells``. Replicates stay matched
    (a truncated row keeps its index), so all three methods apply."""
    a = raw_frame("trunc-a", {"k0": ["late"] * 10 + ["fail"] * 4 + ["ok"] * 18, "k1": ["late"] * 6 + ["ok"] * 26}, horizon=5.0)
    a.loc[a["outcome"] == "late", "t"] = 4.5
    a.loc[a["outcome"] == "late", "outcome"] = "fail"
    b = raw_frame("trunc-b", {"k0": ["fail"] * 5 + ["ok"] * 27, "k1": ["fail"] * 8 + ["ok"] * 24}, horizon=3.0)
    multi = quiet_multi_diff(a, b, manifest("trunc-a", SALT), manifest("trunc-b", SALT), events=("fail",), method=method)
    root = tree().omnibus(a, b, multi, n_permutations=200, seed=GOLDEN_SEED)
    cells = multi.by_event["fail"].cells
    # 16 late events plus arm a's 44 ``ok`` rows at t = 5.0: everything past the horizon is re-censored.
    assert multi.horizon == 3.0 and multi.truncated == 60
    assert sorted(cells["events_a"]) == [0, 4]
    cols = ["config_hash", "n_a", "n_b", "events_a", "events_b"]
    sub = root.units[root.units["event"] == "fail"]
    assert [tuple(r) for r in sub[cols].itertuples(index=False)] == [tuple(r) for r in cells[cols].itertuples(index=False)]


# ---------- O3: Phipson-Smyth form ----------


@pytest.mark.parametrize("method", METHODS)
def test_o3_every_p_is_one_plus_an_integer_over_b_plus_one_on_the_lattice(
    lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """``p = (1 + c) / (B + 1)`` for an integer ``0 <= c <= B``, recovered as
    ``round(p * (B + 1)) - 1``. The ``+ 1`` is what keeps a permutation p from being zero
    (Phipson & Smyth 2010); hence ``floor <= p <= 1``."""
    _, root = lattice_roots[method]
    permutations = root.n_permutations
    for p in (*root.p_location.values(), *root.p_dispersion.values(), root.p_omnibus):
        c = round(p * (permutations + 1)) - 1
        assert 0 <= c <= permutations, p
        assert abs(p - (1 + c) / (permutations + 1)) <= 1e-12, p
        assert 1.0 / (permutations + 1) <= p <= 1.0, p


@PROPERTY_SETTINGS
@given(case=small_pairs())
def test_o3_the_form_holds_over_small_synthetic_pairs_and_both_schemes(case: Any) -> None:
    """A known trap, stated here and not fixed: ties are counted with ``>=``, since discrete
    outcomes tie constantly at small N and ``>`` would be anti-conservative. This test does not
    see that; O10 does."""
    cells_a, cells_b, events, method, permutations, seed = case
    a, b = raw_frame("p-a", cells_a), raw_frame("p-b", cells_b)
    multi = quiet_multi_diff(a, b, manifest("p-a", SALT), manifest("p-b", SALT), events=events, method=method)
    root = tree().omnibus(a, b, multi, n_permutations=permutations, seed=seed)
    assert root.n_permutations == permutations and root.seed == seed
    for p in (*root.p_location.values(), *root.p_dispersion.values(), root.p_omnibus):
        c = round(p * (permutations + 1)) - 1
        assert 0 <= c <= permutations, p
        assert abs(p - (1 + c) / (permutations + 1)) <= 1e-12, p
        assert 1.0 / (permutations + 1) <= p <= 1.0, p


# ---------- O4: strictness, against multi.q ----------


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
@pytest.mark.parametrize("q,expected", ((0.25, False), (0.5, True), (0.2, False)))
def test_o4_rejects_is_strictly_p_omnibus_below_multi_q(
    pair: Any, lattice_trees: Any, method: str, q: float, expected: bool
) -> None:
    """The lattice at ``B = 3``: every permutation is strictly less extreme than the observed
    statistic on both roots (the observed ``|sum delta|`` is 11.8 against an arm-label permutation
    maximum of 2.5 over 4000 draws, measured when this moved to the lattice), so ``c = 0`` and
    ``p_omnibus == 1/4`` exactly. At ``q = 0.25`` that
    is a tie and ``rejects`` is ``False`` -- the same strictness as BH's ``q_adj < q``. At
    ``q = 0.5`` the same p rejects and at ``q = 0.2`` it does not, which is what fails a builder
    comparing to ``0.05`` or to a constant in ``cli.py``."""
    a, b, _, _ = pair
    multi = lattice_trees.multi((EVENT,), method, q=q)
    root = tree().omnibus(a, b, multi, n_permutations=3, seed=GOLDEN_SEED)
    assert root.q == q
    assert root.p_omnibus == 0.25, root.p_omnibus
    assert root.rejects is expected
    assert root.rejects == (root.p_omnibus < multi.q)


def test_o4_rejects_equals_the_strict_comparison_on_every_fixture(
    lattice_roots: dict[str, tuple[Any, Any]],
    mirrored_lattice: dict[str, tuple[Any, Any]],
    identical_lattice: dict[str, tuple[Any, Any]],
    three_outcome_roots: dict[str, tuple[Any, Any]],
) -> None:
    for group in (lattice_roots, mirrored_lattice, identical_lattice, three_outcome_roots):
        for method, (multi, root) in group.items():
            assert root.rejects == (root.p_omnibus < multi.q), (method, root.p_omnibus, multi.q)
            assert type(root.rejects) is bool


# ---------- O5: determinism within an environment ----------


def test_o5_the_same_inputs_give_identical_json_bytes_twice_in_one_process(pair: Any, lattice_trees: Any) -> None:
    """Not across NumPy releases: NEP 19 reserves the right to move a
    ``Generator`` stream. Within one environment the stream is a function of ``seed`` and nothing
    else, so two calls agree byte for byte. ``json.dumps`` succeeding is also the check that
    ``to_json()`` carries native types, which ``--format json`` needs."""
    a, b, _, _ = pair
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    first = tree().omnibus(a, b, multi, n_permutations=200, seed=7)
    second = tree().omnibus(a, b, multi, n_permutations=200, seed=7)
    assert json_bytes(first) == json_bytes(second)
    assert set(first.to_json()) >= EXPECTED_JSON_KEYS


def test_o5_the_same_inputs_give_identical_json_bytes_across_two_processes(pair: Any, lattice_trees: Any) -> None:
    a, b, _, _ = pair
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    here = sha256_of_text(json_bytes(tree().omnibus(a, b, multi, n_permutations=200, seed=0)))
    script = "\n".join(
        [
            "import hashlib, json, sys, warnings",
            "from poisson_prove.store import Store",
            "from poisson_prove.diff import multi_diff, UnpairedAnalysis",
            "from poisson_prove.tree import omnibus",
            "warnings.simplefilter('ignore', UnpairedAnalysis)",
            "s = Store(sys.argv[1]); ra, rb, event = sys.argv[2:5]",
            "a = s.read(ra, meta=False); b = s.read(rb, meta=False)",
            "m = multi_diff(a, b, events=[event], method='fisher_bh', manifest_a=s.manifest(ra), manifest_b=s.manifest(rb))",
            "r = omnibus(a, b, m, n_permutations=200, seed=0)",
            "print(hashlib.sha256(json.dumps(r.to_json(), sort_keys=True).encode('utf-8')).hexdigest())",
        ]
    )
    done = subprocess.run([sys.executable, "-c", script, str(LATTICE_ROOT), RUN_A, RUN_B, EVENT], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == here


def test_o5_a_different_seed_moves_only_the_p_driven_fields(
    unequal_n: dict[str, tuple[Any, Any, pd.DataFrame, pd.DataFrame]]
) -> None:
    """``units``, the two statistics and every count are not Monte Carlo. On this fixture the
    omnibus p sits mid-range, so the seed has room to move it; the assertion is on what it may
    not move."""
    multi, root_a, a, b = unequal_n["mixed"]
    root_b = tree().omnibus(a, b, multi, n_permutations=400, seed=GOLDEN_SEED + 1)
    payload_a, payload_b = root_a.to_json(), root_b.to_json()
    assert set(payload_a) >= set(P_DRIVEN_KEYS)
    assert payload_a["seed"] != payload_b["seed"]
    assert without(payload_a, (*P_DRIVEN_KEYS, "seed")) == without(payload_b, (*P_DRIVEN_KEYS, "seed"))


# ---------- O6: scheme follows method, never paired ----------


def test_o6_the_scheme_table_is_the_spec_table_and_every_root_follows_it(
    lattice_roots: dict[str, tuple[Any, Any]]
) -> None:
    """The table is asserted against this file's literal and not only against
    itself: a builder whose table says ``arm_label`` for every method would otherwise agree with
    its own field. ``logrank_bh`` uses arm label and the same proportions as ``fisher_bh``, so on
    the lattice the two roots differ only in ``method``."""
    assert dict(tree().SCHEME_BY_METHOD) == EXPECTED_SCHEME_BY_METHOD
    assert tuple(tree().ROOT_STATISTICS) == EXPECTED_ROOT_STATISTICS
    assert tree().DEFAULT_PERMUTATIONS == EXPECTED_DEFAULT_PERMUTATIONS
    assert tree().DEFAULT_SEED == EXPECTED_DEFAULT_SEED
    for method, (multi, root) in lattice_roots.items():
        assert root.scheme == EXPECTED_SCHEME_BY_METHOD[method] == EXPECTED_SCHEME_BY_METHOD[multi.method]
        assert root.method == method
    fisher, logrank = lattice_roots["fisher_bh"][1].to_json(), lattice_roots["logrank_bh"][1].to_json()
    assert without(fisher, ("method",)) == without(logrank, ("method",))


def test_o6_the_pairable_pair_and_its_unpairable_twin_give_identical_json(synth_root: Path) -> None:
    """The unpairable twin, S24's C12 construction restated. ``moved-b`` and ``moved-b-unpaired`` hold
    identical episodes and differ only in ``run_salt``, so the two diffs below see the same frames
    and differ only in ``seed_identity_match``. A root that dispatched on it would take pair swap on
    the first and arm label on the second, and the ``scheme`` field alone would separate the two
    payloads."""
    paired_multi, paired_root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=300, seed=GOLDEN_SEED)
    unpaired_multi, unpaired_root = store_root(synth_root, "moved-a", "moved-b-unpaired", events=("fail",), method="fisher_bh", n_permutations=300, seed=GOLDEN_SEED)
    assert paired_multi.seed_identity_match is True and unpaired_multi.seed_identity_match is False
    assert paired_root.n_informative_cells > 0
    assert json_bytes(paired_root) == json_bytes(unpaired_root)
    assert paired_root.scheme == "arm_label"


# ---------- O7: degeneracy, counted ----------


@pytest.mark.parametrize("method", METHODS)
def test_o7_informative_cells_and_discordant_pairs_are_recomputed_from_the_frames_on_the_lattice(
    pair: Any, lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """The operational definition of informative, recomputed from the raw frames (the lattice has no
    errored or truncated row, so raw and rebuilt views coincide). Under ``pair_swap``: cells with
    at least one matched pair whose two outcomes differ, and the total of such pairs. Under
    ``arm_label``: cells whose pooled outcomes are not all identical, and ``None``. Item 4 of the
    module docstring: on the lattice the informative count (35 under either reading) differs from the count
    of cells with a nonzero delta (34): ``gain`` 1.1 at ``load`` 30 moves two episodes each way, so
    it has discordant pairs and mixed outcomes and no change in the share. The test says so, so a
    builder counting nonzero deltas fails under either scheme."""
    a, b, _, _ = pair
    _, root = lattice_roots[method]
    pa = a.pivot(index="config_hash", columns="replicate_index", values="outcome")
    pb = b.pivot(index="config_hash", columns="replicate_index", values="outcome")
    pb = pb.loc[pa.index, pa.columns]
    differ = pa.to_numpy() != pb.to_numpy()
    pooled = np.concatenate([pa.to_numpy(), pb.to_numpy()], axis=1)
    nonzero_delta = int(((pb.to_numpy() == EVENT).mean(axis=1) != (pa.to_numpy() == EVENT).mean(axis=1)).sum())
    if EXPECTED_SCHEME_BY_METHOD[method] == "pair_swap":
        assert root.n_informative_cells == int(differ.any(axis=1).sum())
        assert root.n_discordant == int(differ.sum())
    else:
        assert root.n_informative_cells == int((pooled != pooled[:, :1]).any(axis=1).sum())
        assert root.n_discordant is None
    assert root.n_informative_cells != nonzero_delta, (root.n_informative_cells, nonzero_delta)
    assert 0 < root.n_informative_cells < root.n_cells


def test_o7_the_byte_identical_pair_is_a_point_mass_under_pair_swap(identical_lattice: dict[str, tuple[Any, Any]]) -> None:
    """``b = a.copy()`` with equal salts under ``mcnemar_bh``: no pair differs, so no exchange
    changes anything, every statistic is ``0.0``, every p is ``1.0`` (all ``B`` permutations tie
    the observed statistic and ties count), ``rejects`` is ``False``, and both
    degeneracy counts are zero."""
    _, root = identical_lattice["mcnemar_bh"]
    assert root.scheme == "pair_swap"
    assert all(v == 0.0 for v in root.location.values()) and all(v == 0.0 for v in root.dispersion.values())
    assert all(p == 1.0 for p in root.p_location.values()) and all(p == 1.0 for p in root.p_dispersion.values())
    assert root.p_omnibus == 1.0
    assert root.rejects is False
    assert root.n_informative_cells == 0 and root.n_discordant == 0


def test_o7_the_byte_identical_pair_keeps_its_mixed_cells_informative_under_arm_label(
    pair: Any, identical_lattice: dict[str, tuple[Any, Any]]
) -> None:
    """Item 2 of the module docstring, the arm-label half. Under arm label a cell with mixed outcomes
    is informative even when the two arms are identical: permuting its labels moves the
    statistic away from the observed zero. The lattice's before run has 33 such cells. The statistics and the
    p-values are still ``0.0`` and ``1.0``, because the observed statistic is the minimum of its
    own permutation distribution; the count is not zero, and asserting zero would pin a defect."""
    a, _, _, _ = pair
    _, root = identical_lattice["fisher_bh"]
    pa = a.pivot(index="config_hash", columns="replicate_index", values="outcome").to_numpy()
    mixed = int((pa != pa[:, :1]).any(axis=1).sum())
    assert root.scheme == "arm_label"
    assert all(v == 0.0 for v in root.location.values()) and all(v == 0.0 for v in root.dispersion.values())
    assert all(p == 1.0 for p in root.p_location.values()) and all(p == 1.0 for p in root.p_dispersion.values())
    assert root.p_omnibus == 1.0
    assert root.rejects is False
    assert root.n_discordant is None
    assert root.n_informative_cells == mixed > 0


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_o7_the_counts_are_over_outcomes_not_over_one_event_on_the_three_outcome_pair(
    three_outcome: Any, three_outcome_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """The per-event exchange trap seen from the count: a pair ``(z, y)`` is discordant even for event ``x``,
    because outcomes exchange whole. Every cell here has 16 such pairs, so all six are informative
    and ``n_discordant`` is 96 under pair swap."""
    a, b, _, _ = three_outcome
    _, root = three_outcome_roots[method]
    pa = a.pivot(index="config_hash", columns="replicate_index", values="outcome")
    pb = b.pivot(index="config_hash", columns="replicate_index", values="outcome").loc[pa.index, pa.columns]
    differ = pa.to_numpy() != pb.to_numpy()
    if method == "mcnemar_bh":
        assert root.n_informative_cells == int(differ.any(axis=1).sum()) == 6
        assert root.n_discordant == int(differ.sum()) == 96
    else:
        pooled = np.concatenate([pa.to_numpy(), pb.to_numpy()], axis=1)
        assert root.n_informative_cells == int((pooled != pooled[:, :1]).any(axis=1).sum()) == 6
        assert root.n_discordant is None


# ---------- O8: golden, the lattice rejects at the floor ----------


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_o8_the_lattice_rejects_at_the_floor_under_both_schemes(
    lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """The floor ``1 / (B + 1)`` is exact by construction: the observed statistic exceeds every
    permutation on both roots, ``c = 0``, and the rank-p of a permutation among the ``B``
    includes itself so its minimum is ``1/B > 1/(B+1)`` and no permutation's min-p reaches the
    observed one. ``location`` is recomputed from ``cells.delta``, not typed.
    Bonferroni is computed and printed, and no order is asserted."""
    multi, root = lattice_roots[method]
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    assert root.n_permutations == GOLDEN_PERMUTATIONS and root.seed == GOLDEN_SEED
    assert root.rejects is True
    assert root.p_location[EVENT] == floor
    assert root.p_dispersion[EVENT] == floor
    assert root.p_omnibus == floor
    assert abs(root.location[EVENT] - float(multi.by_event[EVENT].cells["delta"].mean())) <= 1e-12
    bonferroni = min(1.0, 2 * len(root.events) * min(*root.p_location.values(), *root.p_dispersion.values()))
    print(f"O8 {method}: p_omnibus={root.p_omnibus:g} p_bonferroni={bonferroni:g}")


# ---------- O9: the mirrored lattice separates the roots ----------


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_o9_the_mirrored_lattice_is_invisible_to_location_and_rejected_by_dispersion(
    mirrored_lattice: dict[str, tuple[Any, Any]], method: str
) -> None:
    """**Sole-catch guard for a location-only root.** On the lattice as stored every root is at the floor,
    so a location-only omnibus is byte-identical to the dual root there (O8) and blind here: it
    reads ``p_omnibus == 1.0`` on this fixture, measured under both schemes. Half the cells break
    and half improve. ``> 0.5`` rather
    than ``== 1.0`` because floating accumulation can leave ``location`` at ``1e-17`` and a
    permutation can tie it."""
    _, root = mirrored_lattice[method]
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    assert root.n_cells == 2 * lattice.CELLS == 144
    assert abs(root.location[EVENT]) < 1e-9
    assert root.p_location[EVENT] > 0.5
    assert root.p_dispersion[EVENT] == floor
    # PF4.18: the omnibus ranks every permutation on the observed point's scale, a
    # permutation's p being (#{b' : S_b' >= S_b} + [S_obs >= S_b]) / (B + 1). Dispersion's observed
    # statistic exceeds every permuted one, so no permutation reaches the floor there; location's
    # observed statistic is 0, so the one permutation holding location's largest value, when no
    # other ties it, scores 1 / (B + 1) there and is counted. By the definition the omnibus is
    # therefore 1 / (B + 1) or 2 / (B + 1), never more, and the root still rejects.
    assert root.p_omnibus in (floor, 2.0 / (GOLDEN_PERMUTATIONS + 1)), root.p_omnibus
    assert root.rejects is True
    bonferroni = min(1.0, 2 * len(root.events) * min(*root.p_location.values(), *root.p_dispersion.values()))
    print(f"O9 {method}: p_omnibus={root.p_omnibus:g} p_bonferroni={bonferroni:g}")


def test_o9_the_mirrored_fixture_still_separates_the_roots(mirrored_lattice: dict[str, tuple[Any, Any]]) -> None:
    """Before asserting on a fixture, check the fixture could disagree. From ``units``: the deltas
    sum to zero by construction and their squares do not, so a location root has nothing to see
    and a dispersion root has everything. If a change to the frames or to ``mirrored`` ever
    collapses the squares, this says so here rather than leaving O9 green while pinning nothing."""
    _, root = mirrored_lattice["fisher_bh"]
    deltas = root.units["delta"].to_numpy(dtype=float)
    assert abs(float(deltas.sum())) < 1e-9
    assert float((deltas * deltas).sum()) > 1.0
    assert len(deltas) == 2 * lattice.CELLS == 144


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_the_one_pair_per_cell_fixture_is_invisible_to_dispersion_and_rejected_by_location(method: str) -> None:
    """**Not a numbered invariant: the mirror image of O9, the sole catch for a dispersion-only
    omnibus.** Sixty-four cells of 32; arm a all ``ok``; arm b one ``fail`` at replicate 0. Every
    cell holds exactly one event among its 64 episodes, so under either exchange its delta is
    ``+-1/32`` and its square is ``1/1024`` whatever the permutation: the sum of squares is
    invariant, every permutation ties, and ``p_dispersion == 1.0`` exactly. The sum of deltas is
    at its maximum only when every bit falls the same way, probability ``2 * 2**-64`` per
    permutation, so ``p_location`` is the floor. An omnibus that reads only the dispersion side
    returns ``1.0`` here."""
    a = raw_frame("one-a", {f"c{i:02d}": ["ok"] * 32 for i in range(64)})
    b = raw_frame("one-b", {f"c{i:02d}": ["fail"] + ["ok"] * 31 for i in range(64)})
    multi = quiet_multi_diff(a, b, manifest("one-a", SALT), manifest("one-b", SALT), events=("fail",), method=method)
    root = tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    assert root.p_dispersion["fail"] == 1.0
    assert root.p_location["fail"] == floor
    assert root.p_omnibus == floor
    assert root.rejects is True


# ---------- O10: calibration on sharp-null resamples ----------


@pytest.mark.calibration
@pytest.mark.parametrize("method", ("mcnemar_bh", "fisher_bh"))
def test_o10_the_root_is_calibrated_on_sharp_null_resamples_of_the_lattice(pair: Any, method: str) -> None:
    """**What this test is and is not.** A permutation test is exact under the sharp null by
    theorem, for the group that generated the data. So a rejection rate inside the band is not
    evidence the procedure is valid; it is evidence the machinery is wired the way the theorem
    assumes. The band is written so that it fails on a wiring error, and each side names the
    errors it catches.

    **The construction.** Resample ``k`` applies one exchange drawn from ``default_rng(k)`` to the
    lattice's frames under the scheme the method under test uses -- ``pair_swap`` for ``mcnemar_bh``,
    ``arm_label`` for ``fisher_bh`` -- from ``RESAMPLE_SCHEME_BY_METHOD``, this file's literal.
    That produces a dataset uniform on the orbit of the group the test then uses, which is the
    condition the theorem needs. ``multi_diff`` runs afresh on it (O13 refuses the stored pair's
    result), then ``omnibus`` at ``B = 1000`` with seed ``1000 + k``. Resampling with
    ``pair_swap`` under both methods would be wrong: a draw uniform on the pair-swap orbit is not
    invariant under the larger arm-label group, so the arm-label test on it is not exact by
    theorem; measured, that mismatch lands far outside the band and the matched construction
    inside it.

    **The band.** ``0.05 +- 1.96 * sqrt(0.05 * 0.95 / 200) = [0.0198, 0.0802]``, the 95% Monte
    Carlo band for a true rate of 0.05 at ``K = 200``, written as the literal
    ``[0.020, 0.080]``. If a NumPy bump moves the rate out of it, that is a
    Monte Carlo event to re-run with more ``K``, not a reason to loosen the band.

    **Above 0.080 catches anti-conservative wiring**: the exchange applied to per-event indicators
    rather than whole outcomes, labels permuted across cells rather than within, a p-value
    without the ``+ 1``, ties counted with ``>``, a rank-p that excludes the permutation itself,
    an uncalibrated minimum over the ``2K`` p-values.

    **The band catches the scheme mismatch** -- **sole catch** -- the scheme choice regressing to one
    scheme for both methods, which under ``mcnemar_bh`` is resampled here under pair swap and tested
    under arm label (which side of the band it lands on depends on the fixture).

    **Below 0.020 catches conservative wiring**: Bonferroni stacked on top of the calibrated
    min-p, the calibration applied twice, or ``p_omnibus`` compared against a halved ``q``. A
    stream re-seeded on every draw is *not* conservative: every permutation is the same draw, the
    p-value collapses to the floor whenever that one draw is less extreme than the observed
    statistic, and measured on a fixture it read far above the band, not below it.

    Wall time is dominated by the 200 fresh ``multi_diff`` calls and is printed.
    """
    a, b, ma, mb = pair
    keys_a = list(zip(a["config_hash"], a["replicate_index"], strict=True))
    keys_b = list(zip(b["config_hash"], b["replicate_index"], strict=True))
    assert keys_a == keys_b and len(keys_a) == lattice.CELLS * lattice.N, "O10 needs a complete, aligned pair"
    scheme = RESAMPLE_SCHEME_BY_METHOD[method]
    started = time.perf_counter()
    rejections = 0
    for k in range(CALIBRATION_RESAMPLES):
        a2, b2 = resampled(a, b, scheme, np.random.default_rng(k))
        multi = quiet_multi_diff(a2, b2, ma, mb, events=(EVENT,), method=method)
        root = tree().omnibus(a2, b2, multi, n_permutations=CALIBRATION_PERMUTATIONS, seed=CALIBRATION_SEED_OFFSET + k)
        rejections += int(root.rejects)
    rate = rejections / CALIBRATION_RESAMPLES
    print(f"O10 {method} ({scheme} resample): rate={rate:.3f} wall={time.perf_counter() - started:.0f}s")
    assert CALIBRATION_BAND[0] <= rate <= CALIBRATION_BAND[1], (method, scheme, rate)


def test_the_omnibus_p_is_the_calibrated_count_and_not_the_bare_minimum_p() -> None:
    """**Not a numbered invariant: the deterministic guard for an uncalibrated min-p.**
    ``p_omnibus`` counts the permutations whose own min-p reaches the observed one; the bare
    minimum over the ``2K`` p-values is what Westfall-Young exists to correct. Measured on a
    fixture, the bare minimum read one resample above O10's ceiling, so O10 alone catches it
    with no margin. Here the relation is pinned instead. Writing ``c*`` for the count
    behind the smallest per-statistic p, each of those ``c*`` permutations has rank-p at most
    ``c*/B <= (1 + c*)/(B + 1)``, so ``p_omnibus >= min p`` always. The strict half needs the two
    statistics' extreme sets to differ: six cells of 32 with a small net move and some spread put
    both p-values mid-range under arm label, hundreds of permutations in play on each, and the
    pooled permutation decorrelates the two roots enough that the union is strictly larger (a gap
    of 0.15 to 0.18 across seeds when measured). Under pair swap on so few discordant pairs the
    two statistics are functions of the same bits and the sets coincide, so the strict half is
    asserted under ``fisher_bh`` only; the mid-range property is asserted as the precondition."""
    a = raw_frame("mid-a", {f"c{i}": ["fail"] * 4 + ["ok"] * 28 for i in range(6)})
    b = raw_frame("mid-b", {f"c{i}": ["fail"] * k + ["ok"] * (32 - k) for i, k in enumerate((6, 3, 6, 3, 6, 4))})
    multi = quiet_multi_diff(a, b, manifest("mid-a", SALT), manifest("mid-b", OTHER_SALT), events=("fail",), method="fisher_bh")
    root = tree().omnibus(a, b, multi, n_permutations=1000, seed=GOLDEN_SEED)
    smallest = min(root.p_location["fail"], root.p_dispersion["fail"])
    assert 0.2 < root.p_location["fail"] < 0.99 and 0.2 < root.p_dispersion["fail"] < 0.99, (root.p_location, root.p_dispersion)
    assert root.p_omnibus >= smallest
    assert root.p_omnibus > smallest, (root.p_omnibus, smallest)


# ---------- O11: the statistics are not Monte Carlo ----------


def test_o11_more_permutations_move_only_the_p_driven_fields(pair: Any, lattice_trees: Any) -> None:
    a, b, _, _ = pair
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    few = tree().omnibus(a, b, multi, n_permutations=100, seed=GOLDEN_SEED).to_json()
    many = tree().omnibus(a, b, multi, n_permutations=400, seed=GOLDEN_SEED).to_json()
    assert few["n_permutations"] == 100 and many["n_permutations"] == 400
    # ``p_floor`` is ``1 / (n_permutations + 1)``, so it moves with ``n_permutations`` and is excluded beside it.
    assert without(few, (*P_DRIVEN_KEYS, "n_permutations", "p_floor")) == without(many, (*P_DRIVEN_KEYS, "n_permutations", "p_floor"))


# ---------- O12: multi-event ----------


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_o12_only_the_moving_event_rejects_and_every_map_carries_both_events(
    three_outcome: Any, three_outcome_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """Built by hand: ``x`` sits at the same replicates in both arms so it never
    moves; ``y`` goes 4 -> 20 per cell over six cells. A builder reading only ``events[0]`` has no
    ``y``; a builder summing across events has one statistic. With ``events=("x",)`` alone the
    observed statistics are both zero, the minimum of their own permutation distributions, so
    every p is ``1.0`` and nothing rejects."""
    a, b, ma, mb = three_outcome
    _, root = three_outcome_roots[method]
    assert set(root.location) == set(root.dispersion) == set(root.p_location) == set(root.p_dispersion) == {"x", "y"}
    assert tuple(root.events) == ("x", "y")
    assert root.p_location["y"] < 0.01
    assert root.p_location["x"] > 0.2
    assert root.rejects is True
    single = quiet_multi_diff(a, b, ma, mb, events=("x",), method=method)
    root_x = tree().omnibus(a, b, single, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    assert set(root_x.location) == {"x"}
    assert root_x.rejects is False


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_complementary_events_give_exact_duplicate_p_values_and_negated_locations(method: str) -> None:
    """**Not a numbered invariant: a property of the whole-outcome exchange, and the catch for exchanging per-event indicators.**
    With a two-outcome vocabulary and both outcomes requested, every cell's two deltas are exact
    negatives under every whole-outcome exchange, so the four statistics are two pairs of
    duplicates and the p-values agree exactly. Exchanging per-event indicators independently is a
    different null under which a pair can be ``fail`` in both arms; the two events then ride
    different draws and their p-values part company. **The lattice cannot catch that**: its effect puts
    both events at the floor under any draw, and an independent exchange passes there. The six-cell mid-range pair puts both p-values where two draws differ."""
    a = raw_frame("mid-a", {f"c{i}": ["fail"] * 4 + ["ok"] * 28 for i in range(6)})
    b = raw_frame("mid-b", {f"c{i}": ["fail"] * k + ["ok"] * (32 - k) for i, k in enumerate((6, 3, 6, 3, 6, 4))})
    multi = quiet_multi_diff(a, b, manifest("mid-a", SALT), manifest("mid-b", SALT), events=("fail", "ok"), method=method)
    root = tree().omnibus(a, b, multi, n_permutations=1000, seed=GOLDEN_SEED)
    assert tuple(root.events) == ("fail", "ok")
    assert 0.02 < root.p_location["fail"] < 0.98 and 0.02 < root.p_dispersion["fail"] < 0.98, (root.p_location, root.p_dispersion)
    assert root.p_location["fail"] == root.p_location["ok"]
    assert root.p_dispersion["fail"] == root.p_dispersion["ok"]
    assert abs(root.location["fail"] + root.location["ok"]) <= 1e-12
    assert abs(root.dispersion["fail"] - root.dispersion["ok"]) <= 1e-12


# ---------- O13: refusals ----------


@pytest.mark.parametrize(
    "knobs",
    (
        {"n_permutations": 0},
        {"n_permutations": -1},
        {"seed": 1.5},
        {"seed": "0"},
        {"seed": True},
        {"seed": False},
        {"seed": None},
    ),
    ids=lambda k: "-".join(f"{name}={value!r}" for name, value in k.items()),
)
def test_o13_a_bad_knob_is_refused_with_tree_error(lattice_roots: dict[str, tuple[Any, Any]], pair: Any, knobs: dict[str, Any]) -> None:
    """``bool`` is an ``int`` to Python and is refused anyway: ``seed=True`` is a typo, never a
    seed. ``TreeError`` subclasses ``DiffError`` so ``cli``'s ``_REFUSABLE`` maps it to exit 2
    without a change to ``cli.py``."""
    a, b, _, _ = pair
    multi, _ = lattice_roots["fisher_bh"]
    assert issubclass(tree().TreeError, diff_mod.DiffError)
    with pytest.raises(tree().TreeError):
        tree().omnibus(a, b, multi, **{"n_permutations": 50, "seed": 0, **knobs})


def test_o13_frames_from_a_different_pair_are_refused_naming_the_first_mismatching_cell(
    pair: Any, lattice_roots: dict[str, tuple[Any, Any]]
) -> None:
    """The rebuild guard's refusal, and the reason the second construction is safe. ``multi`` was
    computed on ``(before, after)``; handing the root ``(before, before)`` makes ``events_b``
    disagree on every cell where the after run differs from the before run. The refusal names the first such cell in sorted-hash order,
    computed here from the raw frame and ``cells``."""
    a, _, _, _ = pair
    multi, _ = lattice_roots["fisher_bh"]
    cells = multi.by_event[EVENT].cells
    own = a.groupby("config_hash")["outcome"].apply(lambda s: int((s == EVENT).sum()))
    first = next(h for h, eb in zip(cells["config_hash"], cells["events_b"], strict=True) if own[h] != eb)
    with pytest.raises(tree().TreeError) as caught:
        tree().omnibus(a, a, multi, n_permutations=50, seed=0)
    assert first in str(caught.value), (first, str(caught.value))


def test_o13_an_empty_family_is_refused() -> None:
    """``multi_diff`` on a pair with no common cell returns ``n_tests == 0``; the root has nothing
    to test and refuses rather than printing a verdict over zero cells."""
    a = raw_frame("empty-a", {"only-a": ["fail"] * 4 + ["ok"] * 4})
    b = raw_frame("empty-b", {"only-b": ["fail"] * 4 + ["ok"] * 4})
    multi = quiet_multi_diff(a, b, manifest("empty-a", SALT), manifest("empty-b", OTHER_SALT), events=("fail",), method="fisher_bh")
    assert multi.n_tests == 0
    with pytest.raises(tree().TreeError):
        tree().omnibus(a, b, multi, n_permutations=50, seed=0)


@pytest.mark.parametrize("case", ("different-pair", "empty-family", "bool-seed"))
def test_o13_refusals_fire_before_any_permutation_is_drawn(pair: Any, lattice_roots: dict[str, tuple[Any, Any]], case: str) -> None:
    """Pinned by cost, because the order is not otherwise observable from the surface: at
    ``n_permutations = 10**6`` a refusal that validates first returns in milliseconds, and one
    that draws first spends minutes permuting 72 x 32 a million times or fails to allocate the
    block. Ten seconds is a thousandfold margin over the honest path."""
    a, _, _, _ = pair
    multi, _ = lattice_roots["fisher_bh"]
    if case == "different-pair":
        frames, knobs = (a, a, multi), {"n_permutations": 10**6, "seed": 0}
    elif case == "empty-family":
        ea = raw_frame("empty-a", {"only-a": ["fail"] * 4 + ["ok"] * 4})
        eb = raw_frame("empty-b", {"only-b": ["fail"] * 4 + ["ok"] * 4})
        empty = quiet_multi_diff(ea, eb, manifest("empty-a", SALT), manifest("empty-b", OTHER_SALT), events=("fail",), method="fisher_bh")
        frames, knobs = (ea, eb, empty), {"n_permutations": 10**6, "seed": 0}
    else:
        frames, knobs = (a, pair[1], multi), {"n_permutations": 10**6, "seed": True}
    started = time.perf_counter()
    with pytest.raises(tree().TreeError):
        tree().omnibus(*frames, **knobs)
    assert time.perf_counter() - started < 10.0


def test_o13_the_cli_maps_a_refusal_to_exit_one_without_a_traceback(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--permutations", "0"])
    # A refusal exits 1.
    assert code == 1, (out, err)
    assert "error:" in err and "Traceback" not in out + err, err


# ---------- O18: the CLI block ----------


def test_o18_the_block_follows_the_interval_block_and_its_first_line_carries_the_fields(synth_root: Path) -> None:
    """The CLI's omnibus block, through ``main()`` with ``StringIO`` streams. The block is found by index and
    never by ``endswith``: a later change may append after it. The first line's p, q, verdict,
    cell count and event count are captured and checked against the fields under rule 10."""
    multi, root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--method", "fisher_bh"])
    assert code == 0, (out, err)
    # The pair shares a salt, so stderr now carries one note line.
    assert without_notes(err) == "", err
    assert out.index("intervals: ") < out.index("omnibus: "), out
    match = OMNIBUS_FIRST_LINE.search(out)
    assert match is not None, out
    verdict, p, sign, q, n_cells, n_events = match.groups()
    assert root.rejects is True
    assert (verdict, sign) == ("rejected", "<")
    # p and q print under rule 10, not ``:g``.
    assert p == rule_10_p(root.p_omnibus) and q == rule_10_p(multi.q)
    assert int(n_cells) == root.n_cells and int(n_events) == len(root.events) == 1


def test_o18_the_other_branch_reads_not_rejected(synth_root: Path) -> None:
    _, root = store_root(synth_root, "same-a", "same-b", events=("fail",), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "same-a", "same-b", "--event", "fail", "--method", "fisher_bh"])
    # The pair shares a salt, so stderr now carries one note line.
    assert code == 0 and without_notes(err) == "", (out, err)
    match = OMNIBUS_FIRST_LINE.search(out)
    assert match is not None, out
    assert root.rejects is False
    assert (match.group(1), match.group(3)) == ("not rejected", ">=")
    # p prints under rule 10, not ``:g``.
    assert match.group(2) == rule_10_p(root.p_omnibus)


def test_o18_the_second_line_and_the_informative_line_carry_the_fields(synth_root: Path) -> None:
    """Every number on the block is a field the test reads back."""
    _, root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    # PF3: the synthetic pair shares a salt, so the default is now the
    # paired test (scheme pair_swap); the root here is the unpaired test's, named.
    code, out, _ = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--method", "fisher_bh"])
    assert code == 0, out
    second = OMNIBUS_SECOND_LINE.search(out)
    assert second is not None, out
    # The permutation count carries separators (rule 10); the seed does not.
    assert (second.group(1), second.group(2), int(second.group(3))) == (f"{root.n_permutations:,}", root.scheme, root.seed)
    informative = OMNIBUS_INFORMATIVE_LINE.search(out)
    assert informative is not None, out
    assert (int(informative.group(1)), int(informative.group(2)), int(informative.group(3))) == (
        root.n_informative_cells, root.n_cells, root.n_cells - root.n_informative_cells,
    )


def test_o18_one_location_and_one_dispersion_line_per_event_in_events_order(synth_root: Path) -> None:
    """The three-outcome pair on the store, both events requested: two ``location`` lines and two
    ``dispersion`` lines, in ``multi.events`` order, values under rule 10 (``:g`` before it)."""
    _, root = store_root(synth_root, "tri-a", "tri-b", events=("x", "y"), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "tri-a", "tri-b", "--event", "x", "--event", "y"])
    # The pair shares a salt, so stderr now carries one note line.
    assert code == 0 and without_notes(err) == "", (out, err)
    block = omnibus_block(out)
    locations = OMNIBUS_LOCATION_LINE.findall(block)
    dispersions = OMNIBUS_DISPERSION_LINE.findall(block)
    assert [e for e, _, _ in locations] == [e for e, _, _ in dispersions] == list(root.events) == ["x", "y"]
    # Deltas print to three decimals and p under rule 10, not ``:g``.
    for event, value, p in locations:
        assert (value, p) == (f"{root.location[event]:.3f}", rule_10_p(root.p_location[event])), event
    for event, value, p in dispersions:
        assert (value, p) == (f"{root.dispersion[event]:.3f}", rule_10_p(root.p_dispersion[event])), event
    first = OMNIBUS_FIRST_LINE.search(block)
    assert first is not None and int(first.group(6)) == 2, block


def test_o18_permutations_and_seed_reach_the_call_and_json_carries_to_json(synth_root: Path) -> None:
    """``--permutations 200 --seed 3`` reach ``omnibus``; ``--json`` (``--format json`` before) is
    ``{**multi.to_json(), "omnibus": root.to_json()}`` with the CLI composing a mapping and
    computing nothing, so the ``"omnibus"`` value equals the payload the test computes on the
    same frames with the same knobs, after one JSON round trip."""
    multi, root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=200, seed=3)
    # --json replaces --format json; the shared salt adds one note line.
    # PF3: the synthetic pair shares a salt, so the default is now the
    # paired test (scheme pair_swap); the root here is the unpaired test's, named.
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--json", "--permutations", "200", "--seed", "3", "--method", "fisher_bh"])
    assert code == 0 and without_notes(err) == "", (out, err)
    payload = json.loads(out)
    assert payload["omnibus"]["n_permutations"] == 200 and payload["omnibus"]["seed"] == 3
    assert payload["omnibus"] == json.loads(json.dumps(root.to_json()))
    for key in multi.to_json():
        assert key in payload, key


def test_o18_the_defaults_are_the_named_constants(synth_root: Path) -> None:
    # --json replaces --format json.
    code, out, _ = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--json"])
    assert code == 0, out
    payload = json.loads(out)["omnibus"]
    assert payload["n_permutations"] == EXPECTED_DEFAULT_PERMUTATIONS and payload["seed"] == EXPECTED_DEFAULT_SEED


# ---------- O19 and O20: vocabulary ----------


def test_o19_no_headline_uses_the_forbidden_vocabulary(
    lattice_roots: dict[str, tuple[Any, Any]],
    mirrored_lattice: dict[str, tuple[Any, Any]],
    identical_lattice: dict[str, tuple[Any, Any]],
    three_outcome_roots: dict[str, tuple[Any, Any]],
) -> None:
    """The two prohibitions -- nothing shaped like "given the root passed", nothing in the
    "where it broke" vocabulary -- applied to the first rendered byte of the nested family. A
    root has no leaves and no groups, so neither sentence is natural here; the invariant exists
    so the rule is already in force when they arrive. ``headline()`` is one line and is pinned by
    this and O20, never by bytes."""
    for group in (lattice_roots, mirrored_lattice, identical_lattice, three_outcome_roots):
        for method, (_, root) in group.items():
            text = root.headline()
            assert "\n" not in text, (method, text)
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in text.lower(), (method, phrase, text)


def test_o19_the_cli_block_uses_none_of_the_forbidden_vocabulary(synth_root: Path) -> None:
    """On the block only, extracted by its own shape. The synthetic store's ``t_unit`` is
    ``steps``, so a block that printed the unit would trip ``step``; the block does not
    print it."""
    for a, b, events in (("moved-a", "moved-b", ("fail",)), ("same-a", "same-b", ("fail",)), ("tri-a", "tri-b", ("x", "y"))):
        argv = ["--store", str(synth_root), "diff", a, b]
        for event in events:
            argv += ["--event", event]
        code, out, _ = run_cli(argv)
        assert code == 0, out
        block = omnibus_block(out)
        assert block, out
        for phrase in FORBIDDEN_VOCABULARY:
            assert phrase not in block.lower(), (a, phrase, block)


def test_o20_every_headline_quotes_the_null_and_names_the_family(
    lattice_roots: dict[str, tuple[Any, Any]],
    mirrored_lattice: dict[str, tuple[Any, Any]],
    identical_lattice: dict[str, tuple[Any, Any]],
    three_outcome_roots: dict[str, tuple[Any, Any]],
) -> None:
    """The only null this file tests is the sharp "no cell changed", quoted
    verbatim; "same shift" -- Ding, Feller & Miratrix's other null -- is not tested, named or
    printed."""
    for group in (lattice_roots, mirrored_lattice, identical_lattice, three_outcome_roots):
        for method, (_, root) in group.items():
            text = root.headline()
            assert NULL_PHRASE in text, (method, text)
            family = FAMILY_PHRASE.search(text)
            assert family is not None and int(family.group(1)) == len(root.events), (method, text)
            assert FORBIDDEN_NULL not in text.lower(), (method, text)


def test_o20_the_cli_block_quotes_the_null_and_names_the_family(synth_root: Path) -> None:
    for a, b, events in (("moved-a", "moved-b", ("fail",)), ("tri-a", "tri-b", ("x", "y"))):
        argv = ["--store", str(synth_root), "diff", a, b]
        for event in events:
            argv += ["--event", event]
        code, out, _ = run_cli(argv)
        assert code == 0, out
        block = omnibus_block(out)
        assert NULL_PHRASE in block, block
        family = FAMILY_PHRASE.search(block)
        assert family is not None and int(family.group(1)) == len(events), block
        assert FORBIDDEN_NULL not in block.lower(), block


# ---------- O21: unmatched replicates under pair swap ----------


def test_o21_unmatched_replicates_are_dropped_by_the_join_and_not_mispaired() -> None:
    """The fixture that disagrees with O2, so O2 is scoped to matched designs and this pins the
    other case. Cell ``u`` has replicates ``0..31`` in a and ``16..47`` in b; the pair-swap unit is
    the matched pair, so ``units`` sees 16 of them while ``cells`` counts 32 episodes per arm. The
    event counts are over the joined pairs only -- a's fails sit at ``0..7`` and are all outside
    the join, b's at ``16..19`` and all inside it -- and ``n_discordant`` counts joined pairs that
    differ. The two arms store the same seed at every matched ``(config_hash, replicate_index)``
    (``seed_of``)."""
    a = raw_frame("um-a", {"u": ["fail"] * 8 + ["ok"] * 24, "v": ["fail"] * 3 + ["ok"] * 29})
    b = raw_frame("um-b", {"u": ["fail"] * 4 + ["ok"] * 28, "v": ["fail"] * 9 + ["ok"] * 23}, replicate_start={"u": 16})
    multi = quiet_multi_diff(a, b, manifest("um-a", SALT), manifest("um-b", SALT), events=("fail",), method="mcnemar_bh")
    root = tree().omnibus(a, b, multi, n_permutations=300, seed=GOLDEN_SEED)
    u = config_hash({"task": "u"})
    cell = multi.by_event["fail"].cells.set_index("config_hash").loc[u]
    unit = root.units.set_index("config_hash").loc[u]
    assert (int(cell["n_a"]), int(cell["n_b"])) == (32, 32)
    assert (int(unit["n_a"]), int(unit["n_b"])) == (16, 16)
    joined = pd.merge(a[a["config_hash"] == u][["replicate_index", "outcome"]], b[b["config_hash"] == u][["replicate_index", "outcome"]], on="replicate_index", suffixes=("_a", "_b"))
    assert len(joined) == 16
    assert (int(unit["events_a"]), int(unit["events_b"])) == (int((joined["outcome_a"] == "fail").sum()), int((joined["outcome_b"] == "fail").sum())) == (0, 4)
    assert unit["delta"] == 4 / 16 - 0 / 16 + 0.0
    v = config_hash({"task": "v"})
    assert root.n_discordant == int((joined["outcome_a"] != joined["outcome_b"]).sum()) + int((a[a["config_hash"] == v]["outcome"].to_numpy() != b[b["config_hash"] == v]["outcome"].to_numpy()).sum())


# ---------- O22: unequal n under arm label ----------


def test_o22_unequal_n_keeps_each_arms_count_and_the_naive_delta(
    unequal_n: dict[str, tuple[Any, Any, pd.DataFrame, pd.DataFrame]]
) -> None:
    """``arm_label`` permutes the ``n_a + n_b`` labels and assigns the first
    ``n_a`` to arm a, so per-cell sizes are preserved. From the surface: the ``units`` row carries
    ``(32, 20)`` and ``delta == events_b/20 - events_a/32``."""
    _, root, _, _ = unequal_n["mixed"]
    v = config_hash({"task": "v"})
    unit = root.units.set_index("config_hash").loc[v]
    assert (int(unit["n_a"]), int(unit["n_b"])) == (32, 20)
    assert (int(unit["events_a"]), int(unit["events_b"])) == (8, 10)
    assert unit["delta"] == 10 / 20 - 8 / 32 + 0.0
    assert root.scheme == "arm_label"


def test_o22_the_unequal_cell_is_informative_iff_its_fifty_two_outcomes_are_not_all_identical(
    unequal_n: dict[str, tuple[Any, Any, pd.DataFrame, pd.DataFrame]]
) -> None:
    """The exchange pools 52 outcomes. In ``"mixed"`` they vary and the cell counts; in ``"flat"``
    they are all ``ok`` and it does not. Each count equals the arm-label recomputation, and the
    two differ by exactly the one cell."""
    counts = {}
    for variant, (_, root, a, b) in unequal_n.items():
        expected = 0
        for h in sorted(set(a["config_hash"])):
            pooled = np.concatenate([a[a["config_hash"] == h]["outcome"].to_numpy(), b[b["config_hash"] == h]["outcome"].to_numpy()])
            expected += int((pooled != pooled[0]).any())
        assert root.n_informative_cells == expected, variant
        assert root.n_discordant is None
        counts[variant] = root.n_informative_cells
    assert counts["mixed"] - counts["flat"] == 1, counts
