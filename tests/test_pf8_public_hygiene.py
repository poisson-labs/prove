"""PF8 -- public hygiene: everything that ships reads as a public tool (*Prove -- Spec Front Door*,
sections 2.5, 9.1 to 9.5 and PF8.0 to PF8.7; Q35 to Q38 and Q48, ruled yes 2026-10-13).

These tests are frozen before the cleanup they check, which comes last in the build, after the
setup agent, the static UI, the terminal app and the docs have landed. Today's ``main`` fails
many of them, and the release log says which and why.

**What is pinned is what ships.** The wheel and the sdist, built from this checkout once per test
run and shared by every worker (hatchling in a child process, over the files a commit of this
checkout would hold); the repository's tree as ``git`` lists it; the command's help, messages and
the files its verbs write, from processes of their own with ``HOME`` at an empty folder. Nothing
here imports a module of the package to read a string out of it.

**Rules, not lists.** The plain-words test (PF8.4) matches a frozen pattern list over a corpus
that is found, not listed: every member of the wheel, every verb the help lists, every file the
quickstart pair's commands write, every file under the store's ``.poisson/``, every file
``init --agent`` writes, every snapshot of the terminal app, every text file of the tree and the
sdist. A later module that adds text adds it to the corpus by shipping it. The lists that remain
are the spec's own: section 9.1's removed files, section 9.5's third-party items, section 9.3's
families.

**The pattern list** (``FAMILIES``) is section 9.3's families, each term with the case it catches,
each family with ordinary words it must let pass. Every permitted exception is in ``ALLOWED`` with
its reason, a case it allows and a case it still refuses; an exception is tied to the span it
covers, never to the whole line. A match inside the user's own data is not a failure: each
rendered output has the values the test itself typed (its arguments, folders, run ids and names)
masked, at word boundaries, before it is read.

**Readings this file freezes** (each owed as one yes/no in the release log; the cleanup builds
against them unedited):

- **r1** An internal code is told from an ordinary word by its shape and its case: one to three
  capital letters, an optional dash, digits, an optional dotted number and one optional lower-case
  letter, standing alone (``S25``, ``A8a``, ``PR-1``, ``ADR-028``, ``PF0.1``, ``LST12``, ``Q17``).
  Lower-case codes are not matched, in prose or in names: by shape ``a7`` cannot be told from the
  ordinary ``x0``, ``t0``, ``e1`` and ``n10`` of ``src/``, so section 9.2's lower-case identifiers
  are renamed by hand. Names that happen to have the shape are allowed one by one in ``ALLOWED``.
- **r2** The word families match whole words in any case, with no exception for ordinary uses:
  "ruled out" and "a shim" fail and are rewritten, and so does an ordinary use of a word of the
  note-store family.
- **r3** The corpus of ``src/`` is read from the wheel: every string literal, docstring and
  comment, and identifiers too, split at underscores and read for capital codes only
  (``_A7_TRACE_KEYS`` fails; section 9.2 renames it).
- **r4** Besides section 9.3's list, the docs case reads every text file of the tree and the sdist
  outside ``src/`` and ``tests/`` (``pyproject.toml``, ``.gitignore``, ``PKG-INFO``, ``.github/``,
  ``examples/``), except ``LICENSE`` and ``NOTICE``, which must name their copyright holder and the
  data they cover and are PF8.3's, and the two standards. The Go1 fixture's folder is not named in
  them (section 6.3: the fixture is described by what it is).
- **r5** The tests case holds Q38 over the sdist's ``tests/``: no personal name, note-store trace,
  local or scratch path, or session letter anywhere in a test file's strings and comments; the two words
  Q38 makes plain only in docstrings and comments (a test's own data may say them); ids stay in
  test names. This file spells the patterns between two markers, and only those lines are left
  out. The cleanup edits docstrings and comments of frozen test files for those words only, never
  an assertion; the frozen digests over test files are over their code (``conftest.code_of``).
- **r6** The old name may appear in the wheel only in ``poisson_prove/_compat.py``, in the
  CHANGELOG on one line, and in the output of a command given a store the private builds wrote.
- **r7** Section 9.3's three new parts: the terminal app's screens are read from its home screen,
  opened on a pseudo-terminal over the quickstart pair, and from the snapshot files PF6.14 commits
  (every file under a ``__snapshots__`` folder in ``tests/``; at least one must exist); the static
  UI's pages are every file ``poisson-prove ui`` leaves under the store's ``.poisson/``; the setup
  skill is what ``init --agent --print`` prints and every file ``init --agent`` writes. Markup is
  read with its entities decoded and ``data:`` URIs left out. A part that cannot be produced fails
  the test: PF8 is built after PF6, PF11 and PF12.
- **r8** NOTICE names a third-party item of section 9.5 only while the sdist carries it, each in a
  section of its own: AgentChaos for the chaos catalogue, HumanEval for the golden pilot's data,
  the tau2-bench pilot's terms for that pilot, and the committed two-run fixture as Poisson Labs'
  own data. NOTICE's own copyright line is LICENSE's.
- **r9** The CHANGELOG's release headings are ``## X.Y.Z — YYYY-MM-DD``, with ``Unreleased`` in
  place of the date until the release session sets it; the oldest is ``0.1.0``; its section names
  every verb the help lists inside a code span on a bullet; the old name is on one line, under or
  beside the word "Renamed". That it names no internal code is PF8.4's docs case.
- **r10** PF8.5 has two tests: a fast one over the sdist's tests (no test names a place under the
  home folder, a machine's own folders or a folder beside the repository), in the code suite; and
  the suite itself, run once with ``HOME`` at an empty folder, in which no skip's reason names a
  place, marked ``slow`` because it is a whole suite run.
- **r11** ``docs/repo-hygiene.md`` is pinned by the sha256 of the canonical copy, local-stack's at
  ``222ec08755eb754ab187bdaa8424e71cb009db80`` (Trace's copy has the same bytes).
- **r12** ``CONTRIBUTING.md`` carries the three rules section 9.1 moves out of the agent rules
  file, read by their facts: the core imports no network library, frozen tests are not edited,
  commits are Conventional Commits.

**Seams, tested only on PF8's side:** PF7.6 (the exact sdist and wheel sets; here only that
section 9.1's files are absent), PF7.4 (the metadata), PF12.8 and PF12.9 (what a page may load
or hold), PF4.11 (paths in output), PF0's accept-list (the old name read back).

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF8.0 the link check and the study records, before the freeze commit | a process gate, checked by the audit; no test |
| PF8.1 none of section 9.1's removed files is in the tree, the sdist or the wheel | ``test_pf8_1_no_file_section_9_1_removes_ships`` (tree, sdist, wheel) |
| PF8.1 (section 9.1, r12) the rules the agent rules file held are in ``CONTRIBUTING.md`` | ``test_pf8_1_contributing_md_carries_the_three_rules`` |
| PF8.2 ``.gitignore`` lists ``devlog.md`` and no ``notes`` | ``test_pf8_2_gitignore_lists_devlog_md_and_no_notes`` (tree, sdist) |
| PF8.3 LICENSE carries section 9.5's line | ``test_pf8_3_license_is_mit_with_the_copyright_line`` (tree, sdist, wheel) |
| PF8.3 NOTICE lists every third-party item named there with its URL | ``test_pf8_3_notice_names_every_third_party_item_that_ships`` (tree, sdist, wheel) |
| PF8.4 the pattern list catches every family, passes ordinary words, and each exception allows its case and no more | ``test_pf8_4_each_family_catches_its_terms_and_passes_ordinary_words`` (one case per family) |
| PF8.4 the plain-words test passes over its whole corpus | ``test_pf8_4_the_plain_words_test_passes_over_its_whole_corpus`` (one case per part) |
| PF8.5 no skip caused by data outside the repo | ``test_pf8_5_no_test_names_a_place_outside_the_repository``; ``test_pf8_5_with_home_empty_no_skip_names_a_place`` (slow) |
| PF8.6 CHANGELOG has section 9.4's form | ``test_pf8_6_the_changelog_has_section_9_4s_form`` |
| PF8.7 ``docs/repo-hygiene.md`` equals the canonical copy | ``test_pf8_7_repo_hygiene_md_equals_the_canonical_copy`` (tree, sdist) |

PF8.4 has two tests because the pattern list is the instrument the second one reads with:
section 9.3 asks for a case per family, and a pattern or an exception that also caught plain
English, or let a code through, would make the corpus test meaningless. PF8.5 has two because the
rule as stated costs a whole suite run (r10).
"""

