"""M3: the local executor.

Turns a ``SweepSpec`` into a completed run in the store: one seed per (config, replicate),
one call of the user's ``rollout`` per pair, every misbehavior caught and recorded as an
errored row, episodes written in resumable batches, and the run marked complete. Serial
and in-process by design; it is the reference behavior the Modal backend must match.

M3 mints the four manifest fields no other module owns: ``run_id``, ``run_salt``,
``backend``, ``environment``.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import math
import multiprocessing
import os
import platform
import signal
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from types import FrameType
from typing import Any

from poisson_prove import __version__, _look, stats
from poisson_prove import capture as capture_module
from poisson_prove._limits import Design, design
from poisson_prove.capture import CaptureSpec, CaptureStatus, Recorder, capture, install
from poisson_prove.chaos import (
    ChaosError,
    ChaosSpec,
    ChaosStatus,
    FaultRecord,
    _installed_hooks,
    injecting,
)
from poisson_prove.chaos import install as chaos_install
from poisson_prove.diff import mde_two_proportion
from poisson_prove.episode import Episode
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store, StoreError
from poisson_prove.trace import (
    ALIAS_MAP_VERSION,
    OTEL_SEMCONV_VERSION,
    Declaration,
    Trace,
    TraceValidationError,
    finalize,
    merge,
)

Rollout = Callable[[Mapping[str, Any], int], Episode]

_LOG = logging.getLogger(__name__)

_TIMEOUT_ERROR = "timeout"
_POLL_STEP_S = 0.05
_JOIN_GRACE_S = 5.0
#: How long the parent waits, after SIGTERM, for the child's handler to drain its snapshot.
_DRAIN_GRACE_S = 2.0
_PROBE_TIMEOUT_S = 60.0


class ExecutorError(Exception):
    """A run cannot be planned or executed as requested."""


class NotResumable(ExecutorError):
    """The run named by ``resume=`` cannot be continued."""


class PairMismatch(ExecutorError):
    """The run named by ``pair_with=`` cannot be paired with this spec."""


class UnderpoweredDesign(ExecutorError):
    """The design cannot resolve an effect as small as the caller accepts.

    Carries the numbers the refusal is about, so a caller can name the override it offers
    without computing anything: ``mde`` (the design's), ``accepted``, ``replicates`` (the
    design's N), ``replicates_needed`` (the smallest N reaching ``accepted``) and ``offered``
    (the ``--max-mde`` that admits this design, rounded up).
    """

    def __init__(
        self,
        message: str,
        *,
        mde: float | None = None,
        accepted: float | None = None,
        replicates: int | None = None,
        replicates_needed: int | None = None,
        offered: float | None = None,
        most_conditions: int | None = None,
    ) -> None:
        super().__init__(message)
        self.most_conditions = most_conditions
        self.mde = mde
        self.accepted = accepted
        self.replicates = replicates
        self.replicates_needed = replicates_needed
        self.offered = offered


# ---------- identity ----------


def derive_seed(run_salt: str, config_hash: str, replicate_index: int) -> int:
    """Deterministic 32-bit seed: SHA-256 of ``salt:hash:replicate``, first 4 bytes big-endian."""
    digest = hashlib.sha256(f"{run_salt}:{config_hash}:{replicate_index}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def new_run_salt() -> str:
    return os.urandom(8).hex()


def new_run_id(target_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{os.urandom(2).hex()}"


# ---------- plan ----------


@dataclass(frozen=True)
class Pair:
    config: dict[str, Any]
    config_hash: str
    replicate_index: int
    seed: int


@dataclass(frozen=True)
class Plan:
    spec: SweepSpec
    run_id: str
    run_salt: str
    backend: str
    pairs: tuple[Pair, ...]
    resumed: bool
    already_stored: int
    import_path: str | None = None
    #: What the launcher said it accepts as a minimum detectable effect, or None for "nothing
    #: was said". Set at plan time and read by the runners, exactly as ``import_path`` is: a
    #: value the CLI supplies purely so the manifest can record it. ``check_power`` reads it
    #: and never writes it.
    max_mde_accepted: float | None = None
    #: The name given at sweep time, recorded in the new run's manifest.
    name: str | None = None
    #: Under ``pair_with=``, the earlier run's replicates: the gate then asks the paired test, its
    #: pairs the smaller of the two runs' (PF4.30). None for a run paired with nothing.
    paired_replicates: int | None = None


def _all_keys(spec: SweepSpec) -> list[tuple[str, int]]:
    return [(h, k) for h in spec.cells() for k in range(spec.replicates)]


def _manifest_or_raise(store: Store, run_id: str, error: type[ExecutorError]) -> RunManifest:
    try:
        return store.manifest(run_id)
    except StoreError as exc:
        raise error(f"run {run_id!r} is not in the store: {exc}") from exc


def plan(
    spec: SweepSpec,
    store: Store,
    *,
    backend: str = "local",
    run_salt: str | None = None,
    pair_with: str | None = None,
    resume: str | None = None,
    import_path: str | None = None,
    max_mde_accepted: float | None = None,
) -> Plan:
    """Build the ordered list of (config, replicate, seed) pairs for a run.

    pair_with=<run_id>: inherit that run's salt; t_unit must match.
    resume=<run_id>: reuse that run's id + salt; pairs = store.missing(...).
    run_salt, pair_with, resume are mutually exclusive; none -> new salt.
    import_path, when given, is recorded at manifest.environment["import_path"] by
    run_local, matching the Modal backend; the executor still receives the callable.
    max_mde_accepted rides the plan the same way, for manifest.environment["max_mde_accepted"];
    None means the launcher said nothing and the runners record DEFAULT_MAX_MDE.
    """
    options = (("run_salt", run_salt), ("pair_with", pair_with), ("resume", resume))
    given = [name for name, value in options if value is not None]
    if len(given) > 1:
        raise ExecutorError(f"{' and '.join(given)} are mutually exclusive")

    resumed = False
    already_stored = 0
    paired_replicates: int | None = None
    wanted: list[tuple[str, int]] | None = None

    if resume is not None:
        manifest = _manifest_or_raise(store, resume, NotResumable)
        if manifest.status == "complete":
            raise NotResumable(f"run {resume!r} is already complete")
        if manifest.target_id != spec.target_id:
            raise NotResumable(
                f"run {resume!r} targets {manifest.target_id!r}, spec targets {spec.target_id!r}"
            )
        if manifest.t_unit != spec.t_unit:
            raise NotResumable(
                f"run {resume!r} uses t_unit {manifest.t_unit!r}, spec uses {spec.t_unit!r}"
            )
        if dict(manifest.axis_types) != dict(spec.axis_types):
            raise NotResumable(f"run {resume!r} has different axis_types than the spec")
        recorded, declared = _recorded_cap(manifest), _spec_declaration(spec)
        if (None if recorded is None else recorded[1]) != declared:
            raise NotResumable(f"run {resume!r} {_reads(recorded)}, spec {_declares(declared)}")
        if manifest.declared != _spec_declared(spec):
            raise NotResumable(
                f"run {resume!r} {_recorded_declaration(manifest.declared)}, "
                f"spec {_declares_declaration(_spec_declared(spec))}"
            )
        run_id = resume
        salt = manifest.run_salt
        wanted = store.missing(resume, _all_keys(spec))
        already_stored = len(spec.configs) * spec.replicates - len(wanted)
        resumed = True
    elif pair_with is not None:
        manifest = _manifest_or_raise(store, pair_with, PairMismatch)
        if manifest.t_unit != spec.t_unit:
            raise PairMismatch(
                f"run {pair_with!r} uses t_unit {manifest.t_unit!r}, spec uses {spec.t_unit!r}"
            )
        run_id = new_run_id(spec.target_id)
        salt = manifest.run_salt
        recorded = (manifest.environment.get("sweep") or {}).get("replicates")
        paired_replicates = int(recorded) if recorded is not None else spec.replicates
    else:
        run_id = new_run_id(spec.target_id)
        salt = run_salt if run_salt is not None else new_run_salt()

    by_hash = dict(zip(spec.cells(), spec.configs, strict=True))
    keys = wanted if wanted is not None else _all_keys(spec)
    pairs = tuple(
        Pair(
            config=dict(by_hash[h]),
            config_hash=h,
            replicate_index=k,
            seed=derive_seed(salt, h, k),
        )
        for h, k in keys
    )
    return Plan(
        spec=spec,
        run_id=run_id,
        run_salt=salt,
        backend=backend,
        pairs=pairs,
        resumed=resumed,
        already_stored=already_stored,
        import_path=import_path,
        max_mde_accepted=max_mde_accepted,
        paired_replicates=paired_replicates,
    )


# ---------- power ----------

#: The largest minimum detectable effect a sweep may carry without saying so on the command
#: line. A policy choice, stated rather than derived: the MDE at base rate 0.5 is roughly
#: ``1.98 / sqrt(N)``, so 0.20 is about a hundred replicates per cell, and below that a cell
#: cannot see a twenty-point move. It refuses **both** designs this project has actually run --
#: S18 and the Go1 sweep, both N=32, both 0.3251 -- and a default that let those through would
#: be calibrated to let everything through. Go1 still produced a real finding, because its
#: effects were enormous, and that is the case ``--max-mde`` exists for: it proceeds under
#: ``--max-mde 0.35``, which states on the command line that it was only ever looking for
#: effects bigger than thirty-five points.
#:
#: Deliberately not readable from the environment: a threshold set once in a shell profile is a
#: threshold nobody ever sees again, which is the defect this gate exists to fix.
DEFAULT_MAX_MDE: float = 0.20

#: The bisection for the suggested replicate count never needs to look past this.
_N_SEARCH_LIMIT = 1 << 62


def preflight_mde(spec: SweepSpec) -> float:
    """The design's minimum detectable effect, at base rate 0.5, in event-rate points.

    **The one construction.** Both pre-flight lines read this function, and so does everything
    S23 builds on it, so a change to the statistic cannot move the printed number without
    moving whatever is compared against it (W2). It was computed inline in ``preflight`` and
    ``preflight_modal`` would have been a second site.

    Base rate 0.5 is the right design-time anchor: it needs no data, and there is none before
    the run. It is **not** an upper bound over the cells. ``mde_two_proportion`` guards a rate
    of exactly 0 with ``0.5/n`` and returns the largest possible increase when even that is
    undetectable, so cells at extreme base rates exceed this value -- measured on the Go1
    fixture, the realised per-cell maximum was 0.34 against this function's 0.3251, 1.6 points
    higher. That gap is why the printed line no longer calls itself the largest case; anyone
    tempted to make it exact should note that an exact number needs the base rates, and those
    do not exist before the run.
    """
    return mde_two_proportion(0.5, spec.replicates, spec.replicates)


def _offered_override(mde: float) -> float:
    """The ``--max-mde`` value the refusal tells the reader to paste, and it has to work.

    Rounded **up** at four decimals, which is the precision the pre-flight prints. Rounding to
    nearest is the trap: the true MDE at N=32 is 0.32510999..., the pre-flight shows 0.3251,
    and ``--max-mde 0.3251`` refuses the same design again. A message whose one instruction
    does not work is the whole interaction failing.
    """
    offered = math.ceil(mde * 1e4) / 1e4
    # ``mde * 1e4`` can round down across a four-decimal boundary; the offer has to clear the
    # gate, so it is checked rather than argued.
    return offered if offered >= mde else offered + 1e-4


#: The comparison's default ``q``: the gate asks each lone condition's flag at ``q / M`` (PF4.30).
_GATE_Q = 0.05


def _design_events(declared: Declaration | None) -> int:
    """Section 8.10's count of the events a comparison of a sweep will test: the outcomes it
    declares failures or successes; with no kinds, its declared outcomes but one; with no
    outcomes, one."""
    if declared is None:
        return 1
    kinds = len(declared.failures) + len(declared.successes)
    if kinds:
        return kinds
    return max(1, len(declared.outcomes) - 1)


def _design(spec: SweepSpec, *, threshold: float, paired_replicates: int | None) -> Design:
    """The gate's reading of a design (section 8.10): Fisher's test, or the paired test with
    independent arms when the run is paired with an earlier one, over the conditions times the
    events, at the worst base rate with room for the accepted change."""
    test = "fisher" if paired_replicates is None else "mcnemar"
    n_a = spec.replicates if paired_replicates is None else paired_replicates
    return design(
        conditions=len(spec.configs), events=_design_events(_spec_declared(spec)), n_a=n_a,
        n_b=spec.replicates, threshold=threshold, q=_GATE_Q, power=stats.POWER, test=test,
    )


def _plan_design(p: Plan) -> Design:
    """The gate's reading of the plan's design at the change the launcher accepts."""
    return _design(p.spec, threshold=_accepted_mde(p), paired_replicates=p.paired_replicates)


def _design_record(p: Plan) -> dict[str, Any]:
    """What a new run's manifest records as ``design_mde`` on every backend (PF4.30, PF4.48a)."""
    return _plan_design(p).record()


def _recorded_design(manifest: RunManifest) -> dict[str, Any] | None:
    """PF4.4: the design limit a run recorded at sweep time; for a run that recorded none (every
    0.0.1 run), the gate's reading of its recorded replicates, conditions and declaration,
    computed now and labelled so. None when the run recorded no replicates."""
    recorded = manifest.environment.get("design_mde")
    if isinstance(recorded, Mapping) and "test" in recorded:
        return {**dict(recorded), "computed_at_read_time": False}
    sweep = manifest.environment.get("sweep")
    if not isinstance(sweep, Mapping) or sweep.get("replicates") is None:
        return None
    replicates = int(sweep["replicates"])
    accepted = manifest.environment.get("max_mde_accepted")
    found = design(
        conditions=max(1, len(sweep.get("configs") or ())),
        events=_design_events(manifest.declared),
        n_a=replicates,
        n_b=replicates,
        threshold=DEFAULT_MAX_MDE if accepted is None else float(accepted),
        q=_GATE_Q,
        power=stats.POWER,
        test="fisher",
    )
    return {**found.record(), "computed_at_read_time": True}


def _smallest_passing(spec: SweepSpec, accepted: float, paired_replicates: int | None) -> int:
    """The fewest replicates at which the gate passes ``accepted``, by doubling then bisection on
    N; under ``--pair-with`` the earlier run's replicates move with N, as a fresh pair's would."""
    def passes(n: int) -> bool:
        paired = None if paired_replicates is None else n
        resized = replace(spec, replicates=n)
        return _design(resized, threshold=accepted, paired_replicates=paired).passes

    lo, hi = spec.replicates, max(spec.replicates + 1, 2)
    while not passes(hi) and hi < _N_SEARCH_LIMIT:
        lo, hi = hi, hi * 2
    while lo + 1 < hi:
        middle = (lo + hi) // 2
        if passes(middle):
            hi = middle
        else:
            lo = middle
    return hi


def _smallest_accepted(
    spec: SweepSpec, accepted: float, paired_replicates: int | None
) -> float | None:
    """The smallest ``--max-mde`` at three decimals, at or above ``accepted``, that admits the
    design as it stands; None when only 1, which accepts any design, would. A larger accepted
    change only makes the gate easier to pass (more power at it, fewer base rates with room), so
    a bisection over thousandths finds it."""
    def passes(thousandths: int) -> bool:
        threshold = thousandths / 1000
        return _design(spec, threshold=threshold, paired_replicates=paired_replicates).passes

    lo, hi = max(1, math.ceil(accepted * 1000 - 1e-9)), 999
    if not passes(hi):
        return None
    while lo < hi:
        middle = (lo + hi) // 2
        if passes(middle):
            hi = middle
        else:
            lo = middle + 1
    return lo / 1000


def check_power(p: Plan, *, max_mde: float | None = None) -> None:
    """Refuse a design that cannot resolve an effect as small as the caller accepts.

    Section 8.10's gate (PF4.30): a design passes when a change of the accepted size, from every
    base rate with room for it, would be flagged in one condition alone at the stated power.
    ``max_mde=None`` means ``DEFAULT_MAX_MDE``; any value above 0 and up to 1 is accepted, and 1
    admits every design (PF4.49). On the passing path it returns None and does nothing at all --
    it never prints, never touches the store, and never mutates the plan.

    Raises ``UnderpoweredDesign`` carrying the replicates that pass and, where a limit exists,
    the ``--max-mde`` that admits the design; a design in which no lone condition can be flagged
    is refused with section 8.10's facts and no ``--max-mde`` offer.

    The range check on ``max_mde`` lives here rather than in the CLI, by exact analogy with
    M6's ``0 < q < 1``: the CLI parses a float and decides nothing statistical.
    """
    accepted = DEFAULT_MAX_MDE if max_mde is None else float(max_mde)
    if not 0.0 < accepted <= 1.0:
        raise ExecutorError(f"--max-mde must be above 0 and at most 1, got {accepted!r}")
    found = _design(p.spec, threshold=accepted, paired_replicates=p.paired_replicates)
    if found.passes:
        return
    n = p.spec.replicates
    needed = _smallest_passing(p.spec, accepted, p.paired_replicates)
    if not found.flaggable:
        # How many conditions could each be flagged alone at these replicates: the family whose
        # level q / (K E) is still above the smallest p.
        most = max(0, math.ceil(_GATE_Q / (found.p_min * found.events)) - 1)
        raise UnderpoweredDesign(
            f"no single condition of this design can be flagged: with {n} replicates a side the "
            f"smallest possible p is {_look.fmt_p(found.p_min)}, and a flag needs less than "
            f"{_look.fmt_p(found.level)} (q {_GATE_Q:g} over {found.family} tests)",
            mde=math.nan, accepted=accepted, replicates=n, replicates_needed=needed, offered=None,
            most_conditions=most,
        )
    mde = math.nan if found.mde is None else found.mde
    raise UnderpoweredDesign(
        f"underpowered design: one condition alone would be flagged for a change of {mde:.3f} at "
        f"its worst base rate, {found.base_rate:.3f}, and you accept {accepted:.3f}",
        mde=mde, accepted=accepted, replicates=n, replicates_needed=needed,
        offered=_smallest_accepted(p.spec, accepted, p.paired_replicates),
    )


def _capture_line(spec: CaptureSpec | None) -> str | None:
    """The one ``Capture:`` line of the pre-flight, or None when nothing was requested.

    ADR-027 turns on only what the user named, so the pre-flight names it back to them before
    the prompt. Building this line activates nothing.
    """
    if spec is None:
        return None
    named = ", ".join(spec.instrument) if spec.instrument else "none (OTel API only)"
    return (
        f"Capture: on · instrument: {named} · content: {'on' if spec.content else 'off'} · "
        + ("no span cap" if spec.max_spans is None else f"max {spec.max_spans} spans/episode")
    )


def preflight(p: Plan, *, cost_estimate: str | None = None) -> str:
    """Text block describing the run. Non-interactive; M10 prints it and asks."""
    spec = p.spec
    total = spec.total_rollouts()
    lines = [
        f"Sweep: {len(spec.axis_types)} axes · {len(spec.configs)} cells · "
        f"N={spec.replicates} → {total} rollouts",
        f"Backend: {p.backend} · target: {spec.target_id} · t_unit: {spec.t_unit}",
        f"Cost: {cost_estimate if cost_estimate is not None else '$0 (local)'}",
    ]
    capture_line = _capture_line(spec.capture)
    if capture_line is not None:
        lines.append(capture_line)
    if p.resumed:
        lines.append(f"Resuming {p.run_id}: {p.already_stored} stored, {len(p.pairs)} to run")
    return "\n".join(lines) + "\n"


# ---------- per-episode execution ----------

# Outcome of one rollout call: ("ok", episode_dict) | ("error", payload) | ("timeout", payload).
# Two payload shapes for the two errored kinds, read kind first: the timeout payload is the
# trace dict the terminated child drained, or None; the error payload is the traceback text
# (or "rollout returned <type>, expected Episode"), or -- with a capture call and a trace --
# {"error": text, "meta": {"trace": trace_dict}}, exactly those two keys.
_Outcome = tuple[str, Any]


def _episode_id(config_hash: str, replicate_index: int) -> str:
    """The value stamped as ``poisson_prove.episode``. One spelling, both backends."""
    return f"{config_hash}:{replicate_index}"


@dataclass(frozen=True)
class _CaptureCall:
    """What one episode needs to capture: the request and the two routing keys."""

    spec: CaptureSpec
    run_id: str
    episode_id: str


@dataclass(frozen=True)
class _ChaosCall:
    """What one episode needs to inject: the declared fault, which is a run constant."""

    spec: ChaosSpec


def _merge_capture(meta: dict[str, Any], captured: dict[str, Any]) -> None:
    """Land the captured trace in ``meta["trace"]``, never at the cost of the episode.

    Absent: attach. A valid ``poisson-prove.trace/1`` dict: merge. A ``span_id`` collision: keep
    the rollout's trace, drop the capture, warn once — rewriting span ids to dodge the
    collision would violate M12's "``parent_id`` is never rewritten", and an errored row is
    far worse than a missing trace. Anything else in ``meta["trace"]``: leave it exactly as
    the rollout wrote it.
    """
    existing = meta.get("trace")
    if existing is None:
        meta["trace"] = captured
        return
    try:
        own = Trace.from_dict(existing)
    except TraceValidationError as exc:
        _LOG.warning("capture: meta['trace'] is not a trace dict, keeping it as written: %s", exc)
        return
    try:
        merged = merge(own, Trace.from_dict(captured))
    except TraceValidationError as exc:
        _LOG.warning("capture: keeping the rollout's own trace, dropping the capture: %s", exc)
        return
    meta["trace"] = merged.to_dict()


def _errored(text: str, recorder: Recorder | None) -> str | dict[str, Any]:
    """The error payload: the two-key dict when the recorder holds a trace, the text otherwise.

    ``text`` is already in hand -- ``format_exc()`` runs before this is called -- so a
    ``to_meta()`` that raises can neither replace it nor turn one error into another; it is
    guarded exactly as ``_classify`` guards the ok row. Rule zero (``to_meta()`` is None: no
    span, no drops) is the text too, never a dict with an empty meta.
    """
    if recorder is None:
        return text
    try:
        captured = recorder.to_meta()
    except Exception as exc:  # noqa: BLE001 - a capture never turns one error into another
        _LOG.warning("capture: dropping the capture for this errored episode: %r", exc)
        return text
    if captured is None:
        return text
    return {"error": text, "meta": {"trace": captured}}


def _classify(result: Any, recorder: Recorder | None = None) -> _Outcome:
    if not isinstance(result, Episode):
        # The capture block completed normally and the recorder is full: the same payload a
        # raise takes, around the existing text.
        text = f"rollout returned {type(result).__name__}, expected Episode"
        return ("error", _errored(text, recorder))
    episode_dict = result.to_dict()
    if recorder is not None:
        try:
            captured = recorder.to_meta()
            if captured is not None:
                _merge_capture(episode_dict["meta"], captured)
        except Exception as exc:  # noqa: BLE001 - a capture never errors an ok episode
            _LOG.warning("capture: dropping the capture for this episode: %r", exc)
    return ("ok", episode_dict)


def _call_in_process(
    rollout: Rollout,
    config: dict[str, Any],
    seed: int,
    capture_call: _CaptureCall | None = None,
    chaos_call: _ChaosCall | None = None,
) -> _Outcome:
    """The one funnel every execution path goes through.

    Local-no-timeout calls this in the caller's process, local-with-timeout inside the forked
    child, and both ``worker_batch`` branches the same two ways. Capture is installed here, so
    on the forking paths it is installed in the child and never in the forking parent (C1),
    and the trace is merged before the outcome tuple is built and therefore before anything
    is pickled.

    Injection is scoped here too, *inside* the capture block, so a span the recorder opened is
    already current when a call is intercepted and the fault can be stamped on it. A
    ``ChaosError`` is the one exception that is not turned into an errored episode: a run that
    could not apply the fault it declared is not a measurement of anything, so it propagates
    and the run fails as a run.
    """
    if chaos_call is not None:
        # Memoized, so this is inert in a forked child, which inherited the parent's patched
        # client along with its memo. It is not inert under ``spawn``, where the child has
        # its own interpreter: without it the block would open over an unpatched client and
        # the faulted arm would run as a second control arm.
        chaos_install(chaos_call.spec)
    chaos_scope: contextlib.AbstractContextManager[list[FaultRecord]] = (
        contextlib.nullcontext([]) if chaos_call is None else injecting(chaos_call.spec, seed)
    )
    if capture_call is None:
        with chaos_scope:
            try:
                return _classify(rollout(config, seed))
            except Exception:
                return ("error", traceback.format_exc())
    install(capture_call.spec)  # once per process; inert and memoized after the first call
    try:
        with capture(capture_call.run_id, capture_call.episode_id) as recorder, chaos_scope:
            try:
                return _classify(rollout(config, seed), recorder)
            except Exception:
                # Caught inside the block: the rollout's own spans have already ended (their
                # ``with`` blocks ran before the exception reached here), the recorder is in
                # scope and its bucket is still open. The traceback first -- nothing that runs
                # after it may replace what the user needs -- then the trace, if there is one.
                text = traceback.format_exc()
                return ("error", _errored(text, recorder))
    except ChaosError:
        raise
    except Exception:  # capture() itself failed to open or close: the text, as today
        return ("error", traceback.format_exc())


def _arm_drain(drain: Connection) -> None:
    """Install the child's SIGTERM handler: snapshot, send on the drain pipe, ``os._exit``.

    Only a child with a capture call gets one (C3: a run that did not ask keeps the default
    disposition, and this is the only place the child's signal state is touched). The handler
    runs between two bytecodes of whatever the rollout was doing, so it never returns into it
    -- no ``finally`` blocks, no ``atexit``; the rollout is the thing that hung -- and never
    raises: whatever fails inside it, the parent sees the pipe close and records
    ``("timeout", None)``, exactly as before ADR-028.
    """

    def handler(signum: int, frame: FrameType | None) -> None:
        payload: Any = None
        try:
            payload = capture_module._snapshot(_TIMEOUT_ERROR)
        except BaseException:  # noqa: BLE001 - the drain is best effort
            payload = None
        try:
            drain.send((_TIMEOUT_ERROR, payload))
        except BaseException:  # noqa: BLE001 - nothing arriving is today's outcome
            pass
        finally:
            os._exit(1)

    signal.signal(signal.SIGTERM, handler)


def _child_main(
    conn: Connection,
    drain: Connection,
    rollout: Rollout,
    config: dict[str, Any],
    seed: int,
    capture_call: _CaptureCall | None = None,
    chaos_call: _ChaosCall | None = None,
) -> None:
    # The drain pipe always arrives (E14); only a child with a capture call arms the handler
    # that writes to it, so a run that did not ask keeps the default SIGTERM disposition (C3).
    if capture_call is not None:
        _arm_drain(drain)
    try:
        outcome = _call_in_process(rollout, config, seed, capture_call, chaos_call)
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def _probe_main(conn: Connection, spec: CaptureSpec) -> None:
    try:
        status = install(spec)
    except BaseException:  # noqa: BLE001 - the child must always report
        status = CaptureStatus(
            requested=True, active=False, reason=traceback.format_exc(), instrumented=()
        )
    try:
        conn.send(status)
    finally:
        conn.close()


def _capture_probe(spec: CaptureSpec) -> CaptureStatus:
    """What ``install()`` will do in the episode children, measured by doing it in one.

    A forking path must not install in the parent (C1), so the host cannot learn the status by
    installing. It learns it by forking one throwaway child that installs exactly as every
    episode child will, from the same inherited state. Reporting the request alone would leave
    the manifest saying ``active=False`` for a run whose rows all carry traces.
    """
    ctx = _mp_context()
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_probe_main, args=(child_conn, spec))
    proc.start()
    child_conn.close()
    deadline = time.perf_counter() + _PROBE_TIMEOUT_S
    reported: Any = None
    try:
        while reported is None:
            if parent_conn.poll(_POLL_STEP_S):
                reported = parent_conn.recv()
            elif not proc.is_alive() or time.perf_counter() > deadline:
                break
    except EOFError:
        reported = None
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(_JOIN_GRACE_S)
        proc.close()
    if isinstance(reported, CaptureStatus):
        return reported
    return CaptureStatus(
        requested=True,
        active=False,
        reason="the capture probe child reported nothing",
        instrumented=(),
    )


