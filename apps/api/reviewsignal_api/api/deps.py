"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.config import Settings, get_settings
from reviewsignal_api.core.redis import get_redis
from reviewsignal_api.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
