"""M10: the command line.

Eight verbs over the built modules: ``sweep`` runs a plan on a backend after a pre-flight
prompt; ``diff``, ``report``, ``check`` and ``serve`` operate on stored runs; ``inspect`` dumps
the ``(config, seed)`` pairs behind an event plus a reproduction snippet; ``runs`` lists the
store; ``paired`` asserts that a declaration's arms were the same request replayed and writes
the paired-replay artifacts, and ``report --paired`` folds the same sections into the report.
``serve`` is the one verb that binds a socket: a loopback listener holding one page
built before the bind, which writes nothing and dies with the process.
This module computes nothing and decides nothing statistical: it parses arguments, calls
M2–M7, and renders their results. Every number it prints is a field on a ``RunSummary``,
``MultiDiffResult``, ``MultiReport``, ``SurvivalReport``, ``RunManifest`` or a store frame.

``diff``, ``report`` and ``check`` go through the multi-event path: raw store frames to
``multi_diff`` (which censors per event itself), one panel per event in the report. One event
is not a special case; it is a one-event multi call. ``--event`` is repeatable and, when
omitted, inferred (``check`` excepted: a gate never infers). ``report`` with one run id is
the single-run survival report.

``main`` owns the streams. Every write goes through the streams it was given (``sys.*`` by
default), which is what makes the whole CLI testable in-process. Exceptions map to exit codes
in exactly one place, ``_dispatch``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shlex
import sys
import tomllib
import traceback
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TextIO, cast

if TYPE_CHECKING:
    import pandas as pd
    from _typeshed import SupportsWrite

    from poisson_prove.diff import Method

from poisson_prove import __version__
from poisson_prove._compat import (
    retired_default_store,
    retired_default_store_refusal,
    retired_store_variable_note,
)
from poisson_prove._resolve import resolve
from poisson_prove.diff import (
    _CAUSES,
    _PAIRED_METHODS,
    COVERAGE_COLUMNS,
    DiffError,
    EventInferenceError,
    MultiDiffResult,
    UnknownEvent,
    _md_cell,
    infer_events,
    multi_diff,
)
from poisson_prove.executor import (
    ExecutorError,
    Plan,
    RunSummary,
    check_power,
    plan,
    preflight,
    run_local,
)
from poisson_prove.executor_burla import BurlaOptions, preflight_burla, run_burla
from poisson_prove.executor_modal import (
    ImageSpec,
    ModalOptions,
    ModalTarget,
    preflight_modal,
    run_modal,
)
from poisson_prove.paired import (
    Declaration,
    PairedError,
    _artifact_text,
    _Bundle,
    _bundle,
    _cost_block,
    _fold_html,
    _fold_markdown,
)
from poisson_prove.paired import cost as paired_cost
from poisson_prove.report import (
    MultiReport,
    ReportError,
    ReportSpec,
    SurvivalReport,
    _interval_lines,
    _observation_cap,
    _provenance_lines,
    build_multi_report,
    build_survival_report,
)
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.steps import declaration_check
from poisson_prove.store import RunManifest, Store, StoreError
from poisson_prove.survival import SurvivalError, cell_table, competing_set
from poisson_prove.trace import Trace, TraceValidationError
from poisson_prove.tree import (
    DEFAULT_DEPTH,
    DEFAULT_MAX_GROUP_MDE,
    DEFAULT_PERMUTATIONS,
    DEFAULT_SEED,
    DEPTHS,
    TASK_FAMILY_KEYS,
    TRACE_GROUPINGS,
    WHOLE_GRID,
    Bound,
    CellFamily,
    CellResult,
    FaultLines,
    Grouping,
    GroupResult,
    Leaves,
    RootResult,
    TreeResult,
    tree,
)
from poisson_prove.viewer import _HOST, ViewerError, build_structure, render_html, serve_page

__all__ = ["main"]

_COMMAND = "poisson-prove"
_ENV_STORE = "POISSON_PROVE_STORE"
_DEFAULT_STORE = "./prove-runs"
_DEFAULT_BATCH_SIZE = 64
_DEFAULT_METHOD = "fisher_bh"
_DEFAULT_Q = 0.05
_METHODS: tuple[str, ...] = ("fisher_bh", "mcnemar_bh", "logrank_bh")
_REPORT_FILES = ("report.md", "heatmap.svg", "receipt.html")
_SNIPPET_MARKER = "# reproduce one episode"
_MODAL_ONLY_FLAGS = ("concurrency", "infra_retries", "max_cost", "est_seconds", "app_name")
#: The remote-backend flags a Burla run takes from the command line over its ``[burla]`` table.
_BURLA_REFUSED_FLAGS = ("concurrency", "app_name")
_DIFF_ONLY_FLAGS = (
    "method", "methods", "q", "permutations", "seed", "by", "max_group_mde", "depth", "paired",
)
_RUN_ONLY_FLAGS = ("horizon",)
_REFUSABLE = (
    SamplerError, ExecutorError, DiffError, ReportError, StoreError, SurvivalError, ViewerError,
    PairedError,
)
_REPORT_FORMS = (
    "report A B --x AXIS [...]  (two run ids: diff report) or "
    "report RUN --x AXIS [...]  (one run id: survival report)"
)
_SERVE_FORM = "serve A B --event NAME --x AXIS [...]  (two run ids, always: a diff view)"


# ---------- streams, exits, parser ----------


@dataclass
class _IO:
    out: TextIO
    err: TextIO
    inp: TextIO


@dataclass
class _State:
    """What the dispatcher needs to tell a refusal from a failure after work started."""

    run_id: str | None = None


class _Exit(Exception):
    """argparse wanted to exit; carries the status so ``main`` can return it."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class _Refusal(Exception):
    """A verb refused before doing any work. Exit 2, message only."""


class _RetiredStoreRefusal(Exception):
    """The default store is in use, ``./prove-runs`` does not exist and the folder an earlier
    version of Prove wrote to does: every verb that reads or writes a store refuses, creates
    nothing, and says how to move or name the old folder, so a store is never split in two.
    Exit 1: one ``error:`` line, then the ``next:`` lines."""

    def __init__(self, error: str, nexts: list[str]) -> None:
        super().__init__(error)
        self.nexts = nexts


