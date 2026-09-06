"""Benchmark evaluation job (`docs/api-spec.md` §10, `docs/evaluation.md` §30).

One run records one row: `record` writes a single `evaluation_runs` entry whose
`metrics` body carries every family the pass produced (`docs/data-model.md` §16).

Reaching this handler means a predictor was registered when the run was queued; the
guard is repeated here because the registry can change between queueing and execution.
"""

from pathlib import Path

from reviewsignal_api.ai.evaluation.dataset import load_benchmark
from reviewsignal_api.ai.evaluation.registry import get_predictor
from reviewsignal_api.ai.evaluation.runner import run_evaluation
from reviewsignal_api.core.config import get_settings
from reviewsignal_api.core.errors import ModelUnavailableError
from reviewsignal_api.repositories.evaluation_runs import EvaluationRunRepository
from reviewsignal_worker.db import session_scope


def benchmark_path() -> str:
    """Read through a function so a test can retarget it without clearing the settings cache."""
    return get_settings().benchmark_path


def evaluation_run(payload: dict) -> None:
    evaluation_type = payload["evaluation_type"]

    predictor = get_predictor(evaluation_type)
    if predictor is None:
        raise ModelUnavailableError(
            f"No predictor is registered for evaluation type {evaluation_type!r}."
        )

    path = benchmark_path()
    if not path:
        # Failing is the point: scoring the synthetic placeholder would write a row
        # that looks like a result (`data/benchmarks/v0-synthetic.json` forbids it).
        raise ValueError("No benchmark is configured; set BENCHMARK_PATH.")

    result = run_evaluation(load_benchmark(Path(path)), predictor)
    with session_scope() as session:
        EvaluationRunRepository(session).record(result, evaluation_type=evaluation_type)
