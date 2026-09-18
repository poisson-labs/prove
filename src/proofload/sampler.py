"""M2: produce the list of configs a sweep will run, typed per axis, as a SweepSpec.

The primitive is a list of dicts. ``grid``, ``sobol`` and ``scenarios`` are three ways to
make one, and ``+`` is how you combine them. M2 knows nothing about seeds, execution, or
results. Its one hard promise is determinism: the same inputs yield the same list in the
same order, every time, on every machine.

Two layers, both correct: ``grid`` keeps ``5`` as ``int`` so the user's rollout sees what
they wrote; ``config_hash`` treats ``5`` and ``5.0`` as one cell so the store does not
split them. ``SweepSpec.build`` deduplicates on the hash and keeps the first representation.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Literal

from scipy.stats import qmc

from proofload.capture import CaptureSpec
from proofload.chaos import ChaosSpec
from proofload.store import InvalidConfig, config_hash

AxisType = Literal["continuous", "categorical"]

_AXIS_TYPES: tuple[str, ...] = ("continuous", "categorical")
_TOOL_RELIABILITY_RATES: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20, 0.30)
_CAPTURE_FIELDS: tuple[str, ...] = ("instrument", "content", "max_observation_bytes", "max_spans")
_CHAOS_FIELDS: tuple[str, ...] = ("fault", "rate", "steps")


class SamplerError(Exception):
    """A sampler input cannot be turned into a config list or a SweepSpec."""


# ---------- normalization ----------


def _normalize(value: Any, path: str) -> Any:
    """Copy nested containers into plain dicts/lists/tuples; reject non-finite numbers."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise SamplerError(f"non-finite number at config{path}: {value!r}")
        return value
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            out[k] = _normalize(v, f"{path}.{k}")
        return out
    if isinstance(value, tuple):
        return tuple(_normalize(v, f"{path}[{i}]") for i, v in enumerate(value))
    if isinstance(value, list):
        return [_normalize(v, f"{path}[{i}]") for i, v in enumerate(value)]
    return value


def _jsonable(value: Any) -> Any:
    """Tuples become lists so ``to_dict()`` output survives ``json.dumps``."""
    if isinstance(value, Mapping):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _hash(config: Mapping[str, Any]) -> str:
    try:
        return config_hash(config)
    except InvalidConfig as exc:
        raise SamplerError(str(exc)) from exc


# ---------- samplers ----------


