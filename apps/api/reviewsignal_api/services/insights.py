"""Insight read orchestration (`docs/api-dashboard.md` §5)."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.errors import ResourceNotFoundError
from reviewsignal_api.repositories.insights import InsightReader
from reviewsignal_api.schemas.insights import InsightActionPayload, InsightDetail, InsightListItem


class InsightsService:
    def __init__(self, session: AsyncSession) -> None:
        self._insights = InsightReader(session)

    async def list_insights(
        self,
        *,
        status: str | None,
        severity: str | None,
        category_id: uuid.UUID | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[InsightListItem]:
        rows = await self._insights.list_filtered(
            status=status,
            severity=severity,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
        )
        return [InsightListItem.model_validate(row) for row in rows]

    async def get_insight(self, insight_id: uuid.UUID) -> InsightDetail:
        insight = await self._insights.get(insight_id)
        if insight is None:
            raise ResourceNotFoundError("Insight not found.")
        actions = await self._insights.list_actions(insight_id)
        return InsightDetail(
            id=insight.id,
            title=insight.title,
            summary=insight.summary,
            severity=insight.severity,
            evidence_summary=insight.evidence_summary,
            status=insight.status,
            created_at=insight.created_at,
            updated_at=insight.updated_at,
            resolved_at=insight.resolved_at,
            related_review_ids=[],
            actions=[InsightActionPayload.model_validate(action) for action in actions],
            impact=None,
        )
