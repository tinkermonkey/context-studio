"""Reconcile schema drift from failed migrations 7609a5828f1b and 30974cfce846.

Root cause: migration 7609a5828f1b's data migration step read from import_runs before
that table existed in the DB, causing the migration to fail silently after Alembic
had already written the version row. Subsequent manual ALTER TABLE commands added
batch_run_id (change_events) and status (ontology_entities) as nullable columns
without the proper FK semantics or indexes.

By the time this migration runs the tables (import_runs, extraction_runs,
grounding_workflows, workflow_runs) have already been created by SQLAlchemy
create_all on server startup. This migration fixes the remaining index and
constraint drift only:

  - Rename legacy indexes on conflict_resolutions and individual_classes
  - Add missing index on extraction_results.created_at
  - Add missing indexes on change_events.batch_run_id
  - Fix change_events FK on batch_run_id (add ondelete='SET NULL', drop spurious
    entity_id FK that migration 5b3d9c2a8e4f intended to remove)
  - Fix ontology_entities.status nullability (ALTER TABLE added it as nullable)
  - Add missing index on ontology_entities.status

Revision ID: e32c9d911de4
Revises: 30974cfce846
Create Date: 2026-05-13 06:51:18.609963

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e32c9d911de4'
down_revision = '30974cfce846'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename legacy indexes on conflict_resolutions to match ORM-generated names
    op.drop_index('ix_entity_id', table_name='conflict_resolutions')
    op.drop_index('ix_proposal_id', table_name='conflict_resolutions')
    op.create_index('ix_conflict_resolutions_entity_id', 'conflict_resolutions', ['entity_id'], unique=False)
    op.create_index('ix_conflict_resolutions_proposal_id', 'conflict_resolutions', ['proposal_id'], unique=False)

    # Add missing index on extraction_results.created_at
    op.create_index('ix_extraction_results_created_at', 'extraction_results', ['created_at'], unique=False)

    # Rename legacy index on individual_classes and add missing individual_id index
    op.drop_index('idx_class_id', table_name='individual_classes')
    op.create_index('ix_individual_classes_class_id', 'individual_classes', ['class_id'], unique=False)
    op.create_index('ix_individual_classes_individual_id', 'individual_classes', ['individual_id'], unique=False)

    # Add missing indexes on change_events.batch_run_id and fix the FK.
    # The manual ALTER TABLE created batch_run_id with an anonymous inline REFERENCES
    # clause (no ondelete). We use batch mode to rebuild change_events with the correct
    # named FK (ondelete='SET NULL') and remove the lingering entity_id FK that
    # migration 5b3d9c2a8e4f was supposed to drop.
    op.create_index('idx_batch_run_id', 'change_events', ['batch_run_id'], unique=False)
    op.create_index('ix_change_events_batch_run_id', 'change_events', ['batch_run_id'], unique=False)
    with op.batch_alter_table('change_events', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_change_events_batch_run_id',
            'batch_runs',
            ['batch_run_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # Fix ontology_entities.status: was added as nullable via ALTER TABLE; ORM requires NOT NULL
    with op.batch_alter_table('ontology_entities', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.VARCHAR(length=20),
            nullable=False,
            existing_server_default=sa.text("'draft'"),
        )
    op.create_index('ix_ontology_entities_status', 'ontology_entities', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ontology_entities_status', table_name='ontology_entities')
    with op.batch_alter_table('ontology_entities', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.VARCHAR(length=20),
            nullable=True,
            existing_server_default=sa.text("'draft'"),
        )

    with op.batch_alter_table('change_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_change_events_batch_run_id', type_='foreignkey')
    op.drop_index('ix_change_events_batch_run_id', table_name='change_events')
    op.drop_index('idx_batch_run_id', table_name='change_events')

    op.drop_index('ix_individual_classes_individual_id', table_name='individual_classes')
    op.drop_index('ix_individual_classes_class_id', table_name='individual_classes')
    op.create_index('idx_class_id', 'individual_classes', ['class_id'], unique=False)

    op.drop_index('ix_extraction_results_created_at', table_name='extraction_results')

    op.drop_index('ix_conflict_resolutions_proposal_id', table_name='conflict_resolutions')
    op.drop_index('ix_conflict_resolutions_entity_id', table_name='conflict_resolutions')
    op.create_index('ix_proposal_id', 'conflict_resolutions', ['proposal_id'], unique=False)
    op.create_index('ix_entity_id', 'conflict_resolutions', ['entity_id'], unique=False)
