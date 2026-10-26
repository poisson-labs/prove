"""The Store: where every episode is written and where every downstream module reads from."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from poisson_prove import __version__
from poisson_prove._compat import retired_manifest_version
from poisson_prove.episode import Episode
from poisson_prove.trace import Declaration, Span, Trace, TraceValidationError, assemble, split

__all__ = [
    "EpisodeRecord",
    "RunManifest",
    "RunTally",
    "SchemaMismatch",
    "Store",
    "StoreError",
    "config_hash",
]


class StoreError(Exception):
    """Base class for store failures."""


class SchemaMismatch(StoreError):
    """The on-disk schema version is not one this build can read."""


class DuplicateEpisode(StoreError):
    """A (config_hash, replicate_index) pair already exists in the run or the batch."""


class MetaNotSerializable(StoreError):
    """A meta value cannot be encoded as JSON."""


class InvalidConfig(StoreError):
    """A config contains a value that has no canonical form."""


_SCHEMA_VERSION = 1
_TRACE_KEY = "trace"
_PART_PREFIX = "part-"
_PART_SUFFIX = ".parquet"

# The two error marks ``tally`` partitions no-outcome rows on, written here because
# ``executor`` imports this module and not the reverse. They are one vocabulary across three
# modules, not three constants that happen to agree: the S21 oracle pins them equal to
# ``executor._TIMEOUT_ERROR`` and ``executor_modal._INFRA_PREFIX``, so a change to any one of
# them is a cross-module change (ADR-037).
_TIMEOUT_MARK = "timeout"
_INFRA_MARK = "infra: "

_SCHEMA = pa.schema(
    [
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("config_hash", pa.string(), nullable=False),
        pa.field("config", pa.string(), nullable=False),
        pa.field("seed", pa.int64(), nullable=False),
        pa.field("replicate_index", pa.int64(), nullable=False),
        pa.field("outcome", pa.string(), nullable=True),
        pa.field("t", pa.float64(), nullable=True),
        pa.field("horizon", pa.float64(), nullable=True),
        pa.field("confidence", pa.float64(), nullable=True),
        pa.field("meta", pa.string(), nullable=False),
        pa.field("error", pa.string(), nullable=True),
        pa.field("wall_time", pa.float64(), nullable=False),
        pa.field("backend_meta", pa.string(), nullable=False),
        # A7: the trace, split in two and appended. ``trace`` is the envelope -- the span
        # forest with no content -- and ``trace_obs`` the observation bodies it was carrying,
        # keyed by span id. Appended, never inserted, and ``schema_version`` stays 1: the
        # fallback for a part written before A7 is presence-of-column (ADR-047), so there is
        # nothing for a version to select.
        pa.field("trace", pa.string(), nullable=True),
        pa.field("trace_obs", pa.string(), nullable=True),
        # PF4.38 (reading R5): the case the rollout named in ``meta["case_id"]``, copied to its own
        # column when the episode is appended, so a comparison reads it without decoding ``meta``.
        # Appended like A7's columns: a part written before it reads the column as null.
        pa.field("case_id", pa.string(), nullable=True),
    ]
)
_JSON_COLUMNS = ("config", "meta", "backend_meta")
#: Every nullable ``pa.string()`` field of ``_SCHEMA``, spelled out rather than derived from it:
#: a field added to the schema must be added here by hand, and A22's V5 is what fails until it
#: is. Derived, the assertion would follow the schema silently and A7 would inherit a read path
#: whose nulls are NaN under ``row.trace is not None``.
_NULLABLE_STRING_COLUMNS = ("outcome", "error", "trace", "trace_obs", "case_id")
_META_COLUMNS = ("meta", "backend_meta")
#: The two columns the split writes. Not in ``_META_COLUMNS``: ``meta=`` and ``trace=`` are
#: orthogonal knobs and folding these two names into that constant would silently couple them
#: (it gives the right projection for "full" and "none" and the wrong one for "envelope").
_TRACE_COLUMNS = ("trace", "trace_obs")
_TRACE_MODES = ("full", "envelope", "none")
#: A trace as a build before A8a stored it: six trace keys, and spans of thirteen. Spelled out as
#: history and never derived from ``Trace`` or ``Span``, so a field added to either later leaves
#: this saying what the old writer wrote. A8a added the rest -- ``alias_map_version`` and the
#: eight span fields -- and ``Trace.from_dict`` demands the exact key set of the current schema.
_A7_TRACE_KEYS = frozenset({"schema", "source", "source_version", "dropped", "spans", "truncated"})
_A7_SPAN_KEYS = frozenset(
    {
        "span_id",
        "parent_id",
        "kind",
        "name",
        "start_ns",
        "end_ns",
        "input",
        "output",
        "tokens",
        "confidence",
        "error",
        "code",
        "attrs",
    }
)


# ---------- canonical config ----------


def _canonical(x: Any, path: str) -> Any:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, float, np.integer, np.floating)):
        f = float(x)
        if not math.isfinite(f):
            raise InvalidConfig(f"non-finite value at config{path}: {x!r}")
        return f
    if isinstance(x, str):
        return x
    if x is None:
        return None
    if isinstance(x, Mapping):
        out: dict[str, Any] = {}
        for k, v in x.items():
            if not isinstance(k, str):
                raise InvalidConfig(f"non-string key at config{path}: {k!r}")
            out[k] = _canonical(v, f"{path}.{k}")
        return out
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_canonical(v, f"{path}[{i}]") for i, v in enumerate(x)]
    raise InvalidConfig(f"unsupported value at config{path}: {type(x).__name__}")


def _canonical_json(cfg: Mapping[str, Any]) -> str:
    if not isinstance(cfg, Mapping):
        raise InvalidConfig(f"config must be a mapping, got {type(cfg).__name__}")
    return json.dumps(_canonical(cfg, ""), sort_keys=True, separators=(",", ":"))


def config_hash(cfg: Mapping[str, Any]) -> str:
    """16-hex-char SHA-256 prefix of the canonical JSON of cfg. The cell key."""
    return hashlib.sha256(_canonical_json(cfg).encode("utf-8")).hexdigest()[:16]


# ---------- JSON encoding of meta / backend_meta ----------


def _jsonable(x: Any, path: str, label: str) -> Any:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (str, int, float)) or x is None:
        return x
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return [_jsonable(v, f"{path}[{i}]", label) for i, v in enumerate(x.tolist())]
    if isinstance(x, Mapping):
        out: dict[str, Any] = {}
        for k, v in x.items():
            if not isinstance(k, str):
                raise MetaNotSerializable(f"non-string key at {label}{path}: {k!r}")
            out[k] = _jsonable(v, f"{path}.{k}", label)
        return out
    if isinstance(x, (list, tuple)):
        return [_jsonable(v, f"{path}[{i}]", label) for i, v in enumerate(x)]
    raise MetaNotSerializable(f"unserializable value at {label}{path}: {type(x).__name__}")


def _encode_json(m: Mapping[str, Any], label: str) -> str:
    return json.dumps(_jsonable(m, "", label), sort_keys=True, separators=(",", ":"))


def _resolve_trace_mode(trace: str | None, *, meta: bool) -> str:
    """The read's trace mode, resolved from ``trace=`` and ``meta=`` and nothing else.

    ``trace=None`` is every call site written before A7: ``"full"`` where ``meta`` is read and
    ``"none"`` where it is not, so each keeps its exact behaviour without being edited.
    """
    if trace is None:
        return "full" if meta else "none"
    if trace not in _TRACE_MODES:
        raise ValueError(
            f"trace must be one of {', '.join(_TRACE_MODES)} or None, got {trace!r}"
        )
    if trace == "full" and not meta:
        # Refused rather than quietly downgraded: the full read puts the reassembled trace in
        # the meta column, meta=False projects that column away, and a caller who asked for
        # both has a bug that a silent "none" would hide.
        raise ValueError(
            "read(meta=False, trace='full') is refused: the full read reassembles the trace "
            "into the meta column and meta=False projects that column away. Use "
            "trace='envelope' for the trace without meta, or meta=True."
        )
    return trace


def _a7_trace_as_current(stored: Any) -> Any:
    """``stored`` as the current schema reads it, when it is exactly a trace as A7 stored it.

    A trace stored before A8a has six keys and spans of thirteen, and ``Trace.from_dict``, which
    demands the exact key set, rejects it: ``Store.read`` raised on every such row and
    ``inspect`` exited 3 (measured on the four runs of that age in the default store that keep
    their trace in the ``trace`` column; the eight that keep it in ``meta`` on a part before A7
    read back unvalidated and ``inspect`` printed nothing for them). The store knows what it
    wrote, so it recognises that shape here and adds what the shape lacked, each ``None``, which
    is what ``Span`` says a field A8a added means when it is ``None``: not recorded. Never a zero
    and never a blank.

    Exact, and nothing wider. A trace with a key the old shape did not have, one missing a key it
    did, one whose spans are not all thirteen keys, and one already in the current shape all come
    back as they came, so ``from_dict`` says about them what it always said. The recognition is
    here and not in ``from_dict`` because A8a's P8-1 pins that ``from_dict`` rejects both old
    shapes, and because a dict handed to it is not a row this store wrote. It reads and never
    writes: nothing stored is rewritten.
    """
    if not isinstance(stored, Mapping) or set(stored) != _A7_TRACE_KEYS:
        return stored
    spans = stored["spans"]
    if not isinstance(spans, (list, tuple)) or not all(
        isinstance(span, Mapping) and set(span) == _A7_SPAN_KEYS for span in spans
    ):
        return stored
    trace_added = {f.name: None for f in fields(Trace) if f.name not in _A7_TRACE_KEYS}
    span_added = {f.name: None for f in fields(Span) if f.name not in _A7_SPAN_KEYS}
    return {**stored, **trace_added, "spans": [{**span, **span_added} for span in spans]}


def _legacy_envelope(meta: Any) -> dict[str, Any] | None:
    """The envelope of a row written before the split, computed from ``meta["trace"]`` at read.

    A trace ``from_dict`` rejects is an absent trace, the same posture ``append`` and
    ``inspect`` already take: no error, no envelope. One stored as A7 stored it is not rejected:
    it is read as the current schema first (``_a7_trace_as_current``).
    """
    if not isinstance(meta, Mapping):
        return None
    stored = meta.get(_TRACE_KEY)
    if not isinstance(stored, Mapping):
        return None
    try:
        return split(Trace.from_dict(_a7_trace_as_current(stored)))[0]
    except TraceValidationError:
        return None


def _now_iso_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------- RunManifest ----------


@dataclass(frozen=True)
class RunManifest:
    """A run's manifest: its id and name, the target and its time unit, the salt its seeds
    come from, the axes' types, the backend, its status (``partial`` or ``complete``), and what
    the sweep recorded about itself in ``environment``."""
    run_id: str
    target_id: str
    t_unit: str
    run_salt: str
    axis_types: Mapping[str, Literal["continuous", "categorical"]]
    backend: str
    environment: Mapping[str, Any]
    retain_traces_for: tuple[str, ...] | None = None
    status: Literal["partial", "complete"] = "partial"
    created_at: str = field(default_factory=_now_iso_utc)
    poisson_prove_version: str = field(default_factory=lambda: __version__)
    schema_version: int = _SCHEMA_VERSION
    #: What the run's sweep declared it expects -- steps, outcomes, gates -- or ``None`` (A10).
    #: A thirteenth top-level field and not an ``environment`` entry: ``diff`` reads it as part
    #: of run identity beside ``t_unit`` and ``run_salt``. A manifest written before A10 has no
    #: key and reads back ``None``; no ``_SCHEMA_VERSION`` bump, the version gates the rows.
    declared: Declaration | None = None
    #: The name given at sweep time, or ``None``.
    name: str | None = None

    @property
    def written_by(self) -> str | None:
        """The name the run was stored under when it was not this package's, else ``None``.

        Set by ``from_dict`` on a manifest whose version was recorded under a retired key; a
        manifest built in this process has none. Not a field: nothing stored carries it,
        ``to_dict`` never writes it, and the thirteen fields above are the whole record.
        """
        marker: str | None = self.__dict__.get("_written_by")
        return marker

    def __post_init__(self) -> None:
        if not isinstance(self.target_id, str) or not self.target_id:
            raise ValueError("target_id must be a non-empty str")
        if not isinstance(self.t_unit, str) or not self.t_unit:
            raise ValueError("t_unit must be a non-empty str")
        if self.retain_traces_for is not None:
            object.__setattr__(self, "retain_traces_for", tuple(self.retain_traces_for))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "target_id": self.target_id,
            "t_unit": self.t_unit,
            "run_salt": self.run_salt,
            "axis_types": dict(self.axis_types),
            "backend": self.backend,
            "environment": dict(self.environment),
            "retain_traces_for": (
                None if self.retain_traces_for is None else list(self.retain_traces_for)
            ),
            "status": self.status,
            "created_at": self.created_at,
            "poisson_prove_version": self.poisson_prove_version,
            "schema_version": self.schema_version,
            "declared": None if self.declared is None else self.declared.to_dict(),
            **({} if self.name is None else {"name": self.name}),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RunManifest:
        retain = d.get("retain_traces_for")
        declared = d.get("declared")
        # The version under the current key; else under the key an earlier build wrote, with
        # the name that wrote it; else, for a manifest that recorded none, this build's.
        version = d.get("poisson_prove_version")
        written_by: str | None = None
        if version is None:
            recorded = retired_manifest_version(d)
            if recorded is not None:
                version, written_by = recorded
            else:
                version = __version__
        manifest = cls(
            run_id=d["run_id"],
            target_id=d["target_id"],
            t_unit=d["t_unit"],
            run_salt=d["run_salt"],
            axis_types=dict(d["axis_types"]),
            backend=d["backend"],
            environment=dict(d["environment"]),
            retain_traces_for=None if retain is None else tuple(retain),
            status=d.get("status", "partial"),
            created_at=d.get("created_at", _now_iso_utc()),
            poisson_prove_version=str(version),
            schema_version=d.get("schema_version", _SCHEMA_VERSION),
            declared=None if declared is None else Declaration.from_dict(declared),
            name=d.get("name") if isinstance(d.get("name"), str) else None,
        )
        if written_by is not None:
            object.__setattr__(manifest, "_written_by", written_by)
        return manifest


# ---------- EpisodeRecord ----------


@dataclass(frozen=True)
class EpisodeRecord:
    """One stored episode: the condition and its hash, the replicate and its seed, the outcome
    and its time, or the error that ended it, and its trace."""
    run_id: str
    config_hash: str
    config: Mapping[str, Any]
    seed: int
    replicate_index: int
    outcome: str | None
    t: float | None
    horizon: float | None
    confidence: float | None
    meta: Mapping[str, Any]
    error: str | None
    wall_time: float
    backend_meta: Mapping[str, Any]

    def __post_init__(self) -> None:
        has_outcome = self.outcome is not None
        has_error = self.error is not None
        if has_outcome == has_error:
            raise ValueError("exactly one of outcome / error must be set")
        if has_error:
            if self.t is not None or self.horizon is not None or self.confidence is not None:
                raise ValueError("errored record must have t, horizon, confidence = None")
        elif self.t is None or self.horizon is None:
            raise ValueError("record with an outcome must have t and horizon")

    @classmethod
    def from_episode(
        cls,
        ep: Episode,
        *,
        run_id: str,
        config: Mapping[str, Any],
        seed: int,
        replicate_index: int,
        wall_time: float,
        backend_meta: Mapping[str, Any] | None = None,
    ) -> EpisodeRecord:
        return cls(
            run_id=run_id,
            config_hash=config_hash(config),
            config=dict(config),
            seed=seed,
            replicate_index=replicate_index,
            outcome=ep.outcome,
            t=ep.t,
            horizon=ep.horizon,
            confidence=ep.confidence,
            meta=ep.to_dict()["meta"],
            error=None,
            wall_time=wall_time,
            backend_meta={} if backend_meta is None else dict(backend_meta),
        )

    @classmethod
    def errored(
        cls,
        *,
        run_id: str,
        config: Mapping[str, Any],
        seed: int,
        replicate_index: int,
        error: str,
        wall_time: float,
        backend_meta: Mapping[str, Any] | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> EpisodeRecord:
        """An errored row. ``meta`` carries what such a row can still say -- the truncated
        trace of an episode the executor terminated -- and is empty when nothing was kept."""
        return cls(
            run_id=run_id,
            config_hash=config_hash(config),
            config=dict(config),
            seed=seed,
            replicate_index=replicate_index,
            outcome=None,
            t=None,
            horizon=None,
            confidence=None,
            meta={} if meta is None else dict(meta),
            error=error,
            wall_time=wall_time,
            backend_meta={} if backend_meta is None else dict(backend_meta),
        )


# ---------- RunTally ----------


@dataclass(frozen=True)
class RunTally:
    """How a run's stored rows divide into rows with an outcome and rows without one.

    Counted from the rows when they are read, never stored and never a manifest field: a
    sweep's own summary counts one invocation, so a run stopped at ``max_rollouts`` and resumed
    would carry the second call's numbers over the whole run, wrong on exactly the runs where
    the question matters. The rows are the only record that survives a resume.

    ``rows == with_outcome + no_outcome`` and ``no_outcome == timed_out + infra + other``,
    always. An empty run is six zeros.
    """

    rows: int
    with_outcome: int
    no_outcome: int
    timed_out: int
    infra: int
    other: int

    def to_dict(self) -> dict[str, int]:
        """The six fields, in this order."""
        return {
            "rows": self.rows,
            "with_outcome": self.with_outcome,
            "no_outcome": self.no_outcome,
            "timed_out": self.timed_out,
            "infra": self.infra,
            "other": self.other,
        }


# ---------- Store ----------


def _case_id(meta: Any) -> str | None:
    """PF4.38 (reading R5): the case a rollout named in ``meta["case_id"]``, a non-empty string,
    copied into the episode's ``case_id`` column; None when it named none."""
    case = meta.get("case_id") if isinstance(meta, Mapping) else None
    return case if isinstance(case, str) and case else None


