"""Retry-with-backoff, proven through a real queue and a real worker.

`tests/workers/test_job_lifecycle.py` drives the state machine by calling `run_job`
directly, which proves the transitions but not that anything performs them. This file
covers the missing half: that RQ actually re-executes a failing job and that the
attempt arithmetic lands on `dead_letter` exactly once
(`docs/architecture.md` §13, `docs/deployment.md` §29).
"""

import uuid

import pytest
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy.orm import Session

from reviewsignal_api.core.config import get_settings
from reviewsignal_api.core.constants import DEFAULT_QUEUE_NAME
from reviewsignal_api.db.models import Job
from reviewsignal_worker import queue as queue_module
from reviewsignal_worker.queue import enqueue, retry_policy


def test_retry_policy_leaves_one_run_for_the_first_attempt() -> None:
    """max_attempts counts total runs; RQ counts retries after the first."""
    policy = retry_policy(3)
    assert policy is not None
    assert policy.max == 2


def test_a_single_attempt_configures_no_retry() -> None:
    assert retry_policy(1) is None


def test_backoff_intervals_are_supplied_per_retry() -> None:
    policy = retry_policy(4)
    assert policy is not None
    assert policy.intervals == [30, 120, 300]


def test_more_attempts_than_tabulated_reuse_the_longest_backoff() -> None:
    policy = retry_policy(6)
    assert policy is not None
    assert policy.intervals == [30, 120, 300, 300, 300]


@pytest.fixture
def rq_queue() -> Queue:
    connection = Redis.from_url(get_settings().redis_url)
    queue = Queue(DEFAULT_QUEUE_NAME, connection=connection)
    queue.empty()
    return queue


def _reload(session: Session, job_id: uuid.UUID) -> Job:
    session.expire_all()
    job = session.get(Job, job_id)
    assert job is not None
    return job


def test_a_failing_job_is_retried_by_the_queue_and_lands_in_dead_letter(
    session: Session, rq_queue: Queue, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real failure path: enqueue → worker → retry → worker → dead_letter.

    Backoff is zeroed so the retry is requeued immediately instead of parked in the
    scheduled registry; the interval itself is covered by the unit tests above.
    """
    monkeypatch.setattr(queue_module, "RETRY_BACKOFF_SECONDS", (0, 0, 0))

    job_id = enqueue("noop", payload={"fail": True}, max_attempts=2)

    worker = SimpleWorker([rq_queue], connection=rq_queue.connection)
    worker.work(burst=True)

    job = _reload(session, job_id)
    assert job.attempt_count == 2, "the queue did not re-execute the failing job"
    assert job.status == "dead_letter"
    assert "Intentional failure" in (job.error_message or "")


def test_a_succeeding_job_runs_once_through_the_queue(session: Session, rq_queue: Queue) -> None:
    job_id = enqueue("noop", payload={}, max_attempts=3)

    SimpleWorker([rq_queue], connection=rq_queue.connection).work(burst=True)

    job = _reload(session, job_id)
    assert job.status == "succeeded"
    assert job.attempt_count == 1
