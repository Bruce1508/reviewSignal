"""Review persistence: idempotent upsert keyed on source_review_id (`docs/data-model.md` §4).

No business rules here beyond the change-detection needed to answer "was this a
create, an update, or a no-op" — repositories hold no business rules per house style,
but the caller needs that tri-state to fill `sync_runs.reviews_created/updated`.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Review
from reviewsignal_api.integrations.base import NormalizedReview


class UpsertOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, source: str, review: NormalizedReview) -> UpsertOutcome:
        existing = self._session.execute(
            select(Review).where(Review.source_review_id == review.source_review_id)
        ).scalar_one_or_none()

        if existing is None:
            self._session.add(
                Review(
                    source=source,
                    source_review_id=review.source_review_id,
                    rating=review.rating,
                    review_text=review.review_text,
                    reviewer_name=review.reviewer_name,
                    created_at=review.created_at,
                    updated_at=review.updated_at,
                    owner_reply_text=review.owner_reply_text,
                    owner_reply_at=review.owner_reply_at,
                    language=review.language,
                    raw_payload=review.raw_payload,
                    analysis_status="pending" if review.review_text is not None else "skipped",
                )
            )
            return UpsertOutcome.CREATED

        text_changed = existing.review_text != review.review_text
        reply_changed = (
            existing.owner_reply_text != review.owner_reply_text
            or existing.owner_reply_at != review.owner_reply_at
        )
        changed = (
            text_changed
            or reply_changed
            or existing.rating != review.rating
            or existing.updated_at != review.updated_at
            or existing.reviewer_name != review.reviewer_name
        )
        if not changed:
            return UpsertOutcome.UNCHANGED

        existing.rating = review.rating
        existing.review_text = review.review_text
        existing.owner_reply_text = review.owner_reply_text
        existing.owner_reply_at = review.owner_reply_at
        existing.updated_at = review.updated_at
        existing.reviewer_name = review.reviewer_name
        existing.raw_payload = review.raw_payload

        if text_changed:
            existing.analysis_status = "pending" if review.review_text is not None else "skipped"

        return UpsertOutcome.UPDATED

    def existing_source_ids(self, source: str) -> set[str]:
        rows = self._session.execute(
            select(Review.source_review_id).where(Review.source == source)
        ).scalars()
        return set(rows)


class ReviewReader:
    """Async read path for the API (`docs/api-dashboard.md` §2).

    The writer above is synchronous because it runs inside the RQ worker, while the API
    is async (`db/session.py`). Both live here because both are `reviews` persistence
    and neither carries a business rule.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        rating: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[Sequence[Review], int]:
        conditions = []
        if q:
            conditions.append(Review.review_text.ilike(f"%{q}%"))
        if rating is not None:
            conditions.append(Review.rating == rating)
        if start_date is not None:
            conditions.append(Review.created_at >= start_date)
        if end_date is not None:
            conditions.append(Review.created_at <= end_date)

        total_stmt = select(func.count()).select_from(Review)
        page_stmt = select(Review).order_by(Review.created_at.desc(), Review.id.desc())
        for condition in conditions:
            total_stmt = total_stmt.where(condition)
            page_stmt = page_stmt.where(condition)
        page_stmt = page_stmt.offset((page - 1) * page_size).limit(page_size)

        total = (await self._session.execute(total_stmt)).scalar_one()
        rows = (await self._session.execute(page_stmt)).scalars().all()
        return rows, total

    async def get(self, review_id: uuid.UUID) -> Review | None:
        return await self._session.get(Review, review_id)

    async def count_and_average(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[int, float | None]:
        stmt = select(func.count(), func.avg(Review.rating)).where(
            Review.created_at >= start_date, Review.created_at <= end_date
        )
        count, average = (await self._session.execute(stmt)).one()
        return count, float(average) if average is not None else None

    async def daily_trend(self, start_date: datetime, end_date: datetime) -> Sequence[Row]:
        """One row per day that had at least one review; no zero-filled gaps.

        A day with no reviews is not a measurement this query can distinguish from a
        day outside the range, so it is left out rather than fabricated as a zero.
        """
        day = func.date_trunc("day", Review.created_at)
        stmt = (
            select(
                day.label("day"),
                func.count().label("review_count"),
                func.avg(Review.rating).label("average_rating"),
            )
            .where(Review.created_at >= start_date, Review.created_at <= end_date)
            .group_by(day)
            .order_by(day)
        )
        return (await self._session.execute(stmt)).all()
