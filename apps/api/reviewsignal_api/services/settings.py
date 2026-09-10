"""Settings read orchestration (`docs/api-dashboard.md` §6).

Key names below are this dashboard's own convention: nothing else in the codebase
reads or writes `settings` rows yet, so there is no prior convention to follow.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reviewsignal_api.core.config import Settings
from reviewsignal_api.repositories.settings import SettingsReader
from reviewsignal_api.schemas.settings import SettingsPayload

_DATE_RANGE_KEY = "default_date_range_days"
_SYNC_TIME_KEY = "daily_sync_time"
_THRESHOLD_KEY = "classification_threshold"


class SettingsService:
    def __init__(self, session: AsyncSession, config: Settings) -> None:
        self._settings = SettingsReader(session)
        self._config = config

    async def get_settings(self) -> SettingsPayload:
        date_range = await self._settings.get_value(_DATE_RANGE_KEY)
        sync_time = await self._settings.get_value(_SYNC_TIME_KEY)
        threshold = await self._settings.get_value(_THRESHOLD_KEY)
        return SettingsPayload(
            default_date_range_days=date_range.get("days") if date_range else None,
            daily_sync_time=sync_time.get("time") if sync_time else None,
            classification_threshold=threshold.get("threshold") if threshold else None,
            active_model=self._config.ollama_model,
            embedding_model=self._config.embedding_model,
        )
