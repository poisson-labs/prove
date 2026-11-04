# What PF12's tests read

`look-static-ui.md` is the static-UI section of `docs/cli-look.md`, copied byte for byte: every
line from its `## The static UI` heading to the end. The whole file's sha256 is
`c6765e0efe58ad202204774185587b24192ce6d981eb1cf06f6f6edbe6909338` (the one PF6.0 pins); this
section's is `4cd818b59514a24af59142c6500b2b9ae24dc1f33d65a1e5272fb58c8c0f663e`. The tests read
its colour table (twelve tokens, light and dark) and nothing outside this repository.

The stores the tests compare are built while the tests run, from the 0.0.1 stores in
`../stores-0.0.1/` and from runs written by hand through the public `Store`; see
`tests/pf12_support.py`.
