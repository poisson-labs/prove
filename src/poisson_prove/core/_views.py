"""The views behind the static UI's pages, the charts a saved comparison carries, and the
operations that save results, list them and build the UI (the front door's section 18).

A view is the object behind one page: every fact the page shows, as data, with the addresses of
the pages it links to. The page renderer (``poisson_prove._render_ui``) formats a view and never
recomputes anything in it; the terminal app and a later local server read the same objects.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa

from poisson_prove import __version__, _facts, _look, _render_charts, _render_ui, stats
from poisson_prove.core import _artifacts as A
from poisson_prove.core._ops import (
    COMMAND,
    _index,
    _method_first,
    _opened,
    _operation,
    method_line,
    refusal,
)
from poisson_prove.core._ops import run as run_detail
from poisson_prove.core._ops import runs as list_runs
from poisson_prove.core._results import (
    Artifact,
    ArtifactRef,
    CheckResult,
    Comparison,
    UiLocation,
    Unsaved,
    View,
    _document,
)
from poisson_prove.executor import _recorded_design
from poisson_prove.store import Store
from poisson_prove.survival import aalen_johansen, competing_set

VIEW_SCHEMA = f"{A.TOOL}.view/1"
INTERVAL_WORDS = {"tango": "Tango", "miettinen-nurminen": "Miettinen-Nurminen"}
CHART_KINDS = ("heatmap", "differences", "limits")
BUNDLE = ("style.css", "ui.js")
_HAZARD = "log-rank tests the cause-specific hazard"
#: The verdict block's detail lines a page shows elsewhere than under "what the verdict rests on".
_SHOWN_ELSEWHERE = ("method", "before", "after", "trade")


class DamagedArtifact(ValueError):
    """A saved artifact's folder holds a file this Prove cannot read."""


def _test_words(method: str) -> str:
    """The test behind a method, as a reader names it (one table, ``_facts``'s)."""
    try:
        return _facts.test_name(method)
    except KeyError:
        return method


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def _without_empty_notes(entry: dict[str, Any]) -> dict[str, Any]:
    """A row with no note where it has none: a note is beside a value that is missing."""
    return {k: v for k, v in entry.items() if not (k.endswith("_note") and v is None)}


def _could_tell(cell: Mapping[str, Any], threshold: float) -> bool:
    """Whether an unchanged condition could have shown a change of the threshold's size: each
    direction with room has a limit, and it is at or under the threshold."""
    asked = []
    for way in ("rise", "fall"):
        if cell.get(f"mde_{way}_note") == "no room":
            continue
        asked.append(_number(cell.get(f"mde_{way}_verdict", cell.get(f"mde_{way}"))))
    return bool(asked) and all(v is not None and v <= threshold for v in asked)


