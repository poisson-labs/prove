"""What the core's operations return: typed results with a strict JSON form, the events a sweep
reports, and the two ways an operation stops (a refusal, an interruption)."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cached_property
from typing import Any, ClassVar

from poisson_prove import _look

_ENVELOPE = ("schema", "verdict", "sentence", "next")


def _document(
    kind: str, verdict: str, sentence: str, payload: Mapping[str, Any], nexts: Sequence[str]
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema": f"poisson-prove.{kind}/1",
        "verdict": verdict,
        "sentence": sentence,
    }
    for key, value in payload.items():
        if key not in _ENVELOPE:
            doc[key] = value
    doc["next"] = list(nexts)
    strict: dict[str, Any] = _look.strict(_look.native(doc))
    return strict


class LazyPayload(Mapping[str, Any]):
    """A result's own keys, built the first time something reads them: a face that renders only
    the word and the page pays nothing for the document."""

    def __init__(self, build: Callable[[], Mapping[str, Any]]) -> None:
        self._build: Callable[[], Mapping[str, Any]] | None = build
        self._value: Mapping[str, Any] = {}

    def _built(self) -> Mapping[str, Any]:
        if self._build is not None:
            self._value, self._build = self._build(), None
        return self._value

    def __getitem__(self, key: str) -> Any:
        return self._built()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._built())

    def __len__(self) -> int:
        return len(self._built())


@dataclass(frozen=True, eq=False)
class Result:
    """A result every face renders: its word, its sentence, its own keys and the next commands."""

    KIND: ClassVar[str] = "result"
    verdict: str
    sentence: str
    payload: Mapping[str, Any]
    next: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """One strict JSON document: ``schema``, ``verdict``, ``sentence``, the result's own keys,
        ``next`` last."""
        return _document(self.KIND, self.verdict, self.sentence, self.payload, self.next)


@dataclass(frozen=True, eq=False)
class WrittenFiles(Result):
    """What ``init`` wrote."""

    KIND: ClassVar[str] = "written-files"
    paths: tuple[str, ...] = ()
    #: The text that would be written, when nothing was (``init --agent --print``).
    text: str = ""


@dataclass(frozen=True, eq=False)
class Fold:
    """A declaration's paired replay, folded into a report's text and written beside it."""

    bundle: Any

    @property
    def texts(self) -> dict[str, str]:
        from poisson_prove.paired import _artifact_text

        return {name: _artifact_text(artifact) for name, artifact in self.bundle.artifacts.items()}

    def fold_markdown(self, markdown: str) -> str:
        """``report.md`` with the paired-replay sections in it."""
        from poisson_prove.paired import _fold_markdown

        return str(_fold_markdown(markdown, self.bundle))

    def fold_html(self, page: str) -> str:
        """The receipt with the paired-replay sections in it."""
        from poisson_prove.paired import _fold_html

        return str(_fold_html(page, self.bundle))


@dataclass(frozen=True, eq=False)
class Spec:
    """A sweep spec as it was read, and the file it was read from."""

    spec: Any
    path: str | None = None


@dataclass(frozen=True, eq=False)
class RunInfo:
    """One run as the runs table lists it."""

    entry: Mapping[str, Any]
    created: str = ""

    @property
    def run_id(self) -> str:
        return str(self.entry["run_id"])

    @property
    def run_name(self) -> str:
        return str(self.entry["run_name"])

    def to_json(self) -> dict[str, Any]:
        """The run's row as ``runs --json`` lists it."""
        return dict(_look.strict(_look.native(dict(self.entry))))


