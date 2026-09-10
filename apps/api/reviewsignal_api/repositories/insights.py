"""Insight persistence reads for the dashboard (`docs/api-dashboard.md` §1, §5).

Read-only for now: nothing in this codebase writes `insights` yet, since insight
generation sits downstream of the classification pipeline that Google Business
Profile access is still blocking (`docs/PRD.md` §11). The query itself is real and
correct; it simply has nothing to return until that pipeline exists.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.db.models import Insight, InsightAction

# `data-model.md` §11 names "resolved" as the closed state; the other two are active.
_ACTIVE_STATUSES = ("new", "monitoring")


class InsightReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> Sequence[Insight]:
        stmt = (
            select(Insight)
            .where(Insight.status.in_(_ACTIVE_STATUSES))
            .order_by(Insight.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_filtered(
        self,
        *,
        status: str | None,
        severity: str | None,
        category_id: uuid.UUID | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> Sequence[Insight]:
        stmt = select(Insight).order_by(Insight.created_at.desc())
        if status is not None:
            stmt = stmt.where(Insight.status == status)
        if severity is not None:
            stmt = stmt.where(Insight.severity == severity)
        if category_id is not None:
            stmt = stmt.where(Insight.taxonomy_node_id == category_id)
        if start_date is not None:
            stmt = stmt.where(Insight.created_at >= start_date)
        if end_date is not None:
            stmt = stmt.where(Insight.created_at <= end_date)
        return (await self._session.execute(stmt)).scalars().all()

    async def get(self, insight_id: uuid.UUID) -> Insight | None:
        return await self._session.get(Insight, insight_id)

    async def list_actions(self, insight_id: uuid.UUID) -> Sequence[InsightAction]:
        stmt = (
            select(InsightAction)
            .where(InsightAction.insight_id == insight_id)
            .order_by(InsightAction.created_at)
        )
        return (await self._session.execute(stmt)).scalars().all()