class Store:
    """A folder of runs: each run a manifest and its episodes. Reads and writes runs; refuses a
    run whose schema it does not know with ``SchemaMismatch`` and other faults with
    ``StoreError``."""
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    # -- paths --

    def _run_dir(self, run_id: str) -> Path:
        return self._root / run_id

    def _manifest_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "manifest.json"

    def _episodes_dir(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "episodes"

    def _parts(self, run_id: str) -> list[Path]:
        d = self._episodes_dir(run_id)
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob(f"{_PART_PREFIX}*{_PART_SUFFIX}") if p.is_file())

    def _write_manifest(self, manifest: RunManifest) -> None:
        path = self._manifest_path(manifest.run_id)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n")
        os.replace(tmp, path)

    # -- lifecycle --

    def create_run(self, manifest: RunManifest) -> None:
        run_id = manifest.run_id
        if not run_id or "/" in run_id or "\\" in run_id or run_id in (".", ".."):
            raise StoreError(f"invalid run_id: {run_id!r}")
        run_dir = self._run_dir(run_id)
        if run_dir.exists():
            raise StoreError(f"run already exists: {run_id!r}")
        self._episodes_dir(run_id).mkdir(parents=True, exist_ok=False)
        self._write_manifest(replace(manifest, status="partial"))

    def manifest(self, run_id: str) -> RunManifest:
        path = self._manifest_path(run_id)
        if not path.is_file():
            raise StoreError(f"unknown run: {run_id!r}")
        return RunManifest.from_dict(json.loads(path.read_text()))

    def _record_resume(self, run_id: str, entry: Mapping[str, Any]) -> None:
        """PF4.39: append one resume to the run's ``environment["resumes"]``: what a sweep
        ``--resume`` added and whether a comparison of the run was read before it."""
        manifest = self.manifest(run_id)
        environment = dict(manifest.environment)
        environment["resumes"] = [*(environment.get("resumes") or ()), dict(entry)]
        self._write_manifest(replace(manifest, environment=environment))

    def mark_complete(self, run_id: str) -> None:
        self._write_manifest(replace(self.manifest(run_id), status="complete"))

    def runs(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(p.name for p in self._root.iterdir() if (p / "manifest.json").is_file())

    # -- write --

    def append(self, run_id: str, records: Iterable[EpisodeRecord]) -> int:
        manifest = self.manifest(run_id)
        if manifest.status == "complete":
            raise StoreError(f"run is complete, cannot append: {run_id!r}")
        batch = list(records)
        if not batch:
            return 0

        retain = manifest.retain_traces_for
        seen: set[tuple[str, int]] = set()
        rows: list[dict[str, Any]] = []
        for i, r in enumerate(batch):
            if r.run_id != run_id:
                raise StoreError(f"record {i} belongs to run {r.run_id!r}, not {run_id!r}")
            key = (r.config_hash, int(r.replicate_index))
            if key in seen:
                raise DuplicateEpisode(f"duplicate (config_hash, replicate_index) in batch: {key}")
            seen.add(key)
            meta = dict(r.meta)
            # A7: the trace leaves ``meta`` here, at the one site every stored trace passes
            # through, and nothing downstream splits it again. The pop is unconditional --
            # retention decides only whether the two columns are written beside it, never
            # whether the key goes (A22's V7 pins that on an invalid trace too). Retention is a
            # policy over outcomes and an errored row has none, so its trace -- the snapshot of
            # the episode that hung -- is kept whatever ``retain_traces_for`` says.
            stored = meta.pop(_TRACE_KEY, None)
            envelope_json: str | None = None
            obs_json: str | None = None
            keep = retain is None or r.error is not None or r.outcome in retain
            if stored is not None and keep:
                try:
                    envelope, obs = split(Trace.from_dict(stored))
                except TraceValidationError:
                    # Keep the user's value untouched, one layer down from ``_merge_capture``:
                    # a trace this cannot read is stored exactly as it was written, both
                    # columns stay null, and ``append`` does not raise.
                    meta[_TRACE_KEY] = stored
                else:
                    envelope_json = _encode_json(envelope, _TRACE_KEY)
                    obs_json = None if not obs else _encode_json(obs, "trace_obs")
            rows.append(
                {
                    "run_id": r.run_id,
                    "config_hash": r.config_hash,
                    "config": _canonical_json(r.config),
                    "seed": int(r.seed),
                    "replicate_index": int(r.replicate_index),
                    "outcome": r.outcome,
                    "t": None if r.t is None else float(r.t),
                    "horizon": None if r.horizon is None else float(r.horizon),
                    "confidence": None if r.confidence is None else float(r.confidence),
                    "meta": _encode_json(meta, "meta"),
                    "error": r.error,
                    "wall_time": float(r.wall_time),
                    "backend_meta": _encode_json(r.backend_meta, "backend_meta"),
                    "trace": envelope_json,
                    "trace_obs": obs_json,
                    "case_id": _case_id(r.meta),
                }
            )

        existing = self._existing_keys(run_id)
        clash = existing & seen
        if clash:
            raise DuplicateEpisode(
                f"(config_hash, replicate_index) already in store: {sorted(clash)[:5]}"
            )

        parts = self._parts(run_id)
        next_index = 0
        if parts:
            last = parts[-1].name[len(_PART_PREFIX) : -len(_PART_SUFFIX)]
            next_index = int(last) + 1
        final = self._episodes_dir(run_id) / f"{_PART_PREFIX}{next_index:05d}{_PART_SUFFIX}"
        tmp = final.with_name(final.name + ".tmp")
        table = pa.Table.from_pylist(rows, schema=_SCHEMA)
        pq.write_table(table, tmp)
        os.replace(tmp, final)
        return len(rows)

    # -- read --

    def _read_table(
        self,
        run_id: str,
        columns: list[str] | None = None,
        hashes: Sequence[str] | None = None,
    ) -> pa.Table:
        """Every part concatenated, projected to ``columns`` and, when ``hashes`` is given,
        filtered to those ``config_hash`` values at the reader. Both go to Parquet: a projected
        column's bytes are never read, and a filtered row never reaches pandas."""
        parts = self._parts(run_id)
        if not parts:
            table = _SCHEMA.empty_table()
            return table.select(columns) if columns is not None else table
        filters = None if hashes is None else [("config_hash", "in", list(hashes))]
        return pa.concat_tables(
            [
                pq.read_table(p, schema=_SCHEMA, columns=columns, filters=filters)
                for p in parts
            ]
        )

    def _existing_keys(self, run_id: str) -> set[tuple[str, int]]:
        table = self._read_table(run_id, columns=["config_hash", "replicate_index"])
        hashes = table.column("config_hash").to_pylist()
        reps = table.column("replicate_index").to_pylist()
        return {(str(h), int(r)) for h, r in zip(hashes, reps, strict=True)}

    def read(
        self,
        run_id: str,
        *,
        meta: bool = True,
        keys: Iterable[tuple[str, int]] | None = None,
        trace: Literal["full", "envelope", "none"] | None = None,
    ) -> pd.DataFrame:
        """The run's rows, every part concatenated, sorted by ``(config_hash, replicate_index)``.

        ``meta=True``: the thirteen columns, ``config``, ``meta`` and ``backend_meta`` decoded.
        ``meta=False``: the eleven columns that are not ``meta``/``backend_meta``, ``config``
        decoded; the two JSON columns are projected away at the Parquet reader and never
        decoded. ``keys``: only the rows whose ``(config_hash, replicate_index)`` is in the set;
        the hash half is pushed to the reader as an ``in`` predicate, the pair is masked here.
        Unknown keys are absent, duplicates harmless; an empty ``keys`` is an empty frame with
        the requested columns and touches no part.

        ``trace=`` selects how much of the trace is presented, and is orthogonal to ``meta=``:
        ``meta=`` says only whether the ``meta`` column is read. ``None`` resolves to ``"full"``
        when ``meta=True`` and ``"none"`` when ``meta=False``, so every call written before the
        trace had a column of its own keeps its behaviour.

        ``"full"``      the same columns as ever, with the trace reassembled into
                        ``meta["trace"]`` where one is stored. Refused with ``meta=False``:
                        there is no ``meta`` column to hold it.
        ``"envelope"``  one further column, ``trace``, holding the envelope dict or ``None``,
                        and a ``meta`` (where read) with no ``"trace"`` key. The observation
                        bodies are projected away at the Parquet reader and never decoded.
                        ``meta`` is decoded only when the run holds a part written *before*
                        the split, whose envelope can come from nowhere else -- and then for
                        the whole run, not only that part, because every part is read under
                        one projection. A run resumed across the split therefore pays meta's
                        decode on its newer rows too; that is the only way a mixed
                        run exists, and reading each part under its own schema is what would
                        make the saving per part.
        ``"none"``      no trace anywhere: both columns projected away, and an older row's
                        ``meta["trace"]`` stripped, so the two layouts stay indistinguishable.

        A stored null in a string column reads back as ``None``, on every pandas this package
        supports: ``pyarrow`` gives a ``str`` column with ``NaN`` from pandas 3 on, and the
        nullable ones are rebuilt as ``object`` below.
        """
        manifest = self.manifest(run_id)
        if manifest.schema_version != _SCHEMA_VERSION:
            raise SchemaMismatch(
                f"run {run_id!r} has schema_version {manifest.schema_version}, "
                f"this build reads {_SCHEMA_VERSION}"
            )
        mode = _resolve_trace_mode(trace, meta=meta)
        # The projection is computed from the resolved mode and ``meta=`` separately. Adding the
        # two new names to ``_META_COLUMNS`` instead happens to give the right answer for
        # "full" and "none" and the wrong one for "envelope", and it couples two knobs the
        # interface defines as independent.
        columns = [
            c
            for c in _SCHEMA.names
            if c not in _TRACE_COLUMNS and (meta or c not in _META_COLUMNS)
        ]
        needed = set(columns)
        if mode == "full":
            needed.update(_TRACE_COLUMNS)
        elif mode == "envelope":
            needed.add(_TRACE_KEY)
            if not meta and self._has_pre_split_part(run_id):
                needed.add("meta")
        stored_columns = [c for c in _SCHEMA.names if c in needed]
        wanted = None if keys is None else {(str(h), int(i)) for h, i in keys}
        if wanted is not None and not wanted:
            # pyarrow rejects an empty `in` list, and nothing could match anyway.
            table = _SCHEMA.empty_table().select(stored_columns)
        else:
            hashes = None if wanted is None else sorted({h for h, _ in wanted})
            table = self._read_table(run_id, columns=stored_columns, hashes=hashes)
        df: pd.DataFrame = table.to_pandas()
        if wanted is not None:
            # An array, not a list: on an empty frame ``df[[]]`` is a column selection.
            mask = np.fromiter(
                (
                    (str(h), int(i)) in wanted
                    for h, i in zip(df["config_hash"], df["replicate_index"], strict=True)
                ),
                dtype=bool,
                count=len(df),
            )
            df = df[mask]
        df = df.sort_values(["config_hash", "replicate_index"], kind="stable")
        df = df.reset_index(drop=True)
        for col in _NULLABLE_STRING_COLUMNS:
            if col in df.columns:
                df[col] = pd.Series(
                    df[col].to_numpy(dtype=object, na_value=None), index=df.index, dtype=object
                )
        for col in _JSON_COLUMNS:
            if col in df.columns:
                df[col] = pd.Series(
                    [json.loads(s) for s in df[col]], index=df.index, dtype=object
                )
        if mode == "full":
            self._reassemble(df)
        elif mode == "envelope":
            df[_TRACE_KEY] = self._envelopes(df)
        if mode != "full" and "meta" in df.columns:
            # "envelope" and "none" both present a ``meta`` without the key, so a caller cannot
            # tell an older row from a newer one by what ``meta`` still carries.
            for value in df["meta"]:
                if isinstance(value, dict):
                    value.pop(_TRACE_KEY, None)
        return df[columns + ([_TRACE_KEY] if mode == "envelope" else [])]

    def _has_pre_split_part(self, run_id: str) -> bool:
        """Whether any part of this run was written before A7 -- read off each part's own
        Parquet footer and never off the manifest, because the fallback is presence-of-column
        and a run resumed across the A7 boundary holds parts of both kinds.

        Per run and not per row, which is the conservative half of the trade: one pre-A7 part
        makes the whole run's envelope read decode ``meta``. Splitting it per part means
        reading each part under its own schema instead of one concatenation under ``_SCHEMA``,
        which is a change to ``_read_table``'s shape and to where the sort and the key mask
        run; A9 is the packet that should want it, and nothing before then reads a mixed run.
        """
        return any(_TRACE_KEY not in pq.read_schema(p).names for p in self._parts(run_id))

    def _reassemble(self, df: pd.DataFrame) -> None:
        """Put each stored trace back where every consumer already reads it, ``meta["trace"]``.

        A row whose ``trace`` column is null keeps whatever ``meta`` holds: on a pre-A7 part
        that is the trace itself, whole and needing no reassembly; on a post-A7 row it is either
        nothing or the invalid value ``append`` left exactly as it was written. A trace stored as
        A7 stored it, in either place, is read as the current schema (``_a7_trace_as_current``);
        anything else is returned, or rejected, as it always was.
        """
        for envelope_json, obs_json, value in zip(
            df[_TRACE_KEY], df["trace_obs"], df["meta"], strict=True
        ):
            if not isinstance(value, dict):
                continue
            if envelope_json is None:
                if _TRACE_KEY in value:
                    value[_TRACE_KEY] = _a7_trace_as_current(value[_TRACE_KEY])
                continue
            obs = None if obs_json is None else json.loads(obs_json)
            envelope = _a7_trace_as_current(json.loads(envelope_json))
            value[_TRACE_KEY] = assemble(envelope, obs).to_dict()

    def _envelopes(self, df: pd.DataFrame) -> pd.Series:
        """Each row's envelope: decoded from the ``trace`` column where the part has one, and
        split out of ``meta`` at read time where it does not."""
        metas: Any = df["meta"] if "meta" in df.columns else [None] * len(df)
        out = [
            json.loads(envelope_json) if envelope_json is not None else _legacy_envelope(value)
            for envelope_json, value in zip(df[_TRACE_KEY], metas, strict=True)
        ]
        return pd.Series(out, index=df.index, dtype=object)

    def count(self, run_id: str) -> int:
        """The number of stored rows, summed from each part's Parquet footer. No row data is
        read: this is never ``len()`` of a narrow read. An unknown run raises ``StoreError``
        through ``manifest()``; a half-written ``.tmp`` part is not a part."""
        self.manifest(run_id)
        return sum(int(pq.read_metadata(p).num_rows) for p in self._parts(run_id))

    def tally(self, run_id: str) -> RunTally:
        """The run's rows counted by whether an outcome was stored.

        A projected read of the ``outcome`` and ``error`` columns of every part: never
        ``len()`` of a wider read, never a manifest field. ``config``, ``meta`` and
        ``backend_meta`` are projected away at the Parquet reader and never decoded, so a run
        whose JSON columns are unreadable still tallies.

        This reads row data, so it checks ``schema_version`` as ``read()`` does, where
        ``count()`` -- which reads footers only -- does not. An unknown run raises
        ``StoreError`` through ``manifest()``; a half-written ``.tmp`` part is not a part.

        A row with no outcome is errored whatever its ``error`` says: exactly the timeout mark
        is ``timed_out``, the infra prefix is ``infra``, and everything else is ``other`` --
        including a row a foreign writer produced with neither an outcome nor an error, which
        ``EpisodeRecord`` forbids and a Parquet part does not.
        """
        manifest = self.manifest(run_id)
        if manifest.schema_version != _SCHEMA_VERSION:
            raise SchemaMismatch(
                f"run {run_id!r} has schema_version {manifest.schema_version}, "
                f"this build reads {_SCHEMA_VERSION}"
            )
        table = self._read_table(run_id, columns=["outcome", "error"])
        outcomes = table.column("outcome").to_pylist()
        errors = table.column("error").to_pylist()
        with_outcome = timed_out = infra = 0
        for outcome, error in zip(outcomes, errors, strict=True):
            if outcome is not None:
                with_outcome += 1
            elif error == _TIMEOUT_MARK:
                timed_out += 1
            elif error is not None and error.startswith(_INFRA_MARK):
                infra += 1
        rows = len(outcomes)
        no_outcome = rows - with_outcome
        return RunTally(
            rows=rows,
            with_outcome=with_outcome,
            no_outcome=no_outcome,
            timed_out=timed_out,
            infra=infra,
            other=no_outcome - timed_out - infra,
        )

    def missing(
        self, run_id: str, expected: Iterable[tuple[str, int]]
    ) -> list[tuple[str, int]]:
        existing = self._existing_keys(run_id)
        return [(h, i) for h, i in expected if (str(h), int(i)) not in existing]
