"""``inspect`` prints identical errors as one traceback with a count, instead of repeating it for
every episode.

**What is pinned.** The real command over stores real sweeps wrote (``reading_support``), in the plain
rendering. What is expected of the text is worked out from ``--json``, which lists every episode with
its own error and does not change.

**Readings this file fixes.**

- **r1** Identical means the stored error's text, byte for byte. Two tracebacks that differ in a line
  or in a message are two groups, each with its own count.
- **r2** A group's count is every matching episode with that error, after ``--where`` and before
  ``--limit``: ``--limit`` says how many are listed, and the count says how far the same failure goes.
- **r3** Groups come in the order their first episode is stored, so the reproduce snippet, which
  names the first episode, names one on the screen, under the first traceback.
- **r4** Each listed episode under a group takes one line, with its config hash, its config, its seed
  and its replicate. A trace the episode stored stays with it.
- **r5** A group ``--limit`` left no listed episode in is not printed, and its episodes are counted
  in one line, so the output does not read as if the error shown were the only one.
- **r6** An episode that ended in an outcome has no error to group and prints as it always has, and
  so does an error only one episode has: nothing repeats there, and a count of one says nothing.
- **r7** ``--json`` does not change.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pf6_support import run_pty, strip_escapes
from reading_support import QS_B, cli, doc, reading_world  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
TRACEBACK = "Traceback (most recent call last)"
#: The keys of ``inspect --json``, and of each episode in it.
DOCUMENT_KEYS = ["schema", "verdict", "sentence", "run_id", "run_name", "event", "episodes", "reproduce", "next"]
EPISODE_KEYS = ["config_hash", "config", "seed", "replicate_index", "outcome", "t", "error"]


def _inspect(world: dict[str, Path], name: str, event: str, *more: str) -> Any:
    return cli(world[name], "inspect", "latest", "--event", event, *more)


def _episodes(world: dict[str, Path], name: str, event: str, *more: str) -> list[dict[str, Any]]:
    result = _inspect(world, name, event, "--json", *more)
    assert result.code == 0, result.err
    episodes = doc(result)["episodes"]
    assert isinstance(episodes, list)
    return episodes


def _groups(episodes: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Each distinct error, in the order its first episode comes, with how many episodes have it."""
    counts = Counter(str(e["error"]) for e in episodes)
    return list(counts.items())


def _count_line_for(out: str, error: str) -> str:
    """The error's first line where the output prints it once, with the line above it: the count is
    on one of the two."""
    body = out.split("\n", 1)[1]
    first = error.rstrip().splitlines()[0]
    found = list(re.finditer(rf"(?<![\w]){re.escape(first)}(?![\w])", body))
    assert len(found) == 1, (first, len(found), body[:600])
    before = body[: found[0].start()].rstrip().splitlines()
    return f"{before[-1] if before else ''}\n{body[found[0].start():].splitlines()[0]}"


def _says_count(line: str, count: int) -> bool:
    noun = "episode" if count == 1 else "episodes"
    return re.search(rf"(?<![\d,]){count:,} {noun}\b", line) is not None


# ---------- identical errors ----------


def test_identical_errors_print_one_traceback_with_a_count(reading_world: dict[str, Path]) -> None:  # noqa: F811
    episodes = _episodes(reading_world, "same_error", "ValueError")
    assert len(episodes) == 9 and len(_groups(episodes)) == 1
    result = _inspect(reading_world, "same_error", "ValueError")
    assert result.code == 0, result.err
    assert result.out.count(TRACEBACK) == 1, result.out[:600]
    assert result.out.count("ValueError: this rollout always raises") == 1, result.out[:600]
    assert _says_count(_count_line_for(result.out, episodes[0]["error"]), 9), result.out[:600]


