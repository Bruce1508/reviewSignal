"""FastAPI application factory and centralized error mapping."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from reviewsignal_api.api.v1.router import api_router
from reviewsignal_api.core.constants import API_V1_PREFIX
from reviewsignal_api.core.errors import DomainError, ErrorCode
from reviewsignal_api.schemas.envelope import error_body

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="ReviewSignal AI", version="0.1.0", docs_url="/docs")
    app.include_router(api_router, prefix=API_V1_PREFIX)
    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_body(ErrorCode.VALIDATION_ERROR, _summarize(exc)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the cause; never leak internals through the API surface.
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body(ErrorCode.INTERNAL_ERROR, "An internal error occurred."),
        )


def _summarize(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        location = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{location}: {err.get('msg', 'invalid')}" if location else err.get("msg", ""))
    return "; ".join(parts) or "Request validation failed."


app = create_app()
