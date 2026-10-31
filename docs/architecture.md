# Architecture

For contributors: how Prove is put together, and where a change belongs. The short version is
one core and several faces. The core alone computes, reads and writes; a face asks, prints, draws or
serves what the core returns. Nothing a person reads is computed twice.

## The core

`poisson_prove.core` holds every operation the verbs run: reading a sweep spec, planning a sweep
and checking its power, running it, comparing two runs, checking a comparison against a gate,
inspecting episodes, paired replay, listing and naming runs, saving a comparison, and building the
views the dashboard and the terminal app show. Each operation returns a result object whose
`to_json()` is one strict JSON document, and refuses by raising `Refusal`, whose text is the sentence
a face prints. No operation prints, asks a question, exits, or opens a browser.

The core is private: its names may change in any release. Its public view is
`poisson_prove.compare`, which gives the comparison, the gate and the run names as functions over a
store, returning the same result objects; [Python API](python.md) lists the rest of the public
surface (`poisson_prove`, `poisson_prove.stats`, `poisson_prove.store`, `poisson_prove.trace` and the
others).

Under the core sit the modules that do the work: the spec reader (`sampler`), the executors (local,
Modal, Burla), the store, the statistics (`stats`, `survival`, `diff` and the layered `tree`), the
detection limits and the verdict, paired replay (`paired`), traces and capture, and fault
injection (`chaos`). They know nothing of faces.

## The faces

- **The command line**, `cli`: parses arguments, calls one core operation per verb, and prints its
  result: a verdict line first, `label  value` detail lines, tables, `next:` lines, `note:` and
  `error:` lines, or the result's JSON with `--json`. It owns the exit codes and the `[y/N]`
  question.
- **The terminal app**: `poisson-prove` with no verb on a terminal. Each screen renders one core
  view; it computes nothing, and writes only through the core (a comparison it shows is saved, a
  sweep it runs is the core's). See [The terminal app](terminal-app.md).
- **The static dashboard**: `poisson-prove ui`, and every write that refreshes it. Each page is one
  core view rendered to HTML. See [The dashboard](dashboard.md).
- **The serve page and the report**: `serve` and `report` render the same comparison as a page on
  a loopback port and as `report.md`, `heatmap.svg` and `receipt.html`.
- **Python**: `poisson_prove.compare`, for a script or another tool.

## The renderers

A face does not format numbers or choose words itself. The shared renderers do it once:

- the look (`_look`): how a number, a share, a limit, a hash or a name reads on any surface;
- the facts (`_facts`): the detail lines every surface prints about a verdict, as label and text,
  so the command line, the report, the page and the app say the same thing in the same words;
- the terminal renderer (`_render_term`, `_render_pretty`): plain lines through a pipe, and the
  pretty rendering with Rich on a terminal, from the same lines;
- the charts (`_render_charts`): Prove's own SVG, drawn when a comparison is saved;
- the dashboard renderer (`_render_ui`): one page per view, every fact marked with its place in the
  view, nothing loaded from the network.

## Where a change goes

- A new number or a new decision: the core, with its result's JSON, and every face shows it.
- A new way to show an existing result: a face, reading the core's view; never a second
  computation.
- A new word on a surface: the facts or the look, so every surface changes together.
- A new verb: a core operation first, then its face in `cli`, its page under `docs/commands/`, and
  its view in the app and the dashboard if it has one.

The tests hold these lines: the faces are checked against the core's JSON, the pages against the
views, and the docs against the commands they show (`CONTRIBUTING.md` says how to run them).
