"""backfill derived flag from legacy reference metadata

Before #1465 made `derived` a column, House recorded it as `derived: true` in its
external reference's metadata. 7512875103f3 added the column without a backfill,
so those classes and relationship types read as not derived and bundle v1 (#1483)
exports them that way. Set the column from the legacy key. The metadata copy
stays, as the bundle importer expects.

Data only: autogenerate found no schema change (it listed the pre-existing index
drift on individual_classes and extraction_results, left out as in 7512875103f3).

Revision ID: b2cd90812677
Revises: d8b3aea1f6bf
Create Date: 2026-11-10 08:02:50.617620

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b2cd90812677'
down_revision = 'd8b3aea1f6bf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE ontology_entities SET derived = 1"
        " WHERE derived = 0"
        " AND node_type IN ('class', 'property_definition')"
        " AND json_valid(external_references)"
        " AND EXISTS ("
        "   SELECT 1 FROM json_each(ontology_entities.external_references) AS ref"
        "   WHERE ref.type = 'object'"
        "   AND json_extract(ref.value, '$.metadata.derived') = 1"
        " )"
    )


def downgrade() -> None:
    # Backfilled flags can't be told apart from ones set later, so they stay.
    pass
