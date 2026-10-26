# Contributing

Thank you for helping. This page says how to set up a checkout, run the tests, and send a change.
[Architecture](https://github.com/poisson-labs/prove/blob/main/docs/architecture.md) says where a
change belongs.

## Set up

Prove needs Python 3.11 or later. Install the checkout with every extra and the development tools,
in a virtual environment of its own:

<!-- docs-check: skip: installs a checkout for development, run from its root -->
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
```

## Running the tests

Two suites. Run the code suite before every pull request, and the math suite (the statistics,
marked `math`) when you change statistics code:

<!-- docs-check: skip: runs the test suites of a checkout -->
```bash
python -m pytest tests -n 10 -m "not math and not calibration and not backend and not slow"
python -m pytest tests -n 10 -m math
```

`-n` runs the tests in parallel (`pytest-xdist`); pick a number near your machine's cores. The code
suite takes a few minutes. Tests marked `calibration` are the slow statistical checks of the error
rates; tests marked `backend` call a real Modal or Burla account and never run unless you opt in.

Tests marked `slow` take longer and some reach the package index: a browser check of the
dashboard's pages, every docs page run again from the built wheel in a fresh environment, and the
code suite with every requirement installed at its stated floor on Python 3.11. At the floors,
numpy and SciPy each start a BLAS thread pool in every process, so set `OPENBLAS_NUM_THREADS=1`
for this run or the parallel workers swamp the machine. The browser check needs Playwright's
engines:

<!-- docs-check: skip: runs the slow tests of a checkout -->
```bash
python -m playwright install chromium firefox webkit
OPENBLAS_NUM_THREADS=1 python -m pytest tests -n 6 -m "slow and not backend"
```

## The docs are tested

Every command block in the README and under `docs/` runs, from a folder of its own, and must do
what its page shows: each block carries a mark in an HTML comment on the line before it
(`run`, `skip: REASON`, or `file NAME`), and a block with no mark fails. A page's shown output is
checked by its verdict word and its line labels, never by its counts, which change from one sweep
to the next. The docs check under `tests/` defines the marks in its docstring. When you change a
command's output or its help, run the docs tests and update the pages they name.

## Snapshots

A few tests compare a page of the dashboard whole against a snapshot under `tests/snapshots/`,
and a screen of the terminal app whole (its rows and each cell's colour role) against one under
`tests/__snapshots__/`. They are the one place output is pinned whole; everywhere else a test pins
facts. When a change to a page or a screen is meant, rewrite the snapshots with the one command
that does so and review the diff in the pull request:

<!-- docs-check: skip: rewrites the snapshots of a checkout -->
```bash
python -m pytest tests -k snapshot --update-snapshots
```

## Rules the code keeps

- The core imports no network library and no optional package: `modal`, `burla`, `openai` and the
  OpenTelemetry SDK live behind their extras, and a bare install runs every verb locally.
- Prove makes no network call of its own: no telemetry, no update check. `serve` binds 127.0.0.1
  only.
- A test pins a fact, never prose. A test is changed only by a commit that says why, never to make
  a change pass.
- Frozen tests are read-only. A test written before the code it checks is not edited, skipped or
  marked to fail so that a change passes; if one looks wrong, say so in the pull request.
- Every requirement has a floor that the slow floors test installs and runs; raise one only with
  the reason in the commit.

## Sending a change

Commits are signed and their messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
`test:`, `chore:`), each saying in plain words what changed and why. One pull request per change,
with the tests that pin it, the docs it moves, and the suites green.
