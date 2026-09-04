"""Review persistence: idempotent upsert keyed on source_review_id (`docs/data-model.md` §4).

No business rules here beyond the change-detection needed to answer "was this a
create, an update, or a no-op" — repositories hold no business rules per house style,
but the caller needs that tri-state to fill `sync_runs.reviews_created/updated`.
"""

from enum import StrEnum

from sqlalchemy import select
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
