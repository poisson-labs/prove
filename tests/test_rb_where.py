"""C5 of 0.3.0, Remote backends: where a sweep runs, as a step of setting up.

The frozen tests for W1 to W6 and W9 (Remote Backends Spec §3, §9 steps 1 and 2, §15 C5; RB-12 to
RB-16): the ``_where`` module, ``init``'s question in a terminal and ``--runs-on``, and the
``where`` verb. W7 and W8 (the terminal app's page and its sweep) are ``test_rb_where_app.py``.

On the fakes of ``rb_cloud_support.py``: the fake AWS CLI, ``gcloud`` and ``az`` on ``PATH``, the
readiness probe run under the fake of the cluster software, a stand-in for Modal's client. No
network, no cloud, no Modal. ``init``'s question is asked of streams that say they are
terminals in this process, and of a real pseudo-terminal for the cases that turn on one.

**What the tests fix that the invariants leave open** (each a yes/no of this session):

- **Where a spec runs is the table it holds.** A spec with a ``[cloud]`` table runs on the
  reader's cloud account, one with a ``[modal]`` table on Modal, one with neither on this
  machine; ``sweep`` with no ``--backend`` runs there, and ``--backend`` still overrides. A spec
  holding both tables and swept with no ``--backend`` is refused, exit 1, in one line that names
  both tables. (§3 writes "the matching table" and asks for nothing else in the file; §9 and
  §16.4 then sweep with no ``--backend``.)
- **The module.** ``_where.choices()`` returns the three answers in order, each with ``key``
  (``local``, ``modal``, ``cloud``), ``label`` (``this machine``, ``Modal``, ``your cloud
  account``), ``available`` and ``line`` (what the step shows for it); the cloud answer has
  ``clouds``, each with ``key``, ``label``, ``offered`` and ``line``. ``_where.check(choice,
  answers)`` returns the readiness results in §7.1's order, each with ``ok``, ``label``,
  ``value`` and ``next`` (the one fixing command, or None). ``_where.table(choice, answers)``
  returns the table's TOML text, empty for this machine. ``_where.write(spec_path, table)``
  replaces the spec's where-to-run table with that text, or removes it when the text is empty.
- **The where-to-run table** is ``[cloud]``, or ``[modal]`` with its ``[modal.<image>]``
  tables, or a 0.2.1 ``[burla]`` table. Replacing one by another puts the new one where the old
  one stood.
- **What ``where cloud`` writes:** ``provider``, ``region``, ``machine_type``, ``nodes``,
  ``max_vcpus``, ``ledger``, ``stop_cost``, ``max_cost`` and ``est_seconds_per_episode``, and no
  ``image`` (it follows this machine's Python at each sweep). The defaults are §9's: AWS,
  ``us-east-2``, ``m7i.2xlarge``, 4 nodes, the ceiling nodes × the machine's vCPUs, stop $2.00,
  cap $3.00; and two the spec does not give: ``ledger = "cloud-ledger.jsonl"`` (§8's plan) and
  ``est_seconds_per_episode = 1.0``. A table already in the spec keeps every key no flag or
  answer changes.
- **``--yes`` takes the default for every value no flag gives.** Without it and with stdin not a
  terminal, the first value neither given nor already in the spec is refused, exit 1, naming its
  flag.
- **A value Prove knows it cannot use is refused and nothing is written:** a cloud not offered, a
  region or machine type outside the price table. What depends on this machine's state (the
  extra, the cloud's CLI, the sign-in, the quota) writes the table anyway and ends with its
  ``next:``, exit 0, as §9 step 1 says.
- **``init``:** the question goes to stderr after the ``ok`` line on stdout; the answers' lines
  (``signed in``, ``wrote``) and the one ``next:`` go to stdout. ``--runs-on local|modal|cloud``
  answers it on the command line with the defaults and asks nothing. Modal's cap is asked with
  the cloud cap's words, ``refuse above``.
- **Bare ``where`` with no spec in the folder** is refused, exit 1, with ``init`` as its next.
- **W9** is read from what the fakes recorded: the only cloud CLI calls are the two read-only
  ones, no ``gcloud`` or ``az`` runs, no file under the test's home or its AWS files is written,
  Modal's client is asked for ``token_id`` and never ``token_secret``, and no coordinator, record
  or ledger exists after any of ``where``, ``init`` or the module's checks.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import Step, run_pty, strip_escapes
from poisson_prove import cli
from rb_cloud_support import (
    ACCOUNT,
    MASKED,
    PROVE,
    REGION,
    TYPES,
    CloudWorld,
    Done,
    Pool,
    world,
)
from test_rb_cloud_readiness import INSTALL, QUOTA, STS, install_modal, simulate_windows

QUESTION = "where should sweeps run?  1 this machine (default)  2 Modal  3 your cloud account (AWS)"
CLOUD_PROMPTS = ["region [us-east-2]", "machine type [m7i.2xlarge]", "nodes [4]", "stop at [$2.00]",
                 "refuse above [$3.00]"]
READY = "where  your AWS account, us-east-2, 4 × m7i.2xlarge; signed in, ready"
SIGNED_IN = f"  signed in  AWS {MASKED}"
WROTE_CLOUD = "  wrote  [cloud] into prove.toml"
NOT_YET = ["Google Cloud  not yet supported by Prove", "Azure  not yet supported by Prove"]
ON_WINDOWS = "your cloud account  not available on Windows yet"
#: What ``where cloud`` writes when every answer is the default (the fixed reading above).
DEFAULT_CLOUD = {
    "provider": "aws", "region": "us-east-2", "machine_type": "m7i.2xlarge", "nodes": 4, "max_vcpus": 32,
    "ledger": "cloud-ledger.jsonl", "stop_cost": 2.0, "max_cost": 3.0, "est_seconds_per_episode": 1.0,
}
ALL_FLAGS = ["--cloud", "aws", "--region", "us-east-2", "--machine-type", "m7i.2xlarge", "--nodes", "4",
             "--stop-cost", "2", "--max-cost", "3"]
#: What ``init`` writes today and 0.2.1 wrote, byte for byte: the keyless example, the bare
#: template, and the template with ``--target my_agent:rollout``.
SHA_EXAMPLE = "161f57ddd8996b092934fcda293c31c88a91055444cb37d7097ab99181484994"
SHA_TEMPLATE = "b27847eea60ddb5de0752e51ccf6914441eb06051d0a0921e3d7b8eb1be7f87e"
SHA_TARGET = "a7fb729798fe7cede812a645bf1cd993fa62d6bc565946e97afe3ec08cc38f7e"
INIT_OUT = ("ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates\n"
            "  next: poisson-prove sweep\n")

HEAD = '''# A spec of the reader's own, with comments Prove did not write.
target = "pkg.agent:rollout"   # the rollout
target_id = "agent@v3"
t_unit = "steps"
replicates = 40

# What varies.
[axes.model]
type = "categorical"
values = ["small", "large"]
'''
TAIL = '''
# The outcomes that count against the agent.
[declare]
failures = ["timeout"]   # one for now

[chaos]
fault = "tool_error"
rate = 0.25
'''
CLOUD_OLD = '''
[cloud]
provider = "aws"
region = "eu-west-1"
machine_type = "m7i.xlarge"
nodes = 2
ledger = "spend.jsonl"
stop_cost = 1.0
max_cost = 1.5
est_seconds_per_episode = 0.25
packages = ["pkg"]
batch_size = 64
'''
MODAL_OLD = '''
[modal]
concurrency = 16
secrets = ["openai"]

[modal.image]
python = "3.11"
pip = ["openai>=2.20"]
'''
BURLA_OLD = '''
[burla]
head_url = "http://127.0.0.1:5001"
nodes = 3
machine_type = "m7i.xlarge"
slots_per_node = 2
usd_per_node_hour = 0.31
price_asof = "read off the AWS console, 2026-10-30"
ledger = "old-ledger.jsonl"
stop_cost = 4.0
max_cost = 6.0
est_seconds_per_episode = 0.75
packages = ["pkg"]
batch_size = 32
idle_minutes = 7
'''
CARRIED = {
    "nodes": 3, "machine_type": "m7i.xlarge", "slots_per_node": 2, "usd_per_node_hour": 0.31,
    "price_asof": "read off the AWS console, 2026-10-30", "ledger": "old-ledger.jsonl", "stop_cost": 4.0,
    "max_cost": 6.0, "est_seconds_per_episode": 0.75, "packages": ["pkg"], "batch_size": 32, "idle_minutes": 7,
}


def where_module() -> Any:
    import importlib

    return importlib.import_module("poisson_prove._where")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def loaded(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def content_lines(text: str) -> list[str]:
    """The lines that are not blank: a table taken out may leave one blank line or none."""
    return [line for line in text.splitlines() if line.strip()]


class Terminal(io.StringIO):
    """A stream that says it is a terminal."""

    def isatty(self) -> bool:
        return True


class NeverRead(io.StringIO):
    """A stdin that fails the test when anything is read from it."""

    def _no(self, *args: Any) -> Any:
        raise AssertionError("stdin was read: a question was asked")

    read = readline = readlines = __next__ = _no  # type: ignore[assignment]


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(1)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    monkeypatch.setenv("COLUMNS", "250")
    with world(tmp_path, monkeypatch, pool) as made:
        made.before = snapshot(made)  # type: ignore[attr-defined]
        yield made
        problems = touched(made, made.before)  # type: ignore[attr-defined]
        assert problems == [], problems


def snapshot(w: CloudWorld) -> dict[str, Any]:
    return {
        "aws-config": w.aws_config.read_bytes(), "aws-credentials": w.aws_credentials.read_bytes(),
        "home": sorted(str(p.relative_to(w.home)) for p in w.home.rglob("*")),
    }


def touched(w: CloudWorld, before: dict[str, Any]) -> list[str]:
    """W9, after every test of this file: no check wrote cloud configuration, signed in or created
    anything."""
    out = []
    at = QUOTA.index("--region") + 1
    wrong = [c["argv"] for c in w.aws_calls()
             if c["argv"] != STS and [*c["argv"][:at], QUOTA[at], *c["argv"][at + 1:]] != QUOTA]
    if wrong:
        out.append(f"AWS CLI calls other than the two read-only ones: {wrong}")
    if w.other_cli_calls():
        out.append(f"gcloud or az ran: {[c['argv'] for c in w.other_cli_calls()]}")
    if w.aws_config.read_bytes() != before["aws-config"] or w.aws_credentials.read_bytes() != before["aws-credentials"]:
        out.append("an AWS configuration file was written")
    home = sorted(str(p.relative_to(w.home)) for p in w.home.rglob("*"))
    if home != before["home"]:
        out.append(f"files appeared under the home folder: {sorted(set(home) - set(before['home']))}")
    if w.routes() or w.heads():
        out.append(f"the cluster software was started or called: {w.routes()}")
    if w.records() or w.ledger() or w.ledger("cloud-ledger.jsonl"):
        out.append("a record or a ledger line was written")
    return out


def run(w: CloudWorld, *args: str, stdin: io.StringIO | None = None, err: io.StringIO | None = None) -> Done:
    """The command line in this process; stdin never read unless one is given."""
    out, errs = io.StringIO(), err if err is not None else io.StringIO()
    code = cli.main(list(args), stdout=out, stderr=errs, stdin=stdin if stdin is not None else NeverRead())
    return Done(code, out.getvalue(), errs.getvalue())


def asked(w: CloudWorld, *args: str, typed: str) -> Done:
    """The command line with stdin and stderr terminals, ``typed`` on stdin."""
    return run(w, *args, stdin=Terminal(typed), err=Terminal())


def example(w: CloudWorld) -> bytes:
    done = run(w, "init", "--example")
    assert done.code == 0, done
    return w.spec.read_bytes()


def flat(text: str) -> str:
    return " ".join(text.split())


def spec_of(w: CloudWorld, middle: str) -> str:
    text = HEAD + middle + TAIL
    w.spec.write_text(text, encoding="utf-8")
    return text


# ---------- W1: write replaces only the where-to-run table ----------


@pytest.mark.parametrize("old", ["cloud", "modal", "burla"])
@pytest.mark.parametrize("new", ["cloud", "modal"])
def test_w1_write_replaces_only_the_where_table_and_keeps_every_other_byte(tmp_path: Path, old: str, new: str) -> None:
    where = where_module()
    middle = {"cloud": CLOUD_OLD, "modal": MODAL_OLD, "burla": BURLA_OLD}[old]
    spec = tmp_path / "prove.toml"
    spec.write_text(HEAD + middle + TAIL, encoding="utf-8")
    answers = DEFAULT_CLOUD if new == "cloud" else {"max_cost": 5.0}
    table = where.table(new, answers)
    assert isinstance(table, str) and table.lstrip().startswith(f"[{new}]"), table
    where.write(spec, table)
    text = spec.read_text(encoding="utf-8")
    assert text.startswith(HEAD), "the bytes before the table changed"
    assert text.endswith(TAIL), "the bytes after the table changed"
    doc = tomllib.loads(text)
    kept = tomllib.loads(HEAD + TAIL)
    assert {k: v for k, v in doc.items() if k not in ("cloud", "modal")} == kept, doc
    assert "burla" not in doc and ({"cloud", "modal"} & set(doc)) == {new}, sorted(doc)
    for key, value in answers.items():
        assert doc[new][key] == value, (key, doc[new])
    assert list(doc) == [*list(kept)[:5], new, *list(kept)[5:]], f"the table moved: {list(doc)}"


@pytest.mark.parametrize("ending", ["a newline", "a blank line"])
def test_w1_a_spec_with_no_such_table_gets_it_appended_after_a_blank_line(tmp_path: Path, ending: str) -> None:
    where = where_module()
    original = HEAD + TAIL + ("\n" if ending == "a blank line" else "")
    spec = tmp_path / "prove.toml"
    spec.write_text(original, encoding="utf-8")
    where.write(spec, where.table("cloud", DEFAULT_CLOUD))
    text = spec.read_text(encoding="utf-8")
    base = HEAD + TAIL
    assert text.startswith(base), "the spec's own bytes changed"
    added = text[len(base):]
    assert added.startswith("\n[cloud]\n"), repr(added[:40])
    assert tomllib.loads(text)["cloud"] == DEFAULT_CLOUD
    assert text.endswith("\n") and not text.endswith("\n\n"), repr(text[-20:])


@pytest.mark.parametrize("old", ["cloud", "modal", "burla"])
def test_w1_this_machine_takes_the_table_out_and_keeps_every_other_line(tmp_path: Path, old: str) -> None:
    where = where_module()
    middle = {"cloud": CLOUD_OLD, "modal": MODAL_OLD, "burla": BURLA_OLD}[old]
    spec = tmp_path / "prove.toml"
    spec.write_text(HEAD + middle + TAIL, encoding="utf-8")
    assert where.table("local", {}) == ""
    where.write(spec, where.table("local", {}))
    text = spec.read_text(encoding="utf-8")
    assert content_lines(text) == content_lines(HEAD + TAIL), text
    assert tomllib.loads(text) == tomllib.loads(HEAD + TAIL)
    assert "\n\n\n" not in text, "the table left more than one blank line behind"


def test_w1_this_machine_on_a_spec_with_no_table_changes_no_byte(tmp_path: Path) -> None:
    where = where_module()
    spec = tmp_path / "prove.toml"
    spec.write_text(HEAD + TAIL, encoding="utf-8")
    where.write(spec, "")
    assert spec.read_text(encoding="utf-8") == HEAD + TAIL


@pytest.mark.parametrize("new", ["cloud", "modal", "local"])
def test_w1_write_refuses_to_drop_a_key_it_does_not_know(tmp_path: Path, new: str) -> None:
    where = where_module()
    original = HEAD + CLOUD_OLD + 'mystery_key = "kept by hand"\n' + TAIL
    spec = tmp_path / "prove.toml"
    spec.write_text(original, encoding="utf-8")
    table = where.table(new, {"max_cost": 5.0} if new == "modal" else DEFAULT_CLOUD if new == "cloud" else {})
    with pytest.raises(Exception) as caught:  # noqa: PT011 - the kind is the build's; its words are pinned
        where.write(spec, table)
    assert "mystery_key" in str(caught.value), caught.value
    assert spec.read_text(encoding="utf-8") == original, "a refused write changed the spec"


def test_w1_the_table_text_is_the_table_and_nothing_else(tmp_path: Path) -> None:
    where = where_module()
    table = where.table("cloud", DEFAULT_CLOUD)
    assert tomllib.loads(table) == {"cloud": DEFAULT_CLOUD}, table
    assert list(tomllib.loads(table)["cloud"])[:4] == ["provider", "region", "machine_type", "nodes"], table
    assert tomllib.loads(where.table("modal", {"max_cost": 5.0})) == {"modal": {"max_cost": 5.0}}


# ---------- W2: where cloud, on flags ----------


def test_w2_where_cloud_with_every_flag_writes_the_table_says_so_and_asks_nothing(w: CloudWorld) -> None:
    before = example(w)
    done = run(w, "where", "cloud", *ALL_FLAGS, "--yes")
    assert done.code == 0, done
    assert done.out.splitlines()[0] == READY, done
    assert WROTE_CLOUD in done.out.splitlines() and SIGNED_IN in done.out.splitlines(), done
    assert done.nexts == ["next: poisson-prove sweep --dry-run"], done
    assert done.err == "", done
    after = w.spec.read_bytes()
    assert after.startswith(before), "where changed the spec's own bytes"
    assert after[len(before):].startswith(b"\n[cloud]\n"), after[len(before):][:40]
    assert loaded(w.spec)["cloud"] == DEFAULT_CLOUD, loaded(w.spec)["cloud"]
    assert ACCOUNT not in done.out + done.err, done


def test_w2_the_table_it_writes_is_one_the_sweep_reads_and_the_sweep_then_runs_there(w: CloudWorld) -> None:
    """The fixed reading: the table is where the spec runs. With no ``--backend`` the plan is the
    cloud's; ``--backend local`` still plans this machine."""
    example(w)
    assert run(w, "where", "cloud", *ALL_FLAGS, "--yes").code == 0
    plan = run(w, "--store", str(w.store), "sweep", "--dry-run")
    assert plan.code == 0, plan
    assert plan.out.startswith("plan  ") and "on your AWS account" in plan.out.splitlines()[0], plan
    assert "  Backend: cloud · AWS · target: mock-agent · t_unit: tool_calls" in plan.out.splitlines(), plan
    local = run(w, "--store", str(w.store), "sweep", "--dry-run", "--backend", "local")
    assert local.code == 0 and "on local" in local.out.splitlines()[0], local


