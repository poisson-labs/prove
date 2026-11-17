"""M1 of 0.5.0, First run: the ``[burla]`` install extra goes.

The frozen tests for X1 to X5 (First Run Spec §2; FRS-3 to FRS-6), on the fakes of
``rb_cloud_support.py``. Nothing reaches a network or a cloud.

Someone who installed with ``pip install "poisson-prove[burla]"`` on 0.5.0 gets pip's warning
that the extra does not exist, and Poisson Prove without the cluster software. Each way they can
then ask for a cloud sweep tells them the one thing to type, before anything starts or is spent.

| Invariant | Test |
|---|---|
| X1 the extras are the five, and the wheel provides no ``burla`` | ``test_pf7_packaging.py`` (``the set``; ``cloud`` and ``all`` unchanged), ``test_rb_cloud_names.py`` (N7, both), ``test_burla_pin_docs.py``, ``test_pf9_backends.py`` (PF9.2), ``test_rb_docs.py`` (the botocore floor): the existing tests, changed |
| X2 each way in gives the two lines and starts nothing | ``test_x2_*`` here, one per way in |
| X3 nothing a user reads names the software in the message or its ``next:`` | every ``test_x2_*`` reads its whole output; ``test_x3_*`` reads the ``--json`` faces of ``where`` and ``init`` (a refused sweep prints the same two lines under ``--json``); N8's scans (``test_rb_cloud_names.py``) unchanged |
| X4 the docs sentence is gone, 0.3.0's entry is as released, 0.5.0's says Removed | ``test_rb_docs.py``'s D3 scan (changed: the old extra's install name is no longer allowed on a page), ``test_x4_*`` here |
| X5 the existing tests change only where they pin the extra or the sentence | the session's filing lists each |
| §2.3 a user missing the extra and the sign-in is told about the extra | ``test_missing_the_extra_and_the_sign_in_it_is_the_extra_that_is_named`` |
| §2.3 a Ctrl-C at the check exits 130 with nothing started | ``test_ctrl_c_at_the_check_exits_130_and_leaves_nothing`` |

**What the tests fix that the invariants leave open** (each a yes/no of this session):

- **Exit codes.** X2 says exit 1 for all six ways in; §2.1 step 3 says ``where`` and ``init`` say
  it "as they do today", and today they write the table, say the answer is not ready and exit 0
  (W2, W4 and W5 of ``test_rb_where.py`` pin that for every unready answer). These tests pin
  today's: exit 1 for the three sweeps, exit 0 for ``where cloud`` and ``init --runs-on cloud``,
  and the app's page stays open.
- **"Starts nothing"** is R1's "nothing is started, written or spent" (``refused_cleanly`` of
  ``test_rb_cloud_readiness.py``): no coordinator, no call to the cluster software, no ownership
  record, no ledger line, no run stored, and at most the one read-only probe process of §7.1's
  first row. ``where cloud`` and ``init --runs-on cloud`` write the ``[cloud]`` table into the
  spec before they check, as they do for every unready answer.
- **The ``--backend cloud`` way in** is a spec with no ``[cloud]`` table swept with the flag: the
  extra is named before the missing table is.
- **The CHANGELOG's 0.5.0 entry** is headed ``## 0.5.0 — Unreleased`` until the release session
  dates it, and its Removed list has one item naming the ``[burla]`` extra and the line to type.
  Its sentences are Session B's; the facts are pinned.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import signal
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import Grid, Session, drive, says
from poisson_prove import cli
from rb_cloud_support import CloudWorld, Done, Pool, cloud_table, world
from test_rb_cloud_readiness import hide_the_extra, refused_cleanly
from test_rb_where import ALL_FLAGS, CLOUD_PROMPTS, QUESTION, WROTE_CLOUD

REPO = Path(__file__).resolve().parents[1]
ERROR = "error: the cloud extra is not installed"
INSTALL = 'pip install "poisson-prove[cloud]"'
NEXT = f"  next: {INSTALL}"
#: What ``where`` says of the answer ``ALL_FLAGS`` give when the extra is missing.
NOT_READY = "where  your AWS account, us-east-2, 4 × m7i.2xlarge; not ready: the cloud extra is not installed"
INIT_OK = "ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates"
TARGET = "bu_targets.cloud:quick"
BURLA = re.compile("burla", re.I)
#: The 0.3.0 entry as released: from its heading to the line before the next release's heading,
#: the same bytes at the tags v0.3.0 and v0.4.0.
ENTRY_0_3_0 = "abda5d7957fe1afba5876a888bddfd51d3f61b64e21b9d2cb1706d9f2c7a4986"


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(1)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    monkeypatch.setenv("COLUMNS", "250")
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME", "NO_COLOR", "CI", "TEXTUAL"):
        monkeypatch.delenv(name, raising=False)
    with world(tmp_path, monkeypatch, pool) as made:
        # As a stranger types it: no --store, the folder's own ./prove-runs.
        made.store = made.root / "prove-runs"
        yield made


def typed(*args: str) -> Done:
    """The command line in this process, as typed in the test's folder; stdin is empty."""
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), stdout=out, stderr=err, stdin=io.StringIO(""))
    return Done(code, out.getvalue(), err.getvalue())


