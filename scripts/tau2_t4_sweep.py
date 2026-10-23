#!/usr/bin/env python3
"""Generate ``examples/tau2_pilot/t4.toml`` from τ²'s pinned airline task file.

**The rule is pre-registered; the table is not.** [[Prove — T.4 τ²-bench Pre-registration]]
§2.3 fixes a mechanical partition of the 50 airline tasks over each task's
``evaluation_criteria.actions``, and prints a table of task ids beside it that was read by hand.
This script is the rule. It reads the task file at the pinned commit, applies the rule, and
writes the sweep file; the table in the pre-registration is checked against it and any task that
moves is a finding, not a silent correction.

Run it against a checkout of sierra-research/tau2-bench at the pin::

    python scripts/tau2_t4_sweep.py --tasks <checkout>/data/tau2/domains/airline/tasks.json \
        --out examples/tau2_pilot/t4.toml

``--check`` writes nothing and exits nonzero if the committed file is not what the rule
produces, which is what makes the committed file auditable rather than merely present.

**The three junk cells are deliberate and are declared.** ``SweepSpec.load`` refuses a sweep
file with no ``[axes.*]`` table and ``[[scenarios]]`` only *adds* to the grid, so a design whose
cells carry two keys cannot be expressed as a scenario list alone. ``[axes.task_family]`` is
declared first -- so it is the first key in ``axis_types`` and the tree's axis rung resolves on
it without ``--by`` -- and its three-value grid produces three configs carrying no ``task_id``.
The wrapper raises ``KeyError`` on those, the executor records errored rows, and ``diff`` drops
them as non-comparable. Pre-registration §2.4, K8.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "examples"))

from tau2_pilot.guardrail import WRITE_TOOLS  # noqa: E402

#: The subset of ``WRITE_TOOLS`` whose call creates or destroys a reservation, rather than
#: editing one that stays. The second clause of §2.3's rule partitions on this set.
HARD_WRITES: frozenset[str] = frozenset(
    {"book_reservation", "cancel_reservation", "send_certificate"}
)

#: §2.3's three families, in the order the sweep file declares them.
FAMILIES: tuple[str, ...] = ("no_write", "modify_in_place", "cancel_or_book")

#: The commit the task file must come from. Recorded in the generated file's header, and the
#: same string the image's ``TAU2_COMMIT`` carries.
TAU2_COMMIT = "2174a603f6d014ef94473ffa95957f6ce27100db"

#: §4.4's admission rule, as constants: the resolver must admit every family at this floor.
MAX_GROUP_MDE = 0.10
Q = 0.05
N_FAMILIES = 3

TARGET_ID = "tau2-airline/gpt-4.1-mini-2025-04-14@v0"
T_UNIT = "steps"


def family_of(task: Mapping[str, Any]) -> str:
    """§2.3's rule, verbatim and total.

    ``W`` is the set of names under the task's ``evaluation_criteria.actions`` that are write
    tools. ``W`` empty is ``no_write``; ``W`` non-empty but disjoint from the hard writes is
    ``modify_in_place``; anything else is ``cancel_or_book``. There is no judgement call in it,
    and a task whose ``evaluation_criteria`` is absent has an empty action list by the same
    reading τ²'s own evaluator takes.
    """
    criteria = task.get("evaluation_criteria") or {}
    names = {action["name"] for action in (criteria.get("actions") or [])}
    writes = names & WRITE_TOOLS
    if not writes:
        return "no_write"
    if not (writes & HARD_WRITES):
        return "modify_in_place"
    return "cancel_or_book"


def classify(tasks: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {family: [] for family in FAMILIES}
    for task in tasks:
        out[family_of(task)].append(str(task["id"]))
    return out


def least_admitted_replicates(cells_in_smallest_family: int) -> tuple[int, float]:
    """The fewest replicates at which the resolver admits the binding family at the floor.

    §4.4's derivation, run rather than quoted: the resolver's own ``_group_mdes`` is the
    *unpaired* two-proportion MDE at base rate 0.5 and ``alpha = q / G``, and N is the least
    replicate count whose smallest family clears ``--max-group-mde``. Imported from
    ``poisson_prove.diff`` so the number that sizes the run and the number that admits it are the
    same function.
    """
    from poisson_prove.diff import mde_two_proportion

    alpha = Q / N_FAMILIES
    n = 1
    while n < 10_000:
        pairs = cells_in_smallest_family * n
        mde = mde_two_proportion(0.5, pairs, pairs, alpha=alpha)
        if mde <= MAX_GROUP_MDE:
            return n, mde
        n += 1
    raise SystemExit("no replicate count under 10,000 admits the binding family")


def render(
    tasks: Sequence[Mapping[str, Any]],
    families: Mapping[str, list[str]],
    replicates: int,
    digest: str,
) -> str:
    from poisson_prove.diff import mde_two_proportion
    from poisson_prove.executor import _offered_override

    alpha = Q / N_FAMILIES
    family_of_task = {tid: family for family, ids in families.items() for tid in ids}
    per_cell = mde_two_proportion(0.5, replicates, replicates)
    rows = []
    for family in FAMILIES:
        pairs = len(families[family]) * replicates
        rows.append(
            f"#   {family:<16} {len(families[family]):>2} cells  {pairs:>5} pairs  "
            f"group MDE {mde_two_proportion(0.5, pairs, pairs, alpha=alpha):.4f}"
        )
    grid_pairs = len(tasks) * replicates
    rows.append(
        f"#   {'whole grid':<16} {len(tasks):>2} cells  {grid_pairs:>5} pairs  "
        f"root  MDE {mde_two_proportion(0.5, grid_pairs, grid_pairs, alpha=Q):.4f}"
    )

    lines = [
        "# T.4 -- the confirmation sweep: 50 τ²-bench airline tasks x 3 declared families.",
        "#",
        "# GENERATED by scripts/tau2_t4_sweep.py. Do not hand-edit: the family of every task is",
        "# the pre-registration's mechanical rule over that task's evaluation_criteria.actions,",
        "# run against τ²'s own task file, and a hand edit is a silent re-pre-registration.",
        "#",
        f"#   tau2-bench commit   {TAU2_COMMIT}",
        f"#   tasks.json sha256   {digest}",
        f"#   tasks               {len(tasks)}",
        "#",
        "# The design, recomputed by the generator from poisson_prove.diff.mde_two_proportion:",
        "#",
        *rows,
        "#",
        f"#   replicates N = {replicates}: the least count at which the resolver admits the",
        f"#   binding family at --max-group-mde {MAX_GROUP_MDE:g}, alpha = q/G = {alpha:.4f}.",
        f"#   per-cell MDE at N = {replicates} is {per_cell:.4f}, so the sweep needs",
        f"#   --max-mde {_offered_override(per_cell):.4f}. That refusal is the pre-flight telling",
        "#   the truth: this is a Level 2 design and the leaves do not resolve.",
        "#",
        "# The commands (pre-registration §10). The salt is fresh; A' and B pair with A.",
        "#",
        '#   export PYTHONPATH="$PWD/examples${PYTHONPATH:+:$PYTHONPATH}"',
        "#   export POISSON_PROVE_STORE=~/code/poisson-labs/prove-runs",
        "#   export MODAL_IMAGE_BUILDER_VERSION=2024.10        # required; Dockerfile note 6",
        "#   python scripts/tau2_t4_budget.py --arm A          # the launch gate; see note below",
        "#   poisson-prove sweep examples/tau2_pilot/t4.toml \\",
        "#     --target tau2_pilot.rollout:rollout \\",
        f"#     --backend modal --max-mde {_offered_override(per_cell):.4f} --yes",
        "#",
        "# THE THREE JUNK CELLS ARE DECLARED. [axes.task_family] is required -- SweepSpec.load",
        "# refuses a file with no [axes.*] table -- and its grid produces three configs carrying",
        "# no task_id. The wrapper raises KeyError on them, the executor records errored rows,",
        "# and multi_diff filters outcome.notna() before pairing, so they are non-comparable and",
        f"# never reach the tree. n_errored = 3N = {3 * replicates} per arm, and K8 is the check.",
        "#",
        "# task_family is declared FIRST so it is the first key in axis_types and the tree's axis",
        "# rung resolves on it; the diff commands pass --by task_family anyway, so the record is",
        "# explicit either way.",
        "",
        f'target_id = "{TARGET_ID}"',
        f't_unit = "{T_UNIT}"',
        f"replicates = {replicates}",
        "",
        "[axes.task_family]",
        'type = "categorical"',
        "values = [" + ", ".join(f'"{f}"' for f in FAMILIES) + "]",
        "",
    ]

    for task in tasks:
        tid = str(task["id"])
        lines += [
            "[[scenarios]]",
            f'task_family = "{family_of_task[tid]}"',
            f'task_id = "{tid}"',
            "",
        ]

    lines += [
        "# Capture, on and asking for content. CAP2 measured 2026-09-14 that every one of the",
        "# 21,499 observation values the store holds is 15-16 bytes, because the only substrate",
        "# that ever captured content ran content = false. This run is the first realistic",
        "# agentic payload the capture path will see, and A8b's max_observation_bytes is",
        "# untested until it does.",
        "#",
        "# content = true is NECESSARY AND NOT SUFFICIENT. Measured 2026-09-14 against litellm",
        "# 1.80.0 + openai 2.54.0 + opentelemetry-instrumentation-openai-v2 2.4b0: the",
        "# instrumentor emits gen_ai.input.messages / gen_ai.output.messages only when",
        "# OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT is set to SPAN_ONLY (or",
        "# SPAN_AND_EVENT) in the container. Prove's content flag decides what it KEEPS; that",
        "# variable decides what the instrumentor EMITS. The Dockerfile sets it.",
        "#",
        "# max_observation_bytes is pinned by the T.4 pre-registration, which registered this",
        "# value as the number under test; there is no shipped number for it to match, because",
        "# every sweep now declares its own. An airline turn's message list is far over it, so",
        "# the value is stored as its head and its tail, with bytes_original recording its whole",
        "# byte length -- which is the measurement, at a bounded storage cost.",
        "[capture]",
        'instrument = ["openai"]',
        "content = true",
        "max_observation_bytes = 8192",
        "max_spans = 1000",
        "",
        "[modal]",
        "# One episode per batch, so each is its own container and its own store part: an episode",
        "# that hangs takes one row with it and not sixty-four.",
        "concurrency = 16",
        "batch_size = 1",
        "episode_timeout = 900.0",
        "infra_retries = 2",
        'secrets = ["golden-pilot"]',
        "# Measured by the smoke pair (2026-09-13): 20.7 s mean, 41.4 s max.",
        "est_seconds_per_episode = 25.0",
        "# max_cost guards MODAL COMPUTE ONLY (C20) and has never seen a token. Provider spend",
        "# is gated before launch by scripts/tau2_t4_budget.py and stopped only by a",
        "# project-level spend limit at the provider; neither of those is this number, and",
        "# nothing in the container caps an episode.",
        "max_cost = 5.0",
        "",
        "[modal.image]",
        'dockerfile = "examples/tau2_pilot/Dockerfile"',
        'local_packages = ["tau2_pilot"]',
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        help="airline tasks.json from a tau2-bench checkout at the pinned commit",
    )
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "examples" / "tau2_pilot" / "t4.toml"
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=None,
        help="override N; the default is the least count the resolver admits at the floor",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit nonzero if --out is not what the rule produces",
    )
    args = parser.parse_args()

    raw = args.tasks.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    tasks = json.loads(raw)
    if len(tasks) != 50:
        raise SystemExit(f"airline is not 50 tasks: {len(tasks)}")

    families = classify(tasks)
    smallest = min(len(ids) for ids in families.values())
    derived, mde = least_admitted_replicates(smallest)
    replicates = args.replicates if args.replicates is not None else derived

    for family in FAMILIES:
        print(f"{family:<16} {len(families[family]):>2}  {' '.join(families[family])}")
    print(
        f"\nbinding family {smallest} cells -> N = {derived} "
        f"(group MDE {mde:.4f} <= {MAX_GROUP_MDE:g}); writing N = {replicates}"
    )

    text = render(tasks, families, replicates, digest)
    if args.check:
        current = args.out.read_text() if args.out.exists() else ""
        if current != text:
            print(f"\n{args.out} is not what the rule produces", file=sys.stderr)
            return 1
        print(f"\n{args.out} matches the rule")
        return 0
    args.out.write_text(text)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