from __future__ import annotations

import ast
import fcntl
import hashlib
import html
import io
import json
import os
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tarfile
import tempfile
import termios
import time
import tokenize
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

import test_pf1_look as PF1

ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = "tests/test_pf8_public_hygiene.py"
MOCK = "poisson_prove.examples.mock_agent"

# ---------- what section 9 decides ----------

#: Section 9.1: the files that leave the repository (Q35, Q36), as paths relative to the
#: repository; a folder ends in ``/``. ``scripts/`` goes whole.
REMOVED = (
    "CLAUDE.md",
    "SCOPE.md",
    ".githooks/",
    "notes",
    "scripts/",
    "examples/golden_pilot/",
    "examples/tau2_pilot/",
    "tests/test_pilot_golden.py",
    "tests/test_t4_tau2_pilot.py",
)

#: The MIT licence after its copyright line, whitespace aside (https://spdx.org/licenses/MIT.html).
MIT_BODY = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated "
    'documentation files (the "Software"), to deal in the Software without restriction, including without limitation '
    "the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to "
    "permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright "
    "notice and this permission notice shall be included in all copies or substantial portions of the Software. "
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE '
    "WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR "
    "COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR "
    "OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
)

#: PF8.7 (r11): the canonical ``docs/repo-hygiene.md``, local-stack's ``docs/repo-hygiene.md`` at
#: ``222ec08755eb754ab187bdaa8424e71cb009db80`` (github.com/poisson-labs/local-stack), 8,243 bytes,
#: read 2026-10-24; Trace's copy has the same bytes. A new version of the standard moves this pin.
REPO_HYGIENE_SHA256 = "802d0ff86e6a1b269c37281de749e57b9c5b069cd425aa91eed04edeba604131"

#: Section 9.3: the two standards the plain-words test leaves out.
STANDARDS = ("docs/cli-look.md", "docs/repo-hygiene.md")


@dataclass(frozen=True)
class Term:
    """One pattern of a family, with the text from section 9.3 it must catch."""

    label: str
    pattern: re.Pattern[str]
    catches: tuple[str, ...]


@dataclass(frozen=True)
class Family:
    name: str
    terms: tuple[Term, ...]
    #: ordinary text the family must let pass
    passes: tuple[str, ...]


def term(label: str, pattern: str, *catches: str, flags: int = 0) -> Term:
    return Term(label, re.compile(pattern, flags), catches)


@dataclass(frozen=True)
class Allowed:
    """A permitted match. ``text`` matches the whole match; ``context``, when set, must match a
    span of the line that holds the whole match; ``line``, when set, must match the whole line;
    ``part`` and ``place`` limit where (``place`` is searched in the file or call the line came
    from); ``once`` allows it on one line of a place only. ``allows`` and ``refuses`` are a
    ``(part, place, line)`` this exception lets pass and one with the same text it does not.
    ``context`` may be several patterns, each searched on its own."""

    terms: tuple[str, ...]
    text: str
    reason: str
    allows: tuple[str, str, str]
    refuses: tuple[str, str, str]
    context: str | tuple[str, ...] | None = None
    line: str | None = None
    part: str | None = None
    place: str | None = None
    once: bool = False


@dataclass(frozen=True)
class ThirdParty:
    """One item of section 9.5's NOTICE, which NOTICE must name while the sdist carries it (r8)."""

    name: str
    #: sdist paths (a folder ends in ``/``) whose presence means the item ships
    carried_by: tuple[str, ...]
    #: what one section of NOTICE must hold for it (regular expressions): its name, URL, licence
    must_say: tuple[str, ...]


IC = re.IGNORECASE
#: r1: one to three capitals, an optional dash, digits, an optional dotted number, one optional
#: lower-case letter, standing alone.
CODE = r"(?<![A-Za-z0-9_#])[A-Z]{1,3}-?[0-9]+(?:\.[0-9]+)*[a-z]?(?![A-Za-z0-9])"
#: A Modal GPU type, as Modal spells it.
GPU = r"T4|L4|L40S|A10G?|A100(?:-[48]0GB)?|PRO-6000|H100|H200|B200|B300"

# plain-words: the patterns begin (r5: the only lines of this file the tests case leaves out)

#: Section 9.5 and the lab's ruling of 2026-09-28: the copyright holder until incorporation.
COPYRIGHT = "Copyright (c) 2026 Taylor Kolasinski / Poisson Labs"

THIRD_PARTY = (
    ThirdParty("AgentChaos", ("src/poisson_prove/chaos_catalog.py",),
               (r"AgentChaos", r"https://github\.com/floritange/AgentChaos", r"\bMIT\b", r"Copyright \(c\) 2025 AgentChaos contributors")),
    ThirdParty("HumanEval", ("tests/fixtures/golden_pilot/", "examples/golden_pilot/"),
               (r"HumanEval", r"https://github\.com/openai/human-eval", r"\bMIT\b", r"OpenAI")),
    ThirdParty("tau2-bench", ("examples/tau2_pilot/",),
               (r"https://github\.com/sierra-research/tau2-bench",)),
    ThirdParty("the committed two-run fixture", ("tests/fixtures/go1/",),
               (r"tests/fixtures/go1", r"Poisson Labs'? own|own data")),
)

