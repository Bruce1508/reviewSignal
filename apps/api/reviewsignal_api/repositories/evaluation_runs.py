"""Evaluation run persistence (`docs/data-model.md` §16). No business rules here.

Runs accumulate: `evaluation.md` §3 forbids rewriting a result in place, so there is
no update path, only `record`.
"""

import uuid

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
