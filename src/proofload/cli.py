"""M10: the command line.

Six verbs over the built modules: ``sweep`` runs a plan on a backend after a pre-flight
prompt; ``diff``, ``report`` and ``check`` operate on stored runs; ``inspect`` dumps the
``(config, seed)`` pairs behind an event plus a reproduction snippet; ``runs`` lists the store.
This module computes nothing and decides nothing statistical: it parses arguments, calls
M2–M7, and renders their results. Every number it prints is a field on a ``RunSummary``,
``DiffResult``, ``Report``, ``RunManifest`` or a store frame.

``main`` owns the streams. Every write goes through the streams it was given (``sys.*`` by
default), which is what makes the whole CLI testable in-process. Exceptions map to exit codes
in exactly one place, ``_dispatch``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import tomllib
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TextIO

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

from proofload import __version__
from proofload._resolve import resolve
from proofload.diff import DiffError, DiffResult, diff
from proofload.executor import ExecutorError, Plan, RunSummary, plan, preflight, run_local
from proofload.executor_modal import (
    ImageSpec,
    ModalOptions,
    ModalTarget,
    preflight_modal,
    run_modal,
)
from proofload.report import Report, ReportError, ReportSpec, _fmt, build_report
from proofload.sampler import SamplerError, SweepSpec
from proofload.store import RunManifest, Store, StoreError
from proofload.survival import censor

__all__ = ["main"]

_ENV_STORE = "PROOFLOAD_STORE"
_DEFAULT_STORE = "./proofload-runs"
_DEFAULT_BATCH_SIZE = 64
_METHODS: tuple[str, ...] = ("fisher_bh", "mcnemar_bh", "logrank_bh")
_REPORT_FILES = ("report.md", "heatmap.svg", "receipt.html")
_TRACE_SCHEMA = "proofload.trace/1"
_SNIPPET_MARKER = "# reproduce one episode"
_MODAL_ONLY_FLAGS = ("concurrency", "infra_retries", "max_cost", "est_seconds", "app_name")
_REFUSABLE = (SamplerError, ExecutorError, DiffError, ReportError, StoreError)


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
        prog="proofload",
        description="A statistical instrument for finding where autonomous and agentic "
        "systems break.",
    )
    parser.add_argument("--version", action="version", version=f"proofload {__version__}")
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
    sweep.add_argument("--backend", choices=("local", "modal"), default="local")
    identity = sweep.add_mutually_exclusive_group()
    identity.add_argument("--salt", metavar="HEX", help="run salt for seed derivation")
    identity.add_argument("--pair-with", metavar="RUN_ID", help="inherit that run's salt")
    identity.add_argument("--resume", metavar="RUN_ID", help="continue a partial run")
    sweep.add_argument("--episode-timeout", type=float, metavar="S", help="per-episode timeout")
    sweep.add_argument("--max-rollouts", type=int, metavar="N", help="stop after N rollouts")
    sweep.add_argument("--batch-size", type=int, metavar="N", help="rows per store part")
    sweep.add_argument("--yes", action="store_true", help="skip the pre-flight prompt")
    modal = sweep.add_argument_group("modal only (override the [modal] table)")
    modal.add_argument("--concurrency", type=int, metavar="N", help="max containers")
    modal.add_argument("--infra-retries", type=int, metavar="N", help="retries per batch")
    modal.add_argument("--max-cost", type=float, metavar="USD", help="refuse above this estimate")
    modal.add_argument("--est-seconds", type=float, metavar="S", help="seconds per episode")
    modal.add_argument("--app-name", metavar="NAME", help="Modal app name")
    modal.add_argument(
        "--image", default="image", metavar="SECTION", help="[modal.SECTION] image table"
    )

    diff_p = sub.add_parser("diff", help="compare two stored runs cell by cell")
    _add_pair_arguments(diff_p)
    diff_p.add_argument("--methods", choices=("all",), help="also run the other two methods")
    diff_p.add_argument("--format", choices=("md", "json"), default="md")

    report_p = sub.add_parser(
        "report", help="render a diff as report.md, heatmap.svg, receipt.html"
    )
    _add_pair_arguments(report_p)
    report_p.add_argument("--x", required=True, metavar="AXIS", help="config key on the x axis")
    report_p.add_argument("--y", metavar="AXIS", help="config key on the y axis")
    report_p.add_argument(
        "--fix", action="append", default=[], metavar="KEY=VALUE", help="pin a config key"
    )
    report_p.add_argument("--methods", choices=("all",), help="add the method comparison table")
    report_p.add_argument("--theme", choices=("dark", "light"), default="dark")
    report_p.add_argument("--top-n", type=int, default=10, metavar="N", help="worst cells listed")
    report_p.add_argument("--out", metavar="DIR", help="default ./proofload-report-<A>-<B>")
    report_p.add_argument("--title", metavar="TEXT")
    report_p.add_argument("--force", action="store_true", help="write into a non-empty --out")

    check_p = sub.add_parser("check", help="gate on a diff: exit 0 on PASS, 1 on FAIL")
    _add_pair_arguments(check_p)
    check_p.add_argument("--fail-on", choices=("worse", "any"), default="worse")

    inspect_p = sub.add_parser("inspect", help="dump the (config, seed) pairs behind an event")
    inspect_p.add_argument("run", metavar="RUN")
    inspect_p.add_argument("--event", required=True, metavar="NAME")
    inspect_p.add_argument(
        "--where", action="append", default=[], metavar="KEY=VALUE", help="filter on config"
    )
    inspect_p.add_argument("--limit", type=int, metavar="N")

    sub.add_parser("runs", help="list the runs in the store")

    for p in (parser, *sub.choices.values()):
        if isinstance(p, _Parser):
            p.io = io
    return parser


def _add_pair_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("a", metavar="A", help="run id of the baseline")
    p.add_argument("b", metavar="B", help="run id of the candidate")
    p.add_argument(
        "--event", required=True, metavar="NAME", help="outcome that counts as the event"
    )
    p.add_argument("--method", choices=_METHODS, default="fisher_bh")
    p.add_argument("--q", type=float, default=0.05, help="BH false discovery rate")


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
        return _VERBS[ns.verb](ns, io, root, state)
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


def _load_pair(
    store: Store, a: str, b: str, event: str
) -> tuple[Any, Any, RunManifest, RunManifest]:
    ma, mb = store.manifest(a), store.manifest(b)
    fa, fb = censor(store.read(a), event), censor(store.read(b), event)
    return fa, fb, ma, mb


def _run_diffs(
    store: Store, ns: argparse.Namespace, *, all_methods: bool
) -> tuple[DiffResult, dict[str, DiffResult], tuple[RunManifest, RunManifest]]:
    """The primary diff first (so a refusal fires before extra work), then the other two."""
    fa, fb, ma, mb = _load_pair(store, ns.a, ns.b, ns.event)

    def one(method: Any) -> DiffResult:
        return diff(fa, fb, event=ns.event, method=method, q=ns.q, manifest_a=ma, manifest_b=mb)

    primary = one(ns.method)
    others: dict[str, DiffResult] = {}
    if all_methods:
        for method in _METHODS:
            if method != ns.method:
                others[method] = one(method)
    return primary, others, (ma, mb)


def _headline(d: DiffResult) -> str:
    """M7's headline template, rendered from the DiffResult alone."""
    pairing = "paired" if d.paired else "unpaired"
    return (
        f"{d.n_safer} of {len(d.cells)} cells safer, {d.n_worse} worse "
        f"({d.method}, BH q<{_fmt(d.q, 'sig3')}, {pairing})."
    )


