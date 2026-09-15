#!/usr/bin/env python3
"""The T.4 launch gate: refuse to start an arm whose worst case breaks the spend cap.

**Why this exists.** ``estimate_cost`` guards Modal compute and has never seen a token (C20),
so nothing in Proofload bounds provider spend, and the pre-registration's cap was a number in a
document. This is the cap as a gate: it reads what T.4 has already spent -- from the store, from
``meta.cost_tau2``, which is litellm's own per-episode figure -- adds a projection for the arm
about to launch, and exits nonzero if the total would pass ``--cap``. Run it before every arm.

**What it cannot do.** It gates at *arm* granularity: once an arm is launched nothing here can
stop it, and a single arm's projection being wrong is a whole arm of overspend. Two things
narrow that. ``tau2_pilot.budget`` caps what one container may spend, so a runaway episode is
bounded rather than unbounded. And the projection self-calibrates: before arm A it uses the
provider's list price, which is a 2.2x upper bound on what the smoke actually paid; after arm A
it uses arm A's own measured mean with a safety factor, which is the honest number for A' and B.

**The only stop that binds unconditionally is a spend limit on the provider's own project.**
It is not in this repository and this script does not claim to replace it.

    python scripts/tau2_t4_budget.py --arm A
    python scripts/tau2_t4_budget.py --arm B --cap 150
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

#: gpt-4.1-mini list price, read at source 2026-09-14 from
#: https://developers.openai.com/api/docs/pricing (redirected there from platform.openai.com/
#: docs/pricing, 301). Dollars per million tokens. The page prices the ``gpt-4.1-mini`` alias;
#: the run pins the ``-2025-04-14`` snapshot, and OpenAI's table carries one price for both.
LIST_USD_PER_MTOK = {"input": 0.40, "cached_input": 0.10, "output": 1.60}

#: The list-price cost of the smoke pair's mean episode: 54,046 in / 1,023 out at the rates
#: above. $0.0233, which is C23's "list price $0.023 is a 2.2x upper bound". Used as the
#: projection until an arm of this run has been measured.
LIST_ANCHOR_USD = (
    54_046 * LIST_USD_PER_MTOK["input"] / 1e6 + 1_023 * LIST_USD_PER_MTOK["output"] / 1e6
)

#: Applied to a measured mean before projecting it onto an unrun arm. An arm's mean is a
#: measurement of that arm; the next arm is a different agent prompt and a different
#: conversation length, and B's whole point is that it changes what the agent says.
SAFETY = 1.25

DEFAULT_CAP_USD = 150.0
DEFAULT_SPEC = REPO_ROOT / "examples" / "tau2_pilot" / "t4.toml"

#: The sweep file's ``target_id``: how a stored run is recognised as T.4's rather than another
#: substrate's, so "what has this run already spent" needs no hand-kept list of run ids.
TARGET_ID = "tau2-airline/gpt-4.1-mini-2025-04-14@v0"


def episode_counts(spec_path: Path) -> tuple[int, int]:
    """``(launched, with_model_calls)`` for one arm of this sweep file.

    The three junk configs carry no ``task_id``, so the wrapper raises before any request is
    made: they are launched, they cost a container start, and they cost nothing at the provider.
    """
    from proofload.sampler import SweepSpec

    spec = SweepSpec.load(spec_path)
    junk = sum(1 for cfg in spec.configs if "task_id" not in cfg)
    launched = len(spec.configs) * spec.replicates
    return launched, (len(spec.configs) - junk) * spec.replicates


def run_costs(store_path: Path) -> dict[str, tuple[int, float]]:
    """``run_id -> (episodes with a cost, total dollars)`` for every stored T.4 run."""
    from proofload.store import Store

    store = Store(store_path)
    out: dict[str, tuple[int, float]] = {}
    for run_id in store.runs():
        try:
            manifest = store.manifest(run_id)
        except Exception:  # noqa: BLE001 - a run this script cannot read is not T.4's
            continue
        sweep = (getattr(manifest, "environment", None) or {}).get("sweep") or {}
        if sweep.get("target_id") != TARGET_ID:
            continue
        total = 0.0
        counted = 0
        for _, row in store.read(run_id).iterrows():
            meta = row["meta"]
            if meta is None:
                continue
            meta = meta if isinstance(meta, dict) else json.loads(meta)
            cost = meta.get("cost_tau2") or {}
            value = (cost.get("agent") or 0.0) + (cost.get("user") or 0.0)
            if value:
                counted += 1
                total += float(value)
        out[run_id] = (counted, total)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, help="the arm about to launch, for the record")
    parser.add_argument("--cap", type=float, default=DEFAULT_CAP_USD)
    parser.add_argument(
        "--arms", type=int, default=3, help="arms the cap has to cover; K1's denominator"
    )
    parser.add_argument(
        "--price",
        choices=("list", "measured"),
        default="list",
        help="which projection the verdict runs on (default: the list-price bound)",
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("PROOFLOAD_STORE", "./proofload-runs")).expanduser(),
    )
    args = parser.parse_args()

    launched, billable = episode_counts(args.spec)
    prior = run_costs(args.store) if args.store.exists() else {}
    spent = sum(total for _, total in prior.values())

    means = [total / counted for counted, total in prior.values() if counted]
    measured = max(means) * SAFETY if means else None
    projected_list = billable * LIST_ANCHOR_USD
    projected_measured = None if measured is None else billable * measured
    # The verdict runs on the bound, not on the hope. List price is 2.2x what the smoke actually
    # paid, and the whole gap is OpenAI's prompt caching (C23): a cap that holds only while the
    # cache keeps hitting is not a cap. --price measured is the deliberate choice to gate on the
    # cheaper number, and it prints as one.
    decisive = projected_list if args.price == "list" else (projected_measured or projected_list)
    total = spent + decisive

    print(f"arm            {args.arm}")
    print(f"sweep file     {args.spec}")
    print(f"episodes       {launched} launched, {billable} reaching the provider")
    print(
        f"list price     ${LIST_ANCHOR_USD:.5f}/episode -- read at source 2026-09-14; "
        f"${LIST_USD_PER_MTOK['input']}/${LIST_USD_PER_MTOK['cached_input']}/"
        f"${LIST_USD_PER_MTOK['output']} per Mtok in/cached/out"
    )
    if measured is not None:
        print(
            f"measured       ${measured:.5f}/episode -- max prior arm mean "
            f"{max(means):.5f} x {SAFETY} safety"
        )
    print(f"gating on      {args.price}")
    print()
    for run_id, (counted, value) in sorted(prior.items()):
        print(f"  spent  {run_id}  {counted:>5} episodes  ${value:.2f}")
    print(f"  spent  total{'':>26}${spent:.2f}")
    print(f"  this arm at list{'':>22}${projected_list:.2f}")
    if projected_measured is not None:
        print(f"  this arm at measured{'':>18}${projected_measured:.2f}")
    print(f"  cap{'':>35}${args.cap:.2f}")
    print()
    # K1 is the cap divided by every episode the run may bill for, not by one arm's: an arm
    # that passes its own threshold and leaves nothing for the next two is not within the cap.
    print(
        f"K1 threshold at this cap over {args.arms} arms "
        f"({args.arms * billable} episodes): ${args.cap / max(args.arms * billable, 1):.4f}/episode"
    )

    if total > args.cap:
        print()
        print(
            f"REFUSED: ${spent:.2f} already spent plus ${decisive:.2f} projected is "
            f"${total:.2f}, over the ${args.cap:.2f} cap."
        )
        return 1
    print()
    print(f"OK: ${total:.2f} of ${args.cap:.2f} after this arm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
