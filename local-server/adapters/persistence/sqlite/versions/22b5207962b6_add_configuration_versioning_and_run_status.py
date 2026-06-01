"""Add configuration versioning and run status fields to pipeline_runs

Revision ID: 22b5207962b6
Revises: f319bb8dc961
Create Date: 2026-05-31 16:15:31.590815

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '22b5207962b6'
down_revision = 'f319bb8dc961'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'pipeline_runs',
        sa.Column('configuration_slug', sa.String(length=255), nullable=False, server_default='')
    )
    op.add_column(
        'pipeline_runs',
        sa.Column('configuration_version', sa.Integer(), nullable=False, server_default='1')
    )
    op.add_column(
        'pipeline_runs',
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'pipeline_runs',
        sa.Column('failure_reason', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('pipeline_runs', 'failure_reason')
    op.drop_column('pipeline_runs', 'started_at')
    op.drop_column('pipeline_runs', 'configuration_version')
    op.drop_column('pipeline_runs', 'configuration_slug')
