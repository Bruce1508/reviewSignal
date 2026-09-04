"""System status orchestration (`docs/api-spec.md` §2)."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.config import Settings
from reviewsignal_api.core.constants import DEFAULT_QUEUE_NAME
from reviewsignal_api.repositories.system import SystemRepository
from reviewsignal_api.schemas.system import ActiveTaxonomy, LastSync, SystemStatusPayload


class SystemService:
    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings) -> None:
        self._repo = SystemRepository(session)
        self._redis = redis
        self._settings = settings

    async def status(self) -> SystemStatusPayload:
        sync_run = await self._repo.latest_sync_run()
        taxonomy = await self._repo.active_taxonomy_version()

        return SystemStatusPayload(
            last_sync=(
                LastSync(
                    status=sync_run.status,
                    started_at=sync_run.started_at,
                    finished_at=sync_run.finished_at,
                    reviews_created=sync_run.reviews_created,
                    reviews_updated=sync_run.reviews_updated,
                )
                if sync_run is not None
                else None
            ),
            queue_depth=await self._queue_depth(),
            failed_jobs=await self._repo.failed_job_count(),
            active_taxonomy=(
                ActiveTaxonomy(
                    version_number=taxonomy.version_number, activated_at=taxonomy.activated_at
                )
                if taxonomy is not None
                else None
            ),
            active_model=self._settings.ollama_model,
            last_insight_at=await self._repo.last_insight_at(),
        )

    async def _queue_depth(self) -> int:
        """Depth of the RQ queue. Redis being down is reported by /health, not here."""
        try:
            return int(await self._redis.llen(f"rq:queue:{DEFAULT_QUEUE_NAME}"))
        except Exception:
            return 0
