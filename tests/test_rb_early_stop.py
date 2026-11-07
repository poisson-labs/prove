"""Remote backends, C8: a remote sweep stops early when every rollout of its first stored batch has
no outcome (#11), invariants E1 to E7 and rulings RB-30 to RB-32.

**The rule, as these tests read it.** The first batch is the first batch whose rows the shared
runner stores in this segment of the run, in completion order, not batch 0. A row has no outcome
when its rollout raised, timed out, or its batch failed for an infrastructure reason after its
retries (RB-30). The rule waits for the first stored batch of at least ``min(batch_size, 32)`` rows
(RB-31); a smaller batch that lands first is stored and judged together with the next one. When
none of the rows judged has an outcome, the runner takes nothing more from the mapper, closes the
mapper's iterator (how a backend learns to cancel what is in flight, as a Ctrl-C does), keeps every
batch it has stored, and leaves the run partial with ``stopped_by = "first_batch_errored"`` at the
top level of ``manifest.json``. A batch with at least one outcome keeps the sweep going, and later
batches never stop it. The local backend is unchanged (RB-32).

**How it is reached.** Through ``run_with_mapper``, the runner Modal and the cluster backends share,
driven by a scripted mapper that yields batches lazily in the order a test names, so what the
runner pulled and whether it closed the iterator are read off the mapper (E1, E3, E4, E6, the
floors, RB-30). Through ``cli.main`` in process with a fake ``modal`` in ``sys.modules``, whose map
runs Prove's own container function on each item only when the runner asks for it (E1's event log,
E2). E5 on the cluster backend, the ledger closing ``stopped``, is in ``test_bu_burla_backend.py``;
the cluster stop that follows belongs with the cluster's own life. Nothing here reaches a network
(E7).
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import io
import json
import shlex
import sys
import types
from collections.abc import Iterator, Sequence
from pathlib import Path
from secrets import token_hex
from typing import Any

import pytest

from poisson_prove import cli
from poisson_prove.executor import plan
from poisson_prove.executor_modal import ModalOptions, run_with_mapper
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store

STOP = "first_batch_errored"
MESSAGE = "the wrapper's client is not configured"
TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "wrapper.py", line 3, in rollout\n'
    f"ValueError: {MESSAGE}"
)
TARGET = "rb_fixture_target:rollout"
#: Each store a test opened, by identity, and the folder it was opened on.
ROOTS: dict[int, Path] = {}


# ---------- plans, stores and the scripted mapper ----------


def write_spec(root: Path, *, cells: Sequence[str] = ("a", "b"), replicates: int = 20, tail: str = "") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    values = ", ".join(f'"{c}"' for c in cells)
    path = root / "sweep.toml"
    path.write_text(
        f'target_id = "rb-early@v0"\nt_unit = "steps"\nreplicates = {replicates}\n\n'
        f'[axes.cell]\ntype = "categorical"\nvalues = [{values}]\n{tail}',
        encoding="utf-8",
    )
    return path


def make_plan(root: Path, *, cells: Sequence[str] = ("a", "b"), replicates: int = 20,
              resume: str | None = None) -> tuple[Any, Store]:
    spec = SweepSpec.load(write_spec(root, cells=cells, replicates=replicates))
    store = Store(root / "store")
    ROOTS[id(store)] = root / "store"
    if resume is not None:
        return plan(spec, store, backend="modal", resume=resume, import_path=TARGET), store
    return plan(spec, store, backend="modal", run_salt="rb-early-salt", import_path=TARGET), store


def opts(batch_size: int, **over: Any) -> ModalOptions:
    return ModalOptions(batch_size=batch_size, **over)


def ok(job: Sequence[Any]) -> dict[str, Any]:
    return {"outcome": "survived", "t": 1.0, "horizon": 1.0, "meta": {}, "wall_time": 0.0,
            "backend_meta": {"i": job[2]}}


def results(kind: str, jobs: Sequence[Sequence[Any]]) -> list[Any] | BaseException:
    """One batch's results: every row ok, every row raised (a traceback, or the dict form with its
    meta), every row timed out, one row ok and the rest raised, or the whole batch an infra failure."""
    if kind == "ok":
        return [ok(job) for job in jobs]
    if kind == "err":
        return [TRACEBACK for _ in jobs]
    if kind == "err_with_meta":
        return [{"error": TRACEBACK, "meta": {"note": "kept"}} for _ in jobs]
    if kind == "timeout":
        return ["timeout" for _ in jobs]
    if kind == "one_ok":
        return [ok(jobs[0]), *[TRACEBACK for _ in jobs[1:]]]
    if kind == "infra":
        return RuntimeError("fixture: the batch's container was lost")
    raise AssertionError(kind)


class ScriptedMapper:
    """A mapper that yields the batches of each call lazily, in the order its script names and then
    the rest in index order as ``ok``. It notes, per call, which batches the runner pulled and
    whether the runner closed the iterator before taking every batch. It keeps every iterator it
    handed out, so an iterator is closed only by the runner's own ``close()``, never by the
    interpreter collecting it when the runner returns."""

    import_path = TARGET

    def __init__(self, *calls: Sequence[tuple[int, str]]) -> None:
        self.script = [list(call) for call in calls]
        self.pulled: list[list[int]] = []
        self.closed: list[bool] = []
        self.kept: list[Iterator[tuple[int, Any]]] = []

    def __call__(self, batches: Sequence[Sequence[Any]]) -> Iterator[tuple[int, Any]]:
        stream = self._stream(batches)
        self.kept.append(stream)
        return stream

    def _stream(self, batches: Sequence[Sequence[Any]]) -> Iterator[tuple[int, Any]]:
        n = len(self.pulled)
        named = self.script[n] if n < len(self.script) else []
        order = [*named, *[(k, "ok") for k in range(len(batches)) if k not in {k for k, _ in named}]]
        self.pulled.append([])
        self.closed.append(False)
        finished = False
        try:
            for k, kind in order:
                self.pulled[n].append(k)
                yield k, results(kind, batches[k])
            finished = True
        finally:
            if not finished:
                self.closed[n] = True


def manifest(where: Store | Path, run_id: str) -> dict[str, Any]:
    """``manifest.json`` as stored, read as the file it is, from a store's folder or a store opened here."""
    root = where if isinstance(where, Path) else ROOTS[id(where)]
    return json.loads((root / run_id / "manifest.json").read_text(encoding="utf-8"))


