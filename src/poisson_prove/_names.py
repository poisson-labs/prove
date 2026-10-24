"""Run names: the name every run has, the names a user gave in Trace, and the words a verb
takes for a run.

Every run has a name. A run named in ``trace-names.toml`` at the store root (the file
``poisson-trace name`` writes; Prove reads it and never writes it) goes by that name; else by
the name given at sweep time (``sweep --name``, recorded in its manifest); else by the name
computed from its manifest: the target id up to its first ``/``, the day it started in UTC, and
a letter in start order among the runs that would otherwise share that name (``a`` to ``z``,
then ``aa``). A run an import wrote, or one whose target cannot be made into a name a verb could
read back, goes by its id. Computed names are never stored, so the same store gives the same
names on every machine, and the rule is Trace's ``target`` form, byte for byte, so a run reads
the same in both tools.

A verb takes a run as ``latest``, ``previous`` (the two newest complete runs), ``latest:TARGET``,
``previous:TARGET`` (the target as names show it), ``#N`` (row N of ``poisson-prove runs``), a
name from the names file, a name from a manifest, a computed name, or the full id, in that
order between the kinds of word. A word that reaches no run, or two, is refused and never
guessed. Every word is read trimmed.

Everything here is standard library. Nothing here writes a file.
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poisson_prove import _look

NAMES_FILE = "trace-names.toml"
LONGEST = 80
IMPORTED = "import:"
#: the most runs a refusal lists before it says how many more there are
SHOWN = 10
# the characters str.splitlines breaks a line at
_BREAKS = frozenset("\n\r\v\f\x1c\x1d\x1e\x85  ")


class NamesError(Exception):
    """A word that names no run or two, or a names file Trace would refuse. Carries the
    ``next:`` commands that fix it, when there are any."""

    def __init__(self, message: str, nexts: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.nexts = list(nexts)


# ---------- a name alone ----------


def reserved(text: str) -> bool:
    """Whether ``text`` is one of the words a verb reads before any name."""
    return text in ("latest", "previous") or text.startswith(("latest:", "previous:", "#"))


def _unwritable(ch: str) -> bool:
    """A character a name never holds: a control character other than the tab, which a
    terminal acts on rather than shows, or half of a character that is not text."""
    return ch != "\t" and unicodedata.category(ch) in ("Cc", "Cs")


def unfit(text: str) -> str | None:
    """Why ``text``, already trimmed, cannot be a name, or None when it can: a name is not
    empty, is one line of at most 80 characters of text, is not a word a verb reads before any
    name, and does not open with a dash, which a command line reads as an option."""
    if not text:
        return "a name is not empty"
    if len(text) > LONGEST:
        count = _look.fmt_count(len(text))
        return f"a name is at most {LONGEST} characters, and this one has {count}"
    if any(ch in _BREAKS for ch in text):
        return "a name is one line"
    if any(_unwritable(ch) for ch in text):
        return "a name holds no control character and nothing that is not text"
    if text in ("latest", "previous"):
        which = "newest" if text == "latest" else "second newest"
        return f'"{text}" is the word for the {which} complete run'
    if text.startswith(("latest:", "previous:")):
        return "a name beginning latest: or previous: is the word for a target's newest runs"
    if text.startswith("#"):
        return "a name beginning # is the word for a row of poisson-prove runs"
    if text.startswith("-"):
        return "a name beginning with a dash is read as an option on a command line"
    return None


def _letters(n: int) -> str:
    """The n-th letter name, from 0: a to z, then aa, ab and on."""
    out = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        out = chr(ord("a") + rest) + out
    return out


def started(created_at: Any) -> datetime | None:
    """When a run started, in UTC, from its manifest's ``created_at``; None when that is not a
    time a name can be given from."""
    if not isinstance(created_at, str):
        return None
    try:
        at = datetime.fromisoformat(created_at)
        return at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def target_of(target_id: str) -> str:
    """The target as names show it: the target id up to its first ``/``."""
    return target_id.split("/", 1)[0]


def _nameable(target: str) -> bool:
    """Whether a name built on ``target`` could be given back to a verb: one with nothing at
    either end, no tab, no control character, and none of the words a verb reads first."""
    return (
        bool(target)
        and target == target.strip()
        and "\t" not in target
        and unfit(f"{target} 2026-01-01 a") is None
    )


# ---------- the names file ----------


def shown_file(store: str) -> str:
    """The names file as a user reads its path: under the store as they typed it."""
    return f"{store.rstrip('/') or '/'}/{NAMES_FILE}" if store else NAMES_FILE


def _line_of(exc: tomllib.TOMLDecodeError) -> str:
    found = re.search(r"\(at line (\d+)", str(exc))
    return f" (line {found.group(1)})" if found else ""


def read_names_file(root: Path, shown: str) -> tuple[dict[str, str], dict[str, str]]:
    """The names a user gave, trimmed, mapped to the ids they name, empty when the store has
    no names file; and the names among them that cannot be names, each with why. A file that
    is not a names file is refused, naming it, as Trace refuses it."""
    path = root / NAMES_FILE
    if not path.exists() and not path.is_symlink():
        return {}, {}

    def damaged(why: str) -> NamesError:
        return NamesError(f"{shown} is not a names file: {why}")

    try:
        raw = path.read_bytes()
    except OSError as exc:
        why = exc.strerror or type(exc).__name__
        raise NamesError(f"cannot read {shown} ({why})") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise damaged("it is not UTF-8 text") from None
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise damaged(f"it is not TOML{_line_of(exc)}") from None
    except RecursionError:
        raise damaged("it is not TOML a reader can follow: it nests too deep") from None
    for key, value in doc.items():
        if key not in ("version", "names"):
            what = "table" if isinstance(value, dict) else "setting"
            raise damaged(f'"{key}" is not a {what} a names file has; it has version and [names]')
    version = doc.get("version")
    if version is None:
        raise damaged("it has no version line, version = 1")
    if type(version) is not int:
        raise damaged("its version is not the whole number 1")
    if version != 1:
        raise damaged(f"it is version {version}, and this Prove reads version 1")
    table = doc.get("names", {})
    if not isinstance(table, dict):
        raise damaged("its names are not a [names] table")
    entries: dict[str, str] = {}
    given: dict[str, str] = {}
    unfit_names: dict[str, str] = {}
    for key, value in table.items():
        if not isinstance(value, str):
            raise damaged(f'the name "{key}" is given a value that is not a run id in quotes')
        trimmed = key.strip()
        if trimmed in given:
            raise damaged(
                f'"{given[trimmed]}" and "{key}" are one name once their spaces are trimmed'
            )
        hole = unfit(trimmed)
        if hole is not None:
            unfit_names[trimmed] = hole
        given[trimmed] = key
        entries[trimmed] = value
    return entries, unfit_names


# ---------- the runs of a store, named ----------


@dataclass(frozen=True)
class Named:
    """One run of a store and the name it goes by."""

    run_id: str
    name: str
    computed: str | None  # the name from its manifest; None for an imported or unnameable run
    manifest_name: str | None  # the name given at sweep time, when it is one a verb can take
    created_at: str
    started: datetime
    status: str
    target_id: str
    backend: str
    number: int | None = None  # its row in ``poisson-prove runs``; None for a partial run

    @property
    def target(self) -> str:
        return target_of(self.target_id)

    @property
    def imported(self) -> bool:
        return self.backend.startswith(IMPORTED)

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def shown(self) -> str:
        """The run as a refusal names it: its name, and its id when that is not the name."""
        return f'"{self.name}"' if self.name == self.run_id else f'"{self.name}" ({self.run_id})'


@dataclass
class Index:
    """The runs of one store, newest first, each with its name, and the words that reach them."""

    store: str  # the store as the command reaches it
    runs: list[Named]
    entries: dict[str, str]  # the names file: the user's name -> run id
    unreadable: list[str] = field(default_factory=list)  # runs whose manifest cannot be read
    words: dict[str, set[str]] = field(default_factory=dict)

    @property
    def complete(self) -> list[Named]:
        return [r for r in self.runs if r.complete]

    @property
    def partial(self) -> list[Named]:
        return [r for r in self.runs if not r.complete]

    def by_id(self, run_id: str) -> Named | None:
        return next((r for r in self.runs if r.run_id == run_id), None)

    def name_of(self, run_id: str) -> str:
        """The name the run ``run_id`` goes by; the id itself for a run the store lacks."""
        found = self.by_id(run_id)
        return run_id if found is None else found.name

    def holders(self, text: str) -> set[str]:
        """The runs that answer to ``text`` now, by any route."""
        return set(self.words.get(text.strip(), set()))

    def word_for(self, run_id: str) -> str:
        """The word a command gives for the run ``run_id``: its name when that reaches it alone;
        else its number, or its id, which always does. Two runs can come to answer to one name
        when a name was given before a run with that computed name was stored."""
        run = self.by_id(run_id)
        if run is None:
            return run_id
        if self.words.get(run.name) == {run_id}:
            return run.name
        return f"#{run.number}" if run.number is not None else run_id

    # ---------- the words a verb takes ----------

    def find(self, given: str) -> Named:
        """The one run ``given`` names, or a refusal; never a guess."""
        text = given.strip()
        if text in ("latest", "previous"):
            return self._newest(text, None)
        for form in ("latest", "previous"):
            if text.startswith(form + ":"):
                return self._newest(form, text[len(form) + 1 :].strip())
        if text.startswith("#"):
            return self._numbered(text)
        hits = self.words.get(text, set())
        if len(hits) > 1:
            runs = [r for r in self.runs if r.run_id in hits]
            shown = " and ".join(self._with_number(r) for r in runs)
            raise NamesError(
                f'two runs answer to "{text}": {shown}; give one of them by its number or its id',
                [self.listing()],
            )
        if not hits:
            raise NamesError(self._unknown(text), [self.listing()])
        (run_id,) = hits
        found = self.by_id(run_id)
        if found is None:
            # a run whose manifest could not be read: reached by its id alone, and refused by
            # the verb that then reads it
            return Named(
                run_id=run_id,
                name=run_id,
                computed=None,
                manifest_name=None,
                created_at="",
                started=datetime.min.replace(tzinfo=UTC),
                status="unreadable",
                target_id="unreadable",
                backend="",
            )
        return found

    def _with_number(self, run: Named) -> str:
        return run.shown() if run.number is None else f"#{run.number} {run.shown()}"

    def _unknown(self, text: str) -> str:
        shown = [r.shown() for r in self.runs[:SHOWN]]
        more = len(self.runs) - SHOWN
        held = ", ".join(shown) + (f" and {_look.fmt_count(more)} more" if more > 0 else "")
        return f'unknown run "{text}"; the store holds {held or "no runs"}'

    def _newest(self, form: str, target: str | None) -> Named:
        pool = self.complete if target is None else [r for r in self.complete if r.target == target]
        rank = 0 if form == "latest" else 1
        if len(pool) > rank:
            return pool[rank]
        if target is not None and "/" in target:
            raise NamesError(
                f'{form}:TARGET takes the target as names show it, up to its first "/": '
                f'"{target_of(target)}", not "{target}"',
                [self.listing()],
            )
        if target is not None and not any(r.target == target for r in self.runs):
            targets = sorted({f'"{r.target}"' for r in self.runs})
            raise NamesError(
                f'no run of this store has the target "{target}"; its targets are '
                f"{', '.join(targets) or 'none'}",
                [self.listing()],
            )
        whose = "complete runs" if target is None else f'complete runs of the target "{target}"'
        held = "none" if not pool else "one"
        word = "the newest" if form == "latest" else "the second newest"
        label = form if target is None else f"{form}:{target}"
        raise NamesError(
            f"{label} is {word} of the {whose}, and the store holds {held}", [self.listing()]
        )

    def _numbered(self, text: str) -> Named:
        digits = text[1:]
        complete = self.complete
        if not re.fullmatch(r"[1-9][0-9]*", digits, flags=re.ASCII):
            raise NamesError(
                f'"{text}" is not a row of poisson-prove runs: a row is # and a number from 1',
                [self.listing()],
            )
        # a number longer than the count of rows is past the last row, however long it is
        if len(digits) > len(str(len(complete))) or int(digits) > len(complete):
            shown = text if len(digits) <= 12 else f"#{digits[:6]}…"
            raise NamesError(
                f"there is no run {shown}: the store holds {_look.fmt_count(len(complete))} "
                f"complete {'run' if len(complete) == 1 else 'runs'}",
                [self.listing()],
            )
        return complete[int(digits) - 1]

    # ---------- the commands a refusal offers ----------

    def reach(self) -> tuple[str, ...]:
        """The words a command carries to read this store."""
        return ("--store", self.store)

    def listing(self) -> str:
        """The command that lists this store's runs."""
        return _look.command("poisson-prove", *self.reach(), "runs")

    def forget(self, name: str) -> str:
        """Trace's command that takes back the user's name ``name``; one a command line would
        read as an option comes after ``--``."""
        if name.startswith("-"):
            return _look.command("poisson-trace", "name", "--forget", *self.reach(), "--", name)
        return _look.command("poisson-trace", "name", name, "--forget", *self.reach())

    def computed_for(self, target_id: str, at: datetime) -> str | None:
        """The name a new run of ``target_id`` started at ``at`` would be computed, given the
        runs the store holds now; None when its target cannot be made into a name."""
        rest = target_of(target_id)
        if not _nameable(rest):
            return None
        when = at.astimezone(UTC)
        head = f"{rest} {when.strftime('%Y-%m-%d')}"
        pattern = re.compile(re.escape(head) + r" [a-z]+")
        taken = sum(
            1
            for r in self.runs
            if r.computed is not None and pattern.fullmatch(r.computed) and r.started <= when
        )
        return f"{head} {_letters(taken)}"


