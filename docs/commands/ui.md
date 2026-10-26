# `poisson-prove ui`

Builds the dashboard over the store and prints where it is: static pages in the store's
`.poisson/ui/`, opened from disk in any browser, with nothing loaded from the network. It shows
the runs, the saved comparisons with their verdicts and charts, each condition, and the episodes
behind an outcome. [The dashboard](../dashboard.md) describes every view. Once it exists, every
command that writes a run or saves a comparison refreshes it.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove ui --help
usage: poisson-prove ui [-h] [--open] [--json] [--store PATH] [--plain]
                        [--debug]

Build the static dashboard in the store's .poisson/ui/: the runs, the saved
comparisons, their verdicts and charts, as pages opened from disk with nothing
loaded from the network. Every command that writes a run or saves a comparison
refreshes a dashboard the store already has.

options:
  -h, --help    show this help message and exit
  --open        open the dashboard in the browser (default: not opened)
  --json        print where the dashboard is as one JSON document instead of
                text
  --store PATH  the store folder (default: $POISSON_PROVE_STORE when set, else
                ./prove-runs)
  --plain       print plain text, as a pipe gets it, on a terminal too
                (default: pretty on a terminal, plain otherwise)
  --debug       also print the traceback of an unexpected failure

examples:
  poisson-prove ui
  poisson-prove ui --open
```

## Options

- `--open` also opens the dashboard in your browser.
- `--json` prints where the dashboard is as one JSON document, `poisson-prove.ui/1`, with its
  `location`.
- `--store PATH` builds the dashboard of another store; `--plain` prints plain text on a terminal
  too; `--debug` adds the traceback of an unexpected failure.

## Examples

The dashboard of the example's two runs, then opened in the browser:

<!-- docs-check: run -->
```console
$ poisson-prove ui
ok  dashboard at file:///…/prove-runs/.poisson/ui/index.html
$ poisson-prove ui --open
ok  dashboard at file:///…/prove-runs/.poisson/ui/index.html
```

Where it is, for a script:

<!-- docs-check: run -->
```console
$ poisson-prove ui --json
{
  "schema": "poisson-prove.ui/1",
  "verdict": "ok",
  "sentence": "the dashboard over prove-runs",
  "location": "file:///…/prove-runs/.poisson/ui/index.html"
}
```

A store that does not exist is refused, as `runs` refuses it:

<!-- docs-check: run -->
```console
$ poisson-prove --store nowhere ui  # exits 1
error: no store at nowhere. …
  next: poisson-prove --store nowhere sweep SPEC.toml --target pkg.module:rollout
…
```

## Exit codes

- `0`: the dashboard was built; an empty store gets an empty runs page.
- `1`: refused: no store at that path, or a store this version cannot read.
- `2`: the command line is wrong.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

The store's `.poisson/ui/`: `index.html`, a page per run under `runs/` and per saved comparison
under `comparisons/`, and the two files every page shares, `style.css` and `ui.js`. It is derived
from the runs and the saved comparisons, so deleting it loses nothing; `ui` builds it again.
