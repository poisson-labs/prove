"""Paired replay, phase 1: the declaration, the canonical request and the pair assertion.

Two stored arms are only a pair if they were *the same request twice*, and this module says so
before anything compares a number. The declaration is loaded whole and refuses what it does not
know (PR1-PR8); the request is canonicalised without ever passing a number through ``float``
(PR11); every matched key is either eligible or excluded with one named cause, and the counts
reconcile (PR9-PR21). Nothing here computes a rate -- the analysis, the windows and the cost are
phases 2 and 3 of "Prove -- Spec PR Paired Replay".

The canonicaliser is the part where a silent bug would be invisible and total. A JSON round-trip
through Python's ``float`` is the obvious implementation and it is wrong: it makes the digest
blind to exactly the difference the assertion exists to catch -- a ``top_p`` written ``0.95``
against one written ``0.95000000000000001``, a ``max_tokens`` of ``1`` against ``1.0``. Numbers
are parsed into ``_Literal``, which keeps the text the wire carried, and emitted verbatim.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from proofload.store import Store
from proofload.trace import Trace, TraceValidationError


class PairedError(Exception):
    """Every refusal this module makes."""


class DeclarationError(PairedError):
    """The declaration is not loadable, or it does not describe the stored runs."""


class NotAssertable(PairedError):
    """A run-level fact blocks the assertion. It is never a property of one pair."""


class NoEligiblePairs(PairedError):
    """The assertion left a cut with nothing. Phase 1 defines it; who raises it is phase 2's."""


# ---------- the declaration ----------


_WORDS: tuple[str, ...] = ("asserted", "not_recorded")
_CUT_KEYS = frozenset({"name", "threshold"})
_SWEEP_KEYS = frozenset({"name", "a", "b"})


@dataclass(frozen=True)
class Cut:
    name: str
    threshold: Decimal  # from a decimal literal; never parsed through float


@dataclass(frozen=True)
class SweepPair:
    name: str  # the replication's label, e.g. "S1"
    a: str  # run id of arm A
    b: str  # run id of arm A'


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

    # how it is estimated -- ADR-096's no-default rule, applied to an estimator's parameters
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
            "cuts": [{"name": c.name, "threshold": _text(c.threshold)} for c in self.cuts],
            "sweeps": [{"name": s.name, "a": s.a, "b": s.b} for s in self.sweeps],
            "request_span": self.request_span,
            "model_key": self.model_key,
            "model_pin": self.model_pin,
            # Verbatim, not sorted: the order of ``exemptions`` is left unpinned by the spec,
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
            Cut(name=_str(path, table, "name"), threshold=_decimal(path, table, "threshold"))
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
        for key in sorted(_SWEEP_KEYS):
            if key not in table:
                raise DeclarationError(f"{path}: a sweep is missing {key}: {table}")
        sweeps.append(
            SweepPair(
                name=_str(path, table, "name"),
                a=_str(path, table, "a"),
                b=_str(path, table, "b"),
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
    """Assert that each pair of stored rows was the same request twice.

    The order of the refusals is the order of what they are about. A declaration that does not
    describe these runs -- strata that overlap, an exemption that names a body field -- is a
    ``DeclarationError``. A fact about the *run* that cannot be asserted -- the two arms'
    manifests disagreeing, a header identity with nothing recorded to assert it on, a retry
    setting the manifest is silent about, one row's seed moving -- is a ``NotAssertable``, never
    a per-pair exclusion. Everything left is per pair: eligible, or excluded with one named
    cause, counted, and never repaired.
    """
    arms = {
        (sweep.name, arm): _read_arm(store, run_id, sweep.name, arm, declaration)
        for sweep in declaration.sweeps
        for arm, run_id in (("a", sweep.a), ("b", sweep.b))
    }
    _check_strata(arms.values(), declaration)
    _check_exemptions(arms.values(), declaration)
    environment = _environment(store, declaration)
    _check_seeds(arms, declaration)

    pairs: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    exercised: dict[str, int] = {name.lower(): 0 for name in declaration.exemptions}
    keys_by_cut: dict[Any, int] = {}
    for sweep in declaration.sweeps:
        rows_a = arms[(sweep.name, "a")]
        rows_b = arms[(sweep.name, "b")]
        for key in sorted(set(rows_a) | set(rows_b)):
            row = rows_a.get(key) or rows_b[key]
            keys_by_cut[row.cut] = keys_by_cut.get(row.cut, 0) + 1
            if key not in rows_a or key not in rows_b:
                held = "a" if key in rows_a else "b"
                excluded.append(
                    _excluded_row(
                        row, "unmatched", held, f"the key is in arm {held} of {sweep.name} only"
                    )
                )
                continue
            verdict = _judge(rows_a[key], rows_b[key], declaration)
            if verdict.cause is not None:
                excluded.append(
                    _excluded_row(row, verdict.cause, verdict.arm, verdict.detail)
                )
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
                    "value_a": verdict.value_a,
                    "value_b": verdict.value_b,
                }
            )

    order = ("sweep", "cut", "cluster", "config_hash", "replicate_index")
    pairs.sort(key=lambda r: tuple(str(r[k]) for k in order))
    excluded.sort(key=lambda r: tuple(str(r[k]) for k in order))
    counts = _counts(pairs, excluded, keys_by_cut, declaration, exercised)
    return PairAssertion(
        declaration=declaration,
        pairs=_frame(pairs, _PAIRS_COLUMNS),
        excluded=_frame(excluded, _EXCLUDED_COLUMNS),
        environment=environment,
        counts=counts,
    )


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
    """PR3. The declaration file lists cuts, not items, so an overlap becomes visible only here.
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
    """PR4. Every name in ``exemptions`` is a header or a transport identifier. A name that
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
    """PR15, PR17, PR18. Per-arm identity, compared and recorded; the gaps printed.

    ``harness_digest`` and ``client_version`` are printed as gaps on every run and compared on
    none: they are the harness's to record and no ``meta`` key convention exists for them yet
    (spec section 10 item 3, deferred).
    """
    sweeps: dict[str, dict[str, dict[str, Any]]] = {}
    gaps = ["harness_digest", "client_version"]
    for sweep in declaration.sweeps:
        per_arm = {
            arm: _arm_identity(store, run_id)
            for arm, run_id in (("a", sweep.a), ("b", sweep.b))
        }
        differing = sorted(
            key for key in per_arm["a"] if per_arm["a"][key] != per_arm["b"][key]
        )
        if differing:
            raise NotAssertable(
                f"sweep {sweep.name!r}: the two arms' manifests disagree on "
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
        "proofload_version": manifest.proofload_version,
        "run_salt": manifest.run_salt,
        "python": environment.get("python"),
        "concurrency": environment.get("concurrency"),
        "capture_cap": (
            capture.get("max_observation_bytes") if isinstance(capture, Mapping) else None
        ),
    }


