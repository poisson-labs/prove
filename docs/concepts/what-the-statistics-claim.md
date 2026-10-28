# What the statistics claim

Prove compares two runs of the same sweep and says, per condition, whether a failure became more
or less common, and how large a change it could have seen where it saw none. This page says in
plain words what each number and each verdict word means, and what Prove never claims.

## The pieces

**A condition** is one combination of the sweep's axis values, such as task `refund` at tool
failure rate 0.55. Each condition runs the same number of episodes, its replicates, in each run.
Prove compares a condition in one run with the same condition in the other, never across
conditions.

**An event** is an outcome being counted, such as `timeout`. A comparison reads the events you
name with `--event`, or else the failures and successes the runs declare, or, for runs that
declare none, every outcome but the most frequent one. Whether a rise of an event is
bad or good comes from the runs' `[declare]` table: a failure that rises is worse, a success
that rises is safer. An event with no declared kind is only said to go up or down.

**A rate** is the share of a condition's episodes that ended in the event by the comparison's
horizon, the most time an episode had. Every outcome present competes with the others: an
episode that ended in `violated` cannot also time out. Episodes that errored, with no outcome at
all, are left out of the rates and counted on their own (the coverage); when one run errored much
more than the other in a condition, the comparison says so.

**A test** asks, per condition and event, whether the two rates differ by more than chance would
explain. There are three, and the comparison names the one it used:

- the paired test (exact McNemar), for two runs that share their seeds (`--pair-with`): it
  compares each episode with its twin, and only the pairs that ended differently carry
  information, which makes it the stronger test when the runs agree on most episodes. It is the
  default for paired runs. [Pairing](pairing.md) explains when runs are paired;
- Fisher's exact test, for two runs treated as separate samples: the default otherwise;
- the log-rank test, on how soon the event happens rather than whether it does by the horizon
  (`--method logrank_bh`). It tests the event's own hazard, and says so when a competing outcome
  moved at the same time.

**q** is the false discovery rate, 0.05 by default. Many conditions times several events is many
tests, and some would come out significant by chance alone. Prove adjusts each p-value over the
whole family of condition-event pairs (Benjamini and Hochberg) and flags a pair when its adjusted
value is below q: of the pairs flagged, at most 5% on average are expected to be false alarms. That
guarantee is proven for tests that are independent or positively related; the events of one
condition compete with each other, so read it as close rather than exact.

**The verdict word** is stricter than the flags. It counts only the changes that also hold at the
family-wise level (Holm's procedure at q), where the chance of even one false alarm in the whole
comparison is at most 5%. A condition flagged but not counted is shown as such
(`flagged only`).

**An interval on the change** comes with every condition, significant or not: a score interval
on the difference of the two rates (Miettinen and Nurminen's for separate samples, Tango's for
paired ones), at a level that keeps the flagged intervals' false coverage at q (Benjamini and
Yekutieli). Each condition's own share has a 95% Wilson interval, not adjusted.

**The detection limit** is the smallest change in a condition's rate the test would have flagged
4 times in 5 had that condition alone changed, from the rate it was at. Prove gives it per
direction, a rise and a fall, for every condition, and on every line that says nothing moved. A
condition whose rate was 0 has no room to fall, and one with too few episodes may have no limit at
all; both are said in words.

**The power gate** is the same limit computed before a sweep runs, at the worst base rate the
design could meet. If it is above the change you accept, `--max-mde`, 0.20 by default, `sweep`
refuses the design and names the replicates it needs. A run records the change it accepted; the
comparison uses it as its threshold.

**The fragility** is how many episodes would have to have ended differently for the verdict word
to change. A small number means the word rests on a few episodes.

## The verdict words

The first word of `diff`, `report`, `serve` and the dashboard is one of these.

- `worse`: at least one condition got significantly worse, and none got safer.
- `safer`: at least one condition got significantly safer, and none got worse.
- `trade`: at least one condition got worse and at least one got safer, in any events. One
  condition where one failure fell and another rose (a cell-level trade) counts as both.
- `no significant change`: no change counted at the family-wise level, and every condition that
  did not count could have caught a change of the threshold you accepted, 4 times in 5. The line
  says the largest limit it read. A condition flagged only at the false discovery rate can still be
  there; the `flagged only` line says so.
- `too small to tell`: no change counted at the family-wise level, and at least one condition could
  not have caught a change of the threshold. It is not a pass: nothing was seen because not enough
  could be.
  [When it says too small to tell](../recipes/when-it-says-too-small-to-tell.md) says what to
  change.

When an event's kind is not declared, the words say only which way the rates went:

- `higher`: at least one condition's rate rose significantly, and none fell.
- `lower`: at least one fell, and none rose.
- `mixed`: some rose and some fell.

`check` adds its own two words, `passed` and `failed`, from the rule `--fail-on` gives; the
comparison's word is on its `comparison` line.

## What Prove never claims

- **Causation.** Prove compares two runs. That the change you made caused the difference is your
  reading, and it holds only as far as nothing else differed between the runs: the model's
  version, the provider's load, the data. Paired runs share their seeds, not the world.
- **Conditions you did not sweep.** A verdict is about the conditions in the grid. Nothing is
  said about a task, a rate or a model that was not an axis value.
- **Cells it did not run.** A condition that one run has and the other lacks is listed in the
  coverage and compared with nothing.
- **What an outcome means.** Prove counts labels; whether `crashed` meant your agent or your
  provider is decided by your rollout. [Defining outcomes](../defining-outcomes.md) is about
  exactly this.
- **No change.** `no significant change` says a change as large as the threshold would have been
  caught 4 times in 5 in every condition, and none was; a smaller change, or a missed one, can
  still be there.
- **Error rates after peeking.** The error bounds hold for a comparison read once. A partial run
  carries a note saying so, and so does a run resumed with more replicates after a comparison of it
  was read on this machine: Prove keeps the list of comparisons it has printed in
  `~/.cache/poisson-prove/compared.jsonl`, so a comparison read on another machine, or in CI, is
  not known to it.

[The layered report](the-layered-report.md) covers the tests that sit above the conditions: the
omnibus, the fault lines and the bound.