def test_w2_the_ceiling_follows_the_nodes_unless_a_flag_gives_it(w: CloudWorld) -> None:
    example(w)
    flags = [f if f != "4" else "2" for f in ALL_FLAGS]
    assert run(w, "where", "cloud", *flags, "--yes").code == 0
    assert loaded(w.spec)["cloud"]["nodes"] == 2 and loaded(w.spec)["cloud"]["max_vcpus"] == 16
    assert run(w, "where", "cloud", *flags, "--max-vcpus", "40", "--yes").code == 0
    assert loaded(w.spec)["cloud"]["max_vcpus"] == 40, loaded(w.spec)["cloud"]


@pytest.mark.parametrize("flag", ["--region", "--machine-type", "--nodes", "--stop-cost", "--max-cost"])
def test_w2_a_missing_value_with_stdin_not_a_terminal_is_refused_naming_the_flag(w: CloudWorld, flag: str) -> None:
    before = example(w)
    at = ALL_FLAGS.index(flag)
    flags = ALL_FLAGS[:at] + ALL_FLAGS[at + 2:]
    done = run(w, "where", "cloud", *flags, stdin=io.StringIO(""))
    assert done.code == 1, done
    assert len(done.errors) == 1 and flag in done.errors[0], done
    assert done.out == "", done
    assert w.spec.read_bytes() == before, "a refused where wrote the spec"
    assert w.aws_calls() == [], "the checks ran for a command that was refused for a missing value"


