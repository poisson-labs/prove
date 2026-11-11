"""C1 of 0.3.0, Remote backends: the backend's name, the ``[cloud]`` table and Prove's prices.

The frozen tests for N1 to N10 (Remote Backends Spec §2, §4 and §15 C1; RB-1 to RB-8, RB-25). N6
reads the cluster software's installed catalogue and lives with C3-K's contract tests
(``test_rb_cloud_contract.py``). The world is ``rb_cloud_support.py``'s: fakes only, no network.

**What the tests fix that the invariants leave open:**

- The refusals of §2.3 are the spec's lines byte for byte. A missing required key of ``[cloud]``
  is one ``error:`` line naming the key and saying it is missing; an unknown key is the strict
  spec's existing refusal (``"<key>" is not a key of [cloud]; the nearest known key is "<key>"``)
  with its line; ``head_url`` is one ``error:`` line naming the file, its line and the key and
  saying to delete it, never offering a nearest key.
- ``idle_minutes`` outside 2 to 60, ``disk_gb`` outside 10 to 2,000, ``nodes`` under 1, a
  ``max_cost`` under ``stop_cost`` and a ``provider`` other than ``aws``, ``gcp`` and ``azure``
  are each one ``error:`` line naming the key; exit 1.
- Prove's price table is ``poisson_prove._prices_cloud``: ``rows("aws")`` maps
  ``(region, machine_type)`` to a row with ``usd_per_node_hour``, ``asof`` (an ISO date) and
  ``source``; ``vcpus("aws", machine_type)`` is the type's vCPUs. A machine type outside the table
  given with the price override must also give ``slots_per_node`` and ``max_vcpus``, since Prove
  cannot know its vCPUs (yes/no).
- The name scan (N8) covers what Prove prints and serves: every verb's ``--help``, a cloud
  sweep's plan, progress, result and refusals, ``runs``, ``inspect`` and the dashboard on a cloud
  run, the terminal app's page code and the dashboard's bundle. ``README.md`` and ``docs/`` are
  C10's (D3, Pair 3).
"""

from __future__ import annotations

import ast
import importlib.machinery
import json
import re
import sys
import tomllib
import types
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import cli
from rb_cloud_support import (
    ACCOUNT,
    MACHINE,
    MASKED,
    PIN,
    PRICE,
    PRICE_DATE,
    REGION,
    REPO,
    TABLE_REGIONS,
    TYPES,
    VCPUS,
    CloudWorld,
    Pool,
    cloud_table,
    world,
)

SRC = REPO / "src" / "poisson_prove"
BURLA_TABLE = {
    "nodes": 4, "machine_type": "m7i.2xlarge", "slots_per_node": 8, "usd_per_node_hour": 0.4685,
    "price_asof": "AWS console, 2026-11-06", "ledger": "ledger.jsonl",
    "head_url": "http://localhost:5001", "stop_cost": 2.0, "max_cost": 3.0,
    "est_seconds_per_episode": 0.01,
}
REQUIRED = ("provider", "region", "machine_type", "nodes", "ledger", "stop_cost", "max_cost",
            "est_seconds_per_episode")
#: §2.5: the placement record of a new cloud run.
PLACEMENT_KEYS = {
    "provider", "region", "machine_type", "nodes", "slots_per_node", "image", "max_vcpus",
    "idle_minutes", "usd_per_node_hour", "price_asof", "estimate", "ledger", "ledger_total",
    "stop_cost", "max_cost", "func_cpu", "func_ram", "boot_minutes", "account", "engine",
}
N1_LINES = [
    "error: --backend burla is now --backend cloud, and Prove starts and stops the cluster itself",
    "  next: poisson-prove where cloud",
]


def n2_lines(line: int) -> list[str]:
    return [
        f"error: prove.toml, line {line}: [burla] is now [cloud]; rename the table, delete head_url, "
        "and add provider and region (Prove now starts the cluster on your cloud account and stops "
        "it after)",
        "  next: poisson-prove where cloud",
    ]


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Any:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


def line_of(path: Path, text: str) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() == text:
            return number
    raise AssertionError(f"{text!r} not in {path}")


def fake_modal(token: str | None) -> types.ModuleType:
    """Modal's client offline, as far as a plan reads it; its configuration holds a token or not."""
    fake = types.ModuleType("modal")
    fake.__path__ = []  # type: ignore[attr-defined]
    fake.__spec__ = importlib.machinery.ModuleSpec("modal", None, is_package=True)
    config = types.ModuleType("modal.config")
    config.config = {"token_id": token, "token_secret": None if token is None else "as-planted-secret"}  # type: ignore[attr-defined]
    fake.config = config  # type: ignore[attr-defined]
    return fake


