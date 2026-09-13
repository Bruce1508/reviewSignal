"""Job handler registry.

Handlers take a payload dict and the id of the job being run, and return nothing.
The job id is passed so a handler can make its own write idempotent across a retry.
Register new job types here so `runner.run_job` can resolve them by name.
"""

import uuid
from collections.abc import Callable

from reviewsignal_worker.jobs.evaluation import evaluation_run
from reviewsignal_worker.jobs.ingest import google_backfill, google_sync
from reviewsignal_worker.jobs.noop import noop
from reviewsignal_worker.jobs.taxonomy import taxonomy_generate

HANDLERS: dict[str, Callable[[dict, uuid.UUID], None]] = {
    "noop": noop,
    "google_backfill": google_backfill,
    "google_sync": google_sync,
    "evaluation_run": evaluation_run,
    "taxonomy_generate": taxonomy_generate,
}
