"""Write ``pilot.toml`` and ``smoke.toml`` from ``suite.load()``, so the axis cannot drift.

    python examples/golden_pilot/make_toml.py [--suite PATH] [--out DIR] [--model NAME]

The ``task_id`` axis is the suite's ids in file order and nothing else, so a suite that
changes -- a re-fetch, or the MBPP escape hatch of spec section 3 -- is one command away from
a matching sweep. The output is deterministic: same suite, same bytes.

**The model name appears in two places and they must agree.** ``target_id`` here is
``golden-pilot/<model>@v0`` and the agent reads ``GOLDEN_PILOT_MODEL`` at run time; the
manifest records the first and the requests carry the second. Regenerate with ``--model``
whenever the model changes, or the store will name a model the run did not use.

This module never imports ``golden_pilot.agent``: the key holder runs it on a laptop, outside
the isolation boundary (spec section 3, P13).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # imported as ``golden_pilot.make_toml``
    from . import suite
except ImportError:  # pragma: no cover - run as a script: the file's own directory
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import suite  # type: ignore[no-redef]

#: The instrumentor's entry-point name in the ``opentelemetry_instrumentor`` group, read from
#: ``opentelemetry-instrumentation-openai-v2`` 2.4b0 against ``openai`` 1.109.1. It is the
#: group's only member there, and it is recorded nowhere else.
INSTRUMENTOR = "openai"

#: The coin-flip axis: 0.0 with a pinned seed is the reproducible-vs-noise question, 0.7 is
#: the resamples the golden suite never saw (spec section 1).
TEMPERATURES = (0.0, 0.7)

PILOT_REPLICATES = 32
SMOKE_REPLICATES = 2
SMOKE_TASKS = 5

DEFAULT_MODEL = "gpt-4o-mini"
DOCKERFILE = "examples/golden_pilot/Dockerfile"

#: The two ``[modal]`` numbers the smoke fills in by hand. This file writes them as comments,
#: so regenerating over a sized ``pilot.toml`` would throw away the only automated guard on a
#: 10,496-episode run -- and the README tells you to regenerate whenever the model changes,
#: which is exactly what the smoke tells you. Refuse instead, unless asked twice.
SIZED_FIELDS = ("est_seconds_per_episode", "max_cost")

_TEMPLATE = """\
# Written by examples/golden_pilot/make_toml.py from suite.load(); regenerate rather than
# edit the task_id axis by hand, so the sweep and the suite cannot drift apart.
target_id = "golden-pilot/{model}@v0"
t_unit = "tool_calls"
replicates = {replicates}

[axes.task_id]
type = "categorical"
values = [
{task_ids}
]

[axes.temperature]
type = "continuous"
values = [{temperatures}]

[capture]
instrument = ["{instrument}"]
content = false

[modal]
concurrency = 16
batch_size = 64
episode_timeout = 120.0
infra_retries = 2
# Filled from the smoke, before the sized run and never after (spec section 3).
#
# max_cost guards MODAL COMPUTE ONLY: estimate_cost is jobs x est_seconds_per_episode x the
# container rate, and it knows nothing about tokens. The $50 cap is model spend plus compute
# and nothing enforces it -- it is arithmetic you do from the smoke before you launch. If
# three arms do not fit, drop replicates to 16 for all three before cutting task_id, because
# 32 seeds per case is the finding.
# est_seconds_per_episode = <seconds per episode, measured by the smoke>
# max_cost = <USD of Modal compute you will not exceed; the sweep refuses above it>

[modal.image]
dockerfile = "{dockerfile}"
local_packages = ["golden_pilot"]
"""


def render(task_ids: list[str], *, replicates: int, model: str) -> str:
    """One sweep file. Pure: the same arguments give the same bytes."""
    return _TEMPLATE.format(
        model=model,
        replicates=replicates,
        task_ids="\n".join(f"  {json.dumps(task_id)}," for task_id in task_ids),
        temperatures=", ".join(repr(float(value)) for value in TEMPERATURES),
        instrument=INSTRUMENTOR,
        dockerfile=DOCKERFILE,
    )


def sized_values(path: Path) -> list[str]:
    """The smoke-filled ``[modal]`` numbers an existing sweep file already carries."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    found = []
    for name in SIZED_FIELDS:
        if re.search(rf"^\s*{name}\s*=", text, re.M):
            found.append(name)
    return found


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="write pilot.toml and smoke.toml")
    parser.add_argument("--suite", default=None, help="a .jsonl or .jsonl.gz suite file")
    parser.add_argument("--out", default=str(here), help="directory for the two TOMLs")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="the model target_id names")
    parser.add_argument(
        "--force", action="store_true", help="overwrite even where the smoke's numbers are set"
    )
    args = parser.parse_args(argv)

    task_ids = [golden.task_id for golden in suite.load(args.suite)]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if not args.force:
        blocked = [
            (out / name, sized_values(out / name))
            for name in ("pilot.toml", "smoke.toml")
            if sized_values(out / name)
        ]
        if blocked:
            for path, fields in blocked:
                print(f"refusing to overwrite {path}: it already sets {', '.join(fields)}")
            print("those came from the smoke and nothing else writes them.")
            print("pass --force to discard them and regenerate anyway.")
            return 1

    written = []
    for name, replicates, ids in (
        ("pilot.toml", PILOT_REPLICATES, task_ids),
        ("smoke.toml", SMOKE_REPLICATES, task_ids[:SMOKE_TASKS]),
    ):
        path = out / name
        path.write_text(render(ids, replicates=replicates, model=args.model), encoding="utf-8")
        written.append(f"{path} ({len(ids)} tasks x {len(TEMPERATURES)} x {replicates})")
    print("\n".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
