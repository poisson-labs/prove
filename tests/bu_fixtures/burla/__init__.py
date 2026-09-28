"""A fake of Burla 1.8.1, for Prove's Burla backend tests. No network, no account, no cluster.

It stands in for the client at git tag ``1.8.1`` (``f9d801c``, the PyPI release of 2026-09-16).
Citations name files under that tag's ``client/src/burla/`` and ``node_service/``. It
reimplements what Prove's launcher can observe; it copies no Burla source.

It is never importable in the pytest process. Prove's launcher seam (``_launcher_argv``) is
pointed at ``tests/bu_fixtures/launch.py``, which puts this directory first on the launcher's
path. The fake's state (the scripted faults, the worker pool, the records) lives in the folder
named by ``BU_FAKE_BURLA_STATE``, which only that wrapper sets.
"""

from burla._fake import fake_version
from burla._remote_parallel_map import remote_parallel_map

# __init__.py:10 carries the version as a literal. A test that needs the launcher to meet another
# version writes one into the script; nothing else moves it.
__version__ = fake_version("1.8.1")

__all__ = ["remote_parallel_map"]
