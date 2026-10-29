"""The terminal app: ``poisson-prove`` with no verb on a terminal.

A face over the core, as the command line is. It opens on home and reaches every screen by keys
alone; each screen renders one core object (``core.view(store, address)``, the sweep's plan and
events, a comparison the store could not save) laid out by ``_cli_app_pages``. It computes
nothing: the verdicts, limits, names and sentences are the core's, the numbers are spelled by the
shared look. It writes only through the core (a comparison it shows is saved; a sweep it
runs is the core's), never makes a network call and reads no key.

**Drawing.** One canvas, redrawn whole on every change, in the look file's six bands: the header
(the tool, the screen's title and subject, the store at the right edge), a dim rule, the body, the
message line, a dim rule, the key bar. The focus is reverse video with ``›`` in column 1. Colour is
the four meanings in the terminal's 16 named colours; ``NO_COLOR`` set and not empty removes it
(bold, dim and reverse stay), and set but empty changes nothing, as the command line reads it.

**Entry point.** ``ProveApp(store=None)``: ``store`` is the ``--store`` value as typed, ``None`` for
the store every verb finds from the folder the app runs in; ``sweep`` reads that folder's
``prove.toml``. The exit code is Textual's ``return_code``: 0 for ``q``, 130 for Ctrl-C.
"""

from __future__ import annotations

import os
import re
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key, Resize
from textual.filter import Monochrome, NoColor
from textual.widgets import Static

from poisson_prove import _banner, _look, core
from poisson_prove._cli_app_pages import (
    BACK,
    BLANK,
    COMMAND,
    Detail,
    Line,
    Page,
    Screens,
    block,
    verdict_line,
    wrap_line,
)
from poisson_prove.cli import _record_failure

__all__ = ["ProveApp"]

#: The smallest window the app draws in.
MIN_WIDTH, MIN_HEIGHT = 80, 24
_COLOURS = ("green", "yellow", "red")
_QUESTION = "Proceed? [y/N]"
#: How long the opening screen, the banner, stays up at the least while home is read; any key
#: opens home sooner.
OPENING_HOLD = 1.0


