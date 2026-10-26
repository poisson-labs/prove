"""What PF12's two test files share: the command line in process, a page read as a tree, the
format's schemas written from the spec, and the stores both files read.

PF12 (artifacts and the static UI) is reached the way a user and a consumer reach it: the command
line, the files it writes into the store (``.poisson/``, ``events.jsonl``), and the core's boundary
as the front-door spec's section 17.1 names it (``poisson_prove.core``). Nothing here imports a
private module of Prove.

**The stores are built once per test session.** Building them runs about twenty comparisons and
a dozen small sweeps; under ``-n`` every worker would otherwise build its own. ``shared_world``
builds each store once, behind a lock file in the folder the workers share, and the other workers
wait for it and read it. Nothing a test does may change a shared store: a test that writes copies
one first (``copy_store``).
"""

from __future__ import annotations

import contextlib
import hashlib
import html.parser
import json
import os
import re
import shutil
import stat
import sys
import time
import traceback
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
OLD = TESTS / "fixtures" / "stores-0.0.1"
OLD_RUNS: dict[str, str] = json.loads((OLD / "runs.json").read_text(encoding="utf-8"))
QS_A = OLD_RUNS["quickstart_before"]
QS_B = OLD_RUNS["quickstart_after"]
PF12_FIXTURES = TESTS / "fixtures" / "pf12"
SNAPSHOTS = TESTS / "snapshots" / "pf12"
COMMAND = "poisson-prove"
MOCK = "poisson_prove.examples.mock_agent"

#: Keys planted in the environment while every shared store is built: Prove reads no key, so none
#: may appear in anything it writes (PF12.9).
PLANTED_KEYS = {
    "OPENAI_API_KEY": "sk-pf12-planted-openai-0000000000000000",
    "ANTHROPIC_API_KEY": "sk-ant-pf12-planted-anthropic-000000000",
    "MODAL_TOKEN_SECRET": "as-pf12-planted-modal-secret-00000000",
    "BURLA_API_KEY": "pf12-planted-burla-key-000000000000000",
}