def _check_retries(store: Store, declaration: Declaration) -> None:
    """PR18's manifest half. ``retries = "asserted"`` requires both arms' manifests to record
    ``infra_retries == 0`` (PR56). A manifest that is silent is a refusal, the same rule as
    PR15: silence is never a pass."""
    for sweep in declaration.sweeps:
        for arm, run_id in (("a", sweep.a), ("b", sweep.b)):
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
    """PR15. With nothing recorded under ``http.request.header.*`` on either arm, header
    identity cannot be asserted, and under ``headers = "asserted"`` that is a refusal."""
    for sweep in declaration.sweeps:
        recorded = False
        for run_id in (sweep.a, sweep.b):
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


def _check_seeds(arms: Mapping[tuple[str, str], Any], declaration: Declaration) -> None:
    """PR17's per-row half. A matched key whose seed moved between the arms is a run-level
    refusal: the two rows are not the same draw, and that is not a property of one pair."""
    for sweep in declaration.sweeps:
        rows_a = arms[(sweep.name, "a")]
        rows_b = arms[(sweep.name, "b")]
        for key in sorted(set(rows_a) & set(rows_b)):
            if rows_a[key].seed != rows_b[key].seed:
                raise NotAssertable(
                    f"sweep {sweep.name!r}: item {rows_a[key].cluster!r} carries seed "
                    f"{rows_a[key].seed} in arm a and {rows_b[key].seed} in arm b. The arms are "
                    "not the same draw."
                )


# ---------- one pair ----------


@dataclass(frozen=True)
class _Verdict:
    cause: str | None = None
    arm: str = "both"
    detail: str = ""
    digest: str = ""
    exercised: tuple[str, ...] = ()
    value_a: Decimal | None = None
    value_b: Decimal | None = None


