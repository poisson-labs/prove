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
    - dollars as `$1.00`, or with two significant digits below $0.10 (`$0.021`, `$0.0052`);
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

15. **The tool's own options (such as `--store`, `--plain`, `--debug`) may come before or after the
    verb; a verb's options follow the verb; abbreviations are refused.**

16. **Two renderings of one result, and plain is the contract.** Every verb builds one result:
    the verdict word, its sentence, the detail and the next commands. It is printed one of two ways.
    - **Plain**: text only, no escape sequence, standard library only. Tests, docs and the
      conformance test pin this rendering. It falls back to ASCII when the stream cannot encode the
      glyphs (`·`, `–`, `×`).
    - **Pretty**: the same facts in the same order, drawn with Rich. It runs only when stdout and
      stderr are both terminals, `NO_COLOR` is unset or empty, `CI` is unset, `TERM` is not `dumb`,
      stdout is UTF-8, and neither `--json` nor `--plain` was given. Otherwise the plain rendering
      runs, byte for byte.
    - **Colour has four meanings and no others.** Green: the command did what was asked (`ok`,
      `done`, `passed`). Yellow: it stopped short or cannot say (`stopped`, `refused`,
      `too small to tell`, `note:`). Red: an error or a failed check (`error:`, `not ready`, `fail`).
      Dim: secondary text. A verdict word that is neither good nor bad (`plan`, `different`) is bold
      and has no colour. A number is never coloured.
    - Only the terminal's 16 named colours, bold and dim are used, so the user's theme decides the
      shades.
    - A command printed for the user to copy is never hard-wrapped.
    - Questions and progress stay on stderr. A live display is removed when the work ends, so what
      remains on screen is the result.
    - The conformance test runs each invocation both ways. Piped, the pretty build must equal the
      plain build byte for byte. In a pseudo-terminal, with escape sequences removed, the first line
      must carry the same verdict word and sentence, and the exit code must be the same. `--json`
      must be identical.
    - A top-level `--plain` forces the plain rendering. `NO_COLOR` turns off the whole pretty
      rendering, not only its colour.
    - Rich is an ordinary dependency, not an optional extra; a tool that cannot import it prints plain
      and says nothing about it.
    - In a terminal, plain wraps its own long lines at the terminal's width with a hanging indent;
      piped, it prints one line per fact.
    - When a table is too wide for the terminal, pretty moves a unit every cell repeats into the
      header and prints a JSON key one field per line. Pretty is claimed on macOS and Linux
      terminals; on Windows it is not claimed until someone has run it there; in CI it never runs.

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

## The terminal app

A tool may open a full-screen app when its command is run with no verb on a terminal. The rules
above govern the commands; this section governs the app. The app shows the same results the
commands print, built by the same code, and never a fact the command would not print.

### Layout

Every screen has the same six bands, top to bottom:

| row | band | holds |
|---|---|---|
| 1 | header | the tool's name, `·`, the screen's title and its subject (a run's name, a comparison's two runs); the store, as the user gave it, at the right edge |
| 2 | rule | one hairline (`─`), dim |
| 3 to H − 3 | body | the screen's content, below |
| H − 2 | message line | one `note:` or `error:` line, or blank; cleared by the next key |
| H − 1 | rule | one hairline, dim |
| H | key bar | the keys that work on this screen |

- A screen that shows a result opens its body with that result's verdict line: the same word and
  sentence the command prints, at column 3, then one blank line, then its `label  value` detail lines
  in the command's order.
- Below the detail comes the screen's one table or list, which scrolls inside the body; the rows above
  it do not scroll. A screen with a second block (an event log, a reproduce block) shows it below the
  table when the window has room, and behind one key when it does not.
- Links to pages of the static UI are detail lines, `label  address`, where the address is the page's
  address inside the UI (`comparisons/<id>.html#conditions`).
- No borders, boxes or panes. Rules, blank lines and indentation make the structure.

### Keys

| key | does | on |
|---|---|---|
| `↑` `↓` | move the focus one row | every screen with rows |
| `PgUp` `PgDn`, `Home` `End` | move it a page, or to the first or last row | every screen with rows |
| `Enter` | open what has the focus: a row's screen, or a link in the browser | every screen |
| `Esc` | back to the screen this one was opened from, with the focus where it was | every screen but home |
| `Tab` | move the focus between the links and the table | screens with both |
| `/` | filter the table's rows by text; `Esc` clears the filter | screens with a table |
| `y` | copy the focused link's full `file://` address, or the focused command or code | screens with links or commands |
| `?` | help: every key, and what each screen is | every screen |
| `q` | quit, exit 0 | every screen; during a question it answers no |
| `Ctrl-C` | quit, exit 130; during work it stops the work and keeps what was done, as rule 6 says | everywhere |

- A screen's own keys are single lowercase letters, listed in the key bar between the shared keys and
  `? help`. A letter means the same on every screen that has it.
- The key bar lists keys in one order: move, `Enter`, `Esc`, the screen's own, `? help`, `q quit`.
  The key is bold; its word is dim. When the bar is too narrow, words drop before keys do: first the
  words of the move, `Enter` and `Esc` keys, then the screen's own from the right. `? help` and
  `q quit` never lose theirs.
