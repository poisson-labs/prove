"""The core's operations: everything a verb computes, reads and writes, with nothing printed,
asked, exited or opened. A face parses its input, calls these, and renders what comes back."""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import importlib
import importlib.util
import inspect as _pyinspect
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import warnings
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Protocol, cast

import pandas as pd

from poisson_prove import _facts, _look, stats
from poisson_prove import executor_modal as _modal
from poisson_prove._compat import (
    RETIRED_STORE_VARIABLE,
    old_writer_line,
    retired_default_store,
    retired_default_store_refusal,
    retired_store_variable_note,
    version_as_recorded,
)
from poisson_prove._names import Index, NamesError, started, unfit
from poisson_prove._names import index as names_index
from poisson_prove._resolve import resolve as _resolve_import
from poisson_prove._resolve import split_import_path
from poisson_prove.capture import _ENTRY_POINT_GROUP as INSTRUMENTOR_GROUP
from poisson_prove.chaos import fault_names
from poisson_prove.core import _artifacts
from poisson_prove.core._results import (
    CheckResult,
    Comparison,
    EpisodePage,
    Event,
    Fold,
    InspectResult,
    Interrupted,
    LazyPayload,
    PairedResult,
    Plan,
    Refusal,
    Result,
    RunDetail,
    RunInfo,
    RunList,
    RunResult,
    Spec,
    Stopped,
    WrittenFiles,
)
from poisson_prove.diff import (
    KINDS,
    DiffError,
    EventInferenceError,
    MixedCases,
    MultiDiffResult,
    UnknownEvent,
    declared_events,
    infer_events,
    multi_diff,
)
from poisson_prove.executor import (
    DEFAULT_MAX_MDE,
    ExecutorError,
    RunSummary,
    UnderpoweredDesign,
    _plan_design,
    _recorded_design,
    check_power,
    preflight,
    run_local,
)
from poisson_prove.executor import plan as _executor_plan
from poisson_prove.executor_burla import BurlaOptions, preflight_burla, run_burla
from poisson_prove.paired import Declaration, PairedError, _artifact_text, _bundle, _cost_block
from poisson_prove.paired import cost as paired_cost
from poisson_prove.report import ReportError, _observation_cap, _provenance_lines
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
    TreeResult,
    tree,
)
from poisson_prove.viewer import ViewerError

COMMAND = "poisson-prove"
ENV_STORE = "POISSON_PROVE_STORE"
DEFAULT_STORE = "./prove-runs"
DEFAULT_SPEC = "prove.toml"
DEFAULT_Q = 0.05
DEFAULT_BATCH_SIZE = 64
METHODS: tuple[str, ...] = ("fisher_bh", "mcnemar_bh", "logrank_bh")
METHOD_WORDS = {
    "mcnemar_bh": ("paired test on shared seeds", "McNemar"),
    "fisher_bh": ("two separate samples", "Fisher"),
    "logrank_bh": ("time to the event", "log-rank"),
}
MOCK_ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
MOCK_PATCHED = "poisson_prove.examples.mock_agent:rollout_patched"
SWEEP_NEXT = "sweep SPEC.toml --target pkg.module:rollout"
LATEST_PARTIAL = "\0latest-partial"
EXTRA_HINTS = {
    "modal": 'pip install "poisson-prove[modal]"',
    "burla": 'pip install "poisson-prove[burla]"',
    "agent": 'pip install "poisson-prove[agent]"',
}
NEVER_INFERS = {
    "check": "a gate whose meaning changes when a new outcome appears is not a gate",
    "serve": (
        "a picture whose meaning changes when a new outcome appears is worse than a table "
        "with the same defect"
    ),
}
THRESHOLD_SOURCES = {
    "recorded": "recorded at sweep time by the runs",
    "smaller": "the smaller of the two the runs recorded at sweep time",
    "default": "the default; neither run recorded one",
}
MODAL_ONLY_FLAGS = ("concurrency", "infra_retries", "max_cost", "est_seconds", "app_name")
BURLA_REFUSED_FLAGS = ("concurrency", "app_name")
_REFUSABLE = (
    SamplerError,
    ExecutorError,
    DiffError,
    ReportError,
    StoreError,
    SurvivalError,
    ViewerError,
    PairedError,
)
_PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- the boundary: notes, refusals ----------


def _final(message: str) -> str:
    return _look.reprint(_look.one_line(_look.plain_words(message)))


def refusal(message: str, nexts: Sequence[str] = (), **kw: Any) -> Refusal:
    return Refusal(_final(message), nexts, **kw)


@contextmanager
def _collected(notes: list[str]) -> Iterator[None]:
    """Every warning Prove raises becomes a note; a library's warning is dropped."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            yield
        finally:
            for w in caught:
                module = getattr(w.category, "__module__", "") or ""
                here = os.path.abspath(w.filename).startswith(_PACKAGE) if w.filename else False
                if module.startswith("poisson_prove") or here:
                    notes.append(_final(str(w.message)))


class _Operation(Protocol):
    """An operation as a face calls it; ``__wrapped__`` is its own function, which another
    operation calls with its notes."""

    __wrapped__: Callable[..., Any]

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def _operation(fn: Callable[..., Any]) -> _Operation:
    """An operation: Prove's warnings become the result's notes, a library's refusal a
    ``Refusal``, and nothing is printed."""

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        notes: list[str] = []
        try:
            with _collected(notes):
                result = fn(*args, _notes=notes, **kwargs)
        except Refusal as exc:
            exc.notes = [*notes, *exc.notes]
            raise
        except NamesError as exc:
            raise refusal(str(exc), exc.nexts, notes=notes) from exc
        except _REFUSABLE as exc:
            raise refusal(str(exc), getattr(exc, "nexts", ()), notes=notes) from exc
        if isinstance(result, Result) and notes:
            result = dataclasses.replace(result, notes=(*result.notes, *notes))
        return result

    wrapped.__name__ = fn.__name__
    wrapped.__qualname__ = fn.__qualname__
    wrapped.__doc__ = fn.__doc__
    operation = cast("_Operation", wrapped)
    operation.__wrapped__ = fn
    return operation


# ---------- the store ----------


class OpenedStore(Store):
    """A store as an operation was given it: its root, how it is shown, and its notes."""

    def __init__(self, root: Path | str, shown: str | None = None) -> None:
        super().__init__(root)
        self.root = Path(root)
        self.shown = str(root) if shown is None else shown
        self.notes: list[str] = []


def _opened(store: Any) -> OpenedStore:
    if isinstance(store, OpenedStore):
        return store
    if isinstance(store, Store):
        return OpenedStore(store._root)  # noqa: SLF001
    return OpenedStore(Path(store))


def _store_source(given: bool) -> str:
    if given:
        return "it came from --store"
    if os.environ.get(ENV_STORE):
        return f"it came from ${ENV_STORE}"
    return f"it is the default, since neither --store nor ${ENV_STORE} is set"


def _first_sweep(root: Path) -> str:
    return f"{COMMAND} --store {shlex.quote(str(root))} {SWEEP_NEXT}"


def open_store(path: Path | str | None = None, *, verb: str | None = None) -> OpenedStore:
    """The store at ``path``; with none, ``$POISSON_PROVE_STORE`` when it is set, else
    ``./prove-runs``. With ``verb``, a store that verb cannot use is refused: a missing one, an
    empty one for a reading verb, a store the earlier name left beside a missing default."""
    given = path is not None and str(path) != ""
    env = os.environ.get(ENV_STORE)
    root = Path(path) if given else Path(env) if env else Path(DEFAULT_STORE)  # type: ignore[arg-type]
    store = OpenedStore(root)
    # The retired variable is read only to say it is no longer read.
    seen = {
        name: value
        for name, value in (
            (RETIRED_STORE_VARIABLE, os.environ.get(RETIRED_STORE_VARIABLE)),
            (ENV_STORE, env),
        )
        if value is not None
    }
    note = retired_store_variable_note(seen, ENV_STORE)
    if note is not None:
        store.notes.append(note)
    if verb != "init" and root.is_dir():
        # A store written by a newer format than this Prove reads is refused by every verb
        # before anything is planned or written.
        try:
            _artifacts.check_store(root)
        except _artifacts.NewerFormat as exc:
            raise refusal(str(exc), [_artifacts.UPGRADE]) from exc
        except _artifacts.BadDescriptor as exc:
            raise refusal(str(exc)) from exc
    if verb is None:
        return store
    if not given and not env:
        old = retired_default_store(root)
        if old is not None:
            error, nexts = retired_default_store_refusal(root, old, COMMAND, verb)
            raise refusal(error, nexts)
    if verb in ("sweep", "init"):
        return store
    elsewhere = f"{COMMAND} --store PATH {verb}"
    if not root.is_dir():
        raise refusal(
            f"no store at {root}. No directory exists at that path; {_store_source(given)}.",
            [_first_sweep(root), elsewhere],
        )
    if verb not in ("runs", "ui") and not Store(root).runs():
        raise refusal(
            f"no runs in {root}. No directory under it holds a manifest.json; "
            f"{_store_source(given)}.",
            [_first_sweep(root), elsewhere],
        )
    return store


def _index(store: OpenedStore) -> Index:
    try:
        return names_index(Store(store.root), store.root, store.shown)
    except NamesError as exc:
        raise refusal(str(exc), exc.nexts) from exc


def _run_of(idx: Index, word: str, notes: list[str]) -> str:
    counting = word.strip() in ("latest", "previous") or word.strip().startswith(
        ("latest:", "previous:", "#")
    )
    if idx.unreadable and counting:
        notes.append(
            "latest, previous and the numbers leave out the runs whose manifest.json could not "
            f"be read: {', '.join(idx.unreadable)}"
        )
    try:
        found = idx.find(word)
    except NamesError as exc:
        raise refusal(str(exc), exc.nexts) from exc
    if found.status == "unreadable":
        raise refusal(
            f"the run {found.run_id} cannot be read: its manifest.json is damaged or carries no "
            "start time",
            [idx.listing()],
        )
    return found.run_id


def _pair_of(
    idx: Index, verb: str, a: str | None, b: str | None, notes: list[str]
) -> tuple[str, str]:
    if a is None and b is None:
        return _run_of(idx, "previous", notes), _run_of(idx, "latest", notes)
    if a is None or b is None:
        raise refusal(
            f"{verb} takes two runs or none, got 1", [f"{COMMAND} {verb} --help"], usage=True
        )
    return _run_of(idx, a, notes), _run_of(idx, b, notes)


def join(words: Sequence[str]) -> str:
    return _look.command(*words)


def _named_argv(argv: Sequence[str], idx: Index) -> list[str]:
    return [idx.word_for(token) if idx.by_id(token) is not None else token for token in argv]


def _with_names(message: str, idx: Index) -> str:
    for run in idx.runs:
        if run.name == run.run_id or run.run_id not in message:
            continue
        shown = f'"{run.name}" ({run.run_id})'
        message = message.replace(f'"{run.run_id}"', shown).replace(f"'{run.run_id}'", shown)
        message = re.sub(rf"(?<![\w(\"-]){re.escape(run.run_id)}(?![\w-])", shown, message)
    return message


@_operation
def runs(store: Any, *, counted: bool = True, _notes: list[str]) -> RunList:
    """Every run in the store, newest first, named, numbered, with its counts. With
    ``counted=False`` no run's rows are read: each entry has its manifest's facts and no
    ``rows`` or ``no_outcome``, for a face that needs only the names."""
    store = _opened(store)
    st = Store(store.root)
    idx = _index(store)
    entries: list[RunInfo] = []
    for named in idx.runs:
        m = st.manifest(named.run_id)
        shown_at = started(m.created_at)
        entries.append(
            RunInfo(
                created=m.created_at
                if shown_at is None
                else shown_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                entry={
                    "number": named.number,
                    "run_id": named.run_id,
                    "run_name": named.name,
                    "status": m.status,
                    "backend": m.backend,
                    "target_id": m.target_id,
                    "t_unit": m.t_unit,
                    **(
                        {
                            "rows": st.count(named.run_id),
                            "no_outcome": st.tally(named.run_id).no_outcome,
                        }
                        if counted
                        else {}
                    ),
                    "created_at": m.created_at,
                    "poisson_prove_version": (
                        version_as_recorded(m.poisson_prove_version)
                        if m.written_by
                        else m.poisson_prove_version
                    ),
                },
            )
        )
    return RunList(entries, store=store.shown, unreadable=idx.unreadable)


@_operation
def resolve(store: Any, text: str, *, _notes: list[str]) -> str:
    """The id of the one run ``text`` names, in any of the forms a verb takes: ``latest``,
    ``previous``, ``latest:TARGET``, ``#N``, a name, an id."""
    return _run_of(_index(_opened(store)), text, _notes)