FAMILIES = (
    Family("internal id", (
        term("internal id", CODE,
             # packet and rule ids as src/ writes them, the C to Y families included
             "S25", "M14", "A8a", "PR-1", "PR23", "P-1", "FR13", "CD12", "ADR-028", "L20", "O16", "U16", "E1",
             "C3", "D9", "F22", "G4", "I9", "Q7", "V29", "W4", "Y8", "T4",
             # this spec's and its siblings' ids
             "PF0.1", "PF10", "Q17", "TF1", "FD8", "BD3", "LST12", "K8", "R1"),
    ), passes=("HTTP 503", "Python 3.11", "gpt-4.1-mini", "v0.1.0", "sha256", "utf8", "x86_64", "int64", "h1",
               "2026-10-24T17:16:53Z", "20260115T090000Z-7316", "cp1252", "U+2192", "a 2x2 table", "rule 10", "#F88685")),
    Family("session word", (
        term("Phase and a number", r"\bphase\s+[0-9]+\b", "Phase 2", "phase 3", flags=IC),
        term("Session A or B", r"\b[Ss]ession\s+[AB]\b", "Session A", "session B"),
        term("oracle", r"\boracles?\b", "the oracle", "Oracle", flags=IC),
        term("retrofit", r"\bretrofit\w*", "retrofit", "retrofitted", flags=IC),
        term("shim", r"\bshims?\b", "a shim", "shims", flags=IC),
        term("packet", r"\bpackets?\b", "this packet", "Packet", flags=IC),
        term("ruled", r"\bruled\b", "ruled 2026-09-22", "Ruled", "ruled out", flags=IC),
        term("ruling", r"\brulings?\b", "ruling 8", "the rulings", flags=IC),
    ), passes=("the phase of the sweep", "a session", "sessions", "per session a file", "rule 10", "a rule", "rules", "the unruly")),
    Family("internal name", (
        term("Taylor", r"\btaylor\b", "Taylor", "taylor's", flags=IC),
        term("Kolasinski", r"kolasinski", "Kolasinski", "taylorkolasinski", flags=IC),
        term("Go1", r"\bgo1\b", "Go1", "go1", "tests/fixtures/go1", flags=IC),
        term("HUMAIN", r"\bhumain\b", "HUMAIN", flags=IC),
        term("Borderless", r"\bborderless\b", "Borderless", flags=IC),
        term("Codestrap", r"\bcodestrap\b", "Codestrap", flags=IC),
        term("momus", r"\bmomus\b", "momus", flags=IC),
        term("45/44", r"(?<![0-9])45/44(?![0-9])", "45/44", "the 45/44 note"),
    ), passes=("go10", "ago 1 day", "4544", "45/440", "border", "less")),
    Family("vault trace", (
        term("wikilink", r"\[\[[A-Z][^\[\]\n]*\]\]", "[[Prove — Release Decisions]]", "[[Board]]"),
        term("vault", r"\bvault\b", "the vault", "Vault", flags=IC),
        term("Obsidian", r"\bobsidian\b", "Obsidian", flags=IC),
        term("notes/", r"\bnotes/", "notes/2026-10-24.md"),
        term("dispatch", r"\bdispatch\b", "the dispatch chat", "Dispatch 2026-10-07", flags=IC),
    ), passes=("[[scenarios]]", "[[axes.task_id]]", "df[[]]", "[[q.seed for q in pairs]]", "[[:space:]]", "[[-0.1, -2.3]]",
               "singledispatch", "functools.singledispatchmethod", "a note", "notes")),
    Family("local path", (
        term("/Users/", r"/Users/", "/Users/someone/code"),
        term("~/code", r"~/code\b", "~/code/poisson-labs"),
        term("a Windows profile", r"\\Users\\", "C:\\Users\\someone"),
        term("a scratch folder", r"/private/tmp/|\bclaude-[0-9]+\b|\bscratchpad/", "/private/tmp/x", "claude-501", "scratchpad/s29/mint.py"),
    ), passes=("users/", "the users", "~/.cache", "./prove-runs", "/tmp/", "claude.ai", "a scratch pad")),
    Family("old name", (
        term("proofload", r"proofload", "proofload", "PROOFLOAD_STORE", "Proofload", flags=IC),
    ), passes=("proof", "load", "poisson-prove")),
    Family("spec reference", (
        term("section sign", r"§", "§9.3"),
        term("front door", r"\bfront[- ]door\b", "front-door spec", "Front Door", flags=IC),
        term("spec section", r"\bspec(?:'s)?\s+sections?\b", "spec section 4.3", "the spec's section 9", flags=IC),
    ), passes=("the spec file", "a sweep spec", "the [axes] section", "section 3 of the docs")),
)
TERMS = {t.label: t for f in FAMILIES for t in f.terms}

#: r5: what Q38 holds over the tests: these anywhere in a test file's strings and comments ...
TESTS_TERMS = ("Taylor", "Kolasinski", "wikilink", "vault", "Obsidian", "notes/", "dispatch",
               "/Users/", "~/code", "a Windows profile", "a scratch folder", "Session A or B", "oracle", "retrofit")
#: ... and these only in its docstrings and comments, where Q38 makes them plain; a test's own data
#: (a run id, a salt, a file name) may say them.
PROSE_ONLY_TERMS = ("oracle", "retrofit")

