# mypy: ignore-errors
"""Migration 003: Add vector search tables"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration


class Migration003(Migration):
    """Add vector search virtual tables."""

    version = 3
    description = "Add vector search tables"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        # Create sqlite-vec virtual tables for vector search
        # These require the sqlite-vec extension to be loaded
        try:
            # Load sqlite-vec extension for this connection
            try:
                import sqlite_vec
            except ImportError:
                raise RuntimeError(
                    "sqlite-vec extension not available. Install with: pip install sqlite-vec"
                )

            raw_connection = connection.connection
            raw_connection.enable_load_extension(True)
            sqlite_vec.load(raw_connection)
            raw_connection.enable_load_extension(False)

            # Create vector tables for semantic search
            connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS terms_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    title_embedding FLOAT[384],
                    definition_embedding FLOAT[384]
                )
            """))

            connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS domains_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    title_embedding FLOAT[384],
                    definition_embedding FLOAT[384]
                )
            """))

            connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS layers_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    title_embedding FLOAT[384],
                    definition_embedding FLOAT[384]
                )
            """))

        except Exception as e:
            # Migration should fail if vector tables cannot be created
            # This ensures consistent state across all datasets
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create vector tables: {e}")
            logger.error(
                "Migration 003 requires sqlite-vec extension. Install with: pip install sqlite-vec"
            )
            raise RuntimeError(f"Migration 003 failed: {e}") from e

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        # Drop vector tables that were created in up()
        try:
            connection.execute(text("DROP TABLE IF EXISTS terms_vec"))
            connection.execute(text("DROP TABLE IF EXISTS domains_vec"))
            connection.execute(text("DROP TABLE IF EXISTS layers_vec"))
        except Exception as e:
            # Virtual tables might not exist if extension wasn't available during up()
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Could not drop vector tables during rollback: {e}")
            # Don't fail the rollback - the tables might not have been created