class RunList(list[RunInfo]):
    """The runs of a store, newest first, with the document ``runs --json`` prints."""

    def __init__(self, runs: Sequence[RunInfo], *, store: str, unreadable: Sequence[str]) -> None:
        super().__init__(runs)
        self.store = store
        self.unreadable = list(unreadable)

    @property
    def sentence(self) -> str:
        count = _look.fmt_count(len(self))
        plural = "run" if len(self) == 1 else "runs"
        return f"{count} {plural} in {self.store}" if self else f"no runs in {self.store}"

    @property
    def next(self) -> tuple[str, ...]:
        if self:
            return ()
        import shlex

        return (
            f"poisson-prove --store {shlex.quote(self.store)} "
            "sweep SPEC.toml --target pkg.module:rollout",
        )

    def to_json(self) -> dict[str, Any]:
        """The runs document: ``schema``, ``verdict``, ``sentence``, ``store``, ``runs``,
        ``next``."""
        payload = {"store": self.store, "runs": [run.to_json() for run in self]}
        return _document("runs", "ok", self.sentence, payload, self.next)


@dataclass(frozen=True, eq=False)
class RunDetail(Result):
    """One run: its manifest's facts, and per event its conditions' outcomes with their
    intervals, at the horizon read."""

    KIND: ClassVar[str] = "run"
    run_id: str = ""
    run_name: str = ""
    manifest: Any = None
    cells: Any = None
    events: tuple[str, ...] = ()
    non_event: str | None = None
    inferred: bool = False
    horizon: float = 0.0
    shares: Mapping[str, Any] = field(default_factory=dict)
    design: Mapping[str, Any] | None = None
    observations: tuple[int, int] = (0, 0)
    declarations: Any = None
    fixed: Mapping[str, Any] = field(default_factory=dict)

    @property
    def inference(self) -> str | None:
        """Where a defaulted event set came from, as the report prints it; None when the events
        were named."""
        if not self.inferred:
            return None
        if self.non_event is None:
            return (
                f"inferred: no event was given, so the event set is {', '.join(self.events)}, "
                "the failures and successes the run declared"
            )
        return (
            f"inferred: no event was given, so the event set is {', '.join(self.events)}; "
            f"the non-event is {self.non_event}, the most frequent outcome"
        )


@dataclass(frozen=True, eq=False)
class EpisodePage(Result):
    """The episodes behind an event in a run, a page of them."""

    KIND: ClassVar[str] = "episodes"


@dataclass(frozen=True, eq=False)
class InspectResult(Result):
    """The episodes ``inspect`` shows, with what its text needs to print each one."""

    KIND: ClassVar[str] = "inspect"
    rows: tuple[Mapping[str, Any], ...] = ()
    provenance: tuple[str, ...] = ()
    reproduce: Mapping[str, Any] = field(default_factory=dict)
    observation_cap: Mapping[str, Any] | None = None


@dataclass(frozen=True, eq=False)
class PairedResult(Result):
    """``paired``'s files, or its cap check."""

    KIND: ClassVar[str] = "paired"
    artifacts: Mapping[str, str] = field(default_factory=dict)
    default_out: str = ""
    details: tuple[tuple[str, str], ...] = ()
    cap_reached: bool = False