def _drain(conn: Connection) -> dict[str, Any] | None:
    """The trace the terminated child sent on the drain pipe inside ``_DRAIN_GRACE_S``, or None.

    ``poll`` returns on data or on EOF -- the handler's ``os._exit`` closes the child's end --
    so only a child that ignores the signal, or hangs inside its own snapshot, costs the grace;
    both then end at the parent's ``kill()`` as today.
    """
    try:
        if not conn.poll(_DRAIN_GRACE_S):
            return None
        kind, payload = conn.recv()
    except Exception:  # noqa: BLE001 - EOF or a half-written pickle: no trace, as today
        return None
    return payload if kind == _TIMEOUT_ERROR and isinstance(payload, dict) else None


def _call_with_timeout(
    rollout: Rollout,
    config: dict[str, Any],
    seed: int,
    timeout: float,
    ctx: Any,
    capture_call: _CaptureCall | None = None,
    chaos_call: _ChaosCall | None = None,
) -> _Outcome:
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    # The drain: a second pipe, because the outcome pipe may be mid-send when SIGTERM lands and
    # two writers on one pipe interleave. Created beside the outcome pipe on every call, capture
    # call or not (E14): the handler that writes to it exists only with a capture call, and a
    # handler whose channel might not exist is a state that costs an afternoon the first time
    # the two conditions are computed slightly differently. The pipe is cheap; only the handler
    # and the parent's poll below are gated on the capture call.
    drain_parent, drain_child = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_child_main,
        args=(child_conn, drain_child, rollout, config, seed, capture_call, chaos_call),
    )
    proc.start()
    child_conn.close()
    drain_child.close()  # or poll() never sees EOF and the grace is always paid in full
    deadline = time.perf_counter() + timeout
    outcome: _Outcome | None = None
    try:
        while outcome is None:
            remaining = deadline - time.perf_counter()
            if parent_conn.poll(min(_POLL_STEP_S, max(remaining, 0.0))):
                outcome = parent_conn.recv()
            elif not proc.is_alive():
                if parent_conn.poll():
                    outcome = parent_conn.recv()
                else:
                    outcome = (
                        "error",
                        f"rollout worker exited with code {proc.exitcode} before returning",
                    )
            elif remaining <= 0.0:
                outcome = (_TIMEOUT_ERROR, None)
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
            timed_out = outcome is not None and outcome[0] == _TIMEOUT_ERROR
            if capture_call is not None and timed_out:
                # SIGTERM is in flight: the child's handler snapshots, sends and exits, so the
                # join right after is immediate. Nothing inside the grace is today's outcome.
                # Polled only when a handler exists to write: a run without [capture] still
                # returns within timeout + _JOIN_GRACE_S even for a child that ignores SIGTERM.
                outcome = (_TIMEOUT_ERROR, _drain(drain_parent))
            proc.join(_JOIN_GRACE_S)
            if proc.is_alive():
                proc.kill()
                proc.join()
        else:
            proc.join(_JOIN_GRACE_S)
        drain_parent.close()
        proc.close()
    return outcome


