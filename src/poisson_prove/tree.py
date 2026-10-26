"""The dual root -- one permutation-calibrated omnibus over the cells x events family.

``H0`` is the sharp null **"no cell changed"**: for every comparable cell and every episode in
it, the outcome would have been the same under either arm. Under it, exchanging a matched
pair's two outcomes, or permuting the arm labels within a cell, produces a dataset with exactly
the same distribution as the observed one, so the permutation distribution of any statistic is
its exact null distribution. Ding, Feller & Miratrix's warning is about the *other* null -- "the
same shift everywhere", under which the shift is a nuisance parameter -- and that null is not
tested, named or printed here.

Two statistics per event ``k``, over the ``C`` comparable cells, with
``delta_ik = events_b/n_b - events_a/n_a``::

    location_k   = (1/C) * sum_i delta_ik            the mean per-cell movement, signed
    dispersion_k = sqrt( (1/C) * sum_i delta_ik^2 )  the root-mean-square per-cell movement

Both are **unweighted**, and both are monotone transforms of the plan's unweighted sum and
unweighted sum of squares at a fixed ``C``, so every permutation p-value below is the sum's.
Not a pooled-variance test and not Cochran's Q: ``Var(delta_i) = 2 p_i (1 - p_i) / N`` differs
across cells, and ``Q`` degenerates wherever ``p-hat`` is 0 or 1 -- 77% of cells in one
measured sweep.

Extremeness is ``|location_k|`` (two-sided) and ``dispersion_k`` (upper): a signed location
extremeness would be a one-sided test nobody asked for, and a signed dispersion is meaningless.
One set of ``B`` permutations yields all ``2K`` statistics; each gets a Phipson-Smyth p-value
``p = (1 + #{b : S_b >= S_obs}) / (B + 1)`` and the omnibus is Westfall-Young min-p over them.
**Ties are counted with ``>=``**: discrete outcomes tie constantly at N=32 and ``>`` would be
anti-conservative. That is deliberate and is not a defect to fix.

``diff.py`` does not know this module exists. ``omnibus`` consumes the
``MultiDiffResult`` it must agree with -- events, method, ``q``, the horizon and the common
cells are read from it and never re-decided -- plus the raw frames, from which it rebuilds the
cell view with ``diff.py``'s own helpers and refuses if the rebuild disagrees.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from poisson_prove import stats
from poisson_prove._limits import group_limit
from poisson_prove.diff import (
    DiffError,
    Method,
    MultiDiffResult,
    _native,
    _truncate_raw,
    bh,
)
from poisson_prove.executor import DEFAULT_MAX_MDE, _offered_override
from poisson_prove.store import RunManifest

Scheme = Literal["pair_swap", "arm_label"]

#: The scheme follows ``method`` and never the run salt: two
#: runs that happen to share a salt must get the same root as two that do not, or the omnibus
#: becomes a property of run provenance rather than of the request. Written once, read
#: everywhere; nothing below branches on anything else.
SCHEME_BY_METHOD: Mapping[str, Scheme] = {
    "mcnemar_bh": "pair_swap",
    "fisher_bh": "arm_label",
    "logrank_bh": "arm_label",
}

DEFAULT_PERMUTATIONS: int = 4000
DEFAULT_SEED: int = 0
ROOT_STATISTICS: tuple[str, ...] = ("location", "dispersion")
UNITS_COLUMNS: tuple[str, ...] = (
    "event",
    "config_hash",
    "config",
    "n_a",
    "n_b",
    "events_a",
    "events_b",
    "delta",
)

#: Outcome codes. ``_CENSORED`` is what ``_truncate_raw`` leaves behind at the horizon -- an
#: event of no kind -- and ``_PAD`` fills the ragged tail of a cell with fewer units than the
#: widest one. Neither can ever equal a requested event's code, so both count as "not this
#: event" in either arm and under every exchange.
_CENSORED = -1
_PAD = -2
_CODE_COLUMN = "_root_code"

#: The four columns of ``cells`` the rebuild must reproduce exactly, in this order. Everything
#: else on ``cells`` -- the rates, the Aalen-Johansen delta, the test statistic, p, q, the
#: verdict, the MDE -- belongs to the flat family and is none of the root's business.
_REBUILD_COLUMNS = ("n_a", "n_b", "events_a", "events_b")

#: The tag inside the agreement digest's hashed payload. Not a
#: compatibility promise and never a sibling key: it is ``/1`` so that a later
#: change to the canonical form is visible, and no consumer may compare digests across tags.
AGREEMENT_SCHEMA = "poisson-prove.agreement/1"


# ---------- the resolver's vocabulary ----------

#: The rungs the resolver walks, in order. A tuple and not a chain of ``if``s, with the trace
#: slot already in it, so a later grouping by kind lands by filling one function body and
#: moving no entry.
RUNG_ORDER: tuple[str, ...] = ("requested", "trace", "axis", "task_family", "whole_grid")

#: The names the trace rung owns. None in 0.1.0: a grouping by span kind is not
#: offered, so ``kind`` and ``step_kind`` are unknown groupings, refused with the supported list.
TRACE_GROUPINGS: tuple[str, ...] = ()

#: The task-family keys, in order. Read from the configs, not from ``axis_types``: the rung
#: exists for an imported run whose manifest declares fewer axes than its configs carry.
TASK_FAMILY_KEYS: tuple[str, ...] = ("task_family", "task_id", "task")

#: What ``--by`` types to ask for the whole grid; the key the resolved grouping reports.
WHOLE_GRID: str = "grid"
WHOLE_GRID_KEY: str = "whole_grid"
WHOLE_GRID_LABEL: str = "all"

#: Every reason a rung may give. A later release may add to this tuple; nothing branches on it.
REFUSAL_REASONS: tuple[str, ...] = ("unsupported", "underpowered", "one_group", "not_shared")

#: What is not tested, when the level was not tested. The root's reason wins over the level's
#: shape: the gate is evaluated before the grouping's cardinality and the more fundamental fact
#: is the one stated.
NOT_TESTED_REASONS: tuple[str, ...] = ("root_not_rejected", "one_group")

#: The null every group is tested against, quoted on the block exactly as the root's is.
GROUP_NULL: str = "no cell in the group changed"

#: One constant, two readers. The grouping gate and the sweep gate hold the
#: **same object**, so the two cannot drift apart; re-typing ``0.20`` here would be the second
#: site. It moves only through ``--max-group-mde``.
DEFAULT_MAX_GROUP_MDE: float = DEFAULT_MAX_MDE

#: Fewer than two groups that could each answer is one hypothesis dressed as a
#: family, and the whole-grid rung already offers one hypothesis.
MIN_RESOLVABLE_GROUPS: int = 2

#: The fewest groups that make Level 2 a family rather
#: than the root restated. One constant, three readers -- the resolver's one-group refusal in
#: ``_consider``, the gate in ``_fault_lines``, and the depth reduction in ``_depth`` -- where
#: the first two were once a literal ``< 2`` and ``> 1`` and the third would have
#: been a third site. Distinct from ``MIN_RESOLVABLE_GROUPS`` above, which is how many of a
#: grouping's groups must resolve the accepted effect for the grouping to be *admitted*: the
#: two are 2 for different reasons and move independently.
MIN_FAMILY_GROUPS: int = 2

#: A label sorts numerically only when every label in the grouping is a plain number. The
#: pattern is deliberately narrower than ``float()``: ``nan`` and ``inf`` parse and do not
#: order, so a grouping carrying one sorts lexically like any other set of names.
_NUMERIC_LABEL = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")


# ---------- Level 3, and the bound the tree controls at ----------

#: How many levels the procedure tests: ``2`` stops at the fault lines, ``3`` adds the cells
#: under each rejecting one. There is no ``1`` -- a one-level tree is ``omnibus`` and its
#: block, and a bound over a single hypothesis tested at ``q`` is a number that is true and
#: confuses.
DEFAULT_DEPTH: int = 3
DEPTHS: tuple[int, ...] = (2, 3)

#: Yekutieli (2008), *Hierarchical False Discovery Rate-Controlling Methodology*, JASA
#: 103(481):309-316, section 2.1.1: the smallest multiplicative factor satisfying his
#: inequality (1), which he computes as "slightly below 1.44" at a discovery count of four
#: under uniform p-values. A universal constant, chosen before any data and independent of the
#: tree's shape or of anything measured on it. Typed once, here, and read in one function.
DELTA_STAR: float = 1.44

#: The set the printed bound is over. Yekutieli's Corollary A.2 bounds the **outer-nodes**
#: error rate -- the discoveries that are not parents to other discoveries, which is exactly
#: what this report puts in front of a reader: the cells it names, the fault lines under which
#: it could name none, and the root when it could name nothing below. His other universal bound
#: is over the full tree, is depth-free and smaller, and is over a set padded with every
#: finding's ancestors; it is not printed. Carried on the structure so the JSON says which
#: error rate the number is.
BOUND_DISCOVERIES: str = "outer_nodes"

#: The null every leaf is tested against, quoted on the block exactly as the root's and the
#: group's are.
CELL_NULL: str = "this cell did not change"

#: Why Level 3 was not tested, the more fundamental fact first: the procedure's configuration
#: before the root, and the root before the level. The **first** that applies is the one
#: stated, which is the precedence of ``FaultLines.reason`` extended by one. Read in order by
#: ``_leaves_reason``; reordering this tuple reorders the
#: precedence, which is the point of stating it once.
LEAVES_NOT_TESTED_REASONS: tuple[str, ...] = ("depth", "root_not_rejected", "no_group_rejected")


class TreeError(DiffError):
    """A refusal by the nested family.

    Subclasses ``DiffError`` so ``cli``'s ``_REFUSABLE`` already maps it to exit 2 without a
    change to ``cli.py``.
    """


class UnknownGrouping(TreeError):
    """``--by`` named something no rung owns.

    Not a trace grouping, not an axis either manifest declares, not a task-family key the
    configs carry, and not ``WHOLE_GRID``. Refused outright and **never** a fallback: a
    silent-but-stated fallback is its own hazard, so the names nothing can build a grouping from
    are refused while the known-but-unsupported ones fall through with a row.
    """


class TraceGroupingUnsupported(TreeError):
    """The named stub. Raised by the trace rung for every name in ``TRACE_GROUPINGS``.

    Caught by the resolver and recorded as a refusal, never propagated to the caller: a
    ``--by kind`` today produces one row at the trace rung and resolution continues, which is
    exactly the path a later release may replace with a resolution. Nothing downstream of the
    resolver changes shape when it does.
    """


@dataclass(frozen=True)
class RootResult:
    """The dual root's verdict over one ``MultiDiffResult``'s family.

    Every field is set by ``omnibus`` and none defaults, so nothing can hand-build a partial
    result and no field can go unset in silence.
    """

    events: tuple[str, ...]
    method: Method
    scheme: Scheme
    q: float
    n_cells: int
    n_informative_cells: int
    #: ``n_cells - n_informative_cells``, carried rather than derived, so ``cli.py`` can print
    #: the complement without doing the subtraction.
    n_uninformative_cells: int
    n_discordant: int | None
    n_permutations: int
    #: ``1 / (n_permutations + 1)``: the smallest p Phipson-Smyth's ``(1 + count) / (B + 1)`` can
    #: express over this draw, and so a floor under every permutation p in the tree -- the root's
    #: two and its omnibus, and each tested group's three. Carried rather than derived, so a
    #: renderer can label an at-floor p without doing the arithmetic. Not a
    #: statistic: it reads no row and is fixed before a permutation is drawn, the same kind of
    #: field as ``n_permutations`` beside it.
    p_floor: float
    seed: int
    units: pd.DataFrame
    location: Mapping[str, float]
    dispersion: Mapping[str, float]
    p_location: Mapping[str, float]
    p_dispersion: Mapping[str, float]
    p_omnibus: float
    rejects: bool

    def headline(self) -> str:
        """One line: the null in quotes, the verdict, p against q, and the family size.

        Never a causal claim, and none of the layered report's forbidden vocabulary -- no
        "given the root passed" conditional, nothing in the "where it broke" register. A root
        has no groups and no cells below it, so neither sentence is natural here; the rule is
        in force anyway, so the first rendered byte of the nested family already obeys it.
        The text is not pinned as bytes anywhere and is free to be reworded inside the rule.
        """
        verdict = "rejected" if self.rejects else "not rejected"
        sign = "<" if self.rejects else ">="
        events = "event" if len(self.events) == 1 else "events"
        return (
            f'"no cell changed" is {verdict} '
            f"(p = {self.p_omnibus:g} {sign} q {self.q:g}) "
            f"over {self.n_cells} cells x {len(self.events)} {events}"
        )

    def to_json(self) -> dict[str, Any]:
        """Every field, ``units`` as records, plus ``headline``, in native Python types.

        Native, not NumPy: ``cli.py``'s ``--format json`` serialises this mapping directly, and
        ``json.dumps`` refusing a NumPy scalar there would be a defect found by a reader rather
        than by a test. ``events`` is a list, not a tuple, because the payload has to survive a
        JSON round trip unchanged.
        """
        return {
            "events": list(self.events),
            "method": self.method,
            "scheme": self.scheme,
            "q": float(self.q),
            "n_cells": int(self.n_cells),
            "n_informative_cells": int(self.n_informative_cells),
            "n_uninformative_cells": int(self.n_uninformative_cells),
            "n_discordant": None if self.n_discordant is None else int(self.n_discordant),
            "n_permutations": int(self.n_permutations),
            "p_floor": float(self.p_floor),
            "seed": int(self.seed),
            "units": [
                {column: _native(value) for column, value in record.items()}
                for record in self.units.to_dict(orient="records")
            ],
            "location": {k: float(v) for k, v in self.location.items()},
            "dispersion": {k: float(v) for k, v in self.dispersion.items()},
            "p_location": {k: float(v) for k, v in self.p_location.items()},
            "p_dispersion": {k: float(v) for k, v in self.p_dispersion.items()},
            "p_omnibus": float(self.p_omnibus),
            "rejects": bool(self.rejects),
            "headline": self.headline(),
        }


@dataclass(frozen=True)
class _Design:
    """The exchangeable view of one pair: what the permutation acts on.

    Rows are cells in sorted-hash order and columns are units; a cell with fewer units than the
    widest one is padded with ``_PAD``. Under ``pair_swap`` ``left`` and ``right`` hold the two
    arms of each matched pair and ``in_a`` and ``in_b`` are the same mask. Under ``arm_label``
    ``left`` holds each cell's pooled ``n_a + n_b`` outcomes -- arm a's first -- ``right`` is
    empty, and ``in_a`` / ``in_b`` cut the pool at ``n_a``, which is what preserves each arm's
    size through any permutation of the labels.
    """

    scheme: Scheme
    hashes: tuple[str, ...]
    configs: tuple[Any, ...]
    n_a: NDArray[np.int64]
    n_b: NDArray[np.int64]
    left: NDArray[np.int16]
    right: NDArray[np.int16]
    in_a: NDArray[np.bool_]
    in_b: NDArray[np.bool_]
    ragged: bool
    #: Per cell, under the scheme in force: whether some exchange could move it, and how many
    #: matched pairs differ (``None`` under ``arm_label``). Carried per cell rather than only
    #: as a total because the fault lines' groups are row slices of exactly these cells and their
    #: counts must sum back to the root's.
    informative: NDArray[np.bool_]
    discordant: NDArray[np.int64] | None
    n_informative_cells: int
    n_discordant: int | None


# ---------- the rebuild ----------


def _valid(frame: pd.DataFrame) -> pd.DataFrame:
    """``multi_diff``'s valid-row filter in its own words: an errored row has a null outcome
    and is excluded from every numerator and denominator."""
    return frame.loc[frame["outcome"].notna()].reset_index(drop=True)


def _rebuild(
    a: pd.DataFrame, b: pd.DataFrame, horizon: float
) -> tuple[list[str], dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[Any, int]]:
    """The common-cell view ``multi_diff`` built, rebuilt in ``multi_diff``'s own order.

    Filter the null outcomes, truncate both arms at ``multi.horizon`` with ``_truncate_raw``,
    intersect the hashes, sort them, group -- every step the one ``multi_diff`` takes, in the
    order it takes it, because the rebuild's whole purpose is to agree with it. A "simpler"
    rebuild that skips truncation counts a re-censored row as an event and lands a different
    ``events_a`` on any pair whose two arms ran to different horizons; no store measured so far
    can express that, which is exactly why the same call does it here.

    The codebook is built from the truncated frames, so a re-censored outcome does not earn a
    code it can no longer carry, and it is sorted, so the mapping is a function of the data and
    not of row order.
    """
    a_t, _ = _truncate_raw(_valid(a), horizon)
    b_t, _ = _truncate_raw(_valid(b), horizon)
    seen = set(a_t["outcome"].dropna().unique()) | set(b_t["outcome"].dropna().unique())
    codebook = {outcome: index for index, outcome in enumerate(sorted(seen, key=str))}
    for frame in (a_t, b_t):
        frame[_CODE_COLUMN] = (
            frame["outcome"].map(lambda o: codebook.get(o, _CENSORED)).astype(np.int16)
        )
    hashes_a = set(a_t["config_hash"].astype(str))
    hashes_b = set(b_t["config_hash"].astype(str))
    common = sorted(hashes_a & hashes_b)
    groups_a = {str(k): g for k, g in a_t.groupby("config_hash", sort=False)}
    groups_b = {str(k): g for k, g in b_t.groupby("config_hash", sort=False)}
    return common, groups_a, groups_b, codebook


def _matched(
    cell_a: pd.DataFrame, cell_b: pd.DataFrame, config_hash: str
) -> tuple[NDArray[np.int16], NDArray[np.int16]]:
    """The matched pairs of one cell, as two code vectors in replicate order.

    The same inner join on ``replicate_index`` ``_discordant`` uses, so the pairs the root
    exchanges are the pairs ``mcnemar_bh`` tested: an unmatched replicate is dropped rather
    than mispaired, and a duplicate index is refused rather than silently fanned out.
    """
    for label, cell in (("a", cell_a), ("b", cell_b)):
        if cell["replicate_index"].duplicated().any():
            raise TreeError(
                f"cell {config_hash}: duplicate replicate_index in run {label}; cannot pair"
            )
    index_a = cell_a["replicate_index"].to_numpy()
    index_b = cell_b["replicate_index"].to_numpy()
    codes_a = cell_a[_CODE_COLUMN].to_numpy(dtype=np.int16)
    codes_b = cell_b[_CODE_COLUMN].to_numpy(dtype=np.int16)
    if np.array_equal(index_a, index_b):
        # Every replicate matched and already aligned, which is every design this project has
        # run: the join would return exactly these two vectors, so it is skipped and not
        # reimplemented.
        return codes_a, codes_b
    joined = pd.merge(
        pd.DataFrame({"replicate_index": index_a, "code": codes_a}),
        pd.DataFrame({"replicate_index": index_b, "code": codes_b}),
        on="replicate_index",
        how="inner",
        suffixes=("_a", "_b"),
    ).sort_values("replicate_index")
    return (
        joined["code_a"].to_numpy(dtype=np.int16),
        joined["code_b"].to_numpy(dtype=np.int16),
    )


def _design(
    scheme: Scheme,
    common: Sequence[str],
    groups_a: Mapping[str, pd.DataFrame],
    groups_b: Mapping[str, pd.DataFrame],
) -> _Design:
    """The padded code matrices the exchange acts on, plus the degeneracy counts.

    A cell is **informative** when some exchange could move it: under ``pair_swap`` when at
    least one matched pair's two outcomes differ, under ``arm_label`` when its pooled
    ``n_a + n_b`` outcomes are not all identical. Everything else has a permutation
    distribution that is a point mass and contributes the same number under every draw. That
    count is a printed fact and not a footnote; it is a count over
    *outcomes*, so a cell whose only movement is between two outcomes nobody asked about is
    informative here and degenerate in the statistic, which is recorded and not smoothed.
    """
    per_cell: list[tuple[NDArray[np.int16], NDArray[np.int16]]] = []
    configs: list[Any] = []
    informative: list[bool] = []
    discordant: list[int] = []
    for h in common:
        cell_a, cell_b = groups_a[h], groups_b[h]
        configs.append(cell_a["config"].iloc[0])
        if scheme == "pair_swap":
            codes_a, codes_b = _matched(cell_a, cell_b, h)
            differ = int(np.sum(codes_a != codes_b))
            discordant.append(differ)
            informative.append(differ > 0)
        else:
            codes_a = cell_a[_CODE_COLUMN].to_numpy(dtype=np.int16)
            codes_b = cell_b[_CODE_COLUMN].to_numpy(dtype=np.int16)
            pooled = np.concatenate([codes_a, codes_b])
            informative.append(bool(np.any(pooled != pooled[0])))
        per_cell.append((codes_a, codes_b))
    informative_flags = np.array(informative, dtype=np.bool_)
    discordant_counts = (
        np.array(discordant, dtype=np.int64) if scheme == "pair_swap" else None
    )

    n_a = np.array([len(x) for x, _ in per_cell], dtype=np.int64)
    n_b = np.array([len(y) for _, y in per_cell], dtype=np.int64)
    if scheme == "pair_swap":
        width = int(max(n_a.max(), 1))
        left = np.full((len(per_cell), width), _PAD, dtype=np.int16)
        right = np.full((len(per_cell), width), _PAD, dtype=np.int16)
        for row, (codes_a, codes_b) in enumerate(per_cell):
            left[row, : len(codes_a)] = codes_a
            right[row, : len(codes_b)] = codes_b
        column = np.arange(width)[None, :]
        in_a = column < n_a[:, None]
        in_b = column < n_b[:, None]
        ragged = bool(np.any(n_a < width))
    else:
        width = int(max((n_a + n_b).max(), 1))
        left = np.full((len(per_cell), width), _PAD, dtype=np.int16)
        right = np.zeros((len(per_cell), 0), dtype=np.int16)
        for row, (codes_a, codes_b) in enumerate(per_cell):
            left[row, : len(codes_a)] = codes_a
            left[row, len(codes_a) : len(codes_a) + len(codes_b)] = codes_b
        column = np.arange(width)[None, :]
        in_a = column < n_a[:, None]
        in_b = (column >= n_a[:, None]) & (column < (n_a + n_b)[:, None])
        ragged = bool(np.any(n_a + n_b < width))
    return _Design(
        scheme=scheme,
        hashes=tuple(common),
        configs=tuple(configs),
        n_a=n_a,
        n_b=n_b,
        left=left,
        right=right,
        in_a=in_a,
        in_b=in_b,
        ragged=ragged,
        informative=informative_flags,
        discordant=discordant_counts,
        n_informative_cells=int(informative_flags.sum()),
        n_discordant=None if discordant_counts is None else int(discordant_counts.sum()),
    )


# ---------- the exchange, and the one place a stream is constructed ----------


def _observed(
    design: _Design, codes: Sequence[int]
) -> tuple[tuple[NDArray[np.int64], NDArray[np.int64]], NDArray[np.float64]]:
    """``((events_a, events_b), observed deltas)`` -- ``(C, K)`` twice, and no draw at all.

    Split out of ``_draw`` for the fault lines: the grouping is resolved from the design's
    per-arm unit counts *before* a permutation exists, so a refused ``--by`` or an out-of-range
    ``--max-group-mde`` returns in milliseconds at ``n_permutations = 10**6`` rather than after
    the block is allocated. Nothing here touches the stream, so moving it out cannot
    move a single permuted byte.
    """
    pooled = design.scheme == "arm_label"
    counts = _counts(design, design.left, design.left if pooled else design.right, codes)
    return counts, _deltas(design, counts)


def _draw(
    design: _Design,
    codes: Sequence[int],
    *,
    n_permutations: int,
    seed: int,
) -> NDArray[np.float64]:
    """The ``(B, C, K)`` permuted deltas.

    **The single construction site of the permutation stream**. One
    ``default_rng(seed)``, consumed permutation-major, never stored: the per-group pass gets
    the same draws by calling this function, not by re-deriving the stream. A second
    ``default_rng`` anywhere in the package would be a second stream free to disagree with this
    one, and a test's ``ast`` guard exists to stop that arriving.

    Outcomes are exchanged **whole**. Every event's indicator for permutation ``b`` is read off
    one exchanged code matrix, so a ``crashed -> failed_assertion`` pair moves both events
    together; exchanging per-event indicators independently would be a different -- and wrong --
    null, under which one pair can be the same event in both arms.

    Vectorised per permutation and not per cell: one ``(C, W)`` draw feeds every cell at once.
    A Python loop over cells inside the permutation loop is a hundred times slower and just as
    correct, so no assertion would catch it and only the wall clock would.
    """
    rng = np.random.default_rng(seed)
    n_cells, width = design.left.shape
    permuted = np.empty((n_permutations, n_cells, len(codes)), dtype=np.float64)
    for b in range(n_permutations):
        if design.scheme == "pair_swap":
            # One fair bit per matched pair, independently: the exchange the sharp null
            # admits for a paired design.
            swap = rng.random((n_cells, width)) < 0.5
            left = np.where(swap, design.right, design.left)
            right = np.where(swap, design.left, design.right)
        elif design.ragged:
            # Cells of different sizes: rank the real units by a uniform key and push the
            # padding past them, which leaves a uniform permutation of each cell's own pool.
            keys = rng.random((n_cells, width))
            keys[~(design.in_a | design.in_b)] = np.inf
            order = np.argsort(keys, axis=1, kind="stable")
            left = np.take_along_axis(design.left, order, axis=1)
            right = left
        else:
            # Every cell the same size: permute each row of the pool in place.
            left = rng.permuted(design.left, axis=1)
            right = left
        permuted[b] = _deltas(design, _counts(design, left, right, codes))
    return permuted


def _counts(
    design: _Design,
    arm_a: NDArray[np.int16],
    arm_b: NDArray[np.int16],
    codes: Sequence[int],
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """``(C, K)`` event counts per arm for one arrangement of the codes.

    Under ``arm_label`` both arms read the one pooled matrix through ``in_a`` / ``in_b``, so
    the first ``n_a`` of the permuted pool go to arm a and the per-cell arm sizes survive the
    exchange.
    """
    events_a = np.empty((arm_a.shape[0], len(codes)), dtype=np.int64)
    events_b = np.empty((arm_b.shape[0], len(codes)), dtype=np.int64)
    for index, code in enumerate(codes):
        events_a[:, index] = np.sum((arm_a == code) & design.in_a, axis=1)
        events_b[:, index] = np.sum((arm_b == code) & design.in_b, axis=1)
    return events_a, events_b


def _deltas(
    design: _Design, counts: tuple[NDArray[np.int64], NDArray[np.int64]]
) -> NDArray[np.float64]:
    events_a, events_b = counts
    out: NDArray[np.float64] = events_b / design.n_b[:, None] - events_a / design.n_a[:, None]
    return out


def _statistics(
    deltas: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """``(..., C, K)`` deltas to ``(signed mean, RMS, extremeness)`` -- ``(..., K)`` twice and
    ``(..., 2K)`` once, location first then dispersion in the last.

    ``|mean|`` and RMS rather than ``|sum|`` and the sum of squares: at a fixed ``C`` per
    family each is a monotone transform of the plan's statistic, so every p-value is the sum's,
    and the number a reader sees is a per-cell movement rather than one that scales with the
    grid. **Unweighted**, and there is nowhere else a weight could enter: this is the one place
    the deltas become a statistic.

    It returns the *signed* mean and the RMS beside the extremeness because this is also where
    the **reported** ``location`` and ``dispersion`` come from, at the root and at every group
    alike. Computing the reported field a second time beside the tested one is how the reported
    and the tested values split apart, and closing it by construction is what makes
    the drift case fail loudly rather than quietly: every reduction that makes a statistic --
    every ``mean``, ``sqrt`` and ``average`` -- lives in this function and its callers hand it a
    bare array or a row slice of one, nothing else.

    Callers slice the **deltas**, never these statistics: a group's location is a mean over its
    own ``C_g`` cells, and a row slice of the root's mean would be a mean over ``C``.
    """
    n_cells = deltas.shape[-2]
    signed: NDArray[np.float64] = deltas.sum(axis=-2) / n_cells
    root_mean_square: NDArray[np.float64] = np.sqrt((deltas * deltas).sum(axis=-2) / n_cells)
    extremeness: NDArray[np.float64] = np.concatenate(
        [np.abs(signed), root_mean_square], axis=-1
    )
    return signed, root_mean_square, extremeness


# ---------- the calibration ----------


def _phipson_smyth(
    observed: NDArray[np.float64], permuted: NDArray[np.float64]
) -> NDArray[np.float64]:
    """``p_j = (1 + #{b : S_bj >= S_j}) / (B + 1)`` for each of the ``J`` statistics.

    The ``+ 1`` on both counts is Phipson & Smyth (2010): a permutation p-value of zero claims
    a precision the resampling does not have. Ties count, hence ``>=``.
    """
    n_permutations = permuted.shape[0]
    counts = np.sum(permuted >= observed[None, :], axis=0)
    out: NDArray[np.float64] = (1 + counts) / (n_permutations + 1)
    return out


def _min_p(
    observed: NDArray[np.float64], permuted: NDArray[np.float64]
) -> tuple[NDArray[np.float64], float]:
    """Westfall-Young min-p over ``J`` dependent statistics: ``(per-statistic p, omnibus p)``.

    The two roots are one intersection hypothesis on the same deltas, not two hypotheses, so BH
    across them has no proof; calibrating their minimum by the same permutations costs nothing
    to that dependence. Each permutation gets its own rank-p per statistic on the observed
    p's scale: ``(#{b' : S_b' >= S_b} + [S_obs >= S_b]) / (B + 1)``, the reference set
    being the ``B`` permutations and the observed point -- and the omnibus counts the
    permutations whose min-p reaches the observed one. That last count is what separates
    this from the bare minimum of the ``J`` p-values, which is the quantity Westfall-Young
    exists to correct; the two coincide only when one statistic's extreme set contains the
    other's.
    """
    n_permutations = permuted.shape[0]
    p_observed = _phipson_smyth(observed, permuted)
    rank_p = np.empty_like(permuted)
    for j in range(permuted.shape[1]):
        column = np.sort(permuted[:, j])
        at_least = n_permutations - np.searchsorted(column, permuted[:, j], side="left")
        rank_p[:, j] = (at_least + (observed[j] >= permuted[:, j])) / (n_permutations + 1)
    m_observed = float(p_observed.min())
    omnibus_p = (1 + int(np.sum(rank_p.min(axis=1) <= m_observed))) / (n_permutations + 1)
    return p_observed, omnibus_p


# ---------- validation, all of it before anything is drawn ----------


def _require_knobs(n_permutations: Any, seed: Any) -> None:
    """``bool`` is an ``int`` to Python and is refused anyway: ``seed=True`` is a typo, never a
    seed, and ``n_permutations=True`` is one permutation nobody asked for."""
    if isinstance(n_permutations, bool) or not isinstance(n_permutations, int):
        raise TreeError(f"n_permutations must be an int, got {n_permutations!r}")
    if n_permutations < 1:
        raise TreeError(f"n_permutations must be at least 1, got {n_permutations}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TreeError(f"seed must be an int, got {seed!r}")


def _require_depth(value: Any) -> int:
    """``--depth`` is refused here and not in ``cli.py``, by the analogy the comparison's
    ``0 < q < 1`` and ``_require_max_group_mde`` already set: the CLI parses an int and decides
    nothing.

    Called before the rebuild, so a depth outside ``DEPTHS`` costs milliseconds at any number
    of permutations. ``bool`` is an ``int`` to Python and is refused anyway, and a ``"3"`` or a
    ``3.0`` is refused rather than coerced -- a string that happens to parse is a typo, never a
    depth.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TreeError(f"depth must be an int, got {value!r}")
    if value not in DEPTHS:
        raise TreeError(f"depth must be one of {DEPTHS}, got {value}")
    return value


def _agreement_of(rows: Sequence[tuple[str, str, int, int, int, int]]) -> str:
    """The canonical form, written here and nowhere else.

    One line per ``(event, cell)`` carrying the four rebuild integers, sorted, JSON-serialised
    behind ``AGREEMENT_SCHEMA``, sha256, hex. **JSON and not a separator-joined string** because
    an ``event`` is an outcome value read off stored data and this project's own fixtures put
    adversarial strings into axis values on purpose; a delimiter-joined line is ambiguous the
    moment a value contains the delimiter, and two different rebuilds could then mint one digest.
    **Sorted** because the mint walks ``common`` x ``multi.events`` and the recomputation walks
    ``multi.events`` x ``cells`` in row order, and sorting is the only thing that makes one
    function's output checkable by the other's.
    """
    canonical = sorted(
        [str(event), str(config_hash), int(n_a), int(n_b), int(events_a), int(events_b)]
        for event, config_hash, n_a, n_b, events_a, events_b in rows
    )
    payload = json.dumps([AGREEMENT_SCHEMA, canonical], separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def agreement_digest(multi: MultiDiffResult) -> str:
    """The agreement digest recomputed from a diff alone, in the tree's own canonical form.

    The check side of the pair ``_require_agreement`` mints. It reads the four rebuild columns
    off ``cells`` rather than off the frames, which is the whole point: a renderer holds a diff
    and a tree and nothing else, and this is how it asks whether the second was grown from the
    first. Covers the cell set, the event set and the four episode counts per cell per event,
    and nothing else -- not the method, not ``q``, not the horizon or any permutation knob,
    which is why both renderers carry a second, separate knob clause.
    """
    rows: list[tuple[str, str, int, int, int, int]] = []
    for event in multi.events:
        cells = multi.by_event[event].cells
        for row in zip(
            cells["config_hash"],
            *(cells[column] for column in _REBUILD_COLUMNS),
            strict=True,
        ):
            n_a, n_b, events_a, events_b = (int(value) for value in row[1:])
            rows.append((str(event), str(row[0]), n_a, n_b, events_a, events_b))
    return _agreement_of(rows)


def _require_agreement(
    multi: MultiDiffResult,
    common: Sequence[str],
    groups_a: Mapping[str, pd.DataFrame],
    groups_b: Mapping[str, pd.DataFrame],
    codebook: Mapping[Any, int],
) -> str:
    """The rebuild guard: episode counts recomputed from the frames must equal ``cells``.

    The root is a *second* construction of something ``multi_diff`` already built, and this is
    the check that makes the second construction safe. It compares the episode-level counts --
    the four columns ``multi_diff`` itself wrote -- rather than the root's own units, because
    under ``pair_swap`` the unit is the matched pair and an unmatched replicate legitimately
    makes ``units`` smaller than ``cells``. What may not differ is what the two objects both
    claim to have counted from the same frames. When it does, the caller handed the root a
    different pair than the diff, and the refusal names the first mismatching cell in
    sorted-hash order.

    **And it mints the agreement digest**, over the tuples it
    rebuilt from the frames rather than over ``cells`` -- the two are equal by the time this
    returns, so the values are identical and the difference is what the field *means* to a
    consumer: under this mint the tree says *I recomputed these counts from the episodes and
    they matched*, not *here is a hash of the diff I was handed*. It is minted here for the
    same reason the comparison lives here at all: this is the one place the two sides are
    already known to agree, and neither renderer can establish that on its own.
    """
    rows: list[tuple[str, str, int, int, int, int]] = []
    by_hash: dict[str, dict[str, tuple[int, ...]]] = {}
    for event in multi.events:
        cells = multi.by_event[event].cells
        by_hash[event] = {
            str(row[0]): tuple(int(value) for value in row[1:])
            for row in zip(
                cells["config_hash"],
                *(cells[column] for column in _REBUILD_COLUMNS),
                strict=True,
            )
        }
    for h in common:
        codes_a = groups_a[h][_CODE_COLUMN].to_numpy(dtype=np.int16)
        codes_b = groups_b[h][_CODE_COLUMN].to_numpy(dtype=np.int16)
        for event in multi.events:
            recorded_row = by_hash[event].get(h)
            if recorded_row is None:
                raise TreeError(
                    f"cell {h}: rebuilt from the frames but absent from the {event!r} family; "
                    "the frames are not the pair this diff was computed from"
                )
            code = codebook.get(event, _PAD)
            rebuilt = (
                len(codes_a),
                len(codes_b),
                int(np.sum(codes_a == code)),
                int(np.sum(codes_b == code)),
            )
            if rebuilt != recorded_row:
                raise TreeError(
                    f"cell {h}: the rebuild disagrees with the diff on event {event!r} -- "
                    f"{_REBUILD_COLUMNS} is {rebuilt} from the frames and {recorded_row} on "
                    "cells; the frames are not the pair this diff was computed from"
                )
            rows.append((str(event), str(h), *rebuilt))
    return _agreement_of(rows)


# ---------- the public function ----------


def _prepared(
    a: pd.DataFrame,
    b: pd.DataFrame,
    multi: MultiDiffResult,
    *,
    n_permutations: int,
    seed: int,
) -> tuple[
    Scheme,
    tuple[str, ...],
    _Design,
    list[int],
    tuple[NDArray[np.int64], NDArray[np.int64]],
    NDArray[np.float64],
    str,
]:
    """Everything that can refuse, then the design and the observed counts -- and no draw.

    Shared by ``omnibus`` and ``tree`` so the two build one design from one rebuild under one
    guard, and so the grouping resolver can read the per-arm unit counts before a permutation
    exists.
    """
    _require_knobs(n_permutations, seed)
    if multi.n_tests == 0:
        raise TreeError(
            "the family is empty: multi_diff found no comparable cell, so there is no "
            "hypothesis for the root to test"
        )
    scheme = SCHEME_BY_METHOD[multi.method]
    common, groups_a, groups_b, codebook = _rebuild(a, b, multi.horizon)
    if not common:
        raise TreeError(
            f"the rebuild found no common cell but the diff tested {multi.n_tests}; "
            "the frames are not the pair this diff was computed from"
        )
    agreement = _require_agreement(multi, common, groups_a, groups_b, codebook)
    design = _design(scheme, common, groups_a, groups_b)
    # A requested event nobody ran gets a code no outcome carries, so its incidence is zero in
    # both arms rather than an error -- the posture ``multi_diff`` already takes.
    codes = [codebook.get(event, _PAD) for event in multi.events]
    counts, observed = _observed(design, codes)
    return scheme, tuple(common), design, codes, counts, observed, agreement


def _root(
    multi: MultiDiffResult,
    scheme: Scheme,
    common: Sequence[str],
    design: _Design,
    units: pd.DataFrame,
    observed: NDArray[np.float64],
    permuted: NDArray[np.float64],
    *,
    n_permutations: int,
    seed: int,
) -> RootResult:
    """The ``RootResult`` for one draw. The reported statistics and the tested ones are the
    same two arrays, read off one ``_statistics`` call."""
    n_events = len(multi.events)
    observed_block = observed[None, :, :]
    location, dispersion, observed_statistics = _statistics(observed_block)
    _, _, permuted_statistics = _statistics(permuted)
    p_statistics, omnibus_p = _min_p(observed_statistics[0], permuted_statistics)
    return RootResult(
        events=tuple(multi.events),
        method=multi.method,
        scheme=scheme,
        q=float(multi.q),
        n_cells=len(common),
        n_informative_cells=design.n_informative_cells,
        n_uninformative_cells=len(common) - design.n_informative_cells,
        n_discordant=design.n_discordant,
        n_permutations=n_permutations,
        p_floor=1 / (n_permutations + 1),
        seed=seed,
        units=units,
        location={e: float(location[0][i]) for i, e in enumerate(multi.events)},
        dispersion={e: float(dispersion[0][i]) for i, e in enumerate(multi.events)},
        p_location={e: float(p_statistics[i]) for i, e in enumerate(multi.events)},
        p_dispersion={e: float(p_statistics[n_events + i]) for i, e in enumerate(multi.events)},
        p_omnibus=float(omnibus_p),
        rejects=bool(omnibus_p < multi.q),
    )


def omnibus(
    a: pd.DataFrame,
    b: pd.DataFrame,
    multi: MultiDiffResult,
    *,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    seed: int = DEFAULT_SEED,
) -> RootResult:
    """The dual root over the family ``multi`` already tested.

    ``a`` and ``b`` are the RAW ``Store.read()`` frames ``multi`` was computed from; events,
    method, ``q``, the horizon and the common cells are read from ``multi`` and never
    re-decided. Everything that can refuse refuses **before a single permutation is drawn**, so
    a caller who passes ``n_permutations = 10**6`` and a mismatched pair gets the refusal in
    milliseconds rather than after the block is allocated.
    """
    scheme, common, design, codes, counts, observed, _agreement = _prepared(
        a, b, multi, n_permutations=n_permutations, seed=seed
    )
    permuted = _draw(design, codes, n_permutations=n_permutations, seed=seed)
    return _root(
        multi,
        scheme,
        common,
        design,
        _units(design, multi.events, counts),
        observed,
        permuted,
        n_permutations=n_permutations,
        seed=seed,
    )


def _units(
    design: _Design,
    events: Sequence[str],
    counts: tuple[NDArray[np.int64], NDArray[np.int64]],
) -> pd.DataFrame:
    """One row per ``(event, common cell)``: the counts the exchange actually ran over.

    ``delta`` is the naive proportion difference and not ``cells.delta`` (the Aalen-Johansen
    difference at the horizon), because the permutation acts on outcomes and the proportion is
    the honest statistic for the exchange. The two coincide wherever nothing is censored before
    the horizon, which is every input this project has measured; if a change to truncation ever
    makes them differ, this column stays right and the rebuild guard is what notices.
    ``+ 0.0`` so a zero is unsigned, as ``cells`` does.
    """
    events_a, events_b = counts
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        for row, h in enumerate(design.hashes):
            n_a, n_b = int(design.n_a[row]), int(design.n_b[row])
            count_a, count_b = int(events_a[row, index]), int(events_b[row, index])
            rows.append(
                {
                    "event": event,
                    "config_hash": h,
                    "config": design.configs[row],
                    "n_a": n_a,
                    "n_b": n_b,
                    "events_a": count_a,
                    "events_b": count_b,
                    "delta": count_b / n_b - count_a / n_a + 0.0,
                }
            )
    frame = pd.DataFrame.from_records(rows, columns=list(UNITS_COLUMNS))
    frame["config"] = frame["config"].astype(object)
    return frame



# ---------- the grouping, the refusal chain, and the fault lines ----------


@dataclass(frozen=True)
class Refusal:
    """One row of the chain: what a rung would not group by, why, and what came next.

    ``n_groups`` and ``n_resolvable_groups`` are the power rule's findings and are ``None``
    where the rule never ran -- an unsupported name has no partition, and a key one manifest
    does not declare is not a grouping of this pair. ``offered_max_group_mde`` is set only for
    ``underpowered``: it is the value that admits the grouping when pasted back, and offering
    one for a refusal a threshold cannot lift would be an instruction that does not work.
    """

    key: str
    rung: str
    reason: str
    detail: str
    next_rung: str
    n_groups: int | None
    n_resolvable_groups: int | None
    offered_max_group_mde: float | None

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "rung": self.rung,
            "reason": self.reason,
            "detail": self.detail,
            "next_rung": self.next_rung,
            "n_groups": None if self.n_groups is None else int(self.n_groups),
            "n_resolvable_groups": (
                None if self.n_resolvable_groups is None else int(self.n_resolvable_groups)
            ),
            "offered_max_group_mde": (
                None
                if self.offered_max_group_mde is None
                else float(self.offered_max_group_mde)
            ),
        }


@dataclass(frozen=True)
class Grouping:
    """Which grouping Level 2 tests, which rung resolved it, and every refusal on the way.

    The key, the rung, the group count, the cells-per-group distribution and the
    chain are stated **every time**, including when the grouping is the one requested. Every
    field a reader needs is carried rather than derived, so ``cli.py`` prints and computes
    nothing: ``size_min``, ``size_median``, ``size_max``, ``alpha_floor`` and
    ``n_resolvable_groups`` are all here for that reason.

    The whole object is a function of the grouping's **shape** -- unit counts per arm and group
    cardinality -- and of nothing measured, so a grouping is admitted or refused before a single
    delta is read. That is pre-registration discipline at the level that most invites choosing
    after the fact.
    """

    key: str
    resolved_by: str
    requested: str | None
    labels: tuple[str, ...]
    groups: Mapping[str, tuple[str, ...]]
    n_groups: int
    group_sizes: tuple[int, ...]
    size_min: int
    size_median: float
    size_max: int
    alpha_floor: float
    max_group_mde: float
    group_mde: tuple[float, ...]
    n_resolvable_groups: int
    refused: tuple[Refusal, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "resolved_by": self.resolved_by,
            "requested": self.requested,
            "labels": list(self.labels),
            "groups": {label: list(hashes) for label, hashes in self.groups.items()},
            "n_groups": int(self.n_groups),
            "group_sizes": [int(size) for size in self.group_sizes],
            "size_min": int(self.size_min),
            "size_median": float(self.size_median),
            "size_max": int(self.size_max),
            "alpha_floor": float(self.alpha_floor),
            "max_group_mde": float(self.max_group_mde),
            "group_mde": [float(value) for value in self.group_mde],
            "n_resolvable_groups": int(self.n_resolvable_groups),
            "refused": [refusal.to_json() for refusal in self.refused],
        }


@dataclass(frozen=True)
class GroupResult:
    """One group's row of the fault lines: what it holds, what moved, and whether it rejects.

    The counts and the design numbers are present whether or not the level was tested; every
    ``p_*``, ``q_group`` and ``rejects`` is ``None`` when it was not. No p-value is computed for
    an untested level, because a number that exists invites reading.

    ``degenerate`` is about what the exchange **could** move, not about what it did: a group with
    informative cells can still sit at p exactly 1 (two groups of one measured sweep, one
    informative cell each) and is not degenerate. Flagging degeneracy from ``p == 1`` or from a
    zero delta is the mistake the tests are written to catch.
    """

    label: str
    key: str
    cells: tuple[str, ...]
    n_cells: int
    n_informative_cells: int
    n_uninformative_cells: int
    n_discordant: int | None
    n_a: int
    n_b: int
    mde: float
    degenerate: bool
    location: Mapping[str, float]
    dispersion: Mapping[str, float]
    p_location: Mapping[str, float] | None
    p_dispersion: Mapping[str, float] | None
    p_group: float | None
    q_group: float | None
    rejects: bool | None

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "key": self.key,
            "cells": list(self.cells),
            "n_cells": int(self.n_cells),
            "n_informative_cells": int(self.n_informative_cells),
            "n_uninformative_cells": int(self.n_uninformative_cells),
            "n_discordant": None if self.n_discordant is None else int(self.n_discordant),
            "n_a": int(self.n_a),
            "n_b": int(self.n_b),
            "mde": float(self.mde),
            "degenerate": bool(self.degenerate),
            "location": {k: float(v) for k, v in self.location.items()},
            "dispersion": {k: float(v) for k, v in self.dispersion.items()},
            "p_location": (
                None
                if self.p_location is None
                else {k: float(v) for k, v in self.p_location.items()}
            ),
            "p_dispersion": (
                None
                if self.p_dispersion is None
                else {k: float(v) for k, v in self.p_dispersion.items()}
            ),
            "p_group": None if self.p_group is None else float(self.p_group),
            "q_group": None if self.q_group is None else float(self.q_group),
            "rejects": None if self.rejects is None else bool(self.rejects),
        }


