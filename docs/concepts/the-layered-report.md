# The layered report

Under the verdict block and the per-condition tables, `diff` and `report` print a layered report:
the same comparison asked from the top down. First, did anything change at all? Then, along which
lines did it change? Only then, which conditions? Each layer is tested only where the one above it
found something, and the last line gives a bound on the false discoveries of the whole procedure,
with the assumption it rests on. It is
worked here on the example's two runs, the mock agent before and after its retry patch.

<!-- docs-check: setup quickstart -->

<!-- docs-check: run -->
```console
$ poisson-prove diff
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
…
omnibus: "no cell changed" is rejected (p = … < q 0.050) over 9 cells x 2 events
  min-p of location and dispersion; 4,000 within-cell permutations, pair_swap, seed 0
…
fault lines: grouping task_id (axis), 3 groups; …
…
cells: "this cell did not change" tested by BH within each of … rejecting groups at q 0.050: …
…
bound: depth 3 (3 configured); outer-nodes false discovery rate at most …
…
```

## The omnibus

One test over the whole family, every condition and every event at once: is the hypothesis that
no condition changed tenable? It compares two statistics, the mean change across conditions
(`location`) and the spread of the changes (`dispersion`, their root mean square), and combines
them by their smaller p-value, calibrated on the same permutations so that taking the smaller
costs nothing in error rate. The p-values come from permutations within each condition: for paired
runs, swapping which arm each episode pair belongs to (`pair_swap`), 4,000 times with seed 0 by
default (`--permutations`, `--seed`). The `p floor` is the smallest p-value that many permutations
can express; a p at the floor is a bound, not a measurement. `informative cells` counts the
conditions whose permutations can move the statistic at all: a condition where every episode
ended the same way in both runs cannot.

The omnibus catches a change spread thinly over many conditions, too small in any one of them to
be flagged on its own.

## The fault lines

When the omnibus rejects, the conditions are grouped along one axis, and each group is tested the
same way: did no condition in this group change? The groups' p-values are held to the false
discovery rate across groups (Benjamini and Hochberg, at q). The grouping is named on the line,
and chosen in this order: the one `--by KEY` names; else the sweep's own axes, in the order the
baseline run declares them; else a key named `task_family`, `task_id` or `task`; else the whole
grid as one group. A grouping is passed over for the next when the other run does not share it or
its groups cannot resolve the largest group-level change you accept (`--max-group-mde`, 0.20 by
default), and each group's own limit is printed as its `group MDE`.

Here the grouping is `task_id`: the line says, per task, how many conditions it holds, how many
moved, and whether the group as a whole changed.

## The cells

Within each group the omnibus and the fault lines rejected, each condition's change is tested
(Benjamini and Hochberg within the group), and the conditions that changed are listed with their
change, their adjusted p-value and their detection limit. `--depth 2` stops at the fault lines.
This layer's flags can differ from the flat per-condition table above it, which tests every
condition in one family: the layered procedure spends its error rate where the upper layers
found something.

## The bound

The last line bounds the false discovery rate of the whole procedure over its outer nodes, the
results it reports at its deepest level, from Yekutieli's result for hierarchical testing (2008).
The bound is computed from the depth and the grouping's shape alone, never from what rejected. It
assumes each p-value is independent of those above it; here the group and omnibus statistics are
built from their own conditions, so the line says plainly that this assumption is not established.
Read the bound as an order of magnitude, not a guarantee. The cells this layer flags carry only
that bound (here well above q), a weaker promise than the flat per-condition table's false
discovery rate of q: when the two disagree, the flat table is the one held to q.

## How to read it

Start from the verdict word and the flat table: they answer "which conditions changed". Read the
layers when you want to know where the change lives: one task, one failure rate, everywhere a
little. A rejected omnibus with no condition flagged in the flat table is the case to look for: a
change too small to flag in any one condition but visible over the family, which more
replicates per condition may resolve. [What the statistics claim](what-the-statistics-claim.md) covers the per-condition
tests the layers build on.
