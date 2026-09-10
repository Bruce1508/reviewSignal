"""Seed the `reviews` table with a synthetic, stub-adapter-shaped corpus.

Unblocks the Phase 1 dashboard read pages before Google Business Profile access is
granted. `integrations/base.py` keeps `ReviewSourceAdapter` source-agnostic
(`docs/architecture.md` §7, `docs/PRD.md` §11), so a stub adapter can drive the same
`IngestionService` a real Google backfill would, with `source="stub"` instead of
`"google"`.

`source="stub"` is deliberate, not a placeholder: `IngestionService.incremental()` looks
up the previous successful run by `adapter.source` (`services/sync_runs.py`). If this
ran under `source="google"`, the first real Google backfill's incremental sync would see
this stub run as its watermark and silently skip real history older than it.

`build_reviews` is deterministic for a given `(seed, now)`: re-running this script keeps
the same ratings, text, and relative recency, refreshed against the current time so the
corpus doesn't age out of the dashboard's default 7-day window
(`docs/api-dashboard.md` §1). Re-running upserts the same `source_review_id`s rather than
duplicating rows.
"""

import argparse
import random
from datetime import UTC, datetime, timedelta

from reviewsignal_api.integrations.base import NormalizedReview, ReviewPage
from reviewsignal_api.services.ingestion import IngestionService
from reviewsignal_worker.db import session_scope

_REVIEWER_FIRST_NAMES = (
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Casey",
    "Riley",
    "Jamie",
    "Sam",
    "Avery",
    "Quinn",
    "Hana",
    "Minh",
    "Priya",
    "Diego",
    "Fatima",
    "Owen",
)
_REVIEWER_LAST_INITIALS = "ABCDEFGHJKLMNPQRSTVW"

_POSITIVE_TEXTS = (
    "Prints came out sharp and the colours matched the originals exactly.",
    "Booked online in two minutes and the order was ready ahead of the quoted time.",
    "The framing job looked better than the photo I brought in.",
    "Staff walked me through paper options without being pushy about the upsell.",
    "Same-day pickup, no surprises on the price at the counter.",
    "Reprinted a faded photo from decades ago and it looks brand new.",
    "Easy to reach on the phone and they remembered my order from last time.",
    "Large canvas print arrived well packed and exactly the size I ordered.",
    "Helpful with a rush order for a gift, went out of their way to fit me in.",
    "Consistent quality every time I've used them this year.",
)
_NEUTRAL_TEXTS = (
    "Prints were fine, nothing stood out either way.",
    "Took a bit longer than expected but the results were acceptable.",
    "Price was about average for the area, quality matched that.",
    "Booking system worked but the confirmation email was delayed.",
    "Did the job. Would use again if nothing closer opens up.",
)
_NEGATIVE_TEXTS = (
    "Order was ready two days after the promised date with no notice.",
    "Charged more at pickup than the online quote showed.",
    "Colours were noticeably off compared to the digital file I submitted.",
    "Stood at the counter for ten minutes before anyone acknowledged me.",
    "Frame arrived with a visible scratch and no offer to fix it.",
    "Had to call twice to find out my order had actually arrived.",
    "Website said in stock but the paper size I wanted wasn't available in store.",
)

_REPLY_POSITIVE = (
    "Thank you for the kind words, we'll pass this along to the team!",
    "So glad it turned out the way you wanted. See you next time!",
)
_REPLY_NEGATIVE = (
    "Sorry we fell short here. Please reach out so we can make this right.",
    "This isn't the experience we aim for. Contact us directly and we'll fix it.",
)
_REPLY_NEUTRAL = ("Thanks for the feedback, we're always looking to improve.",)


def _rating(rng: random.Random) -> int:
    return rng.choices((5, 4, 3, 2, 1), weights=(40, 25, 12, 10, 13))[0]