@dataclass(frozen=True)
class FaultLines:
    """Level 2: which kind of work moved, and nothing about where anything broke.

    Tested only when the root rejected and the grouping has more than one group;
    corrected by BH across **every** group at ``q``, degenerate ones included, because excluding
    the hopeless ones is Tarone's procedure and discrete BH's and neither is built -- the leak is
    ``n_degenerate_groups``, printed rather than recovered.

    **No conditional claim.** The gate is the procedure; the claim is not. Nothing here, in the
    JSON or on the block says or implies "given the root rejected, the fault lines are controlled
    at q". A level that was not tested is stated, not omitted.
    """

    tested: bool
    reason: str | None
    null: str
    q: float
    n_groups: int
    n_degenerate_groups: int
    n_rejected_groups: int
    rejected_groups: tuple[str, ...]
    groups: tuple[GroupResult, ...]
    #: The group limit's power is the tree's whole flag, the root and the group rejecting.
    mde_basis: str = "unconditional"

    def to_json(self) -> dict[str, Any]:
        return {
            "tested": bool(self.tested),
            "reason": self.reason,
            "null": self.null,
            "q": float(self.q),
            "n_groups": int(self.n_groups),
            "n_degenerate_groups": int(self.n_degenerate_groups),
            "n_rejected_groups": int(self.n_rejected_groups),
            "rejected_groups": list(self.rejected_groups),
            "groups": [group.to_json() for group in self.groups],
            "mde_basis": self.mde_basis,
        }


