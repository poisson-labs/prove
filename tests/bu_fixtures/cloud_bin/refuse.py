"""A fake ``gcloud`` or ``az``: records every call and answers none, exit 2.

Copied into a test's folder on ``PATH`` under the CLI's name. Prove's 0.3.0 offers AWS only, so a
spec naming Google Cloud or Azure is refused before either is run; ``<name>-calls.jsonl`` beside
it must stay empty.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = os.path.basename(sys.argv[0])

with open(os.path.join(HERE, f"{NAME}-calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "time": time.time()}) + "\n")
print(f"fake {NAME}: Prove's checks must not run {NAME} in this release", file=sys.stderr)
sys.exit(2)
