"""Defaults, refusals and faces of the command line and the core's views, each pinned by its
facts: the paired rows' discordant pair counts; the events a comparison defaults to
when the runs declare failures and successes; a refusal's suggested event; plan-time refusals for
an unknown fault and the name of a missing instrumentor; the store a sweep's next lines keep; the
next line of a missing ``--x``; ``paired``'s refusal with no eligible pair and its run names;
``inspect --limit 0``; ``init``'s template and help; pairing and a mixed pair's older writer in the
views; and the missing capture limit's refusal as one paragraph.

Every sweep here is the packaged mock agent at a few replicates with ``--max-mde 1``, so nothing
waits on the design gate and the module's stores build in a few seconds."""

from __future__ import annotations

import json
import re
import shlex
import shutil
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

import poisson_prove
from poisson_prove import cli, core
from poisson_prove.episode import Episode
from poisson_prove.executor import derive_seed
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.trace import Span, Trace

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PACKAGED = Path(poisson_prove.__file__).resolve().parent / "examples" / "quickstart.toml"
MOCK = "poisson_prove.examples.mock_agent"
REPLICATES = "30"
SALT = "c0ffee00d15ea5e5"


def run(argv: list[str]) -> tuple[int, str, str]:
    """``poisson-prove ARGV`` in this process: the exit code, stdout and stderr."""
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def spec_text(declare: str | None) -> str:
    """The packaged quickstart spec with its ``[declare]`` table replaced (or removed)."""
    text = PACKAGED.read_text(encoding="utf-8")
    text = re.sub(r"(?ms)^\[declare\].*?(?=^\[|\Z)", "", text).rstrip() + "\n"
    return text + (f"\n[declare]\n{declare}\n" if declare else "")


def sweep_pair(root: Path, spec: Path) -> tuple[str, str]:
    """A baseline and a patched run paired on one salt; their run ids, oldest first."""
    store = root / "store"
    first = ["--store", str(store), "sweep", str(spec), "--yes", "--replicates", REPLICATES, "--max-mde", "1", "--salt", SALT]
    assert run(first)[0] == 0
    (a,) = Store(store).runs()
    second = ["--store", str(store), "sweep", str(spec), "--yes", "--max-mde", "1",
              "--target", f"{MOCK}:rollout_patched", "--pair-with", a]
    code, out, err = run(second)
    assert code == 0, out + err
    (b,) = set(Store(store).runs()) - {a}
    return a, b


@pytest.fixture(scope="module")
def declared(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """A paired pair whose spec declares ``violated`` alone a failure (not ``timeout``)."""
    root = tmp_path_factory.mktemp("declared")
    spec = root / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]'), encoding="utf-8")
    a, b = sweep_pair(root, spec)
    return root / "store", a, b


