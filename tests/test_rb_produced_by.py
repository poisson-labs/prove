"""Remote backends, C6: ``produced_by`` in the run manifest (#17), invariants P1 to P6 and rulings
RB-35 and RB-36.

The artifact format's 1.1 adds one optional manifest key, ``produced_by``: an object whose shared
members are ``version`` (the writing tool's version) and ``from`` (a list of ``{"name", "sha256"}``
digests of what the run was made from), and whose other members are the tool's own. Prove writes
``version``, ``from`` (the sweep spec file by its name without its folder, then the target's module
by its import path less the function, each a hex SHA-256 of the bytes read), ``tool`` and
``backend``, and on a cloud account ``bundle`` (that case is in ``test_bu_burla_backend.py``, beside
the cluster backend's fake). It is written once, when the run is opened; a resume keeps it and
records the segment's own under its ``resumed`` event.

**What the tests fix that the invariants leave open.** The local and Modal ``produced_by`` holds
exactly the four members above; the manifest is read as the JSON file it is. The ``resume`` verb,
which reads no spec file, records ``from`` with the target alone.

Every sweep runs in this process through ``cli.main``; Modal through a fake ``modal`` in
``sys.modules``. The app is driven by Textual's pilot through ``pf6_support.drive``.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.machinery
import io
import json
import py_compile
import re
import shutil
import socket
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from secrets import token_hex
from typing import Any

import pytest

import poisson_prove
from poisson_prove import cli

MEMBERS = {"version", "from", "tool", "backend"}
ROLLOUT = (
    "from poisson_prove.episode import Episode\n"
    "# a comment a test may change by one byte: a\n\n\n"
    "def rollout(cfg, seed):\n"
    '    return Episode(outcome="fell" if seed % 3 == 0 else "survived", t=1.0, horizon=1.0)\n'
)
SPEC = (
    'target_id = "rb-produced@v0"\nt_unit = "steps"\nreplicates = 6\n'
    "# a comment a test may change by one byte: a\n\n"
    '[axes.cell]\ntype = "categorical"\nvalues = ["a", "b"]\n'
)
MOCK = "poisson_prove.examples.mock_agent"
#: Keys planted in the environment while a run is written: nothing that looks like one may reach
#: ``produced_by`` (P5). The same shapes the PF12 tests plant.
PLANTED = {
    "OPENAI_API_KEY": "sk-rb-planted-openai-00000000000000000",
    "ANTHROPIC_API_KEY": "sk-ant-rb-planted-anthropic-0000000000",
    "MODAL_TOKEN_SECRET": "as-rb-planted-modal-secret-000000000",
    "AWS_SECRET_ACCESS_KEY": "rbPlantedAwsSecret0000000000000000000000",
    "AWS_ACCESS_KEY_ID": "AKIARBPLANTED0000000",
}
SAVED_AT = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z")
KEY_SHAPES = re.compile(r"sk-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]+")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def world(root: Path, monkeypatch: pytest.MonkeyPatch, *, spec: str = SPEC, tail: str = "") -> tuple[Path, str]:
    """A folder holding ``prove.toml`` and a target module of its own name, on the path."""
    root.mkdir(parents=True, exist_ok=True)
    module = f"rb_pb_{token_hex(4)}"
    (root / f"{module}.py").write_text(ROLLOUT, encoding="utf-8")
    (root / "prove.toml").write_text(spec + tail, encoding="utf-8")
    monkeypatch.syspath_prepend(str(root))
    return root / "prove.toml", module


def prove(store: Path, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--store", str(store), *argv], stdout=out, stderr=err, stdin=io.StringIO())
    return code, out.getvalue(), err.getvalue()


def sweep(store: Path, spec: Path, target: str, *more: str, code: int = 0) -> str:
    """One sweep; the id of the run it wrote. A sweep stopped short (``--max-rollouts``) exits 3."""
    got, out, err = prove(store, "sweep", str(spec), "--target", target, "--max-mde", "1", "--yes", "--json", *more)
    assert got == code, (got, out, err)
    return str(json.loads(out)["run_id"])


def manifest(store: Path, run_id: str) -> dict[str, Any]:
    return json.loads((store / run_id / "manifest.json").read_text(encoding="utf-8"))


def events(store: Path, run_id: str) -> list[dict[str, Any]]:
    text = (store / run_id / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def module_file(module: str) -> Path:
    return Path(sys.modules[module].__file__ or "")


def expected_from(spec: Path, module: str, source: Path | None) -> list[dict[str, Any]]:
    return [
        {"name": spec.name, "sha256": sha256(spec)},
        {"name": module, "sha256": None if source is None else sha256(source)},
    ]


def forget(monkeypatch: pytest.MonkeyPatch, module: str) -> None:
    """Drop a target module from ``sys.modules`` so the next sweep imports it from its file again."""
    monkeypatch.delitem(sys.modules, module, raising=False)


# ---------- P1: every run a sweep opens ----------


def test_p1_a_local_run_records_the_tool_the_spec_and_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec, module = world(tmp_path / "w", monkeypatch)
    store = tmp_path / "store"
    run_id = sweep(store, spec, f"{module}:rollout")
    produced = manifest(store, run_id).get("produced_by")
    assert isinstance(produced, dict), manifest(store, run_id)
    assert set(produced) == MEMBERS, produced
    assert produced["version"] == poisson_prove.__version__
    assert produced["tool"] == "poisson-prove" and produced["backend"] == "local", produced
    assert produced["from"] == expected_from(spec, module, tmp_path / "w" / f"{module}.py"), produced


def test_p1_the_mock_agent_is_named_by_its_module_path_and_digested_over_its_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, _ = world(tmp_path / "w", monkeypatch)
    store = tmp_path / "store"
    run_id = sweep(store, spec, f"{MOCK}:rollout_patched")
    produced = manifest(store, run_id)["produced_by"]
    source = Path(poisson_prove.__file__).parent / "examples" / "mock_agent.py"
    assert produced["from"] == expected_from(spec, MOCK, source), produced


def test_p1_rb35_a_target_with_no_source_file_is_listed_with_a_null_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The module is only its compiled file, beside where its source would be (a sourceless import):
    it is listed by name with ``"sha256": null``, never left out."""
    spec, module = world(tmp_path / "w", monkeypatch)
    source = tmp_path / "w" / f"{module}.py"
    py_compile.compile(str(source), cfile=str(tmp_path / "w" / f"{module}.pyc"), doraise=True)
    source.unlink()
    store = tmp_path / "store"
    run_id = sweep(store, spec, f"{module}:rollout")
    assert module_file(module).suffix == ".pyc", module_file(module)
    produced = manifest(store, run_id)["produced_by"]
    assert produced["from"] == expected_from(spec, module, None), produced


