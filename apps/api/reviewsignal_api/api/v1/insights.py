"""Insight read routes (`docs/api-dashboard.md` §5).

Read-only: `PATCH /insights/{id}/status`, `POST /insights/{id}/actions`,
`PATCH /insights/{id}/actions/{action_id}`, and `POST /insights/{id}/recompute-impact`
are mutations and stay out of this pass.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from reviewsignal_api.api.deps import SessionDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.insights import InsightDetail, InsightListItem
from reviewsignal_api.services.insights import InsightsService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=ApiResponse[list[InsightListItem]])
async def list_insights(
    session: SessionDep,
    status: Annotated[Literal["new", "monitoring", "resolved"] | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    category_id: Annotated[uuid.UUID | None, Query()] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
):
    payload = await InsightsService(session).list_insights(
        status=status,
        severity=severity,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse.ok(payload)


@router.get("/{insight_id}", response_model=ApiResponse[InsightDetail])
async def get_insight(insight_id: uuid.UUID, session: SessionDep):
    return ApiResponse.ok(await InsightsService(session).get_insight(insight_id))
