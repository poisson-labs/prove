"""PF7 -- the README, the docs, the recipes and a real agent's example (PF7.1 to PF7.3, PF7.7 and
PF7.8; each case its own sweep axis; the description words; a comparison result's JSON
form).

**What is pinned is what ships, as rules.** The pages are found, not listed:
every Markdown page of the README, ``CONTRIBUTING.md``, ``docs/`` (but the two standards)
and the example is read by the docs check and the link check, so a page a later
change adds is checked by being there. Where a page must carry what the code has (every verb, every
option of a verb, every key a sweep spec takes, every fault, every required ``[burla]`` field, the
prompt ``init --agent`` prints, the steps of the skill it writes), the list is read from what ships:
the command's own output, the public modules, or the field lists the spec reader checks a spec
against. Facts are pinned, never prose, but for the words fixed here: the README's
description words, the never-phones-home paragraph, "its own sweep axis", and the section headings.

**The docs check** is ``pf7_docs_check.py`` (its docstring is the definition of the marks and of
"does what its page shows"). Its own behaviour is pinned here too, on small pages written by the
test, so a check that let a wrong page through would fail here first.

**Choices this file fixes** (the code follows them):

- **d1** A block's mark is an HTML comment alone on the line directly before it, with three kinds
  (``run``, ``skip: REASON``, ``file NAME``) and one page mark (``setup quickstart``), as the check's
  docstring says. Output is checked by its verdict word and its line labels, ``next:`` lines whole,
  ``--help`` whole, ``--json`` by its keys, ``schema`` and ``verdict``; exit codes are 0 unless a
  trailing ``# exits N`` says otherwise.
- **d2** The docs check runs in the code suite against the checkout's install, and once more, slow,
  from the wheel in a fresh environment of each page's own; a line that installs Prove or makes a
  virtual environment is the install step (nothing to do in the checkout; the wheel, with its
  extras, in the fresh environment).
- **d3** The pages it reads are the README, ``CONTRIBUTING.md``, every page under ``docs/`` but
  ``docs/cli-look.md`` and ``docs/repo-hygiene.md`` (copied byte for byte from their canonical
  copies, so they cannot carry marks), and the example's own pages. The pilots' pages are not read:
  they leave the repository with the hygiene module.
- **d4** The README's first screen is everything above its first ``##`` heading; its commands block
  is ``FIRST_COMMANDS``' six lines exactly, fenced or indented.
- **d5** The README's sections are ``SECTIONS``' headings, word for word, as ``##`` headings in that
  order, and no other ``##`` heading.
- **d6** The never-phones-home paragraph is ``NEVER_PHONES_HOME``, word for word with Prove's
  names ("Prove", ``poisson-prove serve``), the same words the hygiene tests pin.
- **d7** "With stated confidence" is on no page and in no help: the README, the docs, the PyPI
  description and every ``--help``, the top-level one included.
- **d8** The quickstart's verdict is ``trade``: its packaged spec declares ``timeout`` and
  ``violated`` failures, so the words are the five a kinded comparison reads, not the kindless
  ``mixed`` that the committed 0.0.1 pair reads. Its counts are never pinned.
- **d9** A verb page has a ``## Exit codes`` section listing exactly the codes that verb can return
  (0, 1, 2, 3 and 130; ``check`` and ``paired`` also 4) and a ``## What it writes`` section; it names
  every option its help lists, outside the help, in backticks; it shows its ``--help`` in a
  ``console`` block marked ``run``, printed at 80 columns through a pipe (its usage block read with
  its line breaks evened out, as the docs check reads it); and two or more of its other examples
  are marked ``run`` with a printed line shown.
- **d10** The layered-report page works on the quickstart pair, which a reader can make, rather
  than on a committed two-run fixture.
- **d11** The example's client is replaced in the test by a stand-in for ``openai.OpenAI`` (the
  Chat Completions call), with ``OPENAI_API_KEY`` set to a placeholder that is no key while the
  stand-in is in place; the example makes its client inside the rollout, never at import, so
  ``sweep --dry-run`` imports it with no key set; its rollout module has at most 20 lines of code,
  docstrings and comments not counted. The test needs ``openai`` installed, as the code suite's
  environment (``[all,dev]``) has it.
- **d14** The sweep spec page and the backends page are checked against lists read from the code:
  the spec reader's own field lists (``sampler._TOP_FIELDS`` and the four tables' lists,
  ``ModalOptions``, ``ImageSpec``, ``BurlaOptions``), the Modal price table's date
  (``executor_modal._PRICES_ASOF``) and ``BurlaOptions``' fields with no default; ``[axes.*]`` or
  ``[axes.<name>]`` both name the axis table.
- **d15** The recipes' skip reasons are ``RECIPES``' words exactly, and each recipe shows what
  ``RECIPE_SHOWS`` checks it shows: ``in-ci`` a ``check`` that exits 4 and a ``--json`` command;
  ``when-it-says-too-small-to-tell`` a comparison whose word is ``too small to tell``;
  ``a-prompt-change`` ``--pair-with latest`` and ``check --fail-on worse``;
  ``a-model-change-with-cost`` a spec the spec reader loads with an ``[axes.model]`` of two values,
  and ``paired --cap-check``; ``paired-replay`` a declaration the paired module loads, and
  ``paired``.
- **d16** Prose is not pinned beyond the words named above: the "What Prove is not" paragraph,
  "never edits your code or your files" and the bullets that go with it, the concepts
  pages' explanations, the form of the Citation (any section with text), how each option is
  explained (named in backticks is the fact), and that the docs describe the pretty rendering.
- **d17** The statistics page explains the five verdict words and the three a comparison of
  events with no kind reads (``mixed``, ``higher``, ``lower``).
- **d18** The case-id refusal is the docs check's run of the your-own-agent page: its refused
  comparison exits 1 and its printed refusal names two or more of the case ids the page's own runs
  recorded (data, not words), so a refusal for another reason does not pass.
- **d13** A recipe "names no run id": no text of the shape a store gives a run id
  (``20261025T235823Z-aba9``) is on it. Other pages may show an id in a command's printed output
  (``runs`` prints them) but no command on any page is given one.

**Seams with the terminal app, tested on its side** (each listed so the two can be checked against
each other): the screens' titles and keys (the terminal-app page is pinned only for how the app
opens, the four keys every screen has and its two exit codes); the canonical ``docs/cli-look.md``
(written there, linked here, read by neither check); the snapshot command, one for both modules'
snapshots (``CONTRIBUTING.md`` names it whole); the pretty rendering (the docs describe it and show
plain output: no escape and no box drawing in a command's shown output); the ``[dev]`` test tools
it adds, which take floors here; the core dependencies it adds; ``poisson-prove`` with no verb,
which opens the app only on a terminal, so a page's example of it is marked ``skip``.
**Seams with the dashboard:** ``poisson-prove ui`` has its verb page; the dashboard page names the dashboard's seven views as headings; the artifact
format's page is that module's, read here only by the three checks.
**Seams with public hygiene:** the plain-words corpus (the release plain-words test reads every page), the never-phones-home words (d6),
the removed files, the CHANGELOG; and a TOML header of an array of tables
(``[[cuts]]`` in a paired declaration, ``[[scenarios]]`` in a sweep spec), which a page must be
able to show and which the hygiene module's double-bracket family would read as a note link.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF7.1 the README's first screen: title, commands block exactly, the three facts, the description words | ``test_pf7_1_the_readme_first_screen_has_the_title_the_first_commands_and_the_three_facts`` |
| PF7.1 every link in the README is absolute | ``test_pf7_1_every_link_in_the_readme_is_absolute_and_resolves`` |
| PF7.1 the README's sections in order, under 250 lines | ``test_pf7_1_the_readme_has_its_sections_in_order_in_under_250_lines`` |
| PF7.1 every command block of the README is run | ``test_pf7_1_every_block_of_the_readme_is_run`` |
| PF7.1 the README links the three pages kept | ``test_pf7_1_the_readme_links_the_three_pages_it_keeps`` |
| PF7.1 each README section carries its facts | ``test_pf7_1_each_readme_section_carries_its_facts`` (one case per section) |
| PF7.1 the never-phones-home paragraph word for word | ``test_pf7_1_the_readme_keeps_the_never_phones_home_paragraph`` |
| PF7.2 every required page exists | ``test_pf7_2_every_required_page_exists_and_opens_with_a_title`` (one case per page) |
| PF7.2 each verb page's help equals ``--help``; options, examples, exit codes, what it writes | ``test_pf7_2_each_verb_page_has_its_help_options_examples_exit_codes_and_writes`` (one case per verb) |
| PF7.2 the first run's pages show its commands and its verdict | ``test_pf7_2_the_first_run_pages_show_its_commands_and_its_verdict`` (README, quickstart) |
| PF7.2 the sweep spec page names every key and table | ``test_pf7_2_the_sweep_spec_page_names_every_key_and_table`` |
| PF7.2 the statistics page explains every verdict word | ``test_pf7_2_the_statistics_page_explains_every_verdict_word`` |
| PF7.2 the backends page: local, Modal, Burla | ``test_pf7_2_the_backends_page_carries_what_each_backend_needs`` (one case per backend) |
| PF7.2 the fault-injection page | ``test_pf7_2_the_fault_injection_page_names_every_fault_and_the_chaos_table`` |
| PF7.2 each case its own sweep axis; the refusal | ``test_pf7_2_the_agent_pages_say_each_case_is_its_own_sweep_axis`` (two pages) |
| PF7.2 the setup page around its table | ``test_pf7_2_the_setup_page_carries_the_prompt_the_steps_and_the_options`` |
| PF11.8 the setup page's table, kept | ``test_pf11_setup_agent::test_pf11_8_…`` (in that file) |
| PF7.2 the terminal app's page (shape) | ``test_pf7_2_the_terminal_app_page_says_how_it_opens_and_its_keys`` |
| PF7.2 the dashboard's page (shape) | ``test_pf7_2_the_dashboard_page_names_the_views_the_verb_and_what_saves`` |
| PF7.2 the architecture page | ``test_pf7_2_the_architecture_page_names_the_core_and_the_faces`` |
| PF7.2 ``CONTRIBUTING.md`` | ``test_pf7_2_contributing_says_how_to_install_test_and_commit`` |
| PF7.2 ``json.dumps`` on an unread result | ``test_pf7_2_the_python_page_says_json_dumps_on_an_unread_result_is_unsupported`` |
| PF7.3 every marked block runs and does what its page shows; unmarked fails; skips name reasons | ``test_pf7_3_every_marked_block_runs_and_does_what_its_page_shows`` (one case per page and install, but the your-own-agent page from the checkout, which the agent pages' test runs; the wheel's slow) |
| PF7.3 the docs check catches each way a page can be wrong | ``test_pf7_3_the_docs_check_catches_each_way_a_page_can_be_wrong`` (one case per way, and a right page) |
| PF7.7 the six recipes | ``test_pf7_7_the_recipes_are_the_six_named`` |
| PF7.7 each recipe: under 150 lines, ends with "What this does not tell you", no run id, run or skip as ``RECIPES`` says | ``test_pf7_7_each_recipe_is_short_ends_with_what_it_cannot_tell_and_is_run_or_skipped_as_listed`` (one case per recipe) |
| PF7.8 the example runs keyless with its client replaced by a stand-in | ``test_pf7_8_the_example_runs_keyless_with_its_client_replaced`` |
| PF7 every link of every page resolves | ``test_pf7_every_link_of_every_page_resolves`` (one case per page) |
| every docs page Prove's code or skill names exists | ``test_pf7_every_docs_page_prove_points_to_exists`` |
| PF7 "with stated confidence" nowhere | ``test_pf7_no_page_or_help_says_with_stated_confidence`` (pages, description, help) |
| PF7 the docs show plain output | ``test_pf7_the_docs_show_plain_output`` |
| PF7 nothing unbuilt is offered | ``test_pf7_no_page_claims_what_0_1_0_does_not_build`` |
| PF7.2 the layered-report page (d10) | ``test_pf7_2_the_layered_report_page_works_on_the_quickstart_pair_and_names_its_layers`` |
| PF7 no command is given a run id (d13) | ``test_pf7_no_command_on_any_page_is_given_a_run_id`` |
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import itertools
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

import pf7_docs_check as check

ROOT = Path(__file__).resolve().parents[1]
README = "README.md"
REPO_BLOB = re.compile(r"https://github\.com/poisson-labs/prove/(?:blob|tree)/main/(?P<path>[^#?]*?)/?(?:#(?P<frag>.*))?$")

FIRST_COMMANDS = [
    "python3 -m venv .venv && source .venv/bin/activate",
    "pip install poisson-prove",
    "poisson-prove init --example",
    "poisson-prove sweep --yes",
    "poisson-prove sweep --yes --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest",
    "poisson-prove diff",
]
DESCRIPTION_WORDS = "with stated error bounds and detection limits"
NEVER_PHONES_HOME = (
    "Prove never phones home. No telemetry, no analytics, no update checks. "
    "`poisson-prove serve` binds a loopback listener on request and makes no outbound connection: "
    "it holds one page built from data already on the machine, and dies with the process."
)
SECTIONS = [
    "What the first run showed",
    "Let your coding agent set it up",
    "The terminal app and the dashboard",
    "Your own agent",
    "Recipes",
    "Commands",
    "What the numbers claim, and what they do not",
    "Where Prove sits beside Trace and Tasks",
    "Backends",
    "Python",
    "Development",
    "Licence",
    "Citation",
]
TEN_VERBS = ("init", "sweep", "diff", "check", "report", "paired", "serve", "inspect", "runs", "ui")
RECIPES = {
    #: name: (has blocks that run, the reason every skipped command block gives, a parsed spec required)
    "first-look": (True, None, False),
    "a-prompt-change": (True, "needs a model key", False),
    "a-model-change-with-cost": (False, "needs two model keys", True),
    "in-ci": (True, None, False),
    "when-it-says-too-small-to-tell": (True, None, False),
    "paired-replay": (False, "needs runs recorded against a real model", True),
}
CONCEPTS = ("what-the-statistics-claim", "the-layered-report", "pairing", "censoring-and-competing-risks", "traces")
VERDICT_WORDS = ("worse", "safer", "trade", "mixed", "higher", "lower", "no significant change", "too small to tell")
QUICKSTART_VERDICT = "trade"
VIEWS = ("runs", "run", "comparison", "condition", "episodes", "could not detect", "charts")
RUN_ID = re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{4}\b")
COMMAND_LANGS = {"console", "bash", "sh", "shell", "python"}


def is_command_block(block: check.Block) -> bool:
    """A block that holds commands or code: indented, a fence with no language, or one of these."""
    return block.indented or block.lang in COMMAND_LANGS or block.lang == ""
SNAPSHOT_COMMAND = "python -m pytest tests -k snapshot --update-snapshots"


# ---------- reading what ships ----------


def text_of(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


def prove(*args: str, cwd: Path | None = None, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    """The command as a user runs it, piped, at 80 columns, with no key and an empty home."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("POISSON_PROVE", "OPENAI", "ANTHROPIC", "CI", "COLUMNS"))}
    env.update(COLUMNS="80", PYTHONIOENCODING="utf-8")
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run([sys.executable, "-m", "poisson_prove", *args], cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=300)


