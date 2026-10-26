"""S25 -- the dual root: the frozen tests for O1-O23 except O15.

Written from "Proofload -- Spec S25 Layered Report P4.1 Dual Root" section B.4, under the two
calls the step-zero report drew (2026-09-07). The build adds ``src/proofload/tree.py`` and the
``diff`` block in ``src/proofload/cli.py`` against this file and does not edit it.

**``proofload.tree`` is imported inside each test body**, the way the M12 frozen tests reached
``proofload.trace`` before it existed: a module-level import of a module that is not there is a
*collection* error, and pytest abandons the whole run on one. Imported lazily, this file collects,
its own tests fail, and every other test in the repo still reports. The static tests read
``src/proofload/tree.py`` as text and fail while it is absent.

**Step zero, re-derived before a test was written.** Six things the spec asserts were checked
against the measurement script and, where the script could not speak, measured again on the
committed fixture of the time; the numbers below are the lattice's (``tests/lattice.py``), measured
when this file moved to it. They are restated here because they are why several tests look the way
they do.

1. **O10's resample as the spec wrote it is not a sharp null for the arm-label test.** The spec
   said a ``pair_swap`` exchange "produces a sharp-null dataset whatever the method under test".
   A uniform draw from the pair-swap orbit is not invariant under the larger arm-label group, so
   the arm-label test on it is not exact by theorem: measured at step zero, a pair-swap resample
   tested by arm label rejected far outside the band ``[0.020, 0.080]``, and the matched
   construction sat inside it. **The resample follows the scheme under test**, from a table that
   is *this file's own literal* and never ``root.scheme`` -- so a scheme choice that regresses to one
   scheme for both methods is resampled under the right scheme and tested under the wrong one, and
   O10 is written to see it. That is the sharpest guard in the packet
   and it is marked sole-catch in the mutation table. ``B`` is 1000, what the measurement used.
2. **O7's byte-identical clause holds only under pair swap.** Under arm label a cell is
   informative when its pooled outcomes are not all identical, and ``b = a.copy()`` of the
   lattice's before run has 33 such cells. The clause is split: ``n_informative_cells == 0`` and ``n_discordant == 0``
   under ``mcnemar_bh``; under ``fisher_bh`` the count equals the arm-label recomputation and is
   greater than zero. Every statistic is ``0.0`` and every p ``1.0`` under both.
3. **O16's blanket ban is red at baseline.** ``capture.py:433`` already constructs
   ``random.Random(os.urandom(32))`` for something that is not a permutation stream. The guard is
   scoped: ``default_rng`` at exactly one call site across ``src/``, in ``tree.py`` (widened
   2026-09-22 to the two named sites, ``tree.py`` ``_draw`` and ``paired.py``
   ``_cluster_bootstrap``, one stream per estimator); no
   ``np.random.seed``, ``RandomState`` or legacy ``np.random.<fn>`` anywhere in ``src/``; no
   ``random.Random``, ``random.seed`` or ``secrets`` in ``tree.py`` or ``diff.py``. The capture
   site is named here as pre-existing and out of scope; naming it beats widening the guard.
4. **The lattice's uniform n = 32 cannot catch n-weighting.** Its unequal rates catch a variance-weighted
   statistic, and only that. O1 is asserted on the unequal-n fixture (O22) as well, where an
   n-weighted mean differs from the unweighted one.
5. **The spec's block example is illustrative.** The lattice has 35 informative cells under
   either reading, and 38 cells with ``delta == 0``, one of which (``gain`` 1.1 at ``load`` 30)
   carries discordant pairs, so 34 have a nonzero delta. Nothing here pins the example; O7 recomputes, and the ``delta == 0`` count
   is asserted to differ from the informative count so a builder counting nonzero deltas fails.
6. **The step-zero log's addendum numbers (mirrored, calibration) were produced by code not in
   the committed script.** Re-derived on the mirrored lattice: ``location`` is exactly ``0.0``,
   ``p_location`` ``1.0``, ``p_dispersion`` at the floor and ``p_omnibus`` at ``2 / (B + 1)`` at
   B=1000 and 4000 under both schemes (PF4.18's scale; O9 says why), and a location-only root reads
   ``p_omnibus == 1.0`` on it.

**Conventions these frozen tests fix where the spec is silent. The build follows these.**

- ``to_json()`` "bytes" means ``json.dumps(payload, sort_keys=True)``. ``json.dumps`` refusing a
  NumPy scalar is a failure, not a test defect: the CLI's ``--format json`` serialises the same
  mapping and O18 exercises it.
- **O2 is scoped to designs where every replicate is matched and no row errored.** An errored row
  is dropped before pairing, so under ``pair_swap`` its replicate is unmatched; the holes fixture
  is asserted under ``fisher_bh`` and ``logrank_bh`` only, and the truncation fixture under all
  three. O21 pins the unmatched case.
- **O7's "informative" is the spec's operational, outcome-level reading**: a cell is informative
  under ``pair_swap`` when some matched pair's two outcomes differ, and under ``arm_label`` when
  its pooled outcomes are not all identical. On a three-outcome vocabulary with a partial event set
  that is not "the statistics' permutation distribution is not a point mass" (a cell varying only
  among unrequested outcomes is outcome-informative and statistic-degenerate). Recorded, not
  resolved; O7 is asserted only on fixtures where no row is errored or truncated.
- **The informative line is pinned by its three numbers, not its wording.** The spec's tail,
  "identical across arms in every episode", is the pair-swap reading and is wrong under arm
  label. The regex captures the counts and leaves the tail free.
- **The CLI block is the ``omnibus:`` line plus every following line indented by two spaces.**
  Never the tail of stdout: a later packet may append after it (Rollout Plan principle 4 rule 4,
  and E12's precedent).
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

**Two guards the spec does not number.** The mirrored lattice (O9) is the sole catch for a location-only
root; nothing in the spec catches a *dispersion-only* omnibus, because on every named fixture the
dispersion root rejects wherever the dual root does. The one-discordant-pair-per-cell fixture
below has ``p_dispersion == 1.0`` exactly (the sum of squares is invariant under every exchange)
and ``p_location`` at the floor, so it is the mirror image of O9. And section 8 trap 2 --
exchanging per-event indicators independently rather than whole outcomes -- is caught with
both complementary events requested: under a whole-outcome exchange the two events' statistics are
exact negatives and their p-values exact duplicates, which section 6 states and which an
independent exchange breaks.

**Named non-observables.** ``units.delta`` versus ``cells.delta`` on censored data has no fixture:
``_truncate_raw`` censors at the horizon, so the Aalen-Johansen estimate equals the naive
proportion on every input (S24 finding 6). Under ``arm_label`` with unequal ``n``, a builder that
assigns the first ``n_b`` of the pool to arm a is a valid permutation of a mirrored design and is
not distinguishable from the surface. The ``--methods all --format json`` shape and the exit code
of ``diff`` on a pair with no comparable cell are spec amendments, not pins: ``test_i9`` fixes the
former's top-level key set to the three methods, and nothing pins the latter.
"""

from __future__ import annotations

import ast
import functools
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

import poisson_prove
from poisson_prove import cli
from poisson_prove import diff as diff_mod
from poisson_prove.diff import multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

import lattice

PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parents[1]
#: The generated pair (``tests/lattice.py``): the before run and the after run.
LATTICE_ROOT = lattice.root()
RUN_A, RUN_B = lattice.RUN_A, lattice.RUN_B
# PF2 (spec section 4.3): every run has a name (target id up to its first "/", the UTC date of
# created_at, a letter); serve names the lattice's runs by these.
NAME_A, NAME_B = lattice.NAME_A, lattice.NAME_B
EVENT, OTHER = lattice.EVENT, lattice.OTHER
TREE_SOURCE = PACKAGE / "tree.py"
METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")

#: Spec section 2 and section 0.2, stated in the spec, so constants here (standing rule 2).
EXPECTED_SCHEME_BY_METHOD = {"mcnemar_bh": "pair_swap", "fisher_bh": "arm_label", "logrank_bh": "arm_label"}
EXPECTED_DEFAULT_PERMUTATIONS = 4000
EXPECTED_DEFAULT_SEED = 0
EXPECTED_ROOT_STATISTICS = ("location", "dispersion")
EXPECTED_UNITS_COLUMNS = ("event", "config_hash", "config", "n_a", "n_b", "events_a", "events_b", "delta")

#: O8 and O9: the golden knobs. The floor is ``1 / (B + 1)``, computed where it is compared.
GOLDEN_PERMUTATIONS = 4000
GOLDEN_SEED = 0

#: O10. ``K = 200`` resamples at ``B = 1000`` (the measurement's own B), test seed ``1000 + k``.
#: The band is the spec's literal; its derivation is in the O10 docstring.
CALIBRATION_RESAMPLES = 200
CALIBRATION_PERMUTATIONS = 1000
CALIBRATION_SEED_OFFSET = 1000
CALIBRATION_BAND = (0.020, 0.080)

#: O10's resample scheme is THIS FILE's literal and is never read from the module or from
#: ``root.scheme``. Step zero item 1 says why.
RESAMPLE_SCHEME_BY_METHOD = {"mcnemar_bh": "pair_swap", "fisher_bh": "arm_label"}

#: O19 and O20, case-insensitive.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke",
    "failed at", "step",
)
NULL_PHRASE = '"no cell changed"'
FAMILY_PHRASE = re.compile(r"cells x (\d+)")
FORBIDDEN_NULL = "same shift"

