"""Aspect-level sentiment metrics (`docs/evaluation.md` §7).

Sentiment is single-label per aspect over the `data-model.md` §9 vocabulary, so the
confusion matrix is fixed to that vocabulary rather than to whatever was observed.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from reviewsignal_api.ai.evaluation.metrics.scores import Score, mean, prf_score
from reviewsignal_api.db.models import SENTIMENTS


@dataclass(frozen=True)
class SentimentMetrics:
    accuracy: float
    macro_f1: float
    per_sentiment: dict[str, Score]
    # confusion[gold][predicted] -> count.
    confusion: dict[str, dict[str, int]]
    # Aspects where gold and prediction both named the category, not reviews:
    # a category the model missed is counted by the classification metrics.
    pair_count: int


def sentiment_metrics(gold: Sequence[str], predicted: Sequence[str]) -> SentimentMetrics:
    """Score aspect sentiment predictions against gold sentiment labels."""
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted must have the same length")
    if not gold:
        raise ValueError("cannot evaluate an empty benchmark")
    for label in (*gold, *predicted):
        if label not in SENTIMENTS:
            raise ValueError(f"unknown sentiment: {label!r}")

    confusion: dict[str, dict[str, int]] = {
        actual: {predicted: 0 for predicted in SENTIMENTS} for actual in SENTIMENTS
    }
    for gold_label, predicted_label in zip(gold, predicted, strict=True):
        confusion[gold_label][predicted_label] += 1

    per_sentiment: dict[str, Score] = {}
    for label in SENTIMENTS:
        true_positives = confusion[label][label]
        false_negatives = sum(confusion[label].values()) - true_positives
        false_positives = sum(confusion[a][label] for a in SENTIMENTS) - true_positives
        per_sentiment[label] = prf_score(true_positives, false_positives, false_negatives)

    correct = sum(confusion[label][label] for label in SENTIMENTS)
    # Averaging in a sentiment the benchmark never contains would understate the score.
    observed = [score.f1 for score in per_sentiment.values() if score.support]
    return SentimentMetrics(
        accuracy=correct / len(gold),
        macro_f1=mean(observed),
        per_sentiment=per_sentiment,
        confusion=confusion,
        pair_count=len(gold),
    )
