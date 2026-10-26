"""The facts every surface prints about a comparison's verdict, written once (PF4.34 to PF4.47).

``diff`` and ``check`` print them as the verdict block's detail lines, ``report.md`` and the receipt
as a section, the page in its Summary; each is a ``(label, text)`` pair so every surface says the
same thing in the same words. The binding words of PF4.35 (``Benjamini``, ``Hochberg``, ``false
discovery rate``, ``Holm``, ``family-wise``, ``cause-specific hazard``, ``Miettinen-Nurminen``,
``Tango``, ``simultaneous``, ``Bonferroni``, ``false coverage``, ``Benjamini-Yekutieli``) are in
these lines. Levels and powers are read from ``poisson_prove.stats`` when a line is written, never
typed in (PF4.1c, PF4.32).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from poisson_prove import _look
from poisson_prove.stats import POWER as _POWER

if TYPE_CHECKING:
    from poisson_prove.diff import MultiDiffResult

_NOTHING_MOVED = ("no significant change", "too small to tell")

#: Each test as a reader names it.
_TEST_NAMES = {
    "fisher_bh": "Fisher",
    "mcnemar_bh": "the paired test (McNemar)",
    "logrank_bh": "log-rank",
    "fisher": "Fisher",
    "mcnemar": "the paired test",
    "logrank": "log-rank",
}


def is_nothing_moved(word: str) -> bool:
    """Whether the word is one of the two that say no condition counted as a change."""
    return word in _NOTHING_MOVED


def test_name(method: str) -> str:
    return _TEST_NAMES[method]


def interval_method(method: str) -> str:
    """The interval on the change a test's rows carry (PF4.42)."""
    return "Tango" if method == "mcnemar_bh" else "Miettinen-Nurminen"


def power_of(multi: MultiDiffResult) -> float:
    """The power a comparison's limits were computed at, as its rows record it."""
    for ev in multi.by_event.values():
        if "mde_power" in ev.cells:
            for value in ev.cells["mde_power"]:
                if value is not None and value == value:
                    return float(value)
    return _POWER


def power_words(power: float | None = None) -> str:
    """The stated power in words: "4 times in 5"."""
    return _look.times_in(_POWER if power is None else power)


def condition_text(config: Any) -> str:
    """A condition as its axis values: ``cell up`` or ``mu 0.7, push 130``."""
    try:
        return ", ".join(f"{key} {value}" for key, value in sorted(dict(config).items()))
    except (TypeError, ValueError):
        return str(config)


def _number(value: Any) -> float | None:
    """A limit as a float, or None when it has none."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


def limit_text(record: Mapping[str, Any]) -> str:
    """A condition's limits as a cell table prints them: each direction's number or, when it has
    none, the reason in words (``rise 0.568, fall: none detectable``); the one number when the two
    directions agree to three decimals, which the table's caption says (PF4.27, PF4.32)."""
    rise, fall = _number(record.get("mde_rise")), _number(record.get("mde_fall"))
    if rise is not None and fall is not None and abs(rise - fall) < 0.001:
        return f"{rise:.3f}"
    parts = []
    for way, value in (("rise", rise), ("fall", fall)):
        parts.append(
            f"{way} {value:.3f}" if value is not None else f"{way}: {record.get(f'mde_{way}_note')}"
        )
    return ", ".join(parts)


def limits_caption(power: float | None = None) -> str:
    """What a cell table's limit column is: the smallest change each way one condition alone
    would be flagged for, with the one number where both directions agree."""
    return (
        f"mde is the smallest rise and the smallest fall one condition alone would be flagged for, "
        f"{power_words(power)}, if it alone changed, from where the condition was; one number is "
        "both the rise's and the fall's, where the two agree to three decimals."
    )


def shares_caption(event: str, level: float) -> str:
    """What the share columns are, and that their intervals are per condition (PF4.3)."""
    return (
        f"share_a and share_b are each condition's share of runs that ended in {event} by the "
        f"comparison's horizon, with a {_look.level_label(level)} Wilson interval per condition, "
        "not adjusted for the number of conditions; the tests compare the rates, and * marks a "
        "share that is not its rate (a run censored before the horizon)."
    )