#: O17. The thirteen root fields the CLI may print and may not compute with.
CLI_GUARDED_FIELDS = {
    "location", "dispersion", "p_location", "p_dispersion", "p_omnibus", "rejects", "n_cells",
    "n_informative_cells", "n_discordant", "n_permutations", "seed", "scheme", "units",
}

#: The fields ``to_json()`` must carry (spec section 2 plus ``headline``); a superset is fine.
EXPECTED_JSON_KEYS = {
    "events", "method", "scheme", "q", "n_cells", "n_informative_cells", "n_discordant",
    "n_permutations", "seed", "units", "location", "dispersion", "p_location", "p_dispersion",
    "p_omnibus", "rejects", "headline",
}
#: O5 and O11: the keys a different seed or a larger B may move.
P_DRIVEN_KEYS = ("p_location", "p_dispersion", "p_omnibus", "rejects", "headline")

#: Section 3.4's block, line by line. Numbers are captured and checked against the fields under
#: rule 10 (front-door spec section 5.4; ``:g`` before it); nothing is pinned as a typed literal. The informative line's tail is left free (see
#: the module docstring).
OMNIBUS_FIRST_LINE = re.compile(
    r'^omnibus: "no cell changed" is (rejected|not rejected) \(p = (\S+) (<|>=) q (\S+)\) '
    r"over (\d+) cells x (\d+) events?$",
    re.MULTILINE,
)
OMNIBUS_SECOND_LINE = re.compile(
    # A count carries thousands separators (front-door spec section 5.4, rule 10).
    r"^  min-p of location and dispersion; ([\d,]+) within-cell permutations, (pair_swap|arm_label), "
    r"seed (-?\d+)$",
    re.MULTILINE,
)
OMNIBUS_LOCATION_LINE = re.compile(r"^  location\s+(\S+): mean delta (\S+), p = (\S+)$", re.MULTILINE)
OMNIBUS_DISPERSION_LINE = re.compile(r"^  dispersion\s+(\S+): rms delta (\S+), p = (\S+)$", re.MULTILINE)
OMNIBUS_INFORMATIVE_LINE = re.compile(r"^  informative cells: (\d+) of (\d+); (\d+) \S", re.MULTILINE)

#: O14 and O23. Minted on the bare tree at cd5f177 (2026-09-07), before the build exists: a hash,
#: never a diff of two renders. ``multi_diff(before, after, events=(EVENT,), method=...)``,
#: ``json.dumps(to_json(), sort_keys=True)``.
# PF4 (PF4.3, PF4.13 to PF4.15, PF4.20): MULTI_JSON_SHA256 is no longer asserted. PF4 adds
# columns to every cell and changes its limits and words, so the multi_diff test checks the facts
# the digest guarded instead (LATTICE_DIRECTION_COUNTS and the per-cell references below).
#: ``check before after --event tripped``: exit code, bare tree.
# PF3 (Q17, spec sections 4.4 and 14; rule R1): the lattice's runs share a salt, so the default is now the paired
# test; check's gate here is the flat family's unpaired test, named.
# PF4 (PF4.20): tripped has no kind, so the default --fail-on worse is refused; --fail-on
# higher is the same gate on it (fail when the rate rose).
CHECK_ARGV = ("check", RUN_A, RUN_B, "--event", EVENT, "--method", "fisher_bh", "--fail-on", "higher")
# CHECK_STDOUT_SHA256 removed: the command line's new look changes check's stdout, and its test
# checks the facts the digest guarded instead (front-door spec section 14).
CHECK_EXIT = 0
#: ``serve before after --event tripped --x gain --y load --json``, bare tree. The structure
#: echoes the ``--store`` path as ``pair.store_root``, so the digest is of the parsed structure with
#: that one value replaced by ``<store>`` and re-serialised with sorted keys; the raw bytes would
#: pin the machine's absolute path.
# PF3 (Q17, spec sections 4.4 and 14; rule R1): the lattice's runs share a salt, so the default is now the paired
# test; the structure digest is the unpaired test's, named.
SERVE_ARGV = ("serve", RUN_A, RUN_B, "--event", EVENT, "--x", lattice.X, "--y", lattice.Y, "--json", "--method", "fisher_bh")
# Re-minted 2026-09-20 (truncation surfacing): the structure's ``diff`` object renames the horizon key in place and gains six keys, and the
# schema is /5 before this projection sets it back to /2. Each value is the baseline's plus that change.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): the structure gains the summary key and each panel's mde_unchanged (spec LS sections 3.3, 3.5); with schema projected back to /2 nothing else moves, the figure included. The same value in all five carriers. Read through this test's own measurement on the built tree, not predicted.
# PF4 (PF4.3, PF4.11, PF4.17, PF4.20): SERVE_STRUCTURE_SHA256 is no longer asserted. PF4 removes
# pair.store_root, adds the Summary's verdict, the shares and the direction words, so the serve
# test checks the facts the digest guarded instead.
#: S29's narrowing (spec S29 section 3.7, draft ADR-074): ``serve --json`` now prints
#: ``proofload.viewpair/3``, which carries M14's tree under one new top-level key. The digest above
#: was minted on the bare tree, so it is taken over the structure with ``tree`` removed and
#: ``schema`` set back to this literal; on the bare tree that projection is the identity.

#: S24's column digests and S21's coverage digest, restated rather than imported, are replaced by
#: the facts they guarded (``assert_q_column_is_bh_over_its_p_column`` and its two siblings below).
#: ``PAIR`` is ``multi_diff(before, after, events=(EVENT, OTHER), method="fisher_bh")``; ``LOGRANK``
#: the same pair at ``events=(EVENT,)``, ``method="logrank_bh"``.
#: The three digests S21's E14 pins, restated. Minted on the bare tree at b10a146 by ``report`` on
#: the pair with one event and both axes.
# PF3 (Q17, spec sections 4.4 and 14; rule R1): the lattice's runs share a salt, so the default is now the paired
# test; the E14 digests and the heatmap are the unpaired test's, named.
E14_ARGV = ("report", RUN_A, RUN_B, "--event", EVENT, "--x", lattice.X, "--y", lattice.Y, "--method", "fisher_bh")
# Re-minted 2026-09-20 (truncation surfacing): report.md and receipt.html take the horizon rename and the two observation-cap lines
# (the builder is handed manifests and no counts); heatmap.svg is unchanged. Each value is the baseline's plus that change, byte for byte.
# PF4 (PF4.3, PF4.15, PF4.20): the three E14 digests are no longer asserted. PF4 changes all three
# files (the share table, the limit notes, direction words for an event of unknown kind), so the
# E14 test checks the facts they guarded instead.
#: PF4: what the multi, E14 and serve digests above guarded on the lattice's ``tripped``, as numbers
#: known outside any build. The direction counts per method are the lattice's references'
#: (``lattice.fisher``, ``lattice.mcnemar``, ``lattice.logrank``): Fisher 22 lower / 0 higher,
#: McNemar 27 / 0, log-rank 27 / 12 (a rejected cell's direction comes from the log-rank statistic,
#: PF4.13, and the twelve ``load`` 100 conditions trip sooner in the after run).
LATTICE_DIRECTION_COUNTS = {"fisher_bh": (22, 0), "mcnemar_bh": (27, 0), "logrank_bh": (27, 12)}
#: The reference each method's per-cell p, q and direction are checked against.
REFERENCE_BY_METHOD = {"fisher_bh": lattice.fisher, "mcnemar_bh": lattice.mcnemar, "logrank_bh": lattice.logrank}
# PF4 re-freeze (PF4.22, PF4.23): the worst-powered unchanged condition is no longer a literal: the
# limits are the exact test's at q / M, so the worst-powered unchanged condition and its limit are
# recomputed from the stats file's Fisher reference (worst_unchanged below).
#: The flat family's interval level and alpha* under Fisher, ``1 - q x R / M`` and ``q x R / M`` with
#: the reference's R = 22 over M = 72, as the alpha* line prints them (``:.4%`` and ``:g``) and as the
#: interval-on-the-change line prints the level (three decimals at most).
INTERVAL_LEVEL_TEXT, ALPHA_STAR_TEXT, ON_CHANGE_LEVEL_TEXT = "98.4722", "0.0152778", "98.472"
#: The per-cell keys every method's JSON must carry as the design gives them.
ARM_KEYS = ("n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b", "delta")
#: Keys that belong to the layered report's tree; none may appear outside ``tree`` on the page.
#: (``bound`` is not among them: the page's ``view`` carries its own forest ``bound`` setting.)
TREE_ONLY_KEYS = ("omnibus", "fault_lines", "leaves")

#: Synthetic vocabularies. Non-events end at the horizon; events end at ``EVENT_T``.
NON_EVENTS = frozenset({"ok", "z"})
EVENT_T = 2.0
HORIZON = 5.0
SALT, OTHER_SALT = "s25-salt", "s25-other-salt"


# ---------- data builders: construction only, no assertions and no decisions ----------


def tree() -> Any:
    """``proofload.tree``, imported at call time (see the module docstring)."""
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
    in its dict. **C49 (P-1 section 7.3), fixed in the P-1 freeze's update.** The old
    ``1000 * index + k`` seeded by dict position and ``replicate_index`` counted from
    ``replicate_start``, so O21's pair stored a different seed at the same
    ``(config_hash, replicate_index)`` in its two arms -- 16 of 48 matched rows disagreed, measured
    at ``a626cd3`` -- while ``mcnemar_bh`` ran on it. Green before and after on the bare tree
    (nothing reads a stored seed there), so its green is not evidence."""
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
    """Spec section 6: every cell present twice, the second copy with its arms exchanged, every
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
    runs sharing a salt) now reaches the CLI's stderr as one ``note:`` line (spec section 5.4)."""
    return "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))


