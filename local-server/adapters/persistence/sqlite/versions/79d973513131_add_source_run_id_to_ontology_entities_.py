"""add_source_run_id_to_ontology_entities_and_relationships

Revision ID: 79d973513131
Revises: b193ca99daf3
Create Date: 2026-05-23 21:17:55.211928

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '79d973513131'
down_revision = 'b193ca99daf3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All prior tables (datasets, pipeline_runs, *_runs subtypes) already exist in the DB;
    # this migration only adds the two new source_run_id columns introduced for pipeline
    # traceability. The catch-up DDL detected by autogenerate was removed because those
    # tables were created outside Alembic tracking and are already present.
    op.add_column('ontology_entities', sa.Column('source_run_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_ontology_entities_source_run_id'), 'ontology_entities', ['source_run_id'], unique=False)
    op.add_column('relationships', sa.Column('source_run_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_relationships_source_run_id'), 'relationships', ['source_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_relationships_source_run_id'), table_name='relationships')
    op.drop_column('relationships', 'source_run_id')
    op.drop_index(op.f('ix_ontology_entities_source_run_id'), table_name='ontology_entities')
    op.drop_column('ontology_entities', 'source_run_id')
