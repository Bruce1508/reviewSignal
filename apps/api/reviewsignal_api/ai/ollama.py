"""Ollama-backed provider (`docs/ai-pipeline.md` §38).

Concrete, not behind a factory: there is one provider, and a second one satisfies
`LLMProvider` without anything here changing. `ai-pipeline.md` §38 names vLLM,
OpenAI-compatible endpoints, and Bedrock as future peers, not as configuration this
slice has to anticipate.

Schema is enforced twice. `format` gives Ollama the JSON Schema so constrained decoding
makes malformed output rare; Pydantic then validates what arrives, because the first
layer is the model's promise and the second is the one this code relies on.
"""

import time

import httpx
from pydantic import BaseModel, ValidationError

from reviewsignal_api.ai.provider import StructuredOutcome, StructuredOutputError

# A taxonomy pass sends the whole sample in one prompt, so the call is long by design
# rather than by accident. Bounded so a hung model still dead-letters the job.
_TIMEOUT_SECONDS = 300.0

# `ai-pipeline.md` §37: a schema failure is retried once, with stricter constraints.
_STRICTER = (
    "Your previous reply did not match the required JSON schema. "
    "Reply with JSON matching the schema exactly. No prose, no code fences, no commentary."
)


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, *, timeout_seconds: float = _TIMEOUT_SECONDS):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def model_version(self) -> str | None:
        """None: Ollama's digest is a second round trip, and `model-runs.md` §1 allows
        the column to be null. Worth filling in once one run is compared against another."""
        return None

    def generate_structured[T: BaseModel](
        self, prompt: str, schema_model: type[T], *, task: str
    ) -> StructuredOutcome[T]:
        schema = schema_model.model_json_schema()
        started = time.monotonic()
        rejections: list[str] = []

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
            for attempt in (1, 2):
                text = self._chat(
                    client, prompt if attempt == 1 else f"{prompt}\n\n{_STRICTER}", schema
                )
                try:
                    value = schema_model.model_validate_json(text)
                except ValidationError as exc:
                    # The reply itself is never kept: `provider.py` explains why no model
                    # text may be carried out of here.
                    rejections.append(f"attempt {attempt}: {exc.error_count()} schema errors")
                    continue
                return StructuredOutcome(
                    value=value,
                    latency_ms=_elapsed_ms(started),
                    attempts=attempt,
                    fallback_used=attempt > 1,
                )

        raise StructuredOutputError(
            "; ".join(rejections), attempts=2, latency_ms=_elapsed_ms(started)
        )

    def _chat(self, client: httpx.Client, prompt: str, schema: dict) -> str:
        """One completion. Transport failures propagate: a model that is down may be up
        on the next attempt, so `architecture.md` §13's retry-with-backoff is the right
        response, not the dead-letter a `PermanentJobError` would force."""
        response = client.post(
            "/api/chat",
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                # Reasoning models emit hidden thinking by default. Non-Negotiable Rule 3
                # forbids exposing or persisting it, and the cheapest way to honour that
                # is never to receive it.
                "think": False,
                "format": schema,
                # Deterministic: two runs of one prompt should differ because the corpus
                # changed, not because sampling did.
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
