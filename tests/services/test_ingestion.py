"""Ingestion runs: stop conditions, tallies, and what a failure leaves behind.

The adapter is a stub so these tests exercise the service's own decisions rather than
Google's API. The Google mapping is covered in `tests/integrations/`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Review, SyncRun
from reviewsignal_api.integrations.base import (
    NormalizedReview,
    ReviewPage,
    SourceFetchError,
)
from reviewsignal_api.services.ingestion import IngestionService

BASE = datetime.now(UTC)


def _review(
    source_review_id: str, updated_at: datetime, text: str | None = "Great"
) -> NormalizedReview:
    return NormalizedReview(
        source_review_id=source_review_id,
        rating=5,
        review_text=text,
        reviewer_name="Jane D.",
        created_at=updated_at,
        updated_at=updated_at,
        owner_reply_text=None,
        owner_reply_at=None,
        language="und",
        raw_payload={"reviewId": source_review_id},
    )


class _StubAdapter:
    """Yields prepared pages; raises instead of a page where a page is `None`."""

    source = "google"

    def __init__(self, pages: list[ReviewPage | None]) -> None:
        self._pages = pages
        self.calls = 0

    def fetch_page(self, cursor: str | None = None) -> ReviewPage:
        page = self._pages[self.calls]
        self.calls += 1
        if page is None:
            raise SourceFetchError("Google is unavailable.")
        return page


def _run(session: Session) -> SyncRun:
    run = session.execute(select(SyncRun).order_by(SyncRun.started_at.desc())).scalars().first()
    assert run is not None, "the service recorded no sync run"
    return run


def test_backfill_walks_every_page_and_records_success(session: Session) -> None:
    adapter = _StubAdapter(
        [
            ReviewPage(reviews=(_review("a", BASE), _review("b", BASE)), next_cursor="p2"),
            ReviewPage(reviews=(_review("c", BASE),), next_cursor=None),
        ]
    )

    outcome = IngestionService(session, adapter).backfill()

    assert adapter.calls == 2
    assert (outcome.created, outcome.updated, outcome.unchanged) == (3, 0, 0)
    run = _run(session)
    assert run.status == "success"
    assert run.reviews_created == 3
    assert run.finished_at is not None


def test_rerunning_a_backfill_over_identical_data_creates_nothing(session: Session) -> None:
    pages = [ReviewPage(reviews=(_review("a", BASE),), next_cursor=None)]
    IngestionService(session, _StubAdapter(list(pages))).backfill()

    outcome = IngestionService(session, _StubAdapter(list(pages))).backfill()

    assert (outcome.created, outcome.updated, outcome.unchanged) == (0, 0, 1)
    assert len(session.execute(select(Review)).scalars().all()) == 1


def test_unmappable_entries_are_counted_but_not_stored(session: Session) -> None:
    adapter = _StubAdapter(
        [ReviewPage(reviews=(_review("a", BASE),), next_cursor=None, unmappable_count=2)]
    )

    outcome = IngestionService(session, adapter).backfill()

    assert outcome.unmappable == 2
    # Fetched counts what the source returned, including what could not be stored.
    assert outcome.fetched == 3
    assert outcome.created == 1


def test_incremental_stops_at_the_previous_successful_watermark(session: Session) -> None:
    IngestionService(
        session,
        _StubAdapter(
            [ReviewPage(reviews=(_review("old", BASE - timedelta(days=2)),), next_cursor=None)]
        ),
    ).backfill()

    # Newest first: one changed review, then one untouched since the last run.
    adapter = _StubAdapter(
        [
            ReviewPage(
                reviews=(
                    _review("new", BASE + timedelta(days=1)),
                    _review("old", BASE - timedelta(days=2)),
                ),
                next_cursor="p2",
            ),
            ReviewPage(reviews=(_review("never-reached", BASE),), next_cursor=None),
        ]
    )

    outcome = IngestionService(session, adapter).incremental()

    assert adapter.calls == 1, "the walk continued past the watermark"
    assert outcome.created == 1
    assert (
        session.execute(
            select(Review).where(Review.source_review_id == "never-reached")
        ).scalar_one_or_none()
        is None
    )


def test_incremental_with_no_previous_run_walks_everything(session: Session) -> None:
    adapter = _StubAdapter(
        [ReviewPage(reviews=(_review("a", BASE - timedelta(days=400)),), next_cursor=None)]
    )

    outcome = IngestionService(session, adapter).incremental()

    assert outcome.created == 1


def test_failure_after_storing_records_a_partial_run_and_keeps_the_reviews(
    session: Session,
) -> None:
    adapter = _StubAdapter(
        [
            ReviewPage(reviews=(_review("a", BASE),), next_cursor="p2"),
            None,
        ]
    )

    with pytest.raises(SourceFetchError):
        IngestionService(session, adapter).backfill()

    run = _run(session)
    assert run.status == "partial"
    assert "SourceFetchError" in (run.error_message or "")
    assert run.finished_at is not None
    stored = session.execute(select(Review)).scalars().all()
    assert len(stored) == 1, "reviews committed before the failure must survive it"


def test_failure_before_storing_anything_records_a_failed_run(session: Session) -> None:
    with pytest.raises(SourceFetchError):
        IngestionService(session, _StubAdapter([None])).backfill()

    run = _run(session)
    assert run.status == "failed"
    assert run.reviews_created == 0


def test_a_failed_run_does_not_become_the_next_watermark(session: Session) -> None:
    """`last_successful` must ignore failures, or a failed sync would skip history."""
    with pytest.raises(SourceFetchError):
        IngestionService(session, _StubAdapter([None])).backfill()

    adapter = _StubAdapter(
        [ReviewPage(reviews=(_review("a", BASE - timedelta(days=365)),), next_cursor=None)]
    )
    outcome = IngestionService(session, adapter).incremental()

    assert outcome.created == 1, "an old review was skipped because a failed run set the watermark"
