"""The command line.

Eight verbs over the built modules: ``sweep`` runs a plan on a backend after showing the plan
and asking; ``diff``, ``report``, ``check`` and ``serve`` operate on stored runs; ``inspect``
prints the ``(config, seed)`` pairs behind an event plus a reproduction snippet; ``runs``
lists the store; ``paired`` asserts that a declaration's arms were the same request replayed
and writes the paired-replay files, and ``report --paired`` folds the same sections into the
report. ``serve`` is the one verb that binds a socket: a loopback listener holding one page
built before the bind, which writes nothing and dies with the process.

This module computes nothing and decides nothing statistical: it parses arguments, calls the
library, and renders what comes back. Every number it prints is a field on a result object,
a manifest or a store frame, spelled the way every Poisson Labs tool spells it: the look.

**The look, in one paragraph.** The first line a verb prints is its verdict: a lowercase word,
two spaces, one sentence; detail follows as indented ``label  value`` lines or as a report
after one blank line. A problem is one ``error:`` line on stderr followed only by ``  next:``
lines naming the exact command to run; a warning Prove raises is one ``note:`` line. Exit codes
mean one thing each: 0 done, 1 refused with nothing spent or written, 2 a wrong command line,
3 stopped or failed after work started, 4 a check that did not pass, 130 interrupted. An
unexpected failure names a log instead of printing a traceback. ``--json`` makes stdout one
strict JSON document whose first keys are ``schema``, ``verdict`` and ``sentence``. The tool's
own options (``--store``, ``--plain``, ``--debug``) go before or after the verb, and an
abbreviated option is refused. Numbers follow rule 10 (``_look``).

``main`` owns the streams. Every write goes through the streams it was given (``sys.*`` by
default), which is what makes the whole command line testable in-process. Exceptions map to
exit codes in exactly one place, ``_dispatch``.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import shlex
import shutil
import sys
import tempfile
import tomllib
import traceback
import warnings
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TextIO, cast

if TYPE_CHECKING:
    import pandas as pd
    from _typeshed import SupportsWrite

    from poisson_prove.diff import Method

from poisson_prove import __version__, _look
from poisson_prove._compat import (
    retired_default_store,
    retired_default_store_refusal,
    retired_store_variable_note,
    version_as_recorded,
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
    UnderpoweredDesign,
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
    _check_cost,
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
_SWEEP_NEXT = "sweep SPEC.toml --target pkg.module:rollout"
#: The tool's own options, accepted before or after the verb.
_GLOBAL_OPTIONS = ("--store", "--plain", "--debug")
_VERB_NAMES = ("sweep", "diff", "check", "report", "paired", "serve", "inspect", "runs")
_SCHEMAS = {verb: f"{_COMMAND}.{verb}/1" for verb in _VERB_NAMES}
_ERRORS_LOG = "~/.cache/poisson-prove/errors.log"
_EXTRA_HINTS = {
    "modal": 'pip install "poisson-prove[modal]"',
    "burla": 'pip install "poisson-prove[burla]"',
}
_NEVER_INFERS = {
    "check": "a gate whose meaning changes when a new outcome appears is not a gate",
    "serve": (
        "a picture whose meaning changes when a new outcome appears is worse than a table "
        "with the same defect"
    ),
}


# ---------- streams, exits, parser ----------


@dataclass
class _IO:
    out: TextIO
    err: TextIO
    inp: TextIO
    #: True when stdout cannot carry the glyphs plain output uses: ASCII stands in.
    ascii: bool = False

    def write(self, text: str) -> None:
        self.out.write(_look.ascii_only(text) if self.ascii else text)

    def line(self, text: str = "") -> None:
        self.write(text + "\n")

    def err_write(self, text: str) -> None:
        """A write to stderr, after stdout is flushed: when the two streams share a pipe, what
        was printed first arrives first."""
        try:
            self.out.flush()
        except (OSError, ValueError):
            pass
        self.err.write(_look.ascii_only(text) if self.ascii else text)

    def err_line(self, text: str) -> None:
        self.err_write(text + "\n")

    def detail(self, label: str, value: str) -> None:
        self.line(f"  {label}  {value}")

    def next(self, command: str) -> None:
        self.line(f"  next: {command}")


@dataclass
class _State:
    """What the dispatcher needs to tell a refusal from a failure after work started, and to
    say what was kept when the work is interrupted."""

    run_id: str | None = None
    planned: int = 0
    json: bool = False
    verb: str = ""
    debug: bool = False
    argv: list[str] = field(default_factory=list)


class _Exit(Exception):
    """argparse wanted to exit after printing help or the version; carries the status."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class _Usage(Exception):
    """The command line is wrong. Exit 2: one ``error:`` line, then ``next:`` lines."""

    def __init__(self, message: str, nexts: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.nexts = list(nexts)


class _Refusal(Exception):
    """A verb refused before doing any work. Exit 1: one ``error:`` line, then ``next:`` lines."""

    def __init__(self, message: str, nexts: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.nexts = list(nexts)


class _Parser(argparse.ArgumentParser):
    """argparse that writes to the streams ``main`` was given, never calls ``sys.exit``, prints
    no usage line before an error, and shows the options a verb needs as required."""

    io: _IO | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        super().__init__(*args, **kwargs)

    def _print_message(self, message: str, file: SupportsWrite[str] | None = None) -> None:
        if not message or self.io is None:
            return
        if file is sys.stderr:
            self.io.err.write(message)
        else:
            self.io.write(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._print_message(message, sys.stderr)
        raise _Exit(status)

    def error(self, message: str) -> NoReturn:
        raise _Usage(_look.plain_words(message), [f"{self.prog} --help"])

    def _shown_required(self) -> list[argparse.Action]:
        return [a for a in self._actions if getattr(a, "shown_required", False)]

    def format_usage(self) -> str:
        shown = self._shown_required()
        for action in shown:
            action.required = True
        try:
            return super().format_usage()
        finally:
            for action in shown:
                action.required = False

    def format_help(self) -> str:
        shown = self._shown_required()
        for action in shown:
            action.required = True
        try:
            return super().format_help()
        finally:
            for action in shown:
                action.required = False


def _add_global_options(p: argparse.ArgumentParser, *, top: bool) -> None:
    """The tool's own options. On the top-level parser they carry their defaults; on a verb's
    parser they are set only when given, so a verb never overrides what came before it."""
    p.add_argument(
        "--store",
        metavar="PATH",
        default=None if top else argparse.SUPPRESS,
        help=f"the store folder (default: ${_ENV_STORE} when set, else {_DEFAULT_STORE})",
    )
    p.add_argument(
        "--plain",
        action="store_true",
        default=False if top else argparse.SUPPRESS,
        help="print plain text (the only rendering in this build)",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        default=False if top else argparse.SUPPRESS,
        help="also print the traceback of an unexpected failure",
    )


def _add_json_option(p: argparse.ArgumentParser, what: str) -> None:
    p.add_argument(
        "--json", action="store_true", help=f"print {what} as one JSON document instead of text"
    )


def _build_parser(io: _IO) -> _Parser:
    parser = _Parser(
        prog=_COMMAND,
        description=(
            "A statistical instrument for finding where autonomous and agentic systems break.\n"
            "Run a sweep of your agent over its conditions, store every episode, and compare\n"
            "two runs condition by condition with stated confidence."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} sweep prove.toml --target my_agent:rollout\n"
            f"  {_COMMAND} diff latest previous\n"
            f"  {_COMMAND} runs"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{_COMMAND} {__version__} (Python {sys.version_info.major}."
        f"{sys.version_info.minor}.{sys.version_info.micro})",
        help="print the version and exit",
    )
    _add_global_options(parser, top=True)
    sub = parser.add_subparsers(
        dest="verb", title="verbs", metavar="VERB", help="what to do; each verb has its own --help"
    )

    sweep = sub.add_parser(
        "sweep",
        help="run a sweep spec on a backend after showing the plan",
        description=(
            "Run every condition of a sweep spec, N replicates each, on the local machine or a\n"
            "remote backend. The plan is printed first, with its cost estimate, and the sweep\n"
            "starts only after a yes."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} sweep prove.toml --target my_agent:rollout\n"
            f"  {_COMMAND} sweep prove.toml --target my_agent:rollout --pair-with latest --yes"
        ),
    )
    sweep.add_argument(
        "spec", metavar="SPEC.toml", help="the sweep spec: the target, the axes, the replicates"
    )
    sweep.add_argument(
        "--target",
        required=True,
        metavar="pkg.module:rollout",
        help="import path of the rollout function (no default)",
    )
    sweep.add_argument(
        "--backend",
        choices=("local", "modal", "burla"),
        default="local",
        help="where the rollouts run: local, modal or burla (default: local)",
    )
    identity = sweep.add_mutually_exclusive_group()
    identity.add_argument(
        "--salt", metavar="HEX", help="the run salt seeds are derived from (default: a fresh one)"
    )
    identity.add_argument(
        "--pair-with",
        metavar="RUN",
        help="inherit that run's salt, so the two runs share their seeds (default: none)",
    )
    identity.add_argument(
        "--resume", metavar="RUN", help="continue that partial run where it stopped (default: none)"
    )
    sweep.add_argument(
        "--episode-timeout",
        type=float,
        metavar="S",
        help="seconds an episode may take before it is recorded as timed out (default: no limit)",
    )
    sweep.add_argument(
        "--max-rollouts",
        type=int,
        metavar="N",
        help="stop after N rollouts and leave the run partial (default: run them all)",
    )
    sweep.add_argument(
        "--batch-size",
        type=int,
        metavar="N",
        help=f"rows written to the store at a time (default: {_DEFAULT_BATCH_SIZE})",
    )
    sweep.add_argument(
        "--max-mde",
        type=float,
        metavar="FRACTION",
        help="the largest minimum detectable effect you accept for this design (default: 0.200)",
    )
    sweep.add_argument(
        "--dry-run", action="store_true", help="print the plan and stop; nothing is run or written"
    )
    sweep.add_argument("--yes", action="store_true", help="skip the question after the plan")
    _add_json_option(sweep, "the plan and the result")
    remote = sweep.add_argument_group(
        "remote backends (override the [modal] table; --infra-retries, --max-cost and "
        "--est-seconds also override [burla])"
    )
    remote.add_argument(
        "--concurrency", type=int, metavar="N", help="containers at once (default: the table's)"
    )
    remote.add_argument(
        "--infra-retries", type=int, metavar="N", help="retries per batch (default: the table's)"
    )
    remote.add_argument(
        "--max-cost",
        type=float,
        metavar="USD",
        help="refuse before anything starts when the estimate is above this (default: no cap)",
    )
    remote.add_argument(
        "--est-seconds",
        type=float,
        metavar="S",
        help="seconds per episode, for the estimate (default: the table's)",
    )
    remote.add_argument(
        "--app-name", metavar="NAME", help="the Modal app name (default: the table's)"
    )
    remote.add_argument(
        "--image",
        default="image",
        metavar="SECTION",
        help="the [modal.SECTION] image table to build from (default: image)",
    )
    _add_global_options(sweep, top=False)

    diff_p = sub.add_parser(
        "diff",
        help="compare two stored runs condition by condition, per event",
        description=(
            "Compare two stored runs condition by condition: which conditions got worse, which\n"
            "got safer, and what the comparison could not have seen."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} diff latest previous\n"
            f"  {_COMMAND} diff latest previous --event violated --json"
        ),
    )
    diff_p.add_argument("a", metavar="A", help="the baseline run")
    diff_p.add_argument("b", metavar="B", help="the candidate run")
    _add_event_argument(diff_p, "default: inferred from the outcomes present")
    _add_method_arguments(diff_p, defaults=True)
    diff_p.add_argument(
        "--methods",
        choices=("all",),
        help="also run the other two methods and print them side by side (default: one method)",
    )
    _add_json_option(diff_p, "the comparison")
    _add_tree_arguments(diff_p, defaults=True)
    _add_global_options(diff_p, top=False)

    report_p = sub.add_parser(
        "report",
        help="write report.md, heatmap.svg and receipt.html for two runs, or one",
        description=(
            "Write a report folder: two runs give the comparison with its heatmap, one run gives\n"
            "its survival report. The folder holds report.md, heatmap.svg and receipt.html."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} report latest previous --x tool_fail_rate --y task_id\n"
            f"  {_COMMAND} report latest --x tool_fail_rate --event violated"
        ),
    )
    report_p.add_argument(
        "runs", nargs="+", metavar="RUN", help="A B for a comparison, one RUN for a survival report"
    )
    _add_event_argument(report_p, "default: inferred from the outcomes present")
    _add_method_arguments(report_p, defaults=False)
    report_p.add_argument(
        "--methods",
        choices=("all",),
        help="add the method comparison table (default: one method; two runs only)",
    )
    _add_tree_arguments(report_p, defaults=False)
    x = report_p.add_argument(
        "--x",
        metavar="AXIS",
        help="required: the config key on the x axis (omitted: lists the axes and events the "
        "runs carry; no default)",
    )
    x.shown_required = True  # type: ignore[attr-defined]
    report_p.add_argument(
        "--y", metavar="AXIS", help="the config key on the y axis (default: none)"
    )
    report_p.add_argument(
        "--fix",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="pin a config key to one value; repeatable (default: nothing pinned)",
    )
    report_p.add_argument(
        "--horizon",
        type=float,
        metavar="T",
        help="truncate a survival report at this time (default: the run's own horizon)",
    )
    report_p.add_argument(
        "--theme",
        choices=("dark", "light"),
        default="dark",
        help="the report's colours (default: dark)",
    )
    report_p.add_argument(
        "--top-n", type=int, default=10, metavar="N", help="worst conditions listed (default: 10)"
    )
    report_p.add_argument(
        "--forest",
        choices=("auto", "always", "never"),
        default="auto",
        help="single-axis panels as a forest plot: auto, always or never (default: auto)",
    )
    report_p.add_argument(
        "--out",
        metavar="DIR",
        help="the folder to write (default: ./prove-report-A-vs-B, or ./prove-report-RUN)",
    )
    report_p.add_argument(
        "--title", metavar="TEXT", help="the report's title (default: the runs and the events)"
    )
    report_p.add_argument(
        "--force", action="store_true", help="write into a folder that is not empty"
    )
    report_p.add_argument(
        "--paired",
        metavar="DECL",
        help="a paired-replay declaration whose sweep (A, B) is; folds its sections into the "
        "report and writes its files beside it (default: none; two runs only)",
    )
    _add_json_option(report_p, "the comparison and the files written")
    _add_global_options(report_p, top=False)

    paired_p = sub.add_parser(
        "paired",
        help="assert that a declaration's arms replayed the same requests, then write its files",
        description=(
            "Assert that a declaration's arms were the same request replayed, then write the\n"
            "paired-replay files: the assertion, the contingency and interval tables, the\n"
            "windows, the cost and, at three arms or more, the replicates."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} paired --declaration paired.toml\n"
            f"  {_COMMAND} paired --declaration paired.toml --cap-check"
        ),
    )
    paired_p.add_argument(
        "--declaration",
        required=True,
        metavar="DECL",
        help="the paired-replay declaration, a TOML file (no default)",
    )
    paired_p.add_argument(
        "--out",
        metavar="DIR",
        help="the folder to write (default: ./prove-paired-<the declaration's digest>)",
    )
    paired_p.add_argument(
        "--cap-check",
        action="store_true",
        help="say whether the recorded input tokens are under the declared cap, write nothing, "
        "and exit 4 at or above it",
    )
    paired_p.add_argument(
        "--force", action="store_true", help="write into a folder that is not empty"
    )
    _add_json_option(paired_p, "the files' contents, writing nothing")
    _add_global_options(paired_p, top=False)

    check_p = sub.add_parser(
        "check",
        help="gate on a comparison: passed exits 0, failed exits 4",
        description=(
            "Gate on a comparison of two runs over the events you name: passed exits 0 and\n"
            "failed exits 4, so a pipeline can stop on a change for the worse."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} check latest previous --event violated\n"
            f"  {_COMMAND} check latest previous --event violated --fail-on any"
        ),
    )
    check_p.add_argument("a", metavar="A", help="the baseline run")
    check_p.add_argument("b", metavar="B", help="the candidate run")
    _add_event_argument(
        check_p,
        "required: a gate never infers its events; omitted: lists the events the runs carry; "
        "no default",
        shown=True,
    )
    _add_method_arguments(check_p, defaults=True)
    check_p.add_argument(
        "--fail-on",
        choices=("worse", "any"),
        default="worse",
        help="fail on a condition significantly worse, or on any significant change "
        "(default: worse)",
    )
    _add_json_option(check_p, "the verdict and the comparison")
    _add_global_options(check_p, top=False)

    serve_p = sub.add_parser(
        "serve",
        help="serve a read-only page comparing two runs on a loopback port",
        description=(
            "Serve a read-only page for one pair of runs on an ephemeral loopback port, built\n"
            "before the bind; Ctrl-C stops it and nothing is written."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} serve latest previous --x tool_fail_rate --event violated\n"
            f"  {_COMMAND} serve latest previous --x tool_fail_rate --event violated --json"
        ),
    )
    serve_p.add_argument(
        "runs", nargs="+", metavar="RUN", help="the baseline and the candidate, in that order"
    )
    _add_event_argument(
        serve_p,
        "required: a picture never infers its event; omitted: lists the axes and events the "
        "runs carry; no default",
        shown=True,
    )
    _add_method_arguments(serve_p, defaults=True)
    # ``serve`` takes the five tree flags through the helper ``report`` already uses, with
    # ``defaults=True``: like ``diff`` and unlike ``report``, it takes two runs, has no
    # single-run form to refuse, and so needs no ``None`` to tell an unset flag from M14's own
    # value.
    _add_tree_arguments(serve_p, defaults=True)
    sx = serve_p.add_argument(
        "--x",
        metavar="AXIS",
        help="required: the config key on the x axis (omitted: lists the axes and events the "
        "runs carry; no default)",
    )
    sx.shown_required = True  # type: ignore[attr-defined]
    serve_p.add_argument(
        "--y", metavar="AXIS", help="the config key on the y axis (default: none)"
    )
    serve_p.add_argument(
        "--fix",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="pin a config key to one value; repeatable (default: nothing pinned)",
    )
    serve_p.add_argument(
        "--theme",
        choices=("dark", "light"),
        default="dark",
        help="the page's colours (default: dark)",
    )
    serve_p.add_argument(
        "--top-n", type=int, default=10, metavar="N", help="worst conditions listed (default: 10)"
    )
    serve_p.add_argument(
        "--forest",
        choices=("auto", "always", "never"),
        default="auto",
        help="single-axis panels as a forest plot: auto, always or never (default: auto)",
    )
    serve_p.add_argument(
        "--title", metavar="TEXT", help="the page's title (default: the runs and the events)"
    )
    serve_p.add_argument(
        "--json",
        action="store_true",
        help="print the page's structure as one JSON document and exit; bind nothing",
    )
    _add_global_options(serve_p, top=False)

    inspect_p = sub.add_parser(
        "inspect",
        help="print the episodes behind an event, with a snippet to reproduce one",
        description=(
            "Print the episodes of a run that ended in an event, or in an error of a kind,\n"
            "each with its config and seed, then a snippet that reproduces one of them."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} inspect latest --event violated\n"
            f"  {_COMMAND} inspect latest --event timeout --limit 5"
        ),
    )
    inspect_p.add_argument("run", metavar="RUN", help="the run to inspect")
    ev = inspect_p.add_argument(
        "--event",
        metavar="NAME",
        help="required: the outcome, or the error kind, to show (omitted: lists the events the "
        "run carries; no default)",
    )
    ev.shown_required = True  # type: ignore[attr-defined]
    inspect_p.add_argument(
        "--where",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="keep only episodes whose config has this value; repeatable (default: all)",
    )
    inspect_p.add_argument(
        "--limit", type=int, metavar="N", help="show at most N episodes (default: all)"
    )
    _add_json_option(inspect_p, "the episodes")
    _add_global_options(inspect_p, top=False)

    runs_p = sub.add_parser(
        "runs",
        help="list the runs in the store",
        description=(
            "List every run in the store with its status, backend, target and row counts,\n"
            "so the next command can name one."
        ),
        epilog=f"examples:\n  {_COMMAND} runs\n  {_COMMAND} runs --json",
    )
    _add_json_option(runs_p, "the list")
    _add_global_options(runs_p, top=False)

    for p in (parser, *sub.choices.values()):
        if isinstance(p, _Parser):
            p.io = io
    return parser


