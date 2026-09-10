"""Schemas for `/insights/*` read endpoints (`docs/api-dashboard.md` §5).

`impact` is always `null` and `related_review_ids` always empty: impact is computed by
`POST /insights/{id}/recompute-impact`, a queued job that does not exist yet
(`docs/insight-pipeline.md` §10), and nothing links a review to an insight directly —
there is no join table for it in `docs/analysis-tables.md`.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class InsightActionPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action_text: str
    action_date: date | None
    note_text: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class InsightListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    severity: str
    status: str
    created_at: datetime


class InsightDetail(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    severity: str
    evidence_summary: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    related_review_ids: list[uuid.UUID]
    actions: list[InsightActionPayload]
    impact: dict | None