def rule_10_p(p: float) -> str:
    """A p-value or q as the command line prints it (spec section 5.4, rule 10): three decimals,
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


def bh_over(values: Any) -> list[float]:
    """``lattice.bh`` (BH written out, independent of ``diff.bh``) over a column of p values."""
    return [float(v) for v in lattice.bh(list(values))]


def assert_q_column_is_bh_over_its_p_column(result: Any, reference: Mapping[str, Mapping[str, Mapping[str, Any]]] | None, events: tuple[str, ...]) -> None:
    """What a q-column digest guarded, as facts: the family covers ``events`` in that order, one
    row per condition of the design each, in sorted-hash order (the order the digest read); its q
    values, in that order, equal BH over its p values exactly (one family over every event); and
    where ``reference`` (per event, per condition) holds an independent p, each p equals it exactly
    and each q equals BH over the reference's p column exactly."""
    assert tuple(result.events) == events and result.n_tests == len(events) * lattice.CELLS, (result.events, result.n_tests)
    order = sorted(lattice.config_hash(c.config) for c in lattice.design_cells())
    for event in result.events:
        assert list(result.by_event[event].cells["config_hash"]) == order, event
    ps = [float(v) for e in result.events for v in result.by_event[e].cells["p"]]
    qs = [float(v) for e in result.events for v in result.by_event[e].cells["q"]]
    assert len(ps) == result.n_tests
    assert qs == bh_over(ps)
    if reference is not None:
        ref_p = [reference[e][h]["p"] for e in result.events for h in result.by_event[e].cells["config_hash"]]
        assert ps == ref_p
        assert qs == bh_over(ref_p)


def assert_delta_column_is_the_naive_difference(result: Any, events: tuple[str, ...]) -> None:
    """What the delta-column digest guarded: the family covers ``events`` in that order, each in
    sorted-hash order; every row's delta is ``events_b/n_b - events_a/n_a`` exactly, with the
    reference's sign of zero (the digest printed ``-0`` apart from ``0``), and its counts and delta
    are the design's (``lattice.fisher``'s)."""
    assert tuple(result.events) == events and result.n_tests == len(events) * lattice.CELLS, (result.events, result.n_tests)
    for event in result.events:
        reference = lattice.fisher(event)
        cells = result.by_event[event].cells
        assert list(cells["config_hash"]) == sorted(reference), event
        for row in cells.itertuples(index=False):
            ref = reference[row.config_hash]
            assert (row.n_a, row.n_b, row.events_a, row.events_b) == (ref["n_a"], ref["n_b"], ref["events_a"], ref["events_b"]), (event, row.config_hash)
            assert row.delta == row.events_b / row.n_b - row.events_a / row.n_a == ref["delta"], (event, row.config_hash)
            assert math.copysign(1.0, row.delta) == math.copysign(1.0, ref["delta"]), (event, row.config_hash, row.delta)


def assert_coverage_is_the_design(result: Any) -> None:
    """What the coverage digest guarded, as facts: ``coverage.to_json(orient="records")``, the
    string the digest hashed, is the one the design gives -- one record per condition in
    sorted-hash order, each with its own condition, every row of both runs present and holding an
    outcome, every condition comparable with no cause -- with its columns in order and its
    integers, booleans and nulls typed as written."""
    design = {lattice.config_hash(c.config): c.config for c in lattice.design_cells()}
    assert len(result.coverage) == len(design) == lattice.CELLS
    expected = [
        {"config_hash": h, "config": design[h], "rows_a": lattice.N, "rows_b": lattice.N, "no_outcome_a": 0,
         "no_outcome_b": 0, "comparable": True, "cause": None}
        for h in sorted(design)
    ]
    assert result.coverage.to_json(orient="records") == json.dumps(expected, separators=(",", ":"))


def assert_logrank_column_is_the_reference(result: Any) -> None:
    """The log-rank family (one event, the design's conditions in sorted-hash order) has its q
    column BH over its p column exactly, and each condition's p, q and direction are the
    independent log-rank reference's (``lattice.logrank``: lifelines on the stored times, BH
    written out) to 1e-12 relative."""
    assert_q_column_is_bh_over_its_p_column(result, None, (EVENT,))
    reference = lattice.logrank(EVENT)
    cells = result.by_event[EVENT].cells
    assert set(cells["config_hash"]) == set(reference)
    for row in cells.itertuples(index=False):
        assert row.p == pytest.approx(reference[row.config_hash]["p"], rel=1e-12, abs=0), row.config_hash
        assert row.q == pytest.approx(reference[row.config_hash]["q"], rel=1e-12, abs=0), row.config_hash
        assert row.direction == reference[row.config_hash]["direction"], row.config_hash


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def enclosing_functions(module: ast.Module) -> dict[ast.AST, str]:
    """Every node mapped to the name of the ``def`` it sits inside, for O16."""
    out: dict[ast.AST, str] = {}

    def walk(node: ast.AST, name: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else name
            if inner is not None:
                out[child] = inner
            walk(child, inner)

    walk(module, None)
    return out


def called_name(node: ast.Call) -> str | None:
    func = node.func
    return func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)


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


def structure_as_ids_named_it(structure: dict[str, Any], events: str) -> dict[str, Any]:
    """PF2 (spec section 4.3): ``serve --json`` on the lattice moves in two places only: ``run_name`` beside
    each arm's ``run_id``, and the default title, which names the runs by name (``view.title`` and
    the figure's title line). First assert each is there as PF2 writes it and nowhere else the
    digest reads, then put the structure back as it was before names (no ``run_name``, the title by
    id) so the frozen digest still guards everything else."""
    arms = {}
    for role, run_id, name in (("a", RUN_A, NAME_A), ("b", RUN_B, NAME_B)):
        arm = structure["pair"][role]
        keys = list(arm)
        assert (arm["run_id"], arm.get("run_name")) == (run_id, name), arm
        assert keys.index("run_name") == keys.index("run_id") + 1, keys
        arms[role] = {k: v for k, v in arm.items() if k != "run_name"}
    named, by_id = f"{NAME_A} vs {NAME_B}: {events}", f"{RUN_A} vs {RUN_B}: {events}"
    assert structure["view"]["title"] == named, structure["view"]["title"]
    line = f'font-size="13">{named}</text>'
    assert structure["heatmap_svg"].count(line) == 1, structure["heatmap_svg"][:600]
    return {
        **structure,
        "pair": {**structure["pair"], **arms},
        "view": {**structure["view"], "title": by_id},
        "heatmap_svg": structure["heatmap_svg"].replace(line, f'font-size="13">{by_id}</text>'),
    }


def structure_as_0_0_1_wrote_it(structure: dict[str, Any]) -> dict[str, Any]:
    """PF0 (Q4, section 2.3): the rename moves one key of the page structure, the version, in both
    arms (``poisson_prove_version``) and in the provenance block, whose value also says when the runs
    were written by 0.0.1. First assert the new key is there and the old one is not, then put both
    back as 0.0.1 wrote them before the frozen digest is taken, so the digest still guards everything
    else."""
    for arm in ("a", "b"):
        assert "poisson_prove_version" in structure["pair"][arm] and "proofload_version" not in structure["pair"][arm], arm
    assert "poisson_prove_version" in structure["diff"] and "proofload_version" not in structure["diff"]
    arms = {
        arm: {("proofload_version" if key == "poisson_prove_version" else key): value for key, value in structure["pair"][arm].items()}
        for arm in ("a", "b")
    }
    diff = {key: value for key, value in structure["diff"].items() if key != "poisson_prove_version"}
    return {**structure, "pair": {**structure["pair"], **arms}, "diff": {**diff, "proofload_version": "0.0.1"}}


