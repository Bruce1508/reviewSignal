"""Taxonomy read orchestration (`docs/api-dashboard.md` §3)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.errors import ResourceNotFoundError
from reviewsignal_api.db.models import TaxonomyNode, TaxonomyVersion
from reviewsignal_api.repositories.taxonomy import TaxonomyReader
from reviewsignal_api.schemas.taxonomy import (
    TaxonomyChangePayload,
    TaxonomyDiffPayload,
    TaxonomyNodePayload,
    TaxonomyTreePayload,
    TaxonomyVersionDetail,
    TaxonomyVersionSummary,
)


def _build_tree(nodes: list[TaxonomyNode]) -> list[TaxonomyNodePayload]:
    """Flat, depth-ordered rows into a nested tree.

    The repository orders by `depth`, guaranteeing a node's parent is visited before
    it, so one pass attaches each node to its parent's payload without a second lookup.
    """
    by_id: dict[uuid.UUID, TaxonomyNodePayload] = {}
    roots: list[TaxonomyNodePayload] = []
    for node in nodes:
        payload = TaxonomyNodePayload(
            id=node.id,
            name=node.name,
            description=node.description,
            slug=node.slug,
            sort_order=node.sort_order,
            children=[],
        )
        by_id[node.id] = payload
        if node.parent_id is None or node.parent_id not in by_id:
            roots.append(payload)
        else:
            by_id[node.parent_id].children.append(payload)
    return roots


class TaxonomyService:
    def __init__(self, session: AsyncSession) -> None:
        self._taxonomy = TaxonomyReader(session)

    async def get_active_tree(self) -> TaxonomyTreePayload | None:
        version = await self._taxonomy.get_active_version()
        if version is None:
            return None
        nodes = await self._taxonomy.list_nodes(version.id)
        return TaxonomyTreePayload(
            version_id=version.id,
            version_number=version.version_number,
            activated_at=version.activated_at,
            nodes=_build_tree(list(nodes)),
        )

    async def list_versions(self) -> list[TaxonomyVersionSummary]:
        versions = await self._taxonomy.list_versions()
        return [TaxonomyVersionSummary.model_validate(v) for v in versions]

    async def get_version(self, version_id: uuid.UUID) -> TaxonomyVersionDetail:
        version = await self._require_version(version_id)
        nodes = await self._taxonomy.list_nodes(version_id)
        return TaxonomyVersionDetail(
            id=version.id,
            version_number=version.version_number,
            status=version.status,
            created_by=version.created_by,
            parent_version_id=version.parent_version_id,
            created_at=version.created_at,
            activated_at=version.activated_at,
            archived_at=version.archived_at,
            nodes=_build_tree(list(nodes)),
        )

    async def get_diff(self, version_id: uuid.UUID) -> TaxonomyDiffPayload:
        version = await self._require_version(version_id)
        changes = await self._taxonomy.list_changes(version_id)
        return TaxonomyDiffPayload(
            version_id=version.id,
            parent_version_id=version.parent_version_id,
            changes=[TaxonomyChangePayload.model_validate(c) for c in changes],
        )

    async def _require_version(self, version_id: uuid.UUID) -> TaxonomyVersion:
        version = await self._taxonomy.get_version(version_id)
        if version is None:
            raise ResourceNotFoundError("Taxonomy version not found.")
        return version
