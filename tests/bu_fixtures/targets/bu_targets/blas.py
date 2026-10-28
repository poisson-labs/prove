"""A target that does linear algebra and reports its process's BLAS thread pools: what a numpy
rollout gets inside a worker (PF10's must-fix: one BLAS thread per worker process)."""

import os
from typing import Any

import numpy as np
import scipy.linalg
from threadpoolctl import threadpool_info

from poisson_prove.episode import Episode

THREAD_VARIABLES = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS")


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    x = np.random.default_rng(seed).random((200, 200))
    scipy.linalg.lu_factor(x @ x)
    return Episode(
        outcome="survived",
        t=1.0,
        horizon=1.0,
        meta={
            "pid": os.getpid(),
            "set": sorted(name for name in THREAD_VARIABLES if name in os.environ),
            "pools": [[pool["user_api"], pool["internal_api"], pool["num_threads"]] for pool in threadpool_info()],
        },
    )
