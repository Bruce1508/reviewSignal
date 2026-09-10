"""Overview orchestration (`docs/api-dashboard.md` §1)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.errors import ValidationFailedError
from reviewsignal_api.repositories.insights import InsightReader
from reviewsignal_api.repositories.reviews import ReviewReader
from reviewsignal_api.schemas.overview import InsightSummary, OverviewPayload, RatingTrendPoint

DEFAULT_WINDOW = timedelta(days=7)


class OverviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._reviews = ReviewReader(session)
        self._insights = InsightReader(session)

    async def get_overview(
        self, start_date: datetime | None, end_date: datetime | None
    ) -> OverviewPayload:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValidationFailedError("start_date must not be after end_date.")

        resolved_end = end_date or datetime.now(UTC)
        resolved_start = start_date or (resolved_end - DEFAULT_WINDOW)

        review_count, average_rating = await self._reviews.count_and_average(
            resolved_start, resolved_end
        )
        trend_rows = await self._reviews.daily_trend(resolved_start, resolved_end)
        active_insights = await self._insights.list_active()

        return OverviewPayload(
            start_date=resolved_start,
            end_date=resolved_end,
            review_count=review_count,
            average_rating=round(average_rating, 2) if average_rating is not None else None,
            rating_trend=[
                RatingTrendPoint(
                    date=row.day.date(),
                    review_count=row.review_count,
                    average_rating=(
                        round(float(row.average_rating), 2)
                        if row.average_rating is not None
                        else None
                    ),
                )
                for row in trend_rows
            ],
            positive_themes=[],
            negative_themes=[],
            active_insights=[InsightSummary.model_validate(i) for i in active_insights],
        )
