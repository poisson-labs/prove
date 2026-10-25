"""The command line, a face over the core.

Ten verbs: ``init`` writes a sweep spec, ``prove.toml``, and nothing else; ``sweep`` runs a plan
on a backend after showing the plan and asking; ``diff``, ``report``, ``check`` and ``serve``
operate on stored runs; ``inspect`` prints the ``(config, seed)`` pairs behind an event plus a
reproduction snippet; ``runs`` lists the store; ``paired`` asserts that a declaration's arms were
the same request replayed and writes the paired-replay files; ``ui`` builds the static dashboard
over the store. ``report`` and ``serve`` save the comparison they show into the store, ``diff``
and ``check`` save theirs with ``--save``. ``serve`` is the one verb that binds a socket: a
loopback listener holding one page built before the bind, which dies with the process.

This module computes nothing and decides nothing: it parses arguments, calls the core
(``poisson_prove.core``), and renders what comes back with the shared formatting. Every number it
prints is a field on a result object, spelled the way every Poisson Labs tool spells it: the look.

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
import html
import json
import math
import os
import re
import shlex
import shutil
import sys
import tempfile
import traceback
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TextIO

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

from poisson_prove import _look, core
from poisson_prove.core import (
    CAUSES,
    COVERAGE_COLUMNS,
    DEFAULT_DEPTH,
    DEFAULT_MAX_GROUP_MDE,
    DEFAULT_PERMUTATIONS,
    DEFAULT_SEED,
    DEPTHS,
    PAIRED_METHODS,
    TASK_FAMILY_KEYS,
    WHOLE_GRID,
    __version__,
)
from poisson_prove.report import (
    MultiReport,
    ReportError,
    ReportSpec,
    SurvivalReport,
    _interval_lines,
    build_multi_report,
    build_survival_report,
)
from poisson_prove.viewer import _HOST, ViewerError, build_structure, render_html, serve_page

__all__ = ["main"]

_COMMAND = "poisson-prove"
_ENV_STORE = core.ENV_STORE
_DEFAULT_STORE = core.DEFAULT_STORE
_DEFAULT_SPEC = core.DEFAULT_SPEC
_DEFAULT_BATCH_SIZE = 64
_DEFAULT_Q = core.DEFAULT_Q
_METHODS: tuple[str, ...] = core.METHODS
_LATEST_PARTIAL = core.LATEST_PARTIAL
_REPORT_FILES = ("report.md", "heatmap.svg", "receipt.html")
_SNIPPET_MARKER = "# reproduce one episode"
_DIFF_ONLY_FLAGS = (
    "method", "methods", "q", "permutations", "seed", "by", "max_group_mde", "depth", "paired",
)
_RUN_ONLY_FLAGS = ("horizon",)
_REPORT_FORMS = (
    "report A B --x AXIS [...]  (two runs, or none for previous and latest: a comparison) or "
    "report RUN --x AXIS [...]  (one run: a survival report)"
)
_SERVE_FORM = (
    "serve A B --event NAME --x AXIS [...]  (two runs, or none for previous and latest: a "
    "comparison view)"
)
#: The tool's own options, accepted before or after the verb.
_GLOBAL_OPTIONS = ("--store", "--plain", "--debug")
_VERB_NAMES = (
    "init", "sweep", "diff", "check", "report", "paired", "serve", "inspect", "runs", "ui",
)
_SCHEMAS = {verb: f"{_COMMAND}.{verb}/1" for verb in _VERB_NAMES}
_ERRORS_LOG = "~/.cache/poisson-prove/errors.log"


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
    #: Whether the verb saved its comparison before it was interrupted (``serve``), so the
    #: stopped line does not say nothing was written.
    saved: bool = False


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

    init_p = sub.add_parser(
        "init",
        help=f"write {_DEFAULT_SPEC}, a sweep spec to edit, or the keyless example",
        description=(
            f"Write a sweep spec, ./{_DEFAULT_SPEC} unless --out names another file, and nothing\n"
            "else: a commented template to edit, or with --example the keyless quickstart,\n"
            "runnable as it is. Nothing is asked."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} init --example\n"
            f"  {_COMMAND} init --target my_agent:rollout"
        ),
    )
    init_p.add_argument(
        "--example",
        action="store_true",
        help="write the keyless quickstart, which runs as it is (default: the template)",
    )
    init_p.add_argument(
        "--target",
        metavar="pkg.module:rollout",
        help="fill the template's target with this rollout (default: a commented placeholder)",
    )
    init_p.add_argument(
        "--out",
        metavar="PATH",
        help=f"the file to write (default: ./{_DEFAULT_SPEC})",
    )
    init_p.add_argument(
        "--force", action="store_true", help="replace the file if it exists (default: refuse)"
    )
    _add_json_option(init_p, "the file written")
    _add_global_options(init_p, top=False)

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
            f"  {_COMMAND} sweep\n"
            f"  {_COMMAND} sweep --target my_agent:rollout_patched --pair-with latest --yes\n"
            f"  {_COMMAND} sweep other.toml --target my_agent:rollout --replicates 300"
        ),
    )
    sweep.add_argument(
        "spec",
        metavar="SPEC.toml",
        nargs="?",
        help=f"the sweep spec: the target, the axes, the replicates (default: ./{_DEFAULT_SPEC})",
    )
    sweep.add_argument(
        "--target",
        metavar="pkg.module:rollout",
        help="import path of the rollout function; wins over the spec's target (default: the "
        "spec's target)",
    )
    sweep.add_argument(
        "--replicates",
        type=int,
        metavar="N",
        help="replicates per condition for this run, recorded in its manifest (default: the "
        "spec's replicates)",
    )
    sweep.add_argument(
        "--backend",
        choices=("local", "modal", "burla"),
        default="local",
        help="where the rollouts run: local, modal or burla (burla is experimental; "
        "default: local)",
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
        "--resume",
        metavar="RUN",
        nargs="?",
        const=_LATEST_PARTIAL,
        help="continue that partial run where it stopped; alone, the latest partial run; "
        "written after SPEC.toml when a spec is given, so the spec is not read as the run "
        "(default: none)",
    )
    sweep.add_argument(
        "--name", metavar="TEXT", help="the name the new run goes by (default: computed)"
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
    diff_p.add_argument(
        "runs", nargs="*", metavar="RUN",
        help="the baseline and the candidate (default: previous and latest)",
    )
    _add_event_argument(diff_p, "default: inferred from the outcomes present")
    _add_method_arguments(diff_p, defaults=True)
    diff_p.add_argument(
        "--methods",
        choices=("all",),
        help="also run the other two methods and print them side by side (default: one method)",
    )
    _add_json_option(diff_p, "the comparison")
    diff_p.add_argument(
        "--save",
        action="store_true",
        help="save the comparison into the store, under .poisson/artifacts/ (default: not saved)",
    )
    _add_tree_arguments(diff_p, defaults=True)
    _add_global_options(diff_p, top=False)

    report_p = sub.add_parser(
        "report",
        help="write report.md, heatmap.svg and receipt.html for two runs, or one, and save the "
            "comparison",
        description=(
            "Write a report folder: two runs give the comparison with its heatmap, one run gives\n"
            "its survival report. The folder holds report.md, heatmap.svg and receipt.html. A\n"
            "comparison is also saved into the store, under .poisson/artifacts/."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} report latest previous --x tool_fail_rate --y task_id\n"
            f"  {_COMMAND} report latest --x tool_fail_rate --event violated"
        ),
    )
    report_p.add_argument(
        "runs", nargs="*", metavar="RUN",
        help="A B for a comparison, one RUN for a survival report (default: previous and latest)",
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
    check_p.add_argument(
        "runs", nargs="*", metavar="RUN",
        help="the baseline and the candidate (default: previous and latest)",
    )
    _add_event_argument(
        check_p,
        "required: a gate never infers its events; omitted: lists the events the runs carry; "
        "no default",
        shown=True,
    )
    _add_method_arguments(check_p, defaults=True)
    check_p.add_argument(
        "--fail-on",
        choices=("worse", "any", "higher", "lower"),
        default="worse",
        help="fail on a condition significantly worse, on any significant change, or on a rate "
        "that rose (higher) or fell (lower); worse needs each event's kind (default: worse)",
    )
    _add_json_option(check_p, "the verdict and the comparison")
    check_p.add_argument(
        "--save",
        action="store_true",
        help="save the check into the store, under .poisson/artifacts/ (default: not saved)",
    )
    _add_global_options(check_p, top=False)

    serve_p = sub.add_parser(
        "serve",
        help="serve a read-only page comparing two runs on a loopback port, and save the "
            "comparison",
        description=(
            "Serve a read-only page for one pair of runs on an ephemeral loopback port, built\n"
            "before the bind; the comparison it shows is saved into the store, under\n"
            ".poisson/artifacts/, before the page is served; Ctrl-C stops it."
        ),
        epilog=(
            "examples:\n"
            f"  {_COMMAND} serve latest previous --x tool_fail_rate --event violated\n"
            f"  {_COMMAND} serve latest previous --x tool_fail_rate --event violated --json"
        ),
    )
    serve_p.add_argument(
        "runs", nargs="*", metavar="RUN",
        help="the baseline and the candidate, in that order (default: previous and latest)",
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
    inspect_p.add_argument(
        "run",
        nargs="?",
        default="latest",
        metavar="RUN",
        help="the run to inspect (default: latest)",
    )
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

    ui_p = sub.add_parser(
        "ui",
        help="build the static dashboard over the store and say where it is",
        description=(
            "Build the static dashboard in the store's .poisson/ui/: the runs, the saved\n"
            "comparisons, their verdicts and charts, as pages opened from disk with nothing\n"
            "loaded from the network. Every command that writes a run or saves a comparison\n"
            "refreshes a dashboard the store already has."
        ),
        epilog=f"examples:\n  {_COMMAND} ui\n  {_COMMAND} ui --open",
    )
    ui_p.add_argument(
        "--open", action="store_true", help="open the dashboard in the browser (default: not "
            "opened)"
    )
    _add_json_option(ui_p, "where the dashboard is")
    _add_global_options(ui_p, top=False)

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
    user did not pass, so the single-run report can name the diff-only flags it was given.
    ``--method`` keeps ``None`` either way: the default test is the comparison's to choose from
    the two manifests, and whether it was named is what every surface says."""
    p.add_argument(
        "--method",
        choices=_METHODS,
        default=None,
        help="the per-condition test: fisher_bh treats the two runs as separate samples, "
        "mcnemar_bh pairs them on their shared seeds, logrank_bh is time to the event "
        "(default: mcnemar_bh for runs paired at sweep time, else fisher_bh)",
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
        f"{'/'.join(TASK_FAMILY_KEYS)}, or {WHOLE_GRID} "
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


def _refused(io: _IO, exc: core.Refusal) -> None:
    """A core refusal: its sentence as it is, then its commands."""
    for note in exc.notes:
        io.err_line(f"note: {note}")
    io.err_line(f"error: {exc}")
    for command in exc.next:
        io.err_line(f"  next: {command}")


def _notes_of(io: _IO, result: Any) -> None:
    for note in getattr(result, "notes", ()):
        io.err_line(f"note: {note}")


@contextmanager
def _notes(io: _IO) -> Iterator[None]:
    """Every warning Prove raises outside the core reaches the user as one ``note:`` line; a
    library's warning is not shown."""

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
    state = _State(
        json=bool(getattr(ns, "json", False)),
        verb=ns.verb,
        debug=bool(getattr(ns, "debug", False)),
        argv=list(argv),
    )
    try:
        with _notes(io):
            if ns.verb == "sweep" and ns.backend == "burla" and os.name == "nt":
                # Burla's launcher needs fcntl, select on pipes and process groups.
                raise _Refusal(
                    "the burla backend cannot run on Windows; run it from macOS or Linux"
                )
            store = core.open_store(getattr(ns, "store", None), verb=ns.verb)
            for note in store.notes:
                io.err_line(f"note: {note}")
            return _VERBS[ns.verb](ns, io, store, state)
    except _Usage as exc:
        _write_error(io, str(exc), exc.nexts)
        return 2
    except _Refusal as exc:
        _write_error(io, str(exc), exc.nexts)
        return 1
    except core.Refusal as exc:
        if exc.plan is not None and not state.json:
            _print_plan(io, exc.plan)
        _refused(io, exc)
        return 2 if exc.usage else 1
    except (ReportError, ViewerError) as exc:
        _write_error(io, str(exc), getattr(exc, "nexts", ()))
        return 1
    except core.Stopped as exc:
        if not state.json:
            io.line(f"stopped  {exc.sentence}")
            for command in exc.next:
                io.next(command)
        io.err_line(f"error: {exc.error}")
        return 3
    except core.Interrupted as exc:
        if state.json:
            _write_json(io, state.verb, "stopped", exc.sentence, {}, exc.next)
        else:
            io.line(f"stopped  {exc.sentence}")
            for command in exc.next:
                io.next(command)
        return 130
    except KeyboardInterrupt:
        sentence = "interrupted" if state.saved else "interrupted; nothing was written"
        if state.json:
            _write_json(io, state.verb, "stopped", sentence, {}, [])
        else:
            io.line(f"stopped  {sentence}")
        return 130
    except BrokenPipeError:
        raise
    except Exception as exc:
        return _unexpected(io, state, exc)


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


def _print_result(io: _IO, verb: str, result: Any) -> None:
    """A core result's document, the verb's schema in place of the result's."""
    doc = result.to_json()
    _write_json(io, verb, doc["verdict"], doc["sentence"], doc, doc["next"])


def _slug(name: str) -> str:
    """A run's name as a folder name: lower case, spaces and slashes as dashes."""
    return name.lower().replace(" ", "-").replace("/", "-")


def _add_names(node: Any, names: Mapping[str, str]) -> Any:
    """A document with ``run_name`` placed after every key named exactly ``run_id``."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            out[key] = _add_names(value, names)
            if isinstance(value, str) and key == "run_id":
                out["run_name"] = names.get(value, value)
        return out
    if isinstance(node, list):
        return [_add_names(v, names) for v in node]
    return node


def _two_runs(verb: str, words: Sequence[str]) -> tuple[str | None, str | None]:
    if len(words) == 0:
        return None, None
    if len(words) == 2:
        return words[0], words[1]
    raise _Usage(f"{verb} takes two runs or none, got {len(words)}", [f"{_COMMAND} {verb} --help"])


# ---------- rendering ----------


def _verdict_block(io: _IO, result: core.Comparison, saved: core.ArtifactRef | None = None) -> None:
    """The verdict line, then its detail lines, as the result gives them, then what was saved;
    a blank line ends it."""
    io.line(f"{result.verdict}  {result.sentence}")
    for label, text in result.detail:
        io.detail(label, text)
    if saved is not None:
        io.detail("saved", f"{saved.kind} {_look.fmt_hash(saved.id)}")
    io.line()


def _save(io: _IO, store: Any, result: core.Comparison) -> core.ArtifactRef | None:
    """Save the result the verb computed; a store that cannot be written to gets one note and
    the command goes on."""
    try:
        saved: core.ArtifactRef = core.save(store, result)
    except core.Unsaved as exc:
        io.err_line(f"note: {exc}")
        return None
    if saved.unrefreshed is not None:
        # The pages are derived and the previous ones stand; the one line says so and names ui.
        io.err_line(
            f"note: the dashboard's pages were not refreshed ({saved.unrefreshed}); "
            f"run {_COMMAND} ui"
        )
    return saved


def _with_saved(doc: Mapping[str, Any], saved: core.ArtifactRef | None) -> dict[str, Any]:
    """A result's document with ``saved`` (the artifact's folder, relative to the store) before
    ``next``."""
    if saved is None:
        return dict(doc)
    out = {k: v for k, v in doc.items() if k != "next"}
    out["saved"] = saved.path
    if "next" in doc:
        out["next"] = doc["next"]
    return out


def _method_markdown(markdown: str, line: str, pair: Sequence[str] = ()) -> str:
    """``report.md`` with the method's line as a paragraph of its own at the end of the header,
    just before the first section, and the two runs by name and id before it; the lines under
    the title keep their places."""
    block = "".join(f"{entry}\n" for entry in pair) + ("\n" if pair else "") + f"method: {line}\n"
    at = markdown.find("\n\n## ")
    if at < 0:
        return f"{markdown.rstrip(chr(10))}\n\n{block}"
    return f"{markdown[: at + 2]}{block}\n{markdown[at + 2 :]}"


def _method_html(page: str, line: str, *, summary: bool = False, pair: Sequence[str] = ()) -> str:
    """A page with the method's line as a paragraph of its own under its ``<h1>`` (and, with
    ``summary``, under its Summary heading), the two runs by name and id before it."""
    words = html.escape(line)
    runs = "".join(f"\n<p>{html.escape(entry)}</p>" for entry in pair)
    page = page.replace("</h1>", f"</h1>{runs}\n<p>method: {words}</p>", 1)
    if summary:
        page = re.sub(
            r"(<h2\b[^>]*>\s*Summary\s*</h2>)",
            lambda m: f"{m.group(1)}\n<p>Method: {words}.</p>",
            page,
            count=1,
        )
    return page


def _method_of(result: core.Comparison) -> str:
    return next(text for label, text in result.detail if label == "method")


def _method_table(results: Sequence[Any]) -> str:
    # The two count columns are an event's safer and worse with a kind, and its falls and rises
    # without one; the header keeps M10's names, which its frozen test reads.
    known = all(m.all_kinds_known() for m in results)
    header = ("method", "event", "pairing", "safer", "worse", "unchanged", "max_mde")
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for m in results:
        pairing = "paired" if m.method in PAIRED_METHODS else "unpaired"
        for e in m.events:
            ev = m.by_event[e]
            n_down, n_up = (ev.n_safer, ev.n_worse) if known else (ev.n_lower, ev.n_higher)
            lines.append(
                f"| {m.method} | {e} | {pairing} | {_look.fmt_count(n_down)} | "
                f"{_look.fmt_count(n_up)} | {_look.fmt_count(ev.n_unchanged)} | "
                f"{_look.fmt_rate(ev.max_mde)} |"
            )
    return "\n".join(lines) + "\n"


def _md_cell(value: Any, column: str | None = None) -> str:
    """A table cell, in the look's forms for its column."""
    if isinstance(value, Mapping):
        return json.dumps(_look.native(value), sort_keys=True, separators=(",", ":"))
    plain = _look.native(value)
    if column is not None and _look.active():
        if column in ("config_hash", "max_mde_unchanged_cell"):
            return _look.fmt_hash(plain)
        if isinstance(plain, bool) or plain is None or isinstance(plain, str):
            return str(plain)
        if isinstance(plain, int):
            return _look.fmt_count(plain)
        if isinstance(plain, float):
            return _look.fmt_num(plain)
        return str(plain)
    if isinstance(plain, float):
        return f"{plain:.6g}"
    return str(plain)


