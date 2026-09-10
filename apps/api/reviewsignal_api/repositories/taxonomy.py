"""Taxonomy persistence reads for the dashboard (`docs/api-dashboard.md` §3).

Read-only: nothing writes `taxonomy_versions`/`taxonomy_nodes`/`taxonomy_changes` yet,
since taxonomy generation is part of the classification pipeline that Google Business
Profile access is still blocking (`docs/PRD.md` §11). These queries are real and
correct against a real, documented schema (`docs/taxonomy-tables.md`); they simply
have nothing to return until that pipeline exists.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.db.models import TaxonomyChange, TaxonomyNode, TaxonomyVersion


class TaxonomyReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_version(self) -> TaxonomyVersion | None:
        stmt = select(TaxonomyVersion).where(TaxonomyVersion.status == "active")
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_version(self, version_id: uuid.UUID) -> TaxonomyVersion | None:
        return await self._session.get(TaxonomyVersion, version_id)

    async def list_versions(self) -> Sequence[TaxonomyVersion]:
        stmt = select(TaxonomyVersion).order_by(TaxonomyVersion.version_number.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def list_nodes(self, version_id: uuid.UUID) -> Sequence[TaxonomyNode]:
        # `depth` first: the tree builder relies on a parent always being visited
        # before its children in a single pass.
        stmt = (
            select(TaxonomyNode)
            .where(TaxonomyNode.taxonomy_version_id == version_id)
            .order_by(TaxonomyNode.depth, TaxonomyNode.sort_order)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_changes(self, to_version_id: uuid.UUID) -> Sequence[TaxonomyChange]:
        stmt = (
            select(TaxonomyChange)
            .where(TaxonomyChange.to_version_id == to_version_id)
            .order_by(TaxonomyChange.created_at)
        )
        return (await self._session.execute(stmt)).scalars().all()
