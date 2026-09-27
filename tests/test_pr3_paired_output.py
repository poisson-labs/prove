"""PR-3 oracle, the output packet: windows, cost and rendering of "Prove -- Spec PR Paired
Replay" -- invariants PR7, PR40 to PR55 and PR77, with named mutants 5, 6 and 7. The
replicates packet (PR57 to PR76) is ``tests/test_pr3_replicates.py``; section 7 lets a Session A
cut PR-3 into the two files and freezes them in one pass.

Written by Session A on 2026-09-22 on ``pr3-oracle`` over the replicates oracle (``9e41c2b``) and
the ruled retrofit ``6f40d92`` (the two phase-2 artifacts print ``comparison``). **Frozen
2026-09-22 in one commit over both PR-3 files, over the reviewed ``ef9f4ef``**, after Taylor
approved the four tables in the handoff (``log/prove-pr3-session-a/README.md``) and an
independent recompute of every hard-coded expectation passed (``recompute_expectations.py``
there, 83 of 83). Session B builds phase 3's output half against this file and does not edit
it: ``WindowReport``,
``windows``, ``CostReport`` and ``cost`` in ``src/proofload/paired.py``, the ``paired`` verb and
the ``--paired`` flag in ``cli.py``, and **nothing in ``report.py``**, whose whole-file digest two
frozen tests pin and this file pins again. Phase 3's names are read through ``getattr`` inside
each test, so the bare tree fails test by test and never at collection.

**What the packet is.** Each sweep is its own window, read from the trace envelope and never
from ``wall_time`` (PR40 to PR43); the per-pair replay gap is reported and never selected on
(PR44, PR45); ``windows.json`` is a timing artifact and nothing else (PR46). Cost is the
provider's own recorded usage summed per phase, per sweep and per arm, priced only against a
declared price, with unrecorded spans counted as what they are and the cap gated between sweeps
(PR7, PR47 to PR52). The renderer folds four sections into ``report.md`` and ``receipt.html``
behind ``--paired``, formats and computes nothing, and prints no verdict (PR53 to PR55, PR77).

**Conventions this file fixes for the build session** (section 2 leaves them open; each goes
into the spec's change log on the freeze):

- *Timing rides on ``pairs``.* ``assert_pairs`` records, per eligible set and per arm label,
  ``start_ns_<label>`` and ``end_ns_<label>`` off the request span (``None`` where the span
  has none), after the value columns and in arm order -- at ``k = 2`` the four
  ``TIMING_COLUMNS`` the replicates oracle names. ``windows`` reads them and reads nothing else,
  so it takes a ``PairAssertion`` and nothing else (PR9) and an excluded set has no window.
- *``WindowReport``.* ``per_sweep`` is one mapping per declared sweep in declaration order:
  ``sweep``, ``timing`` (``"available"`` or ``"unavailable"``), ``reason`` (``None`` or the
  fact, naming the arm and the field), ``arms`` (``{label: {first_start_ns, last_end_ns}}``),
  ``realized_span_s`` (first request ``start_ns`` in arm ``a`` to the last response ``end_ns``
  in the last declared arm, in seconds; ``None`` when unavailable), ``declared_window_s``,
  ``claim`` (``"held"`` when the realized span is at or under the declared window,
  ``"withdrawn"`` above it, ``None`` without a declared window or without timing) and
  ``latency_s`` (``{median, n}`` over every eligible request span of every arm in the sweep with
  both timestamps; ``None`` with none). ``replay_gap`` is keyed by cut name in declaration
  order, ``{min, median, max}`` in seconds of ``start_ns_b - start_ns_a`` over the cut's
  eligible pairs across all sweeps, ``None`` for a cut with no computable gap. A sweep is
  unavailable when no eligible pair carries the needed start or end; a sweep with some
  timestamps missing is not pinned. ``to_json()`` is ``{per_sweep, replay_gap}``.
- *``CostReport``.* ``cost(store, declaration, *, phases)`` reads every run id in ``phases``
  (label to run ids), every span named ``request_span`` in every stored episode -- retries
  included, because they were paid for -- and counts a span with ``tokens["in"]`` as recorded
  and any other span as unrecorded; ``tokens["out"]`` is summed where present. ``phases`` is one
  mapping per run id in the order given: ``phase``, ``run_id``, ``sweep`` and ``arm`` (the
  declaration's, or ``None`` for a run outside every sweep), ``input_tokens``,
  ``output_tokens``, ``recorded_spans``, ``unrecorded_spans``. The totals are their sums;
  ``dollars = Decimal(input_tokens) * price`` or ``None``; ``cap_reached = token_cap is not None
  and input_tokens >= token_cap``. A run id in two phases is a ``PairedError``. In ``to_json()``
  the price and the dollars are their ``Decimal`` literals as strings, never floats.
- *The CLI.* ``proofload paired --declaration DECL.toml [--out DIR] [--format md|json]
  [--cap-check] [--force]`` runs the assertion, the analysis, the windows, the cost with one
  phase per declared sweep (the sweep's name, its arms) and the replicates, and writes the
  artifacts into ``--out`` (default ``./proofload-paired-<first 12 hex of the digest>``, refused
  non-empty without ``--force``), printing one path per line; ``--format json`` prints the
  combined payload -- keys ``pair_assertion``, ``contingency_by_cut``, ``intervals_by_cut``,
  ``windows``, ``cost`` and, at ``k > 2`` only, ``replicates_by_cut`` -- and writes nothing;
  ``--cap-check`` prints the cost block alone, writes nothing, exits 1 at or above the cap and
  0 otherwise. ``report A B --paired DECL.toml`` refuses, by name and with exit 2, a pair that is
  not ``(a, b)`` of a declared sweep, and otherwise writes the three report files and the
  artifacts into ``--out``. A ``PairedError`` is a clean refusal, exit 2.
- *The artifacts.* Every one is a JSON object whose first key is ``declaration_digest``:
  ``windows.json`` and ``cost.json`` wrap the two ``to_json()`` payloads under it;
  ``replicates_by_cut.json`` is ``{declaration_digest, cuts}`` keyed by cut name in declaration
  order, each cut ``ReplicateResult.to_json()``'s object, and it is not written at ``k = 2``.
- *Decimal literals.* A declared price and the dollars it implies are printed and serialised
  with ``format(value, "f")``, never ``str``, which turns ``0.000000042`` into ``4.2E-8``.
- *The sections.* ``## Paired replay``, then at ``k > 2`` ``## Replicates``, then
  ``## Windows``, then ``## Cost``, inserted after the honesty or coverage section and before the
  epistemic fence, in ``report.md`` as markdown and in ``receipt.html`` as ``<h2>`` sections
  before the ``<blockquote>``. Every number is printed as the artifact carries it -- the JSON
  value's own text, a ``Decimal`` literal verbatim -- so PR54 is a byte search. The arm-order
  check is printed under that name and no other. The Provenance block gains ``declaration
  digest``, ``bootstrap seed``, ``bootstrap b``, ``price per input token``, ``input tokens``,
  ``output tokens`` and ``artifacts`` (the filenames, six at ``k > 2``; R2).
- *The comparison in the two phase-2 artifacts (ruled 2026-09-22).* ``CutResult``'s seven fields
  are pinned by the frozen PR-2 oracle, so the cut's declared comparison rides on
  ``CutResult.pooled["comparison"]`` and the two artifact writers print it beside the threshold;
  ``pooled``'s key set is not pinned and ``intervals_json`` prints its keys by name.
- *``report.py`` is not edited.* PR53's byte identity holds by construction: the sections are
  folded into the rendered strings by ``paired.py`` and ``cli.py``, and the whole-file digest
  ``REPORT_PY_SHA256`` two frozen tests carry is carried here too.

**Invariant-to-test map** is in the handoff (``log/prove-pr3-session-a/README.md``).

**Fixtures, and what each cannot express.** Every store is built under ``tmp_path`` by this file
with timestamps and token counts chosen per arm and per item, so a window, a gap, a missing
timestamp and an unrecorded span are each one knob. The Go1 fixture is read for PR53 only: it
is the report the suite already pins, and it carries no paired declaration.

**Green before and after -- named so their green is not read as coverage.**
``test_pr53_a_report_without_paired_is_byte_identical_to_todays`` (the E14 digests the suite
pins, re-taken through the CLI), ``test_pr53_report_py_is_not_touched_by_phase_three`` (the
whole-file digest) and ``test_pr51_the_executor_is_untouched_by_the_cap`` (a source scan) are
green on the bare tree and stay green. Every other test is red on the bare tree: on
``TypeError`` from ``Cut`` without ``comparison``, on ``AttributeError`` for the four missing
names, or on the CLI refusing the ``paired`` verb and the ``--paired`` flag.

**Named gaps, not pinned.** A sweep with some timestamps missing; a run id in ``phases`` that
the store does not hold; the ``paired`` verb's default ``--out`` name beyond its prefix; the
exact wording of any section beyond the words pinned; the alias lifting of token attributes,
which is ``trace.py``'s and A8a's.
"""

