# Changelog

All notable changes to Poisson Prove are written here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/).

## 0.3.0 — 2026-11-13

### Changed

- **Sweeps run on your own cloud account with `--backend cloud`**, and Prove now starts the
  cluster, sets its shape, and stops it when the sweep ends, on success, on failure and on Ctrl-C.
  `--backend burla` and the `[burla]` table are replaced: `--backend burla` is refused with the new
  name, a spec with `[burla]` is refused naming the move, and `poisson-prove where cloud` rewrites
  the table. Install with `pip install "poisson-prove[cloud]"`; `[burla]` installs the same until 0.4.0.
- A cloud sweep's stop reads your account as well as the cluster software. Once the software has
  stopped, Prove reads the instances tagged as the sweep's nodes (`aws ec2 describe-instances`),
  terminates any still running, such as one whose launch was on its way when Ctrl-C stopped the
  boot, and waits up to 2 minutes until every node is terminated, so a sweep started right after
  is not refused on the account's vCPU quota. The `stopped` line counts the nodes that started.
- A cloud start that your account refused before any instance launched exits 1, with nothing
  started, even when the cluster software lists the refused nodes as booting: Prove goes by what
  the account shows. A start refused after a node launched still exits 3, once that node is stopped.
- When a policy on your AWS account refuses the launch, such as a spend limit with its early
  control "Stop new resource launches" on, Prove says that a policy on the account does not allow
  starting instances, and to check the account's spend limit or ask its administrator, rather
  than to sign in again. A start refused on the vCPU quota says whether the quota is too small for
  the nodes asked, or is in use, most likely by the last cluster still stopping.
- The plan prices each node's disk at the size it boots with, 20 GB or the spec's `disk_gb`, plus
  the machine's memory, and names that size ("each node's disk priced at 52 GB";
  `plan.cloud.disk_gb_priced` in `--json`). Every cloud sweep sends its disk size, so a size kept
  from an earlier sweep on the same account is not the one that boots.
- The `[cloud]` extra installs `botocore[crt]>=1.42.39`, which a sign-in made by `aws login` needs.
- **A spec runs where its table says.** `poisson-prove sweep` with no `--backend` now runs on
  your cloud account when the spec holds a `[cloud]` table and on Modal when it holds a `[modal]`
  table. In 0.2 it ran on this machine unless `--backend` was given, so a spec with a `[modal]`
  table that you swept with no `--backend` now plans on Modal. It still names the cost and asks
  before anything runs. `--backend local` runs it on this machine as before, and a spec that holds
  both tables is refused until `--backend` or `poisson-prove where` says which.
