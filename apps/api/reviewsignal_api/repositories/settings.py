"""Settings persistence reads (`docs/api-dashboard.md` §6, `docs/operational-tables.md` §3).

Read-only: nothing writes runtime `settings` rows yet, so a fresh install returns
`None` for each key, never a fabricated default.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.db.models import Setting


class SettingsReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_value(self, key: str) -> dict | None:
        stmt = select(Setting.value).where(Setting.key == key)
        return (await self._session.execute(stmt)).scalar_one_or_none()