# ---------- comparisons ----------


def condition_text(config: Any) -> str:
    cfg = json.loads(config) if isinstance(config, str) else config
    if not isinstance(cfg, Mapping):
        return str(config)
    return " · ".join(
        f"{key} {_look.fmt_num(value) if isinstance(value, float) else value}"
        for key, value in cfg.items()
    )


def method_line(method: str, chosen: str) -> str:
    plain, own = METHOD_WORDS[method]
    if chosen == "named":
        how = "named with --method"
    elif method == "mcnemar_bh":
        how = "the default for runs paired at sweep time"
    else:
        how = "the default for runs not paired at sweep time"
    return f"{plain} ({own}), {how}"


def _with_method(sentence: str, method: str) -> str:
    return f"{sentence} ({METHOD_WORDS[method][0]})"


def _method_first(payload: Mapping[str, Any], method: str, chosen: str) -> dict[str, Any]:
    if "method" not in payload:
        return {"method": method, "method_chosen": chosen, **payload}
    out: dict[str, Any] = {}
    for key, value in payload.items():
        out[key] = value
        if key == "method":
            out["method_chosen"] = chosen
    return out


def _old_writer(manifests: tuple[RunManifest, RunManifest]) -> dict[str, str]:
    if sum(1 for m in manifests if m.written_by) != 1:
        return {}
    out = {}
    for role, m in zip(("before", "after"), manifests, strict=True):
        writer = old_writer_line(version_as_recorded(m.poisson_prove_version))
        if m.written_by and writer is not None:
            out[role] = writer
    return out


def _report_next(
    idx: Index, a: str, b: str, manifests: tuple[RunManifest, RunManifest], named: bool
) -> list[str]:
    axes = list(manifests[0].axis_types)[:2]
    if not axes:
        return []
    command = [COMMAND, "report", *([idx.word_for(a), idx.word_for(b)] if named else [])]
    command += ["--x", axes[0], *(["--y", axes[1]] if len(axes) > 1 else [])]
    return [join(command)]


def _parse_pairs(items: Sequence[str], flag: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise refusal(f'{flag} expects KEY=VALUE, got "{item}"')
        try:
            out[key] = tomllib.loads(f"v = {value.strip()}")["v"]
        except tomllib.TOMLDecodeError as exc:
            raise refusal(
                f'{flag} "{item}": the value must be a TOML scalar (100, 0.5, "text", true): {exc}'
            ) from exc
    return out


def _typed_fix(items: Sequence[str], manifests: Sequence[RunManifest]) -> dict[str, Any]:
    types: dict[str, str] = {}
    held: dict[str, list[Any]] = {}
    for m in manifests:
        for key, kind in m.axis_types.items():
            types.setdefault(key, kind)
        for config in (m.environment.get("sweep") or {}).get("configs", []):
            for key, value in config.items():
                if value not in held.setdefault(key, []):
                    held[key].append(value)
    out: dict[str, Any] = {}
    for item in items:
        key, sep, text = item.partition("=")
        key, text = key.strip(), text.strip()
        if not sep or key not in types or not held.get(key):
            out.update(_parse_pairs([item], "--fix"))
            continue
        values = held[key]
        if types[key] == "continuous":
            try:
                number: float | None = float(text.strip("\"'"))
            except ValueError:
                number = None
            found = [
                v
                for v in values
                if number is not None
                and isinstance(v, (int, float))
                and not isinstance(v, bool)
                and math.isclose(float(v), number, rel_tol=0.0, abs_tol=1e-12)
            ]
        else:
            bare = text
            if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
                bare = str(_parse_pairs([f"{key}={text}"], "--fix")[key])
            found = [v for v in values if str(v) == bare]
        if not found:
            shown = ", ".join(_look.fmt_num(v) if isinstance(v, float) else str(v) for v in values)
            given = text.strip("\"'")
            raise refusal(f"--fix {key}={given}: {given} is not on the axis; {key} holds {shown}")
        out[key] = found[0]
    return out


def _outcome_counts(*frames: Any) -> str:
    counter: Counter[str] = Counter()
    for frame in frames:
        counter.update(str(o) for o in frame["outcome"].dropna().tolist())
    ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{name}={_look.fmt_count(count)}" for name, count in ordered)


def _split_events(events: Sequence[str] | None) -> tuple[list[str] | None, dict[str, str]]:
    if events is None:
        return None, {}
    names: list[str] = []
    kinds: dict[str, str] = {}
    for typed in events:
        name, colon, kind = str(typed).rpartition(":")
        if colon and name and kind in KINDS:
            names.append(name)
            kinds[name] = kind
        else:
            names.append(str(typed))
    return names, kinds


def _multi(
    fa: Any,
    fb: Any,
    ma: RunManifest,
    mb: RunManifest,
    *,
    events: Sequence[str] | None,
    method: str | None,
    q: float,
    verb: str,
    kinds: Mapping[str, str] | None = None,
) -> MultiDiffResult:
    try:
        return multi_diff(
            fa,
            fb,
            events=events,
            method=cast("Any", method),
            q=q,
            power=stats.POWER,
            manifest_a=ma,
            manifest_b=mb,
            kinds=kinds,
        )
    except MixedCases as exc:
        raise refusal(
            str(exc),
            [
                "make each case its own sweep axis in the spec, an [axes.<name>] table whose "
                "values are the cases, then sweep again",
                "see docs/your-own-agent.md: one case per condition",
            ],
        ) from exc
    except EventInferenceError as exc:
        raise refusal(
            f"cannot infer the event set: {exc}; outcome counts: {_outcome_counts(fa, fb)}",
            [f"{COMMAND} {verb} A B --event NAME"],
        ) from exc


def _require_known_events(verb: str, events: Sequence[str] | None, *frames: pd.DataFrame) -> None:
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
    runs_: Sequence[str],
    argv: Sequence[str],
    idx: Index,
    *,
    x_missing: bool,
    event_missing: bool,
) -> Refusal:
    for run in runs_:
        store.manifest(run)
    frames = [store.read(run, meta=False) for run in runs_]
    axes = sorted({str(key) for frame in frames for config in frame["config"] for key in config})
    events = list(competing_set(*frames))
    if verb == "inspect" and "timeout" not in events and store.tally(runs_[0]).timed_out:
        events = sorted({*events, "timeout"})
    flags = " and ".join(
        flag
        for flag, missing in (("--x AXIS", x_missing), ("--event NAME", event_missing))
        if missing
    )
    given = "and neither was given" if x_missing and event_missing else "which was not given"
    reason = f"; {NEVER_INFERS[verb]}" if event_missing and verb in NEVER_INFERS else ""
    shown = [f'"{idx.name_of(r)}"' for r in runs_]
    who = f"{shown[0]} and {shown[1]} carry" if len(runs_) == 2 else f"{shown[0]} carries"
    carried = []
    if verb in ("report", "serve"):
        carried.append(f"axes: {', '.join(axes) or 'none stored'}")
    carried.append(f"events: {', '.join(events) or 'none stored'}")
    message = f"{verb} requires {flags}, {given}{reason}. {who} {'; '.join(carried)}."
    filled = [COMMAND, *_named_argv(argv, idx)]
    if x_missing and axes:
        filled.extend(["--x", axes[0]])
    if event_missing and events:
        filled.extend(["--event", _suggested_event(store, runs_, frames, events)])
    fillable = (not x_missing or axes) and (not event_missing or events)
    return refusal(message, [join(filled)] if fillable else [])


def _suggested_event(
    store: Store, runs_: Sequence[str], frames: Sequence[pd.DataFrame], events: Sequence[str]
) -> str:
    """The event a refusal's filled command names: the first failure, else success, the runs
    declare, else an outcome other than the most frequent (the outcome most runs end in is rarely
    the event), else the first carried."""
    declared = declared_events(*(store.manifest(run) for run in runs_))
    named = [e for e in declared if e in events]
    if named:
        return named[0]
    try:
        found, _ = infer_events(frames[0], frames[-1] if len(frames) > 1 else frames[0].iloc[0:0])
    except (EventInferenceError, DiffError):
        return events[0]
    return next((e for e in found if e in events), events[0])


def _read_record() -> Path:
    return Path.home() / ".cache" / "poisson-prove" / "compared.jsonl"


def _record_read(store: Store, *runs_: tuple[str, int]) -> None:
    at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    try:
        path = _read_record()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for run_id, episodes_ in runs_:
                entry = {
                    "run_id": run_id,
                    "created_at": store.manifest(run_id).created_at,
                    "episodes": int(episodes_),
                    "at": at,
                }
                fh.write(json.dumps(entry, allow_nan=False) + "\n")
    except OSError:
        pass


def _compared_before(manifest: RunManifest) -> bool:
    try:
        text = _read_record().read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if (entry.get("run_id"), entry.get("created_at")) == (manifest.run_id, manifest.created_at):
            return True
    return False


def _run_diffs(
    store: OpenedStore,
    idx: Index,
    a: str,
    b: str,
    *,
    verb: str,
    events: Sequence[str] | None,
    method: str | None,
    q: float,
    all_methods: bool,
) -> tuple[
    MultiDiffResult,
    dict[str, Any],
    tuple[RunManifest, RunManifest],
    tuple[pd.DataFrame, pd.DataFrame],
]:
    st = Store(store.root)
    ma, mb = st.manifest(a), st.manifest(b)
    fa, fb = st.read(a, meta=False), st.read(b, meta=False)
    names, kinds = _split_events(events)
    _require_known_events(verb, names, fa, fb)
    primary = _multi(fa, fb, ma, mb, events=names, method=method, q=q, verb=verb, kinds=kinds)
    if primary.n_tests == 0:
        raise refusal(
            f'no condition has an outcome in both "{a}" and "{b}" ({primary.dropped_a} only in '
            f"A, {primary.dropped_b} only in B); there is nothing to compare",
            [f"{COMMAND} runs"],
        )
    if primary.peeking:
        named = tuple(
            {**entry, "run_name": idx.name_of(str(entry["run_id"]))} for entry in primary.peeking
        )
        primary = dataclasses.replace(primary, peeking=named)
    _record_read(st, (a, len(fa)), (b, len(fb)))
    others: dict[str, Any] = {}
    if all_methods:
        for other in METHODS:
            if other != primary.method:
                others[other] = _multi(
                    fa, fb, ma, mb, events=primary.events, method=other, q=q, verb=verb, kinds=kinds
                )
    return primary, others, (ma, mb), (fa, fb)


def _tree_of(
    multi: MultiDiffResult,
    frames: tuple[pd.DataFrame, pd.DataFrame],
    manifests: tuple[RunManifest, RunManifest],
    *,
    by: str | None,
    permutations: int,
    seed: int,
    max_group_mde: float | None,
    depth: int,
) -> TreeResult:
    try:
        return tree(
            frames[0],
            frames[1],
            multi,
            manifest_a=manifests[0],
            manifest_b=manifests[1],
            by=by,
            n_permutations=permutations,
            seed=seed,
            max_group_mde=max_group_mde,
            depth=depth,
        )
    except DiffError as exc:
        text = str(exc)
        if "n_permutations" in text:
            raise refusal(text.replace("n_permutations", "--permutations")) from exc
        raise