@pytest.mark.parametrize("method", METHODS)
def test_o1_location_is_the_mean_and_dispersion_the_rms_of_units_delta_on_the_lattice(
    lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """Spec section 0.1: the plan's unweighted sum and unweighted sum of squares, in mean and RMS
    form. Recomputed from ``units`` rather than read back. **The lattice's unequal rates are the catch**
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
    """Step zero item 4. The lattice's n is 32 everywhere, so an n-weighted mean equals the unweighted one
    there and only the variance-weighted mutant is caught. On the O22 fixture the cell sizes
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
    """**The packet's most important invariant.** ``omnibus`` rebuilds the cell view from the raw
    frames with ``diff.py``'s own helpers -- a second construction of something ``multi_diff``
    already built -- and this is the check that makes that safe. Section 8 trap 1: the rebuild
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
    """Section 8 trap 1's hardest case: the lattice cannot express truncation. Arm a's horizon is 5 and
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
    """Section 8 trap 4 is stated here and not fixed: ties are counted with ``>=``, since discrete
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
    comparing to ``0.05`` or to a constant in ``cli.py`` (section 8 trap 7)."""
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
    """Section 0.3 says why not across NumPy releases: NEP 19 reserves the right to move a
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
    """Draft ADR-057. The table is asserted against this file's literal and not only against
    itself: a builder whose table says ``arm_label`` for every method would otherwise agree with
    its own field. ``logrank_bh`` uses arm label and the same proportions as ``fisher_bh``, so on
    the lattice the two roots differ only in ``method`` (section 10)."""
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
    """ADR-052's twin, S24's C12 construction restated. ``moved-b`` and ``moved-b-unpaired`` hold
    identical episodes and differ only in ``run_salt``, so the two diffs below see the same frames
    and differ only in ``seed_identity_match`` (``paired`` until P-1). A root that dispatched on it would take pair swap on
    the first and arm label on the second, and the ``scheme`` field alone would separate the two
    payloads."""
    paired_multi, paired_root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=300, seed=GOLDEN_SEED)
    unpaired_multi, unpaired_root = store_root(synth_root, "moved-a", "moved-b-unpaired", events=("fail",), method="fisher_bh", n_permutations=300, seed=GOLDEN_SEED)
    assert paired_multi.seed_identity_match is True and unpaired_multi.seed_identity_match is False
    assert paired_root.n_informative_cells > 0
    assert json_bytes(paired_root) == json_bytes(unpaired_root)
    assert paired_root.scheme == "arm_label"


def test_o6_tree_never_names_paired() -> None:
    """**The rule, in prose.** The scheme is a function of ``method``; ``paired`` is provenance.
    No ``ast.Attribute`` with ``attr == "paired"`` and no ``ast.Name`` ``paired`` anywhere in
    ``tree.py``, so the module cannot even read the field it must not branch on."""
    offenders = [
        (node.lineno, type(node).__name__)
        for node in ast.walk(parsed(TREE_SOURCE))
        if (isinstance(node, ast.Attribute) and node.attr == "paired")
        or (isinstance(node, ast.Name) and node.id == "paired")
    ]
    assert offenders == [], offenders


# ---------- O7: degeneracy, counted ----------


@pytest.mark.parametrize("method", METHODS)
def test_o7_informative_cells_and_discordant_pairs_are_recomputed_from_the_frames_on_the_lattice(
    pair: Any, lattice_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """Spec section 0.5's operational definition, recomputed from the raw frames (the lattice has no
    errored or truncated row, so raw and rebuilt views coincide). Under ``pair_swap``: cells with
    at least one matched pair whose two outcomes differ, and the total of such pairs. Under
    ``arm_label``: cells whose pooled outcomes are not all identical, and ``None``. Step zero
    item 5: on the lattice the informative count (35 under either reading) differs from the count
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
    the observed statistic and ties count, section 8 trap 4), ``rejects`` is ``False``, and both
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
    """Step zero item 2, the half the spec got wrong. Under arm label a cell with mixed outcomes
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
    """Section 8 trap 2 seen from the count: a pair ``(z, y)`` is discordant even for event ``x``,
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
    observed one (section 8 trap 3). ``location`` is recomputed from ``cells.delta``, not typed.
    Bonferroni is computed and printed as section 8 trap 9 asks, and no order is asserted."""
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
    reads ``p_omnibus == 1.0`` on this fixture, measured in step zero under both schemes. The
    ladder's F3 -- half the cells break and half improve -- in fixture form. ``> 0.5`` rather
    than ``== 1.0`` because floating accumulation can leave ``location`` at ``1e-17`` and a
    permutation can tie it."""
    _, root = mirrored_lattice[method]
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    assert root.n_cells == 2 * lattice.CELLS == 144
    assert abs(root.location[EVENT]) < 1e-9
    assert root.p_location[EVENT] > 0.5
    assert root.p_dispersion[EVENT] == floor
    # PF4 (PF4.18): the omnibus now ranks every permutation on the observed point's scale, a
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
    result), then ``omnibus`` at ``B = 1000`` with seed ``1000 + k``. The spec as first written
    resampled with ``pair_swap`` under both methods, and a draw uniform on the pair-swap orbit is
    not invariant under the larger arm-label group, so the arm-label test on it is not exact by
    theorem; step zero measured that mismatch far outside the band and the matched construction
    inside it.

    **The band.** ``0.05 +- 1.96 * sqrt(0.05 * 0.95 / 200) = [0.0198, 0.0802]``, the 95% Monte
    Carlo band for a true rate of 0.05 at ``K = 200``, kept as the spec's literal
    ``[0.020, 0.080]``. Section 8 trap 12: if a NumPy bump moves the rate out of it, that is a
    Monte Carlo event to re-run with more ``K``, not a reason to loosen the band.

    **Above 0.080 catches anti-conservative wiring**: the exchange applied to per-event indicators
    rather than whole outcomes, labels permuted across cells rather than within, a p-value
    without the ``+ 1``, ties counted with ``>``, a rank-p that excludes the permutation itself,
    an uncalibrated minimum over the ``2K`` p-values.

    **The band catches the scheme mismatch** -- **sole catch** -- the scheme choice regressing to one
    scheme for both methods, which under ``mcnemar_bh`` is resampled here under pair swap and tested
    by the build under arm label (which side of the band it lands on is the fixture's; the
    planted-defect pass measures it).

    **Below 0.020 catches conservative wiring**: Bonferroni stacked on top of the calibrated
    min-p, the calibration applied twice, or ``p_omnibus`` compared against a halved ``q``. A
    stream re-seeded on every draw is *not* conservative: every permutation is the same draw, the
    p-value collapses to the floor whenever that one draw is less extreme than the observed
    statistic, and on the fixture these tests were first written against it read far above the band, not below it.

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
    """**Not a numbered invariant: the deterministic guard for an uncalibrated min-p.** Section
    0.1's ``p_omnibus`` counts the permutations whose own min-p reaches the observed one; the
    bare minimum over the ``2K`` p-values is what Westfall-Young exists to correct. On the fixture
    these tests were first written against that mutant read one resample above O10's ceiling, so
    O10 alone catches it with no margin. Here the relation is pinned instead. Writing ``c*`` for the count
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
    # ``p_floor`` is ``1 / (n_permutations + 1)`` (P-1), so it moves with ``n_permutations`` and is excluded beside it.
    assert without(few, (*P_DRIVEN_KEYS, "n_permutations", "p_floor")) == without(many, (*P_DRIVEN_KEYS, "n_permutations", "p_floor"))


# ---------- O12: multi-event ----------


@pytest.mark.parametrize("method", ("fisher_bh", "mcnemar_bh"))
def test_o12_only_the_moving_event_rejects_and_every_map_carries_both_events(
    three_outcome: Any, three_outcome_roots: dict[str, tuple[Any, Any]], method: str
) -> None:
    """Built by hand (section 6): ``x`` sits at the same replicates in both arms so it never
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
    """**Not a numbered invariant: section 6's own statement, and the catch for section 8 trap 2.**
    With a two-outcome vocabulary and both outcomes requested, every cell's two deltas are exact
    negatives under every whole-outcome exchange, so the four statistics are two pairs of
    duplicates and the p-values agree exactly. Exchanging per-event indicators independently is a
    different null under which a pair can be ``fail`` in both arms; the two events then ride
    different draws and their p-values part company. **The lattice cannot catch that**: its effect puts
    both events at the floor under any draw, and the shim's independent-exchange mutant passed
    there. The six-cell mid-range pair puts both p-values where two draws differ."""
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


