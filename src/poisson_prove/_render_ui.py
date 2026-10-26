"""The static UI's pages, rendered from the core's views.

One renderer, one page per view. A page shows every fact of its view and computes none: each
element that shows a fact carries ``data-fact``, the fact's JSON pointer in the view, and
``data-value``, its value as JSON, and its text is the fact as rule 10 prints it (``_look``).
Every address is relative to ``ui/``; a page loads nothing from the network, and says so.
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from poisson_prove import __version__, _facts, _look

TOOL = "poisson-prove"
POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' "
    "data:; "
    "base-uri 'none'; form-action 'none'"
)
#: The four meanings' classes for a verdict word (the look's colour rules); a result word is bold.
_WORD_CLASS = {
    "ok": "w-ok",
    "done": "w-ok",
    "passed": "w-ok",
    "stopped": "w-warn",
    "too small to tell": "w-warn",
    "no significant change": "w-warn",
    "failed": "w-bad",
}
_NONE_WORDS = {
    "total": "not recorded",
    "replicates": "not recorded",
    "horizon": "not recorded",
    "paired_with": "not paired",
    "declared": "nothing declared",
    "design_mde": "not recorded",
    "events": "not recorded",
    "number": "–",
    "kind": "not given",
    "n_worse": "no kind given",
    "n_safer": "no kind given",
    "n01": "not in the saved comparison",
    "n10": "not in the saved comparison",
    "stat": "none",
    "condition": "every condition",
    "p_min": "none",
    "value": "no episode with an outcome",
    "lo": "none",
    "hi": "none",
    "t": "none",
    "q": "none",
    "p": "none",
    "q_holm": "none",
    "ci_lo": "no interval",
    "ci_hi": "no interval",
    "level": "none",
}


def _esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def _escape_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar of a document with its JSON pointer."""
    if isinstance(document, Mapping):
        for key, value in document.items():
            yield from leaves(value, f"{prefix}/{_escape_token(str(key))}")
    elif isinstance(document, list):
        for i, value in enumerate(document):
            yield from leaves(value, f"{prefix}/{i}")
    else:
        yield prefix, document


def resolve(document: Any, pointer: str) -> Any:
    node = document
    for raw in pointer.split("/")[1:] if pointer else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _signed(value: float) -> str:
    return _look.fmt_signed(value)


def relative(address: str, target: str) -> str:
    """``target`` relative to the page at ``address``, both relative to ``ui/`` with ``/``
    between folders: no file system is asked."""
    path, _, anchor = target.partition("#")
    here = address.split("/")[:-1]
    if not path:
        return address.split("/")[-1] + (f"#{anchor}" if anchor else "")
    there = path.split("/")
    common = 0
    while common < len(here) and common < len(there) - 1 and here[common] == there[common]:
        common += 1
    parts = [".."] * (len(here) - common) + there[common:]
    return "/".join(parts) + (f"#{anchor}" if anchor else "")


