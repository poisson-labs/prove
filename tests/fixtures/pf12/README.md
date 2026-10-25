# What PF12's tests read

`look-static-ui.md` is the static-UI section of the look file, copied byte for byte from the file
the design session filed on 2026-10-23: every line from its `## The static UI` heading to the end.
The whole file's sha256 is `92e71488c2824c056252be9a7b340e7fc138d15359fbcb7431bcfc6fa267d85f`
(the one PF6.0 pins once the file is `docs/cli-look.md`); this section's is
`f39b5a83b13e3a3378a994150a3187cc7e764d63e01365641b9409e9c6febfa7`. The tests read its colour table
(twelve tokens, light and dark) and nothing outside this repository.

The stores the tests compare are built while the tests run, from the 0.0.1 stores in
`../stores-0.0.1/` and from runs written by hand through the public `Store`; see
`tests/pf12_support.py`.
