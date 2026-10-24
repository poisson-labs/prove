"""Truncation-surfacing oracle: what the report, the receipt, the viewer and ``inspect`` say about a cut.

Frozen 2026-09-20 off ``95471ba``, after the retrofit commit. The build is written against this
file and does not edit it. The dispatch was "Proofload Truncation Surfacing" (CAP3's recommendation
3: fix the surfacing first and separately from the cap). Nothing here changes the cap or its
default, and Z13 pins that.

**What is being fixed, measured at ``95471ba``.** Two different things are called ``truncated``.
``build_report`` and ``build_multi_report`` put ``diff.truncated`` into the provenance dict, and
that is the count of episodes re-censored at the common horizon (``diff._truncate``: rows with
``t > horizon``). ``report.md``, ``receipt.html`` and the viewer page print it as ``truncated: N``,
which reads as a statement about the observation cut and is not one. ``go1-report.md:45`` and
``go1-receipt.html`` both read ``truncated: 0`` over runs that dropped a third of their
observation values. Nothing on any surface says a value was cut, how many, or at what limit, and
``inspect`` says outright that it prints none of it (``cli.py:1628``).

**What a surface says now** (the names are this file's; the dispatch left them to the build):

| provenance key (pair; the single-run form has no ``_a``/``_b``) | rendered as | from |
|---|---|---|
| ``episodes_censored_at_horizon`` | ``episodes censored at horizon: N`` | ``diff.truncated``, same value, same slot |
| ``observation_cap_a`` / ``_b`` | ``observation cap a: max_observation_bytes=8192`` | the manifest's ``environment["capture"]``: every entry whose key ends ``_bytes``, verbatim, or ``None`` = ``not recorded`` |
| ``trace_spans_a`` / ``_b`` | ``trace spans a: N`` | the run's stored envelopes, counted; ``None`` = ``not counted`` |
| ``observation_cut_spans_a`` / ``_b`` | ``observation cut spans a: N`` | the spans among them stamped ``truncated == "observation"``; ``None`` = ``not counted`` |

The unit is the span and the read is the envelope alone (spec A6 section 3.10: A9 counts
``truncated`` per kind from the envelope column and nothing reads ``trace_obs``). A count is
``None``, never ``0``, for a run whose capture record carries a byte limit under any name but
``max_observation_bytes``: that run was written before the per-value cut, its spans carry no stamp
to count, and a ``0`` there is the lie this packet exists to remove. The reader names no retired
identifier -- A8b's P8-27 bans them from ``src/`` -- it echoes whichever ``*_bytes`` entry the run's
own build recorded, so a pre-A8b run's ``max_span_bytes`` reads as itself.

**Invariant-to-test map** (Z-numbers are this file's; 55 collected ids, and the counts below sum to 55):

| Invariant | Tests |
|---|---|
| Z1 the horizon count is named for what it counts, on every surface | ``test_z1_*`` (2 ids) |
| Z2 the diff layer keeps ``truncated`` and its meaning | ``test_z2_*`` (1) |
| Z3 the cap is on every surface, verbatim, and its absence says so | ``test_z3_*`` (10) |
| Z4 the count is what was cut, from real stored traces | ``test_z4_*`` (6) |
| Z5 a real zero stays a zero | ``test_z5_*`` (3) |
| Z6 an uncountable run is never a zero | ``test_z6_*`` (5) |
| Z7 a run with no capture record is counted, and its cap is not recorded | ``test_z7_*`` (6) |
| Z8 the count reads the envelope and nothing else | ``test_z8_*`` (2) |
| Z9 nothing is backfilled: no stored byte moves | ``test_z9_*`` (1) |
| Z10 the single-run report says the same things | ``test_z10_*`` (2) |
| Z11 the payload's version and its ``diff`` key set | ``test_z11_*`` (3) |
| Z12 ``inspect`` prints the cut | ``test_z12_*`` (4) |
| Z13 the cap, its default and the stored field names are untouched | ``test_z13_*`` (2) |
| Z14 the builders' interface | ``test_z14_*`` (4) |
| Z15 the Go1 pair, the published shape | ``test_z15_*`` (4) |

**Real frames, round-tripped.** Every store here is written by ``Store.append`` from traces cut by
``truncate_observations``, and read back by the CLI, never hand-built (standing rule 14). Seven
runs: ``cut-a`` (cap 64, spans cut), ``cut-b`` (cap 4096, nothing over it), ``legacy`` (a capture
record carrying ``max_span_bytes``, its envelopes rewritten to the shape a build before A8a stored),
``bare`` (no capture record, no trace), ``own`` (no capture record, a trace the default cut bounded)
and ``hz10`` / ``hz5`` (horizons 10 and 5, so 24 episodes are re-censored). The legacy shape is made by
rewriting the ``trace`` column of a written part -- no alias map, thirteen span keys, no stamp --
because ``Store.append`` refuses to write that shape and a fixture that was not the shape would prove
nothing about it; Z6's first test asserts the fixture is what it claims. The expected counts are
arithmetic on the fixture's own span sizes and never a read of a stamp.

**Green before and after -- seven of the 55 ids**, named so their green is not read as coverage (the
other 48 are red on the bare tree): Z2 (the diff layer is not touched), Z6's fixture precondition, Z9
(``report``, ``serve`` and ``inspect`` write nothing on the bare tree either), the ``TOP_LEVEL_KEYS``
test of Z11, the no-cut-and-nine-columns test of Z12, and both tests of Z13.

**Named gaps, not pinned.** (1) ``inspect`` cannot open a run stored before A8a: ``Store.read`` with the
full trace raises ``TraceValidationError`` on the missing ``alias_map_version`` (measured on all four
post-A7 runs in ``proofload-runs``, and the pre-A7 golden-pilot runs read as having no trace); Z9's
``inspect`` loop leaves the ``legacy`` run out on purpose, and no test here asserts the defect. (2)
``diff`` and ``check`` still say ``truncated=N`` for the horizon count (``diff.py``, byte-fenced by A28
and FR); Z2 pins that the layer keeps its name, not that it should. (3) A pre-A8b marker is not read: A8b's
P8-27 bans its text and its name from ``src/``, so a run written before A8b reads ``not counted``, and
what its values would give is a measurement, filed beside this packet, not a surface. (4) The unit is
the span, as A6 section 3.10 counts it; a count of values would need the bodies, which Z8 forbids.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import poisson_prove.cli as cli
from poisson_prove.diff import DiffResult, MultiDiffResult, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import Span, Trace, truncate_observations
from poisson_prove.viewer import SCHEMA, ViewerError, render_html

#: CD (D8) renames ``OBSERVATION_LIMIT_BYTES`` to ``OBSERVATION_ROUTING_BYTES`` and takes away its
#: second job: it is the size at which ``split`` moves an unnamed attribute to ``trace_obs``, and
#: never a cap. The two fixtures below that used it as a *cut* limit now name their own number --
#: which is what they always meant, and is the value that constant still holds.
OWN_RUN_CUT_AT = 8192

REPO = Path(__file__).resolve().parent.parent
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"

# LS retrofit, 2026-09-22 (local serve pass, Phase A): /5 retires with the ``summary`` key.
NEW_SCHEMA = "poisson-prove.viewpair/7"
EPOCH = 1_756_900_000_000_000_000
TASKS = ("t0", "t1", "t2", "t3")
REPLICATES = 8
EVENT_T = 3.0
#: One small and one big observation value, in bytes. ``BIG`` is over 64 and under 4096; ``OWN_BIG``
#: is over the module default.
SMALL, BIG, OWN_BIG = 10, 300, 9000
KNOBS = ["--permutations", "50", "--seed", "0"]
GO1_KNOBS = ["--permutations", "300", "--seed", "0"]

#: The pair provenance keys the CLI's structure carries, in order: the horizon count in
#: ``truncated``'s old slot, and the run-identity block followed by the observation block.
PAIR_KEYS_CLI = (
    "events", "inferred", "non_event", "n_tests", "method", "seed_identity_match", "unpaired_analysis",
    "q", "t_unit", "horizon", "n_not_comparable", "dropped_a", "dropped_b", "episodes_censored_at_horizon",
    "n_absent", "poisson_prove_version", "run_id_a", "run_id_b", "run_salt",
    "observation_cap_a", "observation_cap_b", "trace_spans_a", "trace_spans_b",
    "observation_cut_spans_a", "observation_cut_spans_b",
)
#: The same with the manifests but no counts (a library caller that never read a store).
PAIR_KEYS_MANIFESTS_ONLY = tuple(k for k in PAIR_KEYS_CLI if not k.startswith(("trace_spans", "observation_cut")))
#: The same with neither.
PAIR_KEYS_BARE = tuple(k for k in PAIR_KEYS_MANIFESTS_ONLY if not k.startswith(("run_", "observation_cap")))
#: The labels a pair's provenance list gains or renames, as every text surface prints them.
NEW_LABELS = (
    "episodes censored at horizon", "observation cap a", "observation cap b", "trace spans a", "trace spans b",
    "observation cut spans a", "observation cut spans b",
)
# LS retrofit, 2026-09-22 (local serve pass, Phase A): ``summary`` eighth.
TOP_LEVEL_KEYS = (
    "schema", "pair", "diff", "holes", "view", "headline", "trade_line", "summary", "fence", "panels",
    "intervals", "tree", "unverified", "heatmap_svg",
)
_A8A_SPAN_KEYS = ("operation", "step_name", "outcome", "outcome_by", "attempt", "gate", "truncated", "bytes_original")


# ---------- helpers: data construction, never an assertion ----------


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def shape(i: int, k: int) -> tuple[int, int]:
    """``(small llm spans, big llm spans)`` of replicate ``k`` in cell ``i``: deterministic, uneven,
    and no big span at all in a third of the episodes."""
    return (i + k) % 2 + 1, (i + 2 * k) % 3


def span(n: int, kind: str, size: int | None = None) -> Span:
    attrs = {} if size is None else {"gen_ai.input.messages": "x" * size}
    return Span(
        span_id=f"{n:016x}", parent_id=None if n == 1 else f"{1:016x}", kind=kind, name=f"{kind} {n}",
        start_ns=EPOCH + n, end_ns=EPOCH + n + 10, attrs=attrs,
    )


def trace_of(n_small: int, n_big: int, *, big: int = BIG, truncated: str | None = None) -> Trace:
    """A root, ``n_small`` llm spans with a ``SMALL``-byte input and ``n_big`` with a ``big``-byte one.

    Span ``n`` starts at ``EPOCH + n``, so the printed order of ``inspect`` is the order built here.
    """
    spans = [span(1, "agent")]
    spans += [span(2 + j, "llm", SMALL) for j in range(n_small)]
    spans += [span(2 + n_small + j, "llm", big) for j in range(n_big)]
    return Trace(spans=tuple(spans), source="otel", source_version="1.42.0", alias_map_version="1", truncated=truncated)


@dataclass(frozen=True)
class Expect:
    spans: int
    cut: int


def expect(limit: int, big: int = BIG) -> Expect:
    """What a store written by ``write_run`` holds, by arithmetic on the fixture's own sizes."""
    spans = cut = 0
    for i in range(len(TASKS)):
        for k in range(REPLICATES):
            n_small, n_big = shape(i, k)
            spans += 1 + n_small + n_big
            cut += (n_small if SMALL > limit else 0) + (n_big if big > limit else 0)
    return Expect(spans, cut)


