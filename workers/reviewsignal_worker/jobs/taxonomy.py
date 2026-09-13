"""Taxonomy generation job (`docs/taxonomy-pipeline.md` §3, the first pass only).

Not idempotent by job id, and does not need to be. Every write happens after the model
call returns, so a transport failure retries having stored nothing, and a schema failure
raises `PermanentJobError` and never retries at all. Producing two candidate versions
from one job would take a crash between the writes and the commit, which commits nothing.
"""

import logging
import uuid

from reviewsignal_api.ai.ollama import OllamaProvider
from reviewsignal_api.ai.provider import LLMProvider
from reviewsignal_api.core.config import get_settings
from reviewsignal_api.services.taxonomy_generation import (
    TaxonomyGenerationError,
    TaxonomyGenerationService,
)
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.errors import PermanentJobError

logger = logging.getLogger(__name__)

TAXONOMY_JOB_TYPE = "taxonomy_generate"

# The whole seeded corpus fits one prompt. Batching arrives with the refinement loop
# (`taxonomy-pipeline.md` §3), which is what a corpus too large for one pass needs.
DEFAULT_SAMPLE_SIZE = 150


def build_provider() -> LLMProvider:
    """Built through a function so a test can substitute one without a live model,
    the same seam `jobs/evaluation.py` uses for the benchmark path."""
    settings = get_settings()
    return OllamaProvider(settings.ollama_base_url, settings.ollama_model)


def taxonomy_generate(payload: dict, job_id: uuid.UUID) -> None:
    sample_size = int(payload.get("sample_size", DEFAULT_SAMPLE_SIZE))
    try:
        with session_scope() as session:
            version = TaxonomyGenerationService(session, build_provider()).generate(
                sample_size=sample_size
            )
            logger.info(
                "Job %s stored candidate taxonomy version %s.", job_id, version.version_number
            )
    except TaxonomyGenerationError as exc:
        # A retry reaches the same rejection: neither the corpus nor the prompt changes
        # between attempts. `errors.py` explains why that dead-letters on the first one.
        raise PermanentJobError(str(exc)) from exc
