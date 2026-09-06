"""Unit tests for multi-label classification metrics (`docs/evaluation.md` §5, §6).

Pure unit tests: in-memory label sets only, no database, no model. Every expected
number below is computed by hand in the comments so a failure points at the formula
rather than at another implementation.
"""

import pytest

from reviewsignal_api.ai.evaluation.metrics.classification import classification_metrics

# The worked example used by most cases below.
#
#   item  gold                        predicted
#   1     {wait_time, staff}          {wait_time}
#   2     {photo_quality}             {photo_quality, staff}
#   3     {wait_time}                 {}
#
# Per category (TP / FP / FN):
#   wait_time      1 / 0 / 1   P=1/1=1.0   R=1/2=0.5   F1=2(1)(.5)/1.5 = 0.666...
#   photo_quality  1 / 0 / 0   P=1.0       R=1.0       F1=1.0
#   staff          0 / 1 / 1   P=0/1=0.0   R=0/1=0.0   F1=0.0
#
# Micro  TP=2 FP=1 FN=2 -> P=2/3, R=2/4=0.5, F1=2TP/(2TP+FP+FN)=4/7
# Macro  P=(1.0+1.0+0.0)/3=2/3   R=(0.5+1.0+0.0)/3=0.5   F1=(0.666+1.0+0.0)/3=0.5555...
GOLD = [{"wait_time", "staff"}, {"photo_quality"}, {"wait_time"}]
PREDICTED = [{"wait_time"}, {"photo_quality", "staff"}, set()]


# --- Rule 1: micro aggregates over (item, label) pairs ------------------------


def test_micro_precision_counts_every_predicted_label() -> None:
    assert classification_metrics(GOLD, PREDICTED).micro.precision == pytest.approx(2 / 3)


def test_micro_recall_counts_every_gold_label() -> None:
    assert classification_metrics(GOLD, PREDICTED).micro.recall == pytest.approx(0.5)


def test_micro_f1_is_the_harmonic_mean_of_micro_precision_and_recall() -> None:
    assert classification_metrics(GOLD, PREDICTED).micro.f1 == pytest.approx(4 / 7)


# --- Rule 2: macro averages per-category scores, unweighted -------------------


def test_macro_precision_is_the_unweighted_mean_of_category_precisions() -> None:
    assert classification_metrics(GOLD, PREDICTED).macro.precision == pytest.approx(2 / 3)


def test_macro_recall_is_the_unweighted_mean_of_category_recalls() -> None:
    assert classification_metrics(GOLD, PREDICTED).macro.recall == pytest.approx(0.5)


def test_macro_f1_averages_category_f1s_rather_than_recombining_macro_p_and_r() -> None:
    """The distinction is the whole point of macro F1 (`evaluation.md` §5).

    Mean of per-category F1 is 0.5555...; recombining macro P and R would give
    2(2/3)(0.5)/(2/3+0.5) = 4/7 = 0.5714..., which is the micro value here.
    """
    macro = classification_metrics(GOLD, PREDICTED).macro
    assert macro.f1 == pytest.approx((2 / 3 + 1.0 + 0.0) / 3)
    assert macro.f1 != pytest.approx(4 / 7)


# --- Rule 3: per-category scores expose weak categories ----------------------


def test_per_category_reports_every_observed_label() -> None:
    per_category = classification_metrics(GOLD, PREDICTED).per_category
    assert set(per_category) == {"wait_time", "photo_quality", "staff"}


def test_a_partially_recalled_category_keeps_full_precision() -> None:
    wait_time = classification_metrics(GOLD, PREDICTED).per_category["wait_time"]
    assert wait_time.precision == pytest.approx(1.0)
    assert wait_time.recall == pytest.approx(0.5)
    assert wait_time.f1 == pytest.approx(2 / 3)


def test_a_category_predicted_only_where_it_is_wrong_scores_zero() -> None:
    staff = classification_metrics(GOLD, PREDICTED).per_category["staff"]
    assert staff.precision == 0.0
    assert staff.recall == 0.0
    assert staff.f1 == 0.0


def test_support_counts_gold_occurrences_not_predictions() -> None:
    per_category = classification_metrics(GOLD, PREDICTED).per_category
    assert per_category["wait_time"].support == 2
    assert per_category["staff"].support == 1
    assert per_category["photo_quality"].support == 1


def test_aggregate_support_is_the_total_gold_label_count() -> None:
    result = classification_metrics(GOLD, PREDICTED)
    assert result.micro.support == 4
    assert result.macro.support == 4


def test_item_count_reports_how_many_items_were_scored() -> None:
    assert classification_metrics(GOLD, PREDICTED).item_count == 3


def test_label_count_reports_the_width_of_the_macro_denominator() -> None:
    assert classification_metrics(GOLD, PREDICTED).label_count == 3


def test_a_hallucinated_category_widens_the_macro_denominator() -> None:
    """Macro averages over `gold | predicted`, so two runs are only comparable at
    equal `label_count` (`evaluation.md` §23, §24)."""
    invented = [{"wait_time"}, {"photo_quality", "staff", "parking"}, set()]

    grounded = classification_metrics(GOLD, PREDICTED)
    hallucinating = classification_metrics(GOLD, invented)

    assert grounded.label_count == 3
    assert hallucinating.label_count == 4
    # parking is TP=0 FP=1 FN=0 -> F1 0.0, averaged into a denominator of 4 not 3.
    assert hallucinating.macro.f1 < grounded.macro.f1


# --- Rule 4: degenerate inputs score zero rather than dividing by zero -------


def test_predicting_nothing_anywhere_scores_zero_without_raising() -> None:
    result = classification_metrics([{"wait_time"}, {"staff"}], [set(), set()])
    assert result.micro.precision == 0.0
    assert result.micro.recall == 0.0
    assert result.micro.f1 == 0.0


def test_a_category_never_in_gold_drags_macro_recall_down() -> None:
    """Predicting an unseen category is penalised, not silently ignored."""
    result = classification_metrics([{"wait_time"}], [{"wait_time", "invented"}])
    assert result.per_category["invented"].support == 0
    assert result.per_category["invented"].recall == 0.0
    assert result.macro.recall == pytest.approx(0.5)


def test_a_perfect_prediction_scores_one_across_the_board() -> None:
    result = classification_metrics(GOLD, GOLD)
    assert result.micro.f1 == pytest.approx(1.0)
    assert result.macro.f1 == pytest.approx(1.0)


# --- Rule 5: mismatched or empty input is a bug, not a score ----------------


def test_mismatched_lengths_raise_rather_than_scoring_a_prefix() -> None:
    with pytest.raises(ValueError, match="same length"):
        classification_metrics(GOLD, PREDICTED[:2])


def test_an_empty_benchmark_raises_rather_than_reporting_zero() -> None:
    with pytest.raises(ValueError, match="empty"):
        classification_metrics([], [])


def test_a_benchmark_where_nothing_is_labelled_scores_zero_without_dividing_by_zero() -> None:
    """Rating-only reviews can legitimately carry no aspects at all."""
    result = classification_metrics([set(), set()], [set(), set()])
    assert result.per_category == {}
    assert result.macro.f1 == 0.0
    assert result.micro.f1 == 0.0
    assert result.item_count == 2
