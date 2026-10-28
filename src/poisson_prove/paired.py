"""Paired replay: the declaration, the canonical request, the pair assertion, and the per-cut
paired analysis.

Two stored arms are only a pair if they were *the same request twice*, and this module says so
before anything compares a number. The declaration is loaded whole and refuses what it does not
know; the request is canonicalised without ever passing a number through ``float``; every
matched key is either eligible or excluded with one named cause, and the counts reconcile. That
is the first part of this module: the pair assertion.

The second part is ``analyse``: it takes a ``PairAssertion`` and nothing else, and answers one
question per declared cut -- did the binary action at that cut reproduce? The action is ``value
>= threshold`` on ``Decimal`` from the stored literal; the 2x2, the flip rate and the net swing
are paired quantities; the pooled interval is the percentile cluster bootstrap over items, with
its declared fallback and its design effect; McNemar is the arm-order check and nothing
downstream reads it; no statistic crosses a cut; and the outcome fires only against a declared
floor.

The third part is three more readers and the rendering. ``windows`` reads the timing that rides
on ``pairs`` off the trace envelope and never off ``wall_time``; ``cost`` sums the provider's own
recorded usage per phase, per sweep and per arm, prices it only against a declared price and
gates the cap between sweeps; and ``replicates`` reads a sweep of ``k = 2 + len(more)`` arms --
of which a pair is the case ``k = 2`` -- and answers, per cut and under both action rules, how
often all ``j`` calls agreed and how often two sweeps' ``j``-call majorities agreed, each with
the same item-clustered interval through the one ``_cluster_bootstrap``. The four rendered
sections are folded into the strings ``report.py`` renders, and ``report.py`` itself is not
edited.

The canonicaliser is the part where a silent bug would be invisible and total. A JSON round-trip
through Python's ``float`` is the obvious implementation and it is wrong: it makes the digest
blind to exactly the difference the assertion exists to catch -- a ``top_p`` written ``0.95``
against one written ``0.95000000000000001``, a ``max_tokens`` of ``1`` against ``1.0``. Numbers
are parsed into ``_Literal``, which keeps the text the wire carried, and emitted verbatim.
"""

from __future__ import annotations

import dataclasses
import hashlib
import html as _html
import itertools
import json
import math
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.stats import beta as _beta

from poisson_prove.diff import _discordant, _mcnemar
from poisson_prove.store import Store
from poisson_prove.trace import Trace, TraceValidationError


class PairedError(Exception):
    """Every refusal this module makes."""


class DeclarationError(PairedError):
    """The declaration is not loadable, or it does not describe the stored runs."""


class NotAssertable(PairedError):
    """A run-level fact blocks the assertion. It is never a property of one pair."""


class NoEligiblePairs(PairedError):
    """The assertion left a cut with nothing. The assertion defines it; ``analyse`` raises it."""


# ---------- the declaration ----------


_WORDS: tuple[str, ...] = ("asserted", "not_recorded")
_COMPARISONS: tuple[str, ...] = ("gt", "ge")
_OTHER_COMPARISON: dict[str, str] = {"gt": "ge", "ge": "gt"}
_CUT_KEYS = frozenset({"name", "threshold", "comparison"})
_SWEEP_KEYS = frozenset({"name", "a", "b", "more"})


@dataclass(frozen=True)
class Cut:
    name: str
    threshold: Decimal  # from a decimal literal; never parsed through float
    comparison: Literal["gt", "ge"]  # the action rule, declared with no default


@dataclass(frozen=True)
class SweepPair:
    name: str  # the replication's label, e.g. "sweep-1"
    a: str  # run id of arm A
    b: str  # run id of arm A'
    more: tuple[str, ...] = ()  # arms 3..k in declared order; k = 2 + len(more)

    def __post_init__(self) -> None:
        object.__setattr__(self, "more", tuple(self.more))

    @property
    def arms(self) -> tuple[str, ...]:
        """``(a, b, *more)``: the declared order, and the only order a prefix is read in."""
        return (self.a, self.b, *self.more)


@dataclass(frozen=True)
class Declaration:
    """Everything the module is allowed to know, fixed before the run."""

    # what is measured
    value_key: str
    cluster_key: str
    stratum_key: str
    cuts: tuple[Cut, ...]
    sweeps: tuple[SweepPair, ...]

    # what a pair is
    request_span: str
    model_key: str
    model_pin: str
    exemptions: tuple[str, ...]
    headers: Literal["asserted", "not_recorded"]
    retries: Literal["asserted", "not_recorded"]

    # how it is estimated -- no defaults: an estimator's parameters are declared, never assumed
    bootstrap_b: int
    bootstrap_seed: int
    floor: Decimal | None = None

    # what is described
    declared_window_s: float | None = None
    conditioning: str | None = None

    # what it cost
    price_per_input_token: Decimal | None = None
    token_cap: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cuts", tuple(self.cuts))
        object.__setattr__(self, "sweeps", tuple(self.sweeps))
        object.__setattr__(self, "exemptions", tuple(self.exemptions))
        _check_replicates(self.sweeps)

    @classmethod
    def from_toml(cls, path: str | Path) -> Declaration:
        """Load a declaration file whole. Every refusal here is a ``DeclarationError``: an
        unknown key at any level, a missing required field, a cut without a threshold, two cuts
        under one name, a literal field outside its two words, and an exemption that the
        declaration itself calls a body field by naming it ``model_key``."""
        return cls(**_read_toml(Path(path)))

    @property
    def digest(self) -> str:
        """``sha256`` over the canonical serialisation of every field, ``exemptions`` included.
        A function of the declaration alone: not of the file's key order, its comments or its
        name. A widened exemption list cannot be passed off as the pre-registered one."""
        return hashlib.sha256(self._canonical().encode("utf-8")).hexdigest()

    def _canonical(self) -> str:
        payload: dict[str, Any] = {
            "value_key": self.value_key,
            "cluster_key": self.cluster_key,
            "stratum_key": self.stratum_key,
            "cuts": [
                {"name": c.name, "threshold": _text(c.threshold), "comparison": c.comparison}
                for c in self.cuts
            ],
            # ``more`` is in the digest: a widened set of calls cannot be passed off as the
            # pre-registered one, and an absent ``more`` is the empty one.
            "sweeps": [
                {"name": s.name, "a": s.a, "b": s.b, "more": list(s.more)} for s in self.sweeps
            ],
            "request_span": self.request_span,
            "model_key": self.model_key,
            "model_pin": self.model_pin,
            # Verbatim, not sorted: the order of ``exemptions`` is not pinned by the format,
            # and two different *sets* must never share a digest whatever the spelling.
            "exemptions": list(self.exemptions),
            "headers": self.headers,
            "retries": self.retries,
            "bootstrap_b": self.bootstrap_b,
            "bootstrap_seed": self.bootstrap_seed,
            "floor": _text(self.floor),
            "declared_window_s": self.declared_window_s,
            "conditioning": self.conditioning,
            "price_per_input_token": _text(self.price_per_input_token),
            "token_cap": self.token_cap,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _text(value: Decimal | None) -> str | None:
    """A ``Decimal`` as the literal it was read from, so ``0.30`` and ``0.3`` stay two spellings
    and neither is a binary double."""
    return None if value is None else str(value)


def _check_replicates(sweeps: Sequence[SweepPair]) -> None:
    """Checked in the constructor and so at load too. Every declared sweep carries the same ``k``,
    because ``agree@k`` computed at two different ``k`` is two estimands under one name; and no
    run id repeats inside one sweep's arms, because a call is not its own replicate."""
    for sweep in sweeps:
        repeated = sorted({run_id for run_id in sweep.arms if sweep.arms.count(run_id) > 1})
        if repeated:
            raise DeclarationError(
                f"sweep {sweep.name!r} names {', '.join(repeated)} more than once among its "
                "arms; a call is not its own replicate"
            )
    ks = {sweep.name: 2 + len(sweep.more) for sweep in sweeps}
    if len(set(ks.values())) > 1:
        described = ", ".join(f"{name} at k = {k}" for name, k in ks.items())
        raise DeclarationError(
            f"every declared sweep must carry the same replicate count; this declaration mixes "
            f"{described}. agree@k at two different k is two estimands under one name."
        )


def _field_specs() -> dict[str, dataclasses.Field[Any]]:
    return {f.name: f for f in dataclasses.fields(Declaration)}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle, parse_float=Decimal)
    except OSError as exc:
        raise DeclarationError(f"{path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise DeclarationError(f"{path}: not readable as TOML: {exc}") from exc

    specs = _field_specs()
    unknown = sorted(set(raw) - set(specs))
    if unknown:
        raise DeclarationError(
            f"{path}: unknown key(s) in the declaration: {', '.join(unknown)}. "
            "Nothing in a declaration is silently ignored."
        )
    missing = sorted(
        name
        for name, spec in specs.items()
        if spec.default is dataclasses.MISSING and name not in raw
    )
    if missing:
        raise DeclarationError(
            f"{path}: the declaration is missing {', '.join(missing)}. "
            "There is no default for any of them."
        )

    out: dict[str, Any] = {
        "cuts": _read_cuts(path, raw["cuts"]),
        "sweeps": _read_sweeps(path, raw["sweeps"]),
        "value_key": _str(path, raw, "value_key"),
        "cluster_key": _str(path, raw, "cluster_key"),
        "stratum_key": _str(path, raw, "stratum_key"),
        "request_span": _str(path, raw, "request_span"),
        "model_key": _str(path, raw, "model_key"),
        "model_pin": _str(path, raw, "model_pin"),
        "exemptions": _read_exemptions(path, raw["exemptions"]),
        "headers": _word(path, raw, "headers"),
        "retries": _word(path, raw, "retries"),
        "bootstrap_b": _int(path, raw, "bootstrap_b"),
        "bootstrap_seed": _int(path, raw, "bootstrap_seed"),
        "floor": None if "floor" not in raw else _decimal(path, raw, "floor"),
        "declared_window_s": (
            None if "declared_window_s" not in raw else _float(path, raw, "declared_window_s")
        ),
        "conditioning": None if "conditioning" not in raw else _str(path, raw, "conditioning"),
        "price_per_input_token": (
            None
            if "price_per_input_token" not in raw
            else _decimal(path, raw, "price_per_input_token")
        ),
        "token_cap": None if "token_cap" not in raw else _int(path, raw, "token_cap"),
    }

    model_key = out["model_key"].lower()
    for name in out["exemptions"]:
        if name.lower() == model_key:
            raise DeclarationError(
                f"{path}: exemption {name!r} is the declaration's own model_key, which it calls "
                "a request-body field. An exemption is a header or a transport identifier."
            )
    return out


def _read_cuts(path: Path, tables: Any) -> tuple[Cut, ...]:
    if not isinstance(tables, list):
        raise DeclarationError(f"{path}: cuts must be a list of [[cuts]] tables")
    cuts: list[Cut] = []
    for table in tables:
        if not isinstance(table, dict):
            raise DeclarationError(f"{path}: a cut must be a [[cuts]] table")
        extra = sorted(set(table) - _CUT_KEYS)
        if extra:
            raise DeclarationError(f"{path}: unknown key(s) in a cut: {', '.join(extra)}")
        for key in sorted(_CUT_KEYS):
            if key not in table:
                raise DeclarationError(f"{path}: a cut is missing {key}: {table}")
        cuts.append(
            Cut(
                name=_str(path, table, "name"),
                threshold=_decimal(path, table, "threshold"),
                comparison=_comparison(path, table),
            )
        )
    names = [c.name for c in cuts]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    if duplicated:
        raise DeclarationError(f"{path}: cut names must be unique; {', '.join(duplicated)} repeat")
    return tuple(cuts)


def _read_sweeps(path: Path, tables: Any) -> tuple[SweepPair, ...]:
    if not isinstance(tables, list):
        raise DeclarationError(f"{path}: sweeps must be a list of [[sweeps]] tables")
    sweeps: list[SweepPair] = []
    for table in tables:
        if not isinstance(table, dict):
            raise DeclarationError(f"{path}: a sweep must be a [[sweeps]] table")
        extra = sorted(set(table) - _SWEEP_KEYS)
        if extra:
            raise DeclarationError(f"{path}: unknown key(s) in a sweep: {', '.join(extra)}")
        for key in sorted(_SWEEP_KEYS - {"more"}):
            if key not in table:
                raise DeclarationError(f"{path}: a sweep is missing {key}: {table}")
        # ``more`` is optional and an absent ``more`` is the empty one.
        more = table.get("more", [])
        if not isinstance(more, list) or any(not isinstance(v, str) for v in more):
            raise DeclarationError(f"{path}: more must be a list of run ids, got {more!r}")
        sweeps.append(
            SweepPair(
                name=_str(path, table, "name"),
                a=_str(path, table, "a"),
                b=_str(path, table, "b"),
                more=tuple(more),
            )
        )
    names = [s.name for s in sweeps]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    if duplicated:
        raise DeclarationError(
            f"{path}: sweep names must be unique; {', '.join(duplicated)} repeat"
        )
    return tuple(sweeps)


def _read_exemptions(path: Path, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise DeclarationError(f"{path}: exemptions must be a list of names, got {value!r}")
    return tuple(value)


def _str(path: Path, table: Mapping[str, Any], key: str) -> str:
    value = table[key]
    if not isinstance(value, str):
        raise DeclarationError(f"{path}: {key} must be a string, got {value!r}")
    return value


def _comparison(path: Path, table: Mapping[str, Any]) -> Literal["gt", "ge"]:
    """``comparison`` is ``gt`` or ``ge`` and nothing else, as ``headers`` and
    ``retries`` take only their two words."""
    value = table["comparison"]
    if value not in _COMPARISONS:
        raise DeclarationError(
            f"{path}: a cut's comparison takes {' or '.join(_COMPARISONS)} and nothing else, "
            f"got {value!r}"
        )
    return cast(Literal["gt", "ge"], value)


def _word(path: Path, table: Mapping[str, Any], key: str) -> Any:
    value = table[key]
    if value not in _WORDS:
        raise DeclarationError(
            f"{path}: {key} takes {' or '.join(_WORDS)} and nothing else, got {value!r}"
        )
    return value


def _int(path: Path, table: Mapping[str, Any], key: str) -> int:
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise DeclarationError(f"{path}: {key} must be an integer, got {value!r}")
    return value


def _float(path: Path, table: Mapping[str, Any], key: str) -> float:
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, float)):
        raise DeclarationError(f"{path}: {key} must be a number, got {value!r}")
    return float(value)