def test_w2_yes_takes_the_default_for_every_value_no_flag_gives(w: CloudWorld) -> None:
    example(w)
    done = run(w, "where", "cloud", "--yes")
    assert done.code == 0, done
    assert loaded(w.spec)["cloud"] == DEFAULT_CLOUD, loaded(w.spec)["cloud"]
    assert done.out.splitlines()[0] == READY, done


def test_w2_a_table_already_there_keeps_what_no_flag_changes(w: CloudWorld) -> None:
    spec_of(w, CLOUD_OLD)
    done = run(w, "where", "cloud", "--nodes", "3", stdin=io.StringIO(""))
    assert done.code == 0, done
    table = loaded(w.spec)["cloud"]
    old = tomllib.loads(CLOUD_OLD)["cloud"]
    assert table == {**old, "nodes": 3, **({"max_vcpus": table["max_vcpus"]} if "max_vcpus" in table else {})}, table
    assert table.get("max_vcpus", 12) == 12, table
    text = w.spec.read_text(encoding="utf-8")
    assert text.startswith(HEAD) and text.endswith(TAIL), "where changed the rest of the spec"


@pytest.mark.parametrize("what", ["region", "machine", "cloud-gcp", "cloud-azure"])
def test_w2_w6_a_value_prove_cannot_use_is_refused_and_nothing_is_written(w: CloudWorld, what: str) -> None:
    before = example(w)
    swap = {"region": ("us-east-2", "mars-north-1"), "machine": ("m7i.2xlarge", "m7i.3xlarge"),
            "cloud-gcp": ("aws", "gcp"), "cloud-azure": ("aws", "azure")}[what]
    flags = [swap[1] if f == swap[0] else f for f in ALL_FLAGS]
    done = run(w, "where", "cloud", *flags, "--yes")
    assert done.code == 1, done
    assert done.out == "" and len(done.errors) == 1, done
    if what == "machine":
        assert done.errors == [f"error: m7i.3xlarge is not in Prove's AWS prices for {REGION}; the machine types are "
                               + ", ".join(TYPES)], done
    elif what == "region":
        assert "mars-north-1" in done.errors[0] and "us-east-2" in done.errors[0], done
    else:
        name = "Google Cloud" if what == "cloud-gcp" else "Azure"
        assert done.errors == [f"error: {name} is not yet supported by Prove; AWS is"], done
    assert w.spec.read_bytes() == before, "a refused where wrote the spec"


