"""Job execution wrapper enforcing the documented lifecycle.

    queued → running → succeeded
                     → failed → (retries exhausted) → dead_letter

Lifecycle vocabulary is owned by `docs/data-model.md` §14; the retry-then-DLQ
chain by `docs/architecture.md` §13.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from reviewsignal_api.db.models import Job
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.errors import PermanentJobError
from reviewsignal_worker.jobs import HANDLERS

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def run_job(job_id: str) -> None:
    """Execute one recorded job and record its outcome."""
    key = uuid.UUID(job_id)

    with session_scope() as session:
        job = session.get(Job, key)
        if job is None:
            logger.error("Job %s not found", job_id)
            return
        job.status = "running"
        job.started_at = _now()
        job.attempt_count += 1
        job_type, payload, attempt, max_attempts = (
            job.job_type,
            dict(job.payload),
            job.attempt_count,
            job.max_attempts,
        )

    try:
        handler = _resolve(job_type)
        handler(payload, key)
    except PermanentJobError as exc:
        # Deliberately not re-raised: raising hands the job back to RQ, which would
        # run the identical failure twice more before reaching the dead letter this
        # attempt already earned (`docs/architecture.md` §13).
        _record_failure(key, exc, attempt, max_attempts, permanent=True)
    except Exception as exc:
        _record_failure(key, exc, attempt, max_attempts)
        raise
    else:
        _record_success(key)


def _record_success(key: uuid.UUID) -> None:
    with session_scope() as session:
        job = session.get(Job, key)
        if job is not None:
            job.status = "succeeded"
            job.finished_at = _now()
            job.error_message = None


def _resolve(job_type: str) -> Callable[[dict, uuid.UUID], None]:
    handler = HANDLERS.get(job_type)
    if handler is None:
        raise LookupError(f"No handler registered for job type '{job_type}'.")
    return handler


def _record_failure(
    key: uuid.UUID,
    exc: Exception,
    attempt: int,
    max_attempts: int,
    permanent: bool = False,
) -> None:
    exhausted = permanent or attempt >= max_attempts
    with session_scope() as session:
        job = session.get(Job, key)
        if job is None:
            return
        job.status = "dead_letter" if exhausted else "failed"
        job.finished_at = _now()
        job.error_message = f"{type(exc).__name__}: {exc}"
    logger.warning(
        "Job %s failed on attempt %s/%s%s",
        key,
        attempt,
        max_attempts,
        " — moved to dead_letter, permanently"
        if permanent
        else " — moved to dead_letter"
        if exhausted
        else "",
    )