class _Parser(argparse.ArgumentParser):
    """argparse that writes to the streams ``main`` was given and never calls ``sys.exit``."""

    io: _IO | None = None

    def _print_message(self, message: str, file: SupportsWrite[str] | None = None) -> None:
        if not message or self.io is None:
            return
        target = self.io.err if file is sys.stderr else self.io.out
        target.write(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._print_message(message, sys.stderr)
        raise _Exit(status)

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def _build_parser(io: _IO) -> _Parser:
    parser = _Parser(
        prog=_COMMAND,
        description="A statistical instrument for finding where autonomous and agentic "
        "systems break.",
    )
    parser.add_argument("--version", action="version", version=f"{_COMMAND} {__version__}")
    parser.add_argument(
        "--store",
        metavar="PATH",
        help=f"store root (default: ${_ENV_STORE}, else {_DEFAULT_STORE})",
    )
    sub = parser.add_subparsers(dest="verb", title="verbs")

    sweep = sub.add_parser("sweep", help="run a sweep spec on a backend after a pre-flight")
    sweep.add_argument(
        "spec", metavar="SPEC.toml", help="sweep spec (see examples/quickstart.toml)"
    )
    sweep.add_argument(
        "--target", required=True, metavar="pkg.module:rollout", help="import path of the rollout"
    )
    sweep.add_argument("--backend", choices=("local", "modal", "burla"), default="local")
    identity = sweep.add_mutually_exclusive_group()
    identity.add_argument("--salt", metavar="HEX", help="run salt for seed derivation")
    identity.add_argument("--pair-with", metavar="RUN_ID", help="inherit that run's salt")
    identity.add_argument("--resume", metavar="RUN_ID", help="continue a partial run")
    sweep.add_argument("--episode-timeout", type=float, metavar="S", help="per-episode timeout")
    sweep.add_argument("--max-rollouts", type=int, metavar="N", help="stop after N rollouts")
    sweep.add_argument("--batch-size", type=int, metavar="N", help="rows per store part")
    sweep.add_argument(
        "--max-mde",
        type=float,
        metavar="FLOAT",
        help="largest minimum detectable effect you accept for this design (default 0.20)",
    )
    sweep.add_argument("--yes", action="store_true", help="skip the pre-flight prompt")
    modal = sweep.add_argument_group(
        "remote backends (override the [modal] table; --infra-retries, --max-cost and "
        "--est-seconds also override [burla])"
    )
    modal.add_argument("--concurrency", type=int, metavar="N", help="max containers")
    modal.add_argument("--infra-retries", type=int, metavar="N", help="retries per batch")
    modal.add_argument("--max-cost", type=float, metavar="USD", help="refuse above this estimate")
    modal.add_argument("--est-seconds", type=float, metavar="S", help="seconds per episode")
    modal.add_argument("--app-name", metavar="NAME", help="Modal app name")
    modal.add_argument(
        "--image", default="image", metavar="SECTION", help="[modal.SECTION] image table"
    )

    diff_p = sub.add_parser("diff", help="compare two stored runs cell by cell, per event")
    diff_p.add_argument("a", metavar="A", help="run id of the baseline")
    diff_p.add_argument("b", metavar="B", help="run id of the candidate")
    _add_event_argument(diff_p, "omitted: inferred from the outcomes present")
    _add_method_arguments(diff_p, defaults=True)
    diff_p.add_argument("--methods", choices=("all",), help="also run the other two methods")
    diff_p.add_argument("--format", choices=("md", "json"), default="md")
    _add_tree_arguments(diff_p, defaults=True)

    report_p = sub.add_parser(
        "report",
        help="render report.md, heatmap.svg, receipt.html: two run ids diff them, one run id "
        "is its survival report",
    )
    report_p.add_argument(
        "runs", nargs="+", metavar="RUN", help="A B for a diff report, RUN for a survival report"
    )
    _add_event_argument(report_p, "omitted: inferred from the outcomes present")
    _add_method_arguments(report_p, defaults=False)
    report_p.add_argument(
        "--methods", choices=("all",), help="add the method comparison table (diff report only)"
    )
    _add_tree_arguments(report_p, defaults=False)
    report_p.add_argument(
        "--x",
        metavar="AXIS",
        help="config key on the x axis (omitted: lists the axes and events the runs carry)",
    )
    report_p.add_argument("--y", metavar="AXIS", help="config key on the y axis")
    report_p.add_argument(
        "--fix", action="append", default=[], metavar="KEY=VALUE", help="pin a config key"
    )
    report_p.add_argument(
        "--horizon", type=float, metavar="FLOAT", help="truncate a survival report's horizon"
    )
    report_p.add_argument("--theme", choices=("dark", "light"), default="dark")
    report_p.add_argument("--top-n", type=int, default=10, metavar="N", help="worst cells listed")
    report_p.add_argument(
        "--forest",
        choices=("auto", "always", "never"),
        default="auto",
        help="single-axis diff panels: forest plot, strip, or forest for categorical axes",
    )
    report_p.add_argument(
        "--out",
        metavar="DIR",
        help="default ./prove-report-<A>-vs-<B> or ./prove-report-<RUN>",
    )
    report_p.add_argument("--title", metavar="TEXT")
    report_p.add_argument("--force", action="store_true", help="write into a non-empty --out")
    report_p.add_argument(
        "--paired",
        metavar="DECL",
        help="a paired-replay declaration (TOML) whose sweep (A, B) is; folds the paired "
        "sections into the report and writes the artifacts beside it (diff report only)",
    )

    paired_p = sub.add_parser(
        "paired",
        help="assert that a declaration's arms were the same request replayed, then write the "
        "paired-replay artifacts",
    )
    paired_p.add_argument(
        "--declaration", required=True, metavar="DECL", help="the paired-replay declaration (TOML)"
    )
    paired_p.add_argument(
        "--out", metavar="DIR", help="default ./prove-paired-<declaration digest prefix>"
    )
    paired_p.add_argument("--format", choices=("md", "json"), default="md")
    paired_p.add_argument(
        "--cap-check",
        action="store_true",
        help="print the cost block and exit 1 at or above the declared token cap; write nothing",
    )
    paired_p.add_argument("--force", action="store_true", help="write into a non-empty --out")

    check_p = sub.add_parser("check", help="gate on a diff: exit 0 on PASS, 1 on FAIL")
    check_p.add_argument("a", metavar="A", help="run id of the baseline")
    check_p.add_argument("b", metavar="B", help="run id of the candidate")
    _add_event_argument(check_p, "required: a gate never infers its events")
    _add_method_arguments(check_p, defaults=True)
    check_p.add_argument("--fail-on", choices=("worse", "any"), default="worse")

    serve_p = sub.add_parser(
        "serve", help="serve a read-only page for one run pair on an ephemeral loopback port"
    )
    serve_p.add_argument(
        "runs", nargs="+", metavar="RUN", help="the baseline and the candidate, in that order"
    )
    _add_event_argument(serve_p, "required: a viewer never infers its event")
    _add_method_arguments(serve_p, defaults=True)
    # ``serve`` takes the five tree flags through the helper ``report`` already uses, with
    # ``defaults=True``: like ``diff`` and unlike ``report``, it takes two runs, has no
    # single-run form to refuse, and so needs no ``None`` to tell an unset flag from M14's own
    # value. The helper keeps ``diff``'s two argument groups, so ``diff --help``'s layout is
    # unchanged and ``serve --help`` gains the same two headings.
    _add_tree_arguments(serve_p, defaults=True)
    serve_p.add_argument(
        "--x",
        metavar="AXIS",
        help="required: config key on the x axis (omitted: lists the axes and events the runs "
        "carry)",
    )
    serve_p.add_argument("--y", metavar="AXIS", help="config key on the y axis")
    serve_p.add_argument(
        "--fix", action="append", default=[], metavar="KEY=VALUE", help="pin a config key"
    )
    serve_p.add_argument(
        "--theme",
        choices=("dark", "light"),
        default="dark",
        help="the page's colours (default dark)",
    )
    serve_p.add_argument("--top-n", type=int, default=10, metavar="N", help="worst cells listed")
    serve_p.add_argument(
        "--forest",
        choices=("auto", "always", "never"),
        default="auto",
        help="single-axis diff panels: forest plot, strip, or forest for categorical axes",
    )
    serve_p.add_argument(
        "--title", metavar="TEXT", help="the page's title (default: the two run ids and the events)"
    )
    serve_p.add_argument(
        "--json", action="store_true", help="print the structure to stdout and exit; bind nothing"
    )

    inspect_p = sub.add_parser("inspect", help="dump the (config, seed) pairs behind an event")
    inspect_p.add_argument("run", metavar="RUN")
    inspect_p.add_argument(
        "--event",
        metavar="NAME",
        help="outcome or error to dump (omitted: lists the events the run carries)",
    )
    inspect_p.add_argument(
        "--where", action="append", default=[], metavar="KEY=VALUE", help="filter on config"
    )
    inspect_p.add_argument("--limit", type=int, metavar="N")

    sub.add_parser("runs", help="list the runs in the store")

    for p in (parser, *sub.choices.values()):
        if isinstance(p, _Parser):
            p.io = io
    return parser


def _add_event_argument(p: argparse.ArgumentParser, note: str) -> None:
    p.add_argument(
        "--event",
        action="append",
        metavar="NAME",
        help=f"outcome that counts as an event; repeatable ({note})",
    )


def _add_method_arguments(p: argparse.ArgumentParser, *, defaults: bool) -> None:
    """``--method`` and ``--q``. Without defaults the namespace keeps ``None`` for a flag the
    user did not pass, so the single-run report can name the diff-only flags it was given."""
    p.add_argument(
        "--method",
        choices=_METHODS,
        default=_DEFAULT_METHOD if defaults else None,
        help="the per-cell test: fisher_bh treats the two runs as separate samples (default), "
        "mcnemar_bh pairs them on their shared seeds, logrank_bh is cause-specific",
    )
    p.add_argument(
        "--q", type=float, default=_DEFAULT_Q if defaults else None, help="BH false discovery rate"
    )


def _add_tree_arguments(p: argparse.ArgumentParser, *, defaults: bool) -> None:
    """The five flags that move the tree, in the two groups ``diff`` has always printed, with one
    help text for every verb that takes them. Without defaults the namespace keeps ``None`` for a
    flag the user did not pass -- the help text still states M14's value -- so the single-run
    report can name the diff-only flags it was given and a pair can put M14's constants in by
    name."""
    omnibus_group = p.add_argument_group("the omnibus over the whole family")
    omnibus_group.add_argument(
        "--permutations",
        type=int,
        default=DEFAULT_PERMUTATIONS if defaults else None,
        metavar="N",
        help=f"within-cell permutations behind the omnibus (default {DEFAULT_PERMUTATIONS})",
    )
    omnibus_group.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED if defaults else None,
        metavar="N",
        help=f"permutation seed (default {DEFAULT_SEED})",
    )
    fault_group = p.add_argument_group("the fault lines under the omnibus")
    fault_group.add_argument(
        "--by",
        metavar="KEY",
        help="grouping for the fault lines: an axis both runs declare, "
        f"{'/'.join(TASK_FAMILY_KEYS)}, {' or '.join(TRACE_GROUPINGS)} (unsupported until "
        f"Phase 5.2), or {WHOLE_GRID}. Omitted: resolved in a stated order and named either way",
    )
    fault_group.add_argument(
        "--max-group-mde",
        type=float,
        metavar="FLOAT",
        help="largest group-level minimum detectable effect you accept "
        f"(default {DEFAULT_MAX_GROUP_MDE:g}, the constant sweep's --max-mde uses)",
    )
    fault_group.add_argument(
        "--depth",
        type=int,
        choices=DEPTHS,
        default=DEFAULT_DEPTH if defaults else None,
        metavar="N",
        help=f"levels the procedure tests: 2 stops at the fault lines, 3 adds the cells under "
        f"each rejecting one (default {DEFAULT_DEPTH}). The bound is computed from this and the "
        "grouping's shape, never from what rejected",
    )


# ---------- entry point ----------


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    stdin: TextIO | None = None,
) -> int:
    """Entry point. Streams default to ``sys.*``; tests pass ``StringIO``. Returns the exit code."""
    io = _IO(
        out=sys.stdout if stdout is None else stdout,
        err=sys.stderr if stderr is None else stderr,
        inp=sys.stdin if stdin is None else stdin,
    )
    parser = _build_parser(io)
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        ns = parser.parse_args(args)
    except _Exit as exc:
        return exc.code
    if ns.verb is None:
        parser.print_help(io.out)
        return 0
    return _dispatch(ns, io)


