"""add canonical_predicate to ontology_entities

Revision ID: cf3a1808ba8d
Revises: 6261ddb1ad72
Create Date: 2026-07-13 05:43:19.082994

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'cf3a1808ba8d'
down_revision = '6261ddb1ad72'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable column on the unified ontology_entities table (native SQLite ADD;
    # no table rebuild). The unrelated batch_runs.run_type type-widening that
    # autogenerate also detected (pre-existing model/DB drift) was intentionally
    # removed so this migration only carries the canonical_predicate change.
    op.add_column(
        'ontology_entities',
        sa.Column('canonical_predicate', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('ontology_entities', 'canonical_predicate')
