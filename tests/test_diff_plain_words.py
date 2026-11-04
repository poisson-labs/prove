"""``diff`` reads in plain words by default: the verdict block, then one table of the conditions in
the order of their axis values. The machine sections are behind ``--full``, and ``--json`` is as it
was.

**What is pinned.** The real command over stores real sweeps wrote (``reading_support``), in the plain
rendering, each fact compared with what ``--json`` says of the same comparison.

**Readings this file fixes.**

- **r1** The flag is ``--full``. It prints what ``diff`` printed before this change, in that order.
- **r2** The table's columns are ``condition``, ``event``, ``before``, ``after``, ``change``,
  ``verdict``, ``rise``, ``fall``: the terminal app's conditions screen without its ``p`` and ``q``.
  ``before`` and ``after`` are each run's share of episodes ending in the event, ``change`` is the
  difference the test reads, ``rise`` and ``fall`` the condition's limits or the reason it has none.
- **r3** There is one table, with a row per condition and event. Rows are ordered by the condition,
  then by the event in the order the verdict line names them, so what one condition did stays on
  adjacent rows.
- **r4** Axis values order numbers as numbers and words alphabetically, the first axis printed first.
  Declared order is not used: two runs may declare a different one.
- **r5** The options that shape a machine section (``--by``, ``--depth``, ``--permutations``,
  ``--seed``, ``--max-group-mde``) ask for it by name, so they print the full output. ``--methods all``
  prints its table of methods either way.
- **r6** What the machine sections warn of stays in the default, in words: conditions one run lacks,
  episodes with no outcome, episodes the comparison cut at its horizon.
- **r7** The default says the flag exists, in the text only: ``next`` is the same in the text and in
  ``--json``, and the JSON does not change.
- **r8** The ``limits`` line counts the rows with no limit by direction, since a row with no limit on
  its fall still has one on its rise. "No change of any size" is said only of a row with neither.
- **r9** The line that says which events were inferred stays in the default: it is a plain sentence,
  it says what was compared, and it is not one of the machine sections.
- **r10** This change moves output another tool reads, so it ships as the next minor, 0.2.0, and the
  CHANGELOG says so. ``truncated`` stays a field of ``--json``, the route a reader moves to.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pf6_support import run_pty, strip_escapes
from reading_support import QS_A, QS_B, cli, doc, reading_world, split_row, words_of  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "reading" / "diff-quickstart.json"
COLUMNS = ["condition", "event", "before", "after", "change", "verdict", "rise", "fall"]
NEVER_DEFAULT = (
    r"\bmethod=", r"seed_identity_match", r"\btruncated=", r"^## ", r"config_hash", r"\bn_(safer|worse|higher|lower|unchanged)=", r"max_mde",
    r"alpha\*", r"^omnibus:", r"^fault lines:", r"^cells:", r"^bound:", r"^coverage:", r"^intervals:", r"^\|", r"aalen_johansen",
    r"BH q<", r"\bholes=",
)
#: Every machine section, in the order ``diff`` has always printed them.
FULL_SECTIONS = (
    r"^method=", r"^## (timeout|violated): n_\w+=", r"^coverage: holes=", r"^## coverage$", r"^intervals: ", r"^omnibus: ",
    r"^fault lines: ", r"^cells: ", r"^bound: ",
)
#: Each store and the runs its comparison names; every store is read through its default pair.
PAIRS = {
    "kinds": (),
    "old": (QS_A, QS_B),
    "order": (),
    "holes": (),
    "no_outcome": (),
    "cut": (),
    "small": (),
    "both_ways": (),
    "one_limit": (),
    "at_the_ends": (),
}


def _diff(world: dict[str, Path], name: str, *more: str) -> Any:
    return cli(world[name], "diff", *PAIRS[name], *more)


def _json(world: dict[str, Path], name: str, *more: str) -> dict[str, Any]:
    result = _diff(world, name, "--json", *more)
    assert result.code == 0, result.err
    return doc(result)


def _table(out: str) -> tuple[list[str], list[list[str]]]:
    """The table's header and rows: from the line that opens with its first two columns to the next
    blank line."""
    lines = out.splitlines()
    at = next((i for i, line in enumerate(lines) if split_row(line)[:2] == COLUMNS[:2]), None)
    assert at is not None, out[:1500]
    rows = []
    for line in lines[at + 1:]:
        if not line.strip():
            break
        rows.append(split_row(line))
    return split_row(lines[at]), rows


def _cells(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for event, entry in document["by_event"].items():
        for cell in entry["cells"]:
            yield event, cell


def _limits_clause(out: str) -> str:
    """What the ``limits`` line adds after its first sentence: the rows with no limit."""
    line = next(line for line in out.splitlines() if line.startswith("  limits  "))
    return line.split(";", 1)[1] if ";" in line else ""


def _no_limit(document: dict[str, Any]) -> tuple[int, int, int]:
    """The rows that did not count with no limit: on the fall alone, on the rise alone, on both. A
    direction with no room to move is not one with no limit."""
    fall, rise, both = 0, 0, 0
    for _, cell in _cells(document):
        if cell["holm"]:
            continue
        no_rise = cell["mde_rise"] is None and cell["mde_rise_note"] != "no room"
        no_fall = cell["mde_fall"] is None and cell["mde_fall_note"] != "no room"
        fall += no_fall and not no_rise
        rise += no_rise and not no_fall
        both += no_rise and no_fall
    return fall, rise, both


# ---------- the default: the verdict block, then the table ----------


@pytest.mark.parametrize("name", sorted(PAIRS))
def test_the_default_opens_on_the_verdict_and_ends_on_next(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, name)
    document = _json(reading_world, name)
    assert result.code == 0, result.err
    lines = result.out.splitlines()
    assert lines[0] == f"{document['verdict']}  {document['sentence']}", lines[0]
    nexts = [line for line in lines if line.startswith("  next: ")]
    assert nexts == [f"  next: {command}" for command in document["next"]], nexts
    assert lines[-len(nexts):] == nexts, lines[-4:]


@pytest.mark.parametrize("name", sorted(PAIRS))
def test_no_machine_section_in_the_default(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, name)
    found = [marker for marker in NEVER_DEFAULT if re.search(marker, result.out, flags=re.MULTILINE)]
    assert found == [], (found, result.out[:800])


@pytest.mark.parametrize("method", ["fisher_bh", "logrank_bh"])
def test_no_machine_section_under_the_other_methods(method: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, "kinds", "--method", method)
    assert result.code == 0, result.err
    assert _table(result.out)[0] == COLUMNS
    found = [marker for marker in NEVER_DEFAULT if re.search(marker, result.out, flags=re.MULTILINE)]
    assert found == [], (found, result.out[:800])


def test_the_default_says_the_verdict_and_the_method_once(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """Before this change the verdict's counts and the method were each printed twice, in two forms."""
    result = _diff(reading_world, "kinds")
    document = _json(reading_world, "kinds")
    counts = document["headline"].splitlines()[0]
    assert result.out.count(counts) == 1, result.out[:800]
    assert sum(line.startswith("  method  ") for line in result.out.splitlines()) == 1
    assert "(aalen_johansen" not in result.out


