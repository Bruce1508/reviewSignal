"""Redis client used for the queue and for queue-depth reporting."""

from functools import lru_cache

from redis.asyncio import Redis

from reviewsignal_api.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)