def _coverage_block(multi: Any) -> str:
    """The coverage facts ``diff``'s text output appends, after the markdown and after the
    ``--methods all`` table."""
    frame = multi.coverage
    if frame is None:  # never from the core; a hand-built result says nothing.
        return ""
    holes = frame[~frame["comparable"]]
    counts = {cause: int((holes["cause"] == cause).sum()) for cause in CAUSES}
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


def _interval_block(multi: Any) -> str:
    lines = _interval_lines(multi)
    return "\n".join([lines[0], *(f"  {line}" for line in lines[1:])]) + "\n"


def _omnibus_block(dual_root: Any) -> str:
    """The tree's root, the block ``diff``'s text output appends after the interval block."""
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


def _fault_lines_head(cut: Any, fault: Any) -> str:
    n = _look.fmt_count
    return (
        f"fault lines: grouping {cut.key} ({cut.resolved_by}), {n(cut.n_groups)} groups; "
        f"cells per group min {n(cut.size_min)} / median {_look.fmt_num(cut.size_median)} / "
        f"max {n(cut.size_max)}; {n(fault.n_degenerate_groups)} degenerate; "
        f"{n(cut.n_resolvable_groups)} of {n(cut.n_groups)} groups resolve "
        f"{_look.fmt_rate(cut.max_group_mde)} at alpha {_look.fmt_p(cut.alpha_floor)}"
    )


