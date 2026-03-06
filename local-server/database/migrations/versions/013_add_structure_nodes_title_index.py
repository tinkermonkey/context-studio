"""Migration 013: Add composite index for structure_nodes (node_type, title) to optimize pagination queries."""  # noqa: E501

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration
import logging

logger = logging.getLogger(__name__)


class Migration013(Migration):
    """Add composite index for structure_nodes (node_type, title) to optimize pagination queries."""  # noqa: E501
    version = 13
    description = "Add composite index for structure_nodes (node_type, title) to optimize pagination queries."  # noqa: E501

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        logger.info("Adding composite index for structure_nodes (node_type, title)...")  # noqa: E501

        # Add composite index for efficient filtering by node_type with ordering by title  # noqa: E501
        # This optimizes queries like: SELECT * FROM structure_nodes WHERE node_type = 'term' ORDER BY title LIMIT 100 OFFSET 100  # noqa: E501
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_nodes_type_title ON structure_nodes(node_type, title);"))  # noqa: E501

        logger.info("Successfully added composite index idx_nodes_type_title")

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        logger.info("Removing composite index for structure_nodes (node_type, title)...")  # noqa: E501

        connection.execute(text("DROP INDEX IF EXISTS idx_nodes_type_title;"))

        logger.info("Successfully removed composite index idx_nodes_type_title")  # noqa: E501
