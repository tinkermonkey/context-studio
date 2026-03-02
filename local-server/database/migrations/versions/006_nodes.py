"""Migration 006: The Structure Nodes - Normalize layers, domains, terms into structure_nodes table."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)

class Migration006(Migration):
    """Normalize layers, domains, and terms into a single structure_nodes table."""
# mypy: ignore-errors
    version = 6
    description = "The Structure Nodes - Normalize layers, domains, terms into structure_nodes table."

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Starting The Structure Nodes migration...")
        
        connection.execute(text("PRAGMA foreign_keys=off;"))
        
        # Step 1: Create new tables (if they don't exist)
        self._create_structure_nodes_table_if_not_exists(connection)
        self._create_structure_node_links_table_if_not_exists(connection) 
        self._create_change_events_table_if_not_exists(connection)
        self._create_structure_nodes_vec_table(connection)
        
        # Step 2: Migrate data from existing tables
        self._migrate_layers_to_structure_nodes(connection)
        self._migrate_domains_to_structure_nodes(connection)
        self._migrate_terms_to_structure_nodes(connection)
        self._migrate_term_relationships_to_structure_node_links(connection)
        self._migrate_graph_events_to_change_events(connection)
        
        # Step 3: Create triggers for change events
        self._create_change_event_triggers(connection)
        
        # Step 4: Populate vector embeddings table
        self._populate_vector_embeddings(connection)
        
        # Step 5: Validate migration
        self._validate_migration(connection)
        
        # Step 6: Drop old tables (after validation)
        self._drop_old_tables(connection)
        
        connection.execute(text("PRAGMA foreign_keys=on;"))
        
        logger.info("The Structure Nodes migration completed successfully!")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Rolling back The Structure Nodes migration...")
        
        connection.execute(text("PRAGMA foreign_keys=off;"))
        
        # Recreate original tables
        self._recreate_original_tables(connection)
        
        # Migrate data back from structure_nodes to original tables
        self._migrate_structure_nodes_back_to_original_tables(connection)
        
        # Drop new tables - handle vector table cleanup properly
        self._drop_structure_nodes_vec_table_if_exists(connection)
        
        connection.execute(text("DROP TABLE IF EXISTS change_events;"))
        connection.execute(text("DROP TABLE IF EXISTS structure_node_links;"))
        connection.execute(text("DROP TABLE IF EXISTS structure_nodes;"))
        
        connection.execute(text("PRAGMA foreign_keys=on;"))
        
        logger.info("The Structure Nodes migration rollback completed!")

    def _create_structure_nodes_table_if_not_exists(self, connection: Connection) -> None:
        """Create the new structure_nodes table if it doesn't exist."""
        # Check if table exists
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='structure_nodes'
        """)).fetchone()
        
        if result:
            logger.info("StructureNodes table already exists, skipping creation...")
            return
            
        self._create_structure_nodes_table(connection)

    def _create_structure_node_links_table_if_not_exists(self, connection: Connection) -> None:
        """Create the new structure_node_links table if it doesn't exist."""
        # Check if table exists
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='structure_node_links'
        """)).fetchone()
        
        if result:
            logger.info("Node_links table already exists, skipping creation...")
            return
            
        self._create_structure_node_links_table(connection)

    def _create_change_events_table_if_not_exists(self, connection: Connection) -> None:
        """Create the new change_events table if it doesn't exist."""
        # Check if table exists
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='change_events'
        """)).fetchone()
        
        if result:
            logger.info("change_events table already exists, skipping creation...")
            return
            
        self._create_change_events_table(connection)

    def _create_structure_nodes_table(self, connection: Connection) -> None:
        """Create the new structure_nodes table."""
        logger.info("Creating structure_nodes table...")
        
        connection.execute(text("""
            CREATE TABLE structure_nodes (
                id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
                node_type TEXT NOT NULL CHECK (node_type IN ('layer', 'domain', 'term')),
                parent_node_id TEXT,
                title TEXT NOT NULL,
                definition TEXT,
                structural_predicate_id TEXT,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (parent_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (structural_predicate_id) REFERENCES predicates(id)
            );
        """))

        # Create indexes for performance
        connection.execute(text("CREATE INDEX idx_nodes_node_type ON structure_nodes(node_type);"))
        connection.execute(text("CREATE INDEX idx_nodes_parent_node_id ON structure_nodes(parent_node_id);"))
        connection.execute(text("CREATE INDEX idx_nodes_type_parent ON structure_nodes(node_type, parent_node_id);"))
        
        # Verify table was created
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='structure_nodes'")).fetchone()
        if result:
            logger.info("Successfully created structure_nodes table")
        else:
            logger.error("Failed to create structure_nodes table!")

    def _create_structure_node_links_table(self, connection: Connection) -> None:
        """Create the new structure_node_links table."""
        logger.info("Creating structure_node_links table...")
        
        connection.execute(text("""
            CREATE TABLE structure_node_links (
                id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                predicate_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (source_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (predicate_id) REFERENCES predicates(id),
                
                UNIQUE(source_node_id, target_node_id, predicate)
            );
        """))

        # Create indexes for performance
        connection.execute(text("CREATE INDEX idx_node_links_source ON structure_node_links(source_node_id);"))
        connection.execute(text("CREATE INDEX idx_node_links_target ON structure_node_links(target_node_id);"))

    def _create_change_events_table(self, connection: Connection) -> None:
        """Create the new change_events table."""
        logger.info("Creating change_events table...")
        
        connection.execute(text("""
            CREATE TABLE change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,  -- create, update, delete
                record_type TEXT NOT NULL, -- structure_node, structure_node_link, predicate
                record_id TEXT,            -- ID of the affected record
                old_data TEXT,             -- JSON
                new_data TEXT,             -- JSON
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE NOT NULL
            );
        """))

        # Create indexes for performance
        connection.execute(text("CREATE INDEX idx_change_events_processed ON change_events(processed);"))
        connection.execute(text("CREATE INDEX idx_change_events_record_id ON change_events(record_id);"))
        connection.execute(text("CREATE INDEX idx_change_events_record_type ON change_events(record_type);"))
        connection.execute(text("CREATE INDEX idx_change_events_type_processed ON change_events(record_type, processed);"))

    def _create_structure_nodes_vec_table(self, connection: Connection) -> None:
        """Create vector embeddings virtual table for structure_nodes."""
        logger.info("Creating structure_nodes vector table...")
        
        try:
            # Try to create the vector table - this requires sqlite-vec extension
            try:
                import sqlite_vec
            except ImportError:
                logger.error("sqlite-vec extension not available. Skipping structure_nodes vector table creation.")
                return
                
            raw_connection = connection.connection
            raw_connection.enable_load_extension(True)
            sqlite_vec.load(raw_connection)
            raw_connection.enable_load_extension(False)
            
            # Create virtual table for vector embeddings (sqlite-vec)
            connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS structure_nodes_vec USING vec0(
                    node_id TEXT PRIMARY KEY,
                    title_embedding FLOAT[384],
                    definition_embedding FLOAT[384]
                )
            """))
            
        except Exception as e:
            logger.warning(f"Could not create structure_nodes vector table: {e}")

    def _create_change_event_triggers(self, connection: Connection) -> None:
        """Create triggers for change events."""
        logger.info("Creating change event triggers...")

        try:
            # StructureNode insert trigger
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_structure_node_insert AFTER INSERT ON structure_nodes
                BEGIN
                  INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
                  VALUES ('create', 'structure_node', NEW.id, NULL, 
                          json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id, 
                                     'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id, 
                                     'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), 
                          CURRENT_TIMESTAMP, 0);
                END;
            """))

            # StructureNode update trigger - generates specific event types based on what changed
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

                  -- Generate generic update event for other field changes (if neither node_type nor parent_node_id changed)
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
                END;
            """))

            # StructureNode delete trigger
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_structure_node_delete AFTER DELETE ON structure_nodes
                BEGIN
                  INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
                  VALUES ('delete', 'structure_node', OLD.id, 
                          json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id, 
                                     'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id, 
                                     'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), 
                          NULL, CURRENT_TIMESTAMP, 0);
                END;
            """))

            # StructureNode link triggers
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_structure_node_link_insert AFTER INSERT ON structure_node_links
                BEGIN
                  INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
                  VALUES ('create', 'structure_node_link', NEW.id, NULL, 
                          json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id, 
                                     'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at), 
                          CURRENT_TIMESTAMP, 0);
                END;
            """))

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
                END;
            """))

            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_structure_node_link_delete AFTER DELETE ON structure_node_links
                BEGIN
                  INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
                  VALUES ('delete', 'structure_node_link', OLD.id, 
                          json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id, 
                                     'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at), 
                          NULL, CURRENT_TIMESTAMP, 0);
                END;
            """))

            # Predicate triggers
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_predicate_insert AFTER INSERT ON predicates
                BEGIN
                  INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
                  VALUES ('create', 'predicate', NEW.id, NULL, 
                          json_object('id', NEW.id, 'identifier', NEW.identifier, 'title', NEW.title, 
                                     'definition', NEW.definition, 'mapping', NEW.mapping, 
                                     'date_created', NEW.date_created, 'date_modified', NEW.date_modified), 
                          CURRENT_TIMESTAMP, 0);
                END;
            """))

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
                END;
            """))

            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_predicate_delete AFTER DELETE ON predicates
                BEGIN
                  INSERT INTO change_events (event_type, record_type, record_id, old_data, new_data, timestamp, processed)
                  VALUES ('delete', 'predicate', OLD.id, 
                          json_object('id', OLD.id, 'identifier', OLD.identifier, 'title', OLD.title,
                                     'definition', OLD.definition, 'mapping', OLD.mapping,
                                     'date_created', OLD.date_created, 'date_modified', OLD.date_modified),
                          NULL, CURRENT_TIMESTAMP, 0);
                END;
            """))

        except Exception as e:
            logger.warning(f"Could not create triggers inline: {e}")

    def _populate_vector_embeddings(self, connection: Connection) -> None:
        """Populate the vector embeddings virtual table."""
        logger.info("Populating vector embeddings table...")
        
        try:
            # Check if vector table exists
            vector_table_exists = connection.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='structure_nodes_vec'
            """)).fetchone()
            
            if not vector_table_exists:
                logger.info("Vector table does not exist, skipping vector population")
                return
            
            # Populate vector embeddings from structure_nodes with embeddings
            nodes_with_embeddings = connection.execute(text("""
                SELECT id, title_embedding, definition_embedding 
                FROM structure_nodes 
                WHERE title_embedding IS NOT NULL OR definition_embedding IS NOT NULL
            """)).fetchall()
            
            for structure_node in nodes_with_embeddings:
                try:
                    connection.execute(text("""
                        INSERT INTO structure_nodes_vec (node_id, title_embedding, definition_embedding)
                        VALUES (:node_id, :title_embedding, :definition_embedding)
                    """), {
                        "node_id": structure_node[0],
                        "title_embedding": structure_node[1],
                        "definition_embedding": structure_node[2]
                    })
                except Exception as e:
                    logger.warning(f"Could not insert vector embedding for structure_node {structure_node[0]}: {e}")
                    
            logger.info(f"Populated vector embeddings for {len(nodes_with_embeddings)} structure_nodes")
            
        except Exception as e:
            logger.warning(f"Could not populate vector embeddings: {e}")

    def _migrate_layers_to_structure_nodes(self, connection: Connection) -> None:
        """Migrate layer records to structure_nodes table."""
        logger.info("Migrating layers to structure_nodes...")

        # Check if layers table exists first
        layers_exist = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='layers'
        """)).fetchone()

        if not layers_exist:
            logger.info("No layers table found, skipping layer migration")
            return

        # Use raw SQL with explicit column specification to override default ID generation
        connection.execute(text("""
            INSERT OR IGNORE INTO structure_nodes (
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id,
                title_embedding, definition_embedding,
                created_at, version, last_modified
            )
            SELECT
                id, 'layer', NULL, title, definition,
                NULL,
                title_embedding, definition_embedding,
                created_at, version, last_modified
            FROM layers
        """))

        # Log migration results
        migrated_count = connection.execute(text("""
            SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'layer'
        """)).scalar()
        logger.info(f"Migrated {migrated_count} layers to structure_nodes")

    def _migrate_domains_to_structure_nodes(self, connection: Connection) -> None:
        """Migrate domain records to structure_nodes table."""
        logger.info("Migrating domains to structure_nodes...")

        # Check if domains table exists first
        domains_exist = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='domains'
        """)).fetchone()

        if not domains_exist:
            logger.info("No domains table found, skipping domain migration")
            return

        # Use raw SQL with explicit column specification to override default ID generation
        connection.execute(text("""
            INSERT OR IGNORE INTO structure_nodes (
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id,
                title_embedding, definition_embedding,
                created_at, version, last_modified
            )
            SELECT
                id, 'domain', layer_id, title, definition,
                primary_predicate_id,
                title_embedding, definition_embedding,
                created_at, version, last_modified
            FROM domains
        """))

        # Log migration results
        migrated_count = connection.execute(text("""
            SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'domain'
        """)).scalar()
        logger.info(f"Migrated {migrated_count} domains to structure_nodes")

    def _migrate_terms_to_structure_nodes(self, connection: Connection) -> None:
        """Migrate term records to structure_nodes table."""
        logger.info("Migrating terms to structure_nodes...")

        # Check if terms table exists first
        terms_exist = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='terms'
        """)).fetchone()

        if not terms_exist:
            logger.info("No terms table found, skipping term migration")
            return

        # Use raw SQL with explicit column specification to override default ID generation
        connection.execute(text("""
            INSERT OR IGNORE INTO structure_nodes (
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id,
                title_embedding, definition_embedding,
                created_at, version, last_modified
            )
            SELECT
                id,
                'term',
                CASE
                    WHEN parent_term_id IS NOT NULL THEN parent_term_id
                    ELSE domain_id
                END as parent_node_id,
                title,
                definition,
                NULL,
                title_embedding,
                definition_embedding,
                created_at,
                version,
                last_modified
            FROM terms
        """))

        # Log migration results
        migrated_count = connection.execute(text("""
            SELECT COUNT(*) FROM structure_nodes WHERE node_type = 'term'
        """)).scalar()
        logger.info(f"Migrated {migrated_count} terms to structure_nodes")

    def _migrate_term_relationships_to_structure_node_links(self, connection: Connection) -> None:
        """Migrate term_relationships records to structure_node_links table."""
        logger.info("Migrating term_relationships to structure_node_links...")
        
        connection.execute(text("""
            INSERT INTO structure_node_links (
                id, source_node_id, target_node_id, predicate, predicate_id, created_at
            )
            SELECT 
                id, source_term_id, target_term_id, predicate, predicate_id, created_at
            FROM term_relationships
        """))

    def _migrate_graph_events_to_change_events(self, connection: Connection) -> None:
        """Migrate graph_events records to change_events table with schema transformation."""
        logger.info("Migrating graph_events to change_events...")
        
        connection.execute(text("""
            INSERT INTO change_events (
                event_type, record_type, record_id, old_data, new_data, timestamp, processed
            )
            SELECT 
                event_type,
                CASE 
                    WHEN entity_type IN ('layer', 'domain', 'term') THEN 'structure_node'
                    WHEN entity_type = 'term_relationship' THEN 'structure_node_link'
                    ELSE entity_type 
                END as record_type,
                -- Extract record_id from JSON data where possible
                CASE 
                    WHEN new_data IS NOT NULL THEN json_extract(new_data, '$.id')
                    WHEN old_data IS NOT NULL THEN json_extract(old_data, '$.id')
                    ELSE NULL
                END as record_id,
                old_data, 
                new_data, 
                timestamp, 
                processed
            FROM graph_events
        """))

    def _validate_migration(self, connection: Connection) -> None:
        """Validate migration integrity."""
        logger.info("Validating migration integrity...")
        
        # Count validation for structure_nodes - handle case where original tables don't exist
        try:
            layer_count = connection.execute(text("SELECT COUNT(*) FROM layers")).scalar()
        except Exception:
            layer_count = 0
            
        try:
            domain_count = connection.execute(text("SELECT COUNT(*) FROM domains")).scalar()
        except Exception:
            domain_count = 0
            
        try:
            term_count = connection.execute(text("SELECT COUNT(*) FROM terms")).scalar()
        except Exception:
            term_count = 0
            
        total_original = layer_count + domain_count + term_count
        
        # Ensure structure_nodes table exists
        structure_node_count = connection.execute(text("SELECT COUNT(*) FROM structure_nodes")).scalar()
        
        if structure_node_count != total_original:
            raise Exception(f"Record count mismatch: {structure_node_count} structure_nodes vs {total_original} original records")
        
        # Count validation for structure_node_links - handle case where original tables don't exist
        try:
            term_relationships_count = connection.execute(text("SELECT COUNT(*) FROM term_relationships")).scalar()
        except Exception:
            term_relationships_count = 0
            
        try:
           structure_node_links_count = connection.execute(text("SELECT COUNT(*) FROM structure_node_links")).scalar()
        except Exception:
           structure_node_links_count = 0
        
        if structure_node_links_count != term_relationships_count:
            raise Exception(f"Link count mismatch: {structure_node_links_count} structure_node_links vs {term_relationships_count} term_relationships")
        
        # Count validation for change_events - handle case where original tables don't exist  
        try:
            graph_events_count = connection.execute(text("SELECT COUNT(*) FROM graph_events")).scalar()
        except Exception:
            graph_events_count = 0
            
        try:
           change_events_count = connection.execute(text("SELECT COUNT(*) FROM change_events")).scalar()
        except Exception:
           change_events_count = 0
        
        if change_events_count != graph_events_count:
            raise Exception(f"Event count mismatch: {change_events_count} change_events vs {graph_events_count} graph_events")
        
        # Parent integrity validation
        invalid_parents = connection.execute(text("""
            SELECT COUNT(*) FROM structure_nodes n1
            WHERE n1.parent_node_id IS NOT NULL 
            AND NOT EXISTS (SELECT 1 FROM structure_nodes n2 WHERE n2.id = n1.parent_node_id)
        """)).scalar()
        
        if invalid_parents > 0:
            raise Exception(f"Found {invalid_parents} structure_nodes with invalid parent references")
        
        # Validate vector embeddings virtual table is populated if it exists
        try:
            nodes_vec_count = connection.execute(text("SELECT COUNT(*) FROM structure_nodes_vec")).scalar()
            nodes_with_embeddings_count = connection.execute(text("""
                SELECT COUNT(*) FROM structure_nodes 
                WHERE title_embedding IS NOT NULL OR definition_embedding IS NOT NULL
            """)).scalar()
            
            if nodes_vec_count != nodes_with_embeddings_count:
                logger.warning(f"Vector table count mismatch: {nodes_vec_count} vs {nodes_with_embeddings_count} structure_nodes with embeddings")
        except Exception as e:
            logger.info(f"Vector table validation skipped: {e}")
        
        logger.info(f"Migration validation passed: {structure_node_count} structure_nodes, {structure_node_links_count} links, {change_events_count} events")

    def _drop_old_tables(self, connection: Connection) -> None:
        """Drop old tables after successful migration."""
        logger.info("Dropping old tables...")
        
        connection.execute(text("DROP TABLE IF EXISTS graph_events;"))
        connection.execute(text("DROP TABLE IF EXISTS term_relationships;"))
        connection.execute(text("DROP TABLE IF EXISTS terms;"))
        connection.execute(text("DROP TABLE IF EXISTS domains;"))
        connection.execute(text("DROP TABLE IF EXISTS layers;"))

    def _recreate_original_tables(self, connection: Connection) -> None:
        """Recreate original tables for rollback."""
        logger.info("Recreating original tables for rollback...")
        
        # Recreate layers table
        connection.execute(text("""
            CREATE TABLE layers (
                id TEXT PRIMARY KEY,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Recreate domains table
        connection.execute(text("""
            CREATE TABLE domains (
                id TEXT PRIMARY KEY,
                layer_id TEXT NOT NULL,
                title TEXT NOT NULL,
                definition TEXT NOT NULL,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                primary_predicate TEXT,
                primary_predicate_id TEXT,
                predicate_set TEXT,
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,
                FOREIGN KEY (primary_predicate_id) REFERENCES predicates (id) ON DELETE SET NULL,
                UNIQUE (layer_id, title)
            );
        """))

        # Recreate terms table
        connection.execute(text("""
            CREATE TABLE terms (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                layer_id TEXT NOT NULL,
                title TEXT NOT NULL,
                definition TEXT NOT NULL,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                parent_term_id TEXT,
                FOREIGN KEY (domain_id) REFERENCES domains (id) ON DELETE CASCADE,
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,
                FOREIGN KEY (parent_term_id) REFERENCES terms (id) ON DELETE SET NULL,
                UNIQUE (domain_id, title)
            );
        """))

        # Recreate term_relationships table
        connection.execute(text("""
            CREATE TABLE term_relationships (
                id TEXT PRIMARY KEY,
                source_term_id TEXT NOT NULL,
                target_term_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                predicate_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_term_id) REFERENCES terms (id) ON DELETE CASCADE,
                FOREIGN KEY (target_term_id) REFERENCES terms (id) ON DELETE CASCADE,
                FOREIGN KEY (predicate_id) REFERENCES predicates (id) ON DELETE SET NULL,
                UNIQUE (source_term_id, target_term_id, predicate)
            );
        """))

        # Recreate graph_events table
        connection.execute(text("""
            CREATE TABLE graph_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                old_data TEXT,
                new_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE NOT NULL
            );
        """))

    def _migrate_structure_nodes_back_to_original_tables(self, connection: Connection) -> None:
        """Migrate data back from structure_nodes to original tables for rollback."""
        logger.info("Migrating data back to original tables...")
        
        # Migrate layers back
        layers = connection.execute(text("""
            SELECT id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified 
            FROM structure_nodes WHERE node_type = 'layer'
        """)).fetchall()
        
        for layer in layers:
            connection.execute(text("""
                INSERT INTO layers (id, title, definition, title_embedding, definition_embedding, 
                                  created_at, version, last_modified)
                VALUES (:id, :title, :definition, :title_embedding, :definition_embedding, 
                       :created_at, :version, :last_modified)
            """), {
                "id": layer[0], "title": layer[1], "definition": layer[2],
                "title_embedding": layer[3], "definition_embedding": layer[4],
                "created_at": layer[5], "version": layer[6], "last_modified": layer[7]
            })

        # Migrate domains back
        domains = connection.execute(text("""
            SELECT id, parent_node_id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified, structural_predicate_id
            FROM structure_nodes WHERE node_type = 'domain'
        """)).fetchall()
        
        for domain in domains:
            connection.execute(text("""
                INSERT INTO domains (id, layer_id, title, definition, title_embedding, definition_embedding, 
                                   created_at, version, last_modified, primary_predicate, primary_predicate_id, predicate_set)
                VALUES (:id, :layer_id, :title, :definition, :title_embedding, :definition_embedding, 
                       :created_at, :version, :last_modified, :primary_predicate, :primary_predicate_id, :predicate_set)
            """), {
                "id": domain[0], "layer_id": domain[1], "title": domain[2], "definition": domain[3],
                "title_embedding": domain[4], "definition_embedding": domain[5],
                "created_at": domain[6], "version": domain[7], "last_modified": domain[8],
                "primary_predicate": None, "primary_predicate_id": domain[9], "predicate_set": None
            })

        # Migrate terms back
        terms = connection.execute(text("""
            SELECT n.id, n.title, n.definition, n.title_embedding, n.definition_embedding, 
                   n.created_at, n.version, n.last_modified, n.parent_node_id,
                   CASE 
                       WHEN p.node_type = 'domain' THEN p.id 
                       ELSE p.parent_node_id 
                   END as domain_id,
                   CASE 
                       WHEN p.node_type = 'domain' THEN p.parent_node_id 
                       ELSE (SELECT parent_node_id FROM structure_nodes WHERE id = p.parent_node_id)
                   END as layer_id
            FROM structure_nodes n
            LEFT JOIN structure_nodes p ON n.parent_node_id = p.id
            WHERE n.node_type = 'term'
        """)).fetchall()
        
        for term in terms:
            # parent_term_id is set if parent is also a term, otherwise NULL
            parent_term_id = term[8] if term[8] and connection.execute(text("""
                SELECT node_type FROM structure_nodes WHERE id = :id
            """), {"id": term[8]}).scalar() == 'term' else None
            
            connection.execute(text("""
                INSERT INTO terms (id, domain_id, layer_id, title, definition, title_embedding, 
                                 definition_embedding, created_at, version, last_modified, parent_term_id)
                VALUES (:id, :domain_id, :layer_id, :title, :definition, :title_embedding, 
                       :definition_embedding, :created_at, :version, :last_modified, :parent_term_id)
            """), {
                "id": term[0], "domain_id": term[9], "layer_id": term[10], 
                "title": term[1], "definition": term[2], "title_embedding": term[3],
                "definition_embedding": term[4], "created_at": term[5], 
                "version": term[6], "last_modified": term[7], "parent_term_id": parent_term_id
            })

        # Migrate structure_node_links back to term_relationships
        links = connection.execute(text("SELECT * FROM structure_node_links")).fetchall()
        for link in links:
            connection.execute(text("""
                INSERT INTO term_relationships (id, source_term_id, target_term_id, predicate, predicate_id, created_at)
                VALUES (:id, :source_term_id, :target_term_id, :predicate, :predicate_id, :created_at)
            """), {
                "id": link[0], "source_term_id": link[1], "target_term_id": link[2],
                "predicate": link[3], "predicate_id": link[4], "created_at": link[5]
            })

        # Migrate change_events back to graph_events
        events = connection.execute(text("SELECT * FROM change_events")).fetchall()
        for event in events:
            # Map record_type back to entity_type
            record_type = event[2]
            if record_type == 'structure_node_link':
                entity_type = 'term_relationship'
            elif record_type == 'structure_node':
                # Try to extract node_type from JSON data for backwards compatibility
                entity_type = 'term'  # Default fallback
                if event[4]:  # new_data
                    try:
                        import json
                        data = json.loads(event[4])
                        if 'node_type' in data:
                            entity_type = data['node_type']
                    except Exception:
                        pass
                elif event[3]:  # old_data
                    try:
                        import json
                        data = json.loads(event[3])
                        if 'node_type' in data:
                            entity_type = data['node_type']
                    except Exception:
                        pass
            else:
                entity_type = record_type
            
            connection.execute(text("""
                INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
                VALUES (:event_type, :entity_type, :old_data, :new_data, :timestamp, :processed)
            """), {
                "event_type": event[1], "entity_type": entity_type, "old_data": event[4],
                "new_data": event[5], "timestamp": event[6], "processed": event[7]
            })

    def _drop_structure_nodes_vec_table_if_exists(self, connection: Connection) -> None:
        """Drop the structure_nodes_vec virtual table if it exists, handling sqlite-vec extension properly."""
        try:
            # Check if the table exists first
            result = connection.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='structure_nodes_vec'
            """)).fetchone()
            
            if not result:
                # Table doesn't exist, nothing to drop
                return
                
            # Try to load the sqlite-vec extension before dropping
            try:
                import sqlite_vec
                raw_connection = connection.connection
                raw_connection.enable_load_extension(True)
                sqlite_vec.load(raw_connection)
                raw_connection.enable_load_extension(False)
                
                # Now drop the table
                connection.execute(text("DROP TABLE IF EXISTS structure_nodes_vec;"))
                logger.info("Successfully dropped structure_nodes_vec virtual table")
                
            except ImportError:
                logger.info("sqlite-vec extension not available during rollback, table may not have been created")
            except Exception as e:
                logger.warning(f"Could not properly drop structure_nodes_vec table: {e}")
                # Try to drop anyway in case it's a regular table
                try:
                    connection.execute(text("DROP TABLE IF EXISTS structure_nodes_vec;"))
                except Exception:
                    logger.info("structure_nodes_vec table cleanup skipped")
                    
        except Exception as e:
            logger.warning(f"Error during structure_nodes_vec table cleanup: {e}")