ID = ("internal id",)
ALLOWED = (
    Allowed(("Taylor", "Kolasinski"), r"(?i)taylor|kolasinski", "the copyright line section 9.5 requires, wherever the licence text is carried",
            allows=("docs", "PKG-INFO", "  " + COPYRIGHT), refuses=("docs", "PKG-INFO", COPYRIGHT + ", thanks to Taylor"),
            line=rf"\s*{re.escape(COPYRIGHT)}\s*"),
    Allowed(ID, r"UTF-8", "the name of an encoding", allows=("package", "x.py", "read as UTF-8"), refuses=("package", "x.py", "read as UTF-9")),
    Allowed(ID, r"SHA-?256", "the name of a hash", allows=("package", "x.py", "its SHA-256"), refuses=("package", "x.py", "its SHA-255")),
    Allowed(ID, r"H[01]", "a null or alternative hypothesis, as statistics writes it", context=r"\bH[01]\b\W{0,3}(?::|is\b|the\b)",
            allows=("package", "x.py", "``H0`` is the sharp null"), refuses=("package", "x.py", "see H0 below")),
    Allowed(ID, r"M[1-9]", "an Apple chip, as a platform string names it", context=r"\bApple\s+M[1-9](?:\s+(?:Pro|Max|Ultra))?\b",
            allows=("docs", "README.md", "on an Apple M1 Pro"), refuses=("docs", "README.md", "on an Apple M1, the M4 store format")),
    Allowed(ID, r"S3|EC2", "an AWS service", context=r"\b(?:AWS|Amazon)\W+(?:S3|EC2)\b|\b(?:S3|EC2)\s+(?:buckets?|console|instances?)\b",
            allows=("package", "poisson_prove/executor_burla.py", "check the EC2 console"), refuses=("package", "x.py", "as S3 found")),
    Allowed(ID, GPU, "a GPU type in the table of Modal's prices", part="package", place=r"^poisson_prove/executor_modal\.py$", line=r'"[A-Z0-9-]+"',
            allows=("package", "poisson_prove/executor_modal.py", '"A100"'), refuses=("package", "poisson_prove/cli.py", '"A100"')),
    Allowed(ID, GPU, "a GPU type, beside the word GPU", context=(r"(?i)\bgpus?\b[^.;\n]{0,40}", r"(?i)[^.;\n]{0,15}\bgpus?\b"),
            allows=("help", "sweep --help", "the Modal GPU type, such as T4 or A100"), refuses=("help", "sweep --help", "the GPU type. As T4 decided")),
    Allowed(ID, r".+", "a model's name", context=r"(?i)\b(?:gpt|o[134]|deepseek|claude|llama|gemini|qwen|mistral|mixtral|phi)-[A-Za-z0-9.-]*",
            allows=("docs", "examples/x/README.md", "with GPT-4o or DeepSeek-R1"), refuses=("docs", "examples/x/README.md", "with R1 and GPT")),
    Allowed(ID, r"[A-Z]{1,3}[0-9]{3,4}", "a lint rule's code in a comment that silences it", context=r"#\s*noqa:\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*",
            allows=("package", "x.py", "except Exception:  # noqa: BLE001"), refuses=("package", "x.py", "BLE001 says so  # noqa: E501")),
    Allowed(ID, r"[A-Z]{1,3}[0-9]{3,4}", "a lint rule's code in the linter's own configuration", part="docs", place=r"^pyproject\.toml$",
            context=r'\[\s*"[A-Z]+[0-9]*"(?:\s*,\s*"[A-Z]+[0-9]*")*\s*,?\s*\]',
            allows=("docs", "pyproject.toml", 'ignore = ["E501", "B008"]'), refuses=("docs", "pyproject.toml", '"slow: the E501 lane"')),
    Allowed(("wikilink",), r"\[\[[A-Za-z0-9_.-]+\]\]", "a TOML array-of-tables header, as a docs page shows a sweep spec or a declaration",
            line=r"\s*\[\[[A-Za-z0-9_.-]+\]\]\s*",
            allows=("docs", "docs/sweep-spec.md", "[[Scenarios]]"), refuses=("docs", "docs/sweep-spec.md", "see [[Scenarios]] in the notes")),
    Allowed(ID, r".+", "a command of an SVG path's data", context=r'\bd="[^"]*"',
            allows=("quickstart", "heatmap.svg", '<path d="M136,120h5v5z L-3.5,4"/>'), refuses=("quickstart", "heatmap.svg", '<path d="M1 2"/><text>S25</text>')),
    Allowed(("proofload",), r"(?i)proofload", "the one module that holds every string spelling the old name (section 2.5)",
            part="package", place=r"^poisson_prove/_compat\.py$",
            allows=("package", "poisson_prove/_compat.py", '"proofload"'), refuses=("package", "poisson_prove/cli.py", '"proofload"')),
    Allowed(("proofload",), r"(?i)proofload", "the CHANGELOG's rename line (sections 2.5 and 9.4)", part="docs", place=r"^CHANGELOG\.md$", once=True,
            allows=("docs", "CHANGELOG.md", "were called proofload"), refuses=("docs", "README.md", "were called proofload")),
    Allowed(("proofload",), r"(?i)proofload", "a command given a store the private builds wrote names their writer (section 2.5)", place=r"^old-data:",
            allows=("conformance", "old-data:runs", "written by proofload 0.0.1"), refuses=("conformance", "runs", "written by proofload 0.0.1")),
)

#: r10: a skip whose reason names a place (a folder, the home folder) is a skip for data outside
#: the repository; a skip for a missing package, a platform or an opt-in variable names none.
SKIP_NAMES_A_PLACE = re.compile(r"(?:^|[\s:('\"=])(?:~|/[A-Za-z.]|[A-Za-z]:\\)|\bHOME\b")

#: r10: how a test module at ``tests/`` reaches outside the repository: the home folder by any
#: spelling, a machine's own folders written out, or a folder beside the repository.
OUTSIDE = re.compile(r"Path\.home\(|expanduser\(|/Users/|[A-Za-z]:\\\\?Users|\b(?:ROOT|REPO)\.parent\b|\.parents\[[2-9]\]")
#: The one permitted read outside: a real-backend test (never run without the user's own account)
#: looks for that account's credentials; it reads no data.
OUTSIDE_ALLOWED = re.compile(r"\.modal\.toml")

#: PF8.2: the ``.gitignore`` entries for the private notes folder, which section 9.1 removes.
NOTES_ENTRIES = {"notes", "notes/", "/notes", "/notes/"}

# plain-words: the patterns end


@dataclass(frozen=True)
class Hit:
    part: str
    place: str
    line_no: int
    term: str
    text: str
    line: str
    #: where the match starts in ``line``
    start: int = 0

    def __str__(self) -> str:
        return f"{self.part} {self.place}:{self.line_no} [{self.term}] {self.text!r} in {self.line.strip()[:160]!r}"


def scan(part: str, place: str, text: str, terms: Iterable[str] | None = None) -> list[Hit]:
    """Every match of the pattern list in ``text``, line by line."""
    chosen = [TERMS[label] for label in terms] if terms is not None else list(TERMS.values())
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        for t in chosen:
            for m in t.pattern.finditer(line):
                hits.append(Hit(part, place, no, t.label, m.group(0), line, m.start()))
    return hits


def allowed(hit: Hit) -> Allowed | None:
    end = hit.start + len(hit.text)
    for a in ALLOWED:
        if hit.term not in a.terms or not re.fullmatch(a.text, hit.text):
            continue
        contexts = (a.context,) if isinstance(a.context, str) else a.context or ()
        if contexts and not any(m.start() <= hit.start and end <= m.end() for c in contexts for m in re.finditer(c, hit.line)):
            continue
        if a.line is not None and not re.fullmatch(a.line, hit.line):
            continue
        if a.part is not None and a.part != hit.part:
            continue
        if a.place is not None and not re.search(a.place, hit.place):
            continue
        return a
    return None


def failures(hits: Iterable[Hit]) -> list[Hit]:
    """The hits no exception allows; an exception allowed ``once`` allows its first line only."""
    out, used = [], {}
    for hit in hits:
        a = allowed(hit)
        if a is None:
            out.append(hit)
        elif a.once:
            key = (id(a), hit.place)
            if used.setdefault(key, hit.line_no) != hit.line_no:
                out.append(hit)
    return out


def readable(name: str, text: str) -> str:
    """Markup with its entities decoded and its ``data:`` URIs taken out (r7); other text as it is."""
    if re.search(r"\.(?:html?|svg|xml)$|page$|__snapshots__/", name):
        return html.unescape(re.sub(r"data:[^\"')\s]+", "data:", text))
    return text


# ---------- what ships, built once per run ----------


def once(tmp_path_factory: pytest.TempPathFactory, name: str, build: Callable[[Path], None]) -> Path:
    """``build(folder)`` once per test run, shared by every worker of the run."""
    root = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        root = root.parent
    folder, done = root / f"pf8-{name}", root / f"pf8-{name}.done"
    with open(root / f"pf8-{name}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not done.exists():
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir()
            build(folder)
            done.write_text("", encoding="utf-8")
    return folder


def tree_files() -> list[str]:
    """The paths a commit of this checkout would hold, tracked and untracked, ignored ones left
    out; a symbolic link is one of them (a ``notes`` link into a private folder is section 9.1's)."""
    done = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                          capture_output=True, timeout=60)
    assert done.returncode == 0, done.stderr.decode()
    return sorted({p for p in done.stdout.decode().split("\0") if p and ((ROOT / p).is_symlink() or (ROOT / p).is_file())})