- A Modal or cloud sweep whose first batch has no outcome in any rollout stops there (#11).
- An interrupted command exits 130 even when its output pipe is closed, and the run records
  that it was interrupted (#12).

### Added

- `poisson-prove where`, a new verb, and where a sweep runs as part of setting up: `where` shows
  it or changes it, `init` asks in a terminal (`--runs-on` answers on the command line), and the
  terminal app has a page for it, behind `w`. The verb's page is `docs/commands/where.md`.
- The run manifest's `produced_by` (the artifact format's 1.1) (#17).

### Fixed

- A Ctrl-C that lands while a rollout's own process is starting, under `--episode-timeout`, or
  while the capture probe's process is starting, stops the sweep and exits 130. Before, it could
  be lost, and the sweep ran on until that process ended.

## 0.2.2 — 2026-11-08

A release of the docs alone: the package's code is the same as 0.2.1's.

### Added

- A new page, `docs/what-a-declaration-checks.md`: what a `[declare]` table records, stamps and
  prints, and what `never reached` means and does not. It held the second half of
  `docs/what-capture-stores.md` before, and the sweep spec now links to it for what `steps` and
  `gates` report.

### Changed

- `docs/recipes/in-ci.md` gives every file a GitHub repository needs to gate its pull requests on
  Prove. `make_comment.py` is given in full: it reads the `check --json` file named on its command
  line and prints the comment, and an empty file, which a refused check leaves, gets a comment
  that says so. The main branch's workflow, `prove-baseline.yml`, is given in full beside the pull
  request's, `prove.yml`, which now also posts the comment. Every action in both is pinned to a
  full commit SHA. One line says that `unresolved` and `timeout` are the support bot's events, an
  example: on the quickstart's runs `unresolved` is refused with exit 1, so name your own.
- `docs/artifact-format.md` and `docs/what-capture-stores.md` are in short sections under headings
  you can jump by, with lists and tables where a paragraph listed, and an example of each stored
  format a paragraph describes, from a real run. No fact was cut.

## 0.2.1 — 2026-11-05

### Fixed

- With `--json`, stdout is the one JSON document whatever the target writes (#28). Before, a
  target that printed put its text in stdout beside the document and the sweep still exited 0, so
  a caller got success and a document it could not parse. Now everything the target writes to
  stdout goes to stderr instead, once, as it is written: a `print` in the rollout or at import, a
  write to `sys.stdout.buffer`, `os.write(1, ...)`, the C library, a program the target starts,
  an `atexit` hook, and all of these under `--episode-timeout`. The same holds for
  `ui --open --json`, whose browser inherits stdout, and for what the Modal client or a Burla
  sweep's own process writes. The document, the exit codes and everything without `--json` are
  as they were.
- What that means for a caller of `sweep --json`: read both streams, because a caller that pipes
  stdout and stderr and reads only stdout can hang on a target that prints a lot (200 kB a
  rollout is enough; `subprocess.run(capture_output=True)` reads both); look for the line that
  starts `error: `, not stderr's first line, which can be the target's text; and with stderr a
  terminal the target sees `sys.stdout.isatty()` true, so a framework may draw there.
- A target that calls `sys.exit`, at import or in a rollout, no longer ends `sweep --json` with
  exit 0 and an empty stdout: the sweep exits 3 with one `error: ` line. Without `--json` it ends
  the process as before.
- A target that closes its stdout no longer costs `sweep --json` its document.
- `main()` called in the caller's own process with `--json` and no `stdout=` leaves file
  descriptor 1 pointing at stderr for the rest of that process, so a host script that prints
  afterwards prints to stderr; Prove's own output from later calls still goes to the process's
  real stdout. A caller that passes `stdout=` or uses `contextlib.redirect_stdout` is untouched.
- Under `--episode-timeout`, text a rollout printed and had not yet flushed is no longer lost
  when the episode's process is ended. This holds without `--json` too, where it was lost in some
  runs.
- On Burla, a rollout that writes to stdout through the file descriptor (a flushed `print`,
  `os.write`, a child process, or any `print` under `--episode-timeout`) no longer fails the
  sweep with an `UnpicklingError`, with or without `--json`. What a rollout writes stays with the
  worker.
- The dashboard no longer cuts a chart off at its panel's edge (#31). On the comparison page the
  heatmaps' last column was cut at 1,280, 1,440 and 1,920 wide, and on a phone the differences
  and limits charts and the charts on a condition's page were cut too. A chart now leaves room
  for its own padding inside its panel; a chart in a panel wider than the chart is drawn as
  before.

## 0.2.0 — 2026-11-04

### Changed

- `diff` reads in plain words by default: the verdict block, then one table of the conditions in
  the order of their axis values, each with its change and the smallest rise and fall it could
  have detected, and what the comparison left out, in words. The machine sections (the per-event
  tables by hash, the coverage table, the omnibus, the fault lines and the bound) moved behind
  `--full`, which prints what `diff` printed before. A tool that read them from the text passes
  `--full` or reads `--json`, which did not change.
- Saved comparison ids change at this minor: an id hashes the tool's major and minor version, so
  the same comparison saved again under 0.2.0 gets a new id. Comparisons saved by 0.1.x stay
  readable.
- `inspect` prints identical errors as one traceback with a count of the episodes that have it,
  each listed episode on a line of its own under it; an error none of the listed episodes has is
  counted in one line. `--json` is unchanged.
- The dashboard's comparison page shows its heatmaps on the first screen, between the verdict's
  detail lines and what the verdict rests on; the differences and limits charts stay after the
  conditions.
- The `limits` line of `diff`, `check`, `report`, the dashboard and the terminal app counts the
  rows with no limit by direction, so a row with no limit on its fall is not said to have none on
  its rise; "no change of any size" is said only of a row with no limit either way.
- The look file gains the banner section the Poisson Labs tools share, and its static UI's type
  rule lets labels (table headers, detail labels, captions) take the system's sans.

## 0.1.3 — 2026-11-04

### Fixed

- When every rollout of a sweep errored, the sweep's `next:` line suggests `inspect` with
  `--limit 3`, so the first look shows three of the failing episodes rather than every one.
- `diff`, `report` and `check` of a run in which every episode errored name that run in plain
  words and suggest `inspect` of its commonest error with `--limit 3`, one line per such run, in
  place of an error about the event set. `report` writes nothing for it.
- `report` ends with a `next:` line, `poisson-prove ui`, on the store that was typed, so the chain
  of `next:` lines has no dead end; `--json` carries the same command.
- `runs`, the dashboard and the terminal app show a complete run in which every episode errored as
  `stopped`, as the sweep did. Its manifest and `runs --json` keep `complete`, with `rows` and
  `no_outcome` carrying the fact; a partial run stays `partial`. The app's comparison screen takes
  complete runs, so it no longer offers such a run.

### Changed

- Before a release, and on every pull request, CI runs Poisson Tasks' own Prove check against
  Prove built from the tree: the check from Tasks' latest release, unedited, on a wheel built under
  a version the package index cannot hold, so the check cannot quietly test the release already
  out. A red check stops the release.

## 0.1.2 — 2026-10-31

### Fixed

- `prove ui` prints its address as soon as the viewer is listening. It no longer waits on a reverse
  lookup of its own host name, which took 35 seconds on some machines, among them GitHub's hosted
  macOS runners.

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
