"""Where a sweep runs, as a step of setting up: this machine, Modal, or the reader's own cloud
account. A plain-Python core with no terminal and no app code; ``init``, ``where`` and the
terminal app's page all call it, so the three ask the same questions and write the same table.

Where a spec runs is the table it holds: ``[cloud]``, or ``[modal]`` with its image tables, or
neither for this machine. A spec that holds both does not say.

Nothing here asks for, reads out or stores a secret, writes cloud configuration, signs in, or
creates anything in an account: the checks are the sweep's own, read-only.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import shutil
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poisson_prove import _prices_cloud, _where_checks

LABELS = {"local": "this machine", "modal": "Modal", "cloud": "your cloud account"}
#: The spec's own word for each answer, as ``where`` and ``--runs-on`` take it.
KEYS = ("local", "modal", "cloud")
#: The ledger and the time one rollout takes, which the step does not ask for and the sweep
#: needs. The estimate follows the second, so the reader sets it from a run on this machine.
LEDGER = "cloud-ledger.jsonl"
EST_SECONDS = 1.0
_PROVIDER = "aws"
#: The order ``[cloud]``'s first keys are written in; what a table carries beyond them follows.
_ORDER = (
    "provider",
    "region",
    "machine_type",
    "nodes",
    "max_vcpus",
    "ledger",
    "stop_cost",
    "max_cost",
)
_KEY = r"[A-Za-z0-9_\-]+"
_HEADER = re.compile(rf"^\s*\[\s*({_KEY})((?:\s*\.\s*[^\]]+)?)\s*\]\s*(#.*)?$")
_ANY_HEADER = re.compile(r"^\s*\[")
_KEY_LINE = re.compile(rf"^\s*({_KEY})\s*=")
#: The tables a new table takes the place of, line for line: its own, and for ``[cloud]`` the
#: 0.2 table it replaced.
_FAMILY = {"cloud": ("cloud", "burla"), "modal": ("modal",)}


class WhereError(Exception):
    """The step refuses: a value Prove cannot use, a key it will not drop."""


@dataclass(frozen=True)
class Question:
    """One value the step asks for: the table's key, the words it is asked with, the flag that
    gives it on the command line, and the default Enter takes (``None``: nothing is written)."""

    key: str
    words: str
    flag: str
    default: Any

    def shown(self) -> str:
        if self.default is None:
            return "no cap"
        if self.key.endswith("_cost"):
            return f"${self.default:,.2f}"
        return str(self.default)

    def prompt(self) -> str:
        return f"{self.words} [{self.shown()}]"

    def parse(self, typed: str) -> Any:
        """What was typed, as the table holds it; nothing typed is the default."""
        text = typed.strip()
        if not text:
            return self.default
        if self.key == "nodes":
            if not text.isdigit() or int(text) < 1:
                raise WhereError(f'"{text}" is not a number of nodes; {self.words} takes 1 or more')
            return int(text)
        if self.key.endswith("_cost"):
            try:
                value = float(text.lstrip("$").replace(",", ""))
            except ValueError:
                value = -1.0
            if not 0 < value < float("inf"):
                raise WhereError(f'"{text}" is not an amount in dollars; {self.words} takes one')
            return value
        return text


#: The questions of a cloud account, in the order they are asked, each with its default from
#: Prove's price table.
QUESTIONS = (
    Question("region", "region", "--region", "us-east-2"),
    Question("machine_type", "machine type", "--machine-type", "m7i.2xlarge"),
    Question("nodes", "nodes", "--nodes", 4),
    Question("stop_cost", "stop at", "--stop-cost", 2.0),
    Question("max_cost", "refuse above", "--max-cost", 3.0),
)
#: Modal's one question: the cap, in the cloud cap's words. Enter sets none.
MODAL_CAP = Question("max_cost", "refuse above", "--max-cost", None)


@dataclass(frozen=True)
class Cloud:
    key: str
    label: str
    offered: bool
    line: str


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    available: bool
    line: str
    clouds: tuple[Cloud, ...] = ()


@dataclass(frozen=True)
class Check:
    """One readiness result: what was checked, what was found, and when it failed the one
    command that fixes it. A ``note`` is something the reader is told that fails nothing."""

    label: str
    value: str
    ok: bool
    next: str | None = None


@dataclass(frozen=True)
class Readiness:
    checks: tuple[Check, ...]
    #: Who is signed in to the cloud, for the ownership record's name; never shown unmasked.
    account: str | None = None

    @property
    def failed(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if not c.ok)

    @property
    def shown(self) -> tuple[Check, ...]:
        """The lines under the verdict: what passed, without the notes."""
        return tuple(c for c in self.checks if c.ok and c.label != "note")

    @property
    def notes(self) -> tuple[str, ...]:
        return tuple(c.value for c in self.checks if c.ok and c.label == "note")

    @property
    def nexts(self) -> tuple[str, ...]:
        return tuple(c.next for c in self.failed if c.next)


# ---------- the choices ----------


def choices() -> list[Choice]:
    """The three answers in order. A cloud this release does not offer, and the cloud answer on
    Windows, say so in one line and cannot be chosen."""
    clouds = tuple(
        Cloud(
            key,
            _prices_cloud.NAMES[key],
            key in _prices_cloud.OFFERED,
            _prices_cloud.NAMES[key]
            if key in _prices_cloud.OFFERED
            else f"{_prices_cloud.NAMES[key]}  not yet supported by Prove",
        )
        for key in _prices_cloud.PROVIDERS
    )
    windows = os.name == "nt"
    offered = ", ".join(c.label for c in clouds if c.offered)
    return [
        Choice("local", LABELS["local"], True, LABELS["local"]),
        Choice("modal", LABELS["modal"], True, LABELS["modal"]),
        Choice(
            "cloud",
            LABELS["cloud"],
            not windows,
            f"{LABELS['cloud']}  not available on Windows yet"
            if windows
            else f"{LABELS['cloud']} ({offered})",
            clouds,
        ),
    ]


def question() -> tuple[str, list[str]]:
    """The one question, and the lines shown with it for an answer that cannot be chosen."""
    local, modal, cloud = choices()
    text = f"where should sweeps run?  1 {local.line} (default)  2 {modal.line}"
    if cloud.available:
        return f"{text}  3 {cloud.line}", []
    return text, [cloud.line]


def answer(typed: str) -> str | None:
    """The answer a typed line gives the question: Enter and 1 are this machine. ``None`` for
    anything that is not one of the answers offered."""
    text = typed.strip()
    if text in ("", "1"):
        return "local"
    if text == "2":
        return "modal"
    if text == "3" and choices()[2].available:
        return "cloud"
    return None


def not_offered() -> list[str]:
    """The clouds this release does not offer, a line each, shown once the cloud is chosen."""
    return [cloud.line for cloud in choices()[2].clouds if not cloud.offered]


# ---------- the table's text ----------


def _toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml(v) for v in value) + "]"
    if isinstance(value, Path):
        return json.dumps(str(value))
    if isinstance(value, float) and value == int(value):
        return f"{value:.1f}"
    return json.dumps(value)


def table(choice: str, answers: Mapping[str, Any]) -> str:
    """The where-to-run table's TOML text for ``choice``; empty for this machine."""
    if choice == "local":
        return ""
    keys = [k for k in _ORDER if k in answers] if choice == "cloud" else []
    keys += [k for k in answers if k not in keys]
    return f"[{choice}]\n" + "".join(f"{key} = {_toml(answers[key])}\n" for key in keys)


