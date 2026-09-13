"""Single-pass taxonomy generation (`docs/taxonomy-pipeline.md` §3, the first pass only).

Minibatching, the update loop, the review gate, and automatic acceptance
(`taxonomy-pipeline.md` §5, §6) are not here. A run stores one `candidate` version and
activates nothing, so the single-active-version rule in `taxonomy-tables.md` §1 is not
something this code can break.

Until Google Business Profile access is granted (`docs/PRD.md` §11) the only corpus is
the synthetic seed. A run over it proves the mechanism, the versioning, and the
persistence. It proves nothing about taxonomy quality, and no quality claim should be
drawn from one.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from reviewsignal_api.ai.prompts import TAXONOMY_GENERATE_V1
from reviewsignal_api.ai.provider import LLMProvider, StructuredOutcome, StructuredOutputError
from reviewsignal_api.db.models import Review, TaxonomyNode, TaxonomyVersion
from reviewsignal_api.repositories.model_runs import ModelRunRepository
from reviewsignal_api.schemas.taxonomy_generation import GeneratedTaxonomy

TASK = "taxonomy_generate"

_NON_SLUG = re.compile(r"[^a-z0-9]+")


class TaxonomyGenerationError(Exception):
    """A run that stored no taxonomy. The model run is recorded either way."""


def _unique_slug(name: str, used: set[str]) -> str:
    """A slug unique within the version (`docs/taxonomy-tables.md` §2).

    Nothing stops a model returning the same name twice, and the unique constraint would
    turn that into a failed insert rather than a taxonomy worth reviewing.
    """
    base = _NON_SLUG.sub("_", name.strip().lower()).strip("_") or "category"
    slug = base
    suffix = 1
    while slug in used:
        suffix += 1
        slug = f"{base}_{suffix}"
    used.add(slug)
    return slug


def _format_reviews(reviews: list[Review]) -> str:
    return "\n".join(f"- ({review.rating}/5) {review.review_text}" for review in reviews)


class TaxonomyGenerationService:
    def __init__(self, session: Session, provider: LLMProvider) -> None:
        self._session = session
        self._provider = provider
        self._model_runs = ModelRunRepository(session)

    def generate(self, *, sample_size: int) -> TaxonomyVersion:
        reviews = self._sample(sample_size)
        if not reviews:
            # Before the model call, so an empty corpus costs nothing and records
            # nothing: there was no run to log.
            raise TaxonomyGenerationError("No reviews with text to ground a taxonomy in.")

        prompt = TAXONOMY_GENERATE_V1.render(reviews=_format_reviews(reviews))
        try:
            outcome = self._provider.generate_structured(prompt, GeneratedTaxonomy, task=TASK)
        except StructuredOutputError as exc:
            self._record_rejection(exc, input_count=len(reviews), sample_size=sample_size)
            raise TaxonomyGenerationError(exc.message) from exc
        return self._store(outcome, input_count=len(reviews), sample_size=sample_size)

    def _sample(self, sample_size: int) -> list[Review]:
        """Newest first, and only reviews with text.

        `ai-pipeline.md` §5 rejects empty text, and a rating with no comment carries
        nothing for a taxonomy to be derived from.
        """
        statement = (
            select(Review)
            .where(Review.review_text.isnot(None), Review.review_text != "")
            .order_by(Review.created_at.desc())
            .limit(sample_size)
        )
        return list(self._session.execute(statement).scalars().all())

    def _record_rejection(
        self, exc: StructuredOutputError, *, input_count: int, sample_size: int
    ) -> None:
        self._model_runs.record(
            task=TASK,
            provider=self._provider.name,
            model_name=self._provider.model_name,
            model_version=self._provider.model_version,
            prompt_version=TAXONOMY_GENERATE_V1.id,
            input_count=input_count,
            latency_ms=exc.latency_ms,
            success=False,
            output_valid=False,
            # More than one attempt means the stricter retry of `ai-pipeline.md` §37 ran.
            fallback_used=exc.attempts > 1,
            error_message=exc.message,
            metadata={
                "sample_size": sample_size,
                "attempts": exc.attempts,
                "category_count": 0,
            },
        )
        # Committed here, against the usual rule that the caller owns the transaction.
        # The `TaxonomyGenerationError` raised next unwinds through the job's
        # `session_scope`, which rolls back — taking this row with it.
        # `ai-pipeline.md` §36 wants the rejected run recorded precisely because the job
        # then dead-letters, so it is the one write that must outlive the failure.
        self._session.commit()

    def _store(
        self,
        outcome: StructuredOutcome[GeneratedTaxonomy],
        *,
        input_count: int,
        sample_size: int,
    ) -> TaxonomyVersion:
        run = self._model_runs.record(
            task=TASK,
            provider=self._provider.name,
            model_name=self._provider.model_name,
            model_version=self._provider.model_version,
            prompt_version=TAXONOMY_GENERATE_V1.id,
            input_count=input_count,
            latency_ms=outcome.latency_ms,
            success=True,
            output_valid=True,
            fallback_used=outcome.fallback_used,
            metadata={
                "sample_size": sample_size,
                "attempts": outcome.attempts,
                "category_count": len(outcome.value.nodes),
            },
        )
        version = TaxonomyVersion(
            version_number=self._next_version_number(),
            status="candidate",
            created_by="model",
            generation_model_run_id=run.id,
        )
        self._session.add(version)
        self._session.flush()
        self._store_nodes(version, outcome.value)
        return version

    def _next_version_number(self) -> int:
        highest = self._session.execute(select(func.max(TaxonomyVersion.version_number))).scalar()
        return (highest or 0) + 1

    def _store_nodes(self, version: TaxonomyVersion, taxonomy: GeneratedTaxonomy) -> None:
        used: set[str] = set()
        for order, category in enumerate(taxonomy.nodes):
            parent = self._store_node(
                version, category.name, category.description, None, 0, order, used
            )
            for child_order, child in enumerate(category.children):
                self._store_node(
                    version, child.name, child.description, parent.id, 1, child_order, used
                )

    def _store_node(  # noqa: PLR0913
        self,
        version: TaxonomyVersion,
        name: str,
        description: str,
        parent_id: object,
        depth: int,
        sort_order: int,
        used: set[str],
    ) -> TaxonomyNode:
        node = TaxonomyNode(
            taxonomy_version_id=version.id,
            parent_id=parent_id,
            name=name,
            description=description,
            slug=_unique_slug(name, used),
            depth=depth,
            sort_order=sort_order,
        )
        self._session.add(node)
        self._session.flush()
        return node
