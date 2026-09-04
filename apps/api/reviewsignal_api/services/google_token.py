"""Access-token resolution for worker-side Google calls.

The HTTP layer performs the one-time authorization-code exchange; this module handles
the recurring refresh, synchronously, because RQ workers are synchronous. A Google
access token lives about an hour, which a full backfill can outlast, so refreshing
mid-run is a requirement rather than a nicety.

Tokens are held encrypted (`docs/data-model.md` §17) and are never logged
(`docs/deployment.md` §20).
"""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from reviewsignal_api.core.config import get_settings
from reviewsignal_api.core.crypto import decrypt, encrypt
from reviewsignal_api.db.models import SourceCredential
from reviewsignal_api.integrations.base import SourceFetchError, SourceNotConnectedError

logger = logging.getLogger(__name__)

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
# Refresh a little early so a token cannot expire between the check and the call.
EXPIRY_SKEW = timedelta(minutes=5)


def load_credential(session: Session, source: str) -> SourceCredential:
    credential = session.execute(
        select(SourceCredential).where(SourceCredential.source == source)
    ).scalar_one_or_none()

    if credential is None or credential.status != "connected":
        raise SourceNotConnectedError(f"No connected credential for source '{source}'.")
    if credential.refresh_token_encrypted is None:
        raise SourceNotConnectedError(f"Credential for '{source}' has no refresh token.")
    return credential


def resolve_access_token(session: Session, credential: SourceCredential) -> str:
    """Return a usable access token, refreshing it first when it is close to expiry."""
    if credential.access_token_encrypted is not None and _still_valid(credential):
        return decrypt(credential.access_token_encrypted)
    return _refresh(session, credential)


def _still_valid(credential: SourceCredential) -> bool:
    expires_at = credential.token_expires_at
    return expires_at is not None and expires_at - EXPIRY_SKEW > datetime.now(UTC)


def _refresh(session: Session, credential: SourceCredential) -> str:
    settings = get_settings()
    assert credential.refresh_token_encrypted is not None  # guaranteed by load_credential

    try:
        response = httpx.post(
            TOKEN_ENDPOINT,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": decrypt(credential.refresh_token_encrypted),
                "grant_type": "refresh_token",
            },
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise SourceFetchError(f"Could not reach Google's token endpoint: {exc}") from exc

    # A revoked or withdrawn grant is permanent; retrying it only burns attempts.
    if response.status_code in (400, 401):
        credential.status = "invalid"
        session.commit()
        raise SourceNotConnectedError(
            "Google rejected the refresh token; the connection must be re-authorized."
        )
    if response.status_code >= 300:
        raise SourceFetchError(f"Google token endpoint returned HTTP {response.status_code}.")

    body = response.json()
    access_token = body.get("access_token")
    if not access_token:
        raise SourceFetchError("Google's token response contained no access_token.")

    credential.access_token_encrypted = encrypt(access_token)
    credential.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=int(body.get("expires_in", 3600))
    )
    credential.updated_at = datetime.now(UTC)
    session.commit()
    logger.info("Refreshed Google access token for source '%s'", credential.source)
    return access_token
