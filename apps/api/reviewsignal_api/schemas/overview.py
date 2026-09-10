"""Schemas for `GET /overview` (`docs/api-dashboard.md` §1).

`positive_themes`/`negative_themes` are always empty for now: aggregating them needs
`review_aspects` joined through an active taxonomy version, and no taxonomy version
exists yet (`SystemService.status().active_taxonomy` is `None` on a fresh install too).
Unlike `active_insights` below, there is no real table to query even an empty result
from, so the field is typed but left unimplemented rather than given a dead-end query.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RatingTrendPoint(BaseModel):
    date: date
    review_count: int
    average_rating: float | None


class ThemePayload(BaseModel):
    category_name: str
    sentiment: str
    mention_count: int


class InsightSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    severity: str
    status: str
    created_at: datetime


class OverviewPayload(BaseModel):
    start_date: datetime
    end_date: datetime
    review_count: int
    average_rating: float | None
    rating_trend: list[RatingTrendPoint]
    positive_themes: list[ThemePayload]
    negative_themes: list[ThemePayload]
    active_insights: list[InsightSummary]
