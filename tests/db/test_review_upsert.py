"""Review upsert idempotency and change detection (`docs/PRD.md` §6.1)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Review
from reviewsignal_api.integrations.base import NormalizedReview
from reviewsignal_api.repositories.reviews import ReviewRepository, UpsertOutcome

SOURCE = "google"


def _review(**overrides) -> NormalizedReview:
    now = datetime.now(UTC)
    defaults = dict(
        source_review_id=f"src-{uuid.uuid4()}",
        rating=5,
        review_text="Great prints.",
        reviewer_name="Alex",
        created_at=now,
        updated_at=now,
        owner_reply_text=None,
        owner_reply_at=None,
        language="en",
        raw_payload={"raw": True},
    )
    return NormalizedReview(**{**defaults, **overrides})


def _stored(session: Session, source_review_id: str) -> Review:
    return session.execute(
        select(Review).where(Review.source_review_id == source_review_id)
    ).scalar_one()


def test_insert_new_review_returns_created_and_stores_row(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review()

    outcome = repo.upsert(SOURCE, review)
    session.flush()

    assert outcome is UpsertOutcome.CREATED
    stored = _stored(session, review.source_review_id)
    assert stored.rating == review.rating
    assert stored.review_text == review.review_text
    assert stored.analysis_status == "pending"


def test_rerunning_identical_review_returns_unchanged_and_writes_nothing(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review()
    repo.upsert(SOURCE, review)
    session.flush()

    outcome = repo.upsert(SOURCE, review)

    assert outcome is UpsertOutcome.UNCHANGED
    assert not session.dirty
    assert not session.new


def test_changed_review_text_returns_updated_and_resets_analysis_status(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review()
    repo.upsert(SOURCE, review)
    session.flush()

    stored = _stored(session, review.source_review_id)
    stored.analysis_status = "analyzed"
    session.flush()

    changed = _review(
        source_review_id=review.source_review_id,
        review_text="Actually, the prints faded.",
        updated_at=review.updated_at + timedelta(hours=1),
    )
    outcome = repo.upsert(SOURCE, changed)
    session.flush()

    assert outcome is UpsertOutcome.UPDATED
    stored = _stored(session, review.source_review_id)
    assert stored.review_text == "Actually, the prints faded."
    assert stored.analysis_status == "pending"


def test_changed_owner_reply_alone_returns_updated(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review()
    repo.upsert(SOURCE, review)
    session.flush()

    replied = _review(
        source_review_id=review.source_review_id,
        owner_reply_text="Thanks for the feedback!",
        owner_reply_at=datetime.now(UTC),
        updated_at=review.updated_at + timedelta(hours=1),
    )
    outcome = repo.upsert(SOURCE, replied)
    session.flush()

    assert outcome is UpsertOutcome.UPDATED
    stored = _stored(session, review.source_review_id)
    assert stored.owner_reply_text == "Thanks for the feedback!"


def test_changed_owner_reply_alone_does_not_reset_analysis_status(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review()
    repo.upsert(SOURCE, review)
    session.flush()

    stored = _stored(session, review.source_review_id)
    stored.analysis_status = "analyzed"
    session.flush()

    replied = _review(
        source_review_id=review.source_review_id,
        owner_reply_text="Thanks for the feedback!",
        owner_reply_at=datetime.now(UTC),
        updated_at=review.updated_at + timedelta(hours=1),
    )
    repo.upsert(SOURCE, replied)
    session.flush()

    stored = _stored(session, review.source_review_id)
    assert stored.analysis_status == "analyzed"


def test_rating_only_review_is_stored_as_skipped(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review(review_text=None)

    outcome = repo.upsert(SOURCE, review)
    session.flush()

    assert outcome is UpsertOutcome.CREATED
    stored = _stored(session, review.source_review_id)
    assert stored.analysis_status == "skipped"


def test_text_going_from_present_to_absent_sets_skipped(session: Session) -> None:
    repo = ReviewRepository(session)
    review = _review()
    repo.upsert(SOURCE, review)
    session.flush()

    stored = _stored(session, review.source_review_id)
    stored.analysis_status = "analyzed"
    session.flush()

    emptied = _review(
        source_review_id=review.source_review_id,
        review_text=None,
        updated_at=review.updated_at + timedelta(hours=1),
    )
    repo.upsert(SOURCE, emptied)
    session.flush()

    stored = _stored(session, review.source_review_id)
    assert stored.analysis_status == "skipped"


def test_two_different_source_review_ids_coexist(session: Session) -> None:
    repo = ReviewRepository(session)
    first, second = _review(), _review()

    repo.upsert(SOURCE, first)
    repo.upsert(SOURCE, second)
    session.flush()

    assert (
        _stored(session, first.source_review_id).id != _stored(session, second.source_review_id).id
    )


def test_existing_source_ids_returns_what_was_stored(session: Session) -> None:
    repo = ReviewRepository(session)
    first, second = _review(), _review()
    repo.upsert(SOURCE, first)
    repo.upsert(SOURCE, second)
    session.flush()

    ids = repo.existing_source_ids(SOURCE)

    assert ids == {first.source_review_id, second.source_review_id}
