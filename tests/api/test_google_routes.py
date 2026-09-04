"""Contract tests for `/google/*` (`docs/api-spec.md` §8, §12, §16.5)."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from reviewsignal_api.core.crypto import encrypt
from reviewsignal_api.db.models import SourceCredential
from reviewsignal_api.services.google_connection import GoogleConnectionService
from reviewsignal_worker.db import session_scope

FAKE_REFRESH_TOKEN = "fake-refresh-token"


def _insert_connected_credential() -> bytes:
    """Insert a connected `google` credential directly, bypassing the OAuth flow."""
    ciphertext = encrypt(FAKE_REFRESH_TOKEN)
    with session_scope() as session:
        session.add(
            SourceCredential(
                source="google",
                status="connected",
                refresh_token_encrypted=ciphertext,
                connected_at=datetime.now(UTC),
            )
        )
    return ciphertext


async def test_status_with_no_credential_reports_disconnected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/google/status")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert data["connected"] is False
    assert data["status"] == "disconnected"
    assert data["account_id"] is None
    assert data["location_id"] is None
    assert not any("token" in key.lower() for key in data)


async def test_status_with_connected_credential_never_returns_the_token(
    client: AsyncClient,
) -> None:
    ciphertext = _insert_connected_credential()

    response = await client.get("/api/v1/google/status")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["connected"] is True
    assert data["status"] == "connected"
    assert not any("token" in key.lower() for key in data)

    # The single most important assertion in this file (`docs/api-spec.md` §16.5):
    # neither the plaintext nor the ciphertext of the token may appear anywhere in
    # the serialized response.
    raw = response.text
    assert FAKE_REFRESH_TOKEN not in raw
    assert ciphertext.decode() not in raw


async def test_backfill_without_credential_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/google/backfill")

    assert response.status_code == 409
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "GOOGLE_NOT_CONNECTED"


async def test_sync_without_credential_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/google/sync")

    assert response.status_code == 409
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "GOOGLE_NOT_CONNECTED"


async def test_backfill_with_connected_credential_enqueues_a_job(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert_connected_credential()
    fake_job_id = uuid.uuid4()
    captured: dict = {}

    def fake_enqueue(job_type: str, payload: dict | None, max_attempts: int) -> uuid.UUID:
        captured["job_type"] = job_type
        captured["payload"] = payload
        captured["max_attempts"] = max_attempts
        return fake_job_id

    monkeypatch.setattr("reviewsignal_api.api.v1.google.enqueue", fake_enqueue)

    response = await client.post("/api/v1/google/backfill")

    assert response.status_code == 202
    body = response.json()
    assert body["error"] is None
    assert body["data"] == {
        "job_id": str(fake_job_id),
        "status": "queued",
        "job_type": "google_backfill",
    }
    assert captured["job_type"] == "google_backfill"


async def test_connect_with_no_client_id_is_rejected(client: AsyncClient) -> None:
    # The local .env ships an empty GOOGLE_CLIENT_ID, so no monkeypatching is needed
    # for this to be true in the test environment.
    response = await client.get("/api/v1/google/connect", follow_redirects=False)

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "GOOGLE_NOT_CONNECTED"


async def test_disconnect_clears_tokens_and_marks_disconnected(client: AsyncClient) -> None:
    _insert_connected_credential()

    response = await client.post("/api/v1/google/disconnect")

    assert response.status_code == 200
    assert response.json()["error"] is None

    with session_scope() as session:
        row = session.execute(
            text(
                "SELECT status, access_token_encrypted, refresh_token_encrypted "
                "FROM source_credentials WHERE source = 'google'"
            )
        ).one()
    assert row.status == "disconnected"
    assert row.access_token_encrypted is None
    assert row.refresh_token_encrypted is None


async def test_connect_binds_the_oauth_state_to_the_browser(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        GoogleConnectionService, "authorization_url", lambda self, state: f"https://x/?s={state}"
    )

    response = await client.get("/api/v1/google/connect")

    cookie = response.cookies.get("rs_google_oauth_state")
    assert cookie, "no state cookie was set, so the callback has nothing to verify against"
    assert cookie in response.headers["location"], "cookie and redirect state disagree"


async def test_callback_without_the_state_cookie_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forged callback from another site carries no cookie and must not connect."""
    completed: list[str] = []

    async def _never(self, code: str) -> None:
        completed.append(code)

    monkeypatch.setattr(GoogleConnectionService, "complete", _never)

    response = await client.get("/api/v1/google/callback?code=abc&state=forged")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert completed == [], "the token exchange ran despite an unverified state"


async def test_callback_with_a_mismatched_state_cookie_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _never(self, code: str) -> None:
        raise AssertionError("the token exchange must not run")

    monkeypatch.setattr(GoogleConnectionService, "complete", _never)
    client.cookies.set("rs_google_oauth_state", "the-real-state")

    response = await client.get("/api/v1/google/callback?code=abc&state=a-different-state")
    client.cookies.clear()

    assert response.status_code == 400


async def test_callback_with_a_matching_state_cookie_completes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed: list[str] = []

    async def _complete(self, code: str) -> None:
        completed.append(code)

    monkeypatch.setattr(GoogleConnectionService, "complete", _complete)
    client.cookies.set("rs_google_oauth_state", "matching-state")

    response = await client.get("/api/v1/google/callback?code=abc&state=matching-state")
    client.cookies.clear()

    assert response.status_code == 200
    assert response.json()["data"] == {"connected": True}
    assert completed == ["abc"]
