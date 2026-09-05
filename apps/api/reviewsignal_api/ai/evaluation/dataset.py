"""The human benchmark contract (`docs/evaluation.md` §2, §3).

The benchmark is ground truth, so it is validated rather than coerced: a malformed
file must surface as an error, never as a silently smaller evaluation run. Version
metadata travels with the labels so a run can name exactly what it scored, and
ground truth is replaced by adding a new file, never by rewriting one in place.

The dataset lives on disk rather than in PostgreSQL because `data-model.md` §16
references it by `dataset_version` string and defines no benchmark entity.
"""

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from reviewsignal_api.db.models import SENTIMENTS


class GoldAspect(BaseModel):
    """One human-assigned aspect label and its sentiment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category_id: str
    sentiment: str

    @field_validator("sentiment")
    @classmethod
    def _sentiment_is_known(cls, value: str) -> str:
        if value not in SENTIMENTS:
            raise ValueError(f"unknown sentiment: {value!r}")
        return value


class BenchmarkItem(BaseModel):
    """One labelled review. An empty `aspects` is valid: rating-only reviews exist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    review_id: str
    text: str
    aspects: tuple[GoldAspect, ...] = ()

    @model_validator(mode="after")
    def _one_sentiment_per_category(self) -> "BenchmarkItem":
        labelled = [aspect.category_id for aspect in self.aspects]
        if len(labelled) != len(set(labelled)):
            raise ValueError(f"duplicate category_id on review {self.review_id!r}")
        return self

    @property
    def category_ids(self) -> set[str]:
        return {aspect.category_id for aspect in self.aspects}

    @property
    def sentiment_by_category(self) -> dict[str, str]:
        return {aspect.category_id: aspect.sentiment for aspect in self.aspects}


class BenchmarkDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str
    labeled_at: date
    labeler: str
    taxonomy_version: str | None = None
    notes: str | None = None
    items: tuple[BenchmarkItem, ...]

    @model_validator(mode="after")
    def _items_are_present_and_distinct(self) -> "BenchmarkDataset":
        if not self.items:
            raise ValueError("benchmark has no items")
        review_ids = [item.review_id for item in self.items]
        if len(review_ids) != len(set(review_ids)):
            raise ValueError("duplicate review_id in benchmark")
        return self

    @property
    def gold_categories(self) -> list[set[str]]:
        """Gold label sets in item order, ready for `classification_metrics`."""
        return [item.category_ids for item in self.items]


def load_benchmark(path: Path) -> BenchmarkDataset:
    """Read and validate a benchmark file. A missing file raises, never returns empty."""
    return BenchmarkDataset.model_validate_json(path.read_text())
