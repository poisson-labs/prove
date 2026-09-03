"""Build the Go1 golden fixture from the published policy-robustness-sweep manifests.

Converts the v0 (pre-retrain) and v1 (post-retrain) 32-seed sweeps into two Proofload runs
in the M4 store format, writes golden.json (the published numbers, copied not computed),
and writes a README with provenance.

    python scripts/build_golden_fixture.py --v0 <manifest> --v1 <manifest> --out <dir>
        [--diff <v0-v1-diff.json>]

The published numbers live in this file as constants so the builder does not depend on
files next to its inputs. When --diff is given, the constants are verified against the
published diff JSON before anything is written; a disagreement refuses the build.

The builder refuses to write if the fell fractions it computes from its own converted
records do not round to the published values. Exit 0 on success, 2 on refusal.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from proofload import Episode, __version__
from proofload.store import EpisodeRecord, RunManifest, Store

HORIZON_S = 5.0
SEED_BASE = 1_000_000
RUN_SALT = "go1-g4-32:PRNGKey(1000000+rollout)"
AXIS_TYPES: dict[str, Literal["continuous", "categorical"]] = {
    "mu": "continuous",
    "push_pct_bw": "continuous",
}
BACKEND_META = {"wall_time_synthetic": True, "seed_derived_from": "rollout"}
SOURCE_REPO = "poisson-labs/policy-robustness-sweep"
SOURCE_DATE = "2026-08-18"

# proofload run_id -> (source run_id the manifest must carry, proofload target_id)
RUNS: dict[str, tuple[str, str]] = {
    "go1-v0": ("20260813T155006Z", "go1-g2-converged@20260813T155006Z"),
    "go1-v1": ("20260818T230622Z-v1", "go1-g2-v1@20260818T230622Z-v1"),
}
RUN_TO_GOLDEN_KEY = {"go1-v0": "v0", "go1-v1": "v1"}

# Published numbers. Copied from 2026-08-18-m1_5-retrain-diff.md and
# 2026-08-18-v0-v1-diff.json. Never derived here.
GOLDEN: dict[str, Any] = {
    "grid": {"cells": 400, "seeds_per_cell": 32, "rollouts_per_run": 12800},
    "v0": {"fell_pct": 62.7, "diverged": 0},
    "v1": {"fell_pct": 52.8, "diverged": 0},
    "diff": {"method": "fisher_exact_per_cell + bh_fdr", "q": 0.05, "safer": 60, "worse": 0},
    "boundary_s50_pct_bw": {
        "0.10": [20.0, 85.7],
        "0.20": [70.0, 96.0],
        "0.50": [88.0, 101.3],
        "1.00": [102.6, 108.1],
    },
    "source": {"repo": SOURCE_REPO, "commit": None, "date": SOURCE_DATE},
}


class Refuse(Exception):
    """The build must not proceed. Message explains why."""


# ---------- conversion ----------


def convert(run_id: str, manifest_path: Path) -> tuple[list[EpisodeRecord], dict[str, Any]]:
    source = json.loads(manifest_path.read_text())
    expected_source_run_id, _ = RUNS[run_id]
    if source.get("run_id") != expected_source_run_id:
        raise Refuse(
            f"{manifest_path.name}: run_id {source.get('run_id')!r} is not the published "
            f"{expected_source_run_id!r} for {run_id}"
        )
    records: list[EpisodeRecord] = []
    fell = diverged = 0
    for rec in source["records"]:
        config = {"mu": rec["mu"], "push_pct_bw": rec["push_pct_bw"]}
        seed = SEED_BASE + int(rec["rollout"])
        rep = int(rec["seed_idx"])
        diverged_at = rec.get("diverged_at_s")
        if diverged_at is not None:
            diverged += 1
            records.append(
                EpisodeRecord.errored(
                    run_id=run_id,
                    config=config,
                    seed=seed,
                    replicate_index=rep,
                    error=f"diverged@{diverged_at}s",
                    wall_time=0.0,
                    backend_meta=BACKEND_META,
                )
            )
            continue
        fell_time = rec["fell_time_upz_s"]
        if fell_time is not None:
            fell += 1
            outcome, t = "fell", float(fell_time)
        else:
            outcome, t = "survived", HORIZON_S
        episode = Episode(
            outcome=outcome,
            t=t,
            horizon=HORIZON_S,
            confidence=None,
            meta={
                "rollout": int(rec["rollout"]),
                "min_upz": rec["min_upz"],
                "min_torso_z": rec["min_torso_z"],
                "source_manifest": manifest_path.name,
            },
        )
        records.append(
            EpisodeRecord.from_episode(
                episode,
                run_id=run_id,
                config=config,
                seed=seed,
                replicate_index=rep,
                wall_time=0.0,
                backend_meta=BACKEND_META,
            )
        )
    n = len(records)
    per_cell: dict[tuple[float, float], int] = {}
    for rec in source["records"]:
        key = (float(rec["mu"]), float(rec["push_pct_bw"]))
        per_cell[key] = per_cell.get(key, 0) + (rec["fell_time_upz_s"] is not None)
    stats = {
        "n": n,
        "fell": fell,
        "diverged": diverged,
        "fell_pct": 100.0 * fell / n if n else float("nan"),
        "per_cell_fell": per_cell,
    }
    return records, stats


def check_drift(run_id: str, stats: dict[str, Any]) -> None:
    golden = GOLDEN[RUN_TO_GOLDEN_KEY[run_id]]
    expected_n = GOLDEN["grid"]["rollouts_per_run"]
    if stats["n"] != expected_n:
        raise Refuse(f"{run_id}: {stats['n']} records, published {expected_n}")
    if round(stats["fell_pct"], 1) != golden["fell_pct"]:
        raise Refuse(
            f"{run_id}: computed fell fraction {stats['fell_pct']:.4f}% rounds to "
            f"{round(stats['fell_pct'], 1)}, published {golden['fell_pct']}"
        )
    if stats["diverged"] != golden["diverged"]:
        raise Refuse(
            f"{run_id}: {stats['diverged']} diverged records, published {golden['diverged']}"
        )


# ---------- verification against the published diff JSON ----------


def verify_against_diff(diff_path: Path, stats: dict[str, dict[str, Any]]) -> None:
    d = json.loads(diff_path.read_text())
    checks: list[tuple[str, Any, Any]] = [
        ("n_better", d["n_better"], GOLDEN["diff"]["safer"]),
        ("n_worse", d["n_worse"], GOLDEN["diff"]["worse"]),
        ("significance.q", d["significance"]["q"], GOLDEN["diff"]["q"]),
        ("grid.seeds_per_cell", d["grid"]["seeds_per_cell"], GOLDEN["grid"]["seeds_per_cell"]),
        ("grid.total_rollouts", d["grid"]["total_rollouts"], GOLDEN["grid"]["rollouts_per_run"]),
        ("v0.run_id", d["v0"]["run_id"], RUNS["go1-v0"][0]),
        ("v1.run_id", d["v1"]["run_id"], RUNS["go1-v1"][0]),
    ]
    cells = d["cells_diff"]
    total = GOLDEN["grid"]["rollouts_per_run"]
    checks.append(("cells", len(cells), GOLDEN["grid"]["cells"]))
    fell_a = sum(int(c["fell_a"]) for c in cells)
    fell_b = sum(int(c["fell_b"]) for c in cells)
    checks.append(("v0 fell_pct", round(100.0 * fell_a / total, 1), GOLDEN["v0"]["fell_pct"]))
    checks.append(("v1 fell_pct", round(100.0 * fell_b / total, 1), GOLDEN["v1"]["fell_pct"]))
    v0_cells, v1_cells = stats["go1-v0"]["per_cell_fell"], stats["go1-v1"]["per_cell_fell"]
    for c in cells:
        key = (float(c["mu"]), float(c["push_pct_bw"]))
        checks.append((f"cell {key} fell_a", v0_cells.get(key), int(c["fell_a"])))
        checks.append((f"cell {key} fell_b", v1_cells.get(key), int(c["fell_b"])))
    bad = [(name, got, want) for name, got, want in checks if got != want]
    # Boundary medians are published to one decimal, rounded half up. Compare with a
    # half-decimal tolerance rather than round(), which sends x.x5 down.
    by_mu = {f"{row['mu']:.2f}": row for row in d["boundary_displacement"]}
    for mu, (v0_med, v1_med) in GOLDEN["boundary_s50_pct_bw"].items():
        row = by_mu[mu]
        for label, raw, want in (("v0", row["v0_median_pct_bw"], v0_med),
                                 ("v1", row["v1_median_pct_bw"], v1_med)):
            if raw is None or abs(raw - want) > 0.05 + 1e-9:
                bad.append((f"boundary {mu} {label}", raw, want))
    if bad:
        detail = ", ".join(
            f"{name}: diff has {got!r}, builder has {want!r}" for name, got, want in bad
        )
        raise Refuse(f"published diff {diff_path.name} disagrees with builder constants: {detail}")


# ---------- provenance ----------


def source_commit(files: list[Path]) -> str:
    """SHA of the last commit that touched any of the source files.

    Keyed on the files, not on HEAD, so unrelated commits to the source repo do not
    change the provenance a fresh build writes.
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(files[0].parent), "log", "-1", "--format=%H", "--", *map(str, files)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "unknown"


