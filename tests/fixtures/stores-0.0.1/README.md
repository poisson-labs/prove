# Stores written by 0.0.1

Real stores written by the private builds of Prove, when it was still called `proofload` (version
0.0.1). Prove reads them with every verb and never rewrites a byte of them; `tests/test_pf0_name.py`
holds it to that.

## What is here

`store/` is one store holding seven runs. `runs.json` names each by what it is:

| name in `runs.json` | what the run is | written by |
|---|---|---|
| `quickstart_before` | the keyless mock agent over the quickstart spec, 900 rollouts | `98dc6af` |
| `quickstart_after` | the patched mock agent, paired with the run above (`--pair-with`), 900 rollouts | `98dc6af` |
| `timeout_and_crash` | three timed-out and three crashed episodes, each with its captured trace, and three that finished | `98dc6af` |
| `capture_cut` | a captured tool result longer than the declared cap (64 bytes), so the stored observation is cut | `98dc6af` |
| `chaos` | a declared fault (`tool_corrupt_single` at rate 0.5) on two chat completions per episode, with captured spans carrying the fault stamps | `98dc6af` |
| `modal` | the mock agent on the Modal backend, run against an offline stand-in for `modal` | `98dc6af` |
| `pre_split` | the mock agent written in the layout from before the trace was split into its own two columns: the trace sits inside `meta`, in the span shape of that time | `dc6ba9c` |

`98dc6af` is the last commit of the 0.0.1 line. No build from it can write the layout from before
the split, so that one run comes from `dc6ba9c`, the commit before the split; it too calls itself
0.0.1.

`SHA256SUMS` is every file under `store/` with its digest, as written.

`recorded/` is what 0.0.1 (`98dc6af`) printed for the quickstart pair with each method named:
`diff --format json`, `serve --json` and the three files `report` writes, for `fisher_bh` and for
`mcnemar_bh`. A later build must give the same cells, omnibus p, fault lines and bound when the
same method is named.

## How it was built

`build/build.sh`, run once from the repository root, builds both wheels with `uv`, installs each
into a fresh virtual environment on Python 3.11, and runs every sweep from an emptied environment
in a scratch folder with a neutral name (`/tmp/prove-0.0.1-stores`). The crashed episodes' stored
tracebacks name that folder; nothing else in the store names a path. No key, no model, no network
beyond installing the wheels' dependencies.

- `build/targets.py`: the three rollouts written for this fixture (`mixed`, `captured`,
  `chaotic`). Keyless; the chat completions go to an in-process transport.
- `build/fake_modal/modal.py`: the offline stand-in for `modal`, on `PYTHONPATH` for the Modal
  run only.
- `build/specs/`: the sweep specs. `quickstart.toml` is copied from the `98dc6af` tree at build
  time, and `presplit.toml` is the same spec at 20 replicates.

Run ids carry the time they were written, so a rebuild gives new ids and new bytes. The committed
fixture is the record; rebuild it only to replace it.