def _known(name: str) -> set[str]:
    from poisson_prove.executor_cloud import CloudOptions
    from poisson_prove.executor_modal import ImageSpec, ModalOptions

    if name in ("cloud", "burla"):
        return {f.name for f in dataclasses.fields(CloudOptions)} | {"head_url"}
    if name == "modal":
        return {f.name for f in dataclasses.fields(ModalOptions)}
    return {f.name for f in dataclasses.fields(ImageSpec)}


# ---------- writing the spec ----------


@dataclass(frozen=True)
class _Segment:
    """One where-to-run table of the file: its header's line, the line after its last key (the
    comments and blank lines below that belong to what follows), its name, and whether it is a
    table under ``[modal]``."""

    start: int
    end: int
    name: str
    sub: bool


def _segments(lines: list[str]) -> list[_Segment]:
    out = []
    i = 0
    while i < len(lines):
        found = _HEADER.match(lines[i].rstrip("\r"))
        if found and found.group(1) in ("cloud", "modal", "burla"):
            end = i + 1
            while end < len(lines) and not _ANY_HEADER.match(lines[end]):
                end += 1
            last = end
            while last > i + 1 and (
                not lines[last - 1].strip() or lines[last - 1].lstrip().startswith("#")
            ):
                last -= 1
            out.append(_Segment(i, last, found.group(1), bool(found.group(2).strip())))
            i = end
        else:
            i += 1
    return out


