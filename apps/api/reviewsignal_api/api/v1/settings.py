"""Settings read route (`docs/api-dashboard.md` §6). `PATCH /settings` stays deferred."""

from fastapi import APIRouter

from reviewsignal_api.api.deps import SessionDep, SettingsDep
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.settings import SettingsPayload
from reviewsignal_api.services.settings import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=ApiResponse[SettingsPayload])
async def get_settings_route(session: SessionDep, settings: SettingsDep):
    return ApiResponse.ok(await SettingsService(session, settings).get_settings())
