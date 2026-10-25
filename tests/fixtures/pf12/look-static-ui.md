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
