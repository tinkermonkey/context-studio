"""Migration 014: Add is_relevant column to predicates table"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration


class Migration014(Migration):
    """Add is_relevant column to predicates table for relevance tracking."""

    version = 14
    description = "Add is_relevant column to predicates table"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        # Add is_relevant column to predicates table
        # None = not evaluated, True = relevant, False = irrelevant
        connection.execute(text("""
            ALTER TABLE predicates
            ADD COLUMN is_relevant BOOLEAN DEFAULT NULL
        """))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table  # noqa: E501
        connection.execute(text("""
            CREATE TABLE predicates_backup AS
            SELECT id, identifier, title, definition, mapping, date_created, date_modified  # noqa: E501
            FROM predicates
        """))

        connection.execute(text("DROP TABLE predicates"))

        connection.execute(text("""
            CREATE TABLE predicates (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                mapping TEXT,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        connection.execute(text("""
            INSERT INTO predicates (id, identifier, title, definition, mapping, date_created, date_modified)  # noqa: E501
            SELECT id, identifier, title, definition, mapping, date_created, date_modified  # noqa: E501
            FROM predicates_backup
        """))

        connection.execute(text("DROP TABLE predicates_backup"))