def _dispatch(ns: argparse.Namespace, io: _IO) -> int:
    """The single exception-to-exit-code map."""
    root = _store_root(ns)
    state = _State()
    try:
        note = retired_store_variable_note(os.environ, _ENV_STORE)
        if note is not None:
            io.err.write(f"note: {note}\n")
        _check_retired_default_store(ns, root)
        _check_store(ns, root)
        return _VERBS[ns.verb](ns, io, root, state)
    except _RetiredStoreRefusal as exc:
        io.err.write(f"error: {exc}\n")
        for line in exc.nexts:
            io.err.write(f"  next: {line}\n")
        return 1
    except _Refusal as exc:
        io.err.write(f"error: {exc}\n")
        return 2
    except _REFUSABLE as exc:
        if _work_started(root, state):
            io.err.write(f"error: {exc} (run_id: {state.run_id})\n")
            return 3
        io.err.write(f"error: {exc}\n")
        return 2
    except Exception as exc:
        suffix = f" (run_id: {state.run_id})" if state.run_id is not None else ""
        io.err.write(traceback.format_exc())
        io.err.write(f"error: {type(exc).__name__}: {exc}{suffix}\n")
        return 3


def _store_root(ns: argparse.Namespace) -> Path:
    if ns.store:
        return Path(ns.store)
    env = os.environ.get(_ENV_STORE)
    if env:
        return Path(env)
    return Path(_DEFAULT_STORE)


def _check_retired_default_store(ns: argparse.Namespace, root: Path) -> None:
    """With the default store in use, a folder an earlier version of Prove wrote to beside a
    missing ``./prove-runs`` is a refusal on every verb, ``sweep`` included: reading past it
    would answer from nothing, and writing would split the store in two. Creates nothing."""
    if ns.store or os.environ.get(_ENV_STORE):
        return
    old = retired_default_store(root)
    if old is None:
        return
    error, nexts = retired_default_store_refusal(root, old, _COMMAND, ns.verb)
    raise _RetiredStoreRefusal(error, nexts)


def _slug(name: str) -> str:
    """A run's name as a folder name: lower case, spaces and slashes as dashes."""
    return name.lower().replace(" ", "-").replace("/", "-")


_SWEEP_NEXT = "sweep SPEC.toml --target pkg.module:rollout"


def _store_source(ns: argparse.Namespace) -> str:
    """Which of the three places named the store root, in the order ``_store_root`` reads them.

    An empty ``$POISSON_PROVE_STORE`` is not a source: ``_store_root`` falls through it to the
    default, and the clause has to name the resolution that actually happened (D3).
    """
    if ns.store:
        return "it came from --store"
    if os.environ.get(_ENV_STORE):
        return f"it came from ${_ENV_STORE}"
    return f"it is the default, since neither --store nor ${_ENV_STORE} is set"


def _no_runs_note(ns: argparse.Namespace, root: Path) -> str:
    """The empty-store sentence ``runs`` writes to stderr and the read verbs refuse with.

    ``runs`` prints it without the ``error: `` prefix and still exits 0, because an empty
    listing of a real store is a true answer (D1); the read verbs raise it as a refusal.
    """
    quoted = shlex.quote(str(root))
    return "\n".join(
        [
            f"no runs in {root}. No directory under it holds a manifest.json; "
            f"{_store_source(ns)}.",
            f"  to write the first run there: {_COMMAND} --store {quoted} {_SWEEP_NEXT}",
        ]
    )


def _check_store(ns: argparse.Namespace, root: Path) -> None:
    """E1: a missing store refuses on every verb that reads it, an empty one on every such verb
    but ``runs``. ``sweep`` is the verb that creates the store, so it is never gated.

    A path with no directory at it is certainly wrong, because nothing was ever stored there;
    a directory with no ``manifest.json`` under it can be a fresh project. The exit code is the
    machine-readable half of that distinction (D1). This reads the store and creates nothing.
    """
    if ns.verb == "sweep":
        return
    quoted = shlex.quote(str(root))
    elsewhere = (
        "  to read another store: "
        f"{_COMMAND} --store PATH {ns.verb}, with --store before the verb"
    )
    if not root.is_dir():
        raise _Refusal(
            "\n".join(
                [
                    f"no store at {root}. No directory exists at that path; {_store_source(ns)}.",
                    f"  to create one there: {_COMMAND} --store {quoted} {_SWEEP_NEXT}",
                    elsewhere,
                ]
            )
        )
    if ns.verb != "runs" and not Store(root).runs():
        raise _Refusal("\n".join([_no_runs_note(ns, root), elsewhere]))


def _work_started(root: Path, state: _State) -> bool:
    if state.run_id is None:
        return False
    try:
        return state.run_id in Store(root).runs()
    except OSError:
        return False


# ---------- shared helpers ----------


def _parse_pairs(items: Sequence[str], flag: str) -> dict[str, Any]:
    """``KEY=VALUE`` items with TOML scalar values: ``push=100`` -> int, ``task="x"`` -> str."""
    out: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise _Refusal(f"{flag} expects KEY=VALUE, got {item!r}")
        try:
            out[key] = tomllib.loads(f"v = {value.strip()}")["v"]
        except tomllib.TOMLDecodeError as exc:
            raise _Refusal(
                f"{flag} {item!r}: value must be a TOML scalar (100, 0.5, \"text\", true): {exc}"
            ) from exc
    return out


def _load_pair(store: Store, a: str, b: str) -> tuple[Any, Any, RunManifest, RunManifest]:
    """Narrow frames and manifests. Nothing is censored here: ``multi_diff`` censors per
    event. Nothing downstream reads ``meta``, so it is never decoded on this path."""
    ma, mb = store.manifest(a), store.manifest(b)
    return store.read(a, meta=False), store.read(b, meta=False), ma, mb


def _outcome_counts(*frames: Any) -> str:
    """``name=count`` pairs over the non-null outcomes of the given store frames, most first."""
    counter: Counter[str] = Counter()
    for frame in frames:
        counter.update(str(o) for o in frame["outcome"].dropna().tolist())
    ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{name}={count}" for name, count in ordered)


def _multi(
    fa: Any,
    fb: Any,
    ma: RunManifest,
    mb: RunManifest,
    *,
    events: Sequence[str] | None,
    method: str,
    q: float,
) -> MultiDiffResult:
    try:
        return multi_diff(
            fa,
            fb,
            events=events,
            method=cast("Method", method),
            q=q,
            manifest_a=ma,
            manifest_b=mb,
        )
    except EventInferenceError as exc:
        raise _Refusal(
            f"cannot infer the event set: {exc}; outcome counts: {_outcome_counts(fa, fb)}; "
            "pass --event NAME (repeatable)"
        ) from exc


def _require_known_events(
    verb: str, events: Sequence[str] | None, *frames: pd.DataFrame
) -> None:
    """Refuse an ``--event`` name absent from every frame the verb loaded, before any work.

    Compared against the outcomes actually present, never against an inferred set: a typo
    should never produce a plausible-looking empty result, and the CLI is where every typo
    originates. The library underneath stays permissive.
    """
    if events is None:
        return
    present = competing_set(*frames)
    missing = [str(e) for e in events if str(e) not in present]
    if missing:
        where = "either run" if len(frames) > 1 else "the run"
        raise UnknownEvent(
            f'{verb}: event "{missing[0]}" does not appear in {where}. '
            f"Present: {', '.join(present)}."
        )


_NEVER_INFERS = {
    "check": "a gate whose meaning changes when a new outcome appears is not a gate",
    "serve": (
        "a picture whose meaning changes when a new outcome appears is worse than a table "
        "with the same defect"
    ),
}


def _missing_flags_refusal(
    store: Store, verb: str, runs: Sequence[str], *, x_missing: bool, event_missing: bool
) -> _Refusal:
    """E3: what the named runs carry, in place of argparse's bare "arguments are required".

    The two verbs that refuse to infer keep their own clause: a gate whose meaning moves when a
    new outcome appears is not a gate, and a picture of the same defect is worse. The listing
    replaces the suggestion they used to end on, because a verb that refuses to infer should not
    offer an inference as its advice, and the inferred set is a subset of the list (D7).

    Fires after the store state, the arity and the unknown-run refusal, and before any work: it
    reads the frames of the named runs and calls nothing else (section 3.2.1).
    """
    for run in runs:
        store.manifest(run)
    frames = [store.read(run, meta=False) for run in runs]
    axes = sorted({str(key) for frame in frames for config in frame["config"] for key in config})
    events = list(competing_set(*frames))
    if verb == "inspect" and "timeout" not in events and store.tally(runs[0]).timed_out:
        # ``inspect --event`` matches the error column too, and "timeout" is the one error text
        # a person can type: ``RunTally.timed_out`` counts exactly ``error == "timeout"`` (D9).
        events = sorted({*events, "timeout"})
    flags = " and ".join(
        flag
        for flag, missing in (("--x AXIS", x_missing), ("--event NAME", event_missing))
        if missing
    )
    given = "and neither was given" if x_missing and event_missing else "which was not given"
    reason = f"; {_NEVER_INFERS[verb]}" if event_missing and verb in _NEVER_INFERS else ""
    who = f"{runs[0]} and {runs[1]} carry" if len(runs) == 2 else f"{runs[0]} carries"
    lines = [f"{verb} requires {flags}, {given}{reason}. {who}:"]
    if verb in ("report", "serve"):
        lines.append(f"  axes: {', '.join(axes) or 'none stored'}")
    lines.append(f"  events: {', '.join(events) or 'none stored'}")
    return _Refusal("\n".join(lines))