def test_o13_the_cli_maps_a_refusal_to_exit_two_without_a_traceback(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--permutations", "0"])
    # A refusal exits 1 (spec section 5.2).
    assert code == 1, (out, err)
    assert "error:" in err and "Traceback" not in out + err, err


# ---------- O14: the flat family does not move ----------


def nested_keys(payload: Any) -> set[str]:
    """Every mapping key at any depth of a JSON payload."""
    if isinstance(payload, Mapping):
        return set(payload) | {k for v in payload.values() for k in nested_keys(v)}
    if isinstance(payload, list):
        return {k for v in payload for k in nested_keys(v)}
    return set()


def direction_word(n_lower: int, n_higher: int) -> str:
    """PF4.20's comparison word for an event of unknown kind when something moved."""
    return "mixed" if n_lower and n_higher else ("higher" if n_higher else "lower")


def mcnemar_reference(a: pd.DataFrame, b: pd.DataFrame, event: str) -> dict[str, float]:
    """PF4 (PF4.14): each cell's exact McNemar p from its matched pairs, by statsmodels' documented
    ``mcnemar(table, exact=True)`` with ``table = [[n11, n10], [n01, n00]]`` (rows: arm A with and
    without the event; columns: arm B); a cell with no discordant pair has p 1."""
    from statsmodels.stats.contingency_tables import mcnemar

    keys = ["config_hash", "replicate_index"]
    pairs = a[[*keys, "outcome"]].merge(b[[*keys, "outcome"]], on=keys, suffixes=("_a", "_b"))
    out: dict[str, float] = {}
    for cell_hash, group in pairs.groupby("config_hash"):
        ea = (group["outcome_a"] == event).to_numpy()
        eb = (group["outcome_b"] == event).to_numpy()
        table = [[int((ea & eb).sum()), int((ea & ~eb).sum())], [int((~ea & eb).sum()), int((~ea & ~eb).sum())]]
        discordant = table[0][1] + table[1][0]
        out[str(cell_hash)] = 1.0 if discordant == 0 else float(mcnemar(table, exact=True).pvalue)
    return out


#: PF4 re-freeze (PF4.22, PF4.48): limits are multiples of this grid step.
LIMIT_GRID_STEP = 1e-4


def is_null(value: Any) -> bool:
    """A null limit as JSON (None) or as the frame (NaN) carries it."""
    return value is None or (isinstance(value, float) and math.isnan(value))


@functools.cache
def reference_fisher_limits(events_a: int, n_a: int, n_b: int, level: float) -> tuple[float | None, float | None]:
    """PF4 re-freeze (PF4.23): the stats file's independent Fisher enumeration, rise then fall.
    Imported here, not at module level, so this file still collects where the stats file cannot."""
    from test_pf4_stats import _ref_fisher_limits

    return _ref_fisher_limits(events_a, n_a, n_b, level)


def reference_mde(events_a: int, n_a: int, n_b: int, level: float) -> float | None:
    """Section 8.10's ``mde`` rule over the reference's two limits: the larger of two numbers, the
    number beside a direction with no room, and null otherwise."""
    rise, fall = reference_fisher_limits(events_a, n_a, n_b, level)
    if rise is not None and fall is not None:
        return max(rise, fall)
    if rise is not None and events_a == 0:
        return rise
    if fall is not None and events_a == n_a:
        return fall
    return None


def assert_the_limits_follow_the_rule(cell: Mapping[str, Any], row: Mapping[str, Any], level: float, method: str) -> None:
    """PF4 re-freeze (PF4.22, PF4.23, PF4.27, section 8.10, Q54): the JSON carries the frame's limits;
    a baseline with the event in every run has no rise (``no room``) and its fall is computed; ``mde``
    follows section 8.10's rule, with a note when it is null, and a number is a positive grid value;
    under Fisher both limits are the stats file's reference at the lone-change level ``q / M``."""
    what = (method, cell["config_hash"])
    for key in ("mde", "mde_rise", "mde_fall"):
        assert is_null(cell[key]) == is_null(row[key]), (what, key)
        assert is_null(cell[key]) or cell[key] == row[key], (what, key)
    rise, fall = cell["mde_rise"], cell["mde_fall"]
    if cell["events_a"] == cell["n_a"]:
        assert is_null(rise) and cell["mde_rise_note"] == "no room", what
    if not is_null(rise) and not is_null(fall):
        want = max(rise, fall)
    elif not is_null(rise) and cell["mde_fall_note"] == "no room":
        want = rise
    elif not is_null(fall) and cell["mde_rise_note"] == "no room":
        want = fall
    else:
        want = None
    if want is None:
        assert is_null(cell["mde"]) and cell["mde_note"], (what, cell["mde"], cell["mde_note"])
    else:
        assert cell["mde"] == want and cell["mde"] >= LIMIT_GRID_STEP - 1e-12, (what, cell["mde"], want)
    if method == "fisher_bh":
        assert abs(cell["mde_level"] - level) <= 1e-15, what
        for got, ref in zip((rise, fall), reference_fisher_limits(cell["events_a"], cell["n_a"], cell["n_b"], level), strict=True):
            assert (ref is None and is_null(got)) or (ref is not None and not is_null(got) and abs(got - ref) <= LIMIT_GRID_STEP + 1e-12), (what, got, ref)


def worst_unchanged(multi: Any) -> tuple[set[str], int]:
    """PF4 re-freeze (PF4.22, PF4.23): the lattice's worst-powered unchanged condition under Fisher,
    from the stats file's reference: every unchanged condition whose recomputed ``mde`` is the
    largest (they may tie), written as the report writes a condition, and that limit in whole
    points."""
    level = multi.q / multi.n_tests
    limits = {}
    for row in multi.by_event[EVENT].cells.to_dict(orient="records"):
        if row["direction"] != "unchanged":
            continue
        value = reference_mde(int(row["events_a"]), int(row["n_a"]), int(row["n_b"]), level)
        if value is not None:
            limits[f"{lattice.X}={row['config'][lattice.X]:g}, {lattice.Y}={row['config'][lattice.Y]:g}"] = value
    worst = max(limits.values())
    return {where for where, value in limits.items() if abs(value - worst) <= LIMIT_GRID_STEP + 1e-12}, round(100 * worst)


def assert_lattice_multi_json_carries_the_facts(multi: Any, method: str, a: pd.DataFrame, b: pd.DataFrame) -> None:
    """PF4: the facts the ``to_json()`` digest guarded, with no digest over bytes PF4 changes.

    Every cell's counts, rates and delta equal the frame's and the design's (``lattice.counts``:
    each rate its count over 32, each delta the naive difference); p and q equal the frame's, and
    are the independent reference's (``REFERENCE_BY_METHOD``): exactly under Fisher and McNemar
    (scipy's Fisher test and exact binomial McNemar, one BH family), with the exact McNemar p also
    statsmodels' and its BH q statsmodels', and to 1e-12 relative under log-rank (lifelines on the stored
    times), whose q column is also BH over its p column exactly. A condition whose baseline had the
    event in every run has no rise and its fall computed, and every limit follows section 8.10's
    rule at ``q / M``, Fisher's recomputed from the stats file's reference (PF4.22, PF4.27). Each
    cell's JSON verdict is its direction (tripped has no kind, PF4.20) and the reference's; a cell
    moves exactly when it is rejected, in the direction of its delta except under log-rank (PF4.13);
    and the counts are the references' (``LATTICE_DIRECTION_COUNTS``)."""
    from statsmodels.stats.multitest import multipletests

    payload = json.loads(json.dumps(multi.to_json(), sort_keys=True))
    assert (payload["method"], payload["n_tests"], payload["events"]) == (method, lattice.CELLS, [EVENT]), method
    event = payload["by_event"][EVENT]
    n_lower, n_higher = LATTICE_DIRECTION_COUNTS[method]
    reference = REFERENCE_BY_METHOD[method](EVENT)
    assert lattice.directions(reference) == (n_lower, n_higher), method
    assert (event["kind"], event["n_safer"], event["n_worse"]) == (None, None, None), method
    assert (event["n_lower"], event["n_higher"], event["n_unchanged"]) == (n_lower, n_higher, lattice.CELLS - n_lower - n_higher), method
    rows = multi.by_event[EVENT].cells.to_dict(orient="records")
    assert [c["config_hash"] for c in event["cells"]] == [r["config_hash"] for r in rows], method
    assert set(reference) == {r["config_hash"] for r in rows}, method
    reference_p = mcnemar_reference(a, b, EVENT) if method == "mcnemar_bh" else {}
    for cell, row in zip(event["cells"], rows, strict=True):
        ref = reference[cell["config_hash"]]
        design = {**ref, "rate_a": ref["events_a"] / ref["n_a"], "rate_b": ref["events_b"] / ref["n_b"]}
        for key in ARM_KEYS:
            assert cell[key] == row[key] == design[key], (method, cell["config_hash"], key)
        assert (cell["p"], cell["q"]) == (row["p"], row["q"]), (method, cell["config_hash"])
        if method in ("fisher_bh", "mcnemar_bh"):
            assert (cell["p"], cell["q"]) == (ref["p"], ref["q"]), (method, cell["config_hash"])
        else:
            assert cell["p"] == pytest.approx(ref["p"], rel=1e-12, abs=0) and cell["q"] == pytest.approx(ref["q"], rel=1e-12, abs=0), cell["config_hash"]
        if method == "mcnemar_bh":
            assert abs(cell["p"] - reference_p[cell["config_hash"]]) <= 1e-12, (cell["config_hash"], cell["p"])
            assert cell["pairs"] == ref["n_a"] == ref["n_b"], cell["config_hash"]
        # PF4 re-freeze (PF4.22, PF4.23, PF4.27): each limit is the exact test's at q / M both ways,
        # a 100% baseline has its fall computed, and Fisher's are recomputed from the stats file's
        # reference.
        assert_the_limits_follow_the_rule(cell, row, multi.q / multi.n_tests, method)
        rejected = cell["q"] < multi.q
        assert cell["verdict"] == cell["direction"] == row["direction"] == ref["direction"], (method, cell["config_hash"])
        assert (cell["direction"] != "unchanged") == rejected, (method, cell["config_hash"])
        if rejected and method != "logrank_bh":
            assert cell["direction"] == ("higher" if cell["delta"] > 0 else "lower"), (method, cell["config_hash"])
    directions = [c["direction"] for c in event["cells"]]
    assert (directions.count("lower"), directions.count("higher")) == (n_lower, n_higher), method
    if method == "mcnemar_bh":
        bh = multipletests([reference_p[r["config_hash"]] for r in rows], method="fdr_bh")[1]
        assert max(abs(r["q"] - float(x)) for r, x in zip(rows, bh, strict=True)) <= 1e-12
    if method == "logrank_bh":
        assert_logrank_column_is_the_reference(multi)


def assert_e14_builder_carries_the_result(multi: Any, report: Any, receipt: Any) -> None:
    """PF4: the facts the E14 digests guarded in the tree-less builder's report.md, receipt and
    heatmap: each file's one version entry; the headline counts in direction words (tripped has no
    kind, PF4.20) at the Fisher reference's 22 lower / 0 higher; the worst-powered unchanged condition and
    its limit, recomputed; the interval level and alpha*; no layered block (the root reaches no other
    verb); and every row of the cell table is a cell of the diff with its counts, rates, p, q and
    direction."""
    md, html, svg = report.to_markdown(), receipt.to_html(), report.to_svg()
    as_0_0_1_wrote_it(md)
    as_0_0_1_wrote_it(html)
    tripped = multi.by_event[EVENT]
    cells = tripped.cells
    n_lower, n_higher = LATTICE_DIRECTION_COUNTS["fisher_bh"]
    assert lattice.directions(lattice.fisher(EVENT)) == (n_lower, n_higher)
    assert (tripped.n_lower, tripped.n_higher) == (n_lower, n_higher)
    headline = f"{EVENT}: {n_lower} lower, {n_higher} higher"
    md_lines = md.splitlines()
    assert headline in md_lines and f"## {headline}" in md_lines, md_lines[:12]
    assert f"<h2>{headline}</h2>" in html
    assert f">{headline}</text>" in svg
    # PF4 re-freeze (PF4.22, PF4.23): the worst-powered unchanged condition and its limit are
    # recomputed from the stats file's reference (should they tie, the line names one of them).
    wheres, points = worst_unchanged(multi)
    assert round(100 * tripped.max_mde_unchanged) == points
    for name, text in (("report.md", md), ("receipt.html", html), ("heatmap.svg", svg)):
        honesty = [line for line in text.splitlines() if "Worst-powered unchanged cell" in line]
        assert honesty and any(f"({where}," in honesty[0] for where in wheres) and f"{points}pp" in honesty[0], (name, honesty)
        assert "safer" not in text and "worse" not in text, name
    # PF4 re-freeze (PF4.42): the verdict's section adds its own "intervals: " line, the interval on
    # the change at the same level; the line that names alpha* is the one this pinned.
    # The level and alpha* are the reference's: 1 - q x R / M and q x R / M with R the Fisher
    # reference's flagged count, rendered as the alpha* line (:.4% and :g) and the interval-on-the-
    # change line (three decimals at most) print them.
    rejected = sum(lattice.directions(lattice.fisher(EVENT)))
    level, alpha_star = 1.0 - multi.q * rejected / multi.n_tests, multi.q * rejected / multi.n_tests
    assert (f"{level:.4%}", f"{alpha_star:g}") == (f"{INTERVAL_LEVEL_TEXT}%", ALPHA_STAR_TEXT)
    assert f"{level * 100:.3f}".rstrip("0").rstrip(".") == ON_CHANGE_LEVEL_TEXT
    (intervals,) = [line for line in md_lines if line.startswith("intervals: ") and "alpha*" in line]
    assert INTERVAL_LEVEL_TEXT in intervals and ALPHA_STAR_TEXT in intervals, intervals
    (on_change,) = [line for line in md_lines if line.startswith("intervals: ") and "alpha*" not in line]
    assert f"{ON_CHANGE_LEVEL_TEXT}%" in on_change and "miettinen-nurminen" in on_change.lower().replace("–", "-"), on_change
    for name, text in (("report.md", md), ("receipt.html", html)):
        assert "omnibus" not in text.lower() and "fault lines" not in text.lower(), name
    first = next(i for i, line in enumerate(md_lines) if line.startswith(f"| {lattice.X} |"))
    table = []
    for line in md_lines[first:]:
        if not line.startswith("|"):
            break
        table.append([c.strip() for c in line.strip("|").split("|")])
    header, rows = table[0], [row for row in table[2:]]
    assert header[:9] == [lattice.X, lattice.Y, "n (a/b)", "rate_a (pp)", "rate_b (pp)", "delta (pp)", "p", "q", "verdict"], header
    assert rows
    records = cells.to_dict(orient="records")
    for values in rows:
        row = dict(zip(header, values, strict=True))
        (cell,) = [c for c in records if c["config"] == {lattice.X: float(row[lattice.X]), lattice.Y: float(row[lattice.Y])}]
        assert row["n (a/b)"] == f"{cell['n_a']}/{cell['n_b']}", row
        for column, key in (("rate_a (pp)", "rate_a"), ("rate_b (pp)", "rate_b"), ("delta (pp)", "delta")):
            assert abs(float(row[column]) - 100 * cell[key]) <= 0.05 + 1e-9, (row, column)
        for column in ("p", "q"):
            decimals = len(row[column].partition(".")[2])
            assert abs(float(row[column]) - cell[column]) <= 0.5 * 10.0**-decimals + 1e-12, (row, column)
        assert row["verdict"] == cell["direction"], row


def assert_lattice_page_carries_the_diff(structure: Mapping[str, Any], multi: Any, ma: RunManifest, mb: RunManifest, rows: tuple[int, int]) -> None:
    """PF4: the facts the serve structure digest guarded, on the page minus its tree: both arms
    from their manifests (no store path, platform or import path, PF4.11); the diff's parameters;
    one panel whose counts are the references' and whose 72 cells carry the diff's numbers with
    their direction (PF4.20) and limit (PF4.15); the worst-powered unchanged condition; the
    Summary's comparison word, decided by PF4.20 from those counts; the headline; and no key of the
    layered tree outside ``tree``."""
    assert "store_root" not in structure["pair"]
    for arm, manifest, n_rows in (("a", ma, rows[0]), ("b", mb, rows[1])):
        side = structure["pair"][arm]
        assert (side["run_id"], side["target_id"], side["run_salt"], side["t_unit"]) == (
            manifest.run_id, manifest.target_id, manifest.run_salt, manifest.t_unit,
        ), arm
        assert side["axis_types"] == dict(manifest.axis_types) and side["rows_stored"] == n_rows, arm
        assert not {"platform", "import_path"} & set(side["environment"]), arm
    diff = structure["diff"]
    assert (diff["method"], diff["n_tests"], diff["q"], diff["horizon"], diff["events"]) == (multi.method, multi.n_tests, multi.q, multi.horizon, [EVENT])
    (panel,) = structure["panels"]
    n_lower, n_higher = LATTICE_DIRECTION_COUNTS[multi.method]
    assert lattice.directions(REFERENCE_BY_METHOD[multi.method](EVENT)) == (n_lower, n_higher)
    assert (panel["event"], panel["kind"], panel["n_safer"], panel["n_worse"]) == (EVENT, None, None, None)
    assert (panel["n_lower"], panel["n_higher"], panel["n_unchanged"]) == (n_lower, n_higher, multi.n_tests - n_lower - n_higher)
    by_hash = {r["config_hash"]: r for r in multi.by_event[EVENT].cells.to_dict(orient="records")}
    assert len(panel["cells"]) == len(by_hash) == multi.n_tests
    assert {c["config_hash"] for c in panel["cells"]} == set(by_hash)
    for cell in panel["cells"]:
        row = by_hash[cell["config_hash"]]
        for key in ("n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b", "delta", "p", "q"):
            assert cell[key] == row[key], (cell["config_hash"], key)
        assert cell["verdict"] == cell["direction"] == row["direction"], cell["config_hash"]
        # PF4 re-freeze (PF4.27, Q54): a 100% baseline's limit is its fall, and a null limit is
        # null on the page with its note, as in the diff.
        assert is_null(cell["mde"]) == is_null(row["mde"]), cell["config_hash"]
        assert (is_null(row["mde"]) and cell["mde_note"]) or cell["mde"] == row["mde"], cell["config_hash"]
    # PF4 re-freeze (PF4.22, PF4.23): the worst-powered unchanged condition, recomputed.
    wheres, points = worst_unchanged(multi)
    assert panel["mde_unchanged"]["where"] in wheres and round(100 * panel["mde_unchanged"]["value"]) == points
    assert structure["summary"]["verdict"] == direction_word(n_lower, n_higher)
    assert structure["headline"] == multi.headline()
    assert not set(TREE_ONLY_KEYS) & nested_keys({k: v for k, v in structure.items() if k != "tree"})


@pytest.mark.parametrize("method", METHODS)
def test_o14_multi_diff_on_the_lattice_is_byte_identical_to_the_bare_tree(pair: Any, lattice_trees: Any, method: str) -> None:
    """``multi_diff``'s whole ``to_json()`` under each method, digested on the bare tree at
    cd5f177. The root consumes ``MultiDiffResult``; it does not touch it. Built here from the
    frames rather than taken from the root fixture, so it passes on the bare tree and pins the
    flat family whether or not ``tree.py`` exists."""
    a, b, _, _ = pair
    multi = lattice_trees.multi((EVENT,), method)
    # PF4 (PF4.3, PF4.13 to PF4.15, PF4.20): the digest is replaced by the facts it guarded, each
    # checked against a value known outside the build (the lattice's references and their counts).
    assert_lattice_multi_json_carries_the_facts(multi, method, a, b)


def test_o14_the_s24_column_digests_and_the_coverage_digest_are_unchanged(lattice_trees: Any) -> None:
    """S24's ``q``/``delta`` column digests and S21's coverage digest, restated rather than
    imported so two frozen test files do not share a helper."""
    both = lattice_trees.multi((EVENT, OTHER), "fisher_bh")
    logrank = lattice_trees.multi((EVENT,), "logrank_bh")
    # The four digests are replaced by the facts they guarded (S24's C15 and S21's coverage,
    # restated): each q column is BH over its p column and the references' exactly (Fisher) or to
    # 1e-12 (log-rank); the delta column is the naive difference of the design's counts; the
    # coverage frame is the design, condition for condition.
    assert_q_column_is_bh_over_its_p_column(both, {e: lattice.fisher(e) for e in both.events}, (EVENT, OTHER))
    assert_delta_column_is_the_naive_difference(both, (EVENT, OTHER))
    assert_logrank_column_is_the_reference(logrank)
    assert_coverage_is_the_design(both)


def as_0_0_1_wrote_it(text: str) -> str:
    """PF0 (Q4, section 2.3): the one field the rename changes in a rendered report, receipt or page
    is the version in its provenance list. First assert it is there as the rename writes it -- one
    ``Prove version:`` entry and no ``proofload version:`` -- then put it back as 0.0.1 wrote it and
    drop any separate ``written by proofload`` entry, so the frozen digest still guards every other
    byte."""
    found = re.findall(r"(?m)^- Prove version: [^\n]*$", text) + re.findall(r"<li>Prove version: [^<]*</li>", text)
    assert len(found) == 1 and "proofload version:" not in text, found
    text = re.sub(r"(?m)^- Prove version: [^\n]*$", "- proofload version: 0.0.1", text)
    text = re.sub(r"<li>Prove version: [^<]*</li>", "<li>proofload version: 0.0.1</li>", text)
    text = re.sub(r"(?m)^- [^\n]*written by proofload[^\n]*\n", "", text)
    return re.sub(r"<li>[^<]*written by proofload[^<]*</li>", "", text)


def e14_builder(pair: Any) -> tuple[Any, Any, Any]:
    """The E14 argv's ``multi`` and spec, rendered by the M7 builder with no tree, the way
    ``_report_pair`` builds them: the multi, the dark-theme report and the light-theme receipt."""
    a, b, ma, mb = pair
    multi = quiet_multi_diff(a, b, ma, mb, events=(EVENT,), method="fisher_bh")
    title = f"{RUN_A} vs {RUN_B}: {EVENT}"
    report = build_multi_report(
        multi, ReportSpec(title=title, x_axis=lattice.X, y_axis=lattice.Y), manifests=(ma, mb)
    )
    receipt = build_multi_report(
        multi, ReportSpec(title=title, x_axis=lattice.X, y_axis=lattice.Y, theme="light"),
        manifests=(ma, mb),
    )
    return multi, report, receipt


def assert_cli_heatmap_is_the_builders_under_rule_10(cli_svg: str, builder_svg: str, cells: pd.DataFrame) -> None:
    """The command line's ``heatmap.svg`` against the builder's, whose bytes keep the frozen digest.

    Rule 10 (spec section 5.4) reformats only the text in the file, so every element and attribute
    is the builder's. Each cell's label is its delta to three decimals, read from ``cells``; a text
    the builder prints as a percentage-point number is that number as a fraction; every other text
    that changed keeps its ``key=value`` facts and its counts; and the notes the builder writes in
    percentage points carry the worst-powered MDEs to three decimals.
    """
    def bare(svg: str) -> str:
        return re.sub(r">[^<]*<", "><", svg)

    assert bare(cli_svg) == bare(builder_svg)
    ids = re.findall(r'data-cell="([0-9a-f]+)"', cli_svg)
    label_group = cli_svg.split('<g fill="#E6E6E6" font-size="9" text-anchor="middle">', 1)[1].split("</g>", 1)[0]
    labels = re.findall(r">([^<]*)</text>", label_group)
    delta = dict(zip(cells["config_hash"], cells["delta"]))
    assert len(ids) == len(labels) == len(delta), (len(ids), len(labels), len(delta))
    for short, label in zip(ids, labels):
        (full,) = [h for h in delta if h.startswith(short)]
        assert label == f"{delta[full]:.3f}", (short, label, delta[full])
    number = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")
    texts = list(zip(re.findall(r">([^<]*)</text>", builder_svg), re.findall(r">([^<]*)</text>", cli_svg)))
    for old, new in texts:
        if old == new:
            continue
        if number.fullmatch(old):
            assert number.fullmatch(new) and abs(float(new) - float(old) / 100) <= 1e-3, (old, new)
            continue
        for fact in re.findall(r"\w+=[^\s,;)]+", old):
            assert fact in new, (fact, new)
        for count in re.findall(r"(?<![\d.])\d+(?![\d.%]|pp)", old):
            assert f"{int(count):,}" in new, (count, new)
    notes = [new for old, new in texts if re.search(r"\d+pp", old)]
    assert notes, texts
    for mde in (cells["mde"].max(), cells.loc[cells["verdict"] == "unchanged", "mde"].max()):
        assert any(f"{mde:.3f}" in note for note in notes), (mde, notes)


def test_o14_and_o23_the_lattice_report_still_reproduces_the_three_digests_s21_minted(pair: Any, tmp_path: Path) -> None:
    """E14's three digests, restated. ``report`` renders through ``MultiDiffResult`` and the root
    reaches no other verb (O23); if a byte leaks into ``to_markdown``, the receipt or the heatmap,
    one of these three moves.

    Narrowed for S28 (draft ADR-074, spec S28 section 3.8): ``report`` on a pair now renders the
    layered report into ``report.md`` and ``receipt.html``, so those two files through the CLI
    are S28's to pin. The surface S21 owned is the tree-less M7 builder, which reproduces both
    digests bit for bit (S28 section 0.2), so the two markdown and HTML pins move to
    ``build_multi_report(multi, spec, manifests=...)`` with no tree; ``heatmap.svg`` never
    changes (S28 section 3.3) and stays pinned through the CLI. Narrowed, not deleted.

    Moved for rule 10 (spec section 5.4): the command line now prints the heatmap's text as
    fractions, so its digest moves to the builder's heatmap, and the file the command line writes
    is checked against that one fact by fact."""
    out = tmp_path / "report"
    code, text, _ = run_cli(["--store", str(LATTICE_ROOT), *E14_ARGV, "--out", str(out)])
    assert code == 0, text
    # PF4 (PF4.3, PF4.15, PF4.20): the three digests are replaced by the facts they guarded.
    multi, report, receipt = e14_builder(pair)
    assert_e14_builder_carries_the_result(multi, report, receipt)
    # The command line's heatmap is the builder's with its text under rule 10 (spec section 5.4),
    # checked by its facts rather than a new digest.
    assert_cli_heatmap_is_the_builders_under_rule_10(
        (out / "heatmap.svg").read_text(encoding="utf-8"), report.to_svg(), multi.by_event[EVENT].cells
    )


def test_o14_and_o23_check_on_the_lattice_prints_the_same_bytes_and_exits_the_same(lattice_trees: Any) -> None:
    """``check`` keeps the flat family's gate (section 5); whether the root should gate is
    P4.4's question. Stdout digest and exit code from the bare tree.

    Moved for the command line's look (front-door spec sections 5.3 and 14): the verdict line now
    comes first and the stdout digest is replaced by the facts it guarded: the check passed, it
    names the gated event, the flat family's counts and its size."""
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), *CHECK_ARGV])
    # The lattice's two runs share a salt, so stderr now carries one note line (spec section 5.4).
    assert code == CHECK_EXIT and without_notes(err) == "", (out, err)
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    verdicts = multi.by_event[EVENT].cells["verdict"]
    first = out.splitlines()[0]
    assert first.startswith("passed  ") and EVENT in first, out
    # PF4 (PF4.20): tripped has no kind, so the counts read in direction words; the 22 and 0 are the
    # Fisher reference's (LATTICE_DIRECTION_COUNTS).
    # PF4 re-freeze (PF4.20, no split between the library and the screen): the library's verdict
    # column holds the direction words too, where it held safer and worse.
    n_lower, n_higher = int((verdicts == "lower").sum()), int((verdicts == "higher").sum())
    assert (n_lower, n_higher) == LATTICE_DIRECTION_COUNTS["fisher_bh"] == lattice.directions(lattice.fisher(EVENT))
    assert f"{n_lower:,} lower, {n_higher:,} higher" in out, out
    assert f"{multi.n_tests:,} tests" in out, out
    # PF4 re-freeze (PF4.34, PF4.40, reading R34): check's block names the comparison's own word on
    # its comparison line, read from Holm's rows.
    holm = multi.to_json()["by_event"][EVENT]
    (comparison,) = [line for line in out.splitlines() if line.startswith("  comparison  ")]
    assert comparison.split()[1] == direction_word(holm["n_holm_lower"], holm["n_holm_higher"]), comparison


