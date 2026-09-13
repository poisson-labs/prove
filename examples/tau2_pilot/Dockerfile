# The Modal image for the τ²-bench pilot.
#
# Five things live here and nowhere else.
#
# 1. THE PIN. τ²-bench is not on PyPI (the name `tau2` there is an unrelated package), so it is
#    installed from its own repository at one commit. Everything the benchmark decides -- the
#    task text, the airline database, the policy, the evaluator -- is that commit's, and a run
#    that cannot name it cannot be reproduced. TAU2_COMMIT is read back by the wrapper into
#    meta["tau2_commit"], so the store carries the pin and not just this file.
#
# 2. THE SPARSE CHECKOUT. The repository's data/ directory is ~715 MB, of which 576 MB is
#    data/tau2/results (its published leaderboard runs) and 121 MB is the retail and telecom
#    domains. The airline pilot needs data/tau2/domains/airline (9.4 MB) and
#    data/tau2/user_simulator (24 KB, the user simulator's guidelines, read by
#    user_simulator.py at import). A blobless partial clone plus a sparse checkout takes 17 MB.
#
# 3. TAU2_DATA_DIR. tau2.utils.utils falls back to <site-packages>/../data, which does not
#    exist for a pip-installed copy: the wheel ships src/tau2 only. Without this variable the
#    package imports with a warning and every domain load fails later. Pointing it at the
#    checkout is what makes the installed package and its data the same commit.
#
# 4. websockets. `import tau2` reaches tau2.voice.audio_native.openai.provider, which imports
#    websockets unconditionally -- but websockets is in the [voice] extra, not in the base
#    dependencies. A plain `pip install tau2` therefore cannot be imported. Verified 2026-09-13
#    against 1.0.1 at the commit below.
#
# 5. --ignore-requires-python, AND WHY PYTHON 3.11 AND NOT 3.12.
#    τ² declares requires-python ">=3.12,<3.14". Proofload's Modal backend sends the worker as a
#    `serialized=True` Function, so Modal refuses to start when the image's Python differs from
#    the launching interpreter's, and this repository's venv is 3.11:
#
#      InvalidError: The '_container_batch' Function (using `serialized=True`) was defined with
#      Python 3.11, but its Image has 3.12.
#
#    The image's Python is therefore not free -- it is the launcher's. Measured before deciding
#    to override the pin, 2026-09-13 at tau2 1.0.1: `compileall` over all of site-packages/tau2
#    reports zero syntax errors under 3.11, `registry.get_tasks_loader("airline")()` returns its
#    50 tasks, and `build_text_orchestrator` builds. The declared floor is conservative for the
#    half-duplex text path this pilot uses; it is not conservative for 3.13, where the same
#    voice import chain reaches tau2.voice.utils.audio_preprocessing and imports `audioop`,
#    removed from the standard library in 3.13 (PEP 594).
#
#    The escape hatch, if a later τ² does use 3.12 syntax: launch the sweep from a 3.12
#    interpreter with proofload installed, and set this base image to match it. Nothing in the
#    wrapper changes.
#
# 6. MODAL_IMAGE_BUILDER_VERSION=2024.10 (or newer) ON THE LAUNCHING PROCESS. Not expressible
#    in the sweep file, and not optional. Modal installs its own client requirements into
#    whatever image it is handed, AFTER this Dockerfile and before anything Proofload adds; it
#    picks the requirements file from the workspace's image builder version, and the default
#    here resolves to 2023.12. That file pins fastapi==0.88.0, which requires pydantic<2, so
#    pip DOWNGRADES the pydantic τ² just installed and the container dies at import:
#
#      ImportError: cannot import name 'model_validator' from 'pydantic'
#
#    2024.10 carries no fastapi, no typer and no pydantic at all. It does pin
#    typing_extensions==4.12.2, and a current pydantic_core imports `Sentinel` from it, which
#    4.12.2 does not have -- so the same downgrade kills the container one import further on.
#    That one IS repairable from here: pydantic is not in Modal's list, so a `pydantic<2.12`
#    pin below survives the downgrade, and its pydantic_core 2.33.2 needs only
#    typing_extensions>=4.12. Measured on 3.11 with τ²'s full dependency set and Modal's 2024.10
#    pins forced over it: pydantic 2.11.10 / pydantic_core 2.33.2 / typing_extensions 4.12.2 /
#    litellm 1.82.6 / fastapi 0.141.1 imports τ² and builds an airline orchestrator.
#
#    There is no repair for the fastapi-driven pydantic<2 downgrade, which is why the variable
#    is required rather than merely advisable: this file runs BEFORE Modal's install, and
#    ImageSpec refuses `pip` alongside `dockerfile` (M3 modal I16), so the sweep file has no
#    later hook either.
#
#    A 3.12 base would have needed the same variable for a different reason -- 2023.12 pins
#    aiohttp==3.8.3, which has no cp312 wheel and whose Cython-generated C does not compile
#    against the 3.12 C API -- plus build-essential in the image to attempt the compile. On
#    3.11 a wheel exists, so 2024.10 is the only thing needed.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
# τ² logs the whole conversation through loguru at INFO. The container's stderr is not the
# measurement; the store is.
ENV LOGURU_LEVEL=ERROR

ENV TAU2_COMMIT=2174a603f6d014ef94473ffa95957f6ce27100db
ENV TAU2_DATA_DIR=/opt/tau2-bench/data

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# One RUN, no heredoc: heredocs need the BuildKit dockerfile:1.4 frontend and this file is
# built by Modal's builder, not by a local docker with a syntax directive.
RUN git init /opt/tau2-bench \
 && cd /opt/tau2-bench \
 && git remote add origin https://github.com/sierra-research/tau2-bench.git \
 && git sparse-checkout init --no-cone \
 && git sparse-checkout set /src /pyproject.toml /README.md /LICENSE \
      /data/tau2/domains/airline /data/tau2/user_simulator \
 && git fetch --depth 1 --filter=blob:none origin "$TAU2_COMMIT" \
 && git checkout FETCH_HEAD \
 && test "$(git rev-parse HEAD)" = "$TAU2_COMMIT" \
 && echo "tau2-bench pinned at $TAU2_COMMIT"

# τ²'s own dependency list, read out of the pinned pyproject rather than copied here, so the
# two cannot drift. Only the package itself skips the resolver: --ignore-requires-python applies
# to every requirement it is given, and given the whole tree it picks a numpy that has no 3.11
# release and tries to build it from source.
RUN python -c "\
import tomllib; \
d = tomllib.load(open('/opt/tau2-bench/pyproject.toml','rb')); \
open('/tmp/tau2-requirements.txt','w').write('\n'.join(d['project']['dependencies']) + '\n')" \
 && cat /tmp/tau2-requirements.txt \
 && pip install --no-cache-dir -r /tmp/tau2-requirements.txt "websockets>=13.0" "pydantic<2.12" \
 && pip install --no-cache-dir --no-deps --ignore-requires-python /opt/tau2-bench

# Fail the build, not the first batch, if the pinned copy cannot import or cannot find its data.
RUN python -c "\
from tau2.registry import registry; \
tasks = registry.get_tasks_loader('airline')(); \
assert len(tasks) == 50, 'airline is not 50 tasks: ' + str(len(tasks)); \
print('airline ok: ' + str(len(tasks)) + ' tasks')"