@dataclass(frozen=True, eq=False)
class Comparison(Result):
    """Two runs compared: the word, its sentence, the verdict block's lines, and every fact the
    statistics returned, each as its JSON carries it.

    Its document and its tree are built the first time something reads them, so ``to_json()``
    is the way to get its JSON: ``json.dumps`` on the result, or on its ``payload`` before
    anything has read it, is not supported. It pickles whether or not it has been read (it
    builds itself in full first), and two comparisons are equal when their documents, verdict
    lines and notes are.
    """

    KIND: ClassVar[str] = "comparison"
    detail: tuple[tuple[str, str], ...] = ()
    method_chosen: str = "default"
    run_a: str = ""
    run_b: str = ""
    names: Mapping[str, str] = field(default_factory=dict)
    multi: Any = None
    grow: Callable[[], Any] | None = field(default=None, repr=False)
    others: Mapping[str, Any] = field(default_factory=dict)
    manifests: tuple[Any, ...] = ()
    writers: Mapping[str, str] = field(default_factory=dict)
    observations: tuple[tuple[int, int], ...] = ()
    declarations: tuple[Any, ...] = ()
    rows_counts: tuple[int, int] = (0, 0)
    tallies: tuple[Any, ...] = ()
    fixed: Mapping[str, Any] = field(default_factory=dict)
    bundle: Any = None
    title: str = ""
    #: The tree's settings as the comparison was asked for them, recorded when it is saved.
    tree_settings: Mapping[str, Any] = field(default_factory=dict)
    #: ``report``'s command with the runs' names, the ``next`` a saved comparison carries when
    #: the verb that computed it printed none.
    report_next: tuple[str, ...] = ()
    #: Both runs' episodes, read once, for the charts a saved comparison draws.
    frames: Any = field(default=None, repr=False)

    @property
    def method(self) -> str:
        return str(self.multi.method)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Comparison) or type(other) is not type(self):
            return NotImplemented
        return (self.to_json(), self.detail, self.notes) == (
            other.to_json(),
            other.detail,
            other.notes,
        )

    __hash__ = None  # type: ignore[assignment]

    def __getstate__(self) -> dict[str, Any]:
        """The state a pickle keeps: the result built in full (its document, its tree and its
        facts), so the copy needs nothing the original would have computed them with."""
        state = dict(self.__dict__)
        state["payload"] = dict(self.payload)
        state["tree"] = self.tree
        state["_doc"] = self._doc
        state["grow"] = None
        return state

    @cached_property
    def tree(self) -> Any:
        """The layered report's tree over this comparison, grown the first time it is read;
        ``None`` when there is none to grow."""
        return None if self.grow is None else self.grow()

    @cached_property
    def _doc(self) -> dict[str, Any]:
        doc = dict(self.multi.to_json())
        doc["method_chosen"] = self.method_chosen
        out: dict[str, Any] = _look.strict(_look.native(doc))
        return out

    def _fact(self, key: str) -> Any:
        return self._doc[key]

    @property
    def threshold(self) -> Any:
        return self._fact("threshold")

    @property
    def threshold_source(self) -> Any:
        return self._fact("threshold_source")

    @property
    def verdict_limit(self) -> Any:
        return self._fact("verdict_limit")

    @property
    def fragility(self) -> Any:
        return self._fact("fragility")

    @property
    def fragility_flips(self) -> Any:
        return self._fact("fragility_flips")

    @property
    def fragility_note(self) -> Any:
        return self._fact("fragility_note")

    @property
    def fragility_exact(self) -> Any:
        return self._fact("fragility_exact")

    @property
    def n_flagged_only(self) -> Any:
        return self._fact("n_flagged_only")

    @property
    def peeking(self) -> Any:
        return self._fact("peeking")

    @property
    def errors_differ(self) -> Any:
        return self._fact("errors_differ")

    @property
    def rows(self) -> list[dict[str, Any]]:
        """Every compared row, as its JSON cell with its ``event``."""
        doc = self._doc
        return [
            {**cell, "event": event}
            for event in doc["events"]
            for cell in doc["by_event"][event]["cells"]
        ]


@dataclass(frozen=True, eq=False)
class CheckResult(Comparison):
    """A gate over a comparison: ``passed`` or ``failed``, and what it failed on."""

    KIND: ClassVar[str] = "check"

    @property
    def passed(self) -> bool:
        return bool(self.payload["passed"])

    @property
    def fail_on(self) -> str:
        return str(self.payload["fail_on"])


@dataclass(frozen=True, eq=False)
class ArtifactRef:
    """One saved artifact, as ``save`` and ``artifacts`` name it: its kind, its id and its
    folder, relative to the store."""

    kind: str
    id: str
    path: str
    #: Why the dashboard's pages were not refreshed after the save, when they were not; the
    #: face says so in one line and names ``ui``. ``None`` when nothing failed or nothing was
    #: written.
    unrefreshed: str | None = None

    def to_json(self) -> dict[str, Any]:
        """``{"schema": "poisson-prove.artifact-ref/1", "kind", "id", "path"}``."""
        return {
            "schema": "poisson-prove.artifact-ref/1",
            "kind": self.kind,
            "id": self.id,
            "path": self.path,
        }


