"""Prove's dated price table for the clouds it offers, as it carries Modal's prices.

Per region and machine type, one per-node-hour figure: the on-demand price of the machine (Linux,
shared tenancy), plus its public IPv4 address, plus its disk. A region or machine type outside
the table needs ``usd_per_node_hour`` and ``price_asof`` in the ``[cloud]`` table.

The AWS rows are read from AWS's public price list, the offer files under
``https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/``, which need no account:
``AmazonEC2/current/<region>/index.csv`` for the machines and the disk, and
``AmazonVPC/current/index.csv`` for the address. The disk is the volume the cluster software asks
for, priced at 50 GB: a gp3 volume with 4,000 IOPS and 1,000 MiB/s, so 50 GB of storage, the
1,000 IOPS over gp3's free 3,000 and the 875 MiB/s over its free 125, a month taken as 730
hours.
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
_DISK_GB = 50
_DISK_IOPS_BILLED = 4000 - 3000
_DISK_MIBPS_BILLED = 1000 - 125
_HOURS_PER_MONTH = 730


@dataclass(frozen=True)
class PriceRow:
    usd_per_node_hour: float
    asof: str
    source: str


def _aws() -> dict[tuple[str, str], PriceRow]:
    out = {}
    for region, (large, per_gb, per_iops, per_gibps, address) in _AWS_REGIONS.items():
        disk = (
            _DISK_GB * per_gb + _DISK_IOPS_BILLED * per_iops + _DISK_MIBPS_BILLED * per_gibps / 1024
        ) / _HOURS_PER_MONTH
        for kind, vcpus in _AWS_VCPUS.items():
            machine = large * vcpus / _AWS_VCPUS["m7i.large"]
            asof = _AWS_ASOF_ROW.get((region, kind), _AWS_ASOF)
            out[(region, kind)] = PriceRow(round(machine + address + disk, 4), asof, _AWS_SOURCE)
    return out


_TABLES: dict[str, dict[tuple[str, str], PriceRow]] = {"aws": _aws(), "gcp": {}, "azure": {}}


def rows(provider: str) -> dict[tuple[str, str], PriceRow]:
    """``{(region, machine_type): row}`` for ``provider``; empty for a cloud not priced yet."""
    return dict(_TABLES.get(provider, {}))


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
