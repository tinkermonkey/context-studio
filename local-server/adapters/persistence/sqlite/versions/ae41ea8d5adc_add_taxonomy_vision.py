"""add taxonomy vision

Revision ID: ae41ea8d5adc
Revises: a2135ea544cc
Create Date: 2026-10-26 10:40:59.327946

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae41ea8d5adc'
down_revision = 'a2135ea544cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Index drift on conflict_resolutions, extraction_results and individual_classes
    # that autogenerate also reports predates this revision and is left out on purpose.
    op.add_column('ontology_entities', sa.Column('vision', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('ontology_entities', 'vision')
