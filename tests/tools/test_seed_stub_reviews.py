"""Unit tests for the stub-adapter corpus seeder.

`build_reviews` takes an explicit `now` so determinism can be asserted without racing
the real clock; `seed_stub_reviews.py` itself always defaults to the real clock.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from tools.seed_stub_reviews import StubReviewSourceAdapter, build_reviews

from reviewsignal_api.db.models import Review, SyncRun
from reviewsignal_api.services.ingestion import IngestionService

FIXED_NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def test_build_reviews_is_deterministic_for_the_same_seed_and_clock() -> None:
    first = build_reviews(50, seed=7, now=FIXED_NOW)
    second = build_reviews(50, seed=7, now=FIXED_NOW)

    assert [r.source_review_id for r in first] == [r.source_review_id for r in second]
    assert [r.rating for r in first] == [r.rating for r in second]
    assert [r.review_text for r in first] == [r.review_text for r in second]
    assert [r.created_at for r in first] == [r.created_at for r in second]


def test_build_reviews_shape_and_ordering() -> None:
    reviews = build_reviews(80, seed=1, now=FIXED_NOW)

    assert len(reviews) == 80
    assert {r.source_review_id for r in reviews} == {f"stub-{i:04d}" for i in range(80)}
    assert all(1 <= r.rating <= 5 for r in reviews)
    assert all(r.created_at <= FIXED_NOW for r in reviews)
    assert all(r.language == "en" for r in reviews)
    # Newest-first: IngestionService._absorb assumes this ordering for its watermark.
    assert all(a.created_at >= b.created_at for a, b in zip(reviews, reviews[1:], strict=False))
    # Rating alone with no text must still stay analyzable-but-empty, never a lie about
    # a comment that was never written.
    assert any(r.review_text is None for r in reviews)


def test_seeding_through_ingestion_service_uses_a_distinct_source(session) -> None:
    reviews = build_reviews(30, seed=3, now=FIXED_NOW)
    adapter = StubReviewSourceAdapter(reviews, page_size=10)

    outcome = IngestionService(session, adapter).backfill()

    assert outcome.created == 30
    stored = session.execute(select(Review)).scalars().all()
    assert {r.source for r in stored} == {"stub"}
    run = session.execute(select(SyncRun)).scalars().one()
    assert run.source == "stub", "must never share the 'google' incremental watermark"


def test_rerunning_the_seed_with_the_same_seed_and_clock_is_idempotent(session) -> None:
    def run_once():
        reviews = build_reviews(30, seed=3, now=FIXED_NOW)
        adapter = StubReviewSourceAdapter(reviews, page_size=10)
        return IngestionService(session, adapter).backfill()

    first = run_once()
    second = run_once()

    assert (first.created, first.updated) == (30, 0)
    assert (second.created, second.updated, second.unchanged) == (0, 0, 30)
    assert len(session.execute(select(Review)).scalars().all()) == 30