@dataclass(frozen=True)
class CellResult:
    """One leaf: one ``(cell, event)`` under a group that rejected at Level 2.

    Every number but ``q_within`` and ``rejects`` is the flat family's own row, read from
    ``multi.by_event[event].cells`` and never recomputed. ``p`` is whichever
    test the grid analysis ran on that cell -- Fisher exact, exact McNemar or log-rank -- so a
    reader finds the same p on the heatmap; ``delta`` is that row's Aalen-Johansen difference
    at the horizon and not the root's proportion difference; ``mde`` is the flat row's smallest
    detectable *increase* from arm A's rate, capped at the headroom, so one cell reads one MDE
    across the two surfaces. On a cell at ceiling that cap **is** the headroom and is not a
    power number; the honesty block says so and the row does not carry a
    second MDE.

    **No interval, no per-group level, and no flat-family verdict or ``q``.** The nested and the
    flat rejected sets differ in both directions on a real axis, so a flat ``q`` beside a nested
    verdict is a two-thresholds contradiction; the flat verdict for the same
    cell stays where it is, on the grid.
    """

    config_hash: str
    config: Mapping[str, Any]
    #: The requested event this row tests, one of ``RootResult.events``.
    event: str
    #: The label of the group whose family this row is in.
    group: str
    n_a: int
    n_b: int
    events_a: int
    events_b: int
    delta: float
    p: float
    #: BH over this family's cells x events at ``q`` -- not the flat family's ``q``.
    q_within: float
    rejects: bool
    mde: float
    #: Why a null limit is null, from the flat row; None when ``mde`` is a number.
    mde_note: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "config_hash": self.config_hash,
            "config": {str(key): _native(value) for key, value in self.config.items()},
            "event": self.event,
            "group": self.group,
            "n_a": int(self.n_a),
            "n_b": int(self.n_b),
            "events_a": int(self.events_a),
            "events_b": int(self.events_b),
            "delta": float(self.delta),
            "p": float(self.p),
            "q_within": float(self.q_within),
            "rejects": bool(self.rejects),
            "mde": None if math.isnan(self.mde) else float(self.mde),
            "mde_note": self.mde_note if math.isnan(self.mde) else None,
        }


