"""Worker failure classes.

`docs/architecture.md` §13 routes a failing job through retry-with-backoff before the
dead-letter queue. That chain is worth spending only when the failure might not recur.
An unregistered predictor or an unset benchmark path recurs identically on every
attempt, so retrying one reaches the same dead-letter it started for, roughly 150s
later, having reported three failures where there was one.
"""


class PermanentJobError(Exception):
    """A failure retrying cannot fix. Dead-letters on its first attempt."""
