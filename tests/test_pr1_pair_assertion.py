"""PR-1 oracle: the declaration, the canonicaliser and the pair assertion of "Prove -- Spec PR
Paired Replay" -- invariants PR1 to PR6, PR8 to PR21, and PR56 (the Modal manifest records
``infra_retries``).

Frozen by Session A on 2026-09-21 off ``f7af030``, after Taylor approved the two tables and the
conventions below (written the same day as ``624ce94``; the freeze changes this docstring only).
Session B builds ``src/proofload/paired.py`` (phase 1's part of it) and one line of
``executor_modal.py`` against this file and does not edit it. *Retrofit R1, ruled 2026-09-22
(PR-3 Session A): ``SPEC_PUBLIC_NAMES`` gains ``ReplicateResult`` and ``replicates``, the two
public names section 2 added with the k-replicate amendment; nothing else in this file moves for
it, and nothing in the suite pins this file's bytes. Retrofit R3, ruled the same day: ``Cut``
gains ``comparison``, so every cut this file builds or writes carries ``"ge"`` (the reading PR23
had), PR1 and PR8 gain the no-default and the two-words refusals for it, and PR6's field-change
table gains ``cuts.comparison``. Every test that builds a cut is red on the bare tree until Session
B lands the field; the two new refusals are red for the same reason.* ``proofload.paired`` is imported inside the test that needs it, so the bare tree fails test by
test and never at collection.

**What phase 1 is.** Two stored arms are only a pair if they were the same request twice, and the
module says so before it compares anything: the declaration is loaded whole and refuses what it
does not know (PR1 to PR8), the request is canonicalised without ever passing a number through
``float`` (PR11), and every pair is either eligible or excluded with one named cause, with counts
that reconcile (PR9 to PR21). Nothing here computes a rate.

**Conventions this file fixes for the build session** (the spec leaves them open; each is in the
spec's change log under 2026-09-21):

- *The TOML layout.* Top-level keys are ``Declaration``'s field names. ``[[cuts]]`` tables carry
  ``name``, ``threshold`` and ``comparison`` (retrofit R3, ruled 2026-09-22: the comparison the
  action is taken under, ``"gt"`` or ``"ge"``, with no default -- ADR-096's rule; a cut without
  one, or with any other word, is a ``DeclarationError``); ``[[sweeps]]`` tables carry ``name``,
  ``a`` and ``b``. ``threshold``,
  ``floor`` and ``price_per_input_token`` are TOML number literals and reach ``Decimal`` from their
  literal text (``tomllib``'s ``parse_float=Decimal`` is the obvious route).
- *The stratum.* A row's ``config[stratum_key]`` is the **name** of the cut it is analysed at, and
  ``config[cluster_key]`` is its item. PR3 and PR4 fire where the strata and the bodies become
  visible, which is ``assert_pairs``; an exemption equal to ``model_key`` is refused at load, since
  the declaration itself says that name is a body field.
- *The measured request.* ``Span.input`` of the span named ``request_span`` is the request body as
  **text**, as A6 stores it under ``max_observation_bytes = "none"``. Target identity is read from
  ``attrs["url.full"]``, ``attrs["http.request.method"]`` and ``attrs["http.request.header.<name>"]``.
  Header names match case-insensitively, in ``exemptions`` as in the attribute key.
- *The frames.* ``pairs`` carries at least ``sweep``, ``cut``, ``cluster``, ``config_hash``,
  ``replicate_index``, ``request_digest``, ``exemptions_exercised`` (a tuple of lower-cased header
  names), ``value_a`` and ``value_b`` (``Decimal``). ``excluded`` carries at least ``sweep``, ``cut``,
  ``cluster``, ``config_hash``, ``replicate_index``, ``cause``, ``arm`` (``"a"``, ``"b"`` or
  ``"both"``) and ``detail``. One pair is one row in exactly one of the two frames. ``arm`` is the
  arm the failure was found in; a cause that is a *comparison* of the two arms (``body``,
  ``body_field_absent``, ``header``, ``target``) belongs to neither and reads ``"both"``.
- *The causes.* The spec names five: ``unmatched``, ``body_field_absent``, ``model_pin``, ``header``,
  ``retry_or_multicall``. This file mints the rest of the closed set: ``errored`` (either row carries
  ``error``: an HTTP error, a timeout, an infra failure), ``no_request_span``, ``malformed_body`` (the
  stored request is not a JSON object), ``body`` (same fields, a differing value), ``target`` (URL or
  method), ``value_missing`` and ``value_out_of_range``. Tests build one failure per pair, so the
  precedence between two causes on one pair is **not** pinned.
- *The counts.* ``counts["total"]`` and ``counts["by_cut"][<cut>]`` each carry ``keys``, ``matched``,
  ``unmatched``, ``eligible``, ``ineligible``, ``by_cause``, ``by_arm`` and ``reconciles``. PR20's
  arithmetic is followed to the letter: ``ineligible`` counts **matched** pairs that failed, and
  ``unmatched`` is its own count (PR10 calls an unmatched key "ineligible" in prose; both are in
  ``excluded`` and in ``by_cause``). ``keys`` is summed over sweeps, each sweep's union taken on its
  own, because every sweep replays the same item set. ``counts["exemptions_exercised"]`` maps every
  declared exemption to the number of pairs it absorbed a difference on, zero included (PR16).
- *The environment.* ``environment["sweeps"][<sweep>]["a" | "b"]`` records ``proofload_version``,
  ``run_salt``, ``python``, ``concurrency`` and ``capture_cap`` per arm. ``environment["gaps"]`` is
  the list of identity facts that could not be asserted: ``"headers"`` (PR15), ``"retries"`` (PR18),
  and -- until a ``meta`` key convention exists for them, which is deferred -- ``"harness_digest"``
  and ``"client_version"`` on every run (PR17).
- *The artifact.* ``PairAssertion.to_json()`` is one JSON object with at least
  ``declaration_digest``, ``declaration``, ``environment``, ``pairs``, ``excluded`` and ``counts``.
- *PR56.* The Modal manifest's key is ``environment["infra_retries"]``, an ``int``, and
  ``retries = "asserted"`` reads that key on both arms' manifests whatever the backend.

**Invariant-to-test map** (89 functions, 177 collected ids; the id counts below sum to 177):

| Invariant | Tests |
|---|---|
| control | ``test_control_*`` (1 function, 1 id): the default sweep is twelve eligible pairs |
| PR1 | ``test_pr1_*`` (5 functions, 7 ids) |
| PR2 | ``test_pr2_*`` (5 functions, 7 ids) |
| PR3 | ``test_pr3_*`` (2 functions, 2 ids) |
| PR4 | ``test_pr4_*`` (4 functions, 8 ids) |
| PR5 | ``test_pr5_*`` (3 functions, 3 ids); ``pair_assertion.json`` only -- the other four artifacts and the two renders are phases 2 and 3 |
| PR6 | ``test_pr6_*`` (6 functions, 26 ids) |
| PR8 | ``test_pr8_*`` (6 functions, 7 ids) |
| PR9 | ``test_pr9_*`` (4 functions, 4 ids) |
| PR10 | ``test_pr10_*`` (3 functions, 3 ids) |
| PR11 | ``test_pr11_*`` (12 functions, 30 ids) |
| PR12 | ``test_pr12_*`` (3 functions, 6 ids) |
| PR13 | ``test_pr13_*`` (4 functions, 6 ids) |
| PR14 | ``test_pr14_*`` (2 functions, 5 ids) |
| PR15 | ``test_pr15_*`` (3 functions, 3 ids) |
| PR16 | ``test_pr16_*`` (2 functions, 2 ids) |
| PR17 | ``test_pr17_*`` (4 functions, 8 ids) |
| PR18 | ``test_pr18_*`` (5 functions, 10 ids) |
| PR19 | ``test_pr19_*`` (7 functions, 29 ids) |
| PR20 | ``test_pr20_*`` (4 functions, 4 ids) |
| PR21 | ``test_pr21_*`` (2 functions, 2 ids) |
| PR56 | ``test_pr56_*`` (2 functions, 4 ids) |

**Fixtures, and what each cannot express** (spec section 6, measured first-hand on 2026-09-21).
Every store here is built under ``tmp_path`` by this file -- the hand-built frames section 6 asks
for, with an error in each arm and in both. **Neither committed fixture can guard a phase 1
invariant, and neither is used:** Go1's two runs carry no trace at all, no item axis and no
``python`` in their imported manifests, so every pair would be ``no_request_span`` under every
implementation; and the 45/44 arms (``20260915T210140Z-4847`` / ``20260915T211148Z-965d``) carry
between 6 and 44 spans per episode under one name (none of the 400 episodes carries exactly one),
with ``input`` null on all 7,369, no ``url.full``, no header attribute and one config axis, so the
assertion this file pins refuses every one of their 200 pairs as ``retry_or_multicall``. That is the assertion working. **Ruled 2026-09-21 (spec section
11.2):** phase 2's PR39 builds its ``PairAssertion`` in test code from the two stored arms and hands
it to ``analyse``; it does not go through ``assert_pairs``, and PR9's structural rule (``analyse``
takes a ``PairAssertion`` and nothing else) is unchanged by that.

**Green before and after -- named so their green is not read as coverage.** None. Every test in
this file is red on the bare tree: PR56's four ids on a Modal manifest with no ``infra_retries``,
the other 173 on ``ModuleNotFoundError: proofload.paired``. A missing module is a weak red, so
Session A also ran the file against a shadow shim (177 green) and 40 mutants of it (40 red, no
survivor); the table is in the handoff.

**The four ``hypothesis`` tests are derandomized,** so a run of this file is the same run every
time and a mutation row does not depend on a seed.

**Named gaps, not pinned.** Which function raises ``NoEligiblePairs`` (no test here leaves a cut
empty); what a row whose stratum names no declared cut does; cause precedence; a request whose
stored body is an observation-cut wrapper rather than text; ``target_id`` is not in PR17's list and
is not compared; whether ``"0.30"`` and ``"0.3"`` give one declaration digest; the order of
``exemptions``.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
import random
import re
import tempfile
import typing
from collections.abc import Callable, Iterator, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import proofload
from proofload.episode import Episode
from proofload.executor import derive_seed, plan
from proofload.executor_modal import Job, ModalOptions, Result, run_with_mapper, worker_batch
from proofload.sampler import SweepSpec
from proofload.store import EpisodeRecord, RunManifest, Store, config_hash
from proofload.trace import Span, Trace

MODULE = __name__
HORIZON = 10.0
EPOCH = 1_790_000_000_000_000_000
SALT = "9f4a1c62d08e5b37"
TARGET = "scorer@v1"

REQUEST_SPAN = "scorer.request"
MODEL_PIN = "scorer-1.13.0"
URL = "https://api.example.test/v1/evaluate"
VALUE_KEY = "answers.q1.score"
CUTS: tuple[tuple[str, str], ...] = (("c50", "0.50"), ("c60", "0.60"), ("c90", "0.90"))
ITEMS_PER_CUT = 4
EXEMPTIONS = ("x-request-id", "date")
PYTHON = "3.11.7 (main, Feb 12 2026)"

#: The spec's public names (section 2). Anything else public on the module is a spec violation.
#: Retrofit R1, ruled 2026-09-22 (PR-3 Session A): ``ReplicateResult`` and ``replicates`` join
#: the set, as section 2 has carried them since the k-replicate amendment of the same day.
SPEC_PUBLIC_NAMES = frozenset({
    "PairedError", "DeclarationError", "NotAssertable", "NoEligiblePairs",
    "Cut", "SweepPair", "Declaration", "canonical_request", "request_digest",
    "PairAssertion", "assert_pairs", "CutResult", "PairedResult", "analyse",
    "WindowReport", "windows", "CostReport", "cost", "ReplicateResult", "replicates",
})
PHASE_1_NAMES = frozenset({
    "PairedError", "DeclarationError", "NotAssertable", "NoEligiblePairs",
    "Cut", "SweepPair", "Declaration", "canonical_request", "request_digest",
    "PairAssertion", "assert_pairs",
})
PAIR_ASSERTION_FIELDS = ("declaration", "pairs", "excluded", "environment", "counts")
PAIRS_COLUMNS = frozenset({
    "sweep", "cut", "cluster", "config_hash", "replicate_index", "request_digest",
    "exemptions_exercised", "value_a", "value_b",
})
EXCLUDED_COLUMNS = frozenset({
    "sweep", "cut", "cluster", "config_hash", "replicate_index", "cause", "arm", "detail",
})
COUNT_KEYS = frozenset({
    "keys", "matched", "unmatched", "eligible", "ineligible", "by_cause", "by_arm", "reconciles",
})
CAUSES = frozenset({
    "unmatched", "errored", "no_request_span", "retry_or_multicall", "malformed_body", "model_pin",
    "body_field_absent", "body", "target", "header", "value_missing", "value_out_of_range",
})
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")

MISSING: Any = object()


def P() -> Any:
    """The module under test, imported where it is needed so collection never fails."""
    return importlib.import_module("proofload.paired")


# ---------- helpers: the declaration ----------


def decl_kwargs(**over: Any) -> dict[str, Any]:
    paired = P()
    kwargs: dict[str, Any] = {
        "value_key": VALUE_KEY, "cluster_key": "item", "stratum_key": "cut",
        "cuts": tuple(paired.Cut(name=n, threshold=Decimal(t), comparison="ge") for n, t in CUTS),
        "sweeps": (paired.SweepPair(name="S1", a="s1-a", b="s1-b"),),
        "request_span": REQUEST_SPAN, "model_key": "model", "model_pin": MODEL_PIN,
        "exemptions": EXEMPTIONS, "headers": "asserted", "retries": "not_recorded",
        "bootstrap_b": 2000, "bootstrap_seed": 20260921,
    }
    kwargs.update(over)
    return kwargs


def decl(**over: Any) -> Any:
    return P().Declaration(**decl_kwargs(**over))


TOML_TOP: dict[str, str] = {
    "value_key": f'"{VALUE_KEY}"', "cluster_key": '"item"', "stratum_key": '"cut"',
    "request_span": f'"{REQUEST_SPAN}"', "model_key": '"model"', "model_pin": f'"{MODEL_PIN}"',
    "exemptions": '["x-request-id", "date"]', "headers": '"asserted"', "retries": '"not_recorded"',
    "bootstrap_b": "2000", "bootstrap_seed": "20260921",
}


def decl_toml(
    *,
    top: Mapping[str, str | None] | None = None,
    cuts: Sequence[Mapping[str, str]] | None = None,
    sweeps: Sequence[Mapping[str, str]] | None = None,
    shuffle: random.Random | None = None,
) -> str:
    """A declaration file. Values are raw TOML text, so a threshold's literal is what is written;
    a ``None`` value drops the key."""
    merged: dict[str, str | None] = dict(TOML_TOP)
    merged.update(top or {})
    items = [(k, v) for k, v in merged.items() if v is not None]
    if shuffle is not None:
        shuffle.shuffle(items)
    lines = [f"{k} = {v}" for k, v in items]
    cut_tables = (
        [{"name": f'"{n}"', "threshold": t, "comparison": '"ge"'} for n, t in CUTS]
        if cuts is None else cuts
    )
    sweep_tables = [{"name": '"S1"', "a": '"s1-a"', "b": '"s1-b"'}] if sweeps is None else sweeps
    for header, tables in (("cuts", cut_tables), ("sweeps", sweep_tables)):
        for table in tables:
            lines += ["", f"[[{header}]]"] + [f"{k} = {v}" for k, v in table.items()]
    return "\n".join(lines) + "\n"


def load(tmp_path: Path, text: str, name: str = "decl.toml") -> Any:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return P().Declaration.from_toml(path)


# ---------- helpers: the stored arms ----------


BASE_FIELDS: dict[str, str] = {
    "model": f'"{MODEL_PIN}"',
    "state": '"the state"',
    "questions": '{"q1": {"type": "score", "instructions": "rate it"}}',
    "temperature": "0.30",
    "top_p": "0.95",
    "max_tokens": "64",
}


def body_text(fields: Mapping[str, str]) -> str:
    """A request body as the wire carried it: each value is raw JSON text, so ``0.30`` stays
    ``0.30`` and nothing here round-trips a number."""
    return "{" + ", ".join(f'"{k}": {v}' for k, v in fields.items()) + "}"


@dataclasses.dataclass
class Row:
    item: str
    cut: str
    value: Any = "0.62"
    fields: dict[str, str] = dataclasses.field(default_factory=dict)
    raw_body: str | None = None
    headers: dict[str, list[str]] | None = dataclasses.field(default_factory=dict)
    url: str = URL
    method: str = "POST"
    n_request_spans: int = 1
    other_spans: int = 0
    error: str | None = None
    seed_offset: int = 0
    replicate: int = 0
    extra_config: dict[str, Any] = dataclasses.field(default_factory=dict)


def default_rows() -> dict[str, Row]:
    rows: dict[str, Row] = {}
    for cut, _ in CUTS:
        for k in range(ITEMS_PER_CUT):
            item = f"{cut}-i{k:03d}"
            rows[item] = Row(item=item, cut=cut, fields={"state": f'"state of {item}"'})
    return rows


def _request_span(row: Row, arm: str, k: int) -> Span:
    fields = dict(BASE_FIELDS)
    fields.update(row.fields)
    fields = {name: text for name, text in fields.items() if text is not MISSING}
    attrs: dict[str, Any] = {"url.full": row.url, "http.request.method": row.method}
    if row.headers is not None:
        headers = {
            "content-type": ["application/json"],
            "x-request-id": [f"req-{arm}-{row.item}-{k}"],
        }
        headers.update(row.headers)
        attrs.update({f"http.request.header.{name}": value for name, value in headers.items()})
    return Span(
        span_id=f"{k + 1:016x}", parent_id=None, kind="http", name=REQUEST_SPAN,
        start_ns=EPOCH + k * 1_000_000, end_ns=EPOCH + k * 1_000_000 + 500_000,
        input=body_text(fields) if row.raw_body is None else row.raw_body,
        output='{"answers": {"q1": {"score": 0.62}}}', tokens={"in": 400, "out": 12}, attrs=attrs,
    )


def record(run_id: str, row: Row, arm: str, salt: str) -> EpisodeRecord:
    config = {"item": row.item, "cut": row.cut, **row.extra_config}
    seed = derive_seed(salt, config_hash(config), row.replicate) + row.seed_offset
    if row.error is not None:
        return EpisodeRecord.errored(
            run_id=run_id, config=config, seed=seed, replicate_index=row.replicate,
            error=row.error, wall_time=0.1,
        )
    spans = [_request_span(row, arm, k) for k in range(row.n_request_spans)]
    spans += [
        Span(
            span_id=f"{0xF00 + k:016x}", parent_id=None, kind="other", name="tokenizer",
            start_ns=EPOCH + k, end_ns=EPOCH + k + 10,
        )
        for k in range(row.other_spans)
    ]
    meta: dict[str, Any] = {"trace": Trace(spans=tuple(spans), source="record").to_dict()}
    if row.value is not MISSING:
        meta["answers"] = {"q1": {"score": row.value}}
    episode = Episode(outcome="scored", t=1.0, horizon=HORIZON, meta=meta)
    return EpisodeRecord.from_episode(
        episode, run_id=run_id, config=config, seed=seed, replicate_index=row.replicate,
        wall_time=0.1,
    )


def make_arm(
    store: Store,
    run_id: str,
    rows: Sequence[Row],
    *,
    arm: str,
    salt: str = SALT,
    env: Mapping[str, Any] | None = None,
    version: str | None = None,
) -> None:
    environment: dict[str, Any] = {
        "python": PYTHON, "platform": "oracle", "proofload_version": proofload.__version__,
        "capture": {"content": True, "max_observation_bytes": "none", "max_spans": 200},
    }
    environment.update(env or {})
    extra: dict[str, Any] = {}
    if version is not None:
        extra["proofload_version"] = version
        environment["proofload_version"] = version
    store.create_run(RunManifest(
        run_id=run_id, target_id=TARGET, t_unit="steps", run_salt=salt,
        axis_types={"item": "categorical", "cut": "categorical"}, backend="local",
        environment=environment, **extra,
    ))
    store.append(run_id, [record(run_id, row, arm, salt) for row in rows])
    store.mark_complete(run_id)


def make_sweep(
    root: Path,
    a: Mapping[str, Row] | None = None,
    b: Mapping[str, Row] | None = None,
    *,
    name: str = "store",
    a_kwargs: Mapping[str, Any] | None = None,
    b_kwargs: Mapping[str, Any] | None = None,
) -> Store:
    store = Store(root / name)
    make_arm(store, "s1-a", list((default_rows() if a is None else a).values()), arm="a", **(a_kwargs or {}))
    make_arm(store, "s1-b", list((default_rows() if b is None else b).values()), arm="b", **(b_kwargs or {}))
    return store


def with_row(item: str, **changes: Any) -> dict[str, Row]:
    rows = default_rows()
    rows[item] = dataclasses.replace(rows[item], **changes)
    return rows


def excluded_of(assertion: Any, item: str) -> pd.Series:
    hit = assertion.excluded[assertion.excluded["cluster"] == item]
    assert len(hit) == 1, (item, assertion.excluded.to_dict("records"))
    return hit.iloc[0]


def eligible_items(assertion: Any) -> set[str]:
    return set(assertion.pairs["cluster"])


ITEM = "c60-i001"
ALL_ITEMS = frozenset(default_rows())


def assert_only_excluded(assertion: Any, item: str, cause: str) -> pd.Series:
    """The one broken pair is excluded with ``cause`` and every other pair is eligible -- so a
    test cannot pass because the whole sweep was refused for some other reason."""
    row = excluded_of(assertion, item)
    assert row["cause"] == cause, row.to_dict()
    assert eligible_items(assertion) == ALL_ITEMS - {item}, assertion.excluded.to_dict("records")
    assert len(assertion.excluded) == 1, assertion.excluded.to_dict("records")
    return row


# ---------- the control: every later refusal is measured against this passing ----------


def test_control_the_default_sweep_is_twelve_eligible_pairs_and_nothing_excluded(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path), decl())
    assert eligible_items(assertion) == ALL_ITEMS
    assert len(assertion.pairs) == len(ALL_ITEMS) and len(assertion.excluded) == 0
    assert PAIRS_COLUMNS <= set(assertion.pairs.columns), set(assertion.pairs.columns)
    assert EXCLUDED_COLUMNS <= set(assertion.excluded.columns), set(assertion.excluded.columns)
    assert set(assertion.pairs["sweep"]) == {"S1"}
    assert dict(assertion.pairs.groupby("cut").size()) == {cut: ITEMS_PER_CUT for cut, _ in CUTS}


# ---------- PR1: no default seed, no default B, no cut without a threshold ----------


def test_pr1_control_the_complete_declaration_loads(tmp_path: Path) -> None:
    d = load(tmp_path, decl_toml())
    assert d.bootstrap_b == 2000 and d.bootstrap_seed == 20260921
    assert [c.name for c in d.cuts] == [n for n, _ in CUTS]
    assert [(s.name, s.a, s.b) for s in d.sweeps] == [("S1", "s1-a", "s1-b")]
    assert tuple(d.exemptions) == EXEMPTIONS
    assert d.floor is None and d.price_per_input_token is None and d.token_cap is None


@pytest.mark.parametrize("key", ["bootstrap_b", "bootstrap_seed"])
def test_pr1_a_declaration_without_b_or_a_seed_is_refused_at_load(tmp_path: Path, key: str) -> None:
    load(tmp_path, decl_toml(), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(top={key: None}))


def test_pr1_a_cut_without_a_threshold_is_refused_at_load(tmp_path: Path) -> None:
    cuts = [{"name": '"c50"', "threshold": "0.50", "comparison": '"ge"'}, {"name": '"c60"', "comparison": '"ge"'}]
    load(tmp_path, decl_toml(cuts=[cuts[0]]), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(cuts=cuts))


def test_pr1_a_cut_without_a_comparison_is_refused_at_load(tmp_path: Path) -> None:
    """Retrofit R3 (2026-09-22): the comparison is an estimator's parameter like the seed and
    ``B``, and ADR-096's no-default rule applies -- a cut that does not say ``gt`` or ``ge``
    does not say which items act."""
    cuts = [{"name": '"c50"', "threshold": "0.50", "comparison": '"gt"'}, {"name": '"c60"', "threshold": "0.60"}]
    load(tmp_path, decl_toml(cuts=[cuts[0]]), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(cuts=cuts))


def test_pr1_the_cut_dataclass_itself_carries_no_default_for_the_comparison() -> None:
    paired = P()
    by_name = {f.name: f for f in dataclasses.fields(paired.Cut)}
    assert tuple(by_name) == ("name", "threshold", "comparison")
    assert by_name["comparison"].default is dataclasses.MISSING
    assert by_name["comparison"].default_factory is dataclasses.MISSING
    with pytest.raises(TypeError):
        paired.Cut(name="c50", threshold=Decimal("0.50"))


@pytest.mark.parametrize("field", ["bootstrap_b", "bootstrap_seed"])
def test_pr1_the_dataclass_itself_carries_no_default_for_b_or_the_seed(field: str) -> None:
    by_name = {f.name: f for f in dataclasses.fields(P().Declaration)}
    assert by_name[field].default is dataclasses.MISSING
    assert by_name[field].default_factory is dataclasses.MISSING
    kwargs = decl_kwargs()
    del kwargs[field]
    with pytest.raises(TypeError):
        P().Declaration(**kwargs)


def test_pr1_declaration_error_is_a_paired_error_and_the_three_refusals_are_distinct() -> None:
    paired = P()
    for exc in (paired.DeclarationError, paired.NotAssertable, paired.NoEligiblePairs):
        assert issubclass(exc, paired.PairedError) and exc is not paired.PairedError
    assert not issubclass(paired.NotAssertable, paired.DeclarationError)
    assert not issubclass(paired.DeclarationError, paired.NotAssertable)


# ---------- PR2: unique cut names; a threshold is its literal, never a float ----------


def test_pr2_two_cuts_under_one_name_are_refused(tmp_path: Path) -> None:
    cuts = [{"name": '"c50"', "threshold": "0.50", "comparison": '"ge"'}, {"name": '"c50"', "threshold": "0.60", "comparison": '"ge"'}]
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(cuts=cuts))


def test_pr2_a_threshold_is_a_decimal_equal_to_its_literal_and_to_no_binary_double(tmp_path: Path) -> None:
    cuts = [{"name": '"a"', "threshold": "0.30", "comparison": '"ge"'}, {"name": '"b"', "threshold": "0.3", "comparison": '"ge"'}]
    a, b = load(tmp_path, decl_toml(cuts=cuts)).cuts
    assert isinstance(a.threshold, Decimal) and isinstance(b.threshold, Decimal)
    assert a.threshold == b.threshold == Decimal("0.3")
    assert a.threshold != Decimal(0.30) and b.threshold != Decimal(0.3)


@pytest.mark.parametrize("literal", ["0.3000000000000000444", "0.60000000000000000001", "0.1234567890123456789"])
def test_pr2_a_threshold_longer_than_a_double_holds_survives_the_load(tmp_path: Path, literal: str) -> None:
    """The mutant this is cut for: ``Decimal(str(float(x)))``, which gives back a short literal
    and passes the 0.30 test above."""
    (cut,) = load(tmp_path, decl_toml(cuts=[{"name": '"c"', "threshold": literal, "comparison": '"ge"'}])).cuts
    assert cut.threshold == Decimal(literal)
    assert cut.threshold != Decimal(str(float(literal)))


def test_pr2_an_integer_threshold_is_a_decimal_too(tmp_path: Path) -> None:
    (cut,) = load(tmp_path, decl_toml(cuts=[{"name": '"c"', "threshold": "1", "comparison": '"ge"'}])).cuts
    assert isinstance(cut.threshold, Decimal) and cut.threshold == Decimal(1)


def test_pr2_the_floor_and_the_price_are_decimals_from_their_literals(tmp_path: Path) -> None:
    d = load(tmp_path, decl_toml(top={"floor": "0.01", "price_per_input_token": "0.0000001500000000000000001"}))
    assert isinstance(d.floor, Decimal) and d.floor == Decimal("0.01") and d.floor != Decimal(0.01)
    assert d.price_per_input_token == Decimal("0.0000001500000000000000001")


# ---------- PR3: strata are disjoint ----------


def test_pr3_an_item_under_two_cuts_is_a_declaration_error_naming_both_cuts_and_the_item(tmp_path: Path) -> None:
    paired = P()
    paired.assert_pairs(make_sweep(tmp_path, name="control"), decl())
    rows = default_rows()
    rows["twice"] = Row(item="c50-i000", cut="c90", fields={"state": '"state of c50-i000"'})
    with pytest.raises(paired.DeclarationError) as caught:
        paired.assert_pairs(make_sweep(tmp_path, rows, rows), decl())
    message = str(caught.value)
    assert "c50-i000" in message and "c50" in message.replace("c50-i000", "") and "c90" in message


def test_pr3_the_same_item_in_every_sweep_under_one_cut_is_not_an_overlap(tmp_path: Path) -> None:
    paired = P()
    store = make_sweep(tmp_path)
    make_arm(store, "s2-a", list(default_rows().values()), arm="a", salt="4c71e89b2a0f3d65")
    make_arm(store, "s2-b", list(default_rows().values()), arm="b", salt="4c71e89b2a0f3d65")
    sweeps = (paired.SweepPair(name="S1", a="s1-a", b="s1-b"), paired.SweepPair(name="S2", a="s2-a", b="s2-b"))
    assertion = paired.assert_pairs(store, decl(sweeps=sweeps))
    assert dict(assertion.pairs.groupby("sweep").size()) == {"S1": 12, "S2": 12}


# ---------- PR4: an exemption is a header, never a body field ----------


def test_pr4_control_header_exemptions_are_accepted(tmp_path: Path) -> None:
    load(tmp_path, decl_toml(top={"exemptions": '["x-request-id", "date", "idempotency-key"]'}))
    P().assert_pairs(make_sweep(tmp_path), decl(exemptions=("x-request-id", "date", "idempotency-key")))


def test_pr4_exempting_the_model_key_is_refused_at_load(tmp_path: Path) -> None:
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(top={"exemptions": '["x-request-id", "model"]'}))


@pytest.mark.parametrize("name", ["temperature", "top_p", "max_tokens", "state", "questions.q1.instructions"])
def test_pr4_an_exemption_that_resolves_to_a_body_field_is_a_declaration_error(tmp_path: Path, name: str) -> None:
    paired = P()
    with pytest.raises(paired.DeclarationError) as caught:
        paired.assert_pairs(make_sweep(tmp_path), decl(exemptions=("x-request-id", name)))
    assert name in str(caught.value)


def test_pr4_an_exempted_body_field_cannot_hide_a_sampling_difference(tmp_path: Path) -> None:
    """What PR4 exists for. Whatever the module does with ``temperature`` in ``exemptions``, it
    never reports the pair whose temperature moved as eligible."""
    paired = P()
    store = make_sweep(tmp_path, b=with_row(ITEM, fields={"state": f'"state of {ITEM}"', "temperature": "0.70"}))
    try:
        assertion = paired.assert_pairs(store, decl(exemptions=("x-request-id", "temperature")))
    except paired.DeclarationError:
        return
    assert ITEM not in eligible_items(assertion)


# ---------- PR5, PR6: the digest ----------


def test_pr5_the_digest_is_a_sha256_hex_and_the_same_from_a_file_and_from_the_constructor(tmp_path: Path) -> None:
    from_file = load(tmp_path, decl_toml())
    assert HEX64.match(from_file.digest), from_file.digest
    assert from_file.digest == decl().digest


def test_pr5_pair_assertion_json_carries_the_declaration_and_its_digest(tmp_path: Path) -> None:
    d = decl()
    payload = json.loads(P().assert_pairs(make_sweep(tmp_path), d).to_json())
    assert payload["declaration_digest"] == d.digest
    assert {"declaration", "environment", "pairs", "excluded", "counts"} <= set(payload)
    assert payload["declaration"]["exemptions"] == list(EXEMPTIONS)
    assert payload["declaration"]["bootstrap_seed"] == 20260921
    assert [c["name"] for c in payload["declaration"]["cuts"]] == [n for n, _ in CUTS]


def test_pr5_to_json_is_byte_stable_across_two_assertions_of_the_same_store(tmp_path: Path) -> None:
    store = make_sweep(tmp_path)
    assert P().assert_pairs(store, decl()).to_json() == P().assert_pairs(store, decl()).to_json()


def test_pr6_loading_the_same_file_twice_gives_the_same_digest(tmp_path: Path) -> None:
    text = decl_toml(top={"floor": "0.01", "conditioning": '"items picked to sit beside the cut"'})
    assert load(tmp_path, text, "one.toml").digest == load(tmp_path, text, "two.toml").digest


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_pr6_key_order_comments_and_the_files_name_do_not_move_the_digest(tmp_path: Path, seed: int) -> None:
    plain = load(tmp_path, decl_toml(), "plain.toml").digest
    shuffled = "# a comment\n\n" + decl_toml(shuffle=random.Random(seed)).replace(" = ", "   =   ")
    assert load(tmp_path, shuffled, f"elsewhere-{seed}.toml").digest == plain


def _field_changes() -> dict[str, Callable[[Any], Any]]:
    return {
        "value_key": lambda p: "answers.q2.score",
        "cluster_key": lambda p: "task",
        "stratum_key": lambda p: "band",
        "cuts.threshold": lambda p: tuple(p.Cut(name=n, threshold=Decimal(t) + Decimal("0.01"), comparison="ge") for n, t in CUTS),
        "cuts.name": lambda p: tuple(p.Cut(name=n + "x", threshold=Decimal(t), comparison="ge") for n, t in CUTS),
        # Retrofit R3 (2026-09-22): the comparison is part of the pre-registered cut.
        "cuts.comparison": lambda p: tuple(p.Cut(name=n, threshold=Decimal(t), comparison="gt") for n, t in CUTS),
        "sweeps": lambda p: (p.SweepPair(name="S1", a="s1-a", b="other-b"),),
        "request_span": lambda p: "scorer.other",
        "model_key": lambda p: "request.model",
        "model_pin": lambda p: "scorer-1.13.1",
        "exemptions": lambda p: (*EXEMPTIONS, "idempotency-key"),
        "headers": lambda p: "not_recorded",
        "retries": lambda p: "asserted",
        "bootstrap_b": lambda p: 2001,
        "bootstrap_seed": lambda p: 20260922,
        "floor": lambda p: Decimal("0.01"),
        "declared_window_s": lambda p: 1200.0,
        "conditioning": lambda p: "on items picked to sit beside the cut",
        "price_per_input_token": lambda p: Decimal("0.00000015"),
        "token_cap": lambda p: 6_000_000,
    }


FIELD_CHANGE_IDS = (
    "value_key", "cluster_key", "stratum_key", "cuts.threshold", "cuts.name", "cuts.comparison", "sweeps",
    "request_span", "model_key", "model_pin", "exemptions", "headers", "retries", "bootstrap_b",
    "bootstrap_seed", "floor", "declared_window_s", "conditioning", "price_per_input_token",
    "token_cap",
)


def test_pr6_the_field_change_table_covers_every_field_of_the_declaration() -> None:
    fields = {f.name for f in dataclasses.fields(P().Declaration)}
    assert {name.split(".")[0] for name in FIELD_CHANGE_IDS} == fields
    assert set(_field_changes()) == set(FIELD_CHANGE_IDS)


@pytest.mark.parametrize("change", FIELD_CHANGE_IDS)
def test_pr6_changing_any_one_field_changes_the_digest(change: str) -> None:
    paired = P()
    base = decl()
    moved = decl(**{change.split(".")[0]: _field_changes()[change](paired)})
    assert moved.digest != base.digest, change


def test_pr6_adding_one_exemption_changes_the_digest() -> None:
    assert decl(exemptions=(*EXEMPTIONS, "x-trace-id")).digest != decl().digest
    assert decl(exemptions=()).digest != decl().digest


HEADER_NAMES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12)


@settings(max_examples=60, deadline=None, derandomize=True)
@given(
    first=st.lists(HEADER_NAMES, unique=True, max_size=5),
    second=st.lists(HEADER_NAMES, unique=True, max_size=5),
)
def test_pr6_property_two_exemption_lists_share_a_digest_only_if_they_are_the_same_set(
    first: list[str], second: list[str]
) -> None:
    same = decl(exemptions=tuple(first)).digest == decl(exemptions=tuple(second)).digest
    if set(first) != set(second):
        assert not same
    if first == second:
        assert same


# ---------- PR8: nothing is silently ignored ----------


def test_pr8_an_unknown_top_level_key_is_refused(tmp_path: Path) -> None:
    load(tmp_path, decl_toml(), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(top={"bootstrap_method": '"bca"'}))


def test_pr8_a_misspelt_optional_key_is_refused_rather_than_read_as_absent(tmp_path: Path) -> None:
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(top={"token_caps": "6000000"}))


def test_pr8_an_unknown_key_inside_a_cut_is_refused(tmp_path: Path) -> None:
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(cuts=[{"name": '"c50"', "threshold": "0.50", "comparison": '"ge"', "inclusive": "true"}]))


@pytest.mark.parametrize("word", ['"eq"', '"gte"', '">="', '"GE"', "true"])
def test_pr8_a_cuts_comparison_takes_only_its_two_words(tmp_path: Path, word: str) -> None:
    """Retrofit R3 (2026-09-22): ``comparison`` is ``"gt"`` or ``"ge"`` and nothing else, as
    ``headers`` and ``retries`` take only their two words."""
    load(tmp_path, decl_toml(cuts=[{"name": '"c50"', "threshold": "0.50", "comparison": '"gt"'}]), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(cuts=[{"name": '"c50"', "threshold": "0.50", "comparison": word}]))


def test_pr8_an_unknown_key_inside_a_sweep_is_refused(tmp_path: Path) -> None:
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(sweeps=[{"name": '"S1"', "a": '"s1-a"', "b": '"s1-b"', "c": '"s1-c"'}]))


def test_pr8_an_unknown_table_is_refused(tmp_path: Path) -> None:
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml() + '\n[estimator]\nmethod = "bca"\n')


@pytest.mark.parametrize(("key", "value"), [("headers", '"maybe"'), ("retries", '"zero"')])
def test_pr8_a_literal_field_takes_only_its_two_words(tmp_path: Path, key: str, value: str) -> None:
    with pytest.raises(P().DeclarationError):
        load(tmp_path, decl_toml(top={key: value}))


# ---------- PR9: the assertion is the only door ----------


def test_pr9_the_module_adds_no_public_name_the_spec_does_not_list() -> None:
    paired = P()
    public = {
        name for name, value in vars(paired).items()
        if not name.startswith("_") and getattr(value, "__module__", None) == paired.__name__
    }
    assert PHASE_1_NAMES <= public, PHASE_1_NAMES - public
    assert public <= SPEC_PUBLIC_NAMES, public - SPEC_PUBLIC_NAMES


def test_pr9_a_pair_assertion_is_the_five_fields_and_assert_pairs_takes_a_store_and_a_declaration() -> None:
    paired = P()
    assert tuple(f.name for f in dataclasses.fields(paired.PairAssertion)) == PAIR_ASSERTION_FIELDS
    assert list(inspect.signature(paired.assert_pairs).parameters) == ["store", "declaration"]
    hints = typing.get_type_hints(paired.assert_pairs)
    assert hints["store"] is Store and hints["declaration"] is paired.Declaration
    assert hints["return"] is paired.PairAssertion


def test_pr9_every_public_function_that_is_not_the_assertion_takes_no_frame_and_no_run_id() -> None:
    """Structural, and written to bind phases 2 and 3 as they land: ``analyse`` and ``windows``
    take a ``PairAssertion`` and nothing else, and no public function accepts a ``DataFrame``."""
    paired = P()
    for name in ("analyse", "windows"):
        fn = getattr(paired, name, None)
        if fn is None:
            continue
        hints = typing.get_type_hints(fn)
        hints.pop("return", None)
        assert list(hints.values()) == [paired.PairAssertion], (name, hints)
    for name in SPEC_PUBLIC_NAMES:
        fn = getattr(paired, name, None)
        if inspect.isfunction(fn):
            for hint in typing.get_type_hints(fn).values():
                assert hint is not pd.DataFrame, name


def test_pr9_a_pair_assertion_is_frozen() -> None:
    assert dataclasses.is_dataclass(P().PairAssertion)
    assert P().PairAssertion.__dataclass_params__.frozen


# ---------- PR10: matched on (config_hash, replicate_index) ----------


def test_pr10_a_key_in_one_arm_only_is_unmatched_and_names_the_arm_that_holds_it(tmp_path: Path) -> None:
    a, b = default_rows(), default_rows()
    del b["c50-i002"]
    del a["c90-i003"]
    assertion = P().assert_pairs(make_sweep(tmp_path, a, b), decl())
    only_a, only_b = excluded_of(assertion, "c50-i002"), excluded_of(assertion, "c90-i003")
    assert (only_a["cause"], only_a["arm"], only_a["cut"]) == ("unmatched", "a", "c50")
    assert (only_b["cause"], only_b["arm"], only_b["cut"]) == ("unmatched", "b", "c90")
    assert eligible_items(assertion) == ALL_ITEMS - {"c50-i002", "c90-i003"}


def test_pr10_the_match_is_on_the_key_and_not_on_row_order(tmp_path: Path) -> None:
    b = dict(reversed(list(default_rows().items())))
    assertion = P().assert_pairs(make_sweep(tmp_path, None, b), decl())
    assert eligible_items(assertion) == ALL_ITEMS and len(assertion.excluded) == 0
    expected = {config_hash({"item": r.item, "cut": r.cut}) for r in default_rows().values()}
    assert set(assertion.pairs["config_hash"]) == expected


def test_pr10_the_replicate_index_is_half_of_the_key(tmp_path: Path) -> None:
    a, b = default_rows(), default_rows()
    a["again"] = dataclasses.replace(a[ITEM], replicate=1)
    assertion = P().assert_pairs(make_sweep(tmp_path, a, b), decl())
    unmatched = assertion.excluded[assertion.excluded["cause"] == "unmatched"]
    assert [(r.cluster, int(r.replicate_index), r.arm) for r in unmatched.itertuples()] == [(ITEM, 1, "a")]
    kept = assertion.pairs[assertion.pairs["cluster"] == ITEM]
    assert [int(k) for k in kept["replicate_index"]] == [0]


# ---------- PR11: the canonical request ----------


def test_pr11_key_order_and_whitespace_do_not_move_the_canonical_bytes() -> None:
    canonical_request = P().canonical_request
    one = '{"model": "m", "temperature": 0.30, "nested": {"b": 1, "a": [3, 2, 1]}}'
    two = '{\n  "nested" : {"a":[3,2,1],   "b":1},\n\t"temperature":0.30 ,"model":"m"\n}'
    assert canonical_request(one) == canonical_request(two)
    assert canonical_request(one) == b'{"model":"m","nested":{"a":[3,2,1],"b":1},"temperature":0.30}'


def test_pr11_str_and_bytes_give_the_same_canonical_bytes_and_the_output_is_utf8() -> None:
    canonical_request = P().canonical_request
    text = '{"state": "café — naïve", "n": 1}'
    assert canonical_request(text) == canonical_request(text.encode("utf-8"))
    assert "café — naïve".encode() in canonical_request(text)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("0.30", "0.30000000000000001"),
        ("0.95", "0.95000000000000001"),
        ("0.30", "0.3000000000000000444"),
        ("0.95", "0.9500000000000001"),
        ("1", "1.0"),
        ("100", "1e2"),
        ("0", "-0"),
        ("0.30", "0.3"),
        ("9007199254740993", "9007199254740992"),
        ("1E2", "1e2"),
    ],
)
def test_pr11_number_literals_are_emitted_verbatim_and_never_meet_a_float(left: str, right: str) -> None:
    """Named mutant 1. The first two pairs are **one double each** (``float("0.30") ==
    float("0.30000000000000001")``), so a canonicaliser that meets a float cannot tell them apart.
    The spec's own example, ``0.3000000000000000444``, is the *next* double up from 0.30 and a float
    round-trip still separates it; it is kept because a float emits neither literal as written. The
    rest are one value to a reader and two different requests on the wire."""
    paired = P()
    a, b = f'{{"top_p": {left}, "model": "m"}}', f'{{"top_p": {right}, "model": "m"}}'
    assert f'"top_p":{left}'.encode() in paired.canonical_request(a)
    assert f'"top_p":{right}'.encode() in paired.canonical_request(b)
    assert paired.canonical_request(a) != paired.canonical_request(b)
    digests = {
        paired.request_digest(body, target={"url.full": URL, "http.request.method": "POST"}, headers={}, exemptions=())
        for body in (a, b)
    }
    assert len(digests) == 2


def test_pr11_a_number_inside_an_array_and_inside_a_nested_object_is_verbatim_too() -> None:
    body = '{"a": [0.10, 1.0, 2], "b": {"c": {"d": 3.1400}}}'
    assert P().canonical_request(body) == b'{"a":[0.10,1.0,2],"b":{"c":{"d":3.1400}}}'


def test_pr11_array_order_is_a_value_and_not_whitespace() -> None:
    canonical_request = P().canonical_request
    assert canonical_request('{"a": [1, 2]}') != canonical_request('{"a": [2, 1]}')


@pytest.mark.parametrize(
    ("left", "right"),
    [('"abc"', '"abd"'), ("true", "false"), ("null", "0"), ('"1"', "1"), ('""', "null"), ("[]", "{}")],
)
def test_pr11_changing_any_value_changes_the_canonical_bytes(left: str, right: str) -> None:
    canonical_request = P().canonical_request
    assert canonical_request(f'{{"k": {left}}}') != canonical_request(f'{{"k": {right}}}')


NUMBER_LITERALS = st.one_of(
    st.integers(min_value=-10**20, max_value=10**20).map(str),
    st.decimals(allow_nan=False, allow_infinity=False, places=6, min_value=-1000, max_value=1000).map(
        lambda d: format(d, "f")
    ),
    st.sampled_from(["0.30", "0.3", "0.30000000000000001", "1.0", "1", "1e2", "100", "0.95", "0.95000000000000001"]),
)
STRING_LITERALS = st.text(alphabet="abcdefghij XYZ_-", max_size=8).map(json.dumps)
LEAF_LITERALS = st.one_of(NUMBER_LITERALS, STRING_LITERALS, st.sampled_from(["true", "false", "null"]))
KEYS = st.text(alphabet="abcdefghijklmnop_", min_size=1, max_size=6)


@st.composite
def raw_objects(draw: Any, depth: int = 0) -> list[tuple[str, Any]]:
    """A JSON object as ``[(key, raw)]`` where ``raw`` is literal text or a nested list."""
    keys = draw(st.lists(KEYS, unique=True, min_size=1, max_size=4))
    out: list[tuple[str, Any]] = []
    for key in keys:
        if depth < 2 and draw(st.booleans()) and draw(st.booleans()):
            out.append((key, draw(raw_objects(depth=depth + 1))))
        else:
            out.append((key, draw(LEAF_LITERALS)))
    return out


def render(obj: list[tuple[str, Any]], rng: random.Random | None = None) -> str:
    items = list(obj)
    gap = ""
    if rng is not None:
        rng.shuffle(items)
        gap = rng.choice(["", " ", "\n  ", "\t"])
    parts = [
        f"{gap}{json.dumps(k)}{gap}:{gap}{render(v, rng) if isinstance(v, list) else v}" for k, v in items
    ]
    return "{" + ",".join(parts) + gap + "}"


def leaves(obj: list[tuple[str, Any]], prefix: tuple[int, ...] = ()) -> Iterator[tuple[int, ...]]:
    for i, (_, value) in enumerate(obj):
        if isinstance(value, list):
            yield from leaves(value, (*prefix, i))
        else:
            yield (*prefix, i)


def replace_leaf(obj: list[tuple[str, Any]], where: tuple[int, ...], text: str) -> list[tuple[str, Any]]:
    out = list(obj)
    key, value = out[where[0]]
    out[where[0]] = (key, text if len(where) == 1 else replace_leaf(value, where[1:], text))
    return out


def leaf_at(obj: list[tuple[str, Any]], where: tuple[int, ...]) -> str:
    value = obj[where[0]][1]
    return value if len(where) == 1 else leaf_at(value, where[1:])


@settings(max_examples=200, deadline=None, derandomize=True)
@given(obj=raw_objects(), seed=st.integers(min_value=0, max_value=2**16))
def test_pr11_property_reordering_and_reindenting_never_move_the_digest(obj: list[tuple[str, Any]], seed: int) -> None:
    canonical_request = P().canonical_request
    assert canonical_request(render(obj)) == canonical_request(render(obj, random.Random(seed)))


@settings(max_examples=200, deadline=None, derandomize=True)
@given(obj=raw_objects(), pick=st.integers(min_value=0, max_value=10**6), new=LEAF_LITERALS)
def test_pr11_property_changing_one_leafs_literal_always_moves_the_digest(
    obj: list[tuple[str, Any]], pick: int, new: str
) -> None:
    sites = list(leaves(obj))
    where = sites[pick % len(sites)]
    if leaf_at(obj, where) == new:
        return
    canonical_request = P().canonical_request
    assert canonical_request(render(obj)) != canonical_request(render(replace_leaf(obj, where, new)))


def test_pr11_the_request_digest_is_a_sha256_hex_over_body_target_and_unexempted_headers() -> None:
    request_digest = P().request_digest
    target = {"url.full": URL, "http.request.method": "POST"}
    body = body_text(BASE_FIELDS)
    base = request_digest(body, target=target, headers={"content-type": "application/json", "x-request-id": "1"}, exemptions=("x-request-id",))
    assert HEX64.match(base), base
    same = request_digest(body, target=target, headers={"content-type": "application/json", "x-request-id": "2"}, exemptions=("X-Request-Id",))
    assert same == base
    moved = {
        "unexempted header": request_digest(body, target=target, headers={"content-type": "text/plain", "x-request-id": "1"}, exemptions=("x-request-id",)),
        "the exemption removed": request_digest(body, target=target, headers={"content-type": "application/json", "x-request-id": "2"}, exemptions=()),
        "url": request_digest(body, target={**target, "url.full": URL + "?v=2"}, headers={"content-type": "application/json", "x-request-id": "1"}, exemptions=("x-request-id",)),
        "method": request_digest(body, target={**target, "http.request.method": "PUT"}, headers={"content-type": "application/json", "x-request-id": "1"}, exemptions=("x-request-id",)),
        "body": request_digest(body.replace("0.95", "0.9500000000000001"), target=target, headers={"content-type": "application/json", "x-request-id": "1"}, exemptions=("x-request-id",)),
    }
    assert base not in moved.values(), moved
    assert len(set(moved.values())) == len(moved), moved


def test_pr11_a_stored_pair_that_differs_by_a_literal_a_float_cannot_see_is_excluded_as_body(tmp_path: Path) -> None:
    """Named mutant 1, end to end: the difference travels through the store and the assertion."""
    assert float("0.30") == float("0.30000000000000001")
    fields = {"state": f'"state of {ITEM}"', "temperature": "0.30000000000000001"}
    a = with_row(ITEM, fields={"state": f'"state of {ITEM}"', "temperature": "0.30"})
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, with_row(ITEM, fields=fields)), decl()), ITEM, "body")
    assert (row["cut"], row["arm"]) == ("c60", "both")


@pytest.mark.parametrize(
    ("left", "right"),
    [("1", "1.0"), ("64", "64.0"), ("0.95", "0.95000000000000001"), ("0.30", "0.3"), ("100", "1e2")],
)
def test_pr11_one_versus_one_point_zero_between_arms_is_excluded_as_body(tmp_path: Path, left: str, right: str) -> None:
    state = f'"state of {ITEM}"'
    a = with_row(ITEM, fields={"state": state, "max_tokens": left})
    b = with_row(ITEM, fields={"state": state, "max_tokens": right})
    assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "body")


def test_pr11_key_order_and_indentation_between_arms_leave_the_pair_eligible(tmp_path: Path) -> None:
    fields = {**BASE_FIELDS, "state": f'"state of {ITEM}"'}
    reordered = "{\n  " + ",\n  ".join(f'"{k}" : {v}' for k, v in reversed(list(fields.items()))) + "\n}"
    assertion = P().assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, raw_body=reordered)), decl())
    assert eligible_items(assertion) == ALL_ITEMS
    digest = assertion.pairs.set_index("cluster").loc[ITEM, "request_digest"]
    assert HEX64.match(digest), digest
    assert assertion.pairs["request_digest"].nunique() == len(ALL_ITEMS)


# ---------- PR12: every field, present or absent ----------


@pytest.mark.parametrize("absent_in", ["a", "b"])
@pytest.mark.parametrize("field", ["seed", "top_p"])
def test_pr12_a_field_in_one_arm_and_not_the_other_is_body_field_absent_and_is_named(
    tmp_path: Path, absent_in: str, field: str
) -> None:
    state = f'"state of {ITEM}"'
    present = with_row(ITEM, fields={"state": state, field: "7"})
    absent = with_row(ITEM, fields={"state": state, field: MISSING})
    a, b = (absent, present) if absent_in == "a" else (present, absent)
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "body_field_absent")
    assert field in str(row["detail"]), row.to_dict()


def test_pr12_an_explicit_null_is_present_and_is_not_the_same_as_absent(tmp_path: Path) -> None:
    state = f'"state of {ITEM}"'
    a = with_row(ITEM, fields={"state": state, "seed": "null"})
    b = with_row(ITEM, fields={"state": state})
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "body_field_absent")
    assert "seed" in str(row["detail"])


def test_pr12_a_nested_field_absent_in_one_arm_fails_the_pair(tmp_path: Path) -> None:
    state = f'"state of {ITEM}"'
    a = with_row(ITEM, fields={"state": state, "questions": '{"q1": {"type": "score", "instructions": "rate it", "scale": 5}}'})
    b = with_row(ITEM, fields={"state": state})
    assertion = P().assert_pairs(make_sweep(tmp_path, a, b), decl())
    row = excluded_of(assertion, ITEM)
    assert row["cause"] in {"body_field_absent", "body"}, row.to_dict()
    assert eligible_items(assertion) == ALL_ITEMS - {ITEM}


# ---------- PR13: the pin is asserted inside the body, in both arms ----------


@pytest.mark.parametrize(("wrong_in", "arm"), [(("a",), "a"), (("b",), "b"), (("a", "b"), "both")])
def test_pr13_a_body_whose_model_is_not_the_pin_is_cause_model_pin(
    tmp_path: Path, wrong_in: tuple[str, ...], arm: str
) -> None:
    """The ``both`` case is the one that matters: the two arms agree with each other, their
    digests are equal, and the pair is still not a pair at the pinned model."""
    wrong = with_row(ITEM, fields={"state": f'"state of {ITEM}"', "model": '"scorer-1.12.9"'})
    a = wrong if "a" in wrong_in else default_rows()
    b = wrong if "b" in wrong_in else default_rows()
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "model_pin")
    assert row["arm"] == arm, row.to_dict()


def test_pr13_a_config_axis_that_says_the_pin_does_not_rescue_a_body_that_does_not(tmp_path: Path) -> None:
    def rows(model: str) -> dict[str, Row]:
        out = default_rows()
        for item, row in out.items():
            out[item] = dataclasses.replace(row, extra_config={"model": MODEL_PIN})
        out[ITEM] = dataclasses.replace(out[ITEM], fields={"state": f'"state of {ITEM}"', "model": model})
        return out

    wrong = rows('"scorer-latest"')
    assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, wrong, wrong), decl()), ITEM, "model_pin")


def test_pr13_a_body_with_no_model_field_in_either_arm_is_not_at_the_pin(tmp_path: Path) -> None:
    rows = with_row(ITEM, fields={"state": f'"state of {ITEM}"', "model": MISSING})
    assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, rows, rows), decl()), ITEM, "model_pin")


def test_pr13_the_model_key_is_a_dotted_path_into_the_body(tmp_path: Path) -> None:
    def rows(model: str) -> dict[str, Row]:
        out = default_rows()
        for item, row in out.items():
            fields = {**row.fields, "model": MISSING, "request": f'{{"model": "{MODEL_PIN}"}}'}
            out[item] = dataclasses.replace(row, fields=fields)
        out[ITEM].fields["request"] = f'{{"model": "{model}"}}'
        return out

    d = decl(model_key="request.model")
    assert eligible_items(P().assert_pairs(make_sweep(tmp_path, rows(MODEL_PIN), rows(MODEL_PIN), name="ok"), d)) == ALL_ITEMS
    wrong = rows("scorer-1.12.9")
    assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, wrong, wrong), d), ITEM, "model_pin")


# ---------- PR14: the target ----------


@pytest.mark.parametrize(
    ("header", "a_value", "b_value"),
    [
        ("content-type", ["application/json"], ["application/json; charset=utf-8"]),
        ("x-api-version", ["2026-09-01"], ["2026-09-19"]),
        ("x-api-version", ["2026-09-01"], None),
    ],
)
def test_pr14_a_differing_header_that_is_not_exempt_is_cause_header_and_is_named(
    tmp_path: Path, header: str, a_value: list[str], b_value: list[str] | None
) -> None:
    a = with_row(ITEM, headers={header: a_value})
    b = default_rows() if b_value is None else with_row(ITEM, headers={header: b_value})
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "header")
    assert header in str(row["detail"]).lower(), row.to_dict()
    assert row["arm"] == "both"


@pytest.mark.parametrize("change", [{"url": URL + "/v2"}, {"method": "PUT"}])
def test_pr14_a_differing_url_or_method_is_cause_target(tmp_path: Path, change: dict[str, str]) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, **change)), decl())
    assert assert_only_excluded(assertion, ITEM, "target")["arm"] == "both"


# ---------- PR15: silence is never a pass ----------


def _headerless() -> dict[str, Row]:
    return {item: dataclasses.replace(row, headers=None) for item, row in default_rows().items()}


def test_pr15_no_recorded_header_under_headers_asserted_is_not_assertable(tmp_path: Path) -> None:
    paired = P()
    paired.assert_pairs(make_sweep(tmp_path, name="control"), decl(headers="asserted"))
    with pytest.raises(paired.NotAssertable):
        paired.assert_pairs(make_sweep(tmp_path, _headerless(), _headerless()), decl(headers="asserted"))


def test_pr15_under_not_recorded_the_run_proceeds_and_the_gap_is_printed(tmp_path: Path) -> None:
    store = make_sweep(tmp_path, _headerless(), _headerless())
    assertion = P().assert_pairs(store, decl(headers="not_recorded"))
    assert eligible_items(assertion) == ALL_ITEMS
    assert "headers" in assertion.environment["gaps"]
    assert "headers" in json.loads(assertion.to_json())["environment"]["gaps"]


def test_pr15_recorded_and_asserted_headers_leave_no_header_gap(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path), decl(headers="asserted"))
    assert "headers" not in assertion.environment["gaps"]


# ---------- PR16: exemptions are recorded as exercised ----------


def test_pr16_each_pair_lists_the_exemptions_that_absorbed_a_difference(tmp_path: Path) -> None:
    """``x-request-id`` differs on every pair by construction; ``date`` differs on one; and
    ``idempotency-key`` is declared and never sent, so it must read as declared and unexercised."""
    a = with_row(ITEM, headers={"date": ["Mon, 21 Sep 2026 22:00:00 GMT"]})
    b = with_row(ITEM, headers={"date": ["Mon, 21 Sep 2026 22:14:09 GMT"]})
    d = decl(exemptions=("X-Request-Id", "date", "idempotency-key"))
    assertion = P().assert_pairs(make_sweep(tmp_path, a, b), d)
    assert eligible_items(assertion) == ALL_ITEMS
    exercised = {r.cluster: tuple(r.exemptions_exercised) for r in assertion.pairs.itertuples()}
    assert set(exercised[ITEM]) == {"x-request-id", "date"}
    assert all(v == ("x-request-id",) for k, v in exercised.items() if k != ITEM), exercised
    assert assertion.counts["exemptions_exercised"] == {"x-request-id": 12, "date": 1, "idempotency-key": 0}
    payload = json.loads(assertion.to_json())
    assert payload["counts"]["exemptions_exercised"]["idempotency-key"] == 0
    by_item = {p["cluster"]: p["exemptions_exercised"] for p in payload["pairs"]}
    assert sorted(by_item[ITEM]) == ["date", "x-request-id"]


def test_pr16_an_exempt_header_that_is_equal_in_both_arms_was_not_exercised(tmp_path: Path) -> None:
    same = with_row(ITEM, headers={"x-request-id": ["fixed"], "date": ["Mon, 21 Sep 2026 22:00:00 GMT"]})
    assertion = P().assert_pairs(make_sweep(tmp_path, same, same), decl())
    exercised = {r.cluster: tuple(r.exemptions_exercised) for r in assertion.pairs.itertuples()}
    assert exercised[ITEM] == ()
    assert assertion.counts["exemptions_exercised"] == {"x-request-id": 11, "date": 0}


# ---------- PR17: environment identity is run-level ----------


def test_pr17_the_environment_of_both_arms_is_recorded(tmp_path: Path) -> None:
    env = {"concurrency": 4}
    store = make_sweep(tmp_path, a_kwargs={"env": env}, b_kwargs={"env": env})
    assertion = P().assert_pairs(store, decl())
    arms = assertion.environment["sweeps"]["S1"]
    for arm in ("a", "b"):
        assert arms[arm]["proofload_version"] == proofload.__version__
        assert arms[arm]["run_salt"] == SALT
        assert arms[arm]["python"] == PYTHON
        assert arms[arm]["concurrency"] == 4
        assert arms[arm]["capture_cap"] == "none"
    assert json.loads(assertion.to_json())["environment"]["sweeps"]["S1"]["b"]["run_salt"] == SALT


def test_pr17_the_two_facts_proofload_does_not_record_are_printed_as_gaps(tmp_path: Path) -> None:
    gaps = P().assert_pairs(make_sweep(tmp_path), decl()).environment["gaps"]
    assert {"harness_digest", "client_version"} <= set(gaps), gaps


@pytest.mark.parametrize(
    "b_kwargs",
    [
        pytest.param({"version": "0.0.0+other"}, id="proofload_version"),
        pytest.param({"salt": "4c71e89b2a0f3d65"}, id="run_salt"),
        pytest.param({"env": {"python": "3.12.4 (main)"}}, id="python"),
        pytest.param({"env": {"concurrency": 8}}, id="concurrency"),
        pytest.param({"env": {"capture": {"content": True, "max_observation_bytes": 8192, "max_spans": 200}}}, id="capture_cap"),
    ],
)
def test_pr17_a_difference_between_the_arms_manifests_is_a_run_level_refusal(
    tmp_path: Path, b_kwargs: dict[str, Any]
) -> None:
    paired = P()
    a_kwargs = {"env": {"concurrency": 4}}
    merged = {**b_kwargs, "env": {"concurrency": 4, **b_kwargs.get("env", {})}}
    paired.assert_pairs(make_sweep(tmp_path, name="control", a_kwargs=a_kwargs, b_kwargs=a_kwargs), decl())
    with pytest.raises(paired.NotAssertable):
        paired.assert_pairs(make_sweep(tmp_path, a_kwargs=a_kwargs, b_kwargs=merged), decl())


def test_pr17_one_row_whose_seed_differs_refuses_the_run_and_is_never_a_per_pair_exclusion(tmp_path: Path) -> None:
    paired = P()
    with pytest.raises(paired.NotAssertable):
        paired.assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, seed_offset=1)), decl())


# ---------- PR18: zero retries ----------


@pytest.mark.parametrize("arm", ["a", "b", "both"])
def test_pr18_two_request_spans_in_one_episode_is_retry_or_multicall(tmp_path: Path, arm: str) -> None:
    twice = with_row(ITEM, n_request_spans=2)
    a = twice if arm in ("a", "both") else default_rows()
    b = twice if arm in ("b", "both") else default_rows()
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "retry_or_multicall")
    assert row["arm"] == arm


def test_pr18_spans_under_another_name_are_not_a_second_request(tmp_path: Path) -> None:
    busy = with_row(ITEM, other_spans=3)
    assertion = P().assert_pairs(make_sweep(tmp_path, busy, busy), decl())
    assert eligible_items(assertion) == ALL_ITEMS


def test_pr18_retries_not_recorded_is_printed_as_a_gap(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path), decl(retries="not_recorded"))
    assert "retries" in assertion.environment["gaps"]
    assert "retries" in json.loads(assertion.to_json())["environment"]["gaps"]


def test_pr18_retries_asserted_passes_on_two_manifests_that_record_zero(tmp_path: Path) -> None:
    zero = {"env": {"infra_retries": 0}}
    assertion = P().assert_pairs(make_sweep(tmp_path, a_kwargs=zero, b_kwargs=zero), decl(retries="asserted"))
    assert eligible_items(assertion) == ALL_ITEMS
    assert "retries" not in assertion.environment["gaps"]


@pytest.mark.parametrize(
    ("a_env", "b_env"),
    [
        pytest.param({}, {}, id="neither-records-it"),
        pytest.param({"infra_retries": 0}, {}, id="one-arm-is-silent"),
        pytest.param({"infra_retries": 0}, {"infra_retries": 2}, id="one-arm-retried"),
        pytest.param({"infra_retries": 2}, {"infra_retries": 2}, id="both-arms-retried"),
    ],
)
def test_pr18_retries_asserted_refuses_a_manifest_that_is_silent_or_not_zero(
    tmp_path: Path, a_env: dict[str, Any], b_env: dict[str, Any]
) -> None:
    paired = P()
    with pytest.raises(paired.NotAssertable):
        paired.assert_pairs(
            make_sweep(tmp_path, a_kwargs={"env": a_env}, b_kwargs={"env": b_env}), decl(retries="asserted")
        )


# ---------- PR19: an errored pair is ineligible, counted, and never repaired ----------


@pytest.mark.parametrize("error", ["timeout", "infra: ConnectionError('reset')", "Traceback: HTTPStatusError 429"])
@pytest.mark.parametrize("arm", ["a", "b", "both"])
def test_pr19_a_row_that_errored_in_either_arm_makes_the_pair_ineligible(tmp_path: Path, arm: str, error: str) -> None:
    broken = with_row(ITEM, error=error)
    a = broken if arm in ("a", "both") else default_rows()
    b = broken if arm in ("b", "both") else default_rows()
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "errored")
    assert row["arm"] == arm


@pytest.mark.parametrize("arm", ["a", "b"])
def test_pr19_a_missing_value_key_is_value_missing(tmp_path: Path, arm: str) -> None:
    broken = with_row(ITEM, value=MISSING)
    a, b = (broken, default_rows()) if arm == "a" else (default_rows(), broken)
    row = assert_only_excluded(P().assert_pairs(make_sweep(tmp_path, a, b), decl()), ITEM, "value_missing")
    assert row["arm"] == arm


@pytest.mark.parametrize("value", ["1.5", "-0.1", 1.5, -0.25, 2, "1.0000000000000000001", "-0.0000000000000000001"])
def test_pr19_a_value_outside_the_unit_interval_is_value_out_of_range(tmp_path: Path, value: Any) -> None:
    """The two long literals are one and zero to a float. Read as the text the harness stored,
    they are outside the interval."""
    assertion = P().assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, value=value)), decl())
    row = assert_only_excluded(assertion, ITEM, "value_out_of_range")
    assert row["arm"] == "b"


@pytest.mark.parametrize("value", ["0", "1", 0, 1, "0.0", "1.0", "0.60", 0.6])
def test_pr19_the_ends_of_the_interval_are_inside_it_and_the_value_is_a_decimal(tmp_path: Path, value: Any) -> None:
    rows = with_row(ITEM, value=value)
    assertion = P().assert_pairs(make_sweep(tmp_path, rows, rows), decl())
    assert eligible_items(assertion) == ALL_ITEMS
    pair = assertion.pairs.set_index("cluster").loc[ITEM]
    assert isinstance(pair["value_a"], Decimal) and isinstance(pair["value_b"], Decimal)
    assert pair["value_a"] == pair["value_b"] == Decimal(str(value))


def test_pr19_a_stored_request_that_is_not_a_json_object_is_malformed_body(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, raw_body='{"model": "scorer-1.13.0", ')), decl())
    assert_only_excluded(assertion, ITEM, "malformed_body")


def test_pr19_an_episode_with_no_span_under_the_declared_name_is_no_request_span(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, n_request_spans=0, other_spans=2)), decl())
    row = assert_only_excluded(assertion, ITEM, "no_request_span")
    assert row["arm"] == "b"


def test_pr19_an_errored_pair_is_never_repaired_from_the_arm_that_answered(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, None, with_row(ITEM, error="timeout")), decl())
    assert ITEM not in set(assertion.pairs["cluster"])
    assert len(assertion.pairs) + len(assertion.excluded) == len(ALL_ITEMS)
    assert not assertion.pairs[["value_a", "value_b"]].isna().any().any()


# ---------- PR20, PR21: the counts reconcile and no pair leaves silently ----------


def mixed_arms() -> tuple[dict[str, Row], dict[str, Row]]:
    """An error in each arm and in both, one unmatched key per arm, and four more causes -- the
    frame section 6 says the mock runs cannot give."""
    a, b = default_rows(), default_rows()
    a["c50-i000"] = dataclasses.replace(a["c50-i000"], error="timeout")
    b["c50-i001"] = dataclasses.replace(b["c50-i001"], error="infra: reset")
    a["c60-i000"] = dataclasses.replace(a["c60-i000"], error="timeout")
    b["c60-i000"] = dataclasses.replace(b["c60-i000"], error="timeout")
    del b["c60-i001"]
    del a["c90-i000"]
    b["c90-i001"] = dataclasses.replace(b["c90-i001"], value="1.5")
    b["c90-i002"] = dataclasses.replace(b["c90-i002"], n_request_spans=2)
    b["c50-i002"] = dataclasses.replace(b["c50-i002"], headers={"x-api-version": ["2"]})
    b["c60-i002"] = dataclasses.replace(b["c60-i002"], fields={"state": '"state of c60-i002"', "top_p": "0.9500000000000001"})
    return a, b


MIXED_BY_CUT = {
    "c50": {"keys": 4, "matched": 4, "unmatched": 0, "eligible": 1, "ineligible": 3,
            "by_cause": {"errored": 2, "header": 1}, "by_arm": {"a": 1, "b": 1, "both": 1}},
    "c60": {"keys": 4, "matched": 3, "unmatched": 1, "eligible": 1, "ineligible": 2,
            "by_cause": {"errored": 1, "unmatched": 1, "body": 1}, "by_arm": {"both": 2, "a": 1}},
    "c90": {"keys": 4, "matched": 3, "unmatched": 1, "eligible": 1, "ineligible": 2,
            "by_cause": {"unmatched": 1, "value_out_of_range": 1, "retry_or_multicall": 1},
            "by_arm": {"b": 3}},
}
MIXED_TOTAL = {"keys": 12, "matched": 10, "unmatched": 2, "eligible": 3, "ineligible": 7}


def nonzero(counts: Mapping[str, int]) -> dict[str, int]:
    return {k: int(v) for k, v in counts.items() if v}


def test_pr20_the_counts_are_exact_per_cut_per_cause_and_per_arm(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, *mixed_arms()), decl())
    counts = assertion.counts
    assert set(counts["by_cut"]) == {cut for cut, _ in CUTS}
    for cut, expected in MIXED_BY_CUT.items():
        got = counts["by_cut"][cut]
        assert COUNT_KEYS <= set(got), (cut, set(got))
        for key in ("keys", "matched", "unmatched", "eligible", "ineligible"):
            assert got[key] == expected[key], (cut, key, got)
        assert nonzero(got["by_cause"]) == expected["by_cause"], (cut, got["by_cause"])
        assert nonzero(got["by_arm"]) == expected["by_arm"], (cut, got["by_arm"])
        assert got["reconciles"] is True
    total = counts["total"]
    for key, n in MIXED_TOTAL.items():
        assert total[key] == n, (key, total)
    assert total["reconciles"] is True
    assert set(total["by_cause"]) <= CAUSES, set(total["by_cause"]) - CAUSES


def check_reconciles(assertion: Any, n_keys: int) -> None:
    counts = assertion.counts
    for block in (counts["total"], *counts["by_cut"].values()):
        assert block["eligible"] + block["ineligible"] == block["matched"], block
        assert block["matched"] + block["unmatched"] == block["keys"], block
        assert sum(block["by_cause"].values()) == block["ineligible"] + block["unmatched"], block
        assert block["reconciles"] is True
    for key in ("keys", "matched", "unmatched", "eligible", "ineligible"):
        assert sum(b[key] for b in counts["by_cut"].values()) == counts["total"][key], key
    assert counts["total"]["keys"] == n_keys
    assert counts["total"]["eligible"] == len(assertion.pairs)
    assert counts["total"]["ineligible"] + counts["total"]["unmatched"] == len(assertion.excluded)


def test_pr20_the_artifact_carries_the_reconciliation(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, *mixed_arms()), decl())
    check_reconciles(assertion, 12)
    payload = json.loads(assertion.to_json())
    assert payload["counts"]["total"]["reconciles"] is True
    for key, n in MIXED_TOTAL.items():
        assert payload["counts"]["total"][key] == n
    assert len(payload["pairs"]) == 3 and len(payload["excluded"]) == 9


def test_pr20_the_union_is_taken_per_sweep_and_summed(tmp_path: Path) -> None:
    paired = P()
    store = make_sweep(tmp_path, *mixed_arms())
    salt = "4c71e89b2a0f3d65"
    make_arm(store, "s2-a", list(default_rows().values()), arm="a", salt=salt)
    make_arm(store, "s2-b", list(default_rows().values()), arm="b", salt=salt)
    sweeps = (paired.SweepPair(name="S1", a="s1-a", b="s1-b"), paired.SweepPair(name="S2", a="s2-a", b="s2-b"))
    assertion = paired.assert_pairs(store, decl(sweeps=sweeps))
    check_reconciles(assertion, 24)
    assert assertion.counts["total"]["eligible"] == 3 + 12
    assert assertion.counts["by_cut"]["c50"]["keys"] == 8


FAILURES: dict[str, Callable[[Row], Row | None]] = {
    "ok": lambda r: r,
    "errored": lambda r: dataclasses.replace(r, error="timeout"),
    "unmatched": lambda r: None,
    "value_missing": lambda r: dataclasses.replace(r, value=MISSING),
    "value_out_of_range": lambda r: dataclasses.replace(r, value="7"),
    "retry_or_multicall": lambda r: dataclasses.replace(r, n_request_spans=3),
    "header": lambda r: dataclasses.replace(r, headers={"x-api-version": ["other"]}),
    "target": lambda r: dataclasses.replace(r, url=URL + "/other"),
    "body": lambda r: dataclasses.replace(r, fields={**r.fields, "temperature": "0.31"}),
    "body_field_absent": lambda r: dataclasses.replace(r, fields={**r.fields, "top_p": MISSING}),
    "no_request_span": lambda r: dataclasses.replace(r, n_request_spans=0),
    "malformed_body": lambda r: dataclasses.replace(r, raw_body="not json"),
}
KEEP_ELIGIBLE = frozenset({"c50-i003", "c60-i003", "c90-i003"})


@settings(max_examples=25, deadline=None, derandomize=True)
@given(
    plan_a=st.lists(st.sampled_from(["ok", "ok", "ok", "errored", "unmatched"]), min_size=12, max_size=12),
    plan_b=st.lists(st.sampled_from(sorted(FAILURES)), min_size=12, max_size=12),
)
def test_pr20_property_whatever_breaks_the_counts_reconcile_and_every_cause_is_the_one_injected(
    plan_a: list[str], plan_b: list[str]
) -> None:
    """One cut keeps one untouched item so no cut is left empty (``NoEligiblePairs`` is not this
    phase's to pin). A pair broken in both arms may take either cause; precedence is not pinned."""
    a, b = default_rows(), default_rows()
    injected: dict[str, set[str]] = {}
    for item, fail_a, fail_b in zip(sorted(ALL_ITEMS), plan_a, plan_b, strict=True):
        if item in KEEP_ELIGIBLE:
            continue
        if fail_a == "unmatched" and fail_b == "unmatched":
            fail_b = "ok"
        for rows, fail in ((a, fail_a), (b, fail_b)):
            changed = FAILURES[fail](rows[item])
            if changed is None:
                del rows[item]
            else:
                rows[item] = changed
        causes = {f for f in (fail_a, fail_b) if f != "ok"}
        if causes:
            injected[item] = {"unmatched"} if "unmatched" in causes else causes
    with tempfile.TemporaryDirectory() as root:
        assertion = P().assert_pairs(make_sweep(Path(root), a, b), decl())
    n_keys = len(set(a) | set(b))
    check_reconciles(assertion, n_keys)
    assert eligible_items(assertion) == ALL_ITEMS - set(injected)
    assert set(assertion.excluded["cluster"]) == set(injected)
    for row in assertion.excluded.itertuples():
        assert row.cause in injected[row.cluster], (row.cluster, row.cause, injected[row.cluster])


def test_pr21_every_key_of_either_arm_is_in_exactly_one_of_the_two_frames(tmp_path: Path) -> None:
    a, b = mixed_arms()
    assertion = P().assert_pairs(make_sweep(tmp_path, a, b), decl())
    key = ["sweep", "config_hash", "replicate_index"]
    kept = {tuple(r) for r in assertion.pairs[key].itertuples(index=False)}
    dropped = {tuple(r) for r in assertion.excluded[key].itertuples(index=False)}
    assert not kept & dropped
    assert len(kept) == len(assertion.pairs) and len(dropped) == len(assertion.excluded)
    every = {("S1", config_hash({"item": r.item, "cut": r.cut}), 0) for r in (*a.values(), *b.values())}
    assert kept | dropped == every
    assert assertion.excluded["cause"].notna().all() and set(assertion.excluded["cause"]) <= CAUSES
    assert assertion.excluded["cut"].notna().all()


def test_pr21_the_artifact_lists_every_exclusion_with_its_cause_and_a_total(tmp_path: Path) -> None:
    assertion = P().assert_pairs(make_sweep(tmp_path, *mixed_arms()), decl())
    payload = json.loads(assertion.to_json())
    assert len(payload["excluded"]) == len(assertion.excluded) == 9
    assert sorted(e["cause"] for e in payload["excluded"]) == sorted(assertion.excluded["cause"])
    assert all(e["cause"] in CAUSES and e["cluster"] and e["cut"] for e in payload["excluded"])
    total = payload["counts"]["total"]
    assert total["ineligible"] + total["unmatched"] == len(payload["excluded"])
    assert sum(total["by_cause"].values()) == len(payload["excluded"])


# ---------- PR56: the Modal manifest records the retry setting ----------


def scored_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    return Episode(outcome="scored", t=1.0, horizon=HORIZON)


def in_process_mapper(batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, list[Result]]]:
    for index, jobs in enumerate(batches):
        yield index, worker_batch(jobs, f"{MODULE}:scored_rollout", None)


