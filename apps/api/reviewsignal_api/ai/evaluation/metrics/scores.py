"""Precision/recall/F1 primitives shared by the evaluation metrics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Score:
    """Precision/recall/F1 over some scope. `support` counts gold occurrences."""

    precision: float
    recall: float
    f1: float
    support: int


def prf_score(true_positives: int, false_positives: int, false_negatives: int) -> Score:
    """A count with no denominator scores 0.0 rather than raising."""
    predicted = true_positives + false_positives
    actual = true_positives + false_negatives
    precision = true_positives / predicted if predicted else 0.0
    recall = true_positives / actual if actual else 0.0
    denominator = precision + recall
    f1 = 2 * precision * recall / denominator if denominator else 0.0
    return Score(precision=precision, recall=recall, f1=f1, support=actual)


def mean(values: list[float]) -> float:
    # A benchmark can legitimately contain no labels at all (rating-only reviews).
    return sum(values) / len(values) if values else 0.0
