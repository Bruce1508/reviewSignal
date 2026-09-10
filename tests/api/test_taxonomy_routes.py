"""Contract tests for `/taxonomy/*` (`docs/api-dashboard.md` §3)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import TaxonomyChange, TaxonomyNode, TaxonomyVersion


def _version(
    session: Session,
    *,
    version_number: int,
    status: str,
    parent_version_id: uuid.UUID | None = None,
) -> uuid.UUID:
    version = TaxonomyVersion(
        version_number=version_number,
        status=status,
        created_by="system",
        parent_version_id=parent_version_id,
    )
    session.add(version)
    session.flush()
    return version.id


def _node(
    session: Session,
    *,
    version_id: uuid.UUID,
    name: str,
    slug: str,
    parent_id: uuid.UUID | None = None,
    depth: int = 0,
    sort_order: int = 0,
) -> uuid.UUID:
    node = TaxonomyNode(
        taxonomy_version_id=version_id,
        parent_id=parent_id,
        name=name,
        slug=slug,
        depth=depth,
        sort_order=sort_order,
    )
    session.add(node)
    session.flush()
    return node.id


async def test_active_taxonomy_on_a_fresh_install_is_null_not_an_error(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/taxonomy")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"] is None


async def test_active_taxonomy_returns_a_nested_tree(client: AsyncClient, session: Session) -> None:
    version_id = _version(session, version_number=1, status="active")
    parent_id = _node(session, version_id=version_id, name="Service", slug="service", depth=0)
    _node(
        session,
        version_id=version_id,
        name="Wait Time",
        slug="wait-time",
        parent_id=parent_id,
        depth=1,
    )
    session.commit()

    body = (await client.get("/api/v1/taxonomy")).json()["data"]

    assert body["version_number"] == 1
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["name"] == "Service"
    assert [c["name"] for c in body["nodes"][0]["children"]] == ["Wait Time"]


async def test_versions_are_listed_newest_first(client: AsyncClient, session: Session) -> None:
    _version(session, version_number=1, status="archived")
    _version(session, version_number=2, status="active")
    session.commit()

    body = (await client.get("/api/v1/taxonomy/versions")).json()["data"]

    assert [v["version_number"] for v in body] == [2, 1]


async def test_get_version_returns_its_own_nodes(client: AsyncClient, session: Session) -> None:
    version_id = _version(session, version_number=1, status="archived")
    _node(session, version_id=version_id, name="Pricing", slug="pricing")
    session.commit()

    body = (await client.get(f"/api/v1/taxonomy/versions/{version_id}")).json()["data"]

    assert body["version_number"] == 1
    assert [n["name"] for n in body["nodes"]] == ["Pricing"]


async def test_get_version_missing_id_is_a_resource_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/taxonomy/versions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_diff_returns_only_changes_landing_on_that_version(
    client: AsyncClient, session: Session
) -> None:
    parent_id = _version(session, version_number=1, status="archived")
    child_id = _version(session, version_number=2, status="active", parent_version_id=parent_id)
    session.add(
        TaxonomyChange(
            from_version_id=parent_id,
            to_version_id=child_id,
            change_type="rename",
            source="manual",
            description="Renamed Service to Staff Experience.",
        )
    )
    # A change landing on a different version must not leak into this diff.
    other_id = _version(session, version_number=3, status="candidate")
    session.add(
        TaxonomyChange(
            from_version_id=child_id,
            to_version_id=other_id,
            change_type="add",
            source="automatic",
            description="Unrelated change.",
        )
    )
    session.commit()

    body = (await client.get(f"/api/v1/taxonomy/versions/{child_id}/diff")).json()["data"]

    assert body["parent_version_id"] == str(parent_id)
    assert len(body["changes"]) == 1
    assert body["changes"][0]["change_type"] == "rename"


async def test_diff_missing_version_is_a_resource_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/taxonomy/versions/{uuid.uuid4()}/diff")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
