"""Job handler registry.

Handlers take a payload dict and return nothing. Register new job types here so
`runner.run_job` can resolve them by name.
"""

from collections.abc import Callable

from reviewsignal_worker.jobs.noop import noop

HANDLERS: dict[str, Callable[[dict], None]] = {
    "noop": noop,
}