@dataclass(frozen=True, eq=False)
class Artifact:
    """One saved artifact read back: its descriptor and its result."""

    kind: str
    id: str
    descriptor: Mapping[str, Any]
    result: Mapping[str, Any]

    def to_json(self) -> dict[str, Any]:
        """The descriptor and the result under one document."""
        doc = {
            "schema": "poisson-prove.artifact/1",
            "kind": self.kind,
            "id": self.id,
            "descriptor": dict(self.descriptor),
            "result": dict(self.result),
        }
        out: dict[str, Any] = _look.strict(_look.native(doc))
        return out


@dataclass(frozen=True, eq=False)
class UiLocation(Result):
    """Where the static UI was built: its index page, as a path and as the address a browser
    opens."""

    KIND: ClassVar[str] = "ui"
    index: str = ""
    location: str = ""

    def to_json(self) -> dict[str, Any]:
        """``schema``, ``verdict``, ``sentence``, ``location``, ``next``."""
        return _document(
            self.KIND, self.verdict, self.sentence, {"location": self.location}, self.next
        )


@dataclass(frozen=True, eq=False)
class View:
    """The view behind one page of the UI: every fact the page shows, with the addresses of
    the pages it links to, as one strict document."""

    kind: str
    address: str
    document: Mapping[str, Any]

    def to_json(self) -> dict[str, Any]:
        """``schema`` (``poisson-prove.view/1``), ``view`` (which of the seven), ``address``
        and the view's own fields."""
        doc = {"schema": "poisson-prove.view/1", "view": self.kind, "address": self.address}
        for key, value in self.document.items():
            if key not in doc:
                doc[key] = value
        out: dict[str, Any] = _look.strict(_look.native(doc))
        return out


@dataclass(frozen=True, eq=False)
class Plan(Result):
    """A sweep planned: what will run, where, at what cost, and the design's limit."""

    KIND: ClassVar[str] = "plan"
    inner: Any = None
    lines: tuple[str, ...] = ()
    design_line: str | None = None
    store: Any = None
    target: str = ""
    typed_target: str | None = None
    spec_path: str | None = None
    rollout: Any = None
    modal: Any = None
    burla: Any = None
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, eq=False)
class RunResult(Result):
    """A sweep finished or stopped: what was kept, and how to go on."""

    KIND: ClassVar[str] = "run-result"
    run_id: str = ""
    run_name: str = ""
    details: tuple[tuple[str, str], ...] = ()
    stopped: bool = False


@dataclass(frozen=True, eq=False)
class Event:
    """One event of a sweep, as ``events.jsonl`` holds it."""

    kind: str
    detail: Mapping[str, Any]
    at: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

    def to_json(self) -> dict[str, Any]:
        """``{"schema": "poisson.run-event/1", "at", "kind", "detail"}``."""
        doc = {
            "schema": "poisson.run-event/1",
            "at": self.at,
            "kind": self.kind,
            "detail": dict(self.detail),
        }
        out: dict[str, Any] = _look.strict(_look.native(doc))
        return out


class Refusal(Exception):
    """An operation refused before doing any work. ``str()`` is the sentence a face prints after
    ``error:``; ``next`` the commands to try; ``usage`` marks a wrong command line (exit 2)."""

    def __init__(
        self,
        message: str,
        next: Sequence[str] = (),
        *,
        usage: bool = False,
        plan: Plan | None = None,
        notes: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.next = list(next)
        self.usage = usage
        self.plan = plan
        self.notes = list(notes)


class Unsaved(Exception):
    """A result could not be saved into its store (the store cannot be written to): the words
    a face prints after ``note:``. The command goes on."""

    def __init__(self, kind: str, reason: str) -> None:
        super().__init__(f"the comparison was not saved: {reason}")
        self.kind = kind
        self.reason = reason


class Stopped(Exception):
    """A sweep failed after its run was written: what was kept, how to go on, and the error."""

    def __init__(self, sentence: str, next: Sequence[str], error: str) -> None:
        super().__init__(error)
        self.sentence = sentence
        self.next = list(next)
        self.error = error


class Interrupted(KeyboardInterrupt):
    """A sweep interrupted after its run was written: what was kept and how to go on."""

    def __init__(self, sentence: str, next: Sequence[str]) -> None:
        super().__init__(sentence)
        self.sentence = sentence
        self.next = list(next)
