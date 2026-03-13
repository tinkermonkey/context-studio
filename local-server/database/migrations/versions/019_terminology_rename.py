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

        # Disable foreign key checks during table rebuild operations
        connection.execute(text("PRAGMA foreign_keys=OFF"))

        try:
            # Step 1: Rename predicates table to property_definitions FIRST
            # This must happen before creating ontology_entities which references property_definitions
            logger.info("Renaming predicates to property_definitions...")
            connection.execute(
                text("ALTER TABLE predicates RENAME TO property_definitions")
            )
            logger.info("Successfully renamed predicates to property_definitions")

            # Step 2: Update node_type enum values in structure_nodes BEFORE rebuilding
            # We must rebuild the table to remove the CHECK constraint that prevents new values
            logger.info(
                "Removing CHECK constraint from structure_nodes and updating enum values..."
            )
            connection.execute(text("""
                CREATE TABLE structure_nodes_temp (
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
                    FOREIGN KEY (parent_node_id) REFERENCES structure_nodes_temp(id) ON DELETE CASCADE,
                    FOREIGN KEY (structural_predicate_id) REFERENCES property_definitions(id)
                )
            """))

            # Copy data with enum value mapping in the SELECT statement
            connection.execute(text("""
                INSERT INTO structure_nodes_temp (
                    id, node_type, parent_node_id, title, definition,
                    structural_predicate_id, title_embedding, definition_embedding,
                    reference_links, word_senses, attributes, created_at, version, last_modified
                )
                SELECT
                    id,
                    CASE node_type
                        WHEN 'layer' THEN 'taxonomy'
                        WHEN 'domain' THEN 'concept_scheme'
                        WHEN 'term' THEN 'class'
                        ELSE node_type
                    END,
                    parent_node_id, title, definition,
                    structural_predicate_id, title_embedding, definition_embedding,
                    reference_links, word_senses, attributes, created_at, version, last_modified
                FROM structure_nodes
            """))

            # Drop original table and rename temp
            connection.execute(text("DROP TABLE structure_nodes"))
            connection.execute(
                text("ALTER TABLE structure_nodes_temp RENAME TO structure_nodes")
            )
            logger.info(
                "Successfully removed CHECK constraint and updated node_type enum values"
            )

            # Step 3: Rename structure_nodes table to ontology_entities
            # Using table rebuild pattern to handle column rename (parent_node_id → parent_entity_id)
            logger.info(
                "Renaming structure_nodes table to ontology_entities with column rename..."
            )
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

            # Copy data from structure_nodes, mapping old column names to new
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

            # Step 4: Rename structure_node_links table to relationships
            # Using table rebuild pattern to handle column renames
            logger.info(
                "Renaming structure_node_links to relationships with column renames..."
            )
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

            # Step 5: Recreate indexes on renamed tables
            logger.info("Recreating indexes on renamed tables...")
            # ontology_entities indexes (from structure_nodes)
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ontology_entities_node_type
                ON ontology_entities(node_type)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ontology_entities_parent_entity_id
                ON ontology_entities(parent_entity_id)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ontology_entities_node_type_parent
                ON ontology_entities(node_type, parent_entity_id)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ontology_entities_node_type_title
                ON ontology_entities(node_type, title)
            """))
            # relationships indexes (from structure_node_links)
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_source
                ON relationships(source_entity_id)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_target
                ON relationships(target_entity_id)
            """))
            logger.info("Successfully recreated indexes")

            # Step 6: Recreate triggers with updated table/column names
            logger.info("Recreating triggers with updated table/column names...")
            self._recreate_triggers_up(connection)
            logger.info("Successfully recreated triggers")

            # Step 7: Rename pipeline_flavors table to pipeline_configurations (if it exists)
            logger.info("Checking for pipeline_flavors table...")
            cursor = connection.connection.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_flavors'"
            )
            if cursor.fetchone():
                logger.info("Renaming pipeline_flavors to pipeline_configurations...")
                connection.execute(
                    text(
                        "ALTER TABLE pipeline_flavors RENAME TO pipeline_configurations"
                    )
                )
                logger.info(
                    "Successfully renamed pipeline_flavors to pipeline_configurations"
                )
            else:
                logger.info("pipeline_flavors table does not exist, skipping rename")

            # Step 8: Update change_events record_type values
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

        finally:
            # Re-enable foreign key checks
            connection.execute(text("PRAGMA foreign_keys=ON"))

    def _recreate_triggers_up(self, connection: Connection) -> None:
        """Recreate all triggers with updated table and column names for ontology_entities and relationships."""
        # Drop old triggers on property_definitions (left from predicates rename) to avoid duplicates
        logger.info("Dropping old triggers on property_definitions...")
        connection.execute(text("DROP TRIGGER IF EXISTS trg_predicate_insert"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_predicate_update"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_predicate_delete"))
        connection.execute(
            text("DROP TRIGGER IF EXISTS update_predicates_date_modified")
        )

        # Trigger for ontology_entities insert (was structure_node insert)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_ontology_entity_insert AFTER INSERT ON ontology_entities
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('create', 'ontology_entity', NEW.id, NULL,
                      json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_entity_id', NEW.parent_entity_id,
                                 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for ontology_entities update (was structure_node update with sophisticated logic)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_ontology_entity_update AFTER UPDATE ON ontology_entities
            BEGIN
              -- Generate update-type event if node_type changed
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'update-type', 'ontology_entity', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_entity_id', OLD.parent_entity_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_entity_id', NEW.parent_entity_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE OLD.node_type != NEW.node_type;

              -- Generate move event if parent_entity_id changed
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'move', 'ontology_entity', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_entity_id', OLD.parent_entity_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_entity_id', NEW.parent_entity_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE (OLD.parent_entity_id IS NULL AND NEW.parent_entity_id IS NOT NULL)
                 OR (OLD.parent_entity_id IS NOT NULL AND NEW.parent_entity_id IS NULL)
                 OR (OLD.parent_entity_id != NEW.parent_entity_id);

              -- Generate generic update event for other field changes
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'update', 'ontology_entity', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_entity_id', OLD.parent_entity_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_entity_id', NEW.parent_entity_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE OLD.node_type = NEW.node_type
                AND (OLD.parent_entity_id IS NEW.parent_entity_id OR (OLD.parent_entity_id = NEW.parent_entity_id));
            END
        """))

        # Trigger for ontology_entities delete (was structure_node delete)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_ontology_entity_delete AFTER DELETE ON ontology_entities
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('delete', 'ontology_entity', OLD.id,
                      json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_entity_id', OLD.parent_entity_id,
                                 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                      NULL, CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for relationships insert (was structure_node_link insert)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_relationship_insert AFTER INSERT ON relationships
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('create', 'relationship', NEW.id, NULL,
                      json_object('id', NEW.id, 'source_entity_id', NEW.source_entity_id, 'target_entity_id', NEW.target_entity_id,
                                 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for relationships update (was structure_node_link update)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_relationship_update AFTER UPDATE ON relationships
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('update', 'relationship', NEW.id,
                      json_object('id', OLD.id, 'source_entity_id', OLD.source_entity_id, 'target_entity_id', OLD.target_entity_id,
                                 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at),
                      json_object('id', NEW.id, 'source_entity_id', NEW.source_entity_id, 'target_entity_id', NEW.target_entity_id,
                                 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for relationships delete (was structure_node_link delete)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_relationship_delete AFTER DELETE ON relationships
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('delete', 'relationship', OLD.id,
                      json_object('id', OLD.id, 'source_entity_id', OLD.source_entity_id, 'target_entity_id', OLD.target_entity_id,
                                 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at),
                      NULL, CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for property_definitions insert (was predicate insert)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_property_definition_insert AFTER INSERT ON property_definitions
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('create', 'property_definition', NEW.id, NULL,
                      json_object('id', NEW.id, 'identifier', NEW.identifier, 'title', NEW.title,
                                 'definition', NEW.definition, 'mapping', NEW.mapping,
                                 'date_created', NEW.date_created, 'date_modified', NEW.date_modified),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for property_definitions update (was predicate update)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_property_definition_update AFTER UPDATE ON property_definitions
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('update', 'property_definition', NEW.id,
                      json_object('id', OLD.id, 'identifier', OLD.identifier, 'title', OLD.title,
                                 'definition', OLD.definition, 'mapping', OLD.mapping,
                                 'date_created', OLD.date_created, 'date_modified', OLD.date_modified),
                      json_object('id', NEW.id, 'identifier', NEW.identifier, 'title', NEW.title,
                                 'definition', NEW.definition, 'mapping', NEW.mapping,
                                 'date_created', NEW.date_created, 'date_modified', NEW.date_modified),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for property_definitions delete (was predicate delete)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_property_definition_delete AFTER DELETE ON property_definitions
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('delete', 'property_definition', OLD.id,
                      json_object('id', OLD.id, 'identifier', OLD.identifier, 'title', OLD.title,
                                 'definition', OLD.definition, 'mapping', OLD.mapping,
                                 'date_created', OLD.date_created, 'date_modified', OLD.date_modified),
                      NULL, CURRENT_TIMESTAMP, 0);
            END
        """))

        # Update trigger for property_definitions date_modified (was update_predicates_date_modified)
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS update_property_definitions_date_modified
            AFTER UPDATE ON property_definitions
            BEGIN
              UPDATE property_definitions SET date_modified = CURRENT_TIMESTAMP
              WHERE id = NEW.id;
            END
        """))

    def down(self, connection: Connection) -> None:
        """Rollback the migration: rename all tables, columns, and enum values back to legacy names."""
        logger.info("Rolling back terminology rename migration (019)...")

        # Disable foreign key checks during table rebuild operations
        connection.execute(text("PRAGMA foreign_keys=OFF"))

        try:
            # Step 1: Rename property_definitions back to predicates FIRST
            # This must happen before creating structure_nodes which references predicates
            logger.info("Rolling back property_definitions to predicates...")
            connection.execute(
                text("ALTER TABLE property_definitions RENAME TO predicates")
            )
            logger.info("Successfully rolled back property_definitions to predicates")

            # Step 2: Rename ontology_entities back to structure_nodes with column rename and enum reversion
            # Using table rebuild pattern to handle column rename (parent_entity_id → parent_node_id)
            logger.info(
                "Rolling back ontology_entities to structure_nodes with column rename and enum reversion..."
            )
            connection.execute(text("""
                CREATE TABLE structure_nodes (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
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
                    created_at TIMESTAMP,
                    version INTEGER DEFAULT 1,
                    last_modified TIMESTAMP,
                    FOREIGN KEY (parent_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (structural_predicate_id) REFERENCES predicates(id)
                )
            """))

            # Copy data from renamed table, mapping new column names back to old and reverting enum values
            connection.execute(text("""
                INSERT INTO structure_nodes (
                    id, node_type, parent_node_id, title, definition,
                    structural_predicate_id, title_embedding, definition_embedding,
                    reference_links, word_senses, attributes, created_at, version, last_modified
                )
                SELECT
                    id,
                    CASE node_type
                        WHEN 'taxonomy' THEN 'layer'
                        WHEN 'concept_scheme' THEN 'domain'
                        WHEN 'class' THEN 'term'
                        ELSE node_type
                    END,
                    parent_entity_id, title, definition,
                    structural_predicate_id, title_embedding, definition_embedding,
                    reference_links, word_senses, attributes, created_at, version, last_modified
                FROM ontology_entities
            """))

            # Drop new table
            connection.execute(text("DROP TABLE ontology_entities"))

            logger.info("Successfully rolled back ontology_entities to structure_nodes")

            # Step 3: Rename relationships back to structure_node_links
            # Using table rebuild pattern to handle column renames
            logger.info(
                "Rolling back relationships to structure_node_links with column renames..."
            )
            connection.execute(text("""
                CREATE TABLE structure_node_links (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    predicate_id TEXT,
                    created_at TIMESTAMP,
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

            logger.info(
                "Successfully rolled back relationships to structure_node_links"
            )

            # Step 5: Recreate indexes on rolled-back tables
            logger.info("Recreating indexes on rolled-back tables...")
            # structure_nodes indexes
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_node_type
                ON structure_nodes(node_type)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_parent_node_id
                ON structure_nodes(parent_node_id)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_type_parent
                ON structure_nodes(node_type, parent_node_id)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_type_title
                ON structure_nodes(node_type, title)
            """))
            # structure_node_links indexes
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_node_links_source
                ON structure_node_links(source_node_id)
            """))
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_node_links_target
                ON structure_node_links(target_node_id)
            """))
            logger.info("Successfully recreated indexes")

            # Step 6: Recreate triggers with original table/column names
            logger.info("Recreating triggers with original table/column names...")
            self._recreate_triggers_down(connection)
            logger.info("Successfully recreated triggers")

            # Step 7: Rename pipeline_configurations back to pipeline_flavors (if it exists)
            logger.info("Checking for pipeline_configurations table...")
            cursor = connection.connection.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_configurations'"
            )
            if cursor.fetchone():
                logger.info(
                    "Rolling back pipeline_configurations to pipeline_flavors..."
                )
                connection.execute(
                    text(
                        "ALTER TABLE pipeline_configurations RENAME TO pipeline_flavors"
                    )
                )
                logger.info(
                    "Successfully rolled back pipeline_configurations to pipeline_flavors"
                )
            else:
                logger.info(
                    "pipeline_configurations table does not exist, skipping rollback"
                )

            # Step 8: Revert change_events record_type values
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

            logger.info(
                "Terminology rename migration (019) rollback completed successfully"
            )

        finally:
            # Re-enable foreign key checks
            connection.execute(text("PRAGMA foreign_keys=ON"))

    def _recreate_triggers_down(self, connection: Connection) -> None:
        """Recreate all triggers with original table and column names for structure_nodes and structure_node_links."""
        # Drop new triggers on ontology_entities and relationships (left from table renames) to avoid duplicates
        logger.info("Dropping new triggers on ontology_entities and relationships...")
        connection.execute(text("DROP TRIGGER IF EXISTS trg_ontology_entity_insert"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_ontology_entity_update"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_ontology_entity_delete"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_relationship_insert"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_relationship_update"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_relationship_delete"))

        # Drop property_definition triggers (left from table rename; they persist on predicates table)
        logger.info("Dropping property_definition triggers left on predicates table...")
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_property_definition_insert")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_property_definition_update")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_property_definition_delete")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS update_property_definitions_date_modified")
        )

        # Trigger for structure_nodes insert
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_structure_node_insert AFTER INSERT ON structure_nodes
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('create', 'structure_node', NEW.id, NULL,
                      json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for structure_nodes update with sophisticated logic
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_structure_node_update AFTER UPDATE ON structure_nodes
            BEGIN
              -- Generate update-type event if node_type changed
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'update-type', 'structure_node', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE OLD.node_type != NEW.node_type;

              -- Generate move event if parent_node_id changed
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'move', 'structure_node', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE (OLD.parent_node_id IS NULL AND NEW.parent_node_id IS NOT NULL)
                 OR (OLD.parent_node_id IS NOT NULL AND NEW.parent_node_id IS NULL)
                 OR (OLD.parent_node_id != NEW.parent_node_id);

              -- Generate generic update event for other field changes
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              SELECT 'update', 'structure_node', NEW.id,
                     json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                     json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id,
                                'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id,
                                'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified),
                     CURRENT_TIMESTAMP, 0
              WHERE OLD.node_type = NEW.node_type
                AND (OLD.parent_node_id IS NEW.parent_node_id OR (OLD.parent_node_id = NEW.parent_node_id));
            END
        """))

        # Trigger for structure_nodes delete
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_structure_node_delete AFTER DELETE ON structure_nodes
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('delete', 'structure_node', OLD.id,
                      json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id,
                                 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id,
                                 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified),
                      NULL, CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for structure_node_links insert
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_structure_node_link_insert AFTER INSERT ON structure_node_links
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('create', 'structure_node_link', NEW.id, NULL,
                      json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id,
                                 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for structure_node_links update
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_structure_node_link_update AFTER UPDATE ON structure_node_links
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('update', 'structure_node_link', NEW.id,
                      json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id,
                                 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at),
                      json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id,
                                 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for structure_node_links delete
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_structure_node_link_delete AFTER DELETE ON structure_node_links
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('delete', 'structure_node_link', OLD.id,
                      json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id,
                                 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at),
                      NULL, CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for predicates insert
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_predicate_insert AFTER INSERT ON predicates
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('create', 'predicate', NEW.id, NULL,
                      json_object('id', NEW.id, 'identifier', NEW.identifier, 'title', NEW.title,
                                 'definition', NEW.definition, 'mapping', NEW.mapping,
                                 'date_created', NEW.date_created, 'date_modified', NEW.date_modified),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for predicates update
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_predicate_update AFTER UPDATE ON predicates
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('update', 'predicate', NEW.id,
                      json_object('id', OLD.id, 'identifier', OLD.identifier, 'title', OLD.title,
                                 'definition', OLD.definition, 'mapping', OLD.mapping,
                                 'date_created', OLD.date_created, 'date_modified', OLD.date_modified),
                      json_object('id', NEW.id, 'identifier', NEW.identifier, 'title', NEW.title,
                                 'definition', NEW.definition, 'mapping', NEW.mapping,
                                 'date_created', NEW.date_created, 'date_modified', NEW.date_modified),
                      CURRENT_TIMESTAMP, 0);
            END
        """))

        # Trigger for predicates delete
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_predicate_delete AFTER DELETE ON predicates
            BEGIN
              INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
              VALUES ('delete', 'predicate', OLD.id,
                      json_object('id', OLD.id, 'identifier', OLD.identifier, 'title', OLD.title,
                                 'definition', OLD.definition, 'mapping', OLD.mapping,
                                 'date_created', OLD.date_created, 'date_modified', OLD.date_modified),
                      NULL, CURRENT_TIMESTAMP, 0);
            END
        """))

        # Update trigger for predicates date_modified
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS update_predicates_date_modified
            AFTER UPDATE ON predicates
            BEGIN
              UPDATE predicates SET date_modified = CURRENT_TIMESTAMP
              WHERE id = NEW.id;
            END
        """))