HELPS_SCRIPT = """
import io, json, re, sys
from poisson_prove import cli

def help_of(args):
    out = io.StringIO()
    try:
        code = cli.main([*args, "--help"], stdout=out, stderr=io.StringIO())
    except SystemExit as stop:
        code = stop.code
    return out.getvalue(), code

top, _ = help_of([])
lines = top.splitlines()
at = next((i for i, line in enumerate(lines) if line.strip() == "verbs:"), len(lines))
verbs = [m.group(1) for line in lines[at + 1:] if (m := re.match(r"^ {4}([a-z]+)\\s", line))]
helps = {"": [top, 0]}
for verb in sorted(set(verbs) | set(sys.argv[1:])):
    helps[verb] = list(help_of([verb]))
print(json.dumps({"verbs": verbs, "helps": helps}))
"""


def all_helps() -> dict[str, Any]:
    """Every ``--help`` the command prints, the top level's under ``""``, at 80 columns through a
    pipe, and the verbs its help lists; read once, in one process of its own, from the same
    ``main`` the command runs."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("POISSON_PROVE", "OPENAI", "CI", "COLUMNS"))}
    env.update(COLUMNS="80", PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable, "-c", HELPS_SCRIPT, *TEN_VERBS], env=env, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


HELPS = all_helps()
VERBS = sorted(set(TEN_VERBS) | set(HELPS["verbs"]))
REQUIRED_PAGES = sorted(
    {"docs/quickstart.md", "docs/sweep-spec.md", "docs/reading-a-serve-page.md", "docs/defining-outcomes.md",
     "docs/what-capture-stores.md", "docs/backends.md", "docs/fault-injection.md", "docs/python.md",
     "docs/with-trace-and-tasks.md", "docs/your-own-agent.md", "docs/setup-with-your-agent.md",
     "docs/terminal-app.md", "docs/dashboard.md", "docs/artifact-format.md", "docs/architecture.md",
     "CONTRIBUTING.md", "CHANGELOG.md"}
    | {f"docs/commands/{verb}.md" for verb in VERBS}
    | {f"docs/concepts/{name}.md" for name in CONCEPTS}
    | {f"docs/recipes/{name}.md" for name in RECIPES}
)
PAGES = sorted(set(check.corpus()) | ({README} | set(REQUIRED_PAGES)) - {"CHANGELOG.md"})


def page_of(rel: str) -> check.Page:
    assert (ROOT / rel).is_file(), f"{rel} does not exist"
    return check.read_page(rel)


def sections(text: str, level: int = 2) -> dict[str, str]:
    """A page's sections by heading text, at one level, each with its body up to the next heading
    of that level or above."""
    out: dict[str, str] = {}
    current: str | None = None
    fence = False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
        heading = None if fence else re.match(r"^(#{1,6}) (.+?)\s*#*\s*$", line)
        if heading and len(heading.group(1)) <= level:
            current = heading.group(2).strip() if len(heading.group(1)) == level else None
            if current is not None:
                out.setdefault(current, "")
            continue
        if current is not None:
            out[current] += line + "\n"
    return out


def links_of(text: str) -> list[str]:
    """Every link a page makes: Markdown links and images, autolinks, and HTML ``href`` and ``src``."""
    from markdown_it import MarkdownIt

    found: list[str] = []

    def walk(tokens: list[Any]) -> None:
        for token in tokens:
            if token.type == "link_open":
                found.append(str(token.attrs.get("href", "")))
            elif token.type == "image":
                found.append(str(token.attrs.get("src", "")))
            elif token.type in ("html_inline", "html_block"):
                found.extend(re.findall(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", token.content))
            if token.children:
                walk(token.children)

    walk(MarkdownIt("commonmark").parse(text))
    return found


def heading_text(line: str) -> str:
    """A heading's text as it reads, its inline markup rendered away (code, emphasis, links)."""
    from markdown_it import MarkdownIt

    parts: list[str] = []
    for token in MarkdownIt("commonmark").parseInline(line)[0].children or []:
        if token.type in ("text", "code_inline"):
            parts.append(token.content)
    return "".join(parts)