def nothing_written(w: CloudWorld) -> list[str]:
    problems = []
    if w.store.exists():
        problems.append("the store was written")
    if w.ledger():
        problems.append("a ledger line was written")
    if w.records():
        problems.append("an ownership record was written")
    if [r for r in w.routes() if r != "head stop"]:
        problems.append(f"the cluster software was called: {w.routes()}")
    return problems


# ---------- N1: the backend's name ----------


def test_n1_backend_accepts_local_modal_and_cloud(w: CloudWorld) -> None:
    done = w.run("sweep", "--help")
    assert done.code == 0, done
    assert "--backend {local,modal,cloud}" in done.out, done.out


def test_n1_backend_burla_exits_2_with_the_two_lines_exactly(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.run("sweep", "--backend", "burla", "--target", "bu_targets.cloud:quick", "--dry-run")
    assert done.code == 2, done
    assert done.err.splitlines() == N1_LINES, done
    assert done.out == "", done
    assert nothing_written(w) == [], done


def test_n1_backend_burla_is_refused_before_the_spec_is_read(w: CloudWorld) -> None:
    """No spec here at all: the usage refusal still names the move."""
    done = w.run("sweep", "--backend", "burla")
    assert (done.code, done.err.splitlines()) == (2, N1_LINES), done


# ---------- N2: a 0.2.1 spec ----------


@pytest.mark.parametrize("backend", ["local", "modal", "cloud"])
def test_n2_the_0_2_1_table_is_refused_on_every_backend_naming_its_line(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    w.write_spec(table=BURLA_TABLE, name="burla")
    line = line_of(w.spec, "[burla]")
    # Modal with no sign-in on this machine: the spec's own refusal comes first.
    monkeypatch.setitem(sys.modules, "modal", fake_modal(None))
    monkeypatch.setitem(sys.modules, "modal.config", sys.modules["modal"].config)
    done = w.run("sweep", "prove.toml", "--target", "bu_targets.cloud:quick", "--backend", backend,
                 "--max-mde", "1", "--dry-run")
    assert done.code == 1, done
    assert done.err.splitlines() == n2_lines(line), done
    assert nothing_written(w) == [], done


def test_n2_the_0_2_1_table_is_refused_by_a_real_sweep_too_and_nothing_is_written(w: CloudWorld) -> None:
    w.write_spec(table=BURLA_TABLE, name="burla")
    line = line_of(w.spec, "[burla]")
    done = w.run("sweep", "prove.toml", "--target", "bu_targets.cloud:quick", "--backend", "cloud",
                 "--max-mde", "1", "--yes")
    assert (done.code, done.err.splitlines()) == (1, n2_lines(line)), done
    assert nothing_written(w) == [], done
    assert w.aws_calls() == [] and w.software_starts() == [], (w.aws_calls(), w.software_starts())


# ---------- N3: the [cloud] table's keys ----------


@pytest.mark.parametrize("key", REQUIRED)
def test_n3_each_required_key_missing_is_refused_by_name(w: CloudWorld, key: str) -> None:
    w.write_spec(table=cloud_table(**{key: None}))
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    assert key in done.errors[0] and "missing" in done.errors[0], done
    assert nothing_written(w) == [], done


def test_n3_an_unknown_key_is_refused_with_the_nearest_known_key(w: CloudWorld) -> None:
    w.write_spec(table={**cloud_table(), "mashine_type": "m7i.large"})
    line = line_of(w.spec, 'mashine_type = "m7i.large"')
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert done.errors == [
        f'error: prove.toml, line {line}: "mashine_type" is not a key of [cloud]; the nearest '
        'known key is "machine_type"'
    ], done


def test_n3_head_url_is_refused_naming_its_removal(w: CloudWorld) -> None:
    w.write_spec(table={**cloud_table(), "head_url": "http://localhost:5001"})
    line = line_of(w.spec, 'head_url = "http://localhost:5001"')
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    (error,) = done.errors
    assert f"prove.toml, line {line}" in error and "head_url" in error, error
    assert "delete" in error and "nearest known key" not in error, error
    assert nothing_written(w) == [], done


def test_n3_every_key_of_the_table_parses_and_reaches_the_plan(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(
        nodes=2, max_vcpus=24, slots_per_node=3, image=f"python:3.{sys.version_info.minor}",
        idle_minutes=7, boot_minutes=1.5, usd_per_node_hour=0.5, price_asof="my own reading, 2026-11-09",
        disk_gb=60, func_cpu=2, func_ram=6, batch_size=4, episode_timeout=30.0, infra_retries=1,
        max_rollouts=6,
    ))
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    cluster = next(line for line in done.out.splitlines() if line.strip().startswith("Cluster:"))
    assert "2 × m7i.2xlarge in us-east-2" in cluster, cluster
    assert "ceiling 24" in cluster and "3 slots each" in cluster and "6 at once" in cluster, cluster
    assert f"running python:3.{sys.version_info.minor}" in cluster, cluster
    assert "within 7 min" in cluster, cluster
    cost = next(line for line in done.out.splitlines() if line.strip().startswith("Cost:"))
    assert "$0.5/node-hour" in cost and "my own reading, 2026-11-09" in cost, cost


@pytest.mark.parametrize(
    ("key", "value"),
    [("idle_minutes", 1), ("idle_minutes", 61), ("disk_gb", 9), ("disk_gb", 2001), ("nodes", 0),
     ("max_cost", 1.0), ("provider", "ibm")],
)
def test_n3_a_value_outside_its_range_is_refused_by_name(w: CloudWorld, key: str, value: Any) -> None:
    w.write_spec(table=cloud_table(**{key: value}))
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1 and key in done.errors[0], done
    assert nothing_written(w) == [], done


@pytest.mark.parametrize(("key", "value"), [("idle_minutes", 2), ("idle_minutes", 60),
                                            ("disk_gb", 10), ("disk_gb", 2000)])
def test_n3_the_ends_of_each_range_are_accepted(w: CloudWorld, key: str, value: Any) -> None:
    w.write_spec(table=cloud_table(**{key: value}))
    done = w.sweep("--dry-run")
    assert done.code == 0, done


# ---------- N4: the price override comes whole ----------


@pytest.mark.parametrize("given", [{"usd_per_node_hour": 0.5}, {"price_asof": "my reading, 2026-11-09"}])
def test_n4_half_of_the_price_override_is_refused(w: CloudWorld, given: dict[str, Any]) -> None:
    w.write_spec(table=cloud_table(**given))
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    assert "usd_per_node_hour" in done.errors[0] and "price_asof" in done.errors[0], done
    assert nothing_written(w) == [], done


# ---------- N5: Prove's prices ----------


def test_n5_the_price_is_the_tables_row_and_the_plan_names_its_date(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    cost = next(line for line in done.out.splitlines() if line.strip().startswith("Cost:"))
    assert (f"1 × {MACHINE} at ${PRICE}/node-hour, Prove's AWS prices for {REGION} of {PRICE_DATE}"
            in cost), cost


def test_n5_a_machine_type_not_in_the_table_is_refused_naming_the_regions_types(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(machine_type="m7i.3xlarge"))
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert done.errors == [
        f"error: m7i.3xlarge is not in Prove's AWS prices for {REGION}; the machine types are "
        + ", ".join(TYPES)
    ], done
    assert nothing_written(w) == [], done


def test_n5_a_region_not_in_the_table_is_refused_naming_the_tables_regions(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(region="ap-south-1"))
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    assert "ap-south-1" in done.errors[0] and all(r in done.errors[0] for r in TABLE_REGIONS), done


def test_n5_the_override_prices_a_pair_outside_the_table(w: CloudWorld) -> None:
    w.aws_state(quota=64)
    w.write_spec(table=cloud_table(machine_type="m7i.12xlarge", usd_per_node_hour=2.42,
                                   price_asof="AWS console, 2026-11-09", slots_per_node=48, max_vcpus=48))
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert "1 × m7i.12xlarge at $2.42/node-hour, AWS console, 2026-11-09" in done.out, done


def test_n5_an_overridden_type_outside_the_table_must_name_its_slots_and_ceiling(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(machine_type="m7i.12xlarge", usd_per_node_hour=2.42,
                                   price_asof="AWS console, 2026-11-09"))
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    assert "slots_per_node" in done.errors[0] and "max_vcpus" in done.errors[0], done


def test_n5_the_table_holds_every_m7i_size_in_every_region_with_a_dated_source() -> None:
    from poisson_prove import _prices_cloud

    rows = _prices_cloud.rows("aws")
    assert set(rows) == {(region, kind) for region in TABLE_REGIONS for kind in TYPES}, sorted(rows)
    for (region, kind), row in rows.items():
        assert row.usd_per_node_hour > 0, (region, kind, row)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row.asof), (region, kind, row)
        assert "Price List" in row.source, (region, kind, row)
        assert _prices_cloud.vcpus("aws", kind) == VCPUS[kind]
    row = rows[(REGION, MACHINE)]
    assert (row.usd_per_node_hour, row.asof) == (PRICE, PRICE_DATE), row
    assert _prices_cloud.rows("gcp") == {} and _prices_cloud.rows("azure") == {}


# ---------- N7: the extra ----------


def _extras() -> dict[str, list[str]]:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return {name: sorted(reqs) for name, reqs in data["project"]["optional-dependencies"].items()}


def test_n7_the_cloud_extra_and_the_old_alias_install_the_same_set_and_all_includes_it() -> None:
    extras = _extras()
    assert extras["cloud"] == sorted(["burla==1.8.4", "botocore[crt]>=1.42.39"]), extras
    assert extras["burla"] == extras["cloud"], extras
    assert set(extras["cloud"]) <= set(extras["all"]), extras


def test_n7_the_wheels_metadata_says_so() -> None:
    """Read the way the build reads it: hatchling's own metadata of this checkout."""
    from hatchling.metadata.core import ProjectMetadata
    from hatchling.metadata.spec import construct_metadata_file_2_4

    metadata = ProjectMetadata(str(REPO), None)
    text = construct_metadata_file_2_4(metadata)
    extras = re.findall(r"^Provides-Extra: (\S+)$", text, re.M)
    assert "cloud" in extras and "burla" in extras, extras
    requires = re.findall(r"^Requires-Dist: (.+)$", text, re.M)
    for extra in ("cloud", "burla", "all"):
        assert f"burla==1.8.4; extra == '{extra}'" in requires, (extra, requires)
        assert f"botocore[crt]>=1.42.39; extra == '{extra}'" in requires, (extra, requires)


# ---------- N8: the name scan ----------


BURLA = re.compile("burla", re.I)


def _verbs() -> list[str]:
    return sorted(cli._VERBS)  # noqa: SLF001


def _allowed(line: str) -> bool:
    """§2.6's places a user can read: the refusals that repeat what was typed (N1, N2), and the one
    disclosure of who carries the reader's code and data (the plan's Traffic line, RB-9)."""
    if line.strip() in N1_LINES[0] or line.startswith("error: prove.toml, line") and "[burla] is now [cloud]" in line:
        return True
    return line.strip().startswith("Traffic: ") and "through Burla's relay (the cluster software Prove uses)" in line


def test_n8_no_verbs_help_names_the_cluster_software(w: CloudWorld) -> None:
    found = []
    for argv in [["--help"], *[[verb, "--help"] for verb in _verbs()]]:
        done = w.run(*argv)
        found += [f"{' '.join(argv)}: {line}" for line in (done.out + done.err).splitlines() if BURLA.search(line)]
    assert found == []


def test_n8_a_cloud_sweeps_plan_progress_result_and_reads_name_it_only_in_the_traffic_line(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    seen = [w.sweep("--dry-run"), w.sweep()]
    (run,) = w.runs()
    seen += [w.run("runs"), w.run("runs", "--json"), w.run("inspect", run["run_id"], "--event", "fell"),
             w.run("inspect", run["run_id"], "--event", "fell", "--json"), w.run("ui", "--json")]
    found = [line for done in seen for line in (done.out + done.err).splitlines()
             if BURLA.search(line) and not _allowed(line)]
    assert found == [], found
    assert any(_allowed(line) for line in seen[0].out.splitlines()), seen[0]
    pages = [p for p in (w.store / ".poisson" / "ui").rglob("*") if p.is_file()]
    assert pages, "the dashboard wrote no page"
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        assert not BURLA.search(text), (page, BURLA.findall(text)[:3])


def test_n8_the_refusals_of_a_cloud_sweep_do_not_name_it(w: CloudWorld) -> None:
    cases = [
        dict(table=cloud_table(provider="gcp")),
        dict(table=cloud_table(machine_type="m7i.3xlarge")),
        dict(table=cloud_table(nodes=6, max_vcpus=32)),
        dict(table=cloud_table(image="python:3.9")),
    ]
    found = []
    for case in cases:
        w.write_spec(**case)
        done = w.sweep("--dry-run")
        assert done.code == 1, done
        found += [line for line in done.err.splitlines() if BURLA.search(line)]
    w.write_spec(table=cloud_table())
    w.remove_cli("aws")
    done = w.sweep("--dry-run")
    found += [line for line in done.err.splitlines() if BURLA.search(line)]
    assert found == []


def _string_constants(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
    }
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings]


#: The faces' own modules: every string a user can read on a page of the terminal app, the
#: dashboard and the command line's renderings is a constant of one of these.
FACES = ("_cli_app.py", "_cli_app_pages.py", "_render_ui.py", "_render_term.py", "_render_pretty.py",
         "_look.py", "_render_charts.py", "_banner.py")


def test_n8_the_terminal_app_and_the_dashboard_hold_no_string_naming_it() -> None:
    found = [f"{name}:{line}: {text!r}" for name in FACES for line, text in _string_constants(SRC / name)
             if BURLA.search(text)]
    bundle = SRC / "_ui_bundle"
    found += [str(p) for p in bundle.rglob("*") if p.is_file()
              and BURLA.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert found == []


# ---------- N9: a stored 0.2.1 run ----------


def _make_burla_run(w: CloudWorld) -> tuple[str, bytes]:
    """A run stored as 0.2.1's cluster backend stored it: a local run whose manifest is rewritten
    with ``backend: "burla"`` and 0.2.1's placement record."""
    w.spec.write_text(
        'target_id = "rb-cloud@v0"\nt_unit = "steps"\nreplicates = 2\n\n[axes.cell]\n'
        'type = "categorical"\nvalues = ["a", "b"]\n', encoding="utf-8")
    done = w.run("sweep", "prove.toml", "--target", "bu_targets.cloud:quick", "--max-mde", "1", "--yes")
    assert done.code == 0, done
    (run,) = w.runs()
    path = w.store / run["run_id"] / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["backend"] = "burla"
    manifest["environment"]["burla"] = {**BURLA_TABLE, "pin": PIN, "estimate": 0.31, "ledger_total": 0.0}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run["run_id"], path.read_bytes()


def test_n9_a_run_stored_by_0_2_1s_cluster_backend_reads_as_cloud_everywhere_and_stays_byte_identical(w: CloudWorld) -> None:
    run_id, before = _make_burla_run(w)
    runs_text = w.run("runs")
    runs_json = w.run("runs", "--json")
    inspect_text = w.run("inspect", run_id, "--event", "fell")
    inspect_json = w.run("inspect", run_id, "--event", "fell", "--json")
    ui = w.run("ui", "--json")
    for done in (runs_text, runs_json, inspect_text, inspect_json, ui):
        assert done.code == 0, done
        assert not BURLA.search(done.out + done.err), done
    assert [r["backend"] for r in json.loads(runs_json.out)["runs"]] == ["cloud"], runs_json.out
    assert '"burla"' not in inspect_json.out, inspect_json.out
    pages = [p for p in (w.store / ".poisson" / "ui").rglob("*.html")]
    assert pages and not any(BURLA.search(p.read_text(encoding="utf-8")) for p in pages), pages
    assert any("cloud" in p.read_text(encoding="utf-8") for p in pages), pages
    assert (w.store / run_id / "manifest.json").read_bytes() == before


def test_n9_the_app_reads_the_run_as_cloud(w: CloudWorld) -> None:
    """The terminal app's runs page and run page render the core's views (``core.view``)."""
    from poisson_prove import core

    run_id, before = _make_burla_run(w)
    for address in ("index.html", f"runs/{run_id}.html"):
        text = json.dumps(core.view(str(w.store), address).to_json(), default=str)
        assert not BURLA.search(text), (address, text[:2000])
        assert '"cloud"' in text, (address, text[:2000])
    assert (w.store / run_id / "manifest.json").read_bytes() == before


# ---------- N10: a new cloud run's manifest ----------


def test_n10_a_new_cloud_runs_manifest_records_cloud_its_placement_and_the_engine(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 0, done
    (run,) = w.runs()
    manifest = w.manifest(run["run_id"])
    assert manifest["backend"] == "cloud", manifest["backend"]
    environment = manifest["environment"]
    assert "burla" not in environment, sorted(environment)
    placement = environment["cloud"]
    assert set(placement) == PLACEMENT_KEYS, sorted(set(placement) ^ PLACEMENT_KEYS)
    assert placement["engine"] == {"name": "burla", "version": PIN}, placement["engine"]
    assert placement["account"] == MASKED and ACCOUNT not in json.dumps(manifest), placement["account"]
    assert (placement["provider"], placement["region"], placement["machine_type"], placement["nodes"]) == (
        "aws", REGION, MACHINE, 1)
    assert placement["usd_per_node_hour"] == PRICE and PRICE_DATE in placement["price_asof"], placement
    assert placement["slots_per_node"] == VCPUS[MACHINE] and placement["max_vcpus"] == VCPUS[MACHINE], placement
    assert placement["image"] == f"python:3.{sys.version_info.minor}", placement
    assert "bundle" in environment, sorted(environment)