def _mp_context() -> Any:
    methods = multiprocessing.get_all_start_methods()
    return multiprocessing.get_context("fork" if "fork" in methods else "spawn")


# ---------- run ----------


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    n_ok: int
    n_errored: int
    n_timeout: int
    wall_time: float
    stopped_by: str | None
    complete: bool
    n_infra_retried: int = 0
    n_infra_failed: int = 0


def _accepted_mde(p: Plan) -> float:
    """What ``manifest.environment["max_mde_accepted"]`` records, on either backend.

    Every launched run carries one, because the claim is about the run and not about whether a
    flag was typed: no flag means the default was in force, and that is what is recorded. Both
    backends build ``environment`` separately, which is why this is a function and not two
    literals -- the modal path is the one likely to be missed.
    """
    return DEFAULT_MAX_MDE if p.max_mde_accepted is None else p.max_mde_accepted


def _environment(spec: SweepSpec) -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "poisson_prove_version": __version__,
        "sweep": spec.to_dict(),
    }


def _declaration(spec: CaptureSpec) -> int | str:
    """What a ``[capture]`` table declared, in the words it declared it in (D9).

    The manifest is a record of the *request*, so a cap of ``None`` -- which is the string the
    sweep file carried -- goes back to that string rather than to JSON ``null``: the surfacing
    packet's provenance echo then prints ``none`` without being touched, where a ``null`` would
    be dropped by its ``*_bytes`` filter or printed in Python's spelling.
    """
    return "none" if spec.max_observation_bytes is None else spec.max_observation_bytes