# ---------- P1 on Modal ----------


class _Image:
    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: self


@pytest.fixture
def fake_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Modal's client offline: the map runs Prove's container function on every item in turn."""
    fake = types.ModuleType("modal")
    fake.__spec__ = importlib.machinery.ModuleSpec("modal", None)

    class Function:
        def __init__(self, fn: Any) -> None:
            self.fn = fn

        def map(self, items: Any, **kwargs: Any) -> Iterator[Any]:
            for item in items:
                yield self.fn(item)

    class App:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def function(self, **kwargs: Any) -> Any:
            return Function

        @contextlib.contextmanager
        def run(self) -> Iterator[Any]:
            yield self

    fake.App = App  # type: ignore[attr-defined]
    fake.Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image(),  # type: ignore[attr-defined]
                                       from_dockerfile=lambda *a, **k: _Image())
    fake.Secret = types.SimpleNamespace(from_name=lambda *a, **k: object())  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "modal", fake)


MODAL_TABLE = '\n[modal]\nconcurrency = 1\nbatch_size = 4\n\n[modal.image]\npython = "3.11"\n'


def test_p1_a_modal_run_records_the_same_with_its_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_modal: None
) -> None:
    spec, module = world(tmp_path / "w", monkeypatch, tail=MODAL_TABLE)
    store = tmp_path / "store"
    run_id = sweep(store, spec, f"{module}:rollout", "--backend", "modal")
    produced = manifest(store, run_id)["produced_by"]
    assert set(produced) == MEMBERS, produced
    assert produced["backend"] == "modal" and produced["tool"] == "poisson-prove", produced
    assert produced["version"] == poisson_prove.__version__
    assert produced["from"] == expected_from(spec, module, tmp_path / "w" / f"{module}.py"), produced


# ---------- P2: one byte ----------


def _one_byte(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "one byte: a" in text
    path.write_text(text.replace("one byte: a", "one byte: b"), encoding="utf-8")


def test_p2_one_byte_of_the_spec_changes_the_specs_digest_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, module = world(tmp_path / "w", monkeypatch)
    store = tmp_path / "store"
    before = manifest(store, sweep(store, spec, f"{module}:rollout"))["produced_by"]
    _one_byte(spec)
    forget(monkeypatch, module)
    after = manifest(store, sweep(store, spec, f"{module}:rollout"))["produced_by"]
    assert after["from"][0]["sha256"] == sha256(spec) != before["from"][0]["sha256"]
    assert {**after, "from": after["from"][1:]} == {**before, "from": before["from"][1:]}, (before, after)
    assert after["from"][0]["name"] == before["from"][0]["name"]


def test_p2_one_byte_of_the_targets_module_changes_its_digest_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, module = world(tmp_path / "w", monkeypatch)
    store = tmp_path / "store"
    before = manifest(store, sweep(store, spec, f"{module}:rollout"))["produced_by"]
    source = tmp_path / "w" / f"{module}.py"
    _one_byte(source)
    forget(monkeypatch, module)
    after = manifest(store, sweep(store, spec, f"{module}:rollout"))["produced_by"]
    assert after["from"][1]["sha256"] == sha256(source) != before["from"][1]["sha256"]
    assert {**after, "from": after["from"][:1]} == {**before, "from": before["from"][:1]}, (before, after)
    assert after["from"][1]["name"] == before["from"][1]["name"] == module


# ---------- P3, RB-36: a resume ----------


def test_p3_a_resume_keeps_the_manifests_produced_by_and_records_its_own_in_its_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Segment one stops at --max-rollouts; the target's module changes by one byte; the resume runs
    the run to complete. The manifest's ``produced_by`` is the first segment's, as written, through
    the resume and the run's completion; the ``resumed`` event carries the segment's own, with the
    module's new digest."""
    spec, module = world(tmp_path / "w", monkeypatch)
    store = tmp_path / "store"
    target = f"{module}:rollout"
    run_id = sweep(store, spec, target, "--max-rollouts", "4", code=3)
    assert manifest(store, run_id)["status"] == "partial"
    first = manifest(store, run_id)["produced_by"]
    source = tmp_path / "w" / f"{module}.py"
    _one_byte(source)
    forget(monkeypatch, module)
    assert sweep(store, spec, target, "--resume", run_id) == run_id
    final = manifest(store, run_id)
    assert final["status"] == "complete", final
    assert json.dumps(final["produced_by"], sort_keys=True) == json.dumps(first, sort_keys=True)
    (resumed,) = [e for e in events(store, run_id) if e["kind"] == "resumed"]
    own = resumed["detail"].get("produced_by")
    assert isinstance(own, dict) and set(own) == MEMBERS, resumed
    assert own["from"] == expected_from(spec, module, source), own
    assert own["from"][1]["sha256"] != first["from"][1]["sha256"]


