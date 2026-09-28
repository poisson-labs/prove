"""The submit-time rule: what 1.8.1 would ship, and the call-time imports it refuses.

Before a call runs, 1.8.1 scans the calling interpreter's ``sys.path`` for distributions
(``_env_scan.py:72-88``, ``:264-355``), takes every module in ``sys.modules`` whose file lies
outside those distributions' folders and the standard library as local code to ship by value
(``:384-411``), and parses the function's own source plus every shipped module's file for an
import statement inside a function body that names local code (``:428-551``, called at
``_remote_parallel_map.py:844-847``). Any such statement refuses the call with
``UnsupportedLocalImport``. The fake applies the same rule, in its own code, and records what it
would have shipped: Prove's launcher must present a set that is empty (S2) and a function that
passes (S3).
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import sys
import sysconfig
import textwrap
from dataclasses import dataclass
from typing import Any

# Burla's own code is installed on the nodes, never shipped (_env_scan.py:394-396, :483-484).
_BURLA_TOP_LEVELS = ("burla", "main_service", "node_service")


class UnsupportedLocalImport(Exception):  # _env_scan.py:428-439
    def __init__(self, offenders: list[str]) -> None:
        super().__init__(
            "\n\nThese imports run at call time, but they import local modules.\n"
            + "\n".join(offenders)
            + "\n\nFix: move each of these imports to the top of its file.\n"
        )


@dataclass(frozen=True)
class Scan:
    dist_dir_prefixes: tuple[str, ...]
    stdlib_prefixes: tuple[str, ...]
    local_top_levels: frozenset[str]


def _resolved(path: str) -> str:
    return os.path.realpath(path)


def _pth_paths(pth: str, location: str) -> list[str]:
    grafted = []
    try:
        with open(pth, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith(("#", "import ", "import\t")):
                    continue
                path = line if os.path.isabs(line) else os.path.join(location, line)
                if os.path.isdir(path):
                    grafted.append(_resolved(path))
    except OSError:
        pass
    return grafted


def _local_top_levels(metadata: str) -> set[str]:
    """A non-editable local install copies its code into site-packages, where a path check
    cannot tell it from an index install (_env_scan.py:344-351); its names are local."""
    try:
        with open(os.path.join(metadata, "direct_url.json"), encoding="utf-8") as fh:
            direct = json.load(fh)
    except (OSError, ValueError):
        return set()
    dir_info = direct.get("dir_info")
    if not isinstance(dir_info, dict) or dir_info.get("editable"):
        return set()
    try:
        with open(os.path.join(metadata, "top_level.txt"), encoding="utf-8") as fh:
            return {line.strip() for line in fh if line.strip()}
    except OSError:
        return set()


def scan_environment() -> Scan:
    locations: list[str] = []
    for raw in sys.path:
        path = _resolved(raw or os.getcwd())
        if os.path.isdir(path) and path not in locations:
            locations.append(path)
    queue = [(location, True) for location in locations]
    seen = set(locations)
    dist_dirs: set[str] = set()
    local: set[str] = set()
    index = 0
    while index < len(queue):
        location, expand = queue[index]
        index += 1
        try:
            names = os.listdir(location)
        except OSError:
            continue
        for name in names:
            if name.endswith((".dist-info", ".egg-info")):
                dist_dirs.add(location)
                local |= _local_top_levels(os.path.join(location, name))
            elif expand and name.endswith(".pth"):
                for grafted in _pth_paths(os.path.join(location, name), location):
                    if grafted not in seen:
                        seen.add(grafted)
                        queue.append((grafted, False))
    paths = sysconfig.get_paths()
    stdlib = {paths.get("stdlib"), paths.get("platstdlib")}
    return Scan(
        dist_dir_prefixes=tuple(sorted(d + os.sep for d in dist_dirs)),
        stdlib_prefixes=tuple(sorted(_resolved(d) + os.sep for d in stdlib if d)),
        local_top_levels=frozenset(local),
    )


def modules_to_pickle_by_value(scan: Scan) -> set[str]:
    """What 1.8.1 ships: modules whose code no index can provide (_env_scan.py:384-411)."""
    shipped = set()
    known = scan.dist_dir_prefixes + scan.stdlib_prefixes
    for name, module in list(sys.modules.items()):
        top = name.partition(".")[0]
        if top in _BURLA_TOP_LEVELS:
            continue
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if not origin or origin in ("built-in", "frozen"):
            continue
        if top in scan.local_top_levels:
            shipped.add(name)
            continue
        if not (_resolved(os.path.dirname(origin)) + os.sep).startswith(known):
            shipped.add(name)
    return shipped


def call_time_imports(tree: ast.AST) -> list[tuple[int, str, str, str | None]]:
    """Every import statement inside a function body: (line, function, as written, top level).
    A relative import has no top level and is always local (_env_scan.py:442-478)."""
    found: list[tuple[int, str, str, str | None]] = []

    def visit(node: ast.AST, function: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if function is not None and isinstance(child, ast.Import):
                for alias in child.names:
                    found.append(
                        (child.lineno, function, f"import {alias.name}", alias.name.split(".")[0])
                    )
            elif function is not None and isinstance(child, ast.ImportFrom):
                top = None
                if not child.level and child.module:
                    top = child.module.split(".")[0]
                names = ", ".join(alias.name for alias in child.names)
                written = f"from {'.' * child.level}{child.module or ''} import {names}"
                found.append((child.lineno, function, written, top))
            visit(child, function)

    visit(tree, None)
    return found


def _is_local(top: str | None, scan: Scan) -> bool:
    """_env_scan.py:481-512: relative, a local install's name, or a module found outside every
    distribution folder and the standard library."""
    if top is None:
        return True
    if top in _BURLA_TOP_LEVELS or top in sys.builtin_module_names:
        return False
    if top in scan.local_top_levels:
        return True
    try:
        spec = importlib.util.find_spec(top)
    except (ImportError, ValueError):
        return False
    if spec is None:
        return False
    if spec.origin in (None, "built-in", "frozen"):
        locations = list(spec.submodule_search_locations or [])
        if not locations:
            return False
        directory = str(locations[0])
    else:
        if not os.path.isabs(spec.origin):
            return False
        directory = os.path.dirname(spec.origin)
    return not (_resolved(directory) + os.sep).startswith(
        scan.dist_dir_prefixes + scan.stdlib_prefixes
    )


def offenders(function_: Any, scan: Scan, shipped: set[str]) -> list[str]:
    """The refusal's list (_env_scan.py:533-551): the function's own source, then each shipped
    module's file."""
    sources: list[tuple[str, list[tuple[int, str, str, str | None]]]] = []
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function_)))
        sources.append((f"function `{function_.__name__}`", call_time_imports(tree)))
    except (OSError, TypeError, SyntaxError):
        pass
    checked: set[str] = set()
    for name in sorted(shipped):
        path = getattr(sys.modules.get(name), "__file__", None)
        if not path or path in checked:
            continue
        checked.add(path)
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                sources.append((path, call_time_imports(ast.parse(fh.read()))))
        except (OSError, SyntaxError):
            continue
    return [
        f"    {label}:{line} in `{function}()`: {written}"
        for label, findings in sources
        for line, function, written, top in findings
        if _is_local(top, scan)
    ]
