# Quickstart

The first run takes a minute and needs no key, no account and no network. It sweeps a mock agent,
sweeps a patched version of it on the same seeds, and compares the two. Then it does the same on a
rollout of your own.

## Install

Make a virtual environment first: Homebrew's Python and current Debian and Ubuntu refuse a
`pip install` into the system Python.

<!-- docs-check: run -->
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install poisson-prove
```

Prove needs Python 3.11 or later, on macOS or Linux.

## The example

`init --example` writes `prove.toml`, the spec of the example sweep: the keyless mock agent over
three tasks and three tool failure rates, 194 replicates of each of the nine conditions.

<!-- docs-check: run -->
```console
$ poisson-prove init --example
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
  next: poisson-prove sweep
```

`sweep` reads `./prove.toml`, prints the plan, and with `--yes` runs it without asking (on a
terminal it asks `[y/N]`; piped or in CI it needs `--yes`):

<!-- docs-check: run -->
```console
$ poisson-prove sweep --yes
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
  target  poisson_prove.examples.mock_agent:rollout (imports, takes cfg and seed)
  outcomes  failures: timeout, violated
…
  smallest rise one condition alone would be flagged for  0.199 at its worst base rate, 0.400 (Fisher, q 0.05 over 18 tests, 4 times in 5; you accept up to 0.200)
done  1,746 rollouts in run "mock-agent 2026-10-26 a" (complete) in … s
…
  next: poisson-prove sweep --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest
```

The plan says what will run and what it costs (nothing, here), and the smallest change in one
condition's failure rate this design would catch 4 times in 5. Had that been above the 0.20 you
accept by default, the sweep would have refused before running anything and said how many
replicates it needs. The run gets a name, `mock-agent`, the date and a letter, which every later
command accepts in place of its id.

The patched agent retries a failed tool call once. `--pair-with latest` gives its run the same
seeds as the last one:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --yes --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
done  1,746 rollouts in run "mock-agent 2026-10-26 b" (complete) in … s, paired with "mock-agent 2026-10-26 a"
…
  next: poisson-prove diff
```

`diff` with no runs named compares the previous run with the latest:

<!-- docs-check: run -->
```console
$ poisson-prove diff
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
…
  next: poisson-prove report --x task_id --y tool_fail_rate
```

`trade`: the patch made the agent safer in some conditions and worse in at least one. The forbidden
fallback (`violated`) fell and never rose; running out of tool calls (`timeout`) rose where tools
fail most, because the retries use up the budget. [First look](recipes/first-look.md) reads every
block of this output, and [What the statistics claim](concepts/what-the-statistics-claim.md) says
what each verdict word means.

The `next:` line writes the comparison as a report, with a heatmap of the change per condition:

<!-- docs-check: run -->
```console
$ poisson-prove report --x task_id --y tool_fail_rate
ok  wrote prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b (3 files)
  wrote  prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b/report.md
  wrote  prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b/heatmap.svg
  wrote  prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b/receipt.html
  saved  comparison …
…
```

Everything is in `./prove-runs`: the runs, and under `.poisson/` the saved comparison.
`poisson-prove` alone on a terminal opens the [terminal app](terminal-app.md) over it, and
`poisson-prove ui` builds the [dashboard](dashboard.md).

## On your own rollout

`init --target` writes a commented spec for your own rollout, to edit:

<!-- docs-check: run -->
```console
$ poisson-prove init --target my_rollout:rollout --out mine.toml
ok  wrote mine.toml: a template; set its axes to what you vary
  next: poisson-prove sweep mine.toml
```

Set its axes to what you vary and its outcomes to how your agent's cases end, check it with
`poisson-prove sweep mine.toml --dry-run`, which runs nothing, then sweep, change your agent, and
sweep again with `--pair-with latest`. [Your own agent](your-own-agent.md) does exactly this on a
small example, and [Set Prove up with your coding agent](setup-with-your-agent.md) has your coding
agent write the two files for you to review.