def test_p3_the_cores_resume_keeps_the_manifest_and_records_the_target_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``poisson_prove.core.resume`` continues a partial run from what its manifest recorded and reads
    no spec file, so its segment's ``from`` names the target alone; the
    manifest's ``produced_by`` is unchanged."""
    from poisson_prove import core

    spec, module = world(tmp_path / "w", monkeypatch)
    store = tmp_path / "store"
    run_id = sweep(store, spec, f"{module}:rollout", "--max-rollouts", "4", code=3)
    first = manifest(store, run_id)["produced_by"]
    result = core.resume(str(store))
    assert result.run_id == run_id and not result.stopped, result
    assert manifest(store, run_id)["status"] == "complete"
    assert manifest(store, run_id)["produced_by"] == first
    (resumed,) = [e for e in events(store, run_id) if e["kind"] == "resumed"]
    own = resumed["detail"].get("produced_by")
    assert isinstance(own, dict), resumed
    assert own["from"] == [{"name": module, "sha256": sha256(tmp_path / "w" / f"{module}.py")}], own


# ---------- P4: readers, with and without the key ----------


def _readable_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list[str], list[str]]:
    """Two runs of the mock agent over the quickstart's design, the second the patched agent paired
    with the first, so ``diff`` and ``report`` have a comparison to read."""
    from conftest import quickstart_design

    design = tmp_path / "design" / "quickstart.toml"
    design.parent.mkdir()
    text = quickstart_design(10).read_text(encoding="utf-8").replace("replicates = 10", "replicates = 4")
    design.write_text(text, encoding="utf-8")
    store = tmp_path / "base"
    a = sweep(store, design, f"{MOCK}:rollout")
    b = sweep(store, design, f"{MOCK}:rollout_patched", "--pair-with", a)
    axes = re.findall(r"\[axes\.(\w+)\]", text)
    assert len(axes) == 2, axes
    return store, [a, b], axes


