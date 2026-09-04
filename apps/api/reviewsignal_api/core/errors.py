"""Domain errors and their API error codes.

Error codes are owned by `docs/api-spec.md` §14. Routes raise these; a single
handler in `main.py` maps them to HTTP responses so route handlers stay thin.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    GOOGLE_NOT_CONNECTED = "GOOGLE_NOT_CONNECTED"
    GOOGLE_API_ERROR = "GOOGLE_API_ERROR"
    JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
    TAXONOMY_VERSION_CONFLICT = "TAXONOMY_VERSION_CONFLICT"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """Base class for errors that map to a documented API error code."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationFailedError(DomainError):
    code = ErrorCode.VALIDATION_ERROR
    status_code = 400


class ResourceNotFoundError(DomainError):
    code = ErrorCode.RESOURCE_NOT_FOUND
    status_code = 404


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT
    status_code = 409


class GoogleNotConnectedError(DomainError):
    code = ErrorCode.GOOGLE_NOT_CONNECTED
    status_code = 409


class GoogleApiError(DomainError):
    code = ErrorCode.GOOGLE_API_ERROR
    status_code = 502


class JobNotRetryableError(DomainError):
    code = ErrorCode.JOB_NOT_RETRYABLE
    status_code = 409


class TaxonomyVersionConflictError(DomainError):
    code = ErrorCode.TAXONOMY_VERSION_CONFLICT
    status_code = 409


class ModelUnavailableError(DomainError):
    code = ErrorCode.MODEL_UNAVAILABLE
    status_code = 503


class InternalError(DomainError):
    code = ErrorCode.INTERNAL_ERROR
    status_code = 500