def grid(axes: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Cartesian product. Axis order = declaration order; the last axis varies fastest."""
    if not isinstance(axes, Mapping) or len(axes) == 0:
        raise SamplerError("grid needs at least one axis")
    keys = list(axes)
    columns: list[list[Any]] = []
    for key in keys:
        values = axes[key]
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise SamplerError(f"axis {key!r} must be a sequence of values")
        if len(values) == 0:
            raise SamplerError(f"axis {key!r} has no values")
        columns.append([_normalize(v, f".{key}") for v in values])
    return [dict(zip(keys, combo, strict=True)) for combo in product(*columns)]


def sobol(
    bounds: Mapping[str, tuple[float, float]], n: int, *, seed: int
) -> list[dict[str, Any]]:
    """n scrambled Sobol points scaled into bounds. n must be a power of 2."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or (n & (n - 1)) != 0:
        raise SamplerError(f"sobol needs n to be a power of 2 (1, 2, 4, 8, ...), got {n!r}")
    if len(bounds) == 0:
        raise SamplerError("sobol needs at least one bounded axis")
    keys = list(bounds)
    lows: list[float] = []
    highs: list[float] = []
    for key in keys:
        try:
            lo, hi = (float(x) for x in bounds[key])
        except (TypeError, ValueError) as exc:
            raise SamplerError(f"bounds for {key!r} must be a (low, high) pair") from exc
        if not (math.isfinite(lo) and math.isfinite(hi)) or lo > hi:
            raise SamplerError(f"bounds for {key!r} must be finite with low <= high")
        lows.append(lo)
        highs.append(hi)
    sampler = qmc.Sobol(d=len(keys), scramble=True, seed=seed)
    unit = sampler.random(n)
    scaled = qmc.scale(unit, lows, highs)
    return [
        {key: min(max(float(row[j]), lows[j]), highs[j]) for j, key in enumerate(keys)}
        for row in scaled
    ]


def scenarios(configs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize a hand-written list. Rejects non-mappings and non-finite numbers."""
    out: list[dict[str, Any]] = []
    for i, cfg in enumerate(configs):
        if not isinstance(cfg, Mapping):
            raise SamplerError(f"scenario {i} is not a mapping: {type(cfg).__name__}")
        normalized = _normalize(cfg, "")
        out.append(dict(normalized))
    return out


def infer_axis_types(configs: Sequence[Mapping[str, Any]]) -> dict[str, AxisType]:
    """Top-level keys only. All values numeric (not bool) -> continuous; otherwise categorical."""
    keys: dict[str, None] = {}
    for cfg in configs:
        for key in cfg:
            keys.setdefault(key, None)
    out: dict[str, AxisType] = {}
    for key in keys:
        if not all(key in cfg for cfg in configs):
            out[key] = "categorical"
            continue
        numeric = all(
            isinstance(cfg[key], (int, float)) and not isinstance(cfg[key], bool)
            for cfg in configs
        )
        out[key] = "continuous" if numeric else "categorical"
    return out


# ---------- SweepSpec ----------


def _checked_positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SamplerError(f"[capture].{name} must be an int >= 1, got {value!r}")
    return value


def _positive_int(table: Mapping[str, Any], name: str, default: int) -> int:
    return _checked_positive_int(table.get(name, default), name)


def _optional_positive_int(table: Mapping[str, Any], name: str) -> int | None:
    """``max_spans``'s parse: absent is ``None`` (D6), present is an int >= 1.

    A sibling rather than a widened ``_positive_int``, because ``_positive_int`` called with
    ``default=None`` falls straight into its own ``not isinstance(value, int)`` and raises on
    the absent case -- and widening it would change the reachable error set for
    ``max_observation_bytes``, whose message it shares.
    """
    return None if name not in table else _checked_positive_int(table[name], name)


def _capture_table(table: Any) -> CaptureSpec | None:
    """The optional ``[capture]`` table of a sweep file, as a ``CaptureSpec``.

    An empty ``instrument`` list is a request, not a no-op: a target that emits spans through
    the OpenTelemetry API itself needs no instrumentor.
    """
    if table is None:
        return None
    if not isinstance(table, Mapping):
        raise SamplerError("[capture] must be a table")
    unknown = sorted(set(table) - set(_CAPTURE_FIELDS))
    if unknown:
        raise SamplerError(
            f"[capture] has unknown field(s): {', '.join(unknown)}; "
            f"the fields are {', '.join(_CAPTURE_FIELDS)}"
        )
    instrument = table.get("instrument", [])
    if not isinstance(instrument, list) or not all(isinstance(n, str) for n in instrument):
        raise SamplerError("[capture].instrument must be a list of instrumentor names")
    content = table.get("content", False)
    if not isinstance(content, bool):
        raise SamplerError(f"[capture].content must be true or false, got {content!r}")
    defaults = CaptureSpec()
    return CaptureSpec(
        instrument=tuple(instrument),
        content=content,
        max_observation_bytes=_positive_int(
            table, "max_observation_bytes", defaults.max_observation_bytes
        ),
        max_spans=_optional_positive_int(table, "max_spans"),
    )


def _chaos_table(table: Any) -> ChaosSpec | None:
    """The optional ``[chaos]`` table of a sweep file, as a ``ChaosSpec``.

    Validated by field name the way ``[capture]`` is, and -- like ``[capture]`` -- it rides
    the spec without entering ``to_dict()``: an injection request is not what makes two
    sweeps the same sweep, and keeping it out of the sweep's identity is what lets the
    faulted arm and the ``none`` arm derive the same seeds and pair under ``diff``.

    The fault *name* is not checked here. ``chaos.install`` owns the vocabulary and refuses
    an unknown name before the run exists; a second gate in the sampler would be a second
    copy of the catalogue's membership rule.
    """
    if table is None:
        return None
    if not isinstance(table, Mapping):
        raise SamplerError("[chaos] must be a table")
    unknown = sorted(set(table) - set(_CHAOS_FIELDS))
    if unknown:
        raise SamplerError(
            f"[chaos] has unknown field(s): {', '.join(unknown)}; "
            f"the fields are {', '.join(_CHAOS_FIELDS)}"
        )
    fault = table.get("fault", "none")
    if not isinstance(fault, str) or not fault:
        raise SamplerError(f"[chaos].fault must be a non-empty fault name, got {fault!r}")
    rate = table.get("rate", 1.0)
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0.0 <= rate <= 1.0:
        raise SamplerError(f"[chaos].rate must be a number in [0, 1], got {rate!r}")
    steps = table.get("steps", [])
    if not isinstance(steps, list) or not all(isinstance(name, str) for name in steps):
        raise SamplerError(f"[chaos].steps must be a list of step names, got {steps!r}")
    return ChaosSpec(fault=fault, rate=float(rate), steps=tuple(steps))


@dataclass(frozen=True)
class SweepSpec:
    configs: tuple[dict[str, Any], ...]
    axis_types: Mapping[str, AxisType]
    replicates: int
    target_id: str
    t_unit: str
    retain_traces_for: tuple[str, ...] | None = None
    duplicates_dropped: int = 0
    #: The ``[capture]`` table, when the sweep file has one. It rides the spec but is
    #: deliberately absent from ``to_dict()``: that dict is the sweep's identity in
    #: ``manifest.environment["sweep"]``, and asking for a trace is not part of what makes two
    #: sweeps the same sweep. The manifest records the request at ``environment["capture"]``.
    capture: CaptureSpec | None = None
    #: The ``[chaos]`` table, when the sweep file has one. It rides the spec and is absent
    #: from ``to_dict()`` for the same reason ``capture`` is, and for one more: the whole of
    #: D2 is that an injected fault must not touch ``config_hash``, because that is what
    #: ``derive_seed`` reads and what makes two arms the same episode at the same seed.
    chaos: ChaosSpec | None = None

    @classmethod
    def build(
        cls,
        configs: Sequence[Mapping[str, Any]],
        *,
        replicates: int,
        target_id: str,
        t_unit: str,
        axis_types: Mapping[str, AxisType] | None = None,
        retain_traces_for: Sequence[str] | None = None,
        capture: CaptureSpec | None = None,
        chaos: ChaosSpec | None = None,
    ) -> SweepSpec:
        if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 1:
            raise SamplerError(f"replicates must be an int >= 1, got {replicates!r}")
        if not isinstance(target_id, str) or not target_id:
            raise SamplerError("target_id must be a non-empty str")
        if not isinstance(t_unit, str) or not t_unit:
            raise SamplerError("t_unit must be a non-empty str")
        normalized = scenarios(configs)
        if not normalized:
            raise SamplerError("configs must not be empty")

        survivors: dict[str, dict[str, Any]] = {}
        for cfg in normalized:
            survivors.setdefault(_hash(cfg), cfg)
        kept = tuple(survivors.values())
        dropped = len(normalized) - len(kept)

        inferred = infer_axis_types(kept)
        if axis_types is not None:
            present = {key for cfg in kept for key in cfg}
            for key, kind in axis_types.items():
                if key not in present:
                    raise SamplerError(f"axis_types names {key!r}, which no config carries")
                if kind not in _AXIS_TYPES:
                    raise SamplerError(f"axis_types[{key!r}] must be one of {_AXIS_TYPES}")
                inferred[key] = kind

        retain: tuple[str, ...] | None = None
        if retain_traces_for is not None:
            if isinstance(retain_traces_for, str):
                raise SamplerError("retain_traces_for must be a sequence of outcome names")
            retain = tuple(str(o) for o in retain_traces_for)

        return cls(
            configs=kept,
            axis_types=inferred,
            replicates=replicates,
            target_id=target_id,
            t_unit=t_unit,
            retain_traces_for=retain,
            duplicates_dropped=dropped,
            capture=capture,
            chaos=chaos,
        )

    @classmethod
    def load(cls, path: Path | str) -> SweepSpec:
        """Load a TOML sweep file.

        Top-level fields, ``[axes.*]`` tables in file order, optional ``[[scenarios]]``.
        """
        file = Path(path)
        try:
            with file.open("rb") as fh:
                data = tomllib.load(fh)
        except OSError as exc:
            raise SamplerError(f"cannot read sweep file {file}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise SamplerError(f"invalid TOML in {file}: {exc}") from exc

        for field in ("target_id", "t_unit", "replicates"):
            if field not in data:
                raise SamplerError(f"sweep file {file.name} is missing required field {field!r}")

        axes = data.get("axes")
        if not isinstance(axes, Mapping) or len(axes) == 0:
            raise SamplerError(f"sweep file {file.name} has no [axes.*] tables")
        values_by_axis: dict[str, list[Any]] = {}
        axis_types: dict[str, AxisType] = {}
        for name, table in axes.items():
            if not isinstance(table, Mapping):
                raise SamplerError(f"axis {name!r} must be a table with 'type' and 'values'")
            if "type" not in table:
                raise SamplerError(f"axis {name!r} is missing required field 'type'")
            kind = table["type"]
            if kind not in _AXIS_TYPES:
                raise SamplerError(
                    f"axis {name!r} has type {kind!r}; expected one of {_AXIS_TYPES}"
                )
            if "values" not in table:
                raise SamplerError(f"axis {name!r} is missing required field 'values'")
            values = table["values"]
            if not isinstance(values, list) or len(values) == 0:
                raise SamplerError(f"axis {name!r} needs a non-empty 'values' list")
            values_by_axis[name] = values
            axis_types[name] = "continuous" if kind == "continuous" else "categorical"

        configs = grid(values_by_axis)
        extra = data.get("scenarios", [])
        if not isinstance(extra, list):
            raise SamplerError("scenarios must be an array of tables")
        configs += scenarios(extra)

        retain = data.get("retain_traces_for")
        if retain is not None and (
            not isinstance(retain, list) or not all(isinstance(o, str) for o in retain)
        ):
            raise SamplerError("retain_traces_for must be a list of outcome names")

        return cls.build(
            configs,
            replicates=data["replicates"],
            target_id=data["target_id"],
            t_unit=data["t_unit"],
            axis_types=axis_types,
            retain_traces_for=retain,
            capture=_capture_table(data.get("capture")),
            chaos=_chaos_table(data.get("chaos")),
        )

    def cells(self) -> list[str]:
        return [_hash(cfg) for cfg in self.configs]

    def total_rollouts(self) -> int:
        return len(self.configs) * self.replicates

    def to_dict(self) -> dict[str, Any]:
        return {
            "configs": [_jsonable(cfg) for cfg in self.configs],
            "axis_types": dict(self.axis_types),
            "replicates": self.replicates,
            "target_id": self.target_id,
            "t_unit": self.t_unit,
            "retain_traces_for": (
                None if self.retain_traces_for is None else list(self.retain_traces_for)
            ),
            "duplicates_dropped": self.duplicates_dropped,
        }


# ---------- presets ----------


def preset(
    name: Literal["tool-reliability"], *, tasks: Sequence[Any], **overrides: Any
) -> list[dict[str, Any]]:
    """tool-reliability: tasks (categorical) x tool_fail_rate (continuous)."""
    if name != "tool-reliability":
        raise SamplerError(f"unknown preset {name!r}; available: 'tool-reliability'")
    if isinstance(tasks, str) or len(tasks) == 0:
        raise SamplerError("tool-reliability needs a non-empty sequence of tasks")
    rates = overrides.pop("tool_fail_rate", _TOOL_RELIABILITY_RATES)
    if overrides:
        raise SamplerError(f"unknown overrides for tool-reliability: {sorted(overrides)}")
    if isinstance(rates, str) or len(rates) == 0:
        raise SamplerError("tool_fail_rate override must be a non-empty sequence")
    return grid({"task_id": list(tasks), "tool_fail_rate": list(rates)})
