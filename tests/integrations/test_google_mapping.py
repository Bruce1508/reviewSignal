"""Unit tests for the Google adapter's mapping and error translation.

Pure unit tests: fixtures and in-memory payloads only, no database, no real network
(the client is exercised through `httpx.MockTransport`).
"""

import copy
import json
from datetime import UTC, timedelta
from pathlib import Path

import httpx
import pytest

from reviewsignal_api.integrations.base import SourceFetchError, SourceNotConnectedError
from reviewsignal_api.integrations.google.adapter import GoogleReviewSourceAdapter
from reviewsignal_api.integrations.google.client import GoogleReviewsClient
from reviewsignal_api.integrations.google.mapping import to_normalized_review

FIXTURES = Path(__file__).parent.parent / "fixtures" / "google"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# --- Rule 1: source_review_id -------------------------------------------------


def test_source_review_id_comes_from_review_id() -> None:
    review = to_normalized_review(load("review_normal_with_reply.json"))
    assert review is not None
    assert review.source_review_id == "rev-normal-001"


def test_missing_review_id_raises_source_fetch_error() -> None:
    with pytest.raises(SourceFetchError):
        to_normalized_review(load("review_missing_review_id.json"))


# --- Rule 2: rating --------------------------------------------------------


@pytest.mark.parametrize(
    ("star_rating", "expected"),
    [("ONE", 1), ("TWO", 2), ("THREE", 3), ("FOUR", 4), ("FIVE", 5)],
)
def test_star_rating_maps_to_integer(star_rating: str, expected: int) -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    payload["starRating"] = star_rating
    review = to_normalized_review(payload)
    assert review is not None
    assert review.rating == expected


def test_unspecified_star_rating_returns_none() -> None:
    assert to_normalized_review(load("review_unspecified_rating.json")) is None


def test_missing_star_rating_returns_none() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    del payload["starRating"]
    assert to_normalized_review(payload) is None


def test_unknown_star_rating_value_returns_none() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    payload["starRating"] = "SIX"
    assert to_normalized_review(payload) is None


# --- Rule 3: review_text -----------------------------------------------------


def test_review_text_comes_from_comment() -> None:
    review = to_normalized_review(load("review_normal_with_reply.json"))
    assert review is not None
    assert review.review_text == "Great service, the prints came out beautifully."


def test_absent_comment_maps_to_none() -> None:
    review = to_normalized_review(load("review_rating_only_no_comment.json"))
    assert review is not None
    assert review.review_text is None


def test_empty_string_comment_maps_to_none() -> None:
    review = to_normalized_review(load("review_rating_only_empty_comment.json"))
    assert review is not None
    assert review.review_text is None


def test_whitespace_only_comment_maps_to_none() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    payload["comment"] = "   \n\t  "
    review = to_normalized_review(payload)
    assert review is not None
    assert review.review_text is None


def test_real_text_whitespace_is_preserved_untouched() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    payload["comment"] = "  Great prints.  "
    review = to_normalized_review(payload)
    assert review is not None
    assert review.review_text == "  Great prints.  "


# --- Rule 4: reviewer_name ---------------------------------------------------


def test_reviewer_name_comes_from_display_name() -> None:
    review = to_normalized_review(load("review_normal_with_reply.json"))
    assert review is not None
    assert review.reviewer_name == "Jane D."


def test_anonymous_reviewer_has_no_name() -> None:
    review = to_normalized_review(load("review_anonymous.json"))
    assert review is not None
    assert review.reviewer_name is None


def test_missing_reviewer_has_no_name() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    del payload["reviewer"]
    review = to_normalized_review(payload)
    assert review is not None
    assert review.reviewer_name is None


def test_missing_display_name_has_no_name() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    del payload["reviewer"]["displayName"]
    review = to_normalized_review(payload)
    assert review is not None
    assert review.reviewer_name is None


def test_empty_display_name_has_no_name() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    payload["reviewer"]["displayName"] = ""
    review = to_normalized_review(payload)
    assert review is not None
    assert review.reviewer_name is None


# --- Rule 5: created_at / updated_at -----------------------------------------


def test_created_at_and_updated_at_parse_to_aware_utc() -> None:
    review = to_normalized_review(load("review_normal_with_reply.json"))
    assert review is not None
    assert review.created_at.tzinfo is not None
    assert review.created_at.utcoffset() == UTC.utcoffset(review.created_at)


def test_edited_review_has_update_time_after_create_time() -> None:
    review = to_normalized_review(load("review_edited.json"))
    assert review is not None
    assert review.updated_at > review.created_at


def test_missing_update_time_falls_back_to_create_time() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    del payload["updateTime"]
    review = to_normalized_review(payload)
    assert review is not None
    assert review.updated_at == review.created_at


def test_missing_create_time_raises_source_fetch_error() -> None:
    with pytest.raises(SourceFetchError):
        to_normalized_review(load("review_missing_create_time.json"))


# --- Rule 6: owner reply ------------------------------------------------------


def test_owner_reply_text_and_time_come_from_review_reply() -> None:
    review = to_normalized_review(load("review_normal_with_reply.json"))
    assert review is not None
    assert review.owner_reply_text == "Thanks so much for the kind words!"
    assert review.owner_reply_at is not None


