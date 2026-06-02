"""Add color column and backfill identifier slugs for schema entities

Revision ID: f319bb8dc961
Revises: 79d973513131
Create Date: 2026-05-29 06:49:48.522591

Adds the `color` column on `ontology_entities` (hex string `#rrggbb`, optional)
and backfills `identifier` slugs for any existing taxonomy / concept_scheme /
class rows that don't already have one. Property definitions already carry an
identifier and are untouched.

Slug format: `<prefix>_<8-hex-id>` (e.g. `tax_27a81106`). Property definitions
keep their existing identifiers; the column's pre-existing UNIQUE constraint
continues to enforce global uniqueness across all node types.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f319bb8dc961"
down_revision = "79d973513131"
branch_labels = None
depends_on = None


_PREFIX_BY_NODE_TYPE = {
    "taxonomy": "tax",
    "concept_scheme": "scheme",
    "class": "cls",
}


def upgrade() -> None:
    op.add_column(
        "ontology_entities",
        sa.Column("color", sa.String(length=7), nullable=True),
    )

    conn = op.get_bind()
    for node_type, prefix in _PREFIX_BY_NODE_TYPE.items():
        rows = conn.execute(
            sa.text(
                "SELECT id FROM ontology_entities "
                "WHERE node_type = :node_type AND (identifier IS NULL OR identifier = '')"
            ),
            {"node_type": node_type},
        ).fetchall()
        for (entity_id,) in rows:
            short = entity_id.replace("-", "")[:8]
            slug = f"{prefix}_{short}"
            conn.execute(
                sa.text("UPDATE ontology_entities SET identifier = :slug WHERE id = :entity_id"),
                {"slug": slug, "entity_id": entity_id},
            )


def downgrade() -> None:
    # Backfilled identifiers are not reverted — they remain valid slugs.
    op.drop_column("ontology_entities", "color")