def _moved(multi: MultiDiffResult, event: str, slot: str) -> str:
    if multi.by_event[event].kind == "success":
        slot = "rose" if slot == "fell" else "fell"
    return f"{event} {slot}"


def _detail(
    word: str,
    multi: MultiDiffResult,
    a: str,
    b: str,
    idx: Index,
    manifests: tuple[RunManifest, RunManifest],
    chosen: str,
) -> tuple[tuple[str, str], ...]:
    lines: list[tuple[str, str]] = [("method", method_line(multi.method, chosen))]
    compared = multi.comparison_verdict()
    if word in ("passed", "failed"):
        clause = _facts.limit_clause(multi) if compared == "no significant change" else None
        lines.append(("comparison", compared if clause is None else f"{compared}: {clause}"))
    if _facts.is_nothing_moved(compared):
        source = THRESHOLD_SOURCES[multi.threshold_source]
        lines.append(("threshold", f"{_look.fmt_rate(multi.threshold)} ({source})"))
    writers = _old_writer(manifests)
    for role, run_id in (("before", a), ("after", b)):
        shown = idx.name_of(run_id)
        lines.append((role, f"{shown}, {writers[role]}" if role in writers else shown))
    for record in multi.trades.to_dict(orient="records"):
        moved = [_moved(multi, event, "fell") for event in record.get("safer_events", ())]
        moved += [_moved(multi, event, "rose") for event in record.get("worse_events", ())]
        lines.append(("trade", f"{condition_text(record.get('config'))}: {', '.join(moved)}"))
    names = {run_id: idx.name_of(run_id) for run_id in (a, b)}
    lines.extend(_facts.lines(multi, names))
    return tuple(lines)


def _envelopes(store: Store, run: str) -> pd.DataFrame:
    return store.read(run, meta=False, trace="envelope")


def _declaration_check(store: Store, run: str) -> Any:
    return declaration_check(store.manifest(run), _envelopes(store, run))


def _observation_counts(store: Store, run: str) -> tuple[int, int]:
    frame = _envelopes(store, run)
    spans = [
        span
        for envelope in frame["trace"]
        if isinstance(envelope, Mapping)
        for span in envelope.get("spans", ())
        if isinstance(span, Mapping)
    ]
    return len(spans), sum(1 for span in spans if span.get("truncated") == "observation")


def _paired_declaration(path: str, a: str, b: str) -> Declaration:
    declaration = Declaration.from_toml(path)
    declared = {(sweep.a, sweep.b): sweep.name for sweep in declaration.sweeps}
    if (a, b) not in declared:
        pairs = ", ".join(f"{s.name}: ({s.a}, {s.b})" for s in declaration.sweeps)
        raise refusal(
            f"--paired: ({a}, {b}) is not the declared pair of any sweep in {path}; "
            f"the declaration pairs {pairs}"
        )
    return declaration


@_operation
def compare(
    store: Any,
    a: str | None = None,
    b: str | None = None,
    *,
    events: Sequence[str] | None = None,
    method: str | None = None,
    q: float = DEFAULT_Q,
    methods: str | None = None,
    by: str | None = None,
    permutations: int | None = DEFAULT_PERMUTATIONS,
    seed: int | None = DEFAULT_SEED,
    max_group_mde: float | None = None,
    depth: int | None = DEFAULT_DEPTH,
    with_tree: bool = True,
    verb: str = "diff",
    for_report: bool = False,
    fix: Sequence[str] = (),
    paired: str | None = None,
    require_events: bool = False,
    require_x: bool = False,
    typed: Sequence[str] = (),
    _notes: list[str],
) -> Comparison:
    """Two runs compared, ``previous`` and ``latest`` when neither is given: every condition
    the two share, each event, by the test named or the default for the pair, with every fact
    the verdict rests on."""
    store = _opened(store)
    idx = _index(store)
    run_a, run_b = _pair_of(idx, verb, a, b, _notes)
    st = Store(store.root)
    if require_events and verb == "serve":
        # A declared set does not change when a new outcome appears: serve shows it.
        require_events = not declared_events(st.manifest(run_a), st.manifest(run_b))
    if require_x or require_events:
        raise _missing_flags_refusal(
            st, verb, [run_a, run_b], typed, idx, x_missing=require_x, event_missing=require_events
        )
    fixed = _typed_fix(fix, (st.manifest(run_a), st.manifest(run_b))) if fix else {}
    declaration = None if paired is None else _paired_declaration(paired, run_a, run_b)
    multi, others, manifests, frames = _run_diffs(
        store,
        idx,
        run_a,
        run_b,
        verb=verb,
        events=events,
        method=method,
        q=q,
        all_methods=methods == "all",
    )

    @functools.cache
    def grown() -> TreeResult | None:
        # Grown when first read, so a face that refuses on its own flags first (serve's axes)
        # spends no permutations; a refusal from the tree is still a Refusal.
        if not with_tree or multi.n_tests == 0:
            return None
        try:
            return _tree_of(
                multi,
                frames,
                manifests,
                by=by,
                permutations=DEFAULT_PERMUTATIONS if permutations is None else permutations,
                seed=DEFAULT_SEED if seed is None else seed,
                max_group_mde=max_group_mde,
                depth=DEFAULT_DEPTH if depth is None else depth,
            )
        except _REFUSABLE as exc:
            raise refusal(str(exc), getattr(exc, "nexts", ())) from exc

    chosen = "default" if method is None else "named"
    word = multi.comparison_verdict()
    headline = _with_method(multi.headline().splitlines()[0], multi.method)
    sentence = _facts.verdict_sentence(word, headline, multi)
    nexts = _report_next(idx, run_a, run_b, manifests, a is not None) if verb == "diff" else []
    tree_settings = {
        "by": by,
        "depth": DEFAULT_DEPTH if depth is None else depth,
        "permutations": DEFAULT_PERMUTATIONS if permutations is None else permutations,
        "seed": DEFAULT_SEED if seed is None else seed,
        "max_group_mde": DEFAULT_MAX_GROUP_MDE if max_group_mde is None else max_group_mde,
    }

    def document() -> dict[str, Any]:
        payload: dict[str, Any] = _method_first(multi.to_json(), multi.method, chosen)
        if others:
            payload = {multi.method: payload, **{m: d.to_json() for m, d in others.items()}}
            payload["threshold"] = multi.threshold
            payload["threshold_source"] = multi.threshold_source
        nested = grown() if verb == "diff" else None
        if nested is not None:
            payload = {**payload, "omnibus": nested.root.to_json(), "tree": nested.to_json()}
        return payload

    extra: dict[str, Any] = {}
    if for_report:
        extra = {
            "observations": (_observation_counts(st, run_a), _observation_counts(st, run_b)),
            "declarations": (_declaration_check(st, run_a), _declaration_check(st, run_b)),
            "rows_counts": (st.count(run_a), st.count(run_b)),
            "tallies": (st.tally(run_a), st.tally(run_b)),
            "bundle": None if declaration is None else Fold(_bundle(st, declaration)),
        }
    return Comparison(
        verdict=word,
        sentence=sentence,
        payload=LazyPayload(document),
        next=tuple(nexts),
        detail=_detail(word, multi, run_a, run_b, idx, manifests, chosen),
        method_chosen=chosen,
        run_a=run_a,
        run_b=run_b,
        names={r.run_id: r.name for r in idx.runs},
        multi=multi,
        grow=grown,
        others=others,
        manifests=manifests,
        writers=_old_writer(manifests),
        fixed=fixed,
        title=f"{idx.name_of(run_a)} vs {idx.name_of(run_b)}: {', '.join(multi.events)}",
        tree_settings=tree_settings,
        report_next=tuple(_report_next(idx, run_a, run_b, manifests, True)),
        frames=frames,
        **extra,
    )


def _with_kind(argv: Sequence[str], event: str, kind: str) -> list[str]:
    words = list(argv)
    for i, word in enumerate(words):
        if word == event and i > 0 and words[i - 1] == "--event":
            words[i] = f"{event}:{kind}"
        elif word == f"--event={event}":
            words[i] = f"--event={event}:{kind}"
    return words


def set_option(typed: Sequence[str], option: str, value: str) -> list[str]:
    words = list(typed)
    for at, word in enumerate(words):
        if word == option and at + 1 < len(words):
            words[at + 1] = value
            return words
        if word.startswith(option + "="):
            words[at] = f"{option}={value}"
            return words
    return [*words, option, value]


def _check_sentence(multi: MultiDiffResult, fail_on: str) -> str:
    parts = []
    for event in multi.events:
        ev = multi.by_event[event]
        (up, n_up), (down, n_down) = ev.counts()
        parts.append(
            f"{event}: {_look.fmt_count(n_up)} {up}, {_look.fmt_count(n_down)} {down} in "
            f"{_look.fmt_count(len(ev.cells))} conditions"
        )
    failing: list[str] = []
    for event in multi.events:
        ev = multi.by_event[event]
        for record in ev.records():
            direction = record["direction"]
            if direction == "unchanged" or not record.get("holm", True):
                continue
            worse = fail_on == "worse" and record["verdict"] == "worse"
            bad = worse or fail_on in ("any", direction)
            condition = condition_text(record.get("config"))
            if bad and condition not in failing:
                failing.append(condition)
    tail = f"; failed in {', '.join(failing)}" if failing else ""
    return f"{'; '.join(parts)}; fail on {fail_on}{tail}"


@_operation
def check(
    store: Any,
    a: str | None = None,
    b: str | None = None,
    *,
    events: Sequence[str] | None,
    fail_on: str = "worse",
    method: str | None = None,
    q: float = DEFAULT_Q,
    typed: Sequence[str] = (),
    _notes: list[str],
) -> CheckResult:
    """A gate over two runs: ``passed`` unless a condition counted as a change ``fail_on``
    names (``worse``, ``any``, ``higher``, ``lower``) in one of ``events``."""
    store = _opened(store)
    idx = _index(store)
    run_a, run_b = _pair_of(idx, "check", a, b, _notes)
    st = Store(store.root)
    if events is None:
        raise _missing_flags_refusal(
            st, "check", [run_a, run_b], typed, idx, x_missing=False, event_missing=True
        )
    multi, _, manifests, _ = _run_diffs(
        store,
        idx,
        run_a,
        run_b,
        verb="check",
        events=events,
        method=method,
        q=q,
        all_methods=False,
    )
    if fail_on == "worse":
        unknown = [e for e in multi.events if multi.by_event[e].kind is None]
        if unknown:
            event = unknown[0]
            raise refusal(
                f'check --fail-on worse needs to know whether "{event}" is a failure or a '
                "success, and neither the command line nor the runs say",
                [
                    join([COMMAND, *set_option(typed, "--fail-on", "higher")]),
                    join([COMMAND, *_with_kind(typed, event, "failure")]),
                ],
            )
    passed = multi.check(fail_on=fail_on)
    word = "passed" if passed else "failed"
    sentence = _with_method(_check_sentence(multi, fail_on), multi.method)
    chosen = "default" if method is None else "named"
    payload = {
        "passed": passed,
        "fail_on": fail_on,
        **_method_first(multi.to_json(), multi.method, chosen),
    }
    return CheckResult(
        verdict=word,
        sentence=sentence,
        payload=payload,
        next=(),
        detail=_detail(word, multi, run_a, run_b, idx, manifests, chosen),
        method_chosen=chosen,
        run_a=run_a,
        run_b=run_b,
        names={r.run_id: r.name for r in idx.runs},
        multi=multi,
        manifests=manifests,
        writers=_old_writer(manifests),
    )


# ---------- one run ----------


