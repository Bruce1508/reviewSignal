"""The taxonomy job's two endings: a stored candidate, and a rejection that dead-letters.

Both run against the real database through `session_scope`, because what is being
asserted is what survives a commit — and in the failure case, what survives a rollback.
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from reviewsignal_api.ai.provider import StructuredOutcome, StructuredOutputError
from reviewsignal_api.db.models import ModelRun, Review, TaxonomyVersion
from reviewsignal_api.schemas.taxonomy_generation import GeneratedCategory, GeneratedTaxonomy
from reviewsignal_worker.db import session_scope
from reviewsignal_worker.errors import PermanentJobError
from reviewsignal_worker.jobs import taxonomy as taxonomy_job

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


class _FakeProvider:
    name = "fake"
    model_name = "fake-model"
    model_version = None

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def generate_structured[T: BaseModel](
        self, prompt: str, schema_model: type[T], *, task: str
    ) -> StructuredOutcome[T]:
        if self._error is not None:
            raise self._error
        return cast(
            StructuredOutcome[T],
            StructuredOutcome(
                value=GeneratedTaxonomy(
                    nodes=[GeneratedCategory(name="Service", description="Service feedback.")]
                ),
                latency_ms=12,
                attempts=1,
                fallback_used=False,
            ),
        )


@pytest.fixture
def seeded_review() -> None:
    with session_scope() as session:
        session.add(
            Review(
                source="stub",
                source_review_id="stub-job-1",
                rating=5,
                review_text="Lovely prints",
                created_at=BASE,
                updated_at=BASE,
                language="en",
                raw_payload={},
            )
        )


def test_a_run_stores_a_candidate_version(
    seeded_review: None, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(taxonomy_job, "build_provider", _FakeProvider)

    taxonomy_job.taxonomy_generate({"sample_size": 10}, uuid.uuid4())

    version = session.execute(select(TaxonomyVersion)).scalar_one()
    assert version.status == "candidate"


def test_a_rejected_reply_dead_letters_but_keeps_its_model_run(
    seeded_review: None, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`errors.py`: a failure that recurs identically should not spend the retry chain."""
    monkeypatch.setattr(
        taxonomy_job,
        "build_provider",
        lambda: _FakeProvider(StructuredOutputError("rejected", attempts=2, latency_ms=9)),
    )

    with pytest.raises(PermanentJobError):
        taxonomy_job.taxonomy_generate({"sample_size": 10}, uuid.uuid4())

    assert session.execute(select(TaxonomyVersion)).scalars().all() == []
    run = session.execute(select(ModelRun)).scalar_one()
    assert (run.success, run.output_valid) == (False, False)
