"""add domain range to property definitions

Revision ID: 6261ddb1ad72
Revises: c41e519a8e61
Create Date: 2026-07-07 19:34:02.318547

"""
import sqlalchemy as sa
from alembic import op

revision = "6261ddb1ad72"
down_revision = "c41e519a8e61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ontology_entities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("domain_class_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("range_class_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            op.f("ix_ontology_entities_domain_class_id"), ["domain_class_id"], unique=False
        )
        batch_op.create_index(
            op.f("ix_ontology_entities_range_class_id"), ["range_class_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_ontology_entities_domain_class_id",
            "ontology_entities",
            ["domain_class_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_ontology_entities_range_class_id",
            "ontology_entities",
            ["range_class_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("property_definitions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("domain_class_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("range_class_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            op.f("ix_property_definitions_domain_class_id"), ["domain_class_id"], unique=False
        )
        batch_op.create_index(
            op.f("ix_property_definitions_range_class_id"), ["range_class_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_property_definitions_domain_class_id",
            "ontology_entities",
            ["domain_class_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_property_definitions_range_class_id",
            "ontology_entities",
            ["range_class_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("property_definitions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_property_definitions_range_class_id", type_="foreignkey")
        batch_op.drop_constraint("fk_property_definitions_domain_class_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_property_definitions_range_class_id"))
        batch_op.drop_index(op.f("ix_property_definitions_domain_class_id"))
        batch_op.drop_column("range_class_id")
        batch_op.drop_column("domain_class_id")

    with op.batch_alter_table("ontology_entities", schema=None) as batch_op:
        batch_op.drop_constraint("fk_ontology_entities_range_class_id", type_="foreignkey")
        batch_op.drop_constraint("fk_ontology_entities_domain_class_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_ontology_entities_range_class_id"))
        batch_op.drop_index(op.f("ix_ontology_entities_domain_class_id"))
        batch_op.drop_column("range_class_id")
        batch_op.drop_column("domain_class_id")
