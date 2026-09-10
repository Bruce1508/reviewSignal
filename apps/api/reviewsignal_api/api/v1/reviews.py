"""Review list/detail routes (`docs/api-dashboard.md` §2).

Read-only for now: `POST /reviews/{review_id}/reanalyze` is a mutation and stays out of
this pass (`docs/api-spec.md` §16.2 keeps long jobs asynchronous, and there is no
classification pipeline yet to queue).
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from reviewsignal_api.api.deps import SessionDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.reviews import ReviewDetail, ReviewListPayload
from reviewsignal_api.services.reviews import ReviewsService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=ApiResponse[ReviewListPayload])
async def list_reviews(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query()] = None,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
):
    payload = await ReviewsService(session).list_reviews(
        page=page,
        page_size=page_size,
        q=q,
        rating=rating,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse.ok(payload)


@router.get("/{review_id}", response_model=ApiResponse[ReviewDetail])
async def get_review(review_id: uuid.UUID, session: SessionDep):
    return ApiResponse.ok(await ReviewsService(session).get_review(review_id))