def _run_diffs(
    store: Store,
    a: str,
    b: str,
    *,
    verb: str,
    events: Sequence[str] | None,
    method: str,
    q: float,
    all_methods: bool,
) -> tuple[
    MultiDiffResult,
    dict[str, Any],
    tuple[RunManifest, RunManifest],
    tuple[pd.DataFrame, pd.DataFrame],
]:
    """The primary diff first (so a refusal fires before extra work), then the other two on
    the same event set.

    The raw frames come back beside the result because M14's root consumes both: it rebuilds
    the cell view from the frames and checks it against the diff, and reading the pair a second
    time here would be a second read free to disagree with the first.
    """
    fa, fb, ma, mb = _load_pair(store, a, b)
    _require_known_events(verb, events, fa, fb)
    primary = _multi(fa, fb, ma, mb, events=events, method=method, q=q)
    others: dict[str, Any] = {}
    if all_methods:
        for other in _METHODS:
            if other != method:
                others[other] = _multi(fa, fb, ma, mb, events=primary.events, method=other, q=q)
    return primary, others, (ma, mb), (fa, fb)


def _method_table(results: Sequence[MultiDiffResult]) -> str:
    header = ("method", "event", "pairing", "safer", "worse", "unchanged", "max_mde")
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for m in results:
        # ADR-052: the column states the requested method's pairing, the same fact the headline
        # states, and never the runs' seed identity -- which is its own field on the result.
        pairing = "paired" if m.method in _PAIRED_METHODS else "unpaired"
        for e in m.events:
            ev = m.by_event[e]
            lines.append(
                f"| {m.method} | {e} | {pairing} | {ev.n_safer} | {ev.n_worse} "
                f"| {ev.n_unchanged} | {ev.max_mde:.4f} |"
            )
    return "\n".join(lines) + "\n"


def _coverage_block(multi: MultiDiffResult) -> str:
    """The coverage facts ``diff``'s text output appends, after the markdown and after the
    ``--methods all`` table, exactly as ``_method_table`` already is.

    Not part of ``to_markdown()``: A20 requires a diff whose rows errored to render identically
    to one whose rows did not, so ``to_markdown()`` keeps meaning "the statistical result" and
    the coverage facts reach the reader of ``diff`` here instead (spec S21 section 3.2). The
    ``_md_cell`` style and the column order are M6's, imported rather than restated.
    """
    frame = multi.coverage
    if frame is None:  # never from ``multi_diff``; a hand-built result says nothing.
        return ""
    holes = frame[~frame["comparable"]]
    counts = {cause: int((holes["cause"] == cause).sum()) for cause in _CAUSES}
    cols = list(COVERAGE_COLUMNS)
    lines = [
        f"coverage: holes={len(holes)} (only_a={counts['only_a']}, only_b={counts['only_b']}, "
        f"no_outcome_a={counts['no_outcome_a']}, no_outcome_b={counts['no_outcome_b']}, "
        f"no_outcome_both={counts['no_outcome_both']}), "
        f"no_outcome a={int(frame['no_outcome_a'].sum())} b={int(frame['no_outcome_b'].sum())}",
        "",
        "## coverage",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "|".join("---" for _ in cols) + "|",
    ]
    for record in frame.to_dict(orient="records"):
        lines.append("| " + " | ".join(_md_cell(record[col]) for col in cols) + " |")
    return "\n".join(lines) + "\n"


def _interval_block(multi: MultiDiffResult) -> str:
    """The interval facts ``diff``'s text output appends after the coverage block.

    **One formatter, one module over.** P-1 moved the three lines and the ``R == 0`` line to
    ``report._interval_lines``, so ``report.md``, the receipt, the page's honesty band, the
    payload and this block print the same strings and none of them rewords the others. What is
    left here is layout: the second and third lines are indented two spaces, as they have been
    since S24, and the block's bytes on Go1 are unchanged.
    """
    lines = _interval_lines(multi)
    return "\n".join([lines[0], *(f"  {line}" for line in lines[1:])]) + "\n"


def _omnibus_block(dual_root: RootResult) -> str:
    """M14's root, the block ``diff``'s text output appends after the interval block.

    **The family is named and the null is quoted.** The root tests the sharp "no cell changed"
    over the same cells x events family the flat analysis runs; the other null -- the same
    shift everywhere -- is not tested here and is not printed here either.

    **Every number is a field and none of them is computed here.** That includes the last
    line's complement: ``n_cells - n_informative_cells`` is exactly the arithmetic this module
    must not do, indistinguishable to any robust rule from recovering a count the result
    already carries, so ``RootResult`` carries ``n_uninformative_cells`` and this reads it.
    ``:g`` throughout, so a p-value at the 1/4001 floor prints as 0.00024994 rather than 0.0000.

    The informative line's tail says what is true under **both** schemes: a cell no exchange
    can move contributes the same number under every draw. "identical across arms in every
    episode" is the pair-swap reading of that and is false under arm label, where a cell whose
    two arms agree is still informative if its own outcomes vary.
    """
    lines = [
        f"omnibus: {dual_root.headline()}",
        f"  min-p of location and dispersion; {dual_root.n_permutations} within-cell "
        f"permutations, {dual_root.scheme}, seed {dual_root.seed}",
        # C33 (b): every permutation p below is Phipson-Smyth's ``(1 + count) / (B + 1)`` over
        # the same B, so one field bounds all of them. ``p_floor`` is a field for the same reason
        # every other number in this block is: the renderer may not compute it (ADR-032), and it
        # prints under the same ``:g`` as the p beside it, so an at-floor p and its floor are the
        # same string on the same screen.
        f"  p floor {dual_root.p_floor:g}: the smallest p {dual_root.n_permutations} "
        f"permutations can express; a p at the floor is a bound, not a measurement",
    ]
    for event in dual_root.events:
        lines.append(
            f"  location    {event}: mean delta {dual_root.location[event]:g}, "
            f"p = {dual_root.p_location[event]:g}"
        )
    for event in dual_root.events:
        lines.append(
            f"  dispersion  {event}: rms delta {dual_root.dispersion[event]:g}, "
            f"p = {dual_root.p_dispersion[event]:g}"
        )
    lines.append(
        f"  informative cells: {dual_root.n_informative_cells} of {dual_root.n_cells}; "
        f"{dual_root.n_uninformative_cells} unchanged by every exchange"
    )
    return "\n".join(lines) + "\n"


def _fault_lines_head(cut: Grouping, fault: FaultLines) -> str:
    """The grouping, the rung that resolved it, and the shape it was admitted on.

    Every number is a field printed with ``:g`` and none of them is computed here -- that is why
    ``Grouping`` carries ``size_min``, ``size_median``, ``size_max``, ``alpha_floor`` and
    ``n_resolvable_groups`` rather than leaving them to be derived. No percentage either: a
    ``* 100`` is arithmetic, so the accepted effect prints as ``0.2`` and the executor is the
    only place that says "points".
    """
    return (
        f"fault lines: grouping {cut.key} ({cut.resolved_by}), {cut.n_groups:g} groups; "
        f"cells per group min {cut.size_min:g} / median {cut.size_median:g} / "
        f"max {cut.size_max:g}; {fault.n_degenerate_groups:g} degenerate; "
        f"{cut.n_resolvable_groups:g} of {cut.n_groups:g} groups resolve "
        f"{cut.max_group_mde:g} at alpha {cut.alpha_floor:g}"
    )


def _fault_lines_null(fault: FaultLines) -> str:
    """The null in quotes, and either what tested it or why nothing did.

    **A level that was not tested is stated, not omitted**, and it is stated without a
    conditional: the gate is the procedure and the claim is not, so nothing here says "given the
    root rejected". The root's reason wins over the level's shape when both apply.
    """
    if fault.tested:
        return (
            f'  "{fault.null}" tested by BH across {fault.n_groups:g} groups at '
            f"q {fault.q:g}: {fault.n_rejected_groups:g} rejected"
        )
    if fault.reason == "one_group":
        return f'  "{fault.null}" not tested: one group is the whole family restated'
    return f'  "{fault.null}" not tested: the root did not reject'


def _fault_lines_group(key: str, group: GroupResult) -> str:
    """One group: what it holds, what could move in it, and -- when tested -- its verdict.

    The counts and the design numbers print whether or not the level was tested; the p-values
    print only when they exist, because there is no such thing as a p-value for a level nobody
    tested and a number that exists would be read.
    """
    line = (
        f"  {key}={group.label}  {group.n_cells:g} cells, "
        f"{group.n_informative_cells:g} informative, "
        f"{group.n_uninformative_cells:g} unchanged by every exchange; "
        f"{group.n_a:g} units in a, {group.n_b:g} in b; group MDE {group.mde:g}"
    )
    if group.n_discordant is not None:
        line = f"{line}; {group.n_discordant:g} discordant pairs"
    if group.p_group is None or group.q_group is None:
        return line
    verdict = "rejected" if group.rejects else "not rejected"
    return f"{line}; p {group.p_group:g}, q {group.q_group:g}: {verdict}"


def _fault_lines_block(nested: TreeResult) -> str:
    """Level 2, the block ``diff``'s text output appends after the omnibus block.

    **Which kind of work moved, never where anything broke.** The second vocabulary is forbidden
    on the first Level 2 byte this project prints, and no line here reaches for it.

    The block is its first line plus every following line indented two spaces, and it is never
    the tail of stdout: P4.3 appends after it. The chain comes first so the grouping a reader
    might have expected is accounted for before any verdict; the group lines come last, one per
    group in label order, never ordered by result -- an ordering by verdict is a rendering choice
    and a pre-registration hazard here.
    """
    lines = [_fault_lines_head(nested.grouping, nested.fault_lines)]
    for refusal in nested.grouping.refused:
        lines.append(
            f"  refused {refusal.key} ({refusal.rung}): {refusal.reason}; {refusal.detail} "
            f"next: {refusal.next_rung}"
        )
    lines.append(_fault_lines_null(nested.fault_lines))
    if nested.fault_lines.tested:
        # Only where the level was tested: there is no floor under a p nobody drew.
        lines.append(
            f"  group p floor {nested.root.p_floor:g}: the same "
            f"{nested.root.n_permutations} permutations; a group p at the floor is a bound, "
            "not a measurement"
        )
    for group in nested.fault_lines.groups:
        lines.append(_fault_lines_group(nested.grouping.key, group))
    return "\n".join(lines) + "\n"


