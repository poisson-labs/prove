"""The golden suite pilot (Phase 3.5): a user of Proofload, outside the package.

Importing this package is free of side effects. ``golden_pilot.agent`` refuses to import
outside the isolation boundary (``GOLDEN_PILOT_BOUNDARY``, which only the Dockerfile sets),
so it is deliberately not imported here: ``suite``, ``sandbox``, ``numbers`` and ``make_toml``
run on a laptop, and only the module that executes model-generated code is gated.
"""
