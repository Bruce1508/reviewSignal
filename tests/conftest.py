"""Shared fixtures. Tests run against the local Compose Postgres and Redis."""

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from reviewsignal_api.api.deps import require_session
from reviewsignal_api.core.config import get_settings
from reviewsignal_api.main import app
from reviewsignal_worker.db import get_sessionmaker, session_scope

# Truncated between tests, child-first so foreign keys stay satisfiable.
MANAGED_TABLES = (
    "review_aspects",
    "review_analyses",
    "insight_actions",
    "insights",
    "anomalies",
    "taxonomy_changes",
    "taxonomy_nodes",
    "taxonomy_versions",
    "evaluation_runs",
    "model_runs",
    "reviews",
    "sync_runs",
    "jobs",
    "source_credentials",
)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def session() -> Iterator[Session]:
    """Rolled back, never committed, so a rejected write cannot leak into the next test."""
    db_session = get_sessionmaker()()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    with session_scope() as db_session:
        db_session.execute(text(f"TRUNCATE {', '.join(MANAGED_TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def _lift_session_guard() -> Iterator[None]:
    """Every route under `/api/v1` except `/health` requires a session.

    These suites predate the guard and assert unrelated contracts, so it is lifted
    here rather than threaded through cases that are not about authentication.
    `tests/api/test_auth_routes.py` restores it and is the only place it is asserted.
    """
    app.dependency_overrides[require_session] = lambda: None
    yield
    app.dependency_overrides.pop(require_session, None)
    app.dependency_overrides.pop(get_settings, None)