def _refuse_unknown(doc: Mapping[str, Any], new: str | None, carried: Mapping[str, Any]) -> None:
    """A key of a table being replaced that Prove does not know is never dropped."""
    for name in ("cloud", "burla", "modal"):
        old = doc.get(name)
        if not isinstance(old, Mapping):
            continue
        for key, value in old.items():
            if isinstance(value, Mapping) and name == "modal":
                unknown = sorted(set(value) - _known("image"))
                if unknown and new != "modal":
                    raise WhereError(
                        f'[modal.{key}] holds "{unknown[0]}", a key Prove does not know; it is '
                        "not dropped"
                    )
            elif key not in _known(name) and not (name == new and key in carried):
                raise WhereError(
                    f'[{name}] holds "{key}", a key Prove does not know; it is not dropped'
                )


def _comment(line: str, key: str, value: Any) -> str:
    """The comment a ``key = value`` line ends with, and the space before it; empty for none."""
    at = line.find("#")
    while at != -1:
        try:
            if tomllib.loads(line[:at]) == {key: value}:
                return line[len(line[:at].rstrip()) :]
        except tomllib.TOMLDecodeError:
            pass
        at = line.find("#", at + 1)
    return ""


def _merged(body: list[str], new: Mapping[str, Any]) -> list[str] | None:
    """The old table's lines with the new table's values: a line whose value stands is kept as
    it is, comment and spacing included; one whose value changes keeps its comment; a key the new
    table lacks goes; a key only the new table has is added, before the old keys when it leads
    the new table and after them otherwise. Comments and blank lines between the keys stay.

    ``None`` when a line of the old table is not one ``key = value`` (a value over several
    lines, a quoted or dotted key): the caller then writes the new table whole."""
    out: list[str] = []
    seen: list[str] = []
    for raw in body:
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        found = _KEY_LINE.match(line)
        try:
            parsed = tomllib.loads(line)
        except tomllib.TOMLDecodeError:
            return None
        if found is None or list(parsed) != [found.group(1)]:
            return None
        key = found.group(1)
        seen.append(key)
        if key not in new:
            continue
        old = parsed[key]
        if type(old) is type(new[key]) and old == new[key]:
            out.append(line)
        else:
            out.append(f"{key} = {_toml(new[key])}{_comment(line, key, old)}")
    added = [key for key in new if key not in seen]
    leading = []
    for key in new:
        if key in seen:
            break
        leading.append(key)
    trailing = [key for key in added if key not in leading]
    last = max((i for i, line in enumerate(out) if _KEY_LINE.match(line)), default=-1)
    out[last + 1 : last + 1] = [f"{key} = {_toml(new[key])}" for key in trailing]
    return [f"{key} = {_toml(new[key])}" for key in leading] + out


