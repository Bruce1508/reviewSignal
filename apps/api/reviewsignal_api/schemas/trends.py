"""Schemas for `/trends/*` (`docs/api-dashboard.md` §4)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class RatingHistoryPoint(BaseModel):
    date: date
    review_count: int
    average_rating: float | None


class RatingHistoryPayload(BaseModel):
    start_date: datetime
    end_date: datetime
    points: list[RatingHistoryPoint]


class CategoryTrendPoint(BaseModel):
    category_id: uuid.UUID
    category_name: str
    sentiment: str
    mention_count: int


class CategoryTrendsPayload(BaseModel):
    start_date: datetime
    end_date: datetime
    categories: list[CategoryTrendPoint]


class CategoryMovement(BaseModel):
    category_id: uuid.UUID
    category_name: str
    sentiment: str
    current_count: int
    previous_count: int
    delta: int


class TrendsSummaryPayload(BaseModel):
    current_start: datetime
    current_end: datetime
    previous_start: datetime
    previous_end: datetime
    biggest_increases: list[CategoryMovement]
    biggest_decreases: list[CategoryMovement]
