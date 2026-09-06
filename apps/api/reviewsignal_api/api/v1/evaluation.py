"""Evaluation run routes (`docs/api-spec.md` §10, §12).

The PRD phases the evaluation *dashboard* into Phase 3; this API surface lands ahead of
it so run history and metrics are reachable without one.
"""

import uuid

from fastapi import APIRouter

from reviewsignal_api.api.deps import SessionDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.evaluation import (
    EvaluationRunDetail,
    EvaluationRunRequest,
    EvaluationRunSummary,
)
from reviewsignal_api.schemas.jobs import JobAcceptedPayload
from reviewsignal_api.services.evaluation import EVALUATION_JOB_TYPE, EvaluationService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/runs", response_model=ApiResponse[list[EvaluationRunSummary]])
async def list_evaluation_runs(session: SessionDep):
    return ApiResponse.ok(await EvaluationService(session).list_runs())


@router.get("/runs/{run_id}", response_model=ApiResponse[EvaluationRunDetail])
async def get_evaluation_run(run_id: uuid.UUID, session: SessionDep):
    return ApiResponse.ok(await EvaluationService(session).get_run(run_id))


@router.post("/run", response_model=ApiResponse[JobAcceptedPayload], status_code=202)
async def queue_evaluation_run(payload: EvaluationRunRequest, session: SessionDep):
    job_id = await EvaluationService(session).queue_run(payload.evaluation_type)
    return ApiResponse.ok(
        JobAcceptedPayload(job_id=job_id, status="queued", job_type=EVALUATION_JOB_TYPE)
    )