def stored_keys(store: Store, run_id: str) -> set[tuple[str, int]]:
    frame = store.read(run_id, meta=False)
    return {(str(h), int(k)) for h, k in zip(frame["config_hash"], frame["replicate_index"], strict=True)}


def batch_keys(p: Any, size: int, *ks: int) -> set[tuple[str, int]]:
    pairs = list(p.pairs)
    out: set[tuple[str, int]] = set()
    for k in ks:
        out |= {(pair.config_hash, pair.replicate_index) for pair in pairs[k * size:(k + 1) * size]}
    return out


def assert_stopped(summary: Any, store: Store, p: Any, kept: set[tuple[str, int]]) -> None:
    assert summary.stopped_by == STOP and not summary.complete, summary
    assert stored_keys(store, p.run_id) == kept
    m = manifest(store, p.run_id)
    assert m["status"] == "partial" and m.get("stopped_by") == STOP, m


def assert_ran_to_the_end(summary: Any, store: Store, p: Any) -> None:
    assert summary.stopped_by is None and summary.complete, summary
    assert stored_keys(store, p.run_id) == batch_keys(p, len(p.pairs), 0)
    m = manifest(store, p.run_id)
    assert m["status"] == "complete" and m.get("stopped_by") is None, m


# ---------- E1: the stop, on the shared runner ----------


def test_e1_an_all_errored_first_stored_batch_stops_the_sweep_and_closes_the_mapper(tmp_path: Path) -> None:
    """40 rows in 5 batches of 8; batch 2 lands first with no outcome. The runner takes nothing more,
    closes the mapper's iterator before it returns, submits no second call, and keeps batch 2."""
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(2, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled == [[2]], mapper.pulled
    assert mapper.closed == [True], "the runner did not close the mapper's iterator before returning"
    assert_stopped(summary, store, p, batch_keys(p, 8, 2))


@pytest.mark.parametrize("kind", ["err", "err_with_meta", "timeout"])
def test_e1_rb30_every_kind_of_no_outcome_counts(tmp_path: Path, kind: str) -> None:
    """RB-30: a raise, a raise that kept its meta, and a timeout are each a row with no outcome."""
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(0, kind)])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled == [[0]], mapper.pulled
    assert_stopped(summary, store, p, batch_keys(p, 8, 0))


