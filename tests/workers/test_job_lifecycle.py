"""Job lifecycle: queued → running → succeeded / failed → dead_letter.

Vocabulary from `docs/data-model.md` §14; retry-then-DLQ from
`docs/architecture.md` §13. RQ is bypassed here so the lifecycle is tested
independently of the queue backend, which is exactly how the schema models it.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import Job
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.errors import PermanentJobError
from reviewsignal_worker.jobs import HANDLERS
from reviewsignal_worker.runner import run_job


def _record(
    job_type: str = "noop", payload: dict | None = None, max_attempts: int = 3
) -> uuid.UUID:
    with session_scope() as session:
        job = Job(
            job_type=job_type, status="queued", payload=payload or {}, max_attempts=max_attempts
        )
        session.add(job)
        session.flush()
        return job.id


def _reload(session: Session, job_id: uuid.UUID) -> Job:
    session.expire_all()
    job = session.get(Job, job_id)
    assert job is not None
    return job


def test_successful_job_is_marked_succeeded(session: Session) -> None:
    job_id = _record()

    run_job(str(job_id))

    job = _reload(session, job_id)
    assert job.status == "succeeded"
    assert job.attempt_count == 1
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.error_message is None


def test_failing_job_with_attempts_remaining_is_marked_failed(session: Session) -> None:
    job_id = _record(payload={"fail": True}, max_attempts=3)

    with pytest.raises(RuntimeError):
        run_job(str(job_id))

    job = _reload(session, job_id)
    assert job.status == "failed"
    assert job.attempt_count == 1
    assert "Intentional failure" in (job.error_message or "")


def test_failing_job_moves_to_dead_letter_once_attempts_are_exhausted(session: Session) -> None:
    job_id = _record(payload={"fail": True}, max_attempts=1)

    with pytest.raises(RuntimeError):
        run_job(str(job_id))

    assert _reload(session, job_id).status == "dead_letter"


def test_retries_accumulate_until_the_dead_letter_threshold(session: Session) -> None:
    job_id = _record(payload={"fail": True}, max_attempts=2)

    with pytest.raises(RuntimeError):
        run_job(str(job_id))
    assert _reload(session, job_id).status == "failed"

    with pytest.raises(RuntimeError):
        run_job(str(job_id))

    job = _reload(session, job_id)
    assert job.status == "dead_letter"
    assert job.attempt_count == 2


def test_unknown_job_type_fails_the_job_rather_than_crashing_silently(session: Session) -> None:
    job_id = _record(job_type="not-registered", max_attempts=1)

    with pytest.raises(LookupError):
        run_job(str(job_id))

    job = _reload(session, job_id)
    assert job.status == "dead_letter"
    assert "No handler registered" in (job.error_message or "")


def test_missing_job_record_is_a_no_op(session: Session) -> None:
    run_job(str(uuid.uuid4()))


def test_a_permanent_failure_dead_letters_on_its_first_attempt(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No retry could change this outcome, so the backoff schedule is skipped
    (`docs/architecture.md` §13). `run_job` must not re-raise either: raising hands
    the job back to RQ, which would run the identical failure twice more."""

    def permanently_broken(payload: dict, job_id: uuid.UUID) -> None:
        raise PermanentJobError("No predictor is registered.")

    monkeypatch.setitem(HANDLERS, "permanently_broken", permanently_broken)
    job_id = _record(job_type="permanently_broken", max_attempts=3)

    run_job(str(job_id))

    job = _reload(session, job_id)
    assert job.status == "dead_letter"
    assert job.attempt_count == 1
    assert "No predictor is registered." in (job.error_message or "")
