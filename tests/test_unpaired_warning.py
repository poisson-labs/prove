"""The unpaired-analysis warning (Action List B.4, "paired-test default").

``_pairing`` has always computed ``paired`` and reported it -- in the headline, in
``to_markdown``'s method line, on ``MultiDiffResult`` -- and used it for exactly one decision:
refusing ``mcnemar_bh`` when the two runs cannot be paired. The other side of that predicate
was silent. A user who ran ``--pair-with``, got a shared run salt, and then took the default
``fisher_bh`` was answering a weaker question than the data supports, and nothing said so.

Three constraints the tests below are written to hold, taken from the queue item:

- It fires from **M6**, not the CLI. ``cli.py``'s module docstring commits that module to
  deciding nothing statistical, and a warning about which test to run is a statistical
  decision. U14 and U15 read ``src/`` so the rule is a test rather than a review step.
- **Once per diff, not per cell.** U6 drives a six-cell, three-event diff -- eighteen tests --
  and counts one record.
- **Never a silent switch.** The method is not chosen from whether two runs happen to share a
  salt; that would make the statistic a property of run provenance rather than of the request.
  U8 pins the numbers identical across a pairable pair and its unpairable twin, so the only
  thing the salt changes is the warning.

Plain assertions over shared helpers. There is one frame builder, one manifest builder and one
CLI runner here; everything else is written out at the assertion.
"""

from __future__ import annotations

import ast
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, get_args

import pandas as pd

import poisson_prove.cli as cli
from poisson_prove.diff import (
    Method,
    NotPairable,
    UnpairedAnalysis,
    diff,
    multi_diff,
)
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.survival import censor

SRC = Path(__file__).resolve().parents[1] / "src" / "poisson_prove"
SALT = "unpaired-warning-oracle-salt"
OTHER_SALT = "a-different-salt"
HORIZON = 10.0
EVENTS = ("fail", "timed_out")
# Six cells x three events is eighteen (cell, event) tests under one BH family: enough that a
# warning raised inside either loop would be counted more than once.
CELLS = tuple((task, level) for task in ("alpha", "beta", "gamma") for level in (0.0, 1.0))
MULTI_EVENTS = ("fail", "timed_out", "crashed")


# ---------- builders ----------


def syn_config(task: str, level: float) -> dict[str, Any]:
    return {"task": task, "level": level}


def manifest(run_id: str, salt: str) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id="synthetic@v0",
        t_unit="steps",
        run_salt=salt,
        axis_types={"task": "categorical", "level": "continuous"},
        backend="synthetic",
        environment={"note": "built by test_unpaired_warning"},
    )


def raw(*, fails: int, n: int = 8) -> pd.DataFrame:
    """A raw store frame over CELLS: ``fails`` rows end in ``fail`` at t=3, one ends in
    ``timed_out`` at t=5, one in ``crashed`` at t=1, the rest survive to the horizon."""
    rows: list[dict[str, Any]] = []
    for index, (task, level) in enumerate(CELLS):
        config = syn_config(task, level)
        for k in range(n):
            if k < fails:
                outcome, t = "fail", 3.0
            elif k == n - 2:
                outcome, t = "timed_out", 5.0
            elif k == n - 1:
                outcome, t = "crashed", 1.0
            else:
                outcome, t = "ok", HORIZON
            rows.append(
                {
                    "config_hash": config_hash(config),
                    "config": config,
                    "replicate_index": k,
                    "outcome": outcome,
                    "t": t,
                    "horizon": HORIZON,
                    "seed": 1000 * index + k,
                }
            )
    frame = pd.DataFrame.from_records(rows)
    frame["config"] = frame["config"].astype(object)
    frame["outcome"] = frame["outcome"].astype(object)
    return frame


def caught(fn: Any) -> list[warnings.WarningMessage]:
    """Every warning ``fn()`` raises, with the ``always`` filter so nothing is swallowed by
    the per-location registry -- the count has to be the code's, not the filter's."""
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        fn()
    return list(records)


def unpaired_records(records: Sequence[warnings.WarningMessage]) -> list[warnings.WarningMessage]:
    return [r for r in records if r.category is UnpairedAnalysis]


