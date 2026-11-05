"""A process that calls ``main()`` more than once keeps getting Prove's output on its real stdout
(issue 28).

**What is pinned.** ``--json`` with no ``stdout=`` moves file descriptor 1 onto stderr for the rest
of the process and writes the document to a private copy of the real stdout. The move happens
once. A second call must not take descriptor 1, which is stderr by then, for the real stdout: its
document would land on stderr. So every later call in that process, with ``--json`` or without,
writes its own output to the same copy.

``test_json_stdout.py`` holds one call a process; this holds the calls after the first. What a
host script prints itself after the first call goes to stderr, as the CHANGELOG says, and is not
pinned here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

_DRIVER = """\
import sys
from poisson_prove.cli import main

codes = [main(["init", "--example", "--out", name, *more]) for name, more in (
    ("first.toml", ["--json"]), ("second.toml", ["--json"]), ("third.toml", []),
)]
sys.stdout.flush()
sys.stderr.write(f"codes {codes}\\n")
"""


def _run(base: Path, *argv: str) -> subprocess.CompletedProcess[bytes]:
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "CI", "PYTHONUNBUFFERED")
    env = {key: value for key, value in os.environ.items() if key not in drop}
    env.update(PYTHONPATH=str(SRC), HOME=str(base), NO_COLOR="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, *argv], cwd=base, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)


def test_later_calls_in_one_process_still_write_to_the_real_stdout(tmp_path: Path) -> None:
    """Two ``--json`` calls and then a plain one: stdout holds the two documents and the plain
    call's text, in that order, and stderr holds none of them."""
    (tmp_path / "driver.py").write_text(_DRIVER, encoding="utf-8")
    done = _run(tmp_path, "driver.py")
    assert done.returncode == 0, done.stderr[-600:]
    assert b"codes [0, 0, 0]" in done.stderr, done.stderr[-600:]
    text = done.stdout.decode("utf-8")
    decoder = json.JSONDecoder()
    first, end = decoder.raw_decode(text)
    second, end_second = decoder.raw_decode(text, end + 1)
    assert text[end] == "\n" and text[end_second] == "\n", text[:400]
    for document, name in ((first, "first.toml"), (second, "second.toml")):
        assert document["schema"] == "poisson-prove.init/1", document
        assert name in json.dumps(document), document
    # The plain call's own output is what a process of its own prints for the same command.
    alone = tmp_path / "alone"
    alone.mkdir()
    plain = _run(alone, "-m", "poisson_prove", "init", "--example", "--out", "third.toml")
    assert plain.returncode == 0, plain.stderr[-600:]
    assert plain.stdout, "init without --json prints its verdict"
    assert text[end_second + 1 :] == plain.stdout.decode("utf-8"), text[end_second + 1 :][:400]
    for word in (b'"schema"', b"third.toml"):
        assert word not in done.stderr, done.stderr[-600:]
