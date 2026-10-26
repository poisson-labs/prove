# Changelog

All notable changes to Poisson Prove are written here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/).

## 0.1.0 — Unreleased

The first public release. Prove runs a sweep of an agent over its conditions, stores every
episode, and compares two runs condition by condition, with stated error bounds and detection
limits.

### Verbs

- `poisson-prove init` writes `prove.toml`, a sweep spec to edit, or the keyless example; `init --agent`
  writes the setup files a coding agent follows to wire Prove into a repository.
- `poisson-prove sweep` shows the plan, its cost and the smallest change it can detect, then runs the
  sweep locally, on Modal or on Burla, resumable, and pairs it with an earlier run on request.
- `poisson-prove diff` compares two stored runs condition by condition, per event, and names the method it
  used.
- `poisson-prove report` writes `report.md`, `heatmap.svg` and `receipt.html` for two runs, or one, and
  saves the comparison.
- `poisson-prove paired` checks that a declaration's arms replayed the same requests, then writes its
  files.
- `poisson-prove check` gates on a comparison: passed exits 0, failed exits 4.
- `poisson-prove serve` serves a read-only page comparing two runs on a loopback port.
- `poisson-prove inspect` prints the episodes behind an event, with a snippet to reproduce one.
- `poisson-prove runs` lists the runs in the store, by name and id.
- `poisson-prove ui` builds the static dashboard over the store.
- `poisson-prove` with no verb on a terminal opens the terminal app over the store.

### Concepts

- A sweep spec declares the axes, the replicates and the backend; every episode is stored in
  Parquet with its seed, outcome, time and trace.
- The verdict of a comparison is one of a small set of words, each with its error bound, and a
  comparison too small to tell says so.
- Paired runs share their seeds and are compared episode by episode.
- The layered report: one omnibus test over every condition, the fault lines that group them, and
  the conditions under each.
- Fault injection through a `[chaos]` table, and capture of an agent's trace through OpenTelemetry.
- The Python API (`poisson_prove`) gives the same comparisons the command line prints.

### Renamed

- This is the first public release. Earlier private builds were called proofload; stores they
  wrote are read unchanged.