def _judge(a: _Row, b: _Row, declaration: Declaration) -> _Verdict:
    """One matched key, in the order of what each check is about: the row, then the request,
    then the body, then the target, then the measured value. Every test in the oracle builds one
    failure per pair, so the precedence between two causes on one pair is not pinned; a pair
    broken in both arms may take either of them."""
    errored = _which(a.error is not None, b.error is not None)
    if errored is not None:
        return _Verdict("errored", errored, _first_of(a.error, b.error) or "the row errored")

    absent = _which(not a.spans, not b.spans)
    if absent is not None:
        return _Verdict(
            "no_request_span",
            absent,
            f"no span named {declaration.request_span!r}; the declaration names the request",
        )
    repeated = _which(len(a.spans) > 1, len(b.spans) > 1)
    if repeated is not None:
        return _Verdict(
            "retry_or_multicall",
            repeated,
            f"{max(len(a.spans), len(b.spans))} spans named {declaration.request_span!r} in one "
            "episode; a repeat is a third draw",
        )

    body_a, body_b = _body(a.spans[0]), _body(b.spans[0])
    malformed = _which(body_a is None, body_b is None)
    if malformed is not None:
        return _Verdict("malformed_body", malformed, "the stored request is not a JSON object")
    assert body_a is not None and body_b is not None  # noqa: S101 - narrowed by the check above

    pin_a = _resolve(body_a, declaration.model_key)
    pin_b = _resolve(body_b, declaration.model_key)
    off_pin = _which(not _at_pin(pin_a, declaration), not _at_pin(pin_b, declaration))
    if off_pin is not None:
        # Asserted, never inherited: the ``both`` case is two arms that agree with each other
        # and not with the pin, and it is still not a pair at the pinned model.
        return _Verdict(
            "model_pin",
            off_pin,
            f"{declaration.model_key} is {_shown(pin_a)} in arm a and {_shown(pin_b)} in arm b; "
            f"the pin is {declaration.model_pin!r}",
        )

    leaves_a = dict(_leaves(body_a))
    leaves_b = dict(_leaves(body_b))
    only = sorted(set(leaves_a) ^ set(leaves_b))
    if only:
        return _Verdict(
            "body_field_absent",
            "both",
            f"present in one arm and absent in the other: {', '.join(only)}",
        )
    canonical_a, canonical_b = canonical_request(a.spans[0].input), canonical_request(
        b.spans[0].input
    )
    if canonical_a != canonical_b:
        moved = sorted(
            path for path, value in leaves_a.items() if _emit(value) != _emit(leaves_b[path])
        )
        return _Verdict("body", "both", f"the arms differ at: {', '.join(moved)}")

    target_a, target_b = _target_of(a.spans[0]), _target_of(b.spans[0])
    if target_a != target_b:
        moved = sorted(key for key in _TARGET_KEYS if target_a[key] != target_b[key])
        return _Verdict("target", "both", f"the arms differ at: {', '.join(moved)}")

    headers_a, headers_b = _headers_of(a.spans[0]), _headers_of(b.spans[0])
    exempt = {name.lower() for name in declaration.exemptions}
    differing = sorted(
        name
        for name in set(headers_a) | set(headers_b)
        if headers_a.get(name) != headers_b.get(name)
    )
    unexempted = [name for name in differing if name not in exempt]
    if unexempted:
        return _Verdict("header", "both", f"the arms differ at: {', '.join(unexempted)}")

    value_a, missing_a = _value_of(a, declaration)
    value_b, missing_b = _value_of(b, declaration)
    absent_value = _which(missing_a, missing_b)
    if absent_value is not None:
        return _Verdict(
            "value_missing",
            absent_value,
            f"the episode records no {declaration.value_key}",
        )
    out_of_range = _which(not _in_unit(value_a), not _in_unit(value_b))
    if out_of_range is not None:
        return _Verdict(
            "value_out_of_range",
            out_of_range,
            f"{declaration.value_key} is {_shown(value_a)} in arm a and {_shown(value_b)} in "
            "arm b; the interval is [0, 1]",
        )

    exercised = tuple(
        name.lower() for name in declaration.exemptions if name.lower() in differing
    )
    digest = request_digest(
        a.spans[0].input,
        target=target_a,
        headers=headers_a,
        exemptions=declaration.exemptions,
    )
    return _Verdict(
        digest=digest, exercised=exercised, value_a=value_a, value_b=value_b
    )


def _which(in_a: bool, in_b: bool) -> str | None:
    """Which arm the failure was found in. ``None`` when neither arm has it."""
    if in_a and in_b:
        return "both"
    if in_a:
        return "a"
    if in_b:
        return "b"
    return None


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
                ", ".join(str(v) for v in value)
                if isinstance(value, (list, tuple))
                else str(value)
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
) -> dict[str, Any]:
    """PR20, read to the letter. ``ineligible`` counts **matched** pairs that failed and
    ``unmatched`` is its own count, though PR10's prose calls an unmatched key ineligible; both
    are rows of ``excluded`` and both are in ``by_cause``. ``keys`` is summed over sweeps, each
    sweep's union taken on its own, because every sweep replays the same item set."""
    cuts: list[Any] = [c.name for c in declaration.cuts]
    cuts += [cut for cut in keys_by_cut if cut not in cuts]
    by_cut = {cut: _block(pairs, excluded, keys_by_cut.get(cut, 0), cut) for cut in cuts}
    total = _block(pairs, excluded, sum(keys_by_cut.values()), None)
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
) -> dict[str, Any]:
    kept = [r for r in pairs if cut is None or r["cut"] == cut]
    dropped = [r for r in excluded if cut is None or r["cut"] == cut]
    unmatched = [r for r in dropped if r["cause"] == "unmatched"]
    by_cause = {cause: 0 for cause in _CAUSES}
    by_arm = {arm: 0 for arm in _ARMS}
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
