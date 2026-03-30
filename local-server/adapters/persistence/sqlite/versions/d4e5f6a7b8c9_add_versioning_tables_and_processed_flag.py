"""Add versioning tables and processed flag

Revision ID: d4e5f6a7b8c9
Revises: 3c8f2e9a1b5c
Create Date: 2026-03-30 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '3c8f2e9a1b5c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add processed column to change_events table
    op.add_column('change_events', sa.Column('processed', sa.Boolean(), nullable=False, server_default='0'))
    op.create_index('idx_processed', 'change_events', ['processed'], unique=False)

    # Create entity_versions table
    op.create_table(
        'entity_versions',
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('parent_version', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('entity_id', 'version', name='pk_entity_versions')
    )

    # Create changesets table
    op.create_table(
        'changesets',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('state', sa.String(20), nullable=False, server_default='working'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id', name='pk_changesets')
    )

    # Create changeset_events table (junction table)
    op.create_table(
        'changeset_events',
        sa.Column('changeset_id', sa.String(36), nullable=False),
        sa.Column('change_event_id', sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(['changeset_id'], ['changesets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['change_event_id'], ['change_events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('changeset_id', 'change_event_id', name='pk_changeset_events')
    )
    op.create_index('ix_changeset_events_changeset_id', 'changeset_events', ['changeset_id'])
    op.create_index('ix_changeset_events_change_event_id', 'changeset_events', ['change_event_id'])

    # Create proposals table
    op.create_table(
        'proposals',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('changeset_id', sa.String(36), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='open'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['changeset_id'], ['changesets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_proposals')
    )
    op.create_index('ix_proposals_changeset_id', 'proposals', ['changeset_id'])


def downgrade() -> None:
    # Drop proposals table
    op.drop_index('ix_proposals_changeset_id', table_name='proposals')
    op.drop_table('proposals')

    # Drop changeset_events table
    op.drop_index('ix_changeset_events_change_event_id', table_name='changeset_events')
    op.drop_index('ix_changeset_events_changeset_id', table_name='changeset_events')
    op.drop_table('changeset_events')

    # Drop changesets table
    op.drop_table('changesets')

    # Drop entity_versions table
    op.drop_table('entity_versions')

    # Remove processed column from change_events
    op.drop_index('idx_processed', table_name='change_events')
    op.drop_column('change_events', 'processed')
