"""Contract tests for /health and /system/status (`docs/api-spec.md` §1, §2)."""

from httpx import AsyncClient


async def test_health_reports_all_components_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["status"] == "ok"
    assert body["data"]["components"] == {"api": "ok", "database": "ok", "redis": "ok"}


async def test_system_status_returns_documented_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert set(body["data"]) == {
        "last_sync",
        "queue_depth",
        "failed_jobs",
        "active_taxonomy",
        "active_model",
        "last_insight_at",
    }


async def test_system_status_is_empty_but_valid_on_a_fresh_install(client: AsyncClient) -> None:
    data = (await client.get("/api/v1/system/status")).json()["data"]

    assert data["last_sync"] is None
    assert data["active_taxonomy"] is None
    assert data["last_insight_at"] is None
    assert data["failed_jobs"] == 0


async def test_unknown_route_uses_the_failure_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