def _decimal(path: Path, table: Mapping[str, Any], key: str) -> Decimal:
    """A number literal reaches ``Decimal`` from its text -- ``tomllib``'s ``parse_float`` has
    already built it -- so a threshold longer than a double holds survives the load and no
    threshold is ever the binary double nearest its literal."""
    value = table[key]
    if isinstance(value, bool):
        raise DeclarationError(f"{path}: {key} must be a number, got {value!r}")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise DeclarationError(f"{path}: {key} must be a number literal, got {value!r}")


# ---------- canonicalisation and the pair ----------


class _Literal(str):
    """A JSON number, held as the text the wire carried. ``str`` so the decoder can build it and
    so nothing downstream can accidentally round it; distinguishable from a JSON string, which
    is a plain ``str``, so ``{"k": "1"}`` and ``{"k": 1}`` never canonicalise alike."""

    __slots__ = ()


_DECODER = json.JSONDecoder(parse_float=_Literal, parse_int=_Literal, parse_constant=_Literal)
_ABSENT: Any = object()


def canonical_request(body: str | bytes) -> bytes:
    """The request body as one comparable string of bytes: keys sorted, insignificant whitespace
    removed, UTF-8, array order kept, and **every number emitted verbatim as stored**.

    Re-ordering keys or re-indenting does not move these bytes; changing any value byte does.
    ``ValueError`` when the text is not a JSON object.
    """
    text = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body
    parsed = _DECODER.decode(text)
    if not isinstance(parsed, dict):
        raise ValueError("a request body canonicalises only as a JSON object")
    return _emit(parsed).encode("utf-8")


def _emit(value: Any) -> str:
    if isinstance(value, _Literal):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, dict):
        inner = ",".join(
            f"{json.dumps(k, ensure_ascii=False)}:{_emit(v)}"
            for k, v in sorted(value.items(), key=lambda kv: kv[0])
        )
        return "{" + inner + "}"
    if isinstance(value, list):
        return "[" + ",".join(_emit(v) for v in value) + "]"
    raise ValueError(f"a request body holds no {type(value).__name__}")


def request_digest(
    body: str | bytes,
    *,
    target: Mapping[str, str],
    headers: Mapping[str, str],
    exemptions: Sequence[str],
) -> str:
    """``sha256`` over the canonicalised body, the target, and every header not exempted.

    Header names match case-insensitively, in ``exemptions`` as in the recorded name, so an
    exempted header moves nothing whatever its spelling or its value. Dropping the exemption,
    changing an unexempted header, the URL, the method or one body byte each move the digest,
    and each moves it somewhere different.
    """
    exempt = {name.lower() for name in exemptions}
    payload = {
        "body": canonical_request(body).decode("utf-8"),
        "target": {key: target[key] for key in sorted(target)},
        "headers": {
            name.lower(): value
            for name, value in sorted(headers.items(), key=lambda kv: kv[0].lower())
            if name.lower() not in exempt
        },
    }
    serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PairAssertion:
    declaration: Declaration
    pairs: pd.DataFrame  # one row per eligible pair
    excluded: pd.DataFrame  # one row per ineligible pair, with its cause
    environment: Mapping[str, Any]  # per-arm identity, compared and recorded
    counts: Mapping[str, Any]  # per cut, per arm, per cause

    def to_json(self) -> str:
        payload = {
            "declaration_digest": self.declaration.digest,
            "declaration": _jsonable(_declaration_payload(self.declaration)),
            "environment": _jsonable(self.environment),
            "pairs": _jsonable(self.pairs.to_dict("records")),
            "excluded": _jsonable(self.excluded.to_dict("records")),
            "counts": _jsonable(self.counts),
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)


def _declaration_payload(declaration: Declaration) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for spec in dataclasses.fields(declaration):
        value = getattr(declaration, spec.name)
        if spec.name in ("cuts", "sweeps"):
            out[spec.name] = [dataclasses.asdict(item) for item in value]
        else:
            out[spec.name] = value
    return out


def _jsonable(value: Any) -> Any:
    if isinstance(value, _Literal):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, float)):
        return value
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        # A numpy scalar out of a frame column: json has no writer for one.
        return _jsonable(value.item())
    if isinstance(value, int):
        return int(value)
    return str(value)


# ---------- the assertion ----------


_CAUSES: tuple[str, ...] = (
    "unmatched",
    "errored",
    "no_request_span",
    "retry_or_multicall",
    "malformed_body",
    "model_pin",
    "body_field_absent",
    "body",
    "target",
    "header",
    "value_missing",
    "value_out_of_range",
)
_ARMS: tuple[str, ...] = ("a", "b", "both")
_NS = 1_000_000_000
_HEADER_PREFIX = "http.request.header."
_TARGET_KEYS: tuple[str, ...] = ("url.full", "http.request.method")
_PAIRS_COLUMNS: tuple[str, ...] = (
    "sweep",
    "cut",
    "cluster",
    "config_hash",
    "replicate_index",
    "request_digest",
    "exemptions_exercised",
    "value_a",
    "value_b",
)
_EXCLUDED_COLUMNS: tuple[str, ...] = (
    "sweep",
    "cut",
    "cluster",
    "config_hash",
    "replicate_index",
    "cause",
    "arm",
    "detail",
)
_ZERO = Decimal(0)
_ONE = Decimal(1)


@dataclass(frozen=True)
class _Row:
    """One stored episode, read once, with everything the assertion asks of it."""

    sweep: str
    arm: str
    key: tuple[str, int]
    cluster: Any
    cut: Any
    seed: int
    error: str | None
    meta: Mapping[str, Any]
    spans: tuple[Any, ...]  # the spans matching ``request_span``, in trace order


def assert_pairs(store: Store, declaration: Declaration) -> PairAssertion:
    """Assert that each replicate set of stored rows was the same request ``k`` times.

    The order of the refusals is the order of what they are about. A declaration that does not
    describe these runs -- strata that overlap, an exemption that names a body field -- is a
    ``DeclarationError``. A fact about the *run* that cannot be asserted -- the arms' manifests
    disagreeing, a header identity with nothing recorded to assert it on, a retry setting the
    manifest is silent about, one row's seed moving -- is a ``NotAssertable``, never a per-pair
    exclusion. Everything left is per set: eligible, or excluded with one named cause, counted,
    and never repaired.

    A sweep is ``k = 2 + len(more)`` arms, labelled ``a``, ``b``, ``"3"`` .. ``"k"`` in the
    declared order and no other. A set is matched across all ``k`` arms on
    ``(config_hash, replicate_index)`` and is eligible only when every one of its rows is: all
    ``k``, or none. The ``k`` values ride on ``pairs`` as ``value_a``, ``value_b``,
    ``value_3`` .. and the request span's two timestamps as ``start_ns_<label>`` and
    ``end_ns_<label>`` after them, ``None`` where the span has none; at ``k = 2`` the frame's
    first nine columns are the pair-only frame's columns, unchanged.

    A set that is not whole is excluded from the k-metrics with its cause and the failing arm,
    and its declared pair is judged on arms ``a`` and ``b`` alone: when those two are an
    eligible pair the set stays on ``pairs`` with ``None`` for every value and stamp of arms
    ``3..k``, so the pair analysis counts it and ``replicates`` does not.
    """
    arm_labels = _arm_labels(declaration)
    arms = {
        (sweep.name, label): _read_arm(store, run_id, sweep.name, label, declaration)
        for sweep in declaration.sweeps
        for label, run_id in zip(arm_labels, sweep.arms, strict=True)
    }
    _check_strata(arms.values(), declaration)
    _check_exemptions(arms.values(), declaration)
    environment = _environment(store, declaration)
    _check_seeds(arms, declaration, arm_labels)

    value_columns = _value_columns(arm_labels)
    timing_columns = _timing_columns(arm_labels)
    pairs: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    exercised: dict[str, int] = {name.lower(): 0 for name in declaration.exemptions}
    keys_by_cut: dict[Any, int] = {}
    for sweep in declaration.sweeps:
        by_label = {label: arms[(sweep.name, label)] for label in arm_labels}
        union: set[tuple[str, int]] = set()
        for rows in by_label.values():
            union |= set(rows)
        for key in sorted(union):
            holders = [label for label in arm_labels if key in by_label[label]]
            lacking = [label for label in arm_labels if key not in by_label[label]]
            row = by_label[holders[0]][key]
            keys_by_cut[row.cut] = keys_by_cut.get(row.cut, 0) + 1
            held = [by_label[label][key] for label in holders]
            verdict: _Verdict | None
            if lacking:
                # ``arm`` is read as the first arm, in declared order, that holds the key --
                # and, past a pair, ``detail`` names every arm that lacks it.
                holding = f"arm {holders[0]}" if len(holders) == 1 else "arms " + ", ".join(holders)
                detail = f"the key is in {holding} of {sweep.name} only"
                if len(arm_labels) > 2:
                    detail += "; absent from " + ", ".join(f"arm {label}" for label in lacking)
                excluded.append(_excluded_row(row, "unmatched", holders[0], detail))
                verdict = (
                    _declared_pair(held[:2], arm_labels, declaration)
                    if holders[:2] == list(arm_labels[:2])
                    else None
                )
            else:
                verdict = _judge(held, arm_labels, declaration)
                if verdict.cause is not None:
                    excluded.append(_excluded_row(row, verdict.cause, verdict.arm, verdict.detail))
                    verdict = _declared_pair(held[:2], arm_labels, declaration)
            if verdict is None:
                continue
            for name in verdict.exercised:
                exercised[name] += 1
            pairs.append(
                {
                    "sweep": sweep.name,
                    "cut": row.cut,
                    "cluster": row.cluster,
                    "config_hash": key[0],
                    "replicate_index": key[1],
                    "request_digest": verdict.digest,
                    "exemptions_exercised": verdict.exercised,
                    **dict(zip(value_columns, verdict.values, strict=True)),
                    **dict(zip(timing_columns, verdict.timing, strict=True)),
                }
            )

    order = ("sweep", "cut", "cluster", "config_hash", "replicate_index")
    pairs.sort(key=lambda r: tuple(str(r[k]) for k in order))
    excluded.sort(key=lambda r: tuple(str(r[k]) for k in order))
    counts = _counts(pairs, excluded, keys_by_cut, declaration, exercised, arm_labels)
    frame = _frame(pairs, (*_PAIRS_COLUMNS, *value_columns[2:], *timing_columns))
    for column in timing_columns:
        # Whole timestamps or ``None``, never a float ``NaN`` standing in for an absent stamp.
        # Read off the rows and not off the frame: a column holding a ``None`` beside whole
        # numbers is float64 in the frame, and a nanosecond stamp does not survive a float.
        frame[column] = pd.Series(
            [_stamp(r[column]) for r in pairs], index=frame.index, dtype=object
        )
    return PairAssertion(
        declaration=declaration,
        pairs=frame,
        excluded=_frame(excluded, _EXCLUDED_COLUMNS),
        environment=environment,
        counts=counts,
    )