- A question that spends money is asked inside the app as the command asks it, `[y/N]`, with no
  default other than no; only `y` answers yes.

### Focus

- Exactly one thing has the focus: a row, or a link.
- The focused row is drawn in reverse video and carries `›` in column 1, so the focus still shows
  with no colour.
- A screen opens with the focus on its first row, or on its first link when it has no rows. `Esc`
  returns to the row that was focused when the screen was left.
- The focus never moves on its own: not when rows are added during work, not when a page is rebuilt.

### Colour

- The four meanings of rule 16, and no others: green, the command did what was asked; yellow, it
  stopped short or cannot say; red, an error or a failed check; dim, secondary text. A verdict word
  that is neither good nor bad is bold with no colour. A number is never coloured.
- Reverse video marks the focus and means nothing else.
- Only the terminal's 16 named colours, bold, dim and reverse are used. `NO_COLOR` keeps the app and
  removes its colour; bold, dim and reverse stay.
- Nothing moves except the progress line of running work: one line, a count and a bar, redrawn at
  most once a second, removed when the work ends. No spinner, no animation, no flash.

### Widths

- The app is drawn for 80 × 24 and 120 × 40, and works at any size from 80 × 24 up. Below 80 × 24 it
  shows one line, `the window is 72 × 20; the app needs at least 80 × 24`, and `q quit`.
- Tables keep their columns in one order and drop columns from a fixed list, last listed first, when
  the window is narrow. The columns that never drop are named in each screen's design.
- Numbers are right-aligned and printed by rule 10. Names are left-aligned; a name too long for its
  column is cut in the middle with `…`, and the full name is on the screen the row opens.
- Commands, code and links are never cut and never get a character inserted. One that does not fit at
  its column starts at column 1 on the rows below its label, broken only at spaces at the window's
  edge; `y` copies it whole. A link shows its address inside the UI, and `y` copies the whole
  `file://` address.

### What never moves

- The header, the two rules, the message line and the key bar keep their rows on every screen and at
  every size.
- The verdict line, when a screen has one, is the first line of the body.
- `Enter` opens, `Esc` goes back, `?` is help, `q` quits, everywhere.
- The facts of a screen come in the order the command prints them.

## The static UI

A tool may write static pages over its store, opened from disk. The rules above govern the commands;
this section governs the pages.

### Colour

Each page sets one set of colour tokens, for light and for dark, and follows the system's choice
(`prefers-color-scheme`). The four meanings are the same as the terminal's.

| token | meaning | light | dark |
|---|---|---|---|
| `--bg` | page background | `#fcfcfb` | `#1a1a19` |
| `--surface` | tables, charts, code | `#f4f3ef` | `#242422` |
| `--rule` | hairlines | `#dddcd6` | `#3a3a37` |
| `--text` | text, and bold result words | `#0b0b0b` | `#f0efec` |
| `--dim` | dim: secondary text | `#5f5e59` | `#a8a79f` |
| `--ok` | green: did what was asked | `#006300` | `#5cc45c` |
| `--warn` | yellow: stopped short or cannot say | `#8a5800` | `#e5b23c` |
| `--bad` | red: an error or a failed check | `#bf2626` | `#f07070` |
| `--rise` | charts: a share that rose | `#c4511f` | `#e0703f` |
| `--fall` | charts: a share that fell | `#2a6fc4` | `#4f94e8` |
| `--mid` | charts: no change, the neutral midpoint | `#e9e8e3` | `#383835` |
| `--after` | charts: the second run, beside the first in `--dim` | `#5444c9` | `#9085e9` |

- Every text token reads at 4.5:1 or more on `--bg` and `--surface`.
- `--ok`, `--warn` and `--bad` colour only verdict words, `note:` and `error:` lines, and nothing else:
  never a number, a chart mark or a background. A word that is neither good nor bad is bold in
  `--text`.
- Chart colours never carry the four meanings, and the four meanings' colours never appear in a
  chart.

### Type

- The system's own fonts, no other: prose in `system-ui, -apple-system, "Segoe UI", sans-serif`;
  verdict words, numbers, names, addresses and tables in `ui-monospace, Menlo, Consolas, monospace`
  with tabular figures.
- One size for prose (15 px) and one for tables and detail (13 px); headings by weight, not size,
  except the page title.
- Numbers are printed by rule 10, as the commands print them.

### Charts

- Inline SVG, drawn by the tool from the data beside it; the page shows the data as a table under each
  chart.
- Each chart's title names what it shows, the event, and the test, level and family its intervals or
  limits use, in the commands' words.
- Hairline axes and grid in `--rule`, solid, never dashed. A threshold is one solid line with its value
  written on it.
- Direction is shown by position and shape as well as colour: a rise to the right or up and marked
  `▲`, a fall to the left or down and marked `▼`. The first run is drawn in `--dim`, the second in
  `--after`, each labelled where its line ends.
- Every mark has a hover title giving its row's facts. No chart is the only place a fact appears.

### No network

- A page loads nothing from the network: no font, script, style sheet, image or frame from any host.
  Every reference is a path inside the UI's folder or a `data:` address.
- Each page carries a `Content-Security-Policy` that forbids any other source.
- The script only sorts and filters tables. A page works with the script off.
