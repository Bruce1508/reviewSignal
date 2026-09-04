"""Schemas for the health and system-status contracts (`docs/api-spec.md` §2)."""

from datetime import datetime

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    api: str
    database: str
    redis: str


class HealthPayload(BaseModel):
    status: str
    components: ComponentHealth


class LastSync(BaseModel):
    status: str
    started_at: datetime
    finished_at: datetime | None
    reviews_created: int
    reviews_updated: int


class ActiveTaxonomy(BaseModel):
    version_number: int
    activated_at: datetime | None


class SystemStatusPayload(BaseModel):
    last_sync: LastSync | None
    queue_depth: int
    failed_jobs: int
    active_taxonomy: ActiveTaxonomy | None
    active_model: str
    last_insight_at: datetime | None
