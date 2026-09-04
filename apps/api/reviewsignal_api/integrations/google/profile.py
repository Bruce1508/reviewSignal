"""Account and location discovery for the Google connection (`docs/api-spec.md` §8).

Separate from `client.py` because the surfaces diverged: reviews are still served by
the legacy `mybusiness.googleapis.com/v4` API, while account and location listing moved
to the newer per-surface APIs. They share no base URL, only an error envelope.

Synchronous like the reviews client so the token refresh in `services/google_token.py`
is reused unchanged; the HTTP layer calls this through a threadpool.

Neither the ids nor the labels here reach `integrations/base.py`: listing the profiles a
grant can see is a Google-specific capability, not something every feedback source has.
"""

from dataclasses import dataclass

import httpx

from reviewsignal_api.integrations.base import SourceFetchError
from reviewsignal_api.integrations.google.http import raise_for_status

_ACCOUNTS_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
_LOCATIONS_URL = (
    "https://mybusinessbusinessinformation.googleapis.com/v1/accounts/{account_id}/locations"
)

# Both are the maximums the respective references document.
_ACCOUNTS_PAGE_SIZE = 20
_LOCATIONS_PAGE_SIZE = 100

# `readMask` is required on locations.list. Kept to the two fields a picker needs;
# `storeCode` is omitted because it is rejected for some accounts.
_LOCATIONS_READ_MASK = "name,title"

# A hard stop so a source that keeps issuing page tokens cannot hang a request. Covers
# 100 accounts / 500 locations, far beyond the single-location MVP (`docs/PRD.md` §11).
_MAX_PAGES = 5

_TIMEOUT = httpx.Timeout(connect=30.0, read=30.0, write=30.0, pool=30.0)


@dataclass(frozen=True, slots=True)
class DiscoveredAccount:
    """One Google account the grant can see. `account_id` is the bare path segment."""

    account_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DiscoveredLocation:
    """One location under an account. `location_id` is the bare path segment."""

    location_id: str
    title: str


def _resource_id(name: object, prefix: str) -> str | None:
    """`"accounts/123"` -> `"123"`, or `None` when the shape is not what Google documents.

    The result is interpolated into the reviews URL, so anything containing a slash or
    an unexpected prefix is dropped rather than passed through: a malformed value would
    otherwise silently retarget the request path.
    """
    if not isinstance(name, str) or not name.startswith(prefix):
        return None
    identifier = name[len(prefix) :]
    return identifier if identifier and "/" not in identifier else None


class GoogleProfileClient:
    """Use as a context manager so the connection pool it opens is released.

    Unlike the reviews client, which lives for one worker job, this is constructed per
    HTTP request; leaking a pool on every call to the settings page would accumulate.
    """

    def __init__(self, access_token: str, http_client: httpx.Client | None = None) -> None:
        self._access_token = access_token
        # Only a pool this class opened is this class's to close.
        self._owns_client = http_client is None
        self._client = http_client if http_client is not None else httpx.Client(timeout=_TIMEOUT)

    def __enter__(self) -> "GoogleProfileClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def list_accounts(self) -> list[DiscoveredAccount]:
        accounts: list[DiscoveredAccount] = []
        for envelope in self._paged(_ACCOUNTS_URL, {"pageSize": _ACCOUNTS_PAGE_SIZE}, "accounts"):
            for entry in envelope.get("accounts") or []:
                account_id = _resource_id(entry.get("name"), "accounts/")
                if account_id is None:
                    continue
                accounts.append(
                    DiscoveredAccount(
                        account_id=account_id,
                        # Personal accounts sometimes carry no accountName; the id is a
                        # worse label than a name but better than an empty row.
                        name=entry.get("accountName") or account_id,
                    )
                )
        return accounts

    def list_locations(self, account_id: str) -> list[DiscoveredLocation]:
        url = _LOCATIONS_URL.format(account_id=account_id)
        params: dict[str, str | int] = {
            "pageSize": _LOCATIONS_PAGE_SIZE,
            "readMask": _LOCATIONS_READ_MASK,
        }

        locations: list[DiscoveredLocation] = []
        for envelope in self._paged(url, params, "locations"):
            for entry in envelope.get("locations") or []:
                # Documented as `locations/{locationId}` — no account prefix, unlike the
                # v4 reviews path this id is later spliced into.
                location_id = _resource_id(entry.get("name"), "locations/")
                if location_id is None:
                    continue
                locations.append(
                    DiscoveredLocation(
                        location_id=location_id, title=entry.get("title") or location_id
                    )
                )
        return locations

    def _paged(self, url: str, params: dict[str, str | int], what: str):
        """Yield each page envelope until Google stops issuing tokens or the cap is hit."""
        page_token: str | None = None
        for _ in range(_MAX_PAGES):
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token

            envelope = self._get(url, page_params, what)
            yield envelope

            page_token = envelope.get("nextPageToken") or None
            if page_token is None:
                return

    def _get(self, url: str, params: dict[str, str | int], what: str) -> dict:
        try:
            response = self._client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.RequestError as exc:
            raise SourceFetchError(f"Google {what} request failed: {exc}") from exc

        raise_for_status(response, what)
        return response.json()
