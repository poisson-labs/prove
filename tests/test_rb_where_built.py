"""C5 of 0.3.0, Remote backends: what the build of where a sweep runs does beyond its frozen
tests.

Added by ruling (2026-11-11) from the build's own checks: the cases the frozen tests of
``test_rb_where.py`` left open, and what the module's write keeps. They were written by the
builder, after the build, and no mutation pass stands behind them.

- **The write** keeps the reader's comments, spacing and key order inside a table it changes;
  moves a 0.2 table in place with the new keys first; keeps a file's own line endings and mode,
  and leaves no temporary file; falls back to the whole table for a value over several lines.
- **The ceiling** follows the nodes only when it was following them.
- **The command line:** bare ``where`` on a 0.2 table; ``where modal --yes`` with no cap, and
  with one; ``--spec`` for a spec other than the folder's; ``init --runs-on`` under ``--json``;
  an option given with the wrong answer; a number out of its range; what ``where local`` says;
  the document ``where --json`` prints when it sets.
- **The app:** ``w`` opens the page from home once runs exist.

On the fakes of ``rb_cloud_support.py``. No network, no cloud, no Modal. The cases that start
the fake coordinator are ``test_rb_where_built_cluster.py``.
"""

from __future__ import annotations

import io
import json
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import Session, says
from poisson_prove import _where, cli
from rb_cloud_support import CloudWorld, Done, Pool, world
from test_rb_cloud_readiness import install_modal
from test_rb_where import ALL_FLAGS, BURLA_OLD, DEFAULT_CLOUD, HEAD, TAIL
from test_rb_where_app import in_app, leave


@pytest.fixture(autouse=True)
def _app_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME", "NO_COLOR", "CI", "TEXTUAL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fresh_pool() -> Any:
    own = Pool(2)
    yield own
    own.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_pool: Pool) -> Iterator[CloudWorld]:
    monkeypatch.setenv("COLUMNS", "250")
    with world(tmp_path, monkeypatch, fresh_pool) as made:
        made.store = made.root / "prove-runs"
        yield made


def run(w: CloudWorld, *args: str, stdin: io.StringIO | None = None) -> Done:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), stdout=out, stderr=err, stdin=stdin or io.StringIO(""))
    return Done(code, out.getvalue(), err.getvalue())


# ---------- the module's write ----------

COMMENTED = '''
# Where it runs: the lab account.
[cloud]   # ours
provider = "aws"
region = "eu-west-1"      # nearest to the data
machine_type = "m7i.xlarge"

# two is enough for now
nodes = 2   # raise for the big sweep
ledger = "spend.jsonl"
stop_cost = 1.0
max_cost = 1.5
est_seconds_per_episode = 0.25
'''


