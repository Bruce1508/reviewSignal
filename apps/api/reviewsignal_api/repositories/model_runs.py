"""Model run persistence (`docs/model-runs.md` §1). No business rules here.

Insert-only, like `evaluation_runs`: `model-runs.md` §1 gives the table `created_at` and
no update column, so a run is a fact about one execution rather than a row that evolves.
"""

import uuid

from sqlalchemy.orm import Session

from reviewsignal_api.db.models import ModelRun


class ModelRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        task: str,
        provider: str,
        model_name: str,
        input_count: int,
        latency_ms: int,
        success: bool,
        fallback_used: bool,
        output_valid: bool,
        metadata: dict,
        model_version: str | None = None,
        prompt_version: str | None = None,
        taxonomy_version_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> ModelRun:
        """Every field of `model-runs.md` §1 is a keyword.

        They are same-typed and easy to transpose — `provider` against `model_name`,
        `success` against `output_valid` — and a transposed audit row reads as truth.
        """
        run = ModelRun(
            task=task,
            provider=provider,
            model_name=model_name,
            model_version=model_version,
            prompt_version=prompt_version,
            taxonomy_version_id=taxonomy_version_id,
            input_count=input_count,
            latency_ms=latency_ms,
            success=success,
            fallback_used=fallback_used,
            output_valid=output_valid,
            error_message=error_message,
            meta=metadata,
        )
        self._session.add(run)
        self._session.flush()
        return run