#: Rule 3's verdict line: a lowercase word or phrase, two spaces, then the sentence.
FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  \S")
ISO_UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z$")
ARTIFACT_ID = re.compile(r"^[0-9a-f]{16}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


# ---------- the command line, in process ----------


@dataclass
class Result:
    code: int
    out: str
    err: str

    def lines(self) -> list[str]:
        return self.out.splitlines()


def cli(store: Path | str | None, *argv: str | Path, cwd: Path | None = None) -> Result:
    """``poisson-prove [--store STORE] ARGV…`` in this process, stdin empty, from ``cwd``."""
    from poisson_prove import cli as prove_cli

    out, err = StringIO(), StringIO()
    words = [str(a) for a in argv]
    if store is not None:
        words = ["--store", str(store), *words]
    here = Path.cwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            code = prove_cli.main(words, stdout=out, stderr=err, stdin=StringIO())
    finally:
        os.chdir(here)
    return Result(code, out.getvalue(), err.getvalue())


def doc(result: Result) -> dict[str, Any]:
    """The one strict JSON document a ``--json`` command printed."""
    parsed = json.loads(result.out, parse_constant=_no_constant)
    assert isinstance(parsed, dict), result.out[:200]
    return parsed


def _no_constant(name: str) -> Any:
    raise AssertionError(f"not strict JSON: {name}")


def first_word(text: str) -> str:
    first = text.splitlines()[0] if text else ""
    m = FIRST_LINE.match(first)
    assert m, first
    return m.group(1)


def block(text: str) -> list[str]:
    """The verdict block: the first line and its detail lines, up to the first blank line."""
    return text.split("\n\n", 1)[0].splitlines()


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[-\u2010-\u2015]", " ", text.lower()).split())


def says(text: str, words: str) -> bool:
    """A binding phrase, whatever its case and whichever hyphen or dash joins its words (PF4's
    reading R30, applied to the pages)."""
    return _norm(words) in _norm(text)


def canonical(obj: Any) -> str:
    """The format's canonical JSON: sorted keys, no spaces, UTF-8 (reading PF12-R6)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def version_major_minor() -> str:
    from poisson_prove import __version__

    major, minor = __version__.split(".")[:2]
    return f"{major}.{minor}"


def expected_id(descriptor: dict[str, Any]) -> str:
    """The format's id (Artifact Format section 5.1) recomputed from a descriptor: the first 16 hex
    of the sha256 of the canonical JSON of the kind, the tool, its major.minor version, the inputs
    and every setting but those that only record how the result was asked for (reading PF12-R6)."""
    settings = {k: v for k, v in descriptor["settings"].items() if k not in HOW_ASKED}
    payload = {
        "kind": descriptor["kind"],
        "tool": descriptor["tool"],
        "tool_version": ".".join(descriptor["tool_version"].split(".")[:2]),
        "inputs": descriptor["inputs"],
        "settings": settings,
    }
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()[:16]


#: Settings kept in ``settings`` but not in the id: they record how the result was asked for.
HOW_ASKED = frozenset({"method_chosen"})
#: Every setting that changes a comparison's result (Artifact Format section 5.1, with the tree's
#: ``max_group_mde``: reading PF12-R7). A check runs no tree: its settings are the comparison's
#: without the tree's five, and ``fail_on``.
COMPARISON_SETTINGS = frozenset(
    {"method", "method_chosen", "events", "q", "power", "horizon", "by", "depth", "permutations", "seed", "max_group_mde"}
)
TREE_SETTINGS = frozenset({"by", "depth", "permutations", "seed", "max_group_mde"})
CHECK_SETTINGS = (COMPARISON_SETTINGS - TREE_SETTINGS) | {"fail_on"}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def listing(root: Path) -> dict[str, str]:
    """Every file under ``root``, store-relative POSIX path to sha256."""
    return {p.relative_to(root).as_posix(): sha256_of(p) for p in sorted(root.rglob("*")) if p.is_file()}


def copy_store(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest, symlinks=True)
    return dest


def copy_fixture(src: Path, dest: Path) -> Path:
    """A committed fixture store as committed: frozen tests run ``report`` and ``serve`` on these
    fixtures in place, and their saves land in its ``.poisson/`` while a session runs (reading R39),
    so a copy leaves that folder out."""
    shutil.copytree(src, dest, symlinks=True, ignore=lambda folder, names: [n for n in names if n == ".poisson"])
    return dest


@contextlib.contextmanager
def read_only(root: Path) -> Iterator[None]:
    """``root`` and every folder under it without write permission, restored afterwards."""
    folders = [root, *[p for p in root.rglob("*") if p.is_dir()]]
    modes = {p: p.stat().st_mode for p in folders}
    for p in folders:
        p.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
    try:
        yield
    finally:
        for p in reversed(folders):
            p.chmod(modes[p])


@contextlib.contextmanager
def environment(**variables: str | None) -> Iterator[None]:
    """Process environment variables set (or, with None, unset) for the block."""
    saved = {k: os.environ.get(k) for k in variables}
    try:
        for k, v in variables.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------- the core, through section 17.1's boundary ----------
#
# Every name PF12's tests take from PF5 is used through the three functions below, so the two
# freezes can be checked against each other in one place (the session log's seam list, S1 to S12).


def core() -> Any:
    """S1: the core's entry point is the package ``poisson_prove.core`` (section 17)."""
    from poisson_prove import core as prove_core

    return prove_core


def as_document(obj: Any) -> dict[str, Any]:
    """S2: a core result or view's ``to_json()`` gives one strict JSON document with a ``schema``
    (PF5.9). PF12 reads it as a string of JSON text and also accepts the parsed mapping, since PF5
    is frozen in parallel and either is "one strict JSON document"; whichever PF5 freezes, the
    document must survive a strict round trip."""
    raw = obj.to_json()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        parsed = json.loads(raw, parse_constant=_no_constant)
    else:
        parsed = json.loads(json.dumps(raw, allow_nan=False), parse_constant=_no_constant)
    assert isinstance(parsed, dict) and isinstance(parsed.get("schema"), str), str(raw)[:200]
    return parsed


def view_document(store: Path, address: str) -> dict[str, Any]:
    """S3, S4: ``open_store(path)`` and ``view(store, address)``, the address being the page's
    address inside the UI exactly as the page sits there (``comparisons/<id>.html``; Y17)."""
    c = core()
    return as_document(c.view(c.open_store(store), address))


# ---------- a page, read as a tree ----------

VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
#: Elements whose text a reader does not see.
HIDDEN_TEXT = frozenset({"head", "script", "style", "template", "title", "noscript"})


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None = None
    children: list[Node | str] = field(default_factory=list)

    def iter(self) -> Iterator[Node]:
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter()

    def text(self) -> str:
        """Everything a reader sees inside this element, spaces collapsed."""
        parts: list[str] = []
        _text_into(self, parts)
        return " ".join(" ".join(parts).split())

    def ancestors(self) -> Iterator[Node]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def find_all(self, tag: str) -> list[Node]:
        return [n for n in self.iter() if n.tag == tag]


def _text_into(node: Node, parts: list[str]) -> None:
    if node.tag in HIDDEN_TEXT:
        return
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        else:
            _text_into(child, parts)


class _Builder(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {})
        self.current = self.root
        self.raw_tags: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: (v if v is not None else "") for k, v in attrs}
        self.raw_tags.append((tag, values))
        node = Node(tag, values, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: (v if v is not None else "") for k, v in attrs}
        self.raw_tags.append((tag, values))
        self.current.children.append(Node(tag, values, self.current))

    def handle_endtag(self, tag: str) -> None:
        node: Node | None = self.current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data: str) -> None:
        self.current.children.append(data)