@dataclass(frozen=True)
class CellFamily:
    """The leaves under one rejected group: its ``C_g`` cells x the family's ``K`` events.

    **One family per rejected group**, never one family over the union of the rejecting groups'
    cells -- the two give different rejected sets on every axis of a measured sweep, in
    both directions. Every test is in it, a leaf at p exactly 1 included: a degenerate leaf is
    a hypothesis in the family and not an exclusion, because Tarone's procedure and discrete BH
    are not built and the leak is ``n_tests``, printed rather than recovered.

    ``mde_median`` and ``mde_max`` over the family's own ``cells.mde`` are carried so the family
    line can say what its leaves could not see without ``cli.py`` computing a median.
    """

    label: str
    key: str
    n_tests: int
    n_rejected: int
    #: ``(config_hash, event)`` per rejected leaf, in row order and never in verdict order.
    rejected: tuple[tuple[str, str], ...]
    mde_median: float
    mde_max: float
    #: In sorted-hash order, with the events in ``RootResult.events`` order under each hash --
    #: the flat family's own row order, never by result, the same rule one level down.
    cells: tuple[CellResult, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "key": self.key,
            "n_tests": int(self.n_tests),
            "n_rejected": int(self.n_rejected),
            "rejected": [[config_hash, event] for config_hash, event in self.rejected],
            "mde_median": None if math.isnan(self.mde_median) else float(self.mde_median),
            "mde_max": None if math.isnan(self.mde_max) else float(self.mde_max),
            "cells": [cell.to_json() for cell in self.cells],
        }