UNREADY = {
    "signed-out": (lambda w: w.aws_state(signed_in=False), ["next: aws login"]),
    "sso-signed-out": (lambda w: (w.aws_state(signed_in="expired"),
                                  w.aws_config.write_text("[default]\nsso_session = corp\nregion = us-east-2\n")),
                       ["next: aws sso login"]),
    "no-extra": (lambda w: setattr(w, "mode", "absent") or w.patch_seams(), [INSTALL.strip()]),
    "no-cli": (lambda w: w.remove_cli("aws"), []),
    "quota-short": (lambda w: w.aws_state(quota=16), []),
}


@pytest.mark.parametrize("case", list(UNREADY))
def test_w2_a_check_this_machine_fails_writes_the_table_anyway_and_ends_with_its_next(w: CloudWorld, case: str) -> None:
    example(w)
    arrange, nexts = UNREADY[case]
    arrange(w)
    w.before = snapshot(w)  # type: ignore[attr-defined]
    done = run(w, "where", "cloud", *ALL_FLAGS, "--yes")
    assert done.code == 0, done
    assert loaded(w.spec)["cloud"] == DEFAULT_CLOUD, "the table was not written"
    assert WROTE_CLOUD in done.out.splitlines(), done
    assert done.nexts == nexts, done
    first = done.out.splitlines()[0]
    assert first.startswith("where  your AWS account, us-east-2, 4 × m7i.2xlarge; ") and not first.endswith("ready"), first
    assert SIGNED_IN not in done.out.splitlines() or case == "quota-short", done


