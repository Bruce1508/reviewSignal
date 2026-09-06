"""Which predictor backs each evaluation workflow (`docs/api-spec.md` §10).

Empty by design: Phase 0 ships the scoring harness, not a classifier. `POST
/evaluation/run` reads this to decide whether a run can be queued at all, so a missing
entry surfaces as `MODEL_UNAVAILABLE` (`docs/api-spec.md` §14) rather than a job that is
certain to fail.

Keys are `evaluation_type` values, which name the workflow evaluated rather than a
metric family: one run records one row whose `metrics` body holds every family it
produced (`docs/data-model.md` §16).
"""

from reviewsignal_api.ai.evaluation.protocols import Predictor

PREDICTORS: dict[str, Predictor] = {}


def get_predictor(evaluation_type: str) -> Predictor | None:
    """The predictor registered for a workflow, or `None` when none is."""
    return PREDICTORS.get(evaluation_type)
