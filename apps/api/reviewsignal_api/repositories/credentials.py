"""Persistence for `source_credentials`. No business rules, no commits (`db/models.py`)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.db.models import SourceCredential


class CredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, source: str) -> SourceCredential | None:
        stmt = select(SourceCredential).where(SourceCredential.source == source)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert(
        self,
        source: str,
        *,
        refresh_token_encrypted: bytes,
        access_token_encrypted: bytes | None,
        token_expires_at: datetime | None,
        account_id: str | None,
        location_id: str | None,
        scopes: list[str],
    ) -> SourceCredential:
        credential = await self.get(source)
        if credential is None:
            credential = SourceCredential(source=source)
            self._session.add(credential)

        now = datetime.now(UTC)
        credential.status = "connected"
        credential.account_id = account_id
        credential.location_id = location_id
        credential.access_token_encrypted = access_token_encrypted
        credential.refresh_token_encrypted = refresh_token_encrypted
        credential.token_expires_at = token_expires_at
        credential.scopes = scopes
        credential.connected_at = now
        credential.updated_at = now
        await self._session.flush()
        return credential

    async def set_location(
        self, source: str, *, account_id: str, location_id: str
    ) -> SourceCredential | None:
        """Record which profile to ingest from. Tokens are deliberately untouched."""
        credential = await self.get(source)
        if credential is None:
            return None

        credential.account_id = account_id
        credential.location_id = location_id
        credential.updated_at = datetime.now(UTC)
        await self._session.flush()
        return credential

    async def mark_disconnected(self, source: str) -> None:
        credential = await self.get(source)
        if credential is None:
            return

        credential.status = "disconnected"
        # Disconnect must not leave ciphertext behind.
        credential.access_token_encrypted = None
        credential.refresh_token_encrypted = None
        credential.updated_at = datetime.now(UTC)
        await self._session.flush()
