"""Unit tests for Google account/location discovery (`docs/api-spec.md` §8).

Pure unit tests: recorded fixtures through `httpx.MockTransport`, no database and no
network. Live access is gated at 0 QPM until the API application is approved, so the
recorded envelopes are the only contract evidence available.
"""

import json
from pathlib import Path

import httpx
import pytest

from reviewsignal_api.integrations.base import SourceFetchError, SourceNotConnectedError
from reviewsignal_api.integrations.google.profile import GoogleProfileClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "google"

ACCOUNTS_HOST = "mybusinessaccountmanagement.googleapis.com"
LOCATIONS_HOST = "mybusinessbusinessinformation.googleapis.com"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def client_returning(*responses: httpx.Response) -> tuple[GoogleProfileClient, list[httpx.Request]]:
    """A client that replays `responses` in order, recording every request it received."""
    seen: list[httpx.Request] = []
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return remaining.pop(0)

    transport = httpx.MockTransport(handler)
    return GoogleProfileClient("token-123", httpx.Client(transport=transport)), seen


def ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


# --- Endpoints: reviews stayed on v4, discovery did not -----------------------


def test_accounts_call_the_account_management_api() -> None:
    client, seen = client_returning(ok(load("accounts_page_last.json")))

    client.list_accounts()

    assert seen[0].url.host == ACCOUNTS_HOST
    assert seen[0].url.path == "/v1/accounts"


def test_locations_call_the_business_information_api_under_the_account() -> None:
    client, seen = client_returning(ok(load("locations_page.json")))

    client.list_locations("111111111111111111111")

    assert seen[0].url.host == LOCATIONS_HOST
    assert seen[0].url.path == "/v1/accounts/111111111111111111111/locations"


def test_locations_send_the_required_read_mask() -> None:
    """`readMask` is required on locations.list; without it Google rejects the call."""
    client, seen = client_returning(ok(load("locations_page.json")))

    client.list_locations("111111111111111111111")

    assert seen[0].url.params["readMask"] == "name,title"


def test_requests_carry_the_bearer_token() -> None:
    client, seen = client_returning(ok(load("accounts_page_last.json")))

    client.list_accounts()

    assert seen[0].headers["Authorization"] == "Bearer token-123"


# --- Resource names are reduced to the bare ids the v4 reviews URL needs -------


def test_account_name_is_reduced_to_its_bare_id() -> None:
    client, _ = client_returning(ok(load("accounts_page_last.json")))

    accounts = client.list_accounts()

    assert [account.account_id for account in accounts] == [
        "222222222222222222222",
        "333333333333333333333",
    ]


def test_location_name_is_reduced_to_its_bare_id() -> None:
    """Locations are named `locations/{id}` with no account prefix, unlike the v4 path."""
    client, _ = client_returning(ok(load("locations_page.json")))

    locations = client.list_locations("111111111111111111111")

    assert [location.location_id for location in locations] == [
        "44444444444444444444",
        "55555555555555555555",
    ]


def test_account_without_a_name_falls_back_to_its_id() -> None:
    client, _ = client_returning(ok(load("accounts_page_last.json")))

    accounts = client.list_accounts()

    assert accounts[0].name == "Maple Photo Group"
    assert accounts[1].name == "333333333333333333333"


def test_location_without_a_title_falls_back_to_its_id() -> None:
    client, _ = client_returning(ok(load("locations_page_malformed.json")))

    locations = client.list_locations("111111111111111111111")

    assert locations[0].title == "66666666666666666666"


def test_entries_whose_name_is_not_the_documented_shape_are_dropped() -> None:
    """A malformed id would be spliced into the reviews URL and retarget the request."""
    client, _ = client_returning(ok(load("locations_page_malformed.json")))

    locations = client.list_locations("111111111111111111111")

    assert [location.location_id for location in locations] == ["66666666666666666666"]
    assert all("/" not in location.location_id for location in locations)


def test_an_empty_result_is_an_empty_list_not_an_error() -> None:
    client, _ = client_returning(ok({}))

    assert client.list_accounts() == []


# --- Paging -------------------------------------------------------------------


def test_pages_are_followed_until_the_token_runs_out() -> None:
    client, seen = client_returning(
        ok(load("accounts_page_with_next_token.json")), ok(load("accounts_page_last.json"))
    )

    accounts = client.list_accounts()

    assert len(seen) == 2
    assert seen[1].url.params["pageToken"] == "opaque-accounts-token-abc"
    assert [account.account_id for account in accounts] == [
        "111111111111111111111",
        "222222222222222222222",
        "333333333333333333333",
    ]


def test_paging_stops_at_the_cap_when_a_token_is_always_returned() -> None:
    """A source that always issues a token must not hang the request."""
    endless = [ok(load("accounts_page_with_next_token.json")) for _ in range(10)]
    client, seen = client_returning(*endless)

    client.list_accounts()

    assert len(seen) == 5


# --- Error translation --------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_credentials_raise_not_connected(status: int) -> None:
    client, _ = client_returning(
        httpx.Response(status, json={"error": {"message": "Request had invalid credentials."}})
    )

    with pytest.raises(SourceNotConnectedError, match="invalid credentials"):
        client.list_accounts()


def test_other_failures_raise_fetch_error_carrying_googles_message() -> None:
    client, _ = client_returning(
        httpx.Response(429, json={"error": {"message": "Quota exceeded."}})
    )

    with pytest.raises(SourceFetchError, match="Quota exceeded"):
        client.list_accounts()


def test_a_non_json_error_body_still_produces_a_fetch_error() -> None:
    client, _ = client_returning(httpx.Response(502, text="<html>bad gateway</html>"))

    with pytest.raises(SourceFetchError, match="502"):
        client.list_locations("111111111111111111111")


def test_a_transport_failure_raises_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = GoogleProfileClient("token-123", httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(SourceFetchError, match="connection refused"):
        client.list_accounts()


# --- Connection pool ownership ------------------------------------------------


def test_a_client_it_opened_is_closed_on_exit() -> None:
    """One pool per HTTP request; leaking one per settings-page load would accumulate."""
    with GoogleProfileClient("token-123") as profile:
        opened = profile._client

    assert opened.is_closed


def test_an_injected_client_is_left_open() -> None:
    """Closing a caller's client would break the next call that shares it."""
    injected = httpx.Client(transport=httpx.MockTransport(lambda request: ok({})))

    with GoogleProfileClient("token-123", injected):
        pass

    assert not injected.is_closed