def _fault_lines_null(fault: Any) -> str:
    if fault.tested:
        return (
            f'  "{fault.null}" tested by BH across {_look.fmt_count(fault.n_groups)} groups at '
            f"q {_look.fmt_p(fault.q)}: {_look.fmt_count(fault.n_rejected_groups)} rejected"
        )
    if fault.reason == "one_group":
        return f'  "{fault.null}" not tested: one group is the whole family restated'
    return f'  "{fault.null}" not tested: the root did not reject'


def _fault_lines_group(key: str, group: Any) -> str:
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


def _fault_lines_block(nested: Any) -> str:
    lines = [_fault_lines_head(nested.grouping, nested.fault_lines)]
    for refusal in nested.grouping.refused:
        lines.append(
            f"  refused {refusal.key} ({refusal.rung}): {refusal.reason}; "
            f"{_look.reprint(refusal.detail)} next: {refusal.next_rung}"
        )
    lines.append(_fault_lines_null(nested.fault_lines))
    if nested.fault_lines.tested:
        lines.append(
            f"  group p floor {_look.fmt_p(nested.root.p_floor)}: the same "
            f"{_look.fmt_count(nested.root.n_permutations)} permutations; a group p at the "
            "floor is a bound, not a measurement"
        )
    for group in nested.fault_lines.groups:
        lines.append(_fault_lines_group(nested.grouping.key, group))
    return "\n".join(lines) + "\n"