def _declared_pair(
    rows: Sequence[_Row], arm_labels: Sequence[str], declaration: Declaration
) -> _Verdict | None:
    """A set excluded from the k-metrics still carries its declared pair when arms ``a`` and
    ``b`` are an eligible pair on their own: judged on those two
    rows alone, the values and stamps of arms ``3..k`` padded with ``None``. At ``k = 2`` the set
    is the pair, so there is nothing left to keep."""
    k = len(arm_labels)
    if k == 2:
        return None
    verdict = _judge(rows[:2], arm_labels[:2], declaration)
    if verdict.cause is not None:
        return None
    return dataclasses.replace(
        verdict,
        values=(*verdict.values, *(None,) * (k - 2)),
        timing=(*verdict.timing, *(None,) * (2 * (k - 2))),
    )


def _arm_labels(declaration: Declaration) -> tuple[str, ...]:
    """``a``, ``b``, then ``"3"`` .. ``"k"``: the arms in ``more`` are labelled by their 1-based
    position in the declared order. Every sweep carries the same ``k``."""
    k = 2 + len(declaration.sweeps[0].more) if declaration.sweeps else 2
    return ("a", "b", *(str(i) for i in range(3, k + 1)))


def _value_columns(arm_labels: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"value_{label}" for label in arm_labels)


def _timing_columns(arm_labels: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"{edge}_ns_{label}" for label in arm_labels for edge in ("start", "end"))


def _stamp(value: Any) -> int | None:
    """An epoch-nanosecond stamp as a whole number, or ``None`` when the span carries none."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return int(value)


def _frame(rows: list[dict[str, Any]], columns: Sequence[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(columns))
    return frame.reset_index(drop=True)


def _excluded_row(row: _Row, cause: str, arm: str, detail: str) -> dict[str, Any]:
    return {
        "sweep": row.sweep,
        "cut": row.cut,
        "cluster": row.cluster,
        "config_hash": row.key[0],
        "replicate_index": row.key[1],
        "cause": cause,
        "arm": arm,
        "detail": detail,
    }


def _read_arm(
    store: Store, run_id: str, sweep: str, arm: str, declaration: Declaration
) -> dict[tuple[str, int], _Row]:
    frame = store.read(run_id, meta=True, trace="full")
    out: dict[tuple[str, int], _Row] = {}
    for record in frame.to_dict("records"):
        config = record["config"] if isinstance(record["config"], Mapping) else {}
        meta = record["meta"] if isinstance(record["meta"], Mapping) else {}
        key = (str(record["config_hash"]), int(record["replicate_index"]))
        out[key] = _Row(
            sweep=sweep,
            arm=arm,
            key=key,
            cluster=config.get(declaration.cluster_key),
            cut=config.get(declaration.stratum_key),
            seed=int(record["seed"]),
            error=record["error"],
            meta=meta,
            spans=_request_spans(meta, declaration.request_span),
        )
    return out


def _request_spans(meta: Mapping[str, Any], name: str) -> tuple[Any, ...]:
    stored = meta.get("trace")
    if not isinstance(stored, Mapping):
        return ()
    try:
        trace = Trace.from_dict(stored)
    except (TraceValidationError, KeyError, TypeError, ValueError):
        return ()
    return tuple(span for span in trace.ordered() if span.name == name)


# ---------- the declaration against these runs ----------


def _check_strata(arms: Any, declaration: Declaration) -> None:
    """The declaration file lists cuts, not items, so an overlap becomes visible only here.
    A ``cluster_key`` value under two cuts is refused, naming both cuts and the item."""
    seen: dict[Any, Any] = {}
    for rows in arms:
        for row in rows.values():
            first = seen.setdefault(row.cluster, row.cut)
            if first != row.cut:
                raise DeclarationError(
                    f"the strata overlap: item {row.cluster!r} is analysed under cut "
                    f"{first!r} and under cut {row.cut!r}. Strata are disjoint."
                )


def _check_exemptions(arms: Any, declaration: Declaration) -> None:
    """Every name in ``exemptions`` is a header or a transport identifier. A name that
    resolves against a stored request body -- top level or dotted -- is refused: an exempted
    body field would let a sampling parameter or a length limit differ between arms, which is
    the one thing the assertion exists to catch."""
    paths: set[str] = set()
    for rows in arms:
        for row in rows.values():
            for span in row.spans:
                body = _body(span)
                if body is not None:
                    paths |= _paths(body)
    for name in declaration.exemptions:
        if name in paths:
            raise DeclarationError(
                f"exemption {name!r} resolves to a request-body field. An exemption is a "
                "header or a transport identifier; exempting a body field would let a "
                "sampling parameter differ between the arms."
            )


def _body(span: Any) -> dict[str, Any] | None:
    """The stored request body, parsed with its number literals kept. ``None`` when the span
    carries no text or the text is not a JSON object."""
    text = span.input
    if not isinstance(text, (str, bytes, bytearray)):
        return None
    try:
        parsed = _DECODER.decode(
            text.decode("utf-8") if isinstance(text, (bytes, bytearray)) else text
        )
    except (ValueError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _paths(obj: Mapping[str, Any], prefix: str = "") -> set[str]:
    """Every dotted path into the body, the intermediate objects included."""
    out: set[str] = set()
    for key, value in obj.items():
        path = f"{prefix}{key}"
        out.add(path)
        if isinstance(value, dict) and value:
            out |= _paths(value, path + ".")
    return out


def _leaves(obj: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    for key, value in obj.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            yield from _leaves(value, path + ".")
        else:
            yield path, value


def _resolve(obj: Any, dotted: str) -> Any:
    here: Any = obj
    for part in dotted.split("."):
        if not isinstance(here, Mapping) or part not in here:
            return _ABSENT
        here = here[part]
    return here


# ---------- the run-level facts ----------


def _environment(store: Store, declaration: Declaration) -> dict[str, Any]:
    """Per-arm identity, compared and recorded; the gaps printed.

    ``harness_digest`` and ``client_version`` are printed as gaps on every run and compared on
    none: they are the harness's to record and no ``meta`` key convention exists for them yet,
    so comparing them is deferred.
    """
    sweeps: dict[str, dict[str, dict[str, Any]]] = {}
    gaps = ["harness_digest", "client_version"]
    arm_labels = _arm_labels(declaration)
    for sweep in declaration.sweeps:
        per_arm = {
            label: _arm_identity(store, run_id)
            for label, run_id in zip(arm_labels, sweep.arms, strict=True)
        }
        differing = sorted(
            key
            for key in per_arm["a"]
            if any(per_arm[label][key] != per_arm["a"][key] for label in arm_labels[1:])
        )
        if differing:
            whose = "the two arms'" if len(arm_labels) == 2 else "the arms'"
            raise NotAssertable(
                f"sweep {sweep.name!r}: {whose} manifests disagree on "
                f"{', '.join(differing)}. That is a fact about the run, not about one pair."
            )
        sweeps[sweep.name] = per_arm
    if declaration.retries == "asserted":
        _check_retries(store, declaration)
    else:
        gaps.append("retries")
    if declaration.headers == "asserted":
        _check_headers(store, declaration)
    else:
        gaps.append("headers")
    return {"sweeps": sweeps, "gaps": gaps}


def _arm_identity(store: Store, run_id: str) -> dict[str, Any]:
    manifest = store.manifest(run_id)
    environment = manifest.environment
    capture = environment.get("capture")
    return {
        "poisson_prove_version": manifest.poisson_prove_version,
        "run_salt": manifest.run_salt,
        "python": environment.get("python"),
        "concurrency": environment.get("concurrency"),
        "capture_cap": (
            capture.get("max_observation_bytes") if isinstance(capture, Mapping) else None
        ),
    }


def _check_retries(store: Store, declaration: Declaration) -> None:
    """The manifest half of the retry check. ``retries = "asserted"`` requires both arms'
    manifests to record ``infra_retries == 0``. A manifest that is silent is a refusal, the same
    rule as for headers: silence is never a pass."""
    arm_labels = _arm_labels(declaration)
    for sweep in declaration.sweeps:
        for arm, run_id in zip(arm_labels, sweep.arms, strict=True):
            environment = store.manifest(run_id).environment
            if "infra_retries" not in environment:
                raise NotAssertable(
                    f"sweep {sweep.name!r} arm {arm}: the manifest of run {run_id!r} records no "
                    "infra_retries, so a zero-retry claim cannot be asserted from it. Declare "
                    'retries = "not_recorded" and the gap is printed instead.'
                )
            recorded = environment["infra_retries"]
            if recorded != 0:
                raise NotAssertable(
                    f"sweep {sweep.name!r} arm {arm}: run {run_id!r} was launched with "
                    f"infra_retries = {recorded!r}. A repeat is a third draw."
                )


def _check_headers(store: Store, declaration: Declaration) -> None:
    """With nothing recorded under ``http.request.header.*`` on either arm, header
    identity cannot be asserted, and under ``headers = "asserted"`` that is a refusal."""
    for sweep in declaration.sweeps:
        recorded = False
        for run_id in sweep.arms:
            frame = store.read(run_id, meta=True, trace="full")
            for record in frame.to_dict("records"):
                meta = record["meta"] if isinstance(record["meta"], Mapping) else {}
                for span in _request_spans(meta, declaration.request_span):
                    if _headers_of(span):
                        recorded = True
                        break
                if recorded:
                    break
            if recorded:
                break
        if not recorded:
            raise NotAssertable(
                f"sweep {sweep.name!r}: no http.request.header.* attribute is recorded on either "
                'arm, so header identity cannot be asserted. Declare headers = "not_recorded" '
                "and the gap is printed instead."
            )


def _check_seeds(
    arms: Mapping[tuple[str, str], Any], declaration: Declaration, arm_labels: Sequence[str]
) -> None:
    """The per-row half of the seed check. A matched key whose seed moved between the arms is a
    run-level refusal: the rows are not the same draw, and that is not a property of one
    pair."""
    for sweep in declaration.sweeps:
        by_label = [arms[(sweep.name, label)] for label in arm_labels]
        common = set(by_label[0])
        for rows in by_label[1:]:
            common &= set(rows)
        for key in sorted(common):
            seeds = [rows[key].seed for rows in by_label]
            if len(set(seeds)) > 1:
                raise NotAssertable(
                    f"sweep {sweep.name!r}: item {by_label[0][key].cluster!r} carries seed "
                    f"{_per_arm(arm_labels, seeds)}. The arms are not the same draw."
                )


def _per_arm(arm_labels: Sequence[str], values: Sequence[Any]) -> str:
    """``X in arm a and Y in arm b``; past a pair the arms are listed with commas."""
    parts = [f"{value} in arm {label}" for label, value in zip(arm_labels, values, strict=True)]
    return " and ".join(parts) if len(parts) <= 2 else ", ".join(parts)


# ---------- one pair ----------


@dataclass(frozen=True)
class _Verdict:
    cause: str | None = None
    arm: str = "both"
    detail: str = ""
    digest: str = ""
    exercised: tuple[str, ...] = ()
    values: tuple[Decimal | None, ...] = ()
    timing: tuple[int | None, ...] = ()  # start_ns, end_ns per arm, in arm order


def _judge(rows: Sequence[_Row], arm_labels: Sequence[str], declaration: Declaration) -> _Verdict:
    """One matched key across all ``k`` arms, in the order of what each check is about: the
    row, then the request, then the body, then the target, then the measured value. A per-arm
    fact names the failing arm's label; a comparison of the arms reads ``both`` and names the
    differing arm in ``detail``. Every test of this module builds one failure per set, so the
    precedence between two causes on one set is not pinned; a set broken in two arms may take
    either of them."""
    errored = _failing(arm_labels, [r.error is not None for r in rows])
    if errored is not None:
        return _Verdict(
            "errored", errored, _first_of(*(r.error for r in rows)) or "the row errored"
        )

    absent = _failing(arm_labels, [not r.spans for r in rows])
    if absent is not None:
        return _Verdict(
            "no_request_span",
            absent,
            f"no span named {declaration.request_span!r}; the declaration names the request",
        )
    repeated = _failing(arm_labels, [len(r.spans) > 1 for r in rows])
    if repeated is not None:
        return _Verdict(
            "retry_or_multicall",
            repeated,
            f"{max(len(r.spans) for r in rows)} spans named {declaration.request_span!r} in one "
            "episode; a repeat is a third draw",
        )

    bodies = [_body(r.spans[0]) for r in rows]
    malformed = _failing(arm_labels, [body is None for body in bodies])
    if malformed is not None:
        return _Verdict("malformed_body", malformed, "the stored request is not a JSON object")
    parsed = [body for body in bodies if body is not None]
    assert len(parsed) == len(rows)  # noqa: S101 - narrowed by the check above

    pins = [_resolve(body, declaration.model_key) for body in parsed]
    off_pin = _failing(arm_labels, [not _at_pin(pin, declaration) for pin in pins])
    if off_pin is not None:
        # Asserted, never inherited: the ``both`` case is arms that agree with each other and
        # not with the pin, and it is still not a pair at the pinned model.
        return _Verdict(
            "model_pin",
            off_pin,
            f"{declaration.model_key} is "
            f"{_per_arm(arm_labels, [_shown(pin) for pin in pins])}; "
            f"the pin is {declaration.model_pin!r}",
        )

    leaves = [dict(_leaves(body)) for body in parsed]
    only: set[str] = set()
    for other in leaves[1:]:
        only |= set(leaves[0]) ^ set(other)
    if only:
        return _Verdict(
            "body_field_absent",
            "both",
            f"present in one arm and absent in the other: {', '.join(sorted(only))}"
            + _differing_arms(arm_labels, [set(lv) != set(leaves[0]) for lv in leaves]),
        )
    canonicals = [canonical_request(r.spans[0].input) for r in rows]
    if any(c != canonicals[0] for c in canonicals[1:]):
        moved = sorted(
            path
            for path, value in leaves[0].items()
            if any(_emit(value) != _emit(other[path]) for other in leaves[1:])
        )
        return _Verdict(
            "body",
            "both",
            f"the arms differ at: {', '.join(moved)}"
            + _differing_arms(arm_labels, [c != canonicals[0] for c in canonicals]),
        )

    targets = [_target_of(r.spans[0]) for r in rows]
    if any(t != targets[0] for t in targets[1:]):
        moved = sorted(
            key for key in _TARGET_KEYS if any(t[key] != targets[0][key] for t in targets[1:])
        )
        return _Verdict(
            "target",
            "both",
            f"the arms differ at: {', '.join(moved)}"
            + _differing_arms(arm_labels, [t != targets[0] for t in targets]),
        )

    headers = [_headers_of(r.spans[0]) for r in rows]
    exempt = {name.lower() for name in declaration.exemptions}
    names: set[str] = set()
    for recorded in headers:
        names |= set(recorded)
    differing = sorted(name for name in names if len({h.get(name) for h in headers}) > 1)
    unexempted = [name for name in differing if name not in exempt]
    if unexempted:
        return _Verdict(
            "header",
            "both",
            f"the arms differ at: {', '.join(unexempted)}"
            + _differing_arms(
                arm_labels,
                [any(h.get(n) != headers[0].get(n) for n in unexempted) for h in headers],
            ),
        )

    read = [_value_of(r, declaration) for r in rows]
    values = [value for value, _ in read]
    absent_value = _failing(arm_labels, [missing for _, missing in read])
    if absent_value is not None:
        return _Verdict(
            "value_missing",
            absent_value,
            f"the episode records no {declaration.value_key}",
        )
    out_of_range = _failing(arm_labels, [not _in_unit(value) for value in values])
    if out_of_range is not None:
        return _Verdict(
            "value_out_of_range",
            out_of_range,
            f"{declaration.value_key} is "
            f"{_per_arm(arm_labels, [_shown(value) for value in values])}; "
            "the interval is [0, 1]",
        )

    exercised = tuple(name.lower() for name in declaration.exemptions if name.lower() in differing)
    digest = request_digest(
        rows[0].spans[0].input,
        target=targets[0],
        headers=headers[0],
        exemptions=declaration.exemptions,
    )
    timing = tuple(
        itertools.chain.from_iterable(
            (_stamp(r.spans[0].start_ns), _stamp(r.spans[0].end_ns)) for r in rows
        )
    )
    return _Verdict(digest=digest, exercised=exercised, values=tuple(values), timing=timing)


def _failing(arm_labels: Sequence[str], flags: Sequence[bool]) -> str | None:
    """Which arm the failure was found in: its label alone, ``both`` when more than one arm
    has it, ``None`` when no arm has it. At ``k = 2`` this is the pair's reading exactly."""
    failing = [label for label, flag in zip(arm_labels, flags, strict=True) if flag]
    if not failing:
        return None
    return failing[0] if len(failing) == 1 else "both"


