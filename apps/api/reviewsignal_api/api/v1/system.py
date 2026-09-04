"""Health and system status routes (`docs/api-spec.md` §2, `docs/deployment.md` §22)."""

from fastapi import APIRouter, Response, status

from reviewsignal_api.api.deps import RedisDep, SessionDep, SettingsDep
from reviewsignal_api.core.errors import ErrorCode
from reviewsignal_api.schemas.envelope import ApiResponse, error_body
from reviewsignal_api.schemas.system import HealthPayload, SystemStatusPayload
from reviewsignal_api.services.health import HealthService
from reviewsignal_api.services.system import SystemService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=ApiResponse[HealthPayload])
async def health(session: SessionDep, redis: RedisDep, response: Response):
    """Report API, database, and Redis health.

    Returns 503 when a dependency is unreachable so that a load balancer or
    deploy step can fail the check (`docs/deployment.md` §29).
    """
    payload, unhealthy = await HealthService(session, redis).check()
    if unhealthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return error_body(
            ErrorCode.INTERNAL_ERROR,
            f"Dependency unavailable: {', '.join(unhealthy)}.",
        )
    return ApiResponse.ok(payload)


@router.get("/system/status", response_model=ApiResponse[SystemStatusPayload])
async def system_status(session: SessionDep, redis: RedisDep, settings: SettingsDep):
    """Report last sync, queue depth, failed jobs, active taxonomy, and active model."""
    return ApiResponse.ok(await SystemService(session, redis, settings).status())
