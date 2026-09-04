"""The invariants in `docs/data-model.md` §21 must be enforced by PostgreSQL itself.

Each test writes directly through the ORM, bypassing every service, so a passing
test proves the database rejects the row rather than proving Python does.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from reviewsignal_api.db.models import (
    Review,
    ReviewAnalysis,
    ReviewAspect,
    TaxonomyNode,
    TaxonomyVersion,
)


def _review(**overrides) -> Review:
    defaults = dict(
        source="google",
        source_review_id=f"src-{uuid.uuid4()}",
        rating=5,
        review_text="Great prints.",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        language="en",
        raw_payload={},
    )
    return Review(**{**defaults, **overrides})


def _version(number: int, status: str) -> TaxonomyVersion:
    return TaxonomyVersion(version_number=number, status=status, created_by="system")


@pytest.mark.parametrize("rating", [0, 6, -1, 99])
def test_rating_outside_one_to_five_is_rejected(session: Session, rating: int) -> None:
    session.add(_review(rating=rating))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("rating", [1, 3, 5])
def test_rating_within_range_is_accepted(session: Session, rating: int) -> None:
    session.add(_review(rating=rating))
    session.flush()


def test_duplicate_source_review_id_is_rejected(session: Session) -> None:
    shared_id = f"src-{uuid.uuid4()}"
    session.add(_review(source_review_id=shared_id))
    session.flush()

    session.add(_review(source_review_id=shared_id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_only_one_taxonomy_version_can_be_active(session: Session) -> None:
    session.add(_version(1, "active"))
    session.flush()

    session.add(_version(2, "active"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_many_archived_versions_are_allowed_alongside_one_active(session: Session) -> None:
    session.add_all([_version(1, "archived"), _version(2, "archived"), _version(3, "active")])
    session.flush()


def test_invalid_taxonomy_version_status_is_rejected(session: Session) -> None:
    session.add(_version(1, "not-a-real-status"))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 2.0])
def test_aspect_confidence_outside_zero_to_one_is_rejected(
    session: Session, confidence: float
) -> None:
    aspect = _build_aspect(session, confidence=confidence)
    session.add(aspect)

    with pytest.raises(IntegrityError):
        session.flush()


def test_invalid_sentiment_is_rejected(session: Session) -> None:
    aspect = _build_aspect(session, sentiment="furious")
    session.add(aspect)

    with pytest.raises(IntegrityError):
        session.flush()


def _build_aspect(session: Session, **overrides) -> ReviewAspect:
    review = _review()
    version = _version(1, "active")
    session.add_all([review, version])
    session.flush()

    node = TaxonomyNode(
        taxonomy_version_id=version.id, name="Print Quality", slug="print-quality", depth=0
    )
    session.add(node)
    session.flush()

    analysis = ReviewAnalysis(
        review_id=review.id, taxonomy_version_id=version.id, classifier_type="llm"
    )
    session.add(analysis)
    session.flush()

    defaults = dict(
        review_analysis_id=analysis.id,
        taxonomy_node_id=node.id,
        sentiment="positive",
        confidence=0.9,
        evidence_text="Great prints.",
        source="llm",
    )
    return ReviewAspect(**{**defaults, **overrides})


def test_taxonomy_slug_is_unique_within_a_version(session: Session) -> None:
    version = _version(1, "candidate")
    session.add(version)
    session.flush()

    session.add(TaxonomyNode(taxonomy_version_id=version.id, name="Wait Time", slug="wait-time"))
    session.flush()

    session.add(TaxonomyNode(taxonomy_version_id=version.id, name="Waiting", slug="wait-time"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_same_slug_is_allowed_across_different_versions(session: Session) -> None:
    first, second = _version(1, "archived"), _version(2, "active")
    session.add_all([first, second])
    session.flush()

    session.add_all(
        [
            TaxonomyNode(taxonomy_version_id=first.id, name="Wait Time", slug="wait-time"),
            TaxonomyNode(taxonomy_version_id=second.id, name="Wait Time", slug="wait-time"),
        ]
    )
    session.flush()