def _rate_or_none(value: float) -> str:
    return "none" if math.isnan(value) else _look.fmt_rate(value)


def _cells_head(leaves: Any, bound: Any) -> str:
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


def _cells_family(family: Any) -> str:
    return (
        f"  {family.key}={family.label}  {_look.fmt_count(family.n_tests)} tests, "
        f"{_look.fmt_count(family.n_rejected)} rejected; cell MDE median "
        f"{_rate_or_none(family.mde_median)} / max {_rate_or_none(family.mde_max)}"
    )


def _cells_leaf(leaf: Any) -> str:
    config = ", ".join(f"{key}={value}" for key, value in leaf.config.items())
    return (
        f"    {config}  {leaf.event}: delta {_look.fmt_rate(leaf.delta)}, "
        f"q {_look.fmt_p(leaf.q_within)}, MDE "
        f"{leaf.mde_note if math.isnan(leaf.mde) and leaf.mde_note else _rate_or_none(leaf.mde)}"
    )


def _cells_block(nested: Any) -> str:
    lines = [_cells_head(nested.leaves, nested.bound)]
    for family in nested.leaves.families:
        lines.append(_cells_family(family))
        for leaf in family.cells:
            if leaf.rejects:
                lines.append(_cells_leaf(leaf))
    return "\n".join(lines) + "\n"


def _bound_block(bound: Any) -> str:
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