def test_missing_review_reply_has_no_owner_reply() -> None:
    review = to_normalized_review(load("review_rating_only_no_comment.json"))
    assert review is not None
    assert review.owner_reply_text is None
    assert review.owner_reply_at is None


def test_empty_review_reply_comment_maps_to_none() -> None:
    payload = copy.deepcopy(load("review_normal_with_reply.json"))
    payload["reviewReply"]["comment"] = "   "
    review = to_normalized_review(payload)
    assert review is not None
    assert review.owner_reply_text is None


# --- Rule 7: language ---------------------------------------------------------


def test_language_is_always_und() -> None:
    review = to_normalized_review(load("review_normal_with_reply.json"))
    assert review is not None
    assert review.language == "und"


# --- Rule 8: raw_payload -------------------------------------------------------


def test_raw_payload_is_untouched_original() -> None:
    payload = load("review_normal_with_reply.json")
    review = to_normalized_review(payload)
    assert review is not None
    assert review.raw_payload == payload


# --- GoogleReviewsClient: error translation -----------------------------------


def _client_with_transport(handler) -> GoogleReviewsClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return GoogleReviewsClient(
        access_token="fake-token",
        account_id="111111111111111111111",
        location_id="22222222222222222222",
        http_client=http_client,
    )


def test_list_reviews_returns_parsed_envelope() -> None:
    envelope = load("page_last.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["pageSize"] == "50"
        assert request.url.params["orderBy"] == "updateTime desc"
        assert request.headers["Authorization"] == "Bearer fake-token"
        return httpx.Response(200, json=envelope)

    client = _client_with_transport(handler)
    assert client.list_reviews() == envelope


def test_list_reviews_sends_page_token_when_given() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["pageToken"] == "opaque-page-token-abc"
        return httpx.Response(200, json=load("page_last.json"))

    client = _client_with_transport(handler)
    client.list_reviews(page_token="opaque-page-token-abc")


@pytest.mark.parametrize("status_code", [401, 403])
def test_auth_errors_raise_source_not_connected_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"message": "bad credentials"}})

    client = _client_with_transport(handler)
    with pytest.raises(SourceNotConnectedError):
        client.list_reviews()


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_transient_errors_raise_source_fetch_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"message": "try again"}})

    client = _client_with_transport(handler)
    with pytest.raises(SourceFetchError):
        client.list_reviews()


def test_other_non_2xx_raises_source_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    client = _client_with_transport(handler)
    with pytest.raises(SourceFetchError):
        client.list_reviews()


def test_error_body_without_expected_shape_falls_back_to_raw_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream is on fire")

    client = _client_with_transport(handler)
    with pytest.raises(SourceFetchError, match="upstream is on fire"):
        client.list_reviews()


def test_network_error_raises_source_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client_with_transport(handler)
    with pytest.raises(SourceFetchError):
        client.list_reviews()


# --- GoogleReviewSourceAdapter --------------------------------------------------


def test_adapter_drops_unmappable_reviews_and_counts_them() -> None:
    envelope = {
        "reviews": [
            load("review_normal_with_reply.json"),
            load("review_unspecified_rating.json"),
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope)

    client = _client_with_transport(handler)
    adapter = GoogleReviewSourceAdapter(client)
    page = adapter.fetch_page()

    assert len(page.reviews) == 1
    assert page.unmappable_count == 1


def test_adapter_star_rating_unspecified_is_unmappable() -> None:
    envelope = {"reviews": [load("review_unspecified_rating.json")]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope)

    client = _client_with_transport(handler)
    adapter = GoogleReviewSourceAdapter(client)
    page = adapter.fetch_page()

    assert page.reviews == ()
    assert page.unmappable_count == 1


def test_adapter_next_cursor_from_next_page_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load("page_with_next_token.json"))

    client = _client_with_transport(handler)
    adapter = GoogleReviewSourceAdapter(client)
    page = adapter.fetch_page()

    assert page.next_cursor == "opaque-page-token-abc"


def test_adapter_next_cursor_is_none_on_last_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load("page_last.json"))

    client = _client_with_transport(handler)
    adapter = GoogleReviewSourceAdapter(client)
    page = adapter.fetch_page()

    assert page.next_cursor is None


def test_naive_timestamps_are_pinned_to_utc() -> None:
    """An incremental sync compares these against an aware watermark; naive would raise."""
    payload = {
        "reviewId": "naive-1",
        "starRating": "FOUR",
        "comment": "Fine",
        "createTime": "2026-01-15T10:30:00",
        "updateTime": "2026-01-15T10:30:00",
    }

    normalized = to_normalized_review(payload)

    assert normalized is not None
    assert normalized.created_at.tzinfo is not None
    assert normalized.updated_at.utcoffset() == timedelta(0)


def test_an_unparsable_timestamp_is_reported_as_a_source_error() -> None:
    payload = {
        "reviewId": "bad-time",
        "starRating": "FOUR",
        "createTime": "the fifteenth of January",
    }

    with pytest.raises(SourceFetchError, match="unparsable createTime"):
        to_normalized_review(payload)