def make_manifest(run_id: str, manifest_path: Path, commit: str, date: str) -> RunManifest:
    _, target_id = RUNS[run_id]
    return RunManifest(
        run_id=run_id,
        target_id=target_id,
        t_unit="seconds",
        run_salt=RUN_SALT,
        axis_types=AXIS_TYPES,
        backend="import",
        environment={
            "source_repo": SOURCE_REPO,
            "source_repo_path": str(manifest_path.parent),
            "source_commit": commit,
            "source_manifest": manifest_path.name,
            "conversion_date": date,
            "proofload_version": __version__,
        },
        retain_traces_for=None,
    )


def write_readme(
    out: Path,
    manifests: dict[str, Path],
    diff_path: Path | None,
    commit: str,
    date: str,
    stats: dict[str, dict[str, Any]],
    argv: list[str],
) -> None:
    lines = [
        "# Go1 golden fixture",
        "",
        "Two Proofload runs converted from the published Go1 policy-robustness sweeps. This is",
        "the test oracle for M5, M6 and M7: if Proofload cannot recover the published numbers",
        "in `golden.json` from these runs, Proofload is wrong.",
        "",
        "## Provenance",
        "",
        f"- Source repo: `{SOURCE_REPO}`",
        f"- Source commit: `{commit}`",
        "- Source manifests (under `docs/measurements/`):",
    ]
    for run_id, path in manifests.items():
        lines.append(f"  - `{run_id}` <- `{path.name}`")
    if diff_path is not None:
        lines.append(f"- Published diff verified against: `{diff_path.name}`")
    lines += [
        f"- Publication date: {SOURCE_DATE}",
        f"- Converted: {date} with proofload {__version__}",
        f"- Command: `{' '.join(argv)}`",
        "",
        "## Conversion",
        "",
        "- `t_unit` is seconds; horizon is 5.0 s (250 steps x 0.02 s). No unit conversion.",
        "- `outcome` is `fell` when `fell_time_upz_s` is set, else `survived` with `t == 5.0`.",
        "- `seed = 1000000 + rollout`; `replicate_index = seed_idx`. Identical `run_salt` in",
        "  both runs marks them as paired by construction.",
        "- `wall_time` is 0.0 and synthetic (not in the export); `backend_meta` says so.",
        "- `confidence` is null throughout: the policy is deterministic.",
        "- `golden.json` is copied from the publication, never computed here.",
        "",
        "## Computed fell fractions (drift guard)",
        "",
        "| run | rows | fell | diverged | fell % | published |",
        "|---|---|---|---|---|---|",
    ]
    for run_id, s in stats.items():
        published = GOLDEN[RUN_TO_GOLDEN_KEY[run_id]]["fell_pct"]
        lines.append(
            f"| {run_id} | {s['n']} | {s['fell']} | {s['diverged']} | "
            f"{s['fell_pct']:.4f} | {published} |"
        )
    lines += ["", "## Parts", ""]
    for run_id in manifests:
        for part in sorted((out / run_id / "episodes").glob("*.parquet")):
            lines.append(f"- `{run_id}/episodes/{part.name}`: {part.stat().st_size} bytes")
    (out / "README.md").write_text("\n".join(lines) + "\n")


