"""The Store: where every episode is written and where every downstream module reads from."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from momus import __version__
from momus.episode import Episode


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
    ]
)
_JSON_COLUMNS = ("config", "meta", "backend_meta")


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


def _now_iso_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------- RunManifest ----------


@dataclass(frozen=True)
class RunManifest:
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
    momus_version: str = field(default_factory=lambda: __version__)
    schema_version: int = _SCHEMA_VERSION

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
            "momus_version": self.momus_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RunManifest:
        retain = d.get("retain_traces_for")
        return cls(
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
            momus_version=d.get("momus_version", __version__),
            schema_version=d.get("schema_version", _SCHEMA_VERSION),
        )


# ---------- EpisodeRecord ----------


@dataclass(frozen=True)
class EpisodeRecord:
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
    ) -> EpisodeRecord:
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
            meta={},
            error=error,
            wall_time=wall_time,
            backend_meta={} if backend_meta is None else dict(backend_meta),
        )


# ---------- Store ----------


class Store:
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
            if retain is not None and r.outcome not in retain:
                meta.pop(_TRACE_KEY, None)
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

    def _read_table(self, run_id: str, columns: list[str] | None = None) -> pa.Table:
        parts = self._parts(run_id)
        if not parts:
            table = _SCHEMA.empty_table()
            return table.select(columns) if columns is not None else table
        return pa.concat_tables(
            [pq.read_table(p, schema=_SCHEMA, columns=columns) for p in parts]
        )

    def _existing_keys(self, run_id: str) -> set[tuple[str, int]]:
        table = self._read_table(run_id, columns=["config_hash", "replicate_index"])
        hashes = table.column("config_hash").to_pylist()
        reps = table.column("replicate_index").to_pylist()
        return {(str(h), int(r)) for h, r in zip(hashes, reps, strict=True)}

    def read(self, run_id: str) -> pd.DataFrame:
        manifest = self.manifest(run_id)
        if manifest.schema_version != _SCHEMA_VERSION:
            raise SchemaMismatch(
                f"run {run_id!r} has schema_version {manifest.schema_version}, "
                f"this build reads {_SCHEMA_VERSION}"
            )
        df: pd.DataFrame = self._read_table(run_id).to_pandas()
        df = df.sort_values(["config_hash", "replicate_index"], kind="stable")
        df = df.reset_index(drop=True)
        for col in _JSON_COLUMNS:
            df[col] = pd.Series([json.loads(s) for s in df[col]], index=df.index, dtype=object)
        return df

    def missing(
        self, run_id: str, expected: Iterable[tuple[str, int]]
    ) -> list[tuple[str, int]]:
        existing = self._existing_keys(run_id)
        return [(h, i) for h, i in expected if (str(h), int(i)) not in existing]
