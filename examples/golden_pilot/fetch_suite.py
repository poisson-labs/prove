"""Download HumanEval once, by an explicit user action. Nothing else calls this.

    python examples/golden_pilot/fetch_suite.py

HumanEval is openai/human-eval, MIT licensed, 164 problems. The pilot never fetches at run
time (spec section 3): the suite is on disk before the first sweep.

**The container fetches its own copy.** The Modal backend ships the pilot with
``Image.add_local_python_source``, which copies ``*.py`` files only, so this download does not
travel with the package -- the Dockerfile repeats the same URL and the same :data:`SHA256`.
The digest is what makes the two copies the same bytes, and therefore makes the 164-id axis
in ``pilot.toml`` (generated here, on the laptop) describe the suite the container loads.
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz"

#: The 164-problem release, measured 2026-09-05. Repeated in the Dockerfile; change both.
SHA256 = "b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef"

HERE = Path(__file__).resolve().parent
OUT = HERE / "suite" / "HumanEval.jsonl.gz"
DOCKERFILE = HERE / "Dockerfile"


def check_dockerfile_agrees() -> str | None:
    """The Dockerfile pins the same digest, or a sentence saying it does not."""
    try:
        text = DOCKERFILE.read_text(encoding="utf-8")
    except OSError:
        return f"could not read {DOCKERFILE} to check its pin"
    if SHA256 not in text:
        return f"{DOCKERFILE} does not carry {SHA256}: the container would fetch other bytes"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="download HumanEval, once, by hand")
    parser.add_argument("--url", default=URL, help="where to fetch from")
    parser.add_argument("--out", default=str(OUT), help="where to write the .jsonl.gz")
    parser.add_argument("--force", action="store_true", help="overwrite an existing suite")
    parser.add_argument("--no-verify", action="store_true", help="skip the digest check")
    args = parser.parse_args(argv)

    drift = check_dockerfile_agrees()
    if drift is not None:
        print(f"warning: {drift}")

    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out} is already here; pass --force to re-download")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {args.url}")
    urllib.request.urlretrieve(args.url, out)  # noqa: S310 - a pinned https URL, by hand
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    if not args.no_verify and args.url == URL and digest != SHA256:
        out.unlink(missing_ok=True)
        print(f"error: digest {digest} != pinned {SHA256}; the suite upstream moved")
        return 1
    print(f"wrote {out} ({out.stat().st_size} bytes, sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