def _add_event_argument(p: argparse.ArgumentParser, note: str, *, shown: bool = False) -> None:
    action = p.add_argument(
        "--event",
        action="append",
        metavar="NAME",
        help=f"an outcome that counts as the event; repeatable ({note})",
    )
    if shown:
        action.shown_required = True  # type: ignore[attr-defined]


def _add_method_arguments(p: argparse.ArgumentParser, *, defaults: bool) -> None:
    """``--method`` and ``--q``. Without defaults the namespace keeps ``None`` for a flag the
    user did not pass, so the single-run report can name the diff-only flags it was given."""
    p.add_argument(
        "--method",
        choices=_METHODS,
        default=_DEFAULT_METHOD if defaults else None,
        help="the per-condition test: fisher_bh treats the two runs as separate samples, "
        "mcnemar_bh pairs them on their shared seeds, logrank_bh is time to the event "
        f"(default: {_DEFAULT_METHOD})",
    )
    p.add_argument(
        "--q",
        type=float,
        default=_DEFAULT_Q if defaults else None,
        metavar="Q",
        help=f"the false discovery rate the verdicts are held to (default: {_DEFAULT_Q})",
    )


def _add_tree_arguments(p: argparse.ArgumentParser, *, defaults: bool) -> None:
    """The five flags that move the tree, in the two groups ``diff`` has always printed, with one
    help text for every verb that takes them. Without defaults the namespace keeps ``None`` for a
    flag the user did not pass, so the single-run report can name the diff-only flags it was
    given and a pair can put the constants in by name."""
    omnibus_group = p.add_argument_group("the omnibus over the whole family")
    omnibus_group.add_argument(
        "--permutations",
        type=int,
        default=DEFAULT_PERMUTATIONS if defaults else None,
        metavar="N",
        help=f"within-cell permutations behind the omnibus (default: {DEFAULT_PERMUTATIONS})",
    )
    omnibus_group.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED if defaults else None,
        metavar="N",
        help=f"the permutation seed (default: {DEFAULT_SEED})",
    )
    fault_group = p.add_argument_group("the fault lines under the omnibus")
    fault_group.add_argument(
        "--by",
        metavar="KEY",
        help="the grouping for the fault lines: an axis both runs declare, "
        f"{'/'.join(TASK_FAMILY_KEYS)}, {' or '.join(TRACE_GROUPINGS)}, or {WHOLE_GRID} "
        "(default: resolved in a stated order and named either way)",
    )
    fault_group.add_argument(
        "--max-group-mde",
        type=float,
        metavar="FRACTION",
        help="the largest group-level minimum detectable effect you accept "
        f"(default: {DEFAULT_MAX_GROUP_MDE:.3f}, the constant sweep's --max-mde uses)",
    )
    fault_group.add_argument(
        "--depth",
        type=int,
        choices=DEPTHS,
        default=DEFAULT_DEPTH if defaults else None,
        metavar="N",
        help="levels the procedure tests: 2 stops at the fault lines, 3 adds the cells under "
        f"each rejecting group (default: {DEFAULT_DEPTH}); the bound is computed from this and "
        "the grouping's shape, never from what rejected",
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
    io.ascii = not _look.can_encode(getattr(io.out, "encoding", None))
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        code = _run(args, io)
        io.out.flush()
        io.err.flush()
        return code
    except BrokenPipeError:
        # The reader went away: nothing more to say, and nothing to say about it.
        _quiet_closed_pipe(io)
        return 0


def _quiet_closed_pipe(io: _IO) -> None:
    for stream in (io.out, io.err):
        try:
            fd = stream.fileno()
        except (OSError, ValueError, AttributeError):
            continue
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, fd)
            os.close(devnull)
        except OSError:
            pass


