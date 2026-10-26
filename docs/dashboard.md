# The dashboard

The dashboard is a set of static pages over your store: the runs, the saved comparisons with their
verdicts and charts, each condition, and the episodes behind an outcome. It is built into the
store's `.poisson/ui/` and opened from disk in any browser. Nothing is served and nothing is loaded
from the network: the pages hold the data, the charts are drawn into them, and two shared files
(`style.css`, `ui.js`) do the rest.

## Building it

`poisson-prove ui` builds it and prints where it is; `--open` opens it in your browser:

<!-- docs-check: setup quickstart -->

<!-- docs-check: run -->
~~~console
$ poisson-prove ui
ok  dashboard at file:///…/prove-runs/.poisson/ui/index.html
~~~

Once a store has a dashboard, every command that writes to the store keeps it current: a `sweep`
adds its run, and a comparison saved by `report`, `serve`, `diff --save` or `check --save` adds its
pages. `diff` and `check` without `--save` save nothing, so they add nothing. The pages are derived
from the runs and the saved comparisons, so deleting `.poisson/ui/` loses nothing: `ui` builds it
again. [`poisson-prove ui`](commands/ui.md) has its options.

Every view below is also a screen of the [terminal app](terminal-app.md), and each page shows every
fact its screen does.

## Runs

The front page, `index.html`: every run in the store with its name, status, backend, target and
row counts, newest first, and every saved comparison with its verdict. Each links to its page.

## Run

One run: its status and how many of its rollouts ran, its target and backend, its outcomes and
which are failures or successes, the design it was swept with (the smallest change it could
detect, at which base rate), and each condition's share of each outcome with a 95% interval. Each
share links to the episodes behind it.

## Comparison

One saved comparison: the verdict word and its sentence, then the detail lines `diff` prints (the
method, the two runs, the verdict rule, the limits, the intervals, the fragility), a count per
event of the conditions that got worse, got safer, did not move, or could not tell, the trades,
and every condition with its change. Charts and the could-not-detect page are linked from it.

## Condition

One condition of a comparison: each run's share of the event with its interval and its counts,
the change with its interval, the test with its p-value and q, the smallest rise and fall it could
have detected, and links to the episodes of each run and to the condition's incidence chart.

## Episodes

The episodes of one run that ended in one event, in one condition: each with its seed and replicate,
its outcome and time, and the code that reproduces it, as `inspect` prints them.

## Could not detect

The question the two nothing-moved words answer, asked of every condition that did not change:
could it have caught a change of the threshold, from where it was? Each condition's rise and fall
limits are listed against the threshold, with the ones that could not tell first. It is where to
look when a comparison says `too small to tell`.

## Charts

Each saved comparison draws, per event: a heatmap of the change in every condition (the verdict
colours the cell), the change and its interval for every condition, and the detection limits
against the threshold; and per condition, each run's cumulative incidence of the event over time.
Every chart has its own page and is drawn into the comparison's pages; the drawings are made when
the comparison is saved.

## What is on disk

<!-- docs-check: skip: a picture of the folder, not a command -->
~~~text
prove-runs/.poisson/ui/
  index.html                      runs
  runs/<run id>.html              a run
  runs/<run id>/episodes/...      episodes, per event and condition
  comparisons/<id>.html           a comparison
  comparisons/<id>/<condition>.html            a condition
  comparisons/<id>/could-not-detect.html
  comparisons/<id>/heatmap-<event>.html        and the other charts
  style.css
  ui.js
~~~

[The artifact format](artifact-format.md) describes the saved comparisons the pages are drawn from.
