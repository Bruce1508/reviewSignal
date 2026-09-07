"""Evaluation run persistence (`docs/data-model.md` §16, `docs/evaluation.md` §30)."""

import uuid

from sqlalchemy.orm import Session

from reviewsignal_api.ai.evaluation.metrics.calibration import calibration_metrics
from reviewsignal_api.ai.evaluation.metrics.classification import classification_metrics
from reviewsignal_api.ai.evaluation.metrics.sentiment import sentiment_metrics
from reviewsignal_api.ai.evaluation.runner import EvaluationResult
from reviewsignal_api.db.models import EvaluationRun, Job, TaxonomyVersion
from reviewsignal_api.repositories.evaluation_runs import EvaluationRunRepository


def make_result(*, full: bool = False, taxonomy_version: str | None = None) -> EvaluationResult:
    return EvaluationResult(
        dataset_version="v0-synthetic",
        taxonomy_version=taxonomy_version,
        model_name="stub-classifier",
        model_version="v1",
        classification=classification_metrics([{"wait_time"}, {"pricing"}], [{"wait_time"}, set()]),
        sentiment=sentiment_metrics(["positive"], ["negative"]) if full else None,
        calibration=calibration_metrics([0.8], [True]) if full else None,
    )


def reread(session: Session, run: EvaluationRun) -> EvaluationRun:
    session.flush()
    session.expire(run)
    return session.get(EvaluationRun, run.id)  # type: ignore[return-value]


def test_record_persists_the_run_identity(session: Session) -> None:
    run = EvaluationRunRepository(session).record(make_result(), evaluation_type="classification")

    stored = reread(session, run)
    assert stored.evaluation_type == "classification"
    assert stored.model_name == "stub-classifier"
    assert stored.model_version == "v1"
    assert stored.dataset_version == "v0-synthetic"
    assert stored.created_at is not None


def test_metrics_round_trip_through_jsonb(session: Session) -> None:
    """The payload is nested dataclasses; JSONB must return it unchanged."""
    run = EvaluationRunRepository(session).record(make_result(), evaluation_type="classification")

    metrics = reread(session, run).metrics
    assert metrics["classification"]["micro"]["support"] == 2
    assert metrics["classification"]["per_category"]["pricing"]["recall"] == 0.0
    assert metrics["classification"]["per_category"]["wait_time"]["f1"] == 1.0


def test_absent_metric_families_persist_as_null(session: Session) -> None:
    run = EvaluationRunRepository(session).record(make_result(), evaluation_type="classification")

    metrics = reread(session, run).metrics
    assert metrics["sentiment"] is None
    assert metrics["calibration"] is None


def test_a_full_result_persists_every_metric_family(session: Session) -> None:
    run = EvaluationRunRepository(session).record(
        make_result(full=True), evaluation_type="baseline"
    )

    metrics = reread(session, run).metrics
    assert metrics["sentiment"]["confusion"]["positive"]["negative"] == 1
    buckets = metrics["calibration"]["buckets"]
    # A confidence of 0.8 lands in the [0.8, 0.9) bucket, not in the last one.
    assert buckets[8]["count"] == 1
    assert sum(bucket["count"] for bucket in buckets) == 1


def test_notes_default_to_absent(session: Session) -> None:
    run = EvaluationRunRepository(session).record(make_result(), evaluation_type="classification")

    assert reread(session, run).notes is None


def test_notes_are_stored_when_given(session: Session) -> None:
    run = EvaluationRunRepository(session).record(
        make_result(), evaluation_type="classification", notes="synthetic smoke run"
    )

    assert reread(session, run).notes == "synthetic smoke run"


def test_a_run_can_be_tied_to_a_taxonomy_version(session: Session) -> None:
    version = TaxonomyVersion(version_number=1, status="candidate", created_by="tester")
    session.add(version)
    session.flush()

    run = EvaluationRunRepository(session).record(
        make_result(), evaluation_type="classification", taxonomy_version_id=version.id
    )

    assert reread(session, run).taxonomy_version_id == version.id


def test_a_run_without_a_taxonomy_version_is_allowed(session: Session) -> None:
    """Phase 0 evaluates before any taxonomy exists."""
    run = EvaluationRunRepository(session).record(make_result(), evaluation_type="classification")

    assert reread(session, run).taxonomy_version_id is None


def test_the_benchmark_taxonomy_version_is_recorded_as_provenance(session: Session) -> None:
    """Phase 0 has no `taxonomy_versions` rows, so the benchmark's own string is the
    only taxonomy identity a run can carry (`evaluation.md` §30)."""
    run = EvaluationRunRepository(session).record(
        make_result(taxonomy_version="taxonomy-2026-09-01"), evaluation_type="classification"
    )

    stored = reread(session, run)
    assert stored.taxonomy_version == "taxonomy-2026-09-01"
    assert stored.taxonomy_version_id is None


def test_taxonomy_provenance_is_independent_of_the_foreign_key(session: Session) -> None:
    """The string says what the labels were made against; the key points at a row."""
    version = TaxonomyVersion(version_number=1, status="candidate", created_by="tester")
    session.add(version)
    session.flush()

    run = EvaluationRunRepository(session).record(
        make_result(taxonomy_version="taxonomy-2026-09-01"),
        evaluation_type="classification",
        taxonomy_version_id=version.id,
    )

    stored = reread(session, run)
    assert stored.taxonomy_version == "taxonomy-2026-09-01"
    assert stored.taxonomy_version_id == version.id


def test_a_benchmark_without_a_taxonomy_version_records_none(session: Session) -> None:
    run = EvaluationRunRepository(session).record(make_result(), evaluation_type="classification")

    assert reread(session, run).taxonomy_version is None


def test_each_record_creates_a_distinct_run(session: Session) -> None:
    """Ground truth is never rewritten in place; runs accumulate (`evaluation.md` §3)."""
    repo = EvaluationRunRepository(session)

    first = repo.record(make_result(), evaluation_type="classification")
    second = repo.record(make_result(), evaluation_type="classification")

    session.flush()
    assert first.id != second.id
    assert isinstance(first.id, uuid.UUID)


def test_pruning_a_job_keeps_its_run_and_only_clears_the_link(session: Session) -> None:
    """`docs/data-model.md` §24 requires retaining evaluation runs and does not list
    jobs, so jobs are prunable and a run has to outlive the job that produced it.
    Without `ON DELETE SET NULL` the delete fails instead, making jobs unprunable."""
    job = Job(job_type="evaluation_run", status="succeeded", payload={}, max_attempts=3)
    session.add(job)
    session.flush()
    run = EvaluationRunRepository(session).record(
        make_result(), evaluation_type="classification", job_id=job.id
    )

    session.delete(job)

    stored = reread(session, run)
    assert stored is not None
    assert stored.job_id is None
