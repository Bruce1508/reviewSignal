"""Google Business Profile connection and job routes (`docs/api-spec.md` §8, §12)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Query, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from reviewsignal_api.api.deps import SessionDep, SettingsDep
from reviewsignal_api.core.errors import ValidationFailedError
from reviewsignal_api.schemas.envelope import ApiResponse
from reviewsignal_api.schemas.google import (
    RESOURCE_ID_PATTERN,
    GoogleAccountPayload,
    GoogleLocationPayload,
    GoogleLocationSelection,
    GoogleStatusPayload,
)
from reviewsignal_api.schemas.jobs import JobAcceptedPayload
from reviewsignal_api.services.google_connection import GoogleConnectionService
from reviewsignal_worker.queue import enqueue

router = APIRouter(prefix="/google", tags=["google"])

# The OAuth `state` is bound to the browser that started the flow by echoing it into a
# cookie, so a callback forged by another site cannot complete a connection. SameSite
# must be Lax, not Strict: Google's redirect back here is a cross-site top-level
# navigation, and Strict would withhold the cookie and break the flow.
_STATE_COOKIE = "rs_google_oauth_state"
_STATE_TTL_SECONDS = 600


@router.get("/status", response_model=ApiResponse[GoogleStatusPayload])
async def google_status(session: SessionDep, settings: SettingsDep):
    return ApiResponse.ok(await GoogleConnectionService(session, settings).status())


@router.get("/connect")
async def google_connect(session: SessionDep, settings: SettingsDep) -> RedirectResponse:
    """Redirect to the Google consent screen, binding the state to this browser."""
    state = secrets.token_urlsafe(32)
    url = GoogleConnectionService(session, settings).authorization_url(state)

    response = RedirectResponse(url)
    response.set_cookie(
        _STATE_COOKIE,
        state,
        max_age=_STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.app_env != "local",
        path="/api/v1/google",
    )
    return response


@router.get("/callback", response_model=ApiResponse[dict[str, bool]])
async def google_callback(
    code: str,
    state: str,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    rs_google_oauth_state: str | None = Cookie(default=None),
):
    """Complete the OAuth exchange, rejecting a callback this browser did not start."""
    if rs_google_oauth_state is None or not secrets.compare_digest(rs_google_oauth_state, state):
        raise ValidationFailedError(
            "OAuth state did not match the browser that started the connection."
        )

    # One state, one use: clear it before the exchange so a replayed callback fails.
    response.delete_cookie(_STATE_COOKIE, path="/api/v1/google")

    await GoogleConnectionService(session, settings).complete(code)
    return ApiResponse.ok({"connected": True})


@router.get("/accounts", response_model=ApiResponse[list[GoogleAccountPayload]])
async def google_accounts(session: SessionDep, settings: SettingsDep):
    """List the Google accounts the stored grant can see."""
    return ApiResponse.ok(await GoogleConnectionService(session, settings).list_accounts())


@router.get("/locations", response_model=ApiResponse[list[GoogleLocationPayload]])
async def google_locations(
    account_id: Annotated[str, Query(pattern=RESOURCE_ID_PATTERN)],
    session: SessionDep,
    settings: SettingsDep,
):
    """List the locations under one account, so one can be selected for ingestion."""
    return ApiResponse.ok(
        await GoogleConnectionService(session, settings).list_locations(account_id)
    )


@router.post("/location", response_model=ApiResponse[GoogleStatusPayload])
async def google_select_location(
    payload: GoogleLocationSelection, session: SessionDep, settings: SettingsDep
):
    """Record which profile to ingest from; backfill and sync stay blocked until set."""
    return ApiResponse.ok(
        await GoogleConnectionService(session, settings).select_location(
            payload.account_id, payload.location_id
        )
    )


@router.post("/disconnect", response_model=ApiResponse[dict[str, bool]])
async def google_disconnect(session: SessionDep, settings: SettingsDep):
    await GoogleConnectionService(session, settings).disconnect()
    return ApiResponse.ok({"connected": False})


@router.post("/backfill", response_model=ApiResponse[JobAcceptedPayload], status_code=202)
async def google_backfill(session: SessionDep, settings: SettingsDep):
    await GoogleConnectionService(session, settings).ensure_connected()
    job_id = await run_in_threadpool(enqueue, "google_backfill", None, 3)
    return ApiResponse.ok(
        JobAcceptedPayload(job_id=job_id, status="queued", job_type="google_backfill")
    )


@router.post("/sync", response_model=ApiResponse[JobAcceptedPayload], status_code=202)
async def google_sync(session: SessionDep, settings: SettingsDep):
    await GoogleConnectionService(session, settings).ensure_connected()
    job_id = await run_in_threadpool(enqueue, "google_sync", None, 3)
    return ApiResponse.ok(
        JobAcceptedPayload(job_id=job_id, status="queued", job_type="google_sync")
    )
