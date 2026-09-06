"""Schemas for `/evaluation/*` (`docs/api-spec.md` §10).

`api-spec.md` §10 describes the list as run history and the detail as metrics; this reads
that as keeping the metrics body out of the list. The detail model therefore extends the
summary instead of restating it.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# The workflows `data-model.md` §16 names for `evaluation_type`. An unknown string is
# a request the caller got wrong, not a model that happens to be down, so it is
# rejected here rather than reaching the registry.
EvaluationWorkflow = Literal["classification", "taxonomy", "anomaly", "recommendation"]


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

    evaluation_type: EvaluationWorkflow