def _put(path: Path, text: str) -> None:
    """Write the spec by rename, so a write that is cut short leaves the spec it had."""
    target = path.resolve()
    fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        with contextlib.suppress(OSError):
            shutil.copymode(target, name)
        os.replace(name, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name)
        raise


def write(spec_path: str | Path, table_text: str) -> None:
    """Replace the spec's where-to-run table with ``table_text`` (take it out when the text is
    empty), keeping every other byte of the file as it is; a spec with none gets it appended
    after a blank line.

    A table of the same kind already there (for ``[cloud]``, a 0.2 ``[burla]`` table too) is
    changed line by line, so the reader's comments, spacing and key order inside it stay (see
    ``_merged``). A key of the old table that Prove does not know is never dropped: the write is
    refused and the spec is left as it was."""
    path = Path(spec_path)
    text = path.read_bytes().decode("utf-8")
    doc = tomllib.loads(text)
    new_doc = tomllib.loads(table_text) if table_text.strip() else {}
    new = next(iter(new_doc), None)
    carried: Mapping[str, Any] = new_doc.get(new, {}) if new else {}
    _refuse_unknown(doc, new, carried)
    eol = "\r\n" if "\r\n" in text else "\n"
    cr = eol[:-1]
    lines = text.split("\n")
    segments = _segments(lines)
    if new == "modal":
        # ``[modal]``'s image tables are the reader's, and stay under the new ``[modal]``.
        subs = [s for s in segments if s.name == "modal" and s.sub]
        segments = [s for s in segments if s not in subs]
    else:
        subs = []
    new_lines = [line + cr for line in table_text.rstrip("\n").split("\n")] if new else []
    if not segments:
        if not new_lines:
            return
        if subs:
            # Only image tables stand: the new ``[modal]`` goes above the first of them.
            at = subs[0].start
            _put(path, "\n".join([*lines[:at], *new_lines, cr, *lines[at:]]))
            return
        body = text if text.endswith("\n") else text + eol
        if not body.endswith(eol * 2):
            body += eol
        _put(path, body + "\n".join(new_lines) + "\n")
        return
    place = next((s for s in segments if new and s.name in _FAMILY[new]), segments[0])
    if new and place.name in _FAMILY[new]:
        merged = _merged(lines[place.start + 1 : place.end], carried)
        if merged is not None:
            header = re.sub(
                rf"\[\s*{place.name}\s*\]", f"[{new}]", lines[place.start].rstrip("\r"), count=1
            )
            new_lines = [line + cr for line in [header, *merged]]
    out: list[str] = []
    cuts: list[int] = []
    at = 0
    for segment in segments:
        out += lines[at : segment.start]
        if segment is place and new_lines:
            out += new_lines
        else:
            cuts.append(len(out))
        at = segment.end
    out += lines[at:]
    for cut in reversed(cuts):
        # A table taken out leaves the blank line above it beside the one below: one goes.
        below = out[cut].strip() if cut < len(out) else ""
        if cut > 0 and not out[cut - 1].strip() and not below:
            del out[cut - 1]
    _put(path, "\n".join(out))


# ---------- what the spec holds ----------


def tables(spec_path: str | Path) -> list[str]:
    """The where-to-run tables the spec holds, of ``cloud``, ``burla`` and ``modal``."""
    doc = tomllib.loads(Path(spec_path).read_bytes().decode("utf-8"))
    return [name for name in ("cloud", "burla", "modal") if isinstance(doc.get(name), Mapping)]


def both(spec_path: str | Path) -> str:
    """The refusal's sentence for a spec that holds a cloud table and ``[modal]`` together."""
    where = "poisson-prove where"
    if Path(spec_path) != Path("prove.toml"):
        where += f" --spec {spec_path}"
    return (
        f"{spec_path} holds both [cloud] and [modal], so it does not say where its sweeps run; "
        f"give --backend, or keep one table with {where} cloud, modal or local"
    )