def _method_table(results: Sequence[DiffResult]) -> str:
    header = ("method", "paired", "safer", "worse", "unchanged", "max_mde")
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for d in results:
        lines.append(
            f"| {d.method} | {d.paired} | {d.n_safer} | {d.n_worse} | {d.n_unchanged} "
            f"| {d.max_mde:.4f} |"
        )
    return "\n".join(lines) + "\n"


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

    def finish(self) -> None:
        if self.dirty:
            self.out.write("\n")


# ---------- sweep ----------


def _resolve_target(target: str) -> Any:
    try:
        return resolve(target)
    except (ValueError, ImportError, AttributeError) as exc:
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
    except TypeError as exc:
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


def _cmd_sweep(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    if ns.backend != "modal":
        stray = [name for name in _MODAL_ONLY_FLAGS if getattr(ns, name) is not None]
        if stray or ns.image != "image":
            names = ", ".join("--" + n.replace("_", "-") for n in stray) or "--image"
            raise _Refusal(f"{names} only applies to --backend modal")
    spec_path = Path(ns.spec)
    spec = SweepSpec.load(spec_path)
    rollout = _resolve_target(ns.target)
    store = Store(root)
    p: Plan = plan(
        spec,
        store,
        backend=ns.backend,
        run_salt=ns.salt,
        pair_with=ns.pair_with,
        resume=ns.resume,
    )

    if ns.backend == "modal":
        target, options = _modal_config(ns, spec_path)
        io.out.write(preflight_modal(p, target, options))
    else:
        io.out.write(preflight(p))
    _confirm(ns, io)

    state.run_id = p.run_id
    progress = _Progress(io.out)
    summary: RunSummary
    if ns.backend == "modal":
        summary = run_modal(p, target, store, options=options, on_progress=progress)
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
    primary, others, _ = _run_diffs(Store(root), ns, all_methods=ns.methods == "all")
    if ns.format == "json":
        payload: Any = primary.to_json()
        if others:
            payload = {primary.method: payload, **{m: d.to_json() for m, d in others.items()}}
        io.out.write(json.dumps(payload, indent=2) + "\n")
        return 0
    io.out.write(primary.to_markdown())
    if others:
        io.out.write("\n" + _method_table([primary, *others.values()]))
    return 0


def _cmd_report(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    out_dir = Path(ns.out) if ns.out else Path(f"./proofload-report-{ns.a}-{ns.b}")
    if out_dir.exists():
        if not out_dir.is_dir():
            raise _Refusal(f"--out {out_dir} exists and is not a directory")
        if any(out_dir.iterdir()) and not ns.force:
            raise _Refusal(f"--out {out_dir} exists and is not empty; pass --force to overwrite")
    fixed = _parse_pairs(ns.fix, "--fix")

    primary, others, manifests = _run_diffs(Store(root), ns, all_methods=ns.methods == "all")
    spec = ReportSpec(
        title=ns.title if ns.title else f"{ns.a} vs {ns.b}: {ns.event}",
        x_axis=ns.x,
        y_axis=ns.y,
        fixed=fixed,
        comparison=others,
        theme=ns.theme,
        top_n=ns.top_n,
    )
    report: Report = build_report(primary, spec, curves=None, manifests=manifests)
    receipt = (
        report
        if spec.theme == "light"
        else build_report(
            primary, dataclasses.replace(spec, theme="light"), curves=None, manifests=manifests
        )
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(report.to_markdown())
    (out_dir / "heatmap.svg").write_text(report.to_svg())
    (out_dir / "receipt.html").write_text(receipt.to_html())
    io.out.write(report.headline + "\n")
    for name in _REPORT_FILES:
        io.out.write(f"{out_dir / name}\n")
    return 0


def _cmd_check(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    primary, _, _ = _run_diffs(Store(root), ns, all_methods=False)
    passed = primary.check(fail_on=ns.fail_on)
    io.out.write(_headline(primary) + "\n")
    io.out.write("PASS\n" if passed else "FAIL\n")
    return 0 if passed else 1


# ---------- inspect / runs ----------


def _trace_steps(meta: Any) -> list[Any] | None:
    if not isinstance(meta, Mapping):
        return None
    trace = meta.get("trace")
    if not isinstance(trace, Mapping) or trace.get("schema") != _TRACE_SCHEMA:
        return None
    steps = trace.get("steps")
    return list(steps) if isinstance(steps, list) else None


def _cmd_inspect(ns: argparse.Namespace, io: _IO, root: Path, state: _State) -> int:
    store = Store(root)
    manifest = store.manifest(ns.run)
    df = store.read(ns.run)
    where = _parse_pairs(ns.where, "--where")
    rows = df[df["outcome"] == ns.event]
    for key, value in where.items():
        rows = rows[[isinstance(cfg, Mapping) and cfg.get(key) == value for cfg in rows["config"]]]
    rows = rows.sort_values(["config_hash", "replicate_index"], kind="stable")
    if ns.limit is not None:
        rows = rows.head(max(ns.limit, 0))
    if rows.empty:
        io.out.write(f"no rows with outcome {ns.event!r} in run {ns.run}\n")
        return 0

    for row in rows.itertuples(index=False):
        io.out.write(f"config_hash: {row.config_hash}\n")
        io.out.write(f"config: {json.dumps(row.config, sort_keys=True)}\n")
        io.out.write(f"seed: {row.seed}\n")
        io.out.write(f"replicate_index: {row.replicate_index}\n")
        io.out.write(f"t: {row.t}\n")
        steps = _trace_steps(row.meta)
        if steps:
            for i, step in enumerate(steps):
                get = step.get if isinstance(step, Mapping) else (lambda _k, _d=None: _d)
                error = get("error")
                io.out.write(
                    f"  {i} {get('kind', '-')} {get('name', '-')} {get('latency_ms', '-')} "
                    f"{'-' if error in (None, '') else error}\n"
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
    header = ("run_id", "status", "backend", "target_id", "t_unit", "rows")
    lines = [header]
    for run_id in store.runs():
        m = store.manifest(run_id)
        rows = str(len(store.read(run_id)))
        lines.append((run_id, m.status, m.backend, m.target_id, m.t_unit, rows))
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    for line in lines:
        cells = (cell.ljust(w) for cell, w in zip(line, widths, strict=True))
        io.out.write("  ".join(cells).rstrip() + "\n")
    return 0


_VERBS: dict[str, Callable[[argparse.Namespace, _IO, Path, _State], int]] = {
    "sweep": _cmd_sweep,
    "diff": _cmd_diff,
    "report": _cmd_report,
    "check": _cmd_check,
    "inspect": _cmd_inspect,
    "runs": _cmd_runs,
}