@pytest.fixture(scope="module")
def undeclared(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """The same pair with no ``[declare]`` table."""
    root = tmp_path_factory.mktemp("undeclared")
    spec = root / "prove.toml"
    spec.write_text(spec_text(None), encoding="utf-8")
    a, b = sweep_pair(root, spec)
    return root / "store", a, b


def discordant(store: Path, a: str, b: str, event: str) -> dict[str, tuple[int, int]]:
    """Per condition, from the stored outcomes: pairs where only the after run had the event, and
    where only the before run had it, joined on the replicate."""
    frames = {run_id: Store(store).read(run_id, meta=False) for run_id in (a, b)}
    out = {}
    for h, before in frames[a].groupby("config_hash"):
        after = frames[b][frames[b]["config_hash"] == h]
        joined = pd.merge(before[["replicate_index", "outcome"]], after[["replicate_index", "outcome"]],
                          on="replicate_index", suffixes=("_a", "_b"))
        had_a, had_b = joined["outcome_a"] == event, joined["outcome_b"] == event
        out[str(h)] = (int((~had_a & had_b).sum()), int((had_a & ~had_b).sum()))
    return out


# ---------- the paired rows' discordant pair counts ----------


def test_the_paired_rows_carry_n01_and_n10_the_stored_pairs_give_and_the_unpaired_rows_carry_none(declared: tuple[Path, str, str]) -> None:
    store, a, b = declared
    code, out, err = run(["--store", str(store), "diff", a, b, "--event", "violated", "--event", "timeout", "--json", "--save"])
    assert code == 0, err
    doc = json.loads(out)
    assert doc["method"] == "mcnemar_bh"
    for event in ("violated", "timeout"):
        expected = discordant(store, a, b, event)
        cells = doc["by_event"][event]["cells"]
        assert {c["config_hash"]: (c["n01"], c["n10"]) for c in cells} == expected, event
        for c in cells:
            assert c["n01"] + c["n10"] <= c["pairs"] and isinstance(c["n01"], int)
    assert any(n01 != n10 for n01, n10 in discordant(store, a, b, "violated").values()), "the fixture must tell the two apart"
    # The comparison this diff saved, by the id its saved line names (other tests save into this store too).
    code, out, err = run(["--store", str(store), "diff", a, b, "--event", "violated", "--event", "timeout", "--save"])
    assert code == 0, err
    (cid,) = [line.split()[-1] for line in out.splitlines() if line.startswith("  saved  comparison ")]
    (saved,) = [ref for ref in core.artifacts(core.open_store(str(store))) if ref.kind == "comparison" and ref.id.startswith(cid)]
    result = json.loads((store / saved.path / "comparison.json").read_text(encoding="utf-8"))
    assert {c["config_hash"]: (c["n01"], c["n10"]) for c in result["by_event"]["violated"]["cells"]} == discordant(store, a, b, "violated")
    code, out, err = run(["--store", str(store), "diff", a, b, "--event", "violated", "--json", "--method", "fisher_bh"])
    assert code == 0, err
    assert all(c["n01"] is None and c["n10"] is None for c in json.loads(out)["by_event"]["violated"]["cells"])


# ---------- the events a comparison defaults to ----------


def test_diff_and_report_default_to_the_declared_failures_and_say_so(declared: tuple[Path, str, str], tmp_path: Path) -> None:
    store, a, b = declared
    code, out, err = run(["--store", str(store), "diff", a, b, "--json"])
    assert code == 0, err
    doc = json.loads(out)
    assert doc["events"] == ["violated"] and doc["inferred"] is True and doc["non_event"] is None
    code, out, err = run(["--store", str(store), "diff", a, b])
    assert code == 0, err
    assert "inferred: no event was given, so the event set is violated, the failures and successes the runs declared" in out.splitlines()
    code, out, err = run(["--store", str(store), "report", a, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(tmp_path / "one"), "--json"])
    assert code == 0, err
    assert json.loads(out)["events"] == ["violated"]


def test_the_declared_set_is_the_failures_then_the_successes(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]\nsuccesses = ["completed"]'), encoding="utf-8")
    a, b = sweep_pair(tmp_path, spec)
    code, out, err = run(["--store", str(tmp_path / "store"), "diff", a, b, "--json"])
    assert code == 0, err
    doc = json.loads(out)
    assert doc["events"] == ["violated", "completed"] and doc["non_event"] is None
    assert (doc["by_event"]["violated"]["kind"], doc["by_event"]["completed"]["kind"]) == ("failure", "success")


def test_runs_that_declare_no_kinds_still_infer_every_outcome_but_the_commonest(undeclared: tuple[Path, str, str]) -> None:
    store, a, b = undeclared
    code, out, err = run(["--store", str(store), "diff", a, b, "--json"])
    assert code == 0, err
    doc = json.loads(out)
    frames = pd.concat([Store(store).read(r, meta=False) for r in (a, b)])
    counts = frames["outcome"].value_counts()
    assert doc["non_event"] == counts.index[0] and set(doc["events"]) == set(counts.index[1:])


def test_serve_shows_the_declared_events_and_still_refuses_without_an_event_where_none_is_declared(
    declared: tuple[Path, str, str], undeclared: tuple[Path, str, str]
) -> None:
    store, a, b = declared
    code, out, err = run(["--store", str(store), "serve", a, b, "--x", "task_id", "--y", "tool_fail_rate", "--json"])
    assert code == 0, err
    assert json.loads(out)["diff"]["events"] == ["violated"]
    store, a, b = undeclared
    code, out, err = run(["--store", str(store), "serve", a, b, "--x", "task_id", "--y", "tool_fail_rate", "--json"])
    assert code == 1 and "--event" in err, (code, err)


def test_a_missing_event_refusal_suggests_a_declared_failure_else_an_outcome_other_than_the_commonest(
    declared: tuple[Path, str, str], undeclared: tuple[Path, str, str]
) -> None:
    store, a, b = declared
    code, _, err = run(["--store", str(store), "check", a, b])
    assert code == 1
    assert [line for line in err.splitlines() if line.startswith("  next: ")][-1].endswith("--event violated"), err
    store, a, b = undeclared
    code, _, err = run(["--store", str(store), "check", a, b])
    commonest = pd.concat([Store(store).read(r, meta=False) for r in (a, b)])["outcome"].value_counts().index[0]
    suggested = shlex.split([line for line in err.splitlines() if line.startswith("  next: ")][-1])[-1]
    assert code == 1 and suggested != commonest, err


# ---------- the plan ----------


def test_an_unknown_fault_is_refused_when_the_sweep_is_planned_and_nothing_is_written(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]') + '\n[chaos]\nfault = "not_a_fault"\n', encoding="utf-8")
    store = tmp_path / "store"
    for extra in (["--dry-run"], ["--yes"]):
        code, out, err = run(["--store", str(store), "sweep", str(spec), "--max-mde", "1", *extra])
        assert code == 1, (extra, out, err)
        assert not out.startswith("plan  "), out
        error = [line for line in err.splitlines() if line.startswith("error: ")]
        assert len(error) == 1 and '"not_a_fault"' in error[0] and "tool_error_single" in error[0], err
        assert not store.exists() or not Store(store).runs()


def test_a_missing_instrumentor_is_named_on_the_plan_and_on_the_done_line(tmp_path: Path) -> None:
    pytest.importorskip("opentelemetry.sdk")
    spec = tmp_path / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]')
                    + '\n[capture]\ninstrument = ["no_such_instrumentor"]\nmax_observation_bytes = 1024\n', encoding="utf-8")
    store = tmp_path / "store"
    code, out, err = run(["--store", str(store), "sweep", str(spec), "--dry-run", "--replicates", REPLICATES, "--max-mde", "1"])
    assert code == 0, err
    assert '  capture  not installed here: "no_such_instrumentor", so the sweep records no spans from it' in out.splitlines(), out
    code, out, err = run(["--store", str(store), "sweep", str(spec), "--yes", "--replicates", REPLICATES, "--max-mde", "1"])
    assert code == 0, err
    (done,) = [line for line in out.splitlines() if line.startswith("done  ")]
    assert done.endswith('; no spans from "no_such_instrumentor", not installed'), done
    plain = tmp_path / "plain.toml"
    plain.write_text(spec_text('failures = ["violated"]'), encoding="utf-8")
    code, out, err = run(["--store", str(store), "sweep", str(plain), "--dry-run", "--replicates", REPLICATES, "--max-mde", "1"])
    assert code == 0 and "  capture  " not in out, out


