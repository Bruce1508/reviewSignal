"""Thin HTTP client for the Google Business Profile reviews endpoint.

Synchronous by design: this runs inside an RQ worker, which is sync (`docs/PRD.md`
§11 requires long-running AI/sync work to be queued, not run inline in the API).
"""

import httpx

from reviewsignal_api.integrations.base import SourceFetchError, SourceNotConnectedError

_BASE_URL = "https://mybusiness.googleapis.com/v4"
_PAGE_SIZE = 50
_TIMEOUT = httpx.Timeout(connect=30.0, read=30.0, write=30.0, pool=30.0)


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])
    except Exception:
        return response.text[:200]


class GoogleReviewsClient:
    def __init__(
        self,
        access_token: str,
        account_id: str,
        location_id: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._access_token = access_token
        self._account_id = account_id
        self._location_id = location_id
        self._client = http_client if http_client is not None else httpx.Client(timeout=_TIMEOUT)

    def list_reviews(self, page_token: str | None = None) -> dict:
        url = f"{_BASE_URL}/accounts/{self._account_id}/locations/{self._location_id}/reviews"
        params: dict[str, str | int] = {"pageSize": _PAGE_SIZE, "orderBy": "updateTime desc"}
        if page_token:
            params["pageToken"] = page_token

        try:
            response = self._client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.RequestError as exc:
            raise SourceFetchError(f"Google reviews request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise SourceNotConnectedError(
                f"Google credentials rejected ({response.status_code}): {_error_message(response)}"
            )
        if response.status_code != 200:
            raise SourceFetchError(
                f"Google reviews request failed ({response.status_code}): "
                f"{_error_message(response)}"
            )

        return response.json()
