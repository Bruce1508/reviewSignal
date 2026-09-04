"""Schemas for the Google connection and async-job contracts (`docs/api-spec.md` §8, §12)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# Both ids become path segments in the v4 reviews URL, so this is a boundary guard
# against a malformed value retargeting the request, not cosmetic validation.
RESOURCE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"


class GoogleStatusPayload(BaseModel):
    connected: bool
    status: str
    account_id: str | None
    location_id: str | None
    connected_at: datetime | None
    last_sync: datetime | None


class GoogleAccountPayload(BaseModel):
    account_id: str
    name: str


class GoogleLocationPayload(BaseModel):
    location_id: str
    title: str


class GoogleLocationSelection(BaseModel):
    """Which profile to ingest from (`docs/data-model.md` §18)."""

    account_id: str = Field(pattern=RESOURCE_ID_PATTERN)
    location_id: str = Field(pattern=RESOURCE_ID_PATTERN)


class JobAcceptedPayload(BaseModel):
    job_id: uuid.UUID
    status: str
    job_type: str