SYNTHETIC = {"version": "0.3.0", "from": [{"name": "prove.toml", "sha256": "0" * 64}], "tool": "poisson-prove",
             "backend": "local"}


def _variant(base: Path, dest: Path, keep: dict[str, bool]) -> Path:
    """A copy of ``base`` in which each run's manifest has ``produced_by`` (``keep[run]``) or has
    not. The run's own key is kept where there is one; a manifest without one gets a stand-in."""
    shutil.copytree(base, dest)
    for run_id, with_key in keep.items():
        path = dest / run_id / "manifest.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if with_key:
            doc.setdefault("produced_by", SYNTHETIC)
        else:
            doc.pop("produced_by", None)
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def _read_everything(store: Path, runs: list[str], axes: list[str], out_dir: Path) -> dict[str, str]:
    """What ``runs``, ``inspect``, ``diff``, ``report`` and the dashboard show for the store, with the
    store's own folder written as ``STORE``."""
    a, b = runs
    shown: dict[str, str] = {}
    for label, argv in {
        "runs": ["runs"],
        "runs --json": ["runs", "--json"],
        "inspect": ["inspect", a, "--event", "fell", "--limit", "2", "--json"],
        "diff": ["diff", a, b, "--json"],
        "report": ["report", a, b, "--x", axes[0], "--y", axes[1], "--out", str(out_dir), "--json"],
        "ui": ["ui", "--json"],
    }.items():
        code, out, err = prove(store, *argv)
        assert code in (0, 4), (label, code, out, err)
        shown[label] = f"{code}\n{out}"
    for path in sorted(out_dir.rglob("*")):
        if path.is_file():
            shown[f"report/{path.relative_to(out_dir)}"] = path.read_text(encoding="utf-8", errors="replace")
    ui = store / ".poisson" / "ui"
    for path in sorted(ui.rglob("*")):
        if path.is_file():
            shown[f"ui/{path.relative_to(ui)}"] = path.read_text(encoding="utf-8", errors="replace")
    # A saved comparison carries the moment it was saved, which differs from one reading to the next.
    return {k: SAVED_AT.sub("TIME", v) for k, v in shown.items()}


