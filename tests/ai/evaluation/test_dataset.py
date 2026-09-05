"""Unit tests for the benchmark dataset contract (`docs/evaluation.md` §2, §3).

The benchmark is human ground truth, so the loader validates rather than coerces:
a malformed file is a labelling bug that must surface, never a silently smaller run.
"""

import json
from pathlib import Path

import pytest

from reviewsignal_api.ai.evaluation.dataset import BenchmarkDataset, load_benchmark

SHIPPED = Path(__file__).parents[3] / "data" / "benchmarks" / "v0-synthetic.json"

VALID = {
    "dataset_version": "v-test",
    "taxonomy_version": None,
    "labeled_at": "2026-09-05",
    "labeler": "tester",
    "notes": "fixture",
    "items": [
        {
            "review_id": "r1",
            "text": "The wait was long but the prints look great.",
            "aspects": [
                {"category_id": "wait_time", "sentiment": "negative"},
                {"category_id": "photo_quality", "sentiment": "positive"},
            ],
        },
        {"review_id": "r2", "text": "Fine.", "aspects": []},
    ],
}


def write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(payload))
    return path


# --- Rule 1: version metadata travels with the ground truth -----------------


def test_loading_keeps_the_version_metadata(tmp_path: Path) -> None:
    dataset = load_benchmark(write(tmp_path, VALID))
    assert dataset.dataset_version == "v-test"
    assert dataset.labeler == "tester"
    assert dataset.labeled_at.isoformat() == "2026-09-05"
    assert dataset.notes == "fixture"


def test_taxonomy_version_may_be_absent_before_a_taxonomy_exists(tmp_path: Path) -> None:
    assert load_benchmark(write(tmp_path, VALID)).taxonomy_version is None


# --- Rule 2: items and gold labels ------------------------------------------


def test_items_load_in_file_order(tmp_path: Path) -> None:
    dataset = load_benchmark(write(tmp_path, VALID))
    assert [item.review_id for item in dataset.items] == ["r1", "r2"]


def test_gold_categories_align_one_set_per_item(tmp_path: Path) -> None:
    dataset = load_benchmark(write(tmp_path, VALID))
    assert dataset.gold_categories == [{"wait_time", "photo_quality"}, set()]


def test_an_item_may_carry_no_aspects_at_all(tmp_path: Path) -> None:
    """A rating-only review is legitimate ground truth, not a labelling gap."""
    dataset = load_benchmark(write(tmp_path, VALID))
    assert dataset.items[1].aspects == ()


def test_sentiment_is_readable_per_category(tmp_path: Path) -> None:
    dataset = load_benchmark(write(tmp_path, VALID))
    assert dataset.items[0].sentiment_by_category == {
        "wait_time": "negative",
        "photo_quality": "positive",
    }


# --- Rule 3: the shipped synthetic dataset actually loads -------------------


def test_the_shipped_synthetic_benchmark_loads() -> None:
    dataset = load_benchmark(SHIPPED)
    assert isinstance(dataset, BenchmarkDataset)
    assert dataset.items


def test_the_shipped_synthetic_benchmark_is_labelled_as_synthetic() -> None:
    """Nothing here may be mistaken for measured results on real reviews."""
    dataset = load_benchmark(SHIPPED)
    assert "synthetic" in dataset.dataset_version
    assert dataset.notes is not None
    assert "synthetic" in dataset.notes.lower()


def test_the_shipped_synthetic_benchmark_exercises_every_sentiment() -> None:
    dataset = load_benchmark(SHIPPED)
    used = {aspect.sentiment for item in dataset.items for aspect in item.aspects}
    assert used == {"positive", "neutral", "negative"}


# --- Rule 4: ground truth is validated, never coerced ----------------------


def test_an_unknown_sentiment_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID))
    payload["items"][0]["aspects"][0]["sentiment"] = "mixed"
    with pytest.raises(ValueError, match="unknown sentiment"):
        load_benchmark(write(tmp_path, payload))


def test_a_duplicate_review_id_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID))
    payload["items"][1]["review_id"] = "r1"
    with pytest.raises(ValueError, match="duplicate review_id"):
        load_benchmark(write(tmp_path, payload))


def test_the_same_category_labelled_twice_on_one_item_is_rejected(tmp_path: Path) -> None:
    """Two sentiments for one aspect is a labelling contradiction, not extra data."""
    payload = json.loads(json.dumps(VALID))
    payload["items"][0]["aspects"].append({"category_id": "wait_time", "sentiment": "positive"})
    with pytest.raises(ValueError, match="duplicate category_id"):
        load_benchmark(write(tmp_path, payload))


def test_a_benchmark_with_no_items_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID))
    payload["items"] = []
    with pytest.raises(ValueError, match="no items"):
        load_benchmark(write(tmp_path, payload))


def test_missing_version_metadata_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID))
    del payload["dataset_version"]
    with pytest.raises(ValueError, match="dataset_version"):
        load_benchmark(write(tmp_path, payload))


def test_a_missing_file_raises_rather_than_returning_an_empty_dataset(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_benchmark(tmp_path / "absent.json")


def test_an_unrecognised_field_on_an_item_is_rejected(tmp_path: Path) -> None:
    """A typo'd `aspects` key must not read as a legitimate rating-only review."""
    payload = json.loads(json.dumps(VALID))
    item = payload["items"][0]
    item["apsects"] = item.pop("aspects")
    with pytest.raises(ValueError, match="apsects"):
        load_benchmark(write(tmp_path, payload))


def test_an_unrecognised_field_on_an_aspect_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID))
    payload["items"][0]["aspects"][0]["sentimnet"] = "positive"
    with pytest.raises(ValueError, match="sentimnet"):
        load_benchmark(write(tmp_path, payload))


def test_an_unrecognised_field_on_the_dataset_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(VALID))
    payload["dataset_vresion"] = "v-typo"
    with pytest.raises(ValueError, match="dataset_vresion"):
        load_benchmark(write(tmp_path, payload))
