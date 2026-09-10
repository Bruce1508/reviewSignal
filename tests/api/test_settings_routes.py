"""Contract tests for `GET /settings` (`docs/api-dashboard.md` §6)."""

from httpx import AsyncClient
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Setting


async def test_settings_on_a_fresh_install_has_null_runtime_fields(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/settings")).json()["data"]

    assert body["default_date_range_days"] is None
    assert body["daily_sync_time"] is None
    assert body["classification_threshold"] is None
    assert isinstance(body["active_model"], str) and body["active_model"]
    assert isinstance(body["embedding_model"], str) and body["embedding_model"]


async def test_settings_reflects_stored_runtime_values(
    client: AsyncClient, session: Session
) -> None:
    session.add(Setting(key="default_date_range_days", value={"days": 14}))
    session.add(Setting(key="daily_sync_time", value={"time": "02:00"}))
    session.add(Setting(key="classification_threshold", value={"threshold": 0.6}))
    session.commit()

    body = (await client.get("/api/v1/settings")).json()["data"]

    assert body["default_date_range_days"] == 14
    assert body["daily_sync_time"] == "02:00"
    assert body["classification_threshold"] == 0.6