def _by_hash(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """A run's rows by condition hash, grouped once."""
    if len(frame) == 0:
        return {}
    return {str(h): sub for h, sub in frame.groupby(frame["config_hash"].astype(str), sort=True)}


# ---------- the charts a saved comparison carries ----------


def _incidence_points(
    arms: Sequence[Mapping[str, pd.DataFrame]], condition_hash: str, event: str, horizon: float
) -> tuple[list[list[float]], dict[str, str]]:
    """``[t, before, after]`` at every time the event happened in either run (and the horizon),
    each run's share of its episodes that ended in the event by then (Aalen-Johansen, the other
    endings competing), and the counts the hover titles give."""
    curves: list[Any] = []
    counts: dict[str, str] = {}
    times: set[float] = {0.0, float(horizon)}
    for arm, groups in zip(("before", "after"), arms, strict=True):
        sub = groups.get(condition_hash)
        rows = sub[sub["outcome"].notna()] if sub is not None else None
        hit = rows[rows["outcome"] == event] if rows is not None else None
        counts[arm] = f"{0 if hit is None else len(hit)} of {0 if rows is None else len(rows)}"
        if hit is None or rows is None or len(hit) == 0:
            curves.append(None)
            continue
        curve = aalen_johansen(
            rows["t"].to_numpy(dtype=float),
            rows["outcome"].to_numpy(dtype=object),
            competing_set(rows),
        )
        curves.append(curve)
        times |= {float(t) for t in hit["t"] if t == t}
    points: list[list[float]] = []
    for t in sorted(times):
        values = [0.0 if c is None else float(c.at(event, t)) for c in curves]
        points.append([t, *values])
    return points, counts


def _rest_label(config: Mapping[str, Any], rest: Sequence[str]) -> Any:
    if not rest:
        return ""
    if len(rest) == 1:
        return config.get(rest[0])
    return _look.condition_words({k: config.get(k) for k in rest})


def comparison_charts(
    doc: Mapping[str, Any], frames: Sequence[pd.DataFrame] | None
) -> list[tuple[str, str, dict[str, Any]]]:
    """Every chart of a comparison as ``(path, svg, data)``: per event the verdict heatmap, the
    differences with their intervals and the limits against the threshold; per condition and
    event each run's cumulative incidence. Each chart's data carries its title and caption."""
    out: list[tuple[str, str, dict[str, Any]]] = []
    method, q, m = str(doc["method"]), doc["q"], doc["n_tests"]
    test = _test_words(method)
    hazard = f" ({_HAZARD})" if method == "logrank_bh" else ""
    threshold = float(doc["threshold"])
    level_words = (
        _look.level_label(doc["interval_level"]) if doc.get("interval_level") is not None else "no"
    )
    rule = (
        "false coverage (Benjamini-Yekutieli)"
        if doc.get("n_rejected")
        else "simultaneous (Bonferroni)"
    )
    power = _look.times_in(stats.POWER)
    unit = str(doc.get("t_unit") or "t")
    horizon = _number(doc.get("horizon")) or 0.0
    arms = [_by_hash(f) for f in frames] if frames is not None else None
    for event, entry in doc["by_event"].items():
        cells = entry["cells"]
        axes = list(cells[0]["config"]) if cells else []
        x_axis = axes[0] if axes else "condition"
        rest = axes[1:]
        y_axis = " · ".join(rest)
        x_values = list(dict.fromkeys(c["config"].get(x_axis) for c in cells))
        y_values = list(dict.fromkeys(_rest_label(c["config"], rest) for c in cells))
        methods = sorted(
            {
                INTERVAL_WORDS.get(str(c["ci_method"]), str(c["ci_method"]))
                for c in cells
                if c.get("ci_method")
            }
        )
        base = {"schema": A.CHART_FORMAT, "event": event, "condition": None}
        heat_cells = [
            {
                "condition": _look.condition_words(c["config"]),
                "x": c["config"].get(x_axis),
                "y": _rest_label(c["config"], rest),
                "before": c["share_a"]["value"],
                "after": c["share_b"]["value"],
                "delta": c["delta"],
                "q": c.get("q"),
                "verdict": c["verdict"],
                "flagged": c["verdict"] != "unchanged",
            }
            for c in cells
        ]
        title = (
            f"Verdict heatmap: {event} over the conditions ({test}, flags by Benjamini-Hochberg "
            f"at the false discovery rate q {q:g} over {m} tests){hazard}"
        )
        caption = (
            f"Each condition's verdict for {event} with the change in its share, after minus "
            f"before, and its q; {x_axis} across" + (f", {y_axis} up" if rest else "") + "."
        )
        heat = {
            **base,
            "kind": "heatmap",
            "title": title,
            "caption": caption,
            "columns": [
                "condition",
                x_axis,
                *([y_axis] if rest else []),
                "before",
                "after",
                "delta",
                "q",
                "verdict",
            ],
            "rows": [
                [
                    h["condition"],
                    h["x"],
                    *([h["y"]] if rest else []),
                    h["before"],
                    h["after"],
                    h["delta"],
                    h["q"],
                    h["verdict"],
                ]
                for h in heat_cells
            ],
        }
        svg = _render_charts.heatmap(
            {
                "id": f"heatmap-{event}",
                "event": event,
                "cells": heat_cells,
                "x_values": x_values,
                "y_values": y_values if rest else [""],
                "x_axis": x_axis,
                "y_axis": y_axis,
                "title": title,
                "desc": caption,
            }
        )
        out.append((f"charts/heatmap-{event}.svg", svg, heat))
        diff_cells = [
            {
                "condition": _look.condition_words(c["config"]),
                "verdict": c["verdict"],
                "delta": c["delta"],
                "lo": c.get("ci_lo"),
                "hi": c.get("ci_hi"),
                "q": c.get("q"),
                "flagged": c["verdict"] != "unchanged",
            }
            for c in cells
        ]
        title = (
            f"Per-condition differences: {event}, after minus before, with its {level_words} "
            f"interval ({', '.join(methods) or 'none'}; {rule}; {test}){hazard}"
        )
        caption = (
            f"The change in each condition's share of {event}, after minus before, with the "
            f"interval on the change at {level_words}; flagged rows in their direction's colour, "
            "the rest dim."
        )
        diff = {
            **base,
            "kind": "differences",
            "title": title,
            "caption": caption,
            "columns": ["condition", "verdict", "delta", "lo", "hi", "q"],
            "rows": [
                [d["condition"], d["verdict"], d["delta"], d["lo"], d["hi"], d["q"]]
                for d in diff_cells
            ],
        }
        svg = _render_charts.differences(
            {
                "id": f"differences-{event}",
                "event": event,
                "cells": diff_cells,
                "level": level_words,
                "title": title,
                "desc": caption,
            }
        )
        out.append((f"charts/differences-{event}.svg", svg, diff))
        limit_cells = [
            {
                "condition": _look.condition_words(c["config"]),
                "verdict": c["verdict"],
                "rise": _number(c.get("mde_rise")),
                "rise_note": c.get("mde_rise_note"),
                "fall": _number(c.get("mde_fall")),
                "fall_note": c.get("mde_fall_note"),
                "could_tell": _could_tell(c, threshold) if c["verdict"] == "unchanged" else None,
            }
            for c in cells
        ]
        title = (
            f"Limits against the threshold: {event}, the smallest rise ▲ and fall ▼ one "
            f"condition alone would be flagged for, {power}, if it alone changed, from where it "
            f"was, against the threshold {_look.fmt_rate(threshold)} ({test}, q {q:g} over {m} "
            f"tests){hazard}"
        )
        caption = (
            f"Each condition's detection limit in each direction for {event} beside the "
            "threshold; the unchanged rows, which the verdict asks about, are bold."
        )
        lim = {
            **base,
            "kind": "limits",
            "title": title,
            "caption": caption,
            "columns": ["condition", "verdict", "rise", "fall", "threshold", "could_tell"],
            "rows": [
                [
                    d["condition"],
                    d["verdict"],
                    d["rise"] if d["rise"] is not None else str(d["rise_note"] or "none"),
                    d["fall"] if d["fall"] is not None else str(d["fall_note"] or "none"),
                    threshold,
                    "yes"
                    if d["could_tell"]
                    else "no"
                    if d["could_tell"] is not None
                    else "not asked",
                ]
                for d in limit_cells
            ],
        }
        svg = _render_charts.limits(
            {
                "id": f"limits-{event}",
                "event": event,
                "cells": limit_cells,
                "threshold": threshold,
                "title": title,
                "desc": caption,
            }
        )
        out.append((f"charts/limits-{event}.svg", svg, lim))
        for c in cells:
            h = str(c["config_hash"])
            words = _look.condition_words(c["config"])
            if arms is not None:
                points, counts = _incidence_points(arms, h, event, horizon)
            else:
                points, counts = (
                    [[0.0, 0.0, 0.0], [horizon, 0.0, 0.0]],
                    {"before": "not read", "after": "not read"},
                )
            title = f"Cumulative incidence of {event}, each run: {words}"
            caption = (
                f"The share of each run's episodes in {words} that had ended in {event} by each "
                f"time, before in grey and after in violet, to the horizon "
                f"({_look.fmt_num(horizon)} {unit})."
            )
            data = {
                **base,
                "kind": "incidence",
                "condition": h,
                "title": title,
                "caption": caption,
                "columns": ["t", "before", "after"],
                "rows": [list(p) for p in points],
            }
            svg = _render_charts.incidence(
                {
                    "id": f"incidence-{event}-{h}",
                    "event": event,
                    "points": points,
                    "horizon": horizon or 1.0,
                    "unit": unit,
                    "counts": counts,
                    "title": title,
                    "desc": caption,
                }
            )
            out.append((f"charts/{h}/incidence-{event}.svg", svg, data))
    return out


# ---------- what a saved result records ----------


def _settings_of(result: Comparison, kind: str, doc: Mapping[str, Any]) -> dict[str, Any]:
    """What a saved result records: the result-changing settings and how it was asked for,
    read off the saved document (under ``--methods all`` the comparison's own payload is keyed
    by method; the saved document is the primary method's)."""
    events = sorted(
        ({"name": e, "kind": doc["by_event"][e]["kind"]} for e in doc["by_event"]),
        key=lambda e: str(e["name"]),
    )
    settings: dict[str, Any] = {
        "method": result.method,
        "method_chosen": result.method_chosen,
        "events": events,
        "q": doc["q"],
        "power": stats.POWER,
        "horizon": doc["horizon"],
    }
    if kind == "comparison":
        settings.update(result.tree_settings)
    else:
        settings["fail_on"] = doc["fail_on"]
    return settings


def _saved_document(result: Comparison, kind: str) -> dict[str, Any]:
    """The result as the verb prints it in ``--json``: the comparison with the tree it grew, or
    the check, under the format's schema."""
    if kind == "check":
        return _document("check", result.verdict, result.sentence, result.payload, result.next)
    payload: dict[str, Any] = _method_first(
        result.multi.to_json(), result.method, result.method_chosen
    )
    nested = result.tree
    if nested is not None:
        payload = {**payload, "omnibus": nested.root.to_json(), "tree": nested.to_json()}
    nexts = result.next if result.next else result.report_next
    return _document("comparison", result.verdict, result.sentence, payload, nexts)


@_operation
def save(store: Any, result: Comparison, *, _notes: list[str]) -> ArtifactRef:
    """Save a comparison or a check into the store's ``.poisson/artifacts/``: the same result
    saved twice is one artifact. A store that cannot be written to raises ``Unsaved``."""
    store = _opened(store)
    kind = "check" if isinstance(result, CheckResult) else "comparison"
    doc = _saved_document(result, kind)
    settings = _settings_of(result, kind, doc)
    runs = [result.run_a, result.run_b]
    identity = A.artifact_id(kind, {"runs": runs}, settings)
    try:
        if not A.artifact_exists(store.root, kind, identity):
            charts = comparison_charts(doc, result.frames) if kind == "comparison" else []
            identity = A.save_result(
                store.root,
                kind,
                runs=runs,
                settings=settings,
                result=doc,
                detail=result.detail,
                charts=charts,
            )
    except (OSError, ValueError, pa.ArrowException) as exc:
        reason = getattr(exc, "strerror", None) or str(exc)
        raise Unsaved(kind, reason) from exc
    refresh_ui(store.root)
    return ArtifactRef(kind=kind, id=identity, path=f".poisson/artifacts/{kind}/{identity}")


@_operation
def artifacts(store: Any, *, kind: str | None = None, _notes: list[str]) -> list[ArtifactRef]:
    """Every saved artifact of the store (of one kind when given), by kind then id."""
    store = _opened(store)
    found = []
    for folder in A.artifact_folders(store.root, kind):
        try:
            descriptor = A.read_descriptor(folder)
        except A.NewerFormat as exc:
            raise refusal(str(exc), [A.UPGRADE]) from exc
        except ValueError as exc:
            raise refusal(f"the saved artifact at {folder.name} cannot be read: {exc}") from exc
        found.append(
            ArtifactRef(
                kind=str(descriptor.get("kind", folder.parent.name)),
                id=folder.name,
                path=f".poisson/artifacts/{folder.parent.name}/{folder.name}",
            )
        )
    return found


@_operation
def artifact(store: Any, id: str, *, _notes: list[str]) -> Artifact:  # noqa: A002 - the operation's name for it
    """One saved artifact: its descriptor and its result."""
    store = _opened(store)
    for folder in A.artifact_folders(store.root):
        if folder.name == id:
            try:
                descriptor = A.read_descriptor(folder)
                kind = str(descriptor.get("kind", folder.parent.name))
                return Artifact(
                    kind=kind, id=id, descriptor=descriptor, result=A.read_result(folder, kind)
                )
            except A.NewerFormat as exc:
                raise refusal(str(exc), [A.UPGRADE]) from exc
            except ValueError as exc:
                raise refusal(f"the saved artifact {id} cannot be read: {exc}") from exc
    raise refusal(f"no saved artifact {id} in {store.shown}")


# ---------- the views ----------


class _Context:
    """One reading of a store for its views: its runs, their names and rows, and every saved
    comparison with its descriptor and result. Every check's descriptor is read too, so a check
    in a newer major refuses the build as the format asks."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.name = os.path.basename(os.path.abspath(root))
        self.store = Store(root)
        self.index = _index(_opened(root)) if self.store.runs() else None
        self._frames: dict[str, pd.DataFrame] = {}
        self._groups: dict[str, dict[str, pd.DataFrame]] = {}
        self._manifests: dict[str, Any] = {}
        self.comparisons: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
        for folder in A.artifact_folders(root, "comparison"):
            try:
                descriptor = A.read_descriptor(folder)
                result = A.read_result(folder, "comparison")
            except A.NewerFormat:
                raise
            except (OSError, ValueError) as exc:
                raise DamagedArtifact(
                    f"the saved comparison at .poisson/artifacts/comparison/{folder.name} "
                    f"cannot be read: {exc}"
                ) from exc
            self.comparisons[folder.name] = (descriptor, result, folder)
        for folder in A.artifact_folders(root, "check"):
            try:
                A.read_descriptor(folder)
            except A.NewerFormat:
                raise
            except (OSError, ValueError) as exc:
                raise DamagedArtifact(
                    f"the saved check at .poisson/artifacts/check/{folder.name} cannot be read: "
                    f"{exc}"
                ) from exc
        self.episode_pages: set[tuple[str, str, str]] = set()
        for descriptor, result, _ in self.comparisons.values():
            hashes = {
                str(c["config_hash"]) for e in result["by_event"].values() for c in e["cells"]
            }
            for run in descriptor["inputs"]["runs"]:
                for event in result["by_event"]:
                    for h in hashes:
                        self.episode_pages.add((run, event, h))

    def runs(self) -> list[str]:
        return list(self.store.runs())

    def frame(self, run: str) -> pd.DataFrame:
        if run not in self._frames:
            self._frames[run] = self.store.read(run, meta=False)
        return self._frames[run]

    def groups(self, run: str) -> dict[str, pd.DataFrame]:
        """A run's rows by condition hash, grouped once."""
        if run not in self._groups:
            self._groups[run] = _by_hash(self.frame(run))
        return self._groups[run]

    def manifest(self, run: str) -> Any:
        if run not in self._manifests:
            self._manifests[run] = self.store.manifest(run)
        return self._manifests[run]

    def run_name(self, run: str) -> str:
        if self.index is None:
            return run
        return self.index.name_of(run)

    def comparison_name(self, descriptor: Mapping[str, Any]) -> str:
        a, b = descriptor["inputs"]["runs"]
        return f"{self.run_name(a)} → {self.run_name(b)}"

    def detail(self, descriptor: Mapping[str, Any]) -> list[dict[str, str]]:
        """The verdict block's detail lines the save recorded, as ``{label, text}``."""
        summary = descriptor.get("summary")
        lines = summary.get("detail") if isinstance(summary, Mapping) else None
        if not isinstance(lines, list):
            return []
        return [
            {"label": str(line[0]), "text": str(line[1])}
            for line in lines
            if isinstance(line, list) and len(line) == 2
        ]


def _view(view_kind: str, address: str, **fields: Any) -> View:
    return View(kind=view_kind, address=address, document=dict(fields))


def _run_address(run: str) -> str:
    return f"runs/{run}.html"


def _comparison_address(cid: str) -> str:
    return f"comparisons/{cid}.html"


def _design_sentence(design: Mapping[str, Any] | None) -> str | None:
    if not isinstance(design, Mapping) or not isinstance(design.get("test"), str):
        return None
    mde, base = _number(design.get("mde")), _number(design.get("base_rate"))
    power = _number(design.get("power"))
    q = design.get("q")
    words = _test_words(f"{design['test']}_bh")
    size = _look.fmt_rate(mde) if mde is not None else "none"
    at = "" if base is None else f", {_look.fmt_rate(base)}"
    return (
        f"{size} at its worst base rate{at} ({words}, q {q if q is not None else 'none'} over "
        f"{design.get('family')} tests, {_look.times_in(stats.POWER if power is None else power)})"
    )


def runs_view(ctx: _Context) -> View:
    """View 1: every run, newest first, and the saved comparisons."""
    runs: list[dict[str, Any]] = []
    if ctx.index is not None:
        for info in list_runs.__wrapped__(_opened(ctx.root), _notes=[]):
            row = info.entry
            runs.append(
                {
                    "number": row["number"],
                    "name": row["run_name"],
                    "run_id": row["run_id"],
                    "status": row["status"],
                    "backend": row["backend"],
                    "target": row["target_id"],
                    "rows": row["rows"],
                    "rows_without_outcome": row["no_outcome"],
                    "created_at": row["created_at"],
                    "address": _run_address(str(row["run_id"])),
                }
            )
    comparisons: list[dict[str, Any]] = []
    ordered = sorted(
        ctx.comparisons.items(),
        key=lambda kv: (str(kv[1][0].get("created_at", "")), kv[0]),
        reverse=True,
    )
    for cid, (descriptor, result, _) in ordered:
        entry: dict[str, Any] = {
            "name": ctx.comparison_name(descriptor),
            "verdict": result["verdict"],
            "method": _test_words(str(result["method"])),
            "saved_at": descriptor.get("created_at", ""),
            "id": cid,
            "address": _comparison_address(cid),
        }
        limit = _number(result.get("verdict_limit"))
        if limit is not None and result["verdict"] in (
            "no significant change",
            "too small to tell",
        ):
            entry["limit"] = limit
        comparisons.append(entry)
    n, k = len(runs), len(comparisons)
    if n:
        sentence = (
            f"{_look.fmt_count(n)} run{'s' if n != 1 else ''} and {_look.fmt_count(k)} saved "
            f"comparison{'s' if k != 1 else ''} in {ctx.name}"
        )
    else:
        sentence = f"no runs in {ctx.name}"
    fields: dict[str, Any] = {
        "verdict": "ok",
        "sentence": sentence,
        "store": ctx.name,
        "runs": runs,
        "comparisons": comparisons,
    }
    if not runs:
        fields["first_run"] = f"{COMMAND} init --example\n{COMMAND} sweep"
    if not comparisons:
        fields["no_comparison"] = (
            "No saved comparison yet. report and serve save the comparison they show; diff and "
            "check save it with --save."
        )
    return _view("runs", "index.html", **fields)


def _run_shares(ctx: _Context, run: str, outcomes: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Each condition's share of every outcome with its interval, as the core's ``run``
    operation computes them (one method for the run page and ``report RUN``); empty when the
    run has no row with an outcome."""
    if not outcomes:
        return {}
    detail = run_detail.__wrapped__(_opened(ctx.root), run, events=list(outcomes), _notes=[])
    shares: dict[str, dict[str, Any]] = {}
    for event, entry in detail.payload["by_event"].items():
        for cell in entry["cells"]:
            h = str(cell["config_hash"])
            share = dict(cell["share"])
            share["k"] = cell["n_events"]
            shares.setdefault(h, {})[event] = share
    return shares


def run_view(ctx: _Context, run: str) -> View:
    """View 2: one run's manifest facts, its outcomes per condition with their intervals, its
    design limit and its event log."""
    m = ctx.manifest(run)
    frame = ctx.frame(run)
    outcomes = sorted({str(o) for o in frame["outcome"].dropna()})
    environment = dict(m.environment or {})
    sweep = environment.get("sweep") if isinstance(environment.get("sweep"), Mapping) else {}
    replicates = sweep.get("replicates") if sweep else None
    configs = sweep.get("configs") if sweep else None
    total = (
        len(configs) * int(replicates)
        if isinstance(configs, list) and isinstance(replicates, int)
        else None
    )
    shares_of = _run_shares(ctx, run, outcomes)
    cells: list[dict[str, Any]] = []
    for h, sub in ctx.groups(run).items():
        kept = sub[sub["outcome"].notna()]
        shares: dict[str, Any] = {}
        for outcome in outcomes:
            entry: dict[str, Any] = shares_of.get(h, {}).get(outcome) or {
                "value": None,
                "lo": None,
                "hi": None,
                "level": stats.WILSON_LEVEL,
                "method": "wilson",
                "k": 0,
            }
            if (run, outcome, h) in ctx.episode_pages:
                entry["address"] = f"runs/{run}/episodes/{outcome}/{h}.html"
            shares[outcome] = entry
        cells.append(
            {
                "config": dict(sub.iloc[0]["config"]),
                "condition_hash": h,
                "n": int(len(kept)),
                "errored": int(len(sub) - len(kept)),
                "shares": shares,
            }
        )
    events = A.read_events(ctx.root / run)
    design = _recorded_design(m)
    horizon_values = frame["horizon"].dropna() if "horizon" in frame else pd.Series(dtype=float)
    horizon = float(horizon_values.max()) if len(horizon_values) else None
    paired = environment.get("paired_with")
    declared = (
        m.declared.to_dict() if m.declared is not None and hasattr(m.declared, "to_dict") else None
    )
    fields: dict[str, Any] = {
        "verdict": "ok",
        "sentence": f'"{ctx.run_name(run)}": {m.status}, {_look.fmt_count(len(frame))} rows',
        "name": ctx.run_name(run),
        "run_id": run,
        "status": m.status,
        "done": int(len(frame)),
        "total": total,
        "created_at": m.created_at,
        "target": m.target_id,
        "backend": m.backend,
        "t_unit": m.t_unit,
        "horizon": horizon,
        "paired_with": None if not isinstance(paired, str) else paired,
        "conditions": len(cells),
        "axes": {k: str(v) for k, v in dict(m.axis_types).items()},
        "replicates": replicates if isinstance(replicates, int) else None,
        "outcomes": outcomes,
        "declared": declared,
        "design_mde": dict(design) if isinstance(design, Mapping) else None,
    }
    if isinstance(paired, str) and ctx.index is not None and ctx.index.by_id(paired) is not None:
        fields["paired_with_name"] = ctx.run_name(paired)
        fields["paired_with_address"] = _run_address(paired)
    sentence = _design_sentence(fields["design_mde"])
    if sentence is not None:
        fields["design"] = sentence
    if outcomes:
        fields["shares_rule"] = (
            f"each run's share of episodes ending in each outcome, with a "
            f"{_look.level_label(stats.WILSON_LEVEL)} Wilson interval per condition, not adjusted "
            "for the number of conditions; episodes with no outcome are counted apart"
        )
    fields["comparisons"] = [
        {
            "id": cid,
            "name": ctx.comparison_name(d),
            "verdict": r["verdict"],
            "address": _comparison_address(cid),
        }
        for cid, (d, r, _) in ctx.comparisons.items()
        if run in d["inputs"]["runs"]
    ]
    fields["cells"] = cells
    fields["events"] = events
    if events is None:
        fields["events_note"] = (
            "its events were not recorded: the run was written before runs kept an event log"
        )
    return _view("run", _run_address(run), **fields)


def episodes_view(ctx: _Context, run: str, event: str, h: str) -> View:
    """View 5: the episodes behind an event in one condition of a run."""
    sub = ctx.groups(run).get(h)
    if sub is None:
        sub = ctx.frame(run).iloc[0:0]
    hit = sub[sub["outcome"] == event].sort_values("replicate_index", kind="stable")
    config = dict(sub.iloc[0]["config"]) if len(sub) else {}
    name = ctx.run_name(run)
    episodes = [
        {
            "replicate_index": int(r.replicate_index),
            "seed": int(r.seed),
            "outcome": str(r.outcome),
            "t": None if r.t != r.t else float(r.t),
            "rollout": f"rollout(cfg, seed={int(r.seed)})",
        }
        for r in hit.itertuples(index=False)
    ]
    address = f"runs/{run}/episodes/{event}/{h}.html"
    fields: dict[str, Any] = {
        "verdict": "ok",
        "sentence": (
            f"{_look.fmt_count(len(hit))} of {_look.fmt_count(len(sub))} episodes with outcome "
            f'{event} in run "{name}"'
        ),
        "run": name,
        "run_id": run,
        "run_address": _run_address(run),
        "event": event,
        "condition": config,
        "condition_hash": h,
        "comparisons": [
            {"id": cid, "address": f"comparisons/{cid}/{h}.html#{event}"}
            for cid, (d, r, _) in ctx.comparisons.items()
            if run in d["inputs"]["runs"]
            and event in r["by_event"]
            and any(str(c["config_hash"]) == h for c in r["by_event"][event]["cells"])
        ],
        "episodes": episodes,
        "reproduce": (
            "rollout is the run's target, called as the rollout contract does, rollout(cfg, "
            f"seed); cfg is the condition above. The import line is printed by {COMMAND} inspect "
            f'"{name}" --event {event}'
        ),
    }
    if not episodes:
        fields["empty"] = f"No episode of this condition ended in {event} in this run."
    return _view("episodes", address, **fields)


def comparison_view(ctx: _Context, cid: str) -> View:
    """View 3: the verdict first, then what it rests on, the per-event counts, the trades, the
    conditions and the charts."""
    descriptor, result, folder = ctx.comparisons[cid]
    a, b = descriptor["inputs"]["runs"]
    method = str(result["method"])
    q, m = result["q"], result["n_tests"]
    threshold = float(result["threshold"])
    cells = [c for e in result["by_event"].values() for c in e["cells"]]
    level = (
        _look.level_label(result["interval_level"])
        if result.get("interval_level") is not None
        else None
    )
    wilson = (
        _look.level_label(cells[0]["share_a"]["level"])
        if cells
        else _look.level_label(stats.WILSON_LEVEL)
    )
    rows = []
    for event, entry in result["by_event"].items():
        for c in entry["cells"]:
            rows.append(
                _without_empty_notes(
                    {
                        "event": event,
                        "config": dict(c["config"]),
                        "config_hash": str(c["config_hash"]),
                        "share_a": c["share_a"]["value"],
                        "share_a_lo": c["share_a"]["lo"],
                        "share_a_hi": c["share_a"]["hi"],
                        "share_b": c["share_b"]["value"],
                        "share_b_lo": c["share_b"]["lo"],
                        "share_b_hi": c["share_b"]["hi"],
                        "rate_a": c.get("rate_a"),
                        "rate_b": c.get("rate_b"),
                        "delta": c["delta"],
                        "p": c.get("p"),
                        "q": c.get("q"),
                        "q_holm": c.get("q_holm"),
                        "verdict": c["verdict"],
                        "mde_rise": _number(c.get("mde_rise")),
                        "mde_rise_note": c.get("mde_rise_note"),
                        "mde_fall": _number(c.get("mde_fall")),
                        "mde_fall_note": c.get("mde_fall_note"),
                        "address": f"comparisons/{cid}/{c['config_hash']}.html#{event}",
                    }
                )
            )
    events = []
    for name, entry in result["by_event"].items():
        unchanged = [c for c in entry["cells"] if c["verdict"] == "unchanged"]
        events.append(
            {
                "name": name,
                "kind": entry.get("kind"),
                "n_worse": entry.get("n_worse"),
                "n_safer": entry.get("n_safer"),
                "n_higher": entry.get("n_higher"),
                "n_lower": entry.get("n_lower"),
                "n_unchanged": entry.get("n_unchanged"),
                "n_could_not_tell": sum(1 for c in unchanged if not _could_tell(c, threshold)),
                "n_conditions": len(entry["cells"]),
            }
        )
    trades = [
        {
            "config": dict(t["config"]),
            "config_hash": str(t["config_hash"]),
            "safer": list(t.get("safer_events") or []),
            "worse": list(t.get("worse_events") or []),
            "address": f"comparisons/{cid}/{t['config_hash']}.html",
        }
        for t in result.get("trades") or []
    ]
    charts = [
        {
            "kind": kind,
            "event": event,
            "address": f"comparisons/{cid}/{kind}-{event}.html",
            "svg": (folder / "charts" / f"{kind}-{event}.svg").read_text(encoding="utf-8"),
        }
        for kind in CHART_KINDS
        for event in result["by_event"]
    ]
    test = _test_words(method)
    facts = [f for f in ctx.detail(descriptor) if f["label"] not in _SHOWN_ELSEWHERE]
    fields: dict[str, Any] = {
        "verdict": result["verdict"],
        "sentence": result["sentence"],
        "id": cid,
        "name": ctx.comparison_name(descriptor),
        "method": {
            "name": method,
            "words": test,
            "chosen": result["method_chosen"],
            "line": method_line(method, result["method_chosen"])
            if method in ("fisher_bh", "mcnemar_bh", "logrank_bh")
            else f"{test}, {result['method_chosen']}",
        },
        "before": {
            "name": ctx.run_name(a),
            "run_id": a,
            "status": ctx.manifest(a).status,
            "address": _run_address(a),
        },
        "after": {
            "name": ctx.run_name(b),
            "run_id": b,
            "status": ctx.manifest(b).status,
            "address": _run_address(b),
        },
        "threshold": {"value": threshold, "source": result["threshold_source"]},
        "family": {
            "tests": m,
            "conditions": len({str(c["config_hash"]) for c in cells}),
            "events": len(result["by_event"]),
            "q": q,
        },
        "saved_at": descriptor.get("created_at", ""),
        "facts": facts,
        "events": events,
        "trades": trades,
        "rows_rule": (
            f"before and after: each run's share of episodes ending in the event, with a {wilson} "
            "Wilson interval per condition, not adjusted for the number of conditions; change: "
            f"after minus before, with its {level or 'no'} interval; p is {test}'s, q its "
            f"Benjamini-Hochberg adjustment at the false discovery rate q {q:g} over {m} tests; "
            "rise and fall: the smallest rise and the smallest fall one condition alone would be "
            f"flagged for, {_look.times_in(stats.POWER)}, if it alone changed, from where it was"
        ),
        "rows": rows,
        "charts": charts,
        "could_not_detect": {
            "address": f"comparisons/{cid}/could-not-detect.html",
            "n_could_not_tell": sum(e["n_could_not_tell"] for e in events),
        },
    }
    return _view("comparison", _comparison_address(cid), **fields)


def condition_view(ctx: _Context, cid: str, h: str) -> View:
    """View 4: one condition of a comparison, a block per event."""
    descriptor, result, folder = ctx.comparisons[cid]
    a, b = descriptor["inputs"]["runs"]
    method = str(result["method"])
    test = _test_words(method)
    blocks = []
    config: dict[str, Any] = {}
    for event, entry in result["by_event"].items():
        for c in entry["cells"]:
            if str(c["config_hash"]) != h:
                continue
            config = dict(c["config"])
            shifted = list(c.get("competing_shift") or [])
            k_a, k_b = c.get("events_a"), c.get("events_b")
            delta = _number(c.get("delta"))
            if k_a == 0 and k_b == 0:
                sentence = f"{event}: no episode ended in {event} in either run"
            else:
                moved = "rose" if (delta or 0) > 0 else "fell" if (delta or 0) < 0 else "stayed"
                q_words = _look.fmt_p(c["q"]) if c.get("q") is not None else "none"
                sentence = (
                    f"{event} {moved} from {_look.fmt_rate(c['share_a']['value'])} to "
                    f"{_look.fmt_rate(c['share_b']['value'])} ({_look.fmt_signed(delta)}) "
                    f"({test}, q {q_words})"
                )
            block: dict[str, Any] = {
                "event": event,
                "kind": entry.get("kind"),
                "verdict": c["verdict"],
                "sentence": sentence,
                "share_a": {k: c["share_a"][k] for k in ("value", "lo", "hi", "level", "method")},
                "share_b": {k: c["share_b"][k] for k in ("value", "lo", "hi", "level", "method")},
                "k": {"a": k_a, "b": k_b},
                "n": {"a": c.get("n_a"), "b": c.get("n_b")},
                "delta": c["delta"],
                "ci": {
                    "lo": c.get("ci_lo"),
                    "hi": c.get("ci_hi"),
                    "level": c.get("ci_level"),
                    "basis": INTERVAL_WORDS.get(str(c.get("ci_method")), "none"),
                },
                "test": {
                    "name": test,
                    "n01": c.get("n01"),
                    "n10": c.get("n10"),
                    "stat": c.get("stat"),
                    "p": c.get("p"),
                    "q": c.get("q"),
                    "q_holm": c.get("q_holm"),
                },
                "mde_rise": _number(c.get("mde_rise")),
                "mde_rise_note": c.get("mde_rise_note"),
                "mde_fall": _number(c.get("mde_fall")),
                "mde_fall_note": c.get("mde_fall_note"),
                "mde_test": c.get("mde_test"),
                "mde_level": c.get("mde_level"),
                "mde_family": c.get("mde_family"),
                "mde_power": c.get("mde_power"),
                "mde_anchor": c.get("mde_anchor"),
                "p_min": c.get("p_min"),
                "flaggable": c.get("flaggable"),
                "episodes": [
                    {
                        "run": ctx.run_name(run),
                        "run_id": run,
                        "address": f"runs/{run}/episodes/{event}/{h}.html",
                    }
                    for run in (a, b)
                ],
                "charts": [
                    {
                        "kind": "incidence",
                        "event": event,
                        "address": f"comparisons/{cid}/{h}/incidence-{event}.html",
                        "svg": (folder / "charts" / h / f"incidence-{event}.svg").read_text(
                            encoding="utf-8"
                        ),
                    }
                ],
            }
            if shifted:
                block["competing"] = (
                    f"another outcome's share changed too ({', '.join(shifted)}), so the hazard "
                    "test and the incidence need not move together"
                )
            blocks.append(_without_empty_notes(block))
    wanted = ("verdict rule", "flagged only", "test", "competing", "limits", "intervals")
    rules = [f["text"] for f in ctx.detail(descriptor) if f["label"] in wanted]
    rules.append(
        f"before and after: each run's share with its {_look.level_label(stats.WILSON_LEVEL)} "
        "Wilson interval, per condition, not adjusted; the rise and the fall are each direction's "
        "limit"
    )
    return _view(
        "condition",
        f"comparisons/{cid}/{h}.html",
        condition=config,
        condition_hash=h,
        comparison={
            "id": cid,
            "name": ctx.comparison_name(descriptor),
            "address": _comparison_address(cid),
        },
        before={"name": ctx.run_name(a), "address": _run_address(a)},
        after={"name": ctx.run_name(b), "address": _run_address(b)},
        rules=rules,
        events=blocks,
    )


def could_not_detect_view(ctx: _Context, cid: str) -> View:
    """View 6: every condition that did not change, whether it could have shown a change of the
    threshold's size and why, the could-not-tell rows first."""
    descriptor, result, _ = ctx.comparisons[cid]
    threshold = float(result["threshold"])
    method = str(result["method"])
    test = _test_words(method)
    q, m = result["q"], result["n_tests"]
    rows = []
    for event, entry in result["by_event"].items():
        for c in entry["cells"]:
            if c["verdict"] != "unchanged":
                continue
            rows.append(
                _without_empty_notes(
                    {
                        "config": dict(c["config"]),
                        "config_hash": str(c["config_hash"]),
                        "event": event,
                        "share_a": c["share_a"]["value"],
                        "mde_rise": _number(c.get("mde_rise")),
                        "mde_rise_note": c.get("mde_rise_note"),
                        "mde_fall": _number(c.get("mde_fall")),
                        "mde_fall_note": c.get("mde_fall_note"),
                        "could_tell": _could_tell(c, threshold),
                        "address": f"comparisons/{cid}/{c['config_hash']}.html#{event}",
                    }
                )
            )
    rows.sort(key=lambda r: bool(r["could_tell"]))
    told = sum(1 for r in rows if r["could_tell"])
    cells = [c for e in result["by_event"].values() for c in e["cells"]]
    p_mins = [_number(c.get("p_min")) for c in cells]
    p_min = min((p for p in p_mins if p is not None), default=None)
    flaggable_n = sum(1 for c in cells if c.get("flaggable"))
    level = q / m if m else q
    if rows:
        answer = (
            f"{_look.fmt_count(told)} of {_look.fmt_count(len(rows))} unchanged rows could; "
            f"{_look.fmt_count(len(rows) - told)} could not tell"
        )
    else:
        answer = "nothing is asked: every compared condition changed"
    pairs = cells[0].get("pairs") if cells else None
    size = f"with {_look.fmt_count(pairs)} pairs " if isinstance(pairs, int) else ""
    if p_min is not None:
        flaggable = (
            f"{_look.fmt_count(flaggable_n)} of {_look.fmt_count(len(cells))} rows can be "
            f"flagged: {size}the smallest possible p is {_look.fmt_p(p_min)}, and a flag needs "
            f"less than {_look.fmt_p(level)} (q {q:g} over {m} tests)"
        )
    else:
        flaggable = (
            f"{_look.fmt_count(flaggable_n)} of {_look.fmt_count(len(cells))} rows can be flagged"
        )
    b = descriptor["inputs"]["runs"][1]
    design = _recorded_design(ctx.manifest(b))
    wanted = ("peeking", "errors", "test", "competing")
    fields: dict[str, Any] = {
        "verdict": result["verdict"],
        "sentence": result["sentence"],
        "comparison": {
            "id": cid,
            "name": ctx.comparison_name(descriptor),
            "address": _comparison_address(cid),
        },
        "question": (
            f"could each unchanged condition have caught a change of {_look.fmt_rate(threshold)}, "
            "if it alone changed, from where it was?"
        ),
        "threshold": {"value": threshold, "source": result["threshold_source"]},
        "n_unchanged": len(rows),
        "n_could_not_tell": len(rows) - told,
        "answer": answer,
        "flaggable": flaggable,
        "p_min": p_min,
        "level": level,
        "family": m,
        "design_mde": dict(design) if isinstance(design, Mapping) else None,
        "limits_rule": (
            "rise and fall: the smallest change each way this condition alone would be flagged "
            f"for, {_look.times_in(stats.POWER)}, if it alone changed, from where it was ({test}, "
            f"Holm q {q:g} over {m} tests)" + (f"; {_HAZARD}" if method == "logrank_bh" else "")
        ),
        "facts": [f for f in ctx.detail(descriptor) if f["label"] in wanted],
        "rows": rows,
        "charts": [
            {"kind": "limits", "event": e, "address": f"comparisons/{cid}/limits-{e}.html"}
            for e in result["by_event"]
        ],
    }
    sentence = _design_sentence(fields["design_mde"])
    if sentence is not None:
        fields["design"] = sentence
    return _view("could_not_detect", f"comparisons/{cid}/could-not-detect.html", **fields)


def chart_view(ctx: _Context, cid: str, path: str) -> View:
    """View 7: one chart, large, with its caption and its data as a table."""
    descriptor, result, folder = ctx.comparisons[cid]
    svg = (folder / path).read_text(encoding="utf-8")
    data = json.loads((folder / (path[: -len(".svg")] + ".json")).read_text(encoding="utf-8"))
    title = data.get("title")
    caption = data.get("caption")
    if not isinstance(title, str) or not isinstance(caption, str):
        # A chart saved without its words: they are the SVG's own title and description.
        found_title = re.search(r"<title[^>]*>(.*?)</title>", svg, re.S)
        found_desc = re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S)
        title = html.unescape(found_title.group(1)) if found_title else str(data["kind"])
        caption = html.unescape(found_desc.group(1)) if found_desc else ""
    address = f"comparisons/{cid}/" + path.removeprefix("charts/").replace(".svg", ".html")
    fields: dict[str, Any] = {
        "kind": data["kind"],
        "event": data["event"],
        "condition": data.get("condition"),
        "title": title,
        "caption": caption,
        "comparison": {
            "id": cid,
            "name": ctx.comparison_name(descriptor),
            "address": _comparison_address(cid),
        },
        "svg": svg,
        "data": {"columns": list(data["columns"]), "rows": [list(r) for r in data["rows"]]},
        "source": f".poisson/artifacts/comparison/{cid}/{path}",
    }
    if data.get("condition"):
        h = str(data["condition"])
        for entry in result["by_event"].values():
            for c in entry["cells"]:
                if str(c["config_hash"]) == h:
                    fields["condition_words"] = _look.condition_words(c["config"])
                    fields["condition_address"] = f"comparisons/{cid}/{h}.html#{data['event']}"
    return _view("chart", address, **fields)


def comparison_views(ctx: _Context, cid: str) -> dict[str, View]:
    """Every page of one saved comparison: its own, its could-not-detect page, a page per
    condition, and its charts' pages."""
    _, result, _ = ctx.comparisons[cid]
    views: dict[str, View] = {_comparison_address(cid): comparison_view(ctx, cid)}
    v = could_not_detect_view(ctx, cid)
    views[v.address] = v
    hashes = sorted(
        {str(c["config_hash"]) for e in result["by_event"].values() for c in e["cells"]}
    )
    for h in hashes:
        v = condition_view(ctx, cid, h)
        views[v.address] = v
        for event in result["by_event"]:
            v = chart_view(ctx, cid, f"charts/{h}/incidence-{event}.svg")
            views[v.address] = v
    for kind in CHART_KINDS:
        for event in result["by_event"]:
            v = chart_view(ctx, cid, f"charts/{kind}-{event}.svg")
            views[v.address] = v
    return views


def all_views(ctx: _Context, *, skip: Sequence[str] = ()) -> dict[str, View]:
    """Every view of the store, the comparisons in ``skip`` left out."""
    views = {"index.html": runs_view(ctx)}
    for run in ctx.runs():
        views[_run_address(run)] = run_view(ctx, run)
    for run, event, h in sorted(ctx.episode_pages):
        v = episodes_view(ctx, run, event, h)
        views[v.address] = v
    for cid in ctx.comparisons:
        if cid not in skip:
            views.update(comparison_views(ctx, cid))
    return views


def view_at(ctx: _Context, address: str) -> View:
    """The view behind one address of the UI."""
    parts = address.split("/")
    if address == "index.html":
        return runs_view(ctx)
    if parts[0] == "runs" and len(parts) == 2 and parts[1].endswith(".html"):
        run = parts[1].removesuffix(".html")
        if run in ctx.runs():
            return run_view(ctx, run)
    if parts[0] == "runs" and len(parts) == 5 and parts[2] == "episodes":
        run, event, h = parts[1], parts[3], parts[4].removesuffix(".html")
        if (run, event, h) in ctx.episode_pages:
            return episodes_view(ctx, run, event, h)
    if parts[0] == "comparisons" and len(parts) >= 2:
        cid = parts[1].removesuffix(".html")
        if cid in ctx.comparisons:
            _, result, folder = ctx.comparisons[cid]
            if len(parts) == 2:
                return comparison_view(ctx, cid)
            if parts[2] == "could-not-detect.html":
                return could_not_detect_view(ctx, cid)
            stem = parts[2].removesuffix(".html")
            if len(parts) == 3 and A.is_hex16(stem):
                return condition_view(ctx, cid, stem)
            chart = "charts/" + "/".join(parts[2:]).replace(".html", ".svg")
            if (folder / chart).is_file():
                return chart_view(ctx, cid, chart)
    raise KeyError(address)


# ---------- the UI ----------


def bundle_files() -> dict[str, bytes]:
    folder = resources.files("poisson_prove") / "_ui_bundle"
    return {name: (folder / name).read_bytes() for name in BUNDLE}


_FACT = re.compile(r'data-fact="(/(?:before|after)/(?:name|status))" data-value="([^"]*)"')
_GENERATOR = re.compile(r'<meta name="generator" content="([^"]*)">')


def _reusable(ui: Path, ctx: _Context, cid: str) -> bool:
    """Whether the pages of a saved comparison can be carried over from the UI as it stands:
    they were built by this version from the same artifact, which never changes, for the same
    two complete runs under the same names (R26: the same records give the same bytes)."""
    page = ui / "comparisons" / f"{cid}.html"
    folder = ui / "comparisons" / cid
    if not page.is_file() or not folder.is_dir():
        return False
    try:
        text = page.read_text(encoding="utf-8")
    except OSError:
        return False
    generator = _GENERATOR.search(text)
    if generator is None or generator.group(1) != f"{A.TOOL} {__version__}":
        return False
    descriptor = ctx.comparisons[cid][0]
    a, b = descriptor["inputs"]["runs"]
    wanted = {
        "/before/name": ctx.run_name(a),
        "/after/name": ctx.run_name(b),
        "/before/status": "complete",
        "/after/status": "complete",
    }
    if ctx.manifest(a).status != "complete" or ctx.manifest(b).status != "complete":
        return False
    found: dict[str, Any] = {}
    for pointer, raw in _FACT.findall(text):
        try:
            found[pointer] = json.loads(html.unescape(raw))
        except ValueError:
            return False
    return all(found.get(pointer) == value for pointer, value in wanted.items())


def _dead(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


_STAGING = re.compile(r"^\.ui-(?:new|old)-(\d+)")


def _clean_dead_builds(base: Path) -> None:
    """Staging and set-aside trees a build that died left behind; a live build's are its own."""
    for stale in base.glob(".ui-*"):
        found = _STAGING.match(stale.name)
        if stale.is_dir() and found and _dead(int(found.group(1))):
            shutil.rmtree(stale, ignore_errors=True)


def build_pages(root: Path) -> Path:
    """Build every page beside the UI and rename the new tree in last, so an interrupted build
    leaves the previous pages; the pages of a saved comparison the UI already holds are carried
    over unchanged. Returns the index page."""
    base = root / ".poisson"
    ui = base / "ui"
    ctx = _Context(root)
    reused = [cid for cid in ctx.comparisons if _reusable(ui, ctx, cid)]
    views = all_views(ctx, skip=reused)
    A.ensure_descriptor(root)
    _clean_dead_builds(base)
    A.clean_dead_saves(root)
    staging = Path(tempfile.mkdtemp(prefix=f".ui-new-{os.getpid()}-", dir=base))
    aside: Path | None = None
    try:
        _open_to_others(staging)
        for address, v in views.items():
            page = staging / address
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(_render_ui.render(v.to_json(), ctx.name), encoding="utf-8")
        for cid in reused:
            (staging / "comparisons").mkdir(exist_ok=True)
            shutil.copy2(
                ui / "comparisons" / f"{cid}.html", staging / "comparisons" / f"{cid}.html"
            )
            shutil.copytree(ui / "comparisons" / cid, staging / "comparisons" / cid)

        for name, data in bundle_files().items():
            (staging / name).write_bytes(data)
        if ui.exists():
            aside = base / f".ui-old-{os.getpid()}"
            os.replace(ui, aside)
        try:
            os.replace(staging, ui)
        except BaseException:
            if aside is not None and not ui.exists():
                os.replace(aside, ui)
                aside = None
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if aside is not None and aside.exists() and ui.exists():
            shutil.rmtree(aside, ignore_errors=True)
    return ui / "index.html"


def _open_to_others(folder: Path) -> None:
    """A temporary folder as the user's umask would make it, not the private one ``mkdtemp``
    makes, so a shared store's pages and artifacts are readable to the others who read it."""
    mask = os.umask(0)
    os.umask(mask)
    os.chmod(folder, 0o777 & ~mask)


def refresh_ui(root: Path) -> None:
    """Rebuild the UI a store already has; a store with none gets none from a write (``ui``
    builds the first). The pages are derived, so a failed refresh leaves the last ones and says
    nothing: the next ``ui`` builds them whole and says what is wrong."""
    if not (root / ".poisson" / "ui").is_dir():
        return
    try:
        build_pages(root)
    except Exception:  # noqa: BLE001 - derived files; the next build is whole
        pass


@_operation
def build_ui(store: Any, *, _notes: list[str]) -> UiLocation:
    """Build the static UI in the store's ``.poisson/ui/`` and return where its index is."""
    store = _opened(store)
    try:
        index = build_pages(store.root)
    except A.NewerFormat as exc:
        raise refusal(str(exc), [A.UPGRADE]) from exc
    except DamagedArtifact as exc:
        raise refusal(str(exc)) from exc
    except OSError as exc:
        raise refusal(
            f"cannot write the dashboard into {store.shown}: {exc.strerror or exc}"
        ) from exc
    ctx_name = os.path.basename(os.path.abspath(store.root))
    return UiLocation(
        verdict="ok",
        sentence=f"the dashboard over {ctx_name}",
        payload={},
        next=(),
        index=str(index),
        location=Path(os.path.abspath(index)).as_uri(),
    )


@_operation
def view(store: Any, address: str, *, _notes: list[str]) -> View:
    """The view behind one page of the UI, by the page's address (``comparisons/<id>.html``)."""
    store = _opened(store)
    try:
        return view_at(_Context(store.root), address)
    except A.NewerFormat as exc:
        raise refusal(str(exc), [A.UPGRADE]) from exc
    except DamagedArtifact as exc:
        raise refusal(str(exc)) from exc
    except KeyError as exc:
        raise refusal(f"no view at {address} in {store.shown}") from exc
