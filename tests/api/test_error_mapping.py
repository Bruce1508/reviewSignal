"""Every documented error code must map to a status and render the failure envelope."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from reviewsignal_api.core.errors import (
    ConflictError,
    DomainError,
    ErrorCode,
    GoogleApiError,
    GoogleNotConnectedError,
    InternalError,
    JobNotRetryableError,
    ModelUnavailableError,
    ResourceNotFoundError,
    TaxonomyVersionConflictError,
    UnauthorizedError,
    ValidationFailedError,
)
from reviewsignal_api.main import create_app

CASES = [
    (ValidationFailedError, ErrorCode.VALIDATION_ERROR, 400),
    (ResourceNotFoundError, ErrorCode.RESOURCE_NOT_FOUND, 404),
    (ConflictError, ErrorCode.CONFLICT, 409),
    (GoogleNotConnectedError, ErrorCode.GOOGLE_NOT_CONNECTED, 409),
    (GoogleApiError, ErrorCode.GOOGLE_API_ERROR, 502),
    (JobNotRetryableError, ErrorCode.JOB_NOT_RETRYABLE, 409),
    (TaxonomyVersionConflictError, ErrorCode.TAXONOMY_VERSION_CONFLICT, 409),
    (UnauthorizedError, ErrorCode.UNAUTHORIZED, 401),
    (ModelUnavailableError, ErrorCode.MODEL_UNAVAILABLE, 503),
    (InternalError, ErrorCode.INTERNAL_ERROR, 500),
]


def _app_raising(exc: DomainError) -> FastAPI:
    app = create_app()

    @app.get("/api/v1/boom")
    async def boom() -> None:
        raise exc

    return app


def test_every_documented_error_code_has_a_domain_error() -> None:
    assert {code for _, code, _ in CASES} == set(ErrorCode)


@pytest.mark.parametrize(("error_cls", "code", "status"), CASES)
async def test_domain_error_maps_to_failure_envelope(error_cls, code, status) -> None:
    app = _app_raising(error_cls("something went wrong"))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/boom")

    assert response.status_code == status
    assert response.json() == {
        "data": None,
        "error": {"code": code.value, "message": "something went wrong"},
    }