from __future__ import annotations

import dataclasses
import hashlib
import html
import inspect
import json
import re
import tempfile
import typing
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import proofload
import proofload.cli as cli
from proofload import paired
from proofload.episode import Episode
from proofload.executor import derive_seed
from proofload.store import EpisodeRecord, RunManifest, Store, config_hash
from proofload.trace import Span, Trace

REPO = Path(__file__).resolve().parents[1]
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
#: W20's E14 argv on the Go1 fixture, through the CLI, as today's build writes the three files:
#: minted 2026-09-22 on ``6f40d92``'s ``src/`` (the heatmap is the value ``test_s29_viewer.py``
#: pins; W20 takes its markdown and receipt through the builder, so those two are minted here,
#: the same bytes on two runs). PR53's "the report the same build produces today".
E14_ARGV = ("report", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw")
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): report.md and receipt.html print LS16's respelled Cells sentence ('MDE is the smallest detectable increase', no ADR number) and nothing else new; heatmap.svg is unchanged. Read through this test's own measurement on the built tree, not predicted.
E14_SHA256 = {
    "report.md": "69324de1b24bdcf561501e313561ea481e243249a982a3b274e727445a15c370",
    "heatmap.svg": "2e0dfe4e27314d30f1514104a60d0a566a75f4c032fa1b25f92b779f70c324de",
    "receipt.html": "f5b7342aeb67f1214140bb486b388e9e7a521ffb1d07e2972191b350fa5eb6eb",
}
#: ``test_s29_viewer.py``'s and ``test_fr_first_run.py``'s whole-file digest of ``report.py``.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): report.py is the local serve pass's build (the wrap, the complement, mde_unchanged, LS16's Cells sentence); phase three still does not touch it. The whole-file sha256 of the built file. Read through this test's own measurement on the built tree, not predicted.
# Re-minted 2026-09-26 (A10 declared expectations, phase two, off the build at 662ceff): report.py gains DeclarationCheck under TYPE_CHECKING, _run_declarations and _run_declaration, the declarations keyword on the three builders, and _provenance_lines printing an empty list as none (spec A10 W8); PR-3's phase three still does not touch it. The whole-file sha256 of the built file. Read through this test's own measurement on the built tree, not predicted.
REPORT_PY_SHA256 = "06775d22522d897f8bf7c6086739e301ceb92baf5c0b9d9a806afecaa2962e61"

EPOCH = 1_790_000_000_000_000_000
NS = 1_000_000_000
SALT = "9f4a1c62d08e5b37"
REQUEST_SPAN = "scorer.request"
MODEL_PIN = "scorer-1.13.0"
VALUE_KEY = "answers.q1.score"
URL = "https://api.example.test/v1/evaluate"
CUT, THRESHOLD = "c60", "0.60"
HI, LO = "0.95", "0.05"
B_SMALL = 200
SEED = 20260922

WINDOW_REPORT_FIELDS = ("per_sweep", "replay_gap")
COST_REPORT_FIELDS = (
    "phases", "input_tokens", "output_tokens", "recorded_spans", "unrecorded_spans",
    "price_per_input_token", "dollars", "token_cap", "cap_reached",
)
PER_SWEEP_KEYS = frozenset({
    "sweep", "timing", "reason", "arms", "realized_span_s", "declared_window_s", "claim",
    "latency_s",
})
PHASE_KEYS = frozenset({
    "phase", "run_id", "sweep", "arm", "input_tokens", "output_tokens", "recorded_spans",
    "unrecorded_spans",
})
FIVE = ("pair_assertion.json", "contingency_by_cut.json", "intervals_by_cut.json", "windows.json", "cost.json")
SIXTH = "replicates_by_cut.json"
REPORT_FILES = ("report.md", "heatmap.svg", "receipt.html")
SECTIONS = ("## Paired replay", "## Replicates", "## Windows", "## Cost")
FENCE = "> This is empirical evidence under a stated test envelope"
VERDICT_WORDS = ("reproducib", "stable", "unstable", "reliab", "trustworth", "pass", "fail")
TIMING_COLUMNS = ("start_ns_a", "end_ns_a", "start_ns_b", "end_ns_b")


def P() -> Any:
    return paired


def labels(k: int) -> tuple[str, ...]:
    return ("a", "b", *(str(i) for i in range(3, k + 1)))


# ---------- helpers: a store with timestamps and usage per arm and per item ----------


@dataclass
class TRow:
    """One item in one sweep as ``k`` stored episodes, each with its own request span timing
    and usage. Per-arm overrides are keyed by arm label; ``tokens`` may be ``None`` (no usage
    recorded) and ``end`` may be ``None`` (no response timestamp)."""

    item: str
    cut: str
    values: tuple[str, ...]
    start: dict[str, int] = dataclasses.field(default_factory=dict)
    end: dict[str, int | None] = dataclasses.field(default_factory=dict)
    tokens: dict[str, Mapping[str, int] | None] = dataclasses.field(default_factory=dict)
    error: dict[str, str] = dataclasses.field(default_factory=dict)
    n_spans: dict[str, int] = dataclasses.field(default_factory=dict)
    wall_time: float = 0.1


def default_start(index: int, label: str, sweep_index: int) -> int:
    """Items two seconds apart; arm ``a`` first, each later arm 60 s after the one before; each
    sweep a day after the last."""
    arm_index = labels(9).index(label)
    return EPOCH + sweep_index * 86_400 * NS + index * 2 * NS + arm_index * 60 * NS


DURATION_NS = 400_000_000  # 0.4 s per call unless a row says otherwise
DEFAULT_TOKENS: Mapping[str, int] = {"in": 400, "out": 12}


def _span(body: str, k: int, start: int, end: int | None, tokens: Mapping[str, int] | None) -> Span:
    return Span(
        span_id=f"{k + 1:016x}", parent_id=None, kind="http", name=REQUEST_SPAN,
        start_ns=start, end_ns=end, input=body,
        output='{"answers": {"q1": {"score": 0.62}}}', tokens=tokens,
        attrs={"url.full": URL, "http.request.method": "POST"},
    )


def _record(run_id: str, row: TRow, label: str, index: int, sweep_index: int) -> EpisodeRecord:
    config = {"item": row.item, "cut": row.cut}
    seed = derive_seed(SALT, config_hash(config), 0)
    if label in row.error:
        return EpisodeRecord.errored(
            run_id=run_id, config=config, seed=seed, replicate_index=0, error=row.error[label],
            wall_time=row.wall_time,
        )
    value = row.values[labels(len(row.values)).index(label)]
    body = f'{{"model": "{MODEL_PIN}", "state": "state of {row.item}", "temperature": 0.30, "max_tokens": 64}}'
    start = row.start.get(label, default_start(index, label, sweep_index))
    end = row.end[label] if label in row.end else start + DURATION_NS
    tokens = row.tokens[label] if label in row.tokens else DEFAULT_TOKENS
    spans = [
        _span(body, k, start + k * NS, None if end is None else end + k * NS, tokens)
        for k in range(row.n_spans.get(label, 1))
    ]
    meta: dict[str, Any] = {
        "trace": Trace(spans=tuple(spans), source="record").to_dict(),
        "answers": {"q1": {"score": value}},
    }
    outcome = "acted" if Decimal(value) >= Decimal("0.5") else "declined"
    episode = Episode(outcome=outcome, t=1.0, horizon=10.0, meta=meta)
    return EpisodeRecord.from_episode(
        episode, run_id=run_id, config=config, seed=seed, replicate_index=0,
        wall_time=row.wall_time,
    )