@dataclass(frozen=True)
class Leaves:
    """Level 3: the flat family's own per-cell tests, re-corrected under a fault line.

    Tested when the configured depth is 3 and at least one group rejected at Level 2 -- or,
    under the one-group collapse, when the root rejected, where the one family is the flat
    family bit for bit.

    **No conditional claim.** "Given the group rejected, these cells are reliable at q" is
    false: if the global null holds and the gate passes by chance, the false discovery
    proportion among the leaves is high. The unconditional outer-nodes bound beside this
    structure is the only statement the procedure supports, so nothing here, in the JSON or on
    the block says or implies otherwise, and there is no per-family rate or level for such a
    claim to live in as a number. A level that was not tested is stated, not omitted, and no
    ``q_within`` is computed for one: a number that exists invites reading.
    """

    tested: bool
    #: ``None`` when tested; else the first of ``LEAVES_NOT_TESTED_REASONS`` that applies.
    reason: str | None
    null: str
    q: float
    n_families: int
    #: The sum over the families, ``sum(C_g * K)``; 0 when the level was not tested.
    n_tests: int
    n_rejected: int
    #: In ``FaultLines.rejected_groups`` order; ``()`` when the level was not tested.
    families: tuple[CellFamily, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "tested": bool(self.tested),
            "reason": self.reason,
            "null": self.null,
            "q": float(self.q),
            "n_families": int(self.n_families),
            "n_tests": int(self.n_tests),
            "n_rejected": int(self.n_rejected),
            "families": [family.to_json() for family in self.families],
        }


@dataclass(frozen=True)
class Bound:
    """The error rate the whole procedure controls at, computed from the tree's depth.

    Yekutieli's Corollary A.2. ``depth`` is the number of levels of the tree the
    procedure **runs**: the configured depth, reduced by one only by the one-group collapse,
    which changes the procedure by shape before any delta is read. It is never the depth
    *reached* -- read off what a run found, the bound would be a random variable whose value
    depends on the outcomes it bounds, so a reader comparing two reports would learn which one
    rejected from its bound, and it would understate the error rate after a chance stop.

    ``discoveries`` names the set the number is over, because there are two universal bounds in
    the source over two different sets. The bound rests on a condition the source states and
    this tree does not give -- a p-value independent of its ancestors', where a group's p
    aggregates its own cells -- so it is printed as the rule's number under the rule's
    assumption, with the assumption on the block. No cap: a bound above 1 prints as computed and
    says nothing, which at that ``q`` is the truth.
    """

    depth_configured: int
    depth: int
    q: float
    delta_star: float
    bound: float
    discoveries: str

    def to_json(self) -> dict[str, Any]:
        return {
            "depth_configured": int(self.depth_configured),
            "depth": int(self.depth),
            "q": float(self.q),
            "delta_star": float(self.delta_star),
            "bound": float(self.bound),
            "discoveries": self.discoveries,
        }