def _cells_head(leaves: Leaves, bound: Bound) -> str:
    """The null in quotes and what tested it, or the first reason nothing did.

    **A level that was not tested is stated, not omitted**, and it is stated without a
    conditional: the gate is the procedure and the claim is not, so nothing here says "given the
    group rejected". The reasons are the module's, in the module's order -- the configuration
    before the root, the root before the level.
    """
    if leaves.tested:
        return (
            f'cells: "{leaves.null}" tested by BH within each of {leaves.n_families:g} '
            f"rejecting groups at q {leaves.q:g}: {leaves.n_rejected:g} of "
            f"{leaves.n_tests:g} rejected"
        )
    if leaves.reason == "depth":
        return f"cells: not tested: depth {bound.depth_configured:g}"
    if leaves.reason == "root_not_rejected":
        return "cells: not tested: the root did not reject"
    return "cells: not tested: no group rejected"


def _cells_family(family: CellFamily) -> str:
    """One rejected group's family: how many tests were in it, how many it could name, and what
    its cells could not have seen.

    The two MDEs are fields for the same reason every other number on every other block is: a
    median computed here would be arithmetic on a tree field, and ``CellFamily`` carries both.
    """
    return (
        f"  {family.key}={family.label}  {family.n_tests:g} tests, "
        f"{family.n_rejected:g} rejected; cell MDE median {family.mde_median:g} "
        f"/ max {family.mde_max:g}"
    )


def _cells_leaf(leaf: CellResult) -> str:
    """One named cell: its config, its event, and three numbers.

    ``delta``, ``q_within`` and ``mde`` -- never ``p`` alone, which a reader would compare to
    ``q``; never the flat family's ``q``, which is a verdict from a different selection; never
    an interval and never a rate. Naming a cell says *this configuration's outcome rate moved*,
    which is what the grid analysis has said since S3; the second vocabulary is as forbidden
    here as on a group line.
    """
    config = ", ".join(f"{key}={value}" for key, value in leaf.config.items())
    return (
        f"    {config}  {leaf.event}: delta {leaf.delta:g}, "
        f"q {leaf.q_within:g}, MDE {leaf.mde:g}"
    )


def _cells_block(nested: TreeResult) -> str:
    """Level 3, the block ``diff``'s text output appends after the fault-lines block.

    Its head sits at column 0 and every other line is indented, which is what ends the
    fault-lines block above it: F15 and F20 read that block's last ``n_groups`` lines as the
    group lines, and a head indented two spaces would be swallowed by both.

    One family line per family in ``families`` order, and under each, one line per **rejected**
    cell in the family's own row order -- never ordered by result. A cell that did not reject is
    in the JSON and not here: the family line's counts and MDEs are what it contributes.
    """
    lines = [_cells_head(nested.leaves, nested.bound)]
    for family in nested.leaves.families:
        lines.append(_cells_family(family))
        for leaf in family.cells:
            if leaf.rejects:
                lines.append(_cells_leaf(leaf))
    return "\n".join(lines) + "\n"


def _bound_block(bound: Bound) -> str:
    """The error rate the whole procedure controls at, and the assumption it rests on.

    The head line spells out which set the number is over -- there are two universal bounds in
    the source over two different sets, and this is the one over the findings a reader acts on.
    Every number is a field printed with ``:g``; the ``2`` and the ``x``s are text around four
    of them, and no arithmetic happens here.

    The second line is the assumption, and it is on the block rather than in a footnote because
    the condition the source states is one this tree's construction does not give: a group's
    statistic aggregates its own cells, so a null cell's p is not independent of its ancestors'.
    """
    lines = [
        f"bound: depth {bound.depth:g} ({bound.depth_configured:g} configured); "
        f"outer-nodes false discovery rate at most {bound.bound:g} = "
        f"2 x {bound.depth:g} x {bound.q:g} x {bound.delta_star:g}",
        "  Yekutieli (2008) Corollary A.2, which assumes each p-value is independent of its "
        "ancestors; this tree's group and root statistics aggregate their own cells, so that "
        "assumption is not established here",
    ]
    return "\n".join(lines) + "\n"


def _write_summary(io: _IO, multi: MultiDiffResult) -> None:
    """Inference line when inferred, the headline, and the trade line when present."""
    if multi.inferred:
        io.out.write(multi.to_markdown().splitlines()[0] + "\n")
    io.out.write(multi.headline() + "\n")
    trade = multi.trade_line()
    if trade is not None:
        io.out.write(trade + "\n")


class _Progress:
    """``done/total`` on one rewritten line when stdout is a TTY, else one line per 10%."""

    def __init__(self, out: TextIO) -> None:
        self.out = out
        self.tty = bool(out.isatty())
        self.decile = 0
        self.dirty = False

    def __call__(self, done: int, total: int) -> None:
        if self.tty:
            self.out.write(f"\r{done}/{total}")
            self.out.flush()
            self.dirty = True
            return
        decile = done * 10 // total if total else 10
        if decile > self.decile:
            self.decile = decile
            self.out.write(f"{done}/{total}\n")
            # Flushed for the same reason ``serve`` flushes its URL: stdout is block buffered
            # when it is a pipe, so an unflushed decile arrives with the summary at the end,
            # and progress that only appears once the run is over is not progress. This is the
            # non-TTY branch, which is CI and every ``| tee`` -- exactly where a long sweep is
            # watched through a pipe.
            self.out.flush()

    def finish(self) -> None:
        if self.dirty:
            self.out.write("\n")


# ---------- sweep ----------


def _resolve_target(target: str) -> Any:
    """Import the local branch's rollout, turning any refusal at import into exit 2.

    A module that raises at import because it is outside the boundary it demands -- the golden
    pilot's agent, on a laptop -- raises RuntimeError, which is a refusal of this target and
    not a bug in Prove, so it exits 2 naming the path like the other three.
    """
    try:
        return resolve(target)
    except (ValueError, ImportError, AttributeError, RuntimeError) as exc:
        raise _Refusal(f"cannot resolve --target {target!r}: {exc}") from exc


def _modal_config(ns: argparse.Namespace, spec_path: Path) -> tuple[ModalTarget, ModalOptions]:
    """``[modal]`` -> ModalOptions, ``[modal.<--image>]`` -> ImageSpec; flags override the table."""
    with spec_path.open("rb") as fh:
        data = tomllib.load(fh)
    table = data.get("modal", {})
    if not isinstance(table, Mapping):
        raise _Refusal(f"[modal] in {spec_path} must be a table")
    sections = {k: v for k, v in table.items() if isinstance(v, Mapping)}
    scalars = {k: v for k, v in table.items() if not isinstance(v, Mapping)}

    image_table = sections.get(ns.image)
    if image_table is None:
        if ns.image != "image":
            raise _Refusal(f"no [modal.{ns.image}] table in {spec_path}")
        image_table = {}
    try:
        image = ImageSpec(**image_table)
    except (TypeError, ValueError) as exc:
        raise _Refusal(f"[modal.{ns.image}]: {exc}") from exc
    try:
        options = ModalOptions(**scalars)
    except (TypeError, ValueError) as exc:
        raise _Refusal(f"[modal]: {exc}") from exc

    overrides = {
        name: value
        for name, value in (
            ("concurrency", ns.concurrency),
            ("infra_retries", ns.infra_retries),
            ("max_cost", ns.max_cost),
            ("est_seconds_per_episode", ns.est_seconds),
            ("app_name", ns.app_name),
            ("batch_size", ns.batch_size),
            ("episode_timeout", ns.episode_timeout),
            ("max_rollouts", ns.max_rollouts),
        )
        if value is not None
    }
    options = dataclasses.replace(options, **overrides)
    try:
        target = ModalTarget(import_path=ns.target, image=image)
    except ValueError as exc:
        raise _Refusal(str(exc)) from exc
    return target, options


def _recorded_max_mde(store: Store, resume: str | None) -> float | None:
    """The accepted value a resumed run already recorded, or None when there is none.

    A resume is the same run and inherits its own admission; re-litigating it would train
    people to pass the flag reflexively. ``--pair-with`` is not read here, deliberately: a
    paired arm is a different run making its own claim, and the flag is one word.

    Read defensively. A run id that is not in the store is ``plan``'s refusal to make and not
    this helper's, and a run stored before the gate existed has no such key.
    """
    if resume is None:
        return None
    try:
        recorded = store.manifest(resume).environment.get("max_mde_accepted")
    except StoreError:
        return None
    return float(recorded) if isinstance(recorded, (int, float)) else None


def _confirm(ns: argparse.Namespace, io: _IO) -> None:
    """Prompt once, read exactly one line; anything but y/yes declines. Never hang in CI."""
    if ns.yes:
        return
    if not io.inp.isatty():
        raise _Refusal("stdin is not a terminal; pass --yes to skip the pre-flight prompt")
    io.out.write("Proceed? [y/N] ")
    io.out.flush()
    answer = io.inp.readline().strip().lower()
    if answer not in ("y", "yes"):
        raise _Refusal("declined at pre-flight; nothing was run")