def make_store(
    root: Path,
    rows: Sequence[TRow],
    *,
    k: int = 2,
    sweeps: Sequence[str] = ("S1",),
    per_sweep: Mapping[str, Sequence[TRow]] | None = None,
    extra_runs: Mapping[str, Sequence[TRow]] | None = None,
    name: str = "store",
) -> Store:
    """``rows`` replayed in every sweep (``per_sweep`` overrides one); ``extra_runs`` are run
    ids outside every sweep, for the cost phases."""
    store = Store(root / name)

    def write(run_id: str, label: str, run_rows: Sequence[TRow], sweep_index: int) -> None:
        store.create_run(RunManifest(
            run_id=run_id, target_id="scorer@v1", t_unit="steps", run_salt=SALT,
            axis_types={"item": "categorical", "cut": "categorical"}, backend="local",
            environment={
                "python": "3.11.7", "platform": "oracle",
                "proofload_version": proofload.__version__,
                "capture": {"content": True, "max_observation_bytes": "none"},
            },
        ))
        store.append(run_id, [
            _record(run_id, row, label, index, sweep_index) for index, row in enumerate(run_rows)
        ])
        store.mark_complete(run_id)

    for sweep_index, sweep in enumerate(sweeps):
        sweep_rows = rows if per_sweep is None or sweep not in per_sweep else per_sweep[sweep]
        for label in labels(k):
            write(f"{sweep}-{label}", label, sweep_rows, sweep_index)
    for run_id, run_rows in (extra_runs or {}).items():
        write(run_id, "a", run_rows, 9)
    return store


def trows(g: int, *, cut: str = CUT, k: int = 2, pattern: Any = None) -> list[TRow]:
    return [
        TRow(f"{cut}-i{i:03d}", cut, tuple(
            HI if a else LO for a in (pattern(i) if pattern else (1,) * k)
        ))
        for i in range(g)
    ]


def default_rows(g: int = 8) -> list[TRow]:
    """Eight items at one cut; the first three flip between the arms."""
    return trows(g, pattern=lambda i: (1, 0) if i < 3 else (1, 1))


def declaration(
    *,
    cuts: Sequence[tuple[str, ...]] = ((CUT, THRESHOLD, "ge"),),
    sweeps: Sequence[str] = ("S1",),
    k: int = 2,
    b: int = B_SMALL,
    seed: int = SEED,
    **over: Any,
) -> Any:
    kwargs: dict[str, Any] = {
        "value_key": VALUE_KEY, "cluster_key": "item", "stratum_key": "cut",
        "cuts": tuple(
            P().Cut(name=c[0], threshold=Decimal(c[1]), comparison=c[2] if len(c) > 2 else "ge")
            for c in cuts
        ),
        "sweeps": tuple(
            P().SweepPair(name=s, a=f"{s}-a", b=f"{s}-b", more=tuple(f"{s}-{i}" for i in range(3, k + 1)))
            if k > 2 else P().SweepPair(name=s, a=f"{s}-a", b=f"{s}-b")
            for s in sweeps
        ),
        "request_span": REQUEST_SPAN, "model_key": "model", "model_pin": MODEL_PIN,
        "exemptions": ("x-request-id",), "headers": "not_recorded", "retries": "not_recorded",
        "bootstrap_b": b, "bootstrap_seed": seed,
    }
    kwargs.update(over)
    return P().Declaration(**kwargs)


TOML_TOP: dict[str, str] = {
    "value_key": f'"{VALUE_KEY}"', "cluster_key": '"item"', "stratum_key": '"cut"',
    "request_span": f'"{REQUEST_SPAN}"', "model_key": '"model"', "model_pin": f'"{MODEL_PIN}"',
    "exemptions": '["x-request-id"]', "headers": '"not_recorded"', "retries": '"not_recorded"',
    "bootstrap_b": str(B_SMALL), "bootstrap_seed": str(SEED),
}


def write_declaration(
    path: Path,
    *,
    top: Mapping[str, str] | None = None,
    cuts: Sequence[tuple[str, str, str]] = ((CUT, THRESHOLD, "ge"),),
    sweeps: Sequence[str] = ("S1",),
    k: int = 2,
) -> Path:
    merged = dict(TOML_TOP)
    merged.update(top or {})
    lines = [f"{key} = {value}" for key, value in merged.items()]
    for name, threshold, comparison in cuts:
        lines += ["", "[[cuts]]", f'name = "{name}"', f"threshold = {threshold}", f'comparison = "{comparison}"']
    for s in sweeps:
        lines += ["", "[[sweeps]]", f'name = "{s}"', f'a = "{s}-a"', f'b = "{s}-b"']
        if k > 2:
            lines.append("more = [" + ", ".join(f'"{s}-{i}"' for i in range(3, k + 1)) + "]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@dataclass
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: Sequence[str]) -> Result:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def root_of(store: Store) -> Path:
    """The store's directory, for ``--store``: the one private read this file makes."""
    return Path(store._root)  # noqa: SLF001


def paired_cli(store: Store, decl_path: Path, out: Path, *extra: str) -> Result:
    return run_cli(["--store", str(root_of(store)), "paired", "--declaration", str(decl_path), "--out", str(out), *extra])


def report_cli(store: Store, a: str, b: str, out: Path, *extra: str) -> Result:
    return run_cli(["--store", str(root_of(store)), "report", a, b, "--x", "item", "--out", str(out), *extra])


def artifacts_of(out: Path) -> dict[str, Any]:
    return {name: json.loads((out / name).read_text()) for name in (*FIVE, SIXTH) if (out / name).exists()}


def sections_of(markdown: str) -> str:
    """The paired sections of ``report.md``: from the first paired heading to the fence."""
    start = min((markdown.index(h) for h in SECTIONS if h in markdown), default=-1)
    assert start >= 0, markdown
    return markdown[start:markdown.index(FENCE)]


def html_sections_of(page: str) -> str:
    start = min((page.index(f"<h2>{h[3:]}</h2>") for h in SECTIONS if f"<h2>{h[3:]}</h2>" in page), default=-1)
    assert start >= 0, page
    return page[start:page.index("<blockquote>")]


def plain(html_text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", html_text))


NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:\.\d+)?(?:e-?\d+)?(?![\w.])")
NOISE = re.compile(
    r"\b[0-9a-f]{64}\b|\bj\d+\b|[A-Za-z]+@\d+|\bn(?:11|10|01|00)\b|\bS\d+\b"
    r"|\b\w+-[a-z0-9]+(?:-[a-z0-9]+)*\b|\b\d{1,3}(?:,\d{3})+\b|\bc\d\d\b|\bi\d{3}\b"
)


def numbers_in(text: str) -> list[str]:
    return NUMBER.findall(NOISE.sub(" ", text))


def leaves(node: Any) -> Iterator[Any]:
    if isinstance(node, Mapping):
        for value in node.values():
            yield from leaves(value)
    elif isinstance(node, list):
        for value in node:
            yield from leaves(value)
    else:
        yield node


