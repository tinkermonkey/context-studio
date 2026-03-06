"""Migration 004: Enforce uniqueness for domain title within layer and term title within domain."""  # noqa: E501

from sqlalchemy.engine import Connection
from sqlalchemy import text
from database.migrations.migration_manager import Migration


class Migration004(Migration):
    """Enforce uniqueness for domain title within layer and term title within domain."""  # noqa: E501
    version = 4
    description = "Enforce uniqueness for domain title within layer and term title within domain."  # noqa: E501

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        connection.execute(text("PRAGMA foreign_keys=off;"))
        # Domains table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS domains_new (
                id TEXT PRIMARY KEY,
                layer_id TEXT NOT NULL,
                title TEXT NOT NULL,
                definition TEXT NOT NULL,
                title_embedding BLOB,
                definition_embedding BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,  # noqa: E501
                UNIQUE (layer_id, title)
            );
        """))
        connection.execute(text("INSERT INTO domains_new SELECT * FROM domains;"))  # noqa: E501
        connection.execute(text("DROP TABLE domains;"))
        connection.execute(text("ALTER TABLE domains_new RENAME TO domains;"))
        # Terms table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS terms_new (
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
                FOREIGN KEY (domain_id) REFERENCES domains (id) ON DELETE CASCADE,  # noqa: E501
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,  # noqa: E501
                FOREIGN KEY (parent_term_id) REFERENCES terms (id) ON DELETE SET NULL,  # noqa: E501
                UNIQUE (domain_id, title)
            );
        """))
        connection.execute(text("INSERT INTO terms_new SELECT * FROM terms;"))
        connection.execute(text("DROP TABLE terms;"))
        connection.execute(text("ALTER TABLE terms_new RENAME TO terms;"))
        connection.execute(text("PRAGMA foreign_keys=on;"))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        connection.execute(text("PRAGMA foreign_keys=off;"))
        # Domains table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS domains_old (
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
            );
        """))
        connection.execute(text("INSERT INTO domains_old SELECT * FROM domains;"))  # noqa: E501
        connection.execute(text("DROP TABLE domains;"))
        connection.execute(text("ALTER TABLE domains_old RENAME TO domains;"))
        # Terms table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS terms_old (
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
                FOREIGN KEY (domain_id) REFERENCES domains (id) ON DELETE CASCADE,  # noqa: E501
                FOREIGN KEY (layer_id) REFERENCES layers (id) ON DELETE CASCADE,  # noqa: E501
                FOREIGN KEY (parent_term_id) REFERENCES terms (id) ON DELETE SET NULL,  # noqa: E501
                UNIQUE (layer_id, title)
            );
        """))
        connection.execute(text("INSERT INTO terms_old SELECT * FROM terms;"))
        connection.execute(text("DROP TABLE terms;"))
        connection.execute(text("ALTER TABLE terms_old RENAME TO terms;"))
        connection.execute(text("PRAGMA foreign_keys=on;"))
