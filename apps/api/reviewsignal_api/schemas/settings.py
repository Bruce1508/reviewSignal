"""Schema for `GET /settings` (`docs/api-dashboard.md` §6).

`active_model`/`embedding_model` come from deploy-time environment config
(`core/config.py`), never from `settings`: `docs/data-model.md` §17 keeps secrets and
deploy-time values out of that table. The other three fields are runtime-configurable
and read from `settings`; they are `null` until something writes them.
"""

from pydantic import BaseModel


class SettingsPayload(BaseModel):
    default_date_range_days: int | None
    daily_sync_time: str | None
    classification_threshold: float | None
    active_model: str
    embedding_model: str
