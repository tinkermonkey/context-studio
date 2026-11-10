"""datasets over one schema

Replaces the unused `datasets` table (importable database files, never
populated) with named datasets over a taxonomy's schema, and puts every
individual in one.

Autogenerate rendered the table change as column-by-column alters of the old
table and the new foreign keys as unnamed SQLite ALTERs, which fail; it also
cannot see CHECK constraints. The script below keeps its operations but drops
and recreates the table, uses batch mode for `ontology_entities`, names the
constraints, and adds the data step: each taxonomy with individuals gets a
dataset `default` holding them, before the CHECK that every individual has a
dataset.

Revision ID: a61cfa4aa3d7
Revises: 7512875103f3
Create Date: 2026-11-09 19:10:01.587570

"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a61cfa4aa3d7'
down_revision = '7512875103f3'
branch_labels = None
depends_on = None


def _backfill_default_datasets() -> None:
    """Put each taxonomy's individuals in a new dataset `default`."""
    bind = op.get_bind()
    orphans = bind.exec_driver_sql(
        "SELECT count(*) FROM ontology_entities i WHERE i.node_type = 'individual'"
        " AND NOT EXISTS (SELECT 1 FROM individual_classes ic WHERE ic.individual_id = i.id)"
    ).scalar()
    if orphans:
        raise RuntimeError(
            f"{orphans} individual(s) have no class, so their taxonomy (and dataset)"
            " is unknown; give each a class or delete it, then upgrade again"
        )
    spanning = bind.exec_driver_sql(
        "SELECT count(*) FROM (SELECT ic.individual_id FROM individual_classes ic"
        " JOIN ontology_entities c ON c.id = ic.class_id"
        " GROUP BY ic.individual_id HAVING count(DISTINCT c.taxonomy_id) > 1)"
    ).scalar()
    if spanning:
        raise RuntimeError(
            f"{spanning} individual(s) have classes in more than one taxonomy, so no one"
            " dataset can hold them; give each classes of one taxonomy, then upgrade again"
        )
    crossing = bind.exec_driver_sql(
        "SELECT count(*) FROM relationships r"
        " JOIN individual_classes s ON s.individual_id = r.source_id AND s.position = 0"
        " JOIN individual_classes t ON t.individual_id = r.target_id AND t.position = 0"
        " JOIN ontology_entities sc ON sc.id = s.class_id"
        " JOIN ontology_entities tc ON tc.id = t.class_id"
        " WHERE sc.taxonomy_id != tc.taxonomy_id"
    ).scalar()
    if crossing:
        raise RuntimeError(
            f"{crossing} relationship(s) link individuals of two taxonomies, which would"
            " cross datasets; delete them, then upgrade again"
        )
    # Each individual's taxonomy is its first class's taxonomy.
    rows = bind.exec_driver_sql(
        "SELECT ic.individual_id, c.taxonomy_id FROM individual_classes ic"
        " JOIN ontology_entities c ON c.id = ic.class_id"
        " WHERE ic.position = (SELECT min(position) FROM individual_classes"
        " WHERE individual_id = ic.individual_id)"
    ).fetchall()
    now = datetime.now(timezone.utc)
    dataset_by_taxonomy: dict[str, str] = {}
    for individual_id, taxonomy_id in rows:
        dataset_id = dataset_by_taxonomy.get(taxonomy_id)
        if dataset_id is None:
            dataset_id = str(uuid.uuid4())
            dataset_by_taxonomy[taxonomy_id] = dataset_id
            bind.execute(
                sa.text(
                    "INSERT INTO datasets (id, taxonomy_id, identifier, title,"
                    " yields_to_schema, created_at, last_modified)"
                    " VALUES (:id, :taxonomy_id, 'default', 'Default', 0, :now, :now)"
                ),
                {"id": dataset_id, "taxonomy_id": taxonomy_id, "now": now},
            )
        bind.execute(
            sa.text("UPDATE ontology_entities SET dataset_id = :dataset_id WHERE id = :id"),
            {"dataset_id": dataset_id, "id": individual_id},
        )


def upgrade() -> None:
    # The old table never held rows: the feature only flipped a flag.
    op.drop_index(op.f('ix_datasets_is_active'), table_name='datasets')
    op.drop_index(op.f('ix_datasets_title'), table_name='datasets')
    op.drop_table('datasets')
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('taxonomy_id', sa.String(length=36), nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('yields_to_schema', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_modified', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['taxonomy_id'], ['ontology_entities.id'],
            name='fk_datasets_taxonomy_id', ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('taxonomy_id', 'identifier', name='uk_dataset_taxonomy_identifier'),
    )
    op.create_index(op.f('ix_datasets_taxonomy_id'), 'datasets', ['taxonomy_id'], unique=False)

    with op.batch_alter_table('ontology_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dataset_id', sa.String(length=36), nullable=True))
        batch_op.create_index(
            op.f('ix_ontology_entities_dataset_id'), ['dataset_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_ontology_entities_dataset_id', 'datasets',
            ['dataset_id'], ['id'], ondelete='CASCADE',
        )

    _backfill_default_datasets()

    with op.batch_alter_table('ontology_entities', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_individual_dataset',
            "node_type != 'individual' OR dataset_id IS NOT NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table('ontology_entities', schema=None) as batch_op:
        batch_op.drop_constraint('check_individual_dataset', type_='check')
        batch_op.drop_constraint('fk_ontology_entities_dataset_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_ontology_entities_dataset_id'))
        batch_op.drop_column('dataset_id')

    op.drop_index(op.f('ix_datasets_taxonomy_id'), table_name='datasets')
    op.drop_table('datasets')
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('schema_version', sa.String(length=20), nullable=False),
        sa.Column('layers_count', sa.Integer(), nullable=False),
        sa.Column('domains_count', sa.Integer(), nullable=False),
        sa.Column('terms_count', sa.Integer(), nullable=False),
        sa.Column('relationships_count', sa.Integer(), nullable=False),
        sa.Column('individuals_count', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_datasets_is_active'), 'datasets', ['is_active'], unique=False)
    op.create_index(op.f('ix_datasets_title'), 'datasets', ['title'], unique=False)
