"""Migration 014: Phase 5 - Transaction Management with Audit Logging"""

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration


class Migration014(Migration):
    """Add audit logging and optimistic locking for transaction management."""

    version = 14
    description = "Add audit logging and optimistic locking for transaction management"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        connection.execute(text("PRAGMA foreign_keys=off;"))

        # 1. Create audit_logs table
        connection.execute(text("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id TEXT,
                old_value TEXT,
                new_value TEXT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INTEGER
            );
        """))

        # 2. Create indexes for efficient audit log queries
        connection.execute(text("""
            CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
        """))
        connection.execute(text("""
            CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
        """))

        # 3. Recreate predicates table with is_relevant and version fields
        connection.execute(text("""
            CREATE TABLE predicates_new (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                mapping TEXT,
                is_relevant INTEGER,
                version INTEGER NOT NULL DEFAULT 1,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Copy existing predicates data
        connection.execute(text("""
            INSERT INTO predicates_new (id, identifier, title, definition, mapping, date_created, date_modified)
            SELECT id, identifier, title, definition, mapping, date_created, date_modified
            FROM predicates;
        """))

        # Drop old predicates table and rename new one
        connection.execute(text("DROP TABLE predicates;"))
        connection.execute(text("ALTER TABLE predicates_new RENAME TO predicates;"))

        # Recreate index and trigger
        connection.execute(text("CREATE INDEX idx_predicates_identifier ON predicates(identifier);"))
        connection.execute(text("""
            CREATE TRIGGER update_predicates_date_modified
                AFTER UPDATE ON predicates
                FOR EACH ROW
            BEGIN
                UPDATE predicates SET date_modified = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        """))

        connection.execute(text("PRAGMA foreign_keys=on;"))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        connection.execute(text("PRAGMA foreign_keys=off;"))

        # 1. Recreate predicates table without is_relevant and version fields
        connection.execute(text("""
            CREATE TABLE predicates_old (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE NOT NULL,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                mapping TEXT,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                date_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Copy predicates data back (excluding is_relevant and version)
        connection.execute(text("""
            INSERT INTO predicates_old (id, identifier, title, definition, mapping, date_created, date_modified)
            SELECT id, identifier, title, definition, mapping, date_created, date_modified
            FROM predicates;
        """))

        connection.execute(text("DROP TABLE predicates;"))
        connection.execute(text("ALTER TABLE predicates_old RENAME TO predicates;"))

        # Recreate index and trigger
        connection.execute(text("CREATE INDEX idx_predicates_identifier ON predicates(identifier);"))
        connection.execute(text("""
            CREATE TRIGGER update_predicates_date_modified
                AFTER UPDATE ON predicates
                FOR EACH ROW
            BEGIN
                UPDATE predicates SET date_modified = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        """))

        # 2. Drop audit_logs table and indexes
        connection.execute(text("DROP INDEX IF EXISTS idx_audit_logs_timestamp;"))
        connection.execute(text("DROP INDEX IF EXISTS idx_audit_logs_entity;"))
        connection.execute(text("DROP TABLE audit_logs;"))

        connection.execute(text("PRAGMA foreign_keys=on;"))
