"""ORM models for the core entities.

Schema contract is owned by `docs/data-model.md`. Status/sentiment vocabularies
are enforced with CHECK constraints rather than PostgreSQL ENUM types so that
adding a value stays a cheap migration.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from reviewsignal_api.db.base import Base

REVIEW_ANALYSIS_STATUSES = ("pending", "analyzed", "failed", "skipped")
TAXONOMY_VERSION_STATUSES = ("candidate", "active", "archived", "failed")
TAXONOMY_CHANGE_TYPES = ("add", "rename", "merge", "split", "move", "delete", "rollback")
CLASSIFIER_TYPES = ("llm", "ml", "hybrid", "manual")
SENTIMENTS = ("positive", "neutral", "negative")
ANOMALY_STATUSES = ("candidate", "accepted", "dismissed", "resolved")
INSIGHT_STATUSES = ("new", "monitoring", "resolved")
INSIGHT_ACTION_STATUSES = ("planned", "in_progress", "completed", "cancelled")
SYNC_RUN_STATUSES = ("running", "success", "failed", "partial")
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "dead_letter")
SOURCE_CREDENTIAL_STATUSES = ("connected", "disconnected", "invalid")


def _in(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class Review(Base):
    """Normalized review plus preserved source payload (`data-model.md` §4)."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = _pk()
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_review_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Nullable: a Google review may carry a star rating with no comment. Storing it
    # keeps rating and volume trends complete (`docs/PRD.md` §3.1); it is marked
    # analysis_status='skipped' because there is no text to analyze.
    review_text: Mapped[str | None] = mapped_column(Text)
    reviewer_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_reply_text: Mapped[str | None] = mapped_column(Text)
    owner_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en")
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    analysis_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
        CheckConstraint(
            _in("analysis_status", REVIEW_ANALYSIS_STATUSES), name="ck_reviews_analysis_status"
        ),
        Index("ix_reviews_created_at", "created_at"),
        Index("ix_reviews_rating", "rating"),
        Index("ix_reviews_analysis_status", "analysis_status"),
    )


class ModelRun(Base):
    """One invocation of a model for one task (`data-model.md` §15)."""

    __tablename__ = "model_runs"

    id: Mapped[uuid.UUID] = _pk()
    task: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    taxonomy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id", use_alter=True)
    )
    input_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    output_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    error_message: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_model_runs_created_at", "created_at"),)


class TaxonomyVersion(Base):
    """Immutable taxonomy version (`data-model.md` §5)."""

    __tablename__ = "taxonomy_versions"

    id: Mapped[uuid.UUID] = _pk()
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_model_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_runs.id", use_alter=True)
    )

    __table_args__ = (
        CheckConstraint(
            _in("status", TAXONOMY_VERSION_STATUSES), name="ck_taxonomy_versions_status"
        ),
        # `data-model.md` §5/§21: at most one active version, enforced by the database.
        Index(
            "uq_taxonomy_versions_single_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class TaxonomyNode(Base):
    """A category within one taxonomy version (`data-model.md` §6)."""

    __tablename__ = "taxonomy_nodes"

    id: Mapped[uuid.UUID] = _pk()
    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_nodes.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("taxonomy_version_id", "slug", name="uq_taxonomy_nodes_version_slug"),
        CheckConstraint("depth >= 0", name="ck_taxonomy_nodes_depth_non_negative"),
        Index("ix_taxonomy_nodes_version", "taxonomy_version_id"),
    )


class TaxonomyChange(Base):
    """Audit log of one structural change between versions (`data-model.md` §7)."""

    __tablename__ = "taxonomy_changes"

    id: Mapped[uuid.UUID] = _pk()
    from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id")
    )
    to_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id"), nullable=False
    )
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    old_node_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    new_node_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            _in("change_type", TAXONOMY_CHANGE_TYPES), name="ck_taxonomy_changes_change_type"
        ),
        Index("ix_taxonomy_changes_to_version", "to_version_id"),
    )


class ReviewAnalysis(Base):
    """One analysis pass of one review (`data-model.md` §8)."""

    __tablename__ = "review_analyses"

    id: Mapped[uuid.UUID] = _pk()
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id"), nullable=False
    )
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_runs.id")
    )
    classifier_type: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            _in("classifier_type", CLASSIFIER_TYPES), name="ck_review_analyses_classifier_type"
        ),
        CheckConstraint(
            "overall_confidence IS NULL OR (overall_confidence BETWEEN 0 AND 1)",
            name="ck_review_analyses_confidence_range",
        ),
        Index("ix_review_analyses_review", "review_id"),
        Index("ix_review_analyses_taxonomy_version", "taxonomy_version_id"),
        # Current-state lookups filter to the analysis that has not been superseded.
        Index(
            "ix_review_analyses_current",
            "review_id",
            postgresql_where=text("superseded_at IS NULL"),
        ),
    )


