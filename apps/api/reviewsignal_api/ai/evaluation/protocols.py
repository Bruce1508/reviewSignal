"""The seam between the evaluation harness and whatever produces predictions.

PRD §10 puts the harness in Phase 0 and the classifier in Phase 1, so the harness is
written against this protocol rather than against a model. Phase 0 drives it with a
stub; Phase 1 supplies the real classifier without the harness changing.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from reviewsignal_api.ai.evaluation.dataset import BenchmarkItem


@dataclass(frozen=True)
class PredictedAspect:
    """One predicted aspect, mirroring the structured output in `ai-pipeline.md` §15.

    Evidence text is deliberately absent: `evaluation.md` §8 scores it with a human
    rubric, not a computed metric.
    """

    category_id: str
    sentiment: str
    confidence: float


class Predictor(Protocol):
    """`name` and `version` fill in `evaluation_runs` (`data-model.md` §16)."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str | None: ...

    def predict(self, item: BenchmarkItem) -> Sequence[PredictedAspect]: ...