def capture_record(**limits: int) -> dict[str, Any]:
    """The record ``executor._capture_record`` writes, with the given ``*_bytes`` entries."""
    return {
        "requested": True, "active": True, "reason": None, "instrumented": [], "semconv": "1.42.0",
        "alias_map_version": "1", "content": True, "max_spans": 1000, **limits,
    }


#: What a run written before A8b recorded: the byte limit under a retired name, no alias map.
LEGACY_CAPTURE = {
    "requested": True, "active": False, "reason": "the host installs nothing for a Modal run",
    "instrumented": [], "semconv": "1.42.0", "content": True, "max_span_bytes": 8192, "max_spans": 1000,
}


def manifest(run_id: str, capture: Mapping[str, Any] | None) -> RunManifest:
    environment: dict[str, Any] = {"note": "built by test_cut_surfacing"}
    if capture is not None:
        environment["capture"] = dict(capture)
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=f"salt-{run_id}",
        axis_types={"task": "categorical"}, backend="synthetic", environment=environment,  # type: ignore[arg-type]
    )


def write_run(
    root: Path, run_id: str, *, capture: Mapping[str, Any] | None, traces: bool = False,
    cut_at: int | None = None, big: int = BIG, horizon: float = 10.0,
) -> None:
    """Four cells of eight episodes, the first two of each failing at ``EVENT_T``. With ``traces``
    each episode carries ``trace_of(shape(i, k))``, cut at ``cut_at`` by the real cut when given."""
    store = Store(root)
    store.create_run(manifest(run_id, capture))
    records = []
    for i, task in enumerate(TASKS):
        for k in range(REPLICATES):
            meta: dict[str, Any] = {}
            if traces:
                trace = trace_of(*shape(i, k), big=big)
                if cut_at is not None:
                    trace = truncate_observations(trace, limit=cut_at)
                meta["trace"] = trace.to_dict()
            fail = k < 2
            episode = Episode(outcome="fail" if fail else "ok", t=EVENT_T if fail else horizon, horizon=horizon, meta=meta)
            records.append(EpisodeRecord.from_episode(
                episode, run_id=run_id, config={"task": task}, seed=1000 * i + k, replicate_index=k, wall_time=0.0,
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)


def rewrite_column(root: Path, run_id: str, column: str, fn: Callable[[str | None], str | None]) -> None:
    for part in sorted((root / run_id / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part)
        values = [fn(v) for v in table[column].to_pylist()]
        table = table.set_column(table.schema.get_field_index(column), column, pa.array(values, type=pa.string()))
        tmp = part.with_name(part.name + ".tmp")
        pq.write_table(table, tmp)
        os.replace(tmp, part)


def to_pre_a8a(value: str | None) -> str | None:
    """A stored envelope as a build before A8a wrote it: no alias map, thirteen span keys."""
    if value is None:
        return None
    envelope = json.loads(value)
    envelope.pop("alias_map_version", None)
    for s in envelope["spans"]:
        for key in _A8A_SPAN_KEYS:
            s.pop(key, None)
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


def snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def same_label_values(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    """The same labels with the same values, where a number is compared by value within the coarser
    of the two printed precisions: report.md and receipt.html print numbers under rule 10, the
    served page keeps its own (front-door spec section 5.4)."""
    if set(left) != set(right):
        return False
    for key, a in left.items():
        b = right[key]
        if a == b:
            continue
        numbers = [re.fullmatch(r"-?\d[\d,]*(?:\.(\d+))?", v) for v in (a, b)]
        if not all(numbers):
            return False
        half = max(0.5 * 10.0 ** -len(m.group(1) or "") for m in numbers if m)
        if abs(float(a.replace(",", "")) - float(b.replace(",", ""))) > half + 1e-12:
            return False
    return True


def prov_md(md: str) -> dict[str, str]:
    """``report.md``'s Provenance list as label -> value."""
    out: dict[str, str] = {}
    for line in md.split("## Provenance\n", 1)[1].splitlines():
        if line.startswith("- "):
            label, _, value = line[2:].partition(": ")
            out[label] = value
    return out


def prov_html(doc: str) -> dict[str, str]:
    """The Provenance ``<li>``s of a receipt or of the viewer page as label -> value."""
    found = re.search(r"<h2>Provenance</h2>\s*<ul>(.*?)</ul>", doc, re.S)
    assert found is not None, "no Provenance list"
    out: dict[str, str] = {}
    for item in re.findall(r"<li>(.*?)</li>", found.group(1), re.S):
        label, _, value = html_mod.unescape(item).partition(": ")
        out[label] = value
    return out


def shown(value: object, unknown: str) -> str:
    """How a provenance value reads on a text surface."""
    if value is None:
        return unknown
    if isinstance(value, Mapping):
        return ", ".join(f"{k}={v}" for k, v in value.items())
    return str(value)


@dataclass(frozen=True)
class Surfaces:
    """One pair on every surface the report verb and the viewer produce."""

    md: str
    html: str
    page: str
    payload: dict[str, Any]

    @property
    def diff(self) -> dict[str, Any]:
        return self.payload["diff"]

    def texts(self) -> dict[str, dict[str, str]]:
        return {"report.md": prov_md(self.md), "receipt.html": prov_html(self.html), "viewer page": prov_html(self.page)}


def surfaces(root: Path, a: str, b: str, out: Path, *, x: str = "task", knobs: Sequence[str] = KNOBS, event: str = "fail", y: str | None = None) -> Surfaces:
    base = ["--store", str(root)]
    axes = ["--x", x, *(["--y", y] if y else [])]
    code, _, err = run_cli([*base, "report", a, b, "--event", event, *axes, "--out", str(out), *knobs])
    assert code == 0, err
    code, raw, err = run_cli([*base, "serve", a, b, "--event", event, *axes, "--json", *knobs])
    assert code == 0, err
    payload = json.loads(raw)
    return Surfaces(
        (out / "report.md").read_text(encoding="utf-8"), (out / "receipt.html").read_text(encoding="utf-8"),
        render_html(payload) if payload["schema"] == SCHEMA else "", payload,
    )


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Nine runs, each a real writer's output. ``legacy`` and ``legacy-b`` are rewritten to the shape
    a build before A8a stored; the rest are what the current build writes."""
    root = tmp_path_factory.mktemp("cut-surfacing") / "store"
    write_run(root, "cut-a", capture=capture_record(max_observation_bytes=64), traces=True, cut_at=64)
    write_run(root, "cut-b", capture=capture_record(max_observation_bytes=4096), traces=True, cut_at=4096)
    write_run(root, "legacy", capture=LEGACY_CAPTURE, traces=True)
    rewrite_column(root, "legacy", "trace", to_pre_a8a)
    write_run(root, "bare", capture=None)
    write_run(root, "own", capture=None, traces=True, cut_at=OWN_RUN_CUT_AT, big=OWN_BIG)
    write_run(root, "hz10", capture=None, horizon=10.0)
    write_run(root, "hz5", capture=None, horizon=5.0)
    return root


@pytest.fixture(scope="module")
def s1(corpus: Path, tmp_path_factory: pytest.TempPathFactory) -> Surfaces:
    """A cap of 64 with cuts against a cap of 4096 with none: the dispatch's three-settings scenario."""
    return surfaces(corpus, "cut-a", "cut-b", tmp_path_factory.mktemp("s1"))


@pytest.fixture(scope="module")
def s2(corpus: Path, tmp_path_factory: pytest.TempPathFactory) -> Surfaces:
    """A current run against a run written before the per-value cut."""
    return surfaces(corpus, "cut-a", "legacy", tmp_path_factory.mktemp("s2"))


@pytest.fixture(scope="module")
def s3(corpus: Path, tmp_path_factory: pytest.TempPathFactory) -> Surfaces:
    """No capture record on either side; the second run stored its own trace and the default cut it."""
    return surfaces(corpus, "bare", "own", tmp_path_factory.mktemp("s3"))


@pytest.fixture(scope="module")
def hz(corpus: Path, tmp_path_factory: pytest.TempPathFactory) -> Surfaces:
    """Horizons 10 and 5: every ``ok`` episode of the first arm is re-censored at 5."""
    return surfaces(corpus, "hz10", "hz5", tmp_path_factory.mktemp("hz"))


@pytest.fixture(scope="module")
def go1(tmp_path_factory: pytest.TempPathFactory) -> Surfaces:
    return surfaces(GO1_ROOT, GO1_A, GO1_B, tmp_path_factory.mktemp("go1"), x="mu", y="push_pct_bw", event="fell", knobs=GO1_KNOBS)


def stored_multi(root: Path, a: str, b: str) -> tuple[MultiDiffResult, RunManifest, RunManifest]:
    store = Store(root)
    ma, mb = store.manifest(a), store.manifest(b)
    multi = multi_diff(store.read(a, meta=False), store.read(b, meta=False), events=["fail"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
    return multi, ma, mb


HORIZON_CENSORED = len(TASKS) * (REPLICATES - 2)  # every ``ok`` episode of hz10, at t = 10 > 5


# ---------- Z1: the horizon count, named for what it counts ----------


def test_z1_the_horizon_count_is_named_for_what_it_counts_on_every_surface(hz: Surfaces) -> None:
    assert HORIZON_CENSORED == 24
    for surface, labels in hz.texts().items():
        assert labels["episodes censored at horizon"] == "24", surface
        assert "truncated" not in labels, surface
    assert hz.diff["episodes_censored_at_horizon"] == 24 and "truncated" not in hz.diff
    assert hz.diff["horizon"] == 5.0


def test_z1_the_new_key_takes_the_old_keys_slot_and_the_old_key_is_gone_from_every_builder(hz: Surfaces, corpus: Path) -> None:
    keys = list(hz.diff)
    assert keys.index("episodes_censored_at_horizon") == keys.index("dropped_b") + 1 == keys.index("n_absent") - 1
    multi, ma, mb = stored_multi(corpus, "hz10", "hz5")
    provenance = build_multi_report(multi, ReportSpec(title="z1", x_axis="task"), manifests=(ma, mb)).provenance
    assert "truncated" not in provenance and provenance["episodes_censored_at_horizon"] == multi.truncated == 24


# ---------- Z2: the diff layer keeps its name and its meaning ----------


def test_z2_the_diff_layer_still_says_truncated_and_means_the_same_count(corpus: Path) -> None:
    multi, _, _ = stored_multi(corpus, "hz10", "hz5")
    assert multi.truncated == 24 and "truncated" in MultiDiffResult.__dataclass_fields__
    assert "truncated" in DiffResult.__dataclass_fields__
    code, out, err = run_cli(["--store", str(corpus), "diff", "hz10", "hz5", "--event", "fail", *KNOBS])
    assert code == 0, err
    # The command line prints numbers under rule 10 (front-door spec section 5.4), so the horizon is
    # read by value.
    horizon = re.search(r"\bhorizon=(\S+?),", out)
    assert "truncated=24" in out and horizon and float(horizon.group(1)) == 5.0, out


# ---------- Z3: the cap is on every surface, verbatim ----------


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z3_the_cap_of_each_run_is_on_the_surface_and_the_two_runs_are_told_apart(s1: Surfaces, surface: str) -> None:
    labels = s1.texts()[surface]
    assert labels["observation cap a"] == "max_observation_bytes=64"
    assert labels["observation cap b"] == "max_observation_bytes=4096"


def test_z3_the_payload_carries_the_cap_as_the_recorded_entry_and_nothing_translated(s1: Surfaces, s2: Surfaces, s3: Surfaces) -> None:
    assert s1.diff["observation_cap_a"] == {"max_observation_bytes": 64}
    assert s1.diff["observation_cap_b"] == {"max_observation_bytes": 4096}
    assert s2.diff["observation_cap_b"] == {"max_span_bytes": 8192}
    assert s3.diff["observation_cap_a"] is None and s3.diff["observation_cap_b"] is None


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z3_a_run_written_before_the_per_value_cap_reads_its_own_limit_under_its_own_name(s2: Surfaces, surface: str) -> None:
    assert s2.texts()[surface]["observation cap b"] == "max_span_bytes=8192"


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z3_no_capture_record_reads_not_recorded_and_never_none_or_zero(s3: Surfaces, surface: str) -> None:
    labels = s3.texts()[surface]
    assert labels["observation cap a"] == "not recorded" and labels["observation cap b"] == "not recorded"


# ---------- Z4: the count is what was cut ----------


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z4_spans_and_cut_spans_are_the_fixtures_own_arithmetic_on_every_surface(s1: Surfaces, surface: str) -> None:
    labels = s1.texts()[surface]
    e = expect(64)
    assert e.cut > 0 and e.cut < e.spans
    assert labels["trace spans a"] == str(e.spans) and labels["observation cut spans a"] == str(e.cut)


def test_z4_the_payload_carries_the_counts_as_integers(s1: Surfaces) -> None:
    e = expect(64)
    assert s1.diff["trace_spans_a"] == e.spans and s1.diff["observation_cut_spans_a"] == e.cut
    assert type(s1.diff["trace_spans_a"]) is int and type(s1.diff["observation_cut_spans_a"]) is int


def test_z4_the_three_text_surfaces_and_the_payload_agree_on_every_label(s1: Surfaces, s2: Surfaces, s3: Surfaces) -> None:
    for s in (s1, s2, s3):
        texts = s.texts()
        assert same_label_values(texts["report.md"], texts["receipt.html"]), (texts["report.md"], texts["receipt.html"])
        assert same_label_values(texts["report.md"], texts["viewer page"]), (texts["report.md"], texts["viewer page"])
        assert set(NEW_LABELS) <= set(texts["report.md"]), sorted(set(NEW_LABELS) - set(texts["report.md"]))


def test_z4_the_cut_is_read_off_the_stored_spans_and_not_off_the_limit(tmp_path: Path) -> None:
    """Same traces, same recorded limit, one run whose spans were never cut: the count follows the stamp."""
    root = tmp_path / "store"
    write_run(root, "stamped", capture=capture_record(max_observation_bytes=64), traces=True, cut_at=64)
    write_run(root, "unstamped", capture=capture_record(max_observation_bytes=64), traces=True, cut_at=None)
    s = surfaces(root, "stamped", "unstamped", tmp_path / "out")
    assert s.diff["observation_cut_spans_a"] == expect(64).cut
    assert s.diff["observation_cut_spans_b"] == 0 and s.diff["trace_spans_b"] == expect(64).spans


# ---------- Z5: a real zero stays a zero ----------


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z5_a_run_whose_traces_were_counted_and_cut_nowhere_reads_zero(s1: Surfaces, surface: str) -> None:
    labels = s1.texts()[surface]
    assert labels["observation cut spans b"] == "0" and labels["trace spans b"] == str(expect(4096).spans) != "0"


# ---------- Z6: an uncountable run is never a zero ----------


def test_z6_the_fixture_is_the_shape_it_claims_to_be(corpus: Path) -> None:
    """A pre-A8a envelope has no stamp at all: the precondition that makes a count of it a false zero."""
    envelopes = [e for e in Store(corpus).read("legacy", meta=False, trace="envelope")["trace"] if e is not None]
    assert len(envelopes) == len(TASKS) * REPLICATES
    assert all("truncated" not in s and "bytes_original" not in s for e in envelopes for s in e["spans"])
    assert all("alias_map_version" not in e for e in envelopes)


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z6_a_run_written_before_the_per_value_cut_reads_not_counted_on_every_surface(s2: Surfaces, surface: str) -> None:
    labels = s2.texts()[surface]
    assert labels["trace spans b"] == "not counted" and labels["observation cut spans b"] == "not counted"
    assert labels["observation cut spans a"] == str(expect(64).cut)


def test_z6_the_payload_carries_none_and_the_report_never_prints_a_zero_for_it(s2: Surfaces) -> None:
    assert s2.diff["trace_spans_b"] is None and s2.diff["observation_cut_spans_b"] is None
    assert "observation cut spans b: 0" not in s2.md and "observation cut spans b: 0" not in s2.html


# ---------- Z7: no capture record is a counted run whose cap is not recorded ----------


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z7_a_run_with_no_capture_record_and_no_trace_counts_zero_of_zero(s3: Surfaces, surface: str) -> None:
    labels = s3.texts()[surface]
    assert labels["trace spans a"] == "0" and labels["observation cut spans a"] == "0"


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z7_a_rollouts_own_trace_cut_at_the_default_is_counted_though_no_limit_was_recorded(s3: Surfaces, surface: str) -> None:
    labels = s3.texts()[surface]
    e = expect(OWN_RUN_CUT_AT, big=OWN_BIG)
    assert e.cut > 0
    assert labels["trace spans b"] == str(e.spans) and labels["observation cut spans b"] == str(e.cut)


# ---------- Z8: the count reads the envelope and nothing else ----------


def test_z8_a_run_whose_observation_bodies_are_not_json_reports_the_same_numbers(corpus: Path, s1: Surfaces, tmp_path: Path) -> None:
    poisoned = tmp_path / "store"
    shutil.copytree(corpus, poisoned)
    rewrite_column(poisoned, "cut-a", "trace_obs", lambda v: None if v is None else "not json")
    again = surfaces(poisoned, "cut-a", "cut-b", tmp_path / "out")
    assert again.diff["observation_cut_spans_a"] == expect(64).cut
    assert again.diff == s1.diff


def test_z8_a_post_split_run_whose_meta_column_is_not_json_still_reports(corpus: Path, s1: Surfaces, tmp_path: Path) -> None:
    """Mirrors A7's P7-5: on a post-A7 part the envelope read decodes neither ``trace_obs`` nor ``meta``."""
    poisoned = tmp_path / "store"
    shutil.copytree(corpus, poisoned)
    rewrite_column(poisoned, "cut-a", "meta", lambda v: "not json")
    again = surfaces(poisoned, "cut-a", "cut-b", tmp_path / "out")
    assert again.diff["observation_cut_spans_a"] == expect(64).cut
    assert again.diff == s1.diff


# ---------- Z9: nothing is backfilled ----------


def test_z9_report_serve_and_inspect_leave_every_stored_byte_and_mtime_where_they_were(corpus: Path, tmp_path: Path) -> None:
    before = snapshot(corpus)
    for pair in (("cut-a", "cut-b"), ("cut-a", "legacy"), ("bare", "own")):
        surfaces(corpus, *pair, tmp_path / "-".join(pair))
    for run in ("cut-a", "own"):
        assert run_cli(["--store", str(corpus), "inspect", run, "--event", "fail"])[0] == 0
    assert snapshot(corpus) == before


# ---------- Z10: the single-run report says the same things ----------


def test_z10_a_single_run_report_carries_the_cap_and_the_counts_without_a_side(corpus: Path, tmp_path: Path) -> None:
    code, _, err = run_cli(["--store", str(corpus), "report", "cut-a", "--x", "task", "--event", "fail", "--out", str(tmp_path / "one")])
    assert code == 0, err
    e = expect(64)
    for labels in (prov_md((tmp_path / "one" / "report.md").read_text()), prov_html((tmp_path / "one" / "receipt.html").read_text())):
        assert labels["observation cap"] == "max_observation_bytes=64"
        assert labels["trace spans"] == str(e.spans) and labels["observation cut spans"] == str(e.cut)
        assert "truncated" not in labels


def test_z10_a_single_run_report_over_a_run_written_before_the_cut_says_not_counted(corpus: Path, tmp_path: Path) -> None:
    code, _, err = run_cli(["--store", str(corpus), "report", "legacy", "--x", "task", "--event", "fail", "--out", str(tmp_path / "one")])
    assert code == 0, err
    for labels in (prov_md((tmp_path / "one" / "report.md").read_text()), prov_html((tmp_path / "one" / "receipt.html").read_text())):
        assert labels["observation cap"] == "max_span_bytes=8192"
        assert labels["trace spans"] == "not counted" and labels["observation cut spans"] == "not counted"


# ---------- Z11: the payload's version and its diff key set ----------


def test_z11_the_structure_is_a_new_version_because_its_diff_key_set_changed(s1: Surfaces) -> None:
    assert SCHEMA == NEW_SCHEMA and s1.payload["schema"] == NEW_SCHEMA
    with pytest.raises(ViewerError, match="unknown structure schema"):
        render_html({**s1.payload, "schema": "proofload.viewpair/5"})  # LS retrofit, 2026-09-22 (local serve pass, Phase A): the newest retired version


def test_z11_the_diff_object_is_the_pair_provenance_in_this_order(s1: Surfaces, hz: Surfaces) -> None:
    assert tuple(s1.diff) == PAIR_KEYS_CLI == tuple(hz.diff)


def test_z11_the_top_level_key_set_is_unchanged(s1: Surfaces) -> None:
    # serve --json adds verdict and sentence after schema (front-door spec section 5.6).
    # PF3 (spec section 4.4, R3): serve --json also adds method and method_chosen right after sentence.
    assert tuple(k for k in s1.payload if k not in ("verdict", "sentence")) == ("schema", "method", "method_chosen") + TOP_LEVEL_KEYS[1:]


# ---------- Z12: inspect prints the cut ----------


STEP = re.compile(r"\A  \d+\t")


def blocks_of(out: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in out.splitlines():
        if line.startswith("config_hash: "):
            current = [line]
            blocks.append(current)
        elif line == "":
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def cut_line(limit: str, n_small: int, n_big: int, size: int) -> str:
    parts = [limit] + [f"span {1 + n_small + m}: {size} bytes originally" for m in range(n_big)]
    return "observation: cut (" + "; ".join(parts) + ")"


def inspected(root: Path, run: str, event: str = "fail") -> list[tuple[int, int, list[str]]]:
    """``(n_small, n_big, block lines)`` per printed row, the shape recovered from the row's own config."""
    code, out, err = run_cli(["--store", str(root), "inspect", run, "--event", event])
    assert code == 0, err
    rows = []
    for block in blocks_of(out):
        i = TASKS.index(json.loads(block[1].split(": ", 1)[1])["task"])
        k = int(next(line for line in block if line.startswith("replicate_index: ")).split(": ", 1)[1])
        rows.append((*shape(i, k), block))
    return rows


def test_z12_a_row_with_a_cut_span_prints_one_line_naming_the_limit_and_each_cut_span_before_the_span_lines(corpus: Path) -> None:
    rows = inspected(corpus, "cut-a")
    assert len(rows) == 2 * len(TASKS) and any(n_big for _, n_big, _ in rows)
    for n_small, n_big, block in rows:
        lines = [line for line in block if line.startswith("observation:")]
        if n_big == 0:
            assert lines == [], block
            continue
        assert lines == [cut_line("limit max_observation_bytes=64", n_small, n_big, BIG)], block
        at = block.index(lines[0])
        assert any(line.startswith("t: ") for line in block[:at]) and STEP.match(block[at + 1]), block


def test_z12_the_line_says_when_no_limit_was_recorded(corpus: Path) -> None:
    rows = inspected(corpus, "own")
    cut = [(n_small, n_big, block) for n_small, n_big, block in rows if n_big]
    assert cut
    for n_small, n_big, block in cut:
        assert [line for line in block if line.startswith("observation:")] == [cut_line("limit not recorded", n_small, n_big, OWN_BIG)]


def test_z12_a_row_with_no_cut_prints_no_such_line_and_the_span_lines_keep_their_nine_columns(corpus: Path) -> None:
    rows = inspected(corpus, "cut-b")
    assert len(rows) == 2 * len(TASKS)
    for n_small, n_big, block in rows:
        assert not any(line.startswith("observation:") for line in block), block
        steps = [line for line in block if STEP.match(line)]
        assert len(steps) == 1 + n_small + n_big and all(len(line.split("\t")) == 9 for line in steps), block


def test_z12_the_trace_level_line_and_the_observation_line_are_two_lines_and_the_trace_one_comes_first(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = Store(root)
    store.create_run(manifest("hung", capture_record(max_observation_bytes=64)))
    trace = truncate_observations(trace_of(1, 1, truncated="timeout"), limit=64)
    store.append("hung", [EpisodeRecord.errored(run_id="hung", config={"task": "t0"}, seed=1, replicate_index=0, error="timeout", wall_time=0.0, meta={"trace": trace.to_dict()})])
    store.mark_complete("hung")
    code, out, err = run_cli(["--store", str(root), "inspect", "hung", "--event", "timeout"])
    assert code == 0, err
    (block,) = blocks_of(out)
    assert block.index("trace: truncated (timeout)") + 1 == block.index(cut_line("limit max_observation_bytes=64", 1, 1, BIG))


# ---------- Z13: the cap, its default and the stored field names are untouched ----------


def test_z13_there_is_no_default_cap_and_the_routing_constant_is_not_one() -> None:
    """CD (D1, D8) inverts this test in place, keeping Z13's slot. It was frozen on the morning of
    the day ADR-096 condemned the default: correct for the surfacing packet, whose brief fenced the
    cap off, and wrong the moment the default went. Nothing about the surfacing packet's own
    behaviour moves -- the value 8192 is still there, under the name of the job it still does."""
    import poisson_prove.trace as trace_module
    from poisson_prove.capture import CaptureSpec

    assert trace_module.OBSERVATION_ROUTING_BYTES == 8192
    for name in ("OBSERVATION_LIMIT_BYTES", "OBSERVATION_HEAD_BYTES", "OBSERVATION_TAIL_BYTES"):
        assert not hasattr(trace_module, name), name
    with pytest.raises(TypeError):
        CaptureSpec()  # type: ignore[call-arg]


def test_z13_the_two_stored_fields_and_the_trace_level_field_keep_their_names() -> None:
    fields = Span.__dataclass_fields__
    assert "truncated" in fields and "bytes_original" in fields
    assert "truncated" in Trace.__dataclass_fields__
    assert span(1, "llm", 4).truncated is None


# ---------- Z14: the builders' interface ----------


def test_z14_the_cap_comes_from_the_manifests_and_the_counts_from_the_caller(corpus: Path) -> None:
    multi, ma, mb = stored_multi(corpus, "cut-a", "cut-b")
    spec = ReportSpec(title="z14", x_axis="task")
    assert tuple(build_multi_report(multi, spec).provenance) == PAIR_KEYS_BARE
    with_manifests = build_multi_report(multi, spec, manifests=(ma, mb)).provenance
    assert tuple(with_manifests) == PAIR_KEYS_MANIFESTS_ONLY
    assert with_manifests["observation_cap_a"] == {"max_observation_bytes": 64}
    counted = build_multi_report(multi, spec, manifests=(ma, mb), observations=((7, 3), (9, 0))).provenance
    assert tuple(counted) == PAIR_KEYS_CLI
    assert (counted["trace_spans_a"], counted["observation_cut_spans_a"], counted["trace_spans_b"], counted["observation_cut_spans_b"]) == (7, 3, 9, 0)


def test_z14_counts_are_not_placed_without_manifests(corpus: Path) -> None:
    multi, _, _ = stored_multi(corpus, "cut-a", "cut-b")
    assert tuple(build_multi_report(multi, ReportSpec(title="z14", x_axis="task"), observations=((7, 3), (9, 0))).provenance) == PAIR_KEYS_BARE


def test_z14_a_legacy_manifest_blanks_the_count_whatever_the_caller_passed(corpus: Path) -> None:
    multi, ma, mb = stored_multi(corpus, "cut-a", "legacy")
    provenance = build_multi_report(multi, ReportSpec(title="z14", x_axis="task"), manifests=(ma, mb), observations=((7, 3), (9, 0))).provenance
    assert (provenance["trace_spans_a"], provenance["observation_cut_spans_a"]) == (7, 3)
    assert provenance["trace_spans_b"] is None and provenance["observation_cut_spans_b"] is None
    assert provenance["observation_cap_b"] == {"max_span_bytes": 8192}


def test_z14_the_library_and_the_cli_build_the_same_provenance_from_the_same_inputs(corpus: Path, s1: Surfaces) -> None:
    multi, ma, mb = stored_multi(corpus, "cut-a", "cut-b")
    a, b = expect(64), expect(4096)
    built = build_multi_report(multi, ReportSpec(title="z14", x_axis="task"), manifests=(ma, mb), observations=((a.spans, a.cut), (b.spans, b.cut)))
    assert built.provenance == s1.diff


# ---------- Z15: the Go1 pair, the published shape ----------


@pytest.mark.parametrize("surface", ["report.md", "receipt.html", "viewer page"])
def test_z15_go1_no_longer_says_truncated_and_says_what_it_can_and_cannot_say_about_observations(go1: Surfaces, surface: str) -> None:
    labels = go1.texts()[surface]
    assert "truncated" not in labels and labels["episodes censored at horizon"] == "0"
    assert labels["observation cap a"] == "not recorded" and labels["observation cap b"] == "not recorded"
    assert labels["trace spans a"] == "0" and labels["trace spans b"] == "0"
    assert labels["observation cut spans a"] == "0" and labels["observation cut spans b"] == "0"


def test_z15_go1_carries_the_horizon_count_it_always_carried_under_its_new_name(go1: Surfaces) -> None:
    assert go1.diff["episodes_censored_at_horizon"] == 0 and "truncated" not in go1.diff