def test_a_sweeps_next_lines_keep_the_store_it_was_typed_with(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]'), encoding="utf-8")
    store = tmp_path / "elsewhere"
    code, out, err = run(["--store", str(store), "sweep", str(spec), "--yes", "--replicates", REPLICATES, "--max-mde", "1"])
    assert code == 0, err
    nexts = [shlex.split(line) for line in out.splitlines() if line.startswith("  next: ")]
    assert nexts and all(words[-2:] == ["--store", str(store)] for words in nexts), nexts
    code, out, err = run(["sweep", str(spec), "--yes", "--max-mde", "1", "--target", f"{MOCK}:rollout_patched",
                          "--pair-with", "latest", "--store", str(store)])
    assert code == 0, err
    assert f"  next: poisson-prove diff --store {store}" in out.splitlines(), out


def test_a_missing_x_suggests_a_command_that_places_every_axis(declared: tuple[Path, str, str]) -> None:
    store, a, b = declared
    for verb in (["report", a, b], ["serve", a, b, "--event", "violated"]):
        code, _, err = run(["--store", str(store), *verb])
        assert code == 1
        words = shlex.split([line for line in err.splitlines() if line.startswith("  next: ")][-1])
        assert words[words.index("--x") + 1] == "task_id" and words[words.index("--y") + 1] == "tool_fail_rate", words


