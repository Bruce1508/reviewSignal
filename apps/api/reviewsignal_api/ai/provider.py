"""The seam between a workflow and whatever model runs it (`docs/ai-pipeline.md` §38).

Synchronous, where `ai-pipeline.md` §38 sketches `async def`: the only caller is the RQ
worker, which runs sync (`workers/reviewsignal_worker/db.py`). Making the seam async
would buy an `asyncio.run` at every call site and no concurrency, since a run is one
request. Revisit when a caller is genuinely async.

No member of `StructuredOutcome` holds the model's raw reply. Non-Negotiable Rule 3
forbids exposing or persisting hidden chain-of-thought, and the reasoning models this
runs against emit it by default; leaving the text unrepresentable enforces the rule
through the type rather than through everyone downstream remembering.
"""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


class StructuredOutputError(Exception):
    """The model never produced output valid against the requested schema.

    Carries what the attempt cost so the caller can still record the run
    (`ai-pipeline.md` §36). Without it a rejected run would be the one kind of run that
    leaves no trace, which is the kind most worth tracing.
    """

    def __init__(self, message: str, *, attempts: int, latency_ms: int) -> None:
        super().__init__(message)
        self.message = message
        self.attempts = attempts
        self.latency_ms = latency_ms


@dataclass(frozen=True)
class StructuredOutcome[T: BaseModel]:
    """A validated reply and what producing it cost.

    `attempts` is 1 for a reply accepted first time; more means the stricter retry in
    `ai-pipeline.md` §37 ran. `latency_ms` covers every attempt, because that is what
    the run actually spent.
    """

    value: T
    latency_ms: int
    attempts: int
    fallback_used: bool


class LLMProvider(Protocol):
    """`name`, `model_name` and `model_version` fill in `model_runs`
    (`docs/model-runs.md` §1)."""

    @property
    def name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def model_version(self) -> str | None: ...

    def generate_structured[T: BaseModel](
        self, prompt: str, schema_model: type[T], *, task: str
    ) -> StructuredOutcome[T]:
        """Validated output of `schema_model`, or `StructuredOutputError` if none came.

        `task` names the workflow for logging only; it never changes what is sent.
        """
        ...
