"""Update batch_runs CHECK constraint to include pipeline run type

Revision ID: 787b97be9400
Revises: 01e4a27284f4
Create Date: 2026-05-22 22:19:51.540124

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '787b97be9400'
down_revision = '01e4a27284f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't allow altering constraints directly; we must recreate the table.
    # First, save the existing data, drop the table with the old constraint, and recreate it.

    op.execute("""
        CREATE TABLE batch_runs_new (
            id TEXT PRIMARY KEY NOT NULL,
            created_at DATETIME NOT NULL,
            created_by TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            affected_entity_ids JSON NOT NULL DEFAULT '[]',
            run_type TEXT NOT NULL,
            CHECK (run_type IN ('import', 'extraction', 'pipeline'))
        )
    """)

    op.execute("INSERT INTO batch_runs_new SELECT * FROM batch_runs")
    op.execute("DROP TABLE batch_runs")
    op.execute("ALTER TABLE batch_runs_new RENAME TO batch_runs")

    # Recreate indices on batch_runs
    op.execute("CREATE INDEX idx_run_type_status ON batch_runs(run_type, status)")


def downgrade() -> None:
    # Revert to old constraint
    op.execute("""
        CREATE TABLE batch_runs_new (
            id TEXT PRIMARY KEY NOT NULL,
            created_at DATETIME NOT NULL,
            created_by TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            affected_entity_ids JSON NOT NULL DEFAULT '[]',
            run_type TEXT NOT NULL,
            CHECK (run_type IN ('import', 'extraction'))
        )
    """)

    op.execute("INSERT INTO batch_runs_new SELECT * FROM batch_runs")
    op.execute("DROP TABLE batch_runs")
    op.execute("ALTER TABLE batch_runs_new RENAME TO batch_runs")

    # Recreate indices on batch_runs
    op.execute("CREATE INDEX idx_run_type_status ON batch_runs(run_type, status)")
