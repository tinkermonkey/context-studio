"""Migration 001: Initial schema"""

from database.migrations.migration_manager import Migration
from sqlalchemy import text
from sqlalchemy.engine import Connection


class Migration001(Migration):
    """Initial database schema migration."""

    version = 1
    description = "Initial schema"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        # Create layers table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS layers (
                id TEXT PRIMARY KEY,
                title TEXT UNIQUE NOT NULL,
                definition TEXT,
                primary_predicate TEXT,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create domains table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS domains (
                id TEXT PRIMARY KEY,
                layer_id TEXT NOT NULL,
                title TEXT UNIQUE NOT NULL,
                definition TEXT NOT NULL,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE
            )
        """))

        # Create terms table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS terms (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                layer_id TEXT NOT NULL,
                title TEXT NOT NULL,
                definition TEXT NOT NULL,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                parent_term_id TEXT,
                FOREIGN KEY (domain_id) REFERENCES domains (id) ON DELETE CASCADE,  
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,  
                FOREIGN KEY (parent_term_id) REFERENCES terms (id) ON DELETE SET NULL,  
                UNIQUE (domain_id, title)
            )
        """))

        # Create term_relationships table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS term_relationships (
                id TEXT PRIMARY KEY,
                source_term_id TEXT NOT NULL,
                target_term_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_term_id) REFERENCES terms (id) ON DELETE CASCADE,  
                FOREIGN KEY (target_term_id) REFERENCES terms (id) ON DELETE CASCADE,  
                UNIQUE (source_term_id, target_term_id, predicate)
            )
        """))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        connection.execute(text("DROP TABLE IF EXISTS term_relationships"))
        connection.execute(text("DROP TABLE IF EXISTS terms"))
        connection.execute(text("DROP TABLE IF EXISTS domains"))
        connection.execute(text("DROP TABLE IF EXISTS layers"))