def test_o23_serve_json_on_the_lattice_prints_the_same_structure(lattice_trees: Any) -> None:
    """Narrowed for S29 (spec S29 section 3.7, draft ADR-074): ``serve`` now computes M14's tree
    and ``proofload.viewpair/3`` carries it under one new top-level key, ``tree``. The surface
    S25 owned is everything else: the structure with ``tree`` removed and ``schema`` set back to
    the ``/2`` literal, ``pair.store_root`` normalised as before, digests to the value minted on
    the bare tree. Narrowed, not deleted."""
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), *SERVE_ARGV])
    # The lattice's two runs share a salt, so stderr now carries one note line (spec section 5.4).
    assert code == 0 and without_notes(err) == "", err
    # serve --json now leads with a verdict and a sentence beside the structure (spec section 5.6).
    # PF3 (spec section 4.4, PF3.6b; rule R3): serve --json now names the method at the top level after the
    # sentence; dropped beside the verdict and the sentence.
    structure = {k: v for k, v in json.loads(out).items() if k not in ("verdict", "sentence", "method", "method_chosen")}
    # PF4 (PF4.11, section 8.5): the page no longer carries the store path at all.
    assert "store_root" not in structure["pair"]
    # PF2 (spec section 4.3): run_name beside each arm's run_id and the title by name are asserted,
    # then put back as before names.
    structure = structure_as_ids_named_it(structure, EVENT)
    # PF0's version-field check still holds on the page.
    structure_as_0_0_1_wrote_it(structure)
    # PF4 (PF4.3, PF4.11, PF4.17, PF4.20): the digest is replaced by the facts it guarded; the tree
    # still travels under its own key only.
    assert "tree" in structure
    ga, gb, gma, gmb = lattice_trees.frames()
    page_multi = lattice_trees.multi((EVENT,), "fisher_bh")
    assert len(ga) == len(gb) == lattice.ROWS
    assert_lattice_page_carries_the_diff(structure, page_multi, gma, gmb, (len(ga), len(gb)))


