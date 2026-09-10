"""Trends orchestration (`docs/api-dashboard.md` §4)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.repositories.reviews import ReviewReader
from reviewsignal_api.repositories.trends import TrendsReader
from reviewsignal_api.schemas.trends import (
    CategoryMovement,
    CategoryTrendPoint,
    CategoryTrendsPayload,
    RatingHistoryPayload,
    RatingHistoryPoint,
    TrendsSummaryPayload,
)

RATINGS_WINDOW = timedelta(days=30)
CATEGORIES_WINDOW = timedelta(days=30)
SUMMARY_WINDOW = timedelta(days=7)
TOP_N = 5


class TrendsService:
    def __init__(self, session: AsyncSession) -> None:
        self._reviews = ReviewReader(session)
        self._trends = TrendsReader(session)

    async def get_ratings(
        self, start_date: datetime | None, end_date: datetime | None
    ) -> RatingHistoryPayload:
        resolved_end = end_date or datetime.now(UTC)
        resolved_start = start_date or (resolved_end - RATINGS_WINDOW)
        rows = await self._reviews.daily_trend(resolved_start, resolved_end)
        return RatingHistoryPayload(
            start_date=resolved_start,
            end_date=resolved_end,
            points=[
                RatingHistoryPoint(
                    date=row.day.date(),
                    review_count=row.review_count,
                    average_rating=(
                        round(float(row.average_rating), 2)
                        if row.average_rating is not None
                        else None
                    ),
                )
                for row in rows
            ],
        )

    async def get_categories(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        *,
        sentiment: str | None,
        category_id: uuid.UUID | None,
    ) -> CategoryTrendsPayload:
        resolved_end = end_date or datetime.now(UTC)
        resolved_start = start_date or (resolved_end - CATEGORIES_WINDOW)
        rows = await self._trends.category_sentiment_counts(
            resolved_start, resolved_end, sentiment=sentiment, category_id=category_id
        )
        return CategoryTrendsPayload(
            start_date=resolved_start,
            end_date=resolved_end,
            categories=[
                CategoryTrendPoint(
                    category_id=row.category_id,
                    category_name=row.category_name,
                    sentiment=row.sentiment,
                    mention_count=row.mention_count,
                )
                for row in rows
            ],
        )

    async def get_summary(self) -> TrendsSummaryPayload:
        """Biggest positive/negative movements, current 7 days vs the 7 before it.

        A category present in only one period still moves: it either appeared from
        nothing or vanished entirely, and both are real movements, not gaps.
        """
        current_end = datetime.now(UTC)
        current_start = current_end - SUMMARY_WINDOW
        previous_end = current_start
        previous_start = previous_end - SUMMARY_WINDOW

        current_rows = await self._trends.category_sentiment_counts(current_start, current_end)
        previous_rows = await self._trends.category_sentiment_counts(previous_start, previous_end)

        current = {(row.category_id, row.sentiment): row for row in current_rows}
        previous = {(row.category_id, row.sentiment): row for row in previous_rows}

        movements = []
        for key in current.keys() | previous.keys():
            current_row = current.get(key)
            previous_row = previous.get(key)
            reference = current_row or previous_row
            assert reference is not None  # `key` came from one of these two dicts.
            current_count = current_row.mention_count if current_row else 0
            previous_count = previous_row.mention_count if previous_row else 0
            movements.append(
                CategoryMovement(
                    category_id=reference.category_id,
                    category_name=reference.category_name,
                    sentiment=reference.sentiment,
                    current_count=current_count,
                    previous_count=previous_count,
                    delta=current_count - previous_count,
                )
            )

        increases = sorted(
            (m for m in movements if m.delta > 0), key=lambda m: m.delta, reverse=True
        )[:TOP_N]
        decreases = sorted((m for m in movements if m.delta < 0), key=lambda m: m.delta)[:TOP_N]

        return TrendsSummaryPayload(
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
            biggest_increases=increases,
            biggest_decreases=decreases,
        )
