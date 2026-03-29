"""Add extraction results table

Revision ID: 3c8f2e9a1b5c
Revises: 5b3d9c2a8e4f
Create Date: 2026-03-29 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c8f2e9a1b5c'
down_revision = '5b3d9c2a8e4f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extraction_results table
    op.create_table(
        'extraction_results',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('extracted_entities', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('layers_executed', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('total_duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id', name='pk_extraction_results')
    )
    # Create index on created_at for efficient sorting
    op.create_index('idx_created_at', 'extraction_results', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop index and table
    op.drop_index('idx_created_at', table_name='extraction_results')
    op.drop_table('extraction_results')
