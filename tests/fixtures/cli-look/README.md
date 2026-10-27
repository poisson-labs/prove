# The look file's base

`docs/cli-look.md` is Poisson Prove's copy of the lab's command-line look, and the canonical one: the
other tools copy it from here. The tests in `tests/test_pf6_look.py` hold it to two things it was
made from, both kept in this folder so the tests read nothing outside the repository.

- `bfe802d.md` is the file as the lab's tools shared it before Prove's copy became the canonical
  one, byte for byte (the name is the version it was taken from): 89 lines, sha256
  `af0bb656e8a955befbdcdc031cce7c78d62248cd3b90adebf1e63d837298ce79`.
- `changes.json` holds the three changes made to it, each as the old text, which occurs exactly
  once in the base, and the new text: rule 10's dollars (two significant digits below $0.10), rule
  16 replaced by the two renderings (plain is the contract, pretty is the standard look), and rule
  15's options (the tool's own options before or after the verb, a verb's options after it).

The base with the three changes applied is the first 120 lines of `docs/cli-look.md`, up to and
including the paragraph that closes the exit-code table (sha256
`fca2017b1923ed0725d54fd8829e288f677b75a78b93eff12bd862ad07312697`). The two sections after it, the
terminal app and the static UI, are new. The whole file's sha256 is
`92e71488c2824c056252be9a7b340e7fc138d15359fbcb7431bcfc6fa267d85f`, 275 lines.

Another tool's amended copy carries the same three changes and a dated note under the title;
Prove's copy does not carry the note, since the file states rules, not their history.