#: The 0.2 table ``[cloud]`` took the place of. A spec that still holds one is refused by every
#: sweep, and ``where cloud`` moves it.
OLD_TABLE = "burla"


def moved() -> str:
    """What ``where`` says of a spec that still holds the 0.2 table: the answer is the reader's
    cloud account, and no sweep takes it yet."""
    return (
        f"your cloud account, by a [{OLD_TABLE}] table of 0.2; not ready: [{OLD_TABLE}] is now "
        "[cloud], and Prove starts and stops the cluster itself"
    )


def carried(choice: str, kind: str, existing: Mapping[str, Any]) -> dict[str, Any]:
    """The table already in the spec that a new ``choice`` table is written over, keeping what
    nothing changes: its own kind, and for a cloud account the 0.2 table too."""
    if choice == "cloud" and kind in ("cloud", OLD_TABLE):
        return dict(existing)
    if choice == "modal" and kind == "modal":
        return dict(existing)
    return {}


def current(spec_path: str | Path) -> tuple[str, dict[str, Any]]:
    """Which answer the spec holds and its table: ``cloud``, ``modal`` or ``local``; ``burla``
    for a 0.2 table not yet moved. For a spec holding two, the first of those."""
    doc = tomllib.loads(Path(spec_path).read_bytes().decode("utf-8"))
    for name in ("cloud", "burla", "modal"):
        if isinstance(doc.get(name), Mapping):
            return name, dict(doc[name])
    return "local", {}


def cloud_answers(existing: Mapping[str, Any], given: Mapping[str, Any]) -> dict[str, Any]:
    """The ``[cloud]`` table for the values given, over a table already there, which keeps every
    key nothing given changes (a 0.2 ``[burla]`` table's keys carry over, without ``head_url``).

    A new table gets what the step does not ask for: the ledger, the time one rollout takes, and
    the vCPU ceiling at the nodes times the machine's vCPUs. A ceiling that was following the
    nodes goes on following them; one the reader set stays."""
    answers = {k: v for k, v in existing.items() if k != "head_url"}
    was = (existing.get("nodes"), existing.get("machine_type"), existing.get("max_vcpus"))
    answers.update({k: v for k, v in given.items() if v is not None})
    answers.setdefault("provider", _PROVIDER)
    answers.setdefault("ledger", LEDGER)
    answers.setdefault("est_seconds_per_episode", EST_SECONDS)
    provider = str(answers["provider"])
    size = _prices_cloud.vcpus(provider, str(answers.get("machine_type")))
    if (
        given.get("max_vcpus") is None
        and size is not None
        and isinstance(answers.get("nodes"), int)
    ):
        old_size = _prices_cloud.vcpus(provider, str(was[1]))
        followed = isinstance(was[0], int) and old_size is not None and was[2] == was[0] * old_size
        if not existing or followed:
            answers["max_vcpus"] = answers["nodes"] * size
    return answers


def modal_answers(existing: Mapping[str, Any], given: Mapping[str, Any]) -> dict[str, Any]:
    """The ``[modal]`` table's own keys (its image tables stay in the spec as they are), with
    the cap when one is given. A cap is held against an estimate, and Modal's estimate needs
    the time one rollout takes, so a table with a cap and no such time gets the default the
    cloud table gets; the reader sets it from a run on this machine."""
    answers = {k: v for k, v in existing.items() if not isinstance(v, Mapping)}
    if given.get("max_cost") is not None:
        answers["max_cost"] = float(given["max_cost"])
    if answers.get("max_cost") is not None:
        answers.setdefault("est_seconds_per_episode", EST_SECONDS)
    return answers


