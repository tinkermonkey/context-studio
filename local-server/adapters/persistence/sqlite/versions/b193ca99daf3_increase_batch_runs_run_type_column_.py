"""Increase batch_runs.run_type column width from 20 to 50

Revision ID: b193ca99daf3
Revises: 518a8c514f35
Create Date: 2026-05-23 09:00:29.065925

For SQLite: The run_type column stores discriminator values including
'schema_node_definition_refinement' (33 chars), which exceeds the previous
String(20) limit. SQLite doesn't enforce string length limits at the database
level, but the schema definition is updated to String(50) for documentation
and cross-database compatibility.

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b193ca99daf3'
down_revision = '518a8c514f35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
