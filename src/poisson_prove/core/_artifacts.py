"""The artifact format as Prove writes it: the store descriptor, saved results with their
descriptor, long-form table and charts, and each run's event log (``docs/artifact-format.md``).

Every file this module writes goes under the store's ``.poisson/`` folder, which every reader of
runs ignores. A saved result is written into a temporary folder beside its place and renamed in
last, so an interrupted save leaves no artifact; saving a result whose id exists writes nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from poisson_prove import __version__

TOOL = "poisson-prove"
STORE_FORMAT = "poisson.store/1"
ARTIFACT_FORMAT = "poisson.artifact/1"
EVENT_FORMAT = "poisson.run-event/1"
TABLE_FORMAT = "poisson.table/1"
CHART_FORMAT = f"{TOOL}.chart/1"
#: The one command a reader names when a file is in a newer format than it reads.
UPGRADE = "pip install -U poisson-prove"
#: Settings that record how a result was asked for and are not part of its id.
HOW_ASKED = ("method_chosen",)
#: The event kinds a run's log may hold (the shared kinds of the format); a tool's own kinds
#: are named ``<tool>.<kind>`` and a reader passes over the ones it does not know.
EVENT_KINDS = ("planned", "started", "progress", "note", "finished", "interrupted", "resumed")
#: A saved comparison's table: the per-arm metrics and the pair's, from each condition's row.
ARM_METRICS = ("n", "events", "rate")
SHARE_METRICS = (("share", "value"), ("share_lo", "lo"), ("share_hi", "hi"))
PAIR_METRICS = (
    "delta",
    "stat",
    "p",
    "q",
    "q_holm",
    "ci_lo",
    "ci_hi",
    "mde_rise",
    "mde_fall",
    "mde_rise_verdict",
    "mde_fall_verdict",
    "p_min",
)
_LEVEL_OF = {
    "ci_lo": "ci_level",
    "ci_hi": "ci_level",
    "mde_rise": "mde_level",
    "mde_fall": "mde_level",
}
_NOTE_OF = {"mde_rise": "mde_rise_note", "mde_fall": "mde_fall_note"}
_HEX = frozenset("0123456789abcdef")


class NewerFormat(Exception):
    """A file in a newer major version of the format than this Prove reads."""

    def __init__(self, found: str, known: str) -> None:
        super().__init__(
            f"this store holds {found}, a newer format than this Prove reads ({known})"
        )
        self.found = found
        self.known = known


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def major_minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def _major(text: str) -> int | None:
    try:
        return int(text.rsplit("/", 1)[1])
    except (IndexError, ValueError):
        return None


def refuse_newer(found: Any, known: str) -> None:
    """Raise ``NewerFormat`` when ``found`` names the same kind as ``known`` at a newer major."""
    if not isinstance(found, str):
        return
    if found.rsplit("/", 1)[0] != known.rsplit("/", 1)[0]:
        return
    major, mine = _major(found), _major(known)
    if major is not None and mine is not None and major > mine:
        raise NewerFormat(found, known)


def canonical(value: Any) -> str:
    """The format's canonical JSON: sorted keys, no spaces, UTF-8 as it is."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _write_json(path: Path, document: Any) -> None:
    """A JSON file written whole through a temporary sibling renamed in."""
    staging = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    staging.write_text(
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
    os.replace(staging, path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- the store descriptor ----------


def descriptor_path(root: Path) -> Path:
    return root / ".poisson" / "store.json"


def check_store(root: Path) -> None:
    """Refuse a store whose descriptor is in a newer major than this Prove reads."""
    path = descriptor_path(root)
    if not path.is_file():
        return
    try:
        document = _read_json(path)
    except (OSError, ValueError):
        return
    if isinstance(document, Mapping):
        refuse_newer(document.get("format"), STORE_FORMAT)


def ensure_descriptor(root: Path) -> None:
    """Write the store descriptor on the first write into a store, and add this tool and
    major.minor version to ``writers`` the first time it writes; every other key, and a
    descriptor that already lists this version, is left exactly as it is."""
    path = descriptor_path(root)
    if path.is_file():
        document = _read_json(path)
        writers = document.get("writers")
        if not isinstance(writers, list):
            writers = []
            document["writers"] = writers
        for writer in writers:
            if (
                isinstance(writer, Mapping)
                and writer.get("tool") == TOOL
                and major_minor(str(writer.get("version", ""))) == major_minor(__version__)
            ):
                return
        writers.append({"tool": TOOL, "version": __version__, "first_write": utc_now()})
        _write_json(path, document)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    at = utc_now()
    _write_json(
        path,
        {
            "format": STORE_FORMAT,
            "created_by": {"tool": TOOL, "version": __version__},
            "created_at": at,
            "writers": [{"tool": TOOL, "version": __version__, "first_write": at}],
        },
    )


# ---------- ids and the long-form table ----------


def artifact_id(kind: str, inputs: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    """The first 16 hex of the sha256 of the canonical JSON of the kind, the tool, its
    major.minor version, the inputs and the result-changing settings."""
    payload = {
        "kind": kind,
        "tool": TOOL,
        "tool_version": major_minor(__version__),
        "inputs": dict(inputs),
        "settings": {k: v for k, v in settings.items() if k not in HOW_ASKED},
    }
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()[:16]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def table_rows(artifact: str, result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One row per (event, condition, arm, metric) of a saved result, each metric's value its
    row's own number, with the level where the metric has one and a note beside every null."""
    rows: list[dict[str, Any]] = []
    for event, entry in result["by_event"].items():
        for cell in entry["cells"]:
            base = {
                "artifact_id": artifact,
                "event": event,
                "condition": canonical(cell["config"]),
                "condition_hash": str(cell["config_hash"]),
            }

            def add(
                arm: str,
                metric: str,
                value: Any,
                level: Any = None,
                note: Any = None,
                base: Mapping[str, Any] = base,
            ) -> None:
                number = _number(value)
                if number is None and not note:
                    note = "not computed"
                rows.append(
                    {
                        **base,
                        "arm": arm,
                        "metric": metric,
                        "value": number,
                        "note": None if number is not None else str(note),
                        "level": _number(level),
                    }
                )

            for metric in ARM_METRICS:
                for arm in ("a", "b"):
                    add(arm, metric, cell.get(f"{metric}_{arm}"))
            for arm in ("a", "b"):
                share = cell.get(f"share_{arm}") or {}
                for metric, part in SHARE_METRICS:
                    add(
                        arm,
                        metric,
                        share.get(part),
                        share.get("level"),
                        "no episode with an outcome",
                    )
            for metric in PAIR_METRICS:
                level = cell.get(_LEVEL_OF[metric]) if metric in _LEVEL_OF else None
                add("both", metric, cell.get(metric), level, cell.get(_NOTE_OF.get(metric, "")))
    return rows


def write_table(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """The long-form table as Parquet, the format's nine key columns first."""
    schema = pa.schema(
        [
            ("artifact_id", pa.string()),
            ("event", pa.string()),
            ("condition", pa.string()),
            ("condition_hash", pa.string()),
            ("arm", pa.string()),
            ("metric", pa.string()),
            ("value", pa.float64()),
            ("note", pa.string()),
            ("level", pa.float64()),
        ]
    )
    pq.write_table(pa.Table.from_pylist([dict(r) for r in rows], schema=schema), path)


# ---------- saving ----------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean_stale(parent: Path) -> None:
    """Temporary folders a killed save left behind are removed before the next save."""
    for stale in parent.glob(".*"):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)


def save_result(
    root: Path,
    kind: str,
    *,
    runs: Sequence[str],
    settings: Mapping[str, Any],
    result: Mapping[str, Any],
    charts: Sequence[tuple[str, str, Mapping[str, Any]]] = (),
) -> str:
    """Write one saved result and return its id; an id that exists already is that artifact and
    nothing is written. Raises ``OSError`` when the store cannot be written to."""
    ensure_descriptor(root)
    inputs = {"runs": list(runs)}
    identity = artifact_id(kind, inputs, settings)
    parent = root / ".poisson" / "artifacts" / kind
    parent.mkdir(parents=True, exist_ok=True)
    folder = parent / identity
    if (folder / "artifact.json").is_file():
        return identity
    _clean_stale(parent)
    staging = Path(tempfile.mkdtemp(prefix=f".{identity}.", dir=parent))
    try:
        files: list[dict[str, Any]] = []
        result_name = f"{kind}.json"
        (staging / result_name).write_text(
            json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        files.append(
            {
                "path": result_name,
                "role": "result",
                "media_type": "application/json",
                "schema": f"{TOOL}.{kind}/1",
            }
        )
        write_table(staging / "conditions.parquet", table_rows(identity, result))
        files.append(
            {
                "path": "conditions.parquet",
                "role": "table",
                "media_type": "application/vnd.apache.parquet",
                "schema": TABLE_FORMAT,
            }
        )
        for path, svg, data in charts:
            target = staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(svg, encoding="utf-8")
            data_path = path[: -len(".svg")] + ".json"
            (staging / data_path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            files.append(
                {"path": path, "role": "chart", "media_type": "image/svg+xml", "data": data_path}
            )
            files.append(
                {
                    "path": data_path,
                    "role": "table",
                    "media_type": "application/json",
                    "schema": CHART_FORMAT,
                }
            )
        for entry in files:
            entry["sha256"] = _sha256(staging / entry["path"])
        descriptor = {
            "format": ARTIFACT_FORMAT,
            "kind": kind,
            "id": identity,
            "tool": TOOL,
            "tool_version": __version__,
            "created_at": utc_now(),
            "inputs": inputs,
            "settings": dict(settings),
            "summary": {"verdict": result["verdict"], "sentence": result["sentence"]},
            "files": files,
        }
        (staging / "artifact.json").write_text(
            json.dumps(descriptor, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        try:
            os.replace(staging, folder)
        except OSError:
            # Another process saved the same result first: that is the artifact.
            if not (folder / "artifact.json").is_file():
                raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return identity


# ---------- reading ----------


def is_artifact_id(name: str) -> bool:
    return len(name) == 16 and set(name) <= _HEX


def artifact_folders(root: Path, kind: str | None = None) -> list[Path]:
    """Every saved artifact's folder, by kind then id; a folder not named as an id is not one."""
    base = root / ".poisson" / "artifacts"
    if not base.is_dir():
        return []
    kinds = [kind] if kind is not None else sorted(p.name for p in base.iterdir() if p.is_dir())
    found: list[Path] = []
    for name in kinds:
        folder = base / name
        if not folder.is_dir():
            continue
        for candidate in sorted(folder.iterdir()):
            if is_artifact_id(candidate.name) and (candidate / "artifact.json").is_file():
                found.append(candidate)
    return found


def read_descriptor(folder: Path) -> dict[str, Any]:
    """A saved artifact's descriptor; a newer major is refused."""
    document = _read_json(folder / "artifact.json")
    if not isinstance(document, dict):
        raise ValueError(f"{folder / 'artifact.json'} does not hold a descriptor")
    refuse_newer(document.get("format"), ARTIFACT_FORMAT)
    return document


def read_result(folder: Path, kind: str) -> dict[str, Any]:
    document = _read_json(folder / f"{kind}.json")
    if not isinstance(document, dict):
        raise ValueError(f"{folder / f'{kind}.json'} does not hold a result")
    return document


# ---------- the event log ----------


def read_events(run_dir: Path) -> list[dict[str, Any]] | None:
    """The whole lines of a run's ``events.jsonl``, each as ``{at, kind, detail}``, in order;
    ``None`` when the run has no log. A partial last line (a run still writing, or one that
    died) is left out, as is a line of a kind this Prove does not know; a line in a newer major
    is refused."""
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    whole = lines[:-1]  # the text after the last newline is a line still being written
    events: list[dict[str, Any]] = []
    for line in whole:
        if not line.strip():
            continue
        try:
            document = json.loads(line)
        except ValueError:
            continue
        if not isinstance(document, Mapping):
            continue
        refuse_newer(document.get("schema"), EVENT_FORMAT)
        kind = document.get("kind")
        if kind not in EVENT_KINDS:
            continue
        detail = document.get("detail")
        events.append(
            {
                "at": str(document.get("at", "")),
                "kind": str(kind),
                "detail": dict(detail) if isinstance(detail, Mapping) else {},
            }
        )
    return events
