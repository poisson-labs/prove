"""M14: the dual root -- one permutation-calibrated omnibus over the cells x events family.

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
across cells, and ``Q`` degenerates wherever ``p-hat`` is 0 or 1 -- 77% of cells on the S18
substrate.

Extremeness is ``|location_k|`` (two-sided) and ``dispersion_k`` (upper): a signed location
extremeness would be a one-sided test nobody asked for, and a signed dispersion is meaningless.
One set of ``B`` permutations yields all ``2K`` statistics; each gets a Phipson-Smyth p-value
``p = (1 + #{b : S_b >= S_obs}) / (B + 1)`` and the omnibus is Westfall-Young min-p over them.
**Ties are counted with ``>=``**: discrete outcomes tie constantly at N=32 and ``>`` would be
anti-conservative. That is deliberate and is not a defect to fix.

``diff.py`` does not know this module exists (draft ADR-058). ``omnibus`` consumes the
``MultiDiffResult`` it must agree with -- events, method, ``q``, the horizon and the common
cells are read from it and never re-decided -- plus the raw frames, from which it rebuilds the
cell view with ``diff.py``'s own helpers and refuses if the rebuild disagrees.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from proofload.diff import (
    DiffError,
    Method,
    MultiDiffResult,
    _native,
    _truncate_raw,
)

Scheme = Literal["pair_swap", "arm_label"]

#: Draft ADR-057, spec section 0.2. The scheme follows ``method`` and never the run salt: two
#: runs that happen to share a salt must get the same root as two that do not, or the omnibus
#: becomes a property of run provenance rather than of the request. Written once, read
#: everywhere; nothing below dispatches on anything else.
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


class TreeError(DiffError):
    """A refusal by the nested family.

    Subclasses ``DiffError`` so ``cli``'s ``_REFUSABLE`` already maps it to exit 2 without a
    change to ``cli.py``.
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
    #: the complement without doing the subtraction (spec section 0.4 and invariant O17).
    n_uninformative_cells: int
    n_discordant: int | None
    n_permutations: int
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
    ``events_a`` on any pair whose two arms ran to different horizons; Go1 cannot express that,
    which is exactly why the same call does it here.

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
    count is a printed fact and not a footnote (spec section 0.5); it is a count over
    *outcomes*, so a cell whose only movement is between two outcomes nobody asked about is
    informative here and degenerate in the statistic, which is recorded and not smoothed.
    """
    per_cell: list[tuple[NDArray[np.int16], NDArray[np.int16]]] = []
    configs: list[Any] = []
    informative = 0
    discordant = 0
    for h in common:
        cell_a, cell_b = groups_a[h], groups_b[h]
        configs.append(cell_a["config"].iloc[0])
        if scheme == "pair_swap":
            codes_a, codes_b = _matched(cell_a, cell_b, h)
            differ = int(np.sum(codes_a != codes_b))
            discordant += differ
            informative += int(differ > 0)
        else:
            codes_a = cell_a[_CODE_COLUMN].to_numpy(dtype=np.int16)
            codes_b = cell_b[_CODE_COLUMN].to_numpy(dtype=np.int16)
            pooled = np.concatenate([codes_a, codes_b])
            informative += int(bool(np.any(pooled != pooled[0])))
        per_cell.append((codes_a, codes_b))

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
        n_informative_cells=informative,
        n_discordant=discordant if scheme == "pair_swap" else None,
    )


# ---------- the exchange, and the one place a stream is constructed ----------


def _draw(
    design: _Design,
    codes: Sequence[int],
    *,
    n_permutations: int,
    seed: int,
) -> tuple[
    tuple[NDArray[np.int64], NDArray[np.int64]],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    """``((events_a, events_b), observed deltas, permuted deltas)`` -- ``(C, K)`` and ``(B, C, K)``.

    **The single construction site of the permutation stream** (draft ADR-058). One
    ``default_rng(seed)``, consumed permutation-major, never stored: P4.2's per-group pass gets
    the same draws by calling this function, not by re-deriving the stream. A second
    ``default_rng`` anywhere in the package would be a second stream free to disagree with this
    one, and the oracle's ``ast`` guard exists to stop that arriving.

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
    pooled = design.scheme == "arm_label"
    counts = _counts(design, design.left, design.left if pooled else design.right, codes)
    observed = _deltas(design, counts)
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
    return counts, observed, permuted


