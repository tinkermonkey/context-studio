"""Migration 018: Add attributes column to structure_nodes"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration018(Migration):
    """Add attributes JSON column to structure_nodes table."""

    version = 18
    description = "Add attributes column"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Adding attributes column to structure_nodes table...")

        # Add attributes column (JSON array stored as TEXT)
        # Stores typed metadata attributes like:
        # [{"key": "source_language", "title": "Source Language", "value_type": "string", "value": "English"}]  # noqa: E501
        connection.execute(text("""
            ALTER TABLE structure_nodes
            ADD COLUMN attributes TEXT NULL
        """))
        logger.info("Added attributes column")

        logger.info("Successfully added attributes column to structure_nodes")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Removing attributes column from structure_nodes table...")

        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table  # noqa: E501
        # This is the standard SQLite approach for removing columns

        # Step 1: Create a temporary table with the original schema (without the new column)  # noqa: E501
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
                created_at DATETIME,
                version INTEGER DEFAULT 1,
                last_modified DATETIME,
                FOREIGN KEY (parent_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,  # noqa: E501
                FOREIGN KEY (structural_predicate_id) REFERENCES predicates(id)
            )
        """))

        # Step 2: Copy data from the original table to the temp table
        connection.execute(text("""
            INSERT INTO structure_nodes_temp (
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                reference_links, word_senses, created_at, version, last_modified  # noqa: E501
            )
            SELECT
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                reference_links, word_senses, created_at, version, last_modified  # noqa: E501
            FROM structure_nodes
        """))

        # Step 3: Drop the original table
        connection.execute(text("DROP TABLE structure_nodes"))

        # Step 4: Rename the temp table to the original name
        connection.execute(text("ALTER TABLE structure_nodes_temp RENAME TO structure_nodes"))  # noqa: E501

        # Step 5: Recreate indexes that existed on the original table
        # Check for existing indexes in migration 013
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_structure_nodes_title
            ON structure_nodes(title)
        """))

        logger.info("Successfully removed attributes column from structure_nodes")  # noqa: E501
