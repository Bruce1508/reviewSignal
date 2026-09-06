"""Job submission.

The `jobs` table owns lifecycle state; RQ is only transport
(`docs/data-model.md` §14). Keeping the record here means a queue-backend swap
does not change what the API reports.

Retry policy is configured here rather than left to the caller because
`docs/architecture.md` §13 makes `run → retry with backoff → dead-letter` mandatory
for every external and AI job, and `docs/deployment.md` §29 depends on it for the
"Google API unavailable" path.
"""

import uuid

from redis import Redis
from rq import Queue, Retry

from reviewsignal_api.core.config import get_settings
from reviewsignal_api.core.constants import DEFAULT_QUEUE_NAME
from reviewsignal_api.db.models import Job
from reviewsignal_worker.db import session_scope

# Backoff between retries. Sized for a transient Google 429/5xx: the quota window is
# per-minute, so retrying sooner than that just burns the remaining quota.
RETRY_BACKOFF_SECONDS = (30, 120, 300)


def get_queue() -> Queue:
    return Queue(DEFAULT_QUEUE_NAME, connection=Redis.from_url(get_settings().redis_url))


def retry_policy(max_attempts: int) -> Retry | None:
    """Translate total attempts into RQ's retry count.

    RQ counts retries *after* the first run, while `jobs.max_attempts` counts total
    executions, so the two differ by one. Getting this wrong makes `dead_letter`
    either unreachable or premature.
    """
    retries = max_attempts - 1
    if retries < 1:
        return None
    intervals = [
        RETRY_BACKOFF_SECONDS[min(i, len(RETRY_BACKOFF_SECONDS) - 1)] for i in range(retries)
    ]
    return Retry(max=retries, interval=intervals)


def enqueue(job_type: str, payload: dict | None = None, max_attempts: int = 3) -> uuid.UUID:
    """Record the job, then hand it to RQ. Returns the application job id."""
    with session_scope() as session:
        job = Job(
            job_type=job_type, status="queued", payload=payload or {}, max_attempts=max_attempts
        )
        session.add(job)
        session.flush()
        job_id = job.id

    get_queue().enqueue(
        "reviewsignal_worker.runner.run_job", str(job_id), retry=retry_policy(max_attempts)
    )
    return job_id
