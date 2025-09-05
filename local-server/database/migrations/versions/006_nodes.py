"""Migration 006: The Great Normalization - Normalize layers, domains, terms into nodes table."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)

class Migration006(Migration):
    """Normalize layers, domains, and terms into a single nodes table."""
    version = 6
    description = "The Great Normalization - Normalize layers, domains, terms into nodes table."

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Starting The Great Normalization migration...")
        
        connection.execute(text("PRAGMA foreign_keys=off;"))
        
        # Step 1: Create new tables (if they don't exist)
        self._create_nodes_table_if_not_exists(connection)
        self._create_node_links_table_if_not_exists(connection) 
        self._create_node_events_table_if_not_exists(connection)
        self._create_nodes_vec_table(connection)
        
        # Step 2: Migrate data from existing tables
        self._migrate_layers_to_nodes(connection)
        self._migrate_domains_to_nodes(connection)
        self._migrate_terms_to_nodes(connection)
        self._migrate_term_relationships_to_node_links(connection)
        self._migrate_graph_events_to_node_events(connection)
        
        # Step 3: Create triggers for node events
        self._create_node_triggers(connection)
        
        # Step 4: Populate vector embeddings table
        self._populate_vector_embeddings(connection)
        
        # Step 5: Validate migration
        self._validate_migration(connection)
        
        # Step 6: Drop old tables (after validation)
        self._drop_old_tables(connection)
        
        connection.execute(text("PRAGMA foreign_keys=on;"))
        
        logger.info("The Great Normalization migration completed successfully!")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Rolling back The Great Normalization migration...")
        
        connection.execute(text("PRAGMA foreign_keys=off;"))
        
        # Recreate original tables
        self._recreate_original_tables(connection)
        
        # Migrate data back from nodes to original tables
        self._migrate_nodes_back_to_original_tables(connection)
        
        # Drop new tables
        connection.execute(text("DROP TABLE IF EXISTS nodes_vec;"))
        connection.execute(text("DROP TABLE IF EXISTS node_events;"))
        connection.execute(text("DROP TABLE IF EXISTS node_links;"))
        connection.execute(text("DROP TABLE IF EXISTS nodes;"))
        
        connection.execute(text("PRAGMA foreign_keys=on;"))
        
        logger.info("The Great Normalization migration rollback completed!")

    def _create_nodes_table_if_not_exists(self, connection: Connection) -> None:
        """Create the new nodes table if it doesn't exist."""
        # Check if table exists
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'
        """)).fetchone()
        
        if result:
            logger.info("Nodes table already exists, skipping creation...")
            return
            
        self._create_nodes_table(connection)

    def _create_node_links_table_if_not_exists(self, connection: Connection) -> None:
        """Create the new node_links table if it doesn't exist."""
        # Check if table exists
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='node_links'
        """)).fetchone()
        
        if result:
            logger.info("Node_links table already exists, skipping creation...")
            return
            
        self._create_node_links_table(connection)

    def _create_node_events_table_if_not_exists(self, connection: Connection) -> None:
        """Create the new node_events table if it doesn't exist."""
        # Check if table exists
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='node_events'
        """)).fetchone()
        
        if result:
            logger.info("Node_events table already exists, skipping creation...")
            return
            
        self._create_node_events_table(connection)

    def _create_nodes_table(self, connection: Connection) -> None:
        """Create the new nodes table."""
        logger.info("Creating nodes table...")
        
        connection.execute(text("""
            CREATE TABLE nodes (
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
                
                FOREIGN KEY (parent_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (structural_predicate_id) REFERENCES predicates(id)
            );
        """))

        # Create indexes for performance
        connection.execute(text("CREATE INDEX idx_nodes_node_type ON nodes(node_type);"))
        connection.execute(text("CREATE INDEX idx_nodes_parent_node_id ON nodes(parent_node_id);"))
        connection.execute(text("CREATE INDEX idx_nodes_type_parent ON nodes(node_type, parent_node_id);"))

    def _create_node_links_table(self, connection: Connection) -> None:
        """Create the new node_links table."""
        logger.info("Creating node_links table...")
        
        connection.execute(text("""
            CREATE TABLE node_links (
                id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                predicate_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (source_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (predicate_id) REFERENCES predicates(id),
                
                UNIQUE(source_node_id, target_node_id, predicate)
            );
        """))

        # Create indexes for performance
        connection.execute(text("CREATE INDEX idx_node_links_source ON node_links(source_node_id);"))
        connection.execute(text("CREATE INDEX idx_node_links_target ON node_links(target_node_id);"))

    def _create_node_events_table(self, connection: Connection) -> None:
        """Create the new node_events table."""
        logger.info("Creating node_events table...")
        
        connection.execute(text("""
            CREATE TABLE node_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,  -- create, update, delete
                node_type TEXT NOT NULL,   -- layer, domain, term, node_link
                old_data TEXT,             -- JSON
                new_data TEXT,             -- JSON
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE NOT NULL
            );
        """))

        # Create index for performance
        connection.execute(text("CREATE INDEX idx_node_events_processed ON node_events(processed);"))

    def _create_nodes_vec_table(self, connection: Connection) -> None:
        """Create vector embeddings virtual table for nodes."""
        logger.info("Creating nodes vector table...")
        
        try:
            # Try to create the vector table - this requires sqlite-vec extension
            try:
                import sqlite_vec
            except ImportError:
                logger.warning("sqlite-vec extension not available. Skipping nodes vector table creation.")
                return
                
            raw_connection = connection.connection
            raw_connection.enable_load_extension(True)
            sqlite_vec.load(raw_connection)
            raw_connection.enable_load_extension(False)
            
            # Create virtual table for vector embeddings (sqlite-vec)
            connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS nodes_vec USING vec0(
                    node_id TEXT PRIMARY KEY,
                    title_embedding FLOAT[384],
                    definition_embedding FLOAT[384]
                )
            """))
            
        except Exception as e:
            logger.warning(f"Could not create nodes vector table: {e}")

    def _create_node_triggers(self, connection: Connection) -> None:
        """Create triggers for node events."""
        logger.info("Creating node event triggers...")
        
        # Read the trigger SQL file
        import os
        triggers_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sqlite_node_event_triggers.sql')
        
        if os.path.exists(triggers_path):
            with open(triggers_path, 'r') as f:
                triggers_sql = f.read()
                
            # Split and execute each trigger
            for trigger in triggers_sql.split('CREATE TRIGGER'):
                if trigger.strip():
                    trigger_sql = 'CREATE TRIGGER' + trigger
                    try:
                        connection.execute(text(trigger_sql))
                    except Exception as e:
                        logger.warning(f"Could not create trigger: {e}")
        else:
            logger.warning("Node triggers SQL file not found, creating triggers inline...")
            self._create_node_triggers_inline(connection)

    def _create_node_triggers_inline(self, connection: Connection) -> None:
        """Create triggers inline if SQL file is not found."""
        try:
            # Node insert trigger
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_node_insert AFTER INSERT ON nodes
                BEGIN
                  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
                  VALUES ('create', NEW.node_type, NULL, json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id, 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id, 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), CURRENT_TIMESTAMP, 0);
                END;
            """))

            # Node update trigger
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_node_update AFTER UPDATE ON nodes
                BEGIN
                  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
                  VALUES ('update', NEW.node_type, json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id, 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id, 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), json_object('id', NEW.id, 'node_type', NEW.node_type, 'parent_node_id', NEW.parent_node_id, 'title', NEW.title, 'definition', NEW.definition, 'structural_predicate_id', NEW.structural_predicate_id, 'created_at', NEW.created_at, 'version', NEW.version, 'last_modified', NEW.last_modified), CURRENT_TIMESTAMP, 0);
                END;
            """))

            # Node delete trigger
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_node_delete AFTER DELETE ON nodes
                BEGIN
                  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
                  VALUES ('delete', OLD.node_type, json_object('id', OLD.id, 'node_type', OLD.node_type, 'parent_node_id', OLD.parent_node_id, 'title', OLD.title, 'definition', OLD.definition, 'structural_predicate_id', OLD.structural_predicate_id, 'created_at', OLD.created_at, 'version', OLD.version, 'last_modified', OLD.last_modified), NULL, CURRENT_TIMESTAMP, 0);
                END;
            """))

            # Node link triggers
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_node_link_insert AFTER INSERT ON node_links
                BEGIN
                  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
                  VALUES ('create', 'node_link', NULL, json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id, 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
                END;
            """))

            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_node_link_update AFTER UPDATE ON node_links
                BEGIN
                  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
                  VALUES ('update', 'node_link', json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id, 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at), json_object('id', NEW.id, 'source_node_id', NEW.source_node_id, 'target_node_id', NEW.target_node_id, 'predicate', NEW.predicate, 'predicate_id', NEW.predicate_id, 'created_at', NEW.created_at), CURRENT_TIMESTAMP, 0);
                END;
            """))

            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_node_link_delete AFTER DELETE ON node_links
                BEGIN
                  INSERT INTO node_events (event_type, node_type, old_data, new_data, timestamp, processed)
                  VALUES ('delete', 'node_link', json_object('id', OLD.id, 'source_node_id', OLD.source_node_id, 'target_node_id', OLD.target_node_id, 'predicate', OLD.predicate, 'predicate_id', OLD.predicate_id, 'created_at', OLD.created_at), NULL, CURRENT_TIMESTAMP, 0);
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
                WHERE type='table' AND name='nodes_vec'
            """)).fetchone()
            
            if not vector_table_exists:
                logger.info("Vector table does not exist, skipping vector population")
                return
            
            # Populate vector embeddings from nodes with embeddings
            nodes_with_embeddings = connection.execute(text("""
                SELECT id, title_embedding, definition_embedding 
                FROM nodes 
                WHERE title_embedding IS NOT NULL OR definition_embedding IS NOT NULL
            """)).fetchall()
            
            for node in nodes_with_embeddings:
                try:
                    connection.execute(text("""
                        INSERT INTO nodes_vec (node_id, title_embedding, definition_embedding)
                        VALUES (?, ?, ?)
                    """), (node[0], node[1], node[2]))
                except Exception as e:
                    logger.warning(f"Could not insert vector embedding for node {node[0]}: {e}")
                    
            logger.info(f"Populated vector embeddings for {len(nodes_with_embeddings)} nodes")
            
        except Exception as e:
            logger.warning(f"Could not populate vector embeddings: {e}")

    def _migrate_layers_to_nodes(self, connection: Connection) -> None:
        """Migrate layer records to nodes table."""
        logger.info("Migrating layers to nodes...")
        
        # Use raw SQL with parameter substitution to avoid SQLAlchemy Row issues
        connection.execute(text("""
            INSERT INTO nodes (
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

    def _migrate_domains_to_nodes(self, connection: Connection) -> None:
        """Migrate domain records to nodes table."""
        logger.info("Migrating domains to nodes...")
        
        connection.execute(text("""
            INSERT INTO nodes (
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

    def _migrate_terms_to_nodes(self, connection: Connection) -> None:
        """Migrate term records to nodes table."""
        logger.info("Migrating terms to nodes...")
        
        connection.execute(text("""
            INSERT INTO nodes (
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

    def _migrate_term_relationships_to_node_links(self, connection: Connection) -> None:
        """Migrate term_relationships records to node_links table."""
        logger.info("Migrating term_relationships to node_links...")
        
        connection.execute(text("""
            INSERT INTO node_links (
                id, source_node_id, target_node_id, predicate, predicate_id, created_at
            )
            SELECT 
                id, source_term_id, target_term_id, predicate, predicate_id, created_at
            FROM term_relationships
        """))

    def _migrate_graph_events_to_node_events(self, connection: Connection) -> None:
        """Migrate graph_events records to node_events table."""
        logger.info("Migrating graph_events to node_events...")
        
        connection.execute(text("""
            INSERT INTO node_events (
                event_type, node_type, old_data, new_data, timestamp, processed
            )
            SELECT 
                event_type,
                CASE 
                    WHEN entity_type = 'term_relationship' THEN 'node_link'
                    ELSE entity_type 
                END as node_type,
                old_data, 
                new_data, 
                timestamp, 
                processed
            FROM graph_events
        """))

    def _validate_migration(self, connection: Connection) -> None:
        """Validate migration integrity."""
        logger.info("Validating migration integrity...")
        
        # Count validation for nodes
        layer_count = connection.execute(text("SELECT COUNT(*) FROM layers")).scalar()
        domain_count = connection.execute(text("SELECT COUNT(*) FROM domains")).scalar()
        term_count = connection.execute(text("SELECT COUNT(*) FROM terms")).scalar()
        total_original = layer_count + domain_count + term_count
        
        node_count = connection.execute(text("SELECT COUNT(*) FROM nodes")).scalar()
        
        if node_count != total_original:
            raise Exception(f"Record count mismatch: {node_count} nodes vs {total_original} original records")
        
        # Count validation for node_links
        term_relationships_count = connection.execute(text("SELECT COUNT(*) FROM term_relationships")).scalar()
        node_links_count = connection.execute(text("SELECT COUNT(*) FROM node_links")).scalar()
        
        if node_links_count != term_relationships_count:
            raise Exception(f"Link count mismatch: {node_links_count} node_links vs {term_relationships_count} term_relationships")
        
        # Count validation for node_events  
        graph_events_count = connection.execute(text("SELECT COUNT(*) FROM graph_events")).scalar()
        node_events_count = connection.execute(text("SELECT COUNT(*) FROM node_events")).scalar()
        
        if node_events_count != graph_events_count:
            raise Exception(f"Event count mismatch: {node_events_count} node_events vs {graph_events_count} graph_events")
        
        # Parent integrity validation
        invalid_parents = connection.execute(text("""
            SELECT COUNT(*) FROM nodes n1
            WHERE n1.parent_node_id IS NOT NULL 
            AND NOT EXISTS (SELECT 1 FROM nodes n2 WHERE n2.id = n1.parent_node_id)
        """)).scalar()
        
        if invalid_parents > 0:
            raise Exception(f"Found {invalid_parents} nodes with invalid parent references")
        
        # Validate vector embeddings virtual table is populated if it exists
        try:
            nodes_vec_count = connection.execute(text("SELECT COUNT(*) FROM nodes_vec")).scalar()
            nodes_with_embeddings_count = connection.execute(text("""
                SELECT COUNT(*) FROM nodes 
                WHERE title_embedding IS NOT NULL OR definition_embedding IS NOT NULL
            """)).scalar()
            
            if nodes_vec_count != nodes_with_embeddings_count:
                logger.warning(f"Vector table count mismatch: {nodes_vec_count} vs {nodes_with_embeddings_count} nodes with embeddings")
        except Exception as e:
            logger.info(f"Vector table validation skipped: {e}")
        
        logger.info(f"Migration validation passed: {node_count} nodes, {node_links_count} links, {node_events_count} events")

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

    def _migrate_nodes_back_to_original_tables(self, connection: Connection) -> None:
        """Migrate data back from nodes to original tables for rollback."""
        logger.info("Migrating data back to original tables...")
        
        # Migrate layers back
        layers = connection.execute(text("""
            SELECT id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified 
            FROM nodes WHERE node_type = 'layer'
        """)).fetchall()
        
        for layer in layers:
            connection.execute(text("""
                INSERT INTO layers (id, title, definition, title_embedding, definition_embedding, 
                                  created_at, version, last_modified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """), layer)

        # Migrate domains back
        domains = connection.execute(text("""
            SELECT id, parent_node_id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified, structural_predicate_id
            FROM nodes WHERE node_type = 'domain'
        """)).fetchall()
        
        for domain in domains:
            connection.execute(text("""
                INSERT INTO domains (id, layer_id, title, definition, title_embedding, definition_embedding, 
                                   created_at, version, last_modified, primary_predicate_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), domain)

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
                       ELSE (SELECT parent_node_id FROM nodes WHERE id = p.parent_node_id)
                   END as layer_id
            FROM nodes n
            LEFT JOIN nodes p ON n.parent_node_id = p.id
            WHERE n.node_type = 'term'
        """)).fetchall()
        
        for term in terms:
            # parent_term_id is set if parent is also a term, otherwise NULL
            parent_term_id = term[8] if term[8] and connection.execute(text("""
                SELECT node_type FROM nodes WHERE id = ?
            """), (term[8],)).scalar() == 'term' else None
            
            connection.execute(text("""
                INSERT INTO terms (id, domain_id, layer_id, title, definition, title_embedding, 
                                 definition_embedding, created_at, version, last_modified, parent_term_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (
                term[0], term[9], term[10], term[1], term[2], term[3],
                term[4], term[5], term[6], term[7], parent_term_id
            ))

        # Migrate node_links back to term_relationships
        links = connection.execute(text("SELECT * FROM node_links")).fetchall()
        for link in links:
            connection.execute(text("""
                INSERT INTO term_relationships (id, source_term_id, target_term_id, predicate, predicate_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """), link)

        # Migrate node_events back to graph_events
        events = connection.execute(text("SELECT * FROM node_events")).fetchall()
        for event in events:
            # Map node_type back to entity_type
            node_type = event[2]
            if node_type == 'node_link':
                entity_type = 'term_relationship'
            else:
                entity_type = node_type
            
            connection.execute(text("""
                INSERT INTO graph_events (event_type, entity_type, old_data, new_data, timestamp, processed)
                VALUES (?, ?, ?, ?, ?, ?)
            """), (event[1], entity_type, event[3], event[4], event[5], event[6]))
