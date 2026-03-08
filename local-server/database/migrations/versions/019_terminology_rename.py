"""Migration 019: Rename tables, columns, and enum values to standard ontology terminology.

This migration renames legacy terminology to standard ontology terminology:
- Tables: structure_nodes → ontology_entities, structure_node_links → relationships,
  predicates → property_definitions, pipeline_flavors → pipeline_configurations
- Columns: parent_node_id → parent_entity_id, source_node_id → source_entity_id,
  target_node_id → target_entity_id
- Enum values: layer → taxonomy, domain → concept_scheme, term → class
- Record types: structure_node → ontology_entity, structure_node_link → relationship,
  predicate → property_definition

This migration is reversible and preserves all data with zero loss.
"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration019(Migration):
    """Rename tables, columns, and enum values to standard ontology terminology."""

    version = 19
    description = "Terminology rename: legacy → ontology terminology"

    def up(self, connection: Connection) -> None:
        """Apply the migration: rename all tables, columns, and enum values."""
        logger.info("Starting terminology rename migration (019)...")

        # Step 1: Rename structure_nodes table to ontology_entities
        # Using table rebuild pattern to handle column rename (parent_node_id → parent_entity_id)
        logger.info("Renaming structure_nodes table to ontology_entities with column rename...")
        connection.execute(text("""
            CREATE TABLE ontology_entities (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                parent_entity_id TEXT,
                title TEXT NOT NULL,
                definition TEXT,
                structural_predicate_id TEXT,
                title_embedding BLOB,
                definition_embedding BLOB,
                reference_links TEXT,
                word_senses TEXT,
                attributes TEXT,
                created_at DATETIME,
                version INTEGER DEFAULT 1,
                last_modified DATETIME,
                FOREIGN KEY (parent_entity_id) REFERENCES ontology_entities(id) ON DELETE CASCADE,
                FOREIGN KEY (structural_predicate_id) REFERENCES property_definitions(id)
            )
        """))

        # Copy data from old table, mapping old column names to new
        connection.execute(text("""
            INSERT INTO ontology_entities (
                id, node_type, parent_entity_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                reference_links, word_senses, attributes, created_at, version, last_modified
            )
            SELECT
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                reference_links, word_senses, attributes, created_at, version, last_modified
            FROM structure_nodes
        """))

        # Drop old table
        connection.execute(text("DROP TABLE structure_nodes"))

        logger.info("Successfully renamed structure_nodes to ontology_entities")

        # Step 2: Rename structure_node_links table to relationships
        # Using table rebuild pattern to handle column renames
        logger.info("Renaming structure_node_links to relationships with column renames...")
        connection.execute(text("""
            CREATE TABLE relationships (
                id TEXT PRIMARY KEY,
                source_entity_id TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                predicate_id TEXT,
                created_at DATETIME,
                FOREIGN KEY (source_entity_id) REFERENCES ontology_entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_entity_id) REFERENCES ontology_entities(id) ON DELETE CASCADE,
                FOREIGN KEY (predicate_id) REFERENCES property_definitions(id),
                UNIQUE (source_entity_id, target_entity_id, predicate)
            )
        """))

        # Copy data from old table, mapping old column names to new
        connection.execute(text("""
            INSERT INTO relationships (
                id, source_entity_id, target_entity_id, predicate, predicate_id, created_at
            )
            SELECT
                id, source_node_id, target_node_id, predicate, predicate_id, created_at
            FROM structure_node_links
        """))

        # Drop old table
        connection.execute(text("DROP TABLE structure_node_links"))

        logger.info("Successfully renamed structure_node_links to relationships")

        # Step 3: Rename predicates table to property_definitions
        logger.info("Renaming predicates to property_definitions...")
        connection.execute(text("ALTER TABLE predicates RENAME TO property_definitions"))
        logger.info("Successfully renamed predicates to property_definitions")

        # Step 4: Rename pipeline_flavors table to pipeline_configurations (if it exists)
        logger.info("Checking for pipeline_flavors table...")
        cursor = connection.connection.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_flavors'"
        )
        if cursor.fetchone():
            logger.info("Renaming pipeline_flavors to pipeline_configurations...")
            connection.execute(text("ALTER TABLE pipeline_flavors RENAME TO pipeline_configurations"))
            logger.info("Successfully renamed pipeline_flavors to pipeline_configurations")
        else:
            logger.info("pipeline_flavors table does not exist, skipping rename")

        # Step 5: Update node_type enum values in ontology_entities
        logger.info("Updating node_type enum values...")
        connection.execute(text("""
            UPDATE ontology_entities SET node_type = 'taxonomy' WHERE node_type = 'layer'
        """))
        connection.execute(text("""
            UPDATE ontology_entities SET node_type = 'concept_scheme' WHERE node_type = 'domain'
        """))
        connection.execute(text("""
            UPDATE ontology_entities SET node_type = 'class' WHERE node_type = 'term'
        """))
        logger.info("Successfully updated node_type enum values")

        # Step 6: Recreate indexes on renamed tables
        logger.info("Recreating indexes on renamed tables...")
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ontology_entities_title
            ON ontology_entities(title)
        """))
        logger.info("Successfully recreated indexes")

        # Step 7: Update change_events record_type values
        logger.info("Updating change_events record_type values...")
        connection.execute(text("""
            UPDATE change_events SET record_type = 'ontology_entity'
            WHERE record_type = 'structure_node'
        """))
        connection.execute(text("""
            UPDATE change_events SET record_type = 'relationship'
            WHERE record_type = 'structure_node_link'
        """))
        connection.execute(text("""
            UPDATE change_events SET record_type = 'property_definition'
            WHERE record_type = 'predicate'
        """))
        logger.info("Successfully updated change_events record_type values")

        logger.info("Terminology rename migration (019) completed successfully")

    def down(self, connection: Connection) -> None:
        """Rollback the migration: rename all tables, columns, and enum values back to legacy names."""
        logger.info("Rolling back terminology rename migration (019)...")

        # Step 1: Rename ontology_entities back to structure_nodes
        # Using table rebuild pattern to handle column rename (parent_entity_id → parent_node_id)
        logger.info("Rolling back ontology_entities to structure_nodes with column rename...")
        connection.execute(text("""
            CREATE TABLE structure_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                parent_node_id TEXT,
                title TEXT NOT NULL,
                definition TEXT,
                structural_predicate_id TEXT,
                title_embedding BLOB,
                definition_embedding BLOB,
                reference_links TEXT,
                word_senses TEXT,
                attributes TEXT,
                created_at DATETIME,
                version INTEGER DEFAULT 1,
                last_modified DATETIME,
                FOREIGN KEY (parent_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (structural_predicate_id) REFERENCES predicates(id)
            )
        """))

        # Copy data from renamed table, mapping new column names back to old
        connection.execute(text("""
            INSERT INTO structure_nodes (
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                reference_links, word_senses, attributes, created_at, version, last_modified
            )
            SELECT
                id, node_type, parent_entity_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                reference_links, word_senses, attributes, created_at, version, last_modified
            FROM ontology_entities
        """))

        # Drop new table
        connection.execute(text("DROP TABLE ontology_entities"))

        logger.info("Successfully rolled back ontology_entities to structure_nodes")

        # Step 2: Rename relationships back to structure_node_links
        # Using table rebuild pattern to handle column renames
        logger.info("Rolling back relationships to structure_node_links with column renames...")
        connection.execute(text("""
            CREATE TABLE structure_node_links (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                predicate_id TEXT,
                created_at DATETIME,
                FOREIGN KEY (source_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (predicate_id) REFERENCES predicates(id),
                UNIQUE (source_node_id, target_node_id, predicate)
            )
        """))

        # Copy data from renamed table, mapping new column names back to old
        connection.execute(text("""
            INSERT INTO structure_node_links (
                id, source_node_id, target_node_id, predicate, predicate_id, created_at
            )
            SELECT
                id, source_entity_id, target_entity_id, predicate, predicate_id, created_at
            FROM relationships
        """))

        # Drop new table
        connection.execute(text("DROP TABLE relationships"))

        logger.info("Successfully rolled back relationships to structure_node_links")

        # Step 3: Rename property_definitions back to predicates
        logger.info("Rolling back property_definitions to predicates...")
        connection.execute(text("ALTER TABLE property_definitions RENAME TO predicates"))
        logger.info("Successfully rolled back property_definitions to predicates")

        # Step 4: Rename pipeline_configurations back to pipeline_flavors (if it exists)
        logger.info("Checking for pipeline_configurations table...")
        cursor = connection.connection.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_configurations'"
        )
        if cursor.fetchone():
            logger.info("Rolling back pipeline_configurations to pipeline_flavors...")
            connection.execute(text("ALTER TABLE pipeline_configurations RENAME TO pipeline_flavors"))
            logger.info("Successfully rolled back pipeline_configurations to pipeline_flavors")
        else:
            logger.info("pipeline_configurations table does not exist, skipping rollback")

        # Step 5: Revert node_type enum values back to legacy names
        logger.info("Reverting node_type enum values to legacy names...")
        connection.execute(text("""
            UPDATE structure_nodes SET node_type = 'layer' WHERE node_type = 'taxonomy'
        """))
        connection.execute(text("""
            UPDATE structure_nodes SET node_type = 'domain' WHERE node_type = 'concept_scheme'
        """))
        connection.execute(text("""
            UPDATE structure_nodes SET node_type = 'term' WHERE node_type = 'class'
        """))
        logger.info("Successfully reverted node_type enum values")

        # Step 6: Recreate indexes on renamed tables
        logger.info("Recreating indexes on rolled-back tables...")
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_structure_nodes_title
            ON structure_nodes(title)
        """))
        logger.info("Successfully recreated indexes")

        # Step 7: Revert change_events record_type values
        logger.info("Reverting change_events record_type values...")
        connection.execute(text("""
            UPDATE change_events SET record_type = 'structure_node'
            WHERE record_type = 'ontology_entity'
        """))
        connection.execute(text("""
            UPDATE change_events SET record_type = 'structure_node_link'
            WHERE record_type = 'relationship'
        """))
        connection.execute(text("""
            UPDATE change_events SET record_type = 'predicate'
            WHERE record_type = 'property_definition'
        """))
        logger.info("Successfully reverted change_events record_type values")

        logger.info("Terminology rename migration (019) rollback completed successfully")
