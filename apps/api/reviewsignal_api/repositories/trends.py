"""Trend persistence reads for the dashboard (`docs/api-dashboard.md` §4).

Read-only: nothing writes `review_analyses`/`review_aspects` yet, since classification
is still blocked on Google Business Profile access (`docs/PRD.md` §11). The join below
is real against the documented schema (`docs/analysis-tables.md`); it simply has
nothing to return until that pipeline exists.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.db.models import Review as ReviewModel
from reviewsignal_api.db.models import ReviewAnalysis, ReviewAspect, TaxonomyNode


class TrendsReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def category_sentiment_counts(
        self,
        start_date: datetime,
        end_date: datetime,
        *,
        sentiment: str | None = None,
        category_id: uuid.UUID | None = None,
    ) -> Sequence[Row]:
        """Mention counts per taxonomy node and sentiment within a window.

        Joined through the *current* analysis only (`superseded_at IS NULL`):
        `data-model.md` §19 keeps history, but a trend counts each review once.
        """
        stmt = (
            select(
                TaxonomyNode.id.label("category_id"),
                TaxonomyNode.name.label("category_name"),
                ReviewAspect.sentiment.label("sentiment"),
                func.count().label("mention_count"),
            )
            .join(ReviewAnalysis, ReviewAspect.review_analysis_id == ReviewAnalysis.id)
            .join(ReviewModel, ReviewAnalysis.review_id == ReviewModel.id)
            .join(TaxonomyNode, ReviewAspect.taxonomy_node_id == TaxonomyNode.id)
            .where(
                ReviewAnalysis.superseded_at.is_(None),
                ReviewModel.created_at >= start_date,
                ReviewModel.created_at <= end_date,
            )
            .group_by(TaxonomyNode.id, TaxonomyNode.name, ReviewAspect.sentiment)
        )
        if sentiment is not None:
            stmt = stmt.where(ReviewAspect.sentiment == sentiment)
        if category_id is not None:
            stmt = stmt.where(TaxonomyNode.id == category_id)
        return (await self._session.execute(stmt)).all()
