"""Update batch_runs CHECK constraint for pipeline run types

Revision ID: 99ba9cc55512
Revises: 01e4a27284f4
Create Date: 2026-05-22 22:20:00.000000

Combines constraint updates for pipeline run types (individual_extraction, schema_extraction,
etc.) in a single table rebuild operation instead of multiple sequential rebuilds.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "99ba9cc55512"
down_revision = "01e4a27284f4"
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
                'schema_node_definition_refinement', 'schema_node_connection_refinement',
                'no_op'))
        )
    """)

    op.execute("INSERT INTO batch_runs_new SELECT * FROM batch_runs")
    op.execute("DROP TABLE batch_runs")
    op.execute("ALTER TABLE batch_runs_new RENAME TO batch_runs")

    # Recreate indices on batch_runs
    op.execute("CREATE INDEX idx_run_type_status ON batch_runs(run_type, status)")


def downgrade() -> None:
    pass
