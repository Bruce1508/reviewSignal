"""Every job type the API can enqueue must have a worker handler.

A rename on one side alone produces a job that runs, finds no handler, exhausts its
retries and lands in `dead_letter` — a failure that only shows up in production. This
check is cheap; that failure is not.
"""

import re
from pathlib import Path

from reviewsignal_worker.jobs import HANDLERS

ROUTES = Path(__file__).resolve().parents[2] / "apps/api/reviewsignal_api/api/v1"


def _enqueued_job_types() -> set[str]:
    """Job type literals passed to `enqueue(...)` anywhere in the v1 route modules."""
    pattern = re.compile(r"enqueue,\s*\"([a-z_]+)\"|enqueue\(\s*\"([a-z_]+)\"")
    found: set[str] = set()
    for module in ROUTES.glob("*.py"):
        for first, second in pattern.findall(module.read_text()):
            found.add(first or second)
    return found


def test_the_api_enqueues_at_least_one_job_type() -> None:
    """Guards the regex above: a silent zero-match would make the next test vacuous."""
    assert _enqueued_job_types(), "found no enqueue() call sites to check"


def test_every_enqueued_job_type_has_a_handler() -> None:
    unregistered = _enqueued_job_types() - set(HANDLERS)
    assert not unregistered, f"the API enqueues job types with no worker handler: {unregistered}"