def _scan_globals(args: list[str]) -> None:
    """The tokens before the verb: only the tool's own options may stand there, spelled out in
    full. An abbreviation or an unknown option is a wrong command line, named."""
    known = {*_GLOBAL_OPTIONS, "--version", "--help", "-h"}
    skip = False
    for token in args:
        if skip:
            skip = False
            continue
        if token == "--":
            return
        if not token.startswith("-"):
            return
        name = token.split("=", 1)[0]
        if name not in known:
            raise _Usage(f"unknown option {name}", [f"{_COMMAND} --help"])
        if name == "--store" and "=" not in token:
            skip = True


def _run(args: list[str], io: _IO) -> int:
    parser = _build_parser(io)
    try:
        _scan_globals(args)
        ns = parser.parse_args(args)
    except _Exit as exc:
        return exc.code
    except _Usage as exc:
        _write_error(io, str(exc), exc.nexts)
        return 2
    if ns.verb is None:
        _write_error(io, "no verb given", [f"{_COMMAND} --help"])
        return 2
    return _dispatch(ns, io, args)


def _write_error(io: _IO, message: str, nexts: Sequence[str] = ()) -> None:
    io.err_line(f"error: {_look.reprint(_look.one_line(_look.plain_words(message)))}")
    for command in nexts:
        io.err_line(f"  next: {command}")


@contextmanager
def _notes(io: _IO) -> Iterator[None]:
    """Every warning Prove raises reaches the user as one ``note:`` line; a library's warning
    is not shown."""

    package = os.path.dirname(os.path.abspath(__file__))

    def show(
        message: Any, category: Any, filename: str, lineno: int, file: Any = None, line: Any = None
    ) -> None:
        module = getattr(category, "__module__", "") or ""
        raised_here = os.path.abspath(filename).startswith(package) if filename else False
        if not module.startswith("poisson_prove") and not raised_here:
            return
        text = _look.one_line(_look.plain_words(str(message)))
        io.err_line(f"note: {_look.reprint(text)}")

    with warnings.catch_warnings():
        warnings.simplefilter("always")
        warnings.showwarning = show
        yield


def _dispatch(ns: argparse.Namespace, io: _IO, argv: list[str]) -> int:
    """The single exception-to-exit-code map."""
    root = _store_root(ns)
    state = _State(
        json=bool(getattr(ns, "json", False)),
        verb=ns.verb,
        debug=bool(getattr(ns, "debug", False)),
        argv=list(argv),
    )
    try:
        with _notes(io):
            note = retired_store_variable_note(os.environ, _ENV_STORE)
            if note is not None:
                io.err_line(f"note: {note}")
            _check_retired_default_store(ns, root)
            _check_store(ns, root)
            return _VERBS[ns.verb](ns, io, root, state)
    except _Usage as exc:
        _write_error(io, str(exc), exc.nexts)
        return 2
    except _Refusal as exc:
        _write_error(io, str(exc), exc.nexts)
        return 1
    except KeyboardInterrupt:
        return _interrupted(io, root, state)
    except _REFUSABLE as exc:
        if _work_started(root, state):
            sentence, nexts = _kept(root, state)
            if not state.json:
                io.line(f"stopped  {sentence}")
                for command in nexts:
                    io.next(command)
            _write_error(io, f'{exc} (run "{state.run_id}")')
            return 3
        _write_error(io, str(exc), getattr(exc, "nexts", ()))
        return 1
    except BrokenPipeError:
        raise
    except Exception as exc:
        return _unexpected(io, state, exc)


def _kept(root: Path, state: _State) -> tuple[str, list[str]]:
    """What a sweep that stopped after work started kept, and how to go on."""
    try:
        kept = Store(root).count(state.run_id or "")
    except Exception:  # noqa: BLE001 - the store may be the thing that failed
        kept = 0
    sentence = (
        f"{_look.fmt_count(kept)} of {_look.fmt_count(state.planned)} rollouts "
        f'kept in run "{state.run_id}" (partial)'
    )
    return sentence, [f"{_COMMAND} sweep --resume"]


def _interrupted(io: _IO, root: Path, state: _State) -> int:
    """Ctrl-C: what was kept, and how to go on. Exit 130."""
    if state.verb == "sweep" and state.run_id is not None and _work_started(root, state):
        kept, nexts = _kept(root, state)
        sentence = f"interrupted: {kept}"
    else:
        sentence = "interrupted; nothing was written"
        nexts = []
    if state.json:
        _write_json(io, state.verb, "stopped", sentence, {}, nexts)
    else:
        io.line(f"stopped  {sentence}")
        for command in nexts:
            io.next(command)
    return 130


def _unexpected(io: _IO, state: _State, exc: BaseException) -> int:
    """An unexpected failure: the log gets the command and the traceback, the user gets one
    line naming the log. Exit 3."""
    where = _ERRORS_LOG
    try:
        home = Path.home()
        path = home / ".cache" / "poisson-prove" / "errors.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(f"{stamp}  {shlex.join([_COMMAND, *state.argv])}\n")
            fh.write("".join(traceback.format_exception(exc)))
            fh.write("\n")
        if not path.is_relative_to(home):
            where = str(path)
    except Exception:  # noqa: BLE001 - the log is best effort; the line below is not
        pass
    if state.debug:
        io.err_write("".join(traceback.format_exception(exc)))
    io.err_line(
        f"error: an unexpected failure inside {_COMMAND} ({type(exc).__name__}); the details "
        f"are in {where}"
    )
    return 3