def slugs(text: str) -> set[str]:
    """The anchors GitHub gives a page's headings: the heading's text in lower case, every
    character but letters, digits, ``_``, ``-`` and spaces dropped, spaces made ``-``."""
    seen: dict[str, int] = {}
    out: set[str] = set()
    for line in re.findall(r"^#{1,6} (.+?)\s*#*\s*$", text, flags=re.M):
        slug = re.sub(r"[^\w\- ]", "", heading_text(line).lower()).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


def link_problem(page: str, href: str) -> str | None:
    """Why a link from ``page`` does not resolve, or None."""
    if href.startswith(("http://127.0.0.1", "http://localhost", "mailto:")):
        return None
    repo = REPO_BLOB.match(href)
    if repo:
        target, frag = repo.group("path"), repo.group("frag")
    elif re.match(r"^[a-z][a-z0-9+.-]*:", href):
        return None if href.startswith("https://") else f"{href}: not https"
    else:
        base = Path(page).parent
        path, _, frag = href.partition("#")
        target = os.path.normpath((base / path).as_posix()) if path else page
        frag = frag or None
    if target.startswith("..") or not (ROOT / target).exists():
        return f"{href}: {target} is not in the repository"
    if frag and (ROOT / target).is_file() and target.endswith(".md") and frag not in slugs(text_of(target)):
        return f"{href}: {target} has no heading #{frag}"
    return None


def init_agent_json(tmp: Path) -> dict[str, Any]:
    repo = tmp / "repo"
    repo.mkdir(exist_ok=True)
    done = prove("init", "--agent", "--json", "--repo", str(repo), home=tmp)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def skill_steps(tmp: Path) -> list[str]:
    done = prove("init", "--agent", "--print", home=tmp, cwd=tmp)
    assert done.returncode == 0, done.stderr
    body = sections(done.stdout).get("Steps", "")
    return re.findall(r"^\d+\.\s+\*\*(.+?)\*\*", body, flags=re.M)


def verb_of(command: str) -> str | None:
    """The verb a ``poisson-prove`` command line runs, past the global options before it."""
    words = command.split()
    if not words or words[0] != "poisson-prove":
        return None
    rest = words[1:]
    while rest and rest[0] in ("--store", "--plain", "--debug"):
        rest = rest[2:] if rest[0] == "--store" else rest[1:]
    return rest[0] if rest and not rest[0].startswith("-") else None


def blocks_with(page: check.Page, verb: str) -> list[check.Block]:
    return [b for b in page.blocks if b.lang == "console" and any(verb_of(c) == verb for c, _ in check.commands(b))]


def backticked(text: str) -> str:
    # Inline code only: a fenced block (three or more backticks or tildes) is taken out first, so
    # a fence never pairs with a later backtick.
    prose = re.sub(r"^ {0,3}((`|~)\2{2,})[^\n]*\n.*?^ {0,3}\1\2*[ \t]*$", "", text, flags=re.M | re.S)
    return "\n".join(re.findall(r"`([^`]+)`", prose))


# ---------- PF7.1 the README ----------


def first_screen(text: str) -> str:
    at = re.search(r"^## ", text, flags=re.M)
    return text[: at.start()] if at else text


