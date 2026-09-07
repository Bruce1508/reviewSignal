"""Every job type the API can enqueue must have a worker handler.

A rename on one side alone produces a job that runs, finds no handler, exhausts its
retries and lands in `dead_letter` — a failure that only shows up in production. This
check is cheap; that failure is not.
"""

import importlib
import re
from pathlib import Path

from reviewsignal_worker.jobs import HANDLERS

API_ROOT = Path(__file__).resolve().parents[2] / "apps/api"
PACKAGE = API_ROOT / "reviewsignal_api"

# `enqueue("google_sync", ...)` and `run_in_threadpool(enqueue, EVALUATION_JOB_TYPE, ...)`.
CALL_SITE = re.compile(r"enqueue[,(]\s*(\"[a-z_]+\"|[A-Z][A-Z0-9_]*)")


def _resolve(module_path: Path, token: str) -> str:
    """A literal is its own answer; a constant is read off the module that passes it."""
    if token.startswith('"'):
        return token.strip('"')
    dotted = ".".join(module_path.relative_to(API_ROOT).with_suffix("").parts)
    value = getattr(importlib.import_module(dotted), token)
    assert isinstance(value, str), f"{token} in {dotted} is not a job type string"
    return value


def _enqueued_job_types() -> set[str]:
    """Every job type passed to `enqueue(...)` anywhere in the API package.

    Scanning the whole package, and resolving constants as well as literals, because the
    service layer enqueues too and passes a constant: a scan limited to the route
    modules and to quoted strings misses that call site entirely while still passing.
    """
    return {
        _resolve(module, token)
        for module in PACKAGE.rglob("*.py")
        for token in CALL_SITE.findall(module.read_text())
    }


def test_the_api_enqueues_at_least_one_job_type() -> None:
    """Guards the regex above: a silent zero-match would make the next test vacuous."""
    assert _enqueued_job_types(), "found no enqueue() call sites to check"


def test_the_scan_reaches_the_service_layer_and_not_only_string_literals() -> None:
    """`evaluation_run` is enqueued from `services/evaluation.py` through a constant, so
    it is the one call site that a route-only, literal-only scan silently drops. Pinning
    it keeps the check from quietly narrowing back to what it used to cover.
    """
    assert "evaluation_run" in _enqueued_job_types()


def test_every_enqueued_job_type_has_a_handler() -> None:
    unregistered = _enqueued_job_types() - set(HANDLERS)
    assert not unregistered, f"the API enqueues job types with no worker handler: {unregistered}"