def build_archives(folder: Path) -> None:
    """The wheel and the sdist, built from a copy of the tree's files (a symbolic link is left
    behind: what it points to is not the repository's, and the tree case reports it)."""
    source = folder / "source"
    for rel in tree_files():
        if (ROOT / rel).is_symlink():
            continue
        (source / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, source / rel)
    script = ("import sys\nfrom hatchling.build import build_sdist, build_wheel\n"
              "print(build_wheel(sys.argv[1]))\nprint(build_sdist(sys.argv[1]))\n")
    done = subprocess.run([sys.executable, "-c", script, str(folder / "dist")], cwd=source, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr


@dataclass(frozen=True)
class Archive:
    kind: str
    #: path inside the archive, relative to its root (the sdist's top folder stripped) -> bytes;
    #: a symbolic link in the tree holds its target
    files: dict[str, bytes]

    def has(self, path: str) -> list[str]:
        """The members equal to ``path`` or under it (a folder ends in ``/``), at any depth."""
        parts = path.rstrip("/").split("/")
        found = []
        for name in self.files:
            names = name.split("/")
            for i in range(len(names) - len(parts) + 1):
                if names[i:i + len(parts)] == parts and (path.endswith("/") or i + len(parts) == len(names)):
                    found.append(name)
                    break
        return found

    def text(self, path: str) -> str:
        return self.files[path].decode("utf-8")


@pytest.fixture(scope="module")
def archives(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Archive]:
    folder = once(tmp_path_factory, "archives", build_archives)
    (wheel,) = (folder / "dist").glob("*.whl")
    (sdist,) = (folder / "dist").glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as z:
        wheel_files = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    with tarfile.open(sdist) as t:
        sdist_files = {}
        for m in t.getmembers():
            if m.isfile():
                extracted = t.extractfile(m)
                assert extracted is not None
                sdist_files[m.name.split("/", 1)[1]] = extracted.read()
    tree = {rel: os.readlink(ROOT / rel).encode() if (ROOT / rel).is_symlink() else (ROOT / rel).read_bytes() for rel in tree_files()}
    return {"tree": Archive("tree", tree), "sdist": Archive("sdist", sdist_files), "wheel": Archive("wheel", wheel_files)}


def dist_info(archive: Archive, name: str) -> str:
    """A file of the wheel's ``dist-info`` (its licence files sit under ``licenses/``)."""
    (path,) = [n for n in archive.files if re.fullmatch(rf"[^/]+\.dist-info/(?:licenses/)?{re.escape(name)}", n)]
    return path


def text_of(data: bytes) -> str | None:
    """The bytes as UTF-8 text, or ``None`` for a file that is not text."""
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------- running the command as a user does ----------


def masked(text: str, values: Iterable[str]) -> str:
    """``text`` with the values the test itself typed taken out where they stand as words of their
    own (section 9.3: a match inside the user's own data is not a failure)."""
    for value in sorted({v for v in values if len(v) >= 2}, key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])", "<data>", text)
    return text


def typed(*values: object) -> list[str]:
    """Each value, and each piece of it split at the separators a command line uses, with folders
    in both their spellings (``/var`` and ``/private/var`` on macOS)."""
    out: list[str] = []
    for value in values:
        s = str(value)
        out += [s, *re.split(r"[=:,\s]", s)]
        if isinstance(value, Path):
            out.append(str(value.resolve()))
    return out


def prove(argv: list[str], home: Path, cwd: Path, **extra: str) -> PF1.Result:
    return PF1.prove(argv, home=home, cwd=cwd, **extra)


QUICKSTART_STEPS = (
    ("init", ["init", "--example"]),
    ("sweep", ["sweep", "--yes"]),
    ("sweep-paired", ["sweep", "--target", f"{MOCK}:rollout_patched", "--pair-with", "latest", "--yes"]),
    ("diff", ["diff"]),
    ("check", ["check", "--event", "violated"]),
    ("report", ["report", "--x", "task_id", "--y", "tool_fail_rate"]),
    ("runs", ["runs"]),
)


def build_quickstart(folder: Path) -> None:
    cwd, home = folder / "cwd", folder / "home"
    cwd.mkdir()
    home.mkdir()
    for name, argv in QUICKSTART_STEPS:
        r = prove(argv, home, cwd)
        assert r.code in (0, 4), (name, r.code, r.err[-600:])
        (folder / f"{name}.out").write_text(r.out + "\n" + r.err, encoding="utf-8")


def quickstart_copy(tmp_path_factory: pytest.TempPathFactory, into: Path) -> tuple[Path, Path]:
    """A copy of the shared quickstart folder, for a part that writes into its store, and the
    shared folder the outputs were written in."""
    shared = once(tmp_path_factory, "quickstart", build_quickstart)
    shutil.copytree(shared, into, symlinks=True)
    return into, shared


