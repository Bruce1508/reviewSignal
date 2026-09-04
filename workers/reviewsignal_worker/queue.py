"""Job submission.

The `jobs` table owns lifecycle state; RQ is only transport
(`docs/data-model.md` §14). Keeping the record here means a queue-backend swap
does not change what the API reports.
"""

import uuid

from redis import Redis
from rq import Queue

from reviewsignal_api.core.config import get_settings
from reviewsignal_api.core.constants import DEFAULT_QUEUE_NAME
from reviewsignal_api.db.models import Job
from reviewsignal_worker.db import session_scope


def get_queue() -> Queue:
    return Queue(DEFAULT_QUEUE_NAME, connection=Redis.from_url(get_settings().redis_url))


def enqueue(job_type: str, payload: dict | None = None, max_attempts: int = 3) -> uuid.UUID:
    """Record the job, then hand it to RQ. Returns the application job id."""
    with session_scope() as session:
        job = Job(job_type=job_type, status="queued", payload=payload or {},
                  max_attempts=max_attempts)
        session.add(job)
        session.flush()
        job_id = job.id

    get_queue().enqueue("reviewsignal_worker.runner.run_job", str(job_id))
    return job_id