def test_pf7_1_the_readme_first_screen_has_the_title_the_first_commands_and_the_three_facts() -> None:
    text = text_of(README)
    assert text.splitlines()[0] == "# Poisson Prove", text.splitlines()[:1]
    screen = first_screen(text)
    page = check.read_page(README)
    blocks = [b for b in page.blocks if b.line <= screen.count("\n") + 1]
    assert [[c for c, _ in check.commands(b)] for b in blocks if b.indented or b.lang in check.SHELL] == [FIRST_COMMANDS]
    prose = flat(re.sub(r"^( {4}|\t)[^\n]*$|^```.*?^```", "", screen, flags=re.M | re.S))
    assert DESCRIPTION_WORDS in prose, prose
    bullets = [flat(b) for b in re.findall(r"^[-*] (.+(?:\n(?![-*] ).+)*)", screen, flags=re.M)]
    facts = {
        "no key and no account": lambda b: re.search(r"\bkey\b", b) and "account" in b,
        "nothing sent": lambda b: "telemetry" in b and "update check" in b and "127.0.0.1" in b,
        "the Pythons and platforms": lambda b: all(w in b for w in ("3.11", "3.14", "macOS", "Linux")),
    }
    missing = [name for name, holds in facts.items() if not any(holds(b) for b in bullets)]
    missing += [line for line in ("uv tool install poisson-prove", "pipx install poisson-prove") if line not in screen]
    assert missing == [], (missing, bullets)


def test_pf7_1_every_link_in_the_readme_is_absolute_and_resolves() -> None:
    problems = []
    for href in links_of(text_of(README)):
        if not re.match(r"^(https://|mailto:)", href):
            problems.append(f"{href}: not absolute")
        elif (problem := link_problem(README, href)) is not None:
            problems.append(problem)
    assert problems == [], problems


def test_pf7_1_the_readme_links_the_three_pages_it_keeps() -> None:
    """The three pages kept from before are linked from the README."""
    kept = ("docs/reading-a-serve-page.md", "docs/defining-outcomes.md", "docs/what-capture-stores.md")
    assert [p for p in kept if not _links_to(text_of(README), p)] == []


def test_pf7_1_the_readme_has_its_sections_in_order_in_under_250_lines() -> None:
    text = text_of(README)
    headings = re.findall(r"^## (.+?)\s*$", text, flags=re.M)
    assert headings == SECTIONS, headings
    assert len(text.splitlines()) < 250, len(text.splitlines())


def test_pf7_1_every_block_of_the_readme_is_run() -> None:
    """Every command block of the README is run or written; a block marked as text
    (``text``) may be skipped with its reason. A fence with no language counts as commands."""
    page = page_of(README)
    not_run = [(b.line, b.mark) for b in page.blocks
               if is_command_block(b) and (b.mark is None or b.mark.kind == "skip")]
    assert not_run == [], not_run


def _section(name: str) -> str:
    return sections(text_of(README)).get(name, "")


def _links_to(body: str, rel: str) -> bool:
    return any((m := REPO_BLOB.match(h)) and m.group("path").rstrip("/") == rel for h in links_of(body))


def _first_run_section(tmp: Path) -> list[str]:
    body = _section("What the first run showed")
    return [] if f"`{QUICKSTART_VERDICT}`" in body or re.search(rf"^\s*{QUICKSTART_VERDICT}  ", body, re.M) else ["the verdict word"]


def _setup_section(tmp: Path) -> list[str]:
    body = _section("Let your coding agent set it up")
    prompt = init_agent_json(tmp)["prompt"]
    out = []
    if "poisson-prove init --agent" not in body:
        out.append("poisson-prove init --agent")
    if prompt not in flat(body):
        out.append("the prompt init --agent prints")
    if "poisson-prove sweep" not in body.replace("poisson-prove sweep --", ""):
        out.append("poisson-prove sweep, the person's own next command")
    if not _links_to(body, "docs/setup-with-your-agent.md"):
        out.append("a link to the setup page")
    return out


def _faces_section(tmp: Path) -> list[str]:
    body = _section("The terminal app and the dashboard")
    lines = [line.strip() for b in re.findall(r"```[^\n]*\n(.*?)```", body, flags=re.S) for line in b.splitlines()]
    out = []
    if not ("poisson-prove" in lines or "$ poisson-prove" in lines or "`poisson-prove`" in body):
        out.append("poisson-prove alone")
    if "poisson-prove ui" not in body:
        out.append("poisson-prove ui")
    out += [f"a link to {p}" for p in ("docs/terminal-app.md", "docs/dashboard.md") if not _links_to(body, p)]
    return out


def _own_agent_section(tmp: Path) -> list[str]:
    body = _section("Your own agent")
    out = []
    rollouts = [b for b in re.findall(r"```python\n(.*?)```", body, flags=re.S) if re.search(r"def rollout\(cfg, seed\)", b)]
    if not rollouts or len([line for line in rollouts[0].splitlines() if line.strip()]) > 12:
        out.append("a rollout of at most twelve lines")
    elif (ROOT / "docs/your-own-agent.md").is_file() and rollouts[0] not in text_of("docs/your-own-agent.md"):
        out.append("the same rollout on the your-own-agent page")
    if "`target`" not in body and "target =" not in body:
        out.append("target")
    if "[capture]" not in body:
        out.append("the [capture] table")
    if not _links_to(body, "docs/your-own-agent.md"):
        out.append("a link to the your-own-agent page")
    return out


def _recipes_section(tmp: Path) -> list[str]:
    body = _section("Recipes")
    return [f"a link to {name}" for name in RECIPES if not _links_to(body, f"docs/recipes/{name}.md")]


def _commands_section(tmp: Path) -> list[str]:
    body = _section("Commands")
    items = [line for line in body.splitlines() if re.match(r"^[-*] ", line)]
    out = []
    for verb in VERBS:
        mine = [i for i in items if _links_to(i, f"docs/commands/{verb}.md")]
        if len(mine) != 1 or f"`{verb}`" not in mine[0] and f"poisson-prove {verb}" not in mine[0]:
            out.append(f"one line for {verb}, linking its page")
    if len(items) != len(VERBS):
        out.append(f"one line per verb: {len(items)} lines for {len(VERBS)} verbs")
    return out


def _link_section(name: str, rel: str, *words: str):  # type: ignore[no-untyped-def]
    def holds(tmp: Path) -> list[str]:
        body = _section(name)
        out = [] if _links_to(body, rel) else [f"a link to {rel}"]
        return out + [w for w in words if w not in body]
    return holds


README_SECTIONS = {
    "What the first run showed": _first_run_section,
    "Let your coding agent set it up": _setup_section,
    "The terminal app and the dashboard": _faces_section,
    "Your own agent": _own_agent_section,
    "Recipes": _recipes_section,
    "Commands": _commands_section,
    "What the numbers claim, and what they do not": _link_section(
        "What the numbers claim, and what they do not", "docs/concepts/what-the-statistics-claim.md"),
    "Where Prove sits beside Trace and Tasks": _link_section(
        "Where Prove sits beside Trace and Tasks", "docs/with-trace-and-tasks.md", "Trace", "Tasks"),
    "Backends": _link_section("Backends", "docs/backends.md", "Modal", "Burla", "experimental"),
    "Python": _link_section("Python", "docs/python.md"),
    "Development": _link_section("Development", "CONTRIBUTING.md"),
    "Licence": _link_section("Licence", "LICENSE", "MIT"),
    "Citation": lambda tmp: [] if _section("Citation").strip() else ["how to cite Prove"],
}


@pytest.mark.parametrize("name", list(README_SECTIONS))
def test_pf7_1_each_readme_section_carries_its_facts(name: str, tmp_path: Path) -> None:
    assert name in sections(text_of(README)), f"no section {name!r}"
    assert README_SECTIONS[name](tmp_path) == []


def test_pf7_1_the_readme_keeps_the_never_phones_home_paragraph() -> None:
    assert NEVER_PHONES_HOME in flat(text_of(README))


# ---------- PF7.2 the docs set ----------


