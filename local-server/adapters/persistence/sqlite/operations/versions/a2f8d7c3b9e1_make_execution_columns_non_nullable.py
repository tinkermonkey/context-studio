"""Make ExecutionModel columns non-nullable

Revision ID: a2f8d7c3b9e1
Revises: 619a27b89a15
Create Date: 2026-03-29 06:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2f8d7c3b9e1'
down_revision = '619a27b89a15'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Drop the old index first
    op.drop_index('ix_executions_config_timestamp', table_name='pipeline_executions')

    # Rename the old table
    op.execute('ALTER TABLE pipeline_executions RENAME TO pipeline_executions_old')

    # Create the new table with updated schema
    op.create_table('pipeline_executions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('pipeline_config_id', sa.String(length=36), nullable=False),
    sa.Column('input_text', sa.Text(), nullable=False),
    sa.Column('output_text', sa.Text(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('model', sa.String(length=255), nullable=False),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )

    # Copy data from old table to new table
    op.execute('''INSERT INTO pipeline_executions
        (id, pipeline_config_id, input_text, output_text, provider, model,
         tokens_in, tokens_out, duration_ms, status, error_message, timestamp)
        SELECT id, pipeline_config_id, COALESCE(input_text, ''), COALESCE(output_text, ''),
               COALESCE(provider, ''), COALESCE(model, ''),
               tokens_in, tokens_out, duration_ms, status, error_message, timestamp
        FROM pipeline_executions_old''')

    # Drop the old table
    op.drop_table('pipeline_executions_old')

    # Recreate indexes
    op.create_index('ix_executions_config_timestamp', 'pipeline_executions',
                    ['pipeline_config_id', 'timestamp'], unique=False)
    op.create_index('ix_pipeline_executions_timestamp', 'pipeline_executions',
                    ['timestamp'], unique=False)


def downgrade() -> None:
    # Drop the index
    op.drop_index('ix_executions_config_timestamp', table_name='pipeline_executions')
    op.drop_index('ix_pipeline_executions_timestamp', table_name='pipeline_executions')

    # Rename the table
    op.execute('ALTER TABLE pipeline_executions RENAME TO pipeline_executions_new')

    # Recreate the old table with nullable columns
    op.create_table('pipeline_executions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('pipeline_config_id', sa.String(length=36), nullable=False),
    sa.Column('input_text', sa.Text(), nullable=True),
    sa.Column('output_text', sa.Text(), nullable=True),
    sa.Column('provider', sa.String(length=50), nullable=True),
    sa.Column('model', sa.String(length=255), nullable=True),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )

    # Copy data from new table to old table
    op.execute('''INSERT INTO pipeline_executions
        (id, pipeline_config_id, input_text, output_text, provider, model,
         tokens_in, tokens_out, duration_ms, status, error_message, timestamp)
        SELECT id, pipeline_config_id, NULLIF(input_text, ''), NULLIF(output_text, ''),
               NULLIF(provider, ''), NULLIF(model, ''),
               tokens_in, tokens_out, duration_ms, status, error_message, timestamp
        FROM pipeline_executions_new''')

    # Drop the new table
    op.drop_table('pipeline_executions_new')

    # Recreate indexes
    op.create_index('ix_executions_config_timestamp', 'pipeline_executions',
                    ['pipeline_config_id', 'timestamp'], unique=False)
