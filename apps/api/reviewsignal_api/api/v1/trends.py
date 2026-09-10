"""Trends read routes (`docs/api-dashboard.md` §4)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from reviewsignal_api.api.deps import SessionDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.trends import (
    CategoryTrendsPayload,
    RatingHistoryPayload,
    TrendsSummaryPayload,
)
from reviewsignal_api.services.trends import TrendsService

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/ratings", response_model=ApiResponse[RatingHistoryPayload])
async def get_rating_trend(
    session: SessionDep,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
):
    payload = await TrendsService(session).get_ratings(start_date, end_date)
    return ApiResponse.ok(payload)


@router.get("/categories", response_model=ApiResponse[CategoryTrendsPayload])
async def get_category_trends(
    session: SessionDep,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    sentiment: Annotated[Literal["positive", "neutral", "negative"] | None, Query()] = None,
    category_id: Annotated[uuid.UUID | None, Query()] = None,
):
    payload = await TrendsService(session).get_categories(
        start_date, end_date, sentiment=sentiment, category_id=category_id
    )
    return ApiResponse.ok(payload)


@router.get("/summary", response_model=ApiResponse[TrendsSummaryPayload])
async def get_trends_summary(session: SessionDep):
    return ApiResponse.ok(await TrendsService(session).get_summary())
