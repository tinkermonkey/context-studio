"""add_pipeline_flavors_table

Revision ID: 712819403e8b
Revises: b3e4c9d7f2a1
Create Date: 2026-05-11 22:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "712819403e8b"
down_revision = "b3e4c9d7f2a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_flavors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_flavors_name", "pipeline_flavors", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_pipeline_flavors_name", table_name="pipeline_flavors")
    op.drop_table("pipeline_flavors")
