"""The bargain with Ollama itself: does `format=<schema>` actually constrain the model?

Skipped when nothing answers on the configured host. Every other test in this area
drives a fake provider and so proves only that our own code is correct. This is the one
that can fail because the runtime changed underneath us, which is the failure worth
having a test for.
"""

import httpx
import pytest

from reviewsignal_api.ai.ollama import OllamaProvider
from reviewsignal_api.ai.prompts import TAXONOMY_GENERATE_V1
from reviewsignal_api.core.config import get_settings
from reviewsignal_api.schemas.taxonomy_generation import GeneratedTaxonomy

REVIEWS = """- (5/5) The prints came out beautifully and the colours were exactly right.
- (2/5) I waited nearly forty minutes past my appointment time.
- (5/5) The photographer was patient and friendly with my children.
- (1/5) They lost my film negatives and nobody apologised.
- (4/5) Passport photos done in ten minutes, very convenient."""


def _answers(base_url: str) -> bool:
    try:
        httpx.get(f"{base_url.rstrip('/')}/api/version", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        return False
    return True


@pytest.fixture
def provider() -> OllamaProvider:
    settings = get_settings()
    if not _answers(settings.ollama_base_url):
        pytest.skip("No Ollama answering on the configured host.")
    return OllamaProvider(settings.ollama_base_url, settings.ollama_model)


def test_a_real_model_returns_output_valid_against_the_schema(provider: OllamaProvider) -> None:
    outcome = provider.generate_structured(
        TAXONOMY_GENERATE_V1.render(reviews=REVIEWS),
        GeneratedTaxonomy,
        task="taxonomy_generate",
    )

    assert outcome.value.nodes
    # `taxonomy-pipeline.md` §4 requires descriptions; a schema that admitted blank ones
    # would satisfy Pydantic and fail classification later.
    assert all(node.description.strip() for node in outcome.value.nodes)
    assert outcome.attempts == 1, "the schema should have been honoured first time"
    assert outcome.fallback_used is False
    assert outcome.latency_ms > 0
