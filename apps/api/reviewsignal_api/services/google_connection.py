"""Google OAuth connection lifecycle (`docs/api-spec.md` §8).

Account/location discovery is out of scope here — `account_id`/`location_id` are
persisted as whatever the token response carries (currently nothing), and a later
step wires them up.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.config import Settings
from reviewsignal_api.core.crypto import encrypt
from reviewsignal_api.core.errors import GoogleApiError, GoogleNotConnectedError
from reviewsignal_api.repositories.credentials import CredentialRepository
from reviewsignal_api.repositories.system import SystemRepository
from reviewsignal_api.schemas.google import GoogleStatusPayload

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/business.manage"


class GoogleConnectionService:
    SOURCE = "google"

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._credentials = CredentialRepository(session)

    async def status(self) -> GoogleStatusPayload:
        credential = await self._credentials.get(self.SOURCE)
        sync_run = await SystemRepository(self._session).latest_sync_run()
        last_sync = sync_run.started_at if sync_run is not None else None

        if credential is None:
            return GoogleStatusPayload(
                connected=False,
                status="disconnected",
                account_id=None,
                location_id=None,
                connected_at=None,
                last_sync=last_sync,
            )

        return GoogleStatusPayload(
            connected=credential.status == "connected",
            status=credential.status,
            account_id=credential.account_id,
            location_id=credential.location_id,
            connected_at=credential.connected_at,
            last_sync=last_sync,
        )

    def authorization_url(self, state: str) -> str:
        if not self._settings.google_client_id or not self._settings.google_redirect_uri:
            raise GoogleNotConnectedError(
                "GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI are not configured; set the "
                "Google OAuth environment variables before connecting."
            )
        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self._settings.google_redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTHORIZATION_URL}?{urlencode(params)}"

    async def complete(self, code: str) -> None:
        data = {
            "code": code,
            "client_id": self._settings.google_client_id,
            "client_secret": self._settings.google_client_secret,
            "redirect_uri": self._settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(TOKEN_URL, data=data)
        except httpx.HTTPError as exc:
            raise GoogleApiError(f"Could not reach Google's OAuth token endpoint: {exc}") from exc

        if not 200 <= response.status_code < 300:
            raise GoogleApiError(
                f"Google token exchange failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            # A real, common failure: without access_type=offline+prompt=consent (or a
            # prior grant already on file), Google omits the refresh token. Storing the
            # credential anyway would leave a connected-looking row nothing can use.
            raise GoogleApiError(
                "Google did not grant offline access (no refresh_token in the response); "
                "reconnect and approve offline access."
            )

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        token_expires_at = (
            datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in is not None else None
        )
        scope_string = payload.get("scope", "")
        scopes = scope_string.split() if scope_string else []

        await self._credentials.upsert(
            self.SOURCE,
            refresh_token_encrypted=encrypt(refresh_token),
            access_token_encrypted=encrypt(access_token) if access_token else None,
            token_expires_at=token_expires_at,
            account_id=None,
            location_id=None,
            scopes=scopes,
        )
        await self._session.commit()

    async def disconnect(self) -> None:
        await self._credentials.mark_disconnected(self.SOURCE)
        await self._session.commit()

    async def ensure_connected(self) -> None:
        """Guard for the job-enqueue routes: queuing a sync with no credential would
        just produce a guaranteed dead-letter job.
        """
        credential = await self._credentials.get(self.SOURCE)
        if credential is None or credential.status != "connected":
            raise GoogleNotConnectedError("Google is not connected; connect it before syncing.")
