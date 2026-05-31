"""Add batch lifecycle timestamps: started_at, completed_at, last_updated

Revision ID: 4e9f681d74cd
Revises: f79a82b425a2
Create Date: 2026-05-31 21:44:18.860362

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '4e9f681d74cd'
down_revision = 'f79a82b425a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'batches', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'batches', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'batches',
        sa.Column(
            'last_updated',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index('idx_batch_id_status', 'batches', ['id', 'status'], unique=False)
    op.create_index('ix_batches_started_at', 'batches', ['started_at'], unique=False)
    op.create_index('ix_batches_completed_at', 'batches', ['completed_at'], unique=False)
    op.create_index('ix_batches_last_updated', 'batches', ['last_updated'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_batches_last_updated', table_name='batches')
    op.drop_index('ix_batches_completed_at', table_name='batches')
    op.drop_index('ix_batches_started_at', table_name='batches')
    op.drop_index('idx_batch_id_status', table_name='batches')
    op.drop_column('batches', 'last_updated')
    op.drop_column('batches', 'completed_at')
    op.drop_column('batches', 'started_at')
