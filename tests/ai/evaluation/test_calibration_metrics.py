"""Unit tests for confidence calibration (`docs/evaluation.md` §9).

Calibration is scored per prediction as a (confidence, was_correct) pair, so the
metric stays independent of whether the prediction was a category or a sentiment.
"""

import pytest

from reviewsignal_api.ai.evaluation.metrics.calibration import calibration_metrics

# Four predictions, scored into two buckets of width 0.5.
#
#   confidence  correct   (confidence - outcome)^2
#   0.2         no        0.04
#   0.4         yes       0.36
#   0.6         no        0.36
#   0.9         yes       0.01
#
# Brier = (0.04 + 0.36 + 0.36 + 0.01) / 4 = 0.1925
#
# bucket [0.0, 0.5)  n=2  mean_conf=0.30  accuracy=0.5  gap=0.20
# bucket [0.5, 1.0]  n=2  mean_conf=0.75  accuracy=0.5  gap=0.25
# ECE = (2/4)(0.20) + (2/4)(0.25) = 0.225
CONFIDENCES = [0.2, 0.4, 0.6, 0.9]
CORRECT = [False, True, False, True]


# --- Rule 1: Brier score ----------------------------------------------------


def test_brier_score_is_the_mean_squared_error_against_the_outcome() -> None:
    result = calibration_metrics(CONFIDENCES, CORRECT, bucket_count=2)
    assert result.brier_score == pytest.approx(0.1925)


def test_a_perfectly_confident_and_perfectly_right_model_scores_zero_brier() -> None:
    result = calibration_metrics([1.0, 0.0], [True, False], bucket_count=2)
    assert result.brier_score == pytest.approx(0.0)


def test_a_perfectly_confident_and_perfectly_wrong_model_scores_one_brier() -> None:
    result = calibration_metrics([1.0, 0.0], [False, True], bucket_count=2)
    assert result.brier_score == pytest.approx(1.0)


# --- Rule 2: expected calibration error -------------------------------------


def test_ece_weights_each_bucket_gap_by_bucket_size() -> None:
    result = calibration_metrics(CONFIDENCES, CORRECT, bucket_count=2)
    assert result.expected_calibration_error == pytest.approx(0.225)


def test_a_calibrated_model_has_near_zero_ece() -> None:
    """Claiming 100% and being right, claiming 0% and being wrong: no gap either way."""
    result = calibration_metrics([1.0, 1.0, 0.0, 0.0], [True, True, False, False], bucket_count=2)
    assert result.expected_calibration_error == pytest.approx(0.0)


def test_an_overconfident_model_has_a_large_ece() -> None:
    """Confidently wrong is exactly the failure mode that would waste the Qwen fallback."""
    result = calibration_metrics([0.95, 0.95, 0.95, 0.95], [False] * 4, bucket_count=2)
    assert result.expected_calibration_error == pytest.approx(0.95)


# --- Rule 3: reliability buckets --------------------------------------------


def test_buckets_span_the_whole_confidence_range_in_order() -> None:
    buckets = calibration_metrics(CONFIDENCES, CORRECT, bucket_count=4).buckets
    assert [(b.lower, b.upper) for b in buckets] == [
        (0.0, 0.25),
        (0.25, 0.5),
        (0.5, 0.75),
        (0.75, 1.0),
    ]


def test_each_bucket_reports_its_own_mean_confidence_and_accuracy() -> None:
    buckets = calibration_metrics(CONFIDENCES, CORRECT, bucket_count=2).buckets
    assert buckets[0].count == 2
    assert buckets[0].mean_confidence == pytest.approx(0.3)
    assert buckets[0].accuracy == pytest.approx(0.5)
    assert buckets[1].count == 2
    assert buckets[1].mean_confidence == pytest.approx(0.75)
    assert buckets[1].accuracy == pytest.approx(0.5)


def test_an_empty_bucket_is_reported_rather_than_dropped() -> None:
    """A gap in the reliability curve is a finding, not something to hide."""
    buckets = calibration_metrics([0.9, 0.95], [True, True], bucket_count=2).buckets
    assert buckets[0].count == 0
    assert buckets[1].count == 2


def test_an_empty_bucket_contributes_nothing_to_ece() -> None:
    result = calibration_metrics([0.9, 0.95], [True, True], bucket_count=2)
    assert result.buckets[0].count == 0
    # Only the populated bucket counts: mean_conf 0.925 vs accuracy 1.0.
    assert result.expected_calibration_error == pytest.approx(0.075)


def test_bucket_counts_sum_to_the_number_of_predictions() -> None:
    result = calibration_metrics(CONFIDENCES, CORRECT, bucket_count=10)
    assert sum(bucket.count for bucket in result.buckets) == 4
    assert result.item_count == 4


# --- Rule 4: boundary confidences land in exactly one bucket ---------------


def test_a_confidence_of_one_lands_in_the_last_bucket_not_past_it() -> None:
    buckets = calibration_metrics([1.0], [True], bucket_count=4).buckets
    assert buckets[3].count == 1
    assert sum(bucket.count for bucket in buckets) == 1


def test_a_confidence_of_zero_lands_in_the_first_bucket() -> None:
    buckets = calibration_metrics([0.0], [False], bucket_count=4).buckets
    assert buckets[0].count == 1


def test_a_boundary_confidence_belongs_to_the_bucket_it_opens() -> None:
    """0.5 with two buckets opens the upper bucket rather than closing the lower one."""
    buckets = calibration_metrics([0.5], [True], bucket_count=2).buckets
    assert buckets[0].count == 0
    assert buckets[1].count == 1


def test_a_boundary_confidence_holds_for_a_bucket_count_that_is_not_exact() -> None:
    """`int(6 / 47 * 47)` truncates to 5.999..., filing a boundary one bucket low."""
    confidence = 6 / 47
    result = calibration_metrics([confidence], [True], bucket_count=47)
    filled = [index for index, bucket in enumerate(result.buckets) if bucket.count]
    assert filled == [6]


def test_every_boundary_confidence_lands_in_the_bucket_it_opens() -> None:
    """A bucket must contain the confidences its own reported bounds claim."""
    for bucket_count in range(2, 64):
        for opened in range(bucket_count):
            confidence = opened / bucket_count
            result = calibration_metrics([confidence], [True], bucket_count=bucket_count)
            filled = [index for index, bucket in enumerate(result.buckets) if bucket.count]
            assert filled == [opened], f"{confidence!r} with {bucket_count} buckets"
            bucket = result.buckets[opened]
            assert bucket.lower <= confidence < bucket.upper


# --- Rule 5: invalid input is a bug, not a score ---------------------------


def test_a_confidence_above_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        calibration_metrics([1.5], [True])


def test_a_negative_confidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        calibration_metrics([-0.1], [True])


def test_mismatched_lengths_raise_rather_than_scoring_a_prefix() -> None:
    with pytest.raises(ValueError, match="same length"):
        calibration_metrics(CONFIDENCES, CORRECT[:2])


def test_an_empty_benchmark_raises_rather_than_reporting_zero() -> None:
    with pytest.raises(ValueError, match="empty"):
        calibration_metrics([], [])


def test_a_bucket_count_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="bucket_count"):
        calibration_metrics(CONFIDENCES, CORRECT, bucket_count=0)