def _text_for(rating: int, rng: random.Random) -> str | None:
    if rng.random() < 0.12:
        return None  # star-only, no comment - a real source may return this too.
    pool = _POSITIVE_TEXTS if rating >= 4 else _NEUTRAL_TEXTS if rating == 3 else _NEGATIVE_TEXTS
    return rng.choice(pool)


def _reviewer_name(rng: random.Random) -> str | None:
    if rng.random() < 0.15:
        return None
    return f"{rng.choice(_REVIEWER_FIRST_NAMES)} {rng.choice(_REVIEWER_LAST_INITIALS)}."


def _owner_reply(
    rating: int, created_at: datetime, rng: random.Random
) -> tuple[str | None, datetime | None]:
    if rng.random() > 0.3:
        return None, None
    pool = _REPLY_POSITIVE if rating >= 4 else _REPLY_NEGATIVE if rating <= 2 else _REPLY_NEUTRAL
    reply_at = created_at + timedelta(days=rng.randint(1, 5), hours=rng.randint(0, 23))
    return rng.choice(pool), reply_at


def build_reviews(count: int, *, seed: int, now: datetime | None = None) -> list[NormalizedReview]:
    """`count` reviews, newest-first, spread over the last 180 days before `now`.

    Newest-first matches what a real adapter is expected to yield: `IngestionService.
    _absorb` relies on that order for its incremental watermark, even though this script
    only ever calls `backfill()`. Deterministic given the same `(seed, now)`; `now`
    defaults to the real clock so a fresh run always looks recent.
    """
    rng = random.Random(seed)
    anchor = now if now is not None else datetime.now(UTC)
    reviews = []
    for i in range(count):
        rating = _rating(rng)
        created_at = anchor - timedelta(days=rng.uniform(0, 180), hours=rng.uniform(0, 24))
        reply_text, reply_at = _owner_reply(rating, created_at, rng)
        source_review_id = f"stub-{i:04d}"
        reviews.append(
            NormalizedReview(
                source_review_id=source_review_id,
                rating=rating,
                review_text=_text_for(rating, rng),
                reviewer_name=_reviewer_name(rng),
                created_at=created_at,
                updated_at=created_at,
                owner_reply_text=reply_text,
                owner_reply_at=reply_at,
                language="en",
                raw_payload={
                    "synthetic": True,
                    "generator": "tools/seed_stub_reviews.py",
                    "source_review_id": source_review_id,
                    "rating": rating,
                },
            )
        )
    reviews.sort(key=lambda r: r.created_at, reverse=True)
    return reviews


class StubReviewSourceAdapter:
    """`ReviewSourceAdapter` over an in-memory list, paged like a real source.

    Never `source = "google"` - see the module docstring on why that would corrupt a
    later real backfill's incremental watermark.
    """

    source = "stub"

    def __init__(self, reviews: list[NormalizedReview], *, page_size: int) -> None:
        self._pages = [reviews[i : i + page_size] for i in range(0, len(reviews), page_size)] or [
            []
        ]
        self._index = 0

    def fetch_page(self, cursor: str | None = None) -> ReviewPage:
        page = self._pages[self._index]
        self._index += 1
        next_cursor = str(self._index) if self._index < len(self._pages) else None
        return ReviewPage(reviews=tuple(page), next_cursor=next_cursor)


def seed_corpus(count: int, *, seed: int, page_size: int) -> None:
    reviews = build_reviews(count, seed=seed)
    adapter = StubReviewSourceAdapter(reviews, page_size=page_size)
    with session_scope() as session:
        outcome = IngestionService(session, adapter).backfill()
    print(
        f"seeded stub corpus: fetched={outcome.fetched} created={outcome.created} "
        f"updated={outcome.updated} unchanged={outcome.unchanged} unmappable={outcome.unmappable}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=150, help="number of reviews to generate")
    parser.add_argument("--seed", type=int, default=20260909, help="RNG seed, for reproducibility")
    parser.add_argument("--page-size", type=int, default=25, help="reviews per simulated page")
    args = parser.parse_args(argv)
    seed_corpus(args.count, seed=args.seed, page_size=args.page_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