@dataclass(frozen=True)
class TreeResult:
    """The root, the grouping it was cut by, the fault lines under it, the cells under those,
    and the bound the whole procedure controls at -- from one draw."""

    root: RootResult
    grouping: Grouping
    fault_lines: FaultLines
    leaves: Leaves
    bound: Bound
    #: The rebuild this tree's own construction verified, as a content digest. No
    #: default and last, so nothing can hand-build a partial result: a tree that carries one is
    #: a tree whose four rebuild columns were recomputed from the frames and matched the diff's.
    agreement: str

    def to_json(self) -> dict[str, Any]:
        """Native types throughout, lists for tuples, and a payload that survives a round trip.

        Self-contained: the tree carries its own root rather than pointing at a
        sibling key of whatever mapping ``cli.py`` composes around it.
        """
        return {
            "root": self.root.to_json(),
            "grouping": self.grouping.to_json(),
            "fault_lines": self.fault_lines.to_json(),
            "leaves": self.leaves.to_json(),
            "bound": self.bound.to_json(),
            "agreement": self.agreement,
        }


@dataclass(frozen=True)
class _CellTable:
    """The per-cell facts the resolver reads: a hash, a config, and the units each arm ran.

    Units, not cells: under pair swap the unit is the matched pair
    and under arm label it is the episode, so ``n_a`` is scheme-dependent and the group MDE with
    it. The resolver follows the root rather than re-deciding.
    """

    hashes: tuple[str, ...]
    configs: tuple[Mapping[str, Any], ...]
    n_a: NDArray[np.int64]
    n_b: NDArray[np.int64]
    #: Each compared event's baseline in every cell, arm A's share, in sorted event order;
    #: a group's limit reads each cell's own.
    baselines: tuple[NDArray[np.float64], ...] = ()


@dataclass(frozen=True)
class _Request:
    """What every rung is handed. ``frames`` is unread today and is what the trace rung will
    read in a later release; ``seen`` and ``refused`` carry the chain so a key refused once is
    skipped by every later rung without a second row a reader cannot tell from a second
    refusal."""

    requested: str | None
    manifest_a: RunManifest
    manifest_b: RunManifest
    table: _CellTable
    q: float
    max_group_mde: float
    frames: Any
    seen: set[str] = field(default_factory=set)
    refused: list[Refusal] = field(default_factory=list)


def _require_max_group_mde(value: Any) -> float:
    """The power gate's threshold one level down; the range check lives here, not in ``cli.py``.

    By exact analogy with the comparison's ``0 < q < 1`` and ``check_power``: the CLI parses a
    float and decides nothing statistical. A string is refused rather than coerced --
    ``float("0.3")`` would succeed and turn a typo into a threshold.
    """
    if value is None:
        return DEFAULT_MAX_GROUP_MDE
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TreeError(f"--max-group-mde must be a float, got {value!r}")
    accepted = float(value)
    if not 0.0 < accepted < 1.0:
        raise TreeError(
            f"--max-group-mde must be greater than 0 and less than 1, got {accepted!r}"
        )
    return accepted


def _cell_table(units: pd.DataFrame) -> _CellTable:
    """One row per comparable cell, de-duplicated from ``units`` over the first event.

    The per-arm unit counts are a property of the cell and not of the event, so any event's rows
    give the same table; the first is taken rather than summed, which would double-count a
    two-event family.
    """
    if units.empty:
        raise TreeError("the root's units are empty, so there is nothing to group")
    rows = units[units["event"] == units["event"].iloc[0]]
    hashes = tuple(str(h) for h in rows["config_hash"])
    return _CellTable(
        hashes=hashes,
        configs=tuple(rows["config"]),
        n_a=rows["n_a"].to_numpy(dtype=np.int64),
        n_b=rows["n_b"].to_numpy(dtype=np.int64),
        baselines=tuple(
            _baselines(units, hashes, event) for event in sorted({str(e) for e in units["event"]})
        ),
    )


def _baselines(units: pd.DataFrame, hashes: Sequence[str], event: str) -> NDArray[np.float64]:
    """One event's baseline, arm A's share, in each cell of ``hashes``."""
    rows = units[units["event"].astype(str) == event]
    rows = rows.set_index(rows["config_hash"].astype(str)).loc[list(hashes)]
    sizes = np.maximum(rows["n_a"].to_numpy(dtype=np.float64), 1.0)
    shares: NDArray[np.float64] = rows["events_a"].to_numpy(dtype=np.float64) / sizes
    return shares


def _partition(table: _CellTable, key: str) -> dict[str, list[int]]:
    """``str(value) -> cell indices`` for one config key, over every comparable cell.

    A common cell whose config lacks the key is a corrupt pair, not a grouping question, and is
    refused rather than dropped into a group of its own.
    """
    out: dict[str, list[int]] = {}
    for index, config in enumerate(table.configs):
        if key not in config:
            raise TreeError(
                f"cell {table.hashes[index]} carries no {key!r} in its config, but {key!r} is a "
                "grouping of this pair; the two runs are not the same design"
            )
        out.setdefault(str(config[key]), []).append(index)
    return out


def _ordered_labels(partition: Mapping[str, Sequence[int]]) -> tuple[str, ...]:
    """Numerically where every label is a plain number, lexically otherwise, always total."""
    labels = list(partition)
    if labels and all(_NUMERIC_LABEL.fullmatch(label) for label in labels):
        return tuple(sorted(labels, key=float))
    return tuple(sorted(labels))


def _group_mdes(
    table: _CellTable, partition: Mapping[str, Sequence[int]], labels: Sequence[str], alpha: float
) -> tuple[float, ...]:
    """Each group's detection limit at the family's floor ``alpha`` (``q / G``).

    The smallest change that, made in every condition of the group from its own baseline and in
    no other condition, the tree would flag with the root and the group both rejecting, at the
    stated power, unconditionally (``_limits.group_limit``). With several events it is the largest
    over the events, from each event's own baselines, so whichever event moves the group can tell
    it and the order the events were named in does not matter. 1.0 when a group
    has no room or nothing within its room is detectable.
    """
    sizes_a, sizes_b = table.n_a.astype(np.float64), table.n_b.astype(np.float64)
    events = len(table.baselines)
    return tuple(
        max(
            group_limit(sizes_a, sizes_b, baseline, np.asarray(partition[label], dtype=np.int64),
                        alpha=alpha, groups=len(labels), events=events, power=stats.POWER)
            for baseline in table.baselines
        )
        for label in labels
    )


# ---------- the rungs ----------


def _underpowered_detail(
    *,
    n_resolvable: int,
    n_groups: int,
    accepted: float,
    mde: float,
    n_a: int,
    n_b: int,
    alpha: float,
    offered: float | None,
) -> str:
    """The power gate's message shape one level down: three facts and one instruction.

    The MDE named is the ``MIN_RESOLVABLE_GROUPS``-th smallest -- the one that has to come down
    for the grouping to be admitted -- with the units of the group that carries it, so the
    offered override and the number it is derived from are the same number. The instruction is
    checked rather than argued: ``_offered_override`` rounds up, because rounding to nearest is
    the trap that makes a message whose one instruction refuses the same grouping again.
    """
    # A group with no room, or none detectable, has a limit of 1, which no
    # --max-group-mde admits (the flag refuses 1), so none is offered.
    admits = (
        "No --max-group-mde below 1 admits this grouping."
        if offered is None
        else f"--max-group-mde {offered:.4f} admits this grouping as it stands."
    )
    return (
        f"{n_resolvable} of {n_groups} groups can resolve a change of {accepted * 100:.1f} "
        f"points in a group's event rate (group MDE {mde:.4f} at {n_a} and {n_b} units per arm, "
        f"alpha {alpha:.3g} = q/{n_groups}), and you accepted {accepted * 100:.1f} points "
        f"(--max-group-mde {accepted:.4f}). {admits}"
    )


def _consider(
    request: _Request, key: str, *, rung: str, next_rung: str, resolved_by: str
) -> Grouping | Refusal:
    """One candidate key, judged on shape alone: a ``Grouping`` or the row that says why not.

    Nothing here reads a delta. The partition, the per-arm unit counts and the group count are
    the whole input, which is what makes ``Grouping`` byte-identical on a pair and on its
    unmoved twin.
    """
    partition = _partition(request.table, key)
    labels = _ordered_labels(partition)
    if len(labels) < MIN_FAMILY_GROUPS:
        return Refusal(
            key=key,
            rung=rung,
            reason="one_group",
            detail=(
                f"the grouping has one group over {len(request.table.hashes)} cells, which is "
                "the whole family restated rather than a family of groups."
            ),
            next_rung=next_rung,
            n_groups=len(labels),
            n_resolvable_groups=None,
            offered_max_group_mde=None,
        )
    alpha_floor = request.q / len(labels)
    mdes = _group_mdes(request.table, partition, labels, alpha_floor)
    resolvable = sum(1 for value in mdes if value <= request.max_group_mde)
    if resolvable < MIN_RESOLVABLE_GROUPS:
        order = sorted(range(len(labels)), key=lambda index: mdes[index])
        pivot = order[MIN_RESOLVABLE_GROUPS - 1]
        rows = partition[labels[pivot]]
        return Refusal(
            key=key,
            rung=rung,
            reason="underpowered",
            detail=_underpowered_detail(
                n_resolvable=resolvable,
                n_groups=len(labels),
                accepted=request.max_group_mde,
                mde=mdes[pivot],
                n_a=int(request.table.n_a[rows].sum()),
                n_b=int(request.table.n_b[rows].sum()),
                alpha=alpha_floor,
                offered=_offered_override(mdes[pivot]) if mdes[pivot] < 1.0 else None,
            ),
            next_rung=next_rung,
            n_groups=len(labels),
            n_resolvable_groups=resolvable,
            offered_max_group_mde=_offered_override(mdes[pivot]) if mdes[pivot] < 1.0 else None,
        )
    return _grouping(request, key, resolved_by, partition, labels, alpha_floor, mdes, resolvable)


def _grouping(
    request: _Request,
    key: str,
    resolved_by: str,
    partition: Mapping[str, Sequence[int]],
    labels: Sequence[str],
    alpha_floor: float,
    mdes: Sequence[float],
    resolvable: int,
) -> Grouping:
    """The resolved grouping, with ``refused`` left empty for the walker to fill."""
    groups = {
        label: tuple(sorted(request.table.hashes[index] for index in partition[label]))
        for label in labels
    }
    sizes = tuple(len(groups[label]) for label in labels)
    return Grouping(
        key=key,
        resolved_by=resolved_by,
        requested=request.requested,
        labels=tuple(labels),
        groups=groups,
        n_groups=len(sizes),
        group_sizes=sizes,
        size_min=min(sizes),
        size_median=float(np.median(sizes)),
        size_max=max(sizes),
        alpha_floor=alpha_floor,
        max_group_mde=request.max_group_mde,
        group_mde=tuple(float(value) for value in mdes),
        n_resolvable_groups=resolvable,
        refused=(),
    )