# ---------- main ----------


def build(v0: Path, v1: Path, out: Path, diff: Path | None, argv: list[str]) -> None:
    manifests = {"go1-v0": v0, "go1-v1": v1}
    converted: dict[str, list[EpisodeRecord]] = {}
    stats: dict[str, dict[str, Any]] = {}
    for run_id, path in manifests.items():
        records, s = convert(run_id, path)
        check_drift(run_id, s)
        converted[run_id] = records
        stats[run_id] = s
    if diff is not None:
        verify_against_diff(diff, stats)

    # Nothing above touched disk. Everything below does.
    commit = source_commit([v0, v1] + ([diff] if diff is not None else []))
    date = datetime.now(UTC).date().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    store = Store(out)
    for run_id, records in converted.items():
        run_dir = out / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        store.create_run(make_manifest(run_id, manifests[run_id], commit, date))
        store.append(run_id, records)
        store.mark_complete(run_id)

    golden = json.loads(json.dumps(GOLDEN))
    golden["source"]["commit"] = commit
    # Per-cell counts, computed from the manifests (so a build without --diff is identical)
    # and verified against the published diff JSON whenever --diff is given.
    v0_cells, v1_cells = stats["go1-v0"]["per_cell_fell"], stats["go1-v1"]["per_cell_fell"]
    golden["cells"] = [
        {
            "mu": mu,
            "push_pct_bw": push,
            "fell_a": v0_cells[(mu, push)],
            "fell_b": v1_cells[(mu, push)],
        }
        for mu, push in sorted(v0_cells)
    ]
    (out / "golden.json").write_text(json.dumps(golden, indent=2) + "\n")
    write_readme(out, manifests, diff, commit, date, stats, argv)

    for run_id, s in stats.items():
        print(f"{run_id}: {s['n']} rows, fell {s['fell_pct']:.4f}%, diverged {s['diverged']}")
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--v0", type=Path, required=True, help="v0 (pre-retrain) sweep manifest")
    parser.add_argument("--v1", type=Path, required=True, help="v1 (post-retrain) sweep manifest")
    parser.add_argument("--out", type=Path, required=True, help="fixture directory to write")
    parser.add_argument(
        "--diff",
        type=Path,
        default=None,
        help="published v0-v1 diff JSON; verifies the builder's constants before writing",
    )
    args = parser.parse_args(argv)
    shown = [Path(sys.argv[0]).name, *(sys.argv[1:] if argv is None else argv)]
    try:
        build(args.v0, args.v1, args.out, args.diff, shown)
    except Refuse as exc:
        print(f"refusing to write: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