@pytest.mark.parametrize("rel", REQUIRED_PAGES)
def test_pf7_2_every_required_page_exists_and_opens_with_a_title(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"{rel} does not exist"
    if rel == "CHANGELOG.md":
        return  # its form is the hygiene module's
    first = text_of(rel).lstrip().splitlines()[:1]
    assert first and first[0].startswith("# "), (rel, first)


def exit_codes(verb: str) -> set[int]:
    return {0, 1, 2, 3, 130} | ({4} if verb in ("check", "paired") else set())


@pytest.mark.parametrize("verb", VERBS)
def test_pf7_2_each_verb_page_has_its_help_options_examples_exit_codes_and_writes(verb: str) -> None:
    rel = f"docs/commands/{verb}.md"
    page = page_of(rel)
    text = text_of(rel)
    help_out, help_code = HELPS["helps"][verb]
    assert help_code == 0, f"{verb} --help exits {help_code}"
    helps = [(b, out) for b in blocks_with(page, verb) for c, out in check.commands(b) if c.strip() == f"poisson-prove {verb} --help"]
    assert len(helps) == 1, f"{rel}: one console block shows `poisson-prove {verb} --help`"
    block, shown = helps[0]
    assert block.mark is not None and block.mark.kind == "run", f"{rel}: the help block is marked run"
    assert check.help_lines(shown or []) == check.help_lines(help_out.splitlines()), f"{rel}: the help shown is not --help"
    outside = text.replace(block.text, "")
    options = sorted(set(re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", help_out)) - {"--help"})
    unnamed = [o for o in options if not re.search(rf"`[^`]*(?<![\w-]){re.escape(o)}(?![\w-])[^`]*`", outside)]
    assert unnamed == [], f"{rel}: options not explained: {unnamed}"
    examples = [b for b in blocks_with(page, verb) if b is not block and b.mark is not None and b.mark.kind == "run"
                and any(verb_of(c) == verb and not re.search(r"--help\b", c)
                        and any(line.strip() and line.strip() != "…" for line in out or []) for c, out in check.commands(b))]
    assert len(examples) >= 2, f"{rel}: two or more examples run with their output"
    parts = sections(text)
    assert "Exit codes" in parts and "What it writes" in parts, (rel, list(parts))
    listed = {int(m.group(1)) for line in parts["Exit codes"].splitlines()
              if (m := re.match(r"^\s*(?:[-*]\s+|\|\s*)`?(\d{1,3})`?(?=\s|\||:|$)", line))}
    assert listed == exit_codes(verb), (rel, sorted(listed))


@pytest.mark.parametrize("rel", [README, "docs/quickstart.md"])
def test_pf7_2_the_first_run_pages_show_its_commands_and_its_verdict(rel: str) -> None:
    page = page_of(rel)
    runs = [(c, out) for b in page.blocks if b.mark is not None and b.mark.kind == "run" for c, out in check.commands(b)]
    commands = [check.bare(c) for c, _ in runs]
    missing = [c for c in FIRST_COMMANDS[2:] if c not in commands]
    assert missing == [], f"{rel}: the first run's commands are not all run: {missing}"
    shown = [out for c, out in runs if check.bare(c) == "poisson-prove diff" and out]
    assert shown, f"{rel}: the first run's diff is shown with its output"
    assert check.head(shown[0][0]) == QUICKSTART_VERDICT, shown[0][:1]


def test_pf7_2_the_sweep_spec_page_names_every_key_and_table() -> None:
    from poisson_prove import sampler
    from poisson_prove.executor_burla import BurlaOptions
    from poisson_prove.executor_modal import ImageSpec, ModalOptions

    names = backticked(text_of("docs/sweep-spec.md"))
    fields = {
        "": list(sampler._TOP_FIELDS),
        "axes.<name>": list(sampler._AXIS_FIELDS),
        "capture": list(sampler._CAPTURE_FIELDS),
        "chaos": list(sampler._CHAOS_FIELDS),
        "declare": list(sampler._DECLARE_FIELDS),
        "modal": [f.name for f in dataclasses.fields(ModalOptions)],
        "modal.<image>": [f.name for f in dataclasses.fields(ImageSpec)],
        "burla": [f.name for f in dataclasses.fields(BurlaOptions)],
    }
    missing = [f"[{table}]" for table in fields if table and f"[{table}]" not in names
               and not (table == "axes.<name>" and re.search(r"\[axes\.[^\]]+\]", names))]
    missing += [f"{table or 'top'}.{key}" for table, keys in fields.items() for key in keys
                if not re.search(rf"(?<![\w.-]){re.escape(key)}(?![\w-])", names)]
    assert missing == [], missing


def test_pf7_2_the_statistics_page_explains_every_verdict_word() -> None:
    names = backticked(text_of("docs/concepts/what-the-statistics-claim.md")).splitlines()
    assert [w for w in VERDICT_WORDS if w not in names] == []


def _modal_backend(text: str) -> list[str]:
    from poisson_prove import executor_modal

    out = [w for w in ("[modal]", 'pip install "poisson-prove[modal]"', "`secrets`", "compute", "model tokens") if w not in text]
    if str(executor_modal._PRICES_ASOF) not in text:
        out.append(f"the price table's date, {executor_modal._PRICES_ASOF}")
    return out


def _burla_backend(text: str) -> list[str]:
    from poisson_prove.executor_burla import BurlaOptions

    pin = [r for r in tomllib.loads(text_of("pyproject.toml"))["project"]["optional-dependencies"]["burla"]]
    need = ["experimental", "DISABLE_BURLA_RELAY", 'pip install "poisson-prove[burla]"', *pin, "Windows"]
    out = [w for w in need if w not in text]
    required = [f.name for f in dataclasses.fields(BurlaOptions)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING]
    return out + [f"the required field {name}" for name in required if f"`{name}`" not in text]


BACKENDS = {
    "local": lambda text: [w for w in ("--episode-timeout",) if f"`{w}" not in text],
    "modal": _modal_backend,
    "burla": _burla_backend,
}


@pytest.mark.parametrize("backend", list(BACKENDS))
def test_pf7_2_the_backends_page_carries_what_each_backend_needs(backend: str) -> None:
    text = text_of("docs/backends.md")
    body = next((b for name, b in sections(text).items() if backend in name.lower()), None)
    assert body is not None, f"no section for the {backend} backend"
    assert BACKENDS[backend](body) == []


def test_pf7_2_the_fault_injection_page_names_every_fault_and_the_chaos_table() -> None:
    from poisson_prove import chaos, sampler

    text = text_of("docs/fault-injection.md")
    names = backticked(text)
    missing = [f for f in chaos.fault_names() if not re.search(rf"(?<![\w-]){re.escape(f)}(?![\w-])", names)]
    missing += [k for k in ("[chaos]", "position()", "httpx") if k not in names]
    missing += [k for k in sampler._CHAOS_FIELDS if not re.search(rf"(?<![\w-]){k}(?![\w-])", names)]
    if "AgentChaos" not in text or not any(link_problem("docs/fault-injection.md", h) is None and h.split("#")[0].endswith("NOTICE") for h in links_of(text)):
        missing.append("AgentChaos, with a link to NOTICE")
    assert missing == [], missing


@pytest.mark.parametrize("rel", ["docs/your-own-agent.md", "docs/setup-with-your-agent.md"])
def test_pf7_2_the_agent_pages_say_each_case_is_its_own_sweep_axis(rel: str, tmp_path: Path) -> None:
    text = text_of(rel)
    prose = re.sub(r"^```.*?^```[^\n]*$", "", text, flags=re.M | re.S)
    assert "its own sweep axis" in flat(prose), f"{rel}: said in the page's words, not only in a command's output"
    assert "case_id" in text and "meta" in text, rel
    if rel != "docs/your-own-agent.md":
        return
    for words in ("(cfg, seed)", "Episode", "target", "[capture]"):
        assert words in text, (rel, words)
    page = page_of(rel)
    refused = [(c, out) for b in page.blocks if b.lang == "console" and b.mark is not None and b.mark.kind == "run"
               for c, out in check.commands(b)
               if verb_of(c) in ("diff", "check", "report", "serve") and out and out[0].startswith("error:")]
    assert refused and all(check.expected_code(c) == 1 for c, _ in refused), \
        f"{rel}: a run example of the refused comparison, exiting 1"
    result = check.check_page(rel, check.checkout_install(), tmp_path)
    assert result.problems == [], "\n\n".join(result.problems)
    from poisson_prove.store import Store

    cases: set[str] = set()
    assert result.folder is not None
    for root in {p.parents[1] for p in result.folder.rglob("manifest.json")}:
        try:
            store = Store(root)
            for run in store.runs():
                cases |= {str(c) for c in store.read(run, meta=False, trace="none")["case_id"].dropna()}
        except Exception:  # noqa: BLE001 -- a folder that is not a store
            continue
    printed = [lines for step, code, lines in result.ran if check.bare(step.shown) in {check.bare(c) for c, _ in refused}]
    assert printed, "the refused comparison ran"
    for lines in printed:
        error = next((line for line in lines if line.startswith("error:")), "")
        named = {c for c in cases if re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", error)}
        assert len(named) >= 2, (error, sorted(cases))


def test_pf7_2_the_setup_page_carries_the_prompt_the_steps_and_the_options(tmp_path: Path) -> None:
    rel = "docs/setup-with-your-agent.md"
    text = text_of(rel)
    missing = [] if init_agent_json(tmp_path)["prompt"] in flat(text) else ["the prompt init --agent prints"]
    steps = skill_steps(tmp_path)
    assert len(steps) == 6, steps
    missing += [f"the step {s!r}" for s in steps if s.lower() not in text.lower()]
    missing += [o for o in ("--force", "--repo", "--print", "--dry-run", "--yes") if f"`{o}" not in text and f" {o}" not in backticked(text)]
    assert missing == [], missing


def test_pf7_2_the_terminal_app_page_says_how_it_opens_and_its_keys() -> None:
    rel = "docs/terminal-app.md"
    text = text_of(rel)
    names = backticked(text).splitlines()
    missing = [k for k in ("poisson-prove", "CI", "TERM", "NO_COLOR", "q", "Esc", "Enter", "Ctrl-C", "130") if k not in names]
    if not any(link_problem(rel, h) is None and h.split("#")[0].endswith("dashboard.md") for h in links_of(text)):
        missing.append("a link to the dashboard page")
    assert missing == [], missing


def test_pf7_2_the_dashboard_page_names_the_views_the_verb_and_what_saves() -> None:
    text = text_of("docs/dashboard.md")
    headings = [h.strip().lower() for h in re.findall(r"^#{2,4} (.+?)\s*$", text, flags=re.M)]
    missing = [v for v in VIEWS if not any(h == v or h.startswith(v + " ") or h.endswith(" " + v) for h in headings)]
    names = backticked(text)
    missing += [w for w in ("poisson-prove ui", "--open", ".poisson/ui/", "--save", "report", "serve") if w not in names]
    assert missing == [], missing


def test_pf7_2_the_architecture_page_names_the_core_and_the_faces() -> None:
    text = text_of("docs/architecture.md")
    missing = [w for w in ("poisson_prove.core", "poisson_prove.compare", "cli") if f"`{w}`" not in text]
    missing += [w for w in ("face", "renderer", "core") if not re.search(rf"\b{w}s?\b", text.lower())]
    assert missing == [], missing


def test_pf7_2_contributing_says_how_to_install_test_and_commit() -> None:
    text = text_of("CONTRIBUTING.md")
    commands = [check.bare(c) for c in check.command_lines(check.read_page("CONTRIBUTING.md"))]
    missing = []
    if not any(re.search(r"install .*-e .*\.\[[a-z,]*dev[a-z,]*\]", c) for c in commands):
        missing.append("the dev install")
    if not any(" -m " in c and "not math" in c and "-n" in c.split() for c in commands):
        missing.append("the code suite in parallel")
    if not any(re.search(r"-m [\"']?math\b", c) for c in commands):
        missing.append("the math suite")
    if SNAPSHOT_COMMAND not in commands:
        missing.append("the snapshot command")
    missing += [w for w in ("signed", "Conventional Commits") if w.lower() not in text.lower()]
    assert missing == [], missing


def test_pf7_2_the_python_page_says_json_dumps_on_an_unread_result_is_unsupported() -> None:
    paragraphs = re.split(r"\n\s*\n", text_of("docs/python.md"))
    said = [p for p in paragraphs if "json.dumps" in p and "to_json()" in p
            and re.search(r"\bnot supported\b|\bunsupported\b", p) and re.search(r"\bread\b", p)]
    assert len(said) == 1, said


# ---------- PF7.3 the docs check ----------


#: Every page from the checkout's install and, slow, from the wheel; the your-own-agent page's run
#: from the checkout is ``test_pf7_2_the_agent_pages_say_each_case_is_its_own_sweep_axis``'s.
PAGE_INSTALLS = [
    *(pytest.param(rel, "checkout", id=f"{rel}-checkout") for rel in PAGES if rel != "docs/your-own-agent.md"),
    *(pytest.param(rel, "wheel", marks=pytest.mark.slow, id=f"{rel}-wheel") for rel in PAGES),
]


@pytest.fixture(scope="session")
def shared_base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.getbasetemp()
    return base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base


@pytest.mark.parametrize("rel,install", PAGE_INSTALLS)
def test_pf7_3_every_marked_block_runs_and_does_what_its_page_shows(rel: str, install: str, tmp_path: Path, shared_base: Path) -> None:
    assert (ROOT / rel).is_file(), f"{rel} does not exist"
    if install == "checkout":
        where = check.checkout_install()
        page = check.read_page(rel)
        pair = check.once(shared_base, "quickstart", lambda f: check.build_quickstart(where, f)) if page.setup else None
    else:
        where, pair = check.wheel_install(shared_base, tmp_path), None
    result = check.check_page(rel, where, tmp_path, quickstart=pair)
    assert result.problems == [], "\n\n".join(result.problems)


def _write(tmp: Path, text: str) -> str:
    page = tmp / "page.md"
    page.write_text(text, encoding="utf-8")
    return str(page)


RIGHT = """# A page

<!-- docs-check: setup quickstart -->

<!-- docs-check: run -->
```console
$ poisson-prove runs
ok  the sentence is not compared
…
#  name  a header's first field
$ poisson-prove --store nowhere runs  # exits 1
error: the words of a refusal are not compared
  next: poisson-prove --store nowhere sweep SPEC.toml --target pkg.module:rollout
$ poisson-prove runs --json
{"schema": "poisson-prove.runs/1", "verdict": "ok", "runs": [{"run_id": "…", "run_name": "…"}]}
$ poisson-prove runs --help
{RUNS_HELP}
```

<!-- docs-check: run -->
```console
$ poisson-prove runs
…
#  name  a later line alone
```

<!-- docs-check: file spec.toml -->
```toml
replicates = 3
```

<!-- docs-check: run -->
```bash
test -f spec.toml
poisson-prove runs --json > runs.json
```

<!-- docs-check: run -->
```python
import json
assert json.load(open("runs.json"))["verdict"] == "ok"
```

<!-- docs-check: skip: needs a model key -->
```bash
poisson-prove sweep --yes --target my_agent:rollout
```
"""


def _page(*blocks: str) -> str:
    return "# A page\n\n" + "\n".join(blocks)


def _run(lang: str, body: str) -> str:
    return f"<!-- docs-check: run -->\n```{lang}\n{body}\n```\n"


REFUSAL = "$ poisson-prove --store nowhere runs  # exits 1\nerror: words\n  next: poisson-prove --store nowhere sweep SPEC.toml --target pkg.module:rollout"
EMPTY_JSON = 'mkdir -p empty\n'

#: Each wrong page, small, and the kind of failure the check must report for it.
WRONG = {
    "a block with no mark": ("unmarked", _page("```bash\ntrue\n```\n")),
    "a mark with no block under it": ("dangling", _page("<!-- docs-check: run -->\n\nA paragraph.\n")),
    "a mark it does not know": ("unknown-mark", _page("<!-- docs-check: maybe -->\n```bash\ntrue\n```\n")),
    "a skip with no reason": ("no-reason", _page("<!-- docs-check: skip: x -->\n```bash\ntrue\n```\n")),
    "a text block marked run": ("not-runnable", _page(_run("text", "hello"))),
    "a block marked run with nothing to run": ("not-runnable", _page(_run("console", "ok  no command"))),
    "a setup mark after a block": ("setup-order", _page(_run("bash", "true"), "<!-- docs-check: setup quickstart -->\n")),
    "a file that does not parse": ("parse", _page("<!-- docs-check: file spec.toml -->\n```toml\nreplicates = = 3\n```\n")),
    "a spec with a key no spec has": ("parse", _page(_run("toml", 'target = "my_agent:rollout"\n\n[captur]\ncontent = false'))),
    "a wrong exit code": ("exit", _page(_run("bash", "false"))),
    "a failure inside a pipe": ("exit", _page(_run("bash", "false | cat"))),
    "a python block that fails": ("exit", _page(_run("python", "raise SystemExit(1)"))),
    "a wrong verdict word": ("first-line", _page(_run("console", REFUSAL.replace("error: words", "ok  words")))),
    "a label it did not print": ("not-printed", _page(_run("console", REFUSAL + "\n  then: nothing"))),
    "a line out of order": ("not-printed", _page(_run("console", REFUSAL + "\n  next: poisson-prove --store PATH runs\n"
                                                                   "  next: poisson-prove --store nowhere sweep SPEC.toml --target pkg.module:rollout"))),
    "a next line not printed": ("not-printed", _page(_run("console", REFUSAL.replace("--target pkg.module:rollout", "--target x:y")))),
    "a line at another indent": ("not-printed", _page(_run("console", REFUSAL.replace("\n  next:", "\nnext:")))),
    "a JSON key it does not hold": ("json", _page(_run("bash", EMPTY_JSON), _run("console", '$ poisson-prove --store empty runs --json\n{"schema": "poisson-prove.runs/1", "no_such_key": 1}'))),
    "a JSON schema it did not print": ("json", _page(_run("bash", EMPTY_JSON), _run("console", '$ poisson-prove --store empty runs --json\n{"schema": "poisson-prove.run/1"}'))),
    "a JSON verdict it did not print": ("json", _page(_run("bash", EMPTY_JSON), _run("console", '$ poisson-prove --store empty runs --json\n{"verdict": "no"}'))),
    "a help it does not print": ("help", _page(_run("console", "$ poisson-prove runs --help\nusage: poisson-prove runs [-h]\n\nLists the runs."))),
    "a network connection": ("network", _page(_run("python", "import socket\ntry:\n    socket.create_connection(('192.0.2.1', 443), timeout=1)\nexcept OSError:\n    pass"))),
    "a raw connection": ("network", _page(_run("python", "import socket\ns = socket.socket()\ntry:\n    s.connect(('192.0.2.1', 443))\nexcept OSError:\n    pass"))),
}


@pytest.mark.parametrize("case", ["a right page", *WRONG])
def test_pf7_3_the_docs_check_catches_each_way_a_page_can_be_wrong(case: str, tmp_path: Path, shared_base: Path) -> None:
    where = check.checkout_install()
    if case == "a right page":
        text = RIGHT.replace("{RUNS_HELP}", HELPS["helps"]["runs"][0].rstrip("\n"))
        pair = check.once(shared_base, "quickstart", lambda f: check.build_quickstart(where, f))
        result = check.check_page(_write(tmp_path, text), where, tmp_path / "run", quickstart=pair)
        assert result.problems == [], "\n\n".join(result.problems)
        return
    result = check.check_page(_write(tmp_path, WRONG[case][1]), where, tmp_path / "run")
    assert WRONG[case][0] in result.kinds, (case, result.found)


# ---------- PF7.7 the recipes ----------


def test_pf7_7_the_recipes_are_the_six_named() -> None:
    found = sorted(p.stem for p in (ROOT / "docs" / "recipes").glob("*.md")) if (ROOT / "docs" / "recipes").is_dir() else []
    assert found == sorted(RECIPES), found


@pytest.mark.parametrize("name", list(RECIPES))
def test_pf7_7_each_recipe_is_short_ends_with_what_it_cannot_tell_and_is_run_or_skipped_as_listed(name: str, tmp_path: Path) -> None:
    rel = f"docs/recipes/{name}.md"
    text = text_of(rel)
    assert len(text.splitlines()) < 150, len(text.splitlines())
    headings = re.findall(r"^## (.+?)\s*$", text, flags=re.M)
    assert headings and headings[-1] == "What this does not tell you", headings
    assert RUN_ID.findall(text) == [], RUN_ID.findall(text)
    runs, reason, parsed = RECIPES[name]
    page = page_of(rel)
    command_blocks = [b for b in page.blocks if is_command_block(b)]
    ran = [b for b in command_blocks if b.mark is not None and b.mark.kind == "run"]
    skipped = [b for b in command_blocks if b.mark is not None and b.mark.kind == "skip"]
    assert bool(ran) == runs, (rel, [b.line for b in ran])
    assert all(b.mark is not None and b.mark.arg == reason for b in skipped), (rel, [(b.line, b.mark) for b in skipped])
    if reason is None:
        assert skipped == [], (rel, [b.line for b in skipped])
    if not runs:
        assert skipped, rel
    if parsed:
        specs = [b for b in page.blocks if b.lang == "toml" and b.mark is not None and b.mark.kind in ("run", "file")]
        assert specs, f"{rel}: its spec is parsed"
    assert RECIPE_SHOWS[name](page, tmp_path) == []


def _loaded(page: check.Page, tmp: Path, load) -> list[Any]:  # type: ignore[no-untyped-def]
    """Each TOML block of the page that ``load`` reads from a file without refusing it."""
    out = []
    for n, block in enumerate(b for b in page.blocks if b.lang == "toml"):
        path = tmp / f"block-{n}.toml"
        path.write_text(block.text, encoding="utf-8")
        try:
            out.append(load(path))
        except Exception:  # noqa: BLE001 -- a block this reader refuses is not the one asked for
            continue
    return out


def _runs(page: check.Page) -> list[tuple[str, list[str] | None]]:
    return [(check.bare(c), out) for b in page.blocks if b.mark is not None and b.mark.kind == "run" for c, out in check.commands(b)]


def _shows_in_ci(page: check.Page, tmp: Path) -> list[str]:
    runs = [(c, out) for b in page.blocks if b.mark is not None and b.mark.kind == "run" for c, out in check.commands(b)]
    out = [] if any(verb_of(c) == "check" and check.expected_code(c) == 4 for c, _ in runs) else ["a check that exits 4"]
    return out + ([] if any("--json" in c.split() for c, _ in runs) else ["a --json command"])


def _shows_too_small(page: check.Page, tmp: Path) -> list[str]:
    shown = [out for c, out in _runs(page) if verb_of(c) in ("diff", "check") and out]
    return [] if any(check.head(out[0]) == "too small to tell" for out in shown) else ["a comparison that says too small to tell"]


def _shows_prompt_change(page: check.Page, tmp: Path) -> list[str]:
    runs = [c for c, _ in _runs(page)]
    out = [] if any("--pair-with latest" in c for c in runs) else ["--pair-with latest"]
    return out + ([] if any(verb_of(c) == "check" and "--fail-on worse" in c for c in runs) else ["check --fail-on worse"])


def _shows_model_change(page: check.Page, tmp: Path) -> list[str]:
    from poisson_prove.sampler import SweepSpec

    specs = _loaded(page, tmp, SweepSpec.load)
    out = [] if any(len({str(c.get("model")) for c in s.configs}) == 2 for s in specs) else ["a spec with an [axes.model] of two values"]
    return out + ([] if any(verb_of(c) == "paired" and "--cap-check" in c for c in check.command_lines(page)) else ["paired --cap-check"])


def _shows_paired_replay(page: check.Page, tmp: Path) -> list[str]:
    from poisson_prove.paired import Declaration

    out = [] if _loaded(page, tmp, Declaration.from_toml) else ["a declaration the paired module loads"]
    return out + ([] if any(verb_of(c) == "paired" for c in check.command_lines(page)) else ["paired"])


RECIPE_SHOWS = {
    "first-look": lambda page, tmp: [c for c in FIRST_COMMANDS[2:] if c not in [c for c, _ in _runs(page)]],
    "a-prompt-change": _shows_prompt_change,
    "a-model-change-with-cost": _shows_model_change,
    "in-ci": _shows_in_ci,
    "when-it-says-too-small-to-tell": _shows_too_small,
    "paired-replay": _shows_paired_replay,
}


# ---------- PF7.8 the example ----------


EXAMPLE = ROOT / check.EXAMPLE


class _Reply:
    def __init__(self, content: str) -> None:
        message = type("Message", (), {"content": content, "role": "assistant", "tool_calls": None})()
        self.choices = [type("Choice", (), {"message": message, "finish_reason": "stop", "index": 0})()]
        self.usage = type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})()
        self.model = "stand-in"


class _StandIn:
    """``openai.OpenAI`` with its Chat Completions call answered here; nothing leaves the process."""

    calls: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        outer = self

        class _Completions:
            def create(self, **kwargs: Any) -> _Reply:
                outer.calls.append(kwargs)
                return _Reply("4")

        self.chat = type("Chat", (), {"completions": _Completions()})()


def test_pf7_8_the_example_runs_keyless_with_its_client_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (EXAMPLE / "README.md").is_file() and (EXAMPLE / "prove.toml").is_file(), sorted(p.name for p in EXAMPLE.glob("*"))
    spec = tomllib.loads((EXAMPLE / "prove.toml").read_text(encoding="utf-8"))
    module_name, _, function = spec["target"].partition(":")
    source = EXAMPLE / f"{module_name}.py"
    assert source.is_file(), source
    tree = ast.parse(source.read_text(encoding="utf-8"))
    docstrings = {line for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)
                  for line in range(n.body[0].lineno, (n.body[0].end_lineno or n.body[0].lineno) + 1)}
    code = [line for i, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1)
            if line.strip() and not line.strip().startswith("#") and i not in docstrings]
    assert len(code) <= 20, len(code)
    readme = check.read_page(f"{check.EXAMPLE}/README.md")
    assert any(b.mark is not None and b.mark.kind == "skip" and "key" in b.mark.arg for b in readme.blocks), "the README is marked: needs a key"
    dry = prove("sweep", "--dry-run", cwd=EXAMPLE, home=tmp_path)  # no OPENAI variable reaches it
    assert dry.returncode == 0, dry.stdout + dry.stderr
    for name in [n for n in os.environ if n.startswith("OPENAI")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("OPENAI_API_KEY", "a-placeholder-not-a-key")
    import openai

    monkeypatch.setattr(openai, "OpenAI", _StandIn)
    monkeypatch.syspath_prepend(str(EXAMPLE))
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    try:
        declared = spec.get("declare", {})
        outcomes = set(declared.get("outcomes", ())) | set(declared.get("failures", ())) | set(declared.get("successes", ()))
        axes = spec.get("axes", {})
        grid = [dict(zip(axes, values)) for values in itertools.product(*(a["values"] for a in axes.values()))]
        assert grid and outcomes, (grid, outcomes)
        from poisson_prove import Episode

        _StandIn.calls.clear()
        for cfg, seed in itertools.product(grid, range(3)):
            episode = getattr(module, function)(cfg, seed)
            assert isinstance(episode, Episode), episode
            assert episode.outcome in outcomes | {"completed"}, (cfg, episode.outcome, outcomes)
            assert isinstance((episode.meta or {}).get("case_id"), str), episode.meta
        assert len(_StandIn.calls) >= len(grid), len(_StandIn.calls)
    finally:
        sys.modules.pop(module_name, None)


# ---------- across the pages ----------


@pytest.mark.parametrize("rel", PAGES)
def test_pf7_every_link_of_every_page_resolves(rel: str) -> None:
    problems = [p for href in links_of(text_of(rel)) if (p := link_problem(rel, href)) is not None]
    assert problems == [], problems


def test_pf7_every_docs_page_prove_points_to_exists() -> None:
    package = ROOT / "src" / "poisson_prove"
    named: set[str] = set()
    for path in package.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".md", ".toml", ".txt"):
            named |= set(re.findall(r"(?<![\w/])docs/[\w/-]+\.md", path.read_text(encoding="utf-8")))
    assert named, "the code points to no docs page, which it does today"
    assert sorted(p for p in named if not (ROOT / p).is_file()) == []


