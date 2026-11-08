# What a declaration checks

A sweep file may declare what the run expects of itself, in a `[declare]` table.
[The sweep spec](sweep-spec.md) lists its keys; this page says what Prove records, stamps and
prints from them.

## The table

A `[declare]` table names:

- the steps the target is expected to execute (`steps`);
- the outcome labels it can emit (`outcomes`);
- which of those steps are gates (`gates`, a subset of `steps`);
- which outcomes are failures and which successes (`failures`, `successes`).

<!-- docs-check: run -->
```toml
[declare]
steps = ["plan", "check", "lookup", "verify"]
gates = ["check"]
outcomes = ["resolved", "escalated"]
```

Any of them may be absent. A table that declares nothing is refused, and so is a duplicate: a
repeated name in a hand-written list is a typo, and collapsing it would be guessing at what was
meant.

## Where it is recorded

The declaration is recorded on the run's manifest as `declared`. The table above, as a run of it
recorded it:

<!-- docs-check: run -->
```json
{
  "declared": {
    "gates": ["check"],
    "outcomes": ["escalated", "resolved"],
    "steps": ["check", "lookup", "plan", "verify"]
  }
}
```

It is not part of the sweep's identity, so a declaring arm and a non-declaring arm derive the same
seeds and still pair under `diff`.

## Gates

On the way to the store, a span whose `step_name` is a declared gate and which carries no gate of
its own is stamped `gate = "declared"`. A span the target itself marked `"emitted"` keeps that.
A stored span of the run above, some of its keys:

<!-- docs-check: run -->
```json
{"name": "check_refund", "step_name": "check", "gate": "declared"}
```

## What `never reached` means

For a run that declared, `report`, the receipt, `serve` and `inspect` print, against the
declaration:

- the declared steps, and the declared steps no span in this run carried (`never reached`);
- the observed step names the declaration does not name;
- the declared outcomes, and the observed outcomes it does not name;
- the declared gates, and the declared gates with no span (`gates never reached`);
- the gates the target emitted that the declaration does not name.

On the run above, whose target never takes its `verify` step, `inspect` prints:

<!-- docs-check: skip: lines of inspect's output on a run made for this page, not a command -->
```text
- declared steps: check, lookup, plan, verify
- never reached: verify
- undeclared steps: none
- declared outcomes: escalated, resolved
- undeclared outcomes: none
- declared gates: check
- gates never reached: none
- emitted gates not declared: none
```

A declared step with no span means exactly that: this run's spans did not show it. It does not
mean the target cannot reach the step; it does not mean the step was not instrumented; it does not
mean anything is wrong. A sweep whose configs never take the `verify` branch reports
`never reached: verify` correctly, and that is the finding.

It says nothing at all about a run with no declaration, for which the lines do not exist and the
phrase appears nowhere. A declaration that matches nothing, as on a run whose capture was off for
the whole run, prints every declared step and is not refused.

## Two runs that declare differently

- `diff` refuses two runs that declare different, non-empty outcome sets, since two competing sets
  are two quantities wearing one name.
- `--resume` refuses a sweep whose declaration differs from what the run recorded, while
  `--pair-with` does not.

A misspelt key inside `[declare]` is refused when the sweep file is read, as
[What capture stores](what-capture-stores.md#a-misspelt-table-or-key-is-refused) shows.
