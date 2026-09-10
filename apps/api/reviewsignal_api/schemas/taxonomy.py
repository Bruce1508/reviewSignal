"""Schemas for `/taxonomy/*` read endpoints (`docs/api-dashboard.md` §3).

Every field maps directly to `taxonomy_versions`/`taxonomy_nodes`/`taxonomy_changes`
(`docs/taxonomy-tables.md`) — real tables with no writer yet, so a fresh install
returns an honestly empty/null response rather than a fabricated one.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaxonomyNodePayload(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    slug: str
    sort_order: int
    children: list[TaxonomyNodePayload] = []


class TaxonomyVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    status: str
    created_by: str
    parent_version_id: uuid.UUID | None
    created_at: datetime
    activated_at: datetime | None
    archived_at: datetime | None


class TaxonomyTreePayload(BaseModel):
    version_id: uuid.UUID
    version_number: int
    activated_at: datetime | None
    nodes: list[TaxonomyNodePayload]


class TaxonomyVersionDetail(TaxonomyVersionSummary):
    nodes: list[TaxonomyNodePayload]


class TaxonomyChangePayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    change_type: str
    source: str
    old_node_ids: list[str]
    new_node_ids: list[str]
    description: str
    created_at: datetime


class TaxonomyDiffPayload(BaseModel):
    version_id: uuid.UUID
    parent_version_id: uuid.UUID | None
    changes: list[TaxonomyChangePayload]
