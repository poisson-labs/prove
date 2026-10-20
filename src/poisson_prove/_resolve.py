"""Import-path resolution shared by the CLI and the Modal worker. Not a public symbol."""

from __future__ import annotations

import importlib
from typing import Any


def split_import_path(import_path: str) -> tuple[str, str]:
    """``'pkg.module:attr'`` -> ``('pkg.module', 'attr')``; ValueError on any other shape."""
    if not isinstance(import_path, str) or ":" not in import_path:
        raise ValueError(f"import_path must look like 'pkg.module:rollout', got {import_path!r}")
    module, attr = import_path.split(":", 1)
    if not module or not attr or ":" in attr:
        raise ValueError(f"import_path must look like 'pkg.module:rollout', got {import_path!r}")
    return module, attr


def resolve(import_path: str) -> Any:
    """Import the module and return the named attribute.

    Raises ValueError (bad shape), ImportError (module), or AttributeError (attribute).
    """
    module_name, attr = split_import_path(import_path)
    module = importlib.import_module(module_name)
    return getattr(module, attr)
