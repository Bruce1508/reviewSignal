"""The ingest handlers' account/location precondition (`docs/PRD.md` §6.1).

`_ingest` refuses to run until a location has been selected, because without both ids
there is no reviews URL to call. These tests pin both halves of that guard: that it
still refuses when the selection is missing, and that selecting one actually releases
it — the reason `/google/location` exists.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reviewsignal_api.core.crypto import encrypt
from reviewsignal_api.db.models import SourceCredential
from reviewsignal_api.integrations.base import SourceNotConnectedError
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.jobs import ingest


def _insert_credential(account_id: str | None, location_id: str | None) -> None:
    with session_scope() as session:
        session.add(
            SourceCredential(
                source="google",
                status="connected",
                account_id=account_id,
                location_id=location_id,
                refresh_token_encrypted=encrypt("fake-refresh-token"),
                connected_at=datetime.now(UTC),
            )
        )


@dataclass
class _Outcome:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    unmappable: int = 0


class _StubIngestionService:
    """Replaces the real pipeline; these tests are about the guard, not ingestion."""

    ran: list[str] = []

    def __init__(self, session, adapter) -> None:
        self.adapter = adapter

    def backfill(self) -> _Outcome:
        type(self).ran.append("backfill")
        return _Outcome()

    def incremental(self) -> _Outcome:
        type(self).ran.append("incremental")
        return _Outcome()


@pytest.fixture
def stubbed_ingest(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stub everything past the guard: no token refresh and no Google traffic."""
    captured: dict = {}
    _StubIngestionService.ran = []

    class _RecordingClient:
        def __init__(self, access_token: str, account_id: str, location_id: str) -> None:
            captured["access_token"] = access_token
            captured["account_id"] = account_id
            captured["location_id"] = location_id

    monkeypatch.setattr(ingest, "GoogleReviewsClient", _RecordingClient)
    monkeypatch.setattr(ingest, "IngestionService", _StubIngestionService)
    monkeypatch.setattr(ingest, "resolve_access_token", lambda session, cred: "stub-access-token")
    captured["ran"] = _StubIngestionService.ran
    return captured


@pytest.mark.parametrize(
    ("account_id", "location_id"),
    [(None, None), ("111", None), (None, "222")],
)
def test_ingest_refuses_when_no_location_is_selected(
    account_id: str | None, location_id: str | None, stubbed_ingest: dict
) -> None:
    _insert_credential(account_id, location_id)

    with pytest.raises(SourceNotConnectedError, match="account/location"):
        ingest.google_backfill({})

    assert stubbed_ingest["ran"] == [], "ingestion started without a target location"


def test_backfill_runs_once_a_location_is_selected(stubbed_ingest: dict) -> None:
    _insert_credential("111", "222")

    ingest.google_backfill({})

    assert stubbed_ingest["ran"] == ["backfill"]
    assert stubbed_ingest["account_id"] == "111"
    assert stubbed_ingest["location_id"] == "222"


def test_sync_runs_once_a_location_is_selected(stubbed_ingest: dict) -> None:
    _insert_credential("111", "222")

    ingest.google_sync({})

    assert stubbed_ingest["ran"] == ["incremental"]