class _Page:
    """One page under construction: its parts, and which of the view's facts it has shown."""

    def __init__(self, view: Mapping[str, Any], store: str) -> None:
        self.view = view
        self.address = str(view["address"])
        self.store = store
        self.up = "../" * self.address.count("/")
        self.parts: list[str] = []
        self.shown: set[str] = set()
        self.crumbs: list[tuple[str | None, str]] = []
        self.title = TOOL

    # ---- facts ----

    def value(self, ptr: str) -> Any:
        return resolve(self.view, ptr)

    def text(self, value: Any, kind: str, key: str) -> str:
        """A fact's text as rule 10 prints it."""
        if value is None:
            return _NONE_WORDS.get(key, "none")
        if isinstance(value, bool):
            return "yes" if value else "no"
        if kind == "plain":
            return str(value)
        if isinstance(value, int):
            return _look.fmt_count(value)
        if isinstance(value, float):
            if kind == "rate":
                return _look.fmt_rate(value)
            if kind == "signed":
                return _signed(value)
            if kind == "p":
                return _look.fmt_p(value)
            if kind == "level":
                return _look.level_label(value)
            return _look.fmt_num(value)
        if isinstance(value, (Mapping, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def fact(
        self,
        ptr: str,
        *,
        kind: str = "num",
        tag: str = "span",
        cls: str = "",
        text: str | None = None,
        key: str | None = None,
    ) -> str:
        value = self.value(ptr)
        self.shown.add(ptr)
        name = key if key is not None else ptr.rsplit("/", 1)[-1]
        shown = self.text(value, kind, name) if text is None else text
        classes = f' class="{cls}"' if cls else ""
        return (
            f'<{tag}{classes} data-fact="{_esc(ptr)}" '
            f'data-value="{_esc(json.dumps(value, ensure_ascii=False))}">'
            f"{_esc(shown)}</{tag}>"
        )

    def link(self, ptr: str, inner: str, *, cls: str = "") -> str:
        """A link to the page the fact at ``ptr`` names, showing ``inner`` (facts of its own)."""
        target = str(self.value(ptr))
        self.shown.add(ptr)
        classes = f' class="{cls}"' if cls else ""
        return (
            f'<a href="{_esc(self.rel(target))}"{classes} data-fact="{_esc(ptr)}" '
            f'data-value="{_esc(json.dumps(target, ensure_ascii=False))}">{inner}</a>'
        )

    def rel(self, target: str) -> str:
        return relative(self.address, target)

    def config(self, ptr: str) -> str:
        """A condition as its axis values, each value a fact, wrapped in the config's own fact."""
        config = self.value(ptr)
        self.shown.add(ptr)
        inner = (
            " · ".join(
                f"{_esc(k)} {self.fact(f'{ptr}/{_escape_token(str(k))}', kind='num')}"
                for k in config
            )
            or "the one condition"
        )
        return (
            f'<span class="mono" data-fact="{_esc(ptr)}" '
            f'data-value="{_esc(json.dumps(config, ensure_ascii=False))}">'
            f"{inner}</span>"
        )

    def generic(self, ptr: str, *, kind: str = "num") -> str:
        """Any value: a mapping as a definition list, a list as items, a scalar as its fact."""
        value = self.value(ptr)
        if isinstance(value, Mapping):
            if not value:
                self.shown.add(ptr)
                return f'<span class="dim" data-fact="{_esc(ptr)}" data-value="{{}}">none</span>'
            items = "".join(
                f"<dt>{_esc(str(k).replace('_', ' '))}</dt>"
                f"<dd>{self.generic(f'{ptr}/{_escape_token(str(k))}', kind=kind)}</dd>"
                for k in value
            )
            return f"<dl>{items}</dl>"
        if isinstance(value, list):
            if not value:
                self.shown.add(ptr)
                return f'<span class="dim" data-fact="{_esc(ptr)}" data-value="[]">none</span>'
            return (
                '<ul class="plain">'
                + "".join(
                    f"<li>{self.generic(f'{ptr}/{i}', kind=kind)}</li>" for i in range(len(value))
                )
                + "</ul>"
            )
        return self.fact(ptr, kind=kind)

    # ---- parts ----

    def add(self, text: str) -> None:
        self.parts.append(text)

    def verdict(self, ptr: str = "") -> str:
        word = str(self.value(f"{ptr}/verdict"))
        cls = _WORD_CLASS.get(word, "w-res")
        return (
            f'<p class="verdict">{self.fact(f"{ptr}/verdict", tag="b", cls=cls, kind="plain")}'
            f"{self.fact(f'{ptr}/sentence', kind='plain')}</p>"
        )

    def uncovered(self) -> list[str]:
        return [
            p
            for p, _ in leaves(self.view)
            if p not in self.shown
            and p not in ("/schema", "/view", "/address")
            and not p.endswith("/svg")
        ]

    def html(self) -> str:
        store = self.store_fact()
        rest = self.uncovered()
        if rest:
            # Nothing a view carries is left off its page: whatever the layout above did not
            # place is listed here, by its name in the view.
            items = "".join(
                f"<dt>{_esc(p.lstrip('/').replace('/', ' › ').replace('_', ' '))}</dt>"
                f"<dd>{self.generic(p)}</dd>"
                for p in rest
            )
            self.add(f"<section><h2>Also recorded</h2><dl>{items}</dl></section>")
        crumbs = " / ".join(
            f'<a href="{_esc(self.rel(a))}">{_esc(t)}</a>' if a is not None else _esc(t)
            for a, t in self.crumbs
        )
        kind = self.fact("/view", kind="plain", cls="dim")
        dot = ' <span class="dim">·</span> ' if crumbs else ""
        return (
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{POLICY}">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<meta name="generator" content="{TOOL} {__version__}">\n'
            f"<title>{_esc(self.title)} · {TOOL}</title>\n"
            f'<link rel="stylesheet" href="{self.up}style.css">\n'
            f'<script src="{self.up}ui.js" defer></script>\n</head>\n<body>\n'
            f'<header><span class="tool">{TOOL}</span><nav>{crumbs}{dot}{kind}</nav>'
            f'<span class="store">{store}</span></header>\n<main>\n'
            + "\n".join(self.parts)
            + "\n</main>\n"
            f"<footer>Built by {TOOL} from the store. Nothing was loaded from the network. "
            f"Address: "
            f"{self.fact('/address', kind='plain', cls='mono')}</footer>\n</body>\n</html>\n"
        )

    def store_fact(self) -> str:
        if "store" in self.view:
            return self.fact("/store", kind="plain")
        return _esc(self.store)


def _table(
    page: _Page,
    ident: str,
    columns: Sequence[tuple[str, str]],
    rows: Sequence[Sequence[str]],
    *,
    filter_rows: bool = False,
    row_classes: Sequence[str] | None = None,
    sortable: bool = True,
) -> str:
    """A table: columns are ``(header html, alignment)``; cells are html."""
    out = []
    if filter_rows:
        out.append(
            f'<input class="filter" data-filter="{ident}" placeholder="filter rows" '
            f'aria-label="filter '
            f'rows" hidden>'
        )
    sort = " data-sort" if sortable else ""
    out.append(f'<div class="tablewrap"><table id="{ident}"{sort}><thead><tr>')
    out.append("".join(f'<th class="{a}">{h}</th>' for h, a in columns))
    out.append("</tr></thead><tbody>")
    for i, row in enumerate(rows):
        cls = row_classes[i] if row_classes else ""
        out.append(f'<tr class="{cls}">' if cls else "<tr>")
        for j, cell in enumerate(row):
            align = columns[j][1]
            classes = " ".join(c for c in (align, "cond" if j == 0 else "") if c)
            out.append(f'<td class="{classes}">{cell}</td>' if classes else f"<td>{cell}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _dl(pairs: Sequence[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{_esc(k)}</dt><dd>{v}</dd>" for k, v in pairs) + "</dl>"


def _share(page: _Page, ptr: str) -> str:
    """A share with its interval: ``0.459 [0.389, 0.530]``."""
    return (
        f"{page.fact(f'{ptr}/value', kind='rate')} <span "
        f'class="dim">[{page.fact(f"{ptr}/lo", kind="rate")}, '
        f"{page.fact(f'{ptr}/hi', kind='rate')}]</span>"
    )


def _limit_cell(page: _Page, ptr: str) -> str:
    """A limit, or its note when it has none (the note is the fact's own text then)."""
    value = page.value(ptr)
    if value is not None:
        return page.fact(ptr, kind="rate")
    parent, key = ptr.rsplit("/", 1)
    node = page.value(parent)
    note_key = f"{key}_note"
    if isinstance(node, Mapping) and note_key in node and node[note_key] is not None:
        note = page.fact(f"{parent}/{note_key}", kind="plain", cls="dim")
        page.shown.add(ptr)
        return f'<span data-fact="{_esc(ptr)}" data-value="null">{note}</span>'
    return page.fact(ptr, kind="rate")


def _hash12(value: Any) -> str:
    return _look.fmt_hash(value)


def _kind_of(value: Any) -> str:
    return "plain" if isinstance(value, str) else "num"


def _arm(page: _Page, p: str, arm: str, index: int) -> str:
    """One arm of a condition's block: its share and interval, the counts, and the link to its
    episodes."""
    s = f"{p}/share_{arm}"
    e = f"{p}/episodes/{index}"
    return (
        f"{_share(page, s)} {page.fact(f'{s}/level', kind='level')} "
        f"{page.fact(f'{s}/method', kind='plain')} interval; {page.fact(f'{p}/k/{arm}')} of "
        f"{page.fact(f'{p}/n/{arm}')} episodes · {page.link(f'{e}/address', 'list them')} "
        f"({page.fact(f'{e}/run', kind='plain')}, "
        f'<span class="mono">{page.fact(f"{e}/run_id", kind="plain")}</span>)'
    )


# ---------- the seven views ----------


def _runs(page: _Page) -> None:
    v = page.view
    page.title = "Runs"
    page.crumbs = []
    page.add("<h1>Runs</h1>")
    page.add(page.verdict())
    runs = v["runs"]
    if runs:
        rows = []
        for i in range(len(runs)):
            p = f"/runs/{i}"
            rows.append(
                [
                    page.fact(f"{p}/number", kind="plain"),
                    page.link(f"{p}/address", page.fact(f"{p}/name", kind="plain")),
                    page.fact(f"{p}/run_id", kind="plain", cls="mono"),
                    page.fact(f"{p}/status", kind="plain"),
                    page.fact(f"{p}/backend", kind="plain"),
                    page.fact(f"{p}/target", kind="plain"),
                    page.fact(f"{p}/rows"),
                    page.fact(f"{p}/rows_without_outcome"),
                    page.fact(f"{p}/created_at", kind="plain"),
                ]
            )
        page.add(
            _table(
                page,
                "runs",
                [
                    ("#", "num"),
                    ("name", ""),
                    ("id", ""),
                    ("status", ""),
                    ("backend", ""),
                    ("target", ""),
                    ("rows", "num"),
                    ("no outcome", "num"),
                    ("created", ""),
                ],
                rows,
                filter_rows=True,
            )
        )
        page.add(
            '<p class="note">Newest first. A partial run is listed without a number and is never '
            "<code>latest</code> or <code>previous</code>.</p>"
        )
    else:
        page.add(
            "<p>Nothing has been swept into this store yet. Make the first run from a terminal:</p>"
        )
        page.add(f"<pre>{page.fact('/first_run', kind='plain', tag='code')}</pre>")
    page.add("<h2>Comparisons</h2>")
    comparisons = v["comparisons"]
    if comparisons:
        rows = []
        for i, c in enumerate(comparisons):
            p = f"/comparisons/{i}"
            verdict = page.fact(
                f"{p}/verdict",
                kind="plain",
                tag="b",
                cls=_WORD_CLASS.get(str(c["verdict"]), "w-res"),
            )
            if "limit" in c:
                limit = page.fact(f"{p}/limit", kind="rate")
                verdict += f' <span class="dim">largest limit read {limit}</span>'
            rows.append(
                [
                    page.link(f"{p}/address", page.fact(f"{p}/name", kind="plain")),
                    verdict,
                    page.fact(f"{p}/method", kind="plain"),
                    page.fact(f"{p}/id", kind="plain", cls="mono", text=_look.fmt_hash(c["id"])),
                    page.fact(f"{p}/saved_at", kind="plain"),
                ]
            )
        page.add(
            _table(
                page,
                "comparisons",
                [("before → after", ""), ("verdict", ""), ("test", ""), ("id", ""), ("saved", "")],
                rows,
            )
        )
    else:
        page.add(f'<p class="note">{page.fact("/no_comparison", kind="plain")}</p>')


def _run(page: _Page) -> None:
    v = page.view
    page.title = str(v["name"])
    page.crumbs = [("index.html", "runs"), (None, str(v["name"]))]
    page.add(f"<h1>Run {page.fact('/name', kind='plain', cls='mono')}</h1>")
    page.add(page.verdict())
    if v["total"] is None:
        status = (
            f"{page.fact('/status', kind='plain')}: {page.fact('/done')} rollouts "
            f"(planned total {page.fact('/total')})"
        )
    else:
        status = (
            f"{page.fact('/status', kind='plain')}: {page.fact('/done')} of "
            f"{page.fact('/total')} rollouts"
        )
    target = f"{page.fact('/target', kind='plain')}, on {page.fact('/backend', kind='plain')}"
    unit = f"{page.fact('/t_unit', kind='plain')}, horizon {page.fact('/horizon')}"
    paired = page.fact("/paired_with", kind="plain", cls="mono")
    if "paired_with_name" in v:
        paired = (
            page.link("/paired_with_address", page.fact("/paired_with_name", kind="plain"))
            + f' <span class="dim">({paired}, shared seeds)</span>'
        )
    axes = (
        ", ".join(
            f"{_esc(k)} ({page.fact(f'/axes/{_escape_token(k)}', kind='plain')})" for k in v["axes"]
        )
        or "none"
    )
    conditions = f"{page.fact('/conditions')} ({axes}), {page.fact('/replicates')} replicates each"
    outcomes = (
        ", ".join(page.fact(f"/outcomes/{i}", kind="plain") for i in range(len(v["outcomes"])))
        or '<span class="dim">none</span>'
    )
    pairs = [
        ("id", page.fact("/run_id", kind="plain", cls="mono")),
        ("status", status),
        ("created", page.fact("/created_at", kind="plain")),
        ("target", target),
        ("t_unit", unit),
        ("paired with", paired),
        ("conditions", conditions),
        ("outcomes", outcomes),
        ("declared", page.generic("/declared", kind="plain")),
    ]
    pairs.append(("design limit", _design(page)))
    compared = ", ".join(
        page.link(f"/comparisons/{i}/address", page.fact(f"/comparisons/{i}/name", kind="plain"))
        + f" ({page.fact(f'/comparisons/{i}/verdict', kind='plain', tag='b')}, "
        f"{page.fact(f'/comparisons/{i}/id', kind='plain', cls='mono', text=_hash12(c['id']))}"
        ")"
        for i, c in enumerate(v["comparisons"])
    )
    pairs.append(("compared in", compared or '<span class="dim">no saved comparison</span>'))
    page.add(_dl(pairs))
    page.add("<h2>Outcomes per condition</h2>")
    outcome_names = list(v["outcomes"])
    rows = []
    for i, cell in enumerate(v["cells"]):
        p = f"/cells/{i}"
        row = [
            page.config(f"{p}/config"),
            page.fact(
                f"{p}/condition_hash",
                kind="plain",
                cls="mono",
                text=_hash12(cell["condition_hash"]),
            ),
            page.fact(f"{p}/n"),
            page.fact(f"{p}/errored"),
        ]
        for outcome in outcome_names:
            s = f"{p}/shares/{_escape_token(outcome)}"
            share = cell["shares"].get(outcome)
            if share is None:
                row.append('<span class="dim">—</span>')
                continue
            ended = f"{page.fact(f'{s}/k')} ended"
            if "address" in share:
                ended = page.link(f"{s}/address", ended)
            row.append(
                f"{page.fact(f'{s}/value', kind='rate')} "
                f'<span class="dim">[{page.fact(f"{s}/lo", kind="rate")}, '
                f"{page.fact(f'{s}/hi', kind='rate')}]</span>"
                f'<br><span class="dim">{ended} · {page.fact(f"{s}/level", kind="level")} '
                f"{page.fact(f'{s}/method', kind='plain')} interval</span>"
            )
        rows.append(row)
    columns = [("condition", ""), ("hash", ""), ("with an outcome", "num"), ("errored", "num")]
    columns += [(_esc(outcome), "") for outcome in outcome_names]
    if rows:
        page.add(_table(page, "outcomes", columns, rows, filter_rows=True))
    else:
        page.shown.add("/cells")
        page.add('<p class="note" data-fact="/cells" data-value="[]">No condition has a row.</p>')
    if "shares_rule" in v:
        page.add(f'<p class="note">{page.fact("/shares_rule", kind="plain")}</p>')
    page.add("<h2>Event log</h2>")
    events = v["events"]
    if events is None:
        page.add(f'<p class="note">{page.fact("/events", kind="plain")}</p>')
        if "events_note" in v:
            page.add(f'<p class="note">{page.fact("/events_note", kind="plain")}</p>')
    elif not events:
        page.shown.add("/events")
        page.add('<p class="note" data-fact="/events" data-value="[]">The log is empty.</p>')
    else:
        rows = []
        for i, _event in enumerate(events):
            p = f"/events/{i}"
            detail = page.value(f"{p}/detail")
            words = " · ".join(
                f"{_esc(str(k).replace('_', ' '))} "
                f"{page.generic(f'{p}/detail/{_escape_token(str(k))}', kind=_kind_of(detail[k]))}"
                for k in detail
            )
            if not detail:
                page.shown.add(f"{p}/detail")
                ptr = _esc(p + "/detail")
                words = f'<span class="dim" data-fact="{ptr}" data-value="{{}}">—</span>'
            rows.append(
                [
                    page.fact(f"{p}/at", kind="plain"),
                    page.fact(f"{p}/kind", kind="plain"),
                    f'<span class="wrap">{words}</span>',
                ]
            )
        page.add(
            _table(page, "events", [("at", ""), ("kind", ""), ("detail", "")], rows, sortable=False)
        )


def _episodes(page: _Page) -> None:
    v = page.view
    page.title = f"{v['event']} episodes · {v['run']}"
    page.crumbs = [
        ("index.html", "runs"),
        (str(v["run_address"]), str(v["run"])),
        (None, f"{v['event']} episodes"),
    ]
    page.add(
        f"<h1>Episodes {page.config('/condition')} · "
        f"{page.fact('/event', kind='plain', cls='mono')}</h1>"
    )
    page.add(page.verdict())
    comparisons = (
        ", ".join(
            page.link(
                f"/comparisons/{i}/address",
                page.fact(
                    f"/comparisons/{i}/id", kind="plain", cls="mono", text=_look.fmt_hash(c["id"])
                ),
            )
            for i, c in enumerate(v["comparisons"])
        )
        or '<span class="dim">none saved</span>'
    )
    short = _hash12(v["condition_hash"])
    page.add(
        _dl(
            [
                (
                    "run",
                    page.link("/run_address", page.fact("/run", kind="plain"))
                    + f' <span class="mono dim">{page.fact("/run_id", kind="plain")}</span>',
                ),
                (
                    "condition",
                    f'{page.config("/condition")} <span class="mono '
                    f'dim">{page.fact("/condition_hash", kind="plain", text=short)}'
                    "</span>",
                ),
                ("in the comparison", comparisons),
            ]
        )
    )
    episodes = v["episodes"]
    if not episodes:
        page.shown.add("/episodes")
        page.add(
            f'<p class="note" data-fact="/episodes" '
            f'data-value="[]">{page.fact("/empty", kind="plain")}</p>'
        )
    else:
        rows = []
        for i in range(len(episodes)):
            p = f"/episodes/{i}"
            rows.append(
                [
                    page.fact(f"{p}/replicate_index", kind="plain"),
                    page.fact(f"{p}/seed", kind="plain"),
                    page.fact(f"{p}/outcome", kind="plain"),
                    page.fact(f"{p}/t"),
                    page.fact(f"{p}/rollout", kind="plain", tag="code"),
                ]
            )
        page.add(
            _table(
                page,
                "episodes",
                [
                    ("replicate", "num"),
                    ("seed", "num"),
                    ("outcome", ""),
                    ("t", "num"),
                    ("reproduce", ""),
                ],
                rows,
                filter_rows=True,
            )
        )
    page.add(f'<p class="note">{page.fact("/reproduce", kind="plain")}</p>')


#: How each key of a recorded design reads, and prints.
_DESIGN_WORDS = {
    "mde": ("limit", "rate"),
    "base_rate": ("at the worst base rate", "rate"),
    "direction": ("direction", "plain"),
    "test": ("test", "test"),
    "level": ("level", "p"),
    "family": ("over tests", "num"),
    "conditions": ("conditions", "num"),
    "events": ("events", "num"),
    "q": ("q", "num"),
    "power": ("power", "power"),
    "flaggable": ("flaggable", "num"),
    "computed_at_read_time": ("computed now from the recorded replicates", "num"),
}


def _design(page: _Page) -> str:
    """The design's limit as a sentence, then as recorded, each key in words."""
    design = page.value("/design_mde")
    if not isinstance(design, Mapping):
        return page.fact("/design_mde", kind="plain")
    parts = []
    for key in design:
        words, kind = _DESIGN_WORDS.get(str(key), (str(key).replace("_", " "), "num"))
        value = design[key]
        ptr = f"/design_mde/{_escape_token(str(key))}"
        if kind == "test" and isinstance(value, str):
            cell = page.fact(ptr, kind="plain", text=_test_words(value))
        elif kind == "power" and isinstance(value, (int, float)):
            cell = page.fact(
                ptr, kind="num", text=f"{_look.fmt_num(value)} ({_look.times_in(float(value))})"
            )
        elif isinstance(value, (Mapping, list)):
            cell = page.generic(ptr)
        else:
            cell = page.fact(ptr, kind=kind if kind != "test" else "plain")
        parts.append(f"{_esc(words)} {cell}")
    recorded = ' <span class="dim">·</span> '.join(parts)
    if "design" in page.view:
        sentence = page.fact("/design", kind="plain")
        return f'{sentence}<br><span class="dim">recorded as</span> {recorded}'
    return recorded


def _test_words(key: str) -> str:
    """A test as a reader names it, from the one table the verdict's lines use."""
    try:
        return _facts.test_name(key)
    except KeyError:
        return key


def _plural(count: Any, word: str) -> str:
    return word if count == 1 else f"{word}s"


def _kind_words(page: _Page, ptr: str) -> str:
    value = page.value(ptr)
    if value is None:
        return page.fact(ptr, kind="plain", text="kind not given")
    return f"a {page.fact(ptr, kind='plain')}"


def _facts_dl(page: _Page, ptr: str) -> str:
    facts = page.value(ptr)
    if not facts:
        page.shown.add(ptr)
        return ""
    return (
        "<dl>"
        + "".join(
            f"<dt>{page.fact(f'{ptr}/{i}/label', kind='plain')}</dt>"
            f"<dd>{page.fact(f'{ptr}/{i}/text', kind='plain')}</dd>"
            for i in range(len(facts))
        )
        + "</dl>"
    )


def _comparison(page: _Page) -> None:
    v = page.view
    page.title = str(v["name"])
    page.crumbs = [("index.html", "runs"), (None, str(v["name"]))]
    page.add("<h1>Comparison</h1>")
    page.add('<section id="verdict">' + page.verdict())
    page.add(
        _dl(
            [
                ("pair", page.fact("/name", kind="plain", cls="mono")),
                (
                    "method",
                    f"{page.fact('/method/line', kind='plain')} <span "
                    f'class="dim">({page.fact("/method/name", kind="plain")}; '
                    f"{page.fact('/method/words', kind='plain')}, chosen: "
                    f"{page.fact('/method/chosen', kind='plain')})</span>",
                ),
                (
                    "before",
                    page.link("/before/address", page.fact("/before/name", kind="plain"))
                    + f' <span class="mono dim">{page.fact("/before/run_id", kind="plain")}</span>'
                    + f' <span class="dim">({page.fact("/before/status", kind="plain")})</span>',
                ),
                (
                    "after",
                    page.link("/after/address", page.fact("/after/name", kind="plain"))
                    + f' <span class="mono dim">{page.fact("/after/run_id", kind="plain")}</span>'
                    + f' <span class="dim">({page.fact("/after/status", kind="plain")})</span>',
                ),
                (
                    "threshold",
                    f"{page.fact('/threshold/value', kind='rate')}, "
                    f"{page.fact('/threshold/source', kind='plain')}",
                ),
                (
                    "tests",
                    f"{page.fact('/family/tests')} {_plural(v['family']['tests'], 'test')} over "
                    f"{page.fact('/family/conditions')} "
                    f"{_plural(v['family']['conditions'], 'condition')} and "
                    f"{page.fact('/family/events')} {_plural(v['family']['events'], 'event')}, q "
                    f"{page.fact('/family/q')}",
                ),
                (
                    "saved",
                    f"{page.fact('/id', kind='plain', cls='mono', text=_look.fmt_hash(v['id']))} "
                    f"at "
                    f"{page.fact('/saved_at', kind='plain')}",
                ),
            ]
        )
    )
    page.add("<h3>What the verdict rests on</h3>" + _facts_dl(page, "/facts") + "</section>")
    page.add('<h2 id="counts">Per event</h2>')
    rows = []
    for i, _event in enumerate(v["events"]):
        p = f"/events/{i}"
        rows.append(
            [
                page.fact(f"{p}/name", kind="plain"),
                page.fact(f"{p}/kind", kind="plain"),
                page.fact(f"{p}/n_worse"),
                page.fact(f"{p}/n_safer"),
                page.fact(f"{p}/n_higher"),
                page.fact(f"{p}/n_lower"),
                page.fact(f"{p}/n_unchanged"),
                page.fact(f"{p}/n_could_not_tell"),
                page.fact(f"{p}/n_conditions"),
            ]
        )
    page.add(
        _table(
            page,
            "counts",
            [
                ("event", ""),
                ("kind", ""),
                ("worse", "num"),
                ("safer", "num"),
                ("rose", "num"),
                ("fell", "num"),
                ("unchanged", "num"),
                ("could not tell", "num"),
                ("conditions", "num"),
            ],
            rows,
            sortable=False,
        )
    )
    page.add(
        f'<p class="note">Could not tell: unchanged conditions that could not have shown a change '
        f"of the threshold's size. "
        f"{page.link('/could_not_detect/address', 'What this comparison could not detect')}: "
        f"{page.fact('/could_not_detect/n_could_not_tell')} such conditions.</p>"
    )
    page.add('<h2 id="trades">Trades</h2>')
    trades = v["trades"]
    if trades:
        items = []
        for i, t in enumerate(trades):
            p = f"/trades/{i}"
            safer = ", ".join(
                page.fact(f"{p}/safer/{j}", kind="plain") for j in range(len(t["safer"]))
            ) or page.generic(f"{p}/safer")
            worse = ", ".join(
                page.fact(f"{p}/worse/{j}", kind="plain") for j in range(len(t["worse"]))
            ) or page.generic(f"{p}/worse")
            short = _hash12(t["config_hash"])
            items.append(
                f'<li>{page.link(f"{p}/address", page.config(f"{p}/config"))} <span class="mono '
                f'dim">{page.fact(f"{p}/config_hash", kind="plain", text=short)}'
                "</span>: "
                f"safer in {safer}; worse in {worse}</li>"
            )
        page.add('<ul class="plain">' + "".join(items) + "</ul>")
    else:
        page.shown.add("/trades")
        page.add(
            '<p class="note" data-fact="/trades" data-value="[]">No condition traded one event for '
            "another.</p>"
        )
    page.add('<h2 id="conditions">Conditions</h2>')
    rows, classes = [], []
    for i, r in enumerate(v["rows"]):
        p = f"/rows/{i}"
        short = _hash12(r["config_hash"])
        rows.append(
            [
                page.link(f"{p}/address", page.config(f"{p}/config")) + f' <span class="mono '
                f'dim">{page.fact(f"{p}/config_hash", kind="plain", text=short)}'
                "</span>",
                page.fact(f"{p}/event", kind="plain"),
                f"{page.fact(f'{p}/share_a', kind='rate')} <span "
                f'class="dim">[{page.fact(f"{p}/share_a_lo", kind="rate")}, '
                f"{page.fact(f'{p}/share_a_hi', kind='rate')}]</span>",
                f"{page.fact(f'{p}/share_b', kind='rate')} <span "
                f'class="dim">[{page.fact(f"{p}/share_b_lo", kind="rate")}, '
                f"{page.fact(f'{p}/share_b_hi', kind='rate')}]</span>",
                f'<span class="dim">{page.fact(f"{p}/rate_a", kind="rate")} → '
                f"{page.fact(f'{p}/rate_b', kind='rate')}</span>",
                page.fact(f"{p}/delta", kind="signed"),
                page.fact(f"{p}/p", kind="p"),
                page.fact(f"{p}/q", kind="p"),
                page.fact(f"{p}/q_holm", kind="p"),
                page.fact(f"{p}/verdict", kind="plain", tag="b"),
                _limit_cell(page, f"{p}/mde_rise"),
                _limit_cell(page, f"{p}/mde_fall"),
            ]
        )
        classes.append("flagged" if r["verdict"] != "unchanged" else "")
    page.add(
        _table(
            page,
            "conditions",
            [
                ("condition", ""),
                ("event", ""),
                ("before", ""),
                ("after", ""),
                ("rates", ""),
                ("change", "num"),
                ("p", "num"),
                ("q", "num"),
                ("Holm", "num"),
                ("verdict", ""),
                ("rise", ""),
                ("fall", ""),
            ],
            rows,
            filter_rows=True,
            row_classes=classes,
        )
    )
    page.add(f'<p class="note">{page.fact("/rows_rule", kind="plain")}</p>')
    page.add('<h2 id="charts">Charts</h2><div class="charts">')
    for i, chart in enumerate(v["charts"]):
        p = f"/charts/{i}"
        page.add(
            f"<figure "
            f'id="{_esc(chart["kind"])}-{_esc(chart["event"])}">'
            f"<figcaption>{page.fact(f'{p}/kind', kind='plain')} "
            f"· "
            f"{page.fact(f'{p}/event', kind='plain')} · "
            f"{page.link(f'{p}/address', 'open')}</figcaption>{chart['svg']}</figure>"
        )
        page.shown.add(f"{p}/svg")
    page.add("</div>")
    page.add('<p class="note">Each condition\'s cumulative incidence chart is on its page.</p>')


def _condition(page: _Page) -> None:
    v = page.view
    words = _look.condition_words(v["condition"])
    page.title = words
    page.crumbs = [
        ("index.html", "runs"),
        (str(v["comparison"]["address"]), str(v["comparison"]["name"])),
        (None, words),
    ]
    page.add(f"<h1>Condition {page.config('/condition')}</h1>")
    cid = _hash12(v["comparison"]["id"])
    page.add(
        _dl(
            [
                (
                    "comparison",
                    page.link("/comparison/address", page.fact("/comparison/name", kind="plain"))
                    + f' <span class="mono '
                    f'dim">{page.fact("/comparison/id", kind="plain", text=cid)}'
                    "</span>",
                ),
                ("before", page.link("/before/address", page.fact("/before/name", kind="plain"))),
                ("after", page.link("/after/address", page.fact("/after/name", kind="plain"))),
                ("hash", page.fact("/condition_hash", kind="plain", cls="mono")),
            ]
        )
    )
    for i, block in enumerate(v["events"]):
        p = f"/events/{i}"
        page.add(
            f'<section id="{_esc(block["event"])}"><h2>{page.fact(f"{p}/event", kind="plain")} '
            f'<span class="dim">({_kind_words(page, f"{p}/kind")})</span></h2>'
        )
        page.add(page.verdict(p))
        before = _arm(page, p, "a", 0)
        after = _arm(page, p, "b", 1)
        change = (
            f"{page.fact(f'{p}/delta', kind='signed')} [{page.fact(f'{p}/ci/lo', kind='signed')}, "
            f"{page.fact(f'{p}/ci/hi', kind='signed')}], "
            f"{page.fact(f'{p}/ci/level', kind='level')} "
            f"{page.fact(f'{p}/ci/basis', kind='plain')} interval"
        )
        if block["test"]["n01"] is None:
            paired = str(block.get("test", {}).get("name", "")).startswith("the paired")
            if paired:
                pairs_text = (
                    f"the discordant pair counts are not in the saved comparison (only after "
                    f"{page.fact(f'{p}/test/n01', kind='plain', text='–')}, only before "
                    f"{page.fact(f'{p}/test/n10', kind='plain', text='–')})"
                )
            else:
                pairs_text = (
                    f"not a paired test, so no discordant pairs (only after "
                    f"{page.fact(f'{p}/test/n01', kind='plain', text='–')}, only before "
                    f"{page.fact(f'{p}/test/n10', kind='plain', text='–')})"
                )
        else:
            pairs_text = (
                f"{page.fact(f'{p}/test/n01')} pairs had the event only after, "
                f"{page.fact(f'{p}/test/n10')} only before"
            )
        test = (
            f"{page.fact(f'{p}/test/name', kind='plain')}: {pairs_text}; "
            f"statistic {page.fact(f'{p}/test/stat')}; p {page.fact(f'{p}/test/p', kind='p')}, "
            f"q {page.fact(f'{p}/test/q', kind='p')}, "
            f"Holm {page.fact(f'{p}/test/q_holm', kind='p')}"
        )
        test_key = str(block.get("mde_test") or "")
        test_words = _test_words(test_key)
        power_value = block.get("mde_power")
        power_words = (
            f"{_look.fmt_num(power_value)} ({_look.times_in(float(power_value))})"
            if isinstance(power_value, (int, float)) and not isinstance(power_value, bool)
            else None
        )
        limits = (
            f"computed by {page.fact(f'{p}/mde_test', kind='plain', text=test_words)} at level "
            f"{page.fact(f'{p}/mde_level', kind='p')} over {page.fact(f'{p}/mde_family')} tests, "
            f"power {page.fact(f'{p}/mde_power', text=power_words)}, from the "
            f"{page.fact(f'{p}/mde_anchor', kind='plain')}; the smallest possible p here is "
            f"{page.fact(f'{p}/p_min', kind='p')}, so this condition "
            f"{'can' if block.get('flaggable') else 'cannot'} be flagged "
            f"({page.fact(f'{p}/flaggable')})"
        )
        pairs = [
            ("before", before),
            ("after", after),
            ("change", change),
            ("test", test),
            ("rise", _limit_cell(page, f"{p}/mde_rise")),
            ("fall", _limit_cell(page, f"{p}/mde_fall")),
            ("limits", limits),
        ]
        if "competing" in block:
            pairs.append(("competing", page.fact(f"{p}/competing", kind="plain")))
        page.add(_dl(pairs))
        for j, chart in enumerate(block["charts"]):
            c = f"{p}/charts/{j}"
            page.add(
                f"<figure><figcaption>{page.fact(f'{c}/kind', kind='plain')} of "
                f"{page.fact(f'{c}/event', kind='plain')}, each run · "
                f"{page.link(f'{c}/address', 'open')}</figcaption>{chart['svg']}</figure>"
            )
            page.shown.add(f"{c}/svg")
        page.add("</section>")
    page.add("<h2>How to read this page</h2>")
    page.add(
        '<ul class="rules">'
        + "".join(
            f"<li>{page.fact(f'/rules/{i}', kind='plain')}</li>" for i in range(len(v["rules"]))
        )
        + "</ul>"
    )


def _could_not_detect(page: _Page) -> None:
    v = page.view
    page.title = "Could not detect"
    page.crumbs = [
        ("index.html", "runs"),
        (str(v["comparison"]["address"]), str(v["comparison"]["name"])),
        (None, "could not detect"),
    ]
    page.add("<h1>What the comparison could not detect</h1>")
    page.add(page.verdict())
    pairs = [
        (
            "comparison",
            page.link(
                "/comparison/address", page.fact("/comparison/name", kind="plain", cls="mono")
            )
            + f' <span class="mono '
            f'dim">{page.fact("/comparison/id", kind="plain", text=_hash12(v["comparison"]["id"]))}'
            "</span>",
        ),
        ("asked", page.fact("/question", kind="plain")),
        (
            "answer",
            f"{page.fact('/answer', kind='plain')} <span "
            f'class="dim">({page.fact("/n_could_not_tell")} '
            f"of {page.fact('/n_unchanged')} unchanged rows)</span>",
        ),
        (
            "flaggable",
            f'{page.fact("/flaggable", kind="plain")} <span class="dim">(smallest p '
            f"{page.fact('/p_min', kind='p')}; a flag needs less than "
            f"{page.fact('/level', kind='p')} "
            f"over {page.fact('/family')} tests)</span>",
        ),
        (
            "threshold",
            f"{page.fact('/threshold/value', kind='rate')}, "
            f"{page.fact('/threshold/source', kind='plain')}",
        ),
    ]
    pairs.append(("design", _design(page)))
    page.add(_dl(pairs))
    facts = _facts_dl(page, "/facts")
    if facts:
        page.add("<h3>Caveats</h3>" + facts)
    page.add("<h2>Unchanged rows and their limits</h2>")
    rows, classes = [], []
    for i, r in enumerate(v["rows"]):
        p = f"/rows/{i}"
        short = _hash12(r["config_hash"])
        rows.append(
            [
                page.link(f"{p}/address", page.config(f"{p}/config")) + f' <span class="mono '
                f'dim">{page.fact(f"{p}/config_hash", kind="plain", text=short)}'
                "</span>",
                page.fact(f"{p}/event", kind="plain"),
                page.fact(f"{p}/share_a", kind="rate"),
                _limit_cell(page, f"{p}/mde_rise"),
                _limit_cell(page, f"{p}/mde_fall"),
                page.fact(f"{p}/could_tell", tag="b" if not r["could_tell"] else "span"),
            ]
        )
        classes.append("asked" if not r["could_tell"] else "")
    if rows:
        page.add(
            _table(
                page,
                "rows",
                [
                    ("condition", ""),
                    ("event", ""),
                    ("before", "num"),
                    ("rise", ""),
                    ("fall", ""),
                    ("could tell", ""),
                ],
                rows,
                filter_rows=True,
                row_classes=classes,
            )
        )
    else:
        page.shown.add("/rows")
        page.add(
            '<p class="note" data-fact="/rows" data-value="[]">Every compared condition changed, '
            "so "
            "no row is asked.</p>"
        )
    page.add(
        f'<p class="note">{page.fact("/limits_rule", kind="plain")} Charts: '
        + " · ".join(
            page.link(
                f"/charts/{i}/address",
                f"{page.fact(f'/charts/{i}/kind', kind='plain')}, "
                f"{page.fact(f'/charts/{i}/event', kind='plain')}",
            )
            for i in range(len(v["charts"]))
        )
        + ".</p>"
    )


def _chart(page: _Page) -> None:
    v = page.view
    page.title = str(v["title"]).split(":")[0]
    crumbs: list[tuple[str | None, str]] = [
        ("index.html", "runs"),
        (str(v["comparison"]["address"]), str(v["comparison"]["name"])),
    ]
    if "condition_address" in v:
        crumbs.append((str(v["condition_address"]), str(v["condition_words"])))
    crumbs.append((None, f"{v['kind']} · {v['event']}"))
    page.crumbs = crumbs
    page.add(f"<h1>{page.fact('/title', kind='plain')}</h1>")
    pairs = [
        ("chart", f"{page.fact('/kind', kind='plain')} of {page.fact('/event', kind='plain')}"),
        (
            "comparison",
            page.link("/comparison/address", page.fact("/comparison/name", kind="plain"))
            + f' <span class="mono '
            f'dim">{page.fact("/comparison/id", kind="plain", text=_hash12(v["comparison"]["id"]))}'
            "</span>",
        ),
    ]
    if "condition_address" in v:
        pairs.append(
            (
                "condition",
                page.link("/condition_address", page.fact("/condition_words", kind="plain"))
                + f' <span class="mono dim">{page.fact("/condition", kind="plain")}</span>',
            )
        )
    else:
        pairs.append(("condition", page.fact("/condition", kind="plain")))
    page.add(_dl(pairs))
    page.add(
        f"<figure "
        f'class="wide"><figcaption>{page.fact("/caption", kind="plain")}</figcaption>'
        f"{v['svg']}</figure>"
    )
    page.shown.add("/svg")
    page.add("<h2>The data</h2>")
    columns = [
        (page.fact(f"/data/columns/{j}", kind="plain", tag="span"), "")
        for j in range(len(v["data"]["columns"]))
    ]
    rows = []
    for i, row in enumerate(v["data"]["rows"]):
        cells = []
        for j, value in enumerate(row):
            name = str(v["data"]["columns"][j])
            kind = (
                "p"
                if name == "q"
                else "signed"
                if name in ("delta", "lo", "hi")
                else "rate"
                if name in ("before", "after", "rise", "fall", "threshold")
                else "num"
            )
            cells.append(
                page.fact(
                    f"/data/rows/{i}/{j}", kind=kind if not isinstance(value, str) else "plain"
                )
            )
        rows.append(cells)
    page.add(_table(page, "data", columns, rows, filter_rows=True))
    page.add(
        f'<p class="note">From <span class="mono">{page.fact("/source", kind="plain")}</span>; the '
        f"chart's data file sits beside its SVG.</p>"
    )


RENDERERS = {
    "runs": _runs,
    "run": _run,
    "episodes": _episodes,
    "comparison": _comparison,
    "condition": _condition,
    "could_not_detect": _could_not_detect,
    "chart": _chart,
}


def render(view: Mapping[str, Any], store: str) -> str:
    """One page from one view document (``to_json()`` of a core ``View``)."""
    page = _Page(view, store)
    RENDERERS[str(view["view"])](page)
    return page.html()
