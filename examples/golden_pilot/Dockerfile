# The Modal image for the golden suite pilot.
#
# Two things live here and nowhere else.
#
# 1. GOLDEN_PILOT_BOUNDARY. This file is the only place it is set, anywhere in the
#    repository. golden_pilot.agent refuses to import without it, which is what makes the
#    local backend unsupported for this suite rather than merely discouraged (spec 3, P13).
#
# 2. The suite. The Modal backend ships the pilot into the container with
#    Image.add_local_python_source, which by default copies *.py files only -- so
#    suite/HumanEval.jsonl.gz does NOT travel with the package and the container has to
#    fetch its own copy. It is pinned by SHA-256 to the same bytes fetch_suite.py puts on
#    the laptop, because pilot.toml's 164-id axis is generated from the laptop's copy and a
#    container loading a different suite would produce a finding nobody could reproduce.
#    The URL and the digest are repeated in fetch_suite.py; change one and change the other
#    (fetch_suite.py checks that this file still carries its digest and says so if not).
FROM python:3.11-slim

ENV GOLDEN_PILOT_BOUNDARY=container
ENV PYTHONUNBUFFERED=1

# The pins of requirements.txt. proofload itself is not installed: the Modal backend ships
# the checkout's source and pip-installs proofload's own runtime requirements on top of this
# image, so a PyPI copy here would shadow the code under test.
RUN pip install --no-cache-dir \
      "openai<2" \
      "opentelemetry-instrumentation-openai-v2==2.4b0" \
      "opentelemetry-sdk"

# One RUN, no heredoc: heredocs need the BuildKit dockerfile:1.4 frontend and this file is
# built by Modal's builder, not by a local docker with a syntax directive.
RUN python -c "\
import hashlib, pathlib, urllib.request; \
url = 'https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz'; \
sha = 'b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef'; \
path = pathlib.Path('/opt/golden-pilot/HumanEval.jsonl.gz'); \
path.parent.mkdir(parents=True, exist_ok=True); \
urllib.request.urlretrieve(url, path); \
digest = hashlib.sha256(path.read_bytes()).hexdigest(); \
assert digest == sha, 'HumanEval moved upstream: ' + digest + ' is not the pinned digest'; \
print('suite pinned at ' + digest)"

ENV GOLDEN_PILOT_SUITE=/opt/golden-pilot/HumanEval.jsonl.gz
