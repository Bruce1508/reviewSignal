"""Contract tests for `/trends/*` (`docs/api-dashboard.md` §4)."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import (
    Review,
    ReviewAnalysis,
    ReviewAspect,
    TaxonomyNode,
    TaxonomyVersion,
)

NOW = datetime.now(UTC)


def _review(session: Session, *, rating: int, created_at: datetime, source_id: str) -> uuid.UUID:
    review = Review(
        source="stub",
        source_review_id=source_id,
        rating=rating,
        review_text="Fine.",
        created_at=created_at,
        updated_at=created_at,
        language="en",
        raw_payload={"synthetic": True},
        analysis_status="analyzed",
    )
    session.add(review)
    session.flush()
    return review.id


def _taxonomy(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    version = TaxonomyVersion(version_number=1, status="active", created_by="system")
    session.add(version)
    session.flush()
    node = TaxonomyNode(taxonomy_version_id=version.id, name="Wait Time", slug="wait-time")
    session.add(node)
    session.flush()
    return version.id, node.id


def _aspect(
    session: Session,
    *,
    review_id: uuid.UUID,
    taxonomy_version_id: uuid.UUID,
    node_id: uuid.UUID,
    sentiment: str,
    superseded: bool = False,
) -> None:
    analysis = ReviewAnalysis(
        review_id=review_id,
        taxonomy_version_id=taxonomy_version_id,
        classifier_type="llm",
        superseded_at=NOW if superseded else None,
    )
    session.add(analysis)
    session.flush()
    session.add(
        ReviewAspect(
            review_analysis_id=analysis.id,
            taxonomy_node_id=node_id,
            sentiment=sentiment,
            confidence=0.9,
            source="llm",
        )
    )


async def test_rating_trend_on_a_fresh_install_is_empty(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/trends/ratings")).json()["data"]

    assert body["points"] == []


async def test_rating_trend_defaults_to_a_thirty_day_window(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/trends/ratings")).json()["data"]

    start = datetime.fromisoformat(body["start_date"])
    end = datetime.fromisoformat(body["end_date"])
    assert (end - start) == timedelta(days=30)


async def test_rating_trend_buckets_reviews_by_day(client: AsyncClient, session: Session) -> None:
    day = (NOW - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    _review(session, rating=5, created_at=day, source_id="a")
    _review(session, rating=3, created_at=day.replace(hour=18), source_id="b")
    session.commit()

    body = (await client.get("/api/v1/trends/ratings")).json()["data"]

    assert len(body["points"]) == 1
    assert body["points"][0]["review_count"] == 2
    assert body["points"][0]["average_rating"] == 4.0


async def test_category_trends_on_a_fresh_install_is_empty(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/trends/categories")).json()["data"]

    assert body["categories"] == []


async def test_category_trends_counts_mentions_by_node_and_sentiment(
    client: AsyncClient, session: Session
) -> None:
    version_id, node_id = _taxonomy(session)
    review_a = _review(session, rating=2, created_at=NOW - timedelta(days=1), source_id="a")
    review_b = _review(session, rating=1, created_at=NOW - timedelta(days=1), source_id="b")
    _aspect(
        session,
        review_id=review_a,
        taxonomy_version_id=version_id,
        node_id=node_id,
        sentiment="negative",
    )
    _aspect(
        session,
        review_id=review_b,
        taxonomy_version_id=version_id,
        node_id=node_id,
        sentiment="negative",
    )
    session.commit()

    body = (await client.get("/api/v1/trends/categories")).json()["data"]

    assert len(body["categories"]) == 1
    assert body["categories"][0]["category_name"] == "Wait Time"
    assert body["categories"][0]["mention_count"] == 2


async def test_category_trends_excludes_superseded_analyses(
    client: AsyncClient, session: Session
) -> None:
    version_id, node_id = _taxonomy(session)
    review_id = _review(session, rating=1, created_at=NOW - timedelta(days=1), source_id="a")
    _aspect(
        session,
        review_id=review_id,
        taxonomy_version_id=version_id,
        node_id=node_id,
        sentiment="negative",
        superseded=True,
    )
    session.commit()

    body = (await client.get("/api/v1/trends/categories")).json()["data"]

    assert body["categories"] == []


async def test_category_trends_sentiment_filter_narrows_the_result(
    client: AsyncClient, session: Session
) -> None:
    version_id, node_id = _taxonomy(session)
    review_pos = _review(session, rating=5, created_at=NOW - timedelta(days=1), source_id="a")
    review_neg = _review(session, rating=1, created_at=NOW - timedelta(days=1), source_id="b")
    _aspect(
        session,
        review_id=review_pos,
        taxonomy_version_id=version_id,
        node_id=node_id,
        sentiment="positive",
    )
    _aspect(
        session,
        review_id=review_neg,
        taxonomy_version_id=version_id,
        node_id=node_id,
        sentiment="negative",
    )
    session.commit()

    body = (await client.get("/api/v1/trends/categories", params={"sentiment": "negative"})).json()[
        "data"
    ]

    assert len(body["categories"]) == 1
    assert body["categories"][0]["sentiment"] == "negative"


async def test_trends_summary_on_a_fresh_install_has_no_movements(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/trends/summary")).json()["data"]

    assert body["biggest_increases"] == []
    assert body["biggest_decreases"] == []


async def test_trends_summary_ranks_the_biggest_increase(
    client: AsyncClient, session: Session
) -> None:
    version_id, node_id = _taxonomy(session)
    # Two mentions in the current 7 days, none in the previous 7: a fresh increase.
    for i in range(2):
        review_id = _review(
            session, rating=1, created_at=NOW - timedelta(days=1), source_id=f"current-{i}"
        )
        _aspect(
            session,
            review_id=review_id,
            taxonomy_version_id=version_id,
            node_id=node_id,
            sentiment="negative",
        )
    session.commit()

    body = (await client.get("/api/v1/trends/summary")).json()["data"]

    assert len(body["biggest_increases"]) == 1
    increase = body["biggest_increases"][0]
    assert increase["category_name"] == "Wait Time"
    assert increase["current_count"] == 2
    assert increase["previous_count"] == 0
    assert increase["delta"] == 2
    assert body["biggest_decreases"] == []
