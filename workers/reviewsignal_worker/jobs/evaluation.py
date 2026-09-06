"""Benchmark evaluation job (`docs/api-spec.md` §10, `docs/evaluation.md` §30).

One run records one row: `record` writes a single `evaluation_runs` entry whose
`metrics` body carries every family the pass produced (`docs/data-model.md` §16).

Reaching this handler means a predictor was registered when the run was queued; the
guard is repeated here because the API and the RQ worker are separate processes and
can be running skewed code.
"""

import uuid
from pathlib import Path

from reviewsignal_api.ai.evaluation.dataset import load_benchmark
from reviewsignal_api.ai.evaluation.registry import get_predictor
from reviewsignal_api.ai.evaluation.runner import run_evaluation
from reviewsignal_api.core.config import get_settings
from reviewsignal_api.repositories.evaluation_runs import EvaluationRunRepository
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.errors import PermanentJobError


def benchmark_path() -> str:
    """Read through a function so a test can retarget it without clearing the settings cache."""
    return get_settings().benchmark_path


def evaluation_run(payload: dict, job_id: uuid.UUID) -> None:
    evaluation_type = payload["evaluation_type"]

    with session_scope() as session:
        if EvaluationRunRepository(session).already_recorded(job_id):
            # A retry that got past the run being committed. Re-scoring would add a
            # second baseline to the history, so this attempt has nothing left to do.
            return

    predictor = get_predictor(evaluation_type)
    if predictor is None:
        raise PermanentJobError(
            f"No predictor is registered for evaluation type {evaluation_type!r}."
        )

    path = benchmark_path()
    if not path:
        # Failing is the point: scoring the synthetic placeholder would write a row
        # that looks like a result (`data/benchmarks/v0-synthetic.json` forbids it).
        raise PermanentJobError("No benchmark is configured; set BENCHMARK_PATH.")

    result = run_evaluation(load_benchmark(Path(path)), predictor)
    with session_scope() as session:
        EvaluationRunRepository(session).record(
            result, evaluation_type=evaluation_type, job_id=job_id
        )