# ---------- W3: a 0.2.1 spec ----------


def test_w3_where_cloud_rewrites_a_0_2_1_table_keeping_every_carried_value(w: CloudWorld) -> None:
    spec_of(w, BURLA_OLD)
    done = run(w, "where", "cloud", "--cloud", "aws", "--region", "us-west-2", stdin=io.StringIO(""))
    assert done.code == 0, done
    doc = loaded(w.spec)
    assert "burla" not in doc, sorted(doc)
    table = doc["cloud"]
    assert {k: table.get(k) for k in CARRIED} == CARRIED, table
    assert table["provider"] == "aws" and table["region"] == "us-west-2", table
    assert "head_url" not in table and "image" not in table, table
    assert table.get("max_vcpus", 12) == 12, table
    assert set(table) <= {*CARRIED, "provider", "region", "max_vcpus"}, sorted(table)
    text = w.spec.read_text(encoding="utf-8")
    assert text.startswith(HEAD) and text.endswith(TAIL), "where changed the rest of the spec"
    assert "  wrote  [cloud] into prove.toml" in done.out.splitlines(), done
    # What it wrote is a table the sweep's own reader takes.
    from poisson_prove.executor_cloud import CloudOptions

    options = CloudOptions.from_sweep_file(w.spec)
    assert options.nodes == 3 and options.region == "us-west-2" and options.usd_per_node_hour == 0.31, options


def test_w3_it_asks_only_for_what_is_new(w: CloudWorld) -> None:
    """Off a terminal, the region is the one value a 0.2.1 table cannot give; on one, it is the
    one question asked beyond which cloud."""
    original = spec_of(w, BURLA_OLD)
    refused = run(w, "where", "cloud", stdin=io.StringIO(""))
    assert refused.code == 1 and "--region" in refused.errors[0], refused
    assert w.spec.read_text(encoding="utf-8") == original
    done = asked(w, "where", "cloud", typed="us-west-2\n")
    assert done.code == 0, done
    prompts = [p.split(" [")[0] for p in CLOUD_PROMPTS]
    shown = [p for p in prompts if f"{p} [" in done.err]
    assert shown == ["region"], done.err
    assert loaded(w.spec)["cloud"]["region"] == "us-west-2" and loaded(w.spec)["cloud"]["nodes"] == 3


# ---------- W4: bare where ----------


def test_w4_bare_where_says_where_the_spec_runs_and_that_it_is_ready(w: CloudWorld) -> None:
    example(w)
    assert run(w, "where", "cloud", *ALL_FLAGS, "--yes").code == 0
    before = w.spec.read_bytes()
    done = run(w, "where")
    assert done.code == 0, done
    lines = done.out.splitlines()
    assert lines[0] == READY, done
    assert SIGNED_IN in lines, done
    assert done.nexts == ["next: poisson-prove sweep"], done
    assert done.err == "", done
    assert w.spec.read_bytes() == before, "bare where wrote the spec"
    assert "wrote" not in done.out, done


@pytest.mark.parametrize("case", list(UNREADY))
def test_w4_an_unready_answer_is_still_exit_0_with_its_fixing_next(w: CloudWorld, case: str) -> None:
    example(w)
    assert run(w, "where", "cloud", *ALL_FLAGS, "--yes").code == 0
    before = w.spec.read_bytes()
    arrange, nexts = UNREADY[case]
    arrange(w)
    w.before = snapshot(w)  # type: ignore[attr-defined]
    done = run(w, "where")
    assert done.code == 0, done
    first = done.out.splitlines()[0]
    assert first.startswith("where  your AWS account, us-east-2, 4 × m7i.2xlarge; ") and not first.endswith("ready"), first
    assert done.nexts == nexts, done
    assert done.errors == [], done
    assert w.spec.read_bytes() == before


def test_w4_this_machine(w: CloudWorld) -> None:
    example(w)
    done = run(w, "where")
    assert done.code == 0, done
    assert done.out.splitlines()[0].startswith("where  this machine"), done
    assert done.nexts == ["next: poisson-prove sweep"], done
    assert w.aws_calls() == [], "this machine needs no check"