def _burla_config(ns: argparse.Namespace, spec_path: Path) -> BurlaOptions:
    """``[burla]`` -> BurlaOptions; the flags a Burla run accepts override the table."""
    try:
        options = BurlaOptions.from_sweep_file(spec_path)
        overrides = {
            name: value
            for name, value in (
                ("max_cost", ns.max_cost),
                ("est_seconds_per_episode", ns.est_seconds),
                ("infra_retries", ns.infra_retries),
                ("episode_timeout", ns.episode_timeout),
                ("max_rollouts", ns.max_rollouts),
                ("batch_size", ns.batch_size),
            )
            if value is not None
        }
        return dataclasses.replace(options, **overrides)
    except (TypeError, ValueError) as exc:
        raise _Refusal(f"[burla] in {spec_path}: {exc}") from exc


def _cmd_sweep(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    if ns.backend == "local":
        stray = [name for name in _MODAL_ONLY_FLAGS if getattr(ns, name) is not None]
        if stray or ns.image != "image":
            names = ", ".join("--" + n.replace("_", "-") for n in stray) or "--image"
            raise _Refusal(f"{names} only applies to --backend modal")
    if ns.backend == "burla":
        stray = [name for name in _BURLA_REFUSED_FLAGS if getattr(ns, name) is not None]
        if stray or ns.image != "image":
            names = ", ".join("--" + n.replace("_", "-") for n in stray) or "--image"
            raise _Refusal(f"{names} does not apply to --backend burla")
    spec_path = Path(ns.spec)
    spec = SweepSpec.load(spec_path)
    if ns.backend == "modal":
        # The container is the resolver: this machine only checks the path's shape, which
        # ModalTarget does. A target importable solely inside its image -- the case the Modal
        # backend exists for -- must not be imported here (ADR-029).
        target, options = _modal_config(ns, spec_path)
    else:
        # Local and Burla both run this machine's code: Burla's workers run it from the bundle.
        rollout = _resolve_target(ns.target)
    if ns.backend == "burla":
        burla_options = _burla_config(ns, spec_path)
    store = Store(root)
    p: Plan = plan(
        spec,
        store,
        backend=ns.backend,
        run_salt=ns.salt,
        pair_with=ns.pair_with,
        resume=ns.resume,
        import_path=ns.target,
        max_mde_accepted=(
            ns.max_mde if ns.max_mde is not None else _recorded_max_mde(store, ns.resume)
        ),
    )

    # Describe, then decide, then ask. The reader who gets the refusal has already been shown
    # the MDE line it is about, and `--yes` skips only the prompt: the threshold, the
    # comparison and the message all live in M3 (spec S23 sections 3 and 6).
    if ns.backend == "modal":
        io.out.write(preflight_modal(p, target, options))
    elif ns.backend == "burla":
        io.out.write(preflight_burla(p, ns.target, burla_options))
    else:
        io.out.write(preflight(p))
    check_power(p, max_mde=p.max_mde_accepted)
    _confirm(ns, io)

    state.run_id = p.run_id
    progress = _Progress(io.out)
    summary: RunSummary
    if ns.backend == "modal":
        summary = run_modal(p, target, store, options=options, on_progress=progress)
    elif ns.backend == "burla":
        summary = run_burla(p, ns.target, store, options=burla_options, on_progress=progress)
    else:
        summary = run_local(
            p,
            rollout,
            store,
            episode_timeout=ns.episode_timeout,
            max_rollouts=ns.max_rollouts,
            batch_size=_DEFAULT_BATCH_SIZE if ns.batch_size is None else ns.batch_size,
            on_progress=progress,
        )
    progress.finish()
    for field in dataclasses.fields(summary):
        if field.name == "run_id":
            continue
        value = getattr(summary, field.name)
        text = f"{value:.3f}" if isinstance(value, float) else str(value)
        io.out.write(f"{field.name}: {text}\n")
    io.out.write(f"run_id: {summary.run_id}\n")
    return 0


# ---------- diff / report / check ----------


def _cmd_diff(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    primary, others, manifests, frames = _run_diffs(
        Store(root),
        ns.a,
        ns.b,
        verb="diff",
        events=ns.event,
        method=ns.method,
        q=ns.q,
        all_methods=ns.methods == "all",
    )
    # The root refuses an empty family (M14's O13), and ``diff`` on a pair with no comparable
    # cell exits 0 today. Turning that into exit 2 is a change to a path no test pins and it is
    # not this packet's to make, so the block is skipped there and the verb keeps its exit
    # code. Deleting this guard is the whole of the amendment when the exit code is settled.
    wanted = primary.n_tests > 0
    if ns.format == "json":
        payload: Any = primary.to_json()
        if others:
            # ``--methods all`` keeps its three-method shape (draft ADR-070): the scheme follows
            # the method, so one omnibus and one tree beside three method objects would claim
            # one test across three. The per-method shape is three draws and is not built.
            payload = {primary.method: payload, **{m: d.to_json() for m, d in others.items()}}
        elif wanted:
            nested = _diff_tree(ns, primary, frames, manifests)
            payload = {**payload, "omnibus": nested.root.to_json(), "tree": nested.to_json()}
        io.out.write(json.dumps(payload, indent=2) + "\n")
        return 0
    io.out.write(primary.to_markdown())
    if others:
        io.out.write("\n" + _method_table([primary, *others.values()]))
    coverage = _coverage_block(primary)
    if coverage:
        io.out.write("\n" + coverage)
    io.out.write("\n" + _interval_block(primary))
    if wanted:
        # One call, one draw: the omnibus block and the fault-lines block are two renderings of
        # one ``TreeResult`` rather than two permutation streams that happen to share a seed.
        nested = _diff_tree(ns, primary, frames, manifests)
        io.out.write("\n")
        io.out.write(_omnibus_block(nested.root))
        io.out.write("\n")
        io.out.write(_fault_lines_block(nested))
        io.out.write("\n")
        io.out.write(_cells_block(nested))
        io.out.write("\n")
        io.out.write(_bound_block(nested.bound))
    return 0


def _diff_tree(
    ns: argparse.Namespace,
    multi: MultiDiffResult,
    frames: tuple[pd.DataFrame, pd.DataFrame],
    manifests: tuple[RunManifest, RunManifest],
) -> TreeResult:
    """``tree`` on the pair ``multi`` was computed from, with the four flags that move it.

    The three new ones are passed through untouched: ``--by`` is verbatim and case-sensitive,
    and the range checks on ``--max-group-mde`` and ``--depth`` live in ``tree.py`` by the
    analogy M6's ``0 < q < 1`` and S23's ``check_power`` already set. Argparse's ``choices``
    refuses a depth this parser was not offered, which is the parser's own refusal and not the
    check: this module parses an int and a float and decides nothing.
    """
    return tree(
        frames[0],
        frames[1],
        multi,
        manifest_a=manifests[0],
        manifest_b=manifests[1],
        by=ns.by,
        n_permutations=ns.permutations,
        seed=ns.seed,
        max_group_mde=ns.max_group_mde,
        depth=ns.depth,
    )


def _prepare_out_dir(ns: argparse.Namespace, default: str) -> Path:
    """Refuse a non-empty ``--out`` before any work unless ``--force``; nothing is created yet."""
    out_dir = Path(ns.out) if ns.out else Path(default)
    if out_dir.exists():
        if not out_dir.is_dir():
            raise _Refusal(f"--out {out_dir} exists and is not a directory")
        if any(out_dir.iterdir()) and not ns.force:
            raise _Refusal(f"--out {out_dir} exists and is not empty; pass --force to overwrite")
    return out_dir


def _write_report_files(
    io: _IO,
    out_dir: Path,
    report: MultiReport | SurvivalReport,
    receipt: MultiReport | SurvivalReport,
    bundle: _Bundle | None = None,
) -> None:
    """With a paired ``bundle`` the four sections are folded into the rendered strings and the
    artifacts are written beside the three files; without one every byte is what it was."""
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown, page = report.to_markdown(), receipt.to_html()
    if bundle is not None:
        markdown, page = _fold_markdown(markdown, bundle), _fold_html(page, bundle)
    (out_dir / "report.md").write_text(markdown)
    (out_dir / "heatmap.svg").write_text(report.to_svg())
    (out_dir / "receipt.html").write_text(page)
    for name in _REPORT_FILES:
        io.out.write(f"{out_dir / name}\n")
    if bundle is not None:
        for name, artifact in bundle.artifacts.items():
            (out_dir / name).write_text(_artifact_text(artifact))
            io.out.write(f"{out_dir / name}\n")


def _cmd_report(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    """The positional arity picks the verb: two run ids diff, one run id is a survival report."""
    runs: list[str] = list(ns.runs)
    if len(runs) not in (1, 2):
        raise _Refusal(f"report takes one or two run ids, got {len(runs)}: {_REPORT_FORMS}")
    if ns.x is None:
        raise _missing_flags_refusal(
            Store(root), "report", runs, x_missing=True, event_missing=False
        )
    if len(runs) == 2:
        return _report_pair(ns, io, root, runs[0], runs[1])
    return _report_run(ns, io, root, runs[0])


def _report_pair(ns: argparse.Namespace, io: _IO, root: Path, a: str, b: str) -> int:
    stray = [f"--{name}" for name in _RUN_ONLY_FLAGS if getattr(ns, name) is not None]
    if stray:
        raise _Refusal(
            f"{', '.join(stray)}: single-run flag{'s' if len(stray) > 1 else ''}; a diff report "
            f"takes its horizon from the two runs ({_REPORT_FORMS})"
        )
    out_dir = _prepare_out_dir(ns, f"./prove-report-{_slug(a)}-vs-{_slug(b)}")
    declaration = None if ns.paired is None else _paired_declaration(ns.paired, a, b)
    fixed = _parse_pairs(ns.fix, "--fix")
    method = _DEFAULT_METHOD if ns.method is None else ns.method
    q = _DEFAULT_Q if ns.q is None else ns.q

    store = Store(root)
    multi, others, manifests, frames = _run_diffs(
        store,
        a,
        b,
        verb="report",
        events=ns.event,
        method=method,
        q=q,
        all_methods=ns.methods == "all",
    )
    spec = ReportSpec(
        title=ns.title if ns.title else f"{a} vs {b}: {', '.join(multi.events)}",
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=fixed,
        comparison=others,
        theme=ns.theme,
        top_n=ns.top_n,
        forest=ns.forest,
    )
    nested: TreeResult | None = None
    if multi.n_tests > 0:
        # ``report`` parses the five tree flags with no default so the single-run form can refuse
        # one that was given; here an absent knob becomes M14's constant, by name. They go on a
        # copy of the namespace, because ``_diff_tree`` reads its knobs off ``ns`` and ``diff``
        # shares it, and the parsed namespace keeps telling absent from given. An empty family
        # grows no tree: M7's axis check refuses it below with the message it has always had.
        knobs = argparse.Namespace(**vars(ns))
        for name, constant in (
            ("permutations", DEFAULT_PERMUTATIONS),
            ("seed", DEFAULT_SEED),
            ("depth", DEFAULT_DEPTH),
        ):
            if getattr(knobs, name) is None:
                setattr(knobs, name, constant)
        nested = _diff_tree(knobs, multi, frames, manifests)
    observations = (_observation_counts(store, a), _observation_counts(store, b))
    declarations = (_declaration_check(store, a), _declaration_check(store, b))
    # One tree for both builds: the light receipt renders the same draw, never a second one.
    report = build_multi_report(
        multi,
        spec,
        manifests=manifests,
        tree=nested,
        observations=observations,
        declarations=declarations,
    )
    receipt = (
        report
        if spec.theme == "light"
        else build_multi_report(
            multi,
            dataclasses.replace(spec, theme="light"),
            manifests=manifests,
            tree=nested,
            observations=observations,
            declarations=declarations,
        )
    )
    _write_summary(io, multi)
    bundle = None if declaration is None else _bundle(store, declaration)
    _write_report_files(io, out_dir, report, receipt, bundle)
    return 0


def _paired_declaration(path: str, a: str, b: str) -> Declaration:
    """``report A B --paired DECL``: ``(A, B)`` must be the declared pair of one of the
    declaration's sweeps; any other pair is refused by name. The sections then cover every
    declared sweep, because the replications are the point."""
    declaration = Declaration.from_toml(path)
    declared = {(sweep.a, sweep.b): sweep.name for sweep in declaration.sweeps}
    if (a, b) not in declared:
        pairs = ", ".join(f"{s.name}: ({s.a}, {s.b})" for s in declaration.sweeps)
        raise _Refusal(
            f"--paired: ({a}, {b}) is not the declared pair of any sweep in {path}; the "
            f"declaration pairs {pairs}"
        )
    return declaration


def _cmd_paired(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    """The assertion, the analysis, the windows, the cost with one phase per declared sweep,
    and the replicates, written as the five artifacts (six at ``k > 2``). ``--format json``
    prints the combined payload and writes nothing; ``--cap-check`` prints the cost block alone
    and exits 1 at or above the declared token cap, the module's one exit-code path."""
    declaration = Declaration.from_toml(ns.declaration)
    store = Store(root)
    if ns.cap_check:
        report = paired_cost(
            store, declaration, phases={s.name: s.arms for s in declaration.sweeps}
        )
        io.out.write(_artifact_text(_cost_block(declaration, report)) + "\n")
        return 1 if report.cap_reached else 0
    if ns.format == "json":
        io.out.write(_artifact_text(_bundle(store, declaration).payload) + "\n")
        return 0
    out_dir = _prepare_out_dir(ns, f"./prove-paired-{declaration.digest[:12]}")
    bundle = _bundle(store, declaration)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, artifact in bundle.artifacts.items():
        (out_dir / name).write_text(_artifact_text(artifact))
        io.out.write(f"{out_dir / name}\n")
    return 0


def _report_run(ns: argparse.Namespace, io: _IO, root: Path, run: str) -> int:
    # Each named as it was typed: --max-group-mde, not the namespace's max_group_mde.
    given = [
        f"--{name.replace('_', '-')}" for name in _DIFF_ONLY_FLAGS if getattr(ns, name) is not None
    ]
    if given:
        raise _Refusal(
            f"{', '.join(given)}: diff-only flag{'s' if len(given) > 1 else ''}; "
            f"a single-run report compares nothing ({_REPORT_FORMS})"
        )
    out_dir = _prepare_out_dir(ns, f"./prove-report-{_slug(run)}")
    fixed = _parse_pairs(ns.fix, "--fix")

    store = Store(root)
    manifest = store.manifest(run)
    df = store.read(run, meta=False)
    _require_known_events("report", ns.event, df)
    inferred = ns.event is None
    if inferred:
        try:
            # One frame, so the second arm is an empty slice of it: infer_events pools both
            # arms for its counts, and passing df twice would double every count it reports.
            events, non_event = infer_events(df, df.iloc[0:0])
        except EventInferenceError as exc:
            raise _Refusal(
                f"cannot infer the event set: {exc}; outcome counts: {_outcome_counts(df)}; "
                "pass --event NAME (repeatable)"
            ) from exc
    else:
        events, non_event = tuple(dict.fromkeys(str(e) for e in ns.event)), None
    valid_t = df["t"].dropna()
    if valid_t.empty:
        raise _Refusal(f"run {run} has no rows with a time; nothing to report")
    horizon = float(valid_t.max()) if ns.horizon is None else float(ns.horizon)
    if horizon <= 0.0:
        raise _Refusal(f"--horizon must be > 0, got {horizon}")

    # The Aalen-Johansen competing set is every terminal outcome present, not only the events
    # asked for: a row that ended in the non-event is absorbed, not censored, so it must stay
    # out of the risk set. This is the call site that printed 100% violated in S13 by passing
    # only ``events``; the helper is the one construction (ADR-021), and multi_diff uses it too.
    competing = list(competing_set(df))
    cells = cell_table(df, events[0], horizon=horizon, method="aj", events=competing)
    spec = ReportSpec(
        title=ns.title if ns.title else f"{run}: {', '.join(events)}",
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=fixed,
        theme=ns.theme,
        top_n=ns.top_n,
        forest=ns.forest,
    )
    observations = _observation_counts(store, run)
    declarations = _declaration_check(store, run)
    report = build_survival_report(
        cells,
        spec,
        events=events,
        horizon=horizon,
        manifest=manifest,
        observations=observations,
        declarations=declarations,
    )
    receipt = (
        report
        if spec.theme == "light"
        else build_survival_report(
            cells,
            dataclasses.replace(spec, theme="light"),
            events=events,
            horizon=horizon,
            manifest=manifest,
            observations=observations,
            declarations=declarations,
        )
    )
    if inferred:
        io.out.write(
            f"inferred: no event was given, so the event set is {', '.join(events)}; "
            f"the non-event is {non_event}, the most frequent outcome\n"
        )
    io.out.write(
        f"{run}: survival report over {', '.join(events)} at horizon "
        f"{report.provenance['horizon']}\n"
    )
    _write_report_files(io, out_dir, report, receipt)
    return 0


def _cmd_check(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    store = Store(root)
    if ns.event is None:
        raise _missing_flags_refusal(
            store, "check", [ns.a, ns.b], x_missing=False, event_missing=True
        )
    multi, _, _, _ = _run_diffs(
        store,
        ns.a,
        ns.b,
        verb="check",
        events=ns.event,
        method=ns.method,
        q=ns.q,
        all_methods=False,
    )
    passed = multi.check(fail_on=ns.fail_on)
    _write_summary(io, multi)
    io.out.write("PASS\n" if passed else "FAIL\n")
    return 0 if passed else 1


def _cmd_serve(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    """``_report_pair`` up to the report, then a structure instead of three files.

    The structure is complete before anything binds, so every refusal happens with no listening
    socket in existence, and ``--json`` returns having bound nothing at all. Nothing on this
    path writes to the store, to the cwd, or to a temp file.
    """
    runs: list[str] = list(ns.runs)
    if len(runs) != 2:
        raise _Refusal(f"serve takes two run ids, got {len(runs)}: {_SERVE_FORM}")
    a, b = runs[0], runs[1]
    store = Store(root)
    if ns.x is None or ns.event is None:
        raise _missing_flags_refusal(
            store, "serve", [a, b], x_missing=ns.x is None, event_missing=ns.event is None
        )
    fixed = _parse_pairs(ns.fix, "--fix")
    multi, _, manifests, frames = _run_diffs(
        store,
        a,
        b,
        verb="serve",
        events=ns.event,
        method=ns.method,
        q=ns.q,
        all_methods=False,
    )
    spec = ReportSpec(
        title=ns.title if ns.title else f"{a} vs {b}: {', '.join(multi.events)}",
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=fixed,
        theme=ns.theme,
        top_n=ns.top_n,
        forest=ns.forest,
    )
    report = build_multi_report(
        multi,
        spec,
        manifests=manifests,
        observations=(_observation_counts(store, a), _observation_counts(store, b)),
        declarations=(_declaration_check(store, a), _declaration_check(store, b)),
    )
    # After the report and before the structure: M7's axis check refuses an unknown ``--x``
    # first, so no refusal spends a tree, and every tree refusal -- an unknown ``--by``, an
    # out-of-range ``--max-group-mde`` -- still fires before anything binds. One call, one
    # draw, on the frames ``_run_diffs`` already read.
    nested = _diff_tree(ns, multi, frames, manifests)
    structure = build_structure(
        report,
        multi,
        tree=nested,
        manifest_a=manifests[0],
        manifest_b=manifests[1],
        rows_a=store.count(a),
        rows_b=store.count(b),
        tally_a=store.tally(a),
        tally_b=store.tally(b),
        store_root=str(root),
    )
    if ns.json:
        io.out.write(json.dumps(structure, indent=2, sort_keys=False, allow_nan=False) + "\n")
        return 0

    def announce(srv: Any) -> None:
        # The only line this verb writes, and only once the socket is up: an ephemeral port
        # nobody is told about is a page nobody can open. Flushed because stdout is block
        # buffered when it is a pipe, and a URL that arrives when the server is killed is a
        # URL nobody was handed.
        io.out.write(f"http://{_HOST}:{srv.server_address[1]}/\n")
        io.out.flush()

    serve_page(render_html(structure), on_bind=announce)
    return 0


# ---------- inspect / runs ----------


def _envelopes(store: Store, run: str) -> pd.DataFrame:
    """The run's narrow frame with its trace envelopes: the one read the observation counts and
    the declaration check share. No observation body is decoded, and on a run written after the
    split neither is ``meta``."""
    return store.read(run, meta=False, trace="envelope")


def _declaration_check(store: Store, run: str) -> Any:
    """A10: what the run declared against its stored envelopes, or ``None`` when it declared
    nothing. Typed ``Any`` because ``DeclarationCheck`` is not among this module's imports
    (FR18 pins them); the builders name the type."""
    return declaration_check(store.manifest(run), _envelopes(store, run))


def _observation_counts(store: Store, run: str) -> tuple[int, int]:
    """``(spans, spans stamped as cut)`` over the run's stored envelopes.

    The envelope read and nothing else. Whether the second number says anything about this run
    is ``report``'s to decide from the manifest; this counts what is stored.
    """
    frame = _envelopes(store, run)
    spans = [
        span
        for envelope in frame["trace"]
        if isinstance(envelope, Mapping)
        for span in envelope.get("spans", ())
        if isinstance(span, Mapping)
    ]
    return len(spans), sum(1 for span in spans if span.get("truncated") == "observation")


def _stored_trace(meta: Any) -> Trace | None:
    """The row's stored trace, or None when there is no readable one.

    The schema check *is* ``from_dict``: a trace it rejects is an absent trace, printed the
    same way -- no trace block and no error.
    """
    if not isinstance(meta, Mapping):
        return None
    trace = meta.get("trace")
    if not isinstance(trace, Mapping):
        return None
    try:
        return Trace.from_dict(trace)
    except (TraceValidationError, TypeError):
        return None


def _cmd_inspect(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    store = Store(root)
    manifest = store.manifest(ns.run)
    if ns.event is None:
        raise _missing_flags_refusal(
            store, "inspect", [ns.run], x_missing=False, event_missing=True
        )
    check = _declaration_check(store, ns.run)
    if check is not None:
        # A10: what the run declared against what its envelopes hold -- once, before the rows,
        # in the provenance block's own line form. A run that declared nothing prints nothing.
        for line in _provenance_lines(check.provenance()):
            io.out.write(f"{line}\n")
        io.out.write("\n")
    # Select on the narrow frame; decode ``meta`` only for the rows that survive selection.
    df = store.read(ns.run, meta=False)
    where = _parse_pairs(ns.where, "--where")
    # An event is an outcome or an error. "timeout" is the executor's error and may also be a
    # target's outcome (the mock agent's); both kinds print under one --event, told apart by
    # the block's shape.
    rows = df[(df["outcome"] == ns.event) | (df["error"] == ns.event)]
    for key, value in where.items():
        # Labels, not a boolean list: ``rows[[]]`` on an empty selection is a column selection,
        # and the sort below then raises on the columns it no longer has.
        keep = [
            label
            for label, cfg in zip(rows.index, rows["config"], strict=True)
            if isinstance(cfg, Mapping) and cfg.get(key) == value
        ]
        rows = rows.loc[keep]
    rows = rows.sort_values(["config_hash", "replicate_index"], kind="stable")
    if ns.limit is not None:
        rows = rows.head(max(ns.limit, 0))
    if rows.empty:
        io.out.write(f"no rows with outcome or error {ns.event!r} in run {ns.run}\n")
        return 0
    selected = [
        (str(h), int(i))
        for h, i in zip(rows["config_hash"], rows["replicate_index"], strict=True)
    ]
    rows = store.read(ns.run, keys=selected)
    # The keyed read promises sorted rows and nothing more; sorting again is the no-op that
    # keeps this loop's order the store's, whatever read(keys=) does later.
    rows = rows.sort_values(["config_hash", "replicate_index"], kind="stable")

    for row in rows.itertuples(index=False):
        io.out.write(f"config_hash: {row.config_hash}\n")
        io.out.write(f"config: {json.dumps(row.config, sort_keys=True)}\n")
        io.out.write(f"seed: {row.seed}\n")
        io.out.write(f"replicate_index: {row.replicate_index}\n")
        if isinstance(row.error, str):
            # The errored row: no outcome and no time, its error where the ok row's t: line
            # stands. The ok row keeps the shape M10's I15/I16 pin.
            io.out.write("outcome: -\n")
            io.out.write("t: -\n")
            io.out.write(f"error: {row.error}\n")
        else:
            io.out.write(f"t: {row.t}\n")
        trace = _stored_trace(row.meta)
        if trace is not None:
            if trace.truncated is not None:
                # Begins with a letter, so it can never read as a span line.
                io.out.write(f"trace: truncated ({trace.truncated})\n")
            cut = [
                (j, span)
                for j, span in enumerate(trace.ordered())
                if span.truncated == "observation"
            ]
            if cut:
                # Its own line, after the trace-level one: that says why the forest stops, this
                # says which values in it were bounded and by what. The limit is the run's own
                # record of it, spelled as recorded, and a size is the value's original length,
                # not what was over the limit.
                limits = _observation_cap(manifest)
                limit = "not recorded" if limits is None else ", ".join(
                    f"{name}={value}" for name, value in limits.items()
                )
                sizes = [
                    f"span {j}"
                    if span.bytes_original is None
                    else f"span {j}: {span.bytes_original} bytes originally"
                    for j, span in cut
                ]
                detail = "; ".join([f"limit {limit}", *sizes])
                io.out.write(f"observation: cut ({detail})\n")
            for j, span in enumerate(trace.ordered()):
                duration = span.duration_ms
                # Tab-delimited: a span name and an error message are free text and OTel
                # spells names like "invoke_agent planner", so a space cannot be the column
                # separator without shifting every column after it.
                # Nine columns: A8a's four after error, each "-" when not recorded. operation and
                # outcome_by are not printed: a row reader shows what a person reading a failed
                # episode asks for, not every field. A cut is not one of the fields left out; it
                # is the row's ``observation:`` line, above.
                io.out.write(
                    f"  {j}\t{span.kind or '-'}\t{span.name or '-'}\t"
                    f"{'-' if duration is None else duration}\t"
                    f"{'-' if span.error in (None, '') else span.error}\t"
                    f"{'-' if span.step_name is None else span.step_name}\t"
                    f"{'-' if span.attempt is None else span.attempt}\t"
                    f"{'-' if span.outcome is None else span.outcome}\t"
                    f"{'-' if span.gate is None else span.gate}\n"
                )
        io.out.write("\n")

    first = rows.iloc[0]
    import_path = manifest.environment.get("import_path")
    if isinstance(import_path, str) and ":" in import_path:
        module, fn = import_path.split(":", 1)
    else:
        module, fn = "your_module", "rollout"
    io.out.write(f"{_SNIPPET_MARKER}\n")
    io.out.write(f"from {module} import {fn}\n")
    io.out.write(f"{fn}({json.dumps(first['config'], sort_keys=True)}, seed={first['seed']})\n")
    return 0


def _cmd_runs(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    store = Store(root)
    io.out.write(f"store: {root}\n")
    # ``no_outcome``, never ``errored``: the number says whether the executor stored an
    # outcome, not whether the run was healthy. A run whose every episode ended in the same
    # outcome label prints 0 here, correctly, and that is the right next question to ask.
    header = ("run_id", "status", "backend", "target_id", "t_unit", "rows", "no_outcome")
    lines = [header]
    for run_id in store.runs():
        m = store.manifest(run_id)
        rows = str(store.count(run_id))
        no_outcome = str(store.tally(run_id).no_outcome)
        lines.append((run_id, m.status, m.backend, m.target_id, m.t_unit, rows, no_outcome))
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    for line in lines:
        cells = (cell.ljust(w) for cell, w in zip(line, widths, strict=True))
        io.out.write("  ".join(cells).rstrip() + "\n")
    if len(lines) == 1:
        io.err.write(_no_runs_note(ns, root) + "\n")
    return 0


_VERBS: dict[str, Callable[[argparse.Namespace, _IO, Path, _State], int]] = {
    "sweep": _cmd_sweep,
    "diff": _cmd_diff,
    "report": _cmd_report,
    "check": _cmd_check,
    "serve": _cmd_serve,
    "inspect": _cmd_inspect,
    "runs": _cmd_runs,
    "paired": _cmd_paired,
}