def _differing_arms(arm_labels: Sequence[str], flags: Sequence[bool]) -> str:
    """Past a pair, a comparison cause names the arm that differs from arm ``a`` (the
    reading for the causes that read ``both``). At ``k = 2`` nothing is added."""
    if len(arm_labels) == 2:
        return ""
    named = [label for label, flag in zip(arm_labels, flags, strict=True) if flag]
    return " (" + ", ".join(f"arm {label}" for label in named) + ")" if named else ""


def _first_of(*values: str | None) -> str | None:
    return next((v for v in values if v is not None), None)


def _at_pin(value: Any, declaration: Declaration) -> bool:
    return type(value) is str and value == declaration.model_pin


def _shown(value: Any) -> str:
    return "absent" if value is _ABSENT or value is None else repr(str(value))


def _target_of(span: Any) -> dict[str, str]:
    attrs = span.attrs if isinstance(span.attrs, Mapping) else {}
    return {key: "" if attrs.get(key) is None else str(attrs[key]) for key in _TARGET_KEYS}


def _headers_of(span: Any) -> dict[str, str]:
    """The recorded request headers, names lower-cased. A multi-valued header is the values in
    the order the recorder kept them, which is what the wire sent."""
    attrs = span.attrs if isinstance(span.attrs, Mapping) else {}
    out: dict[str, str] = {}
    for key, value in attrs.items():
        if isinstance(key, str) and key.lower().startswith(_HEADER_PREFIX):
            name = key[len(_HEADER_PREFIX) :].lower()
            out[name] = (
                ", ".join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value)
            )
    return out


def _value_of(row: _Row, declaration: Declaration) -> tuple[Decimal | None, bool]:
    """The scalar under test, read as the literal text the harness stored and parsed with
    ``Decimal``. Never through ``float``: two 19-digit literals that are exactly 1 and 0 to a
    double are outside the interval as written."""
    raw = _resolve(row.meta, declaration.value_key)
    if raw is _ABSENT or raw is None:
        return None, True
    try:
        return Decimal(str(raw)), False
    except (InvalidOperation, ValueError):
        return None, False


def _in_unit(value: Decimal | None) -> bool:
    return value is not None and _ZERO <= value <= _ONE


# ---------- the counts ----------


def _counts(
    pairs: Sequence[Mapping[str, Any]],
    excluded: Sequence[Mapping[str, Any]],
    keys_by_cut: Mapping[Any, int],
    declaration: Declaration,
    exercised: Mapping[str, int],
    arm_labels: Sequence[str],
) -> dict[str, Any]:
    """Read to the letter: ``ineligible`` counts **matched** pairs that failed and
    ``unmatched`` is its own count, though an unmatched key is also called ineligible; both
    are rows of ``excluded`` and both are in ``by_cause``. ``keys`` is summed over sweeps, each
    sweep's union taken on its own, because every sweep replays the same item set. The counts are
    of pairs: a set excluded only past its declared pair is an eligible pair here, and its row of
    ``excluded`` is counted by ``replicates`` instead."""
    cuts: list[Any] = [c.name for c in declaration.cuts]
    cuts += [cut for cut in keys_by_cut if cut not in cuts]
    arms = (*arm_labels, "both")
    by_cut = {cut: _block(pairs, excluded, keys_by_cut.get(cut, 0), cut, arms) for cut in cuts}
    total = _block(pairs, excluded, sum(keys_by_cut.values()), None, arms)
    return {
        "total": total,
        "by_cut": by_cut,
        "exemptions_exercised": dict(exercised),
    }


def _block(
    pairs: Sequence[Mapping[str, Any]],
    excluded: Sequence[Mapping[str, Any]],
    keys: int,
    cut: Any,
    arms: Sequence[str] = _ARMS,
) -> dict[str, Any]:
    kept = [r for r in pairs if cut is None or r["cut"] == cut]
    kept_keys = {(r["sweep"], r["config_hash"], r["replicate_index"]) for r in kept}
    dropped = [
        r
        for r in excluded
        if (cut is None or r["cut"] == cut)
        and (r["sweep"], r["config_hash"], r["replicate_index"]) not in kept_keys
    ]
    unmatched = [r for r in dropped if r["cause"] == "unmatched"]
    by_cause = {cause: 0 for cause in _CAUSES}
    by_arm = {arm: 0 for arm in arms}
    for row in dropped:
        by_cause[row["cause"]] = by_cause.get(row["cause"], 0) + 1
        by_arm[row["arm"]] = by_arm.get(row["arm"], 0) + 1
    matched = keys - len(unmatched)
    ineligible = len(dropped) - len(unmatched)
    reconciles = bool(
        len(kept) + ineligible == matched
        and matched + len(unmatched) == keys
        and sum(by_cause.values()) == ineligible + len(unmatched)
    )
    return {
        "keys": keys,
        "matched": matched,
        "unmatched": len(unmatched),
        "eligible": len(kept),
        "ineligible": ineligible,
        "by_cause": by_cause,
        "by_arm": by_arm,
        "reconciles": reconciles,
    }


# ---------- the analysis ----------


_DIRECTION = "b_minus_a"  # the net swing subtracts the first arm from the second
_FALLBACK_BELOW = 5  # fewer flipping items than this and the bootstrap is not reported
_CAN_REJECT_FROM = 6  # a two-sided exact binomial on fewer discordant pairs cannot reach 0.05
_CONTINGENCY_KEYS: tuple[str, ...] = (
    "n11",
    "n10",
    "n01",
    "n00",
    "n",
    "ties",
    "arm_order_check",
)
_INTERVAL_KEYS: tuple[str, ...] = ("rate_a", "rate_b", "flip_rate", "net_swing")


@dataclass(frozen=True)
class CutResult:
    name: str
    threshold: Decimal
    per_sweep: tuple[Mapping[str, Any], ...]  # 2x2, rates, exact interval, arm-order check
    pooled: Mapping[str, Any]  # flip rate, net swing, clustered intervals
    ties: Mapping[str, int]
    design_effect: Mapping[str, float]
    outcome: Literal["A", "B", "C"] | None


@dataclass(frozen=True)
class PairedResult:
    declaration_digest: str
    cuts: tuple[CutResult, ...]

    def contingency_json(self) -> str:
        """Per cut and per sweep: the 2x2, ``n``, the ties, and the arm-order check. Every
        statistic sits under exactly one cut name; the threshold is its literal text."""
        payload = {
            "declaration_digest": self.declaration_digest,
            "cuts": {
                c.name: {
                    "threshold": str(c.threshold),
                    "comparison": c.pooled["comparison"],
                    "per_sweep": {
                        str(s["sweep"]): {key: s[key] for key in _CONTINGENCY_KEYS}
                        for s in c.per_sweep
                    },
                    "ties": dict(c.ties),
                }
                for c in self.cuts
            },
        }
        return json.dumps(_jsonable(payload), indent=2, ensure_ascii=False)

    def intervals_json(self) -> str:
        """Per cut: the pooled flip rate and net swing with their clustered intervals, the design
        effect, the per-sweep exact intervals, the ineligibility rate, and the outcome beside the
        interval it was decided from. The arm-order check is not here."""
        payload = {
            "declaration_digest": self.declaration_digest,
            "cuts": {
                c.name: {
                    "threshold": str(c.threshold),
                    "comparison": c.pooled["comparison"],
                    "n": dict(c.pooled["n"]),
                    "flip_rate": dict(c.pooled["flip_rate"]),
                    "net_swing": dict(c.pooled["net_swing"]),
                    "design_effect": dict(c.design_effect),
                    "per_sweep": {
                        str(s["sweep"]): {key: s[key] for key in _INTERVAL_KEYS}
                        for s in c.per_sweep
                    },
                    "ineligibility_rate": c.pooled["ineligibility_rate"],
                    "outcome": c.outcome,
                    "outcome_interval": (
                        None if c.outcome is None else dict(c.pooled["flip_rate"])
                    ),
                }
                for c in self.cuts
            },
        }
        return json.dumps(_jsonable(payload), indent=2, ensure_ascii=False)


def analyse(assertion: PairAssertion) -> PairedResult:
    """One question per declared cut: did the binary action at that cut reproduce?

    Takes a ``PairAssertion`` and nothing else. Every number is computed on that cut's
    eligible pairs alone, in declaration order, and no figure is computed over more than one
    cut. The input frames are read and never written.
    """
    declaration = assertion.declaration
    cuts = tuple(_analyse_cut(assertion, cut) for cut in declaration.cuts)
    return PairedResult(declaration_digest=declaration.digest, cuts=cuts)


def _analyse_cut(assertion: PairAssertion, cut: Cut) -> CutResult:
    declaration = assertion.declaration
    rows = _actions(assertion.pairs, cut)
    per_sweep = tuple(_sweep_block(rows, sweep.name) for sweep in declaration.sweeps)
    ties = {"a": int(rows["tie_a"].sum()), "b": int(rows["tie_b"].sum())}
    pooled = _pooled(rows, declaration, assertion.counts, cut)
    return CutResult(
        name=cut.name,
        threshold=cut.threshold,
        per_sweep=per_sweep,
        pooled=pooled,
        ties=ties,
        design_effect=_design_effect(rows),
        outcome=_outcome(pooled["flip_rate"], declaration.floor),
    )