@pytest.mark.parametrize("token", ["ak-planted-modal-token-id-0000", None])
def test_w4_w9_modal_is_asked_of_modals_client_and_never_for_its_secret(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, token: str | None
) -> None:
    config = install_modal(monkeypatch, token)
    example(w)
    done = run(w, "where", "modal", "--max-cost", "5", "--yes")
    assert done.code == 0, done
    assert loaded(w.spec)["modal"] == {"max_cost": 5.0}, loaded(w.spec)
    assert "  wrote  [modal] into prove.toml" in done.out.splitlines(), done
    bare = run(w, "where")
    assert bare.code == 0, bare
    first = bare.out.splitlines()[0]
    assert first.startswith("where  Modal"), bare
    if token:
        assert first.endswith("ready") and bare.nexts == ["next: poisson-prove sweep"], bare
    else:
        assert not first.endswith("ready") and bare.nexts == ["next: modal setup"], bare
    assert "token_id" in config.asked and "token_secret" not in config.asked, config.asked
    assert "ak-planted" not in done.out + done.err + bare.out + bare.err


def test_w4_where_local_takes_the_table_out(w: CloudWorld) -> None:
    before = example(w)
    assert run(w, "where", "cloud", *ALL_FLAGS, "--yes").code == 0
    done = run(w, "where", "local")
    assert done.code == 0, done
    assert done.out.splitlines()[0].startswith("where  this machine"), done
    assert w.spec.read_bytes() == before, "the spec is not what it was before the table was added"


def test_w4_json_gives_the_same_verdict_sentence_and_next(w: CloudWorld) -> None:
    example(w)
    assert run(w, "where", "cloud", *ALL_FLAGS, "--yes").code == 0
    done = run(w, "where", "--json")
    assert done.code == 0, done
    doc = json.loads(done.out)
    assert doc["schema"] == "poisson-prove.where/1" and doc["verdict"] == "where", doc
    assert doc["sentence"] == READY.split("  ", 1)[1], doc
    assert doc["next"] == ["poisson-prove sweep"], doc
    assert ACCOUNT not in done.out, done


def test_w4_with_no_spec_in_the_folder_it_is_refused_and_names_init(w: CloudWorld) -> None:
    for args in (("where",), ("where", "cloud", *ALL_FLAGS, "--yes")):
        done = run(w, *args)
        assert done.code == 1, done
        assert len(done.errors) == 1 and "prove.toml" in done.errors[0], done
        assert len(done.nexts) == 1 and done.nexts[0].startswith("next: poisson-prove init"), done
        assert not w.spec.exists()


