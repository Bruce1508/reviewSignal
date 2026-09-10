"""Contract tests for `/insights/*` (`docs/api-dashboard.md` §5)."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Insight, InsightAction, TaxonomyNode, TaxonomyVersion

NOW = datetime.now(UTC)


def _insight(
    session: Session,
    *,
    title: str,
    status: str = "new",
    severity: str = "medium",
    taxonomy_node_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> uuid.UUID:
    insight = Insight(
        title=title,
        summary="Summary.",
        severity=severity,
        status=status,
        taxonomy_node_id=taxonomy_node_id,
    )
    session.add(insight)
    session.flush()
    if created_at is not None:
        insight.created_at = created_at
    return insight.id


def _node(session: Session) -> uuid.UUID:
    version = TaxonomyVersion(version_number=1, status="active", created_by="system")
    session.add(version)
    session.flush()
    node = TaxonomyNode(taxonomy_version_id=version.id, name="Wait Time", slug="wait-time")
    session.add(node)
    session.flush()
    return node.id


async def test_listing_insights_with_none_stored_returns_an_empty_list(
    client: AsyncClient,
) -> None:
    body = (await client.get("/api/v1/insights")).json()["data"]

    assert body == []


async def test_listing_returns_newest_first(client: AsyncClient, session: Session) -> None:
    _insight(session, title="Older", created_at=NOW - timedelta(days=2))
    _insight(session, title="Newer", created_at=NOW - timedelta(days=1))
    session.commit()

    body = (await client.get("/api/v1/insights")).json()["data"]

    assert [item["title"] for item in body] == ["Newer", "Older"]


async def test_status_filter_narrows_the_result(client: AsyncClient, session: Session) -> None:
    _insight(session, title="Active", status="new")
    _insight(session, title="Closed", status="resolved")
    session.commit()

    body = (await client.get("/api/v1/insights", params={"status": "resolved"})).json()["data"]

    assert [item["title"] for item in body] == ["Closed"]


async def test_category_filter_narrows_the_result(client: AsyncClient, session: Session) -> None:
    node_id = _node(session)
    _insight(session, title="Tagged", taxonomy_node_id=node_id)
    _insight(session, title="Untagged")
    session.commit()

    body = (await client.get("/api/v1/insights", params={"category_id": str(node_id)})).json()[
        "data"
    ]

    assert [item["title"] for item in body] == ["Tagged"]


async def test_invalid_status_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/insights", params={"status": "archived"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_get_insight_returns_metadata_actions_and_a_null_impact(
    client: AsyncClient, session: Session
) -> None:
    insight_id = _insight(session, title="Wait times climbing")
    session.add(
        InsightAction(
            insight_id=insight_id,
            action_text="Add extra coverage Friday evening.",
            note_text="Two-week trial.",
        )
    )
    session.commit()

    body = (await client.get(f"/api/v1/insights/{insight_id}")).json()["data"]

    assert body["title"] == "Wait times climbing"
    assert len(body["actions"]) == 1
    assert body["actions"][0]["action_text"] == "Add extra coverage Friday evening."
    assert body["impact"] is None
    assert body["related_review_ids"] == []


async def test_get_insight_missing_id_is_a_resource_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/insights/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
