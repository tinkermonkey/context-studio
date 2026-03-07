"""Migration 007: Add Change Management System - Entity versioning, working tree state management."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration007(Migration):
    """Add comprehensive change management system for entity versioning."""

    version = 7
    description = "Add Change Management System - Entity versioning, working tree state management"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Starting Change Management System migration...")

        connection.execute(text("PRAGMA foreign_keys=off;"))

        try:
            # Step 1: Create entity_versions table
            self._create_entity_versions_table(connection)

            # Step 2: Create working_tree table
            self._create_working_tree_table(connection)

            # Step 3: Extend change_events table
            self._extend_change_events_table(connection)

            # Step 4: Create indexes
            self._create_indexes(connection)

            # Step 5: Validate migration
            self._validate_migration(connection)

            logger.info("Change Management System migration completed successfully!")

        except Exception as e:
            logger.error(f"Change Management migration failed: {e}")
            raise
        finally:
            connection.execute(text("PRAGMA foreign_keys=on;"))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Rolling back Change Management System migration...")

        connection.execute(text("PRAGMA foreign_keys=off;"))

        try:
            # Remove added columns from change_events table
            self._rollback_change_events_table(connection)

            # Drop new tables
            connection.execute(text("DROP TABLE IF EXISTS working_tree;"))
            connection.execute(text("DROP TABLE IF EXISTS entity_versions;"))

            logger.info("Change Management System migration rollback completed!")

        except Exception as e:
            logger.error(f"Change Management rollback failed: {e}")
            raise
        finally:
            connection.execute(text("PRAGMA foreign_keys=on;"))

    def _create_entity_versions_table(self, connection: Connection) -> None:
        """Create the entity_versions table."""
        logger.info("Creating entity_versions table...")

        connection.execute(text("""
            CREATE TABLE entity_versions (
                id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),  
                entity_type TEXT NOT NULL CHECK (entity_type IN ('structure_node', 'structure_node_link')),  
                entity_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('WORKING', 'STAGED', 'PROPOSED', 'APPROVED', 'MERGED', 'REJECTED')),  
                parent_version_id TEXT,
                changeset_id TEXT,
                author_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT,

                FOREIGN KEY (parent_version_id) REFERENCES entity_versions(id),
                UNIQUE(entity_type, entity_id, version_number)
            );
        """))

        logger.info("Successfully created entity_versions table")

    def _create_working_tree_table(self, connection: Connection) -> None:
        """Create the working_tree table."""
        logger.info("Creating working_tree table...")

        connection.execute(text("""
            CREATE TABLE working_tree (
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                current_version_id TEXT NOT NULL,
                canonical_version_id TEXT NOT NULL,
                staged BOOLEAN DEFAULT FALSE,
                modified_at TEXT NOT NULL,

                PRIMARY KEY (entity_type, entity_id),
                FOREIGN KEY (current_version_id) REFERENCES entity_versions(id),  
                FOREIGN KEY (canonical_version_id) REFERENCES entity_versions(id)  
            );
        """))

        logger.info("Successfully created working_tree table")

    def _extend_change_events_table(self, connection: Connection) -> None:
        """Extend change_events table with versioning columns."""
        logger.info("Extending change_events table...")

        # Add version_id column
        try:
            connection.execute(text("ALTER TABLE change_events ADD COLUMN version_id TEXT;"))
            logger.info("Added version_id column to change_events")
        except Exception as e:
            if "duplicate column name" not in str(e).lower():
                raise
            logger.info("version_id column already exists in change_events")

        # Add change_state column
        try:
            connection.execute(text("""
                ALTER TABLE change_events ADD COLUMN change_state TEXT
                CHECK (change_state IN ('WORKING', 'STAGED', 'PROPOSED', 'APPROVED', 'MERGED', 'REJECTED'));  
            """))
            logger.info("Added change_state column to change_events")
        except Exception as e:
            if "duplicate column name" not in str(e).lower():
                raise
            logger.info("change_state column already exists in change_events")

    def _create_indexes(self, connection: Connection) -> None:
        """Create indexes for performance."""
        logger.info("Creating indexes...")

        # Entity versions indexes
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_entity_versions_entity ON entity_versions(entity_type, entity_id);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_entity_versions_state ON entity_versions(state);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_entity_versions_created ON entity_versions(created_at);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_entity_versions_parent ON entity_versions(parent_version_id);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_entity_versions_author ON entity_versions(author_id);"))

        # Working tree indexes
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_working_tree_staged ON working_tree(staged);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_working_tree_modified ON working_tree(modified_at);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_working_tree_current ON working_tree(current_version_id);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_working_tree_canonical ON working_tree(canonical_version_id);"))

        # Change events indexes for new columns
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_version ON change_events(version_id);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_state ON change_events(change_state);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_version_state ON change_events(version_id, change_state);"))

        logger.info("Successfully created all indexes")

    def _validate_migration(self, connection: Connection) -> None:
        """Validate migration integrity."""
        logger.info("Validating migration integrity...")

        # Check that entity_versions table exists and has correct structure
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='entity_versions'  
        """)).fetchone()

        if not result:
            raise Exception("entity_versions table was not created")

        # Check that working_tree table exists and has correct structure
        result = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='working_tree'  
        """)).fetchone()

        if not result:
            raise Exception("working_tree table was not created")

        # Check that change_events table has new columns
        change_events_columns = connection.execute(text("""
            PRAGMA table_info(change_events)
        """)).fetchall()

        column_names = [col[1] for col in change_events_columns]

        if 'version_id' not in column_names:
            raise Exception("version_id column not added to change_events table")

        if 'change_state' not in column_names:
            raise Exception("change_state column not added to change_events table")

        # Validate indexes exist
        indexes = connection.execute(text("""
            SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_entity_versions_%'  
        """)).fetchall()

        if len(indexes) < 5:  # We created 5 entity_versions indexes
            logger.warning(f"Expected 5 entity_versions indexes, found {len(indexes)}")

        logger.info("Migration validation passed!")

    def _rollback_change_events_table(self, connection: Connection) -> None:
        """Rollback changes to change_events table."""
        logger.info("Rolling back change_events table modifications...")

        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        # First, get the original table schema (without the new columns)
        connection.execute(text("""
            CREATE TABLE change_events_backup AS
            SELECT id, event_type, record_type, record_id, old_data, new_data, timestamp, processed  
            FROM change_events;
        """))

        # Drop the original table
        connection.execute(text("DROP TABLE change_events;"))

        # Recreate the original table structure
        connection.execute(text("""
            CREATE TABLE change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                record_type TEXT NOT NULL,
                record_id TEXT,
                old_data TEXT,
                new_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE NOT NULL
            );
        """))

        # Restore data
        connection.execute(text("""
            INSERT INTO change_events (id, event_type, record_type, record_id, old_data, new_data, timestamp, processed)  
            SELECT id, event_type, record_type, record_id, old_data, new_data, timestamp, processed  
            FROM change_events_backup;
        """))

        # Drop backup table
        connection.execute(text("DROP TABLE change_events_backup;"))

        # Recreate original indexes
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_processed ON change_events(processed);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_record_id ON change_events(record_id);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_record_type ON change_events(record_type);"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_change_events_type_processed ON change_events(record_type, processed);"))

        logger.info("Successfully rolled back change_events table")
