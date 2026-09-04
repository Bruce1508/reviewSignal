"""phase 0 ingestion: nullable review_text, source credentials

Revision ID: 3f8513e22ef8
Revises: 70c5a19c093f
Create Date: 2026-09-04 17:34:32.080889

Autogenerate also re-proposed the model_runs <-> taxonomy_versions foreign keys.
Those already exist from the baseline; they only reappear because `use_alter=True`
keeps them out of the CREATE TABLE statements. Re-adding them would create
duplicate unnamed constraints, so they are removed from this revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '3f8513e22ef8'
down_revision: str | None = '70c5a19c093f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('source_credentials',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), server_default='disconnected', nullable=False),
    sa.Column('account_id', sa.String(length=255), nullable=True),
    sa.Column('location_id', sa.String(length=255), nullable=True),
    sa.Column('access_token_encrypted', sa.LargeBinary(), nullable=True),
    sa.Column('refresh_token_encrypted', sa.LargeBinary(), nullable=True),
    sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status <> 'connected' OR refresh_token_encrypted IS NOT NULL", name='ck_source_credentials_connected_has_token'),
    sa.CheckConstraint("status IN ('connected', 'disconnected', 'invalid')", name='ck_source_credentials_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source')
    )
    op.alter_column('reviews', 'review_text',
               existing_type=sa.TEXT(),
               nullable=True)


def downgrade() -> None:
    # NOT NULL cannot be restored while rating-only reviews are stored. Collapsing them
    # to '' is lossy, but it is the only way back and it is what NOT NULL implied.
    op.execute("UPDATE reviews SET review_text = '' WHERE review_text IS NULL")
    op.alter_column('reviews', 'review_text',
               existing_type=sa.TEXT(),
               nullable=False)
    op.drop_table('source_credentials')
