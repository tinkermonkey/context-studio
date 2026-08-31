"""Migration 012: Add unified reference cache tables"""

from database.migrations.migration_manager import Migration
from sqlalchemy import text
from sqlalchemy.engine import Connection


class Migration012(Migration):
    """Add unified reference cache tables for the unified context facade."""

    version = 12
    description = "Add unified reference cache tables"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        # Create unified cache table for storing search results and node data
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS unified_cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create index on expires_at for efficient cleanup
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_unified_cache_expires
            ON unified_cache(expires_at)
        """))

        # Create index on created_at for analytics
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_unified_cache_created
            ON unified_cache(created_at)
        """))

        print("✓ Created unified_cache table with indexes")

    def down(self, connection: Connection) -> None:
        """Reverse the migration."""
        # Drop indexes first
        connection.execute(text("DROP INDEX IF EXISTS idx_unified_cache_expires"))
        connection.execute(text("DROP INDEX IF EXISTS idx_unified_cache_created"))

        # Drop the table
        connection.execute(text("DROP TABLE IF EXISTS unified_cache"))

        print("✓ Dropped unified_cache table and indexes")
