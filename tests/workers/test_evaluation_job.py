"""The `evaluation_run` job handler (`docs/api-spec.md` §10, `docs/evaluation.md` §30).

The handler is reachable only once a predictor is registered; the route rejects the
request before queueing otherwise. These tests register a stub so the recorded shape is
still pinned down now, rather than after a real classifier lands.
"""

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text

from reviewsignal_api.ai.evaluation.protocols import PredictedAspect
from reviewsignal_api.ai.evaluation.registry import PREDICTORS
from reviewsignal_api.db.models import EvaluationRun, Job
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.errors import PermanentJobError
from reviewsignal_worker.jobs import HANDLERS
from reviewsignal_worker.jobs.evaluation import evaluation_run

BENCHMARK = {
    "dataset_version": "v0-test",
    "labeled_at": "2026-01-01",
    "labeler": "test-fixture",
    "taxonomy_version": "taxonomy-test",
    "items": [
        {
            "review_id": "t-1",
            "text": "Sharp prints, slow service.",
            "aspects": [{"category_id": "cat-a", "sentiment": "positive"}],
        },
        {
            "review_id": "t-2",
            "text": "Friendly staff.",
            "aspects": [{"category_id": "cat-a", "sentiment": "positive"}],
        },
    ],
}


class StubPredictor:
    """Always finds `cat-a` and calls it positive, which the benchmark agrees with."""

    name = "stub-classifier"
    version = "v0"

    def predict(self, item: object) -> list[PredictedAspect]:
        return [PredictedAspect(category_id="cat-a", sentiment="positive", confidence=0.9)]


@pytest.fixture
def benchmark_file(tmp_path: Path) -> Path:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(BENCHMARK), encoding="utf-8")
    return path


@pytest.fixture
def registered_predictor() -> Iterator[None]:
    PREDICTORS["classification"] = StubPredictor()
    yield
    PREDICTORS.pop("classification", None)


def _configure_benchmark(monkeypatch: pytest.MonkeyPatch, path: Path | str) -> None:
    """Point the handler at a benchmark without mutating the cached global settings."""
    monkeypatch.setattr("reviewsignal_worker.jobs.evaluation.benchmark_path", lambda: str(path))


def _queued_job() -> uuid.UUID:
    """`evaluation_runs.job_id` is a foreign key, so the run needs a real job."""
    with session_scope() as session:
        job = Job(job_type="evaluation_run", status="running", payload={}, max_attempts=3)
        session.add(job)
        session.flush()
        return job.id


def test_the_handler_is_registered_under_its_job_type() -> None:
    assert HANDLERS["evaluation_run"] is evaluation_run


def test_a_run_records_exactly_one_row_with_every_family(
    monkeypatch: pytest.MonkeyPatch, benchmark_file: Path, registered_predictor: None
) -> None:
    """One run is one row (`docs/data-model.md` §16), not one row per metric family."""
    _configure_benchmark(monkeypatch, benchmark_file)

    evaluation_run({"evaluation_type": "classification"}, _queued_job())

    with session_scope() as session:
        rows = session.query(EvaluationRun).all()
        assert len(rows) == 1
        run = rows[0]
        assert run.evaluation_type == "classification"
        assert run.model_name == "stub-classifier"
        assert run.dataset_version == "v0-test"
        assert run.taxonomy_version == "taxonomy-test"
        assert set(run.metrics) == {"classification", "sentiment", "calibration"}


def test_the_recorded_type_names_the_workflow_not_a_metric_family(
    monkeypatch: pytest.MonkeyPatch, benchmark_file: Path, registered_predictor: None
) -> None:
    """`evaluation_type` is the workflow evaluated; sentiment/calibration are families."""
    _configure_benchmark(monkeypatch, benchmark_file)

    evaluation_run({"evaluation_type": "classification"}, _queued_job())

    with session_scope() as session:
        types = list(session.execute(text("SELECT evaluation_type FROM evaluation_runs")).scalars())
    assert types == ["classification"]


def test_an_unregistered_predictor_fails_the_job(
    monkeypatch: pytest.MonkeyPatch, benchmark_file: Path
) -> None:
    _configure_benchmark(monkeypatch, benchmark_file)

    with pytest.raises(PermanentJobError):
        evaluation_run({"evaluation_type": "classification"}, _queued_job())


def test_an_unconfigured_benchmark_fails_the_job_rather_than_scoring_nothing(
    monkeypatch: pytest.MonkeyPatch, registered_predictor: None
) -> None:
    """A missing benchmark must surface, never produce an empty-but-successful run."""
    _configure_benchmark(monkeypatch, "")

    with pytest.raises(PermanentJobError, match="benchmark"):
        evaluation_run({"evaluation_type": "classification"}, _queued_job())


def test_a_missing_evaluation_type_in_the_payload_fails_the_job(
    monkeypatch: pytest.MonkeyPatch, benchmark_file: Path, registered_predictor: None
) -> None:
    _configure_benchmark(monkeypatch, benchmark_file)

    with pytest.raises(KeyError):
        evaluation_run({}, _queued_job())


def test_a_retried_job_does_not_record_a_second_run(
    monkeypatch: pytest.MonkeyPatch, benchmark_file: Path, registered_predictor: None
) -> None:
    """`record` is insert-only, so this guard is what stops a requeue adding a second
    baseline to the history `docs/evaluation.md` §23 compares against."""
    _configure_benchmark(monkeypatch, benchmark_file)
    job_id = _queued_job()

    evaluation_run({"evaluation_type": "classification"}, job_id)
    evaluation_run({"evaluation_type": "classification"}, job_id)

    with session_scope() as session:
        rows = session.query(EvaluationRun).all()
        assert len(rows) == 1
        assert rows[0].job_id == job_id


def test_a_separate_job_records_its_own_run(
    monkeypatch: pytest.MonkeyPatch, benchmark_file: Path, registered_predictor: None
) -> None:
    """The guard keys on the job, so it must not suppress a genuinely new run."""
    _configure_benchmark(monkeypatch, benchmark_file)

    evaluation_run({"evaluation_type": "classification"}, _queued_job())
    evaluation_run({"evaluation_type": "classification"}, _queued_job())

    with session_scope() as session:
        assert session.query(EvaluationRun).count() == 2
