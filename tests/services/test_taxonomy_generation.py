"""Single-pass taxonomy generation: what a run stores, and what a bad reply leaves behind.

The provider is a fake so these tests exercise the service's own decisions rather than
Ollama. The provider's own bargain with Ollama is covered in
`tests/ai/test_ollama_provider.py`, which needs a running model and skips without one.
"""

from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from reviewsignal_api.ai.provider import StructuredOutcome, StructuredOutputError
from reviewsignal_api.db.models import ModelRun, Review, TaxonomyNode, TaxonomyVersion
from reviewsignal_api.schemas.taxonomy_generation import (
    GeneratedCategory,
    GeneratedSubcategory,
    GeneratedTaxonomy,
)
from reviewsignal_api.services.taxonomy_generation import (
    TaxonomyGenerationError,
    TaxonomyGenerationService,
)

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _store_review(session: Session, index: int, text: str | None = "Great photos") -> Review:
    review = Review(
        source="stub",
        source_review_id=f"stub-{index}",
        rating=5,
        review_text=text,
        reviewer_name="Jane D.",
        created_at=BASE,
        updated_at=BASE,
        language="en",
        raw_payload={},
    )
    session.add(review)
    session.flush()
    return review


def _taxonomy(*categories: GeneratedCategory) -> GeneratedTaxonomy:
    return GeneratedTaxonomy(nodes=list(categories))


def _category(name: str, *children: str) -> GeneratedCategory:
    return GeneratedCategory(
        name=name,
        description=f"Feedback about {name.lower()}.",
        children=[
            GeneratedSubcategory(name=child, description=f"Feedback about {child.lower()}.")
            for child in children
        ],
    )


class _FakeProvider:
    """Returns a prepared taxonomy, or raises where one was not prepared."""

    name = "fake"
    model_name = "fake-model"
    model_version = None

    def __init__(
        self,
        taxonomy: GeneratedTaxonomy | None = None,
        error: Exception | None = None,
    ) -> None:
        self._taxonomy = taxonomy
        self._error = error
        self.calls = 0
        self.last_prompt: str | None = None

    def generate_structured[T: BaseModel](
        self, prompt: str, schema_model: type[T], *, task: str
    ) -> StructuredOutcome[T]:
        self.calls += 1
        self.last_prompt = prompt
        if self._error is not None:
            raise self._error
        assert self._taxonomy is not None
        # The double is wired for one schema. The cast lets it satisfy the generic
        # protocol without pretending to be generic itself.
        return cast(
            StructuredOutcome[T],
            StructuredOutcome(value=self._taxonomy, latency_ms=42, attempts=1, fallback_used=False),
        )


def test_generation_stores_a_candidate_version_with_its_tree(session: Session) -> None:
    _store_review(session, 1)
    provider = _FakeProvider(_taxonomy(_category("Service", "Wait Time", "Staff")))

    version = TaxonomyGenerationService(session, provider).generate(sample_size=10)

    assert version.status == "candidate"
    assert version.created_by == "model"
    assert version.activated_at is None
    nodes = (
        session.execute(
            select(TaxonomyNode)
            .where(TaxonomyNode.taxonomy_version_id == version.id)
            .order_by(TaxonomyNode.depth, TaxonomyNode.sort_order)
        )
        .scalars()
        .all()
    )
    assert [(n.name, n.depth, n.sort_order) for n in nodes] == [
        ("Service", 0, 0),
        ("Wait Time", 1, 0),
        ("Staff", 1, 1),
    ]
    assert nodes[1].parent_id == nodes[0].id
    assert nodes[2].parent_id == nodes[0].id


def test_generation_does_not_activate_the_version(session: Session) -> None:
    """`taxonomy-tables.md` §1 allows one active version; this slice activates none."""
    _store_review(session, 1)
    provider = _FakeProvider(_taxonomy(_category("Service")))

    TaxonomyGenerationService(session, provider).generate(sample_size=10)

    active = (
        session.execute(select(TaxonomyVersion).where(TaxonomyVersion.status == "active"))
        .scalars()
        .all()
    )
    assert active == []


