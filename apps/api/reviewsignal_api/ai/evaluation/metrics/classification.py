"""Multi-label classification metrics (`docs/evaluation.md` §5, §6).

Pure functions over label sets. Nothing here knows about reviews, taxonomy nodes, or
the database, so the harness can be exercised before a classifier exists.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from reviewsignal_api.ai.evaluation.metrics.scores import Score, mean, prf_score


@dataclass(frozen=True)
class ClassificationMetrics:
    micro: Score
    macro: Score
    per_category: dict[str, Score]
    item_count: int
    # How many labels `macro` averaged over. It varies with what the model predicted,
    # so an `evaluation.md` §23 regression comparison must check it before comparing.
    label_count: int


def classification_metrics(
    gold: Sequence[Collection[str]],
    predicted: Sequence[Collection[str]],
) -> ClassificationMetrics:
    """Score multi-label predictions against gold labels, one label set per item.

    The label universe is whatever appears in `gold` or `predicted`, so a category the
    model invents is scored and penalised rather than silently dropped.
    """
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted must have the same length")
    if not gold:
        raise ValueError("cannot evaluate an empty benchmark")

    labels = sorted(
        {label for item in gold for label in item} | {label for item in predicted for label in item}
    )

    per_category: dict[str, Score] = {}
    micro_true_positives = micro_false_positives = micro_false_negatives = 0

    for label in labels:
        true_positives = false_positives = false_negatives = 0
        for gold_item, predicted_item in zip(gold, predicted, strict=True):
            in_gold = label in gold_item
            in_predicted = label in predicted_item
            if in_gold and in_predicted:
                true_positives += 1
            elif in_predicted:
                false_positives += 1
            elif in_gold:
                false_negatives += 1

        per_category[label] = prf_score(true_positives, false_positives, false_negatives)
        micro_true_positives += true_positives
        micro_false_positives += false_positives
        micro_false_negatives += false_negatives

    micro = prf_score(micro_true_positives, micro_false_positives, micro_false_negatives)
    scores = list(per_category.values())
    macro = Score(
        precision=mean([score.precision for score in scores]),
        recall=mean([score.recall for score in scores]),
        f1=mean([score.f1 for score in scores]),
        support=micro.support,
    )
    return ClassificationMetrics(
        micro=micro,
        macro=macro,
        per_category=per_category,
        item_count=len(gold),
        label_count=len(labels),
    )