def test_w4_a_spec_with_both_tables_swept_with_no_backend_is_refused_naming_both(w: CloudWorld) -> None:
    example(w)
    with w.spec.open("a", encoding="utf-8") as fh:
        fh.write(CLOUD_OLD + MODAL_OLD)
    done = run(w, "--store", str(w.store), "sweep", "--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1 and "[cloud]" in done.errors[0] and "[modal]" in done.errors[0], done
    assert done.out == "", done
    # Bare where does not call such a spec ready, or send the reader to a sweep that is refused.
    bare = run(w, "where")
    assert not bare.out.splitlines()[0].endswith("ready") if bare.out else bare.code == 1, bare
    assert "next: poisson-prove sweep" not in bare.nexts, bare


# ---------- W5: init ----------


@pytest.mark.parametrize("args,digest,name", [
    (("--example",), SHA_EXAMPLE, "prove.toml"),
    ((), SHA_TEMPLATE, "prove.toml"),
    (("--target", "my_agent:rollout", "--out", "u.toml"), SHA_TARGET, "u.toml"),
])
def test_w5_init_off_a_terminal_writes_what_0_2_1_wrote_and_asks_nothing(
    w: CloudWorld, args: tuple[str, ...], digest: str, name: str
) -> None:
    done = run(w, "init", *args)
    assert done.code == 0, done
    assert sha(w.root / name) == digest, "init wrote other bytes than 0.2.1 did"
    assert done.err == "", done
    if args == ("--example",):
        assert done.out == INIT_OUT, done


@pytest.mark.parametrize("streams", ["stdin a terminal, stderr piped", "stderr a terminal, stdin piped", "--json"])
def test_w5_init_asks_only_when_stdin_and_stderr_are_both_terminals_and_no_json(w: CloudWorld, streams: str) -> None:
    if streams == "--json":
        done = run(w, "init", "--example", "--json", stdin=Terminal("3\n"), err=Terminal())
        assert json.loads(done.out)["wrote"] == ["prove.toml"], done
    elif streams.startswith("stdin"):
        done = run(w, "init", "--example", stdin=Terminal("3\n"))
        assert done.out == INIT_OUT, done
    else:
        done = run(w, "init", "--example", err=Terminal())
        assert done.out == INIT_OUT, done
    assert done.code == 0, done
    assert "where should sweeps run" not in done.out + done.err, done
    assert sha(w.spec) == SHA_EXAMPLE


def test_w5_in_a_terminal_init_asks_the_question_and_enter_keeps_this_machine(w: CloudWorld) -> None:
    done = asked(w, "init", "--example", typed="\n")
    assert done.code == 0, done
    assert flat(done.err) == flat(QUESTION), done.err
    assert done.out == INIT_OUT, done
    assert sha(w.spec) == SHA_EXAMPLE, "Enter changed what init writes"


def test_w5_answer_1_is_this_machine_too(w: CloudWorld) -> None:
    done = asked(w, "init", "--example", typed="1\n")
    assert done.code == 0 and done.out == INIT_OUT and sha(w.spec) == SHA_EXAMPLE, done


def test_w5_answer_3_asks_one_question_a_line_checks_writes_the_table_and_names_the_dry_run(w: CloudWorld) -> None:
    done = asked(w, "init", "--example", typed="3\n" + "\n" * len(CLOUD_PROMPTS))
    assert done.code == 0, done
    err = flat(done.err)
    assert err.startswith(flat(QUESTION)), done.err
    at = [err.find(prompt) for prompt in CLOUD_PROMPTS]
    assert -1 not in at and at == sorted(at) and len(set(at)) == len(at), (at, done.err)
    for line in NOT_YET:
        assert flat(line) in err, (line, done.err)
    out = done.out.splitlines()
    assert out[0] == INIT_OUT.splitlines()[0], done
    assert SIGNED_IN in out and WROTE_CLOUD in out and out.index(SIGNED_IN) < out.index(WROTE_CLOUD), done
    assert done.nexts == ["next: poisson-prove sweep --dry-run"] and out[-1] == "  next: poisson-prove sweep --dry-run", done
    text = w.spec.read_bytes()
    assert hashlib.sha256(text[: text.index(b"\n[cloud]\n")]).hexdigest() == SHA_EXAMPLE, "init changed the spec's own bytes"
    assert loaded(w.spec)["cloud"] == DEFAULT_CLOUD, loaded(w.spec)["cloud"]
    assert ACCOUNT not in done.out + done.err, done


def test_w5_typed_answers_are_what_is_written(w: CloudWorld) -> None:
    done = asked(w, "init", "--example", typed="3\nus-west-2\nm7i.xlarge\n2\n1\n1.5\n")
    assert done.code == 0, done
    assert loaded(w.spec)["cloud"] == {**DEFAULT_CLOUD, "region": "us-west-2", "machine_type": "m7i.xlarge",
                                       "nodes": 2, "max_vcpus": 8, "stop_cost": 1.0, "max_cost": 1.5}


def test_w5_a_check_that_fails_writes_the_table_anyway_and_ends_with_its_next(w: CloudWorld) -> None:
    w.aws_state(signed_in=False)
    done = asked(w, "init", "--example", typed="3\n" + "\n" * len(CLOUD_PROMPTS))
    assert done.code == 0, done
    assert loaded(w.spec)["cloud"] == DEFAULT_CLOUD
    assert WROTE_CLOUD in done.out.splitlines() and SIGNED_IN not in done.out.splitlines(), done
    assert done.nexts == ["next: aws login"], done


def test_w5_answer_2_is_modal(w: CloudWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    install_modal(monkeypatch, None)
    done = asked(w, "init", "--example", typed="2\n4\n")
    assert done.code == 0, done
    assert "refuse above" in done.err, done.err
    assert loaded(w.spec)["modal"] == {"max_cost": 4.0}, loaded(w.spec)
    assert "  wrote  [modal] into prove.toml" in done.out.splitlines(), done
    assert done.nexts == ["next: modal setup"], done


@pytest.mark.parametrize("runs_on", ["local", "modal", "cloud"])
@pytest.mark.parametrize("terminal", [False, True])
def test_w5_runs_on_answers_the_question_on_the_command_line(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, runs_on: str, terminal: bool
) -> None:
    install_modal(monkeypatch, "ak-planted-modal-token-id-0000")
    args = ("init", "--example", "--runs-on", runs_on)
    done = run(w, *args, err=Terminal(), stdin=_never_read_terminal()) if terminal else run(w, *args)
    assert done.code == 0, done
    assert "where should sweeps run" not in done.out + done.err, done
    text = w.spec.read_bytes()
    doc = loaded(w.spec)
    if runs_on == "local":
        assert sha(w.spec) == SHA_EXAMPLE and done.out == INIT_OUT, done
        return
    assert hashlib.sha256(text[: text.index(f"\n[{runs_on}]\n".encode())]).hexdigest() == SHA_EXAMPLE
    if runs_on == "cloud":
        assert doc["cloud"] == DEFAULT_CLOUD and WROTE_CLOUD in done.out.splitlines(), done
    else:
        assert "modal" in doc and "cloud" not in doc, sorted(doc)
    assert done.nexts == ["next: poisson-prove sweep --dry-run"], done


def _never_read_terminal() -> io.StringIO:
    class Both(NeverRead):
        def isatty(self) -> bool:
            return True

    return Both()


def test_w5_runs_on_goes_with_a_spec_not_with_the_agent_setup_and_takes_only_the_three(w: CloudWorld) -> None:
    done = run(w, "init", "--agent", "--runs-on", "cloud")
    assert done.code == 2 and "--runs-on" in done.errors[0], done
    wrong = run(w, "init", "--runs-on", "aws")
    assert wrong.code == 2, wrong
    assert not w.spec.exists()


def test_w5_inits_help_names_runs_on_and_no_longer_says_nothing_is_asked(w: CloudWorld) -> None:
    done = run(w, "init", "--help")
    assert done.code == 0, done
    flat = " ".join(done.out.split())
    assert "--runs-on {local,modal,cloud}" in flat, done.out
    assert "Nothing is asked" not in flat, done.out
    assert "terminal" in flat, "the help does not say when the question is asked"


def prove_in_a_terminal(w: CloudWorld, *argv: str, steps: tuple[Step, ...], stdin: str = "pty") -> Any:
    """``poisson-prove ARGV`` with the cloud fakes, as its own process on a pseudo-terminal: stdin,
    stdout and stderr all the one terminal, plain rendering."""
    return run_pty([], home=w.home, cwd=w.root, cols=200, rows=50, stdin=stdin, steps=steps, timeout=180,
                   command=[str(PROVE), str(w.config()), *argv])


def test_w5_on_a_real_terminal_the_question_is_asked_and_answered(w: CloudWorld) -> None:
    run_ = prove_in_a_terminal(
        w, "--plain", "init", "--example",
        steps=(Step(b"3\r", until="where should sweeps run?"),
               *(Step(b"\r", until=prompt) for prompt in CLOUD_PROMPTS)),
    )
    shown = [line.rstrip() for line in strip_escapes(run_.out).splitlines()]
    assert run_.code == 0, shown
    assert QUESTION in "\n".join(shown), shown
    assert SIGNED_IN in shown and WROTE_CLOUD in shown, shown
    assert shown[-1] == "  next: poisson-prove sweep --dry-run", shown[-5:]
    assert loaded(w.spec)["cloud"] == DEFAULT_CLOUD


def test_w5_pretty_asks_the_same_question(w: CloudWorld) -> None:
    run_ = prove_in_a_terminal(w, "init", "--example", steps=(Step(b"\r", until="where should sweeps run?"),))
    shown = strip_escapes(run_.out)
    assert run_.code == 0, shown
    for words in ("1 this machine (default)", "2 Modal", "3 your cloud account (AWS)"):
        assert words in shown, shown
    assert sha(w.spec) == SHA_EXAMPLE


def test_w5_on_a_terminal_with_stdin_not_one_init_asks_nothing(w: CloudWorld) -> None:
    run_ = prove_in_a_terminal(w, "--plain", "init", "--example", steps=(), stdin="null")
    shown = strip_escapes(run_.out)
    assert run_.code == 0, shown
    assert "where should sweeps run" not in shown, shown
    assert [line.rstrip() for line in shown.splitlines() if line.strip()] == INIT_OUT.splitlines(), shown
    assert sha(w.spec) == SHA_EXAMPLE


# ---------- W6: what is not offered ----------


def test_w6_the_choices_are_the_three_and_the_clouds_not_offered_say_so(w: CloudWorld) -> None:
    where = where_module()
    choices = where.choices()
    assert [c.key for c in choices] == ["local", "modal", "cloud"], choices
    assert [c.label for c in choices] == ["this machine", "Modal", "your cloud account"], choices
    assert all(c.available for c in choices), choices
    clouds = {c.key: c for c in choices[2].clouds}
    assert list(clouds) == ["aws", "gcp", "azure"], clouds
    assert clouds["aws"].offered and clouds["aws"].label == "AWS", clouds["aws"]
    assert [clouds[k].line for k in ("gcp", "azure")] == NOT_YET, clouds
    assert not clouds["gcp"].offered and not clouds["azure"].offered


def test_w6_on_windows_the_cloud_is_shown_as_not_available_and_cannot_be_chosen(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = example(w)
    with monkeypatch.context() as inner:
        simulate_windows(inner)
        cloud = where_module().choices()[2]
        chosen = run(w, "where", "cloud", *ALL_FLAGS, "--yes")
        typed = asked(w, "init", "--example", "--out", "second.toml", typed="3\n\n")
    assert not cloud.available and cloud.line == ON_WINDOWS, cloud
    assert chosen.code == 1 and len(chosen.errors) == 1 and "Windows" in chosen.errors[0], chosen
    assert w.spec.read_bytes() == before
    assert flat(ON_WINDOWS) in flat(typed.err), typed.err
    assert "3 your cloud account" not in typed.err, typed.err
    assert "cloud" not in loaded(w.root / "second.toml"), "the cloud was chosen on Windows"
    assert w.aws_calls() == [] and w.software_starts() == [], (w.aws_calls(), w.software_starts())


def test_w6_a_cloud_not_offered_cannot_be_typed_at_the_question(w: CloudWorld) -> None:
    """Only AWS is offered, so answer 3 asks no "which cloud": the five questions follow at once."""
    done = asked(w, "init", "--example", typed="3\n" + "\n" * len(CLOUD_PROMPTS))
    err = flat(done.err)
    asked_first = err[len(flat(QUESTION)):err.index(CLOUD_PROMPTS[0])]
    for line in NOT_YET:
        asked_first = asked_first.replace(flat(line), "")
    assert asked_first.strip() == "", f"something was asked before the region: {asked_first!r}"
    assert loaded(w.spec)["cloud"]["provider"] == "aws"


# ---------- W9: the module's checks ----------


def test_w9_the_modules_check_gives_each_result_with_its_one_fixing_command(w: CloudWorld) -> None:
    where = where_module()
    results = where.check("cloud", DEFAULT_CLOUD)
    assert results and all(r.ok for r in results), [(r.label, r.ok, r.value) for r in results]
    signed = next(r for r in results if r.label == "signed in")
    assert signed.value == f"AWS {MASKED}" and signed.next is None, signed
    assert [c["argv"] for c in w.aws_calls()] == [STS, QUOTA], w.aws_calls()
    w.aws_state(signed_in=False)
    failed = [r for r in where.check("cloud", DEFAULT_CLOUD) if not r.ok]
    assert [r.next for r in failed] == ["aws login"], [(r.label, r.next) for r in failed]
    assert where.check("local", {}) == [] or all(r.ok for r in where.check("local", {}))
    assert ACCOUNT not in repr([(r.label, r.value, r.next) for r in results]), results


def test_w9_no_secret_reaches_anything_where_or_init_prints_or_writes(w: CloudWorld) -> None:
    from rb_cloud_support import secrets_in

    example(w)
    shown = ""
    for args in (("where", "cloud", *ALL_FLAGS, "--yes"), ("where",), ("where", "--json")):
        done = run(w, *args)
        shown += done.out + done.err
    shown += w.spec.read_text(encoding="utf-8")
    assert secrets_in(shown) == [], secrets_in(shown)
    for call in w.aws_calls():
        assert secrets_in(json.dumps(call["argv"])) == [], call["argv"]
    assert os.environ["AWS_SECRET_ACCESS_KEY"] not in shown
