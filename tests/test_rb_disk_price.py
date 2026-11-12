"""The disk in Prove's cloud price (0.3.0, ruled 2026-11-09).

Each row of Prove's AWS table prices a node's disk at the size the cluster software boots it with
``disk_gb`` unset: 20 GB plus the machine's RAM. A ``disk_gb`` the reader sets is priced at
``disk_gb`` plus the RAM, never under the image's 20 GB. The plan's ``Cost:`` line and ``--json``'s
``plan.cloud.disk_gb_priced`` say which size was priced; a price the reader gives prices no disk
of Prove's. Prove sends the disk on every cloud sweep, 20 when the spec leaves ``disk_gb`` unset (ruled
2026-11-12): the software keeps its settings per account across coordinators, so an earlier
sweep's ``disk_gb`` would otherwise boot under a price for the default.

The boot size is read from the installed ``burla==1.8.4``'s own files (parsed as text, never
imported, as C3-K reads them); where the cloud extra is not installed at the pin that test is
skipped with the reason. The table is pinned row by row to the figures AWS's public price list
gives: the offer files AmazonEC2 20261107002852 (read again at 20261110173852, unchanged) and
AmazonVPC 20261105181945.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import _look
from rb_cloud_support import (
    MACHINE,
    PIN,
    PRICE,
    PRICE_DATE,
    REGION,
    TABLE_REGIONS,
    TYPES,
    CloudWorld,
    Pool,
    cloud_table,
    world,
)

#: ``(usd_per_node_hour, disk GB)`` per machine type, in ``TYPES``'s order: the machine, its
#: public IPv4 address and a gp3 disk of 20 GB plus the RAM at 4,000 IOPS and 1,000 MiB/s.
_US = [(0.1637, 28), (0.2653, 36), (0.4687, 52), (0.8754, 84), (1.6888, 148), (3.3156, 276)]
TABLE = {
    "us-east-1": _US,
    "us-east-2": _US,
    "us-west-2": _US,
    "eu-west-1": [(0.181, 28), (0.2943, 36), (0.5209, 52), (0.9742, 84), (1.8807, 148), (3.6937, 276)],
    "eu-central-1": [(0.1947, 28), (0.3165, 36), (0.5601, 52), (1.0472, 84), (2.0216, 148),
                     (3.9703, 276)],
}
#: us-east-2 m7i.2xlarge with ``disk_gb = 500``: 532 GB of disk.
PRICE_500 = 0.5213


def _installed() -> importlib.metadata.Distribution | None:
    try:
        dist = importlib.metadata.distribution("burla")
    except importlib.metadata.PackageNotFoundError:
        return None
    return dist if dist.version == PIN else None


DIST = _installed()


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


def _cost(out: str) -> str:
    return next(line.strip() for line in out.splitlines() if line.strip().startswith("Cost:"))


# ---------- the boot size, from the pin's own files ----------


@pytest.mark.skipif(DIST is None, reason=f"reads the installed burla=={PIN}, which the cloud extra "
                    'installs (pip install -e ".[cloud]"); it is not installed at the pin here')
def test_the_boot_size_is_the_pins_twenty_gb_or_disk_gb_plus_the_ram() -> None:
    assert DIST is not None

    def text(rel: str) -> str:
        path = Path(str(DIST.locate_file(rel)))
        assert path.is_file(), f"burla {PIN} has no {rel}"
        return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))

    node = text("main_service/node.py")
    assert "self.disk_size = ( disk_size if disk_size else 20 )" in node
    assert 'disk_size=self.disk_size + machine_spec(machine_type)["ram_gb"]' in node
    lifecycle = text("main_service/endpoints/cluster_lifecycle.py")
    assert 'disk_size=node_spec.get("disk_size_gb")' in lifecycle
    assert '"disk_gb": "disk_size_gb"' in text("main_service/endpoints/management.py")
    aws = text("main_service/providers/aws.py")
    assert '"VolumeSize": max(disk_size, 20), "VolumeType": "gp3",' in aws
    assert '"Iops": 4000, "Throughput": 1000,' in aws
    catalog = text("main_service/providers/catalog.py")
    m7i = catalog[catalog.index('machine_type.startswith("m7i.")'):]
    assert re.match(r'.{0,200}return \{"cpus": cpus, "ram_gb": cpus \* 4, "gpus": 0\}', m7i), m7i[:300]


# ---------- the table ----------


def test_every_row_prices_the_disk_the_software_boots_with_disk_gb_unset() -> None:
    from poisson_prove import _prices_cloud

    rows = _prices_cloud.rows("aws")
    got = {region: [(rows[(region, kind)].usd_per_node_hour, rows[(region, kind)].disk_gb)
                    for kind in TYPES] for region in TABLE_REGIONS}
    assert got == TABLE, got
    assert (rows[(REGION, MACHINE)].usd_per_node_hour, rows[(REGION, MACHINE)].asof) == (PRICE, PRICE_DATE)
    assert PRICE == 0.4687


def test_disk_gb_is_priced_at_disk_gb_plus_the_ram_never_under_the_images_twenty() -> None:
    from poisson_prove import _prices_cloud

    row = _prices_cloud.price("aws", REGION, MACHINE, 500)
    assert row is not None and (row.usd_per_node_hour, row.disk_gb, row.asof) == (PRICE_500, 532, PRICE_DATE)
    assert _prices_cloud.price("aws", REGION, MACHINE, None) == _prices_cloud.rows("aws")[(REGION, MACHINE)]
    assert _prices_cloud.boot_disk_gb("aws", "m7i.large", 10) == 20
    assert _prices_cloud.boot_disk_gb("aws", "m7i.large", 13) == 21
    assert _prices_cloud.boot_disk_gb("aws", "m7i.16xlarge", 2000) == 2256
    assert _prices_cloud.boot_disk_gb("aws", "m7i.3xlarge", 40) is None
    assert _prices_cloud.price("aws", REGION, "m7i.3xlarge", 40) is None


# ---------- the plan ----------


def test_the_plan_prices_disk_gb_and_says_the_size_priced(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(nodes=2, disk_gb=500))
    plan = w.sweep("--dry-run")
    assert plan.code == 0, plan
    cost = _cost(plan.out)
    assert (f"2 × {MACHINE} at ${PRICE_500}/node-hour, Prove's AWS prices for {REGION} of {PRICE_DATE}, "
            "each node's disk priced at 532 GB)") in cost, cost
    assert "each node's disk priced at 532 GB" in plan.out.splitlines()[0], plan.out
    as_json = w.sweep("--dry-run", "--json")
    assert as_json.code == 0, as_json
    cloud = json.loads(as_json.out)["plan"]["cloud"]
    assert (cloud["usd_per_node_hour"], cloud["disk_gb_priced"]) == (PRICE_500, 532), cloud
    # The estimate is the 0.2.1 formula at the disk_gb price: 2 nodes, the cheap table's
    # allowances (boot 0, idle 2 min) and a few seconds of rollouts.
    assert cloud["estimate"] == pytest.approx(2 * PRICE_500 * (0 + 2 * 0.01 / 60 + 2) / 60), cloud
    assert f"~{_look.fmt_dollars(cloud['estimate'])} this run" in cost, cost


def test_the_plan_without_disk_gb_says_the_default_size_priced(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    as_json = w.sweep("--dry-run", "--json")
    assert as_json.code == 0, as_json
    cloud = json.loads(as_json.out)["plan"]["cloud"]
    assert (cloud["usd_per_node_hour"], cloud["disk_gb_priced"]) == (PRICE, 52), cloud
    assert any(line.endswith("each node's disk priced at 52 GB) · ledger ledger.jsonl $0 so far · "
                             "stop $5.00 · cap $5.00")
               for line in json.loads(as_json.out)["plan"]["lines"]), as_json.out


def test_a_price_the_reader_gives_prices_no_disk_of_proves(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(disk_gb=500, usd_per_node_hour=0.9, price_asof="my bill, 2026-11-10"))
    as_json = w.sweep("--dry-run", "--json")
    assert as_json.code == 0, as_json
    cloud = json.loads(as_json.out)["plan"]["cloud"]
    assert (cloud["usd_per_node_hour"], cloud["disk_gb_priced"]) == (0.9, None), cloud
    assert "disk priced" not in as_json.out, as_json.out


def test_a_done_sweep_with_disk_gb_charges_and_records_the_disk_gb_price(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(disk_gb=500))
    done = w.sweep()
    assert done.code == 0, done
    (run,) = w.runs()
    placement = w.manifest(run["run_id"])["environment"]["cloud"]
    assert placement["usd_per_node_hour"] == PRICE_500, placement
    opened = w.ledger()
    assert [e["usd_per_node_hour"] for e in opened if e.get("event") == "open"] == [PRICE_500], opened


def test_an_earlier_sweeps_disk_gb_is_not_kept_a_sweep_without_it_sends_twenty(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(disk_gb=500))
    assert w.sweep().code == 0
    assert w.cluster()["settings"]["disk_gb"] == 500, w.cluster()["settings"]
    w.write_spec(table=cloud_table())
    plan = w.sweep("--dry-run", "--json")
    assert plan.code == 0, plan
    cloud = json.loads(plan.out)["plan"]["cloud"]
    assert (cloud["usd_per_node_hour"], cloud["disk_gb_priced"]) == (PRICE, 52), cloud
    assert w.sweep().code == 0
    updates = [e for e in w.management() if e["route"] == "PATCH /v1/management/settings"]
    assert [u["body"]["disk_gb"] for u in updates] == [500, 20], updates
    assert w.cluster()["settings"]["disk_gb"] == 20, w.cluster()["settings"]
