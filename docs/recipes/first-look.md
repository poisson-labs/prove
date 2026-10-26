# First look

Run the keyless example, then read what `diff` prints, block by block. It takes a minute and needs
no key.

## Run it

<!-- docs-check: run -->
```console
$ poisson-prove init --example
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
  next: poisson-prove sweep
$ poisson-prove sweep --yes
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
$ poisson-prove sweep --yes --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
  next: poisson-prove diff
```

The mock agent runs a task (`search`, `checkout`, `refund`) through its tools, at a tool failure
rate of 0, 0.3 or 0.55: nine conditions, 194 episodes each. It ends `completed`, `violated` (three
tool failures in a row made it take a forbidden fallback) or `timeout` (it used up its 20 tool
calls). The patched agent retries a failed call once, on the same seeds.

## Read it

<!-- docs-check: run -->
```console
$ poisson-prove diff
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
…
  verdict rule  the verdict counts changes at the family-wise level (Holm, q 0.05 over 18 tests); …
…
  limits  the smallest change one condition alone would be flagged for, 4 times in 5, …
  intervals  on each condition's change: Tango at 97.5%, …
…
inferred: no event was given, so the event set is violated, timeout; the non-event is completed, the most frequent outcome
…
coverage: holes=0 (only_a=0, only_b=0, no_outcome_a=0, no_outcome_b=0, no_outcome_both=0), no_outcome a=0 b=0
…
omnibus: "no cell changed" is rejected …
…
bound: depth 3 (3 configured); …
…
  next: poisson-prove report --x task_id --y tool_fail_rate
```

**The verdict line.** The first word is the verdict: `trade`, because some conditions got safer
and at least one got worse. Then, per event, how many conditions it fell in and rose in, and the
test. The counts move a little between pairs of sweeps; the word did not, in our runs.

**The detail lines.** `method` names the test and why it was chosen: the runs share their seeds,
so each episode is compared with its twin. `before` and `after` are the runs, by name. A `trade`
line names a condition where one event fell and another rose: here, `refund` at 0.55, where the
retries keep the agent off the forbidden path and use up its tool calls. `verdict rule` says the
word counts the changes that hold at the family-wise level (Holm), while each condition's flag is
held to the false discovery rate (Benjamini-Hochberg); a `flagged only` line counts the
conditions that are flagged and not counted. `limits` says what the detection limits mean, and
names the rows that have none. `intervals` says how the interval on each condition's change is
computed. `fragility` says how many episodes would have to have ended differently for the word to
change.

**The events.** `inferred` says which outcomes were compared: none was named, so every outcome but
the most frequent one, `completed`.

**The tables.** One per event: each condition with its episodes, its events in each run, each
run's share with a 95% interval, the change and an interval on it, the test's statistic, its p and
adjusted q, the verdict, and the smallest rise and fall it could have detected. Then the trades,
and the coverage: conditions one run lacks, and episodes with no outcome, none here.

**The layered report.** The `omnibus` asks whether anything changed at all; the `fault lines` ask
along which task; the `cells` ask which conditions, within the tasks that changed; the `bound`
caps the false discoveries of the whole procedure. [The layered report](../concepts/the-layered-report.md)
explains each.

**The next command.** `next:` lines are whole commands. This one writes the comparison as a report
with a heatmap, task across and tool failure rate down:

<!-- docs-check: run -->
```console
$ poisson-prove report --x task_id --y tool_fail_rate
ok  wrote prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b (3 files)
…
```

## What this does not tell you

Whether the patch is good. The verdict says the patch traded forbidden fallbacks for time-outs in
these nine conditions of a mock agent; whether that trade is worth it is your call, and nothing is
said about tasks or failure rates that were not swept. [What the statistics claim](../concepts/what-the-statistics-claim.md)
lists what Prove never claims.
