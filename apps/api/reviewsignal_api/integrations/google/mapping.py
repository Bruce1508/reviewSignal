"""Google Business Profile review payload -> `NormalizedReview` (`docs/data-model.md` §4).

Field shapes follow the Google Business Profile API v4 `reviews` resource
(`GET mybusiness.googleapis.com/v4/accounts/*/locations/*/reviews`). `starRating` is a
string enum there, not an integer, and a review may legitimately carry no `comment`.
"""

from datetime import UTC, datetime

from reviewsignal_api.integrations.base import NormalizedReview, SourceFetchError

_STAR_RATINGS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def _parse_datetime(value: str, field: str, review_id: str) -> datetime:
    """Parse an RFC3339 timestamp into an aware UTC datetime.

    Naive results are pinned to UTC: an incremental sync compares these against a
    timezone-aware watermark, and mixing the two raises `TypeError` mid-run.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SourceFetchError(
            f"Google review {review_id} has an unparsable {field}: {value!r}"
        ) from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _clean_text(value: str | None) -> str | None:
    """`None` for absent/empty/whitespace-only text; real text is returned untouched."""
    if value is None:
        return None
    return value if value.strip() else None


def to_normalized_review(payload: dict) -> NormalizedReview | None:
    """Map one Google `reviews[]` entry, or `None` if it cannot be stored."""
    review_id = payload.get("reviewId")
    if not review_id:
        raise SourceFetchError("Google review payload is missing reviewId")

    star_rating = payload.get("starRating")
    rating = _STAR_RATINGS.get(star_rating) if isinstance(star_rating, str) else None
    if rating is None:
        return None

    create_time = payload.get("createTime")
    if not create_time:
        raise SourceFetchError(f"Google review {review_id} is missing createTime")
    created_at = _parse_datetime(create_time, "createTime", review_id)

    update_time = payload.get("updateTime")
    updated_at = (
        _parse_datetime(update_time, "updateTime", review_id) if update_time else created_at
    )

    reviewer = payload.get("reviewer") or {}
    reviewer_name = None
    if not reviewer.get("isAnonymous"):
        reviewer_name = reviewer.get("displayName") or None

    reply = payload.get("reviewReply") or {}
    reply_update_time = reply.get("updateTime")

    return NormalizedReview(
        source_review_id=review_id,
        rating=rating,
        review_text=_clean_text(payload.get("comment")),
        reviewer_name=reviewer_name,
        created_at=created_at,
        updated_at=updated_at,
        owner_reply_text=_clean_text(reply.get("comment")),
        owner_reply_at=(
            _parse_datetime(reply_update_time, "reviewReply.updateTime", review_id)
            if reply_update_time
            else None
        ),
        # The API carries no language field; guessing "en" would corrupt downstream
        # language-dependent metrics, so this is always the "undetermined" tag.
        language="und",
        raw_payload=payload,
    )