def _app_screen(store: Path) -> str:
    from pf6_support import drive

    async def runs_page(session: Any) -> str:
        await session.settle()
        return str(await session.read_through())

    code, text = drive(runs_page, cwd=store.parent, store=str(store), size=(160, 40))
    return str(text)


def test_p4_every_reader_reads_a_store_with_and_without_the_key_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same two runs, three ways: both manifests with ``produced_by``, neither, and one of each
    (a run 0.2.1 wrote beside one this release wrote). ``runs``, ``inspect``, ``diff``, ``report``,
    the dashboard's pages and the app's runs page read the three alike, and reading leaves every
    manifest byte for byte as it was."""
    monkeypatch.setenv("NO_COLOR", "1")
    base, runs, axes = _readable_store(tmp_path, monkeypatch)
    a, b = runs
    stores = {
        "with": _variant(base, tmp_path / "s-with", {a: True, b: True}),
        "without": _variant(base, tmp_path / "s-without", {a: False, b: False}),
        "mixed": _variant(base, tmp_path / "s-mixed", {a: False, b: True}),
    }
    for store in stores.values():
        when = "2026-01-02T03:04:05.000000Z"
        for run_id in runs:
            path = store / run_id / "manifest.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["created_at"] = when  # one age on every page, whenever each store is read
            path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Each variant is read at one and the same place, so every path a reader prints is the same.
    place, out_dir = tmp_path / "read" / "store", tmp_path / "read" / "report"
    shown: dict[str, dict[str, str]] = {}
    screens: dict[str, str] = {}
    for name, store in stores.items():
        before = {r: (store / r / "manifest.json").read_bytes() for r in runs}
        shutil.rmtree(place.parent, ignore_errors=True)
        shutil.copytree(store, place)
        # The app first, while the store holds no saved comparison: one saved by a reader below
        # would show the minute it was saved.
        screens[name] = _app_screen(place)
        shown[name] = _read_everything(place, runs, axes, out_dir)
        after = {r: (place / r / "manifest.json").read_bytes() for r in runs}
        assert after == before, (name, "reading the store rewrote a manifest")
    for name in ("without", "mixed"):
        assert shown[name].keys() == shown["with"].keys(), name
        for key in shown["with"]:
            assert shown[name][key] == shown["with"][key], (name, key)
    assert screens["without"] == screens["with"] == screens["mixed"], screens


# ---------- P5: nothing private ----------


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def test_p5_no_member_holds_a_key_an_absolute_path_or_a_host_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keys planted in the environment, the spec and the target in a folder named after this machine:
    no string in ``produced_by`` is a planted key or has a key's shape, holds a folder separator or
    this machine's name."""
    host = socket.gethostname()
    for name, value in PLANTED.items():
        monkeypatch.setenv(name, value)
    spec, module = world(tmp_path / f"{host}-work", monkeypatch)
    store = tmp_path / "store"
    run_id = sweep(store, spec, f"{module}:rollout")
    produced = manifest(store, run_id)["produced_by"]
    names = {host, host.split(".")[0]} - {""}
    for text in _strings(produced):
        assert not any(value in text for value in PLANTED.values()), text
        assert not KEY_SHAPES.search(text), text
        assert "/" not in text and "\\" not in text and not text.startswith("~"), text
        assert not any(name.lower() in text.lower() for name in names), (text, names)


# ---------- P6: the format's page ----------


def test_p6_the_artifact_format_page_documents_the_key_and_its_five_members() -> None:
    page = (Path(__file__).resolve().parents[1] / "docs" / "artifact-format.md").read_text(encoding="utf-8")
    start = page.index("### `manifest.json`")
    end = page.index("\n### ", start + 1)
    section = page[start:end]
    for word in ("produced_by", "version", "from", "tool", "backend", "bundle", "name", "sha256"):
        assert f"`{word}`" in section, word