def _write_summary(io: _IO, multi: Any) -> None:
    """Inference line when inferred, the headline, and the trade line when present."""
    if multi.inferred:
        io.line(multi.to_markdown().splitlines()[0])
    io.write(multi.headline() + "\n")
    trade = multi.trade_line()
    if trade is not None:
        io.line(trade)


class _Progress:
    """The sweep's progress events as ``done/total`` on stderr: one rewritten line when stderr
    is a terminal, else one line per tenth, counts with separators."""

    def __init__(self, io: _IO) -> None:
        self.io = io
        self.err = io.err
        self.tty = bool(getattr(io.err, "isatty", lambda: False)())
        self.decile = 0
        self.dirty = False

    def __call__(self, event: Any) -> None:
        doc = event.to_json()
        if doc["kind"] != "progress":
            return
        done, total = int(doc["detail"]["done"]), int(doc["detail"]["total"])
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


def _print_plan(io: _IO, p: core.Plan) -> None:
    io.line(f"plan  {p.sentence}")
    for line in p.lines:
        io.line(f"  {line}")
    if p.design_line is not None:
        io.line(p.design_line)


# ---------- sweep ----------


def _sweep_overrides(ns: argparse.Namespace, state: _State) -> dict[str, Any]:
    keys = (
        "target", "replicates", "backend", "image", "salt", "pair_with", "resume", "name",
        "max_mde", "episode_timeout", "max_rollouts", "batch_size", "concurrency",
        "infra_retries", "max_cost", "est_seconds", "app_name",
    )
    out = {key: getattr(ns, key, None) for key in keys}
    out["typed"] = list(state.argv)
    out["spec_typed"] = ns.spec
    return out


def _cmd_sweep(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    planned = core.plan(None, store=store, overrides=_sweep_overrides(ns, state))
    _notes_of(io, planned)
    if not ns.json:
        _print_plan(io, planned)
    if ns.dry_run:
        if ns.json:
            _print_result(io, "sweep", planned)
        return 0
    if not ns.yes and not io.inp.isatty():
        raise _Refusal(
            "stdin is not a terminal, so the question after the plan cannot be asked",
            [f"{_look.command(_COMMAND, *planned.options['typed_named'])} --yes"],
        )
    if not ns.yes:
        io.err_write("Proceed? [y/N] ")
        io.err.flush()
        answer = io.inp.readline().strip().lower()
        if answer not in ("y", "yes"):
            raise _Refusal("declined at the question; nothing was run")
    progress = _Progress(io)
    try:
        result = core.start(planned, on_event=progress)
    finally:
        progress.finish()
    _notes_of(io, result)
    if ns.json:
        _print_result(io, "sweep", result)
        return 3 if result.stopped else 0
    io.line(f"{result.verdict}  {result.sentence}")
    for label, value in result.details:
        io.detail(label, value)
    for command in result.next:
        io.next(command)
    return 3 if result.stopped else 0


# ---------- init ----------


def _cmd_init(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    """Write one sweep spec and nothing else. Asks nothing."""
    written = core.init(
        ns.out, example=ns.example, target=ns.target, force=ns.force, typed=state.argv
    )
    if ns.json:
        _print_result(io, "init", written)
        return 0
    io.line(f"ok  {written.sentence}")
    for command in written.next:
        io.next(command)
    return 0


# ---------- diff / report / check ----------


def _cmd_diff(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    a, b = _two_runs("diff", ns.runs)
    result = core.compare(
        store, a, b, events=ns.event, method=ns.method, q=ns.q, methods=ns.methods, by=ns.by,
        permutations=ns.permutations, seed=ns.seed, max_group_mde=ns.max_group_mde, depth=ns.depth,
    )
    _notes_of(io, result)
    saved = _save(io, store, result) if ns.save else None
    if ns.json:
        doc = _with_saved(result.to_json(), saved)
        _write_json(io, "diff", doc["verdict"], doc["sentence"], doc, doc["next"])
        return 0
    multi, nested = result.multi, result.tree
    _verdict_block(io, result, saved)
    with _look.rule10():
        io.write(multi.to_markdown())
        if result.others:
            io.write("\n" + _method_table([multi, *result.others.values()]))
        coverage = _coverage_block(multi)
        if coverage:
            io.write("\n" + coverage)
        io.write("\n" + _interval_block(multi))
        io.write("\n")
        io.write(_omnibus_block(nested.root))
        io.write("\n")
        io.write(_fault_lines_block(nested))
        io.write("\n")
        io.write(_cells_block(nested))
        io.write("\n")
        io.write(_bound_block(nested.bound))
    for command in result.next:
        io.write("\n")
        io.next(command)
    return 0


def _ns_argv(ns: argparse.Namespace) -> list[str]:
    return list(getattr(ns, "typed", []))


def _prepare_out_dir(
    ns: argparse.Namespace, default: str, named: Sequence[str] | None = None
) -> Path:
    """Refuse a non-empty ``--out`` before any work unless ``--force``; nothing is created yet."""
    out_dir = Path(ns.out) if ns.out else Path(default)
    if out_dir.exists():
        if not out_dir.is_dir():
            raise _Refusal(f"--out {out_dir} exists and is not a folder")
        if any(out_dir.iterdir()) and not ns.force:
            raise _Refusal(
                f"--out {out_dir} exists and is not empty",
                [
                    _look.command(
                        _COMMAND, *(named if named is not None else _ns_argv(ns)), "--force"
                    )
                ],
            )
    return out_dir


@contextmanager
def _staged(out_dir: Path) -> Iterator[Path]:
    """A folder to write into that becomes ``out_dir`` last: an interrupt or a failure while
    writing leaves no half-written folder behind."""
    parent = Path(os.path.abspath(out_dir)).parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=parent))
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
    bundle: Any = None,
    method_line: str | None = None,
    pair: Sequence[str] = (),
) -> list[Path]:
    written: list[Path] = []
    with _staged(out_dir) as staging:
        with _look.rule10():
            markdown, page, figure = report.to_markdown(), receipt.to_html(), report.to_svg()
        if bundle is not None:
            markdown, page = bundle.fold_markdown(markdown), bundle.fold_html(page)
        if method_line is not None:
            markdown = _method_markdown(markdown, method_line, pair)
            page = _method_html(page, method_line, pair=pair)
        (staging / "report.md").write_text(markdown, encoding="utf-8")
        (staging / "heatmap.svg").write_text(figure, encoding="utf-8")
        (staging / "receipt.html").write_text(page, encoding="utf-8")
        written.extend(out_dir / name for name in _REPORT_FILES)
        if bundle is not None:
            for name, text in bundle.texts.items():
                (staging / name).write_text(text, encoding="utf-8")
                written.append(out_dir / name)
    return written


