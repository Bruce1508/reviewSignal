"""Contract tests for `/auth/*` and the session guard (`docs/api-spec.md` §15)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from reviewsignal_api.api.deps import require_session
from reviewsignal_api.core.auth import SESSION_COOKIE, issue_token
from reviewsignal_api.core.config import Settings, get_settings
from reviewsignal_api.main import app

PASSWORD = "correct-horse-battery-staple"
SECRET = "test-session-secret"


@pytest.fixture
def guarded() -> Iterator[Settings]:
    """Restore the real guard, which `conftest` lifts for every other test."""
    settings = get_settings().model_copy(
        update={"operator_password": PASSWORD, "session_secret": SECRET}
    )
    app.dependency_overrides.pop(require_session, None)
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def unconfigured() -> Iterator[Settings]:
    """No operator password set: the deployment cannot be logged into at all."""
    settings = get_settings().model_copy(update={"operator_password": "", "session_secret": SECRET})
    app.dependency_overrides.pop(require_session, None)
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


async def _login(client: AsyncClient, password: str):
    return await client.post("/api/v1/auth/login", json={"password": password})


async def test_login_with_the_configured_password_sets_a_session_cookie(
    client: AsyncClient, guarded: Settings
) -> None:
    response = await _login(client, PASSWORD)

    assert response.status_code == 200
    assert response.json()["error"] is None
    cookie = response.cookies.get(SESSION_COOKIE)
    assert cookie is not None
    assert PASSWORD not in cookie


async def test_the_session_cookie_is_http_only(client: AsyncClient, guarded: Settings) -> None:
    response = await _login(client, PASSWORD)

    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()


async def test_login_with_a_wrong_password_is_rejected_without_a_cookie(
    client: AsyncClient, guarded: Settings
) -> None:
    response = await _login(client, "not-the-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.cookies.get(SESSION_COOKIE) is None


async def test_login_is_refused_when_no_operator_password_is_configured(
    client: AsyncClient, unconfigured: Settings
) -> None:
    """An empty configured password must not mean 'any password works'."""
    response = await _login(client, "")

    assert response.status_code == 401
    assert response.cookies.get(SESSION_COOKIE) is None


async def test_health_stays_public(client: AsyncClient, guarded: Settings) -> None:
    """Container health checks run without credentials."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200


async def test_a_protected_route_refuses_without_a_cookie(
    client: AsyncClient, guarded: Settings
) -> None:
    response = await client.get("/api/v1/system/status")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_google_routes_are_guarded_too(client: AsyncClient, guarded: Settings) -> None:
    """The nine Google endpoints were the reason this guard exists."""
    response = await client.get("/api/v1/google/status")

    assert response.status_code == 401


async def test_evaluation_routes_are_guarded_too(client: AsyncClient, guarded: Settings) -> None:
    """`api-spec.md` §15 guards every `/api/v1` route but `/health`, this one included."""
    response = await client.get("/api/v1/evaluation/runs")

    assert response.status_code == 401


async def test_a_protected_route_accepts_a_freshly_issued_cookie(
    client: AsyncClient, guarded: Settings
) -> None:
    await _login(client, PASSWORD)

    response = await client.get("/api/v1/system/status")

    assert response.status_code != 401


@pytest.mark.parametrize(
    "token",
    ["", "garbage", "9999999999.deadbeef", "notanumber.deadbeef"],
    ids=["empty", "unstructured", "wrong-signature", "unparsable-expiry"],
)
async def test_a_forged_cookie_is_refused(
    client: AsyncClient, guarded: Settings, token: str
) -> None:
    client.cookies.set(SESSION_COOKIE, token)

    response = await client.get("/api/v1/system/status")

    assert response.status_code == 401


async def test_an_expired_cookie_is_refused(client: AsyncClient, guarded: Settings) -> None:
    stale = issue_token(SECRET, ttl=timedelta(hours=12), now=datetime.now(UTC) - timedelta(days=2))
    client.cookies.set(SESSION_COOKIE, stale)

    response = await client.get("/api/v1/system/status")

    assert response.status_code == 401


async def test_a_cookie_signed_with_another_secret_is_refused(
    client: AsyncClient, guarded: Settings
) -> None:
    """Rotating SESSION_SECRET must invalidate every outstanding session."""
    foreign = issue_token("a-different-secret", ttl=timedelta(hours=12))
    client.cookies.set(SESSION_COOKIE, foreign)

    response = await client.get("/api/v1/system/status")

    assert response.status_code == 401


async def test_logout_clears_the_cookie(client: AsyncClient, guarded: Settings) -> None:
    await _login(client, PASSWORD)

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert not client.cookies.get(SESSION_COOKIE)