def test_pf7_no_page_or_help_says_with_stated_confidence(tmp_path: Path) -> None:
    said = [rel for rel in PAGES if "stated confidence" in flat(text_of(rel))]
    if "stated confidence" in tomllib.loads(text_of("pyproject.toml"))["project"].get("description", ""):
        said.append("the PyPI description")
    for verb, (text, _) in HELPS["helps"].items():
        if "stated confidence" in flat(text):
            said.append(f"{verb or 'the top-level'} --help")
    assert said == [], said


def test_pf7_no_page_claims_what_0_1_0_does_not_build() -> None:
    """No page offers a flag, a verb or an extra 0.1.0 does not have."""
    said = []
    for rel in PAGES:
        if not (ROOT / rel).is_file():
            continue
        text = text_of(rel)
        said += [f"{rel}: {w}" for w in ("--target-mde", "check --baseline", "poisson-prove[chaos]", "poisson-prove[viz]") if w in text]
        said += [f"{rel}: {c}" for c in check.command_lines(check.read_page(rel)) if verb_of(c) == "run"]
    assert said == [], said


def test_pf7_2_the_layered_report_page_works_on_the_quickstart_pair_and_names_its_layers() -> None:
    rel = "docs/concepts/the-layered-report.md"
    assert page_of(rel).setup == "quickstart", f"{rel}: set up on the quickstart pair (d10)"
    text = text_of(rel).lower()
    assert [w for w in ("omnibus", "fault line", "cell", "bound") if w not in text] == []


def test_pf7_the_docs_show_plain_output() -> None:
    shown = []
    for rel in PAGES:
        if not (ROOT / rel).is_file():
            continue
        for block in check.read_page(rel).blocks:
            if block.lang != "console":
                continue
            for _, out in check.commands(block):
                for line in out or []:
                    if "\x1b" in line or re.search(r"[─-▟]", line):
                        shown.append(f"{rel}:{block.line}: {line!r}")
    assert shown == [], shown[:20]


def test_pf7_no_command_on_any_page_is_given_a_run_id() -> None:
    given = [f"{rel}: {c}" for rel in PAGES if (ROOT / rel).is_file()
             for c in check.command_lines(check.read_page(rel)) if RUN_ID.search(c)]
    assert given == [], given
