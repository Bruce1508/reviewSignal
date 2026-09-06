"""Smoke-test handler used to verify the job lifecycle end to end."""

import logging
import uuid

logger = logging.getLogger(__name__)


def noop(payload: dict, job_id: uuid.UUID) -> None:
    """Succeed, or fail on demand when the payload asks for it."""
    if payload.get("fail"):
        raise RuntimeError("Intentional failure requested by payload.")
    logger.info("noop job executed with payload=%s", payload)