def _options(answers: Mapping[str, Any]) -> Any:
    from poisson_prove.executor_cloud import CloudOptions

    known = {f.name for f in dataclasses.fields(CloudOptions)}
    unknown = sorted(set(answers) - known)
    if unknown:
        raise WhereError(f'[cloud] holds "{unknown[0]}", a key Prove does not know')
    try:
        return CloudOptions(**answers)
    except (TypeError, ValueError) as exc:
        missing = [
            f.name
            for f in dataclasses.fields(CloudOptions)
            if f.default is dataclasses.MISSING and f.name not in answers
        ]
        if missing:
            raise WhereError(f"[cloud] is missing {', '.join(missing)}") from None
        raise WhereError(f"[cloud]: {exc}") from None


def usable(answers: Mapping[str, Any]) -> None:
    """Refuse a value Prove knows it cannot use, whatever this machine's state: a cloud not
    offered, a region or machine type outside the price table with no price given, a number out
    of its range."""
    from poisson_prove.executor_cloud import CloudRefusal, resolve

    provider = str(answers.get("provider"))
    name = _prices_cloud.NAMES.get(provider, provider)
    if provider not in _prices_cloud.OFFERED:
        offered = ", ".join(_prices_cloud.NAMES[p] for p in _prices_cloud.OFFERED)
        raise WhereError(f"{name} is not yet supported by Prove; {offered} is")
    try:
        resolve(_options(answers))
    except CloudRefusal as exc:
        raise WhereError(str(exc)) from None


# ---------- readiness ----------


def check(choice: str, answers: Mapping[str, Any] | None = None) -> list[Check]:
    """The readiness checks of ``choice`` on this machine, in the order a sweep makes them, each
    with the one command that fixes it. The first that fails is the last: what follows it
    cannot be checked yet. Nothing is written, signed in or created."""
    return list(ready(choice, answers).checks)


def ready(choice: str, answers: Mapping[str, Any] | None = None) -> Readiness:
    """``check``'s results, and for a cloud account that is signed in, who is."""
    from poisson_prove.executor_cloud import CloudRefusal

    held = dict(answers or {})
    if choice == "local":
        return Readiness(())
    if choice == "modal":
        try:
            _where_checks.check_modal()
        except CloudRefusal as exc:
            fix = exc.nexts[0] if exc.nexts else None
            return Readiness((Check("signed in", str(exc), False, fix),))
        checks = [Check("signed in", "Modal", True)]
        return Readiness(tuple(checks))
    try:
        found = _where_checks.check_cloud(_options(held))
    except WhereError as exc:
        return Readiness((Check("not ready", str(exc), False),))
    except CloudRefusal as exc:
        fix = exc.nexts[0] if exc.nexts else None
        return Readiness((Check("not ready", str(exc), False, fix),))
    name = _prices_cloud.NAMES.get(found.provider, found.provider)
    checks = [Check("signed in", f"{name} {found.masked}", True)]
    checks += [Check("note", note, True) for note in found.notes]
    return Readiness(tuple(checks), found.account)


def place(choice: str, answers: Mapping[str, Any]) -> str:
    """Where the spec runs, without whether it is ready: the sentence's first half."""
    if choice != "cloud":
        return LABELS.get(choice, LABELS["local"])
    provider = str(answers.get("provider"))
    name = _prices_cloud.NAMES.get(provider, provider)
    return (
        f"your {name} account, {answers.get('region')}, {answers.get('nodes')} × "
        f"{answers.get('machine_type')}"
    )


def sentence(choice: str, answers: Mapping[str, Any], checks: list[Check]) -> str:
    """Where the spec runs and whether that is ready, in one sentence."""
    failed = [c for c in checks if not c.ok]
    if choice not in ("modal", "cloud"):
        return place(choice, answers)
    if not failed:
        return f"{place(choice, answers)}; signed in, ready"
    if choice == "modal":
        return f"{place(choice, answers)}; this machine is not signed in"
    return f"{place(choice, answers)}; not ready: {failed[0].value}"