def _spec_declaration(spec: SweepSpec) -> int | str | None:
    """The cap a sweep declared, or ``None`` when it carries no ``[capture]`` table at all.

    Deliberately not ``_declared_limit``: the cut sites are right not to tell the two nothings
    apart (D5), and the resume gate is right to (D14). A run that recorded *keep every value
    whole* and a sweep that asked for no capture are two different requests, and continuing one
    run directory under the other is this packet's own failure mode reached by a flag.
    """
    return None if spec.capture is None else _declaration(spec.capture)


def _recorded_cap(manifest: RunManifest) -> tuple[str, int | str] | None:
    """The observation cap a stored run recorded -- the name it used and the value it wrote.

    Read by the ``_bytes`` suffix, the idiom ``report._observation_cap`` already uses one file
    over and for the same reason: a run written before A8b recorded this same field under a
    spelling this package has retired, and comparing it as the same field must not put that
    spelling back. A third spelling reads the same way, and the name travels into the refusal
    as data rather than as a literal.
    """
    capture = manifest.environment.get("capture")
    if not isinstance(capture, Mapping):
        return None
    for key, value in sorted(capture.items(), key=lambda entry: str(entry[0])):
        if not str(key).endswith("_bytes") or isinstance(value, bool):
            continue
        if isinstance(value, (int, str)):
            return str(key), value
    return None


