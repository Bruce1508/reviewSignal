"""Review ingestion orchestration.

Source-agnostic by construction: this service knows only the contract in
`integrations/base.py`. `docs/architecture.md` §7 requires the ingestion contract to
stay source-independent, and `docs/PRD.md` §11 names that isolation as the mitigation
for Google API and auth changes.

Backfill and incremental sync differ only in their stop condition
(`docs/PRD.md` §6.1); everything else about the two runs is identical.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from reviewsignal_api.db.models import SyncRun
from reviewsignal_api.integrations.base import ReviewPage, ReviewSourceAdapter, iter_pages
from reviewsignal_api.repositories.reviews import ReviewRepository, UpsertOutcome
from reviewsignal_api.repositories.sync_runs import SyncRunRepository

logger = logging.getLogger(__name__)


@dataclass
class IngestionOutcome:
    """Counts for one run, shaped to fill `sync_runs` (`docs/data-model.md` §13)."""

    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    unmappable: int = 0

    @property
    def stored_anything(self) -> bool:
        return bool(self.created or self.updated)


class IngestionService:
    def __init__(self, session: Session, adapter: ReviewSourceAdapter) -> None:
        self._session = session
        self._adapter = adapter
        self._reviews = ReviewRepository(session)
        self._sync_runs = SyncRunRepository(session)

    def backfill(self) -> IngestionOutcome:
        """Walk the whole corpus. First connection only (`docs/PRD.md` §4.1)."""
        return self._run(stop_at=None)

    def incremental(self) -> IngestionOutcome:
        """Daily sync, stopping at the previous successful run's watermark.

        The watermark is the previous run's `started_at`, not its `finished_at`: a
        review edited while that run was in flight must be picked up again rather than
        fall into the gap between the two timestamps.
        """
        previous = self._sync_runs.last_successful(self._adapter.source)
        return self._run(stop_at=previous.started_at if previous is not None else None)

    def _run(self, stop_at: datetime | None) -> IngestionOutcome:
        run = self._sync_runs.start(self._adapter.source)
        self._session.commit()
        run_id = run.id
        outcome = IngestionOutcome()

        try:
            for page in iter_pages(self._adapter):
                outcome.unmappable += page.unmappable_count
                outcome.fetched += len(page.reviews) + page.unmappable_count
                exhausted = self._absorb(page, stop_at, outcome)
                self._sync_runs.save_cursor(run, {"next_cursor": page.next_cursor})
                # Commit per page so a crash keeps the reviews already stored and
                # leaves `sync_runs` showing real progress rather than nothing.
                self._session.commit()
                if exhausted:
                    break
        except Exception as exc:
            self._fail(run_id, outcome, exc)
            raise

        self._finish(run, "success", outcome)
        return outcome

    def _absorb(
        self, page: ReviewPage, stop_at: datetime | None, outcome: IngestionOutcome
    ) -> bool:
        """Upsert one page. Returns True when the watermark ends the walk.

        Early exit assumes the adapter yields newest-changed-first. Google supports
        that ordering; a future source that cannot must pass `stop_at=None` and rely
        on the upsert being idempotent instead.
        """
        for review in page.reviews:
            if stop_at is not None and review.updated_at <= stop_at:
                return True
            match self._reviews.upsert(self._adapter.source, review):
                case UpsertOutcome.CREATED:
                    outcome.created += 1
                case UpsertOutcome.UPDATED:
                    outcome.updated += 1
                case _:
                    outcome.unchanged += 1
        return False

    def _finish(self, run: SyncRun, status: str, outcome: IngestionOutcome) -> None:
        self._sync_runs.finish(
            run,
            status=status,
            reviews_fetched=outcome.fetched,
            reviews_created=outcome.created,
            reviews_updated=outcome.updated,
        )
        self._session.commit()

    def _fail(self, run_id: uuid.UUID, outcome: IngestionOutcome, exc: Exception) -> None:
        """Record the failure on its own transaction, then let the job layer retry.

        A run that stored something before failing is `partial`, not `failed`: the
        distinction is what tells an operator whether the corpus is now half-updated
        (`docs/data-model.md` §13).
        """
        self._session.rollback()
        run = self._session.get(SyncRun, run_id)
        if run is None:
            logger.error("Sync run %s vanished while recording a failure", run_id)
            return
        self._sync_runs.finish(
            run,
            status="partial" if outcome.stored_anything else "failed",
            reviews_fetched=outcome.fetched,
            reviews_created=outcome.created,
            reviews_updated=outcome.updated,
            error_message=f"{type(exc).__name__}: {exc}",
        )
        run.finished_at = datetime.now(UTC)
        self._session.commit()