def _damage(
    entries: Mapping[str, str], unfit_names: Mapping[str, str], ids: Iterable[str], idx: Index
) -> NamesError | None:
    """The refusal a names file with a stale entry, a name that cannot be one, or two names for
    one run gets from every verb, as Trace refuses it; Prove has no verb that takes one back."""
    held = set(ids)
    stale = {n: r for n, r in entries.items() if r not in held}
    if stale:
        shown = ", ".join(f'"{n}" for the run "{r}"' for n, r in sorted(stale.items()))
        return NamesError(
            f"{shown_file(idx.store)} names {shown}, which the store does not hold",
            [idx.forget(n) for n in sorted(stale)],
        )
    if unfit_names:
        name, why = next(iter(sorted(unfit_names.items())))
        first = name if not any(ch in _BREAKS for ch in name) else name.splitlines()[0] + " …"
        return NamesError(
            f'{shown_file(idx.store)} holds "{first}", which cannot be a name: {why}',
            [idx.forget(n) for n in sorted(unfit_names) if not any(c in _BREAKS for c in n)],
        )
    mine: dict[str, list[str]] = {}
    for name, run_id in entries.items():
        mine.setdefault(run_id, []).append(name)
    doubled = {r: sorted(n) for r, n in mine.items() if len(n) > 1}
    if doubled:
        run_id, names = next(iter(sorted(doubled.items())))
        return NamesError(
            f"{shown_file(idx.store)} gives the run {run_id} two names, "
            + " and ".join(f'"{n}"' for n in names)
            + "; a run has one",
            [idx.forget(n) for n in names[1:]],
        )
    return None