def _reads(entry: tuple[str, int | str] | None) -> str:
    """CD-E4's recorded half. A run with no capture record recorded no cap, which is a different
    fact from a run that recorded one, and is said in different words."""
    return "recorded no observation cap" if entry is None else f"recorded {entry[0]} {entry[1]!r}"


def _declares(value: int | str | None) -> str:
    """CD-E4's declared half, in the same two shapes."""
    return "has no [capture] table" if value is None else f"declares {value!r}"


def _spec_declared(spec: SweepSpec) -> Declaration | None:
    """The ``[declare]`` table a sweep carries, or ``None`` (A10).

    Deliberately not ``_declaration``, which is the cap's. Imported by ``executor_modal`` on
    D6's argument: the mapping from a spec to what the manifest and the funnel take exists once.
    """
    return spec.declare


def _declaration_text(d: Declaration) -> str:
    """A declaration as data for a refusal: its three lists, ``-`` for an empty one, and the
    failures and successes when it names any."""
    kinds = tuple(name for name in ("failures", "successes") if getattr(d, name))
    return "; ".join(
        f"{name} {', '.join(getattr(d, name)) or '-'}"
        for name in ("steps", "outcomes", "gates", *kinds)
    )


def _recorded_declaration(d: Declaration | None) -> str:
    """The resume gate's recorded half, in ``_reads``'s two shapes: a run that recorded no
    declaration is a different fact from a run that recorded one."""
    return "recorded no declaration" if d is None else f"recorded {_declaration_text(d)}"