def limit_clause(multi: MultiDiffResult) -> str | None:
    """The verdict limit on the no-significant-change line (PF4.40, reading R8): the largest limit
    the verdict's question read, with its test, level, family and power."""
    if multi.verdict_limit is None:
        return None
    return (
        f"every condition that did not count could have shown a change of "
        f"{_look.fmt_rate(multi.threshold)}: the largest limit it read is "
        f"{multi.verdict_limit:.3f} "
        f"({test_name(multi.method)}, Holm q {multi.q:g} over {multi.n_tests} tests, "
        f"{power_words(power_of(multi))})"
    )


def verdict_sentence(word: str, base: str, multi: MultiDiffResult) -> str:
    """The verdict line's sentence: the counts, then, when they differ from the flags', the
    counts that decided the word (PF4.35); under ``no significant change`` the limit first."""
    sentence = base
    decided = []
    for event in sorted(multi.events):
        ev = multi.by_event[event]
        if (ev.n_holm_higher, ev.n_holm_lower) != (ev.n_higher, ev.n_lower):
            decided.append(f"{event} {ev.n_holm_higher} rose and {ev.n_holm_lower} fell")
    if decided:
        sentence += "; counted at the family-wise level: " + ", ".join(decided)
    if word == "no significant change":
        clause = limit_clause(multi)
        if clause is not None:
            sentence = f"{clause}; {sentence}"
    return sentence


def lines(multi: MultiDiffResult, names: Mapping[str, str] | None = None) -> list[tuple[str, str]]:
    """The facts under the verdict, ``(label, text)`` in order. ``names`` maps a run's id to the
    name it goes by, for the peeking caveat."""
    m, q = multi.n_tests, f"{multi.q:g}"
    out = [
        (
            "verdict rule",
            f"the verdict counts changes at the family-wise level (Holm, q {q} over {m} tests); "
            f"a condition's flag is Benjamini-Hochberg's, at the false discovery rate q {q} over "
            f"{m} tests",
        )
    ]
    if multi.n_flagged_only:
        verb = "does" if multi.n_flagged_only == 1 else "do"
        out.append(
            (
                "flagged only",
                f"{multi.n_flagged_only} flagged at the false discovery rate {verb} "
                "not count at the family-wise level",
            )
        )
    if multi.method == "logrank_bh":
        out.append(
            (
                "test",
                "log-rank tests the cause-specific hazard: every other ending is censored, so "
                "the hazard test and the incidence need not move together",
            )
        )
        shifted = []
        for event in multi.events:
            for record in multi.by_event[event].records():
                if record.get("competing_shift"):
                    shifted.append(
                        f"{condition_text(record['config'])} ({event}): "
                        f"{', '.join(record['competing_shift'])}"
                    )
        if shifted:
            out.append(
                (
                    "competing",
                    f"in {len(shifted)} rows another outcome's share changed too, so the "
                    "hazard test and the incidence need not agree: " + "; ".join(shifted),
                )
            )
    out.append(
        (
            "limits",
            "the smallest change one condition alone would be flagged for, "
            f"{power_words(power_of(multi))}, "
            f"if it alone changed, from where the condition was ({test_name(multi.method)}, "
            f"q {q} over {m} tests){_without_limit(multi)}",
        )
    )
    if multi.interval_level is not None:
        level = _look.level_label(multi.interval_level)
        if multi.n_rejected:
            rule = (
                f"false coverage (Benjamini-Yekutieli) over the {multi.n_rejected} flagged; an "
                "unflagged row's interval is at the same level with no adjusted promise of its own"
            )
        else:
            rule = f"simultaneous (Bonferroni) over the {m} tests"
        out.append(
            (
                "intervals",
                f"on each condition's change: {interval_method(multi.method)} at {level}, {rule}",
            )
        )
    out.append(("fragility", _fragility_text(multi)))
    for entry in multi.peeking:
        shown = (names or {}).get(str(entry["run_id"])) or entry.get("run_name") or entry["run_id"]
        why = (
            "replicates were added after a comparison of it was read"
            if entry["reason"] == "resumed after a comparison"
            else "it is partial"
        )
        out.append(
            (
                "peeking",
                f'run "{shown}": {why}; the tests assume the number of runs was fixed before '
                "any result was seen, so their error rates do not hold for it",
            )
        )
    if multi.errors_differ:
        worst = max(
            multi.errors_differ,
            key=lambda e: abs(e["errored_b"] / e["rows_b"] - e["errored_a"] / e["rows_a"]),
        )
        out.append(
            (
                "errors",
                f"errored episodes differ between the runs in {len(multi.errors_differ)} "
                f"conditions (largest {condition_text(worst['config'])}: {worst['errored_a']} "
                f"of {worst['rows_a']} against {worst['errored_b']} of {worst['rows_b']}); runs "
                "that errored are in neither the shares nor the tests, so a change in errors can "
                "hide or make a change in the outcomes",
            )
        )
    return out