def _counts(
    design: _Design,
    arm_a: NDArray[np.int16],
    arm_b: NDArray[np.int16],
    codes: Sequence[int],
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """``(C, K)`` event counts per arm for one arrangement of the codes.

    Under ``arm_label`` both arms read the one pooled matrix through ``in_a`` / ``in_b``, so
    the first ``n_a`` of the permuted pool go to arm a and the per-cell arm sizes survive the
    exchange (spec section 8 trap 5).
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


def _statistics(deltas: NDArray[np.float64]) -> NDArray[np.float64]:
    """``(..., C, K)`` deltas to ``(..., 2K)`` extremeness, location first then dispersion.

    ``|mean|`` and RMS rather than ``|sum|`` and the sum of squares: at a fixed ``C`` per
    family each is a monotone transform of the plan's statistic, so every p-value is the sum's,
    and the number a reader sees is a per-cell movement rather than one that scales with the
    grid. **Unweighted**, and there is nowhere else a weight could enter: this is the one place
    the deltas become a statistic.
    """
    n_cells = deltas.shape[-2]
    location = np.abs(deltas.sum(axis=-2) / n_cells)
    dispersion = np.sqrt((deltas * deltas).sum(axis=-2) / n_cells)
    return np.concatenate([location, dispersion], axis=-1)


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
    to that dependence. Each permutation gets its own rank-p per statistic -- a count that
    **includes the permutation itself**, so its minimum is ``1/B`` -- and the omnibus counts
    the permutations whose min-p reaches the observed one. That last count is what separates
    this from the bare minimum of the ``J`` p-values, which is the quantity Westfall-Young
    exists to correct; the two coincide only when one statistic's extreme set contains the
    other's.
    """
    n_permutations = permuted.shape[0]
    p_observed = _phipson_smyth(observed, permuted)
    rank_p = np.empty_like(permuted)
    for j in range(permuted.shape[1]):
        column = np.sort(permuted[:, j])
        rank_p[:, j] = (
            n_permutations - np.searchsorted(column, permuted[:, j], side="left")
        ) / n_permutations
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


def _require_agreement(
    multi: MultiDiffResult,
    common: Sequence[str],
    groups_a: Mapping[str, pd.DataFrame],
    groups_b: Mapping[str, pd.DataFrame],
    codebook: Mapping[Any, int],
) -> None:
    """The rebuild guard: episode counts recomputed from the frames must equal ``cells``.

    The root is a *second* construction of something ``multi_diff`` already built, and this is
    the check that makes the second construction safe. It compares the episode-level counts --
    the four columns ``multi_diff`` itself wrote -- rather than the root's own units, because
    under ``pair_swap`` the unit is the matched pair and an unmatched replicate legitimately
    makes ``units`` smaller than ``cells``. What may not differ is what the two objects both
    claim to have counted from the same frames. When it does, the caller handed the root a
    different pair than the diff, and the refusal names the first mismatching cell in
    sorted-hash order.
    """
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


# ---------- the public function ----------


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
    _require_agreement(multi, common, groups_a, groups_b, codebook)

    design = _design(scheme, common, groups_a, groups_b)
    # A requested event nobody ran gets a code no outcome carries, so its incidence is zero in
    # both arms rather than an error -- the posture ``multi_diff`` already takes.
    codes = [codebook.get(event, _PAD) for event in multi.events]
    counts, observed, permuted = _draw(
        design, codes, n_permutations=n_permutations, seed=seed
    )

    n_events = len(multi.events)
    observed_statistics = _statistics(observed[None, :, :])[0]
    permuted_statistics = _statistics(permuted)
    p_statistics, omnibus_p = _min_p(observed_statistics, permuted_statistics)
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
        seed=seed,
        units=_units(design, multi.events, counts),
        location={e: float(np.mean(observed[:, i])) for i, e in enumerate(multi.events)},
        dispersion={
            e: math.sqrt(float(np.mean(observed[:, i] * observed[:, i])))
            for i, e in enumerate(multi.events)
        },
        p_location={e: float(p_statistics[i]) for i, e in enumerate(multi.events)},
        p_dispersion={e: float(p_statistics[n_events + i]) for i, e in enumerate(multi.events)},
        p_omnibus=float(omnibus_p),
        rejects=bool(omnibus_p < multi.q),
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


__all__ = [
    "DEFAULT_PERMUTATIONS",
    "DEFAULT_SEED",
    "ROOT_STATISTICS",
    "SCHEME_BY_METHOD",
    "UNITS_COLUMNS",
    "RootResult",
    "Scheme",
    "TreeError",
    "omnibus",
]