def test_the_default_says_which_events_it_inferred(reading_world: dict[str, Path]) -> None:  # noqa: F811
    inferred = [line for line in _diff(reading_world, "kinds").out.splitlines() if line.startswith("inferred: ")]
    assert len(inferred) == 1, inferred
    assert not [line for line in _diff(reading_world, "kinds", "--event", "violated").out.splitlines() if line.startswith("inferred: ")]


def test_the_default_is_short_enough_to_read(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """The verdict block, the inference line, the table, a line naming the flag, the next line and the
    blank lines between them: the machine sections ran to about 100 more."""
    result = _diff(reading_world, "kinds")
    _, rows = _table(result.out)
    block = result.out.split("\n\n", 1)[0].splitlines()
    assert len(result.out.splitlines()) <= len(block) + len(rows) + 1 + 8, result.out


def test_the_table_has_its_columns_in_order(reading_world: dict[str, Path]) -> None:  # noqa: F811
    assert _table(_diff(reading_world, "kinds").out)[0] == COLUMNS


@pytest.mark.parametrize("name", ["kinds", "old", "order", "both_ways"])
def test_each_row_says_what_the_comparison_says(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    """Every condition and event once, each cell the comparison's own fact, each number as rule 10
    prints it."""
    _, rows = _table(_diff(reading_world, name).out)
    want = {(words_of(cell["config"]), event): cell for event, cell in _cells(_json(reading_world, name))}
    assert len(rows) == len(want), rows
    seen = set()
    for row in rows:
        assert len(row) == len(COLUMNS), row
        fields = dict(zip(COLUMNS, row, strict=True))
        cell = want[(fields["condition"], fields["event"])]
        seen.add((fields["condition"], fields["event"]))
        assert re.fullmatch(r"\d\.\d{3}", fields["before"]), row
        assert fields["before"] == f"{cell['share_a']['value']:.3f}", (row, cell["share_a"])
        assert fields["after"] == f"{cell['share_b']['value']:.3f}", (row, cell["share_b"])
        assert float(fields["change"]) == pytest.approx(cell["delta"], abs=0.0005), (row, cell["delta"])
        assert fields["verdict"] == cell["verdict"], row
        for side in ("rise", "fall"):
            value, note = cell[f"mde_{side}"], cell[f"mde_{side}_note"]
            assert fields[side] == (note if value is None else f"{value:.3f}"), (row, side, value, note)
    assert seen == set(want)


def test_the_condition_column_prints_the_axes_not_the_json(reading_world: dict[str, Path]) -> None:  # noqa: F811
    _, rows = _table(_diff(reading_world, "kinds").out)
    assert all(row[0].startswith("task_id ") and " · tool_fail_rate " in row[0] for row in rows), rows[:3]
    assert not any("{" in row[0] for row in rows)


# ---------- the order of the rows ----------


def test_rows_are_ordered_by_axis_values_numbers_as_numbers(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """Numbers ascending as numbers (2 before 10, -1 first), words alphabetically, the first axis
    printed first; neither the comparison's own order nor the text's would give this."""
    document = _json(reading_world, "order")
    _, rows = _table(_diff(reading_world, "order").out)
    config = {words_of(cell["config"]): cell["config"] for _, cell in _cells(document)}
    shown = [config[row[0]] for row in rows]
    axes = list(shown[0])
    assert shown == sorted(shown, key=lambda c: tuple(c[axis] for axis in axes)), [row[0] for row in rows]
    load = [c["load"] for c in shown]
    assert load[0] == -1 and load[-1] == 10 and load.index(2) < load.index(10), load
    # The fixture tells the orders apart.
    as_text = sorted(config)
    as_stored = [words_of(cell["config"]) for _, cell in _cells(document)]
    assert [row[0] for row in rows] not in (as_text, as_stored), rows


@pytest.mark.parametrize("name", ["kinds", "old"])
def test_a_conditions_events_are_adjacent_in_the_order_the_verdict_names_them(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    document = _json(reading_world, name)
    _, rows = _table(_diff(reading_world, name).out)
    events = sorted(document["by_event"], key=document["sentence"].find)
    assert len(events) == 2, events
    for first, second in zip(rows[0::2], rows[1::2], strict=True):
        assert first[0] == second[0], (first, second)
        assert [first[1], second[1]] == events, (first, second)


# ---------- what the machine sections warn of stays, in words ----------


def test_conditions_one_run_lacks_are_said_in_words(reading_world: dict[str, Path]) -> None:  # noqa: F811
    document = _json(reading_world, "holes")
    assert document["n_not_comparable"] == 1
    result = _diff(reading_world, "holes")
    _, rows = _table(result.out)
    assert len(rows) == document["n_tests"], rows
    said = [line for line in result.out.splitlines() if re.search(r"\b1 condition\b", line) and "compared" in line]
    assert len(said) == 1, result.out


def test_a_comparison_with_no_holes_says_nothing_of_them(reading_world: dict[str, Path]) -> None:  # noqa: F811
    assert "not compared" not in _diff(reading_world, "kinds").out


def test_episodes_with_no_outcome_are_said_in_words(reading_world: dict[str, Path]) -> None:  # noqa: F811
    document = _json(reading_world, "no_outcome")
    before = sum(row["no_outcome_a"] for row in document["coverage"])
    after = sum(row["no_outcome_b"] for row in document["coverage"])
    assert before > 0 and after > 0, (before, after)
    said = [line for line in _diff(reading_world, "no_outcome").out.splitlines() if "no outcome" in line]
    assert len(said) == 1, said
    assert re.search(rf"\b{before}\b", said[0]) and re.search(rf"\b{after}\b", said[0]), said


def test_episodes_the_comparison_cut_are_said_in_words(reading_world: dict[str, Path]) -> None:  # noqa: F811
    document = _json(reading_world, "cut")
    assert document["truncated"] > 0, document["truncated"]
    said = [line for line in _diff(reading_world, "cut").out.splitlines() if "horizon" in line]
    assert len(said) == 1, said
    assert re.search(rf"\b{document['truncated']}\b", said[0]), said


def test_a_comparison_that_cut_nothing_says_nothing_of_it(reading_world: dict[str, Path]) -> None:  # noqa: F811
    assert _json(reading_world, "kinds")["truncated"] == 0
    assert "horizon" not in _diff(reading_world, "kinds").out


# ---------- the limits line ----------


@pytest.mark.parametrize("name", ["kinds", "old"])
def test_rows_with_no_limit_on_their_fall_are_not_said_to_have_no_limit_at_all(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    fall, rise, both = _no_limit(_json(reading_world, name))
    assert fall > 0 and rise == 0 and both == 0, (fall, rise, both)
    clause = _limits_clause(_diff(reading_world, name).out)
    assert re.search(rf"\b{fall}\b[^;]*\bfall\b", clause), clause
    assert not re.search(r"\brise\b", clause), clause
    assert "no change of any size" not in clause, clause
    assert "none detectable" in clause, clause


def test_rows_with_no_limit_each_way_are_counted_each_way(reading_world: dict[str, Path]) -> None:  # noqa: F811
    fall, rise, both = _no_limit(_json(reading_world, "both_ways"))
    assert fall == 1 and rise == 1 and both == 0, (fall, rise, both)
    clause = _limits_clause(_diff(reading_world, "both_ways").out)
    assert re.search(r"\bfall\b", clause) and re.search(r"\brise\b", clause), clause
    assert "no change of any size" not in clause, clause


@pytest.mark.parametrize("name", ["small", "order"])
def test_a_row_with_no_limit_either_way_keeps_the_claim_of_any_size(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    fall, rise, both = _no_limit(_json(reading_world, name))
    assert both > 0 and fall == 0 and rise == 0, (fall, rise, both)
    clause = _limits_clause(_diff(reading_world, name).out)
    assert re.search(rf"\b{both}\b", clause), clause
    assert "no change of any size" in clause, clause


def test_a_direction_with_no_room_is_not_counted_as_one_with_no_limit(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """A rate of 0 cannot fall, and a rate of 1 cannot rise. Such a row has no limit one way only, so
    the claim of any size does not reach it."""
    document = _json(reading_world, "at_the_ends")
    notes = {(cell["mde_rise_note"], cell["mde_fall_note"]) for _, cell in _cells(document)}
    assert any("no room" in pair for pair in notes), notes
    fall, rise, both = _no_limit(document)
    assert both == 0 and fall + rise > 0, (fall, rise, both, notes)
    clause = _limits_clause(_diff(reading_world, "at_the_ends").out)
    assert "no change of any size" not in clause, clause
    for count, word in ((fall, "fall"), (rise, "rise")):
        if count:
            assert re.search(rf"\b{count}\b[^;]*\b{word}\b", clause), clause


def test_the_limits_line_agrees_in_number(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """One row has, several have; the line said "1 row that did not count have"."""
    assert _no_limit(_json(reading_world, "one_limit")) == (1, 0, 0)
    one = _limits_clause(_diff(reading_world, "one_limit").out)
    assert re.search(r"\b1 row\b[^;,]*\bhas\b", one), one
    assert not re.search(r"\bhave\b", one), one
    many = _limits_clause(_diff(reading_world, "old").out)
    assert re.search(r"\b3 rows\b[^;]*\bhave\b", many), many


def test_a_comparison_where_every_row_has_its_limits_adds_no_clause(reading_world: dict[str, Path]) -> None:  # noqa: F811
    assert _no_limit(_json(reading_world, "cut")) == (0, 0, 0)
    assert _limits_clause(_diff(reading_world, "cut").out) == ""


# ---------- the flag ----------


@pytest.mark.parametrize("name", ["kinds", "old", "holes"])
def test_full_prints_every_machine_section_in_the_order_it_always_had(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, name, "--full")
    assert result.code == 0, result.err
    at = -1
    for section in FULL_SECTIONS:
        found = re.search(section, result.out, flags=re.MULTILINE)
        assert found, (section, result.out[:800])
        assert found.start() > at, (section, result.out[:800])
        at = found.start()


def test_full_keeps_the_machine_tables_columns(reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, "kinds", "--full")
    assert "| config_hash | config |" in result.out
    assert "## trades" in result.out
    assert "| config_hash | config | rows_a | rows_b |" in result.out


def test_full_opens_with_the_same_verdict_block_as_the_default(reading_world: dict[str, Path]) -> None:  # noqa: F811
    default = _diff(reading_world, "kinds")
    full = _diff(reading_world, "kinds", "--full")
    assert full.code == default.code == 0
    assert full.out.split("\n\n", 1)[0] == default.out.split("\n\n", 1)[0]


def test_full_ends_on_the_same_next_lines(reading_world: dict[str, Path]) -> None:  # noqa: F811
    default = _diff(reading_world, "kinds").out.splitlines()
    full = _diff(reading_world, "kinds", "--full").out.splitlines()
    assert full[-1] == default[-1] and full[-1].startswith("  next: "), (full[-1], default[-1])


def test_full_still_prints_what_a_reader_of_the_text_looks_for(reading_world: dict[str, Path]) -> None:  # noqa: F811
    for name, want in (("kinds", 0), ("cut", 30)):
        assert _json(reading_world, name)["truncated"] == want
        assert re.search(rf"\btruncated={want}\b", _diff(reading_world, name, "--full").out), name


def test_the_default_says_the_flag_exists_and_full_does_not_repeat_it(reading_world: dict[str, Path]) -> None:  # noqa: F811
    default = _diff(reading_world, "kinds")
    assert "--full" in default.out.split("\n\n", 1)[1], default.out
    assert "--full" not in _diff(reading_world, "kinds", "--full").out


def test_the_help_names_the_flag_and_its_default() -> None:
    result = cli(None, "diff", "--help")
    assert result.code == 0
    usage = " ".join(result.out.split())
    assert "--full" in usage
    assert re.search(r"--full .*?default", usage), usage


@pytest.mark.parametrize(
    ("options", "section"),
    [
        (("--by", "task_id"), r"^fault lines: grouping task_id"),
        (("--depth", "2"), r"^bound: depth 2"),
        (("--permutations", "200"), r"^omnibus: "),
        (("--seed", "7"), r"^omnibus: "),
        (("--max-group-mde", "0.5"), r"^fault lines: "),
    ],
)
def test_an_option_that_shapes_a_machine_section_prints_it(options: tuple[str, ...], section: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, "kinds", *options)
    assert result.code == 0, result.err
    assert re.search(section, result.out, flags=re.MULTILINE), (options, result.out[:800])
    assert re.search(r"^method=", result.out, flags=re.MULTILINE), options


def test_methods_all_prints_its_table_without_the_flag(reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _diff(reading_world, "kinds", "--methods", "all")
    assert result.code == 0, result.err
    assert _table(result.out)[0] == COLUMNS
    for method in ("mcnemar_bh", "fisher_bh", "logrank_bh"):
        assert re.search(rf"^\S*\s*{method}\b", result.out, flags=re.MULTILINE), (method, result.out[-800:])
    assert not re.search(r"^omnibus:", result.out, flags=re.MULTILINE)


def test_save_says_what_it_saved_either_way_and_saves_one_comparison(reading_world: dict[str, Path], tmp_path: Path) -> None:  # noqa: F811
    from pf12_support import copy_store

    store = copy_store(reading_world["kinds"], tmp_path / "prove-runs")
    default = cli(store, "diff", "--save")
    full = cli(store, "diff", "--save", "--full")
    said = [next(line for line in r.out.splitlines() if line.startswith("  saved  ")) for r in (default, full)]
    assert said[0] == said[1], said
    assert len(list((store / ".poisson" / "artifacts" / "comparison").iterdir())) == 1


# ---------- what does not change ----------


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    return value


def test_the_json_document_is_as_it_was(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """The whole document on the committed quickstart pair, against what it was before this change;
    its floats to six places, as libraries differ in the last bits. Key order counts."""
    typed = cli("prove-runs", "diff", QS_A, QS_B, "--json", cwd=reading_world["old"].parent)
    assert typed.code == 0, typed.err
    got = _rounded(doc(typed))
    want = _rounded(json.loads(GOLDEN.read_text(encoding="utf-8")))
    assert json.dumps(got, indent=1) == json.dumps(want, indent=1)


@pytest.mark.parametrize("name", ["kinds", "holes", "cut"])
def test_full_changes_nothing_in_the_json(name: str, reading_world: dict[str, Path]) -> None:  # noqa: F811
    assert _diff(reading_world, name, "--json", "--full").out == _diff(reading_world, name, "--json").out


def test_the_field_a_reader_of_the_text_moves_to_is_in_the_json(reading_world: dict[str, Path]) -> None:  # noqa: F811
    document = _json(reading_world, "kinds")
    assert document["schema"] == "poisson-prove.diff/1"
    assert document["truncated"] == 0


@pytest.mark.parametrize("more", [(), ("--full",), ("--json",)])
def test_an_all_errored_run_is_refused_the_same_way_with_or_without_the_flag(more: tuple[str, ...], reading_world: dict[str, Path]) -> None:  # noqa: F811
    plain = cli(reading_world["one_errored"], "diff")
    result = cli(reading_world["one_errored"], "diff", *more)
    assert result.code == plain.code == 1, result
    assert result.out == "" and result.err == plain.err, result


def test_report_keeps_its_own_output(reading_world: dict[str, Path], tmp_path: Path) -> None:  # noqa: F811
    """The report's text still carries the sections ``diff`` no longer prints by default, and the
    ``--full`` flag is not one of its options."""
    from pf12_support import copy_store

    store = copy_store(reading_world["kinds"], tmp_path / "prove-runs")
    result = cli(store, "report", "--x", "task_id", "--y", "tool_fail_rate", "--out", tmp_path / "out")
    assert result.code == 0, result.err
    assert "--full" not in result.out


# ---------- on a terminal ----------


def test_on_a_terminal_the_default_is_the_same_reading(reading_world: dict[str, Path], tmp_path: Path) -> None:  # noqa: F811
    home = tmp_path / "home"
    home.mkdir()
    run = run_pty(["--store", str(reading_world["kinds"]), "diff"], home=home, cwd=tmp_path, cols=160, rows=60)
    assert run.code == 0, run.err[-400:]
    text = strip_escapes(run.out)
    assert text.split()[0] == _json(reading_world, "kinds")["verdict"]
    for word in COLUMNS:
        assert re.search(rf"\b{word}\b", text), word
    for marker in NEVER_DEFAULT:
        assert not re.search(marker, text, flags=re.MULTILINE), (marker, text[:600])


# ---------- the numbering and the words around it ----------


def _version_of(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("+")[0].split(".")[:3])


def test_the_release_is_the_next_minor() -> None:
    """Output another tool reads moved, so the version is at least 0.2.0, in both version files."""
    from poisson_prove import __version__

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert _version_of(project["version"]) >= (0, 2, 0), project["version"]
    assert _version_of(__version__) >= (0, 2, 0), __version__


def test_the_changelog_says_what_moved_and_what_readers_do() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    found = re.search(r"^## 0\.2\.0 — \d{4}-\d\d-\d\d$(.*?)(?=^## |\Z)", changelog, flags=re.MULTILINE | re.DOTALL)
    assert found, "no entry for 0.2.0"
    entry = found.group(1)
    for word in ("`diff`", "--full", "--json"):
        assert word in entry, (word, entry[:400])


def test_the_diff_page_names_the_flag_and_says_what_is_behind_it() -> None:
    page = (ROOT / "docs" / "commands" / "diff.md").read_text(encoding="utf-8")
    options = page.split("## Options", 1)[1].split("\n## ", 1)[0]
    bullet = next((b for b in options.split("\n- ") if b.startswith("`--full`")), None)
    assert bullet, options[:400]
    for word in ("omnibus", "fault lines", "bound", "coverage"):
        assert word in bullet, (word, bullet)