def test_generation_records_a_successful_model_run(session: Session) -> None:
    _store_review(session, 1)
    _store_review(session, 2)
    provider = _FakeProvider(_taxonomy(_category("Service")))

    version = TaxonomyGenerationService(session, provider).generate(sample_size=10)

    run = session.execute(select(ModelRun)).scalar_one()
    assert (run.task, run.provider, run.model_name) == ("taxonomy_generate", "fake", "fake-model")
    assert run.prompt_version == "taxonomy_generate_v1"
    assert (run.success, run.output_valid, run.fallback_used) == (True, True, False)
    assert run.input_count == 2
    assert run.latency_ms == 42
    assert run.error_message is None
    assert version.generation_model_run_id == run.id


def test_model_run_metadata_never_carries_model_output(session: Session) -> None:
    """Non-Negotiable Rule 3: no hidden reasoning is persisted, so no raw text is either."""
    _store_review(session, 1)
    provider = _FakeProvider(_taxonomy(_category("Service")))

    TaxonomyGenerationService(session, provider).generate(sample_size=10)

    run = session.execute(select(ModelRun)).scalar_one()
    assert set(run.meta) == {"sample_size", "attempts", "category_count"}


def test_version_number_follows_the_highest_existing(session: Session) -> None:
    session.add(TaxonomyVersion(version_number=7, status="archived", created_by="model"))
    session.flush()
    _store_review(session, 1)
    provider = _FakeProvider(_taxonomy(_category("Service")))

    version = TaxonomyGenerationService(session, provider).generate(sample_size=10)

    assert version.version_number == 8


def test_repeated_names_get_distinct_slugs(session: Session) -> None:
    """`taxonomy-tables.md` §2 makes slug unique per version, and a model may repeat a name."""
    _store_review(session, 1)
    provider = _FakeProvider(
        _taxonomy(_category("Service", "Wait Time"), _category("Service", "Wait Time"))
    )

    version = TaxonomyGenerationService(session, provider).generate(sample_size=10)

    slugs = (
        session.execute(
            select(TaxonomyNode.slug).where(TaxonomyNode.taxonomy_version_id == version.id)
        )
        .scalars()
        .all()
    )
    assert len(slugs) == len(set(slugs))
    assert "service" in slugs and "service_2" in slugs


def test_only_reviews_with_text_reach_the_prompt(session: Session) -> None:
    _store_review(session, 1, text="Lovely prints")
    _store_review(session, 2, text=None)
    provider = _FakeProvider(_taxonomy(_category("Service")))

    TaxonomyGenerationService(session, provider).generate(sample_size=10)

    assert provider.last_prompt is not None
    assert "Lovely prints" in provider.last_prompt
    run = session.execute(select(ModelRun)).scalar_one()
    assert run.input_count == 1


def test_an_empty_corpus_fails_before_calling_the_model(session: Session) -> None:
    """Nothing to ground a taxonomy in, so `taxonomy-pipeline.md` §1 cannot be satisfied."""
    provider = _FakeProvider(_taxonomy(_category("Service")))

    with pytest.raises(TaxonomyGenerationError):
        TaxonomyGenerationService(session, provider).generate(sample_size=10)

    assert provider.calls == 0
    assert session.execute(select(ModelRun)).scalars().all() == []


def test_a_rejected_reply_still_records_a_failed_model_run(session: Session) -> None:
    """`ai-pipeline.md` §36 logs runs; a run that only logs its successes logs nothing."""
    _store_review(session, 1)
    provider = _FakeProvider(
        error=StructuredOutputError("not valid against the schema", attempts=2, latency_ms=91)
    )

    with pytest.raises(TaxonomyGenerationError):
        TaxonomyGenerationService(session, provider).generate(sample_size=10)

    run = session.execute(select(ModelRun)).scalar_one()
    assert (run.success, run.output_valid, run.fallback_used) == (False, False, True)
    assert run.error_message is not None
    assert run.latency_ms == 91
    assert session.execute(select(TaxonomyVersion)).scalars().all() == []


def test_a_failed_run_survives_the_callers_rollback(session: Session) -> None:
    """The job's transaction rolls back on the exception, and the audit row must not."""
    _store_review(session, 1)
    provider = _FakeProvider(
        error=StructuredOutputError("not valid against the schema", attempts=2, latency_ms=91)
    )

    with pytest.raises(TaxonomyGenerationError):
        TaxonomyGenerationService(session, provider).generate(sample_size=10)
    session.rollback()

    assert session.execute(select(ModelRun)).scalar_one() is not None
