"""Confidence calibration (`docs/evaluation.md` §9).

Confidence decides whether a prediction is accepted or sent to the Qwen fallback
(`ai-pipeline.md` §22/§23), so a miscalibrated score costs either quality or latency.
That document puts it plainly: thresholds come from evaluation, not guesswork.
Scored per prediction as `(confidence, was_correct)`, which keeps the metric
independent of whether the prediction was a category or a sentiment.
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ReliabilityBucket:
    """One point on the reliability curve.

    `lower` is inclusive and `upper` exclusive, except on the last bucket, whose `upper`
    is inclusive so that a confidence of exactly 1.0 has a home. Deriving membership as
    `lower <= c < upper` would drop those predictions and the counts would stop summing
    to `item_count`.
    """

    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float


@dataclass(frozen=True)
class CalibrationMetrics:
    brier_score: float
    expected_calibration_error: float
    buckets: list[ReliabilityBucket]
    item_count: int


def calibration_metrics(
    confidences: Sequence[float],
    correct: Sequence[bool],
    bucket_count: int = 10,
) -> CalibrationMetrics:
    """Score how well confidence tracks correctness."""
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must have the same length")
    if not confidences:
        raise ValueError("cannot evaluate an empty benchmark")
    if bucket_count < 1:
        raise ValueError("bucket_count must be at least 1")
    for confidence in confidences:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence out of range: {confidence!r}")

    edges = [index / bucket_count for index in range(bucket_count + 1)]
    counts = [0] * bucket_count
    confidence_sums = [0.0] * bucket_count
    correct_counts = [0] * bucket_count
    squared_error = 0.0

    for confidence, was_correct in zip(confidences, correct, strict=True):
        squared_error += (confidence - float(was_correct)) ** 2
        # Assigned against the same edges the buckets report, so a confidence sitting
        # exactly on a boundary cannot be filed one bucket low by float truncation.
        # A confidence of exactly 1.0 belongs to the last bucket, not past its end.
        index = min(bisect_right(edges, confidence) - 1, bucket_count - 1)
        counts[index] += 1
        confidence_sums[index] += confidence
        correct_counts[index] += int(was_correct)

    total = len(confidences)
    buckets: list[ReliabilityBucket] = []
    expected_calibration_error = 0.0

    for index in range(bucket_count):
        count = counts[index]
        mean_confidence = confidence_sums[index] / count if count else 0.0
        accuracy = correct_counts[index] / count if count else 0.0
        buckets.append(
            ReliabilityBucket(
                lower=edges[index],
                upper=edges[index + 1],
                count=count,
                mean_confidence=mean_confidence,
                accuracy=accuracy,
            )
        )
        # An empty bucket carries zero weight, so a gap in the curve costs nothing.
        expected_calibration_error += (count / total) * abs(accuracy - mean_confidence)

    return CalibrationMetrics(
        brier_score=squared_error / total,
        expected_calibration_error=expected_calibration_error,
        buckets=buckets,
        item_count=total,
    )
