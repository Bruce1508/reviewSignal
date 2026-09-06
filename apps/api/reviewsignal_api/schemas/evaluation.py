"""Schemas for `/evaluation/*` (`docs/api-spec.md` §10).

`api-spec.md` §10 splits the read contract: the list is run history, metrics come from the detail
route. The detail model therefore extends the summary instead of restating it.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Matches `evaluation_runs.evaluation_type` in `db/models.py`.
EVALUATION_TYPE_MAX_LENGTH = 64


class EvaluationRunSummary(BaseModel):
    """One row of run history. Deliberately without `metrics`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evaluation_type: str
    model_name: str
    model_version: str | None
    taxonomy_version: str | None
    dataset_version: str
    created_at: datetime


class EvaluationRunDetail(EvaluationRunSummary):
    taxonomy_version_id: uuid.UUID | None
    # Every metric family the run produced. A family it could not measure is null,
    # never zero, because zero is a measurement (`docs/evaluation.md` §30).
    metrics: dict
    notes: str | None


class EvaluationRunRequest(BaseModel):
    """`evaluation_type` names the workflow to evaluate, not a metric family."""

    evaluation_type: str = Field(min_length=1, max_length=EVALUATION_TYPE_MAX_LENGTH)
