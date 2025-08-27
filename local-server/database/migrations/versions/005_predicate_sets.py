"""Migration 005: Add predicate sets functionality."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration

class Migration005(Migration):
    """Add predicate sets functionality with predicates table and related schema changes."""
    version = 5
    description = "Add predicate sets functionality with predicates table and related schema changes."

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        connection.execute(text("PRAGMA foreign_keys=off;"))
        
        # 1. Create predicates table
        connection.execute(text("""
            CREATE TABLE predicates (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                mapping TEXT,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # 2. Create index for efficient lookup by identifier
        connection.execute(text("CREATE INDEX idx_predicates_identifier ON predicates(identifier);"))
        
        # 3. Create trigger to update date_modified on updates
        connection.execute(text("""
            CREATE TRIGGER update_predicates_date_modified 
                AFTER UPDATE ON predicates
                FOR EACH ROW
            BEGIN
                UPDATE predicates SET date_modified = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        """))
        
        # 4. Recreate domains table with new predicate fields
        connection.execute(text("""
            CREATE TABLE domains_new (
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
        
        # Copy existing domains data
        connection.execute(text("""
            INSERT INTO domains_new (id, layer_id, title, definition, title_embedding, definition_embedding, 
                                   created_at, version, last_modified)
            SELECT id, layer_id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified
            FROM domains;
        """))
        
        # Drop old domains table and rename new one
        connection.execute(text("DROP TABLE domains;"))
        connection.execute(text("ALTER TABLE domains_new RENAME TO domains;"))
        
        # 5. Recreate term_relationships table with predicate_id field
        connection.execute(text("""
            CREATE TABLE term_relationships_new (
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
        
        # Copy existing term_relationships data
        connection.execute(text("""
            INSERT INTO term_relationships_new (id, source_term_id, target_term_id, predicate, created_at)
            SELECT id, source_term_id, target_term_id, predicate, created_at
            FROM term_relationships;
        """))
        
        # Drop old term_relationships table and rename new one
        connection.execute(text("DROP TABLE term_relationships;"))
        connection.execute(text("ALTER TABLE term_relationships_new RENAME TO term_relationships;"))
        
        # 6. Recreate layers table without primary_predicate field
        connection.execute(text("""
            CREATE TABLE layers_new (
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
        
        # Copy existing layers data (excluding primary_predicate if it exists)
        connection.execute(text("""
            INSERT INTO layers_new (id, title, definition, title_embedding, definition_embedding, 
                                  created_at, version, last_modified)
            SELECT id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified
            FROM layers;
        """))
        
        # Drop old layers table and rename new one
        connection.execute(text("DROP TABLE layers;"))
        connection.execute(text("ALTER TABLE layers_new RENAME TO layers;"))
        
        # 7. Create vector table for predicates (if sqlite-vec is available)
        self._create_predicates_vector_table(connection)
        
        # 8. Update existing term_relationships to reference predicate IDs where possible
        self._update_existing_predicate_references(connection)
        
        connection.execute(text("PRAGMA foreign_keys=on;"))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        connection.execute(text("PRAGMA foreign_keys=off;"))
        
        # 1. Recreate layers table with primary_predicate field
        connection.execute(text("""
            CREATE TABLE layers_old (
                id TEXT PRIMARY KEY,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                primary_predicate TEXT,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Copy layers data back
        connection.execute(text("""
            INSERT INTO layers_old (id, title, definition, title_embedding, definition_embedding, 
                                  created_at, version, last_modified)
            SELECT id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified
            FROM layers;
        """))
        
        connection.execute(text("DROP TABLE layers;"))
        connection.execute(text("ALTER TABLE layers_old RENAME TO layers;"))
        
        # 2. Recreate term_relationships table without predicate_id
        connection.execute(text("""
            CREATE TABLE term_relationships_old (
                id TEXT PRIMARY KEY,
                source_term_id TEXT NOT NULL,
                target_term_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_term_id) REFERENCES terms (id) ON DELETE CASCADE,
                FOREIGN KEY (target_term_id) REFERENCES terms (id) ON DELETE CASCADE,
                UNIQUE (source_term_id, target_term_id, predicate)
            );
        """))
        
        # Copy term_relationships data back (excluding predicate_id)
        connection.execute(text("""
            INSERT INTO term_relationships_old (id, source_term_id, target_term_id, predicate, created_at)
            SELECT id, source_term_id, target_term_id, predicate, created_at
            FROM term_relationships;
        """))
        
        connection.execute(text("DROP TABLE term_relationships;"))
        connection.execute(text("ALTER TABLE term_relationships_old RENAME TO term_relationships;"))
        
        # 3. Recreate domains table without predicate fields
        connection.execute(text("""
            CREATE TABLE domains_old (
                id TEXT PRIMARY KEY,
                layer_id TEXT NOT NULL,
                title TEXT NOT NULL,
                definition TEXT NOT NULL,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,
                UNIQUE (layer_id, title)
            );
        """))
        
        # Copy domains data back (excluding predicate fields)
        connection.execute(text("""
            INSERT INTO domains_old (id, layer_id, title, definition, title_embedding, definition_embedding, 
                                   created_at, version, last_modified)
            SELECT id, layer_id, title, definition, title_embedding, definition_embedding, 
                   created_at, version, last_modified
            FROM domains;
        """))
        
        connection.execute(text("DROP TABLE domains;"))
        connection.execute(text("ALTER TABLE domains_old RENAME TO domains;"))
        
        # 4. Drop predicates table and related objects
        connection.execute(text("DROP TABLE IF EXISTS predicates_vec;"))
        connection.execute(text("DROP TRIGGER IF EXISTS update_predicates_date_modified;"))
        connection.execute(text("DROP INDEX IF EXISTS idx_predicates_identifier;"))
        connection.execute(text("DROP TABLE predicates;"))
        
        connection.execute(text("PRAGMA foreign_keys=on;"))

    def _create_predicates_vector_table(self, connection: Connection) -> None:
        """Create vector table for predicates if sqlite-vec is available."""
        try:
            # Try to create the vector table - this requires sqlite-vec extension
            try:
                import sqlite_vec
            except ImportError:
                # If sqlite-vec is not available, skip vector table creation
                # This allows the migration to succeed even without the extension
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("sqlite-vec extension not available. Skipping predicates vector table creation.")
                return
                
            raw_connection = connection.connection
            raw_connection.enable_load_extension(True)
            sqlite_vec.load(raw_connection)
            raw_connection.enable_load_extension(False)
            
            # Create vector table for predicates semantic search
            connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS predicates_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    title_embedding FLOAT[384],
                    definition_embedding FLOAT[384]
                )
            """))
            
        except Exception as e:
            # Don't fail the migration if vector table creation fails
            # The core functionality works without vector search
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not create predicates vector table: {e}")

    def _update_existing_predicate_references(self, connection: Connection) -> None:
        """Update existing term_relationships to reference predicate IDs where possible."""
        # Get all existing predicates from term_relationships
        existing_predicates = connection.execute(text("""
            SELECT DISTINCT predicate FROM term_relationships
        """)).fetchall()
        
        for row in existing_predicates:
            predicate_value = row[0]
            
            # Try to find a matching predicate by identifier or title
            predicate_match = connection.execute(text("""
                SELECT id FROM predicates 
                WHERE identifier = :predicate OR title = :predicate
                LIMIT 1
            """), {"predicate": predicate_value}).fetchone()
            
            if predicate_match:
                predicate_id = predicate_match[0]
                
                # Update all term_relationships with this predicate
                connection.execute(text("""
                    UPDATE term_relationships 
                    SET predicate_id = :predicate_id 
                    WHERE predicate = :predicate
                """), {
                    "predicate_id": predicate_id,
                    "predicate": predicate_value
                })

    def _generate_identifier_from_title(self, title: str) -> str:
        """
        Generate a code-safe identifier from a title.
        Converts CamelCase to underscore_lowercase and handles spaces/special chars.
        """
        import re
        # First, convert CamelCase to underscore_case
        # Insert underscore before uppercase letters that follow lowercase letters or digits
        identifier = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', title)
        # Convert to lowercase
        identifier = identifier.lower()
        # Replace whitespace and special characters with underscores
        identifier = re.sub(r'[^\w]', '_', identifier)
        # Remove multiple consecutive underscores
        identifier = re.sub(r'_+', '_', identifier)
        # Remove leading/trailing underscores
        identifier = identifier.strip('_')
        return identifier
