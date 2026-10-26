# Censoring and competing risks

An episode ends one way, at one time. That simple fact shapes how Prove counts: an agent that stops
taking forbidden fallbacks may run out of time more often instead, and a run cut short tells you
nothing about what would have happened next. This page says how Prove reads time, the horizon, the
outcomes that compete, and the episodes that never got an outcome at all.

## Time and the horizon

Every episode reports `t`, when it ended, and `horizon`, the most `t` could have been, in the
spec's `t_unit` (steps, tool calls, seconds). The mock agent's horizon is 20 tool calls: it
either finishes its task, takes the forbidden fallback, or reaches the 20th call and times out.

A comparison reads both runs up to a common horizon, the shorter of the two runs' horizons, so the
two rates count the same window of time. An event that happened after the common horizon is not
counted in it.

## Outcomes compete

Every outcome present in the two runs is a competing ending: an episode that ended in `violated`
cannot also end in `timeout`. So a rate here is a cumulative incidence: the share of episodes that
ended in this event by the horizon, with every other ending counted as what it is, not as
"survived". Prove computes it with the Aalen-Johansen estimator; when every episode ends by the
horizon, as most do, that is simply the share of episodes that ended in the event.

This matters most when you read one event alone. A patch that removes one way of failing leaves
those episodes to end some other way, and if the other way is also a failure, it rises. The
comparison says so in a line of its own, a trade: a condition where one event fell and another
rose. The example's patch does exactly this where tools fail most:

<!-- docs-check: setup quickstart -->

<!-- docs-check: run -->
```console
$ poisson-prove diff
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
  trade  task_id refund · tool_fail_rate 0.55: violated fell, timeout rose
…
```

The tables say the same per condition: each event's share in each run is its share by the horizon,
with a 95% Wilson interval, and a share is starred when it is not its rate, which happens when a
run was censored before the horizon.

## Censoring

For the rates above, an episode that ended in another outcome is not censored: it is counted as
ending that way, a competing ending. Only an episode still running at the common horizon is
censored there. The log-rank test (`--method logrank_bh`) reads time differently: for it, an
episode that ended in any outcome other than the event is censored at its time, still at risk until
then, and the test asks whether the event happens sooner, not only whether it happens by the
horizon. It tests the
event's own hazard among the episodes still running, so when a competing outcome moved too, the
row says so: a lower hazard of one ending can come from a higher hazard of another.

## Episodes with no outcome

An episode that raised an error, or ran past `--episode-timeout`, has no outcome. It is not a
failure and not a success, and it is left out of every rate: counting it either way would turn a
crash in the harness into a finding about the agent. It is counted on its own instead: `runs`
lists each run's rows without an outcome, the comparison's coverage table has them per condition,
and when one run errored significantly more often than the other in a condition, the comparison
warns that the rates there may differ for that reason. `inspect` shows the errors, by kind.

A sweep in which every rollout errored is stored and exits 3, pointing at `inspect`: there is
nothing to compare. If errors are part of what you are measuring (an API that times out on the
agent), make them outcomes in your rollout, so they are counted. [Defining outcomes](../defining-outcomes.md)
says how to tell which is which.