def walk(node: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, node
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield from walk(value, (*path, str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, (*path, f"[{i}]"))


def artifact_values(artifacts: Mapping[str, Any]) -> tuple[set[float], set[str]]:
    numbers: set[float] = set()
    strings: set[str] = set()
    for tree in artifacts.values():
        for leaf in leaves(tree):
            if isinstance(leaf, bool) or leaf is None:
                continue
            if isinstance(leaf, (int, float)):
                numbers.add(float(leaf))
            elif isinstance(leaf, str):
                strings.add(leaf)
    return numbers, strings


def assert_every_number_is_in_the_artifacts(text: str, artifacts: Mapping[str, Any]) -> int:
    numbers, strings = artifact_values(artifacts)
    seen = 0
    for token in numbers_in(text):
        seen += 1
        assert token in strings or float(token) in numbers, (token, text[:400])
    return seen


def mask_digest(text: str) -> str:
    return re.sub(r'"declaration_digest": "[0-9a-f]{64}"', '"declaration_digest": "-"', text)


def two_by_two(store: Store, decl: Any) -> Any:
    return P().analyse(P().assert_pairs(store, decl))


def windows_of(store: Store, decl: Any) -> Any:
    return P().windows(P().assert_pairs(store, decl))


# ---------- the control ----------


def test_control_the_five_artifacts_and_the_report_come_out_of_one_store(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml")
    out = tmp_path / "paired"
    r = paired_cli(store, decl_path, out)
    assert r.code == 0, r.err
    assert sorted(p.name for p in out.iterdir()) == sorted(FIVE)
    assert [line.strip() for line in r.out.splitlines()] == [str(out / name) for name in FIVE]
    artifacts = artifacts_of(out)
    digest = P().Declaration.from_toml(decl_path).digest
    for name, tree in artifacts.items():
        assert list(tree)[0] == "declaration_digest" and tree["declaration_digest"] == digest, name
    assert artifacts["windows.json"]["per_sweep"][0]["timing"] == "available"
    assert artifacts["cost.json"]["input_tokens"] == 16 * 400
    report_out = tmp_path / "report"
    r = report_cli(store, "S1-a", "S1-b", report_out, "--paired", str(decl_path))
    assert r.code == 0, r.err
    assert sorted(p.name for p in report_out.iterdir()) == sorted((*REPORT_FILES, *FIVE))
    markdown = (report_out / "report.md").read_text()
    positions = [markdown.index(h) for h in ("## Paired replay", "## Windows", "## Cost", FENCE, "## Provenance")]
    assert positions == sorted(positions)
    assert "## Replicates" not in markdown


# ---------- PR7: no price, no dollars; no cap, no gate ----------


def test_pr7_with_no_price_cost_json_and_both_renders_report_tokens_and_print_no_dollars(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml")
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    cost = json.loads((out / "cost.json").read_text())
    assert cost["price_per_input_token"] is None and cost["dollars"] is None
    assert cost["input_tokens"] == 6400 and cost["output_tokens"] == 192
    for text in ((out / "report.md").read_text(), plain((out / "receipt.html").read_text())):
        section = text[text.index("Cost"):text.index("Provenance")]
        assert "6400" in section and "192" in section
        assert "no price declared" in section
        assert not re.search(r"dollars\W+(0|0\.0+|\$0)", section), section
        assert "$" not in section
    assert "- price per input token: none" in (out / "report.md").read_text()


def test_pr7_with_no_cap_cap_reached_is_false_and_cap_check_exits_zero(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml")
    out = tmp_path / "paired"
    r = paired_cli(store, decl_path, out, "--cap-check")
    assert r.code == 0, r.err
    block = json.loads(r.out)
    assert block["token_cap"] is None and block["cap_reached"] is False
    assert not out.exists()


# ---------- PR40: each sweep is its own window ----------


def test_pr40_windows_json_has_exactly_one_entry_per_declared_sweep_in_declaration_order(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2", "S3"))
    report = windows_of(store, declaration(sweeps=("S3", "S1", "S2")))
    assert [entry["sweep"] for entry in report.per_sweep] == ["S3", "S1", "S2"]
    for entry in report.per_sweep:
        assert set(entry) == PER_SWEEP_KEYS, set(entry)
    payload = json.loads(report.to_json())
    assert list(payload) == list(WINDOW_REPORT_FIELDS)
    assert [entry["sweep"] for entry in payload["per_sweep"]] == ["S3", "S1", "S2"]


def test_pr40_no_span_is_computed_across_two_sweeps(tmp_path: Path) -> None:
    """S2 runs a day after S1: each sweep's span is its own, and no number anywhere in the
    artifact reaches from one sweep into the other."""
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    report = windows_of(store, declaration(sweeps=("S1", "S2")))
    spans = {entry["sweep"]: entry["realized_span_s"] for entry in report.per_sweep}
    expected = (7 * 2 + 60 + 0.4)  # first a start to last b end: seven items apart, one arm gap, one call
    assert spans["S1"] == pytest.approx(expected) and spans["S2"] == pytest.approx(expected)
    day = 86_400.0
    for path, value in walk(json.loads(report.to_json())):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and path[-1] not in ("first_start_ns", "last_end_ns"):
            assert value < day, (path, value)
    s1, s2 = report.per_sweep
    assert s2["arms"]["a"]["first_start_ns"] - s1["arms"]["a"]["first_start_ns"] == day * NS


# ---------- PR41: the realized span comes from the envelope, never from wall_time ----------


def test_pr41_the_realized_span_is_first_start_in_arm_a_to_last_end_in_arm_b_off_the_envelope(tmp_path: Path) -> None:
    """Named mutant 5. Every record's ``wall_time`` says 0.1 s; the spans say ten minutes."""
    rows = default_rows(4)
    for i, row in enumerate(rows):
        row.start = {"a": EPOCH + i * 30 * NS, "b": EPOCH + 300 * NS + i * 30 * NS}
        row.end = {"a": row.start["a"] + NS, "b": row.start["b"] + 2 * NS}
    rows[3].end["b"] = EPOCH + 600 * NS  # the last response, later than its own start order
    store = make_store(tmp_path, rows)
    (entry,) = windows_of(store, declaration()).per_sweep
    assert entry["timing"] == "available" and entry["reason"] is None
    assert entry["arms"]["a"]["first_start_ns"] == EPOCH
    assert entry["arms"]["b"]["last_end_ns"] == EPOCH + 600 * NS
    assert entry["realized_span_s"] == pytest.approx(600.0)
    assert entry["realized_span_s"] != pytest.approx(0.1 * 8) and entry["realized_span_s"] > 1.0


def test_pr41_a_missing_arm_b_end_is_not_replaced_by_wall_time_or_by_a_start(tmp_path: Path) -> None:
    rows = default_rows(4)
    for row in rows:
        row.end = {"b": None}
        row.wall_time = 123.0
    (entry,) = windows_of(store := make_store(tmp_path, rows), declaration()).per_sweep
    assert entry["timing"] == "unavailable" and entry["realized_span_s"] is None
    assert entry["arms"]["b"]["last_end_ns"] is None
    assert "b" in entry["reason"] and "end" in entry["reason"]
    assert store is not None


def test_pr41_at_k_five_the_span_ends_at_the_last_declared_arm(tmp_path: Path) -> None:
    store = make_store(tmp_path, trows(3, k=5), k=5)
    (entry,) = windows_of(store, declaration(k=5)).per_sweep
    assert set(entry["arms"]) == set(labels(5))
    last = entry["arms"]["5"]["last_end_ns"]
    assert entry["realized_span_s"] == pytest.approx((last - entry["arms"]["a"]["first_start_ns"]) / NS)
    assert entry["realized_span_s"] == pytest.approx(2 * 2 + 4 * 60 + 0.4)


# ---------- PR42: no timestamp means unavailable, named, and nothing else moves ----------


def test_pr42_a_sweep_with_no_response_timestamp_is_unavailable_with_the_reason_and_blocks_nothing(tmp_path: Path) -> None:
    timed = make_store(tmp_path, default_rows(), name="timed")
    rows = default_rows()
    for row in rows:
        row.end = {"a": None, "b": None}
    untimed = make_store(tmp_path, rows, name="untimed")
    decl = declaration(declared_window_s=1200.0)
    (entry,) = windows_of(untimed, decl).per_sweep
    assert entry["timing"] == "unavailable"
    assert isinstance(entry["reason"], str) and entry["reason"]
    assert entry["realized_span_s"] is None and entry["claim"] is None and entry["latency_s"] is None
    assert entry["declared_window_s"] == 1200.0
    for value in leaves({"arms": entry["arms"], "span": entry["realized_span_s"]}):
        assert value is None or value >= EPOCH, value  # a start may be there; nothing reads zero
    assert mask_digest(two_by_two(untimed, decl).contingency_json()) == mask_digest(two_by_two(timed, decl).contingency_json())
    assert mask_digest(two_by_two(untimed, decl).intervals_json()) == mask_digest(two_by_two(timed, decl).intervals_json())
    a = P().assert_pairs(untimed, decl)
    assert len(a.pairs) == 8 and len(a.excluded) == 0


def test_pr42_it_never_yields_a_zero_and_the_gap_is_absent_too(tmp_path: Path) -> None:
    rows = default_rows()
    for row in rows:
        row.end = {"a": None, "b": None}
    report = windows_of(make_store(tmp_path, rows), declaration())
    (entry,) = report.per_sweep
    for path, value in walk(entry):
        assert value != 0 and value != 0.0, path
    assert report.replay_gap[CUT] is not None  # the gap needs starts only, and those are there
    started_late = default_rows()
    store = make_store(tmp_path, started_late, name="starts")
    a = P().assert_pairs(store, declaration())
    a = dataclasses.replace(a, pairs=a.pairs.assign(**{c: None for c in TIMING_COLUMNS}))
    stripped = P().windows(a)
    assert stripped.per_sweep[0]["timing"] == "unavailable"
    assert stripped.replay_gap[CUT] is None


# ---------- PR43: held or withdrawn, and nothing else moves ----------


@pytest.mark.parametrize(("window", "claim"), [(1200.0, "held"), (74.4, "held"), (74.0, "withdrawn"), (None, None)])
def test_pr43_claim_is_held_at_or_under_the_declared_window_and_withdrawn_above_it(tmp_path: Path, window: float | None, claim: str | None) -> None:
    store = make_store(tmp_path, default_rows())
    (entry,) = windows_of(store, declaration(declared_window_s=window)).per_sweep
    assert entry["realized_span_s"] == pytest.approx(74.4)
    assert entry["declared_window_s"] == window and entry["claim"] == claim


def test_pr43_withdrawal_changes_the_description_and_nothing_else(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    held = declaration(sweeps=("S1", "S2"), declared_window_s=1200.0)
    withdrawn = declaration(sweeps=("S1", "S2"), declared_window_s=10.0)
    a_held, a_withdrawn = P().assert_pairs(store, held), P().assert_pairs(store, withdrawn)
    assert a_held.pairs.equals(a_withdrawn.pairs) and a_held.counts == a_withdrawn.counts
    for artifact in ("contingency_json", "intervals_json"):
        assert mask_digest(getattr(P().analyse(a_held), artifact)()) == mask_digest(getattr(P().analyse(a_withdrawn), artifact)())
    w_held, w_withdrawn = P().windows(a_held), P().windows(a_withdrawn)
    assert [e["claim"] for e in w_held.per_sweep] == ["held", "held"]
    assert [e["claim"] for e in w_withdrawn.per_sweep] == ["withdrawn", "withdrawn"]
    assert [e["realized_span_s"] for e in w_held.per_sweep] == [e["realized_span_s"] for e in w_withdrawn.per_sweep]
    assert w_held.replay_gap == w_withdrawn.replay_gap


# ---------- PR44: the replay gap per cut ----------


def test_pr44_the_replay_gap_is_per_cut_min_median_max_of_start_b_minus_start_a_in_seconds(tmp_path: Path) -> None:
    rows = default_rows(5) + trows(3, cut="c50")
    gaps = [30, 90, 45, 60, 75]
    for row, gap in zip(rows[:5], gaps, strict=True):
        row.start = {"a": EPOCH, "b": EPOCH + gap * NS}
    for i, row in enumerate(rows[5:]):
        row.start = {"a": EPOCH + i * NS, "b": EPOCH + i * NS + 5 * NS}
    store = make_store(tmp_path, rows)
    report = windows_of(store, declaration(cuts=((CUT, THRESHOLD, "ge"), ("c50", "0.50", "ge"))))
    assert list(report.replay_gap) == [CUT, "c50"]
    assert report.replay_gap[CUT] == {"min": 30.0, "median": 60.0, "max": 90.0}
    assert report.replay_gap["c50"] == {"min": 5.0, "median": 5.0, "max": 5.0}
    assert json.loads(report.to_json())["replay_gap"] == report.replay_gap


def test_pr44_the_gap_is_over_the_cuts_eligible_pairs_of_every_sweep(tmp_path: Path) -> None:
    rows = default_rows(3)
    later = [dataclasses.replace(r, start={"a": EPOCH + 86_400 * NS, "b": EPOCH + 86_400 * NS + 120 * NS}) for r in rows]
    for row in rows:
        row.start = {"a": EPOCH, "b": EPOCH + 60 * NS}
    broken = dataclasses.replace(later[0], error={"b": "HTTP 500"}, start=dict(later[0].start))
    store = make_store(tmp_path, rows, sweeps=("S1", "S2"), per_sweep={"S2": [broken, *later[1:]]})
    report = windows_of(store, declaration(sweeps=("S1", "S2")))
    assert report.replay_gap[CUT] == {"min": 60.0, "median": 60.0, "max": 120.0}  # 3 at 60, 2 at 120


# ---------- PR45: no pair is dropped on a timing criterion ----------


def test_pr45_a_pair_replayed_ten_days_later_is_still_a_pair(tmp_path: Path) -> None:
    """Named mutant 6: filtering pairs on the replay gap."""
    rows = default_rows()
    rows[1].start = {"a": EPOCH, "b": EPOCH + 10 * 86_400 * NS}
    store = make_store(tmp_path, rows)
    decl = declaration(declared_window_s=1200.0)
    a = P().assert_pairs(store, decl)
    assert len(a.pairs) == 8 and len(a.excluded) == 0
    assert a.counts["by_cut"][CUT]["eligible"] == 8
    report = P().windows(a)
    assert report.replay_gap[CUT]["max"] == pytest.approx(10 * 86_400.0)
    assert report.per_sweep[0]["claim"] == "withdrawn"
    cut = {c.name: c for c in P().analyse(a).cuts}[CUT]
    assert cut.per_sweep[0]["n"] == 8 and cut.per_sweep[0]["n10"] == 3


_PR45: dict[str, Any] = {}


def pr45_assertion() -> Any:
    """One stored two-sweep assertion, built once for the property test (a function-scoped
    fixture cannot serve a hypothesis test)."""
    if "a" not in _PR45:
        root = Path(tempfile.mkdtemp(prefix="pr45-"))
        store = make_store(root, default_rows(), sweeps=("S1", "S2"))
        decl = declaration(sweeps=("S1", "S2"), declared_window_s=1200.0)
        _PR45["a"] = P().assert_pairs(store, decl)
    return _PR45["a"]


@settings(max_examples=40, deadline=None, derandomize=True)
@given(deleted=st.frozensets(st.sampled_from(TIMING_COLUMNS)))
def test_pr45_property_deleting_timestamps_moves_windows_json_and_nothing_else(deleted: frozenset[str]) -> None:
    """Nulling any subset of the timing columns changes no count, no table and no interval;
    only the windows artifact can move, and it does whenever anything was deleted."""
    a = pr45_assertion()
    stripped = dataclasses.replace(a, pairs=a.pairs.assign(**{c: None for c in deleted}))
    full, without = P().analyse(a), P().analyse(stripped)
    assert full.contingency_json() == without.contingency_json()
    assert full.intervals_json() == without.intervals_json()
    assert a.counts == stripped.counts and len(a.pairs) == len(stripped.pairs)
    w_full, w_without = P().windows(a), P().windows(stripped)
    if deleted:
        assert w_full.to_json() != w_without.to_json()
    else:
        assert w_full.to_json() == w_without.to_json()


# ---------- PR46: a timing artifact and nothing else ----------


def test_pr46_windows_json_carries_no_rate_no_flip_count_and_no_interval(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    payload = json.loads(windows_of(store, declaration(sweeps=("S1", "S2"), declared_window_s=100.0)).to_json())
    for path, _ in walk(payload):
        for key in path:
            low = key.lower()
            assert not any(word in low for word in ("rate", "flip", "interval", "estimate", "basis", "n11", "n10", "n01", "n00", "outcome", "bootstrap")), path
            assert low not in ("lo", "hi", "p"), path


# ---------- PR47: input tokens are the provider's recorded usage ----------


def test_pr47_input_tokens_are_span_tokens_in_summed_per_phase_per_sweep_and_per_arm(tmp_path: Path) -> None:
    rows = default_rows(4)
    for i, row in enumerate(rows):
        row.tokens = {"a": {"in": 100 + i, "out": 10}, "b": {"in": 200 + i, "out": 20}}
    store = make_store(tmp_path, rows, sweeps=("S1", "S2"))
    decl = declaration(sweeps=("S1", "S2"))
    report = P().cost(store, decl, phases={"S1": ("S1-a", "S1-b"), "S2": ("S2-a", "S2-b")})
    by_run = {entry["run_id"]: entry for entry in report.phases}
    assert [entry["run_id"] for entry in report.phases] == ["S1-a", "S1-b", "S2-a", "S2-b"]
    assert set(by_run["S1-a"]) == PHASE_KEYS
    assert (by_run["S1-a"]["phase"], by_run["S1-a"]["sweep"], by_run["S1-a"]["arm"]) == ("S1", "S1", "a")
    assert (by_run["S2-b"]["phase"], by_run["S2-b"]["sweep"], by_run["S2-b"]["arm"]) == ("S2", "S2", "b")
    assert by_run["S1-a"]["input_tokens"] == 100 + 101 + 102 + 103
    assert by_run["S1-b"]["input_tokens"] == 200 + 201 + 202 + 203
    assert report.input_tokens == 2 * (406 + 806) and report.output_tokens == 2 * (40 + 80)
    assert report.recorded_spans == 16 and report.unrecorded_spans == 0


def test_pr47_a_retry_span_is_paid_for_and_an_errored_episode_records_nothing(tmp_path: Path) -> None:
    rows = default_rows(3)
    rows[0].n_spans = {"a": 3}
    rows[1].error = {"b": "HTTP 500"}
    store = make_store(tmp_path, rows)
    report = P().cost(store, declaration(), phases={"S1": ("S1-a", "S1-b")})
    assert report.recorded_spans == 3 + 2 + 2  # three spans in a for item 0; no span in b for item 1
    assert report.input_tokens == 7 * 400


def test_pr47_the_module_holds_no_tokeniser_and_no_rate_card() -> None:
    source = Path(P().__file__).read_text(encoding="utf-8")
    for word in ("tiktoken", "encoding_for_model", "transformers", "per_1k", "per_million", "usd_per"):
        assert word not in source, word
    assert not re.search(r"\$\s*\d", source)
    assert "price_per_input_token" in source


# ---------- PR48: output tokens with or without a price ----------


def test_pr48_output_tokens_are_totalled_with_or_without_a_price(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    without = P().cost(store, declaration(), phases={"S1": ("S1-a", "S1-b")})
    priced = P().cost(store, declaration(price_per_input_token=Decimal("0.000001")), phases={"S1": ("S1-a", "S1-b")})
    assert without.output_tokens == priced.output_tokens == 16 * 12
    assert without.dollars is None and priced.dollars is not None


# ---------- PR49: dollars are tokens times the price, the price echoed ----------


def test_pr49_dollars_are_input_tokens_times_the_price_with_the_price_echoed_in_cost_json_report_and_receipt(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    price = "0.000000042"
    decl_path = write_declaration(tmp_path / "decl.toml", top={"price_per_input_token": price})
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    cost = json.loads((out / "cost.json").read_text())
    assert cost["input_tokens"] == 6400
    assert cost["price_per_input_token"] == price  # the literal, never str(Decimal)'s 4.2E-8
    assert cost["dollars"] == format(Decimal(6400) * Decimal(price), "f")
    assert Decimal(cost["dollars"]) == Decimal("0.0002688")
    markdown = (out / "report.md").read_text()
    receipt = plain((out / "receipt.html").read_text())
    for text in (markdown, receipt):
        section = text[text.index("Cost"):text.index("Provenance")]
        assert price in section and cost["dollars"] in section
    assert f"- price per input token: {price}" in markdown
    library = P().cost(store, P().Declaration.from_toml(decl_path), phases={"S1": ("S1-a", "S1-b")})
    assert isinstance(library.dollars, Decimal) and library.dollars == Decimal("0.0002688")
    assert isinstance(library.price_per_input_token, Decimal)


# ---------- PR50: a span with no usage is counted, never zero ----------


def test_pr50_a_span_with_no_recorded_usage_is_counted_under_unrecorded_spans_and_never_as_zero(tmp_path: Path) -> None:
    """Named mutant 7."""
    rows = default_rows(4)
    rows[0].tokens = {"a": None}
    rows[1].tokens = {"b": {"out": 5}}  # output but no input: unrecorded for the input total
    rows[2].tokens = {"a": {}, "b": None}
    store = make_store(tmp_path, rows)
    report = P().cost(store, declaration(), phases={"S1": ("S1-a", "S1-b")})
    assert report.unrecorded_spans == 4 and report.recorded_spans == 4
    assert report.input_tokens == 4 * 400
    assert report.output_tokens == 4 * 12 + 5
    by_run = {entry["run_id"]: entry for entry in report.phases}
    assert (by_run["S1-a"]["recorded_spans"], by_run["S1-a"]["unrecorded_spans"]) == (2, 2)
    assert (by_run["S1-b"]["recorded_spans"], by_run["S1-b"]["unrecorded_spans"]) == (2, 2)
    payload = json.loads(report.to_json())
    assert list(payload) == list(COST_REPORT_FIELDS)
    assert payload["unrecorded_spans"] == 4


def test_pr50_a_total_over_spans_that_recorded_nothing_is_reported_as_what_it_is(tmp_path: Path) -> None:
    rows = default_rows(4)
    for row in rows:
        row.tokens = {"a": None, "b": None}
    store = make_store(tmp_path, rows)
    decl_path = write_declaration(tmp_path / "decl.toml", top={"price_per_input_token": "0.000001"})
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    cost = json.loads((out / "cost.json").read_text())
    assert (cost["input_tokens"], cost["recorded_spans"], cost["unrecorded_spans"]) == (0, 0, 8)
    assert cost["dollars"] == "0E-6" or Decimal(cost["dollars"]) == 0
    section = (out / "report.md").read_text()
    section = section[section.index("## Cost"):section.index(FENCE)]
    assert "unrecorded spans" in section and re.search(r"unrecorded spans\D*8\b", section)
    assert re.search(r"recorded spans\D*0\b", section)


# ---------- PR51: the cap, between sweeps ----------


@pytest.mark.parametrize(("cap", "reached"), [(6400, True), (6399, True), (6401, False), (1, True)])
def test_pr51_cap_reached_is_cumulative_input_tokens_at_or_above_the_declared_cap(tmp_path: Path, cap: int, reached: bool) -> None:
    store = make_store(tmp_path, default_rows())
    report = P().cost(store, declaration(token_cap=cap), phases={"S1": ("S1-a", "S1-b")})
    assert report.input_tokens == 6400 and report.token_cap == cap and report.cap_reached is reached


@pytest.mark.parametrize(("cap", "code"), [(6400, 1), (6401, 0)])
def test_pr51_cap_check_prints_the_cost_block_writes_nothing_and_exits_one_at_the_cap(tmp_path: Path, cap: int, code: int) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml", top={"token_cap": str(cap)})
    out = tmp_path / "paired"
    r = paired_cli(store, decl_path, out, "--cap-check")
    assert r.code == code, r.err
    block = json.loads(r.out)
    assert block["cap_reached"] is (code == 1) and block["input_tokens"] == 6400
    assert list(block)[0] == "declaration_digest"
    assert not out.exists()


def test_pr51_the_cap_is_over_completed_runs_and_a_later_sweep_adds_to_it(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    one = P().cost(store, declaration(sweeps=("S1", "S2"), token_cap=7000), phases={"S1": ("S1-a", "S1-b")})
    both = P().cost(store, declaration(sweeps=("S1", "S2"), token_cap=7000), phases={"S1": ("S1-a", "S1-b"), "S2": ("S2-a", "S2-b")})
    assert (one.input_tokens, one.cap_reached) == (6400, False)
    assert (both.input_tokens, both.cap_reached) == (12800, True)


def test_pr51_the_executor_is_untouched_by_the_cap() -> None:
    """Green before and after: the cap is analysis-side (ruled 2026-09-21) and neither executor
    knows the word."""
    for name in ("executor.py", "executor_modal.py"):
        source = (Path(P().__file__).parent / name).read_text(encoding="utf-8")
        assert "token_cap" not in source and "cap_reached" not in source, name


# ---------- PR52: the cost block reconciles ----------


def test_pr52_the_sum_over_phases_equals_the_study_total_and_each_run_is_in_exactly_one_phase(tmp_path: Path) -> None:
    rows = default_rows(4)
    rows[1].tokens = {"a": None}
    store = make_store(tmp_path, rows, sweeps=("S1", "S2"), extra_runs={"calib-1": default_rows(6)})
    decl = declaration(sweeps=("S1", "S2"), price_per_input_token=Decimal("0.000001"))
    phases = {"calibration": ("calib-1",), "S1": ("S1-a", "S1-b"), "S2": ("S2-a", "S2-b")}
    report = P().cost(store, decl, phases=phases)
    assert [e["run_id"] for e in report.phases] == ["calib-1", "S1-a", "S1-b", "S2-a", "S2-b"]
    calib = report.phases[0]
    assert (calib["phase"], calib["sweep"], calib["arm"]) == ("calibration", None, None)
    for key in ("input_tokens", "output_tokens", "recorded_spans", "unrecorded_spans"):
        assert sum(e[key] for e in report.phases) == getattr(report, key), key
    assert report.recorded_spans == 2 * 7 + 6 and report.unrecorded_spans == 2  # one unrecorded span per sweep
    with pytest.raises(P().PairedError):
        P().cost(store, decl, phases={"S1": ("S1-a", "S1-b"), "again": ("S1-a",)})


def test_pr52_the_cli_phases_are_the_declared_sweeps(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    decl_path = write_declaration(tmp_path / "decl.toml", sweeps=("S1", "S2"))
    out = tmp_path / "paired"
    assert paired_cli(store, decl_path, out).code == 0
    cost = json.loads((out / "cost.json").read_text())
    assert [(e["phase"], e["run_id"]) for e in cost["phases"]] == [("S1", "S1-a"), ("S1", "S1-b"), ("S2", "S2-a"), ("S2", "S2-b")]
    assert cost["input_tokens"] == 12800


# ---------- PR53: without --paired, today's bytes ----------


def test_pr53_a_report_without_paired_is_byte_identical_to_todays(tmp_path: Path) -> None:
    """Green before and after: W20's three digests through the CLI on the Go1 fixture."""
    out = tmp_path / "go1"
    r = run_cli(["--store", str(GO1_ROOT), *E14_ARGV, "--out", str(out)])
    assert r.code == 0, r.err
    assert sorted(p.name for p in out.iterdir()) == sorted(REPORT_FILES)
    for name, digest in E14_SHA256.items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest, name


def test_pr53_report_py_is_not_touched_by_phase_three() -> None:
    """Green before and after: the paired sections are folded into the rendered strings, and the
    renderer's whole-file digest is the one two frozen tests carry."""
    source = (Path(P().__file__).parent / "report.py").read_bytes()
    assert hashlib.sha256(source).hexdigest() == REPORT_PY_SHA256


def test_pr53_without_the_flag_no_paired_section_and_no_artifact_exists_and_the_flag_needs_a_value(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    out = tmp_path / "plain"
    r = report_cli(store, "S1-a", "S1-b", out)
    assert r.code == 0, r.err
    assert sorted(p.name for p in out.iterdir()) == sorted(REPORT_FILES)
    markdown = (out / "report.md").read_text()
    receipt = (out / "receipt.html").read_text()
    for heading in SECTIONS:
        assert heading not in markdown and f"<h2>{heading[3:]}</h2>" not in receipt
    assert "declaration digest" not in markdown and "artifacts" not in markdown
    r = report_cli(store, "S1-a", "S1-b", tmp_path / "bad", "--paired")
    assert r.code == 2 and "Traceback" not in r.err


# ---------- PR54: the renderer formats, it does not compute ----------


def test_pr54_every_number_printed_in_the_paired_sections_is_in_an_artifact_with_the_same_value(tmp_path: Path) -> None:
    rows = default_rows(12) + trows(6, cut="c50", pattern=lambda i: (1, 0) if i % 2 else (0, 0))
    store = make_store(tmp_path, rows, sweeps=("S1", "S2"))
    decl_path = write_declaration(
        tmp_path / "decl.toml", cuts=((CUT, THRESHOLD, "ge"), ("c50", "0.50", "gt")), sweeps=("S1", "S2"),
        top={"price_per_input_token": "0.000000042", "token_cap": "100000", "floor": "0.01",
             "declared_window_s": "90.5", "conditioning": '"items picked to sit beside the cut"'},
    )
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--y", "cut", "--paired", str(decl_path)).code == 0
    artifacts = artifacts_of(out)
    markdown = sections_of((out / "report.md").read_text())
    seen_md = assert_every_number_is_in_the_artifacts(markdown, artifacts)
    receipt = plain(html_sections_of((out / "receipt.html").read_text()))
    seen_html = assert_every_number_is_in_the_artifacts(receipt, artifacts)
    assert seen_md > 40 and seen_html > 40, (seen_md, seen_html)
    intervals = artifacts["intervals_by_cut.json"]["cuts"][CUT]
    for value in (intervals["flip_rate"]["lo"], intervals["flip_rate"]["hi"], intervals["net_swing"]["estimate"]):
        assert json.dumps(value) in markdown and json.dumps(value) in receipt


def test_pr54_the_provenance_block_names_the_six_facts_and_the_artifact_files(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml", top={"price_per_input_token": "0.000000042"})
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    decl = P().Declaration.from_toml(decl_path)
    cost = json.loads((out / "cost.json").read_text())
    markdown = (out / "report.md").read_text()
    provenance = markdown[markdown.index("## Provenance"):]
    expected = [
        f"- declaration digest: {decl.digest}",
        f"- bootstrap seed: {SEED}",
        f"- bootstrap b: {B_SMALL}",
        "- price per input token: 0.000000042",
        f"- input tokens: {cost['input_tokens']}",
        f"- output tokens: {cost['output_tokens']}",
        "- artifacts: " + ", ".join(FIVE),
    ]
    for line in expected:
        assert line in provenance, line
    assert SIXTH not in provenance
    receipt = plain((out / "receipt.html").read_text())
    for line in expected:
        assert line[2:] in receipt, line


# ---------- PR55: structure, not judgement ----------


def test_pr55_the_rendered_sections_print_no_verdict_word(tmp_path: Path) -> None:
    rows = default_rows(20)  # three flips of twenty: outcome C under a floor, B without it
    store = make_store(tmp_path, rows, sweeps=("S1", "S2"))
    decl_path = write_declaration(tmp_path / "decl.toml", sweeps=("S1", "S2"), top={"floor": "0.01", "declared_window_s": "10.0"})
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    markdown = sections_of((out / "report.md").read_text())
    receipt = plain(html_sections_of((out / "receipt.html").read_text()))
    for text in (markdown, receipt):
        low = text.lower()
        for word in VERDICT_WORDS:
            assert not re.search(rf"\b{word}", low), (word, text[:300])
        assert "withdrawn" in low and "arm order check" in low
        for line in text.splitlines():
            if "arm order check" in line.lower():
                assert "reproducib" not in line.lower()


def test_pr55_conditioning_is_printed_verbatim_beside_every_rate_and_nothing_stands_in_for_it(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    sentence = "items picked to sit beside the cut, not a production mix"
    with_it = write_declaration(tmp_path / "with.toml", sweeps=("S1", "S2"), top={"conditioning": json.dumps(sentence)})
    without = write_declaration(tmp_path / "without.toml", sweeps=("S1", "S2"))
    out_with, out_without = tmp_path / "with", tmp_path / "without"
    assert report_cli(store, "S1-a", "S1-b", out_with, "--paired", str(with_it)).code == 0
    assert report_cli(store, "S1-a", "S1-b", out_without, "--paired", str(without)).code == 0
    md_with = sections_of((out_with / "report.md").read_text())
    md_without = sections_of((out_without / "report.md").read_text())
    rate_lines = [line for line in md_with.splitlines() if "flip rate" in line.lower()]
    assert rate_lines and all(sentence in line for line in rate_lines), rate_lines
    assert "conditioning" not in md_without.lower()
    bare_rate_lines = [line for line in md_without.splitlines() if "flip rate" in line.lower()]
    assert len(bare_rate_lines) == len(rate_lines)
    for line in bare_rate_lines:
        assert not any(phrase in line.lower() for phrase in ("not declared", "none declared", "no conditioning", "n/a")), line
    receipt_with = plain(html_sections_of((out_with / "receipt.html").read_text()))
    assert sentence in receipt_with


# ---------- PR77: the Replicates section ----------


def replicate_rows() -> list[TRow]:
    def pattern(i: int) -> tuple[int, ...]:
        return ((1, 1, 1, 1, 1), (1, 0, 1, 1, 0), (0, 0, 1, 0, 0), (1, 1, 0, 1, 1))[i % 4]
    return trows(12, k=5, pattern=pattern)


def test_pr77_at_k_five_the_replicates_section_sits_between_paired_replay_and_windows_and_prints_no_verdict(tmp_path: Path) -> None:
    store = make_store(tmp_path, replicate_rows(), k=5, sweeps=("S1", "S2", "S3"))
    decl_path = write_declaration(tmp_path / "decl.toml", k=5, sweeps=("S1", "S2", "S3"), top={"conditioning": '"near-cut items"', "price_per_input_token": "0.000000042"})
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    assert sorted(p.name for p in out.iterdir()) == sorted((*REPORT_FILES, *FIVE, SIXTH))
    markdown = (out / "report.md").read_text()
    positions = [markdown.index(h) for h in ("## Paired replay", "## Replicates", "## Windows", "## Cost", FENCE)]
    assert positions == sorted(positions)
    receipt = (out / "receipt.html").read_text()
    html_positions = [receipt.index(f"<h2>{h[3:]}</h2>") for h in SECTIONS] + [receipt.index("<blockquote>")]
    assert html_positions == sorted(html_positions)
    section = markdown[markdown.index("## Replicates"):markdown.index("## Windows")]
    low = section.lower()
    for word in ("stable", "unstable", "reliab", "trustworth", "reproducib", "pass", "fail"):
        assert not re.search(rf"\b{word}", low), word
    assert "decisions agreed" in low and "agree@" in low and "ms@" in low
    assert "near-cut items" in section
    assert "out of 10,000" in low
    provenance = markdown[markdown.index("## Provenance"):]
    assert "- artifacts: " + ", ".join((*FIVE, SIXTH)) in provenance


def test_pr77_every_number_in_the_replicates_section_is_in_replicates_by_cut_json(tmp_path: Path) -> None:
    store = make_store(tmp_path, replicate_rows(), k=5, sweeps=("S1", "S2", "S3"))
    decl_path = write_declaration(tmp_path / "decl.toml", k=5, sweeps=("S1", "S2", "S3"), top={"conditioning": '"near-cut items"', "price_per_input_token": "0.000000042"})
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    sixth = json.loads((out / SIXTH).read_text())
    assert list(sixth) == ["declaration_digest", "cuts"] and list(sixth["cuts"]) == [CUT]
    block = sixth["cuts"][CUT]
    assert block["k"] == 5 and list(block["agree"]) == ["primary", "sensitivity"]
    markdown = (out / "report.md").read_text()
    section = markdown[markdown.index("## Replicates"):markdown.index("## Windows")]
    seen = assert_every_number_is_in_the_artifacts(section, {SIXTH: sixth})
    assert seen > 30
    receipt = (out / "receipt.html").read_text()
    html_section = plain(receipt[receipt.index("<h2>Replicates</h2>"):receipt.index("<h2>Windows</h2>")])
    assert assert_every_number_is_in_the_artifacts(html_section, {SIXTH: sixth}) > 30
    for key in ("j2", "j5"):
        assert json.dumps(block["agree"]["primary"][key]["estimate"]) in section
    assert json.dumps(block["cost_framing"]["primary"]["j3"]["per_10000"]["n"]) in section


def test_pr77_at_k_two_no_replicates_section_and_no_sixth_artifact_exists(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml")
    out = tmp_path / "report"
    assert report_cli(store, "S1-a", "S1-b", out, "--paired", str(decl_path)).code == 0
    assert not (out / SIXTH).exists()
    markdown = (out / "report.md").read_text()
    assert "## Replicates" not in markdown and "agree@" not in markdown.lower()
    r = paired_cli(store, decl_path, tmp_path / "json", "--format", "json")
    assert r.code == 0 and SIXTH[:-5] not in json.loads(r.out)


# ---------- the CLI: the verb and the flag ----------


def test_cli_paired_format_json_prints_the_combined_payload_and_writes_nothing(tmp_path: Path) -> None:
    store = make_store(tmp_path, replicate_rows(), k=5, sweeps=("S1", "S2"))
    decl_path = write_declaration(tmp_path / "decl.toml", k=5, sweeps=("S1", "S2"))
    out = tmp_path / "paired"
    r = paired_cli(store, decl_path, out, "--format", "json")
    assert r.code == 0, r.err
    payload = json.loads(r.out)
    assert list(payload) == ["pair_assertion", "contingency_by_cut", "intervals_by_cut", "windows", "cost", "replicates_by_cut"]
    assert not out.exists()
    digest = P().Declaration.from_toml(decl_path).digest
    for key, tree in payload.items():
        assert tree["declaration_digest"] == digest, key
    written = paired_cli(store, decl_path, out)
    assert written.code == 0
    for key, name in zip(payload, (*FIVE, SIXTH), strict=True):
        assert json.loads((out / name).read_text()) == payload[key], name


def test_cli_report_paired_refuses_a_pair_that_is_not_a_declared_sweep_by_name(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows(), sweeps=("S1", "S2"))
    decl_path = write_declaration(tmp_path / "decl.toml", sweeps=("S1", "S2"))
    r = report_cli(store, "S1-a", "S2-b", tmp_path / "x", "--paired", str(decl_path))
    assert r.code == 2 and "Traceback" not in r.err
    assert "S1-a" in r.err and "S2-b" in r.err
    assert not (tmp_path / "x").exists()
    r = report_cli(store, "S1-b", "S1-a", tmp_path / "y", "--paired", str(decl_path))
    assert r.code == 2, r.err
    r = report_cli(store, "S2-a", "S2-b", tmp_path / "z", "--paired", str(decl_path))
    assert r.code == 0, r.err
    markdown = (tmp_path / "z" / "report.md").read_text()
    assert "S1" in sections_of(markdown) and "S2" in sections_of(markdown)  # every sweep is covered


def test_cli_a_declaration_error_and_a_not_assertable_run_are_clean_refusals(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    bad = tmp_path / "bad.toml"
    bad.write_text(write_declaration(tmp_path / "ok.toml").read_text().replace('comparison = "ge"', 'comparison = "ge"\ninclusive = true'))
    r = paired_cli(store, bad, tmp_path / "out")
    assert r.code == 2 and "Traceback" not in r.err and "inclusive" in r.err
    asserted = write_declaration(tmp_path / "asserted.toml", top={"headers": '"asserted"'})
    r = paired_cli(store, asserted, tmp_path / "out2")
    assert r.code == 2 and "Traceback" not in r.err and "header" in r.err.lower()
    assert not (tmp_path / "out").exists() and not (tmp_path / "out2").exists()


def test_cli_paired_refuses_a_non_empty_out_dir_without_force_and_names_a_default(tmp_path: Path) -> None:
    store = make_store(tmp_path, default_rows())
    decl_path = write_declaration(tmp_path / "decl.toml")
    out = tmp_path / "paired"
    assert paired_cli(store, decl_path, out).code == 0
    r = paired_cli(store, decl_path, out)
    assert r.code == 2 and "--force" in r.err
    assert paired_cli(store, decl_path, out, "--force").code == 0
    r = run_cli(["--store", str(root_of(store)), "paired", "--declaration", str(decl_path), "--format", "json"])
    assert r.code == 0 and "declaration_digest" in r.out


# ---------- the structure: section 2's names and fields ----------


def test_structure_window_report_and_cost_report_are_section_twos_fields_and_the_two_functions_take_what_section_two_says() -> None:
    module = P()
    assert tuple(f.name for f in dataclasses.fields(module.WindowReport)) == WINDOW_REPORT_FIELDS
    assert tuple(f.name for f in dataclasses.fields(module.CostReport)) == COST_REPORT_FIELDS
    for cls in (module.WindowReport, module.CostReport):
        assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen
        assert typing.get_type_hints(cls.to_json)["return"] is str
    hints = typing.get_type_hints(module.windows)
    assert list(hints) == ["assertion", "return"] and hints["assertion"] is module.PairAssertion
    assert hints["return"] is module.WindowReport
    signature = inspect.signature(module.cost)
    assert list(signature.parameters) == ["store", "declaration", "phases"]
    assert signature.parameters["phases"].kind is inspect.Parameter.KEYWORD_ONLY
    cost_hints = typing.get_type_hints(module.cost)
    assert cost_hints["store"] is Store and cost_hints["declaration"] is module.Declaration
    assert cost_hints["return"] is module.CostReport
    public = {
        name for name, value in vars(module).items()
        if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
    }
    assert {"WindowReport", "windows", "CostReport", "cost"} <= public


def test_structure_timing_rides_on_pairs_after_the_values_in_arm_order(tmp_path: Path) -> None:
    store = make_store(tmp_path, trows(2, k=3), k=3)
    a = P().assert_pairs(store, declaration(k=3))
    columns = list(a.pairs.columns)
    assert columns[-6:] == ["start_ns_a", "end_ns_a", "start_ns_b", "end_ns_b", "start_ns_3", "end_ns_3"]
    assert columns.index("value_3") < columns.index("start_ns_a")
    row = a.pairs.iloc[0]
    assert int(row["start_ns_a"]) == EPOCH and int(row["end_ns_a"]) == EPOCH + DURATION_NS
    assert int(row["start_ns_b"]) == EPOCH + 60 * NS and int(row["start_ns_3"]) == EPOCH + 120 * NS
    latency = P().windows(a).per_sweep[0]["latency_s"]
    assert latency == {"median": pytest.approx(0.4), "n": 6}


def test_structure_the_latency_is_the_median_over_every_arms_recorded_calls_and_absent_with_none(tmp_path: Path) -> None:
    rows = default_rows(4)
    for i, row in enumerate(rows):
        row.end = {"a": default_start(i, "a", 0) + (i + 1) * NS, "b": default_start(i, "b", 0) + 10 * NS}
    store = make_store(tmp_path, rows)
    (entry,) = windows_of(store, declaration()).per_sweep
    assert entry["latency_s"] == {"median": pytest.approx(float(np.median([1, 2, 3, 4, 10, 10, 10, 10]))), "n": 8}
    for row in rows:
        row.end = {"a": None, "b": None}
    (entry,) = windows_of(make_store(tmp_path, rows, name="none"), declaration()).per_sweep
    assert entry["latency_s"] is None