def example() -> None:
    done = typed("init", "--example")
    assert done.code == 0, done


def started_nothing(w: CloudWorld, done: Any) -> None:
    """R1's "nothing is started, written or spent", and the probe is the only process there was."""
    assert refused_cleanly(w) == [], done
    assert [s["argv"][1] for s in w.software_starts()] in ([], ["probe"]), w.software_starts()
    assert w.ledger("cloud-ledger.jsonl") == [], "a ledger line was written"


def names_only_the_cloud_extra(text: str) -> None:
    assert not BURLA.search(text), text
    assert INSTALL in text, text


# ---------- X2: one test per way in ----------


def test_x2_where_cloud_says_the_extra_is_missing_and_what_to_type(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    example()
    hide_the_extra(w, monkeypatch)
    done = typed("where", "cloud", *ALL_FLAGS, "--yes")
    assert done.code == 0, done
    assert done.out.splitlines() == [NOT_READY, WROTE_CLOUD, NEXT], done
    assert done.err == "", done
    names_only_the_cloud_extra(done.out)
    started_nothing(w, done)


def test_x2_init_runs_on_cloud_says_the_extra_is_missing_and_what_to_type(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    hide_the_extra(w, monkeypatch)
    done = typed("init", "--example", "--runs-on", "cloud")
    assert done.code == 0, done
    assert done.out.splitlines() == [INIT_OK, WROTE_CLOUD, "  not ready  the cloud extra is not installed", NEXT], done
    assert done.err == "", done
    names_only_the_cloud_extra(done.out)
    started_nothing(w, done)


def test_x2_the_apps_where_page_says_the_extra_is_missing_and_what_to_type(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    example()
    hide_the_extra(w, monkeypatch)

    async def scenario(s: Session) -> Grid:
        await s.wait_title("home")
        await s.press("w")
        await s.wait(lambda g: g.title() == "where" and says(g.text(), "this machine"), 60, "the page")
        await s.press("enter")
        await s.wait(lambda g: says(g.text(), QUESTION), 60, "the question")
        await s.press("3")
        for prompt in CLOUD_PROMPTS:
            await s.wait(lambda g, p=prompt: says(g.text(), p), 60, prompt)
            await s.press("enter")
        g = await s.wait(lambda g: says(g.text(), "not ready"), 90, "the answer's readiness")
        await s.press("q")
        return g

    rc, g = drive(scenario, cwd=w.root, store=None, size=(160, 44))
    assert rc == 0, g.text()
    said = [" ".join(row.split()) for row in g.body if row.strip()]
    assert said == [" ".join(NOT_READY.split()), f"next {INSTALL}"], g.text()
    names_only_the_cloud_extra(g.text())
    started_nothing(w, g.text())


@pytest.mark.parametrize("dry_run", [False, True], ids=["sweep", "sweep --dry-run"])
def test_x2_a_sweep_of_a_spec_with_a_cloud_table_is_refused_with_the_two_lines(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    """Two ways in: ``sweep`` and ``sweep --dry-run``, the spec's table saying where, no flag."""
    hide_the_extra(w, monkeypatch)
    w.write_spec(table=cloud_table())
    done = typed("sweep", "--target", TARGET, "--max-mde", "1", *(["--dry-run"] if dry_run else ["--yes"]))
    assert done.code == 1, done
    assert (done.out, done.err) == ("", f"{ERROR}\n{NEXT}\n"), done
    names_only_the_cloud_extra(done.err)
    started_nothing(w, done)


def test_x2_backend_cloud_on_a_spec_with_no_table_is_refused_with_the_two_lines(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    hide_the_extra(w, monkeypatch)
    w.write_spec(table=None)
    done = typed("sweep", "--target", TARGET, "--max-mde", "1", "--backend", "cloud", "--yes")
    assert done.code == 1, done
    assert (done.out, done.err) == ("", f"{ERROR}\n{NEXT}\n"), done
    names_only_the_cloud_extra(done.err)
    started_nothing(w, done)


# ---------- X3: the faces a tool reads ----------


@pytest.mark.parametrize("argv", [
    ("where", "--json"),
    ("where", "cloud", *ALL_FLAGS, "--yes", "--json"),
    ("init", "--example", "--runs-on", "cloud", "--force", "--json"),
], ids=["where", "where cloud", "init --runs-on cloud"])
def test_x3_the_json_face_names_the_cloud_extra_and_never_the_software(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...]
) -> None:
    example()
    assert typed("where", "cloud", *ALL_FLAGS, "--yes").code == 0
    hide_the_extra(w, monkeypatch)
    done = typed(*argv)
    assert not BURLA.search(done.out + done.err), done
    doc = json.loads(done.out)
    assert (done.code, doc["ready"], doc["next"]) == (0, False, [INSTALL]), done


# ---------- X4: the backends page and the CHANGELOG ----------


def test_x4_the_backends_page_no_longer_says_the_old_extra_installs_anything() -> None:
    """The install paragraph is still there (the scan is not blind), and no paragraph of the page
    pairs ``[burla]`` with installing or keeps 0.3.0's "until 0.4.0"."""
    text = (REPO / "docs" / "backends.md").read_text(encoding="utf-8")
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    assert any(INSTALL in p for p in paragraphs), "the page lost its install line"
    said = [p for p in paragraphs if "[burla]" in p and re.search(r"(?i)install", p)]
    assert said == [], said
    assert not [p for p in paragraphs if "until 0.4.0" in p]


def _changelog() -> str:
    return (REPO / "CHANGELOG.md").read_text(encoding="utf-8")


def test_x4_the_0_3_0_entry_is_byte_for_byte_as_released() -> None:
    text = _changelog().encode("utf-8")
    start = text.index(b"## 0.3.0 \xe2\x80\x94 ")
    end = text.index(b"\n## ", start) + 1
    assert hashlib.sha256(text[start:end]).hexdigest() == ENTRY_0_3_0, text[start:end].decode("utf-8")[:600]


def test_x4_the_0_5_0_entry_says_the_extra_is_removed_and_what_to_type() -> None:
    text = _changelog()
    found = re.search(r"(?m)^## 0\.5\.0 — (\S+)\s*$", text)
    assert found, "no entry headed ## 0.5.0 — Unreleased (or its date)"
    assert found.group(1) == "Unreleased" or re.fullmatch(r"\d{4}-\d\d-\d\d", found.group(1)), found.group(1)
    assert text.index("## 0.5.0") < text.index("## 0.4.0"), "the entry is not the newest"
    entry = text[found.end():].split("\n## ", 1)[0]
    removed = re.search(r"(?ms)^### Removed\s*$(.*?)(?=^### |\Z)", entry)
    assert removed, entry[:400]
    items = [" ".join(item.split()) for item in re.split(r"(?m)^- ", removed.group(1))[1:]]
    named = [item for item in items if "`[burla]`" in item]
    assert len(named) == 1, items
    (item,) = named
    missing = [fact for fact in ("extra", INSTALL, "0.3.0", "0.4.0") if fact not in item]
    assert missing == [], (missing, item)


# ---------- §2.3: the edge cases ----------


def test_missing_the_extra_and_the_sign_in_it_is_the_extra_that_is_named(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§7.1's order, where the sweep's own first check is not in the way: ``where`` asks the
    probe first and the sign-in after, so a machine missing both is never sent to ``aws login``
    before the install."""
    example()
    hide_the_extra(w, monkeypatch)
    w.aws_state(signed_in=False)
    done = typed("where", "cloud", *ALL_FLAGS, "--yes")
    assert done.code == 0, done
    assert done.nexts == [NEXT.strip()], done
    assert "not signed in" not in done.out + done.err, done
    assert w.aws_calls() == [], "the sign-in was asked before the extra was found missing"


_HOLD = (
    "import os, pathlib, sys, time\n"
    "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\n"
    "time.sleep(600)\n"
)


def _gone(pid: int, within: float = 30.0) -> bool:
    until = time.time() + within
    while time.time() < until:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.mark.parametrize("argv", [
    ("where", "cloud", *ALL_FLAGS, "--yes"),
    ("init", "--example", "--runs-on", "cloud", "--force"),
    ("sweep", "--target", TARGET, "--max-mde", "1", "--yes"),
    ("sweep", "--target", TARGET, "--max-mde", "1", "--dry-run"),
], ids=["where cloud", "init --runs-on cloud", "sweep", "sweep --dry-run"])
def test_ctrl_c_at_the_check_exits_130_and_leaves_nothing(w: CloudWorld, argv: tuple[str, ...]) -> None:
    """The check held open (a probe that never answers), then the terminal's Ctrl-C: Prove leaves
    with 130, the probe is not left running, and nothing was started, recorded or spent."""
    w.write_spec(table=cloud_table())
    marker = w.root / "probe.pid"
    hold = [sys.executable, "-I", "-c", _HOLD, str(marker)]
    w.seams = lambda: {"_launcher_argv": hold, "_head_argv": hold, "_cli_argv": hold}  # type: ignore[method-assign]
    proc = w.spawn(*argv, sweep=False)
    try:
        until = time.time() + 60
        while not (marker.exists() and marker.read_text().strip()):
            assert proc.poll() is None, proc.communicate()
            assert time.time() < until, "the check never started its probe"
            time.sleep(0.05)
        probe = int(marker.read_text())
        os.killpg(proc.pid, signal.SIGINT)
        out, err = (stream.decode() for stream in proc.communicate(timeout=60))
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 130, (out, err)
    assert _gone(probe), "the probe was left running"
    assert w.records() == {} and w.ledger() == [] and w.ledger("cloud-ledger.jsonl") == [], (out, err)
    assert w.routes() == [] and w.heads() == [] and w.aws_calls() == [], (out, err)
    assert not w.store.exists() or not any(p.is_dir() for p in w.store.iterdir()), "a run was stored"
