"""Persistence reads backing the system-status contract. No business rules here."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.db.models import Insight, Job, SyncRun, TaxonomyVersion


class SystemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        await self._session.execute(select(1))

    async def latest_sync_run(self) -> SyncRun | None:
        stmt = select(SyncRun).order_by(SyncRun.started_at.desc()).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def failed_job_count(self) -> int:
        failed = ("failed", "dead_letter")
        stmt = select(func.count()).select_from(Job).where(Job.status.in_(failed))
        return (await self._session.execute(stmt)).scalar_one()

    async def active_taxonomy_version(self) -> TaxonomyVersion | None:
        stmt = select(TaxonomyVersion).where(TaxonomyVersion.status == "active")
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def last_insight_at(self) -> datetime | None:
        stmt = select(func.max(Insight.created_at))
        return (await self._session.execute(stmt)).scalar_one_or_none()
