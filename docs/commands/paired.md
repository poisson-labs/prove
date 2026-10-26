# `poisson-prove paired`

Paired replay asks a narrower question than `diff`: when the same request is sent twice, does it
get the same decision? A grader that scores an answer, a classifier that routes a ticket, a judge
that passes or fails a run: if the model behind it is not deterministic, the same input can land
on either side of a threshold. `paired` first checks that two runs (the arms) really sent the same
request, pair by pair, then counts how often the decision at each declared threshold flipped
between them, with an interval clustered by item.

Its input is a declaration, a TOML file fixed before you look at the results: which span holds the
request, which value is the score, the thresholds (cuts), and which runs are the arms.

## Help

<!-- docs-check: run -->
```console
$ poisson-prove paired --help
usage: poisson-prove paired [-h] --declaration DECL [--out DIR] [--cap-check]
                            [--force] [--json] [--store PATH] [--plain]
                            [--debug]

Assert that a declaration's arms were the same request replayed, then write the
paired-replay files: the assertion, the contingency and interval tables, the
windows, the cost and, at three arms or more, the replicates.

options:
  -h, --help          show this help message and exit
  --declaration DECL  the paired-replay declaration, a TOML file (no default)
  --out DIR           the folder to write (default: ./prove-paired-<the
                      declaration's digest>)
  --cap-check         say whether the recorded input tokens are under the
                      declared cap, write nothing, and exit 4 at or above it
  --force             write into a folder that is not empty
  --json              print the files' contents, writing nothing as one JSON
                      document instead of text
  --store PATH        the store folder (default: $POISSON_PROVE_STORE when
                      set, else ./prove-runs)
  --plain             print plain text, as a pipe gets it, on a terminal too
                      (default: pretty on a terminal, plain otherwise)
  --debug             also print the traceback of an unexpected failure

examples:
  poisson-prove paired --declaration paired.toml
  poisson-prove paired --declaration paired.toml --cap-check
```

## Options

- `--declaration DECL` is the paired-replay declaration, required. Its keys have no defaults:
  each is required but five optional ones (`floor`, `declared_window_s`, `conditioning`,
  `price_per_input_token`, `token_cap`), and an unknown key is refused.
  [Paired replay](../recipes/paired-replay.md) walks through each one.
- `--out DIR` is the folder to write, `./prove-paired-` and the start of the declaration's digest
  by default; `--force` writes into a folder that is not empty.
- `--cap-check` reads the input tokens the arms recorded on their request spans, says whether they
  are under the declaration's `token_cap`, writes nothing, and exits 4 at or above it: run it
  between sweeps of a paid replay.
- `--json` prints the files' contents as one JSON document and writes nothing.
- `--store PATH` is the store folder; `--plain` prints plain text on a terminal too; `--debug`
  adds the traceback of an unexpected failure.

## Examples

A stand-in grader, so the example runs with no key: it records the request it sends as a span,
as your own harness would, and its score varies from one call to the next the way a provider's
can. The answer being graded is the item, and each is its own sweep axis value:

<!-- docs-check: file grader.py -->
```python
"""A stand-in for a model that grades answers: the same request can come back with a different
score. It records the request it sends, as your own harness would."""
import json
import random

from poisson_prove import Episode
from poisson_prove.trace import collect, record

#: Each answer, and the score the grader gives it on average.
ANSWERS = {"a1": 0.52, "a2": 0.58, "a3": 0.61, "a4": 0.66, "a5": 0.74, "a6": 0.45}


def rollout(cfg, seed):
    body = {"model": "grader-1", "temperature": 0, "seed": seed,
            "messages": [{"role": "user", "content": f"Grade answer {cfg['answer']} from 0 to 1."}]}
    with collect() as collected:
        with record("llm", "grader.request", input=json.dumps(body)) as span:
            score = min(1.0, max(0.0, ANSWERS[cfg["answer"]] + random.gauss(0, 0.05)))
            span.output = json.dumps({"score": round(score, 2)})
    meta = {"trace": collected.trace.to_dict(), "grade": {"score": f"{score:.2f}"}}
    return Episode(outcome="graded", t=1, horizon=1, meta=meta)
```

