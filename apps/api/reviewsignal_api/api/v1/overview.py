"""Overview route (`docs/api-dashboard.md` §1)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from reviewsignal_api.api.deps import SessionDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.overview import OverviewPayload
from reviewsignal_api.services.overview import OverviewService

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=ApiResponse[OverviewPayload])
async def get_overview(
    session: SessionDep,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
):
    payload = await OverviewService(session).get_overview(start_date, end_date)
    return ApiResponse.ok(payload)