def index(store: Any, root: Path, shown: str) -> Index:
    """The runs ``store`` (Prove's store at ``root``, reached as ``shown``) holds, named. A
    names file Trace would refuse is refused here too, with Trace's command to fix it."""
    entries, unfit_names = read_names_file(root, shown_file(shown))
    runs: list[Named] = []
    unreadable: list[str] = []
    for run_id in store.runs():
        try:
            manifest = store.manifest(run_id)
        except Exception:  # noqa: BLE001 - a run that cannot be read is reached by id alone
            unreadable.append(run_id)
            continue
        started_at = started(manifest.created_at)
        if started_at is None:
            unreadable.append(run_id)
            continue
        given = getattr(manifest, "name", None)
        given = given.strip() if isinstance(given, str) else None
        runs.append(
            Named(
                run_id=run_id,
                name=run_id,
                computed=None,
                manifest_name=given if given and unfit(given) is None else None,
                created_at=manifest.created_at,
                started=started_at,
                status=str(manifest.status),
                target_id=str(manifest.target_id),
                backend=str(manifest.backend),
            )
        )
    runs.sort(key=lambda r: (r.started, r.run_id))
    computed: dict[str, str] = {}
    letters: dict[str, int] = {}
    for run in runs:
        if run.imported or not _nameable(run.target):
            continue
        head = f"{run.target} {run.started.strftime('%Y-%m-%d')}"
        n = letters.get(head, 0)
        letters[head] = n + 1
        computed[run.run_id] = f"{head} {_letters(n)}"
    ids = {r.run_id for r in runs} | set(unreadable)
    checked = Index(shown, [], dict(entries))
    damage = _damage(entries, unfit_names, ids, checked)
    if damage is not None:
        raise damage
    mine: dict[str, str] = {run_id: name for name, run_id in entries.items()}
    named: list[Named] = []
    for run in runs:
        own = computed.get(run.run_id)
        if run.run_id in mine:
            name = mine[run.run_id]
        elif run.manifest_name is not None:
            name = run.manifest_name
        else:
            name = own if own is not None else run.run_id
        named.append(replace(run, name=name, computed=own))
    named.reverse()
    numbered: list[Named] = []
    n = 0
    for run in named:
        if run.complete:
            n += 1
            numbered.append(replace(run, number=n))
        else:
            numbered.append(run)
    words: dict[str, set[str]] = {}

    def add(word: str, run_id: str) -> None:
        words.setdefault(word, set()).add(run_id)

    for run in numbered:
        add(run.run_id, run.run_id)
        if run.computed is not None:
            add(run.computed, run.run_id)
        if run.manifest_name is not None:
            add(run.manifest_name, run.run_id)
    for name, run_id in entries.items():
        add(name, run_id)
    for run_id in unreadable:
        add(run_id, run_id)
    return Index(shown, numbered, dict(entries), unreadable, words)
