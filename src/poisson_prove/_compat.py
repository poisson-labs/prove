"""Where the old name lives: every string Prove still reads or shows that spells ``proofload``.

Prove was called ``proofload`` in its private builds (version 0.0.1). The rename moved every
name a user types, imports, reads or stores: the distribution and command (``poisson-prove``),
the import package (``poisson_prove``), the schema strings (``poisson-prove.*``), the span
attribute prefix (``poisson_prove.``), the manifest's version key (``poisson_prove_version``),
the store variable (``POISSON_PROVE_STORE``) and the default store folder (``./prove-runs``).
Nothing stored under the old names is ever rewritten, so every reader of one of those strings
also accepts the old spelling, and it accepts it here and nowhere else: one function per kind of
string, so no reader spells the old name twice and no reader spells it on its own.

The texts a user of the private builds can meet live here too: the provenance of a run written
by ``proofload``, the note that the old store variable is no longer read, and the refusal that
keeps a store from being split in two when only the old default folder is present. They reach a
screen only when old data or an old variable is present.

This module imports nothing of the package.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__: list[str] = []

#: The name the private builds went by, as a distribution, a command and an import package.
RETIRED_NAME = "proofload"

#: The trace schema string those builds wrote into every stored row. The current string is
#: ``poisson-prove.trace/1``, and the shape is the same.
RETIRED_TRACE_SCHEMAS: tuple[str, ...] = ("proofload.trace/1",)

#: The manifest key the version was recorded under. The current key is ``poisson_prove_version``.
RETIRED_VERSION_KEY = "proofload_version"

#: The chaos catalogue's version string as recorded in a manifest's ``environment["chaos"]``.
#: The current string is ``poisson-prove.chaos-catalog/1``; the catalogue is the same.
RETIRED_CHAOS_CATALOGUE_VERSIONS: tuple[str, ...] = ("m11-catalog/1",)

#: The span attribute prefix those builds wrote, documented and stamped. The current prefix is
#: ``poisson_prove.``; the key names after it did not change.
RETIRED_SPAN_PREFIX = "proofload."
_CURRENT_SPAN_PREFIX = "poisson_prove."

#: The environment variable that named the store. It is not read any more.
RETIRED_STORE_VARIABLE = "PROOFLOAD_STORE"

#: The default store folder. ``./prove-runs`` is the default now.
RETIRED_DEFAULT_STORE = "proofload-runs"


# ---------- schema strings ----------


def is_retired_trace_schema(schema: object) -> bool:
    """Whether ``schema`` is a trace schema string an earlier build wrote for the current shape."""
    return isinstance(schema, str) and schema in RETIRED_TRACE_SCHEMAS


def is_retired_chaos_catalogue_version(version: object) -> bool:
    """Whether ``version`` names the current chaos catalogue under its earlier version string."""
    return isinstance(version, str) and version in RETIRED_CHAOS_CATALOGUE_VERSIONS


# ---------- the manifest's version key ----------


def retired_manifest_version(manifest: Mapping[str, Any]) -> tuple[str, str] | None:
    """The version a manifest recorded under the retired key, with the name that wrote it.

    ``None`` when the manifest carries no retired key. A manifest that carries the current key is
    the reader's own business and never comes here.
    """
    recorded = manifest.get(RETIRED_VERSION_KEY)
    if recorded is None:
        return None
    return str(recorded), RETIRED_NAME


# ---------- span attribute keys ----------


def span_key(key: str) -> str:
    """The current spelling of a span attribute key: a key under the retired prefix comes back
    under the current one, and any other key comes back as it is."""
    if key.startswith(RETIRED_SPAN_PREFIX):
        return _CURRENT_SPAN_PREFIX + key[len(RETIRED_SPAN_PREFIX):]
    return key


# ---------- what a user of the private builds can see ----------


def version_as_recorded(version: str) -> str:
    """How a run written by the private builds gives its version: ``0.0.1 (as proofload)``."""
    return f"{version} (as {RETIRED_NAME})"


def old_writer_line(version_shown: str) -> str | None:
    """The provenance line of a run written by the private builds, ``written by proofload 0.0.1``,
    when ``version_shown`` is a version as :func:`version_as_recorded` gives it; else ``None``."""
    suffix = f" (as {RETIRED_NAME})"
    if not version_shown.endswith(suffix):
        return None
    return f"written by {RETIRED_NAME} {version_shown[: -len(suffix)]}"


def retired_store_variable_note(environ: Mapping[str, str], current: str) -> str | None:
    """The note every verb prints when the retired store variable is set and the current one,
    ``current``, does not name a store: the old one is not read. ``None`` otherwise."""
    if RETIRED_STORE_VARIABLE not in environ or environ.get(current):
        return None
    return (
        f"{RETIRED_STORE_VARIABLE} is set and no longer read; Prove reads {current}"
    )


def retired_default_store(default: Path) -> Path | None:
    """The old default store folder beside ``default``, when the default folder does not exist
    and the old one does: the case in which a verb must refuse rather than split a store in two.
    ``None`` when the default is present or the old folder is not."""
    old = default.parent / RETIRED_DEFAULT_STORE
    if default.exists() or not old.is_dir():
        return None
    return old


def retired_default_store_refusal(
    default: Path, old: Path, command: str, verb: str
) -> tuple[str, list[str]]:
    """The refusal's error text and its ``next:`` lines, for a verb that found only the old
    default store: move the folder, or name it with ``--store``."""
    error = f"no store at {default}; a store from an earlier version of Prove is at {old}"
    return error, [f"mv {old} {default}", f"{command} --store {old} {verb}"]
