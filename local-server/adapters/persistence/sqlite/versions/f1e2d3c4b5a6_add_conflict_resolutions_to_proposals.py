"""Add conflict_resolutions to proposals

Revision ID: f1e2d3c4b5a6
Revises: d4e5f6a7b8c9
Create Date: 2026-03-30 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1e2d3c4b5a6'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add conflict_resolutions column to proposals table
    op.add_column('proposals', sa.Column('conflict_resolutions', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    # Remove conflict_resolutions column from proposals table
    op.drop_column('proposals', 'conflict_resolutions')
