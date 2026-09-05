"""Operator session routes (`docs/api-spec.md` §15)."""

from fastapi import APIRouter, Response

from reviewsignal_api.api.deps import SettingsDep
from reviewsignal_api.core.auth import SESSION_COOKIE, SESSION_TTL, issue_token, password_matches
from reviewsignal_api.core.errors import UnauthorizedError
from reviewsignal_api.schemas.auth import LoginRequest, SessionPayload
from reviewsignal_api.schemas.envelope import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[SessionPayload])
async def login(body: LoginRequest, settings: SettingsDep, response: Response):
    """Exchange the operator password for a signed session cookie."""
    if not password_matches(body.password, settings.operator_password):
        # One message for a wrong password and for an unconfigured one: the
        # difference is useful to an attacker and not to the operator.
        raise UnauthorizedError("Invalid credentials.")
    response.set_cookie(
        SESSION_COOKIE,
        issue_token(settings.session_secret),
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=settings.app_env != "local",
        samesite="lax",
        path="/",
    )
    return ApiResponse.ok(SessionPayload(authenticated=True))


@router.post("/logout", response_model=ApiResponse[SessionPayload])
async def logout(response: Response):
    """Drop the session cookie. Unguarded, so an expired session can still be cleared."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    return ApiResponse.ok(SessionPayload(authenticated=False))
