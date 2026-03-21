"""Migration 013: Add composite index for structure_nodes (node_type, title) to optimize pagination queries."""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration013(Migration):
    """Add composite index for structure_nodes (node_type, title) to optimize pagination queries."""

    version = 13
    description = "Add composite index for structure_nodes (node_type, title) to optimize pagination queries."

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Adding composite index for structure_nodes (node_type, title)...")

        # Add composite index for efficient filtering by node_type with ordering by title
        # This optimizes queries like: SELECT * FROM structure_nodes WHERE node_type = 'term' ORDER BY title LIMIT 100 OFFSET 100
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_nodes_type_title ON structure_nodes(node_type, title);"
            )
        )

        logger.info("Successfully added composite index idx_nodes_type_title")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info(
            "Removing composite index for structure_nodes (node_type, title)..."
        )

        connection.execute(text("DROP INDEX IF EXISTS idx_nodes_type_title;"))

        logger.info("Successfully removed composite index idx_nodes_type_title")
