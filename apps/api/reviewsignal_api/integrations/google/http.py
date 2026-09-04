"""Shared HTTP error translation for the Google surfaces.

Reviews are still served by the legacy v4 API while account/location discovery moved
to the newer per-surface APIs, so the two clients cannot share a base URL. They do
share an error envelope and the same auth semantics, so the translation into the
source-agnostic errors of `integrations/base.py` lives here rather than twice.
"""

import httpx

from reviewsignal_api.integrations.base import SourceFetchError, SourceNotConnectedError


def error_message(response: httpx.Response) -> str:
    """Google's `error.message`, falling back to raw text when the body is not JSON."""
    try:
        return str(response.json()["error"]["message"])
    except Exception:
        return response.text[:200]


def raise_for_status(response: httpx.Response, what: str) -> None:
    """Translate a non-200 Google response into the ingestion contract's errors.

    401/403 is a credential problem no retry can fix — the operator must reconnect.
    Everything else is treated as transient and left retryable.
    """
    if response.status_code in (401, 403):
        raise SourceNotConnectedError(
            f"Google credentials rejected ({response.status_code}): {error_message(response)}"
        )
    if response.status_code != 200:
        raise SourceFetchError(
            f"Google {what} request failed ({response.status_code}): {error_message(response)}"
        )
