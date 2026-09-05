# Golden pilot fixtures (S18)

The three-golden mini-suite and the candidate code `tests/test_pilot_golden.py` executes
inside the sandbox. Nothing here was captured live: no network, no API key, no model.

## `mini_suite.jsonl`

Three problems copied byte-for-byte from HumanEval (`openai/human-eval`, MIT licence,
`data/HumanEval.jsonl.gz`, 164 problems), in the HumanEval JSONL shape — `task_id`,
`prompt`, `entry_point`, `canonical_solution`, `test` — one problem per line:

| task_id | entry_point | why this one |
|---|---|---|
| `HumanEval/0` | `has_close_elements` | a list problem whose `check` starts with a `True` case |
| `HumanEval/2` | `truncate_number` | the shortest canonical solution; every bad candidate is written for it |
| `HumanEval/3` | `below_zero` | a second list problem, so the suite has three distinct prompts |

`suite.load(path)` must read this file as it reads the real one; the real
`suite/HumanEval.jsonl.gz` is never required by any test.

## `wrong_solutions.json`

One deliberately wrong completion per problem, keyed by `task_id`, in the shape of
`canonical_solution` (a function body, indented, to be appended to `prompt`). Each fails an
assertion in that problem's `check` without raising anything else — `submit` of a wrong
solution is the `failed_assertion` outcome, not `crashed`.

## `bad_candidates.json`

Completions for `HumanEval/2` (the `_task_id` key), each isolating one thing the sandbox
must handle. The four hygiene candidates are otherwise *correct* solutions, so the only way
each fails is the limit under test:

| key | what it does | what must make it fail |
|---|---|---|
| `assertion` | returns the wrong value | the golden's `check` |
| `raises` | raises `ValueError` | nothing to enforce: a raise is a failure |
| `hangs` | sleeps 30 s, then returns the right value | the wall clock |
| `allocates` | allocates 8 GiB, then returns the right value | the memory limit (`resource.setrlimit`; skipped on macOS, see the oracle) |
| `socket` | opens and closes a TCP socket, then returns the right value | the replaced `socket` module |
| `long_reason` | raises with a 5,000-character message | the 500-character cap on the reason |

The oracle builds a complete candidate as `prompt + completion` and hands it to
`sandbox.run_tests(candidate, golden)`.
