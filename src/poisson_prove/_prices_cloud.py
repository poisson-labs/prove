"""Prove's dated price table for the clouds it offers, as it carries Modal's prices.

Per region and machine type, one per-node-hour figure: the on-demand price of the machine (Linux,
shared tenancy), plus its public IPv4 address, plus its disk at the size the cluster software
boots it. A region or machine type outside the table needs ``usd_per_node_hour`` and
``price_asof`` in the ``[cloud]`` table.

The AWS rows are read from AWS's public price list, the offer files under
``https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/``, which need no account:
``AmazonEC2/current/<region>/index.csv`` for the machines and the disk, and
``AmazonVPC/current/index.csv`` for the address. The disk is the volume the cluster software asks
for: a gp3 volume with 4,000 IOPS and 1,000 MiB/s, so its storage, the 1,000 IOPS over gp3's free
3,000 and the 875 MiB/s over its free 125, a month taken as 730 hours. Its size is the software's:
with ``disk_gb`` unset a node boots 20 GB plus the machine's RAM, and with ``disk_gb`` set,
``disk_gb`` plus the RAM, never under the 20 GB of the image (burla 1.8.4,
``main_service/node.py:116-118, 180``, ``main_service/providers/aws.py:89``; the RAM is 4 GB a
vCPU on ``m7i``, ``main_service/providers/catalog.py:387-392``). Each row is that unset size;
``price`` gives the figure for a ``disk_gb`` the reader sets.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The clouds a ``[cloud]`` table may name, and the ones this release offers.
PROVIDERS = ("aws", "gcp", "azure")
OFFERED = ("aws",)
NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}

_AWS_SOURCE = (
    "AWS Price List, the offer files AmazonEC2 20261107002852 and AmazonVPC 20261105181945"
)
#: The day the rows were read from the offer files.
_AWS_ASOF = "2026-11-09"
#: Rows read on an earlier day and found unchanged on ``_AWS_ASOF`` keep the day first read.
_AWS_ASOF_ROW = {("us-east-2", "m7i.2xlarge"): "2026-11-06"}

_AWS_VCPUS = {
    "m7i.large": 2,
    "m7i.xlarge": 4,
    "m7i.2xlarge": 8,
    "m7i.4xlarge": 16,
    "m7i.8xlarge": 32,
    "m7i.16xlarge": 64,
}
#: On-demand dollars per hour of ``m7i.large`` (each larger size is its vCPUs' multiple, as the
#: offer files list it), then the disk's three monthly rates (gp3 storage per GB, IOPS each,
#: throughput per GiB/s) and the public IPv4 address per hour.
_AWS_REGIONS: dict[str, tuple[float, float, float, float, float]] = {
    "us-east-1": (0.1008, 0.08, 0.005, 40.96, 0.005),
    "us-east-2": (0.1008, 0.08, 0.005, 40.96, 0.005),
    "us-west-2": (0.1008, 0.08, 0.005, 40.96, 0.005),
    "eu-west-1": (0.11235, 0.088, 0.0055, 45.056, 0.005),
    "eu-central-1": (0.12075, 0.0952, 0.006, 48.7424, 0.005),
}
#: The cluster software's disk with ``disk_gb`` unset, before it adds the machine's RAM. Prove
#: sends it when a spec leaves ``disk_gb`` unset: the software keeps its settings per account
#: across coordinators, so an earlier sweep's ``disk_gb`` would otherwise stay.
DISK_DEFAULT_GB = 20
#: The image's own disk: a smaller volume is booted at this size.
_DISK_FLOOR_GB = 20
_RAM_GB_PER_VCPU = 4
_DISK_IOPS_BILLED = 4000 - 3000
_DISK_MIBPS_BILLED = 1000 - 125
_HOURS_PER_MONTH = 730


@dataclass(frozen=True)
class PriceRow:
    usd_per_node_hour: float
    asof: str
    source: str
    #: The disk the figure prices, in GB: the size the cluster software boots each node's disk at.
    disk_gb: int


def boot_disk_gb(provider: str, machine_type: str, disk_gb: int | None = None) -> int | None:
    """The size the cluster software boots each node's disk at, in GB: ``disk_gb`` (20 when
    unset) plus the machine's RAM, never under the image's 20 GB. None for a machine type Prove's
    table does not hold."""
    vcpus_ = _AWS_VCPUS.get(machine_type) if provider == "aws" else None
    if vcpus_ is None:
        return None
    return max((disk_gb or DISK_DEFAULT_GB) + vcpus_ * _RAM_GB_PER_VCPU, _DISK_FLOOR_GB)


def _aws_row(region: str, kind: str, disk_gb: int | None) -> PriceRow:
    large, per_gb, per_iops, per_gibps, address = _AWS_REGIONS[region]
    size = boot_disk_gb("aws", kind, disk_gb) or _DISK_FLOOR_GB
    disk = (
        size * per_gb + _DISK_IOPS_BILLED * per_iops + _DISK_MIBPS_BILLED * per_gibps / 1024
    ) / _HOURS_PER_MONTH
    machine = large * _AWS_VCPUS[kind] / _AWS_VCPUS["m7i.large"]
    asof = _AWS_ASOF_ROW.get((region, kind), _AWS_ASOF)
    return PriceRow(round(machine + address + disk, 4), asof, _AWS_SOURCE, size)


def _aws() -> dict[tuple[str, str], PriceRow]:
    return {
        (region, kind): _aws_row(region, kind, None)
        for region in _AWS_REGIONS
        for kind in _AWS_VCPUS
    }


_TABLES: dict[str, dict[tuple[str, str], PriceRow]] = {"aws": _aws(), "gcp": {}, "azure": {}}


def rows(provider: str) -> dict[tuple[str, str], PriceRow]:
    """``{(region, machine_type): row}`` for ``provider``; empty for a cloud not priced yet."""
    return dict(_TABLES.get(provider, {}))


def price(
    provider: str, region: str, machine_type: str, disk_gb: int | None = None
) -> PriceRow | None:
    """The row for ``(region, machine_type)`` with its disk priced at the size the cluster
    software boots for ``disk_gb``; the table's own row when ``disk_gb`` is unset. None for a pair
    the table does not hold."""
    row = _TABLES.get(provider, {}).get((region, machine_type))
    if row is None or not disk_gb:
        return row
    return _aws_row(region, machine_type, disk_gb)


def vcpus(provider: str, machine_type: str) -> int | None:
    """The machine type's vCPUs, or None for one Prove's table does not hold."""
    return _AWS_VCPUS.get(machine_type) if provider == "aws" else None


def regions(provider: str) -> list[str]:
    seen: list[str] = []
    for region, _ in _TABLES.get(provider, {}):
        if region not in seen:
            seen.append(region)
    return seen


def machine_types(provider: str, region: str) -> list[str]:
    return [kind for (r, kind) in _TABLES.get(provider, {}) if r == region]