# ---------- O16: one construction of the stream ----------


def test_o16_default_rng_is_called_in_exactly_one_function_and_it_lives_in_tree_py() -> None:
    """**The rule, in prose.** Draft ADR-058, widened 2026-09-22 (PR-2 build): one
    seeded stream per estimator, each constructed in one function and never stored. The tree's
    permutation stream is built in ``tree.py``'s ``_draw`` and P4.2 obtains the same draws by
    calling that function; the paired replay's item-clustered bootstrap is built in
    ``paired.py``'s ``_cluster_bootstrap`` from the declared ``bootstrap_seed`` (Prove -- Spec PR
    Paired Replay, PR29). A ``default_rng`` anywhere else in the package is a second stream free
    to disagree with one of these, which is the ADR-021 shape this project has shipped twice, and
    the two named sites are the whole of the allowance. Legacy NumPy RNG entry points --
    ``np.random.seed``, ``RandomState``, any ``np.random.<fn>`` other than ``default_rng`` -- are
    global state and are forbidden everywhere in ``src/``. *Updated, ruled 2026-09-22: this test
    read "exactly one site, in tree.py" from ``5143c8d`` until the paired bootstrap landed; the
    name is kept so the row in the S25 frozen-test map still resolves.*"""
    sites: list[tuple[str, int, str]] = []
    legacy: list[tuple[str, int, str]] = []
    for path in sorted(PACKAGE.rglob("*.py")):  # PF5 (spec section 17): the core is a package now, so the scan reads src/ recursively.
        module = parsed(path)
        enclosing = enclosing_functions(module)
        for node in ast.walk(module):
            if isinstance(node, ast.Call):
                name = called_name(node)
                if name == "default_rng":
                    sites.append((path.name, node.lineno, enclosing.get(node, "<module>")))
                elif (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "random"
                ):
                    legacy.append((path.name, node.lineno, f"np.random.{name}"))
            if (isinstance(node, ast.Attribute) and node.attr == "RandomState") or (
                isinstance(node, ast.Name) and node.id == "RandomState"
            ):
                legacy.append((path.name, node.lineno, "RandomState"))
    assert sorted((path, function) for path, _, function in sites) == [
        ("paired.py", "_cluster_bootstrap"),
        ("tree.py", "_draw"),
    ], sites
    assert legacy == [], legacy


