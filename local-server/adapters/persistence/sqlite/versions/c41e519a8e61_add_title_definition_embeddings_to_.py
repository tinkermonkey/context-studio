"""add title/definition embeddings to ontology_entities

Revision ID: c41e519a8e61
Revises: 4e9f681d74cd
Create Date: 2026-06-14 08:52:10.320326

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c41e519a8e61"
down_revision = "4e9f681d74cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Two derived embedding columns for schema vector search (title and
    # description embedded separately so search can report which field matched).
    # The unrelated batch_runs.run_type drift autogenerate also detected is left
    # out of this migration — it belongs to its own change, not this one.
    op.add_column(
        "ontology_entities", sa.Column("title_embedding", sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        "ontology_entities", sa.Column("definition_embedding", sa.LargeBinary(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ontology_entities", "definition_embedding")
    op.drop_column("ontology_entities", "title_embedding")