class ProveApp(App[int], Screens):
    """The terminal app over one store."""

    CSS = """
    Screen { background: ansi_default; color: ansi_default; }
    Static { background: ansi_default; color: ansi_default; width: 100%; height: 100%; }
    """
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("ctrl+c", "interrupt", priority=True, show=False)]

    def __init__(self, store: str | None = None) -> None:
        no_color = os.environ.get("NO_COLOR")
        super().__init__(ansi_color=True)
        # NO_COLOR set and not empty drops the colours; set but empty changes nothing.
        # Textual takes any NO_COLOR as set, so its own filter goes when the value is empty.
        self.mono = bool(no_color)
        if no_color == "":
            self._filters = [f for f in self._filters if not isinstance(f, (NoColor, Monochrome))]
            self.no_color = False
        self.store_arg = store
        self.store: Any = None
        self.shown = store or os.path.normpath(core.DEFAULT_STORE)
        self.stack: list[Page] = []
        #: What the app leaves to print once it has left the terminal, as the command prints it:
        #: a verdict word, its sentence and the next commands (a sweep stopped by Ctrl-C).
        self.after: tuple[str, str, list[str]] | None = None
        self.cancel = threading.Event()
        self.sweeping = False
        #: The sweep screen whose sweep is running: it cannot be left until the sweep ends.
        self.sweep_page: Page | None = None
        #: Whether the static UI was built (``None``: not tried yet), and where it is.
        self._ui: bool | None = None
        self._ui_base = ""
        self._mounted = False
        #: The opening screen, the banner, is up: home is read behind it.
        self.opening = False
        self._opened_at = 0.0

    def compose(self) -> ComposeResult:
        yield Static(id="canvas")

    def on_mount(self) -> None:
        self._mounted = True
        if self.is_headless:
            # No one is looking at a headless run: it opens on home.
            self.stack = [self.home()]
            self.redraw()
            return
        self.opening, self._opened_at = True, time.monotonic()
        self.redraw()
        self.call_after_refresh(self._read_home)

    def _read_home(self) -> None:
        """Home is read while the banner is up, which stays for ``OPENING_HOLD`` at the least."""
        self.stack = [self.home()]
        if not self.opening:
            self.redraw()
            return
        left = OPENING_HOLD - (time.monotonic() - self._opened_at)
        self.set_timer(max(0.0, left), self._end_opening)

    def _end_opening(self) -> None:
        if self.opening and self.stack:
            self.opening = False
            self.redraw()

    # ---------- the store ----------

    def home(self) -> Page:
        """Home, or the store's refusal: a store named by ``--store`` that does not
        exist, or one the core cannot read, is ``runs``'s refusal; no store yet and none named is
        home's empty state."""
        page = Page("home")
        try:
            self.store = core.open_store(self.store_arg)
            self.shown = str(self.store.shown)
            if self.store_arg is not None or Path(self.store.root).exists():
                self.store = core.open_store(self.store_arg, verb="runs")
                core.runs(self.store)
            doc = dict(core.view(self.store, "home").to_json())
        except core.Refusal as exc:
            # a store the app cannot read has no runs, sweep or comparison to offer: help and quit
            self.store = None
            return self.refused(page, exc)
        return self.home_page(doc)

    def ui_page(self, address: str) -> bool:
        """Whether the static UI's pages can be linked to: the core builds the UI the first time
        a screen shows a link (the app builds a store's first UI), and every write after that (a
        save, a sweep) refreshes it, so a link to a view's address resolves."""
        if self.store is None or not Path(self.store.root).is_dir():
            return False
        if self._ui is None:
            try:
                built = core.build_ui(self.store)
            except (core.Refusal, OSError):
                self._ui = False
            else:
                self._ui, self._ui_base = True, str(built.location).rsplit("/", 1)[0]
        return bool(self._ui)

    def _uri(self, address: str) -> str:
        """A page's whole ``file://`` address, from the address of the UI the core built."""
        return f"{self._ui_base}/{address}"

    # ---------- moving between screens ----------

    def width(self) -> int:
        return int(self.size.width)

    def push(self, page: Page) -> None:
        self.stack.append(page)
        self.redraw()

    def replace(self, page: Page) -> None:
        self.stack[-1] = page
        self.redraw()

    def pop(self) -> None:
        if len(self.stack) > 1:
            left = self.stack.pop()
            if len(self.stack) == 1 and self.stack[0].title == "home" and left.title != "help":
                focus = self.stack[0].focus
                self.stack[0] = self.home()  # what was saved or swept since shows
                self.stack[0].focus = focus
        self.redraw()

    def open_run(self, run_id: str) -> None:
        page = Page("run", keys=[BACK])
        try:
            doc = dict(core.view(self.store, f"runs/{run_id}.html").to_json())
        except core.Refusal as exc:
            self.push(self.refused(page, exc))
            return
        self.push(self.run_page(doc))

    def open_episodes(
        self, run_id: str, event: str, condition_hash: str, address: str | None
    ) -> None:
        self.push(self._episodes(run_id, event, condition_hash, address))

    def _episodes(self, run_id: str, event: str, condition_hash: str, address: str | None) -> Page:
        """The episodes view at its address; for a run in no saved comparison, which has no page
        of its own, the core's ``episodes`` page."""
        page = Page("episodes", keys=[BACK])
        try:
            if address:
                doc = dict(core.view(self.store, address).to_json())
            else:
                doc = dict(
                    core.episodes(
                        self.store, run_id, event=event, condition=condition_hash
                    ).to_json()
                )
            found = core.inspect(self.store, run_id, event=event, condition=condition_hash, limit=1)
            reproduce = found.reproduce if found.rows else None
        except core.Refusal as exc:
            return self.refused(page, exc)

        def next_event() -> None:
            try:
                run = dict(core.view(self.store, f"runs/{run_id}.html").to_json())
            except core.Refusal as exc:
                self.message(f"error: {exc}")
                return
            cell = next((c for c in run["cells"] if c["condition_hash"] == condition_hash), None)
            outcomes = [o for o in (cell or {}).get("shares", {}) if o != event] if cell else []
            if not outcomes:
                self.message("note: no other event in this condition")
                return
            order = list(cell["shares"]) if cell else []
            later = (
                [o for o in order[order.index(event) + 1 :] if o in outcomes]
                if event in order
                else []
            )
            nxt = (later or outcomes)[0]
            share = cell["shares"][nxt] if cell else {}
            self.replace(self._episodes(run_id, nxt, condition_hash, share.get("address")))

        return self.episodes_page(doc, reproduce, next_event)

    def open_saved(self, cid: str) -> None:
        try:
            doc = dict(core.view(self.store, f"comparisons/{cid}.html").to_json())
        except core.Refusal as exc:
            self.push(self.refused(Page("comparison", keys=[BACK]), exc))
            return
        self.push(self.verdict_page(doc, saved=True))

    def open_condition(self, cid: str, address: str) -> None:
        try:
            doc = dict(core.view(self.store, address).to_json())
        except core.Refusal as exc:
            self.push(self.refused(Page("condition", keys=[BACK]), exc))
            return
        self.push(self.condition_page(doc))

    def open_could_not_detect(self, cid: str) -> None:
        try:
            doc = dict(core.view(self.store, f"comparisons/{cid}/could-not-detect.html").to_json())
        except core.Refusal as exc:
            self.push(self.refused(Page("could not detect", keys=[BACK]), exc))
            return
        self.push(self.could_not_detect_page(doc))

    # ---------- compare ----------

    def open_compare(self, after: str | None = None) -> None:
        page = Page("compare", "pick two runs", keys=[BACK])
        try:
            doc = self.runs_view() if Path(self.store.root).is_dir() else {"runs": []}
        except core.Refusal as exc:
            self.push(self.refused(page, exc))
            return
        chosen: dict[str, str | None] = {}
        page = self.compare_page(doc, chosen, lambda: self._compare(chosen))
        if after is not None:
            chosen["after"] = after
            names = [
                str(r["run_id"])
                for r in doc.get("runs", [])
                if r["status"] == "complete" and str(r["run_id"]) != after
            ]
            if chosen.get("before") == after:
                chosen["before"] = names[0] if names else None
        self.push(page)

    def _compare(self, chosen: dict[str, str | None]) -> None:
        """``diff`` of the two chosen runs with no options, saved: the verdict screen shows the
        saved comparison's view, or the comparison itself and a note when the store cannot be
        written. The comparison runs beside the screen; leaving the screen before it is done saves
        nothing, and quitting does not wait for it."""
        a, b = chosen.get("before"), chosen.get("after")
        if not a or not b:
            self.message("error: a comparison takes two complete runs; choose before and after")
            return
        target = Page("comparison", keys=[BACK])
        target.top = [Line("  comparing…", [(2, 12, "dim")])]
        self.push(target)

        def work() -> None:
            try:
                page = self._compared(target, a, b)
            except Exception as exc:  # noqa: BLE001 - a failure inside is the command's unexpected one
                sentence = _record_failure([COMMAND, "diff", a, b], exc)
                page = Page(
                    "comparison", keys=[BACK], message=f"error: {sentence}", keep_message=True
                )
            if page is not None:
                self._from_worker(self._swap, target, page)

        threading.Thread(target=work, name="prove-compare", daemon=True).start()

    def _compared(self, target: Page, a: str, b: str) -> Page | None:
        try:
            result = core.compare(self.store, a, b)
        except core.Refusal as exc:
            return self.refused(Page("comparison", keys=[BACK]), exc)
        if target not in self.stack:
            return None  # the screen was left before the comparison was done: nothing is saved
        note = ""
        try:
            ref = core.save(self.store, result)
            doc = dict(core.view(self.store, f"comparisons/{ref.id}.html").to_json())
            page = self.verdict_page(doc, saved=True)
            if ref.unrefreshed is not None:
                note = (
                    f"note: the dashboard's pages were not refreshed ({ref.unrefreshed}); "
                    f"run {COMMAND} ui"
                )
        except core.Unsaved as exc:
            doc = dict(result.to_json())
            doc["_detail"] = list(result.detail)
            doc["name"] = " → ".join(_names(result))
            page = self.verdict_page(doc, saved=False)
            note = f"note: {exc}"
        page.message, page.keep_message = note, bool(note)
        return page

    def _from_worker(self, call: Any, *args: Any) -> None:
        """``call`` on the app's thread, unless the app has already left."""
        try:
            self.call_from_thread(call, *args)
        except RuntimeError:
            pass

    def _swap(self, old: Page, new: Page) -> None:
        if old in self.stack:
            self.stack[self.stack.index(old)] = new
        self.redraw()

    # ---------- the sweep ----------

    def open_sweep(self, overrides: dict[str, Any] | None = None) -> None:
        self.push(self._sweep(overrides or {}))

    def _sweep(self, overrides: dict[str, Any]) -> Page:
        """The plan ``sweep`` shows for ``./prove.toml`` as it is, and its question;
        the latest partial run is resumed when it is the store's newest run."""
        page = Page("sweep", "prove.toml", keys=[BACK])
        o: dict[str, Any] = {"typed": ["sweep"], "spec_typed": None, **overrides}
        try:
            if self.store is not None and Path(self.store.root).is_dir():
                newest = core.runs(self.store)
                if newest and newest[0].to_json().get("status") == "partial":
                    o["resume"] = core.LATEST_PARTIAL
            plan = core.plan(None, store=self.store, overrides=o)
        except core.Refusal as exc:
            return self._plan_refused(page, exc, overrides)
        lines = self.plan_lines(plan)

        def layout(width: int) -> None:
            if page.top and page.top[0].text.startswith(("  done  ", "  stopped  ")):
                return
            page.top = [*lines, BLANK]
            if not self.sweeping:
                page.top.append(Line(f"  {_QUESTION}", [(2, 2 + len(_QUESTION), "bold")]))

        page.layout = layout
        page.keys = [("y", "run"), ("n", "no"), BACK]
        page.on_key = lambda ch: self._answer(page, plan, lines, ch)
        return page

    def _plan_refused(self, page: Page, exc: Any, overrides: dict[str, Any]) -> Page:
        """``sweep``'s refusal at the plan: the plan stays when the core kept one (an underpowered
        design), with the ``error:`` line and the next commands; ``p`` plans again with the
        replicates the refusal names, never writing the spec."""
        refused = self.refused(page, exc)
        plan_lines = self.plan_lines(exc.plan) if getattr(exc, "plan", None) is not None else []
        nexts = list(getattr(exc, "next", []) or [])
        named = re.search(r"--replicates (\d+)", " ".join(nexts))

        def layout(width: int) -> None:
            page.top = [*plan_lines, BLANK] if plan_lines else []
            if len(refused.message) > width:
                page.top += [*block([Detail("error", str(exc))]), BLANK]
            page.top += block([Detail("next", c, code=True) for c in nexts])
            page.header, page.rows, page.bottom = None, [], []

        page.layout = layout
        if named:
            n = int(named.group(1))
            page.keys = [("p", f"plan with {_look.fmt_count(n)}"), BACK]

            def again(ch: str) -> bool:
                if ch != "p":
                    return False
                self.replace(self._sweep({**overrides, "replicates": n}))
                return True

            page.on_key = again
        return page

    def _answer(self, page: Page, plan: Any, lines: list[Line], ch: str) -> bool:
        """The question: only ``y`` answers yes; ``n``, Esc, ``q`` and Enter answer no; no
        other key answers it."""
        if self.sweeping or page.on_key is None:
            return False
        if ch in ("n", "q", "\x1b", "\r"):
            page.top = [*lines, BLANK, Line("  not run: nothing was spent", [(2, 28, "dim")])]
            page.layout, page.on_key = None, None
            page.keys = [BACK]
            if ch == "\x1b":  # no, and back to where the sweep was opened from
                self.pop()
            return True
        if ch != "y":
            # a printable key answers nothing; ``?`` is still help
            return ch != "?" and ch.isprintable() and len(ch) == 1
        self.sweeping, self.sweep_page = True, page
        page.keys = [("ctrl-c", "stop and keep what is done")]
        progress = Line("  starting")
        named = Line("")
        page.top = [*lines, BLANK, progress, named]
        page.layout = None
        started = time.monotonic()

        def on_event(event: Any) -> None:
            d = event.to_json()
            if d["kind"] == "started" or d["kind"] == "resumed":
                name = d.get("detail", {}).get("run_name") or plan.to_json().get("run_name", "")
                self._from_worker(self._set, named, f'  run "{name}" (partial until it ends)', [])
            if d["kind"] != "progress":
                return
            det = d["detail"]
            done, total = int(det["done"]), int(det["total"])
            cells = 24
            filled = cells * done // total if total else cells
            text = (
                f"  {_look.fmt_count(done)} of {_look.fmt_count(total)} · "
                f"{_look.fmt_count(det['errored'])} errored · "
                f"{_look.fmt_duration(time.monotonic() - started)}  "
                f"{'█' * filled}{'░' * (cells - filled)}"
            )
            bar = len(text) - cells
            self._from_worker(self._set, progress, text, [(bar, len(text), "dim")])

        def work() -> None:
            try:
                result = core.start(plan, on_event=on_event, cancel=self.cancel)
            except core.Interrupted as exc:
                self._from_worker(self._stopped, str(exc.sentence), list(exc.next))
                return
            except core.Refusal as exc:
                self._from_worker(self._failed, page, lines, str(exc), list(exc.next))
                return
            except Exception as exc:  # noqa: BLE001 - the command's unexpected failure, said its way
                sentence = _record_failure([COMMAND, "sweep", "--yes"], exc)
                self._from_worker(self._failed, page, lines, sentence, [])
                return
            if self.cancel.is_set():
                self._from_worker(self._stopped, str(result.sentence), list(result.next))
                return
            self._from_worker(self._done, page, lines, result)

        self.run_worker(work, thread=True)
        return True

    def _set(self, line: Line, text: str, spans: list[tuple[int, int, str]]) -> None:
        line.text, line.spans = text, spans
        self.redraw()

    def _done(self, page: Page, lines: list[Line], result: Any) -> None:
        """``sweep``'s result line and detail first, its notes, the plan kept below it; Enter
        opens the run."""
        self.sweeping, self.sweep_page = False, None
        details = [Detail(str(label), str(value)) for label, value in result.details]
        details += [Detail("note", str(note)) for note in getattr(result, "notes", ())]
        details += [Detail("next", c, code=True) for c in result.next]
        page.top = [
            verdict_line(result.verdict, result.sentence),
            *block(details),
            BLANK,
            *lines[2:],
        ]
        page.keys = [("enter", "open the run"), BACK]
        run_id = str(result.run_id)

        def keys(ch: str) -> bool:
            if ch != "\r":
                return False
            self.open_run(run_id)
            return True

        page.on_key = keys
        self._ui = None if self._ui is False else self._ui
        self.redraw()

    def _failed(self, page: Page, lines: list[Line], sentence: str, nexts: list[str]) -> None:
        self.sweeping, self.sweep_page = False, None
        page.message, page.keep_message = f"error: {sentence}", True
        whole = block([Detail("error", sentence)]) if len(page.message) > self.width() else []
        page.top = [*lines, BLANK, *whole, *block([Detail("next", c, code=True) for c in nexts])]
        page.keys, page.on_key = [BACK], None
        self.redraw()

    def _stopped(self, sentence: str, nexts: list[str]) -> None:
        """Ctrl-C during the sweep: the run is partial and resumable; once the app has left
        the terminal, ``sweep``'s stopped line and its next command; exit 130."""
        self.after = ("stopped", sentence, nexts)
        self.exit(return_code=130)

    # ---------- keys ----------

    def action_interrupt(self) -> None:
        if self.sweeping:
            self.cancel.set()  # the core stops at the next rollout boundary and keeps the run
            return
        self.exit(return_code=130)

    def message(self, text: str) -> None:
        if self.stack:
            self.stack[-1].message = text
        self.redraw()

    def on_key(self, event: Key) -> None:
        event.stop()
        event.prevent_default()
        w, h = self.size
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            if event.character == "q" and not self.sweeping:
                self.exit(return_code=0)
            return
        key, ch = event.key, event.character or ""
        if self.opening:
            # On the banner, q quits and any other key opens home (``?`` its help).
            if ch == "q":
                self.exit(return_code=0)
                return
            self.opening = False
            if self.stack and ch == "?":
                self.push(self.help_page())
                return
            self.redraw()
            return
        if not self.stack:
            return
        page = self.stack[-1]
        if not page.keep_message:
            page.message = ""
        if page.filtering:
            self._filter_key(page, key, ch)
            return
        if ch == "/" and page.rows:
            page.filtering, page.filter, page.focus = True, "", 0
        elif key == "escape" and page.filter:
            page.filter, page.focus = "", 0
        elif (
            page.on_key is not None
            and (ch or key in ("enter", "escape"))
            and page.on_key({"enter": "\r", "escape": "\x1b"}.get(key, ch))
        ):
            pass
        elif key in ("up", "down", "pageup", "pagedown", "home", "end"):
            self._move(page, key, h)
        elif key == "tab":
            if page.links() and page.visible_rows():
                page.in_links = not page.in_links
                page.focus, page.other_focus = page.other_focus, page.focus
        elif key == "enter":
            self._enter(page)
        elif ch == "y":
            self._copy(page)
        elif ch == "m" and page.more:
            page.show_more = not page.show_more
        elif key == "escape":
            if self.sweeping and page is self.sweep_page:
                page.message = "note: the sweep is running; ctrl-c stops it and keeps what is done"
            else:
                self.pop()
                return
        elif ch == "?" and page.title != "help":
            self.push(self.help_page())
            return
        elif ch == "q":
            if self.sweeping:
                page.message = "note: the sweep is running; ctrl-c stops it and keeps what is done"
            else:
                self.exit(return_code=0)
                return
        self.redraw()

    def _filter_key(self, page: Page, key: str, ch: str) -> None:
        if key == "escape":
            page.filtering, page.filter = False, ""
        elif key == "enter":
            page.filtering = False
        elif key == "backspace":
            page.filter = page.filter[:-1]
        elif ch and ch.isprintable():
            page.filter += ch
        page.focus = 0
        self.redraw()

    def _move(self, page: Page, key: str, height: int) -> None:
        focusables = (
            page.links() if page.in_links or not page.visible_rows() else page.visible_rows()
        )
        if not focusables:
            return
        page_rows = max(1, height - 8)
        step = {
            "up": -1,
            "down": 1,
            "pageup": -page_rows,
            "pagedown": page_rows,
            "home": -(10**9),
            "end": 10**9,
        }[key]
        page.focus = max(0, min(len(focusables) - 1, page.focus + step))
        if page.on_focus is not None:
            page.on_focus()

    def _focused_link(self, page: Page) -> Line | None:
        links = page.links()
        if not links or (page.visible_rows() and not page.in_links):
            return None
        return links[min(page.focus, len(links) - 1)]

    def _enter(self, page: Page) -> None:
        link = self._focused_link(page)
        if link is not None and link.link is not None:
            if self.ui_page(link.link):
                webbrowser.open(self._uri(link.link))
            else:
                page.message = "note: the dashboard's pages could not be built in this store"
            return
        row = page.focused_row()
        if row is not None and row.opens is not None:
            row.opens()

    def _copy(self, page: Page) -> None:
        """``y``: the focused link's whole ``file://`` address, or the screen's command or code."""
        link = self._focused_link(page)
        if link is not None and link.link is not None:
            self.copy_to_clipboard(self._uri(link.link))
            page.message = "note: copied the link"
            return
        code = next((line.copy for line in [*page.top, *page.bottom] if line.copy), None)
        if code is not None:
            self.copy_to_clipboard(code)
            page.message = "note: copied"

    def on_resize(self, event: Resize) -> None:
        self.call_after_refresh(self.redraw)  # a page is laid out again for a new width

    # ---------- drawing ----------

    def redraw(self) -> None:
        if not self._mounted or not (self.stack or self.opening):
            return
        try:
            canvas = self.query_one("#canvas", Static)
        except Exception:  # noqa: BLE001 - not composed yet: the next redraw draws it
            return
        w, h = self.size
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            canvas.update(
                Text(
                    f"the window is {w} × {h}; the app needs at least {MIN_WIDTH} × "
                    f"{MIN_HEIGHT}\nq quit"
                )
            )
            return
        if self.opening or not self.stack:
            canvas.update(self._draw_opening(w, h))
            return
        page = self.stack[-1]
        if page.layout is not None and page.laid_width != w:
            page.layout(w)
            page.laid_width = w
            if not page.rows and page.links():
                page.in_links = True
        canvas.update(self._draw(page, w, h))

    def _style(self, style: str) -> str:
        return "" if self.mono and style in _COLOURS else style

    def _draw_opening(self, w: int, h: int) -> Text:
        """The opening screen: the frame's six bands, with the banner in the middle of the body."""
        out = Text()

        def put(text: str, spans: list[tuple[int, int, str]]) -> None:
            t = Text(text[:w].ljust(w))
            for a, b, style in spans:
                t.stylize(style, a, min(b, w))
            out.append(t)
            out.append("\n")

        tool = "poisson-prove"
        put(
            tool.ljust(w - len(self.shown)) + self.shown,
            [(0, len(tool), "bold"), (w - len(self.shown), w, "dim")],
        )
        put("─" * w, [(0, w, "dim")])
        body_room = h - 5
        banner = _banner.lines()
        above = (body_room - len(banner)) // 2
        left = max(0, (w - _banner.WIDTH) // 2)
        for _ in range(above):
            put("", [])
        for text, spans in banner:
            put(" " * left + text, [(a + left, b + left, style) for a, b, style in spans])
        for _ in range(body_room - above - len(banner)):
            put("", [])
        put("", [])
        put("─" * w, [(0, w, "dim")])
        bar, spans = _key_bar([("enter", "home")], w, help_screen=False)
        put(bar, spans)
        out.rstrip()
        return out

    def _draw(self, page: Page, w: int, h: int) -> Text:
        out = Text()

        def put(
            text: str, spans: list[tuple[int, int, str]] | None = None, whole: str = ""
        ) -> None:
            if len(text.rstrip()) > w:  # a row longer than the window shows where it is cut
                text = text[: w - 1] + "…"
            t = Text(text[:w].ljust(w))
            for a, b, style in spans or []:
                style = self._style(style)
                if style and a < w:
                    t.stylize(style, a, min(b, w))
            if whole:
                t.stylize(whole)
            out.append(t)
            out.append("\n")

        # the header and its rule
        title = f"poisson-prove · {page.title}"
        subject = f"  {page.subject}" if page.subject else ""
        room = w - len(self.shown) - 1
        left = (title + subject)[:room]
        put(
            left.ljust(w - len(self.shown)) + self.shown,
            [
                (0, 13, "bold"),
                (13, 16, "dim"),
                (len(title), len(left), "dim"),
                (w - len(self.shown), w, "dim"),
            ],
        )
        put("─" * w, [(0, w, "dim")])
        body_room = h - 5
        focus_link = self._focused_link(page)
        groups = [wrap_line(line, w, line is focus_link) for line in page.top]
        top = [x for g in groups for x in g]
        rows = page.visible_rows()
        bottom = [x for line in page.bottom for x in wrap_line(line, w, line is focus_link)]
        header = [(page.header, False)] if page.header is not None else []
        if page.filtering or page.filter:
            shown_filter = f"  filter  {page.filter}" + ("_" if page.filtering else "")
            top.append((Line(shown_filter, [(2, 8, "dim")]), False))
            if not rows:
                top.append(
                    (Line(f'  no row matches "{page.filter}"; esc clears the filter'), False)
                )
        # The rows above the table never scroll: the whole lines with no room are a second block
        # behind ``m``, and one row says so.
        below = bottom if page.keep_bottom else []
        need = len(header) + min(len(rows), 3) + len(below)
        page.more = []
        if len(top) + need > body_room and not (page.filtering or page.filter):
            room = max(1, body_room - need - 1)
            kept: list[tuple[Line, bool]] = []
            for i, g in enumerate(groups):
                if len(kept) + len(g) > room:
                    page.more = page.top[i:]
                    break
                kept += g
            hidden = sum(len(g) for g in groups[len(page.top) - len(page.more) :])
            hint = f"  {_look.fmt_count(hidden)} more lines above the table: m shows them"
            top = [*kept, (Line(hint, [(2, len(hint), "dim")]), False)]
        if page.show_second and page.second:
            second = [x for line in page.second for x in wrap_line(line, w, False)]
            lines = top[: max(2, body_room - len(second))] + second
        elif page.show_more and page.more:
            more = [x for line in page.more for x in wrap_line(line, w, False)]
            lines = top[:-1] + more
        else:
            window = max(0, body_room - len(top) - len(header) - len(below))
            mark = not page.in_links and not page.scroll_only
            scroll = [(r, mark and i == page.focus) for i, r in enumerate(rows)]
            scroll += [] if below else bottom
            if page.scroll_only:  # help: the keys scroll the text, nothing has the focus
                page.focus = min(page.focus, max(0, len(scroll) - window))
                page.offset = page.focus
            focus = page.focus if rows and not page.in_links else 0
            if focus < page.offset:
                page.offset = focus
            if focus >= page.offset + window:
                page.offset = focus - window + 1
            if rows and focus == len(rows) - 1:
                page.offset = max(page.offset, min(focus, len(scroll) - window))
            page.offset = max(0, min(page.offset, max(0, len(scroll) - window)))
            visible = scroll[page.offset : page.offset + window]
            after = len(scroll) - page.offset - len(visible)
            if after > 0 and len(visible) > 1 and not visible[-1][1]:
                # the design's ``↓ 7 more``: the last row says how many follow
                hint = f"  ↓ {_look.fmt_count(after + 1)} more"
                visible = [*visible[:-1], (Line(hint, [(2, len(hint), "dim")]), False)]
            lines = top + header + visible + below
        lines = lines[:body_room]
        for line, focused in lines:
            text = ("›" + line.text[1:]) if focused else line.text
            put(text, line.spans, "reverse" if focused else "")
        for _ in range(body_room - len(lines)):
            put("")
        message = page.message
        put(
            message,
            [(0, 5, "yellow")]
            if message.startswith("note:")
            else [(0, 6, "red")]
            if message.startswith("error:")
            else [],
        )
        put("─" * w, [(0, w, "dim")])
        keys = [k for k in page.keys if k[0] != "q"]
        if page.more:
            keys.append(("m", "more"))
        keys += [k for k in page.keys if k[0] == "q"]
        bar, spans = _key_bar(keys, w, help_screen=page.title == "help")
        put(bar, spans)
        out.rstrip()
        return out


def _key_bar(
    keys: list[tuple[str, str]], w: int, *, help_screen: bool
) -> tuple[str, list[tuple[int, int, str]]]:
    """The key bar: move, Enter, Esc, the screen's own, ``? help``, ``q quit``; each key bold, its
    word dim. Too narrow, words drop first from the move, Enter and Esc keys, then from the
    screen's own from the right; ``? help`` and ``q quit`` keep theirs."""
    shared = {"↑↓", "enter", "esc"}
    tail = [] if help_screen else [("?", "help"), ("q", "quit")]
    entries = [[k, word] for k, word in [*keys, *tail]]

    def laid() -> str:
        return "  " + "   ".join(f"{k} {word}".rstrip() for k, word in entries)

    order = [i for i, (k, _) in enumerate(entries) if k in shared]
    order += [
        i
        for i in reversed(range(len(entries)))
        if entries[i][0] not in shared and i < len(entries) - len(tail)
    ]
    for i in order:
        if len(laid()) <= w:
            break
        entries[i][1] = ""
    bar, spans, pos = "  ", [], 2
    for k, word in entries:
        piece = f"{k} {word}".rstrip()
        spans.append((pos, pos + len(k), "bold"))
        if word:
            spans.append((pos + len(k) + 1, pos + len(piece), "dim"))
        bar += piece + "   "
        pos += len(piece) + 3
    return bar.rstrip(), spans


def _names(result: core.Comparison) -> list[str]:
    """The two runs of a comparison by the names the core gave them."""
    return [str(result.names.get(run, run)) for run in (result.run_a, result.run_b)]
