"""evaluation run prompt version

Revision ID: 537d54fe5104
Revises: c87f5e6195fd
Create Date: 2026-09-07 14:09:31.767935
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "537d54fe5104"
down_revision: str | None = "c87f5e6195fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs", sa.Column("prompt_version", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("evaluation_runs", "prompt_version")
