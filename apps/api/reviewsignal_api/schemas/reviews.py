"""Schemas for `GET /reviews` and `GET /reviews/{review_id}` (`docs/api-dashboard.md` §2).

`ReviewDetail.analysis` is always `null` for now: `review_analyses`/`review_aspects` have
no writer yet, since the classification pipeline is out of scope until Google Business
Profile access lands (`docs/PRD.md` §11). The shape is still declared here, per the
documented contract, so the frontend can code against it ahead of that pipeline landing.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rating: int
    review_text: str | None
    reviewer_name: str | None
    created_at: datetime
    analysis_status: str


class ReviewListPayload(BaseModel):
    items: list[ReviewSummary]
    page: int
    page_size: int
    total: int


class ReviewAspectPayload(BaseModel):
    category_id: uuid.UUID
    category_name: str
    sentiment: str
    confidence: float | None
    evidence_span: str | None


class ReviewAnalysisPayload(BaseModel):
    classifier_type: str
    overall_confidence: float | None
    taxonomy_version_number: int
    aspects: list[ReviewAspectPayload]


class ReviewDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    rating: int
    review_text: str | None
    reviewer_name: str | None
    created_at: datetime
    updated_at: datetime
    owner_reply_text: str | None
    owner_reply_at: datetime | None
    analysis_status: str
    analysis: ReviewAnalysisPayload | None = None