@dataclass
class Page:
    path: Path
    address: str
    source: str
    root: Node
    tags: list[tuple[str, dict[str, str]]]

    def body_text(self) -> str:
        bodies = self.root.find_all("body")
        return bodies[0].text() if bodies else self.root.text()

    def facts(self) -> list[Node]:
        return [n for n in self.root.iter() if "data-fact" in n.attrs]

    def head(self) -> Node:
        (head,) = self.root.find_all("head")
        return head


def read_page(ui: Path, path: Path) -> Page:
    source = path.read_text(encoding="utf-8")
    builder = _Builder()
    builder.feed(source)
    builder.close()
    return Page(path, path.relative_to(ui).as_posix(), source, builder.root, builder.raw_tags)


def pages_of(ui: Path) -> list[Path]:
    return sorted(p for p in ui.rglob("*.html"))


# ---------- JSON pointers into a view ----------


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar in a JSON document with its JSON pointer (RFC 6901)."""
    if isinstance(document, dict):
        for key, value in document.items():
            yield from leaves(value, f"{prefix}/{_escape(str(key))}")
    elif isinstance(document, list):
        for i, value in enumerate(document):
            yield from leaves(value, f"{prefix}/{i}")
    else:
        yield prefix, document


def resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    assert pointer.startswith("/"), pointer
    node = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            assert token.isdigit(), pointer
            node = node[int(token)]
        else:
            assert isinstance(node, dict) and token in node, pointer
            node = node[token]
    return node


_NUMBER = re.compile(r"[+\-\u2212]?\d+(?:\.\d+)?(?:e[+\-\u2212]?\d+)?%?", re.IGNORECASE)
_DURATION = re.compile(r"(?:(\d+) h)?\s*(?:(\d+) min)?\s*(?:(\d+(?:\.\d+)?) s)?")


def shows_number(text: str, value: float) -> bool:
    """Whether ``text`` prints ``value`` as rule 10 does: some number in it equals the value at the
    precision it was printed to (a percentage read over 100, a duration read in seconds)."""
    plain = text.replace(",", "").replace("\u2212", "-")
    # a whole token only: never a run of digits inside a hex id or a word (``c3bc1b052e785f44``)
    for m in re.finditer(rf"(?<![0-9A-Za-z])(?>{_NUMBER.pattern})(?![0-9A-Za-z])", plain, re.IGNORECASE):
        token = m.group(0)
        percent = token.endswith("%")
        body = token.rstrip("%")
        try:
            shown = float(body)
        except ValueError:
            continue
        if percent:
            shown /= 100.0
        if "e" in body.lower():
            mantissa = body.lower().split("e")[0]
            decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
            exponent = int(body.lower().split("e")[1].replace("\u2212", "-"))
            if abs(exponent) > 400:
                continue  # no float has this exponent: a whole token of digits, an e and digits
            tolerance = 0.5 * 10 ** (exponent - decimals)
        else:
            decimals = len(body.split(".")[1]) if "." in body else 0
            tolerance = 0.5 * 10 ** (-decimals) * (0.01 if percent else 1.0)
        if abs(shown - value) <= tolerance * (1 + 1e-9) + 1e-15:
            return True
    for m in _DURATION.finditer(text):
        if not any(m.groups()):
            continue
        hours, minutes, seconds = (float(g) if g else 0.0 for g in m.groups())
        total = hours * 3600 + minutes * 60 + seconds
        if abs(total - value) <= 0.5 + 0.05 * abs(value):
            return True
    return False


# ---------- the format's schemas (Artifact Format sections 3 to 5, written when the PF12 tests were frozen) ----------

_UTC = {"type": "string", "pattern": ISO_UTC.pattern}

STORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["format", "created_by", "created_at", "writers"],
    "properties": {
        "format": {"const": "poisson.store/1"},
        "created_by": {
            "type": "object",
            "required": ["tool", "version"],
            "properties": {"tool": {"type": "string", "minLength": 1}, "version": {"type": "string", "minLength": 1}},
        },
        "created_at": _UTC,
        "writers": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["tool", "version", "first_write"],
                "properties": {
                    "tool": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "minLength": 1},
                    "first_write": _UTC,
                },
            },
        },
    },
}

_FILE_ENTRY: dict[str, Any] = {
    "type": "object",
    "required": ["path", "role", "media_type", "sha256"],
    "properties": {
        "path": {"type": "string", "pattern": r"^[^/][^\\]*$"},
        "role": {"enum": ["result", "table", "chart", "report", "log"]},
        "media_type": {"type": "string", "minLength": 3},
        "schema": {"type": "string", "pattern": r"^[a-z0-9-]+\.[a-z0-9-]+/\d+$"},
        "sha256": {"type": "string", "pattern": SHA256.pattern},
        "data": {"type": "string"},
    },
}

ARTIFACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["format", "kind", "id", "tool", "tool_version", "created_at", "inputs", "settings", "summary", "files"],
    "properties": {
        "format": {"const": "poisson.artifact/1"},
        "kind": {"enum": ["comparison", "check"]},
        "id": {"type": "string", "pattern": ARTIFACT_ID.pattern},
        "tool": {"const": "poisson-prove"},
        "tool_version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+"},
        "created_at": _UTC,
        "inputs": {
            "type": "object",
            "required": ["runs"],
            "properties": {"runs": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string", "minLength": 1}}},
        },
        "settings": {
            "type": "object",
            "required": sorted(COMPARISON_SETTINGS & CHECK_SETTINGS),
            "properties": {
                "method": {"enum": ["fisher_bh", "mcnemar_bh", "logrank_bh"]},
                "method_chosen": {"enum": ["default", "named"]},
                "events": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name", "kind"],
                        "properties": {"name": {"type": "string"}, "kind": {"enum": ["failure", "success", None]}},
                    },
                },
                "q": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                "power": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                "horizon": {"type": ["number", "null"]},
                "by": {"type": ["string", "null"]},
                "depth": {"type": "integer"},
                "permutations": {"type": "integer", "minimum": 1},
                "seed": {"type": "integer"},
                "max_group_mde": {"type": "number"},
                "fail_on": {"enum": ["worse", "any", "higher", "lower"]},
            },
        },
        "summary": {
            "type": "object",
            "required": ["verdict", "sentence"],
            "properties": {"verdict": {"type": "string", "minLength": 1}, "sentence": {"type": "string", "minLength": 1}},
        },
        "files": {"type": "array", "minItems": 1, "items": _FILE_ENTRY},
    },
}

EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schema", "at", "kind", "detail"],
    "properties": {
        "schema": {"const": "poisson.run-event/1"},
        "at": _UTC,
        "kind": {"type": "string", "minLength": 1},
        "detail": {"type": "object"},
    },
}

PROGRESS_KEYS = ("done", "kept", "errored", "total")
#: Section 17.2's grammar within a run, one letter per event.
EVENT_LETTERS = {"planned": "P", "started": "S", "progress": "g", "note": "n", "finished": "F", "interrupted": "I", "resumed": "R"}
EVENT_GRAMMAR = re.compile(r"^PS[gn]*[FI](R[gn]*[FI])*$")


def validate(document: Any, schema: dict[str, Any]) -> None:
    import jsonschema

    jsonschema.Draft202012Validator(schema).validate(document)


#: The long-form table's key columns, in order, with their Arrow types (Artifact Format 5.3).
TABLE_COLUMNS = (
    ("artifact_id", "string"), ("event", "string"), ("condition", "string"), ("condition_hash", "string"),
    ("arm", "string"), ("metric", "string"), ("value", "double"), ("note", "string"), ("level", "double"),
)
#: Every metric a comparison's table holds, from each condition's row in the result (reading
#: PF12-R10): per arm (``a`` and ``b``) the counts, the rate and the share with its Wilson bounds;
#: for the pair (``both``) the change, the test and its adjusted p-values, the interval on the change,
#: the limits both ways at the row's level and at the verdict's, and the smallest possible p.
ARM_METRICS = {"n": "n", "events": "events", "rate": "rate"}
SHARE_METRICS = ("share", "share_lo", "share_hi")
BOTH_METRICS = ("delta", "stat", "p", "q", "q_holm", "ci_lo", "ci_hi", "mde_rise", "mde_fall", "mde_rise_verdict", "mde_fall_verdict", "p_min")
#: The metrics whose rows carry a level, and where the level comes from in the row.
LEVELLED = {"share": "share", "share_lo": "share", "share_hi": "share", "ci_lo": "ci_level", "ci_hi": "ci_level", "mde_rise": "mde_level", "mde_fall": "mde_level"}


# ---------- stores written by hand (through the public Store) ----------

HORIZON = 10.0


def arm(k: int, n: int, *, event: str = "fell", start: float = 1.0, step: float = 0.1, other: str = "ok") -> list[tuple[int, str | None, float]]:
    """``n`` runs of which the first ``k`` ended in ``event`` at ``start``, ``start + step``, …; the
    rest end in ``other`` at the horizon."""
    return [(i, event, start + step * i) if i < k else (i, other, HORIZON) for i in range(n)]


def errored(rows: list[tuple[int, str | None, float]], how_many: int) -> list[tuple[int, str | None, float]]:
    """The same runs with the last ``how_many`` errored (no outcome)."""
    return [(i, None, t) if i >= len(rows) - how_many else (i, o, t) for i, o, t in rows]


def write_run(
    root: Path,
    run_id: str,
    cells: dict[str, list[tuple[int, str | None, float]]],
    *,
    created_at: str,
    axis: str = "cell",
    configs: dict[str, dict[str, Any]] | None = None,
    axis_types: dict[str, str] | None = None,
    case_ids: dict[str, list[str]] | None = None,
    complete: bool = True,
    salt: str | None = None,
) -> None:
    from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

    store = Store(root)
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="pf12-target",
            t_unit="steps",
            run_salt=salt or f"salt-{run_id}",
            axis_types=dict(axis_types or {axis: "categorical"}),
            backend="local",
            environment={"max_mde_accepted": 0.2},
            created_at=created_at,
        )
    )
    records = []
    for name, rows in cells.items():
        config = dict((configs or {}).get(name, {axis: name}))
        for rep, outcome, t in rows:
            meta: dict[str, Any] = {}
            if case_ids and name in case_ids:
                meta["case_id"] = case_ids[name][rep % len(case_ids[name])]
            common = dict(
                run_id=run_id, config_hash=config_hash(config), config=config, seed=1000 + rep,
                replicate_index=rep, t=t, horizon=HORIZON, confidence=None, meta=meta,
                wall_time=0.01, backend_meta={},
            )
            if outcome is None:
                records.append(EpisodeRecord(outcome=None, error="ValueError: the rollout raised", **{**common, "t": None, "horizon": None}))
            else:
                records.append(EpisodeRecord(outcome=outcome, error=None, **common))
    store.append(run_id, records)
    if complete:
        store.mark_complete(run_id)


def stamp(index: int) -> tuple[str, str]:
    """A run id and its creation time, one minute apart per index, in the order they were made."""
    hour, minute = 10 + index // 60, index % 60
    return f"20261024T{hour:02d}{minute:02d}00Z-p{index:03d}", f"2026-10-24T{hour:02d}:{minute:02d}:00Z"


def config_hash_of(config: dict[str, Any]) -> str:
    from poisson_prove.store import config_hash

    return config_hash(config)


# ---------- the shared stores ----------


def _shared_base(factory: pytest.TempPathFactory) -> Path:
    base = factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        base = base.parent
    path = base / "pf12-shared"
    path.mkdir(parents=True, exist_ok=True)
    return path


def shared_world(factory: pytest.TempPathFactory, name: str, build: Callable[[Path], dict[str, Any]]) -> tuple[Path, dict[str, Any]]:
    """The folder ``name`` built once for the whole session by ``build(folder)``, which returns what
    the tests need to know about it (written beside it as JSON); every other worker waits."""
    base = _shared_base(factory)
    folder, done, failed, lock = base / name, base / f"{name}.json", base / f"{name}.error", base / f"{name}.lock"
    deadline = time.monotonic() + 1800  # a builder that died holding the lock fails the waiters, not hangs them
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"the shared store {name} was not built within 30 min ({lock} is held)")
        if done.exists():
            return folder, json.loads(done.read_text(encoding="utf-8"))
        if failed.exists():
            raise RuntimeError(f"building the shared store {name} failed:\n{failed.read_text(encoding='utf-8')}")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            time.sleep(0.2)
            continue
        try:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir()
            home = base / f"{name}-home"
            home.mkdir(exist_ok=True)
            with environment(HOME=str(home), POISSON_PROVE_STORE=None, PROOFLOAD_STORE=None, XDG_CACHE_HOME=None, **PLANTED_KEYS):
                facts = build(folder)
            tmp = done.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(facts, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(done)
        except BaseException:
            failed.write_text(traceback.format_exc(), encoding="utf-8")
            raise
        finally:
            os.close(fd)


def saved_id(result: Result, kind: str, store: Path) -> str:
    """The id of what a save wrote, from its ``  saved  <kind> <id>`` detail line (section 18.2),
    which shows the id as rule 10 shows a hash in text, its first 12 hex (reading R1); the folder
    under ``.poisson/artifacts/<kind>/`` carries the whole id."""
    found = [line.removeprefix(f"  saved  {kind} ") for line in result.lines() if line.startswith(f"  saved  {kind} ")]
    assert len(found) == 1, (result.code, result.out, result.err)
    assert re.match(r"^[0-9a-f]{12}$", found[0]), found
    folder = store / ".poisson" / "artifacts" / kind
    (whole,) = [p.name for p in folder.iterdir() if ARTIFACT_ID.match(p.name) and p.name.startswith(found[0])]
    return whole


SMALL_SPEC = """\
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 6

