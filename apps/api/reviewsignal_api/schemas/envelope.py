"""Response envelope. Shape is owned by `docs/api-spec.md` §1."""

from pydantic import BaseModel

from reviewsignal_api.core.errors import ErrorCode


class ApiError(BaseModel):
    code: ErrorCode
    message: str


class ApiResponse[T](BaseModel):
    data: T | None = None
    error: ApiError | None = None

    @classmethod
    def ok(cls, data: T) -> "ApiResponse[T]":
        return cls(data=data, error=None)


def error_body(code: ErrorCode, message: str) -> dict:
    """Failure envelope as a plain dict, for use inside exception handlers."""
    return {"data": None, "error": {"code": code.value, "message": message}}
