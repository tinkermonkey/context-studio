"""add_batches_table_and_batch_id_column

Revision ID: f79a82b425a2
Revises: 22b5207962b6
Create Date: 2026-05-31 18:28:24.473073

"""

import sqlalchemy as sa
from alembic import op

revision = "f79a82b425a2"
down_revision = "22b5207962b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="check_valid_batch_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_batches_created_at"), "batches", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_batches_status"), "batches", ["status"], unique=False)

    with op.batch_alter_table("batch_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("batch_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            op.f("ix_batch_runs_batch_id"), ["batch_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_batch_runs_batch_id",
            "batches",
            ["batch_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("batch_runs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_batch_runs_batch_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_batch_runs_batch_id"))
        batch_op.drop_column("batch_id")

    op.drop_index(op.f("ix_batches_status"), table_name="batches")
    op.drop_index(op.f("ix_batches_created_at"), table_name="batches")
    op.drop_table("batches")
