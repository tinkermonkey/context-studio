"""drop the leftover dr spec reference

The DR taxonomy's documentation_robotics/spec reference was made to hold DR's
predicate catalog (#1383). The catalog moved to the predicates table (#1480,
37f2a2e39452), which left the reference holding only ``spec_version``: a stale
copy of the taxonomy's ``source_revision`` (#1463), which drift stamps and DR
reads. The importer no longer writes it; this drops it from every taxonomy that
has it, leaving the taxonomy's other references as they are.

Data only: autogenerate finds no schema change (beyond the pre-existing index
drift on extraction_results and individual_classes).

Revision ID: 76b182ca4cbb
Revises: 3d7b38dca806
Create Date: 2026-11-11 12:07:57.815907

"""

import json
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "76b182ca4cbb"
down_revision = "3d7b38dca806"
branch_labels = None
depends_on = None

DR_SOURCE = "documentation_robotics"
DR_SPEC_IDENTIFIER = "spec"

entities_table = sa.table(
    "ontology_entities",
    sa.column("id", sa.String),
    sa.column("external_references", sa.JSON),
)


def _json_list(value: Any) -> list[dict[str, Any]]:
    """A stored JSON list column as a Python list (tolerates raw strings and NULL)."""
    if isinstance(value, str):
        value = json.loads(value)
    return list(value or [])


def _is_dr_spec_reference(ref: dict[str, Any]) -> bool:
    return ref.get("source") == DR_SOURCE and ref.get("identifier") == DR_SPEC_IDENTIFIER


def upgrade() -> None:
    conn = op.get_bind()
    taxonomies = conn.execute(
        sa.text(
            "SELECT id, external_references FROM ontology_entities WHERE node_type = 'taxonomy'"
        )
    ).fetchall()
    for taxonomy_id, raw_refs in taxonomies:
        refs = _json_list(raw_refs)
        kept = [ref for ref in refs if not _is_dr_spec_reference(ref)]
        if len(kept) == len(refs):
            continue
        conn.execute(
            entities_table.update()
            .where(entities_table.c.id == taxonomy_id)
            .values(external_references=kept)
        )


def downgrade() -> None:
    # No-op: the reference held only a stale spec_version, which the taxonomy's
    # source_revision records; nothing reads it, so there is nothing to restore.
    pass