def _declares_declaration(d: Declaration | None) -> str:
    """The resume gate's declared half, in ``_declares``'s two shapes."""
    return "has no [declare] table" if d is None else f"declares {_declaration_text(d)}"


def _capture_record(spec: CaptureSpec, status: CaptureStatus) -> dict[str, Any]:
    """``manifest.environment["capture"]``: the request and what became of it, once per run.

    This is also where M12 §3's semconv pin lands in the run manifest, which until now was
    owned by nobody. The ``[capture]`` table itself is deliberately not part of
    ``SweepSpec.to_dict()``: a capture request is not what makes two sweeps the same sweep.
    """
    return {
        "requested": status.requested,
        "active": status.active,
        "reason": status.reason,
        "instrumented": list(status.instrumented),
        "semconv": OTEL_SEMCONV_VERSION,
        "alias_map_version": ALIAS_MAP_VERSION,
        "content": spec.content,
        "max_observation_bytes": _declaration(spec),
        "max_spans": spec.max_spans,
    }


def _chaos_record(spec: ChaosSpec, status: ChaosStatus, hooks: Sequence[str]) -> dict[str, Any]:
    """``manifest.environment["chaos"]`` and ``backend_meta["chaos"]``: the request, and what
    the process that made the calls actually armed.

    ``hooks`` is what distinguishes the two: the ``none`` arm asks for injection, installs
    nothing and runs under an unpatched client, and a record that did not say so would make
    the control arm indistinguishable from a faulted arm that failed to arm.
    """
    return {
        "requested": status.requested,
        "fault": status.fault,
        "rate": status.rate,
        "steps": list(spec.steps),
        "engine_version": status.engine_version,
        "hooks": list(hooks),
    }


