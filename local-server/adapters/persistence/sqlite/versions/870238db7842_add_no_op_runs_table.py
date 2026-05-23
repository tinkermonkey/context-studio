"""Add no_op_runs table for NoOpPipelineRun

Revision ID: 870238db7842
Revises: 99ba9cc55512
Create Date: 2026-05-23 00:59:42.651852

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '870238db7842'
down_revision = '99ba9cc55512'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('no_op_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['id'], ['pipeline_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('no_op_runs')
