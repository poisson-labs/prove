"""C10 of 0.3.0, Remote backends: the docs.

The frozen tests for D1 to D3 (Remote Backends Spec §16.3, §10.2, §2.6 and §15 C10; RB-8, RB-9),
with N8's name scan over ``README.md`` and ``docs/`` (given to this pair by Pair 2's yes/no 14),
and one sentence of ``CONTRIBUTING.md`` (Pair 1's yes/no 5).

**What is pinned is facts, never prose**, as the docs tests before these: a page is checked for
what it names (a flag, a key, a line Prove prints, a number), read from the code where the code
has it. The pages themselves are also read by the docs check and the link check of
``test_pf7_docs.py``, which find a page by its being there; this file adds what 0.3.0 changes.

- **D1, every page of §16.3 carries its change** (``CHANGED``, one entry per page and fact), every
  block that needs an account is marked ``skip`` with a reason that names the account, and every
  output a page quotes from a cloud sweep is the plain rendering: each such block's commands are
  run here on the cloud fakes, in the page's order, and compared by the docs check's own rule
  (the verdict word and the line labels, ``next:`` lines whole).
- **D2, the data-flow section** (``### What leaves this machine``, under the backends page's
  cloud section) says §10.2's six facts, each in a sentence of its own, and no page claims more: nothing on any page says that
  nothing leaves the reader's cloud, that the relay cannot see the traffic, or names a private
  mode this release does not run.
- **D3, the name scan.** No line of the README, of a page under ``docs/`` or of the setup skill
  names the cluster software, but for the places in ``ALLOWED``, each with its reason.
- **The botocore floor and the nightly's lanes, as built** (the nightly fix, ruled 2026-11-11):
  every page that gives ``botocore[crt]`` a version gives ``pyproject.toml``'s, and
  ``CONTRIBUTING.md`` names each job the nightly workflow runs tests in.
- **CONTRIBUTING's sentence:** a test lane started as a background shell job ignores SIGINT, so
  the interrupt tests go falsely red; run lanes in the foreground.

**Choices this file fixes** (each a yes/no of this session):

- The data-flow section is a ``###`` heading under ``## Your cloud account``, since the section
  that names who carries the reader's code belongs with the backend it is true of, and the
  backends page's own frozen test reads that section for it.
- The scan allows the three things a reader of 0.2 typed (``[burla]``, ``--backend burla``, the
  ``poisson-prove[burla]`` extra) wherever a page says they moved, and nothing else outside the
  data-flow section and the artifact format's two fields.
- ``CONTRIBUTING.md`` is not scanned: it is for the people who build Prove, who meet the software
  by name in ``pyproject.toml`` and the fakes.
- The CHANGELOG's 0.3.0 entry is written in this pair under ``## 0.3.0 — Unreleased``; the release
  session dates it.
"""

from __future__ import annotations

import io
import re
import shlex
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

import pf7_docs_check as check
from poisson_prove import cli
from rb_cloud_support import MASKED, TABLE_REGIONS, TYPES, CloudWorld, Pool, world
from test_rb_where import ALL_FLAGS, CLOUD_PROMPTS, QUESTION, READY
from test_rb_where_app import FIRST_RUN_LINE

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = "docs/backends.md"
SKILL = "src/poisson_prove/skills/poisson-prove-setup/SKILL.md"
DATA_FLOW = "What leaves this machine"
TRAFFIC = ("your code, its inputs and its results go between this machine and the nodes through Burla's relay "
           "(the cluster software Prove uses); the store stays on this machine")
WHERE_FLAGS = ("--cloud", "--region", "--machine-type", "--nodes", "--max-vcpus", "--stop-cost", "--max-cost", "--yes")
CLOUD_MODULES = ("executor_cloud", "_cloud_submit", "_cloud_head", "_cloud_record", "_prices_cloud",
                 "_where_checks", "_where")


