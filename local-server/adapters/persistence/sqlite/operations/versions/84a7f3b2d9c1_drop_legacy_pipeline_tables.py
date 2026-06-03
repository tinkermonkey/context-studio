"""drop_legacy_pipeline_tables

Revision ID: 84a7f3b2d9c1
Revises: 712819403e8b
Create Date: 2026-05-31 12:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "84a7f3b2d9c1"
down_revision = "712819403e8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_executions_config_timestamp", table_name="pipeline_executions")
    op.drop_index(
        "ix_pipeline_configurations_pipeline", table_name="pipeline_configurations"
    )
    op.drop_index("ix_pipeline_flavors_name", table_name="pipeline_flavors")
    op.drop_table("pipeline_executions")
    op.drop_table("pipeline_configurations")
    op.drop_table("pipeline_flavors")


def downgrade() -> None:
    op.create_table(
        "pipeline_flavors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_flavors_name", "pipeline_flavors", ["name"], unique=True
    )
    op.create_table(
        "pipeline_configurations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pipeline", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_configurations_pipeline",
        "pipeline_configurations",
        ["pipeline"],
        unique=False,
    )
    op.create_table(
        "pipeline_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pipeline_config_id", sa.String(length=36), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_executions_config_timestamp",
        "pipeline_executions",
        ["pipeline_config_id", "timestamp"],
        unique=False,
    )