def test_write_keeps_the_readers_comments_spacing_and_order_inside_the_table(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(HEAD + COMMENTED + TAIL, encoding="utf-8")
    old = tomllib.loads(COMMENTED)["cloud"]
    _where.write(spec, _where.table("cloud", _where.cloud_answers(old, {"nodes": 3})))
    text = spec.read_text(encoding="utf-8")
    assert text == (HEAD + COMMENTED + TAIL).replace("nodes = 2   # raise", "nodes = 3   # raise"), text


def test_write_moves_a_burla_table_in_place_with_the_new_keys_first(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(HEAD + BURLA_OLD + TAIL, encoding="utf-8")
    old = tomllib.loads(BURLA_OLD)["burla"]
    _where.write(spec, _where.table("cloud", _where.cloud_answers(old, {"region": "us-west-2"})))
    text = spec.read_text(encoding="utf-8")
    body = text[len(HEAD): len(text) - len(TAIL)].strip().splitlines()
    assert body[:3] == ["[cloud]", 'provider = "aws"', 'region = "us-west-2"'], body
    kept = [line for line in BURLA_OLD.strip().splitlines()[1:] if not line.startswith("head_url")]
    assert body[3:] == kept, body


def test_write_keeps_a_files_own_line_endings(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_bytes((HEAD + TAIL).replace("\n", "\r\n").encode())
    _where.write(spec, _where.table("cloud", DEFAULT_CLOUD))
    data = spec.read_bytes()
    assert data.startswith((HEAD + TAIL).replace("\n", "\r\n").encode())
    assert b"\n" not in data.replace(b"\r\n", b""), "a bare newline in a CRLF file"
    assert tomllib.loads(data.decode())["cloud"] == DEFAULT_CLOUD
    _where.write(spec, "")
    assert spec.read_bytes() == (HEAD + TAIL).replace("\n", "\r\n").encode()


def test_write_leaves_no_temporary_file_and_keeps_the_mode(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    spec.write_text(HEAD + TAIL, encoding="utf-8")
    spec.chmod(0o640)
    _where.write(spec, _where.table("cloud", DEFAULT_CLOUD))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["prove.toml"]
    assert spec.stat().st_mode & 0o777 == 0o640


def test_a_value_over_several_lines_falls_back_to_the_whole_table(tmp_path: Path) -> None:
    spec = tmp_path / "prove.toml"
    old = '\n[cloud]\nprovider = "aws"\npackages = [\n  "pkg",\n]\nregion = "us-east-2"\n'
    spec.write_text(HEAD + old + TAIL, encoding="utf-8")
    _where.write(spec, _where.table("cloud", DEFAULT_CLOUD))
    text = spec.read_text(encoding="utf-8")
    assert text.startswith(HEAD) and text.endswith(TAIL)
    assert tomllib.loads(text)["cloud"] == DEFAULT_CLOUD


def test_a_ceiling_the_reader_set_stays_and_one_that_followed_follows() -> None:
    followed = _where.cloud_answers({**DEFAULT_CLOUD}, {"nodes": 2})
    assert followed["max_vcpus"] == 16
    own = _where.cloud_answers({**DEFAULT_CLOUD, "max_vcpus": 40}, {"nodes": 2})
    assert own["max_vcpus"] == 40


# ---------- the command line ----------


def test_bare_where_on_a_burla_spec_is_not_ready_exit_0_and_names_the_move(w: CloudWorld) -> None:
    w.spec.write_text(HEAD + BURLA_OLD + TAIL, encoding="utf-8")
    before = w.spec.read_bytes()
    done = run(w, "where")
    assert done.code == 0, done
    first = done.out.splitlines()[0]
    assert first.startswith("where  your cloud account, by a [burla] table of 0.2; not ready: "), done
    assert done.nexts == ["next: poisson-prove where cloud"], done
    assert w.spec.read_bytes() == before and w.aws_calls() == []
    doc = json.loads(run(w, "where", "--json").out)
    assert doc["ready"] is False and doc["next"] == ["poisson-prove where cloud"], doc


def test_where_modal_yes_with_no_cap_writes_the_table_alone(w: CloudWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    install_modal(monkeypatch, "ak-planted-modal-token-id-0000")
    assert run(w, "init", "--example").code == 0
    done = run(w, "where", "modal", "--yes")
    assert done.code == 0 and done.err == "", done
    assert tomllib.loads(w.spec.read_text())["modal"] == {}, w.spec.read_text()
    assert done.nexts == ["next: poisson-prove sweep --dry-run"], done
    capped = run(w, "where", "modal", "--max-cost", "5", "--yes")
    assert capped.code == 0 and capped.err == "", capped
    assert tomllib.loads(w.spec.read_text())["modal"] == {"max_cost": 5.0, "est_seconds_per_episode": 1.0}


def test_where_takes_a_spec_other_than_the_folders_and_names_it_after(w: CloudWorld) -> None:
    assert run(w, "init", "--example", "--out", "u.toml").code == 0
    done = run(w, "where", "cloud", "--spec", "u.toml", *ALL_FLAGS, "--yes")
    assert done.code == 0, done
    assert "  wrote  [cloud] into u.toml" in done.out.splitlines(), done
    assert done.nexts == ["next: poisson-prove sweep u.toml --dry-run"], done
    assert tomllib.loads((w.root / "u.toml").read_text())["cloud"] == DEFAULT_CLOUD
    assert not w.spec.exists()
    bare = run(w, "where", "--spec", "u.toml")
    assert bare.code == 0 and bare.nexts == ["next: poisson-prove sweep u.toml"], bare
    missing = run(w, "where", "--spec", "none.toml")
    assert missing.code == 1 and missing.nexts == ["next: poisson-prove init --out none.toml"], missing
    made = run(w, "init", "--example", "--out", "v.toml", "--runs-on", "cloud")
    assert made.code == 0 and made.nexts == ["next: poisson-prove sweep v.toml --dry-run"], made


def test_init_runs_on_under_json_is_one_document_that_says_where(w: CloudWorld) -> None:
    done = run(w, "init", "--example", "--runs-on", "cloud", "--json")
    assert done.code == 0 and done.err == "", done
    doc = json.loads(done.out)
    assert doc["schema"] == "poisson-prove.init/1" and doc["wrote"] == ["prove.toml"], doc
    assert doc["runs_on"] == "cloud" and doc["ready"] is True, doc
    assert doc["next"] == ["poisson-prove sweep --dry-run"], doc
    assert tomllib.loads(w.spec.read_text())["cloud"] == DEFAULT_CLOUD
    w.aws_state(signed_in=False)
    done = run(w, "init", "--example", "--runs-on", "cloud", "--json", "--force")
    doc = json.loads(done.out)
    assert doc["ready"] is False and doc["next"] == ["aws login"], doc
    plain = json.loads(run(w, "init", "--example", "--json", "--force").out)
    assert "runs_on" not in plain and "ready" not in plain, plain


@pytest.mark.parametrize("args,flag", [
    (("where", "--region", "us-east-2"), "--region"),
    (("where", "local", "--nodes", "3"), "--nodes"),
    (("where", "modal", "--stop-cost", "2"), "--stop-cost"),
    (("where", "local", "--max-cost", "2"), "--max-cost"),
    (("where", "--yes"), "--yes"),
    (("where", "modal", "--max-cost", "-1"), "--max-cost"),
])
def test_an_option_that_goes_with_another_answer_is_a_usage_error(w: CloudWorld, args: tuple[str, ...], flag: str) -> None:
    assert run(w, "init", "--example").code == 0
    before = w.spec.read_bytes()
    done = run(w, *args)
    assert done.code == 2 and len(done.errors) == 1 and flag in done.errors[0], done
    assert w.spec.read_bytes() == before


def test_a_number_out_of_its_range_is_refused_and_nothing_is_written(w: CloudWorld) -> None:
    assert run(w, "init", "--example").code == 0
    before = w.spec.read_bytes()
    for flags in (["--nodes", "0"], ["--stop-cost", "5", "--max-cost", "3"]):
        done = run(w, "where", "cloud", *flags, "--yes")
        assert done.code == 1 and len(done.errors) == 1, done
        assert w.spec.read_bytes() == before


def test_where_local_says_what_it_took_out(w: CloudWorld) -> None:
    assert run(w, "init", "--example").code == 0
    assert run(w, "where", "cloud", *ALL_FLAGS, "--yes").code == 0
    done = run(w, "where", "local")
    assert "  wrote  prove.toml without [cloud]" in done.out.splitlines(), done
    again = run(w, "where", "local")
    assert "wrote" not in again.out, again


def test_where_json_when_setting_carries_what_was_written_and_the_checks(w: CloudWorld) -> None:
    assert run(w, "init", "--example").code == 0
    doc = json.loads(run(w, "where", "cloud", *ALL_FLAGS, "--yes", "--json").out)
    assert doc["runs_on"] == "cloud" and doc["ready"] is True and doc["wrote"] == ["prove.toml"], doc
    assert [c["label"] for c in doc["checks"]] == ["signed in"], doc


# ---------- the app ----------


def test_w_opens_the_page_from_home_once_runs_exist(w: CloudWorld) -> None:
    assert run(w, "init", "--example").code == 0
    assert run(w, "--store", str(w.store), "sweep", "--yes", "--max-mde", "1").code == 0

    async def scenario(s: Session) -> tuple[str, str]:
        home = await s.wait_title("home")
        await s.press("w")
        page = await s.wait(lambda g: g.title() == "where" and says(g.text(), "this machine"), 60, "the page")
        await leave(s)
        return home.text(), page.text()

    rc, (home, page) = in_app(w, scenario)
    assert rc == 0
    assert "press w" not in home, "the first-run line is for a store with no runs"
    assert says(page, "where this machine")
