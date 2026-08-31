"""Migration template for new migrations."""

from database.migrations.migration_manager import Migration
from sqlalchemy.engine import Connection


class MigrationXXX(Migration):
    """Migration template."""

    version = 0  # Replace with next version number
    description = "Description of what this migration does"

    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        # TODO: Add your migration SQL here
        # Example:
        # connection.execute(text("""
        #     CREATE TABLE new_table (
        #         id INTEGER PRIMARY KEY,
        #         name TEXT NOT NULL
        #     )
        # """))

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        # TODO: Add your rollback SQL here
        # Example:
        # connection.execute(text("DROP TABLE new_table"))