class ReviewAspect(Base):
    """One aspect label with sentiment and evidence (`data-model.md` §9)."""

    __tablename__ = "review_aspects"

    id: Mapped[uuid.UUID] = _pk()
    review_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_analyses.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_nodes.id"), nullable=False
    )
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(_in("sentiment", SENTIMENTS), name="ck_review_aspects_sentiment"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_review_aspects_confidence_range"),
        Index("ix_review_aspects_analysis", "review_analysis_id"),
        Index("ix_review_aspects_node", "taxonomy_node_id"),
        Index("ix_review_aspects_sentiment", "sentiment"),
    )


class Anomaly(Base):
    """A statistically detected deviation (`data-model.md` §10)."""

    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = _pk()
    taxonomy_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_nodes.id"), nullable=False
    )
    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(_in("status", ANOMALY_STATUSES), name="ck_anomalies_status"),
        CheckConstraint("period_start <= period_end", name="ck_anomalies_period_order"),
        CheckConstraint("support_count >= 0", name="ck_anomalies_support_non_negative"),
        Index("ix_anomalies_node", "taxonomy_node_id"),
        Index("ix_anomalies_period", "period_start", "period_end"),
    )


class Insight(Base):
    """An evidence-grounded insight (`data-model.md` §11)."""

    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = _pk()
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anomalies.id")
    )
    taxonomy_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_nodes.id")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="new")
    generated_by_model_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_runs.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_status_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        CheckConstraint(_in("status", INSIGHT_STATUSES), name="ck_insights_status"),
        Index("ix_insights_status", "status"),
        Index("ix_insights_created_at", "created_at"),
    )


class InsightAction(Base):
    """An operator action attached to an insight (`data-model.md` §12)."""

    __tablename__ = "insight_actions"

    id: Mapped[uuid.UUID] = _pk()
    insight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insights.id", ondelete="CASCADE"), nullable=False
    )
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_date: Mapped[date | None] = mapped_column(Date)
    note_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="planned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(_in("status", INSIGHT_ACTION_STATUSES), name="ck_insight_actions_status"),
        Index("ix_insight_actions_insight", "insight_id"),
    )


class SyncRun(Base):
    """One ingestion run against a source (`data-model.md` §13)."""

    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = _pk()
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviews_fetched: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviews_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviews_updated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    cursor_state: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_in("status", SYNC_RUN_STATUSES), name="ck_sync_runs_status"),
        Index("ix_sync_runs_started_at", "started_at"),
    )


class Job(Base):
    """Application-level job record, independent of the queue backend (`data-model.md` §14)."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = _pk()
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUSES), name="ck_jobs_status"),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count_non_negative"),
        CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts_positive"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_job_type", "job_type"),
        Index("ix_jobs_queued_at", "queued_at"),
    )


class EvaluationRun(Base):
    """One benchmark evaluation run (`data-model.md` §16)."""

    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = _pk()
    # The job that produced this run. Unique, so a retried job cannot add a second
    # row to the history; NULL for a run recorded outside the queue.
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), unique=True
    )
    evaluation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64))
    taxonomy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_versions.id")
    )
    # The benchmark names its taxonomy as text; the key above points at a row that may
    # not exist yet. Both are kept so a run can say what it scored (`evaluation.md` §30).
    taxonomy_version: Mapped[str | None] = mapped_column(String(64))
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_evaluation_runs_created_at", "created_at"),)


class Setting(Base):
    """Non-secret configuration (`data-model.md` §17).

    Deploy-time secrets live in the environment; runtime-issued OAuth tokens live in
    `source_credentials`, encrypted. Neither belongs here.
    """

    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = _pk()
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceCredential(Base):
    """OAuth credentials for one feedback source, encrypted at rest.

    A refresh token is issued at runtime by the OAuth callback, so it cannot live in an
    environment variable (set at deploy time) and `data-model.md` §17 bars it from
    `settings`. It is stored here as ciphertext and never returned by the API
    (`docs/api-spec.md` §16.5). Keyed by source so a second connector
    (`data-model.md` §25) needs no schema change.
    """

    __tablename__ = "source_credentials"

    id: Mapped[uuid.UUID] = _pk()
    source: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="disconnected")
    account_id: Mapped[str | None] = mapped_column(String(255))
    location_id: Mapped[str | None] = mapped_column(String(255))
    access_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            _in("status", SOURCE_CREDENTIAL_STATUSES), name="ck_source_credentials_status"
        ),
        # A connected source must actually hold a refresh token; anything else is a
        # half-written connection that /google/status would misreport.
        CheckConstraint(
            "status <> 'connected' OR refresh_token_encrypted IS NOT NULL",
            name="ck_source_credentials_connected_has_token",
        ),
    )
