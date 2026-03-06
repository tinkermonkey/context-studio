"""Migration 017: Add reference_links and word_senses columns to structure_nodes"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration017(Migration):
    """Add reference_links and word_senses JSON columns to structure_nodes table."""

    version = 17
    description = "Add reference_links and word_senses columns"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Adding reference_links and word_senses columns to structure_nodes table...")

        # Add reference_links column (JSON array stored as TEXT)
        # Stores external reference node identifiers like:
        # [{"source": "schema.org", "external_id": "Person"}, {"source": "wikidata", "external_id": "Q5"}]
        connection.execute(text("""
            ALTER TABLE structure_nodes
            ADD COLUMN reference_links TEXT NULL
        """))
        logger.info("Added reference_links column")

        # Add word_senses column (JSON array stored as TEXT)
        # Stores NLP-identified word sense disambiguations like:
        # [{"term": "bank", "sense_type": "wordnet", "sense_id": "bank.n.01", "definition": "financial institution", "domain": "noun.group"}]
        connection.execute(text("""
            ALTER TABLE structure_nodes
            ADD COLUMN word_senses TEXT NULL
        """))
        logger.info("Added word_senses column")

        logger.info("Successfully added reference_links and word_senses columns to structure_nodes")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Removing reference_links and word_senses columns from structure_nodes table...")

        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        # This is the standard SQLite approach for removing columns

        # Step 1: Create a temporary table with the original schema (without the new columns)
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
                created_at DATETIME,
                version INTEGER DEFAULT 1,
                last_modified DATETIME,
                FOREIGN KEY (parent_node_id) REFERENCES structure_nodes(id) ON DELETE CASCADE,  
                FOREIGN KEY (structural_predicate_id) REFERENCES predicates(id)
            )
        """))

        # Step 2: Copy data from the original table to the temp table
        connection.execute(text("""
            INSERT INTO structure_nodes_temp (
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                created_at, version, last_modified
            )
            SELECT
                id, node_type, parent_node_id, title, definition,
                structural_predicate_id, title_embedding, definition_embedding,
                created_at, version, last_modified
            FROM structure_nodes
        """))

        # Step 3: Drop the original table
        connection.execute(text("DROP TABLE structure_nodes"))

        # Step 4: Rename the temp table to the original name
        connection.execute(text("ALTER TABLE structure_nodes_temp RENAME TO structure_nodes"))

        # Step 5: Recreate indexes that existed on the original table
        # Check for existing indexes in migration 013
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_structure_nodes_title
            ON structure_nodes(title)
        """))

        logger.info("Successfully removed reference_links and word_senses columns from structure_nodes")