# ---------- paired ----------


def _record(run_id: str, item: str, temperature: str) -> EpisodeRecord:
    body = f'{{"model": "grader-1", "state": "{item}", "temperature": {temperature}}}'
    span = Span(span_id="0000000000000001", parent_id=None, kind="http", name="grader.request",
                start_ns=1_790_000_000_000_000_000, end_ns=1_790_000_000_000_500_000, input=body, output="{}",
                tokens={"in": 10, "out": 1}, attrs={"url.full": "https://api.example.test/v1", "http.request.method": "POST"})
    config = {"answer": item, "rubric": "r1"}
    meta = {"trace": Trace(spans=(span,), source="record").to_dict(), "grade": {"score": "0.75"}}
    return EpisodeRecord.from_episode(
        Episode(outcome="graded", t=1.0, horizon=10.0, meta=meta), run_id=run_id, config=config,
        seed=derive_seed(SALT, config_hash(config), 0), replicate_index=0, wall_time=0.1,
    )


def _paired_store(root: Path, temperatures: tuple[str, str]) -> Path:
    store = Store(root)
    for run_id, temperature in zip(("grade-a-run", "grade-b-run"), temperatures, strict=True):
        store.create_run(RunManifest(
            run_id=run_id, target_id="grader", t_unit="steps", run_salt=SALT,
            axis_types={"answer": "categorical", "rubric": "categorical"}, backend="local",
            environment={"python": "3.11.7", "platform": "test", "poisson_prove_version": poisson_prove.__version__,
                         "capture": {"content": True, "max_observation_bytes": "none"}},
        ))
        store.append(run_id, [_record(run_id, f"answer-{i}", temperature) for i in range(6)])
        store.mark_complete(run_id)
    return root


def _declaration(path: Path, a: str, b: str) -> Path:
    path.write_text(
        'value_key = "grade.score"\ncluster_key = "answer"\nstratum_key = "rubric"\nrequest_span = "grader.request"\n'
        'model_key = "model"\nmodel_pin = "grader-1"\nexemptions = []\nheaders = "not_recorded"\nretries = "not_recorded"\n'
        'bootstrap_b = 200\nbootstrap_seed = 7\n\n[[cuts]]\nname = "pass"\nthreshold = 0.60\ncomparison = "ge"\n\n'
        f'[[sweeps]]\nname = "replay"\na = "{a}"\nb = "{b}"\n',
        encoding="utf-8",
    )
    return path


def test_paired_refuses_a_declaration_with_no_eligible_pair_and_writes_nothing(tmp_path: Path) -> None:
    root = _paired_store(tmp_path / "store", ("0.30", "0.90"))
    decl = _declaration(tmp_path / "replay.toml", "grade-a-run", "grade-b-run")
    out_dir = tmp_path / "out"
    code, out, err = run(["--store", str(root), "paired", "--declaration", str(decl), "--out", str(out_dir)])
    assert code == 1, (out, err)
    assert err.startswith("error: no eligible pairs: ") and "nothing was written" in err, err
    assert not out_dir.exists()


def test_paired_takes_an_arm_by_its_runs_name_as_by_its_id(tmp_path: Path) -> None:
    root = _paired_store(tmp_path / "store", ("0.30", "0.30"))
    names = {entry["run_id"]: entry["run_name"] for entry in json.loads(run(["--store", str(root), "runs", "--json"])[1])["runs"]}
    by_id = _declaration(tmp_path / "ids.toml", "grade-a-run", "grade-b-run")
    by_name = _declaration(tmp_path / "names.toml", names["grade-a-run"], names["grade-b-run"])
    outs = []
    for decl in (by_id, by_name):
        code, out, err = run(["--store", str(root), "paired", "--declaration", str(decl), "--json"])
        assert code == 0, err
        outs.append(json.loads(out))
    # The names resolve to the same runs, so the declaration, its digest and every file are the same.
    assert outs[0] == outs[1]
    assert outs[0]["pair_assertion"]["counts"]["total"]["eligible"] == 6


# ---------- inspect, init ----------


