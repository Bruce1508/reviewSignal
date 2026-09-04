"""Sync run lifecycle persistence (`docs/data-model.md` §13). No business rules here."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import SYNC_RUN_STATUSES, SyncRun

# finish() may only ever leave a run in a terminal state; "running" is the start state.
_FINISH_STATUSES = tuple(s for s in SYNC_RUN_STATUSES if s != "running")


class SyncRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(self, source: str) -> SyncRun:
        run = SyncRun(source=source, status="running", started_at=datetime.now(UTC))
        self._session.add(run)
        self._session.flush()
        return run

    def save_cursor(self, run: SyncRun, cursor_state: dict | None) -> None:
        run.cursor_state = cursor_state

    def finish(
        self,
        run: SyncRun,
        status: str,
        reviews_fetched: int,
        reviews_created: int,
        reviews_updated: int,
        error_message: str | None = None,
    ) -> None:
        if status not in _FINISH_STATUSES:
            raise ValueError(f"invalid sync run finish status: {status!r}")

        run.status = status
        run.finished_at = datetime.now(UTC)
        run.reviews_fetched = reviews_fetched
        run.reviews_created = reviews_created
        run.reviews_updated = reviews_updated
        run.error_message = error_message

    def latest(self, source: str) -> SyncRun | None:
        stmt = (
            select(SyncRun)
            .where(SyncRun.source == source)
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def last_successful(self, source: str) -> SyncRun | None:
        stmt = (
            select(SyncRun)
            .where(SyncRun.source == source, SyncRun.status == "success")
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()