def _without_limit(multi: MultiDiffResult) -> str:
    """The rows that did not count and have no limit, by reason: a largest limit elsewhere says
    nothing about them, so a claim that nothing changed holds at no size there (PF4.27, PF4.29)."""
    reasons: dict[str, int] = {}
    for event in multi.events:
        for record in multi.by_event[event].records():
            if record.get("holm") or record.get("mde") is not None:
                continue
            note = str(record.get("mde_note") or "none detectable")
            reasons[note] = reasons.get(note, 0) + 1
    if not reasons:
        return ""
    n = sum(reasons.values())
    counts = ", ".join(f"{note}: {_look.fmt_count(k)}" for note, k in sorted(reasons.items()))
    rows = "row" if n == 1 else "rows"
    return (
        f"; {_look.fmt_count(n)} {rows} that did not count have no limit ({counts}), so no "
        "change of any size can be excluded there"
    )


def _fragility_text(multi: MultiDiffResult) -> str:
    """PF4.44: how many stored outcomes would change the word, and which."""
    if multi.fragility is None:
        return f"none: {multi.fragility_note}"
    exact = "" if multi.fragility_exact else " (the search is not exhaustive: it may be fewer)"
    configs = {
        str(r["config_hash"]): r["config"]
        for e in multi.events
        for r in multi.by_event[e].cells[["config_hash", "config"]].to_dict(orient="records")
    }
    groups: dict[tuple[str, str, str, str], int] = {}
    for flip in multi.fragility_flips:
        key = (str(flip["config_hash"]), str(flip["event"]), str(flip["run"]), str(flip["to"]))
        groups[key] = groups.get(key, 0) + 1
    parts = []
    for (config_hash, event, run, to), n in groups.items():
        where = condition_text(configs.get(config_hash, config_hash))
        runs = "run" if n == 1 else "runs"
        made = (
            f"made to end in {event}"
            if to == "event"
            else f"that ended in {event} made to end otherwise"
        )
        parts.append(f"{n} {runs} of {run.upper()} in {where} {made}")
    flips = f": {'; '.join(parts)}" if parts else ""
    noun = "outcome" if multi.fragility == 1 else "outcomes"
    return f"{multi.fragility} {noun} would change the word{exact}{flips}"


def markdown(multi: MultiDiffResult, names: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """The facts as ``report.md``'s section."""
    out = ["## What the verdict rests on", ""]
    for label, text in lines(multi, names):
        out += [f"{label}: {text}", ""]
    return tuple(out)


def counts_text(multi: MultiDiffResult, events: Sequence[str]) -> str:
    """The verdict line's counts per event, in direction words: what rose and what fell."""
    parts = []
    for event in events:
        ev = multi.by_event[event]
        parts.append(
            f"{event} rose in {_look.fmt_count(ev.n_higher)} and fell in "
            f"{_look.fmt_count(ev.n_lower)} of {_look.fmt_count(len(ev.cells))} conditions"
        )
    return "; ".join(parts)