def multi(method: str, salt_b: str = SALT, **kwargs: Any) -> Any:
    a, b = raw(fails=2), raw(fails=4)
    return multi_diff(
        a,
        b,
        events=list(EVENTS),
        method=method,  # type: ignore[arg-type]
        manifest_a=kwargs.pop("manifest_a", manifest("run-a", SALT)),
        manifest_b=kwargs.pop("manifest_b", manifest("run-b", salt_b)),
        **kwargs,
    )


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: Sequence[str]) -> Result:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def write_run(store: Store, run_id: str, salt: str, *, fails: int) -> None:
    store.create_run(manifest(run_id, salt))
    records = []
    for index, (task, level) in enumerate(CELLS):
        config = syn_config(task, level)
        for k in range(8):
            episode = (
                Episode(outcome="fail", t=3.0, horizon=HORIZON)
                if k < fails
                else Episode(outcome="ok", t=HORIZON, horizon=HORIZON)
            )
            records.append(
                EpisodeRecord.from_episode(
                    episode,
                    run_id=run_id,
                    config=config,
                    seed=1000 * index + k,
                    replicate_index=k,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


# ---------- the warning fires ----------


def test_u1_a_pairable_pair_analysed_with_fisher_warns() -> None:
    """The case the README shipped for months: --pair-with ran, the salts match, and the
    default method compares the two arms as independent samples anyway."""
    records = unpaired_records(caught(lambda: multi("fisher_bh")))
    assert len(records) == 1, [str(r.message) for r in records]


def test_u2_logrank_warns_too() -> None:
    """The predicate is 'the method does not read the pairing', not 'the method is fisher'.
    logrank_bh discards the correspondence exactly as fisher_bh does."""
    records = unpaired_records(caught(lambda: multi("logrank_bh")))
    assert len(records) == 1, [str(r.message) for r in records]


def test_u3_the_paired_method_does_not_warn() -> None:
    """mcnemar_bh is the method that uses the correspondence; there is nothing to warn about."""
    assert unpaired_records(caught(lambda: multi("mcnemar_bh"))) == []


def test_u4_a_salt_mismatch_does_not_warn() -> None:
    """Two runs that are not pairable discard nothing by being analysed unpaired. The warning
    is about a *pairable* pair analysed unpaired, not about the absence of pairing."""
    assert unpaired_records(caught(lambda: multi("fisher_bh", salt_b=OTHER_SALT))) == []


def test_u5_missing_manifests_do_not_warn() -> None:
    """Without both manifests, pairing is unknown rather than discarded. This is the same
    boundary NotPairable already draws for mcnemar_bh."""
    records = caught(lambda: multi("fisher_bh", manifest_a=None, manifest_b=None))
    assert unpaired_records(records) == []


def test_u6_once_per_diff_not_per_cell() -> None:
    """Six cells x three events is eighteen tests under one BH family. A warning raised inside
    the cell loop, or inside the event loop, would be counted here."""
    a, b = raw(fails=2), raw(fails=4)
    records = caught(
        lambda: multi_diff(
            a,
            b,
            events=list(MULTI_EVENTS),
            method="fisher_bh",
            manifest_a=manifest("run-a", SALT),
            manifest_b=manifest("run-b", SALT),
        )
    )
    assert len(unpaired_records(records)) == 1, [str(r.message) for r in records]


def test_u7_the_single_event_diff_warns_from_the_same_place() -> None:
    """diff() is the other public entry point and takes the same manifests. It routes through
    _pairing, so there is one predicate rather than two copies that can drift apart."""
    a = censor(raw(fails=2), "fail")
    b = censor(raw(fails=4), "fail")
    records = caught(
        lambda: diff(
            a,
            b,
            event="fail",
            method="fisher_bh",
            manifest_a=manifest("run-a", SALT),
            manifest_b=manifest("run-b", SALT),
        )
    )
    assert len(unpaired_records(records)) == 1, [str(r.message) for r in records]


# ---------- the warning changes nothing ----------


def test_u8_the_warning_never_switches_the_test() -> None:
    """The constraint that makes this a warning and not a default: the same command on the
    same rows must produce the same statistic whether or not the two runs share a salt. If
    the method were switched on provenance, a reader could not tell which test ran without
    going back to the manifests."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        pairable = multi("fisher_bh")
        unpairable = multi("fisher_bh", salt_b=OTHER_SALT)
    assert pairable.method == unpairable.method == "fisher_bh"
    for event in EVENTS:
        pd.testing.assert_frame_equal(
            pairable.by_event[event].cells, unpairable.by_event[event].cells
        )


def test_u9_the_headline_states_the_request_and_seed_identity_is_a_field_beside_it() -> None:
    """**Inverted by P-1 (ADR-052; Master Action List C1).** Until P-1 this test pinned the
    defect: the headline printed ``paired`` next to the method that discarded the pairing, and
    this docstring called that something a reader could see. It was a fact about the *runs*
    printed where the reader reads about the *analysis*. Now the headline's last token is the
    requested method's pairing -- ``unpaired`` for ``fisher_bh`` however the runs were produced --
    and the runs' seed identity is a field, ``seed_identity_match``, with ``unpaired_analysis``
    beside it saying the identity was there and the request discarded it. The warning is the
    same fact a third time, on stderr, for the reader who reads nothing else."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        result = multi("fisher_bh")
    assert result.seed_identity_match is True and result.unpaired_analysis is True
    assert "fisher_bh" in result.headline() and result.headline().endswith("unpaired)")


def test_u10_unpaired_analysis_is_a_user_warning() -> None:
    """A CI that already spells ``-W error::UserWarning`` catches this without being told
    about a new name; one that wants only this gate spells the qualified name."""
    assert issubclass(UnpairedAnalysis, UserWarning)


def test_u11_the_warning_points_at_the_callers_line() -> None:
    """stacklevel is the difference between a warning a reader can act on and one that points
    at library internals. It must name the file that called multi_diff -- this one."""
    records = unpaired_records(caught(lambda: multi("fisher_bh")))
    assert records[0].filename == __file__, records[0].filename


def test_u12_the_message_names_the_method_and_the_alternative() -> None:
    """Containment, not an exact string: the wording stays the implementer's. What a reader
    has to be able to act on is which method ran and which one to pass instead."""
    message = str(unpaired_records(caught(lambda: multi("fisher_bh")))[0].message)
    assert "fisher_bh" in message and "mcnemar_bh" in message


# ---------- where it is built ----------


def test_u13_every_method_either_refuses_or_warns() -> None:
    """The refusal and the warning are one predicate seen from its two sides, so every method
    in the public Method literal must land on exactly one side: it needs pairing and refuses
    without it, or it discards pairing and warns when there was some. A method added to the
    literal and to neither branch fails here."""
    for method in get_args(Method):
        try:
            refuses = False
            caught(lambda m=method: multi(m, salt_b=OTHER_SALT))  # type: ignore[misc]
        except NotPairable:
            refuses = True
        warns = bool(unpaired_records(caught(lambda m=method: multi(m))))  # type: ignore[misc]
        assert refuses != warns, (method, refuses, warns)


def test_u14_the_cli_raises_no_warning_of_its_own() -> None:
    """cli.py computes nothing and decides nothing statistical. Which test to run is a
    statistical decision, so the module that renders results must not be the module that
    raises this. Read from src/ rather than reviewed."""
    tree = ast.parse((SRC / "cli.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "warn"
    ]
    assert calls == [], [node.lineno for node in calls]


def test_u15_only_m6_names_the_category() -> None:
    """One source for the decision. Any other module under src/ naming UnpairedAnalysis is a
    second place the rule could be applied, or applied differently."""
    named = sorted(
        path.name
        for path in SRC.glob("*.py")
        if "UnpairedAnalysis" in path.read_text(encoding="utf-8")
    )
    assert named == ["diff.py"], named


def test_u16_a_cli_diff_warns_and_the_artifact_is_unchanged_by_it(tmp_path: Path) -> None:
    """End to end: the CLI's diff on a pairable pair raises the warning, and the warning is
    out of band: nothing it says reaches the streams the CLI was given, and ``mcnemar_bh`` is
    named on neither. **Narrowed by P-1.** This docstring once said the bytes a reader tees to a
    file do not depend on whether two runs shared a salt; that was already false of
    ``to_markdown()``'s ``paired=True`` and is now deliberately false of
    ``seed_identity_match=True, unpaired_analysis=True`` (C24: the fact reaches every artifact).
    What still holds, and what this pins, is that the warning's own sentence stays off the
    streams and the CLI names the alternative method nowhere (U14)."""
    store = Store(tmp_path)
    write_run(store, "run-a", SALT, fails=2)
    write_run(store, "run-b", SALT, fails=4)
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the pair shares a salt, so the default is now the paired
    # test, which raises no warning; the warning this pins is the unpaired test's, named.
    argv = ["--store", str(tmp_path), "diff", "run-a", "run-b", "--event", "fail", "--method", "fisher_bh"]
    box: list[Result] = []
    caught(lambda: box.append(run_cli(argv)))
    result = box[0]
    # The warning now reaches the CLI's own stderr as one note line, whose wording is the warning's
    # (front-door spec section 5.4); outside that line the CLI still names the alternative nowhere.
    notes = [line for line in result.err.splitlines() if line.startswith("note: ")]
    assert len(notes) == 1, result.err
    assert result.code == 0, result.err
    rest = "".join(line for line in result.err.splitlines(keepends=True) if not line.startswith("note: "))
    assert "mcnemar_bh" not in result.out + rest, result.out + rest
