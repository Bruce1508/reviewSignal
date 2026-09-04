"""Source-agnostic ingestion contract.

`docs/architecture.md` §7 requires the ingestion contract to stay source-agnostic so
Yelp, surveys, or support tickets can be added later without touching the core, and
`docs/PRD.md` §11 names that isolation as the mitigation for Google API/auth changes.

Nothing in this module may reference a Google-specific type, field name, or endpoint.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


class SourceFetchError(RuntimeError):
    """A source could not be read. Callers decide whether to retry or fail the run."""


class SourceNotConnectedError(RuntimeError):
    """No usable credentials exist for the source."""


@dataclass(frozen=True, slots=True)
class NormalizedReview:
    """One review in the shape `reviews` stores (`docs/data-model.md` §4).

    `source` is not carried here: the adapter declares it, so a DTO cannot disagree
    with the adapter that produced it. `raw_payload` preserves the untouched source
    record, which §19 requires for reprocessing.
    """

    source_review_id: str
    rating: int
    review_text: str | None
    reviewer_name: str | None
    created_at: datetime
    updated_at: datetime
    owner_reply_text: str | None
    owner_reply_at: datetime | None
    language: str
    raw_payload: dict


@dataclass(frozen=True, slots=True)
class ReviewPage:
    """One page of results plus the opaque cursor for the next one.

    The cursor is deliberately opaque: only the adapter that issued it may interpret
    it. It is persisted verbatim in `sync_runs.cursor_state` (`data-model.md` §13).
    """

    reviews: tuple[NormalizedReview, ...]
    next_cursor: str | None
    # Entries the source returned that could not be normalized. Carried here rather
    # than on the adapter so the ingestion service can account for them without
    # reaching into a source-specific object.
    unmappable_count: int = 0


@runtime_checkable
class ReviewSourceAdapter(Protocol):
    """What the ingestion service needs from any feedback source.

    Deliberately minimal: paging is the only capability every source is assumed to
    have. Whether a source can filter server-side by change time varies, so the stop
    condition for an incremental sync lives in the service, driven by
    `NormalizedReview.updated_at`, not in this contract.
    """

    source: str

    def fetch_page(self, cursor: str | None = None) -> ReviewPage:
        """Return one page of reviews, newest first where the source allows it."""
        ...


def iter_pages(
    adapter: ReviewSourceAdapter, start_cursor: str | None = None
) -> Iterator[ReviewPage]:
    """Walk an adapter's pages until it stops issuing cursors."""
    cursor = start_cursor
    while True:
        page = adapter.fetch_page(cursor)
        yield page
        if page.next_cursor is None:
            return
        cursor = page.next_cursor