def _act(value: Decimal, threshold: Decimal, comparison: str) -> int:
    """The action under the cut's declared rule, on ``Decimal`` from the stored literal:
    ``value >= threshold`` under ``ge`` and ``value > threshold`` under ``gt``."""
    return int(value >= threshold) if comparison == "ge" else int(value > threshold)


def _actions(pairs: pd.DataFrame, cut: Cut) -> pd.DataFrame:
    """The cut's eligible pairs with the action taken in each of the declared pair's two arms,
    on the ``Decimal`` the assertion parsed from the stored literal under the cut's
    declared comparison. No rounding, no rescaling, no ``float``: a rounding step would move
    items across the cut and the module would be measuring the rounding. A value equal to the
    threshold is a tie under either rule, counted per arm; it acts under ``ge`` and not
    under ``gt``. Arms ``3..k`` are never read here.

    Rows are put in one canonical order first, so every sum below is the same sum whatever
    order the frame arrived in.
    """
    columns = ["sweep", "cluster", "config_hash", "replicate_index", "value_a", "value_b"]
    rows = _canonical_rows(pairs, cut, columns)
    rows["act_a"] = [_act(v, cut.threshold, cut.comparison) for v in rows["value_a"]]
    rows["act_b"] = [_act(v, cut.threshold, cut.comparison) for v in rows["value_b"]]
    rows["tie_a"] = [int(v == cut.threshold) for v in rows["value_a"]]
    rows["tie_b"] = [int(v == cut.threshold) for v in rows["value_b"]]
    rows["flip"] = (rows["act_a"] != rows["act_b"]).astype(int)
    rows["d"] = rows["act_b"] - rows["act_a"]
    return rows


def _canonical_rows(pairs: pd.DataFrame, cut: Cut, columns: Sequence[str]) -> pd.DataFrame:
    """The cut's rows of ``pairs``, the named columns, in the one canonical order."""
    rows = pairs.loc[pairs["cut"] == cut.name, list(columns)].copy()
    rows["_order"] = [
        (str(s), str(c), str(h), int(r))
        for s, c, h, r in zip(
            rows["sweep"],
            rows["cluster"],
            rows["config_hash"],
            rows["replicate_index"],
            strict=True,
        )
    ]
    rows = rows.sort_values("_order", kind="mergesort").drop(columns="_order")
    return rows.reset_index(drop=True)


def _sweep_block(rows: pd.DataFrame, sweep: str) -> dict[str, Any]:
    """One sweep of one cut: the 2x2, the arm rates as bare numbers, the flip
    rate with its exact two-sided interval, the net swing and McNemar's exact
    test under ``arm_order_check`` and nowhere else.

    The discordant counts and the binomial are ``diff``'s own ``_discordant`` and ``_mcnemar``,
    reused rather than re-derived, so the module adds no second binomial.
    """
    sub = rows[rows["sweep"] == sweep]
    act_a = sub["act_a"].to_numpy(dtype=int)
    act_b = sub["act_b"].to_numpy(dtype=int)
    cell_a = pd.DataFrame({"replicate_index": range(len(sub)), "observed": act_a.astype(bool)})
    cell_b = pd.DataFrame({"replicate_index": range(len(sub)), "observed": act_b.astype(bool)})
    n10, n01, n = _discordant(cell_a, cell_b, sweep)
    n11 = int(np.sum((act_a == 1) & (act_b == 1)))
    n00 = n - n11 - n10 - n01
    nd = n10 + n01
    _, p = _mcnemar(cell_a, cell_b, sweep)
    lo, hi = _exact_two_sided(nd, n)
    return {
        "sweep": sweep,
        "n11": n11,
        "n10": n10,
        "n01": n01,
        "n00": n00,
        "n": n,
        "ties": {"a": int(sub["tie_a"].sum()), "b": int(sub["tie_b"].sum())},
        "rate_a": float((n11 + n10) / n) if n else 0.0,
        "rate_b": float((n11 + n01) / n) if n else 0.0,
        "flip_rate": {
            "estimate": float(nd / n) if n else 0.0,
            "lo": lo,
            "hi": hi,
            "basis": "exact_binomial",
        },
        "net_swing": {
            "estimate": float((n01 - n10) / n) if n else 0.0,
            "direction": _DIRECTION,
        },
        "arm_order_check": {
            "p": float(p),
            "n_discordant": nd,
            "can_reject": nd >= _CAN_REJECT_FROM,
        },
    }


def _exact_two_sided(k: int, n: int) -> tuple[float, float]:
    """The two-sided 95% Clopper-Pearson interval on ``k`` of ``n``. ``[0, 1]`` at ``n = 0``."""
    if n == 0:
        return 0.0, 1.0
    lo = 0.0 if k == 0 else float(_beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta.ppf(0.975, k + 1, n - k))
    return lo, hi


def _pooled(
    rows: pd.DataFrame, declaration: Declaration, counts: Mapping[str, Any], cut: Cut
) -> dict[str, Any]:
    """The cut over every sweep: ``n`` as items and sweeps and never their product, the
    flip rate and the net swing with the item-clustered interval or the declared fallback,
    and the ineligibility rate read off the assertion's own counts."""
    groups_flip = _clusters(rows, "flip")
    groups_d = _clusters(rows, "d")
    g_count = len(groups_flip)
    total = int(len(rows))
    flip_estimate = float(rows["flip"].sum() / total) if total else 0.0
    swing_estimate = float(rows["d"].sum() / total) if total else 0.0
    k = int(sum(1 for grp in groups_flip if grp.any()))
    if k < _FALLBACK_BELOW:
        # The one-sided exact 95% upper bound on the item-level flip probability; the lower
        # bound is zero by observation, not by estimation. A percentile bootstrap degenerating
        # to [0, 0] would read as a precise zero and is not one. A signed quantity has no
        # one-sided exact bound, so the net swing is not estimated here.
        flip_rate: dict[str, Any] = {
            "estimate": flip_estimate,
            "lo": 0.0,
            "hi": float(_beta.ppf(0.95, k + 1, g_count - k)) if g_count > k else 1.0,
            "basis": "exact_upper_one_sided",
            "lower_bound_by_observation": True,
        }
        net_swing: dict[str, Any] = {
            "estimate": swing_estimate,
            "lo": None,
            "hi": None,
            "basis": "not_estimated",
            "direction": _DIRECTION,
        }
    else:
        seed, b = declaration.bootstrap_seed, declaration.bootstrap_b
        lo, hi = _cluster_bootstrap(groups_flip, seed, b)
        slo, shi = _cluster_bootstrap(groups_d, seed, b)
        flip_rate = {"estimate": flip_estimate, "lo": lo, "hi": hi, "basis": "cluster_bootstrap"}
        net_swing = {
            "estimate": swing_estimate,
            "lo": slo,
            "hi": shi,
            "basis": "cluster_bootstrap",
            "direction": _DIRECTION,
        }
    return {
        # ``CutResult``'s seven fields are frozen, so the cut's declared comparison rides here
        # and the two artifact writers print it beside the threshold.
        "comparison": cut.comparison,
        "n": {"items": g_count, "sweeps": len(declaration.sweeps)},
        "flip_rate": flip_rate,
        "net_swing": net_swing,
        "ineligibility_rate": _ineligibility_rate(counts, cut),
    }


def _clusters(rows: pd.DataFrame, column: str) -> list[NDArray[np.int64]]:
    """One array per item, the items in ascending order of the cluster key -- a stable sort,
    strings as strings -- so the bootstrap's index draw lands on the same item whatever order
    the rows arrived in."""
    return [grp[column].to_numpy(dtype=np.int64) for _, grp in rows.groupby("cluster", sort=True)]


