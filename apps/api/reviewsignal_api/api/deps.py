"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.auth import SESSION_COOKIE, verify_token
from reviewsignal_api.core.config import Settings, get_settings
from reviewsignal_api.core.errors import UnauthorizedError
from reviewsignal_api.core.redis import get_redis
from reviewsignal_api.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_session(
    settings: SettingsDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    """Reject any request without a live, correctly signed session cookie."""
    if token is None or not verify_token(settings.session_secret, token):
        raise UnauthorizedError("Authentication is required.")
