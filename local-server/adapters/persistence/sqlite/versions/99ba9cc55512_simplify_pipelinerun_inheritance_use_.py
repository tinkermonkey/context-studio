"""Simplify PipelineRun inheritance - use run_type for pipeline type discrimination

Revision ID: 99ba9cc55512
Revises: 787b97be9400
Create Date: 2026-05-22 22:24:00.000000

This migration simplifies the polymorphic inheritance of PipelineRun by using
run_type directly for pipeline type discrimination instead of a intermediate
'pipeline' value. This aligns better with SQLAlchemy's polymorphic inheritance.

The new run_type values are:
- 'import' (for ImportRun)
- 'extraction' (for ExtractionRun, kept for backward compat)
- 'individual_extraction' (for IndividualExtractionRun)
- 'schema_extraction' (for SchemaExtractionRun)
- 'schema_node_grounding' (for SchemaGroundingRun)
- 'schema_node_definition_refinement' (for SchemaDefinitionRefinementRun)
- 'schema_node_connection_refinement' (for SchemaConnectionRefinementRun)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99ba9cc55512'
down_revision = '787b97be9400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update the batch_runs constraint to include all pipeline type run_types
    op.execute("""
        CREATE TABLE batch_runs_new (
            id TEXT PRIMARY KEY NOT NULL,
            created_at DATETIME NOT NULL,
            created_by TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            affected_entity_ids JSON NOT NULL DEFAULT '[]',
            run_type TEXT NOT NULL,
            CHECK (run_type IN ('import', 'extraction', 'individual_extraction',
                'schema_extraction', 'schema_node_grounding',
                'schema_node_definition_refinement', 'schema_node_connection_refinement'))
        )
    """)

    op.execute("INSERT INTO batch_runs_new SELECT * FROM batch_runs")
    op.execute("DROP TABLE batch_runs")
    op.execute("ALTER TABLE batch_runs_new RENAME TO batch_runs")

    # Recreate indices on batch_runs
    op.execute("CREATE INDEX idx_run_type_status ON batch_runs(run_type, status)")


def downgrade() -> None:
    pass