def _trace_refusal(key: str) -> Refusal:
    """The stub's one row. Recorded at the **trace** rung whoever asked for it, because the rung
    that could not answer is the fact worth stating, and a later release may replace this row
    with a resolution at that same rung."""
    return Refusal(
        key=key,
        rung="trace",
        reason="unsupported",
        detail=(
            "grouping by a trace attribute is not supported yet; the "
            "resolver continues at the next rung."
        ),
        next_rung="axis",
        n_groups=None,
        n_resolvable_groups=None,
        offered_max_group_mde=None,
    )


def _rung_requested(request: _Request) -> Grouping | Refusal | None:
    """``--by``, checked by whichever owner the name has, and refused outright when it has none.

    A name in ``TRACE_GROUPINGS`` is handed to the trace rung's check by falling through to it,
    so the row that comes back names the rung that could not answer -- the stub's slot is the
    fact, and a later release may replace that row with a resolution at that same rung. Every
    other name is checked here, and a requested grouping that passes reads ``resolved_by ==
    "requested"`` -- except ``WHOLE_GRID``, which is the whole-grid rung answering and says so.
    """
    name = request.requested
    if name is None or name in request.seen or name in TRACE_GROUPINGS:
        return None
    if name == WHOLE_GRID:
        return _whole_grid(request)
    declared_a = name in request.manifest_a.axis_types
    declared_b = name in request.manifest_b.axis_types
    if declared_a or declared_b:
        if not (declared_a and declared_b):
            missing = "b" if declared_a else "a"
            return Refusal(
                key=name,
                rung="requested",
                reason="not_shared",
                detail=(
                    f"run {missing} does not declare {name!r} as an axis, so the two runs share "
                    "no grouping by it."
                ),
                next_rung="trace",
                n_groups=None,
                n_resolvable_groups=None,
                offered_max_group_mde=None,
            )
        return _consider(
            request, name, rung="requested", next_rung="trace", resolved_by="requested"
        )
    if name in TASK_FAMILY_KEYS and _carried_by_every_cell(request, name):
        return _consider(
            request, name, rung="requested", next_rung="trace", resolved_by="requested"
        )
    raise UnknownGrouping(
        f"--by {name}: no rung groups by that. Name an axis both runs "
        f"declare ({', '.join(_shared_axes(request)) or 'none'}), a task-family key the configs "
        f"carry ({', '.join(TASK_FAMILY_KEYS)}), or {WHOLE_GRID}."
    )


def _rung_trace(request: _Request) -> Grouping | Refusal | None:
    """A later release fills this body and moves no entry in ``RUNG_ORDER``.

    It reads nothing today -- not ``request.frames``, which is what it will read -- and offers
    nothing unless a trace grouping was asked for, in which case it raises the named stub and the
    walker records the row. Without a ``--by`` no row of the chain is ever at this rung.
    """
    name = request.requested
    if name is None or name in request.seen or name not in TRACE_GROUPINGS:
        return None
    raise TraceGroupingUnsupported(name)


def _rung_axis(request: _Request) -> Grouping | Refusal | None:
    """The sweep's declared axes, in **arm A's** declared order, intersected with arm B's.

    Not sorted, not by group count, not the union. Declared order is the rule until a
    measured substrate shows it choosing the wrong passing axis, and A's order is the one a
    reader of the baseline manifest can predict.
    """
    candidates = [key for key in request.manifest_a.axis_types if key not in request.seen]
    if not candidates:
        return None
    key = candidates[0]
    next_rung = "axis" if candidates[1:] else "task_family"
    if key not in request.manifest_b.axis_types:
        return Refusal(
            key=key,
            rung="axis",
            reason="not_shared",
            detail=(
                f"run b does not declare {key!r} as an axis, so the two runs share no grouping "
                "by it."
            ),
            next_rung=next_rung,
            n_groups=None,
            n_resolvable_groups=None,
            offered_max_group_mde=None,
        )
    return _consider(request, key, rung="axis", next_rung=next_rung, resolved_by="axis")


def _carried_by_every_cell(request: _Request, key: str) -> bool:
    return all(key in config for config in request.table.configs)


def _shared_axes(request: _Request) -> list[str]:
    return [key for key in request.manifest_a.axis_types if key in request.manifest_b.axis_types]


def _rung_task_family(request: _Request) -> Grouping | Refusal | None:
    """The task-family keys, read from the **configs** rather than from ``axis_types``.

    Vacuous on every store this project has: the task key is a declared axis everywhere, so the
    axis rung tries and refuses it first and this rung skips it without a second row. It exists
    for an imported run whose manifest was written after the fact and declares fewer axes than
    its configs carry, and a test fixture is what keeps it from being dead code.
    """
    candidates = [
        key
        for key in TASK_FAMILY_KEYS
        if key not in request.seen and _carried_by_every_cell(request, key)
    ]
    if not candidates:
        return None
    key = candidates[0]
    next_rung = "task_family" if candidates[1:] else "whole_grid"
    return _consider(
        request, key, rung="task_family", next_rung=next_rung, resolved_by="task_family"
    )


def _whole_grid(request: _Request) -> Grouping:
    """One group over every comparable cell. This rung never refuses, which is what guarantees
    the resolver always finds a grouping and lets every rung above it fall through."""
    partition = {WHOLE_GRID_LABEL: list(range(len(request.table.hashes)))}
    labels = (WHOLE_GRID_LABEL,)
    mdes = _group_mdes(request.table, partition, labels, request.q)
    return _grouping(
        request,
        WHOLE_GRID_KEY,
        "whole_grid",
        partition,
        labels,
        request.q,
        mdes,
        sum(1 for value in mdes if value <= request.max_group_mde),
    )


_RUNGS: Mapping[str, Any] = {
    "requested": _rung_requested,
    "trace": _rung_trace,
    "axis": _rung_axis,
    "task_family": _rung_task_family,
    "whole_grid": _whole_grid,
}


def resolve_grouping(
    requested: str | None,
    *,
    manifest_a: RunManifest,
    manifest_b: RunManifest,
    units: pd.DataFrame,
    q: float,
    max_group_mde: float | None = None,
    frames: tuple[pd.DataFrame, pd.DataFrame] | None = None,
) -> Grouping:
    """Walk ``RUNG_ORDER`` until a rung offers a grouping, recording every refusal on the way.

    Each rung returns a ``Grouping`` (resolved, stop), a ``Refusal`` (record it, try again) or
    ``None`` (nothing to offer here, go on). A rung that refuses is re-entered so it can pass
    over a second candidate of its own -- the axis rung refuses one axis and reaches the next --
    and the key it refused is in the chain, so no later rung says the same thing twice.

    ``frames`` is unread: it is what the trace rung will read in a later release, and the resolver's
    output is identical whether it is passed or not.
    """
    request = _Request(
        requested=requested,
        manifest_a=manifest_a,
        manifest_b=manifest_b,
        table=_cell_table(units),
        q=float(q),
        max_group_mde=_require_max_group_mde(max_group_mde),
        frames=frames,
    )
    for rung in RUNG_ORDER:
        while True:
            try:
                outcome = _RUNGS[rung](request)
            except TraceGroupingUnsupported as unsupported:
                outcome = _trace_refusal(str(unsupported))
            if not isinstance(outcome, Refusal):
                break
            request.refused.append(outcome)
            request.seen.add(outcome.key)
        if isinstance(outcome, Grouping):
            return replace(outcome, refused=tuple(request.refused))
    raise TreeError(  # pragma: no cover - the whole-grid rung never returns anything else
        "no rung offered a grouping, which the whole-grid rung is there to make impossible"
    )


# ---------- Level 2, on the root's own draws ----------


def _fault_lines(
    root: RootResult,
    grouping: Grouping,
    design: _Design,
    observed: NDArray[np.float64],
    permuted: NDArray[np.float64],
) -> FaultLines:
    """Every group's statistics from row slices of the root's own observed and permuted deltas.

    **Slice the deltas, not the statistics.** A group's location is a mean over its own ``C_g``
    cells; a row slice of the root's mean would be a mean over ``C`` and would be wrong by a
    constant that varies with the grouping.

    **The draws are the root's.** The permuted block is the one ``_draw`` built, grouped
    afterwards, so a group's p is comparable to the root's and to every other group's and no
    second stream exists. A Level 2 that drew its own ``(C_g, W)`` block from the same seed gets
    different bits, which a test pins from the surface.

    **BH over all G, then the gate, then the fields.** ``q_group`` is ``diff.bh`` over every
    group's p with ``m`` the group count; the gate decides whether any of it is computed at all,
    and when it does not, every p-field is ``None`` and nothing is calculated.
    """
    position = {h: index for index, h in enumerate(design.hashes)}
    observed_block = observed[None, :, :]
    n_events = len(root.events)
    tested = bool(root.rejects and grouping.n_groups >= MIN_FAMILY_GROUPS)
    rows_by_label = {
        label: np.array([position[h] for h in grouping.groups[label]], dtype=np.int64)
        for label in grouping.labels
    }

    measured: list[dict[str, Any]] = []
    for index, label in enumerate(grouping.labels):
        rows = rows_by_label[label]
        group_observed = observed_block[:, rows, :]
        location, dispersion, extremeness = _statistics(group_observed)
        informative = int(design.informative[rows].sum())
        record: dict[str, Any] = {
            "label": label,
            "cells": grouping.groups[label],
            "n_cells": len(rows),
            "n_informative_cells": informative,
            "n_uninformative_cells": len(rows) - informative,
            "n_discordant": (
                None if design.discordant is None else int(design.discordant[rows].sum())
            ),
            "n_a": int(design.n_a[rows].sum()),
            "n_b": int(design.n_b[rows].sum()),
            "mde": grouping.group_mde[index],
            "degenerate": informative == 0,
            "location": {e: float(location[0][k]) for k, e in enumerate(root.events)},
            "dispersion": {e: float(dispersion[0][k]) for k, e in enumerate(root.events)},
            "p_location": None,
            "p_dispersion": None,
            "p_group": None,
        }
        if tested:
            group_permuted = permuted[:, rows, :]
            _, _, permuted_extremeness = _statistics(group_permuted)
            p_statistics, p_group = _min_p(extremeness[0], permuted_extremeness)
            record["p_location"] = {
                e: float(p_statistics[k]) for k, e in enumerate(root.events)
            }
            record["p_dispersion"] = {
                e: float(p_statistics[n_events + k]) for k, e in enumerate(root.events)
            }
            record["p_group"] = float(p_group)
        measured.append(record)

    adjusted: list[float | None] = [None] * len(measured)
    if tested:
        raw = np.array([record["p_group"] for record in measured], dtype=np.float64)
        adjusted = [float(value) for value in bh(raw, root.q)]
    groups = tuple(
        GroupResult(
            label=record["label"],
            key=grouping.key,
            cells=record["cells"],
            n_cells=record["n_cells"],
            n_informative_cells=record["n_informative_cells"],
            n_uninformative_cells=record["n_uninformative_cells"],
            n_discordant=record["n_discordant"],
            n_a=record["n_a"],
            n_b=record["n_b"],
            mde=record["mde"],
            degenerate=record["degenerate"],
            location=record["location"],
            dispersion=record["dispersion"],
            p_location=record["p_location"],
            p_dispersion=record["p_dispersion"],
            p_group=record["p_group"],
            q_group=q_group,
            rejects=None if q_group is None else bool(q_group < root.q),
        )
        for record, q_group in zip(measured, adjusted, strict=True)
    )
    rejected = tuple(group.label for group in groups if group.rejects)
    return FaultLines(
        tested=tested,
        reason=None if tested else ("root_not_rejected" if not root.rejects else "one_group"),
        null=GROUP_NULL,
        q=float(root.q),
        n_groups=grouping.n_groups,
        n_degenerate_groups=sum(1 for group in groups if group.degenerate),
        n_rejected_groups=len(rejected),
        rejected_groups=rejected,
        groups=groups,
    )


