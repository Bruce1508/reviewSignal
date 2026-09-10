"""Contract tests for `/overview` (`docs/api-dashboard.md` §1)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Insight, Review

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def _review(session: Session, *, rating: int, created_at: datetime, source_id: str) -> None:
    session.add(
        Review(
            source="stub",
            source_review_id=source_id,
            rating=rating,
            review_text="Fine.",
            created_at=created_at,
            updated_at=created_at,
            language="en",
            raw_payload={"synthetic": True},
            analysis_status="pending",
        )
    )


def _insight(session: Session, *, title: str, status: str) -> None:
    session.add(Insight(title=title, summary="Summary.", severity="medium", status=status))


async def test_overview_on_a_fresh_install_is_empty_but_valid(client: AsyncClient) -> None:
    response = await client.get("/api/v1/overview")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["review_count"] == 0
    assert body["average_rating"] is None
    assert body["rating_trend"] == []
    assert body["active_insights"] == []
    assert body["positive_themes"] == []
    assert body["negative_themes"] == []


async def test_default_window_is_the_last_seven_days(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/overview")).json()["data"]

    start = datetime.fromisoformat(body["start_date"])
    end = datetime.fromisoformat(body["end_date"])
    assert (end - start) == timedelta(days=7)


async def test_review_count_and_average_only_cover_the_requested_window(
    client: AsyncClient, session: Session
) -> None:
    _review(session, rating=5, created_at=NOW, source_id="in-range")
    _review(session, rating=1, created_at=NOW - timedelta(days=30), source_id="out-of-range")
    session.commit()

    body = (
        await client.get(
            "/api/v1/overview",
            params={
                "start_date": (NOW - timedelta(days=1)).isoformat(),
                "end_date": (NOW + timedelta(days=1)).isoformat(),
            },
        )
    ).json()["data"]

    assert body["review_count"] == 1
    assert body["average_rating"] == 5.0


async def test_rating_trend_buckets_by_day(client: AsyncClient, session: Session) -> None:
    day_one = NOW.replace(hour=1)
    day_one_later = NOW.replace(hour=20)
    day_two = NOW + timedelta(days=1)
    _review(session, rating=4, created_at=day_one, source_id="a")
    _review(session, rating=2, created_at=day_one_later, source_id="b")
    _review(session, rating=5, created_at=day_two, source_id="c")
    session.commit()

    body = (
        await client.get(
            "/api/v1/overview",
            params={
                "start_date": day_one.replace(hour=0).isoformat(),
                "end_date": (day_two + timedelta(days=1)).isoformat(),
            },
        )
    ).json()["data"]

    assert len(body["rating_trend"]) == 2
    assert body["rating_trend"][0]["review_count"] == 2
    assert body["rating_trend"][0]["average_rating"] == 3.0
    assert body["rating_trend"][1]["review_count"] == 1


async def test_active_insights_excludes_resolved(client: AsyncClient, session: Session) -> None:
    _insight(session, title="New signal", status="new")
    _insight(session, title="Watching", status="monitoring")
    _insight(session, title="Closed", status="resolved")
    session.commit()

    body = (await client.get("/api/v1/overview")).json()["data"]

    assert {i["title"] for i in body["active_insights"]} == {"New signal", "Watching"}


async def test_start_date_after_end_date_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/overview?start_date=2026-09-10T00:00:00Z&end_date=2026-09-01T00:00:00Z"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
