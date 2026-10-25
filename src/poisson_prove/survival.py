"""M5: per-cell survival estimation.

Derives censoring from a declared event, fits Kaplan-Meier or Aalen-Johansen per cell,
attaches Wilson and Greenwood intervals, and returns the cell table M6 diffs and M7
draws. Everything is hand-rolled in numpy. A cell is the set of rows sharing a
``config_hash``; this module never reads the grid.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

_MEDIAN_TOL = 1e-9

CELL_TABLE_COLUMNS = (
    "config_hash",
    "config",
    "n",
    "n_errored",
    "n_events",
    "event_rate",
    "event_rate_lo",
    "event_rate_hi",
    "event_rate_level",
    "s_at_horizon",
    "s_var_at_horizon",
    "median_t",
    "curve",
)


class SurvivalError(Exception):
    """A frame or argument violates what the estimators require."""


# ---------- curves ----------


def _step_index(times: FloatArray, t: float) -> int:
    """Index of the last time <= t for a right-continuous step function, or -1."""
    return int(np.searchsorted(times, t, side="right")) - 1


@dataclass(frozen=True, eq=False)
class KMCurve:
    """Kaplan-Meier estimate at each distinct event time, ascending."""

    times: FloatArray
    survival: FloatArray
    var: FloatArray
    n_at_risk: IntArray
    n_events: IntArray

    def at(self, t: float) -> float:
        i = _step_index(self.times, t)
        return 1.0 if i < 0 else float(self.survival[i])

    def median(self) -> float | None:
        hits = np.flatnonzero(self.survival <= 0.5 + _MEDIAN_TOL)
        return None if len(hits) == 0 else float(self.times[hits[0]])


@dataclass(frozen=True, eq=False)
class CIFCurve:
    """Aalen-Johansen cumulative incidence per competing event, at each event time."""

    times: FloatArray
    cif: Mapping[str, FloatArray]

    def at(self, outcome: str, t: float) -> float:
        if outcome not in self.cif:
            raise SurvivalError(f"unknown outcome {outcome!r}; curve has {sorted(self.cif)}")
        i = _step_index(self.times, t)
        return 0.0 if i < 0 else float(self.cif[outcome][i])


# ---------- estimators ----------


def kaplan_meier(t: NDArray[Any], observed: NDArray[Any]) -> KMCurve:
    """The Kaplan-Meier survival curve of times ``t``, ``observed`` true where the event happened
    and false where the time was censored, with Greenwood's variance at each event time."""
    tt = np.asarray(t, dtype=np.float64)
    obs = np.asarray(observed, dtype=bool)
    if tt.shape != obs.shape or tt.ndim != 1:
        raise SurvivalError("t and observed must be 1-d arrays of the same length")
    times = np.unique(tt[obs])
    n_at_risk = np.array([np.sum(tt >= x) for x in times], dtype=np.int64)
    n_events = np.array([np.sum((tt == x) & obs) for x in times], dtype=np.int64)
    n = n_at_risk.astype(np.float64)
    d = n_events.astype(np.float64)
    survival: FloatArray = np.cumprod((n - d) / n, dtype=np.float64)
    # Greenwood: sum d / (n (n - d)); the n == d term is undefined and taken as 0, which
    # holds the sum at its last finite value (lifelines does the same).
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(n > d, d / (n * (n - d)), 0.0)
    var = survival**2 * np.cumsum(term)
    return KMCurve(times=times, survival=survival, var=var, n_at_risk=n_at_risk, n_events=n_events)


def aalen_johansen(
    t: NDArray[Any], outcome: NDArray[Any], events: Sequence[str]
) -> CIFCurve:
    """Competing risks. Rows whose outcome is not in `events` are censored."""
    tt = np.asarray(t, dtype=np.float64)
    out = np.asarray(outcome, dtype=object)
    if tt.shape != out.shape or tt.ndim != 1:
        raise SurvivalError("t and outcome must be 1-d arrays of the same length")
    keys = list(dict.fromkeys(events))
    if not keys:
        raise SurvivalError("events must name at least one outcome")
    is_event = np.isin(out, keys)
    times = np.unique(tt[is_event])
    cif = {k: np.zeros(len(times), dtype=np.float64) for k in keys}
    s_prev = 1.0  # overall survival S(t-) across all competing events
    for i, x in enumerate(times):
        n = float(np.sum(tt >= x))
        at_x = tt == x
        d_total = 0.0
        for k in keys:
            d_k = float(np.sum(at_x & (out == k)))
            prev = cif[k][i - 1] if i else 0.0
            cif[k][i] = prev + s_prev * d_k / n
            d_total += d_k
        s_prev *= (n - d_total) / n
    return CIFCurve(times=times, cif=cif)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0 or k < 0 or k > n:
        raise SurvivalError(f"wilson needs 0 <= k <= n with n > 0, got k={k}, n={n}")
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    lo = 0.0 if k == 0 else max(0.0, center - half)
    hi = 1.0 if k == n else min(1.0, center + half)
    return lo, hi


# ---------- frame helpers ----------