def test_the_first_line_is_as_it_was(reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _inspect(reading_world, "same_error", "ValueError", "--limit", "3")
    document = doc(_inspect(reading_world, "same_error", "ValueError", "--limit", "3", "--json"))
    assert result.out.splitlines()[0] == f"ok  {document['sentence']}", result.out.splitlines()[0]
    assert document["sentence"].startswith("3 of 9 episodes"), document["sentence"]


def test_every_listed_episode_stays_on_one_line_of_its_own(reading_world: dict[str, Path]) -> None:  # noqa: F811
    episodes = _episodes(reading_world, "same_error", "ValueError")
    lines = _inspect(reading_world, "same_error", "ValueError").out.splitlines()
    for episode in episodes:
        config = json.dumps(episode["config"], sort_keys=True)
        holding = [line for line in lines[:-1] if re.search(rf"\b{episode['seed']}\b", line) and config in line]
        assert len(holding) == 1, (episode["seed"], holding)
        line = holding[0]
        assert episode["config_hash"][:12] in line, line
        assert re.search(rf"replicate_index:? {episode['replicate_index']}\b", line), line


def test_a_thousand_episodes_are_counted_as_the_look_prints_counts(reading_world: dict[str, Path]) -> None:  # noqa: F811
    result = _inspect(reading_world, "many_errors", "ValueError", "--limit", "1")
    assert result.out.count(TRACEBACK) == 1, result.out[:600]
    assert re.search(r"(?<![\d,])1,200 episodes\b", result.out.split("\n", 1)[1]), result.out[:600]
    assert len(result.out.splitlines()) < 30, result.out


# ---------- errors that differ ----------


def test_tracebacks_that_differ_are_groups_of_their_own_in_the_order_stored(reading_world: dict[str, Path]) -> None:  # noqa: F811
    episodes = _episodes(reading_world, "two_tracebacks", "ValueError")
    groups = _groups(episodes)
    assert sorted(count for _, count in groups) == [3, 6], [count for _, count in groups]
    result = _inspect(reading_world, "two_tracebacks", "ValueError")
    assert result.out.count(TRACEBACK) == 2, result.out[:800]
    places = []
    for error, count in groups:
        # The two share their first line, so each is found by the line that tells them apart.
        where = result.out.find(error.rstrip())
        assert where >= 0, (error, result.out[:800])
        places.append(where)
        above = result.out[:where].rstrip().splitlines()[-1]
        assert _says_count(above, count), (count, above)
    assert places == sorted(places), places


def test_an_error_that_names_its_seed_is_not_identical_to_the_next(reading_world: dict[str, Path]) -> None:  # noqa: F811
    episodes = _episodes(reading_world, "own_text", "ValueError")
    assert len(_groups(episodes)) == 9
    result = _inspect(reading_world, "own_text", "ValueError")
    assert result.out.count(TRACEBACK) == 9, result.out[:800]
    assert not re.search(r"(?<![\d,])\d[\d,]* episodes?\b", result.out.split("\n", 1)[1]), result.out[:800]
    lines = result.out.splitlines()
    assert sum(line.startswith("config_hash: ") for line in lines) == 9, lines
    assert sum(line == "outcome: -" for line in lines) == 9, lines
    assert sum(line.startswith("error: Traceback") for line in lines) == 9, lines


def test_an_error_with_no_traceback_is_grouped_too(reading_world: dict[str, Path]) -> None:  # noqa: F811
    episodes = _episodes(reading_world, "timeouts", "episode_timeout")
    assert {e["error"] for e in episodes} == {"timeout"}, {e["error"] for e in episodes}
    result = _inspect(reading_world, "timeouts", "episode_timeout")
    assert _says_count(_count_line_for(result.out, "timeout"), 9), result.out[:600]


# ---------- --limit and --where ----------


def test_the_count_is_every_matching_episode_and_limit_lists_fewer(reading_world: dict[str, Path]) -> None:  # noqa: F811
    listed = _episodes(reading_world, "same_error", "ValueError", "--limit", "2")
    result = _inspect(reading_world, "same_error", "ValueError", "--limit", "2")
    assert result.out.count(TRACEBACK) == 1
    assert _says_count(_count_line_for(result.out, listed[0]["error"]), 9), result.out[:600]
    seeds = {e["seed"] for e in _episodes(reading_world, "same_error", "ValueError")}
    shown = {seed for seed in seeds if re.search(rf"\bseed:? {seed}\b", result.out)}
    assert shown == {e["seed"] for e in listed}, (shown, listed)


def test_a_group_the_limit_hides_is_counted_and_not_printed(reading_world: dict[str, Path]) -> None:  # noqa: F811
    everything = _groups(_episodes(reading_world, "two_tracebacks", "ValueError"))
    (first, first_count), (_, second_count) = everything
    result = _inspect(reading_world, "two_tracebacks", "ValueError", "--limit", "1")
    assert result.out.count(TRACEBACK) == 1, result.out[:800]
    assert first.rstrip() in result.out, result.out[:800]
    above = result.out[: result.out.find(first.rstrip())].rstrip().splitlines()[-1]
    assert _says_count(above, first_count), above
    below = result.out[result.out.find(first.rstrip()) + len(first.rstrip()):]
    assert _says_count(below, second_count), below


def test_no_group_is_hidden_when_nothing_is_said_of_one(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """With one error in the run there is no other to count."""
    out = _inspect(reading_world, "same_error", "ValueError", "--limit", "1").out
    after = out[out.find("ValueError: this rollout always raises"):]
    assert not re.search(r"(?<![\d,])\d[\d,]* (more|other)", after), after


def test_where_narrows_the_count(reading_world: dict[str, Path]) -> None:  # noqa: F811
    episodes = _episodes(reading_world, "same_error", "ValueError", "--where", 'cell="a"')
    assert len(episodes) == 3
    result = _inspect(reading_world, "same_error", "ValueError", "--where", 'cell="a"')
    assert _says_count(_count_line_for(result.out, episodes[0]["error"]), 3), result.out[:600]


# ---------- the reproduce snippet ----------


def test_the_snippet_names_the_first_episode_under_the_first_traceback(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """It came last, after everything scrolled away, naming an episode the screen no longer showed."""
    result = _inspect(reading_world, "two_tracebacks", "ValueError")
    document = doc(_inspect(reading_world, "two_tracebacks", "ValueError", "--json"))
    first = document["episodes"][0]
    assert document["reproduce"]["seed"] == first["seed"], document["reproduce"]
    lines = result.out.splitlines()
    assert lines[-3] == "# reproduce one episode" and f"seed={first['seed']}" in lines[-1], lines[-3:]
    second_traceback = result.out.find(TRACEBACK, result.out.find(TRACEBACK) + 1)
    assert re.search(rf"\bseed:? {first['seed']}\b", result.out[:second_traceback]), result.out[:800]


# ---------- what does not change ----------


def test_a_trace_stays_with_its_episode(reading_world: dict[str, Path]) -> None:  # noqa: F811
    """The traceback is the same on all of them; each trace is its own, so each listed episode keeps
    its own span lines."""
    result = _inspect(reading_world, "traced", "ValueError", "--limit", "2")
    assert result.out.count(TRACEBACK) == 1, result.out[:800]
    spans = [line for line in result.out.splitlines() if re.match(r"\s+\d+\t", line)]
    assert len(spans) == 2, result.out[:800]
    assert all("invoke_agent" in line for line in spans), spans


def test_an_episode_that_ended_in_an_outcome_prints_as_it_always_has(reading_world: dict[str, Path]) -> None:  # noqa: F811
    from pf12_support import QS_A

    store = reading_world["old"]
    for run in (QS_A, QS_B):
        result = cli(store, "inspect", run, "--event", "violated", "--limit", "2")
        assert result.code == 0, result.err
        lines = result.out.splitlines()
        assert sum(line.startswith("config_hash: ") for line in lines) == 2, lines
        assert sum(line.startswith("config: ") for line in lines) == 2, lines
        assert sum(line.startswith("seed: ") for line in lines) == 2, lines
        assert sum(line.startswith("replicate_index: ") for line in lines) == 2, lines
        assert sum(line.startswith("t: ") for line in lines) == 2, lines
        assert not re.search(r"(?<![\d,])\d[\d,]* episodes?\b", "\n".join(lines[1:])), lines


@pytest.mark.parametrize("more", [(), ("--limit", "2")])
def test_the_json_lists_every_episode_with_its_own_error(more: tuple[str, ...], reading_world: dict[str, Path]) -> None:  # noqa: F811
    document = doc(_inspect(reading_world, "same_error", "ValueError", "--json", *more))
    assert list(document) == DOCUMENT_KEYS, list(document)
    assert len(document["episodes"]) == (2 if more else 9)
    for episode in document["episodes"]:
        assert list(episode) == EPISODE_KEYS, list(episode)
        assert TRACEBACK in episode["error"], episode["error"]


def test_on_a_terminal_it_is_the_same_reading(reading_world: dict[str, Path], tmp_path: Path) -> None:  # noqa: F811
    home = tmp_path / "home"
    home.mkdir()
    run = run_pty(["--store", str(reading_world["same_error"]), "inspect", "latest", "--event", "ValueError"], home=home, cwd=tmp_path, cols=160, rows=60)
    assert run.code == 0, run.err[-400:]
    text = strip_escapes(run.out)
    assert text.count(TRACEBACK) == 1, text[:600]
    assert re.search(r"(?<![\d,])9 episodes\b", text.split("\n", 1)[1]), text[:600]


def test_the_page_says_errors_are_grouped() -> None:
    page = (ROOT / "docs" / "commands" / "inspect.md").read_text(encoding="utf-8")
    assert re.search(r"(?i)identical errors?\b.*\btraceback\b.*\bcount\b", " ".join(page.split())), page[:400]
