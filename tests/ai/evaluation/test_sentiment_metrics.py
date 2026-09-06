"""Unit tests for aspect-level sentiment metrics (`docs/evaluation.md` §7).

Sentiment is single-label per aspect over the vocabulary in `data-model.md` §9.
Expected numbers are computed by hand in the comments below.
"""

import pytest

from reviewsignal_api.ai.evaluation.metrics.sentiment import sentiment_metrics

# Eight aspect instances. Index 3, 5 and 7 (1-based) are the three mistakes.
#
#   #  gold      predicted
#   1  positive  positive   hit
#   2  positive  positive   hit
#   3  positive  neutral    miss  (positive read as neutral)
#   4  negative  negative   hit
#   5  negative  positive   miss  (a complaint read as praise)
#   6  neutral   neutral    hit
#   7  neutral   negative   miss
#   8  positive  positive   hit
#
# Accuracy = 5/8 = 0.625
#
# positive  TP=3 FP=1 FN=1 -> P=3/4 R=3/4 F1=0.75    support 4
# neutral   TP=1 FP=1 FN=1 -> P=1/2 R=1/2 F1=0.5     support 2
# negative  TP=1 FP=1 FN=1 -> P=1/2 R=1/2 F1=0.5     support 2
# Macro F1 = (0.75 + 0.5 + 0.5) / 3 = 0.58333...
GOLD = [
    "positive",
    "positive",
    "positive",
    "negative",
    "negative",
    "neutral",
    "neutral",
    "positive",
]
PREDICTED = [
    "positive",
    "positive",
    "neutral",
    "negative",
    "positive",
    "neutral",
    "negative",
    "positive",
]


# --- Rule 1: accuracy and macro F1 are different numbers ---------------------


def test_accuracy_is_the_share_of_exactly_matching_aspects() -> None:
    assert sentiment_metrics(GOLD, PREDICTED).accuracy == pytest.approx(0.625)


def test_macro_f1_averages_the_three_sentiment_f1_scores() -> None:
    assert sentiment_metrics(GOLD, PREDICTED).macro_f1 == pytest.approx((0.75 + 0.5 + 0.5) / 3)


def test_macro_f1_is_not_accuracy() -> None:
    """Accuracy hides a rare sentiment doing badly; macro F1 is why we report both."""
    result = sentiment_metrics(GOLD, PREDICTED)
    assert result.macro_f1 != pytest.approx(result.accuracy)


# --- Rule 2: per-sentiment scores -------------------------------------------


def test_per_sentiment_scores_match_the_hand_computed_values() -> None:
    per_sentiment = sentiment_metrics(GOLD, PREDICTED).per_sentiment
    assert per_sentiment["positive"].f1 == pytest.approx(0.75)
    assert per_sentiment["neutral"].f1 == pytest.approx(0.5)
    assert per_sentiment["negative"].f1 == pytest.approx(0.5)


def test_support_counts_gold_occurrences_per_sentiment() -> None:
    per_sentiment = sentiment_metrics(GOLD, PREDICTED).per_sentiment
    assert per_sentiment["positive"].support == 4
    assert per_sentiment["neutral"].support == 2
    assert per_sentiment["negative"].support == 2


# --- Rule 3: the confusion matrix always covers the full vocabulary ---------


def test_confusion_matrix_is_keyed_gold_then_predicted() -> None:
    confusion = sentiment_metrics(GOLD, PREDICTED).confusion
    assert confusion["positive"]["neutral"] == 1
    assert confusion["negative"]["positive"] == 1
    assert confusion["neutral"]["negative"] == 1


def test_confusion_matrix_keeps_empty_cells_so_absent_labels_stay_visible() -> None:
    """A sentiment the model never predicts must show as a zero row, not vanish."""
    confusion = sentiment_metrics(["positive", "positive"], ["positive", "positive"]).confusion
    assert set(confusion) == {"positive", "neutral", "negative"}
    assert set(confusion["neutral"]) == {"positive", "neutral", "negative"}
    assert confusion["neutral"]["neutral"] == 0


def test_confusion_matrix_rows_sum_to_gold_support() -> None:
    confusion = sentiment_metrics(GOLD, PREDICTED).confusion
    assert sum(confusion["positive"].values()) == 4
    assert sum(confusion["neutral"].values()) == 2
    assert sum(confusion["negative"].values()) == 2


def test_pair_count_reports_how_many_aspects_were_scored() -> None:
    assert sentiment_metrics(GOLD, PREDICTED).pair_count == 8


# --- Rule 4: perfect and worst cases ---------------------------------------


def test_a_perfect_prediction_scores_one() -> None:
    result = sentiment_metrics(GOLD, GOLD)
    assert result.accuracy == pytest.approx(1.0)
    assert result.macro_f1 == pytest.approx(1.0)


def test_a_sentiment_never_predicted_correctly_scores_zero() -> None:
    result = sentiment_metrics(["neutral", "neutral"], ["positive", "positive"])
    assert result.accuracy == 0.0
    assert result.per_sentiment["neutral"].f1 == 0.0
    assert result.per_sentiment["positive"].f1 == 0.0


# --- Rule 5: an out-of-vocabulary label is a bug, not a score --------------


def test_an_unknown_predicted_sentiment_is_rejected() -> None:
    """Structured model output is validated, never scored as if it were a label."""
    with pytest.raises(ValueError, match="mixed"):
        sentiment_metrics(["positive"], ["mixed"])


def test_an_unknown_gold_sentiment_is_rejected() -> None:
    with pytest.raises(ValueError, match="unlabelled"):
        sentiment_metrics(["unlabelled"], ["positive"])


def test_mismatched_lengths_raise_rather_than_scoring_a_prefix() -> None:
    with pytest.raises(ValueError, match="same length"):
        sentiment_metrics(GOLD, PREDICTED[:4])


def test_an_empty_benchmark_raises_rather_than_reporting_zero() -> None:
    with pytest.raises(ValueError, match="empty"):
        sentiment_metrics([], [])


def test_macro_f1_ignores_a_sentiment_absent_from_the_gold_labels() -> None:
    """Averaging in a sentiment the benchmark never contains would understate the score.

    The confusion matrix still shows it, so the absence stays visible.
    """
    result = sentiment_metrics(["positive", "neutral"], ["positive", "neutral"])
    assert result.macro_f1 == pytest.approx(1.0)
    assert result.per_sentiment["negative"].support == 0
    assert set(result.confusion) == {"positive", "neutral", "negative"}
