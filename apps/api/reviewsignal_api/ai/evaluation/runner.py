"""Runs a benchmark through a predictor and scores it (`docs/evaluation.md` §35).

One pass over the dataset produces all three metric families, because sentiment and
calibration both depend on which categories the predictor got right.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from reviewsignal_api.ai.evaluation.dataset import BenchmarkDataset
from reviewsignal_api.ai.evaluation.metrics.calibration import (
    CalibrationMetrics,
    calibration_metrics,
)
from reviewsignal_api.ai.evaluation.metrics.classification import (
    ClassificationMetrics,
    classification_metrics,
)
from reviewsignal_api.ai.evaluation.metrics.sentiment import SentimentMetrics, sentiment_metrics
from reviewsignal_api.ai.evaluation.protocols import PredictedAspect, Predictor
from reviewsignal_api.db.models import SENTIMENTS


@dataclass(frozen=True)
class EvaluationResult:
    """Scores plus the identity needed to record an `evaluation_runs` row."""

    dataset_version: str
    taxonomy_version: str | None
    model_name: str
    model_version: str | None
    classification: ClassificationMetrics
    # Absent rather than zero when the run produced nothing to score.
    sentiment: SentimentMetrics | None
    calibration: CalibrationMetrics | None

    def metrics_payload(self) -> dict:
        """The `evaluation_runs.metrics` JSONB body."""
        return {
            "classification": asdict(self.classification),
            "sentiment": asdict(self.sentiment) if self.sentiment else None,
            "calibration": asdict(self.calibration) if self.calibration else None,
        }


def _validated(aspects: Sequence[PredictedAspect], review_id: str) -> list[PredictedAspect]:
    """Structured predictor output is checked before it is scored."""
    categories = [aspect.category_id for aspect in aspects]
    if len(categories) != len(set(categories)):
        raise ValueError(f"duplicate category_id predicted for review {review_id!r}")
    for aspect in aspects:
        if aspect.sentiment not in SENTIMENTS:
            raise ValueError(f"unknown sentiment: {aspect.sentiment!r}")
        if not 0.0 <= aspect.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {aspect.confidence!r}")
    return list(aspects)


def run_evaluation(dataset: BenchmarkDataset, predictor: Predictor) -> EvaluationResult:
    """Score `predictor` against `dataset`."""
    predicted_categories: list[set[str]] = []
    gold_sentiments: list[str] = []
    predicted_sentiments: list[str] = []
    confidences: list[float] = []
    correct: list[bool] = []

    for item in dataset.items:
        aspects = _validated(predictor.predict(item), item.review_id)
        predicted = {aspect.category_id: aspect for aspect in aspects}
        gold = item.sentiment_by_category
        predicted_categories.append(set(predicted))

        # Sentiment is only meaningful where the category was found; missing a category
        # is already counted by the classification metrics.
        for category_id in sorted(set(predicted) & set(gold)):
            gold_sentiments.append(gold[category_id])
            predicted_sentiments.append(predicted[category_id].sentiment)

        for aspect in aspects:
            confidences.append(aspect.confidence)
            # A prediction is right only if both the category and the sentiment are.
            correct.append(gold.get(aspect.category_id) == aspect.sentiment)

    return EvaluationResult(
        dataset_version=dataset.dataset_version,
        taxonomy_version=dataset.taxonomy_version,
        model_name=predictor.name,
        model_version=predictor.version,
        classification=classification_metrics(dataset.gold_categories, predicted_categories),
        sentiment=sentiment_metrics(gold_sentiments, predicted_sentiments)
        if gold_sentiments
        else None,
        calibration=calibration_metrics(confidences, correct) if confidences else None,
    )