def _empty_envelope() -> dict[str, Any]:
    """D9's zero-span envelope: *capture ran and this episode emitted nothing*, which is a
    different fact from *capture never ran* and has to be stored as one.

    Constructed and never spelled as a literal. ``Trace.to_dict()``'s key set is exact in both
    directions and ``Store.append`` validates what arrives with ``from_dict``, so a hand-written
    dict would be rejected outright the moment ``Trace`` gains a field -- landing the row in
    exactly the both-columns-null state it has to be distinguishable from.

    Stamped exactly as ``from_otel([])`` stamps its trace -- both pins -- because it stands in
    for a capture that normalised zero spans, and a captured row should not read as unstamped
    only because the episode emitted nothing.
    """
    return Trace(
        spans=(),
        source="otel",
        source_version=OTEL_SEMCONV_VERSION,
        alias_map_version=ALIAS_MAP_VERSION,
    ).to_dict()


def _declared_limit(spec: SweepSpec) -> int | None:
    """What the sweep declared, as the cut sites take it: ``None`` when nothing was declared and
    when ``"none"`` was, an int otherwise. The one place the two are the same thing.

    D6: the mapping exists once and ``executor_modal`` imports it. A field list copied into the
    Modal transport is how a rename went silently wrong across a process boundary once already
    (U5), and two copies of a two-case mapping is that shape one size down.
    """
    return None if spec.capture is None else spec.capture.max_observation_bytes


def _finalized(
    record: EpisodeRecord, limit: int | None, declaration: Declaration | None
) -> EpisodeRecord:
    """``finalize`` over a row's own trace, on its way to the store.

    **It never raises.** ``record.meta["trace"]`` is a plain dict that nothing has validated,
    and A7's P7-9 pins that one which is not a valid trace dict is stored exactly as written,
    both trace columns null, with ``Store.append`` not raising. ``Trace.from_dict`` here runs
    one frame before the guard written for it, so the guard has to be here too.

    The record comes back untouched when nothing was stamped and nothing was cut --
    ``finalize`` returns the trace itself in that case -- so a trace that needed neither is
    stored byte for byte as it arrived, and no existing run's stored bytes move.

    ``declaration`` is the run's own too (A10): its gates are stamped on the parsed trace inside
    ``finalize``, after the guard above, so a declaration adds no raise one frame earlier.

    ``limit`` is the run's own (D5). A8b wired this site with none, so every stored row of both
    backends was cut at a module constant whatever its sweep file declared, while the manifest,
    the receipt and the viewer all reported the declaration. ``None`` is *cut nothing*, which is
    what a sweep declaring ``"none"`` and a sweep with no ``[capture]`` table both asked for.
    """
    try:
        parsed = Trace.from_dict(record.meta["trace"])
    except Exception:  # noqa: BLE001 - an unreadable trace is stored exactly as written
        return record
    final = finalize(parsed, declaration=declaration, limit=limit)
    if final is parsed:
        return record
    return replace(record, meta={**record.meta, "trace": final.to_dict()})


def _with_capture_envelope(
    record: EpisodeRecord,
    active: bool,
    limit: int | None,
    declaration: Declaration | None = None,
) -> EpisodeRecord:
    """The one funnel every stored row passes through: ``finalize`` over a trace it carries,
    D9's empty envelope for a row that ran under active capture and carries none.

    ``declaration`` (A10) reaches ``finalize`` through ``_finalized`` the way ``limit`` does.
    Both backends' call sites pass ``_spec_declared(p.spec)``; it defaults to ``None`` so a
    caller with three arguments keeps the meaning it had, and the stamp is host-side on Modal
    because this funnel is.

    The shipped shape returned early on ``"trace" in record.meta`` -- exactly the branch that
    needs the cut -- so the two branches are separated rather than collapsed. Rule zero (C7) is
    untouched either way: this runs on the built row, after ``_merge_capture`` has already
    declined to write an empty capture over a rollout's own trace. Inside ``_classify`` it
    would break that; here it cannot.
    """
    if "trace" in record.meta:
        return _finalized(record, limit, declaration)
    if not active:
        return record
    return replace(record, meta={**record.meta, "trace": _empty_envelope()})


def _record(
    p: Plan,
    pair: Pair,
    index: int,
    outcome: _Outcome,
    wall_time: float,
    *,
    capture_active: bool = False,
) -> EpisodeRecord:
    kind, payload = outcome
    backend_meta = {"i": index}
    if kind == "ok":
        return _with_capture_envelope(
            EpisodeRecord.from_episode(
                Episode.from_dict(payload),
                run_id=p.run_id,
                config=pair.config,
                seed=pair.seed,
                replicate_index=pair.replicate_index,
                wall_time=wall_time,
                backend_meta=backend_meta,
            ),
            capture_active,
            _declared_limit(p.spec),
            _spec_declared(p.spec),
        )
    meta: dict[str, Any] | None
    if kind == _TIMEOUT_ERROR:
        # A terminated child that drained its snapshot: the payload is the trace dict, and it
        # rides the errored row's meta exactly where an ok row's trace rides.
        error = _TIMEOUT_ERROR
        meta = {"trace": payload} if isinstance(payload, dict) else None
    elif kind == "error" and isinstance(payload, dict):
        # A rollout that raised, or returned the wrong thing, under capture: the two-key dict,
        # its trace complete up to the failure. The kind was read first, so a timeout's bare
        # trace dict never reaches this branch.
        error = str(payload["error"])
        meta = payload["meta"]
    else:
        error = str(payload)
        meta = None
    return _with_capture_envelope(
        EpisodeRecord.errored(
            run_id=p.run_id,
            config=pair.config,
            seed=pair.seed,
            replicate_index=pair.replicate_index,
            error=error,
            wall_time=wall_time,
            backend_meta=backend_meta,
            meta=meta,
        ),
        capture_active,
        _declared_limit(p.spec),
        _spec_declared(p.spec),
    )