def test_inspect_refuses_a_limit_below_one(declared: tuple[Path, str, str]) -> None:
    store, a, _ = declared
    for limit in ("0", "-2"):
        code, out, err = run(["--store", str(store), "inspect", a, "--event", "violated", "--limit", limit])
        assert code == 2 and out == "", (limit, out, err)
        assert err.splitlines()[0] == f"error: --limit must be 1 or more, got {limit}", err


def test_inits_template_carries_a_commented_declare_table_and_its_help_line_names_agent(tmp_path: Path) -> None:
    code, out, err = run(["init", "--target", "pkg.mod:rollout", "--out", str(tmp_path / "prove.toml")])
    assert code == 0, err
    text = (tmp_path / "prove.toml").read_text(encoding="utf-8")
    assert "# [declare]" in text and "# failures = [" in text and "# successes = [" in text
    import tomllib

    assert "declare" not in tomllib.loads(text), "the table stays commented until the outcomes are the user's"
    code, out, _ = run(["--help"])
    init_line = " ".join(out.split("  init ", 1)[1].split("\n  sweep", 1)[0].split())
    assert code == 0 and "--agent" in init_line, init_line


# ---------- the views ----------


def test_the_run_view_names_the_run_it_shares_its_seeds_with_and_the_runs_view_carries_each_salt(declared: tuple[Path, str, str]) -> None:
    store, a, b = declared
    opened = core.open_store(str(store))
    runs = {row["run_id"]: row for row in core.view(opened, "index.html").document["runs"]}
    assert runs[a]["run_salt"] == runs[b]["run_salt"] == SALT
    after = core.view(opened, f"runs/{b}.html").document
    assert after["paired_with"] == a and after["paired_with_name"] == runs[a]["name"]
    assert core.view(opened, f"runs/{a}.html").document["paired_with"] is None


def test_a_third_run_on_the_same_seeds_is_paired_with_the_newest_run_before_it(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]'), encoding="utf-8")
    a, b = sweep_pair(tmp_path, spec)
    store = tmp_path / "store"
    code, out, err = run(["--store", str(store), "sweep", str(spec), "--yes", "--max-mde", "1", "--pair-with", b])
    assert code == 0, err
    (c,) = set(Store(store).runs()) - {a, b}
    assert core.view(core.open_store(str(store)), f"runs/{c}.html").document["paired_with"] == b


def test_a_mixed_pairs_comparison_view_carries_the_older_writer_on_that_run_alone(tmp_path: Path) -> None:
    store = tmp_path / "store"
    shutil.copytree(FIXTURES / "stores-0.0.1" / "store", store)
    old = json.loads((FIXTURES / "stores-0.0.1" / "runs.json").read_text(encoding="utf-8"))["quickstart_before"]
    code, out, err = run(["--store", str(store), "sweep", str(PACKAGED), "--yes", "--max-mde", "1", "--pair-with", old])
    assert code == 0, err
    (new,) = set(Store(store).runs()) - set(json.loads((FIXTURES / "stores-0.0.1" / "runs.json").read_text(encoding="utf-8")).values())
    code, out, err = run(["--store", str(store), "diff", old, new, "--save"])
    assert code == 0, err
    opened = core.open_store(str(store))
    (saved,) = [ref for ref in core.artifacts(opened) if ref.kind == "comparison"]
    doc = core.view(opened, f"comparisons/{saved.id}.html").document
    assert doc["before"]["writer"] == "written by proofload 0.0.1"
    assert "writer" not in doc["after"]


# ---------- the capture limit's refusal ----------


def test_the_missing_capture_limit_is_refused_in_one_paragraph_with_its_values_as_typed(tmp_path: Path) -> None:
    pytest.importorskip("opentelemetry.sdk")
    spec = tmp_path / "prove.toml"
    spec.write_text(spec_text('failures = ["violated"]') + "\n[capture]\ninstrument = []\n", encoding="utf-8")
    code, out, err = run(["--store", str(tmp_path / "store"), "sweep", str(spec), "--dry-run"])
    assert code == 1, (out, err)
    (line,) = err.splitlines()
    assert line.startswith("error: [capture].max_observation_bytes is required and has no default. It is ")
    assert ".;" not in line and "before this change" not in line
    for typed in ('"max_observation_bytes = 64"', '"max_observation_bytes = 1024"', '"max_observation_bytes = 8192"'):
        assert typed in line, typed