def text_of(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"{rel} does not exist"
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


def section(text: str, heading: str, level: int = 2) -> str:
    """The body under the heading whose text is ``heading`` (or holds it), down to the next
    heading of that level or above."""
    marks = "#" * level
    found = re.search(rf"(?m)^{marks} [^\n]*{re.escape(heading)}[^\n]*\n", text)
    assert found, f"no {marks} heading holding {heading!r}"
    rest = text[found.end():]
    end = re.search(rf"(?m)^#{{1,{level}}} ", rest)
    return rest[: end.start()] if end else rest


def code_spans(text: str) -> set[str]:
    return set(re.findall(r"`([^`\n]+)`", text))


def blocks_text(rel: str) -> str:
    return "\n".join(b.text for b in check.read_page(rel).blocks)


def cloud_section() -> str:
    return section(text_of(BACKENDS), "Your cloud account")


def data_flow() -> str:
    return section(cloud_section(), DATA_FLOW, level=3)


# ---------- D1: every page of §16.3 carries its change ----------


def _backends_opening() -> list[str]:
    text = text_of(BACKENDS)
    opening = text.split("\n## ", 1)[0]
    missing = [w for w in ("this machine", "Modal", "your cloud account") if w not in opening]
    missing += [f"`{w}`" for w in ("local", "modal", "cloud") if w not in code_spans(opening)]
    if re.search(r"(?i)experimental", text):
        missing.append("the page still calls a backend experimental")
    if "poisson-prove where" not in text:
        missing.append("`poisson-prove where`, how the choice is made")
    return missing


def _backends_starts_and_stops() -> list[str]:
    body = flat(cloud_section())
    missing = []
    if not re.search(r"\bstarts?\b[^.]*\b(nodes|cluster)\b", body) or not re.search(r"\bstops?\b[^.]*\b(nodes|cluster|them|it)\b", body):
        missing.append("that Prove starts the nodes and stops them")
    for ending, pattern in (("done", r"\b(finish|done|complet)"), ("failed", r"\bfail"), ("stopped early", r"\bearly\b"),
                            ("interrupted", r"\b(interrupt|Ctrl-C)")):
        if not re.search(pattern, body):
            missing.append(f"the ending {ending!r}")
    if not re.search(r"\bcoordinator\b|\bcluster software\b", body):
        missing.append("that Prove runs the cluster software on this machine")
    if "does not change or stop" not in body and "did not start" not in body:
        missing.append("that Prove leaves alone what it did not start")
    return missing


def _backends_bounds() -> list[str]:
    body = flat(cloud_section())
    missing = []
    if not re.search(r"`idle_minutes`[^.]{0,80}\b5\b|\b5\b[^.]{0,80}`idle_minutes`", body):
        missing.append("the nodes' own idle stop, `idle_minutes`, 5 by default")
    if not re.search(r"\b(3|three) min", body):
        missing.append("the three-minute bound when the coordinator is gone too")
    if not re.search(r"next (cloud )?sweep", body) or "ledger" not in body:
        missing.append("that the next cloud sweep finds what was left and closes its ledger line")
    if not re.search(r"\bidle sleep\b|\bkept (awake|from)", body):
        missing.append("that this machine is kept from idle sleep while the nodes run")
    return missing


def _backends_modal_sign_in() -> list[str]:
    body = section(text_of(BACKENDS), "Modal")
    missing = [w for w in ("modal setup", "error: this machine is not signed in to Modal") if w not in body]
    return missing


def _sweep_spec() -> list[str]:
    from poisson_prove import _prices_cloud

    text = text_of("docs/sweep-spec.md")
    body = section(text, "[cloud]")
    missing = [f"the region {r}" for r in TABLE_REGIONS if r not in body]
    missing += [f"the machine type {t}" for t in TYPES if t not in body]
    dates = sorted({row.asof for row in _prices_cloud.rows("aws").values()})
    missing += [f"the price table's date {d}" for d in dates if d not in body]
    if not re.search(r"(?i)price list", body):
        missing.append("where the prices were read, AWS's price list")
    missing += [w for w in ("[burla]", "poisson-prove where cloud", "head_url") if w not in body]
    return missing


def _sweep_page() -> list[str]:
    text = text_of("docs/commands/sweep.md")
    body = flat(text)
    missing = []
    if "--backend {local,modal,cloud}" not in body:
        missing.append("--backend {local,modal,cloud}")
    if "poisson-prove where" not in text:
        missing.append("that the spec says where it runs when no --backend is given (`poisson-prove where`)")
    if not re.search(r"first batch", body) or "no outcome" not in body:
        missing.append("the early stop: every rollout of the first batch with no outcome")
    exits = flat(section(text, "Exit codes"))
    for word in ("130", "Ctrl-C", "SIGTERM", "SIGHUP", "pipe"):
        if word not in exits:
            missing.append(f"{word} among the exit codes")
    shown = blocks_text("docs/commands/sweep.md")
    for label in ("starting  ", "ready  ", "stopping  the cluster", "stopped  ", "  cluster  "):
        if not re.search(rf"(?m)^{re.escape(label)}", shown):
            missing.append(f"the cluster's line {label.strip()!r} in a shown block")
    return missing


def _init_page() -> list[str]:
    text = text_of("docs/commands/init.md")
    shown = blocks_text("docs/commands/init.md")
    missing = []
    if "--runs-on" not in code_spans(section(text, "Options")) and not any(s.startswith("--runs-on") for s in code_spans(section(text, "Options"))):
        missing.append("`--runs-on` among the options")
    if QUESTION not in shown:
        missing.append("the question, as a terminal shows it")
    missing += [f"the prompt {p!r}" for p in CLOUD_PROMPTS if p not in shown]
    if re.search(r"(?i)asks no question|nothing is asked", text.split("\n## Help", 1)[0]):
        missing.append("the page still opens by saying init asks nothing")
    if "terminal" not in flat(text.split("\n## Help", 1)[0]):
        missing.append("when the question is asked: in a terminal")
    return missing


def _where_page() -> list[str]:
    rel = "docs/commands/where.md"
    if not (ROOT / rel).is_file():
        return [f"{rel} does not exist"]
    text = text_of(rel)
    spans = code_spans(text)
    missing = [f"`{flag}`" for flag in WHERE_FLAGS if not any(s.split()[0] == flag for s in spans if s.split())]
    shown = blocks_text(rel)
    if READY not in shown:
        missing.append("the line a ready cloud account prints")
    for heading in ("Help", "Options", "Examples", "Exit codes", "What it writes"):
        if not re.search(rf"(?m)^## {heading}\s*$", text):
            missing.append(f"the section {heading}")
    for word in ("local", "modal", "cloud"):
        if not re.search(rf"poisson-prove where {word}\b", text):
            missing.append(f"poisson-prove where {word}")
    if "[burla]" not in text:
        missing.append("that it rewrites a 0.2 spec's [burla] table")
    return missing


def _terminal_app() -> list[str]:
    text = text_of("docs/terminal-app.md")
    missing = []
    if "w" not in code_spans(section(text, "The keys")):
        missing.append("the key `w` among the keys")
    if "Where sweeps run" not in text:
        missing.append("the page, Where sweeps run")
    if FIRST_RUN_LINE not in blocks_text("docs/terminal-app.md"):
        missing.append("the first-run screen's where line, as the screen shows it")
    return missing


def _artifact_format() -> list[str]:
    text = text_of("docs/artifact-format.md")
    body = flat(text)
    missing = [f"`{w}`" for w in ("produced_by", "stopped_by", "environment.cloud", "engine") if w not in code_spans(text)]
    if '"first_batch_errored"' not in text:
        missing.append('stopped_by = "first_batch_errored"')
    if '`"cloud"`' not in text:
        missing.append('the backend value "cloud"')
    if not re.search(r'`"burla"`[^.]*\bcloud\b|\bcloud\b[^.]*`"burla"`', body):
        missing.append('that a stored "burla" backend is read as cloud')
    engine = [line for line in text.splitlines() if "engine" in line]
    if not any("name" in line and "version" in line for line in engine):
        missing.append("the engine's name and version")
    return missing


def _setup_page_and_skill() -> list[str]:
    page, skill = text_of("docs/setup-with-your-agent.md"), text_of(SKILL)
    missing = []
    if "poisson-prove where" not in page and "--runs-on" not in page:
        missing.append("the page: where it runs is asked by init or set with `poisson-prove where`")
    for word in ("--backend", "--runs-on", "[modal]", "[cloud]"):
        if word in skill:
            missing.append(f"the skill names {word}: where it runs is not the skill's to ask or set")
    if "poisson-prove where" not in skill:
        missing.append("the skill: that where sweeps run is the person's choice, with `poisson-prove where`")
    return missing


def _python_page() -> list[str]:
    text = text_of("docs/python.md")
    spans = code_spans(text)
    missing = [f"`{m}`" for m in CLOUD_MODULES if m not in spans]
    missing += [f"the old name {m}" for m in ("executor_burla", "_burla_submit") if m in text]
    return missing


def _architecture() -> list[str]:
    text = flat(text_of("docs/architecture.md"))
    return [] if re.search(r"Modal, your cloud account", text) else ["\"Modal, your cloud account\" among the executors"]


def _quickstart() -> list[str]:
    text = text_of("docs/quickstart.md")
    example = section(text, "The example")
    at = example.find("poisson-prove where")
    if at < 0:
        return ["a line naming `poisson-prove where` in The example"]
    first_diff = example.find("poisson-prove diff")
    if first_diff < 0 or at < first_diff:
        return ["the where line comes after the first comparison"]
    line = next(line for line in flat(example[first_diff:]).split(". ") if "poisson-prove where" in line)
    return [] if "Modal" in line and re.search(r"\bcloud\b", line) else ["the where line names Modal and your cloud"]


def _readme() -> list[str]:
    body = section(text_of("README.md"), "Backends")
    missing = [w for w in ("--backend cloud", 'pip install "poisson-prove[cloud]"', "poisson-prove where",
                           'pip install "poisson-prove[modal]"') if w not in body]
    if re.search(r"(?i)experimental", body):
        missing.append("the section still says experimental")
    if "docs/backends.md#what-leaves-this-machine" not in body:
        missing.append("a link to the backends page's What leaves this machine")
    return missing


def _changelog() -> list[str]:
    text = text_of("CHANGELOG.md")
    found = re.search(r"(?m)^## 0\.3\.0 — (\S+)\s*$", text)
    if not found:
        return ["an entry headed ## 0.3.0 — Unreleased (or its date)"]
    assert found.group(1) == "Unreleased" or re.fullmatch(r"\d{4}-\d\d-\d\d", found.group(1)), found.group(1)
    assert text.index("## 0.3.0") < text.index("## 0.2.2"), "the entry is not the newest"
    entry = text[found.end():].split("\n## ", 1)[0]
    changed, added = section(entry, "Changed", level=3), section(entry, "Added", level=3)
    first = flat(changed).split("- ", 2)[1]
    missing = [f"the Changed list opens with what moved: {w}" for w in
               ("--backend cloud", "--backend burla", "[burla]", "poisson-prove where cloud",
                'pip install "poisson-prove[cloud]"', "0.4.0") if w not in first]
    missing += [f"Changed: {w}" for w in ("(#11)", "(#12)") if w not in changed]
    missing += [f"Added: {w}" for w in ("poisson-prove where", "init", "produced_by", "(#17)") if w not in added]
    return missing


CHANGED: dict[str, Callable[[], list[str]]] = {
    "backends.md: this machine, Modal, your cloud account": _backends_opening,
    "backends.md: what Prove starts and stops": _backends_starts_and_stops,
    "backends.md: the bounds when this machine stops first": _backends_bounds,
    "backends.md: Modal's sign-in line": _backends_modal_sign_in,
    "sweep-spec.md: [cloud], the price table, the refusal of [burla]": _sweep_spec,
    "commands/sweep.md: the backends, the early stop, interrupts, the cluster lines": _sweep_page,
    "commands/init.md: the question in a terminal, --runs-on": _init_page,
    "commands/where.md: new": _where_page,
    "terminal-app.md: the Where page, the first-run line": _terminal_app,
    "artifact-format.md: produced_by, first_batch_errored, cloud and the old burla": _artifact_format,
    "setup-with-your-agent.md and the setup skill": _setup_page_and_skill,
    "python.md: the private modules' names": _python_page,
    "architecture.md: Modal, your cloud account": _architecture,
    "quickstart.md: the where line": _quickstart,
    "README.md: the extras and the backends paragraph": _readme,
    "CHANGELOG.md: the 0.3.0 entry": _changelog,
}


@pytest.mark.parametrize("change", list(CHANGED))
def test_d1_each_page_carries_its_change(change: str) -> None:
    assert CHANGED[change]() == [], change


# ---------- D1: the blocks that need an account ----------

ACCOUNT_COMMANDS = (
    (re.compile(r"\baws (sso )?login\b|--backend cloud\b|--runs-on cloud\b|\bwhere cloud\b"), re.compile(r"(?i)\b(AWS|cloud) account\b"),
     "your AWS account"),
    (re.compile(r"--backend modal\b|\bmodal setup\b|--runs-on modal\b|\bwhere modal\b"), re.compile(r"(?i)\bModal\b"), "Modal"),
)


def test_d1_a_block_that_needs_an_account_is_skipped_with_a_reason_that_names_it() -> None:
    wrong = []
    for rel in check.corpus():
        for block in check.read_page(rel).blocks:
            if not (block.indented or block.lang in check.SHELL | {"console"}):
                continue
            for command, _ in check.commands(block):
                for needs, names, what in ACCOUNT_COMMANDS:
                    if not needs.search(command) or "--help" in command:
                        continue
                    if block.mark is None or block.mark.kind != "skip" or not names.search(block.mark.arg):
                        wrong.append(f"{rel}, line {block.line}: {command!r} needs {what}; its mark is "
                                     f"{block.mark.kind + ': ' + block.mark.arg if block.mark else None!r}")
    assert wrong == [], wrong


# ---------- D1: every output a page quotes from a cloud sweep is the plain rendering ----------

#: The pages of §16.3 that quote a cloud sweep's output, and what each must show at the least.
QUOTED = {
    BACKENDS: ("  Account:", "  Cluster:", "  Traffic:"),
    "docs/commands/sweep.md": ("starting", "ready", "stopping", "stopped", "  cluster"),
    "docs/commands/where.md": ("where",),
    "docs/commands/init.md": ("  signed in", "  wrote"),
}


def quoted_commands(rel: str) -> list[tuple[int, str, list[str]]]:
    """Each ``poisson-prove`` command of a console block skipped for needing a cloud account, with
    the page's line and the lines shown under it."""
    out = []
    for block in check.read_page(rel).blocks:
        if block.lang != "console" or block.mark is None or block.mark.kind != "skip":
            continue
        if not re.search(r"(?i)\b(AWS|cloud) account\b", block.mark.arg):
            continue
        for command, shown in check.commands(block):
            if shown is None or not check.bare(command).startswith("poisson-prove "):
                continue
            out.append((block.line, command, shown))
    return out


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    monkeypatch.setenv("COLUMNS", "250")
    with world(tmp_path, monkeypatch, pool) as made:
        # The folder's own ./prove-runs, as a page's reader has it: a ``next:`` line names no store.
        made.store = made.root / "prove-runs"
        yield made


def printed_by(w: CloudWorld, command: str) -> tuple[int, list[str]]:
    """The command run in this process on the cloud fakes: its exit code and every line it
    printed, stdout and stderr in the order printed."""
    words = shlex.split(check.bare(command), comments=True)
    assert words[0] == "poisson-prove" and not ({"|", ">", "&&", ";"} & set(words)), f"not a plain command: {command}"
    both = io.StringIO()
    code = cli.main(words[1:], stdout=both, stderr=both, stdin=io.StringIO(""))
    return code, both.getvalue().splitlines()


@pytest.mark.parametrize("rel", list(QUOTED))
def test_d1_what_a_page_quotes_from_a_cloud_sweep_is_what_the_plain_rendering_prints(w: CloudWorld, rel: str) -> None:
    assert (ROOT / rel).is_file(), f"{rel} does not exist"
    commands = quoted_commands(rel)
    shown_all = "\n".join(line for _, _, shown in commands for line in shown)
    missing = [label for label in QUOTED[rel] if not re.search(rf"(?m)^{re.escape(label)}(?=\s|$)", shown_all)]
    assert missing == [], f"{rel} quotes no cloud output with {missing}"
    # The page's cloud examples start where the spec's do: the example on 4 × m7i.2xlarge in us-east-2.
    if not any(check.bare(c).startswith("poisson-prove init") for _, c, _ in commands):
        assert cli.main(["init", "--example"], stdout=io.StringIO(), stderr=io.StringIO(), stdin=io.StringIO("")) == 0
        assert cli.main(["where", "cloud", *ALL_FLAGS, "--yes"], stdout=io.StringIO(), stderr=io.StringIO(),
                        stdin=io.StringIO("")) == 0
    wrong = []
    for line, command, shown in commands:
        code, printed = printed_by(w, command)
        if code != check.expected_code(command):
            wrong.append(f"{rel}, line {line}: {command!r} exits {code}, the page says {check.expected_code(command)}")
            continue
        differs = check.compare(check.bare(command), shown, printed)
        if differs is not None:
            wrong.append(f"{rel}, line {line}: {command!r}: {differs[1]}")
        masked = [s for s in shown if s.lstrip().startswith(("Account:", "signed in  "))]
        wrong += [f"{rel}, line {line}: the account is not shown masked as {MASKED}: {s!r}" for s in masked if MASKED not in s]
    assert wrong == [], "\n".join(wrong)


def test_d1_the_backends_page_shows_the_plans_traffic_line_as_printed() -> None:
    assert f"  Traffic: {TRAFFIC}" in blocks_text(BACKENDS), "the cloud plan's Traffic line, whole"


# ---------- D2: the data-flow section ----------

FACTS = {
    "the account is registered with the software's service by a proof of ownership": (r"\bregist", r"\bproof\b", r"\bown"),
    "no sign-in to that service, no password, no key": (r"no sign-in|without signing in|no account with", r"password", r"\bkey\b"),
    "code and data travel through its relay, and whose it is": (r"\bBurla's relay\b", r"\bcode\b", r"\b(data|inputs|results)\b"),
    "the coordinator on this machine fetches a licence key from it at start": (r"licen[cs]e", r"\bcoordinator\b"),
    "Prove turns its telemetry off on this machine and the nodes": (r"telemetry", r"\boff\b", r"\bnodes\b", r"this machine"),
    "the nodes fetch their image from Docker Hub and your packages from PyPI": (r"Docker Hub", r"PyPI"),
    "Prove itself sends nothing to Poisson Labs or anyone else": (r"sends nothing to Poisson Labs",),
}
#: What no page may say: 0.3.0 runs through the relay, in the software's ordinary mode.
CLAIMS = (
    r"nothing leaves (your|the) (cloud|account)", r"never (leaves|contacts|touches|reaches)\b[^.]*\b(cloud|account|Burla|servers?)",
    r"(cannot|can't|can not|does not|doesn't|never) (see|read|inspect)\b[^.]*\b(traffic|code|data)",
    r"end-to-end", r"private mode", r"BURLA_PRIVATE", r"zero packets", r"no third party", r"stays (inside|within|in) your (cloud|account)",
    r"only (ever )?(between|inside|within) your", r"DISABLE_BURLA_RELAY",
)


@pytest.mark.parametrize("fact", list(FACTS))
def test_d2_the_data_flow_section_says_each_fact(fact: str) -> None:
    sentences = [flat(s) for s in re.split(r"(?<=[.])\s+|\n\s*- ", data_flow()) if s.strip()]
    said = [s for s in sentences if all(re.search(p, s) for p in FACTS[fact])]
    assert said, (fact, "no one sentence of the section says it", FACTS[fact])


def test_d2_the_section_names_the_pin_and_quotes_the_traffic_line() -> None:
    from poisson_prove.executor_cloud import _PIN

    body = data_flow()
    assert f"burla=={_PIN}" in body, "the software and the one version Prove runs"
    assert "`Traffic`" in body, "that the plan's Traffic line says the same"


def pages() -> list[str]:
    return ["README.md", *sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs").rglob("*.md")), SKILL]


def test_d2_no_page_claims_more() -> None:
    wrong = []
    for rel in pages():
        text = flat(text_of(rel))
        for claim in CLAIMS:
            for found in re.finditer(rf"(?i)[^.]*{claim}[^.]*", text):
                wrong.append(f"{rel}: {found.group(0).strip()[:160]!r}")
    assert wrong == [], "\n".join(wrong)


def test_d2_the_scan_of_claims_is_not_blind() -> None:
    for sentence in ("In private mode a cluster never contacts Burla's servers.", "Nothing leaves your cloud.",
                     "The relay cannot see your traffic.", "Set BURLA_PRIVATE=True."):
        assert any(re.search(rf"(?i){claim}", sentence) for claim in CLAIMS), sentence


# ---------- D3: the name scan over README.md and docs/ ----------

NAME = re.compile(r"(?i)burla")
#: What a reader of 0.2 typed, which a page that says it moved must be able to repeat (§2.6:
#: the refusals "repeat what the reader typed", and the old extra's alias).
TYPED = re.compile(r'\[burla\]|--backend burla\b|poisson-prove\[burla\]')


def allowed(rel: str, line: str, in_data_flow: bool) -> str | None:
    """Why a line that names the software may; None when it may not."""
    if rel == BACKENDS and in_data_flow:
        return "the one disclosure of who carries the reader's code, and the pin (§2.6 items 1 and 6)"
    if rel == "docs/artifact-format.md" and ("engine" in line or '"burla"' in line):
        return "the manifest's engine field, and the stored backend value read as cloud (§2.5, §2.6 item 5)"
    if not NAME.search(TYPED.sub("", line)):
        return "what a 0.2 reader typed, where a page says it moved (§2.6 item 3)"
    if rel == BACKENDS and line.strip() == f"Traffic: {TRAFFIC}":
        return "the plan's Traffic line, quoted as printed (§8, RB-9)"
    return None


def named_lines() -> list[tuple[str, int, str, str | None]]:
    out = []
    for rel in pages():
        in_flow, flow_level = False, 0
        for number, line in enumerate(text_of(rel).splitlines(), 1):
            heading = re.match(r"^(#{1,6}) (.*)$", line)
            if heading:
                level = len(heading.group(1))
                if DATA_FLOW in heading.group(2):
                    in_flow, flow_level = True, level
                elif in_flow and level <= flow_level:
                    in_flow = False
            if NAME.search(line):
                out.append((rel, number, line, allowed(rel, line, in_flow)))
    return out


def test_d3_no_page_names_the_cluster_software_outside_the_allowed_places() -> None:
    wrong = [f"{rel}, line {n}: {line.strip()[:140]}" for rel, n, line, why in named_lines() if why is None]
    assert wrong == [], "\n".join(wrong)


def test_d3_the_scan_reads_the_pages_and_finds_the_disclosure() -> None:
    """The scan cannot pass by finding nothing: the backends page names the software in its
    data-flow section, and the scan reads every page of §16.3."""
    found = named_lines()
    assert any(rel == BACKENDS and why is not None and "disclosure" in why for rel, _, _, why in found), found
    read = set(pages())
    for rel in ("README.md", BACKENDS, "docs/sweep-spec.md", "docs/commands/sweep.md", "docs/commands/init.md",
                "docs/terminal-app.md", "docs/artifact-format.md", "docs/setup-with-your-agent.md", "docs/python.md",
                "docs/architecture.md", "docs/quickstart.md", "docs/cli-look.md", SKILL):
        assert rel in read, rel


@pytest.mark.parametrize("line,ok", [
    ("`--backend burla` runs them on your own Burla cluster.", False),
    ("A 0.2 spec's `[burla]` table is refused, naming the move to `[cloud]`.", True),
    ("`--backend burla` is refused with the new name.", True),
    ('`pip install "poisson-prove[burla]"` installs the same until 0.4.0.', True),
    ("A Modal container or a Burla worker runs your rollout's BLAS on one thread.", False),
    ("The cluster software is pinned (`burla==1.8.4`).", False),
    ("go through burla's relay", False),
])
def test_d3_the_allow_list_allows_what_was_typed_and_nothing_else(line: str, ok: bool) -> None:
    assert (allowed("docs/sweep-spec.md", line, False) is not None) is ok, line


def test_d3_the_names_place_on_the_backends_page_is_the_data_flow_section_alone() -> None:
    lines = [(n, line, why) for rel, n, line, why in named_lines() if rel == BACKENDS]
    outside = [(n, line) for n, line, why in lines if why is not None and "disclosure" not in why and "Traffic" not in why
               and NAME.search(TYPED.sub("", line))]
    assert outside == [], outside


# ---------- the botocore floor and the nightly's lanes, as built ----------


def test_every_page_that_gives_botocore_a_version_gives_the_floor_pyproject_has() -> None:
    extras = tomllib.loads(text_of("pyproject.toml"))["project"]["optional-dependencies"]
    (floor,) = [r for r in extras["cloud"] if r.startswith("botocore")]
    assert floor == "botocore[crt]>=1.42.39", floor
    assert [r for r in extras["burla"] if r.startswith("botocore")] == [floor] and floor in extras["all"]
    wrong = []
    named = 0
    for rel in [*pages(), "CONTRIBUTING.md"]:
        text = text_of(rel)
        for found in re.finditer(r"botocore\[crt\]([<>=!~]=?[\w.]+)?", text):
            named += 1
            if found.group(1) and found.group(0) != floor:
                wrong.append(f"{rel}: {found.group(0)}")
        if re.search(r"(?i)botocore[^.\n]{0,80}\b(unpinned|no floor|any version)\b", text):
            wrong.append(f"{rel}: says botocore has no floor")
    assert wrong == [], wrong
    assert floor in cloud_section(), "the backends page states the floor"
    assert named, "no page names botocore[crt]"


def test_contributing_names_each_job_the_nightly_runs_tests_in() -> None:
    workflow = text_of(".github/workflows/nightly.yml")
    jobs = re.findall(r"(?m)^  ([a-z_]+):\n", workflow.split("\njobs:\n", 1)[1])
    assert {"code", "math", "slow", "home", "floors", "linux"} <= set(jobs), jobs
    nightly = flat(text_of("CONTRIBUTING.md").split("**Nightly**", 1)[1].split("\n\n", 1)[0])
    for job, words in (("code", r"code suite"), ("math", r"math suite"), ("slow", r"slow tests"), ("home", r"`home`"),
                       ("floors", r"`floors`"), ("linux", r"Debian container")):
        assert re.search(words, nightly), f"CONTRIBUTING's nightly paragraph does not name the {job} job"


# ---------- CONTRIBUTING: lanes run in the foreground ----------


def test_contributing_says_a_lane_run_in_the_background_ignores_sigint() -> None:
    body = section(text_of("CONTRIBUTING.md"), "Running the tests")
    sentences = [s for s in re.split(r"(?<=[.:;])\s+", flat(body)) if "SIGINT" in s]
    assert sentences, "Running the tests does not mention SIGINT"
    near = " ".join(sentences)
    assert re.search(r"\bbackground\b", near), near
    assert re.search(r"\binterrupt", near), "which tests go red: the interrupt tests"
    assert re.search(r"\bforeground\b", flat(body)), "what to do: run the lanes in the foreground"