def run_local(
    p: Plan,
    rollout: Rollout,
    store: Store,
    *,
    episode_timeout: float | None = None,
    max_rollouts: int | None = None,
    batch_size: int = 64,
    on_progress: Callable[[int, int], None] | None = None,
) -> RunSummary:
    """Execute a plan serially, in-process, writing episodes in batches of ``batch_size``.

    The rollout receives a fresh shallow copy of the pair's config on every call.
    """
    if batch_size < 1:
        raise ExecutorError(f"batch_size must be >= 1, got {batch_size}")
    if max_rollouts is not None and max_rollouts < 1:
        raise ExecutorError(f"max_rollouts must be >= 1 when given, got {max_rollouts}")
    if episode_timeout is not None and episode_timeout <= 0:
        raise ExecutorError(f"episode_timeout must be > 0 when given, got {episode_timeout}")

    existing: RunManifest | None
    try:
        existing = store.manifest(p.run_id)
    except StoreError:
        existing = None
    if existing is not None and existing.status == "complete":
        raise ExecutorError(f"run {p.run_id!r} is already complete")
    if p.resumed:
        if existing is None:
            raise ExecutorError(f"resumed run {p.run_id!r} is not in the store")
    elif existing is not None:
        raise ExecutorError(f"run {p.run_id!r} already exists; plan with resume= to continue it")

    # Capture, before the manifest is written and after the run is known to be startable. With
    # a timeout every episode runs in a forked child, so the provider must be installed there:
    # a provider set here would make the child's set_tracer_provider a refused no-op (C1).
    ctx = _mp_context() if episode_timeout is not None else None
    capture_spec = p.spec.capture
    capture_status: CaptureStatus | None = None
    if capture_spec is not None:
        capture_status = _capture_probe(capture_spec) if ctx is not None else install(capture_spec)

    # Injection is armed here, before the manifest exists, because its two front refusals --
    # an unknown fault name, and a faulted arm in a process with no client loaded -- are
    # reasons the run must not start at all. Unlike capture, the hooks go in *this* process
    # even with a timeout: a forked child inherits the patched client, and the target is
    # resolved before this point on both paths.
    chaos_spec = p.spec.chaos
    chaos_status: ChaosStatus | None = None
    if chaos_spec is not None:
        chaos_status = chaos_install(chaos_spec)

    if not p.resumed:
        environment = _environment(p.spec)
        environment["max_mde_accepted"] = _accepted_mde(p)
        environment["design_mde"] = _design_record(p)
        if p.import_path is not None:
            environment["import_path"] = p.import_path
        if capture_spec is not None and capture_status is not None:
            environment["capture"] = _capture_record(capture_spec, capture_status)
        if chaos_spec is not None and chaos_status is not None:
            environment["chaos"] = _chaos_record(chaos_spec, chaos_status, _installed_hooks())
        store.create_run(
            RunManifest(
                run_id=p.run_id,
                target_id=p.spec.target_id,
                t_unit=p.spec.t_unit,
                run_salt=p.run_salt,
                axis_types=dict(p.spec.axis_types),
                backend=p.backend,
                environment=environment,
                retain_traces_for=p.spec.retain_traces_for,
                declared=_spec_declared(p.spec),
                name=p.name,
            )
        )

    total = len(p.pairs)
    batch: list[EpisodeRecord] = []
    n_ok = n_errored = n_timeout = 0
    executed = 0
    stopped_by: str | None = None
    t_run = time.perf_counter()

    def flush() -> None:
        if batch:
            store.append(p.run_id, list(batch))
            batch.clear()

    try:
        for index, pair in enumerate(p.pairs):
            config = dict(pair.config)
            call = (
                None
                if capture_spec is None
                else _CaptureCall(
                    spec=capture_spec,
                    run_id=p.run_id,
                    episode_id=_episode_id(pair.config_hash, pair.replicate_index),
                )
            )
            chaos_call = None if chaos_spec is None else _ChaosCall(spec=chaos_spec)
            t0 = time.perf_counter()
            if ctx is None:
                outcome = _call_in_process(rollout, config, pair.seed, call, chaos_call)
            else:
                assert episode_timeout is not None
                outcome = _call_with_timeout(
                    rollout, config, pair.seed, episode_timeout, ctx, call, chaos_call
                )
            wall_time = time.perf_counter() - t0
            batch.append(
                _record(
                    p,
                    pair,
                    index,
                    outcome,
                    wall_time,
                    capture_active=capture_status is not None and capture_status.active,
                )
            )
            executed += 1
            if outcome[0] == "ok":
                n_ok += 1
            else:
                n_errored += 1
                if outcome[0] == _TIMEOUT_ERROR:
                    n_timeout += 1
            if on_progress is not None:
                on_progress(executed, total)
            if len(batch) >= batch_size:
                flush()
            if max_rollouts is not None and executed >= max_rollouts and executed < total:
                stopped_by = "max_rollouts"
                break
    finally:
        flush()

    complete = executed == total and stopped_by is None
    if complete:
        store.mark_complete(p.run_id)
    return RunSummary(
        run_id=p.run_id,
        n_ok=n_ok,
        n_errored=n_errored,
        n_timeout=n_timeout,
        wall_time=time.perf_counter() - t_run,
        stopped_by=stopped_by,
        complete=complete,
    )