def _single_run_shares(
    df: pd.DataFrame, cells: pd.DataFrame, events: Sequence[str], horizon: float
) -> dict[str, list[dict[str, Any]]]:
    from poisson_prove.report import _cif_at

    valid = df.loc[df["outcome"].notna()]
    by_hash = {str(h): g for h, g in valid.groupby("config_hash", sort=True)}
    curves = {str(r["config_hash"]): r["curve"] for r in cells.to_dict(orient="records")}
    out: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        rows = []
        for h, group in by_hash.items():
            n = int(len(group))
            k = int(((group["outcome"] == event) & (group["t"].astype(float) <= horizon)).sum())
            incidence = float(_cif_at(curves[h], event, horizon))
            rows.append(
                {
                    "config_hash": h,
                    "config": group["config"].iloc[0],
                    "n": n,
                    "n_events": k,
                    "share": stats.share(k, n),
                    "incidence": incidence,
                    "share_differs": abs(incidence - k / n) > 1e-12,
                }
            )
        out[event] = rows
    return out


@_operation
def run(
    store: Any,
    ref: str = "latest",
    *,
    events: Sequence[str] | None = None,
    horizon: float | None = None,
    fix: Sequence[str] = (),
    require_x: bool = False,
    typed: Sequence[str] = (),
    _notes: list[str],
) -> RunDetail:
    """One run: its manifest's facts and, per event, each condition's share with its interval
    at the run's horizon (or ``horizon``), the cumulative incidence beside it, and the design's
    limit."""
    store = _opened(store)
    idx = _index(store)
    run_id = _run_of(idx, ref, _notes)
    st = Store(store.root)
    if require_x:
        raise _missing_flags_refusal(
            st, "report", [run_id], typed, idx, x_missing=True, event_missing=False
        )
    manifest = st.manifest(run_id)
    fixed = _typed_fix(fix, (manifest,)) if fix else {}
    df = st.read(run_id, meta=False)
    named, _ = _split_events(events)
    _require_known_events("report", named, df)
    inferred = named is None
    if named is None and declared_events(manifest):
        found, non_event = declared_events(manifest), None
    elif named is None:
        try:
            found, non_event = infer_events(df, df.iloc[0:0])
        except EventInferenceError as exc:
            raise refusal(
                f"cannot infer the event set: {exc}; outcome counts: {_outcome_counts(df)}",
                [f"{COMMAND} report RUN --x AXIS --event NAME"],
            ) from exc
    else:
        found, non_event = tuple(dict.fromkeys(named)), None
    valid_t = df["t"].dropna()
    if valid_t.empty:
        raise refusal(f"run {run_id} has no rows with a time; nothing to report")
    at = float(valid_t.max()) if horizon is None else float(horizon)
    if at <= 0.0:
        shown = "the run's own" if horizon is None else str(horizon)
        raise refusal(f"--horizon must be above 0, got {shown}")
    competing = list(competing_set(df))
    cells = cell_table(df, found[0], horizon=at, method="aj", events=competing)
    shares = _single_run_shares(df, cells, found, at)
    design = _recorded_design(manifest)
    name = idx.name_of(run_id)
    payload = {
        "run_id": run_id,
        "run_name": name,
        "status": manifest.status,
        "target_id": manifest.target_id,
        "events": list(found),
        "non_event": non_event,
        "horizon": at,
        "by_event": {e: {"cells": list(shares[e])} for e in found},
        "design_mde": design,
    }
    return RunDetail(
        verdict="ok",
        sentence=f'"{name}": {manifest.status}, {_look.fmt_count(st.count(run_id))} rows',
        payload=payload,
        run_id=run_id,
        run_name=name,
        manifest=manifest,
        cells=cells,
        events=tuple(found),
        non_event=non_event,
        inferred=inferred,
        horizon=at,
        shares=shares,
        design=design,
        observations=_observation_counts(st, run_id),
        declarations=_declaration_check(st, run_id),
        fixed=fixed,
    )


def _error_kind(error: Any) -> str | None:
    if not isinstance(error, str) or not error:
        return None
    if error == "timeout":
        return "timeout"
    last = [line for line in error.splitlines() if line.strip()]
    if not last:
        return None
    head = last[-1].strip().partition(":")[0].strip()
    return head.rsplit(".", 1)[-1] if head else None


def _stored_trace(meta: Any) -> Trace | None:
    if not isinstance(meta, Mapping):
        return None
    trace = meta.get("trace")
    if not isinstance(trace, Mapping):
        return None
    try:
        return Trace.from_dict(trace)
    except (TraceValidationError, TypeError):
        return None


def _selected(st: Store, run_id: str, event: str, where: Mapping[str, Any]) -> pd.DataFrame:
    df = st.read(run_id, meta=False)
    kinds = df["error"].map(_error_kind)
    rows = df[(df["outcome"] == event) | (df["error"] == event) | (kinds == event)]
    for key, value in where.items():
        keep = [
            label
            for label, cfg in zip(rows.index, rows["config"], strict=True)
            if isinstance(cfg, Mapping) and cfg.get(key) == value
        ]
        rows = rows.loc[keep]
    return rows.sort_values(["config_hash", "replicate_index"], kind="stable")


def _episode_json(row: Any) -> dict[str, Any]:
    return {
        "config_hash": str(row.config_hash),
        "config": dict(row.config),
        "seed": int(row.seed),
        "replicate_index": int(row.replicate_index),
        "outcome": None if not isinstance(row.outcome, str) else row.outcome,
        "t": None if row.t != row.t else float(row.t),
        "error": row.error if isinstance(row.error, str) else None,
    }


@_operation
def episodes(
    store: Any,
    ref: str = "latest",
    *,
    event: str,
    condition: str | None = None,
    offset: int = 0,
    limit: int | None = None,
    _notes: list[str],
) -> EpisodePage:
    """The episodes behind ``event`` in a run (in one condition, by its hash, when given), in the
    store's order, ``limit`` of them from ``offset``."""
    store = _opened(store)
    idx = _index(store)
    run_id = _run_of(idx, ref, _notes)
    st = Store(store.root)
    rows = _selected(st, run_id, event, {})
    if condition is not None:
        rows = rows[rows["config_hash"].astype(str) == condition]
    total = len(rows)
    rows = rows.iloc[offset:] if limit is None else rows.iloc[offset : offset + max(limit, 0)]
    name = idx.name_of(run_id)
    payload = {
        "run_id": run_id,
        "run_name": name,
        "event": event,
        "condition": condition,
        "offset": offset,
        "total": total,
        "episodes": [_episode_json(row) for row in rows.itertuples(index=False)],
    }
    sentence = (
        f"{_look.fmt_count(len(rows))} of {_look.fmt_count(total)} episodes with outcome or "
        f'error "{event}" in run "{name}"'
    )
    return EpisodePage(verdict="ok", sentence=sentence, payload=payload)


@_operation
def inspect(
    store: Any,
    ref: str | None = "latest",
    *,
    event: str | None,
    condition: str | None = None,
    where: Sequence[str] = (),
    limit: int | None = None,
    typed: Sequence[str] = (),
    _notes: list[str],
) -> InspectResult:
    """The ``(config, seed)`` pairs behind an event in a run, with the line that reproduces the
    first one."""
    store = _opened(store)
    idx = _index(store)
    run_id = _run_of(idx, "latest" if ref is None else ref, _notes)
    name = idx.name_of(run_id)
    st = Store(store.root)
    manifest = st.manifest(run_id)
    if event is None:
        raise _missing_flags_refusal(
            st, "inspect", [run_id], typed, idx, x_missing=False, event_missing=True
        )
    checked = _declaration_check(st, run_id)
    provenance = () if checked is None else tuple(_provenance_lines(checked.provenance()))
    rows = _selected(st, run_id, event, _parse_pairs(where, "--where"))
    if condition is not None:
        rows = rows[rows["config_hash"].astype(str) == condition]
    total = len(rows)
    if limit is not None:
        rows = rows.head(max(limit, 0))
    if rows.empty:
        sentence = f'no rows with outcome or error "{event}" in run "{name}"'
        empty = {"run_id": run_id, "run_name": name, "event": event, "episodes": []}
        return InspectResult(verdict="ok", sentence=sentence, payload=empty, provenance=provenance)
    selected = [
        (str(h), int(i)) for h, i in zip(rows["config_hash"], rows["replicate_index"], strict=True)
    ]
    full = st.read(run_id, keys=selected).sort_values(
        ["config_hash", "replicate_index"], kind="stable"
    )
    first = full.iloc[0]
    import_path = manifest.environment.get("import_path")
    if isinstance(import_path, str) and ":" in import_path:
        module, fn = import_path.split(":", 1)
    else:
        module, fn = "your_module", "rollout"
    sentence = (
        f"{_look.fmt_count(len(full))} of {_look.fmt_count(total)} episodes with outcome or "
        f'error "{event}" in run "{name}"'
    )
    shown = []
    for row in full.itertuples(index=False):
        shown.append({**_episode_json(row), "trace": _stored_trace(row.meta)})
    payload = {
        "run_id": run_id,
        "run_name": name,
        "event": event,
        "episodes": [_episode_json(row) for row in full.itertuples(index=False)],
        "reproduce": {
            "module": module,
            "function": fn,
            "config": dict(first["config"]),
            "seed": int(first["seed"]),
        },
    }
    return InspectResult(
        verdict="ok",
        sentence=sentence,
        payload=payload,
        rows=tuple(shown),
        provenance=provenance,
        reproduce=cast("Mapping[str, Any]", payload["reproduce"]),
        observation_cap=_observation_cap(manifest),
    )


# ---------- paired ----------


@_operation
def paired(
    store: Any, declaration: str | Path, *, cap_check: bool = False, _notes: list[str]
) -> PairedResult:
    """A declaration's paired replay: the assertion that its arms were the same request
    replayed, the analysis, the windows, the cost and the replicates, as files to write; with
    ``cap_check``, whether the recorded input tokens are under the declared cap."""
    store = _opened(store)
    decl = Declaration.from_toml(str(declaration))
    st = Store(store.root)
    if cap_check:
        report = paired_cost(st, decl, phases={s.name: s.arms for s in decl.sweeps})
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
        details = [
            ("output tokens", n(report.output_tokens)),
            ("request spans with usage", n(report.recorded_spans)),
            ("request spans without", n(report.unrecorded_spans)),
        ]
        if report.dollars is not None:
            details.append(("dollars", _look.fmt_dollars(float(report.dollars))))
        return PairedResult(
            verdict=verdict,
            sentence=sentence,
            payload=_cost_block(decl, report),
            details=tuple(details),
            cap_reached=bool(report.cap_reached),
        )
    bundle = _bundle(st, decl)
    sentence = f"{_look.fmt_count(len(bundle.artifacts))} files, written nowhere"
    return PairedResult(
        verdict="ok",
        sentence=sentence,
        payload=bundle.payload,
        artifacts={name: _artifact_text(artifact) for name, artifact in bundle.artifacts.items()},
        default_out=f"./prove-paired-{decl.digest[:12]}",
    )


# ---------- setup ----------

_TEMPLATE = """\
# A sweep spec for poisson-prove: what to run, over which conditions, how many times each.
# Set the target to your rollout and the axes to what you vary, then sweep it with
# poisson-prove sweep (naming this file when it is not ./prove.toml).

# The rollout, a function (cfg, seed) -> Episode, as an import path; --target wins over it.
{target}
# The name the runs go by, and the unit their times are counted in.
target_id = "my-agent"
t_unit = "steps"
# Episodes per condition.
replicates = 194

# Every combination of the axes' values is one condition.
[axes.task_id]
type = "categorical"
values = ["search", "refund"]

[axes.temperature]
type = "continuous"
values = [0.0, 0.7]
"""