<!-- docs-check: file grading.toml -->
```toml
target = "grader:rollout"
target_id = "grader"
t_unit = "calls"
replicates = 200

[axes.answer]
type = "categorical"
values = ["a1", "a2", "a3", "a4", "a5", "a6"]

[axes.rubric]
type = "categorical"
values = ["pass-mark"]
```

The two arms are two runs on the same seeds, so pair by pair they sent the same request:

<!-- docs-check: run -->
```console
$ poisson-prove sweep grading.toml --yes
plan  1,200 rollouts of grader: 6 cells x 200 replicates on local, $0 (local)
…
$ poisson-prove sweep grading.toml --yes --pair-with latest
plan  1,200 rollouts of grader: 6 cells x 200 replicates on local, $0 (local)
…
```

The declaration names the arms by their run ids, which exist only once the runs do, so here a few
lines of Python write it:

<!-- docs-check: run -->
```python
from poisson_prove import compare

before, after = [run.run_id for run in compare.runs("prove-runs")][::-1][:2]
declaration = f"""value_key = "grade.score"
cluster_key = "answer"
stratum_key = "rubric"
request_span = "grader.request"
model_key = "model"
model_pin = "grader-1"
exemptions = []
headers = "not_recorded"
retries = "not_recorded"
bootstrap_b = 400
bootstrap_seed = 7

[[cuts]]
name = "pass-mark"
threshold = 0.60
comparison = "ge"

[[sweeps]]
name = "replay"
a = "{before}"
b = "{after}"
"""
open("replay.toml", "w").write(declaration)
```

<!-- docs-check: run -->
```console
$ poisson-prove paired --declaration replay.toml --out replay
ok  wrote replay (5 files)
  wrote  replay/pair_assertion.json
  wrote  replay/contingency_by_cut.json
  wrote  replay/intervals_by_cut.json
  wrote  replay/windows.json
  wrote  replay/cost.json
  not recorded  the harness's digest and the client's version (the runs did not record them)
```

The stand-in records no token usage, and the declaration sets no cap, so the cap check has
nothing to stop; with a `token_cap` and the usage your client reports on the request span, it
exits 4 at the cap:

<!-- docs-check: run -->
```console
$ poisson-prove paired --declaration replay.toml --cap-check
under cap  0 input tokens recorded; no cap declared
…
```

`intervals_by_cut.json` holds the answer: the share of pairs whose decision at 0.60 flipped
(`flip_rate`, with an interval from a bootstrap over the six answers), and the net swing between
the arms (`net_swing`), which is near zero when the flips cancel out:

<!-- docs-check: run -->
```python
import json

cut = json.load(open("replay/intervals_by_cut.json"))["cuts"]["pass-mark"]
print("flipped", round(cut["flip_rate"]["estimate"], 3), cut["flip_rate"]["lo"], cut["flip_rate"]["hi"])
print("net swing", round(cut["net_swing"]["estimate"], 3))
```

## Exit codes

- `0`: the files were written; with `--cap-check`, the recorded tokens are under the cap.
- `1`: refused, and nothing was written: the declaration cannot be read or names a key it does not
  know, an arm is not in the store, the arms are not the same draw (different seeds), the
  thresholds' items overlap, or the output folder is not empty without `--force`.
- `2`: the command line is wrong, such as no `--declaration`.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `4`: with `--cap-check`, the recorded input tokens are at or above `token_cap`.
- `130`: interrupted with Ctrl-C.

## What it writes

The output folder: `pair_assertion.json` (every matched pair, eligible or excluded with one named
cause, and counts that reconcile), `contingency_by_cut.json` (the 2 by 2 of decisions per cut),
`intervals_by_cut.json` (the flip rate and the net swing, with their intervals),
`windows.json` (when each arm's requests were sent) and `cost.json` (the tokens recorded, priced
only against a price the declaration gives), and, for three arms or more, the replicates' file.
Nothing in the store. `--cap-check` and `--json` write nothing.