@pytest.mark.parametrize("name", ("tree.py", "diff.py"))
def test_o16_the_statistics_modules_use_no_stdlib_random_and_no_secrets(name: str) -> None:
    """Scoped to the two statistics modules (step zero item 3): ``capture.py:433`` already holds a
    ``random.Random(os.urandom(32))`` for something that is not a permutation stream, and naming
    that site beats widening the guard until it forbids what exists. In ``tree.py`` and
    ``diff.py`` there is no ``random``, no ``secrets``, no ``Random``."""
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(parsed(PACKAGE / name)):
        if isinstance(node, ast.Import):
            offenders.extend((node.lineno, alias.name) for alias in node.names if alias.name.split(".")[0] in ("random", "secrets"))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in ("random", "secrets"):
            offenders.append((node.lineno, node.module))
        elif isinstance(node, ast.Attribute) and node.attr in ("Random", "seed") and isinstance(node.value, ast.Name) and node.value.id == "random":
            offenders.append((node.lineno, f"random.{node.attr}"))
        elif isinstance(node, ast.Name) and node.id == "Random":
            offenders.append((node.lineno, "Random"))
    assert offenders == [], offenders


# ---------- O17: the CLI does no arithmetic on any root field ----------


def test_o17_the_cli_does_no_arithmetic_on_any_root_field() -> None:
    """**The rule, in prose.** ``cli.py`` reads a field and prints it; it may ask whether one is
    ``None``; it may not do arithmetic on one. The complement on the informative line is exactly
    the arithmetic this forbids -- ``n_cells - n_informative_cells`` -- so the result must carry
    it, or the CLI must render it from a field. Any ``BinOp`` whose subtree names one of the
    thirteen fields fails. As the risk ledger records for C19, ``ast.walk`` of a ``BinOp``
    descends into joined f-strings; that is not narrowed here either."""
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(parsed(PACKAGE / "cli.py")):
        if not isinstance(node, ast.BinOp):
            continue
        mentioned = {
            child.attr if isinstance(child, ast.Attribute) else child.id
            for child in ast.walk(node)
            if isinstance(child, (ast.Attribute, ast.Name))
        }
        if mentioned & CLI_GUARDED_FIELDS:
            offenders.append((node.lineno, sorted(mentioned & CLI_GUARDED_FIELDS)[0]))
    assert offenders == [], offenders


# ---------- O18: the CLI block ----------


def test_o18_the_block_follows_the_interval_block_and_its_first_line_carries_the_fields(synth_root: Path) -> None:
    """Section 3.4, through ``main()`` with ``StringIO`` streams. The block is found by index and
    never by ``endswith``: a later packet may append after it. The first line's p, q, verdict,
    cell count and event count are captured and checked against the fields under rule 10."""
    multi, root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail"])
    assert code == 0, (out, err)
    # The pair shares a salt, so stderr now carries one note line (spec section 5.4).
    assert without_notes(err) == "", err
    assert out.index("intervals: ") < out.index("omnibus: "), out
    match = OMNIBUS_FIRST_LINE.search(out)
    assert match is not None, out
    verdict, p, sign, q, n_cells, n_events = match.groups()
    assert root.rejects is True
    assert (verdict, sign) == ("rejected", "<")
    # p and q print under rule 10 (spec section 5.4), not ``:g``.
    assert p == rule_10_p(root.p_omnibus) and q == rule_10_p(multi.q)
    assert int(n_cells) == root.n_cells and int(n_events) == len(root.events) == 1


def test_o18_the_other_branch_reads_not_rejected(synth_root: Path) -> None:
    _, root = store_root(synth_root, "same-a", "same-b", events=("fail",), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "same-a", "same-b", "--event", "fail"])
    # The pair shares a salt, so stderr now carries one note line (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (out, err)
    match = OMNIBUS_FIRST_LINE.search(out)
    assert match is not None, out
    assert root.rejects is False
    assert (match.group(1), match.group(3)) == ("not rejected", ">=")
    # p prints under rule 10 (spec section 5.4), not ``:g``.
    assert match.group(2) == rule_10_p(root.p_omnibus)


def test_o18_the_second_line_and_the_informative_line_carry_the_fields(synth_root: Path) -> None:
    """Every number on the block is a field the test reads back (section 0.4)."""
    _, root = store_root(synth_root, "moved-a", "moved-b", events=("fail",), method="fisher_bh", n_permutations=EXPECTED_DEFAULT_PERMUTATIONS, seed=EXPECTED_DEFAULT_SEED)
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the synthetic pair shares a salt, so the default is now the
    # paired test (scheme pair_swap); the root here is the unpaired test's, named.
    code, out, _ = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--method", "fisher_bh"])
    assert code == 0, out
    second = OMNIBUS_SECOND_LINE.search(out)
    assert second is not None, out
    # The permutation count carries separators (spec section 5.4, rule 10); the seed does not.
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
    # The pair shares a salt, so stderr now carries one note line (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (out, err)
    block = omnibus_block(out)
    locations = OMNIBUS_LOCATION_LINE.findall(block)
    dispersions = OMNIBUS_DISPERSION_LINE.findall(block)
    assert [e for e, _, _ in locations] == [e for e, _, _ in dispersions] == list(root.events) == ["x", "y"]
    # Deltas print to three decimals and p under rule 10 (spec section 5.4), not ``:g``.
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
    # --json replaces --format json (spec section 5.6); the shared salt adds one note line (5.4).
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the synthetic pair shares a salt, so the default is now the
    # paired test (scheme pair_swap); the root here is the unpaired test's, named.
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--json", "--permutations", "200", "--seed", "3", "--method", "fisher_bh"])
    assert code == 0 and without_notes(err) == "", (out, err)
    payload = json.loads(out)
    assert payload["omnibus"]["n_permutations"] == 200 and payload["omnibus"]["seed"] == 3
    assert payload["omnibus"] == json.loads(json.dumps(root.to_json()))
    for key in multi.to_json():
        assert key in payload, key


def test_o18_the_defaults_are_the_named_constants(synth_root: Path) -> None:
    # --json replaces --format json (spec section 5.6).
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
    """The plan's two prohibitions -- nothing shaped like "given the root passed", nothing in the
    "where it broke" vocabulary -- applied to the first rendered byte of the nested family. A
    root has no leaves and no groups, so neither sentence is natural here; the invariant exists
    so the rule is already in force when they arrive. ``headline()`` is one line and is pinned by
    this and O20, never by bytes (section 8 trap 11)."""
    for group in (lattice_roots, mirrored_lattice, identical_lattice, three_outcome_roots):
        for method, (_, root) in group.items():
            text = root.headline()
            assert "\n" not in text, (method, text)
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in text.lower(), (method, phrase, text)


def test_o19_the_cli_block_uses_none_of_the_forbidden_vocabulary(synth_root: Path) -> None:
    """On the block only, extracted by its own shape. The synthetic store's ``t_unit`` is
    ``steps``, so a block that printed the unit would trip ``step``; the spec's block does not
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
    """Section 0.0: the only null this packet tests is the sharp "no cell changed", quoted
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
    since the P-1 freeze's update (C49; ``seed_of``): before it 16 of 48 matched rows disagreed and
    ``mcnemar_bh`` ran on them anyway."""
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
    """Section 8 trap 5: ``arm_label`` permutes the ``n_a + n_b`` labels and assigns the first
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