def test_e1_rb30_a_batch_failed_for_infrastructure_after_its_retries_counts(tmp_path: Path) -> None:
    """RB-30: with no retry left, an infra failure is stored as rows with no outcome, and it is the
    first stored batch."""
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(3, "infra")])
    summary = run_with_mapper(p, mapper, store, options=opts(8, infra_retries=0))
    assert mapper.pulled == [[3]], mapper.pulled
    assert_stopped(summary, store, p, batch_keys(p, 8, 3))


def test_e1_an_infra_failure_with_a_retry_left_is_not_a_stored_batch(tmp_path: Path) -> None:
    """A batch that fails for infrastructure and will be retried stores nothing, so it is not the
    first stored batch: the first stored is the ok one after it, and the sweep runs to the end."""
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(0, "infra"), (1, "ok")])
    summary = run_with_mapper(p, mapper, store, options=opts(8, infra_retries=1))
    assert_ran_to_the_end(summary, store, p)
    assert len(mapper.pulled) == 2, "the failed batch was not retried"


# ---------- E3, E4: what does not stop ----------


def test_e1_a_first_batch_that_is_the_whole_sweep_leaves_nothing_to_stop(tmp_path: Path) -> None:
    """Eight rows in one batch of eight, none with an outcome: every row asked for is stored, so the
    run completes as an all-errored run does today, with no stop recorded."""
    p, store = make_plan(tmp_path, replicates=4)
    mapper = ScriptedMapper([(0, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert summary.complete and summary.stopped_by is None, summary
    m = manifest(store, p.run_id)
    assert m["status"] == "complete" and m.get("stopped_by") is None, m


def test_e3_a_first_batch_with_one_outcome_does_not_stop(tmp_path: Path) -> None:
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(1, "one_ok"), (0, "err"), (2, "err"), (3, "err"), (4, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled == [[1, 0, 2, 3, 4]] and mapper.closed == [False], (mapper.pulled, mapper.closed)
    assert_ran_to_the_end(summary, store, p)


def test_e3_a_later_all_errored_batch_does_not_stop(tmp_path: Path) -> None:
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(0, "ok"), (1, "err"), (2, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.closed == [False]
    assert_ran_to_the_end(summary, store, p)


def test_e4_the_first_batch_is_the_first_stored_not_batch_0(tmp_path: Path) -> None:
    """Batch 0 has no outcome, but an ok batch lands before it: the sweep runs to the end."""
    p, store = make_plan(tmp_path)
    mapper = ScriptedMapper([(3, "ok"), (0, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled == [[3, 0, 1, 2, 4]], mapper.pulled
    assert_ran_to_the_end(summary, store, p)


# ---------- RB-31: the floor ----------


def test_rb31_a_batch_under_the_floor_landing_first_does_not_stop_alone(tmp_path: Path) -> None:
    """42 rows in batches of 8: batch 5 holds 2 rows, under ``min(8, 32)``. It lands first with no
    outcome; the runner takes the next batch, which has outcomes, and runs to the end."""
    p, store = make_plan(tmp_path, replicates=21)
    mapper = ScriptedMapper([(5, "err"), (0, "ok")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled[0][:2] == [5, 0] and mapper.closed == [False], (mapper.pulled, mapper.closed)
    assert_ran_to_the_end(summary, store, p)


def test_rb31_under_the_floor_then_a_full_batch_with_no_outcome_stops_keeping_both(tmp_path: Path) -> None:
    p, store = make_plan(tmp_path, replicates=21)
    mapper = ScriptedMapper([(5, "err"), (0, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled == [[5, 0]] and mapper.closed == [True], (mapper.pulled, mapper.closed)
    assert_stopped(summary, store, p, batch_keys(p, 8, 5, 0))


def test_rb31_an_outcome_under_the_floor_keeps_the_sweep_going(tmp_path: Path) -> None:
    """The small batch that landed first has outcomes and the full batch after it has none. The rows
    judged are every row stored until the floor is met, and some have an outcome, so the sweep runs
    to the end."""
    p, store = make_plan(tmp_path, replicates=21)
    mapper = ScriptedMapper([(5, "ok"), (0, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert_ran_to_the_end(summary, store, p)


def test_rb31_the_floor_is_32_rows_when_the_batch_is_larger(tmp_path: Path) -> None:
    """``batch_size`` 64 over 97 rows: the tail of 33 rows meets ``min(64, 32)`` and counts alone."""
    p, store = make_plan(tmp_path, cells=("a",), replicates=97)
    mapper = ScriptedMapper([(1, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(64))
    assert mapper.pulled == [[1]] and mapper.closed == [True], (mapper.pulled, mapper.closed)
    assert_stopped(summary, store, p, batch_keys(p, 64, 1))


def test_rb31_a_tail_of_31_rows_is_under_the_floor_of_32(tmp_path: Path) -> None:
    """``batch_size`` 64 over 95 rows: the tail of 31 rows is under the floor and does not count alone."""
    p, store = make_plan(tmp_path, cells=("a",), replicates=95)
    mapper = ScriptedMapper([(1, "err"), (0, "ok")])
    summary = run_with_mapper(p, mapper, store, options=opts(64))
    assert_ran_to_the_end(summary, store, p)


# ---------- E6: a resumed run's own segment ----------


def _first_segment_ok_then_partial(tmp_path: Path) -> tuple[Any, Store]:
    p, store = make_plan(tmp_path)
    summary = run_with_mapper(p, ScriptedMapper(), store, options=opts(8, max_rollouts=8))
    assert summary.stopped_by == "max_rollouts" and not summary.complete, summary
    return p, store


def test_e6_a_resumed_segment_judges_its_own_first_stored_batch(tmp_path: Path) -> None:
    """Segment one stored a batch with outcomes and stopped at --max-rollouts. The resumed segment's
    first stored batch has none: it stops, though the run already holds outcomes."""
    first, _ = _first_segment_ok_then_partial(tmp_path)
    p, store = make_plan(tmp_path, resume=first.run_id)
    mapper = ScriptedMapper([(1, "err")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert mapper.pulled == [[1]] and mapper.closed == [True], (mapper.pulled, mapper.closed)
    assert_stopped(summary, store, p, batch_keys(first, 8, 0) | batch_keys(p, 8, 1))


def test_e6_rows_stored_before_the_resume_are_not_judged(tmp_path: Path) -> None:
    """Segment one stopped early with no outcome at all. The resumed segment's first stored batch has
    outcomes: it runs to the end, and the run is complete with ``stopped_by`` cleared."""
    p1, store = make_plan(tmp_path)
    stopped = run_with_mapper(p1, ScriptedMapper([(0, "err")]), store, options=opts(8))
    assert stopped.stopped_by == STOP, stopped
    p, store = make_plan(tmp_path, resume=p1.run_id)
    mapper = ScriptedMapper([(0, "ok")])
    summary = run_with_mapper(p, mapper, store, options=opts(8))
    assert summary.complete and summary.stopped_by is None, summary
    assert stored_keys(store, p1.run_id) == batch_keys(p1, len(p1.pairs), 0)
    m = manifest(store, p1.run_id)
    assert m["status"] == "complete" and m.get("stopped_by") is None, m


# ---------- the command line: E1's event log and E2's words, on a fake Modal ----------


class _Image:
    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: self


class FakeModal:
    """Modal's client offline: ``map`` runs Prove's container function on one item at a time, only
    when the caller asks for the next, first the items named in ``first`` and then the rest in
    order. It records which items ran and whether the caller closed the map early."""

    def __init__(self, first: Sequence[int]) -> None:
        self.first = list(first)
        self.ran: list[int] = []
        self.closed = False

    def module(self) -> types.ModuleType:
        fake = types.ModuleType("modal")
        fake.__spec__ = importlib.machinery.ModuleSpec("modal", None)
        owner = self

        class Function:
            def __init__(self, fn: Any) -> None:
                self.fn = fn

            def map(self, items: Any, **kwargs: Any) -> Iterator[Any]:
                listed = list(items)
                order = [*owner.first, *[k for k in range(len(listed)) if k not in owner.first]]
                done = False
                try:
                    for k in order:
                        owner.ran.append(k)
                        yield self.fn(listed[k])
                    done = True
                finally:
                    owner.closed = not done

        class App:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def function(self, **kwargs: Any) -> Any:
                return Function

            @contextlib.contextmanager
            def run(self) -> Iterator[Any]:
                yield self

        fake.App = App  # type: ignore[attr-defined]
        fake.Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image(),  # type: ignore[attr-defined]
                                           from_dockerfile=lambda *a, **k: _Image())
        fake.Secret = types.SimpleNamespace(from_name=lambda *a, **k: object())  # type: ignore[attr-defined]
        return fake


MODAL_TABLE = '\n[modal]\nconcurrency = 1\nbatch_size = 8\n\n[modal.image]\npython = "3.11"\n'


def _modal_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first: Sequence[int],
                 body: str) -> tuple[FakeModal, Path, str]:
    """A spec of 40 rows on Modal in batches of 8, a target module of its own name on the path, and
    the fake client in ``sys.modules``."""
    module = f"rb_wrapper_{token_hex(4)}"
    (tmp_path / f"{module}.py").write_text(
        "from poisson_prove.episode import Episode\n\n\ndef rollout(cfg, seed):\n" + body, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    write_spec(tmp_path, tail=MODAL_TABLE)
    fake = FakeModal(first)
    monkeypatch.setitem(sys.modules, "modal", fake.module())
    return fake, tmp_path / "store", f"{module}:rollout"


RAISES = f"    raise ValueError({MESSAGE!r})\n"


def _sweep(store: Path, spec: Path, target: str, *more: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--store", str(store), "sweep", str(spec), "--target", target, "--backend", "modal",
                     "--max-mde", "1", "--yes", *more], stdout=out, stderr=err, stdin=io.StringIO())
    return code, out.getvalue(), err.getvalue()


def _only_run(store: Path) -> tuple[str, str]:
    out = io.StringIO()
    assert cli.main(["--store", str(store), "runs", "--json"], stdout=out, stderr=io.StringIO()) == 0
    (run,) = json.loads(out.getvalue())["runs"]
    return run["run_id"], run["run_name"]


def _events(store: Path, run_id: str) -> list[dict[str, Any]]:
    path = store / run_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sentence(name: str) -> str:
    return f'every rollout of the first batch had no outcome, so the sweep stopped after 8 of 40 (run "{name}")'


ERROR_LINE = "error: every rollout of the first batch had no outcome; the rest of the sweep was not run"


def test_e1_e2_a_modal_sweep_stops_says_so_and_ends_its_log_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake, store_root, target = _modal_world(tmp_path, monkeypatch, [3], RAISES)
    code, out, err = _sweep(store_root, tmp_path / "sweep.toml", target)
    report = (code, out, err)
    assert code == 3, report
    assert fake.ran == [3] and fake.closed, ("the map went on after the first batch", fake.ran, fake.closed)
    run_id, name = _only_run(store_root)
    assert Store(store_root).count(run_id) == 8
    m = manifest(store_root, run_id)
    assert m["status"] == "partial" and m.get("stopped_by") == STOP, m
    last = _events(store_root, run_id)[-1]
    assert last["kind"] == "interrupted" and last["detail"].get("why") == STOP, last
    lines = out.splitlines()
    # The plan's block, then the result's: its first line is the verdict and its sentence.
    verdicts = [line for line in lines if line and not line.startswith(" ")]
    assert verdicts[0].startswith("plan  ") and verdicts[1:] == [f"stopped  {_sentence(name)}"], report
    commonest = [line.strip() for line in lines if line.strip().startswith("the commonest error  ")]
    assert len(commonest) == 1, report
    assert f"ValueError: {MESSAGE}" in commonest[0] and commonest[0].endswith("(8 of 8)"), commonest
    errors = [line for line in err.splitlines() if line.startswith("error: ")]
    assert errors == [ERROR_LINE], report


def test_e2_the_only_next_inspects_the_stopped_run_and_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No resume line, since resuming would run the same broken target: the one ``next:`` is
    ``inspect`` of that run (its word as the argument ``inspect`` takes), the commonest error's
    kind as ``--event``, ``--limit 3``, and it runs."""
    fake, store_root, target = _modal_world(tmp_path, monkeypatch, [0], RAISES)
    code, out, err = _sweep(store_root, tmp_path / "sweep.toml", target)
    assert code == 3, (code, out, err)
    assert fake.ran == [0], ("the sweep did not stop after its first batch", fake.ran)
    nexts = [line.strip()[len("next: "):] for line in out.splitlines() if line.strip().startswith("next: ")]
    assert len(nexts) == 1, out
    words = shlex.split(nexts[0])
    assert words[:2] == ["poisson-prove", "inspect"], words
    assert "--resume" not in words and "sweep" not in words, words
    assert words[words.index("--limit") + 1] == "3", words
    assert words[words.index("--event") + 1] == "ValueError", words
    run_id, _ = _only_run(store_root)
    shown = io.StringIO()
    assert cli.main([*words[1:], "--json"], stdout=shown, stderr=io.StringIO()) == 0, words
    document = json.loads(shown.getvalue())
    assert document.get("run_id") == run_id, document


def test_e2_json_carries_the_same_verdict_sentence_and_next(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake, store_root, target = _modal_world(tmp_path, monkeypatch, [1], RAISES)
    code, out, err = _sweep(store_root, tmp_path / "sweep.toml", target)
    assert code == 3, (code, out, err)
    plain_next = [line.strip()[len("next: "):] for line in out.splitlines() if line.strip().startswith("next: ")]
    other = tmp_path / "again"
    other.mkdir()
    fake2, store2, target2 = _modal_world(other, monkeypatch, [1], RAISES)
    code, out, err = _sweep(store2, other / "sweep.toml", target2, "--json")
    assert code == 3, (code, out, err)
    document = json.loads(out)
    _, name = _only_run(store2)
    assert document["verdict"] == "stopped" and document["sentence"] == _sentence(name), document
    assert [shlex.split(n)[:2] for n in document["next"]] == [["poisson-prove", "inspect"]], document
    assert len(document["next"]) == len(plain_next) == 1
    assert document.get("stopped_by") == STOP, document


def test_e1_a_modal_sweep_whose_first_batch_has_an_outcome_runs_to_the_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control for the two above: the same world, a target that returns, every batch run."""
    fake, store_root, target = _modal_world(
        tmp_path, monkeypatch, [3], '    return Episode(outcome="survived", t=1.0, horizon=1.0)\n')
    code, out, err = _sweep(store_root, tmp_path / "sweep.toml", target)
    assert code == 0, (code, out, err)
    assert sorted(fake.ran) == [0, 1, 2, 3, 4] and not fake.closed, fake.ran
    run_id, _ = _only_run(store_root)
    assert _events(store_root, run_id)[-1]["kind"] == "finished"


# ---------- RB-32: the local backend is unchanged ----------


def test_rb32_a_local_sweep_whose_every_rollout_errors_runs_to_the_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = f"rb_local_{token_hex(4)}"
    (tmp_path / f"{module}.py").write_text(f"def rollout(cfg, seed):\n{RAISES}", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    spec = write_spec(tmp_path, replicates=20)
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--store", str(tmp_path / "store"), "sweep", str(spec), "--target", f"{module}:rollout",
                     "--max-mde", "1", "--yes", "--batch-size", "8"], stdout=out, stderr=err, stdin=io.StringIO())
    assert code == 3, (code, out.getvalue(), err.getvalue())
    run_id, _ = _only_run(tmp_path / "store")
    assert Store(tmp_path / "store").count(run_id) == 40
    assert manifest(tmp_path / "store", run_id).get("stopped_by") is None
    assert "first batch" not in out.getvalue() + err.getvalue()


def test_e1_the_stopped_run_reads_as_stopped_in_runs_and_keeps_its_stored_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Section 11.2: the run stays in the store as ``stopped`` in ``runs``, as an all-errored run does
    today, while the manifest and ``runs --json`` keep the stored ``partial``."""
    fake, store_root, target = _modal_world(tmp_path, monkeypatch, [2], RAISES)
    code, out, err = _sweep(store_root, tmp_path / "sweep.toml", target)
    assert code == 3 and fake.ran == [2], (code, fake.ran, out, err)
    run_id, name = _only_run(store_root)
    shown = io.StringIO()
    assert cli.main(["--store", str(store_root), "runs"], stdout=shown, stderr=io.StringIO()) == 0
    (row,) = [line for line in shown.getvalue().splitlines() if name in line]
    assert "stopped" in row.split() and "partial" not in row.split(), row
    listed = io.StringIO()
    assert cli.main(["--store", str(store_root), "runs", "--json"], stdout=listed, stderr=io.StringIO()) == 0
    (entry,) = json.loads(listed.getvalue())["runs"]
    assert entry["status"] == "partial", entry
