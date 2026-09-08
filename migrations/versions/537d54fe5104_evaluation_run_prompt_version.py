"""evaluation run prompt version

Revision ID: 537d54fe5104
Revises: c87f5e6195fd
Create Date: 2026-09-07 14:09:31.767935

`evaluation.md` §30 lists a prompt version among the fields a run record stores, and
`data-model.md` §16 carried that gap as an explicit Unresolved note until now. The
column is nullable: every Phase 0 workflow runs no prompt, and NULL is that meaning
rather than a missing value.

Autogenerate additionally proposed two foreign keys as newly added, stripped by hand
rather than kept:

    op.create_foreign_key(None, "model_runs", "taxonomy_versions", ...)
    op.create_foreign_key(None, "taxonomy_versions", "model_runs", ...)

Both are real drift, not a false positive. `db/models.py` declares
`ModelRun.taxonomy_version_id` and `TaxonomyVersion.generation_model_run_id` with
`use_alter=True` to break their circular reference, but the baseline revision
`70c5a19c093f` embedded each one inline in its own `op.create_table` call and never
emitted a follow-up ALTER. SQLAlchemy only schedules that ALTER when `create_all`
sorts the tables itself, so these two constraints have never existed in any database
built from this chain - confirmed against `pg_constraint`, which returns neither.

They are stripped here because the drift predates this revision and belongs in its
own change: a single-purpose migration should not carry an unrelated schema fix. The
generated statements were also unusable as written - `create_foreign_key(None, ...)`
emits an unnamed constraint that the paired `drop_constraint(None, ...)` could never
drop, so the downgrade would have failed.

Recorded rather than resolved silently: every future `alembic revision --autogenerate`
reproduces this same pair until the drift is fixed, and whoever runs it next must
strip them again rather than merge them.
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
