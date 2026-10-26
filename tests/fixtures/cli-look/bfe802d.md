# The command-line look

How every command of a Poisson Labs tool reads and behaves: the help, the first line, where
problems go, the exit codes. Each tool's own conformance test runs its commands and checks
them against this page.

## The rules

1. **One command per tool, verbs under it.** `python -m <package>` runs the same command.

2. **Help a stranger can act on.** Every verb's `--help` gives a description, help text for
   every argument with its default (or "no default"), and at least one example command.
   Help goes to stdout, exits 0, and never needs an optional dependency, the network or a key.

3. **The result comes first.** The first line a verb prints on stdout is a verdict line: a
   lowercase verdict word or phrase from that verb's closed set, two spaces, one sentence.
   Detail follows as `label  value` lines indented two spaces, or as a report after one blank
   line.

4. **Problems go to stderr, one line each, and say what to do.**
   - An error is `error: <what happened, in plain words>`, with optional
     `  next: <exact command>` lines indented two spaces.
   - A warning is `note: <sentence>`.
   - Where there are valid alternatives, the line lists them.
   - An error never contains a traceback, raw library exception text, a Python value printed
     as itself (a tuple, a quoted list, `'name'`), an internal reference, or a key.
   - An unexpected failure prints
     `error: an unexpected failure inside <tool> (<ExceptionType>); the details are in <log path>`,
     and the traceback goes to that file (and to stderr too with `--debug`).

5. **Exit codes mean the same in every tool** (below).

6. **Ctrl-C is a stop, not a crash.** It prints `stopped  interrupted: <what was kept>`, then
   `next: <the resume command>` where there is one, and exits 130.

7. **Anything that spends money shows the plan first, checks the cap before asking, and keeps
   the plan on screen when it refuses.**
   - The plan has a verdict line and an estimate that names its source.
   - It asks with `[y/N]` on stderr, and `--yes` skips the question.
   - A stdin that is not a terminal, without `--yes`, prints the plan and refuses.
   - `--dry-run` prints the plan and stops.

8. **Keys are named, never read except to use, never shown.**

9. **`--json` makes stdout exactly one strict JSON document.**
   - `schema` is the first key, then `verdict` (the word) and `sentence` (the verdict line's
     sentence);
   - no `NaN` or `Infinity`;
   - the exit code is the same as without `--json`;
   - errors stay on stderr, in text.

10. **Numbers read the same everywhere.**
    - rates and shares to three decimals;
    - p-values to three decimals, or `2.3e-08` below 0.001;
    - dollars as `$1.00`, or with three significant digits below $0.10 (`$0.021`, `$0.0052`);
    - counts with thousands separators (`4,200`);
    - durations as `1 min 40 s` and `1 h 36 min`;
    - hashes at 12 hex characters in text and in full in JSON;
    - times in UTC with `Z`.

11. **Plain words.** No internal reference numbers or project names anywhere a user reads:
    output, help, README, user docs, changelog. Documented product names are fine.

12. **A verb that writes files says what it wrote, and refuses to overwrite without
    `--force`.**

13. **A verb with an obvious next step ends with `next: <exact command>`.**

14. **Configs are strict.** An unknown key in any config or spec file is refused with the
    nearest known key.

15. **Options may come before or after the verb; abbreviations are refused.**

16. **Plain text, no colour.** Output falls back to ASCII when stdout cannot encode the glyphs
    (`·`, `–`, `×`).

## Exit codes

| code | meaning |
|---|---|
| 0 | done: the result is printed, whatever it says |
| 1 | refused: nothing was spent or written |
| 2 | the command line is wrong (usage) |
| 3 | stopped or failed after work started, or an unexpected failure; what was kept is printed |
| 4 | a check you asked for did not pass |
| 130 | interrupted |

Exit 4 belongs to a check the user asked for, never to a result the user did not ask to gate
on.
