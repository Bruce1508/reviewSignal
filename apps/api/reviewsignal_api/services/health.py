"""Health orchestration: probe each dependency and report which are unreachable."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.repositories.system import SystemRepository
from reviewsignal_api.schemas.system import ComponentHealth, HealthPayload

OK = "ok"
UNAVAILABLE = "unavailable"


class HealthService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = SystemRepository(session)
        self._redis = redis

    async def check(self) -> tuple[HealthPayload, list[str]]:
        """Return the health payload and the list of unhealthy component names."""
        database = await self._probe_database()
        redis = await self._probe_redis()

        unhealthy = [
            name for name, state in (("database", database), ("redis", redis)) if state != OK
        ]
        payload = HealthPayload(
            status=OK if not unhealthy else "degraded",
            components=ComponentHealth(api=OK, database=database, redis=redis),
        )
        return payload, unhealthy

    async def _probe_database(self) -> str:
        try:
            await self._repo.ping()
        except Exception:
            return UNAVAILABLE
        return OK

    async def _probe_redis(self) -> str:
        try:
            await self._redis.ping()
        except Exception:
            return UNAVAILABLE
        return OK
