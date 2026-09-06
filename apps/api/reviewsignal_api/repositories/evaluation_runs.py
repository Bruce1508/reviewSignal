"""Evaluation run persistence (`docs/data-model.md` §16). No business rules here.

Runs accumulate: `data-model.md` §16 gives the table `created_at` and no update
column, so there is no update path, only `record`.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from reviewsignal_api.ai.evaluation.runner import EvaluationResult
from reviewsignal_api.db.models import EvaluationRun


class EvaluationRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        result: EvaluationResult,
        evaluation_type: str,
        taxonomy_version_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> EvaluationRun:
        """`taxonomy_version_id` is passed in rather than read from the dataset: the
        benchmark file records a taxonomy version as provenance text, while this column
        is a foreign key the caller must resolve. The provenance text is stored too, so
        a run still names its taxonomy before any `taxonomy_versions` row exists."""
        run = EvaluationRun(
            evaluation_type=evaluation_type,
            model_name=result.model_name,
            model_version=result.model_version,
            taxonomy_version_id=taxonomy_version_id,
            taxonomy_version=result.taxonomy_version,
            dataset_version=result.dataset_version,
            metrics=result.metrics_payload(),
            notes=notes,
        )
        self._session.add(run)
        self._session.flush()
        return run


class EvaluationRunReader:
    """Async read path for the API.

    The writer above is synchronous because it runs inside the RQ worker, while the API
    is async (`db/session.py`). Both live here because both are `evaluation_runs`
    persistence and neither carries a business rule.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_newest_first(self) -> Sequence[EvaluationRun]:
        """The table is the history: `data-model.md` §16 defines no update column.

        `id` breaks ties because `created_at` defaults to `now()`, which PostgreSQL
        holds constant across a transaction — runs written together would otherwise
        come back in arbitrary order.
        """
        result = await self._session.execute(
            select(EvaluationRun).order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
        )
        return result.scalars().all()

    async def get(self, run_id: uuid.UUID) -> EvaluationRun | None:
        return await self._session.get(EvaluationRun, run_id)
