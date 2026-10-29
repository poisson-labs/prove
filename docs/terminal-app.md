# The terminal app

`poisson-prove` with no verb, on a terminal, opens the terminal app: your runs, your comparisons
and their verdicts, a sweep of the spec in the folder, and every condition and episode behind a
verdict, reached by keys alone. It computes nothing of its own: every number, verdict and sentence
on its screens is the one the commands print.

## How it opens

<!-- docs-check: skip: opens the terminal app, which needs a terminal -->
~~~console
$ poisson-prove
$ poisson-prove --store path/to/prove-runs
~~~

It opens on the store the commands use, `./prove-runs` (or `$POISSON_PROVE_STORE`), or the one
`--store` names, and `s` sweeps the folder's `prove.toml`. It opens only when it can be used: stdin
and stdout are both a terminal, `CI` is not set (set to anything, it is CI), and `TERM` is not
`dumb`. Otherwise `poisson-prove` with no verb exits 2 and points at `poisson-prove --help`, so a
script never finds itself inside an app. With `NO_COLOR` set to anything but empty, the colours go
and bold, dim and reverse stay. The app needs a window of at least 80 by 24; in a smaller one it
says the size it needs and waits.

It opens on Prove's banner, the mark of the Poisson Labs tools with Prove's name and version, while
it reads the store, then shows home after a moment; any key shows home sooner, and `q` quits.

## The screens

Every screen has the same frame: the tool and the screen's name at the top with what it is about,
the store at the top right, the body, and the keys at the bottom. The focused row is in reverse
with `›` beside it. Home, at 80 by 24, with the example's two runs and their saved comparison
(a command too long for its line starts on the next one, whole, so it can be copied):

<!-- docs-check: skip: a screen of the terminal app, not a command -->
~~~text
poisson-prove · home                                                  prove-runs
────────────────────────────────────────────────────────────────────────────────
  ok  2 runs and 1 saved comparison in prove-runs

  latest     mock-agent 2026-10-26 b (complete)
  compared   mock-agent 2026-10-26 a → b: trade
  next
poisson-prove report "mock-agent 2026-10-26 a" "mock-agent 2026-10-26 b" --x
task_id --y tool_fail_rate
  dashboard  index.html

  kind        name                         result     rows  created
› comparison  mock-agent 2026-10-26 a → b  trade            2026-10-26 14:53Z
  run         mock-agent 2026-10-26 b      complete  1,746  2026-10-26 14:46Z
  run         mock-agent 2026-10-26 a      complete  1,746  2026-10-26 14:46Z

────────────────────────────────────────────────────────────────────────────────
  ↑↓   enter   tab links   s sweep   c compare   r runs   y   ? help   q quit
~~~

- **home**: the store at a glance, the latest run and comparison, the next command, and every run
  and saved comparison, newest first.
- **runs**: every run with its number, status, backend and row counts, and the saved comparisons.
- **run**: one run: its status, target, outcomes and their kinds, the design it was swept with,
  and each condition's share of each outcome with its interval; `g` shows its event log.
- **sweep**: the plan `sweep` prints, the same question, then the sweep's progress; declining
  writes nothing.
- **compare**: pick two runs, `space` for before then after, or `l` for previous and latest, and
  `enter` compares them; the comparison is saved, as `diff --save` saves it.
- **comparison**: the verdict block `diff` prints, then each event's count of conditions worse,
  safer, unchanged and could-not-tell, and links to its charts.
- **conditions** (`t`): every condition and event with its shares before and after, its change,
  q, verdict and limit.
- **condition**: one condition: each run's share with its interval, the change and its
  interval, the test, the rise and fall it could have detected, and its episodes.
- **episodes**: the episodes behind an event in one condition, with the snippet that reproduces
  one; `e` moves to the condition's next event.
- **could not detect** (`d`): the question the nothing-moved words answer, and each unchanged
  condition's limits against the threshold.

Every screen but home, sweep and compare is also a page of the [dashboard](dashboard.md). A link on
a screen (a chart, a page) opens it in your browser with `Enter`; the first link shown builds the
dashboard if the store has none.

## The keys

On every screen:

| key | what it does |
|---|---|
| `↑` `↓`, `PgUp` `PgDn` `Home` `End` | move the focus |
| `Enter` | open the focused row's screen, or its link in the browser |
| `Esc` | back, with the focus where it was |
| `Tab` | move the focus between the links and the table |
| `/` | filter the table's rows by text; `Esc` clears it |
| `y` | copy the focused link's `file://` address, or the focused command |
| `m` | the lines the window has no room for, when a screen says so |
| `?` | the keys, and the screens |
| `q` | quit, exit `0`; during a question, no |
| `Ctrl-C` | quit, exit `130`; in a sweep, stop it and keep what is done |

On one screen: `s` sweep and `c` compare (home, runs), `r` runs (home), `t` conditions and `d` could
not detect (comparison), `v` back to the verdict (conditions), `e` the next event (condition,
episodes), `g` the event log (run), `space` and `l` (compare), and `p` (sweep, when the plan is
refused for its size) to plan again with the replicates the refusal names.

A sweep stopped with `Ctrl-C` leaves the run partial, as the command does, and once the app has
left the terminal it prints the same stopped line and the `next:` command that resumes it.

## What it never does

It makes no network call, reads no key, and writes only what the commands write: a comparison it
shows is saved through the same code `diff --save` uses, a sweep is the same sweep `sweep --yes`
runs, and like every command it keeps its notes under `~/.cache/poisson-prove/`.
`prove.toml` is never written. If Textual, the library it is drawn with, cannot be imported, the
app says it cannot start and exits 1; every verb still works.