[axes.task_id]
type = "categorical"
values = ["search", "refund"]
"""
LOOSE = ("--max-mde", "1")


def raising_rollout(cfg: Any, seed: int) -> Any:
    """A rollout that always raises, so every rollout of a sweep errors."""
    raise ValueError("this rollout always raises")


def build_old(folder: Path) -> dict[str, Any]:
    """The 0.0.1 store, copied; ``runs --json`` read before anything is added; the quickstart pair
    compared with ``diff --save`` (both runs as 0.0.1 wrote them, paired at sweep time, events
    inferred); then ``ui``."""
    store = copy_fixture(OLD / "store", folder / "prove-runs")
    before_runs = doc(cli(store, "runs", "--json"))
    before_latest = doc(cli(store, "diff", "--json"))
    saved = cli(store, "diff", QS_A, QS_B, "--save")
    assert saved.code == 0, saved.err
    built = cli(store, "ui")
    built_json = cli(store, "ui", "--json")
    return {
        "store": str(store),
        "runs_before": before_runs,
        "latest_before": [before_latest["verdict"], before_latest["sentence"], before_latest["next"]],
        "comparison": saved_id(saved, "comparison", store),
        "diff_save": saved.__dict__,
        "ui": built.__dict__,
        "ui_json": built_json.__dict__,
    }


#: The pairs of the hand-written store, each as (A's cells, B's cells, the command's arguments).
def _stats_pairs() -> dict[str, dict[str, Any]]:
    grid_configs = {f"{t}-{r}": {"task": t, "rate": r} for t in ("a", "b") for r in (0.1, 0.5)}
    grid_a = {"a-0.1": arm(4, 40), "a-0.5": arm(20, 40), "b-0.1": arm(4, 40), "b-0.5": arm(20, 40)}
    grid_b = {"a-0.1": arm(4, 40), "a-0.5": arm(34, 40), "b-0.1": arm(4, 40), "b-0.5": arm(20, 40)}
    return {
        # A trade: one condition worse, one safer, the rest unchanged, with a top and a zero row.
        "trade": dict(
            a={"up": arm(4, 40), "down": arm(30, 40), "same": arm(10, 40), "top": arm(40, 40), "near_top": arm(38, 40), "zero": arm(0, 40)},
            b={"up": arm(30, 40), "down": arm(4, 40), "same": arm(10, 40), "top": arm(40, 40), "near_top": arm(38, 40), "zero": arm(0, 40)},
            argv=["--event", "fell:failure", "--method", "fisher_bh"],
        ),
        # Nothing moved, and every limit is under the threshold: no significant change.
        "nothing": dict(
            a={"p": arm(120, 400), "q": arm(200, 400)},
            b={"p": arm(120, 400), "q": arm(200, 400)},
            argv=["--event", "fell:failure", "--method", "fisher_bh"],
        ),
        # Nothing moved on five runs a side: too small to tell.
        "tiny": dict(
            a={"p": arm(1, 5), "q": arm(2, 5)},
            b={"p": arm(1, 5), "q": arm(2, 5)},
            argv=["--event", "fell:failure", "--method", "fisher_bh"],
        ),
        # B is partial: the peeking caveat names it.
        "peeking": dict(
            a={"p": arm(10, 60), "q": arm(30, 60)},
            b={"p": arm(30, 50), "q": arm(25, 50)},
            argv=["--event", "fell:failure", "--method", "fisher_bh"],
            b_complete=False,
        ),
        # Errored episodes differ between the runs in one condition: the attrition warning.
        "errors": dict(
            a={"e1": arm(10, 60), "e2": arm(12, 60)},
            b={"e1": errored(arm(10, 60), 25), "e2": arm(12, 60)},
            argv=["--event", "fell:failure", "--method", "fisher_bh"],
        ),
        # Log-rank, where another outcome's share moved: the cause-specific hazard and its note.
        "logrank": dict(
            a={"c1": arm(10, 60), "c2": arm(30, 60)},
            b={"c1": [(i, o if i < 10 else ("slow" if i < 40 else "ok"), t) for i, o, t in arm(10, 60)], "c2": arm(30, 60)},
            argv=["--event", "fell:failure", "--method", "logrank_bh"],
        ),
        # Two axes, for the heatmap and for the settings that move the tree.
        "grid": dict(
            a=grid_a, b=grid_b, configs=grid_configs, axis_types={"task": "categorical", "rate": "continuous"},
            argv=["--event", "fell:failure", "--method", "fisher_bh"],
        ),
    }


STATS_PAIRS = tuple(_stats_pairs())


def build_stats(folder: Path) -> dict[str, Any]:
    """One store holding every hand-written pair, each saved with ``diff --save``; the trade also
    saved as a check; a pair whose condition ran two cases, refused; then ``ui``."""
    store = folder / "prove-runs"
    facts: dict[str, Any] = {"store": str(store), "pairs": {}}
    index = 0
    for name, pair in _stats_pairs().items():
        a_id, a_at = stamp(index)
        b_id, b_at = stamp(index + 1)
        index += 2
        kw = {k: pair[k] for k in ("configs", "axis_types") if k in pair}
        if "configs" in pair:
            kw["axis"] = "task"
        write_run(store, a_id, pair["a"], created_at=a_at, **kw)
        write_run(store, b_id, pair["b"], created_at=b_at, complete=pair.get("b_complete", True), **kw)
        saved = cli(store, "diff", a_id, b_id, *pair["argv"], "--save")
        assert saved.code == 0, (name, saved.err)
        facts["pairs"][name] = {"a": a_id, "b": b_id, "argv": pair["argv"], "comparison": saved_id(saved, "comparison", store), "diff_save": saved.__dict__}
    trade = facts["pairs"]["trade"]
    checked = cli(store, "check", trade["a"], trade["b"], "--event", "fell:failure", "--method", "fisher_bh", "--save")
    assert checked.code == 4, checked.err
    facts["check"] = {"id": saved_id(checked, "check", store), "result": checked.__dict__}
    # One condition whose episodes ran two cases: every comparing verb refuses, and saves nothing.
    a_id, a_at = stamp(index)
    b_id, b_at = stamp(index + 1)
    write_run(store, a_id, {"m": arm(10, 40), "n": arm(10, 40)}, created_at=a_at, case_ids={"m": ["case-1", "case-2"]})
    write_run(store, b_id, {"m": arm(10, 40), "n": arm(10, 40)}, created_at=b_at, case_ids={"m": ["case-1", "case-2"]})
    facts["cases"] = {"a": a_id, "b": b_id}
    built = cli(store, "ui")
    assert built.code == 0, built.err
    facts["ui"] = built.__dict__
    return facts


def build_sweep(folder: Path) -> dict[str, Any]:
    """Runs written by sweeps in 0.1.0's format: one complete; one stopped by ``--max-rollouts``
    then resumed; one paired with the first; one whose every rollout raised; then ``ui``."""
    work = folder / "work"
    work.mkdir()
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    store = work / "prove-runs"
    target = ("--target", f"{MOCK}:rollout")
    first = cli(store, "sweep", spec, *target, "--yes", *LOOSE, cwd=work)
    assert first.code == 0, first.err
    from poisson_prove.store import Store

    (complete,) = Store(store).runs()
    stopped = cli(store, "sweep", spec, *target, "--max-rollouts", "5", "--yes", *LOOSE, cwd=work)
    assert stopped.code == 3, stopped.err
    (partial,) = [r for r in Store(store).runs() if r != complete]
    events_when_stopped = (store / partial / "events.jsonl").read_text(encoding="utf-8")
    resumed = cli(store, "sweep", spec, "--resume", partial, "--yes", *LOOSE, cwd=work)
    assert resumed.code == 0, resumed.err
    paired = cli(store, "sweep", spec, "--target", f"{MOCK}:rollout_patched", "--pair-with", complete, "--yes", *LOOSE, cwd=work)
    assert paired.code == 0, paired.err
    (paired_id,) = [r for r in Store(store).runs() if r not in (complete, partial)]
    raising = cli(store, "sweep", spec, "--target", "pf12_support:raising_rollout", "--yes", *LOOSE, cwd=work)
    assert raising.code == 3, raising.err
    (raised_id,) = [r for r in Store(store).runs() if r not in (complete, partial, paired_id)]
    built = cli(store, "ui")
    assert built.code == 0, built.err
    return {
        "store": str(store),
        "spec": str(spec),
        "work": str(work),
        "runs": {"complete": complete, "resumed": partial, "paired": paired_id, "errored": raised_id},
        "events_when_stopped": events_when_stopped,
        "results": {"first": first.__dict__, "stopped": stopped.__dict__, "resumed": resumed.__dict__, "paired": paired.__dict__, "errored": raising.__dict__},
    }


#: The writing verbs, in the order ``build_bytes`` runs them over a copy of the 0.0.1 store.
BYTE_STEPS = ("sweep", "diff --save", "check --save", "report", "serve --json", "ui")


def build_bytes(folder: Path) -> dict[str, Any]:
    """Every writing verb run in turn over one copy of the 0.0.1 store, with the store's files and
    their digests read before the first and after each (PF0.6's byte check, extended)."""
    store = copy_fixture(OLD / "store", folder / "prove-runs")
    work = folder / "work"
    work.mkdir()
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    steps: dict[str, list[str]] = {
        "sweep": ["sweep", str(spec), "--target", f"{MOCK}:rollout", "--yes", *LOOSE],
        "diff --save": ["diff", QS_A, QS_B, "--save"],
        "check --save": ["check", QS_A, QS_B, "--event", "violated:failure", "--save"],
        "report": ["report", QS_A, QS_B, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(work / "report")],
        "serve --json": ["serve", QS_A, QS_B, "--x", "task_id", "--y", "tool_fail_rate", "--event", "timeout", "--json"],
        "ui": ["ui"],
    }
    assert tuple(steps) == BYTE_STEPS
    record: dict[str, Any] = {"store": str(store), "before": listing(store), "after": {}, "results": {}}
    for name, argv in steps.items():
        result = cli(store, *argv, cwd=work)
        record["results"][name] = result.__dict__
        record["after"][name] = listing(store)
    return record


def build_resume_old(folder: Path) -> dict[str, Any]:
    """A 0.0.1 run left partial (its last seven episode parts taken away and its status word set to
    ``partial``, the one byte change 0.0.1 itself made while a run was going), then resumed by
    0.1.0: the one place an existing file may change (PF12.1)."""
    store = folder / "prove-runs"
    store.mkdir()
    run = store / QS_A
    shutil.copytree(OLD / "store" / QS_A, run)
    for part in sorted((run / "episodes").glob("part-*.parquet"))[8:]:
        part.unlink()
    manifest = run / "manifest.json"
    text = manifest.read_text(encoding="utf-8")
    assert text.count('"status": "complete"') == 1
    manifest.write_text(text.replace('"status": "complete"', '"status": "partial"'), encoding="utf-8")
    work = folder / "work"
    work.mkdir()
    spec = work / "spec.toml"
    spec.write_text(
        'target_id = "mock-agent@v0"\nt_unit = "tool_calls"\nreplicates = 100\n\n'
        '[axes.task_id]\ntype = "categorical"\nvalues = ["search", "checkout", "refund"]\n\n'
        '[axes.tool_fail_rate]\ntype = "continuous"\nvalues = [0.0, 0.3, 0.55]\n',
        encoding="utf-8",
    )
    before = listing(store)
    result = cli(store, "sweep", spec, "--resume", QS_A, "--target", f"{MOCK}:rollout", "--yes", *LOOSE, cwd=work)
    return {"store": str(store), "before": before, "after": listing(store), "result": result.__dict__}


# ---------- the look's static-UI tokens (look file sha256 92e71488…d85f, Y14) ----------


def look_tokens() -> dict[str, tuple[str, str]]:
    """Each colour token of the look file's static-UI section with its light and dark value, read
    from the section as it was written (``tests/fixtures/pf12/look-static-ui.md``)."""
    text = (PF12_FIXTURES / "look-static-ui.md").read_text(encoding="utf-8")
    tokens = {}
    for m in re.finditer(r"^\| `(--[a-z]+)` \| [^|]+ \| `(#[0-9a-f]{6})` \| `(#[0-9a-f]{6})` \|$", text, re.MULTILINE):
        tokens[m.group(1)] = (m.group(2), m.group(3))
    assert len(tokens) == 12, sorted(tokens)
    return tokens


#: The tokens a chart may draw with (the look's static-UI section: the four meanings' colours never
#: appear in a chart).
CHART_TOKENS = ("--rise", "--fall", "--mid", "--after", "--dim", "--rule", "--text", "--bg", "--surface")
MEANING_TOKENS = ("--ok", "--warn", "--bad")


# ---------- snapshots (PF12.13) ----------

#: The command that rewrites the snapshots, the one documented way (section 10.6).
SNAPSHOT_COMMAND = "python -m pytest tests -k snapshot --update-snapshots"


def normalise(text: str, keep: set[str]) -> str:
    """A page with what changes from build to build replaced: every UTC time not in ``keep`` (the
    times the fixture's runs recorded) by ``<time>``, and the running version by ``<version>``."""
    from poisson_prove import __version__

    def time_of(m: re.Match[str]) -> str:
        return m.group(0) if m.group(0) in keep else "<time>"

    text = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", time_of, text)
    return re.sub(rf"(?<![\d.]){re.escape(__version__)}(?![\d.])", "<version>", text)


def fixture_times(store: Path) -> set[str]:
    times: set[str] = set()
    for manifest in store.glob("*/manifest.json"):
        times |= set(re.findall(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", manifest.read_text(encoding="utf-8")))
    return times


if str(TESTS) not in sys.path:  # the raising rollout is imported by name from this module
    sys.path.insert(0, str(TESTS))
