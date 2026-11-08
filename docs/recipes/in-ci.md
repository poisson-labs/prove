# In CI

Make a change to the agent fail the build when it makes the agent fail more often. `check` is the
gate: it compares the baseline run with the candidate over the events you name and exits 4 when a
condition got worse, 0 when none did. This page gives every file a GitHub repository needs to gate
its pull requests: a comment script and two workflows.

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
every condition. Write it to a file; `make_comment.py`, at the root of your repository, turns the
file it is given into the comment: the verdict, its sentence, and a table of the conditions that
counted for the verdict with each run's rate of the event. A refused check writes nothing to the
file, and its comment says so:

<!-- docs-check: file make_comment.py -->
```python
import json
import sys
from pathlib import Path

path = sys.argv[1]
text = Path(path).read_text(encoding="utf-8")
if not text.strip():
    print(f"**Prove: refused**\n\nThe check compared nothing, so {path} is empty. The job's log says why.")
    sys.exit()
result = json.loads(text)
print(f"**Prove: {result['verdict']}**\n\n{result['sentence']}")
counted = [(event, cell) for event, e in result["by_event"].items() for cell in e["cells"] if cell["holm"]]
if counted:
    print("\n| event | condition | before | after | change |\n|---|---|---|---|---|")
for event, cell in counted:
    condition = " · ".join(f"{axis} {value}" for axis, value in cell["config"].items())
    before, after = ("–" if r is None else f"{r:.0%}" for r in (cell["rate_a"], cell["rate_b"]))
    print(f"| {event} | {condition} | {before} | {after} | {cell['verdict']} |")
```

The failing gate, a passing one and a refused one:

<!-- docs-check: run -->
```console
$ poisson-prove check --event timeout --json > check.json  # exits 4
$ python make_comment.py check.json
**Prove: failed**
timeout: … worse, … safer in 9 conditions; fail on worse; failed in task_id refund · tool_fail_rate 0.55 (paired test on shared seeds)
| event | condition | before | after | change |
…
$ poisson-prove check --event violated --json > check.json
$ python make_comment.py check.json
**Prove: passed**
…
$ poisson-prove check --event unresolved --json > check.json  # exits 1
…
$ python make_comment.py check.json
**Prove: refused**
…
```

## The workflows

In CI the sweep runs piped, so it needs `--yes`, and the output is plain text. Two files go in
`.github/workflows/`:

<!-- docs-check: run -->
```bash
mkdir -p .github/workflows
```

The baseline is the run of your main branch. `prove-baseline.yml` sweeps on every push to main and
keeps the store in GitHub's cache under that commit:

<!-- docs-check: file .github/workflows/prove-baseline.yml -->
```yaml
name: prove-baseline
on:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  baseline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      - run: pip install poisson-prove -e .
      - run: poisson-prove sweep --yes
      - uses: actions/cache/save@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with:
          path: prove-runs
          key: prove-baseline-${{ github.sha }}
```

`prove.yml` restores the baseline of the pull request's base commit, sweeps the pull request's
code paired with it, gates, and comments:

<!-- docs-check: file .github/workflows/prove.yml -->
```yaml
name: prove
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  prove:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      - run: pip install poisson-prove -e .
      - uses: actions/cache/restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with:
          path: prove-runs
          key: prove-baseline-${{ github.event.pull_request.base.sha }}
          fail-on-cache-miss: true
      - run: poisson-prove sweep --yes --pair-with latest
      - id: check
        run: poisson-prove check --event unresolved --event timeout --json > check.json
      - if: always() && steps.check.outcome != 'skipped'
        run: python make_comment.py check.json > comment.md && cat comment.md >> "$GITHUB_STEP_SUMMARY"
      - if: always() && steps.check.outcome != 'skipped' && !github.event.pull_request.head.repo.fork
        run: gh pr comment "$PR" --repo "$GITHUB_REPOSITORY" --body-file comment.md
        env:
          GH_TOKEN: ${{ github.token }}
          PR: ${{ github.event.pull_request.number }}
```

**The events are yours.** `unresolved` and `timeout` are the support bot's, from
[Your own agent](../your-own-agent.md), and stand here as an example: name the failures your own
spec's `[declare]` table lists. On the quickstart's runs `unresolved` is refused with exit 1.

What the steps do:

- The `check` step is the gate: its exit 4 fails the job.
- The comment steps run whether the gate passed or failed, and put the comment on the run's
  summary page and on the pull request. A pull request from a fork gets a read-only token, so its
  comment is on the summary page only.
- A pull request whose base commit has no baseline yet, because main's job has not finished, fails
  at the restore: re-run it when that job is done. GitHub removes a cache unused for seven days; a
  push to main makes a new one.

Keep the spec, the target and the replicates the same on both sides, or the two runs will not
have the same conditions to compare. A model key your agent needs goes in the CI's secrets, as for
any test that calls the model.

## What this does not tell you

Whether the main branch's run is still a fair baseline. A model's answers drift with its version
and its provider's load, so a baseline swept weeks ago differs from today's run in more than your
change. Re-sweep the baseline when the model or the provider changes, and when in doubt run both
sides in the same job. A passing gate says no condition counted as worse; each condition's detection
limit says how large a rise it would have caught 4 times in 5. It does not say nothing got worse.
