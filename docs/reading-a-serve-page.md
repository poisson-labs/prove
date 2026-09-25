# Reading a serve page

`proofload serve A B --event NAME --x AXIS` builds one page for one stored pair and holds it on a
loopback port until Ctrl-C. The page is a snapshot: nothing on it is fetched, and it does not change
while it is open. Fourteen sections, in page order. Each says what it answers and what it cannot.

## Summary

The answer in plain words: whether either run stopped early, whether two named outcomes are exact
complements of each other, then per outcome how many conditions got worse, how many got safer and
how many show no significant change; the conditions that got worse, before and after, with how sure
the run is of each; and the least sensitive condition the run did not call a change, which is the
detection limit "0 worse" rests on. It states counts and never a verdict: whether a change should
ship is not something the page knows. Every sentence is a field of `serve --json`.

## Events

The outcomes the comparison is over, as given by `--event`; nothing here is inferred.

## Omnibus

Whether anything changed at all, across the whole family of conditions, before any single condition
is named. Its p is bounded by the number of permutations and says so.

## Result

The headline count per outcome and the test that produced it. When the two runs share their seeds
and the test treats them as separate samples, a line says so. When two outcomes are exact
complements the line says so; when one outcome fell where another rose, the line counts where.

## Honesty

What the run could not have seen: the worst-powered condition it called unchanged, the worst-powered
overall, the intervals, and the bound the whole procedure controls at. It cannot say a condition is
safe.

## Not verified

What this page cannot confirm about the two runs, and whether a change is planned that would.

## Fault lines

Which grouping of conditions the layered report admitted and which groups moved. It cannot say why.

## Cells

The conditions the layered report rejected inside each rejecting group. It cannot say a condition
outside a rejecting group is unchanged.

## Heatmap

Every condition on the two axes, coloured by its change; click a cell to open it below. Text inside
the figure is not a click target.

## Cell

One condition's own numbers, chosen from the picker or by clicking. Every value is a field.

## Holes

The conditions the two runs do not share, how many of each cause, and where each is.

## Worst cells

The largest rises per outcome, as a table.

## Run pair

The two runs' identity and tallies as stored, and the sign convention. `status` here is what the
writing process recorded; the page does not re-derive it.

## Provenance

The parameters of the comparison and the version that produced it.
