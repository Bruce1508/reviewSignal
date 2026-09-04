"""Schemas for the Google connection and async-job contracts (`docs/api-spec.md` §8, §12)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class GoogleStatusPayload(BaseModel):
    connected: bool
    status: str
    account_id: str | None
    location_id: str | None
    connected_at: datetime | None
    last_sync: datetime | None


class JobAcceptedPayload(BaseModel):
    job_id: uuid.UUID
    status: str
    job_type: str
