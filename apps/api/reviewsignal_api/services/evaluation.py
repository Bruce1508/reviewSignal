"""Evaluation history and run submission (`docs/api-spec.md` §10).

Handlers stay thin (`docs/api-spec.md` §16.1), so the not-found and no-predictor
decisions live here.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from reviewsignal_api.ai.evaluation.registry import get_predictor
from reviewsignal_api.core.errors import ModelUnavailableError, ResourceNotFoundError
from reviewsignal_api.repositories.evaluation_runs import EvaluationRunReader
from reviewsignal_api.schemas.evaluation import EvaluationRunDetail, EvaluationRunSummary
from reviewsignal_worker.queue import enqueue

EVALUATION_JOB_TYPE = "evaluation_run"


class EvaluationService:
    def __init__(self, session: AsyncSession) -> None:
        self._runs = EvaluationRunReader(session)

    async def list_runs(self) -> list[EvaluationRunSummary]:
        runs = await self._runs.list_newest_first()
        return [EvaluationRunSummary.model_validate(run) for run in runs]

    async def get_run(self, run_id: uuid.UUID) -> EvaluationRunDetail:
        run = await self._runs.get(run_id)
        if run is None:
            raise ResourceNotFoundError("Evaluation run not found.")
        return EvaluationRunDetail.model_validate(run)

    async def queue_run(self, evaluation_type: str) -> uuid.UUID:
        """Refuse before queueing rather than after.

        A run with no registered predictor cannot succeed, and a dead row in `jobs`
        is worse than a refusal the caller can act on: `jobs` is what `/system/status`
        reports failures from (`docs/api-spec.md` §2).
        """
        if get_predictor(evaluation_type) is None:
            raise ModelUnavailableError(
                f"No predictor is registered for evaluation type {evaluation_type!r}."
            )
        return await run_in_threadpool(
            enqueue, EVALUATION_JOB_TYPE, {"evaluation_type": evaluation_type}, 3
        )
