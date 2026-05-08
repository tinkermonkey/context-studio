"""Add constraints to extraction_runs table for data integrity

Revision ID: dea59f0b2b28
Revises: 7609a5828f1b
Create Date: 2026-05-08 17:28:42.170847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dea59f0b2b28'
down_revision = '7609a5828f1b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add constraints to extraction_runs table to enforce domain invariants
    with op.batch_alter_table('extraction_runs', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_temperature_min',
            'temperature >= 0.0',
        )
        batch_op.create_check_constraint(
            'check_temperature_max',
            'temperature <= 2.0',
        )
        batch_op.create_check_constraint(
            'check_tokens_non_negative',
            'tokens_used >= 0',
        )
        batch_op.create_check_constraint(
            'check_duration_non_negative',
            'duration_ms >= 0',
        )
        batch_op.create_check_constraint(
            'check_triples_extracted_non_negative',
            'triples_extracted >= 0',
        )
        batch_op.create_check_constraint(
            'check_triples_committed_non_negative',
            'triples_committed >= 0',
        )
        batch_op.create_check_constraint(
            'check_triples_committed_le_extracted',
            'triples_committed <= triples_extracted',
        )


def downgrade() -> None:
    # Remove constraints from extraction_runs table
    with op.batch_alter_table('extraction_runs', schema=None) as batch_op:
        batch_op.drop_constraint('check_triples_committed_le_extracted', type_='check')
        batch_op.drop_constraint('check_triples_committed_non_negative', type_='check')
        batch_op.drop_constraint('check_triples_extracted_non_negative', type_='check')
        batch_op.drop_constraint('check_duration_non_negative', type_='check')
        batch_op.drop_constraint('check_tokens_non_negative', type_='check')
        batch_op.drop_constraint('check_temperature_max', type_='check')
        batch_op.drop_constraint('check_temperature_min', type_='check')
