"""Base migration class and migration manager."""

import hashlib
import importlib.util
import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from dataset.models import MigrationStatus
from utils.logger import get_logger

logger = get_logger(__name__)


class Migration(ABC):
    """Base class for database migrations."""

    version: int
    description: str

    @abstractmethod
    def up(self, connection: Connection) -> None:
        """Apply the migration."""
        pass

    @abstractmethod
    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        pass


class MigrationManager:
    """Handles database schema migrations."""

    def __init__(self, database_path: str):
        self.database_path = database_path
        self.database_url = f"sqlite:///{database_path}"
        self.migrations_dir = os.path.join(
            os.path.dirname(__file__),
            "versions"
        )
        self.current_version = self._get_current_schema_version()
        self.target_version = self._get_latest_migration_version()
        logger.info(f"MigrationManager initialized: current_version={self.current_version}, target_version={self.target_version}")  # noqa: E501

    def get_current_version(self) -> int:
        """Get the current schema version (alias for current_version property)."""  # noqa: E501
        return self.current_version

    def _ensure_schema_history_table(self, connection: Connection) -> None:
        """Ensure the schema_history table exists."""
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL UNIQUE,
                description TEXT NOT NULL,
                migration_file TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT NOT NULL,
                execution_time_ms INTEGER
            )
        """))

    def _get_current_schema_version(self) -> int:
        """Get the current schema version from the database."""
        if not os.path.exists(self.database_path):
            return 0

        try:
            engine = create_engine(self.database_url, connect_args={"check_same_thread": False})  # noqa: E501
            with engine.connect() as conn:
                self._ensure_schema_history_table(conn)
                result = conn.execute(text(
                    "SELECT MAX(version) FROM schema_history"
                )).scalar()
                return result or 0
        except Exception as e:
            logger.warning(f"Failed to get current schema version: {e}")
            return 0

    def _get_latest_migration_version(self) -> int:
        """Get the latest available migration version."""
        migrations = self._discover_migrations()
        if not migrations:
            return 0
        return max(migration.version for migration in migrations)

    def _discover_migrations(self) -> List[Migration]:
        """Discover all migration files in the versions directory."""
        migrations: List[Migration] = []

        if not os.path.exists(self.migrations_dir):
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")  # noqa: E501
            return migrations

        for filename in sorted(os.listdir(self.migrations_dir)):
            if filename.endswith('.py') and filename != '__init__.py':
                migration_path = os.path.join(self.migrations_dir, filename)
                try:
                    migration = self._load_migration(migration_path)
                    if migration:
                        migrations.append(migration)
                except Exception as e:
                    logger.error(f"Failed to load migration {filename}: {e}")

        return sorted(migrations, key=lambda m: m.version)

    def _load_migration(self, migration_path: str) -> Optional[Migration]:
        """Load a migration from a Python file."""
        spec = importlib.util.spec_from_file_location("migration", migration_path)  # noqa: E501
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find Migration class in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, Migration) and
                attr != Migration):  # noqa: E129
                return attr()

        return None

    def _calculate_migration_checksum(self, migration: Migration) -> str:
        """Calculate checksum for a migration."""
        content = f"{migration.version}:{migration.description}"
        return hashlib.md5(content.encode()).hexdigest()

    def migrate_to_version(self, target_version: int) -> bool:
        """Apply or rollback migrations to reach specific version."""
        if isinstance(target_version, str):
            target_version = int(target_version)

        logger.info(f"Migrating to version {target_version} from {self.current_version}")  # noqa: E501

        if target_version == self.current_version:
            logger.info(f"Already at version {target_version}")
            return True
        elif target_version > self.current_version:
            # Apply forward migrations
            migrations = self._discover_migrations()
            pending_migrations = [
                m for m in migrations
                if self.current_version < m.version <= target_version
            ]

            if not pending_migrations:
                logger.info("No migrations to apply")
                return True

            logger.info(f"Applying {len(pending_migrations)} migrations to reach version {target_version}")  # noqa: E501

            engine = create_engine(self.database_url, connect_args={"check_same_thread": False})  # noqa: E501

            try:
                with engine.connect() as conn:
                    # Ensure schema history table exists
                    with conn.begin():
                        self._ensure_schema_history_table(conn)

                    for migration in pending_migrations:
                        try:
                            # Use a separate transaction for each migration
                            with conn.begin():
                                start_time = time.time()

                                logger.info(f"Applying migration {migration.version}: {migration.description}")  # noqa: E501
                                migration.up(conn)

                                execution_time = int((time.time() - start_time) * 1000)  # noqa: E501
                                checksum = self._calculate_migration_checksum(migration)  # noqa: E501

                                # Record migration in history
                                conn.execute(text("""
                                    INSERT INTO schema_history
                                    (version, description, migration_file, checksum, execution_time_ms)  # noqa: E501
                                    VALUES (:version, :description, :migration_file, :checksum, :execution_time)  # noqa: E501
                                """), {
                                    "version": migration.version,
                                    "description": migration.description,
                                    "migration_file": f"{migration.version:03d}_{migration.description.lower().replace(' ', '_')}.py",  # noqa: E501
                                    "checksum": checksum,
                                    "execution_time": execution_time
                                })

                                logger.info(f"Migration {migration.version} completed in {execution_time}ms")  # noqa: E501

                        except Exception as e:
                            logger.error(f"Migration {migration.version} failed: {e}")  # noqa: E501
                            raise

                # Update current version
                self.current_version = self._get_current_schema_version()
                logger.info(f"Forward migration completed. Current version: {self.current_version}")  # noqa: E501
                return True

            except Exception as e:
                logger.error(f"Migration process failed: {e}")
                return False
            finally:
                engine.dispose()
        else:
            # Rollback to earlier version
            return self.rollback_to_version(target_version)

    def migrate_to_latest(self, skip_on_error: bool = False) -> bool:
        """Apply all pending migrations to bring database to latest version."""
        logger.info(f"Migrate to latest: current schema version: {self.current_version}, target version: {self.target_version}")  # noqa: E501
        migrations = self._discover_migrations()
        pending_migrations = [
            m for m in migrations
            if m.version > self.current_version
        ]

        if not pending_migrations:
            logger.info("No pending migrations")
            return True

        logger.info(f"Applying {len(pending_migrations)} pending migrations")

        engine = create_engine(self.database_url, connect_args={"check_same_thread": False})  # noqa: E501

        try:
            with engine.connect() as conn:
                # Ensure schema history table exists
                with conn.begin():
                    self._ensure_schema_history_table(conn)

                for migration in pending_migrations:
                    try:
                        # Use a separate transaction for each migration
                        with conn.begin():
                            start_time = time.time()

                            logger.info(f"Applying migration {migration.version}: {migration.description}")  # noqa: E501
                            migration.up(conn)

                            execution_time = int((time.time() - start_time) * 1000)  # noqa: E501
                            checksum = self._calculate_migration_checksum(migration)  # noqa: E501

                            # Record migration in history
                            conn.execute(text("""
                                INSERT INTO schema_history
                                (version, description, migration_file, checksum, execution_time_ms)  # noqa: E501
                                VALUES (:version, :description, :migration_file, :checksum, :execution_time)  # noqa: E501
                            """), {
                                "version": migration.version,
                                "description": migration.description,
                                "migration_file": f"{migration.version:03d}_{migration.description.lower().replace(' ', '_')}.py",  # noqa: E501
                                "checksum": checksum,
                                "execution_time": execution_time
                            })

                            logger.info(f"Migration {migration.version} completed in {execution_time}ms")  # noqa: E501

                    except Exception as e:
                        logger.error(f"Migration {migration.version} failed: {e}")  # noqa: E501
                        if not skip_on_error:
                            raise
                        continue

            # Update current version
            self.current_version = self._get_current_schema_version()
            logger.info(f"Migrations completed. Current version: {self.current_version}")  # noqa: E501
            return True

        except Exception as e:
            logger.error(f"Migration process failed: {e}")
            return False
        finally:
            engine.dispose()

    def get_migration_status(self) -> MigrationStatus:
        """Get current migration status."""
        migrations = self._discover_migrations()
        pending_migrations = [
            f"{m.version:03d}_{m.description.lower().replace(' ', '_')}.py"
            for m in migrations
            if m.version > self.current_version
        ]

        return MigrationStatus(
            current_version=self.current_version,
            target_version=self.target_version,
            pending_migrations=pending_migrations,
            needs_migration=len(pending_migrations) > 0
        )

    def rollback_to_version(self, target_version: int) -> bool:
        """Rollback to a specific schema version."""
        if target_version >= self.current_version:
            logger.info(f"Already at or below version {target_version}")
            return True

        migrations = self._discover_migrations()
        rollback_migrations = [
            m for m in reversed(migrations)
            if target_version < m.version <= self.current_version
        ]

        if not rollback_migrations:
            logger.info("No migrations to rollback")
            return True

        logger.info(f"Rolling back {len(rollback_migrations)} migrations")

        engine = create_engine(self.database_url, connect_args={"check_same_thread": False})  # noqa: E501

        try:
            with engine.connect() as conn:
                for migration in rollback_migrations:
                    try:
                        # Use a separate transaction for each rollback
                        with conn.begin():
                            logger.info(f"Rolling back migration {migration.version}: {migration.description}")  # noqa: E501
                            migration.down(conn)

                            # Remove from history
                            conn.execute(text(
                                "DELETE FROM schema_history WHERE version = :version"  # noqa: E501
                            ), {"version": migration.version})

                            logger.info(f"Migration {migration.version} rolled back")  # noqa: E501

                    except Exception as e:
                        logger.error(f"Rollback of migration {migration.version} failed: {e}")  # noqa: E501
                        raise

            # Update current version
            self.current_version = self._get_current_schema_version()
            logger.info(f"Rollback completed. Current version: {self.current_version}")  # noqa: E501
            return True

        except Exception as e:
            logger.error(f"Rollback process failed: {e}")
            return False
        finally:
            engine.dispose()

    def generate_migration(self, description: str) -> str:
        """Generate a new migration file template."""
        next_version = self.target_version + 1
        filename = f"{next_version:03d}_{description.lower().replace(' ', '_')}.py"  # noqa: E501
        filepath = os.path.join(self.migrations_dir, filename)

        template = f'''"""Migration {next_version}: {description}"""

from sqlalchemy.engine import Connection
from database.migrations.migration_manager import Migration


class Migration{next_version:03d}(Migration):
    """Migration for: {description}"""

    version = {next_version}
    description = "{description}"

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
        pass

    def down(self, connection: Connection) -> None:
        """Rollback the migration."""
        # TODO: Add your rollback SQL here
        # Example:
        # connection.execute(text("DROP TABLE new_table"))
        pass
'''

        with open(filepath, 'w') as f:
            f.write(template)

        logger.info(f"Generated migration file: {filepath}")
        return filepath
