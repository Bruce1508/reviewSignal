"""Contract tests for `/reviews/*` (`docs/api-dashboard.md` §2)."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Review

BASE = datetime(2026, 9, 1, tzinfo=UTC)


def _review(
    session: Session,
    *,
    source_review_id: str,
    rating: int = 5,
    review_text: str | None = "Great service.",
    created_at: datetime = BASE,
) -> uuid.UUID:
    review = Review(
        source="stub",
        source_review_id=source_review_id,
        rating=rating,
        review_text=review_text,
        reviewer_name="Jane D.",
        created_at=created_at,
        updated_at=created_at,
        owner_reply_text=None,
        owner_reply_at=None,
        language="en",
        raw_payload={"synthetic": True},
        analysis_status="pending" if review_text is not None else "skipped",
    )
    session.add(review)
    session.flush()
    return review.id


async def test_listing_reviews_with_none_stored_returns_an_empty_page(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/reviews")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body == {"items": [], "page": 1, "page_size": 20, "total": 0}


async def test_listing_returns_newest_first_and_a_correct_total(
    client: AsyncClient, session: Session
) -> None:
    _review(session, source_review_id="a", created_at=BASE)
    _review(session, source_review_id="b", created_at=BASE + timedelta(days=1))
    session.commit()

    body = (await client.get("/api/v1/reviews")).json()["data"]

    assert body["total"] == 2
    assert [item["rating"] for item in body["items"]] == [5, 5]
    assert body["items"][0]["created_at"].startswith("2026-09-02")


async def test_page_size_limits_the_page_without_changing_the_total(
    client: AsyncClient, session: Session
) -> None:
    for i in range(3):
        _review(session, source_review_id=f"r{i}", created_at=BASE + timedelta(days=i))
    session.commit()

    body = (await client.get("/api/v1/reviews?page=1&page_size=2")).json()["data"]

    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_rating_filter_narrows_the_result(client: AsyncClient, session: Session) -> None:
    _review(session, source_review_id="low", rating=2)
    _review(session, source_review_id="high", rating=5)
    session.commit()

    body = (await client.get("/api/v1/reviews?rating=5")).json()["data"]

    assert body["total"] == 1
    assert body["items"][0]["rating"] == 5


async def test_q_filters_by_review_text(client: AsyncClient, session: Session) -> None:
    _review(session, source_review_id="match", review_text="Loved the framing job.")
    _review(session, source_review_id="nomatch", review_text="Fine overall.")
    session.commit()

    body = (await client.get("/api/v1/reviews?q=framing")).json()["data"]

    assert body["total"] == 1
    assert "framing" in body["items"][0]["review_text"]


async def test_an_invalid_rating_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/reviews?rating=6")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_start_date_after_end_date_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/reviews?start_date=2026-09-10T00:00:00Z&end_date=2026-09-01T00:00:00Z"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_get_review_returns_raw_metadata_and_a_null_analysis(
    client: AsyncClient, session: Session
) -> None:
    review_id = _review(session, source_review_id="x", review_text="Sharp prints.")
    session.commit()

    body = (await client.get(f"/api/v1/reviews/{review_id}")).json()["data"]

    assert body["review_text"] == "Sharp prints."
    assert body["source"] == "stub"
    assert body["analysis"] is None


async def test_get_review_missing_id_is_a_resource_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/reviews/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
