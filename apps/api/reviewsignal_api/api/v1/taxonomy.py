"""Taxonomy read routes (`docs/api-dashboard.md` §3).

Read-only: every mutation (`POST /taxonomy/rebuild`, node create/patch/merge/split/
delete, `POST /taxonomy/rollback/{version_id}`) stays out of this pass — there is no
taxonomy pipeline yet to drive them, and `docs/api-spec.md` §16.2 keeps long jobs
asynchronous regardless.
"""

import uuid

from fastapi import APIRouter

from reviewsignal_api.api.deps import SessionDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.taxonomy import (
    TaxonomyDiffPayload,
    TaxonomyTreePayload,
    TaxonomyVersionDetail,
    TaxonomyVersionSummary,
)
from reviewsignal_api.services.taxonomy import TaxonomyService

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("", response_model=ApiResponse[TaxonomyTreePayload | None])
async def get_active_taxonomy(session: SessionDep):
    return ApiResponse.ok(await TaxonomyService(session).get_active_tree())


@router.get("/versions", response_model=ApiResponse[list[TaxonomyVersionSummary]])
async def list_taxonomy_versions(session: SessionDep):
    return ApiResponse.ok(await TaxonomyService(session).list_versions())


@router.get("/versions/{version_id}", response_model=ApiResponse[TaxonomyVersionDetail])
async def get_taxonomy_version(version_id: uuid.UUID, session: SessionDep):
    return ApiResponse.ok(await TaxonomyService(session).get_version(version_id))


@router.get("/versions/{version_id}/diff", response_model=ApiResponse[TaxonomyDiffPayload])
async def get_taxonomy_diff(version_id: uuid.UUID, session: SessionDep):
    return ApiResponse.ok(await TaxonomyService(session).get_diff(version_id))