# ---------- Level 3, on the flat family's own per-cell tests ----------


def _flat_rows(multi: MultiDiffResult) -> dict[str, dict[str, Mapping[str, Any]]]:
    """``multi_diff``'s per-cell rows, per event, indexed by hash.

    The whole of Level 3's input beside the partition. Nothing here draws a permutation,
    touches the root's stream or reads ``units``: the third level is the grid analysis's own
    per-cell test, scoped -- which is what "leaves are 32 against 32" means operationally, and
    is checkable bit for bit against ``cells``.
    """
    return {
        event: {
            str(record["config_hash"]): record
            for record in multi.by_event[event].cells.to_dict(orient="records")
        }
        for event in multi.events
    }


def _family(
    flat: Mapping[str, Mapping[str, Mapping[str, Any]]],
    events: Sequence[str],
    grouping: Grouping,
    label: str,
    q: float,
) -> CellFamily:
    """One rejected group's ``C_g x K`` leaves, BH-corrected within that family alone.

    Rows in the flat family's own order -- sorted hash, events under each hash -- so the
    correction is over an array a reader can reproduce from ``cells``, and so the one-group
    collapse's ``bh`` call is over the same array ``multi_diff`` built, in the same order, which
    is what makes its ``q_within`` equal ``cells.q`` bit for bit rather than nearly.
    """
    rows = [
        (config_hash, event, flat[event][config_hash])
        for config_hash in sorted(grouping.groups[label])
        for event in events
    ]
    adjusted = bh(np.array([float(row["p"]) for _, _, row in rows], dtype=np.float64), q)
    cells = tuple(
        CellResult(
            config_hash=config_hash,
            config=row["config"],
            event=event,
            group=label,
            n_a=int(row["n_a"]),
            n_b=int(row["n_b"]),
            events_a=int(row["events_a"]),
            events_b=int(row["events_b"]),
            delta=float(row["delta"]),
            p=float(row["p"]),
            q_within=float(value),
            rejects=bool(float(value) < q),
            mde=float(row["mde"]),
            mde_note=row.get("mde_note") if isinstance(row.get("mde_note"), str) else None,
        )
        for (config_hash, event, row), value in zip(rows, adjusted, strict=True)
    )
    mdes = [cell.mde for cell in cells if not math.isnan(cell.mde)]
    return CellFamily(
        label=label,
        key=grouping.key,
        n_tests=len(cells),
        n_rejected=sum(1 for cell in cells if cell.rejects),
        rejected=tuple((cell.config_hash, cell.event) for cell in cells if cell.rejects),
        mde_median=float(np.median(mdes)) if mdes else math.nan,
        mde_max=max(mdes) if mdes else math.nan,
        cells=cells,
    )


def _leaves_reason(
    root: RootResult, fault_lines: FaultLines, depth_configured: int
) -> str | None:
    """The first entry of ``LEAVES_NOT_TESTED_REASONS`` that applies, or ``None`` when tested.

    Stated in the tuple's order rather than by a chain of ``if``s, so the precedence lives in
    one place: the procedure's configuration first, then the root, then the level. A grouping
    that collapsed reaches none of them -- Level 2 is not a level there and the root's verdict
    is the gate.
    """
    applies = {
        "depth": depth_configured < DEFAULT_DEPTH,
        "root_not_rejected": not root.rejects,
        "no_group_rejected": fault_lines.tested and fault_lines.n_rejected_groups == 0,
    }
    return next((reason for reason in LEAVES_NOT_TESTED_REASONS if applies[reason]), None)


def _leaves(
    multi: MultiDiffResult,
    root: RootResult,
    grouping: Grouping,
    fault_lines: FaultLines,
    depth_configured: int,
) -> Leaves:
    """Level 3: the cells under each rejecting fault line, and nowhere else.

    **The gate, then the family, then the fields.** No ``CellResult`` exists for a cell under a
    group that did not reject and no ``q_within`` is computed for an untested level: the printed
    set is where a builder who ignores the gate differs, and a number that exists would be read.

    Under the one-group collapse Level 2 is not a level, the labels are the grouping's own one,
    and the family is every common cell x event corrected together -- the flat family, bit for
    bit, which is what makes the collapse a two-level tree rather than a special case.
    """
    reason = _leaves_reason(root, fault_lines, depth_configured)
    families: tuple[CellFamily, ...] = ()
    if reason is None:
        flat = _flat_rows(multi)
        labels = fault_lines.rejected_groups if fault_lines.tested else grouping.labels
        families = tuple(
            _family(flat, root.events, grouping, label, root.q) for label in labels
        )
    return Leaves(
        tested=reason is None,
        reason=reason,
        null=CELL_NULL,
        q=float(root.q),
        n_families=len(families),
        n_tests=sum(family.n_tests for family in families),
        n_rejected=sum(family.n_rejected for family in families),
        families=families,
    )


def _depth(depth_configured: int, grouping: Grouping) -> int:
    """The number of levels the procedure runs: the configured depth, less the collapse.

    The third reader of ``MIN_FAMILY_GROUPS``. The reduction is decided by the grouping's
    **shape** -- one group is the root restated, so the tree the procedure runs is root ->
    cells -- and the shape is fixed before any delta is read, which is why a moved pair and its
    unmoved twin print the same depth. It is not "depth reached": a root that fails to reject,
    or a Level 2 that rejects nothing, leaves this alone.
    """
    collapsed = grouping.n_groups < MIN_FAMILY_GROUPS
    return depth_configured - int(collapsed)


def _bound(depth_configured: int, depth: int, q: float) -> Bound:
    """Yekutieli's outer-nodes bound, minted here and nowhere else.

    The literal ``2`` beside the constant is his (A.7): a rejected outer node has at most one
    rejected ancestor per level, so ``R_Full + |J| <= 2 * R_Full <= 2 * L * R_Outer`` and the
    families tested are at most the discoveries plus one per level. The other two true numbers
    -- his depth-free full-tree bound, and his approximation (5), which is a function of the
    observed discovery counts -- are not computed here or anywhere.
    """
    return Bound(
        depth_configured=depth_configured,
        depth=depth,
        q=q,
        delta_star=DELTA_STAR,
        bound=2 * depth * q * DELTA_STAR,
        discoveries=BOUND_DISCOVERIES,
    )


def tree(
    a: pd.DataFrame,
    b: pd.DataFrame,
    multi: MultiDiffResult,
    *,
    manifest_a: RunManifest,
    manifest_b: RunManifest,
    by: str | None = None,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    seed: int = DEFAULT_SEED,
    max_group_mde: float | None = None,
    depth: int = DEFAULT_DEPTH,
) -> TreeResult:
    """One rebuild, one agreement check, one draw: the root, the grouping, the fault lines, the
    cells under the rejecting ones, and the bound the whole procedure controls at.

    The root comes from the whole design; the grouping is resolved from the root's units and the
    manifests, **before the draw**, so a refused ``--by``, an out-of-range ``--max-group-mde`` or
    a depth outside ``DEPTHS`` costs milliseconds at any number of permutations; and every
    group's statistics are row slices of the same observed and permuted deltas the root was
    calibrated by.

    ``tree(...).root`` is byte-equal to ``omnibus(...)`` on the same inputs and knobs -- the same
    function builds both -- so a caller who wants only the root need not choose between them and
    ``cli.py`` prints both blocks from one draw.

    **``depth`` reaches Level 3 and the bound and nothing above them.** One draw serves all three
    levels, so the root, the grouping and the fault lines are byte-identical at either depth;
    and the bound is computed from the argument and the grouping's shape, never from what the
    run reached.
    """
    depth_configured = _require_depth(depth)
    scheme, common, design, codes, counts, observed, agreement = _prepared(
        a, b, multi, n_permutations=n_permutations, seed=seed
    )
    units = _units(design, multi.events, counts)
    grouping = resolve_grouping(
        by,
        manifest_a=manifest_a,
        manifest_b=manifest_b,
        units=units,
        q=multi.q,
        max_group_mde=max_group_mde,
        frames=(a, b),
    )
    permuted = _draw(design, codes, n_permutations=n_permutations, seed=seed)
    root = _root(
        multi,
        scheme,
        common,
        design,
        units,
        observed,
        permuted,
        n_permutations=n_permutations,
        seed=seed,
    )
    fault_lines = _fault_lines(root, grouping, design, observed, permuted)
    return TreeResult(
        root=root,
        grouping=grouping,
        fault_lines=fault_lines,
        leaves=_leaves(multi, root, grouping, fault_lines, depth_configured),
        bound=_bound(depth_configured, _depth(depth_configured, grouping), float(root.q)),
        agreement=agreement,
    )

__all__ = [
    "AGREEMENT_SCHEMA",
    "BOUND_DISCOVERIES",
    "CELL_NULL",
    "DEFAULT_DEPTH",
    "DEFAULT_MAX_GROUP_MDE",
    "DEFAULT_PERMUTATIONS",
    "DEFAULT_SEED",
    "DELTA_STAR",
    "DEPTHS",
    "GROUP_NULL",
    "LEAVES_NOT_TESTED_REASONS",
    "MIN_FAMILY_GROUPS",
    "MIN_RESOLVABLE_GROUPS",
    "NOT_TESTED_REASONS",
    "REFUSAL_REASONS",
    "ROOT_STATISTICS",
    "RUNG_ORDER",
    "SCHEME_BY_METHOD",
    "TASK_FAMILY_KEYS",
    "TRACE_GROUPINGS",
    "UNITS_COLUMNS",
    "WHOLE_GRID",
    "WHOLE_GRID_KEY",
    "WHOLE_GRID_LABEL",
    "Bound",
    "CellFamily",
    "CellResult",
    "FaultLines",
    "GroupResult",
    "Grouping",
    "Leaves",
    "Refusal",
    "RootResult",
    "Scheme",
    "TraceGroupingUnsupported",
    "TreeError",
    "TreeResult",
    "UnknownGrouping",
    "agreement_digest",
    "omnibus",
    "resolve_grouping",
    "tree",
]
