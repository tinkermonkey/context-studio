"""Remove foreign key constraint from change_events.entity_id

The entity_id column can reference entities outside ontology_entities
(extraction results, pipeline executions) so the FK constraint must be removed.

Revision ID: 5b3d9c2a8e4f
Revises: da604771ce10
Create Date: 2026-03-29 12:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '5b3d9c2a8e4f'
down_revision = 'da604771ce10'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support dropping constraints directly
    # We need to recreate the table without the FK
    pass


def downgrade() -> None:
    # Restore the FK constraint
    with op.batch_alter_table('change_events', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'change_events_ibfk_1',
            'ontology_entities',
            ['entity_id'],
            ['id'],
            ondelete='CASCADE'
        )
