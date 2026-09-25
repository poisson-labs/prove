# Proofload

Proofload is a statistical instrument for finding where autonomous and agentic
systems break. It measures failure rather than simulating, training, or
benchmarking, and it stays out of the environment and the user's code.

Pre-release. Not yet usable.

## Serve

`serve` holds a read-only page for one stored pair on an ephemeral loopback port: the plain summary
first, then the statistics it came from.

```
proofload --store ./proofload-runs serve A B --event NAME --x AXIS
```

It binds nothing until the page is built, fetches nothing, and writes nothing; `--json` prints the
page's structure instead. What each section answers is in [Reading a serve page](docs/reading-a-serve-page.md).

## Docs

- [Reading a serve page](docs/reading-a-serve-page.md) — what each of the fourteen sections answers, and what it cannot
- [Defining outcomes](docs/defining-outcomes.md) — an outcome names what happened
  to the system under test, never what happened to the instrument. The rule, the
  case that taught it, and a checklist to run before the first episode.
- [What capture stores](docs/what-capture-stores.md) — what `content = false`
  strips, what it keeps on purpose, and how `max_observation_bytes` bounds one
  observation value.
