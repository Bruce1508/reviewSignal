"""Shared fixtures. Tests run against the local Compose Postgres and Redis."""

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.orm import Session

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