@_operation
def init(
    path: str | Path | None = None,
    *,
    example: bool = False,
    target: str | None = None,
    force: bool = False,
    typed: Sequence[str] = (),
    _notes: list[str],
) -> WrittenFiles:
    """Write one sweep spec and nothing else: the keyless quickstart with ``example``, else the
    template, its target filled with ``target`` or left a commented line. Asks nothing."""
    from importlib import resources

    given = path is not None
    if example and target is not None:
        raise refusal(
            "--example writes the quickstart with its own target; --target fills the template",
            [f"{COMMAND} init --example", join([COMMAND, "init", "--target", target])],
            usage=True,
        )
    out = Path(DEFAULT_SPEC if path is None else path)
    if out.exists() and not out.is_file():
        raise refusal(f"{out} exists and is not a file; init writes a file")
    if out.exists() and not force:
        raise refusal(
            f"{out} exists; init replaces it only with --force",
            [join([COMMAND, *typed, "--force"])],
        )
    if not out.parent.is_dir():
        raise refusal(f"no folder {out.parent} to write {out.name} into")
    if example:
        data = (resources.files("poisson_prove.examples") / "quickstart.toml").read_bytes()
        doc = tomllib.loads(data.decode("utf-8"))
        cells = math.prod(len(axis["values"]) for axis in doc["axes"].values())
        about = (
            f"a sweep of the keyless mock agent, {_look.fmt_count(cells)} conditions x "
            f"{_look.fmt_count(doc['replicates'])} replicates"
        )
    else:
        line = (
            f"target = {json.dumps(target)}"
            if target is not None
            else '# target = "pkg.module:rollout"'
        )
        data = _TEMPLATE.format(target=line).encode("utf-8")
        about = (
            "a template; set its axes to what you vary"
            if target is not None
            else "a template; set its target to your rollout and its axes to what you vary"
        )
    out.write_bytes(data)
    nexts: list[str] = []
    if example or target is not None:
        default = not given or Path(str(path)) == Path(DEFAULT_SPEC)
        nexts.append(f"{COMMAND} sweep" if default else join([COMMAND, "sweep", str(out)]))
    return WrittenFiles(
        verdict="ok",
        sentence=f"wrote {out}: {about}",
        payload={"wrote": [str(out)]},
        next=tuple(nexts),
        paths=(str(out),),
    )


#: The setup a person's own coding agent follows: the skill's folder, the two places the
#: agents read skills from, and the prompt the person gives their agent.
AGENT_SKILL = "poisson-prove-setup"
AGENT_FOLDERS = (f".agents/skills/{AGENT_SKILL}", f".claude/skills/{AGENT_SKILL}")
AGENT_PROMPT = (
    f"Use the {AGENT_SKILL} skill in this repository: set Poisson Prove up for me to review, "
    "then stop."
)
_VERSION_LINE = "  poisson-tool-version: "


def _agent_skill() -> str:
    """The packaged skill with this version filled in: the only line that differs from the
    template."""
    from importlib import resources

    from poisson_prove import __version__

    template = (resources.files("poisson_prove") / "skills" / AGENT_SKILL / "SKILL.md").read_text(
        encoding="utf-8"
    )
    lines = template.split("\n")
    (at,) = [i for i, line in enumerate(lines) if line.startswith(_VERSION_LINE)]
    lines[at] = f"{_VERSION_LINE}{json.dumps(__version__)}"
    return "\n".join(lines)


@_operation
def init_agent(
    repo: str | Path | None = None,
    *,
    force: bool = False,
    write: bool = True,
    typed: Sequence[str] = (),
    _notes: list[str],
) -> WrittenFiles:
    """Write the setup a person's own coding agent follows: the skill and the prompt, in each of
    the two folders the agents read skills from, and nothing else. ``repo`` is the folder as
    given (the current one by default; no root is looked for). An existing file of the four is
    refused unless ``force``, which replaces those four only; with ``write`` false nothing is
    written and the skill is the result's ``text``."""
    skill = _agent_skill()
    folder = Path("." if repo is None else repo)
    if repo is not None and (str(repo) == "" or not folder.is_dir()):
        why = "is not a folder" if folder.exists() else "does not exist"
        raise refusal(f'--repo "{repo}" {why}; the setup is written into a folder')
    files = [
        (f"{where}/{name}", text)
        for where in AGENT_FOLDERS
        for name, text in (("SKILL.md", skill), ("prompt.txt", AGENT_PROMPT + "\n"))
    ]
    shown = [rel if repo is None else str(Path(str(repo)) / rel) for rel, _ in files]
    sentence = f"wrote the setup for your coding agent ({_look.fmt_count(len(files))} files)"
    nexts = ("give your coding agent the prompt above, then review what it wrote",)
    if not write:
        return WrittenFiles(
            verdict="ok",
            sentence="the setup for your coding agent, printed; nothing was written",
            payload={"wrote": [], "prompt": AGENT_PROMPT},
            next=nexts,
            text=skill,
        )
    # Every path is checked before anything is written: a file standing where a folder must be,
    # or a folder where a file must be, is refused, so a refusal leaves nothing half written.
    for rel, _ in files:
        parts = Path(rel).parts
        for depth in range(1, len(parts)):
            above = folder.joinpath(*parts[:depth])
            if above.exists() and not above.is_dir():
                raise refusal(f"{Path(*parts[:depth])} is a file; the setup needs a folder there")
        if (folder / rel).is_dir():
            raise refusal(f"{rel} is a folder; the setup writes a file there")
    existing = [rel for rel, _ in files if (folder / rel).exists() or (folder / rel).is_symlink()]
    if existing and not force:
        raise refusal(
            f"{_join_words(existing)} already {'exists' if len(existing) == 1 else 'exist'}; "
            "init --agent replaces them only with --force",
            [join([COMMAND, *typed, "--force"])],
        )
    for rel, text in files:
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written beside and moved into place: a link standing there is replaced, never written
        # through to the file it points at.
        staged = path.with_name(f".{path.name}.poisson-prove-new")
        staged.write_text(text, encoding="utf-8")
        os.replace(staged, path)
    return WrittenFiles(
        verdict="ok",
        sentence=sentence,
        payload={"wrote": shown, "prompt": AGENT_PROMPT},
        next=nexts,
        paths=tuple(shown),
    )