def _store_root(ns: argparse.Namespace) -> Path:
    if getattr(ns, "store", None):
        return Path(ns.store)
    env = os.environ.get(_ENV_STORE)
    if env:
        return Path(env)
    return Path(_DEFAULT_STORE)


def _check_retired_default_store(ns: argparse.Namespace, root: Path) -> None:
    """With the default store in use, a folder an earlier version of Prove wrote to beside a
    missing ``./prove-runs`` is a refusal on every verb, ``sweep`` included: reading past it
    would answer from nothing, and writing would split the store in two. Creates nothing."""
    if getattr(ns, "store", None) or os.environ.get(_ENV_STORE):
        return
    old = retired_default_store(root)
    if old is None:
        return
    error, nexts = retired_default_store_refusal(root, old, _COMMAND, ns.verb)
    raise _Refusal(error, nexts)


def _slug(name: str) -> str:
    """A run's name as a folder name: lower case, spaces and slashes as dashes."""
    return name.lower().replace(" ", "-").replace("/", "-")


def _store_source(ns: argparse.Namespace) -> str:
    """Which of the three places named the store root, in the order ``_store_root`` reads them.

    An empty ``$POISSON_PROVE_STORE`` is not a source: ``_store_root`` falls through it to the
    default, and the clause has to name the resolution that actually happened.
    """
    if getattr(ns, "store", None):
        return "it came from --store"
    if os.environ.get(_ENV_STORE):
        return f"it came from ${_ENV_STORE}"
    return f"it is the default, since neither --store nor ${_ENV_STORE} is set"


def _first_sweep(root: Path) -> str:
    return f"{_COMMAND} --store {shlex.quote(str(root))} {_SWEEP_NEXT}"


def _check_store(ns: argparse.Namespace, root: Path) -> None:
    """A missing store refuses on every verb that reads it, an empty one on every such verb
    but ``runs``. ``sweep`` is the verb that creates the store, so it is never gated.

    A path with no directory at it is certainly wrong, because nothing was ever stored there;
    a directory with no ``manifest.json`` under it can be a fresh project. This reads the
    store and creates nothing.
    """
    if ns.verb == "sweep":
        return
    elsewhere = f"{_COMMAND} --store PATH {ns.verb}"
    if not root.is_dir():
        raise _Refusal(
            f"no store at {root}. No directory exists at that path; {_store_source(ns)}.",
            [_first_sweep(root), elsewhere],
        )
    if ns.verb != "runs" and not Store(root).runs():
        raise _Refusal(
            f"no runs in {root}. No directory under it holds a manifest.json; "
            f"{_store_source(ns)}.",
            [_first_sweep(root), elsewhere],
        )


def _work_started(root: Path, state: _State) -> bool:
    if state.run_id is None:
        return False
    try:
        return state.run_id in Store(root).runs()
    except Exception:  # noqa: BLE001 - a store that cannot be read kept nothing we can name
        return False


def _write_json(
    io: _IO,
    verb: str,
    verdict: str,
    sentence: str,
    payload: Mapping[str, Any],
    nexts: Sequence[str] | None,
) -> None:
    """One strict JSON document: ``schema``, ``verdict`` and ``sentence`` first, the verb's own
    keys, and ``next`` last (``serve`` has none)."""
    schema = "poisson-prove.viewpair/7" if verb == "serve" else _SCHEMAS[verb]
    document: dict[str, Any] = {"schema": schema, "verdict": verdict, "sentence": sentence}
    for key, value in payload.items():
        if key != "schema":
            document[key] = value
    if nexts is not None:
        document["next"] = list(nexts)
    text = json.dumps(
        _look.strict(document), indent=2, allow_nan=False, ensure_ascii=io.ascii
    )
    io.out.write(text + "\n")


# ---------- shared helpers ----------