def runs_named(cwd: Path) -> list[str]:
    """The run ids and names in the quickstart's store, which a rendered page shows as data."""
    out = []
    for manifest in (cwd / "prove-runs").glob("*/manifest.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        out += [data["run_id"], *([data["name"]] if data.get("name") else [])]
    return out


def serve_page(cwd: Path, home: Path) -> tuple[str, str]:
    """``serve``'s output and the page it serves, read over loopback, then Ctrl-C."""
    argv = [sys.executable, "-m", "poisson_prove", "serve", "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate"]
    proc = subprocess.Popen(argv, cwd=cwd, env=PF1.child_env(home), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, preexec_fn=PF1.default_sigint)
    assert proc.stdout is not None and proc.stderr is not None
    said, url = b"", None
    try:
        deadline = time.monotonic() + 60
        while url is None and time.monotonic() < deadline and proc.poll() is None:
            ready, _, _ = select.select([proc.stdout], [], [], 0.2)
            if ready:
                said += os.read(proc.stdout.fileno(), 65536)
                url = re.search(r"http://127\.0\.0\.1:[0-9]+/", said.decode("utf-8", "replace"))
        assert url, (said[-600:], proc.poll())
        with urllib.request.urlopen(url.group(0), timeout=30) as response:
            page = response.read().decode("utf-8")
    finally:
        proc.send_signal(signal.SIGINT)
        rest, err = proc.communicate(timeout=30)
    return (said + rest).decode("utf-8", "replace") + err.decode("utf-8", "replace"), page


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")


def app_home_screen(cwd: Path, home: Path, waits_for: Iterable[str]) -> tuple[int | None, str]:
    """The terminal app opened with no arguments on a 120 x 40 pseudo-terminal, read until one of
    ``waits_for`` is on the screen (or 60 s), then ``q``: the exit code and the screen's text
    without escapes."""
    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    env = {k: v for k, v in PF1.child_env(home).items() if k not in ("CI", "COLUMNS", "LINES")}
    env["TERM"] = "xterm-256color"
    proc = subprocess.Popen([sys.executable, "-m", "poisson_prove"], cwd=cwd, env=env, stdin=slave, stdout=slave,
                            stderr=slave, start_new_session=True, preexec_fn=PF1.default_sigint)
    os.close(slave)
    chunks: list[bytes] = []
    wanted = [w for w in waits_for if w]

    def screen() -> str:
        return ANSI.sub("", b"".join(chunks).decode("utf-8", "replace"))

    def read(until: Callable[[], bool], limit: float) -> None:
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline and not until():
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    return
                if not data:
                    return
                chunks.append(data)
            elif proc.poll() is not None:
                return

    try:
        read(lambda: any(w in screen() for w in wanted), 60)
        if proc.poll() is None:
            os.write(master, b"q")
            read(lambda: proc.poll() is not None, 10)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    finally:
        os.close(master)
    return proc.returncode, screen()


# ---------- the corpus, one part at a time ----------


def docstring_lines(text: str) -> set[int]:
    """The first line of every docstring in a Python file."""
    lines = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines.add(first.lineno)
    return lines


def source_hits(part: str, name: str, text: str, terms: Iterable[str] | None = None, *, identifiers: bool = False,
                prose_only: Iterable[str] = ()) -> list[Hit]:
    """A Python file's string literals, docstrings and comments; with ``identifiers``, its names
    too, split at underscores and read for codes only (r3); ``prose_only`` terms count in its
    docstrings and comments only."""
    hits = []
    labels = list(terms if terms is not None else TERMS)
    docs = docstring_lines(text) if prose_only else set()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        kind = tokenize.tok_name[tok.type]
        if kind in ("STRING", "COMMENT", "FSTRING_MIDDLE"):
            data = kind != "COMMENT" and tok.start[0] not in docs
            chosen = [label for label in labels if not (data and label in prose_only)]
            for hit in scan(part, name, tok.string, chosen):
                hits.append(Hit(part, name, tok.start[0] + hit.line_no - 1, hit.term, hit.text, hit.line, hit.start))
        elif kind == "NAME" and identifiers:
            for hit in scan(part, name, tok.string.replace("_", " "), ID):
                hits.append(Hit(part, name, tok.start[0], hit.term, hit.text, tok.string, hit.start))
    return hits


def package_hits(archives: dict[str, Archive]) -> list[Hit]:
    """Every member of the wheel (r3): a module's strings, docstrings, comments and identifiers;
    any other file whole. The licence files are PF8.3's (r4); ``RECORD`` and ``WHEEL`` are written
    by the build tool and hold hashes and its name."""
    hits: list[Hit] = []
    for name, data in sorted(archives["wheel"].files.items()):
        if re.search(r"\.dist-info/(?:RECORD|WHEEL|licenses/.*)$", name):
            continue
        text = text_of(data)
        assert text is not None or not name.endswith(".py"), name
        if text is None:
            continue
        hits += source_hits("package", name, text, identifiers=True) if name.endswith(".py") else scan("package", name, readable(name, text))
    return hits


def verbs_of(help_text: str) -> list[str]:
    """The verbs the top-level help lists, one to a line, indented under its list of verbs."""
    return re.findall(r"(?m)^ {4}([a-z][a-z-]*)(?: {2,}| *$)", help_text)


def help_hits(tmp_path: Path) -> list[Hit]:
    home = tmp_path / "home"
    home.mkdir()
    top = prove(["--help"], home, tmp_path)
    assert top.code == 0, top.err
    verbs = verbs_of(top.out)
    assert "sweep" in verbs and len(verbs) >= 9, verbs
    calls = {"--help": top, "--version": prove(["--version"], home, tmp_path)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for verb, r in zip(verbs, pool.map(lambda v: prove([v, "--help"], home, tmp_path), verbs)):
            calls[f"{verb} --help"] = r
    hits = []
    for name, r in calls.items():
        assert r.code == 0, (name, r.err)
        hits += scan("help", name, masked(r.out + "\n" + r.err, typed(tmp_path, home)))
    return hits


def holds_old_run(path: Path) -> bool:
    """Whether ``path`` holds a run the private builds wrote, at most two folders down."""
    if not path.is_dir():
        return False
    return any('"proofload_version"' in m.read_text(encoding="utf-8", errors="replace")
               for pattern in ("*/manifest.json", "*/*/manifest.json") for m in path.glob(pattern))


def conformance_hits(tmp_path_factory: pytest.TempPathFactory) -> list[Hit]:
    """Section 10.2's conformance corpus: PF1's invocations, run here once more."""
    world = PF1.world.__wrapped__(tmp_path_factory)
    corpus = PF1.corpus.__wrapped__(world)
    # the world's own data: every quoted value of the files it wrote, and the runs in its stores
    own = [v for spec in world.base.glob("*.toml") for v in re.findall(r'"([^"]+)"', spec.read_text(encoding="utf-8"))]
    own += [run.name for store in (world.store, world.paired_store) for run in store.iterdir() if run.is_dir()]
    hits = []
    for name, ran in corpus.items():
        cwd = world.folders[ran.call.cwd] if ran.call.cwd else world.base
        old = holds_old_run(cwd) or any(holds_old_run(Path(w)) for w in ran.argv if w.startswith("/"))
        place = f"old-data:{name}" if old else name
        values = [*typed(world.base, world.home, world.store, world.paired_store, *world.folders.values(), *ran.argv, world.a, world.b), *own]
        hits += scan("conformance", place, masked(ran.out + "\n" + ran.err, values))
    return hits


def quickstart_hits(tmp_path_factory: pytest.TempPathFactory, tmp_path: Path) -> list[Hit]:
    """Section 4.1's path: every command's output, every file it wrote outside the store, and the
    page ``serve`` serves."""
    folder, shared = quickstart_copy(tmp_path_factory, tmp_path / "qs")
    cwd, home = folder / "cwd", folder / "home"
    values = typed(folder, cwd, home, shared, shared / "cwd", shared / "home", *runs_named(cwd))
    hits = []
    for out in sorted(folder.glob("*.out")):
        hits += scan("quickstart", out.stem, masked(out.read_text(encoding="utf-8"), values))
    written = [p for p in cwd.rglob("*") if p.is_file() and "prove-runs" not in p.relative_to(cwd).parts]
    assert any(p.name == "report.md" for p in written) and any(p.name == "receipt.html" for p in written), written
    for path in written:
        text = text_of(path.read_bytes())
        if text is not None:
            hits += scan("quickstart", str(path.relative_to(cwd)), masked(readable(path.name, text), values))
    said, page = serve_page(cwd, home)
    hits += scan("quickstart", "serve", masked(said, values))
    hits += scan("quickstart", "serve page", masked(readable("page", page), values))
    return hits


def static_ui_hits(tmp_path_factory: pytest.TempPathFactory, tmp_path: Path) -> list[Hit]:
    """Every file ``poisson-prove ui`` leaves under the quickstart store's ``.poisson/`` (r7)."""
    folder, shared = quickstart_copy(tmp_path_factory, tmp_path / "qs")
    cwd, home = folder / "cwd", folder / "home"
    r = prove(["ui"], home, cwd)
    assert r.code == 0, f"the static UI could not be built, so its pages cannot be read: exit {r.code}: {r.err[-400:]}"
    values = typed(folder, cwd, home, cwd / "prove-runs", shared, *runs_named(cwd))
    hits = scan("static-ui", "ui", masked(r.out + "\n" + r.err, values))
    pages = [p for p in (cwd / "prove-runs" / ".poisson").rglob("*") if p.is_file()]
    assert any(p.suffix == ".html" for p in pages), pages
    for path in pages:
        text = text_of(path.read_bytes())
        if text is not None:
            hits += scan("static-ui", str(path.relative_to(cwd)), masked(readable(path.name, text), values))
    return hits


def setup_skill_hits(tmp_path: Path) -> list[Hit]:
    """What ``init --agent --print`` prints and every file ``init --agent`` writes (r7)."""
    home, repo = tmp_path / "home", tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    printed = prove(["init", "--agent", "--print"], home, repo)
    assert printed.code == 0, f"init --agent --print could not run, so the skill cannot be read: exit {printed.code}: {printed.err[-400:]}"
    wrote = prove(["init", "--agent"], home, repo)
    assert wrote.code == 0, f"init --agent could not run: exit {wrote.code}: {wrote.err[-400:]}"
    values = typed(tmp_path, home, repo)
    hits = scan("setup-skill", "init --agent --print", masked(printed.out + "\n" + printed.err, values))
    hits += scan("setup-skill", "init --agent", masked(wrote.out + "\n" + wrote.err, values))
    files = [p for p in repo.rglob("*") if p.is_file()]
    assert files, "init --agent wrote nothing"
    for path in files:
        text = text_of(path.read_bytes())
        if text is not None:
            hits += scan("setup-skill", str(path.relative_to(repo)), masked(text, values))
    return hits


def terminal_app_hits(tmp_path_factory: pytest.TempPathFactory, archives: dict[str, Archive]) -> list[Hit]:
    """The app's home screen over the quickstart pair, and every snapshot of its screens (r7). The
    pair is copied into a short folder of its own, so no path on the screen is wrapped or cut."""
    short = Path(tempfile.mkdtemp(prefix="pf8-app-", dir="/tmp"))
    try:
        folder, shared = quickstart_copy(tmp_path_factory, short / "qs")
        cwd, home = folder / "cwd", folder / "home"
        names = runs_named(cwd)
        code, screen = app_home_screen(cwd, home, names)
        assert code == 0 and any(n in screen for n in names), f"the terminal app did not open on the store and quit with q, so its screens cannot be read: exit {code}: {screen[-400:]!r}"
        hits = scan("terminal-app", "home screen", masked(screen, typed(short, folder, cwd, home, shared, *names)))
    finally:
        shutil.rmtree(short, ignore_errors=True)
    snapshots = [name for name in sorted(archives["sdist"].files) if name.startswith("tests/") and "/__snapshots__/" in name]
    assert snapshots, "no snapshot of the app's screens ships (PF6.14), so its other screens cannot be read"
    for name in snapshots:
        text = text_of(archives["sdist"].files[name])
        if text is not None:
            hits += scan("terminal-app", name, readable(name, text))
    return hits


def docs_hits(archives: dict[str, Archive]) -> list[Hit]:
    """Every text file of the tree and the sdist outside ``src/`` and ``tests/`` but LICENSE,
    NOTICE and the two standards (r4)."""
    hits = []
    files = {**archives["sdist"].files, **archives["tree"].files}
    assert "README.md" in files and "CHANGELOG.md" in files and any(n.startswith("docs/") for n in files), sorted(files)[:20]
    for name in sorted(files):
        if name.startswith(("src/", "tests/")) or name in ("LICENSE", "NOTICE", *STANDARDS):
            continue
        text = text_of(files[name])
        if text is not None:
            hits += scan("docs", name, readable(name, text))
    return hits


def q38_hits(archives: dict[str, Archive]) -> list[Hit]:
    """Q38 over the sdist's ``tests/`` (r5), a test module read as ``src/`` is (its strings,
    docstrings and comments); this file's lines between its two pattern markers are left out."""
    hits = []
    for name, data in sorted(archives["sdist"].files.items()):
        if not name.startswith("tests/"):
            continue
        text = text_of(data)
        if text is None:
            continue
        found = source_hits("tests", name, text, TESTS_TERMS, prose_only=PROSE_ONLY_TERMS) if name.endswith(".py") else scan("tests", name, readable(name, text), TESTS_TERMS)
        if name == THIS_FILE:
            lines = text.splitlines()
            begin = next(i for i, line in enumerate(lines, 1) if line.startswith("# plain-words: the patterns begin"))
            end = next(i for i, line in enumerate(lines, 1) if line.startswith("# plain-words: the patterns end"))
            found = [hit for hit in found if not begin <= hit.line_no <= end]
        hits += found
    return hits


PARTS = ("package", "help", "conformance", "quickstart", "static-ui", "setup-skill", "terminal-app", "docs", "tests")


# ---------- PF8.1 ----------


@pytest.mark.parametrize("kind", ["tree", "sdist", "wheel"])
def test_pf8_1_no_file_section_9_1_removes_ships(kind: str, archives: dict[str, Archive]) -> None:
    present = {path: archives[kind].has(path) for path in REMOVED}
    assert not {p: found[:5] for p, found in present.items() if found}


def test_pf8_1_contributing_md_carries_the_three_rules(archives: dict[str, Archive]) -> None:
    assert "CONTRIBUTING.md" in archives["sdist"].files
    text = " ".join(archives["sdist"].text("CONTRIBUTING.md").split())
    assert re.search(r"(?i)\bnetwork\b", text) and re.search(r"(?i)\bcore\b", text), "the core imports no network library"
    assert re.search(r"(?i)\bfrozen\b", text), "frozen tests are not edited"
    assert re.search(r"(?i)conventional commits|conventionalcommits\.org", text), "commits are Conventional Commits"


# ---------- PF8.2 ----------


@pytest.mark.parametrize("kind", ["tree", "sdist"])
def test_pf8_2_gitignore_lists_devlog_md_and_no_notes(kind: str, archives: dict[str, Archive]) -> None:
    entries = {line.strip() for line in archives[kind].text(".gitignore").splitlines() if line.strip() and not line.lstrip().startswith("#")}
    assert entries & {"devlog.md", "/devlog.md"}, sorted(entries)
    assert not entries & NOTES_ENTRIES, sorted(entries)


# ---------- PF8.3 ----------


@pytest.mark.parametrize("kind", ["tree", "sdist", "wheel"])
def test_pf8_3_license_is_mit_with_the_copyright_line(kind: str, archives: dict[str, Archive]) -> None:
    path = dist_info(archives[kind], "LICENSE") if kind == "wheel" else "LICENSE"
    lines = [line.strip() for line in archives[kind].text(path).splitlines() if line.strip()]
    assert lines[:2] == ["MIT License", COPYRIGHT], lines[:2]
    assert " ".join(" ".join(lines[2:]).split()) == MIT_BODY


@pytest.mark.parametrize("kind", ["tree", "sdist", "wheel"])
def test_pf8_3_notice_names_every_third_party_item_that_ships(kind: str, archives: dict[str, Archive]) -> None:
    path = dist_info(archives[kind], "NOTICE") if kind == "wheel" else "NOTICE"
    text = archives[kind].text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert lines[0] == "Poisson Prove", lines[0]
    assert COPYRIGHT in lines, lines[:4]
    shipped = [item for item in THIRD_PARTY if any(archives["sdist"].has(p) for p in item.carried_by)]
    assert any(item.name == "AgentChaos" for item in shipped)
    sections = [" ".join(s.split()) for s in re.split(r"(?m)^\s*-{10,}\s*$", text)]
    missing = [item.name for item in shipped if not any(all(re.search(p, s) for p in item.must_say) for s in sections)]
    assert not missing, missing


# ---------- PF8.4 ----------


@pytest.mark.parametrize("family", FAMILIES, ids=lambda f: f.name)
def test_pf8_4_each_family_catches_its_terms_and_passes_ordinary_words(family: Family) -> None:
    labels = [t.label for t in family.terms]
    for t in family.terms:
        for case in t.catches:
            assert failures(scan("case", t.label, case, (t.label,))), (t.label, case)
    assert not [h for case in family.passes for h in scan("case", "ordinary", case, labels)]
    for a in ALLOWED:
        assert set(a.terms) <= set(TERMS) and a.reason, a
        if not set(a.terms) & set(labels):
            continue
        (part, place, line), (r_part, r_place, r_line) = a.allows, a.refuses
        terms = [label for label in a.terms]
        assert scan(part, place, line, terms) and not failures(scan(part, place, line, terms)), (a.reason, "allows", line)
        assert failures(scan(r_part, r_place, r_line, terms)), (a.reason, "refuses", r_line)


@pytest.mark.parametrize("part", PARTS)
def test_pf8_4_the_plain_words_test_passes_over_its_whole_corpus(part: str, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    factory = request.getfixturevalue("tmp_path_factory")
    if part in ("package", "docs", "tests", "terminal-app"):
        archives = request.getfixturevalue("archives")
    hits = {
        "package": lambda: package_hits(archives),
        "help": lambda: help_hits(tmp_path),
        "conformance": lambda: conformance_hits(factory),
        "quickstart": lambda: quickstart_hits(factory, tmp_path),
        "static-ui": lambda: static_ui_hits(factory, tmp_path),
        "setup-skill": lambda: setup_skill_hits(tmp_path),
        "terminal-app": lambda: terminal_app_hits(factory, archives),
        "docs": lambda: docs_hits(archives),
        "tests": lambda: q38_hits(archives),
    }[part]()
    failed = failures(hits)
    by_term: dict[str, int] = {}
    for hit in failed:
        by_term[hit.term] = by_term.get(hit.term, 0) + 1
    assert not failed, f"{len(failed)} matches by term {by_term}:\n" + "\n".join(str(h) for h in failed[:80])


# ---------- PF8.5 ----------


def test_pf8_5_no_test_names_a_place_outside_the_repository(archives: dict[str, Archive]) -> None:
    found = []
    for name, data in sorted(archives["sdist"].files.items()):
        if name.startswith("tests/") and name.endswith(".py") and name != THIS_FILE:
            text = data.decode("utf-8")
            found += [f"{name}:{no}: {line.strip()[:140]}" for no, line in enumerate(text.splitlines(), 1) if OUTSIDE.search(line) and not OUTSIDE_ALLOWED.search(line)]
    assert not found, "\n".join(found)


def importlib_has(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


@pytest.mark.slow
def test_pf8_5_with_home_empty_no_skip_names_a_place(tmp_path: Path) -> None:
    """The suite, run once with ``HOME`` at an empty folder (so no code folder under it) and no store
    variable, reports no skip whose reason names a place. Real-backend tests are left out (a paid
    call), and so is this test. Package caches are kept: a cache is not data a test reads."""
    home = tmp_path / "home"
    home.mkdir()
    junit = tmp_path / "suite.xml"
    keep = {k: os.environ[k] for k in ("UV_CACHE_DIR", "PIP_CACHE_DIR") if k in os.environ}
    uv = shutil.which("uv")
    if uv and "UV_CACHE_DIR" not in keep:
        keep["UV_CACHE_DIR"] = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True, timeout=60).stdout.strip()
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONDONTWRITEBYTECODE")
    env = {k: v for k, v in os.environ.items() if k not in drop and not k.startswith("PYTEST_")}
    env.update(keep, HOME=str(home), PATH=os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")]))
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not backend", "-rs",
            "--deselect", f"{THIS_FILE}::test_pf8_5_with_home_empty_no_skip_names_a_place", f"--junitxml={junit}"]
    if importlib_has("xdist"):
        argv += ["-n", "auto"]
    done = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=3600, preexec_fn=PF1.default_sigint)
    assert junit.is_file(), done.stdout[-2000:] + done.stderr[-2000:]
    root = ET.parse(junit).getroot()
    assert sum(1 for _ in root.iter("testcase")) > 1000, done.stdout[-2000:]
    skips = []
    for case in root.iter("testcase"):
        skipped = case.find("skipped")
        if skipped is not None and SKIP_NAMES_A_PLACE.search(skipped.get("message") or ""):
            skips.append(f"{case.get('classname')}::{case.get('name')}: {(skipped.get('message') or '')[:200]}")
    assert not skips, "\n".join(skips)


# ---------- PF8.6 ----------

RELEASE_HEADING = re.compile(r"^## ([0-9]+\.[0-9]+\.[0-9]+) — ([0-9]{4}-[0-9]{2}-[0-9]{2}|Unreleased)$")


def test_pf8_6_the_changelog_has_section_9_4s_form(archives: dict[str, Archive], tmp_path: Path) -> None:
    lines = archives["sdist"].text("CHANGELOG.md").splitlines()
    assert lines[0] == "# Changelog", lines[:1]
    headings = [(no, line) for no, line in enumerate(lines) if line.startswith("## ")]
    assert headings and all(RELEASE_HEADING.match(line) for _, line in headings), [line for _, line in headings]
    oldest_no, oldest = headings[-1]
    first_release = RELEASE_HEADING.match(oldest)
    assert first_release and first_release.group(1) == "0.1.0", oldest
    section = lines[oldest_no + 1:]
    home = tmp_path / "home"
    home.mkdir()
    verbs = verbs_of(prove(["--help"], home, tmp_path).out)
    assert verbs
    bullets = [line for line in section if re.match(r"\s*[-*] ", line)]
    named = {verb for verb in verbs if any(re.search(rf"`[^`]*\b{re.escape(verb)}\b[^`]*`", line) for line in bullets)}
    assert named == set(verbs), sorted(set(verbs) - named)
    old = [no for no, line in enumerate(lines) if re.search(r"(?i)proofload", line)]
    assert len(old) == 1, [lines[no] for no in old]
    (at,) = old
    above = next((lines[no] for no in range(at - 1, -1, -1) if lines[no].startswith("#")), "")
    assert "Renamed" in lines[at] or "Renamed" in above, (above, lines[at])


# ---------- PF8.7 ----------


@pytest.mark.parametrize("kind", ["tree", "sdist"])
def test_pf8_7_repo_hygiene_md_equals_the_canonical_copy(kind: str, archives: dict[str, Archive]) -> None:
    data = archives[kind].files.get("docs/repo-hygiene.md")
    assert data is not None, "docs/repo-hygiene.md is missing"
    assert hashlib.sha256(data).hexdigest() == REPO_HYGIENE_SHA256
