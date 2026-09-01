"""Migration 002: Add graph events table"""

from database.migrations.migration_manager import Migration
from sqlalchemy import text
from sqlalchemy.engine import Connection


class Migration002(Migration):
    """Add graph events table for change tracking."""

    version = 2
    description = "Add graph events"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS graph_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                old_data TEXT,
                new_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE
            )
        """))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        connection.execute(text("DROP TABLE IF EXISTS graph_events"))
