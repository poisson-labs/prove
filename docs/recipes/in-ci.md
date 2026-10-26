# In CI

Make a change to the agent fail the build when it makes the agent fail more often. `check` is the
gate: it compares the baseline run with the candidate over the events you name and exits 4 when a
condition got worse, 0 when none did. Its `--json` output is what a bot needs to comment on the
pull request.

<!-- docs-check: setup quickstart -->

## The gate

On the example's two runs, a gate on time-outs fails, because the patch runs out of tool calls
more often where tools fail most. The exit code is 4:

<!-- docs-check: run -->
```console
$ poisson-prove check --event timeout  # exits 4
failed  timeout: … worse, … safer in 9 conditions; fail on worse; failed in task_id refund · tool_fail_rate 0.55 (paired test on shared seeds)
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  comparison  trade
…
```

Exit codes mean one thing each, so a CI step can tell them apart: 0 passed, 4 failed, 1 refused
(nothing was compared, such as an event the runs do not have), 2 a wrong command line, 3 an
unexpected failure.

## A comment for the pull request

`--json` prints the same result as one document, with `passed`, the verdict, its sentence and
every condition. Write it to a file, then turn it into the comment your bot posts:

<!-- docs-check: run -->
```console
$ poisson-prove check --event timeout --event violated --json > check.json  # exits 4
```

<!-- docs-check: run -->
```python
import json

result = json.load(open("check.json"))
lines = [f"**Prove: {result['verdict']}**", "", result["sentence"]]
print("\n".join(lines))
```

## The workflow

In CI the sweep runs piped, so it needs `--yes`, and the output is plain text. The baseline is the
run of your main branch; keep its store between jobs (here, a cache), sweep the pull request's
code paired with it, and gate:

<!-- docs-check: run -->
```yaml
name: prove
on: pull_request
jobs:
  prove:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poisson-prove -e .
      - uses: actions/cache/restore@v4
        with:
          path: prove-runs
          key: prove-baseline-${{ github.event.pull_request.base.sha }}
      - run: poisson-prove sweep --yes --pair-with latest
      - run: poisson-prove check --event unresolved --event timeout --json > check.json
      - if: always()
        run: python make_comment.py check.json
```

The main branch's job is the same without the pull request's steps: it sweeps, and saves
`prove-runs` with `actions/cache/save` under its own commit. Keep the spec, the target and the
replicates the same on both sides, or the two runs will not have the same conditions to compare.
A model key your agent needs goes in the CI's secrets, as for any test that calls the model.

## What this does not tell you

Whether the main branch's run is still a fair baseline. A model's answers drift with its version
and its provider's load, so a baseline swept weeks ago differs from today's run in more than your
change. Re-sweep the baseline when the model or the provider changes, and when in doubt run both
sides in the same job. A passing gate says no condition counted as worse; each condition's detection
limit says how large a rise it would have caught 4 times in 5. It does not say nothing got worse.
