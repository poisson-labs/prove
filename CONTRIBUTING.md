# Contributing

## Running the tests

The code suite runs on every pull request; the math suite (the statistics, marked `math`) on a
pull request that changes statistics code, nightly, and before a release:

```
.venv/bin/python -m pytest tests -n 10 -m "not math and not calibration and not backend and not slow"
.venv/bin/python -m pytest tests -n 10 -m math
```

Tests marked `slow` (a browser check of the dashboard's pages, a wheel built from the checkout)
run on `main` and nightly; the browser check needs Playwright's engines:

```
.venv/bin/python -m playwright install chromium firefox webkit
```

## Snapshots

A few tests compare a page of the dashboard whole against a snapshot under `tests/snapshots/`,
and a screen of the terminal app whole (its rows and each cell's colour role) against one under
`tests/__snapshots__/`. They are the one place output is pinned whole; everywhere else a test pins
facts. When a change to a page or a screen is meant, rewrite the snapshots with the one command
that does so and review the diff in the pull request:

```
python -m pytest tests -k snapshot --update-snapshots
```
