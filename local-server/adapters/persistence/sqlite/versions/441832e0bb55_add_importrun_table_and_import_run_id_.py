"""Add ImportRun table and import_run_id to ChangeEvent

Revision ID: 441832e0bb55
Revises: b2ac4e5f3d7a
Create Date: 2026-05-03 10:42:43.342376

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '441832e0bb55'
down_revision = 'b2ac4e5f3d7a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create import_runs table
    op.create_table('import_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('format', sa.String(length=20), nullable=False),
        sa.Column('source_uri', sa.Text(), nullable=True),
        sa.Column('source_hash', sa.String(length=64), nullable=False),
        sa.Column('scope_type', sa.String(length=20), nullable=False),
        sa.Column('scope_taxonomy_id', sa.String(length=36), nullable=True),
        sa.Column('scope_scheme_id', sa.String(length=36), nullable=True),
        sa.Column('scope_include_descendants', sa.Boolean(), nullable=False),
        sa.Column('scope_entity_ids', sa.JSON(), nullable=True),
        sa.Column('resolutions', sa.JSON(), nullable=False),
        sa.Column('affected_entity_ids', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Add import_run_id column to change_events using batch mode for SQLite
    with op.batch_alter_table('change_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_run_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_change_events_import_run_id', 'import_runs', ['import_run_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('idx_import_run_id', ['import_run_id'], unique=False)

    op.drop_index(op.f('idx_class_id'), table_name='individual_classes')


def downgrade() -> None:
    # Re-add idx_class_id to individual_classes
    op.create_index(op.f('idx_class_id'), 'individual_classes', ['class_id'], unique=False)

    # Remove import_run_id column from change_events using batch mode
    with op.batch_alter_table('change_events', schema=None) as batch_op:
        batch_op.drop_index('idx_import_run_id')
        batch_op.drop_constraint('fk_change_events_import_run_id', type_='foreignkey')
        batch_op.drop_column('import_run_id')

    # Drop import_runs table
    op.drop_table('import_runs')
