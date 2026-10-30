# Changelog

All notable changes to Poisson Prove are written here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/).

## 0.1.1 — 2026-10-30

Prove's Burla backend now runs on Burla 1.8.4, the first Burla client with private mode, in which
a cluster in your own cloud account never contacts Burla's servers.

### Changed

- The `[burla]` extra pins exactly Burla 1.8.4, in place of 1.8.2. The backend is still
  experimental.
- The plan's `Traffic` line says that code, inputs and results go through Burla's relay unless the
  cluster's head runs in private mode (`BURLA_PRIVATE=True`), and directly between your machine
  and the nodes when it does. Burla 1.8.4 no longer has the `DISABLE_BURLA_RELAY` switch the line
  used to name.
- When no node is running, the error also says how to start a cluster in private mode: through
  the coordinator's localhost API, `POST /v1/settings`, then `POST /v1/management/cluster/start`.
- Prove neither sets nor checks private mode. Its Burla client is private when the environment
  Prove runs in sets `BURLA_PRIVATE=True`.

## 0.1.0 — 2026-10-29

The first public release. Prove tells you whether a change to an AI agent really changed how often
it fails. It replays the same cases before and after the change, on the same seeds, compares the
two runs condition by condition, and gives a verdict with stated error bounds and detection
limits. Python 3.11 to 3.14, on macOS and Linux.

### Verbs

- `poisson-prove init` writes `prove.toml`, a sweep spec to edit; `init --example` writes the
  keyless example; `init --agent` writes a skill and a prompt for your own coding agent, which sets
  Prove up in your repository for you to review. Prove itself makes no model call.
- `poisson-prove sweep` prints the plan, its cost and the smallest change one condition alone would
  be flagged for, refuses a design too small for the change you accept and names the replicates
  that would do, then runs the sweep on this machine, on Modal or on Burla. A stopped sweep resumes
  where it stopped, and `--pair-with` gives a sweep an earlier run's seeds.
- `poisson-prove diff` compares two stored runs condition by condition, per outcome, and names the
  method it used.
- `poisson-prove report` writes `report.md`, `heatmap.svg` and `receipt.html` for two runs, or one,
  and saves the comparison.
- `poisson-prove paired` checks that a declaration's arms replayed the same requests, then writes
  its files.
- `poisson-prove check` gates on a comparison: passed exits 0, failed exits 4.
- `poisson-prove serve` serves a read-only page comparing two runs on a loopback port, and saves
  the comparison.
- `poisson-prove inspect` prints the episodes behind an outcome, with a snippet to reproduce one.
- `poisson-prove runs` lists the runs in the store, by name and id.
- `poisson-prove ui` builds the dashboard: static pages over the store, opened from disk.
- `poisson-prove` with no verb, on a terminal, opens the terminal app over the store.

### Concepts

- The verdict is one word for the whole comparison: `safer`, `worse`, `trade` (some conditions
  safer and at least one worse), `no significant change` (no change counted, and every condition
  could have caught one of the size you accepted) or `too small to tell` (no change counted, and at
  least one condition could not have).
- A condition's flag is held to a false discovery rate (Benjamini-Hochberg); the verdict counts
  only the changes that also hold at the family-wise level (Holm).
- Every condition that did not move says how large a change it would have caught 4 times in 5,
  computed for the test the comparison used, or that it could not have caught one at all.
- Runs paired at sweep time share their seeds and are compared with the paired test (McNemar) by
  default; every output names the method it used.
- Every episode is stored in Parquet with its seed, outcome, time and trace. Runs go by readable
  names, and `latest` and `previous` stand for the two newest.
- Runs and saved comparisons are written in a documented artifact format, which the dashboard and
  the terminal app read.
- The layered report: one omnibus test over every condition, the fault lines that group them, and
  the conditions under each.
- Fault injection through a `[chaos]` table, and capture of an agent's trace through OpenTelemetry.
- A Modal or Burla worker runs the rollout's BLAS on one thread unless its environment sets a
  thread count; `threadpoolctl` is a core requirement for this.
- The Python API (`poisson_prove`) gives the same comparisons the command line prints.
- The packaged example needs no key: a mock agent and a patched version of it, swept on the same
  seeds, whose comparison reads `trade`.

### Install

- `pip install poisson-prove`. The extras are `[modal]` (Modal 1.0.0 or later), `[burla]`
  (exactly Burla 1.8.2; the backend is experimental), `[agent]` (OpenTelemetry capture and the
  OpenAI client), and `[all]`.
- Prove sends nothing anywhere beyond the backend you choose: no telemetry, no analytics, no update
  check. `serve` binds to 127.0.0.1 only.

### Renamed

- This is the first public release. Earlier private builds were called proofload; stores they
  wrote are read unchanged.
