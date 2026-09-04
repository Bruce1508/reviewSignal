"""`ReviewSourceAdapter` implementation for Google Business Profile (`base.py`)."""

from reviewsignal_api.integrations.base import NormalizedReview, ReviewPage
from reviewsignal_api.integrations.google.client import GoogleReviewsClient
from reviewsignal_api.integrations.google.mapping import to_normalized_review


class GoogleReviewSourceAdapter:
    source = "google"

    def __init__(self, client: GoogleReviewsClient) -> None:
        self._client = client

    def fetch_page(self, cursor: str | None = None) -> ReviewPage:
        envelope = self._client.list_reviews(cursor)

        reviews: list[NormalizedReview] = []
        unmappable_count = 0
        for entry in envelope.get("reviews", []):
            normalized = to_normalized_review(entry)
            if normalized is None:
                unmappable_count += 1
                continue
            reviews.append(normalized)

        return ReviewPage(
            reviews=tuple(reviews),
            next_cursor=envelope.get("nextPageToken") or None,
            unmappable_count=unmappable_count,
        )