def _wrote_sentence(out_dir: Path, written: Sequence[Path]) -> str:
    count = len(written)
    return f"wrote {out_dir} ({_look.fmt_count(count)} file{'' if count == 1 else 's'})"


def _wrote(io: _IO, out_dir: Path, written: Sequence[Path]) -> None:
    io.line(f"ok  {_wrote_sentence(out_dir, written)}")
    for path in written:
        io.detail("wrote", str(path))


def _name_provenance(provenance: dict[str, object], result: core.Comparison) -> None:
    """For a pair of one run written under the old name and one this build wrote, a provenance
    line per old run saying which run that was, by name, beside the pair's run ids."""
    writers = result.writers
    added = {
        f"run_{'a' if role == 'before' else 'b'}": (
            f'"{result.names.get(run_id, run_id)}", {writers[role]}'
        )
        for role, run_id in (("before", result.run_a), ("after", result.run_b))
        if role in writers
    }
    if not added:
        return
    items = list(provenance.items())
    provenance.clear()
    for key, value in items:
        provenance[key] = value
        if key == "run_salt":
            provenance.update(added)
            added = {}
    provenance.update(added)


def _cmd_report(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    """The positional arity picks the verb: two runs (or none) compare, one run is a survival
    report."""
    ns.typed = list(state.argv)
    words: list[str] = list(ns.runs)
    if len(words) not in (0, 1, 2):
        raise _Usage(
            f"report takes one or two runs, or none, got {len(words)}: {_REPORT_FORMS}",
            [f"{_COMMAND} report --help"],
        )
    if len(words) == 1:
        return _report_run(ns, io, store, words[0], state)
    return _report_pair(ns, io, store, words, state)


def _report_pair(
    ns: argparse.Namespace, io: _IO, store: Any, words: Sequence[str], state: _State
) -> int:
    a, b = _two_runs("report", words)
    if ns.x is None:
        core.compare(store, a, b, verb="report", require_x=True, typed=state.argv)
    stray = [f"--{name}" for name in _RUN_ONLY_FLAGS if getattr(ns, name) is not None]
    if stray:
        raise _Refusal(
            f"{', '.join(stray)}: single-run flag{'s' if len(stray) > 1 else ''}; a diff report "
            f"takes its horizon from the two runs ({_REPORT_FORMS})"
        )
    first = core.resolve(store, "previous" if a is None else a)
    second = core.resolve(store, "latest" if b is None else b)
    named = core.runs(store, counted=False)
    names = {run.run_id: run.run_name for run in named}
    out_dir = _prepare_out_dir(
        ns,
        f"./prove-report-{_slug(names.get(first, first))}-vs-{_slug(names.get(second, second))}",
        _named_words(state.argv, named),
    )
    result = core.compare(
        store, a, b, events=ns.event, method=ns.method, q=_DEFAULT_Q if ns.q is None else ns.q,
        methods=ns.methods, by=ns.by, permutations=ns.permutations, seed=ns.seed,
        max_group_mde=ns.max_group_mde, depth=ns.depth, verb="report", for_report=True, fix=ns.fix,
        paired=ns.paired,
    )
    _notes_of(io, result)
    multi = result.multi
    spec = ReportSpec(
        title=ns.title if ns.title else result.title,
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=dict(result.fixed),
        comparison=dict(result.others),
        theme=ns.theme,
        top_n=ns.top_n,
        forest=ns.forest,
    )
    with _look.rule10():
        report = build_multi_report(
            multi, spec, manifests=result.manifests, tree=result.tree,
            observations=result.observations, declarations=result.declarations,
        )
        receipt = (
            report
            if spec.theme == "light"
            else build_multi_report(
                multi, dataclasses.replace(spec, theme="light"), manifests=result.manifests,
                tree=result.tree, observations=result.observations,
                declarations=result.declarations,
            )
        )
    for built in {id(report): report, id(receipt): receipt}.values():
        _name_provenance(built.provenance, result)
        # Each run's id is in the header beside its name, so the provenance list gives it no more.
        built.provenance.pop("run_id_a", None)
        built.provenance.pop("run_id_b", None)
    pair = [
        f"before  {result.names.get(result.run_a, result.run_a)} ({result.run_a})",
        f"after  {result.names.get(result.run_b, result.run_b)} ({result.run_b})",
    ]
    written = _write_report_files(
        io, out_dir, report, receipt, result.bundle, _method_of(result), pair
    )
    saved = _save(io, store, result)
    if ns.json:
        doc = result.to_json()
        payload = {"out": str(out_dir), "wrote": [str(p) for p in written]}
        # Under --methods all the comparison's document holds one per method; the report's
        # carries the one it rendered, flat.
        body = doc[result.method] if result.others else doc
        dropped = ("schema", "verdict", "sentence", "next", "omnibus", "tree")
        payload.update({k: v for k, v in body.items() if k not in dropped})
        if saved is not None:
            payload["saved"] = saved.path
        _write_json(io, "report", "ok", _wrote_sentence(out_dir, written), payload, [])
        return 0
    _wrote(io, out_dir, written)
    if saved is not None:
        io.detail("saved", f"{saved.kind} {_look.fmt_hash(saved.id)}")
    io.line()
    _write_summary(io, multi)
    return 0


def _named_words(argv: Sequence[str], named: Sequence[Any]) -> list[str]:
    """The command as typed with every run id replaced by its name."""
    by_id = {run.run_id: run for run in named}
    return [by_id[token].run_name if token in by_id else token for token in argv]


def _report_run(ns: argparse.Namespace, io: _IO, store: Any, word: str, state: _State) -> int:
    if ns.x is None:
        core.run(store, word, require_x=True, typed=state.argv)
    run_id = core.resolve(store, word)
    given = [
        f"--{name.replace('_', '-')}" for name in _DIFF_ONLY_FLAGS if getattr(ns, name) is not None
    ]
    if given:
        raise _Refusal(
            f"{', '.join(given)}: diff-only flag{'s' if len(given) > 1 else ''}; "
            f"a single-run report compares nothing ({_REPORT_FORMS})"
        )
    named = core.runs(store, counted=False)
    name = next((run.run_name for run in named if run.run_id == run_id), run_id)
    out_dir = _prepare_out_dir(
        ns, f"./prove-report-{_slug(name)}", _named_words(state.argv, named)
    )
    # The word as typed, so the note on what latest, previous and the numbers leave out is said.
    detail = core.run(store, word, events=ns.event, horizon=ns.horizon, fix=ns.fix)
    _notes_of(io, detail)
    events = detail.events
    spec = ReportSpec(
        title=ns.title if ns.title else f"{detail.run_name}: {', '.join(events)}",
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=dict(detail.fixed),
        theme=ns.theme,
        top_n=ns.top_n,
        forest=ns.forest,
    )
    kwargs: dict[str, Any] = dict(
        events=events, horizon=detail.horizon, manifest=detail.manifest,
        observations=detail.observations,
        declarations=detail.declarations, shares=detail.shares, design_mde=detail.design,
    )
    with _look.rule10():
        report = build_survival_report(detail.cells, spec, **kwargs)
        receipt = report if spec.theme == "light" else build_survival_report(
            detail.cells, dataclasses.replace(spec, theme="light"), **kwargs
        )
    written = _write_report_files(io, out_dir, report, receipt)
    if ns.json:
        doc = detail.to_json()
        payload = {"out": str(out_dir), "wrote": [str(p) for p in written]}
        for key in (
            "run_id", "run_name", "events", "non_event", "horizon", "by_event", "design_mde",
        ):
            payload[key] = doc[key]
        _write_json(io, "report", "ok", _wrote_sentence(out_dir, written), payload, [])
        return 0
    _wrote(io, out_dir, written)
    io.line()
    if detail.inferred:
        io.line(
            f"inferred: no event was given, so the event set is {', '.join(events)}; "
            f"the non-event is {detail.non_event}, the most frequent outcome"
        )
    io.line(
        f'"{detail.run_name}": survival report over {", ".join(events)} at horizon '
        f"{_look.fmt_num(report.provenance['horizon'])}"
    )
    return 0


def _cmd_paired(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    """The paired-replay files; ``--json`` prints the combined payload and writes nothing;
    ``--cap-check`` says whether the recorded input tokens are under the declared cap, writes
    nothing, and exits 4 at or above it."""
    ns.typed = list(state.argv)
    result = core.paired(store, ns.declaration, cap_check=ns.cap_check)
    if ns.cap_check:
        code = 4 if result.cap_reached else 0
        if ns.json:
            _print_result(io, "paired", result)
            return code
        io.line(f"{result.verdict}  {result.sentence}")
        for label, value in result.details:
            io.detail(label, value)
        return code
    if ns.json:
        _print_result(io, "paired", result)
        return 0
    out_dir = _prepare_out_dir(ns, result.default_out)
    written: list[Path] = []
    with _staged(out_dir) as staging:
        for name, text in result.artifacts.items():
            (staging / name).write_text(text, encoding="utf-8")
            written.append(out_dir / name)
    _wrote(io, out_dir, written)
    io.detail(
        "not recorded",
        "the harness's digest and the client's version (the runs did not record them)",
    )
    return 0


def _cmd_check(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    a, b = _two_runs("check", ns.runs)
    result = core.check(
        store, a, b, events=ns.event, fail_on=ns.fail_on, method=ns.method, q=ns.q,
        typed=state.argv,
    )
    _notes_of(io, result)
    code = 0 if result.passed else 4
    saved = _save(io, store, result) if ns.save else None
    if ns.json:
        doc = _with_saved(result.to_json(), saved)
        _write_json(io, "check", doc["verdict"], doc["sentence"], doc, doc["next"])
        return code
    _verdict_block(io, result, saved)
    _write_summary(io, result.multi)
    return code


def _cmd_serve(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    """``report`` up to the report, then a structure instead of three files. The structure is
    complete before anything binds; ``--json`` returns having bound nothing at all."""
    words: list[str] = list(ns.runs)
    if len(words) not in (0, 2):
        raise _Usage(
            f"serve takes two runs or none, got {len(words)}: {_SERVE_FORM}",
            [f"{_COMMAND} serve --help"],
        )
    a, b = _two_runs("serve", words)
    if ns.x is None or ns.event is None:
        core.compare(
            store, a, b, verb="serve", require_x=ns.x is None,
            require_events=ns.event is None, typed=state.argv,
        )
    result = core.compare(
        store, a, b, events=ns.event, method=ns.method, q=ns.q, by=ns.by,
        permutations=ns.permutations,
        seed=ns.seed, max_group_mde=ns.max_group_mde, depth=ns.depth, verb="serve", for_report=True,
        fix=ns.fix,
    )
    _notes_of(io, result)
    spec = ReportSpec(
        title=ns.title if ns.title else result.title,
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=dict(result.fixed),
        theme=ns.theme,
        top_n=ns.top_n,
        forest=ns.forest,
    )
    report = build_multi_report(
        result.multi, spec, manifests=result.manifests, observations=result.observations,
        declarations=result.declarations,
    )
    _name_provenance(report.provenance, result)
    nested = result.tree
    structure = build_structure(
        report,
        result.multi,
        tree=nested,
        manifest_a=result.manifests[0],
        manifest_b=result.manifests[1],
        rows_a=result.rows_counts[0],
        rows_b=result.rows_counts[1],
        tally_a=result.tallies[0],
        tally_b=result.tallies[1],
        store_root=str(store.shown),
    )
    structure = {"method": result.method, "method_chosen": result.method_chosen, **structure}
    a_name = result.names.get(result.run_a, result.run_a)
    b_name = result.names.get(result.run_b, result.run_b)
    # The comparison the page shows is saved before anything binds; the page structure keeps
    # its keys, so the save shows in the store and, once bound, on the line after the address.
    saved = _save(io, store, result)
    state.saved = saved is not None
    if ns.json:
        sentence = f'the page comparing "{a_name}" with "{b_name}", bound nowhere'
        structure = _add_names(structure, result.names)
        _write_json(io, "serve", "ok", sentence, structure, None)
        return 0
    page = _method_html(render_html(structure), _method_of(result), summary=True)

    def announce(srv: Any) -> None:
        io.line(
            f'ok  serving "{a_name}" against "{b_name}" at '
            f"http://{_HOST}:{srv.server_address[1]}/ (Ctrl-C stops)"
        )
        if saved is not None:
            io.detail("saved", f"{saved.kind} {_look.fmt_hash(saved.id)}")
        io.out.flush()

    serve_page(page, on_bind=announce)
    return 0


# ---------- inspect / runs ----------


def _cmd_inspect(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    result = core.inspect(
        store, ns.run, event=ns.event, where=ns.where, limit=ns.limit, typed=state.argv,
    )
    _notes_of(io, result)
    if ns.json:
        _print_result(io, "inspect", result)
        return 0
    io.line(f"ok  {result.sentence}")
    if not result.rows:
        return 0
    for line in result.provenance:
        io.line(line)
    io.line()
    for row in result.rows:
        io.line(f"config_hash: {_look.fmt_hash(row['config_hash'])}")
        io.line(f"config: {json.dumps(row['config'], sort_keys=True)}")
        io.line(f"seed: {row['seed']}")
        io.line(f"replicate_index: {_look.fmt_count(row['replicate_index'])}")
        if isinstance(row["error"], str):
            io.line("outcome: -")
            io.line("t: -")
            io.line(f"error: {row['error']}")
        else:
            io.line(f"t: {_look.fmt_num(row['t'])}")
        trace = row["trace"]
        if trace is not None:
            if trace.truncated is not None:
                io.line(f"trace: truncated ({trace.truncated})")
            cut = [
                (j, span) for j, span in enumerate(trace.ordered())
                if span.truncated == "observation"
            ]
            if cut:
                limits = result.observation_cap
                limit = "not recorded" if limits is None else ", ".join(
                    f"{name}={value}" for name, value in limits.items()
                )
                sizes = [
                    f"span {j}" if span.bytes_original is None
                    else f"span {j}: {span.bytes_original} bytes originally"
                    for j, span in cut
                ]
                io.line(f"observation: cut ({'; '.join([f'limit {limit}', *sizes])})")
            for j, span in enumerate(trace.ordered()):
                duration = span.duration_ms
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
    reproduce = result.reproduce
    io.line(_SNIPPET_MARKER)
    io.line(f"from {reproduce['module']} import {reproduce['function']}")
    config = json.dumps(reproduce["config"], sort_keys=True)
    io.line(f"{reproduce['function']}({config}, seed={reproduce['seed']})")
    return 0


def _cmd_runs(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    listed = core.runs(store)
    if ns.json:
        _print_result(io, "runs", listed)
        return 0
    io.line(f"ok  {listed.sentence}")
    if listed.unreadable:
        io.err_line(
            f"note: {_look.fmt_count(len(listed.unreadable))} of this store's runs could not be "
            f"read and are not listed; each has a manifest.json that is damaged or carries no "
            f"start time: {', '.join(listed.unreadable)}"
        )
    if not listed:
        for command in listed.next:
            io.next(command)
        return 0
    header = (
        "#", "name", "id", "status", "backend", "target", "rows", "rows without an outcome",
        "created",
    )
    lines: list[tuple[str, ...]] = [header]
    for run in listed:
        entry = run.entry
        lines.append((
            "" if entry["number"] is None else str(entry["number"]), str(entry["run_name"]),
            str(entry["run_id"]), str(entry["status"]), str(entry["backend"]),
            str(entry["target_id"]), _look.fmt_count(entry["rows"]),
            _look.fmt_count(entry["no_outcome"]), run.created,
        ))
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    io.line()
    for line in lines:
        cells = (cell.ljust(w) for cell, w in zip(line, widths, strict=True))
        io.line("  ".join(cells).rstrip())
    return 0


def _cmd_ui(ns: argparse.Namespace, io: _IO, store: Any, state: _State) -> int:
    """Build the dashboard and say where it is; ``--open`` opens it in the browser, once."""
    import webbrowser

    built = core.build_ui(store)
    _notes_of(io, built)
    if ns.json:
        _print_result(io, "ui", built)
    else:
        io.line(f"ok  dashboard at {built.location}")
    if ns.open:
        io.out.flush()
        webbrowser.open(built.location)
    return 0


_VERBS: dict[str, Callable[[argparse.Namespace, _IO, Any, _State], int]] = {
    "ui": _cmd_ui,
    "init": _cmd_init,
    "sweep": _cmd_sweep,
    "diff": _cmd_diff,
    "report": _cmd_report,
    "check": _cmd_check,
    "serve": _cmd_serve,
    "inspect": _cmd_inspect,
    "runs": _cmd_runs,
    "paired": _cmd_paired,
}