@pytest.mark.parametrize("retries", [0, 1, 5])
def test_pr56_the_modal_manifest_records_infra_retries_as_it_was_set(tmp_path: Path, retries: int) -> None:
    store = Store(tmp_path / "store")
    spec = SweepSpec.build([{"x": 0.1}, {"x": 0.2}], replicates=2, target_id=TARGET, t_unit="steps")
    p = plan(spec, store, backend="modal")
    run_with_mapper(p, in_process_mapper, store, options=ModalOptions(batch_size=2, infra_retries=retries))
    environment = dict(store.manifest(p.run_id).environment)
    assert "infra_retries" in environment, sorted(environment)
    assert environment["infra_retries"] == retries and type(environment["infra_retries"]) is int
    assert json.loads(json.dumps(environment)) == environment


def test_pr56_the_default_is_recorded_too_because_the_claim_is_about_the_run(tmp_path: Path) -> None:
    """Not a flag echo: a run launched with no ``--infra-retries`` retried up to the default, and
    that is what its manifest must say."""
    store = Store(tmp_path / "store")
    spec = SweepSpec.build([{"x": 0.1}], replicates=1, target_id=TARGET, t_unit="steps")
    p = plan(spec, store, backend="modal")
    run_with_mapper(p, in_process_mapper, store, options=ModalOptions())
    assert store.manifest(p.run_id).environment["infra_retries"] == ModalOptions().infra_retries
