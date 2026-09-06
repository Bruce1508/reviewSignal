"""Unit tests for the evaluation runner (`docs/evaluation.md` §5, §7, §9, §30).

The runner is driven by a stub predictor so the harness is provable before the real
classifier exists (PRD §10 puts the harness in Phase 0 and the classifier in Phase 1).
"""

import json

import pytest

from reviewsignal_api.ai.evaluation.dataset import BenchmarkDataset, BenchmarkItem
from reviewsignal_api.ai.evaluation.protocols import PredictedAspect
from reviewsignal_api.ai.evaluation.runner import run_evaluation

DATASET = BenchmarkDataset.model_validate(
    {
        "dataset_version": "v-test",
        "labeled_at": "2026-09-05",
        "labeler": "tester",
        "taxonomy_version": "tax-1",
        "items": [
            {
                "review_id": "r1",
                "text": "Long wait, lovely prints.",
                "aspects": [
                    {"category_id": "wait_time", "sentiment": "negative"},
                    {"category_id": "photo_quality", "sentiment": "positive"},
                ],
            },
            {
                "review_id": "r2",
                "text": "Too expensive.",
                "aspects": [{"category_id": "pricing", "sentiment": "negative"}],
            },
            {"review_id": "r3", "text": "Fine.", "aspects": []},
        ],
    }
)

# Predictions, and what each one costs:
#
#   r1  wait_time/negative     0.9   right category, right sentiment
#   r1  staff_service/positive 0.4   category not in gold          -> false positive
#   r2  pricing/positive       0.8   right category, wrong sentiment
#   r3  (nothing)
#
# Categories  gold [{wait,photo}, {pricing}, {}]  pred [{wait,staff}, {pricing}, {}]
#   micro TP=2 FP=1 FN=1 -> P=R=F1=2/3, support 3
#
# Sentiment is scored on gold-and-predicted categories only: wait_time (hit) and
# pricing (miss) -> accuracy 1/2.
#
# Calibration counts a prediction correct only when category AND sentiment are right:
#   [0.9 True, 0.4 False, 0.8 False]
#   Brier = (0.01 + 0.16 + 0.64) / 3 = 0.27
PREDICTIONS = {
    "r1": [
        PredictedAspect(category_id="wait_time", sentiment="negative", confidence=0.9),
        PredictedAspect(category_id="staff_service", sentiment="positive", confidence=0.4),
    ],
    "r2": [PredictedAspect(category_id="pricing", sentiment="positive", confidence=0.8)],
}


class StubPredictor:
    """Stands in for the Phase 1 classifier. Returns canned aspects per review."""

    name = "stub-classifier"
    version = "v1"

    def __init__(self, predictions: dict[str, list[PredictedAspect]]) -> None:
        self._predictions = predictions

    def predict(self, item: BenchmarkItem) -> list[PredictedAspect]:
        return self._predictions.get(item.review_id, [])


def run(predictions: dict[str, list[PredictedAspect]] | None = None):
    canned = PREDICTIONS if predictions is None else predictions
    return run_evaluation(DATASET, StubPredictor(canned))


# --- Rule 1: the run names exactly what it scored --------------------------


def test_the_result_carries_the_dataset_and_model_identity() -> None:
    """`evaluation_runs` (data-model.md §16) cannot be filled in without these."""
    result = run()
    assert result.dataset_version == "v-test"
    assert result.taxonomy_version == "tax-1"
    assert result.model_name == "stub-classifier"
    assert result.model_version == "v1"


# --- Rule 2: classification is scored over all items -----------------------


def test_classification_scores_every_item_including_unlabelled_ones() -> None:
    classification = run().classification
    assert classification.item_count == 3
    assert classification.micro.f1 == pytest.approx(2 / 3)
    assert classification.micro.support == 3


def test_a_category_the_predictor_invents_is_penalised() -> None:
    per_category = run().classification.per_category
    assert per_category["staff_service"].support == 0
    assert per_category["staff_service"].precision == 0.0


def test_a_gold_category_the_predictor_misses_scores_zero_recall() -> None:
    assert run().classification.per_category["photo_quality"].recall == 0.0


# --- Rule 3: sentiment is scored only where the category was found ---------


def test_sentiment_is_scored_on_categories_present_in_both_gold_and_prediction() -> None:
    """Otherwise a missed aspect would be counted twice: once as a category miss and
    again as a sentiment miss, when classification metrics already measure the first."""
    sentiment = run().sentiment
    assert sentiment is not None
    assert sentiment.item_count == 2
    assert sentiment.accuracy == pytest.approx(0.5)


def test_a_wrong_sentiment_on_a_correct_category_shows_in_the_confusion_matrix() -> None:
    sentiment = run().sentiment
    assert sentiment is not None
    assert sentiment.confusion["negative"]["positive"] == 1
    assert sentiment.confusion["negative"]["negative"] == 1


# --- Rule 4: calibration covers every prediction the model made -----------


def test_calibration_scores_every_predicted_aspect() -> None:
    calibration = run().calibration
    assert calibration is not None
    assert calibration.item_count == 3


def test_a_prediction_counts_as_correct_only_when_category_and_sentiment_both_match() -> None:
    calibration = run().calibration
    assert calibration is not None
    assert calibration.brier_score == pytest.approx(0.27)


# --- Rule 5: an unmeasurable metric is reported as absent, not as zero ----


def test_a_predictor_that_predicts_nothing_still_produces_classification_metrics() -> None:
    result = run({})
    assert result.classification.micro.recall == 0.0
    assert result.classification.item_count == 3


def test_sentiment_and_calibration_are_absent_when_there_is_nothing_to_score() -> None:
    """Reporting 0.0 would claim a measurement that was never made."""
    result = run({})
    assert result.sentiment is None
    assert result.calibration is None


def test_sentiment_is_absent_when_no_predicted_category_was_correct() -> None:
    result = run({"r1": [PredictedAspect("invented", "positive", 0.5)]})
    assert result.sentiment is None
    assert result.calibration is not None


# --- Rule 6: structured predictor output is validated --------------------


def test_a_duplicate_category_in_one_prediction_is_rejected() -> None:
    predictions = {
        "r1": [
            PredictedAspect("wait_time", "negative", 0.9),
            PredictedAspect("wait_time", "positive", 0.8),
        ]
    }
    with pytest.raises(ValueError, match="duplicate category_id"):
        run(predictions)


def test_an_unknown_predicted_sentiment_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown sentiment"):
        run({"r1": [PredictedAspect("wait_time", "mixed", 0.9)]})


def test_a_confidence_outside_zero_to_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        run({"r1": [PredictedAspect("wait_time", "negative", 1.4)]})


# --- Rule 7: the result can be persisted as `evaluation_runs.metrics` -----


def test_the_metrics_payload_is_json_serialisable() -> None:
    payload = run().metrics_payload()
    assert json.loads(json.dumps(payload))["classification"]["micro"]["f1"] == pytest.approx(2 / 3)


def test_the_metrics_payload_records_absent_metrics_as_null() -> None:
    payload = run({}).metrics_payload()
    assert payload["sentiment"] is None
    assert payload["calibration"] is None


def test_the_metrics_payload_keeps_per_category_detail() -> None:
    """Per-category scores are what reveal a weak category (`evaluation.md` §6)."""
    payload = run().metrics_payload()
    assert payload["classification"]["per_category"]["photo_quality"]["support"] == 1