def _cluster_bootstrap(
    groups: Sequence[NDArray[np.int64]], seed: int, b: int
) -> tuple[float, float]:
    """The percentile cluster bootstrap over items, exactly as ``scripts/repro_r1_agreement.py``
    published it: a fresh ``default_rng(seed)`` per quantity and per cut, ``B`` resamples of the
    ``G`` item clusters with replacement as one ``integers(0, G, size=(B, G))`` draw, each
    resample's per-observation indicators concatenated and averaged, the 2.5th and 97.5th
    percentiles. Whole items, never observations. The concatenated mean is taken as the
    resample's summed indicators over its summed sizes, which is the same number: both sums are
    exact integers."""
    rng = np.random.default_rng(seed)
    g_count = len(groups)
    sums = np.array([int(grp.sum()) for grp in groups], dtype=np.int64)
    sizes = np.array([len(grp) for grp in groups], dtype=np.int64)
    idx = rng.integers(0, g_count, size=(b, g_count))
    draws = sums[idx].sum(axis=1) / sizes[idx].sum(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def _ineligibility_rate(counts: Mapping[str, Any], cut: Cut) -> float:
    """``ineligible / matched`` off the assertion's ``counts["by_cut"]``. An unmatched key
    is its own count and never enters the rate. The module computes the rate and chooses
    no threshold for it."""
    by_cut = counts.get("by_cut", {})
    block = by_cut.get(cut.name, {}) if isinstance(by_cut, Mapping) else {}
    matched = int(block.get("matched", 0))
    ineligible = int(block.get("ineligible", 0))
    return float(ineligible / matched) if matched else 0.0


def _design_effect(rows: pd.DataFrame) -> dict[str, float]:
    """The item-level intraclass correlation, one-way ANOVA ``ICC(1)`` on each item's flip
    indicators, ``(MSB - MSW) / (MSB + (m0 - 1) MSW)`` clipped at zero, and the design effect
    ``deff = 1 + (m_bar - 1) icc`` with ``m_bar`` the observations per item. ``m0`` is the ANOVA
    cluster size, which equals ``m_bar`` on a balanced design; with one observation per item
    there is no within-item replication to estimate a correlation from, so ``icc`` is zero and
    ``deff`` is one."""
    total = int(len(rows))
    g_count = int(rows["cluster"].nunique()) if total else 0
    if g_count == 0:
        return {"icc": 0.0, "m_bar": 0.0, "deff": 1.0}
    m_bar = total / g_count
    if g_count < 2 or total <= g_count:
        return {"icc": 0.0, "m_bar": float(m_bar), "deff": 1.0}
    y = rows["flip"].astype(float)
    grand = float(y.mean())
    by_item = rows.groupby("cluster", sort=True)["flip"]
    sizes = by_item.size().astype(float)
    means = by_item.mean()
    msb = float((sizes * (means - grand) ** 2).sum()) / (g_count - 1)
    msw = float(((y - rows["cluster"].map(means)) ** 2).sum()) / (total - g_count)
    m0 = (total - float((sizes**2).sum()) / total) / (g_count - 1)
    denominator = msb + (m0 - 1) * msw
    icc = 0.0 if denominator == 0 else max(0.0, (msb - msw) / denominator)
    return {"icc": float(icc), "m_bar": float(m_bar), "deff": float(1 + (m_bar - 1) * icc)}


def _outcome(flip_rate: Mapping[str, Any], floor: Decimal | None) -> Literal["A", "B", "C"] | None:
    """The outcome, only against a declared floor, from the pooled flip-rate interval: **A**
    when the lower bound is zero and the upper bound is under the floor, **B** when the lower
    bound leaves zero, **C** when the interval covers both. The upper bound is compared as the
    exact value of the double it is, against the floor as the literal it was declared as."""
    if floor is None:
        return None
    lo, hi = flip_rate["lo"], flip_rate["hi"]
    if lo > 0:
        return "B"
    if Decimal(hi) < floor:
        return "A"
    return "C"


# ---------- replications and windows ----------


_WINDOW_REPORT_KEYS: tuple[str, ...] = ("per_sweep", "replay_gap")


@dataclass(frozen=True)
class WindowReport:
    per_sweep: tuple[Mapping[str, Any], ...]  # realized span, claim held/withdrawn, latency
    replay_gap: Mapping[str, Mapping[str, float] | None]  # per cut: min, median, max

    def to_json(self) -> str:
        payload = {
            "per_sweep": [dict(entry) for entry in self.per_sweep],
            "replay_gap": {
                name: None if g is None else dict(g) for name, g in self.replay_gap.items()
            },
        }
        return json.dumps(_jsonable(payload), indent=2, ensure_ascii=False)


def windows(assertion: PairAssertion) -> WindowReport:
    """Each sweep is its own window, read off the timestamps that ride on ``pairs`` --
    the request span's ``start_ns`` and ``end_ns`` from the trace envelope, never ``wall_time``
    -- and off nothing else, so an excluded set has no window, a set kept for its
    declared pair alone has the stamps of arms ``a`` and ``b`` only, and no pair is dropped on
    a timing criterion. A sweep with no usable stamp is ``unavailable`` with the reason
    named, and never a zero. With a declared window the claim is ``held`` or
    ``withdrawn`` and nothing else moves. The replay gap is per cut. This is a
    timing artifact: no rate, no count of flips, no interval.
    """
    declaration = assertion.declaration
    arm_labels = _arm_labels(declaration)
    pairs = assertion.pairs
    per_sweep: list[dict[str, Any]] = []
    for sweep in declaration.sweeps:
        rows = pairs[pairs["sweep"] == sweep.name] if len(pairs) else pairs
        arms: dict[str, dict[str, int | None]] = {}
        latencies: list[float] = []
        for label in arm_labels:
            starts = [s for s in _column(rows, f"start_ns_{label}") if s is not None]
            ends = [e for e in _column(rows, f"end_ns_{label}") if e is not None]
            arms[label] = {
                "first_start_ns": min(starts) if starts else None,
                "last_end_ns": max(ends) if ends else None,
            }
            starts_all = _column(rows, f"start_ns_{label}")
            ends_all = _column(rows, f"end_ns_{label}")
            latencies += [
                (end - start) / _NS
                for start, end in zip(starts_all, ends_all, strict=True)
                if start is not None and end is not None
            ]
        first = arms["a"]["first_start_ns"]
        last = arms[arm_labels[-1]]["last_end_ns"]
        reason: str | None = None
        if len(rows) == 0:
            reason = "no eligible replicate set in this sweep"
        elif first is None:
            reason = "arm a records no request start_ns on any eligible request span"
        elif last is None:
            reason = f"arm {arm_labels[-1]} records no response end_ns on any eligible request span"
        span: float | None = None
        if reason is None and first is not None and last is not None:
            span = (last - first) / _NS
        declared = declaration.declared_window_s
        claim: str | None = None
        if span is not None and declared is not None:
            claim = "held" if span <= declared else "withdrawn"
        per_sweep.append(
            {
                "sweep": sweep.name,
                "timing": "available" if reason is None else "unavailable",
                "reason": reason,
                "arms": arms,
                "realized_span_s": span,
                "declared_window_s": declared,
                "claim": claim,
                "latency_s": (
                    {"median": float(np.median(latencies)), "n": len(latencies)}
                    if latencies
                    else None
                ),
            }
        )
    replay_gap: dict[str, dict[str, float] | None] = {}
    for cut in declaration.cuts:
        rows = pairs[pairs["cut"] == cut.name] if len(pairs) else pairs
        gaps = [
            (b - a) / _NS
            for a, b in zip(_column(rows, "start_ns_a"), _column(rows, "start_ns_b"), strict=True)
            if a is not None and b is not None
        ]
        replay_gap[cut.name] = (
            {"min": float(min(gaps)), "median": float(np.median(gaps)), "max": float(max(gaps))}
            if gaps
            else None
        )
    return WindowReport(per_sweep=tuple(per_sweep), replay_gap=replay_gap)


def _column(rows: pd.DataFrame, name: str) -> list[int | None]:
    """A timing column as whole numbers or ``None``; a frame without it reads as all absent."""
    if name not in rows.columns:
        return [None] * len(rows)
    return [_stamp(v) for v in rows[name]]


# ---------- cost ----------


_COST_REPORT_KEYS: tuple[str, ...] = (
    "phases",
    "input_tokens",
    "output_tokens",
    "recorded_spans",
    "unrecorded_spans",
    "price_per_input_token",
    "dollars",
    "token_cap",
    "cap_reached",
)


@dataclass(frozen=True)
class CostReport:
    phases: tuple[Mapping[str, Any], ...]  # per phase, per sweep, per arm
    input_tokens: int
    output_tokens: int
    recorded_spans: int  # request spans with recorded usage
    unrecorded_spans: int
    price_per_input_token: Decimal | None
    dollars: Decimal | None
    token_cap: int | None
    cap_reached: bool

    def to_json(self) -> str:
        payload = {
            "phases": [dict(entry) for entry in self.phases],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "recorded_spans": self.recorded_spans,
            "unrecorded_spans": self.unrecorded_spans,
            "price_per_input_token": _literal(self.price_per_input_token),
            "dollars": _literal(self.dollars),
            "token_cap": self.token_cap,
            "cap_reached": self.cap_reached,
        }
        return json.dumps(_jsonable(payload), indent=2, ensure_ascii=False)


def _literal(value: Decimal | None) -> str | None:
    """A price or a dollar figure as its literal, never through ``str``, which turns
    ``0.000000042`` into ``4.2E-8`` and cannot be redone by hand."""
    return None if value is None else format(value, "f")


def cost(
    store: Store,
    declaration: Declaration,
    *,
    phases: Mapping[str, Sequence[str]],
) -> CostReport:
    """The provider's own recorded usage, summed per phase, per sweep and per arm: every
    span named ``request_span`` in every stored episode of every run id in ``phases`` -- retries
    included, because they were paid for -- with a span carrying ``tokens["in"]`` counted as
    recorded and any other span as unrecorded, never as zero. Output tokens are totalled
    with or without a price; dollars are input tokens times the declared price, the price
    echoed beside them, and absent without one. The cap is cumulative input tokens
    at or above ``token_cap``. A run id in two phases is refused. The module holds
    no tokeniser and no rate card.
    """
    where = {
        run_id: (sweep.name, label)
        for sweep in declaration.sweeps
        for label, run_id in zip(_arm_labels(declaration), sweep.arms, strict=True)
    }
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for phase, run_ids in phases.items():
        for run_id in run_ids:
            if run_id in seen:
                raise PairedError(
                    f"run {run_id!r} is named in more than one phase; every run is in exactly "
                    "one, or the sum over phases is not the study total"
                )
            seen.add(run_id)
            sweep_name, arm = where.get(run_id, (None, None))
            tokens_in = tokens_out = recorded = unrecorded = 0
            frame = store.read(run_id, meta=True, trace="full")
            for record in frame.to_dict("records"):
                meta = record["meta"] if isinstance(record["meta"], Mapping) else {}
                for span in _request_spans(meta, declaration.request_span):
                    usage = span.tokens if isinstance(span.tokens, Mapping) else {}
                    if usage.get("in") is not None:
                        recorded += 1
                        tokens_in += int(usage["in"])
                    else:
                        unrecorded += 1
                    if usage.get("out") is not None:
                        tokens_out += int(usage["out"])
            entries.append(
                {
                    "phase": phase,
                    "run_id": run_id,
                    "sweep": sweep_name,
                    "arm": arm,
                    "input_tokens": tokens_in,
                    "output_tokens": tokens_out,
                    "recorded_spans": recorded,
                    "unrecorded_spans": unrecorded,
                }
            )
    input_tokens = sum(int(e["input_tokens"]) for e in entries)
    price = declaration.price_per_input_token
    return CostReport(
        phases=tuple(entries),
        input_tokens=input_tokens,
        output_tokens=sum(int(e["output_tokens"]) for e in entries),
        recorded_spans=sum(int(e["recorded_spans"]) for e in entries),
        unrecorded_spans=sum(int(e["unrecorded_spans"]) for e in entries),
        price_per_input_token=price,
        dollars=None if price is None else Decimal(input_tokens) * price,
        token_cap=declaration.token_cap,
        cap_reached=declaration.token_cap is not None and input_tokens >= declaration.token_cap,
    )


# ---------- k replicates: agree@j and MS@j ----------


_WITHIN_SWEEP = "within_sweep"
_ACROSS_SWEEPS = "across_sweeps"
_PER_TEN_THOUSAND = 10000


@dataclass(frozen=True)
class ReplicateResult:
    name: str  # the cut
    threshold: Decimal
    k: int
    agree: Mapping[str, Mapping[str, Any]]  # rule -> {"j2": {...}, ..., "steps": {...}}
    majority: Mapping[str, Mapping[str, Any]]  # rule -> {"j1": {...}, "j3": {...}, ...} odd j
    counts: Mapping[str, Any]  # eligible sets, sweep pairs, per-arm exclusions, ties
    cost_framing: Mapping[str, Any]  # rule -> per odd j: dollars, latency, per-10,000 with bounds

    def to_json(self) -> str:
        payload = {
            "name": self.name,
            "threshold": str(self.threshold),
            "comparison": self.counts["rules"]["primary"],
            "k": self.k,
            "agree": self.agree,
            "majority": self.majority,
            "counts": self.counts,
            "cost_framing": self.cost_framing,
        }
        return json.dumps(_jsonable(payload), indent=2, ensure_ascii=False)


def replicates(
    assertion: PairAssertion,
    *,
    cost: CostReport | None = None,
    windows: WindowReport | None = None,
) -> tuple[ReplicateResult, ...]:
    """A second reader of the same ``PairAssertion``, beside ``analyse`` and ``windows``: per
    cut, and under the cut's declared comparison and the other one, ``agree@j`` for
    ``j = 2..k`` -- the rate at which the first ``j`` calls of a replicate set all took one action
    -- and ``MS@j`` for odd ``j`` -- the rate at which two sweeps' ``j``-call
    majorities for one item agreed. Every interval is the item-clustered bootstrap of
    ``analyse`` through ``_cluster_bootstrap`` with a fresh generator per quantity, with its
    small-count fallback pointed at the top and the design effect on that metric's own footing.
    A step between two prefixes is paired on the same draws. The cost framing is emitted
    whole from ``cost`` and ``windows`` where they were passed. Returns ``()`` when every
    sweep is a pair, so the pair-only artifacts are unchanged by construction.
    """
    declaration = assertion.declaration
    arm_labels = _arm_labels(declaration)
    k = len(arm_labels)
    if k == 2:
        return ()
    return tuple(
        _replicate_cut(assertion, cut, arm_labels, cost, windows) for cut in declaration.cuts
    )


def _replicate_cut(
    assertion: PairAssertion,
    cut: Cut,
    arm_labels: Sequence[str],
    cost: CostReport | None,
    windows: WindowReport | None,
) -> ReplicateResult:
    declaration = assertion.declaration
    k = len(arm_labels)
    seed, b = declaration.bootstrap_seed, declaration.bootstrap_b
    stops = k if k % 2 else k - 1
    value_columns = _value_columns(arm_labels)
    rows = _whole_sets(
        _canonical_rows(
            assertion.pairs,
            cut,
            ["sweep", "cluster", "config_hash", "replicate_index", *value_columns],
        ),
        value_columns,
    )
    n_sets = int(len(rows))
    values = [list(rows[column]) for column in value_columns]
    clusters = list(rows["cluster"])
    sweeps = [str(s) for s in rows["sweep"]]
    set_keys = list(zip(rows["cluster"], rows["config_hash"], rows["replicate_index"], strict=True))
    sweep_names = [sweep.name for sweep in declaration.sweeps]

    rules = {"primary": cut.comparison, "sensitivity": _OTHER_COMPARISON[cut.comparison]}
    agree: dict[str, dict[str, Any]] = {}
    majority: dict[str, dict[str, Any]] = {}
    framing: dict[str, dict[str, Any]] = {}
    for rule, comparison in rules.items():
        acts = np.array(
            [[_act(v, cut.threshold, comparison) for v in arm] for arm in values], dtype=np.int64
        ).T.reshape(n_sets, k)
        rule_agree: dict[str, Any] = {}
        by_prefix: dict[int, NDArray[np.int64]] = {}
        for j in range(2, k + 1):
            # The prefix is arms 1..j of the declared order, never a per-set subset.
            prefix = acts[:, :j]
            indicator = (prefix.min(axis=1) == prefix.max(axis=1)).astype(np.int64)
            by_prefix[j] = indicator
            rule_agree[f"j{j}"] = _metric_block(clusters, indicator, seed, b, _WITHIN_SWEEP)
        steps: dict[str, Any] = {}
        for j in range(2, k):
            both = (
                rule_agree[f"j{j}"]["basis"] == "cluster_bootstrap"
                and rule_agree[f"j{j + 1}"]["basis"] == "cluster_bootstrap"
            )
            steps[f"j{j}_to_j{j + 1}"] = _step_block(
                clusters, by_prefix[j + 1] - by_prefix[j], seed, b, both
            )
        rule_agree["steps"] = steps
        agree[rule] = rule_agree

        rule_majority: dict[str, Any] = {}
        for j in range(1, stops + 1, 2):
            maj = (2 * acts[:, :j].sum(axis=1) > j).astype(np.int64)
            obs_clusters, obs = _majority_observations(set_keys, sweeps, maj, sweep_names)
            rule_majority[f"j{j}"] = _metric_block(obs_clusters, obs, seed, b, _ACROSS_SWEEPS)
        majority[rule] = rule_majority

        rule_framing: dict[str, Any] = {}
        for j in range(1, stops + 1, 2):
            rule_framing[f"j{j}"] = _cost_framing(
                j, rule_majority[f"j{j}"], declaration, assertion.environment, cost, windows
            )
        framing[rule] = rule_framing

    counts = _replicate_counts(
        assertion, cut, arm_labels, rows, values, set_keys, sweeps, sweep_names, rules, stops
    )
    return ReplicateResult(
        name=cut.name,
        threshold=cut.threshold,
        k=k,
        agree=agree,
        majority=majority,
        counts=counts,
        cost_framing=framing,
    )


def _whole_sets(rows: pd.DataFrame, value_columns: Sequence[str]) -> pd.DataFrame:
    """All ``k``, or none: the rows of ``pairs`` that are whole replicate sets. A row
    kept for its declared pair alone carries ``None`` in arms ``3..k`` and is not read here."""
    whole = [
        all(not pd.isna(v) for v in values)
        for values in zip(*(rows[column] for column in value_columns), strict=True)
    ]
    return rows[whole].reset_index(drop=True) if len(rows) else rows


def _majority_observations(
    set_keys: Sequence[tuple[Any, ...]],
    sweeps: Sequence[str],
    maj: NDArray[np.int64],
    sweep_names: Sequence[str],
) -> tuple[list[Any], list[int]]:
    """One observation per replicate set and per **unordered** pair of distinct sweeps in which
    both of that item's sets are eligible: ``1`` when the two majorities are equal. The
    cluster is the item; with one sweep there is no observation at all."""
    by_key: dict[tuple[Any, ...], dict[str, int]] = {}
    for key, sweep, m in zip(set_keys, sweeps, maj, strict=True):
        by_key.setdefault(key, {})[sweep] = int(m)
    obs_clusters: list[Any] = []
    obs: list[int] = []
    for key, majorities in by_key.items():
        for first, second in itertools.combinations(sweep_names, 2):
            if first in majorities and second in majorities:
                obs_clusters.append(key[0])
                obs.append(int(majorities[first] == majorities[second]))
    return obs_clusters, obs


def _metric_block(
    clusters: Sequence[Any], indicators: Sequence[int], seed: int, b: int, observation: str
) -> dict[str, Any]:
    """One k-metric at one prefix under one rule: the mean of the indicator, its interval and
    its design effect. The interval is the pooled estimator through the one ``_cluster_bootstrap``,
    drawn afresh from ``bootstrap_seed``; when fewer than five item clusters carry a
    disagreement it is the one-sided exact 95% lower bound on the item-level agreement
    probability, with the upper bound one by observation. ``m_bar`` is observations per
    item for this metric."""
    frame = pd.DataFrame({"cluster": list(clusters), "flip": list(indicators)})
    if len(frame) == 0:
        return {
            "estimate": None,
            "lo": None,
            "hi": None,
            "basis": "not_estimated",
            "observation": observation,
            "design_effect": _design_effect(frame),
        }
    groups = _clusters(frame, "flip")
    g_count = len(groups)
    estimate = float(frame["flip"].sum() / len(frame))
    k_dis = int(sum(1 for grp in groups if (grp == 0).any()))
    block: dict[str, Any]
    if k_dis < _FALLBACK_BELOW:
        # A percentile bootstrap degenerating to [1, 1] would read as a certainty and is not
        # one: the pooled fallback's reasoning, pointed the other way. At zero disagreeing items
        # the bound is 0.05 ** (1 / G).
        block = {
            "estimate": estimate,
            "lo": float(_beta.ppf(0.05, g_count - k_dis, k_dis + 1)) if g_count > k_dis else 0.0,
            "hi": 1.0,
            "basis": "exact_lower_one_sided",
            "upper_bound_by_observation": True,
        }
    else:
        lo, hi = _cluster_bootstrap(groups, seed, b)
        block = {"estimate": estimate, "lo": lo, "hi": hi, "basis": "cluster_bootstrap"}
    block["observation"] = observation
    block["design_effect"] = _design_effect(frame)
    return block


def _step_block(
    clusters: Sequence[Any], d: NDArray[np.int64], seed: int, b: int, both: bool
) -> dict[str, Any]:
    """The difference between two prefixes as one paired quantity, bootstrapped over items
    on its own per-set differences -- the same resample indices as every other draw from this
    seed -- and never two intervals compared by overlap. Not estimated when either endpoint is
    under the fallback."""
    estimate = float(np.mean(d)) if len(d) else None
    if not both:
        return {"estimate": estimate, "lo": None, "hi": None, "basis": "not_estimated"}
    groups = _clusters(pd.DataFrame({"cluster": list(clusters), "d": list(d)}), "d")
    lo, hi = _cluster_bootstrap(groups, seed, b)
    return {"estimate": estimate, "lo": lo, "hi": hi, "basis": "cluster_bootstrap"}


def _cost_framing(
    j: int,
    ms: Mapping[str, Any],
    declaration: Declaration,
    environment: Mapping[str, Any],
    cost: CostReport | None,
    windows: WindowReport | None,
) -> dict[str, Any]:
    """The cost framing, per odd ``j``. The per-10,000 figure carries both bounds from the same
    clustered interval and the declared conditioning in one object, and is not emitted without a
    conditioning; the dollar row needs a priced cost report with recorded spans; the latency row
    needs the windows. What is absent is absent, never zero."""
    block: dict[str, Any] = {}
    if declaration.conditioning is not None and ms["estimate"] is not None:
        block["per_10000"] = {
            "n": round(_PER_TEN_THOUSAND * (1 - ms["estimate"])),
            "n_lo": round(_PER_TEN_THOUSAND * (1 - ms["hi"])),
            "n_hi": round(_PER_TEN_THOUSAND * (1 - ms["lo"])),
            "conditioning": declaration.conditioning,
        }
    if cost is not None and cost.price_per_input_token is not None and cost.recorded_spans:
        mean_tokens = cost.input_tokens / cost.recorded_spans
        block["dollars_per_decision"] = {
            "estimate": float(j * mean_tokens * float(cost.price_per_input_token)),
            "mean_input_tokens": float(mean_tokens),
            "price_per_input_token": format(cost.price_per_input_token, "f"),
        }
    if windows is not None:
        medians = [
            float(entry["latency_s"]["median"])
            for entry in windows.per_sweep
            if isinstance(entry.get("latency_s"), Mapping)
        ]
        if medians:
            median = float(np.median(medians))
            row: dict[str, Any] = {"median_call_s": median, "serial_s": j * median}
            concurrency = _declared_concurrency(environment)
            if concurrency:
                row["at_declared_concurrency_s"] = j * median / concurrency
            block["latency_per_decision"] = row
    return block


def _declared_concurrency(environment: Mapping[str, Any]) -> float | None:
    """The one concurrency every arm's manifest recorded, or ``None`` when any arm is silent or
    the arms disagree."""
    sweeps = environment.get("sweeps")
    if not isinstance(sweeps, Mapping) or not sweeps:
        return None
    seen: set[float] = set()
    for per_arm in sweeps.values():
        if not isinstance(per_arm, Mapping) or not per_arm:
            return None
        for identity in per_arm.values():
            value = identity.get("concurrency") if isinstance(identity, Mapping) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                return None
            seen.add(float(value))
    return seen.pop() if len(seen) == 1 else None


def _replicate_counts(
    assertion: PairAssertion,
    cut: Cut,
    arm_labels: Sequence[str],
    rows: pd.DataFrame,
    values: Sequence[Sequence[Decimal]],
    set_keys: Sequence[tuple[Any, ...]],
    sweeps: Sequence[str],
    sweep_names: Sequence[str],
    rules: Mapping[str, str],
    stops: int,
) -> dict[str, Any]:
    """The cut's counts: items, sweeps, eligible sets per sweep, sweep pairs per item, the
    exclusions per arm off this cut's rows of ``excluded``, ties per arm over all sweeps, the
    two rules and where the majority curve stops. No key holds ``G x S``."""
    present: dict[tuple[Any, ...], set[str]] = {}
    for key, sweep in zip(set_keys, sweeps, strict=True):
        present.setdefault(key, set()).add(sweep)
    excluded = assertion.excluded
    excluded_rows = excluded[excluded["cut"] == cut.name] if len(excluded) else excluded
    excluded_by_arm = {label: 0 for label in (*arm_labels, "both")}
    for arm in excluded_rows["arm"] if len(excluded_rows) else []:
        excluded_by_arm[str(arm)] = excluded_by_arm.get(str(arm), 0) + 1
    return {
        "items": int(rows["cluster"].nunique()) if len(rows) else 0,
        "sweeps": len(sweep_names),
        "eligible_sets": {name: int(sum(1 for s in sweeps if s == name)) for name in sweep_names},
        "sweep_pairs": {
            f"{first}|{second}": sum(
                1 for held in present.values() if first in held and second in held
            )
            for first, second in itertools.combinations(sweep_names, 2)
        },
        "excluded_by_arm": excluded_by_arm,
        "ties": {
            label: int(sum(1 for v in arm if v == cut.threshold))
            for label, arm in zip(arm_labels, values, strict=True)
        },
        "rules": dict(rules),
        "majority_stops_at": stops,
    }


# ---------- the artifacts and the rendered sections ----------


_ARTIFACT_NAMES: tuple[str, ...] = (
    "pair_assertion.json",
    "contingency_by_cut.json",
    "intervals_by_cut.json",
    "windows.json",
    "cost.json",
)
_SIXTH = "replicates_by_cut.json"
_PAYLOAD_KEYS: dict[str, str] = {
    "pair_assertion.json": "pair_assertion",
    "contingency_by_cut.json": "contingency_by_cut",
    "intervals_by_cut.json": "intervals_by_cut",
    "windows.json": "windows",
    "cost.json": "cost",
    _SIXTH: "replicates_by_cut",
}
_FENCE_MD = "> This is empirical evidence under a stated test envelope"
_FENCE_HTML = "<blockquote>"
_PROVENANCE_HTML_END = "</ul>\n</body>"


@dataclass(frozen=True)
class _Bundle:
    """Everything one declaration produces from one store, as the CLI writes and renders it."""

    declaration: Declaration
    assertion: PairAssertion
    result: PairedResult
    windows: WindowReport
    cost: CostReport
    replicates: tuple[ReplicateResult, ...]
    artifacts: Mapping[str, Any]  # file name -> the JSON tree the file carries, in order

    @property
    def payload(self) -> dict[str, Any]:
        return {_PAYLOAD_KEYS[name]: tree for name, tree in self.artifacts.items()}


def _bundle(store: Store, declaration: Declaration) -> _Bundle:
    """The assertion, the analysis, the windows, the cost with one phase per declared sweep, and
    the replicates, in that order; then the five artifacts, six at ``k > 2``."""
    assertion = assert_pairs(store, declaration)
    result = analyse(assertion)
    window_report = windows(assertion)
    cost_report = cost(
        store, declaration, phases={sweep.name: sweep.arms for sweep in declaration.sweeps}
    )
    replicate_results = replicates(assertion, cost=cost_report, windows=window_report)
    digest = declaration.digest
    out: dict[str, Any] = {
        "pair_assertion.json": json.loads(assertion.to_json()),
        "contingency_by_cut.json": json.loads(result.contingency_json()),
        "intervals_by_cut.json": json.loads(result.intervals_json()),
        "windows.json": {"declaration_digest": digest, **json.loads(window_report.to_json())},
        "cost.json": {"declaration_digest": digest, **json.loads(cost_report.to_json())},
    }
    if replicate_results:
        out[_SIXTH] = {
            "declaration_digest": digest,
            "cuts": {r.name: json.loads(r.to_json()) for r in replicate_results},
        }
    return _Bundle(
        declaration=declaration,
        assertion=assertion,
        result=result,
        windows=window_report,
        cost=cost_report,
        replicates=replicate_results,
        artifacts=out,
    )


def _cost_block(declaration: Declaration, report: CostReport) -> dict[str, Any]:
    """The ``--cap-check`` block: ``cost.json``'s tree, the digest first."""
    return {"declaration_digest": declaration.digest, **json.loads(report.to_json())}


def _artifact_text(tree: Mapping[str, Any]) -> str:
    return json.dumps(tree, indent=2, ensure_ascii=False)


def _num(value: Any) -> str:
    """A number as the artifact carries it: the JSON value's own text, a literal verbatim, so
    every number printed is a byte of an artifact. The renderer computes nothing."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return json.dumps(_jsonable(value))


def _interval(block: Mapping[str, Any]) -> str:
    if block.get("lo") is None or block.get("hi") is None:
        return "(not estimated)"
    basis = str(block.get("basis", "")).replace("_", " ")
    return f"[{_num(block['lo'])}, {_num(block['hi'])}] ({basis})"


def _design(block: Mapping[str, Any]) -> str:
    d = block.get("design_effect")
    if not isinstance(d, Mapping):
        return ""
    return f"; icc {_num(d['icc'])}, m_bar {_num(d['m_bar'])}, deff {_num(d['deff'])}"


def _sections(bundle: _Bundle) -> list[tuple[str, list[str]]]:
    """The four sections as (title, lines): **Paired replay**, **Replicates** at ``k > 2`` only,
    **Windows**, **Cost**. Every number is read off the artifact trees, never recomputed;
    no verdict word is printed; the conditioning is printed verbatim
    beside every rate where declared, and nothing stands in for it where not."""
    declaration = bundle.declaration
    beside = f" -- {declaration.conditioning}" if declaration.conditioning is not None else ""
    contingency = bundle.artifacts["contingency_by_cut.json"]["cuts"]
    intervals = bundle.artifacts["intervals_by_cut.json"]["cuts"]
    sections: list[tuple[str, list[str]]] = []

    lines: list[str] = [
        "Two stored arms are a pair only when they were the same request twice; the assertion "
        "ran before any comparison, and every count reconciles in pair_assertion.json.",
        "",
    ]
    for name, c_block in contingency.items():
        i_block = intervals[name]
        lines.append(
            f"### {name} (threshold {_num(c_block['threshold'])}, {c_block['comparison']})"
        )
        lines.append("")
        for sweep_name, sweep in c_block["per_sweep"].items():
            rates = i_block["per_sweep"][sweep_name]
            check = sweep["arm_order_check"]
            lines.append(
                f"- {sweep_name}: n11 = {_num(sweep['n11'])}, n10 = {_num(sweep['n10'])}, "
                f"n01 = {_num(sweep['n01'])}, n00 = {_num(sweep['n00'])}, n = {_num(sweep['n'])}; "
                f"ties a = {_num(sweep['ties']['a'])}, b = {_num(sweep['ties']['b'])}; "
                f"rate a {_num(rates['rate_a'])}, rate b {_num(rates['rate_b'])}; flip rate "
                f"{_num(rates['flip_rate']['estimate'])} {_interval(rates['flip_rate'])}, "
                f"net swing {_num(rates['net_swing']['estimate'])} (b minus a){beside}"
            )
            lines.append(
                f"  arm order check: p = {_num(check['p'])}, n discordant = "
                f"{_num(check['n_discordant'])}, can reject = {_num(check['can_reject'])}"
            )
        n = i_block["n"]
        flip = i_block["flip_rate"]
        swing = i_block["net_swing"]
        lines.append(
            f"- pooled over {_num(n['items'])} items and {_num(n['sweeps'])} sweeps: flip rate "
            f"{_num(flip['estimate'])} {_interval(flip)}, net swing {_num(swing['estimate'])} "
            f"{_interval(swing)} (b minus a){beside}"
        )
        lines.append(
            f"  design effect: icc {_num(i_block['design_effect']['icc'])}, m_bar "
            f"{_num(i_block['design_effect']['m_bar'])}, deff "
            f"{_num(i_block['design_effect']['deff'])}; ineligibility rate "
            f"{_num(i_block['ineligibility_rate'])}"
        )
        outcome = i_block["outcome"]
        lines.append(
            "  outcome: none without a declared floor."
            if outcome is None
            else f"  outcome: {outcome}, decided from the pooled flip rate interval "
            f"{_interval(i_block['outcome_interval'])}."
        )
        lines.append("")
    sections.append(("Paired replay", lines))

    if _SIXTH in bundle.artifacts:
        sections.append(("Replicates", _replicates_lines(bundle, beside)))

    w = bundle.artifacts["windows.json"]
    lines = [
        "Each sweep is its own window, read from the request spans' timestamps in the trace "
        "envelope. No pair was dropped on any timing criterion.",
        "",
    ]
    for entry in w["per_sweep"]:
        declared = entry["declared_window_s"]
        window_text = (
            "no declared window" if declared is None else f"declared window {_num(declared)} s"
        )
        if entry["timing"] == "available":
            claim = "" if entry["claim"] is None else f"; claim {entry['claim']}"
            latency = entry["latency_s"]
            latency_text = (
                "; no per-call latency recorded"
                if latency is None
                else f"; latency median {_num(latency['median'])} s over {_num(latency['n'])} calls"
            )
            lines.append(
                f"- {entry['sweep']}: timing available; realized span "
                f"{_num(entry['realized_span_s'])} s; {window_text}{claim}{latency_text}"
            )
        else:
            lines.append(
                f"- {entry['sweep']}: timing unavailable ({entry['reason']}); {window_text}; "
                "no span, no claim"
            )
    lines.append("")
    lines.append("Replay gap per cut, arm b's request start minus arm a's, in seconds:")
    lines.append("")
    for name, gap in w["replay_gap"].items():
        if gap is None:
            lines.append(f"- {name}: no computable gap")
        else:
            lines.append(
                f"- {name}: min {_num(gap['min'])}, median {_num(gap['median'])}, max "
                f"{_num(gap['max'])}"
            )
    lines.append("")
    sections.append(("Windows", lines))

    c = bundle.artifacts["cost.json"]
    lines = [
        "Input tokens are the provider's own recorded usage on every request span, retries "
        "included; the module holds no tokeniser and no rate card.",
        "",
        f"- input tokens: {_num(c['input_tokens'])}",
        f"- output tokens: {_num(c['output_tokens'])}",
        f"- recorded spans: {_num(c['recorded_spans'])}",
        f"- unrecorded spans: {_num(c['unrecorded_spans'])}",
    ]
    if c["price_per_input_token"] is None:
        lines.append("- price per input token: no price declared, so no dollar figure is printed")
    else:
        lines.append(f"- price per input token: {_num(c['price_per_input_token'])}")
        lines.append(f"- dollars: {_num(c['dollars'])} (input tokens times the price)")
    lines.append(
        "- token cap: none declared"
        if c["token_cap"] is None
        else f"- token cap: {_num(c['token_cap'])}; cap reached: {_num(c['cap_reached'])}"
    )
    lines.append("")
    lines.append(
        "| phase | run id | sweep | arm | input tokens | output tokens | recorded spans | "
        "unrecorded spans |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for entry in c["phases"]:
        lines.append(
            f"| {entry['phase']} | {entry['run_id']} | {_num(entry['sweep'])} | "
            f"{_num(entry['arm'])} | {_num(entry['input_tokens'])} | "
            f"{_num(entry['output_tokens'])} | {_num(entry['recorded_spans'])} | "
            f"{_num(entry['unrecorded_spans'])} |"
        )
    lines.append("")
    lines.append(
        "The cap is checked between sweeps and never halts a sweep in flight; the worst-case "
        "overshoot is one sweep."
    )
    lines.append("")
    sections.append(("Cost", lines))
    return sections


def _replicates_lines(bundle: _Bundle, beside: str) -> list[str]:
    """The **Replicates** section: every number a leaf of ``replicates_by_cut.json``."""
    cuts = bundle.artifacts[_SIXTH]["cuts"]
    lines: list[str] = [
        "Each item was sent k times per sweep. agree@j is the rate at which the first j calls of "
        "an item in one sweep all took one action, so all j decisions agreed; MS@j is the rate "
        "at which two sweeps' j-call majority decisions for one item agreed. Both are computed "
        "under the cut's declared comparison (primary) and under the other one (sensitivity), "
        "and every interval is the item-clustered bootstrap.",
        "",
    ]
    for name, block in cuts.items():
        counts = block["counts"]
        lines.append(
            f"### {name} (threshold {_num(block['threshold'])}, {block['comparison']}, "
            f"k = {_num(block['k'])})"
        )
        lines.append("")
        eligible = ", ".join(f"{s} {_num(n)}" for s, n in counts["eligible_sets"].items())
        pairs = ", ".join(f"{s} {_num(n)}" for s, n in counts["sweep_pairs"].items())
        ties = ", ".join(f"arm-{label} {_num(n)}" for label, n in counts["ties"].items())
        lines.append(
            f"- {_num(counts['items'])} items over {_num(counts['sweeps'])} sweeps; eligible "
            f"sets per sweep: {eligible}; items with both sets eligible per sweep pair: "
            f"{pairs or 'none'}; ties per arm: {ties}; the majority curve stops at "
            f"j = {_num(counts['majority_stops_at'])}"
        )
        for rule in ("primary", "sensitivity"):
            comparison = counts["rules"][rule]
            lines.append("")
            lines.append(f"Under the {rule} rule ({comparison}):")
            lines.append("")
            for key, entry in block["agree"][rule].items():
                if key == "steps":
                    continue
                lines.append(
                    f"- agree@{key[1:]}: {_num(entry['estimate'])} {_interval(entry)}"
                    f"{_design(entry)}{beside}"
                )
            for key, step in block["agree"][rule]["steps"].items():
                low, high = key.split("_to_")
                lines.append(
                    f"- step agree@{low[1:]} to agree@{high[1:]}: {_num(step['estimate'])} "
                    f"{_interval(step)}, paired on the same draws"
                )
            for key, entry in block["majority"][rule].items():
                lines.append(
                    f"- MS@{key[1:]}: {_num(entry['estimate'])} {_interval(entry)}"
                    f"{_design(entry)}{beside}"
                )
            for key, entry in block["cost_framing"][rule].items():
                parts: list[str] = []
                if "per_10000" in entry:
                    ten = entry["per_10000"]
                    parts.append(
                        f"out of 10,000 near-cut decisions, {_num(ten['n'])} decided "
                        f"differently [{_num(ten['n_lo'])}, {_num(ten['n_hi'])}] -- "
                        f"{ten['conditioning']}"
                    )
                if "dollars_per_decision" in entry:
                    d = entry["dollars_per_decision"]
                    parts.append(
                        f"dollars per decision {_num(d['estimate'])} (mean recorded input "
                        f"tokens {_num(d['mean_input_tokens'])} at a price of "
                        f"{_num(d['price_per_input_token'])} per input token)"
                    )
                if "latency_per_decision" in entry:
                    lat = entry["latency_per_decision"]
                    text = (
                        f"latency per decision {_num(lat['serial_s'])} s serial (median call "
                        f"{_num(lat['median_call_s'])} s)"
                    )
                    if "at_declared_concurrency_s" in lat:
                        text += (
                            f", {_num(lat['at_declared_concurrency_s'])} s at the declared "
                            "concurrency"
                        )
                    parts.append(text)
                if parts:
                    lines.append(f"- MS@{key[1:]} cost framing: " + "; ".join(parts))
        lines.append("")
    return lines


def _provenance_lines(bundle: _Bundle) -> list[tuple[str, str]]:
    c = bundle.artifacts["cost.json"]
    declaration = bundle.declaration
    return [
        ("declaration digest", declaration.digest),
        ("bootstrap seed", str(declaration.bootstrap_seed)),
        ("bootstrap b", str(declaration.bootstrap_b)),
        ("price per input token", _num(c["price_per_input_token"])),
        ("input tokens", _num(c["input_tokens"])),
        ("output tokens", _num(c["output_tokens"])),
        ("artifacts", ", ".join(bundle.artifacts)),
    ]


def _fold_markdown(text: str, bundle: _Bundle) -> str:
    """The sections into ``report.md`` before the epistemic fence, and the seven provenance
    lines after the block's own. ``report.py`` renders the rest and is not edited."""
    parts: list[str] = []
    for title, lines in _sections(bundle):
        parts += [f"## {title}", "", *lines]
    index = text.index(_FENCE_MD)
    provenance = "".join(f"- {key}: {value}\n" for key, value in _provenance_lines(bundle))
    folded = text[:index] + "\n".join(parts) + "\n" + text[index:]
    return folded + ("" if folded.endswith("\n") else "\n") + provenance


def _fold_html(text: str, bundle: _Bundle) -> str:
    """The same sections into ``receipt.html`` as ``<h2>`` sections before the ``<blockquote>``,
    and the provenance lines into the block's list."""
    parts: list[str] = []
    for title, lines in _sections(bundle):
        parts.append(f"<h2>{_html.escape(title)}</h2>")
        parts += _html_lines(lines)
    index = text.index(_FENCE_HTML)
    folded = text[:index] + "\n".join(parts) + "\n" + text[index:]
    items = "".join(
        f"<li>{_html.escape(f'{key}: {value}')}</li>" for key, value in _provenance_lines(bundle)
    )
    end = folded.rindex(_PROVENANCE_HTML_END)
    return folded[:end] + items + folded[end:]


def _html_lines(lines: Sequence[str]) -> list[str]:
    """Markdown-shaped lines as HTML: a heading, a table, a list or a paragraph per block."""
    out: list[str] = []
    bullets: list[str] = []
    table: list[str] = []

    def flush() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_html.escape(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()
        if table:
            rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table]
            head = "".join(f"<th>{_html.escape(h)}</th>" for h in rows[0])
            body = "".join(
                "<tr>" + "".join(f"<td>{_html.escape(v)}</td>" for v in r) + "</tr>"
                for r in rows[2:]
            )
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
            table.clear()

    for line in lines:
        if line.startswith("### "):
            flush()
            out.append(f"<h3>{_html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if table:
                flush()
            bullets.append(line[2:])
        elif line.startswith("  ") and bullets:
            bullets[-1] += " " + line.strip()
        elif line.startswith("|"):
            if bullets:
                flush()
            table.append(line)
        elif not line.strip():
            flush()
        else:
            flush()
            out.append(f"<p>{_html.escape(line)}</p>")
    flush()
    return out
