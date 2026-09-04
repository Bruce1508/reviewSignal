"""Google connection lifecycle (`docs/api-spec.md` §8).

Connecting is two steps, not one: OAuth grants access to a *user*, but reviews are
fetched per location, so the callback cannot know which profile to ingest. `complete`
stores the grant and `select_location` records the choice made from `list_accounts` /
`list_locations`. Until both ids are set, `jobs/ingest.py` refuses to run.

Discovery is synchronous under the hood so it reuses the worker's token refresh
unchanged; it is called through a threadpool to keep the event loop free.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from reviewsignal_api.core.config import Settings
from reviewsignal_api.core.crypto import encrypt
from reviewsignal_api.core.errors import GoogleApiError, GoogleNotConnectedError
from reviewsignal_api.integrations.base import SourceFetchError, SourceNotConnectedError
from reviewsignal_api.integrations.google.profile import (
    DiscoveredAccount,
    DiscoveredLocation,
    GoogleProfileClient,
)
from reviewsignal_api.repositories.credentials import CredentialRepository
from reviewsignal_api.repositories.system import SystemRepository
from reviewsignal_api.schemas.google import (
    GoogleAccountPayload,
    GoogleLocationPayload,
    GoogleStatusPayload,
)
from reviewsignal_api.services.google_token import load_credential, resolve_access_token
from reviewsignal_worker.db import session_scope

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/business.manage"


def _access_token() -> str:
    """Resolve a usable access token, refreshing it if needed.

    The session closes before the caller makes its network call, so a slow Google
    request never holds a database connection open.
    """
    with session_scope() as session:
        source = GoogleConnectionService.SOURCE
        return resolve_access_token(session, load_credential(session, source))


def _fetch_accounts() -> list[DiscoveredAccount]:
    with GoogleProfileClient(_access_token()) as profile:
        return profile.list_accounts()


def _fetch_locations(account_id: str) -> list[DiscoveredLocation]:
    with GoogleProfileClient(_access_token()) as profile:
        return profile.list_locations(account_id)


async def _discover[T](fetch: Callable[[], T]) -> T:
    """Run a blocking discovery call off the event loop, in documented error terms.

    The integration layer speaks `SourceFetchError` / `SourceNotConnectedError`; only
    `DomainError` subclasses reach a documented API error code (`docs/api-spec.md` §14),
    so an untranslated one would surface as an opaque 500.
    """
    try:
        return await run_in_threadpool(fetch)
    except SourceNotConnectedError as exc:
        raise GoogleNotConnectedError(str(exc)) from exc
    except SourceFetchError as exc:
        raise GoogleApiError(str(exc)) from exc


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

    async def list_accounts(self) -> list[GoogleAccountPayload]:
        """Accounts the stored grant can see (`docs/api-spec.md` §8)."""
        await self.ensure_connected()
        accounts = await _discover(_fetch_accounts)
        return [
            GoogleAccountPayload(account_id=account.account_id, name=account.name)
            for account in accounts
        ]

    async def list_locations(self, account_id: str) -> list[GoogleLocationPayload]:
        """Locations under one account (`docs/api-spec.md` §8)."""
        await self.ensure_connected()
        locations = await _discover(lambda: _fetch_locations(account_id))
        return [
            GoogleLocationPayload(location_id=location.location_id, title=location.title)
            for location in locations
        ]

    async def select_location(self, account_id: str, location_id: str) -> GoogleStatusPayload:
        """Record which profile to ingest from, unblocking backfill and sync.

        The pair is stored as given rather than re-verified against Google: the ids come
        from a list this same grant just produced, and a stale one fails loudly on the
        first fetch instead of silently ingesting the wrong location.
        """
        await self.ensure_connected()
        await self._credentials.set_location(
            self.SOURCE, account_id=account_id, location_id=location_id
        )
        await self._session.commit()
        return await self.status()

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
