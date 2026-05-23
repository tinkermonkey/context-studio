"""Add no_op to batch_runs CHECK constraint

Revision ID: 518a8c514f35
Revises: 870238db7842
Create Date: 2026-05-23 05:14:01.749643

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '518a8c514f35'
down_revision = '870238db7842'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update batch_runs CHECK constraint to include 'no_op' run type
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
    op.execute("CREATE INDEX ix_batch_runs_created_at ON batch_runs(created_at)")
    op.execute("CREATE INDEX ix_batch_runs_status ON batch_runs(status)")
    op.execute("CREATE INDEX ix_batch_runs_run_type ON batch_runs(run_type)")


def downgrade() -> None:
    # Revert batch_runs CHECK constraint to exclude 'no_op' run type
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

    op.execute("INSERT INTO batch_runs_new SELECT * FROM batch_runs WHERE run_type != 'no_op'")
    op.execute("DROP TABLE batch_runs")
    op.execute("ALTER TABLE batch_runs_new RENAME TO batch_runs")

    # Recreate indices on batch_runs
    op.execute("CREATE INDEX idx_run_type_status ON batch_runs(run_type, status)")
    op.execute("CREATE INDEX ix_batch_runs_created_at ON batch_runs(created_at)")
    op.execute("CREATE INDEX ix_batch_runs_status ON batch_runs(status)")
    op.execute("CREATE INDEX ix_batch_runs_run_type ON batch_runs(run_type)")