def censor(df: pd.DataFrame, event: str) -> pd.DataFrame:
    """Return df with an added bool column `observed` = (outcome == event).

    Errored rows (outcome null) are dropped and their count is attached as
    df.attrs['n_errored']. `t` is unchanged.
    """
    errored = df["outcome"].isna()
    out = df.loc[~errored].reset_index(drop=True)
    out["observed"] = (out["outcome"] == event).to_numpy(dtype=bool)
    out.attrs["n_errored"] = int(errored.sum())
    return out


def competing_set(*frames: pd.DataFrame) -> tuple[str, ...]:
    """Every distinct non-null ``outcome`` across all frames, sorted.

    Empty frames contribute nothing. This is the ONLY supported way to build the event set
    passed to aalen_johansen / cell_table (ADR-021): every terminal outcome present is an
    absorbing competing risk, whether or not its CIF is being reported.
    """
    present: set[str] = set()
    for df in frames:
        present.update(str(o) for o in df["outcome"].dropna().unique())
    return tuple(sorted(present))


def multi_outcome_guard(df: pd.DataFrame, event: str) -> list[str]:
    """Distinct non-event terminal outcomes present, when there is more than one.

    Non-empty means single-event KM will treat competing events as censoring.
    """
    present = df["outcome"].dropna().unique().tolist()
    others = sorted(str(o) for o in present if o != event)
    return others if len(others) > 1 else []


def _early_others(df: pd.DataFrame, event: str, horizon: float) -> list[str]:
    """The outcomes other than ``event`` that end a run before the horizon, sorted: what
    Kaplan-Meier treats as censoring when it is a competing ending (PF4.19). An outcome seen only
    at the horizon ends no run early."""
    valid = df.loc[df["outcome"].notna()]
    early = valid.loc[(valid["outcome"] != event) & (valid["t"].astype(float) < horizon), "outcome"]
    return sorted({str(o) for o in early})


def _single_horizon(df: pd.DataFrame, horizon: float | None) -> float:
    present = df["horizon"].dropna().unique()
    if len(present) > 1:
        raise SurvivalError(f"mixed horizons within a run: {sorted(float(h) for h in present)}")
    if horizon is not None:
        return float(horizon)
    if len(present) == 0:
        raise SurvivalError("frame has no horizon and none was given")
    return float(present[0])


def cell_table(
    df: pd.DataFrame,
    event: str,
    *,
    horizon: float | None = None,
    method: Literal["km", "aj"] = "km",
    events: Sequence[str] | None = None,
) -> pd.DataFrame:
    """One row per config_hash, sorted, with the columns in CELL_TABLE_COLUMNS."""
    if method not in ("km", "aj"):
        raise SurvivalError(f"method must be 'km' or 'aj', got {method!r}")
    h = _single_horizon(df, horizon)
    if method == "km":
        competing = _early_others(df, event, h)
        if competing:
            warnings.warn(
                f"single-event KM for {event!r} treats competing outcomes as censoring: "
                f"{competing}; consider method='aj'",
                UserWarning,
                stacklevel=2,
            )
        aj_events: list[str] = []
    else:
        aj_events = list(dict.fromkeys(events)) if events is not None else [event]
        if event not in aj_events:
            raise SurvivalError(f"events {aj_events} must include the declared event {event!r}")

    # PF4.1b: the share's Wilson interval at the level every surface reads, recorded beside it,
    # read when the table is computed. ``stats`` is imported here because it imports this module.
    from poisson_prove import stats

    level = stats.WILSON_LEVEL
    rows: list[dict[str, Any]] = []
    for config_hash, cell in df.groupby("config_hash", sort=True):
        valid = censor(cell, event)
        n = int(len(valid))
        n_errored = int(valid.attrs["n_errored"])
        n_events = int(valid["observed"].sum())
        t = valid["t"].to_numpy(dtype=np.float64)
        observed = valid["observed"].to_numpy(dtype=bool)
        km = kaplan_meier(t, observed)
        curve: KMCurve | CIFCurve
        if method == "km":
            curve = km
            s_h = km.at(h)
            var_h = _var_at(km, h)
        else:
            outcome = valid["outcome"].to_numpy(dtype=object)
            curve = aalen_johansen(t, outcome, aj_events)
            s_h = 1.0 - sum(curve.at(k, h) for k in aj_events)
            var_h = _var_at(kaplan_meier(t, np.isin(outcome, aj_events)), h)
        if n > 0:
            rate = n_events / n
            interval = stats.wilson(n_events, n, level=level)
            lo, hi = interval.lo, interval.hi
        else:
            rate = lo = hi = s_h = var_h = float("nan")
        rows.append(
            {
                "config_hash": str(config_hash),
                "config": cell["config"].iloc[0],
                "n": n,
                "n_errored": n_errored,
                "n_events": n_events,
                "event_rate": rate,
                "event_rate_lo": lo,
                "event_rate_hi": hi,
                "event_rate_level": level,
                "s_at_horizon": s_h,
                "s_var_at_horizon": var_h,
                "median_t": km.median(),
                "curve": curve,
            }
        )
    table = pd.DataFrame.from_records(rows, columns=list(CELL_TABLE_COLUMNS))
    for col in ("config", "median_t", "curve"):
        table[col] = table[col].astype(object)
    return table


def _var_at(curve: KMCurve, t: float) -> float:
    i = _step_index(curve.times, t)
    return 0.0 if i < 0 else float(curve.var[i])
