"""dr sample dataset yields to the schema

Context Studio's own DR model lives in the DR spec taxonomy (`dr_spec`). Its
`default` dataset becomes `context-studio` and yields to the schema (#1485), so
spec proposals never block on it. Data only: autogenerate found no schema change.

Revision ID: fc64b1c76476
Revises: a61cfa4aa3d7
Create Date: 2026-11-09 19:48:46.650069

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'fc64b1c76476'
down_revision = 'a61cfa4aa3d7'
branch_labels = None
depends_on = None


_DR_TAXONOMY = (
    "(SELECT id FROM ontology_entities WHERE node_type = 'taxonomy' AND identifier = 'dr_spec')"
)


def upgrade() -> None:
    op.execute(
        "UPDATE datasets SET identifier = 'context-studio', title = 'Context Studio',"
        f" yields_to_schema = 1 WHERE identifier = 'default' AND taxonomy_id = {_DR_TAXONOMY}"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE datasets SET identifier = 'default', title = 'Default', yields_to_schema = 0"
        f" WHERE identifier = 'context-studio' AND taxonomy_id = {_DR_TAXONOMY}"
    )