def _join_words(items: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    items = list(items)
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


@_operation
def read_spec(path: str | Path, *, _notes: list[str]) -> Spec:
    """A sweep spec, read strictly: an unknown key or table is refused, naming the file, the
    line and the nearest known key."""
    return Spec(spec=SweepSpec.load(Path(path)), path=str(path))


# ---------- sweeps ----------


#: How long the check lets the target's import take.
IMPORT_LIMIT_S = 30
_ERRORS_LOG = Path("~") / ".cache" / "poisson-prove" / "errors.log"

#: The check's import, run in a process of its own with this interpreter, this environment and this
#: import path, the spec's folder first. Its first act is an audit hook that refuses every lookup,
#: connection or send to a host other than loopback (Prove imports no network module: the hook
#: reads the events Python raises before it touches the network); the hook stays on until the
#: process ends. The module is imported on the process's main thread, as a real sweep imports it,
#: with no byte code written; the target is looked up and its signature read, never called; the
#: answer goes to a file, and the process ends at once, so nothing the import left running reaches
#: the network after it. Standard library only.
_CHECK_IMPORT = r'''
import ipaddress, json, os, sys

_ATTEMPTS = []


class NetworkBlocked(OSError):
    pass


def _text(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("ascii", "replace")
    return value


def _loopback(host):
    if host is None:
        return True
    host = str(_text(host)).strip("[]")
    if host == "" or host.lower().rstrip(".") == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    address = getattr(address, "ipv4_mapped", None) or address
    return address.is_loopback or address.is_unspecified


def _hook(event, args):
    if not event.startswith("socket."):
        return
    if event == "socket.getaddrinfo":
        host, port = args[0], args[1]
    elif event in ("socket.gethostbyname", "socket.gethostbyaddr"):
        host, port = args[0], None
    elif event == "socket.getnameinfo":
        host, port = args[0][0], args[0][1]
    elif event in ("socket.connect", "socket.sendto", "socket.sendmsg"):
        address = args[1]
        if not isinstance(address, tuple) or not address:
            return
        host, port = address[0], address[1] if len(address) > 1 else None
    else:
        return
    if _loopback(host):
        return
    where = str(_text(host)) if port is None else str(_text(host)) + ":" + str(_text(port))
    _ATTEMPTS.append(where)
    raise NetworkBlocked("the check does not allow a connection to " + where)


sys.addaudithook(_hook)
sys.dont_write_bytecode = True
_out, _folder, _module, _attr, _path = json.loads(sys.argv[1])
sys.path[:] = [_folder, *(p for p in _path if p != _folder)]
_result = {"attempts": _ATTEMPTS}


def _failed(exc):
    import traceback

    _result["error"] = [type(exc).__name__, str(exc), "".join(traceback.format_exception(exc))]


try:
    import importlib

    module = importlib.import_module(_module)
except BaseException as exc:
    _failed(exc)
else:
    try:
        target = getattr(module, _attr, None)
    except BaseException as exc:
        _failed(exc)
    else:
        import inspect

        _result["callable"] = callable(target)
        _result["callables"] = sorted(
            name for name, value in vars(module).items()
            if not name.startswith("_")
            and callable(value)
            and getattr(value, "__module__", None) == module.__name__
        )
        try:
            _result["params"] = [
                [p.name, p.kind.name, p.default is not p.empty]
                for p in inspect.signature(target).parameters.values()
            ]
        except (TypeError, ValueError):
            _result["params"] = None
        except BaseException as exc:
            _failed(exc)
with open(_out, "w", encoding="utf-8") as fh:
    json.dump({**_result, "attempts": list(_ATTEMPTS)}, fh)
os._exit(0)
'''


@dataclasses.dataclass(frozen=True)
class _Param:
    """A target's parameter, as the check read it."""

    name: str
    kind: str
    has_default: bool


def _python_words(kind: str, words: str) -> str:
    """An exception as ``Type: its words``, its words starting lower case as Prove's do."""
    words = _look.one_line(words)
    if words[:1].isupper() and words[1:2].islower():
        words = words[0].lower() + words[1:]
    return f"{kind}: {words}" if words else kind


def _log_traceback(text: str, typed: Sequence[str]) -> None:
    """A traceback the person is not shown, appended to the errors log."""
    try:
        path = _ERRORS_LOG.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(f"{stamp}  {join([COMMAND, *typed])}\n{text.rstrip()}\n\n")
    except Exception:  # noqa: BLE001 - the log is best effort; the refusal is not
        pass


def _end(proc: subprocess.Popen[bytes]) -> None:
    """The check's process ended, with everything it started in its group."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        pass
    proc.wait()


def _checked_import(
    target: str, module_name: str, attr: str, folder: str, typed: Sequence[str]
) -> list[_Param] | None:
    """The check's import of the target (``_CHECK_IMPORT``), its answer read back: every way it
    fails is a refusal; the target's parameters when it passes (None when they cannot be read).
    The rollout is never called, and this process's import path and modules are untouched."""
    with tempfile.TemporaryDirectory(prefix="poisson-prove-check-") as scratch:
        out, err = Path(scratch) / "result.json", Path(scratch) / "stderr.txt"
        request = json.dumps([str(out), folder, module_name, attr, list(sys.path)])
        with err.open("wb") as stderr:
            proc = subprocess.Popen(
                [sys.executable, "-B", "-c", _CHECK_IMPORT, request],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )
            try:
                proc.wait(IMPORT_LIMIT_S)
            except subprocess.TimeoutExpired:
                _end(proc)
                raise refusal(
                    f"importing the target took over {IMPORT_LIMIT_S} s",
                    [f"move slow work out of what importing {module_name} runs, into the rollout"],
                ) from None
            finally:
                _end(proc)
        if not out.is_file():
            _log_traceback(err.read_text(encoding="utf-8", errors="replace"), typed)
            raise refusal(
                f'the target "{target}" could not be imported: its import ended the process '
                f"(exit {proc.returncode})",
                [f"the details are in {_ERRORS_LOG}"],
            )
        answer = json.loads(out.read_text(encoding="utf-8"))
    if answer["attempts"]:
        raise refusal(
            f"importing the target tried to connect to {answer['attempts'][0]}; the check does "
            "not allow it",
            [
                f"move the client's creation into the rollout, so importing {module_name} "
                "connects to nothing"
            ],
        )
    if "error" in answer:
        kind, words, trace = answer["error"]
        _log_traceback(trace, typed)
        raise refusal(
            f'the target "{target}" could not be imported ({_python_words(kind, words)})',
            [f"the traceback is in {_ERRORS_LOG}"],
        )
    if not answer["callable"]:
        has = ", ".join(answer["callables"]) or "none"
        raise refusal(
            f'"{module_name}" has no callable "{attr}"; it has {has}',
            [f"set target to one of them, as {module_name}:NAME, in the sweep spec"],
        )
    if answer["params"] is None:
        return None
    return [_Param(name, kind, has_default) for name, kind, has_default in answer["params"]]


def _params_of(fn: Any) -> list[_Param] | None:
    try:
        found = _pyinspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return None
    return [_Param(p.name, p.kind.name, p.default is not p.empty) for p in found]


def _takes_cfg_and_seed(params: Sequence[_Param]) -> bool:
    """A rollout takes ``(cfg, seed)``: its first two parameters by those names, any further one
    with a default (the executor calls ``rollout(cfg, seed)``)."""
    positional = [p for p in params if p.kind in ("POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD")]
    if [p.name for p in positional[:2]] != ["cfg", "seed"]:
        return False
    rest = [*positional[2:], *(p for p in params if p.kind == "KEYWORD_ONLY")]
    return all(p.has_default for p in rest)


def _parameters(params: Sequence[_Param]) -> str:
    stars = {"VAR_POSITIONAL": "*", "VAR_KEYWORD": "**"}
    return "(" + ", ".join(stars.get(p.kind, "") + p.name for p in params) + ")"


def _target_line(target: str, params: Sequence[_Param] | None, backend: str) -> str:
    """The plan's ``target`` line: the import path, and what was found where it was imported."""
    if backend == "modal":
        return f"target  {target}"
    if params is None:
        return f"target  {target} (imports)"
    if _takes_cfg_and_seed(params):
        return f"target  {target} (imports, takes cfg and seed)"
    return f"target  {target} (imports; takes {_parameters(params)}, not cfg and seed)"


@contextmanager
def _folder_first(folder: str) -> Iterator[None]:
    """``folder`` first on Python's import path for the block, then taken off again."""
    if sys.path and sys.path[0] == folder:
        yield
        return
    sys.path.insert(0, folder)
    try:
        yield
    finally:
        if folder in sys.path:
            sys.path.remove(folder)


def _resolve_target(
    target: str, *, folder: str, checked: bool, typed: Sequence[str]
) -> tuple[Any, list[_Param] | None]:
    """The rollout at ``target`` and its parameters. A sweep imports it here (the spec's folder is
    first on the path while it plans and runs); the check (``sweep --dry-run``) imports it in a
    process of its own instead (``_checked_import``), refuses a target that does not take
    ``(cfg, seed)``, and returns no rollout: it is never called."""
    try:
        module_name, attr = split_import_path(target)
    except ValueError as exc:
        raise refusal(f'cannot resolve --target "{target}": {exc}') from exc
    if checked:
        params = _checked_import(target, module_name, attr, folder, typed)
        if params is not None and not _takes_cfg_and_seed(params):
            raise refusal(
                f"the target takes {_parameters(params)}; a rollout takes (cfg, seed)",
                [
                    "write it as def rollout(cfg, seed) -> Episode (the rollout contract, "
                    "docs/your-own-agent.md)"
                ],
            )
        return None, params
    try:
        fn = _resolve_import(target)
    except (ValueError, ImportError, AttributeError, RuntimeError) as exc:
        raise refusal(f'cannot resolve --target "{target}": {exc}') from exc
    return fn, _params_of(fn)


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _missing_instrumentors(spec: SweepSpec) -> tuple[str, ...]:
    """The ``[capture].instrument`` names no installed package provides, in the spec's order."""
    if spec.capture is None or not spec.capture.instrument:
        return ()
    try:
        installed = {ep.name for ep in entry_points(group=INSTRUMENTOR_GROUP)}
    except Exception:  # noqa: BLE001 - an unreadable environment names nothing
        return ()
    return tuple(name for name in spec.capture.instrument if name not in installed)


def _missing_line(missing: Sequence[str]) -> str:
    """The plan's ``capture`` line when an instrumentor the spec names is not installed."""
    names = ", ".join(f'"{name}"' for name in missing)
    return f"capture  not installed here: {names}, so the sweep records no spans from it"


def _outcomes_line(spec: SweepSpec) -> str:
    """The plan's ``outcomes`` line: each failure and each success, then the other outcomes."""
    declared = spec.declare
    outcomes = tuple(declared.outcomes) if declared is not None else ()
    failures = tuple(declared.failures) if declared is not None else ()
    successes = tuple(declared.successes) if declared is not None else ()
    if not failures and not successes:
        named = f"{', '.join(outcomes)}; " if outcomes else ""
        return f"outcomes  {named}none declared a failure or a success"
    parts = [
        f"{label}: {', '.join(names)}"
        for label, names in (
            ("failures", failures),
            ("successes", successes),
            ("neither", tuple(o for o in outcomes if o not in failures + successes)),
        )
        if names
    ]
    return "outcomes  " + "; ".join(parts)


def _setup_notes(spec: SweepSpec) -> list[str]:
    """The check's notes on a setup that passes: no kinds declared, and axes that vary nothing."""
    notes = []
    declared = spec.declare
    if declared is None or not (declared.failures or declared.successes):
        notes.append(
            'no outcome is declared a failure or a success, so comparisons will say "higher" '
            'and "lower", not "worse" and "safer"'
        )
    for name in spec.axis_types:
        values = {json.dumps(config.get(name), sort_keys=True) for config in spec.configs}
        if len(values) == 1:
            notes.append(f'the axis "{name}" has one value, so it varies nothing')
    if len(spec.configs) == 1:
        notes.append("no axis varies, so the sweep runs one condition")
    return notes


def _require_extra(name: str) -> None:
    try:
        found = importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        found = False
    if not found:
        raise refusal(
            f'the {name} backend needs the "{name}" extra, which is not installed',
            [EXTRA_HINTS[name]],
        )


def _modal_config(o: Mapping[str, Any], spec_path: Path, target_path: str) -> tuple[Any, Any]:
    with spec_path.open("rb") as fh:
        data = tomllib.load(fh)
    table = data.get("modal", {})
    if not isinstance(table, Mapping):
        raise refusal(f"[modal] in {spec_path} must be a table")
    sections = {k: v for k, v in table.items() if isinstance(v, Mapping)}
    scalars = {k: v for k, v in table.items() if not isinstance(v, Mapping)}
    image_name = o.get("image") or "image"
    image_table = sections.get(image_name)
    if image_table is None:
        if image_name != "image":
            raise refusal(f"no [modal.{image_name}] table in {spec_path}")
        image_table = {}
    try:
        image = _modal.ImageSpec(**image_table)
    except (TypeError, ValueError) as exc:
        raise refusal(f"[modal.{image_name}]: {exc}") from exc
    try:
        options = _modal.ModalOptions(**scalars)
    except (TypeError, ValueError) as exc:
        raise refusal(f"[modal]: {exc}") from exc
    overrides = {
        name: o.get(key)
        for name, key in (
            ("concurrency", "concurrency"),
            ("infra_retries", "infra_retries"),
            ("max_cost", "max_cost"),
            ("est_seconds_per_episode", "est_seconds"),
            ("app_name", "app_name"),
            ("batch_size", "batch_size"),
            ("episode_timeout", "episode_timeout"),
            ("max_rollouts", "max_rollouts"),
        )
        if o.get(key) is not None
    }
    options = dataclasses.replace(options, **cast("dict[str, Any]", overrides))
    try:
        target = _modal.ModalTarget(import_path=target_path, image=image)
    except ValueError as exc:
        raise refusal(str(exc)) from exc
    return target, options


def _burla_config(o: Mapping[str, Any], spec_path: Path) -> BurlaOptions:
    try:
        options = BurlaOptions.from_sweep_file(spec_path)
        overrides = {
            name: o.get(key)
            for name, key in (
                ("max_cost", "max_cost"),
                ("est_seconds_per_episode", "est_seconds"),
                ("infra_retries", "infra_retries"),
                ("episode_timeout", "episode_timeout"),
                ("max_rollouts", "max_rollouts"),
                ("batch_size", "batch_size"),
            )
            if o.get(key) is not None
        }
        return dataclasses.replace(options, **cast("dict[str, Any]", overrides))
    except (TypeError, ValueError) as exc:
        raise refusal(f"[burla] in {spec_path}: {exc}") from exc


def _recorded_max_mde(store: Store, resume_id: str | None) -> float | None:
    if resume_id is None:
        return None
    try:
        recorded = store.manifest(resume_id).environment.get("max_mde_accepted")
    except StoreError:
        return None
    return float(recorded) if isinstance(recorded, (int, float)) else None


def _cost_phrase(block: str) -> str:
    for line in block.splitlines():
        if line.startswith("Cost: "):
            return _look.reprint(line[len("Cost: ") :])
    return "no estimate"


def _plan_sentence(p: Any, block: str) -> str:
    spec = p.spec
    return (
        f"{_look.fmt_count(spec.total_rollouts())} rollouts of {spec.target_id}: "
        f"{_look.fmt_count(len(spec.configs))} cells x {_look.fmt_count(spec.replicates)} "
        f"replicates on {p.backend}, {_cost_phrase(block)}"
    )


def _planned_name(idx: Index, p: Any, given: str | None) -> str:
    if p.resumed:
        return idx.name_of(p.run_id)
    if given is not None:
        return given
    return idx.computed_for(p.spec.target_id, datetime.now(UTC)) or p.run_id


def _empty_index(store: OpenedStore) -> Index:
    return Index(store.shown, [], {})


@_operation
def plan(
    spec: Spec | SweepSpec | None,
    *,
    store: Any,
    overrides: Mapping[str, Any] | None = None,
    _notes: list[str],
) -> Plan:
    """What a sweep would run: the conditions and replicates, the backend and its cost, the
    design's detection limit and the power gate's answer. An underpowered design is refused
    with the plan attached, so a face can still show it. The target is imported with the spec
    file's folder first on the import path; with ``overrides["dry_run"]`` (the check) it
    is imported with the network blocked and a time limit, its name and signature are checked,
    and it is never called."""
    with contextlib.ExitStack() as on_path:
        return _planned(spec, store=store, overrides=overrides, on_path=on_path, _notes=_notes)


def _planned(
    spec: Spec | SweepSpec | None,
    *,
    store: Any,
    overrides: Mapping[str, Any] | None,
    on_path: contextlib.ExitStack,
    _notes: list[str],
) -> Plan:
    o = dict(overrides or {})
    checked = bool(o.get("dry_run"))
    store = _opened(store)
    typed = list(o.get("typed") or [])
    backend = o.get("backend") or "local"
    image = o.get("image") or "image"
    if backend == "local":
        stray = [name for name in MODAL_ONLY_FLAGS if o.get(name) is not None]
        if stray or image != "image":
            names = ", ".join("--" + n.replace("_", "-") for n in stray) or "--image"
            raise refusal(f"{names} only applies to --backend modal")
    if backend == "burla":
        stray = [name for name in BURLA_REFUSED_FLAGS if o.get(name) is not None]
        if stray or image != "image":
            names = ", ".join("--" + n.replace("_", "-") for n in stray) or "--image"
            raise refusal(f"{names} does not apply to --backend burla")
    if backend in ("modal", "burla"):
        _require_extra(backend)
    idx = _index(store) if store.root.is_dir() else _empty_index(store)
    name = o.get("name")
    resume_ref = o.get("resume")
    if name is not None:
        if resume_ref is not None:
            raise refusal("--name names a new run; a resumed run keeps the name it has")
        typed_name, name = name, str(name).strip()
        why = unfit(name)
        if why is not None:
            shown = _look.one_line(typed_name) or typed_name
            raise refusal(f'--name "{shown}" cannot name a run: {why}')
        holders = idx.holders(name)
        if holders:
            run_id = sorted(holders)[0]
            raise refusal(
                f'--name "{name}": the run "{idx.name_of(run_id)}" ({run_id}) already answers '
                "to it; give the new run another name",
                [idx.listing()],
            )
    pair_with = o.get("pair_with")
    if pair_with is not None:
        pair_with = _run_of(idx, pair_with, _notes)
    if resume_ref == LATEST_PARTIAL:
        partial = idx.partial
        if not partial:
            raise refusal(f"no partial run to resume in {store.shown}", [_first_sweep(store.root)])
        resume_id: str | None = partial[0].run_id
    elif resume_ref is not None:
        resume_id = _run_of(idx, resume_ref, _notes)
    else:
        resume_id = None
    if spec is None:
        typed_spec = o.get("spec_typed")
        if typed_spec is None and not Path(DEFAULT_SPEC).is_file():
            raise refusal(
                f"no sweep spec here: no ./{DEFAULT_SPEC} in this folder, and none was given",
                [f"{COMMAND} init", f"{COMMAND} init --example", f"{COMMAND} init --agent"],
            )
        spec = read_spec.__wrapped__(
            DEFAULT_SPEC if typed_spec is None else typed_spec, _notes=_notes
        )
    spec_path = spec.path if isinstance(spec, Spec) else None
    spec = spec.spec if isinstance(spec, Spec) else spec
    shown_spec = spec_path or DEFAULT_SPEC
    folder = os.path.dirname(os.path.abspath(shown_spec))
    target = o.get("target")
    typed_target = target
    st = Store(store.root)
    if resume_id is not None and target is None:
        recorded = st.manifest(resume_id).environment.get("import_path")
        if isinstance(recorded, str):
            target = recorded
    if target is None:
        if spec.target is None:
            raise refusal(
                "no target to run: give --target pkg.module:rollout, or set "
                f'target = "pkg.module:rollout" in {shown_spec}',
                [f"{COMMAND} sweep --help"],
                usage=True,
            )
        target = spec.target
    replicates = o.get("replicates")
    if replicates is not None:
        if replicates < 1:
            raise refusal(
                f"--replicates must be 1 or more, got {replicates}",
                [f"{COMMAND} sweep --help"],
                usage=True,
            )
        spec = dataclasses.replace(spec, replicates=replicates)
    if checked and spec.capture is not None and not _has_module("opentelemetry.sdk"):
        raise refusal(
            '[capture] needs the "agent" extra, which is not installed', [EXTRA_HINTS["agent"]]
        )
    if spec.chaos is not None and spec.chaos.fault not in fault_names():
        raise refusal(
            f'[chaos].fault "{spec.chaos.fault}" is not a fault this build implements; the '
            f"names are {', '.join(fault_names())}"
        )
    # Only a local run's instrumentors are this machine's to look for.
    missing = _missing_instrumentors(spec) if backend == "local" else ()
    # The spec's folder is first on the path while the sweep plans (Burla's bundle reads it) and,
    # in ``start``, while it runs, as the rollout may import more of the person's code.
    on_path.enter_context(_folder_first(folder))
    rollout: Any = None
    params: list[_Param] | None = None
    burla_options: BurlaOptions | None = None
    modal: tuple[Any, Any] | None = None
    if backend == "modal":
        modal = _modal_config(o, Path(spec_path or DEFAULT_SPEC), target)
    else:
        rollout, params = _resolve_target(target, folder=folder, checked=checked, typed=typed)
    if backend == "burla":
        burla_options = _burla_config(o, Path(spec_path or DEFAULT_SPEC))
    max_mde = o.get("max_mde")
    try:
        p = _executor_plan(
            spec,
            st,
            backend=backend,
            run_salt=o.get("salt"),
            pair_with=pair_with,
            resume=resume_id,
            import_path=target,
            max_mde_accepted=max_mde if max_mde is not None else _recorded_max_mde(st, resume_id),
        )
    except ExecutorError as exc:
        raise refusal(_with_names(_look.plain_words(str(exc)), idx)) from exc
    p = dataclasses.replace(p, name=name)
    if backend == "modal":
        assert modal is not None
        block = _modal.preflight_modal(p, modal[0], modal[1])
    elif backend == "burla":
        assert burla_options is not None
        try:
            block = preflight_burla(p, target, burla_options)
        except ExecutorError as exc:
            kept = getattr(exc, "plan", None)
            shown_plan = None
            if isinstance(kept, str):
                shown_plan = Plan(
                    verdict="plan",
                    sentence=_plan_sentence(p, kept),
                    payload={},
                    lines=tuple(_look.reprint(line) for line in kept.splitlines()),
                )
            raise refusal(str(exc), getattr(exc, "nexts", ()), plan=shown_plan) from exc
    else:
        block = preflight(p)
    if p.resumed:
        block = block.replace(f"Resuming {p.run_id}:", f'Resuming "{idx.name_of(p.run_id)}":')
    sentence = _plan_sentence(p, block)
    lines = (
        _target_line(target, params, backend),
        _outcomes_line(spec),
        *([_missing_line(missing)] if missing else []),
        *(_look.reprint(line) for line in block.splitlines()),
    )
    payload: dict[str, Any] = {
        "run_id": p.run_id,
        "run_name": _planned_name(idx, p, name),
        "plan": {
            "rollouts": len(p.pairs),
            "cells": len(spec.configs),
            "replicates": spec.replicates,
            "backend": p.backend,
            "target": target,
            "cost": _cost_phrase(block),
            "lines": list(lines),
        },
    }
    shown = Plan(verdict="plan", sentence=sentence, payload=payload, lines=lines)
    try:
        check_power(p, max_mde=p.max_mde_accepted)
    except UnderpoweredDesign as exc:
        nexts = []
        if exc.replicates_needed is not None:
            nexts.append(
                join([COMMAND, *set_option(typed, "--replicates", str(exc.replicates_needed))])
            )
        if exc.offered is not None:
            nexts.append(join([COMMAND, *set_option(typed, "--max-mde", _look.ceil3(exc.offered))]))
        elif exc.most_conditions is not None:
            nexts.append(
                f"sweep fewer conditions: with {p.spec.replicates} replicates a side at most "
                f"{_look.fmt_count(exc.most_conditions)} can each be flagged alone"
            )
        raise refusal(str(exc), nexts, plan=shown) from exc
    design = _plan_design(p)
    design_line = None
    if design.flaggable:
        accepted = DEFAULT_MAX_MDE if p.max_mde_accepted is None else p.max_mde_accepted
        limit = "none detectable" if design.mde is None else _look.fmt_rate(design.mde)
        design_line = (
            f"  smallest {design.direction} one condition alone would be flagged for  "
            f"{limit} at its worst base rate, {_look.fmt_rate(design.base_rate)} "
            f"({_facts.test_name(design.test)}, q {design.q:g} over {design.family} tests, "
            f"{_look.times_in(design.power)}; you accept up to {_look.fmt_rate(accepted)})"
        )
    else:
        _notes.append(
            f"no single condition of this design can be flagged: the smallest possible p is "
            f"{_look.fmt_p(design.p_min)}, and a flag needs less than {_look.fmt_p(design.level)} "
            f"(q {design.q:g} over {design.family} tests); you accepted that with --max-mde 1"
        )
    payload["design_mde"] = design.record()
    if checked:
        _notes.extend(_setup_notes(spec))
    if backend == "modal":
        assert modal is not None
        try:
            _modal._check_cost(p, modal[1], modal[0].image)  # noqa: SLF001
        except ExecutorError as exc:
            raise refusal(
                str(exc),
                getattr(exc, "nexts", ()),
                plan=dataclasses.replace(shown, design_line=design_line),
            ) from exc
    return Plan(
        verdict="plan",
        sentence=sentence,
        payload=payload,
        next=(),
        lines=lines,
        design_line=design_line,
        inner=p,
        store=store,
        target=target,
        typed_target=typed_target,
        spec_path=o.get("spec_typed"),
        rollout=rollout,
        modal=modal,
        burla=burla_options,
        missing_instrumentors=missing,
        options={
            **o,
            "pair_with": pair_with,
            "name": name,
            "backend": backend,
            "image": image,
            "typed_named": _named_argv(typed, idx),
            "spec_folder": folder,
        },
    )


def _resume_command(o: Mapping[str, Any], typed_target: str | None) -> str:
    words = [
        COMMAND,
        "sweep",
        *([o["spec_typed"]] if o.get("spec_typed") is not None else []),
        "--resume",
    ]
    if typed_target is not None:
        words += ["--target", typed_target]
    if o.get("replicates") is not None:
        words += ["--replicates", str(o["replicates"])]
    if o.get("backend", "local") != "local":
        words += ["--backend", o["backend"]]
    if (o.get("image") or "image") != "image":
        words += ["--image", o["image"]]
    return join([*words, *_typed_store(o)])


def _typed_store(o: Mapping[str, Any]) -> list[str]:
    """``--store PATH`` when the sweep was typed with it, for its next lines, which act on the
    same store (the tool's options are accepted after the verb)."""
    typed = list(o.get("typed_named") or ())
    for i, token in enumerate(typed):
        if token == "--store" and i + 1 < len(typed):
            return ["--store", typed[i + 1]]
        if token.startswith("--store="):
            return ["--store", token.split("=", 1)[1]]
    return []


def _after_sweep(o: Mapping[str, Any], idx: Index, run_id: str, target: str) -> list[str]:
    pair_with = o.get("pair_with")
    store = _typed_store(o)
    if pair_with is not None:
        newest = [r.run_id for r in idx.complete[:2]]
        if newest == [run_id, pair_with]:
            return [join([COMMAND, "diff", *store])]
        return [join([COMMAND, "diff", idx.word_for(pair_with), idx.word_for(run_id), *store])]
    if target == MOCK_ROLLOUT:
        spec = [] if o.get("spec_typed") is None else [o["spec_typed"]]
        twin = ["--target", MOCK_PATCHED, "--pair-with", "latest"]
        return [join([COMMAND, "sweep", *spec, *twin, *store])]
    return []


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


class _Events:
    """The run's event log and the face's callback, one event at a time: progress at most once
    a second, plus once just before the end. An event that comes before the run's folder exists
    (a remote backend writes the folder when its first results arrive) is written as soon as the
    folder is there, ahead of the next one."""

    def __init__(
        self, store_root: Path, run_id: str, on_event: Callable[[Event], None] | None
    ) -> None:
        self.path = store_root / run_id / "events.jsonl"
        self.on_event = on_event
        self.last_progress: float | None = None
        self.unwritten: list[Event] = []

    def emit(self, kind: str, detail: Mapping[str, Any]) -> None:
        event = Event(kind, detail)
        self.unwritten.append(event)
        if self.path.parent.is_dir():
            with self.path.open("a", encoding="utf-8") as fh:
                for held in self.unwritten:
                    fh.write(json.dumps(held.to_json(), allow_nan=False) + "\n")
                fh.flush()
            self.unwritten.clear()
        if self.on_event is not None:
            self.on_event(event)

    def progress(self, done: int, kept: int, errored: int, total: int) -> None:
        detail = {"done": done, "kept": kept, "errored": errored, "total": total}
        now = time.monotonic()
        if self.last_progress is None or now - self.last_progress >= 1.0:
            self.last_progress = now
            self.emit("progress", detail)

    def flush_progress(self, detail: Mapping[str, Any]) -> None:
        self.emit("progress", detail)


def _kept(
    st: Store, idx_root: OpenedStore, run_id: str, planned: int, resume: str
) -> tuple[str, list[str]]:
    try:
        kept = st.count(run_id)
    except Exception:  # noqa: BLE001
        kept = 0
    try:
        name = _index(idx_root).name_of(run_id)
    except Exception:  # noqa: BLE001
        name = run_id
    sentence = (
        f"{_look.fmt_count(kept)} of {_look.fmt_count(planned)} rollouts kept in run "
        f'"{name}" (partial)'
    )
    return sentence, [resume]


def _resume_before(store: Store, p: Any) -> dict[str, Any]:
    manifest = store.manifest(p.run_id)
    tally = store.tally(p.run_id)
    return {
        "episodes_before": int(tally.with_outcome + tally.no_outcome),
        "replicates_before": (manifest.environment.get("sweep") or {}).get("replicates"),
        "after_comparison": _compared_before(manifest),
    }


def _record_resume(store: Store, p: Any, before: Mapping[str, Any]) -> None:
    tally = store.tally(p.run_id)
    after = int(tally.with_outcome + tally.no_outcome)
    if after <= before["episodes_before"]:
        return
    store._record_resume(
        p.run_id,
        {  # noqa: SLF001
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "episodes_before": before["episodes_before"],
            "episodes_after": after,
            "replicates_before": before["replicates_before"],
            "replicates_after": int(p.spec.replicates),
            "after_comparison": bool(before["after_comparison"]),
        },
    )


class _Cancelled(Exception):
    pass


@_operation
def start(
    plan: Plan,
    *,
    on_event: Callable[[Any], None] | None = None,
    cancel: threading.Event | None = None,
    _notes: list[str],
) -> RunResult:
    """Run a plan. ``on_event`` gets the sweep's events (``planned``, ``started`` or ``resumed``,
    ``progress``, ``note``, then ``finished`` or ``interrupted``), which the run's
    ``events.jsonl`` also holds; when ``cancel`` is set the run stops at the next rollout,
    ``partial`` and resumable."""
    p = plan.inner
    store = _opened(plan.store)
    st = Store(store.root)
    o = plan.options
    before = _resume_before(st, p) if p.resumed else None
    # A resumed run that has no log yet (one 0.0.1 wrote) starts its log at ``resumed``.
    events = _Events(store.root, p.run_id, on_event)
    total = len(p.pairs)
    began = time.monotonic()

    def on_progress(done: int, total_: int) -> None:
        # Counted over the whole run, so a resumed run's progress ends where its last event does;
        # an errored rollout is told apart only once the run is read at the end.
        shown = p.already_stored + done
        events.progress(shown, shown, 0, p.already_stored + total_)
        if cancel is not None and cancel.is_set() and done < total_:
            raise _Cancelled

    def closing_progress() -> int:
        kept = st.count(p.run_id)
        events.flush_progress(
            {"done": kept, "kept": kept, "errored": 0, "total": total + p.already_stored}
        )
        return kept

    started_once = {"done": False}

    def begin() -> None:
        if started_once["done"]:
            return
        started_once["done"] = True
        try:
            _artifacts.ensure_descriptor(store.root)
        except (OSError, ValueError):
            pass  # the run is written; the descriptor follows on the next write that can
        if p.resumed:
            events.emit(
                "resumed",
                {"run_id": p.run_id, "already_stored": p.already_stored, "rollouts": total},
            )
        else:
            events.emit(
                "planned",
                {
                    "run_id": p.run_id,
                    "rollouts": total,
                    "backend": p.backend,
                    "cost": plan.payload.get("plan", {}).get("cost"),
                },
            )
            events.emit("started", {"run_id": p.run_id})

    summary: RunSummary
    stopped_by_cancel = False
    try:
        if p.backend == "modal":
            assert plan.modal is not None
            if p.resumed:
                begin()
            summary = _modal_run(p, plan, st, on_progress, begin)
        elif p.backend == "burla":
            assert plan.burla is not None
            with _folder_first(o.get("spec_folder") or os.getcwd()):
                summary = run_burla(
                    p,
                    plan.target,
                    st,
                    options=plan.burla,
                    on_progress=_starting(begin, on_progress),
                )
        else:
            with _folder_first(o.get("spec_folder") or os.getcwd()):
                summary = _local_run(p, plan, st, o, on_progress, begin)
    except _Cancelled:
        # Set during a rollout: the run stops at the next boundary, partial and resumable.
        stopped_by_cancel = True
        summary = RunSummary(
            run_id=p.run_id,
            n_ok=st.count(p.run_id),
            n_errored=0,
            n_timeout=0,
            wall_time=time.monotonic() - began,
            stopped_by="cancel",
            complete=False,
        )
    except KeyboardInterrupt as exc:
        if p.run_id in st.runs():
            begin()
            sentence, nexts = _kept(
                st, store, p.run_id, len(p.pairs), _resume_command(o, plan.typed_target)
            )
            kept = closing_progress()
            events.emit("interrupted", {"kept": kept, "status": "partial"})
            raise Interrupted(f"interrupted: {sentence}", nexts) from exc
        raise
    except _REFUSABLE as exc:
        if p.run_id in st.runs():
            begin()
            sentence, nexts = _kept(
                st, store, p.run_id, len(p.pairs), _resume_command(o, plan.typed_target)
            )
            error = _final(f'{exc} (run "{p.run_id}")')
            kept = closing_progress()
            events.emit("interrupted", {"kept": kept, "status": "partial", "error": error})
            raise Stopped(sentence, nexts, error) from exc
        raise
    begin()
    if before is not None:
        _record_resume(st, p, before)
    result = _sweep_result(plan, store, st, p, summary)
    for note in _notes:
        events.emit("note", {"sentence": note})
    # The closing progress reads the store: done is every stored rollout, errored those with no
    # outcome, kept the rest, so the three always add up.
    done_now = int(result.payload.get("rows", 0))
    errored_now = int(result.payload.get("no_outcome", 0))
    events.flush_progress(
        {
            "done": done_now,
            "kept": done_now - errored_now,
            "errored": errored_now,
            "total": len(p.pairs) + p.already_stored,
        }
    )
    # A run that stopped short (a cancel, a --max-rollouts stop) ends its segment with
    # ``interrupted`` and is resumable; only a complete run ends with ``finished``.
    end = "finished" if summary.complete and not stopped_by_cancel else "interrupted"
    events.emit(end, {"status": result.payload.get("status"), "kept": done_now - errored_now})
    from poisson_prove.core._views import refresh_ui

    unrefreshed = refresh_ui(store.root)
    if unrefreshed is not None:
        result = dataclasses.replace(
            result,
            notes=(*result.notes, _dashboard_note(unrefreshed)),
        )
    return result


def _dashboard_note(why: str) -> str:
    """The one line a face prints when a write could not refresh the dashboard's pages."""
    return f"the dashboard's pages were not refreshed ({why}); run {COMMAND} ui"


def _starting(
    begin: Callable[[], None], on_progress: Callable[..., None]
) -> Callable[[int, int], None]:
    def call(done: int, total: int) -> None:
        begin()
        on_progress(done, total)

    return call


def _modal_run(
    p: Any, plan: Plan, st: Store, on_progress: Callable[..., None], begin: Callable[[], None]
) -> RunSummary:
    target, options = plan.modal
    begin()
    return _modal.run_modal(
        p, target, st, options=options, on_progress=_starting(begin, on_progress)
    )


def _local_run(
    p: Any,
    plan: Plan,
    st: Store,
    o: Mapping[str, Any],
    on_progress: Callable[..., None],
    begin: Callable[[], None],
) -> RunSummary:
    batch = o.get("batch_size")

    def progress(done: int, total: int) -> None:
        begin()
        on_progress(done, total)

    return run_local(
        p,
        plan.rollout,
        st,
        episode_timeout=o.get("episode_timeout"),
        max_rollouts=o.get("max_rollouts"),
        batch_size=DEFAULT_BATCH_SIZE if batch is None else batch,
        on_progress=progress,
    )


def _sweep_result(
    plan: Plan, store: OpenedStore, st: Store, p: Any, summary: RunSummary
) -> RunResult:
    o = plan.options
    run_id = summary.run_id
    try:
        idx = _index(store)
    except Refusal:
        idx = _empty_index(store)
    name = idx.name_of(run_id)
    pair_with = o.get("pair_with")
    paired_clause = "" if pair_with is None else f', paired with "{idx.name_of(pair_with)}"'
    payload = {**plan.payload, "run_id": run_id, "run_name": name}
    try:
        status = st.manifest(run_id).status
        tally = st.tally(run_id)
        kept = st.count(run_id)
        with_outcome, no_outcome, timed_out = tally.with_outcome, tally.no_outcome, tally.timed_out
    except StoreError:
        status = "complete" if summary.complete else "partial"
        kept = summary.n_ok + summary.n_errored
        with_outcome, no_outcome, timed_out = summary.n_ok, summary.n_errored, summary.n_timeout
    planned = _look.fmt_count(len(p.pairs) + p.already_stored)
    n = _look.fmt_count
    nexts: list[str] = []
    stopped = False
    if not summary.complete:
        verdict = "stopped"
        sentence = (
            f'{n(kept)} of {planned} rollouts kept in run "{name}" ({status}) in '
            f"{_look.fmt_duration(summary.wall_time)}"
        )
        nexts.append(_resume_command(o, plan.typed_target))
        stopped = True
    elif kept and with_outcome == 0:
        verdict = "stopped"
        commonest = _commonest_error(st, run_id)
        sentence = (
            f'every rollout errored in run "{name}": {n(no_outcome)} of {n(kept)}, '
            f"commonest {commonest or 'unknown'}"
        )
        if commonest is not None:
            inspect = [COMMAND, "inspect", "latest", "--event", commonest]
            nexts.append(join([*inspect, *_typed_store(o)]))
        stopped = True
    else:
        verdict = "done"
        nexts.extend(_after_sweep(o, idx, run_id, plan.target))
        missing = ", ".join(f'"{m}"' for m in plan.missing_instrumentors)
        unrecorded = f"; no spans from {missing}, not installed" if missing else ""
        sentence = (
            f'{n(kept)} rollouts in run "{name}" ({status}) in '
            f"{_look.fmt_duration(summary.wall_time)}{paired_clause}{unrecorded}"
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
    return RunResult(
        verdict=verdict,
        sentence=sentence,
        payload=payload,
        next=tuple(nexts),
        run_id=run_id,
        run_name=name,
        details=tuple(details),
        stopped=stopped,
    )


@_operation
def resume(
    store: Any,
    ref: str | None = None,
    *,
    on_event: Callable[[Any], None] | None = None,
    cancel: threading.Event | None = None,
    _notes: list[str],
) -> RunResult:
    """Continue a partial run (the latest one when ``ref`` is None) from what its manifest
    recorded: its conditions, replicates and target, on this machine, asking nothing."""
    store = _opened(store)
    idx = _index(store)
    if ref is None:
        if not idx.partial:
            raise refusal(f"no partial run to resume in {store.shown}", [_first_sweep(store.root)])
        run_id = idx.partial[0].run_id
    else:
        run_id = _run_of(idx, ref, _notes)
    manifest = Store(store.root).manifest(run_id)
    if manifest.backend != "local":
        raise refusal(
            f'the run "{idx.name_of(run_id)}" ran on {manifest.backend}; its image or bundle '
            "comes from its spec",
            [
                join(
                    [
                        COMMAND,
                        "sweep",
                        "SPEC.toml",
                        "--resume",
                        idx.word_for(run_id),
                        "--backend",
                        manifest.backend,
                    ]
                )
            ],
        )
    recorded = dict(manifest.environment.get("sweep") or {})
    spec = _spec_from_record(recorded, manifest)
    planned = plan.__wrapped__(spec, store=store, overrides={"resume": run_id}, _notes=_notes)
    finished: RunResult = start.__wrapped__(
        planned, on_event=on_event, cancel=cancel, _notes=_notes
    )
    return finished


def _spec_from_record(recorded: Mapping[str, Any], manifest: RunManifest) -> SweepSpec:
    retain = recorded.get("retain_traces_for")
    return SweepSpec(
        configs=tuple(dict(c) for c in recorded.get("configs", [])),
        axis_types=dict(recorded.get("axis_types", manifest.axis_types)),
        replicates=int(recorded.get("replicates", 1)),
        target_id=str(recorded.get("target_id", manifest.target_id)),
        t_unit=str(recorded.get("t_unit", manifest.t_unit)),
        retain_traces_for=None if retain is None else tuple(retain),
        duplicates_dropped=int(recorded.get("duplicates_dropped", 0)),
        declare=manifest.declared,
    )