def _parse_pairs(items: Sequence[str], flag: str) -> dict[str, Any]:
    """``KEY=VALUE`` items with TOML scalar values: ``push=100`` -> int, ``task="x"`` -> str."""
    out: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise _Refusal(f'{flag} expects KEY=VALUE, got "{item}"')
        try:
            out[key] = tomllib.loads(f"v = {value.strip()}")["v"]
        except tomllib.TOMLDecodeError as exc:
            raise _Refusal(
                f'{flag} "{item}": the value must be a TOML scalar (100, 0.5, "text", true): '
                f"{exc}"
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
    return ", ".join(f"{name}={_look.fmt_count(count)}" for name, count in ordered)


def _multi(
    fa: Any,
    fb: Any,
    ma: RunManifest,
    mb: RunManifest,
    *,
    events: Sequence[str] | None,
    method: str,
    q: float,
    verb: str = "diff",
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
            f"cannot infer the event set: {exc}; outcome counts: {_outcome_counts(fa, fb)}",
            [f"{_COMMAND} {verb} A B --event NAME"],
        ) from exc


def _require_known_events(
    verb: str, events: Sequence[str] | None, *frames: pd.DataFrame
) -> None:
    """Refuse an ``--event`` name absent from every frame the verb loaded, before any work.

    Compared against the outcomes actually present, never against an inferred set: a typo
    should never produce a plausible-looking empty result, and the command line is where every
    typo originates. The library underneath stays permissive.
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


def _missing_flags_refusal(
    store: Store,
    verb: str,
    runs: Sequence[str],
    argv: Sequence[str],
    *,
    x_missing: bool,
    event_missing: bool,
) -> _Refusal:
    """What the named runs carry, in place of argparse's bare "arguments are required".

    The two verbs that refuse to infer keep their own clause: a gate whose meaning moves when a
    new outcome appears is not a gate, and a picture of the same defect is worse. The listing
    replaces the suggestion they used to end on, because a verb that refuses to infer should not
    offer an inference as its advice. The ``next:`` line is the command as typed with the first
    listed value filled in.

    Fires after the store state, the arity and the unknown-run refusal, and before any work: it
    reads the frames of the named runs and calls nothing else.
    """
    for run in runs:
        store.manifest(run)
    frames = [store.read(run, meta=False) for run in runs]
    axes = sorted({str(key) for frame in frames for config in frame["config"] for key in config})
    events = list(competing_set(*frames))
    if verb == "inspect" and "timeout" not in events and store.tally(runs[0]).timed_out:
        # ``inspect --event`` matches the error column too, and "timeout" is the one error text
        # a person can type: ``RunTally.timed_out`` counts exactly ``error == "timeout"``.
        events = sorted({*events, "timeout"})
    flags = " and ".join(
        flag
        for flag, missing in (("--x AXIS", x_missing), ("--event NAME", event_missing))
        if missing
    )
    given = "and neither was given" if x_missing and event_missing else "which was not given"
    reason = f"; {_NEVER_INFERS[verb]}" if event_missing and verb in _NEVER_INFERS else ""
    who = f"{runs[0]} and {runs[1]} carry" if len(runs) == 2 else f"{runs[0]} carries"
    carried = []
    if verb in ("report", "serve"):
        carried.append(f"axes: {', '.join(axes) or 'none stored'}")
    carried.append(f"events: {', '.join(events) or 'none stored'}")
    message = f"{verb} requires {flags}, {given}{reason}. {who} {'; '.join(carried)}."
    filled = [_COMMAND, *argv]
    if x_missing and axes:
        filled.extend(["--x", axes[0]])
    if event_missing and events:
        filled.extend(["--event", events[0]])
    fillable = (not x_missing or axes) and (not event_missing or events)
    return _Refusal(message, [shlex.join(filled)] if fillable else [])


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

    The raw frames come back beside the result because the tree consumes both: it rebuilds
    the cell view from the frames and checks it against the diff, and reading the pair a second
    time here would be a second read free to disagree with the first.
    """
    fa, fb, ma, mb = _load_pair(store, a, b)
    _require_known_events(verb, events, fa, fb)
    primary = _multi(fa, fb, ma, mb, events=events, method=method, q=q, verb=verb)
    others: dict[str, Any] = {}
    if all_methods:
        for other in _METHODS:
            if other != method:
                others[other] = _multi(
                    fa, fb, ma, mb, events=primary.events, method=other, q=q, verb=verb
                )
    return primary, others, (ma, mb), (fa, fb)


def _method_table(results: Sequence[MultiDiffResult]) -> str:
    header = ("method", "event", "pairing", "safer", "worse", "unchanged", "max_mde")
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for m in results:
        # The column states the requested method's pairing, the same fact the headline states,
        # and never the runs' seed identity, which is its own field on the result.
        pairing = "paired" if m.method in _PAIRED_METHODS else "unpaired"
        for e in m.events:
            ev = m.by_event[e]
            lines.append(
                f"| {m.method} | {e} | {pairing} | {_look.fmt_count(ev.n_safer)} | "
                f"{_look.fmt_count(ev.n_worse)} | {_look.fmt_count(ev.n_unchanged)} | "
                f"{_look.fmt_rate(ev.max_mde)} |"
            )
    return "\n".join(lines) + "\n"


def _coverage_block(multi: MultiDiffResult) -> str:
    """The coverage facts ``diff``'s text output appends, after the markdown and after the
    ``--methods all`` table, exactly as ``_method_table`` already is.

    Not part of ``to_markdown()``: a diff whose rows errored must render identically to one
    whose rows did not, so ``to_markdown()`` keeps meaning "the statistical result" and the
    coverage facts reach the reader of ``diff`` here instead. The ``_md_cell`` style and the
    column order are the diff module's, imported rather than restated.
    """
    frame = multi.coverage
    if frame is None:  # never from ``multi_diff``; a hand-built result says nothing.
        return ""
    holes = frame[~frame["comparable"]]
    counts = {cause: int((holes["cause"] == cause).sum()) for cause in _CAUSES}
    cols = list(COVERAGE_COLUMNS)
    n = _look.fmt_count
    lines = [
        f"coverage: holes={n(len(holes))} (only_a={n(counts['only_a'])}, "
        f"only_b={n(counts['only_b'])}, no_outcome_a={n(counts['no_outcome_a'])}, "
        f"no_outcome_b={n(counts['no_outcome_b'])}, "
        f"no_outcome_both={n(counts['no_outcome_both'])}), "
        f"no_outcome a={n(int(frame['no_outcome_a'].sum()))} "
        f"b={n(int(frame['no_outcome_b'].sum()))}",
        "",
        "## coverage",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "|".join("---" for _ in cols) + "|",
    ]
    for record in frame.to_dict(orient="records"):
        lines.append("| " + " | ".join(_md_cell(record[col], col) for col in cols) + " |")
    return "\n".join(lines) + "\n"


def _interval_block(multi: MultiDiffResult) -> str:
    """The interval facts ``diff``'s text output appends after the coverage block, from the one
    formatter every surface shares; what is left here is layout: the second and third lines
    are indented two spaces."""
    lines = _interval_lines(multi)
    return "\n".join([lines[0], *(f"  {line}" for line in lines[1:])]) + "\n"


def _omnibus_block(dual_root: RootResult) -> str:
    """The tree's root, the block ``diff``'s text output appends after the interval block.

    **The family is named and the null is quoted.** The root tests the sharp "no cell changed"
    over the same cells x events family the flat analysis runs.

    **Every number is a field and none of them is computed here.** That includes the last
    line's complement: ``n_cells - n_informative_cells`` is exactly the arithmetic this module
    must not do, so ``RootResult`` carries ``n_uninformative_cells`` and this reads it.
    """
    n, p_ = _look.fmt_count, _look.fmt_p
    verdict = "rejected" if dual_root.rejects else "not rejected"
    sign = "<" if dual_root.rejects else ">="
    events = "event" if len(dual_root.events) == 1 else "events"
    lines = [
        f'omnibus: "no cell changed" is {verdict} (p = {p_(dual_root.p_omnibus)} {sign} q '
        f"{p_(dual_root.q)}) over {n(dual_root.n_cells)} cells x {n(len(dual_root.events))} "
        f"{events}",
        f"  min-p of location and dispersion; {n(dual_root.n_permutations)} within-cell "
        f"permutations, {dual_root.scheme}, seed {dual_root.seed}",
        # Every permutation p below is ``(1 + count) / (B + 1)`` over the same B, so one field
        # bounds all of them; the floor prints under the same rule as the p beside it.
        f"  p floor {p_(dual_root.p_floor)}: the smallest p {n(dual_root.n_permutations)} "
        f"permutations can express; a p at the floor is a bound, not a measurement",
    ]
    for event in dual_root.events:
        lines.append(
            f"  location    {event}: mean delta {_look.fmt_rate(dual_root.location[event])}, "
            f"p = {p_(dual_root.p_location[event])}"
        )
    for event in dual_root.events:
        lines.append(
            f"  dispersion  {event}: rms delta {_look.fmt_rate(dual_root.dispersion[event])}, "
            f"p = {p_(dual_root.p_dispersion[event])}"
        )
    lines.append(
        f"  informative cells: {n(dual_root.n_informative_cells)} of {n(dual_root.n_cells)}; "
        f"{n(dual_root.n_uninformative_cells)} unchanged by every exchange"
    )
    return "\n".join(lines) + "\n"


def _fault_lines_head(cut: Grouping, fault: FaultLines) -> str:
    """The grouping, the rung that resolved it, and the shape it was admitted on. Every number
    is a field and none of them is computed here."""
    n = _look.fmt_count
    return (
        f"fault lines: grouping {cut.key} ({cut.resolved_by}), {n(cut.n_groups)} groups; "
        f"cells per group min {n(cut.size_min)} / median {_look.fmt_num(cut.size_median)} / "
        f"max {n(cut.size_max)}; {n(fault.n_degenerate_groups)} degenerate; "
        f"{n(cut.n_resolvable_groups)} of {n(cut.n_groups)} groups resolve "
        f"{_look.fmt_rate(cut.max_group_mde)} at alpha {_look.fmt_p(cut.alpha_floor)}"
    )


def _fault_lines_null(fault: FaultLines) -> str:
    """The null in quotes, and either what tested it or why nothing did. A level that was not
    tested is stated, not omitted, and stated without a conditional."""
    if fault.tested:
        return (
            f'  "{fault.null}" tested by BH across {_look.fmt_count(fault.n_groups)} groups at '
            f"q {_look.fmt_p(fault.q)}: {_look.fmt_count(fault.n_rejected_groups)} rejected"
        )
    if fault.reason == "one_group":
        return f'  "{fault.null}" not tested: one group is the whole family restated'
    return f'  "{fault.null}" not tested: the root did not reject'


def _fault_lines_group(key: str, group: GroupResult) -> str:
    """One group: what it holds, what could move in it, and, when tested, its verdict. The
    p-values print only when they exist."""
    n = _look.fmt_count
    line = (
        f"  {key}={group.label}  {n(group.n_cells)} cells, "
        f"{n(group.n_informative_cells)} informative, "
        f"{n(group.n_uninformative_cells)} unchanged by every exchange; "
        f"{n(group.n_a)} units in a, {n(group.n_b)} in b; group MDE {_look.fmt_rate(group.mde)}"
    )
    if group.n_discordant is not None:
        line = f"{line}; {n(group.n_discordant)} discordant pairs"
    if group.p_group is None or group.q_group is None:
        return line
    verdict = "rejected" if group.rejects else "not rejected"
    return f"{line}; p {_look.fmt_p(group.p_group)}, q {_look.fmt_p(group.q_group)}: {verdict}"


def _fault_lines_block(nested: TreeResult) -> str:
    """Level 2, the block ``diff``'s text output appends after the omnibus block: its first
    line, then every following line indented two spaces, the chain first and one line per
    group in label order, never ordered by result."""
    lines = [_fault_lines_head(nested.grouping, nested.fault_lines)]
    for refusal in nested.grouping.refused:
        lines.append(
            f"  refused {refusal.key} ({refusal.rung}): {refusal.reason}; "
            f"{_look.reprint(refusal.detail)} next: {refusal.next_rung}"
        )
    lines.append(_fault_lines_null(nested.fault_lines))
    if nested.fault_lines.tested:
        # Only where the level was tested: there is no floor under a p nobody drew.
        lines.append(
            f"  group p floor {_look.fmt_p(nested.root.p_floor)}: the same "
            f"{_look.fmt_count(nested.root.n_permutations)} permutations; a group p at the "
            "floor is a bound, not a measurement"
        )
    for group in nested.fault_lines.groups:
        lines.append(_fault_lines_group(nested.grouping.key, group))
    return "\n".join(lines) + "\n"


def _cells_head(leaves: Leaves, bound: Bound) -> str:
    """The null in quotes and what tested it, or the first reason nothing did."""
    n = _look.fmt_count
    if leaves.tested:
        return (
            f'cells: "{leaves.null}" tested by BH within each of {n(leaves.n_families)} '
            f"rejecting groups at q {_look.fmt_p(leaves.q)}: {n(leaves.n_rejected)} of "
            f"{n(leaves.n_tests)} rejected"
        )
    if leaves.reason == "depth":
        return f"cells: not tested: depth {n(bound.depth_configured)}"
    if leaves.reason == "root_not_rejected":
        return "cells: not tested: the root did not reject"
    return "cells: not tested: no group rejected"


def _cells_family(family: CellFamily) -> str:
    """One rejected group's family: how many tests were in it, how many it could name, and what
    its cells could not have seen."""
    return (
        f"  {family.key}={family.label}  {_look.fmt_count(family.n_tests)} tests, "
        f"{_look.fmt_count(family.n_rejected)} rejected; cell MDE median "
        f"{_look.fmt_rate(family.mde_median)} / max {_look.fmt_rate(family.mde_max)}"
    )


def _cells_leaf(leaf: CellResult) -> str:
    """One named cell: its config, its event, and three numbers."""
    config = ", ".join(f"{key}={value}" for key, value in leaf.config.items())
    return (
        f"    {config}  {leaf.event}: delta {_look.fmt_rate(leaf.delta)}, "
        f"q {_look.fmt_p(leaf.q_within)}, MDE {_look.fmt_rate(leaf.mde)}"
    )


def _cells_block(nested: TreeResult) -> str:
    """Level 3, the block ``diff``'s text output appends after the fault-lines block: one
    family line per family, and under each one line per rejected cell in row order."""
    lines = [_cells_head(nested.leaves, nested.bound)]
    for family in nested.leaves.families:
        lines.append(_cells_family(family))
        for leaf in family.cells:
            if leaf.rejects:
                lines.append(_cells_leaf(leaf))
    return "\n".join(lines) + "\n"


def _bound_block(bound: Bound) -> str:
    """The error rate the whole procedure controls at, and the assumption it rests on."""
    n = _look.fmt_count
    lines = [
        f"bound: depth {n(bound.depth)} ({n(bound.depth_configured)} configured); "
        f"outer-nodes false discovery rate at most {_look.fmt_rate(bound.bound)} = "
        f"2 x {n(bound.depth)} x {_look.fmt_p(bound.q)} x {_look.fmt_rate(bound.delta_star)}",
        "  Yekutieli (2008) Corollary A.2, which assumes each p-value is independent of its "
        "ancestors; this tree's group and root statistics aggregate their own cells, so that "
        "assumption is not established here",
    ]
    return "\n".join(lines) + "\n"


def _write_summary(io: _IO, multi: MultiDiffResult) -> None:
    """Inference line when inferred, the headline, and the trade line when present."""
    if multi.inferred:
        io.line(multi.to_markdown().splitlines()[0])
    io.write(multi.headline() + "\n")
    trade = multi.trade_line()
    if trade is not None:
        io.line(trade)


class _Progress:
    """``done/total`` on stderr: one rewritten line when stderr is a terminal, else one line
    per tenth, counts with separators."""

    def __init__(self, io: _IO) -> None:
        self.io = io
        self.err = io.err
        self.tty = bool(getattr(io.err, "isatty", lambda: False)())
        self.decile = 0
        self.dirty = False

    def __call__(self, done: int, total: int) -> None:
        text = f"{_look.fmt_count(done)}/{_look.fmt_count(total)}"
        if self.tty:
            self.io.err_write(f"\r{text}")
            self.err.flush()
            self.dirty = True
            return
        decile = done * 10 // total if total else 10
        if decile > self.decile:
            self.decile = decile
            self.io.err_write(f"{text}\n")
            self.err.flush()

    def finish(self) -> None:
        if self.dirty:
            self.err.write("\n")


# ---------- sweep ----------


def _resolve_target(target: str) -> Any:
    """Import the local branch's rollout, turning any refusal at import into exit 1.

    A module that raises at import because it is outside the boundary it demands raises
    RuntimeError, which is a refusal of this target and not a bug in Prove.
    """
    try:
        return resolve(target)
    except (ValueError, ImportError, AttributeError, RuntimeError) as exc:
        raise _Refusal(f'cannot resolve --target "{target}": {exc}') from exc


def _require_extra(name: str) -> None:
    """A backend's package must import before the plan is built: a missing extra is refused
    first, with the install line."""
    try:
        found = importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        found = False
    if not found:
        raise _Refusal(
            f'the {name} backend needs the "{name}" extra, which is not installed',
            [_EXTRA_HINTS[name]],
        )


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

    A resume is the same run and inherits its own admission. ``--pair-with`` is not read here:
    a paired arm is a different run making its own claim.
    """
    if resume is None:
        return None
    try:
        recorded = store.manifest(resume).environment.get("max_mde_accepted")
    except StoreError:
        return None
    return float(recorded) if isinstance(recorded, (int, float)) else None


def _confirm(ns: argparse.Namespace, io: _IO) -> None:
    """Ask once on stderr, read exactly one line; anything but y/yes declines. Never hang."""
    if ns.yes:
        return
    if not io.inp.isatty():
        raise _Refusal(
            "stdin is not a terminal, so the question after the plan cannot be asked",
            [f"{shlex.join([_COMMAND, *ns.typed])} --yes"],
        )
    io.err_write("Proceed? [y/N] ")
    io.err.flush()
    answer = io.inp.readline().strip().lower()
    if answer not in ("y", "yes"):
        raise _Refusal("declined at the question; nothing was run")


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


def _cost_phrase(block: str) -> str:
    """The estimate as the plan names it, from the library's ``Cost:`` line."""
    for line in block.splitlines():
        if line.startswith("Cost: "):
            return _look.reprint(line[len("Cost: ") :])
    return "no estimate"


def _plan_sentence(p: Plan, block: str) -> str:
    spec = p.spec
    return (
        f"{_look.fmt_count(spec.total_rollouts())} rollouts: "
        f"{_look.fmt_count(len(spec.configs))} cells x {_look.fmt_count(spec.replicates)} "
        f"replicates on {p.backend}, {_cost_phrase(block)}"
    )


def _error_kind(error: Any) -> str | None:
    """What ``inspect --event`` matches an errored row on besides its stored text: ``timeout``
    for a timeout, else the exception's type name, the last line of the traceback up to its
    colon."""
    if not isinstance(error, str) or not error:
        return None
    if error == "timeout":
        return "timeout"
    last = [line for line in error.splitlines() if line.strip()]
    if not last:
        return None
    head = last[-1].strip().partition(":")[0].strip()
    return head.rsplit(".", 1)[-1] if head else None


def _commonest_error(store: Store, run_id: str) -> str | None:
    try:
        frame = store.read(run_id, meta=False)
    except StoreError:
        return None
    kinds = Counter(k for k in (_error_kind(e) for e in frame["error"].tolist()) if k)
    if not kinds:
        return None
    top = max(kinds.values())
    if kinds.get("timeout") == top:
        return "timeout"
    return next(kind for kind, count in kinds.items() if count == top)


def _cmd_sweep(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    ns.typed = [a for a in state.argv]
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
    if ns.backend == "modal":
        _require_extra("modal")
    spec_path = Path(ns.spec)
    spec = SweepSpec.load(spec_path)
    rollout: Any = None
    burla_options: BurlaOptions | None = None
    target: ModalTarget | None = None
    options: ModalOptions | None = None
    if ns.backend == "modal":
        # The container is the resolver: this machine only checks the path's shape, which
        # ModalTarget does. A target importable solely inside its image must not be imported here.
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
    state.planned = len(p.pairs)

    # Describe, then decide, then ask. The reader who gets a refusal has already been shown
    # the plan it is about; ``--yes`` skips only the question.
    if ns.backend == "modal":
        assert target is not None and options is not None
        block = preflight_modal(p, target, options)
    elif ns.backend == "burla":
        assert burla_options is not None
        try:
            block = preflight_burla(p, ns.target, burla_options)
        except ExecutorError as exc:
            # The cap refusal carries the plan it is about; it stays on screen (rule 7).
            kept = getattr(exc, "plan", None)
            if isinstance(kept, str) and not ns.json:
                io.line(f"plan  {_plan_sentence(p, kept)}")
                for line in kept.splitlines():
                    io.line(f"  {_look.reprint(line)}")
            raise
    else:
        block = preflight(p)
    sentence = _plan_sentence(p, block)
    detail = [_look.reprint(line) for line in block.splitlines()]
    if not ns.json:
        io.line(f"plan  {sentence}")
        for line in detail:
            io.line(f"  {line}")
    plan_payload: dict[str, Any] = {
        "run_id": p.run_id,
        "plan": {
            "rollouts": len(p.pairs),
            "cells": len(spec.configs),
            "replicates": spec.replicates,
            "backend": p.backend,
            "target": ns.target,
            "cost": _cost_phrase(block),
            "lines": detail,
        },
    }
    try:
        check_power(p, max_mde=p.max_mde_accepted)
    except UnderpoweredDesign as exc:
        nexts = []
        if exc.offered is not None:
            typed = [a for a in ns.typed]
            offered = _look.ceil3(exc.offered)
            if "--max-mde" in typed:
                at = typed.index("--max-mde")
                typed[at + 1 : at + 2] = [offered]
            else:
                typed.extend(["--max-mde", offered])
            nexts.append(shlex.join([_COMMAND, *typed]))
        raise _Refusal(str(exc), nexts) from exc
    if ns.backend == "modal":
        assert target is not None and options is not None
        _check_cost(p, options, target.image)
    if ns.dry_run:
        if ns.json:
            _write_json(io, "sweep", "plan", sentence, plan_payload, [])
        return 0
    _confirm(ns, io)

    state.run_id = p.run_id
    progress = _Progress(io)
    summary: RunSummary
    if ns.backend == "modal":
        assert target is not None and options is not None
        summary = run_modal(p, target, store, options=options, on_progress=progress)
    elif ns.backend == "burla":
        assert burla_options is not None
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
    return _sweep_result(ns, io, store, p, summary, plan_payload)


def _sweep_result(
    ns: argparse.Namespace,
    io: _IO,
    store: Store,
    p: Plan,
    summary: RunSummary,
    payload: dict[str, Any],
) -> int:
    """The closing verdict of a sweep: ``done``, or ``stopped`` with exit 3 when it stopped
    short or every rollout errored."""
    run_id = summary.run_id
    try:
        status = store.manifest(run_id).status
        tally = store.tally(run_id)
        kept = store.count(run_id)
        with_outcome, no_outcome, timed_out = tally.with_outcome, tally.no_outcome, tally.timed_out
    except StoreError:
        # A backend that stored nothing here (a launch answered elsewhere): the summary's own
        # counts stand in for the store's.
        status = "complete" if summary.complete else "partial"
        kept = summary.n_ok + summary.n_errored
        with_outcome, no_outcome, timed_out = summary.n_ok, summary.n_errored, summary.n_timeout
    planned = _look.fmt_count(len(p.pairs) + p.already_stored)
    n = _look.fmt_count
    nexts: list[str] = []
    code = 0
    if not summary.complete:
        verdict = "stopped"
        sentence = (
            f'{n(kept)} of {planned} rollouts kept in run "{run_id}" ({status}) '
            f"in {_look.fmt_duration(summary.wall_time)}"
        )
        nexts.append(f"{_COMMAND} sweep --resume")
        code = 3
    elif kept and with_outcome == 0:
        verdict = "stopped"
        commonest = _commonest_error(store, run_id)
        sentence = (
            f'every rollout errored in run "{run_id}": {n(no_outcome)} of {n(kept)}, '
            f"commonest {commonest or 'unknown'}"
        )
        if commonest is not None:
            nexts.append(f"{_COMMAND} inspect latest --event {commonest}")
        code = 3
    else:
        verdict = "done"
        sentence = (
            f'{n(kept)} rollouts in run "{run_id}" ({status}) in '
            f"{_look.fmt_duration(summary.wall_time)}"
        )
    details = [
        ("episodes with an outcome", n(with_outcome)),
        ("episodes with no outcome", n(no_outcome)),
        ("episodes timed out", n(timed_out)),
        ("wall time", _look.fmt_duration(summary.wall_time)),
    ]
    if summary.n_infra_retried or summary.n_infra_failed:
        details.append(("infrastructure retries", n(summary.n_infra_retried)))
        details.append(("infrastructure failures", n(summary.n_infra_failed)))
    if ns.json:
        payload = {
            **payload,
            "status": status,
            "rows": kept,
            "with_outcome": with_outcome,
            "no_outcome": no_outcome,
            "timed_out": timed_out,
            "wall_time_s": summary.wall_time,
            "stopped_by": summary.stopped_by,
        }
        _write_json(io, "sweep", verdict, sentence, payload, nexts)
        return code
    io.line(f"{verdict}  {sentence}")
    for label, value in details:
        io.detail(label, value)
    for command in nexts:
        io.next(command)
    return code


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
    # The root refuses an empty family, and ``diff`` on a pair with no comparable cell exits 0
    # today; turning that into a refusal is a later module's.
    wanted = primary.n_tests > 0
    nested = None
    if wanted and not (ns.json and others):
        # One call, one draw: the omnibus block and the fault-lines block are two renderings of
        # one ``TreeResult``. Grown before anything is printed, so a knob the tree refuses is a
        # refusal with nothing on stdout.
        nested = _diff_tree(ns, primary, frames, manifests)
    if ns.json:
        payload: Any = primary.to_json()
        if others:
            # ``--methods all`` keeps its three-method shape: the scheme follows the method, so
            # one omnibus and one tree beside three method objects would claim one test across
            # three.
            payload = {primary.method: payload, **{m: d.to_json() for m, d in others.items()}}
        elif nested is not None:
            payload = {**payload, "omnibus": nested.root.to_json(), "tree": nested.to_json()}
        _write_json(io, "diff", "ok", primary.headline().splitlines()[0], payload, [])
        return 0
    with _look.rule10():
        io.write(primary.to_markdown())
        if others:
            io.write("\n" + _method_table([primary, *others.values()]))
        coverage = _coverage_block(primary)
        if coverage:
            io.write("\n" + coverage)
        io.write("\n" + _interval_block(primary))
        if nested is not None:
            io.write("\n")
            io.write(_omnibus_block(nested.root))
            io.write("\n")
            io.write(_fault_lines_block(nested))
            io.write("\n")
            io.write(_cells_block(nested))
            io.write("\n")
            io.write(_bound_block(nested.bound))
    return 0


def _diff_tree(
    ns: argparse.Namespace,
    multi: MultiDiffResult,
    frames: tuple[pd.DataFrame, pd.DataFrame],
    manifests: tuple[RunManifest, RunManifest],
) -> TreeResult:
    """``tree`` on the pair ``multi`` was computed from, with the flags that move it, passed
    through untouched: the range checks live in the tree module, and argparse's ``choices``
    refuses a depth this parser was not offered."""
    try:
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
    except DiffError as exc:
        # The tree names its parameters; the user typed flags.
        text = str(exc)
        if "n_permutations" in text:
            raise _Refusal(text.replace("n_permutations", "--permutations")) from exc
        raise


def _prepare_out_dir(ns: argparse.Namespace, default: str) -> Path:
    """Refuse a non-empty ``--out`` before any work unless ``--force``; nothing is created yet."""
    out_dir = Path(ns.out) if ns.out else Path(default)
    if out_dir.exists():
        if not out_dir.is_dir():
            raise _Refusal(f"--out {out_dir} exists and is not a folder")
        if any(out_dir.iterdir()) and not ns.force:
            raise _Refusal(
                f"--out {out_dir} exists and is not empty",
                [shlex.join([_COMMAND, *_ns_argv(ns), "--force"])],
            )
    return out_dir


def _ns_argv(ns: argparse.Namespace) -> list[str]:
    return list(getattr(ns, "typed", []))


@contextmanager
def _staged(out_dir: Path) -> Iterator[Path]:
    """A folder to write into that becomes ``out_dir`` last: an interrupt or a failure while
    writing leaves no half-written folder behind. With ``out_dir`` already there (``--force``),
    the staged files move into it one by one."""
    parent = Path(os.path.abspath(out_dir)).parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=parent))
    # ``mkdtemp`` makes a private folder; a report folder is an ordinary one.
    mask = os.umask(0)
    os.umask(mask)
    os.chmod(staging, 0o777 & ~mask)
    try:
        yield staging
        if out_dir.exists():
            for item in staging.iterdir():
                target = out_dir / item.name
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                shutil.move(str(item), str(target))
            shutil.rmtree(staging, ignore_errors=True)
        else:
            os.replace(staging, out_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _write_report_files(
    io: _IO,
    out_dir: Path,
    report: MultiReport | SurvivalReport,
    receipt: MultiReport | SurvivalReport,
    bundle: _Bundle | None = None,
) -> list[Path]:
    """With a paired ``bundle`` the four sections are folded into the rendered strings and the
    files are written beside the three; every file is UTF-8 and named on a ``wrote`` line."""
    written: list[Path] = []
    with _staged(out_dir) as staging:
        with _look.rule10():
            markdown, page, figure = report.to_markdown(), receipt.to_html(), report.to_svg()
        if bundle is not None:
            markdown, page = _fold_markdown(markdown, bundle), _fold_html(page, bundle)
        (staging / "report.md").write_text(markdown, encoding="utf-8")
        (staging / "heatmap.svg").write_text(figure, encoding="utf-8")
        (staging / "receipt.html").write_text(page, encoding="utf-8")
        written.extend(out_dir / name for name in _REPORT_FILES)
        if bundle is not None:
            for name, artifact in bundle.artifacts.items():
                (staging / name).write_text(_artifact_text(artifact), encoding="utf-8")
                written.append(out_dir / name)
    return written


def _cmd_report(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    """The positional arity picks the verb: two run ids diff, one run id is a survival report."""
    ns.typed = [a for a in state.argv]
    runs: list[str] = list(ns.runs)
    if len(runs) not in (1, 2):
        raise _Usage(
            f"report takes one or two run ids, got {len(runs)}: {_REPORT_FORMS}",
            [f"{_COMMAND} report --help"],
        )
    if ns.x is None:
        raise _missing_flags_refusal(
            Store(root), "report", runs, state.argv, x_missing=True, event_missing=False
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
        # one that was given; here an absent knob becomes the tree's constant, by name. They go
        # on a copy of the namespace, because ``_diff_tree`` reads its knobs off ``ns``.
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
    with _look.rule10():
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
    bundle = None if declaration is None else _bundle(store, declaration)
    written = _write_report_files(io, out_dir, report, receipt, bundle)
    if ns.json:
        payload = {"out": str(out_dir), "wrote": [str(p) for p in written], **multi.to_json()}
        _write_json(io, "report", "ok", f"wrote {out_dir} ({len(written)} files)", payload, [])
        return 0
    _write_summary(io, multi)
    for path in written:
        io.line(str(path))
    return 0


def _paired_declaration(path: str, a: str, b: str) -> Declaration:
    """``report A B --paired DECL``: ``(A, B)`` must be the declared pair of one of the
    declaration's sweeps; any other pair is refused by name."""
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
    and the replicates, written as the five files (six at ``k > 2``). ``--json`` prints the
    combined payload and writes nothing; ``--cap-check`` says whether the recorded input tokens
    are under the declared cap, writes nothing, and exits 4 at or above it."""
    ns.typed = [a for a in state.argv]
    declaration = Declaration.from_toml(ns.declaration)
    store = Store(root)
    if ns.cap_check:
        report = paired_cost(
            store, declaration, phases={s.name: s.arms for s in declaration.sweeps}
        )
        n = _look.fmt_count
        tokens = n(report.input_tokens)
        if report.token_cap is None:
            verdict, sentence = "under cap", f"{tokens} input tokens recorded; no cap declared"
        elif report.cap_reached:
            verdict = "at cap"
            sentence = (
                f"{tokens} input tokens recorded, at or above the cap of {n(report.token_cap)}"
            )
        else:
            verdict = "under cap"
            sentence = f"{tokens} input tokens recorded, under the cap of {n(report.token_cap)}"
        code = 4 if report.cap_reached else 0
        if ns.json:
            _write_json(io, "paired", verdict, sentence, _cost_block(declaration, report), [])
            return code
        io.line(f"{verdict}  {sentence}")
        io.detail("output tokens", n(report.output_tokens))
        io.detail("request spans with usage", n(report.recorded_spans))
        io.detail("request spans without", n(report.unrecorded_spans))
        if report.dollars is not None:
            io.detail("dollars", _look.fmt_dollars(float(report.dollars)))
        return code
    if ns.json:
        bundle = _bundle(store, declaration)
        sentence = f"{_look.fmt_count(len(bundle.artifacts))} files, written nowhere"
        _write_json(io, "paired", "ok", sentence, bundle.payload, [])
        return 0
    out_dir = _prepare_out_dir(ns, f"./prove-paired-{declaration.digest[:12]}")
    bundle = _bundle(store, declaration)
    written: list[Path] = []
    with _staged(out_dir) as staging:
        for name, artifact in bundle.artifacts.items():
            (staging / name).write_text(_artifact_text(artifact), encoding="utf-8")
            written.append(out_dir / name)
    for path in written:
        io.line(str(path))
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
                f"cannot infer the event set: {exc}; outcome counts: {_outcome_counts(df)}",
                [f"{_COMMAND} report RUN --x AXIS --event NAME"],
            ) from exc
    else:
        events, non_event = tuple(dict.fromkeys(str(e) for e in ns.event)), None
    valid_t = df["t"].dropna()
    if valid_t.empty:
        raise _Refusal(f"run {run} has no rows with a time; nothing to report")
    horizon = float(valid_t.max()) if ns.horizon is None else float(ns.horizon)
    if horizon <= 0.0:
        typed = "the run's own" if ns.horizon is None else str(ns.horizon)
        raise _Refusal(f"--horizon must be above 0, got {typed}")

    # The competing set is every terminal outcome present, not only the events asked for: a
    # row that ended in the non-event is absorbed, not censored, so it must stay out of the
    # risk set.
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
    with _look.rule10():
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
    written = _write_report_files(io, out_dir, report, receipt)
    if ns.json:
        payload = {
            "out": str(out_dir),
            "wrote": [str(p) for p in written],
            "run_id": run,
            "events": list(events),
            "non_event": non_event,
            "horizon": horizon,
        }
        _write_json(io, "report", "ok", f"wrote {out_dir} ({len(written)} files)", payload, [])
        return 0
    if inferred:
        io.line(
            f"inferred: no event was given, so the event set is {', '.join(events)}; "
            f"the non-event is {non_event}, the most frequent outcome"
        )
    io.line(
        f"{run}: survival report over {', '.join(events)} at horizon "
        f"{_look.fmt_num(report.provenance['horizon'])}"
    )
    for path in written:
        io.line(str(path))
    return 0


def _check_sentence(multi: MultiDiffResult, fail_on: str) -> str:
    parts = []
    for event in multi.events:
        ev = multi.by_event[event]
        parts.append(
            f"{event}: {_look.fmt_count(ev.n_worse)} worse, {_look.fmt_count(ev.n_safer)} safer "
            f"in {_look.fmt_count(len(ev.cells))} conditions"
        )
    return f"{'; '.join(parts)}; fail on {fail_on}"


def _cmd_check(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    store = Store(root)
    if ns.event is None:
        raise _missing_flags_refusal(
            store, "check", [ns.a, ns.b], state.argv, x_missing=False, event_missing=True
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
    verdict = "passed" if passed else "failed"
    sentence = _check_sentence(multi, ns.fail_on)
    if ns.json:
        payload = {"passed": passed, "fail_on": ns.fail_on, **multi.to_json()}
        _write_json(io, "check", verdict, sentence, payload, [])
        return 0 if passed else 4
    io.line(f"{verdict}  {sentence}")
    io.detail("method", multi.method)
    io.line()
    _write_summary(io, multi)
    return 0 if passed else 4


def _cmd_serve(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    """``_report_pair`` up to the report, then a structure instead of three files.

    The structure is complete before anything binds, so every refusal happens with no listening
    socket in existence, and ``--json`` returns having bound nothing at all. Nothing on this
    path writes to the store, to the cwd, or to a temp file.
    """
    runs: list[str] = list(ns.runs)
    if len(runs) != 2:
        raise _Usage(
            f"serve takes two run ids, got {len(runs)}: {_SERVE_FORM}", [f"{_COMMAND} serve --help"]
        )
    a, b = runs[0], runs[1]
    store = Store(root)
    if ns.x is None or ns.event is None:
        raise _missing_flags_refusal(
            store,
            "serve",
            [a, b],
            state.argv,
            x_missing=ns.x is None,
            event_missing=ns.event is None,
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
    # After the report and before the structure: the report's axis check refuses an unknown
    # ``--x`` first, so no refusal spends a tree, and every tree refusal still fires before
    # anything binds. One call, one draw, on the frames ``_run_diffs`` already read.
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
        sentence = f'the page comparing "{a}" with "{b}", bound nowhere'
        _write_json(io, "serve", "ok", sentence, structure, None)
        return 0

    def announce(srv: Any) -> None:
        # Once the socket is up: an ephemeral port nobody is told about is a page nobody can
        # open. Flushed because stdout is block buffered when it is a pipe.
        io.line(f"http://{_HOST}:{srv.server_address[1]}/")
        io.out.flush()

    serve_page(render_html(structure), on_bind=announce)
    return 0


# ---------- inspect / runs ----------


def _envelopes(store: Store, run: str) -> pd.DataFrame:
    """The run's narrow frame with its trace envelopes: the one read the observation counts and
    the declaration check share."""
    return store.read(run, meta=False, trace="envelope")


def _declaration_check(store: Store, run: str) -> Any:
    """What the run declared against its stored envelopes, or ``None`` when it declared
    nothing."""
    return declaration_check(store.manifest(run), _envelopes(store, run))


def _observation_counts(store: Store, run: str) -> tuple[int, int]:
    """``(spans, spans stamped as cut)`` over the run's stored envelopes."""
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
    """The row's stored trace, or None when there is no readable one."""
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
            store, "inspect", [ns.run], state.argv, x_missing=False, event_missing=True
        )
    check = _declaration_check(store, ns.run)
    provenance = [] if check is None else _provenance_lines(check.provenance())
    # Select on the narrow frame; decode ``meta`` only for the rows that survive selection.
    df = store.read(ns.run, meta=False)
    where = _parse_pairs(ns.where, "--where")
    # An event is an outcome, an error text, or an error's kind: "timeout" for a timeout, else
    # the exception's type name.
    kinds = df["error"].map(_error_kind)
    rows = df[(df["outcome"] == ns.event) | (df["error"] == ns.event) | (kinds == ns.event)]
    for key, value in where.items():
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
        sentence = f'no rows with outcome or error "{ns.event}" in run "{ns.run}"'
        if ns.json:
            empty = {"run_id": ns.run, "event": ns.event, "episodes": []}
            _write_json(io, "inspect", "ok", sentence, empty, [])
            return 0
        io.line(f"ok  {sentence}")
        return 0
    selected = [
        (str(h), int(i))
        for h, i in zip(rows["config_hash"], rows["replicate_index"], strict=True)
    ]
    rows = store.read(ns.run, keys=selected)
    # The keyed read promises sorted rows and nothing more; sorting again keeps this loop's
    # order the store's.
    rows = rows.sort_values(["config_hash", "replicate_index"], kind="stable")
    first = rows.iloc[0]
    import_path = manifest.environment.get("import_path")
    if isinstance(import_path, str) and ":" in import_path:
        module, fn = import_path.split(":", 1)
    else:
        module, fn = "your_module", "rollout"
    sentence = (
        f"{_look.fmt_count(len(rows))} episode{'' if len(rows) == 1 else 's'} with outcome or "
        f'error "{ns.event}" in run "{ns.run}"'
    )
    if ns.json:
        episodes = []
        for row in rows.itertuples(index=False):
            episodes.append({
                "config_hash": str(row.config_hash),
                "config": dict(row.config),
                "seed": int(row.seed),
                "replicate_index": int(row.replicate_index),
                "outcome": None if not isinstance(row.outcome, str) else row.outcome,
                "t": None if row.t != row.t else float(row.t),
                "error": row.error if isinstance(row.error, str) else None,
            })
        payload = {
            "run_id": ns.run,
            "event": ns.event,
            "episodes": episodes,
            "reproduce": {
                "module": module,
                "function": fn,
                "config": dict(first["config"]),
                "seed": int(first["seed"]),
            },
        }
        _write_json(io, "inspect", "ok", sentence, payload, [])
        return 0
    io.line(f"ok  {sentence}")
    if provenance:
        for line in provenance:
            io.line(line)
    io.line()
    for row in rows.itertuples(index=False):
        io.line(f"config_hash: {_look.fmt_hash(row.config_hash)}")
        io.line(f"config: {json.dumps(row.config, sort_keys=True)}")
        io.line(f"seed: {row.seed}")
        io.line(f"replicate_index: {_look.fmt_count(row.replicate_index)}")
        if isinstance(row.error, str):
            # The errored row: no outcome and no time, its error where the ok row's t: line
            # stands.
            io.line("outcome: -")
            io.line("t: -")
            io.line(f"error: {row.error}")
        else:
            io.line(f"t: {_look.fmt_num(row.t)}")
        trace = _stored_trace(row.meta)
        if trace is not None:
            if trace.truncated is not None:
                # Begins with a letter, so it can never read as a span line.
                io.line(f"trace: truncated ({trace.truncated})")
            cut = [
                (j, span)
                for j, span in enumerate(trace.ordered())
                if span.truncated == "observation"
            ]
            if cut:
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
                io.line(f"observation: cut ({detail})")
            for j, span in enumerate(trace.ordered()):
                duration = span.duration_ms
                # Tab-delimited: a span name and an error message are free text, so a space
                # cannot be the column separator without shifting every column after it.
                io.line(
                    f"  {j}\t{span.kind or '-'}\t{span.name or '-'}\t"
                    f"{'-' if duration is None else duration}\t"
                    f"{'-' if span.error in (None, '') else span.error}\t"
                    f"{'-' if span.step_name is None else span.step_name}\t"
                    f"{'-' if span.attempt is None else span.attempt}\t"
                    f"{'-' if span.outcome is None else span.outcome}\t"
                    f"{'-' if span.gate is None else span.gate}"
                )
        io.line()

    io.line(_SNIPPET_MARKER)
    io.line(f"from {module} import {fn}")
    io.line(f"{fn}({json.dumps(first['config'], sort_keys=True)}, seed={first['seed']})")
    return 0


def _version_shown(m: RunManifest) -> str:
    return version_as_recorded(m.poisson_prove_version) if m.written_by else m.poisson_prove_version


def _cmd_runs(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    store = Store(root)
    entries: list[dict[str, Any]] = []
    for run_id in store.runs():
        m = store.manifest(run_id)
        entries.append({
            "run_id": run_id,
            "status": m.status,
            "backend": m.backend,
            "target_id": m.target_id,
            "t_unit": m.t_unit,
            "rows": store.count(run_id),
            "no_outcome": store.tally(run_id).no_outcome,
            "created_at": m.created_at,
            "poisson_prove_version": _version_shown(m),
        })
    count = _look.fmt_count(len(entries))
    sentence = f"{count} runs in {root}" if entries else f"no runs in {root}"
    nexts = [] if entries else [_first_sweep(root)]
    if ns.json:
        _write_json(io, "runs", "ok", sentence, {"store": str(root), "runs": entries}, nexts)
        return 0
    io.line(f"store: {root}")
    # ``no_outcome``, never ``errored``: the number says whether the executor stored an
    # outcome, not whether the run was healthy.
    header = ("run_id", "status", "backend", "target_id", "t_unit", "rows", "no_outcome")
    lines: list[tuple[str, ...]] = [header]
    for entry in entries:
        lines.append((
            str(entry["run_id"]), str(entry["status"]), str(entry["backend"]),
            str(entry["target_id"]), str(entry["t_unit"]), _look.fmt_count(entry["rows"]),
            _look.fmt_count(entry["no_outcome"]),
        ))
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    for line in lines:
        cells = (cell.ljust(w) for cell, w in zip(line, widths, strict=True))
        io.line("  ".join(cells).rstrip())
    if not entries:
        io.err_line(
            f"note: no runs in {root}. No directory under it holds a manifest.json; "
            f"{_store_source(ns)}."
        )
        io.err_line(f"  next: {_first_sweep(root)}")
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
