"""use_alter foreign keys the baseline never created

Revision ID: e2b7c4a91f36
Revises: 537d54fe5104
Create Date: 2026-09-08 19:04:12.000000

`db/models.py` declares `ModelRun.taxonomy_version_id` and
`TaxonomyVersion.generation_model_run_id` with `use_alter=True` to break the circular
reference between the two tables. The baseline revision `70c5a19c093f` wrote each one
inline in its own `op.create_table` call, and SQLAlchemy's `CreateTable` compiler omits
any constraint carrying `use_alter=True`: it expects a later `ADD CONSTRAINT` that only
`create_all` schedules and that `op.create_table` never emits. Both constraints were
therefore discarded at CREATE TABLE time and have never existed in a database built from
this chain. Before this revision `pg_constraint` returned exactly one foreign key across
the two tables, the self-referential `taxonomy_versions_parent_version_id_fkey`.

`537d54fe5104` recorded the drift and stripped the two statements autogenerate proposed,
because they belonged in a change of their own and because `create_foreign_key(None, ...)`
emits an unnamed constraint that its paired `drop_constraint(None, ...)` could never drop.
This revision is that change.

Each constraint is created under the name PostgreSQL would have generated itself had the
inline definition survived, matching the sibling foreign key the baseline did create. The
same names are now declared in `db/models.py`, which is what stops autogenerate from
reproposing the pair on every subsequent run and what lets the downgrade below name what
it drops.

No ON DELETE behaviour is specified, matching the ORM declarations exactly rather than
improving on them: trading this drift for a different one would leave the chain no more
trustworthy than it is today. Both columns are nullable and neither parent is deleted in
normal operation - taxonomy versions are immutable (`data-model.md` §5) - so NO ACTION is
the correct default here and not a placeholder.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e2b7c4a91f36"
down_revision: str | None = "537d54fe5104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "model_runs_taxonomy_version_id_fkey",
        "model_runs",
        "taxonomy_versions",
        ["taxonomy_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "taxonomy_versions_generation_model_run_id_fkey",
        "taxonomy_versions",
        "model_runs",
        ["generation_model_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "taxonomy_versions_generation_model_run_id_fkey", "taxonomy_versions", type_="foreignkey"
    )
    op.drop_constraint("model_runs_taxonomy_version_id_fkey", "model_runs", type_="foreignkey")
