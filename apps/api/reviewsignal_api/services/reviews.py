"""Review list/detail orchestration (`docs/api-dashboard.md` §2)."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.errors import ResourceNotFoundError, ValidationFailedError
from reviewsignal_api.repositories.reviews import ReviewReader
from reviewsignal_api.schemas.reviews import ReviewDetail, ReviewListPayload, ReviewSummary


class ReviewsService:
    def __init__(self, session: AsyncSession) -> None:
        self._reviews = ReviewReader(session)

    async def list_reviews(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None,
        rating: int | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> ReviewListPayload:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValidationFailedError("start_date must not be after end_date.")

        rows, total = await self._reviews.list_page(
            page=page,
            page_size=page_size,
            q=q,
            rating=rating,
            start_date=start_date,
            end_date=end_date,
        )
        return ReviewListPayload(
            items=[ReviewSummary.model_validate(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def get_review(self, review_id: uuid.UUID) -> ReviewDetail:
        review = await self._reviews.get(review_id)
        if review is None:
            raise ResourceNotFoundError("Review not found.")
        return ReviewDetail.model_validate(review)
