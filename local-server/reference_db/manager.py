"""
Manager for reference database lifecycle and operations.

This module provides the ReferenceManager class for database initialization,
schema validation, and rebuild operations.
"""

import os
import threading
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session

from utils.logger import get_logger
from .models import Base
from .config import ReferenceConfig, REFERENCE_SCHEMA_VERSION, EMBEDDING_MODEL_VERSION


logger = get_logger(__name__)


class ReferenceManager:
    """
    Manages the reference database lifecycle.

    Handles database initialization, schema version detection, validation,
    and rebuilds when schema changes are detected. Uses atomic lock files
    to prevent race conditions during concurrent operations.

    Attributes:
        config: ReferenceConfig instance with database settings
        engine: SQLAlchemy engine for database connections
        _session_local: Session factory for creating database sessions
        _lock: Thread lock for ensuring thread-safe operations
    """

    def __init__(self, config: Optional[ReferenceConfig] = None):
        """
        Initialize the ReferenceManager.

        Args:
            config: Optional ReferenceConfig instance. Uses defaults if not provided.
        """
        self.config = config or ReferenceConfig()
        self.engine: Optional[Engine] = None
        self._session_local: Optional[sessionmaker] = None
        self._lock = threading.RLock()
        logger.info(
            "ReferenceManager initialized with database_path=%s",
            self.config.database_path
        )

    def get_engine(self) -> Engine:
        """
        Get or create the SQLAlchemy engine for the reference database.

        Uses database.utils functions to ensure sqlite-vec extension is loaded.

        Returns:
            SQLAlchemy Engine instance

        Raises:
            RuntimeError: If sqlite-vec extension fails to load
        """
        if self.engine is None:
            database_url = f"sqlite:///{os.path.abspath(self.config.database_path)}"
            logger.debug("Creating engine for database_url=%s", database_url)

            try:
                # Import here to avoid circular dependencies
                from database.utils import get_engine, init_db

                # Create base engine
                base_engine = get_engine(database_url=database_url)

                # Initialize with sqlite-vec extension loading
                self.engine = init_db(engine=base_engine)

                logger.info("Engine created successfully with sqlite-vec extension")
            except Exception as e:
                logger.error("Failed to create engine with sqlite-vec: %s", e)
                raise RuntimeError(
                    "Vector search dependencies missing. Install sqlite-vec: pip install sqlite-vec"
                ) from e

        return self.engine

    def get_session_local(self) -> sessionmaker:
        """
        Get or create the session factory.

        Returns:
            sessionmaker bound to the reference database engine
        """
        if self._session_local is None:
            engine = self.get_engine()
            self._session_local = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
                expire_on_commit=False
            )
        return self._session_local

    def initialize(self) -> bool:
        """
        Initialize the reference database.

        Validates schema version and rebuilds database if schema or embedding
        model versions don't match. Creates tables if they don't exist.

        Returns:
            True if initialization succeeded, False otherwise

        Raises:
            RuntimeError: If critical initialization errors occur
        """
        logger.info("Initializing reference database")

        with self._lock:
            try:
                # Check if database needs rebuild
                if self._needs_rebuild():
                    logger.info("Schema version mismatch detected, rebuilding database")
                    if not self._rebuild_database():
                        logger.error("Database rebuild failed")
                        return False

                # Create tables if they don't exist
                engine = self.get_engine()
                Base.metadata.create_all(engine)

                # Store current schema version
                self._store_schema_version()

                logger.info("Reference database initialized successfully")
                return True

            except Exception as e:
                logger.exception("Failed to initialize reference database: %s", e)
                return False

    def _needs_rebuild(self) -> bool:
        """
        Check if database needs to be rebuilt due to schema version mismatch.

        Compares stored schema version and embedding model version against
        current versions defined in config module.

        Returns:
            True if rebuild is needed, False otherwise
        """
        db_path = self.config.database_path

        # If database doesn't exist, no rebuild needed (will be created fresh)
        if not os.path.exists(db_path):
            logger.debug("Database file does not exist, no rebuild needed")
            return False

        try:
            engine = self.get_engine()

            # Check if version table exists
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name='reference_db_version'"
                    )
                ).fetchone()

                if not result:
                    logger.info("Version table not found, rebuild required")
                    return True

                # Get stored versions
                version_row = conn.execute(
                    text(
                        "SELECT schema_version, embedding_model FROM reference_db_version "
                        "ORDER BY updated_at DESC LIMIT 1"
                    )
                ).fetchone()

                if not version_row:
                    logger.info("No version record found, rebuild required")
                    return True

                stored_schema = version_row[0]
                stored_embedding_model = version_row[1]

                # Compare versions
                if stored_schema != REFERENCE_SCHEMA_VERSION:
                    logger.info(
                        "Schema version mismatch: stored=%s, current=%s",
                        stored_schema, REFERENCE_SCHEMA_VERSION
                    )
                    return True

                if stored_embedding_model != EMBEDDING_MODEL_VERSION:
                    logger.info(
                        "Embedding model version mismatch: stored=%s, current=%s",
                        stored_embedding_model, EMBEDDING_MODEL_VERSION
                    )
                    return True

                logger.debug("Schema versions match, no rebuild needed")
                return False

        except Exception as e:
            logger.warning("Error checking schema version: %s", e)
            # If we can't verify version, assume rebuild is needed
            return True

    def _rebuild_database(self) -> bool:
        """
        Rebuild the database by creating timestamped backup and recreating schema.

        Uses atomic lock file to prevent concurrent rebuilds. Creates backup
        before deletion to preserve existing data.

        Returns:
            True if rebuild succeeded, False otherwise
        """
        db_path = Path(self.config.database_path)
        lock_path = db_path.with_suffix('.lock')

        # Use atomic lock file to prevent concurrent rebuilds
        try:
            # Try to create lock file atomically
            lock_fd = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644
            )

            try:
                # We have the lock, proceed with rebuild
                logger.info("Acquired rebuild lock")

                # Create timestamped backup if database exists
                if db_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = db_path.with_suffix(f'.backup_{timestamp}.db')

                    try:
                        import shutil
                        shutil.copy2(str(db_path), str(backup_path))
                        logger.info("Created backup at %s", backup_path)
                    except Exception as e:
                        logger.error("Failed to create backup: %s", e)
                        # Continue with rebuild even if backup fails
                        # (but log the error for troubleshooting)

                    # Delete existing database
                    try:
                        db_path.unlink()
                        logger.info("Deleted existing database")
                    except Exception as e:
                        logger.error("Failed to delete existing database: %s", e)
                        return False

                # Clear engine to force recreation
                if self.engine:
                    self.engine.dispose()
                    self.engine = None
                    self._session_local = None

                logger.info("Database rebuild completed successfully")
                return True

            finally:
                # Release lock
                os.close(lock_fd)
                try:
                    lock_path.unlink()
                except Exception:
                    pass

        except FileExistsError:
            logger.warning("Another process is rebuilding the database, waiting...")
            # Another process has the lock, wait for it to complete
            import time
            max_wait = 30  # Wait up to 30 seconds
            waited = 0
            while lock_path.exists() and waited < max_wait:
                time.sleep(0.5)
                waited += 0.5

            if lock_path.exists():
                logger.error("Timeout waiting for database rebuild lock")
                return False

            logger.info("Other process completed rebuild")
            return True

        except Exception as e:
            logger.exception("Failed to rebuild database: %s", e)
            return False

    def _store_schema_version(self) -> None:
        """
        Store current schema and embedding model versions in the database.

        Creates version table if it doesn't exist and inserts current version record.
        """
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                # Create version table if not exists
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS reference_db_version (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            schema_version TEXT NOT NULL,
                            embedding_model TEXT NOT NULL,
                            updated_at TIMESTAMP NOT NULL
                        )
                        """
                    )
                )

                # Insert current version
                conn.execute(
                    text(
                        """
                        INSERT INTO reference_db_version
                        (schema_version, embedding_model, updated_at)
                        VALUES (:schema_version, :embedding_model, :updated_at)
                        """
                    ),
                    {
                        "schema_version": REFERENCE_SCHEMA_VERSION,
                        "embedding_model": EMBEDDING_MODEL_VERSION,
                        "updated_at": datetime.now()
                    }
                )
                conn.commit()

                logger.debug(
                    "Stored schema version: %s, embedding model: %s",
                    REFERENCE_SCHEMA_VERSION,
                    EMBEDDING_MODEL_VERSION
                )

        except Exception as e:
            logger.warning("Failed to store schema version: %s", e)
            # Non-fatal error, continue

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the reference database.

        Returns:
            Dictionary containing database status information:
                - is_initialized: Whether database is initialized
                - node_count: Number of reference nodes
                - link_count: Number of reference links
                - database_size: Size of database file in bytes
                - schema_version: Current schema version
                - embedding_model: Current embedding model
        """
        status = {
            "is_initialized": False,
            "node_count": 0,
            "link_count": 0,
            "database_size": 0,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "embedding_model": EMBEDDING_MODEL_VERSION
        }

        try:
            db_path = Path(self.config.database_path)
            if db_path.exists():
                status["database_size"] = db_path.stat().st_size

                engine = self.get_engine()
                with engine.connect() as conn:
                    # Check if tables exist
                    tables_exist = conn.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='table' "
                            "AND name IN ('reference_nodes', 'reference_links')"
                        )
                    ).fetchall()

                    if len(tables_exist) == 2:
                        status["is_initialized"] = True

                        # Get counts
                        node_count = conn.execute(
                            text("SELECT COUNT(*) FROM reference_nodes")
                        ).scalar()
                        status["node_count"] = int(node_count or 0)

                        link_count = conn.execute(
                            text("SELECT COUNT(*) FROM reference_links")
                        ).scalar()
                        status["link_count"] = int(link_count or 0)

        except Exception as e:
            logger.debug("Error getting database status: %s", e)

        return status

    def cleanup(self) -> None:
        """
        Clean up database resources.

        Disposes of the engine and closes all connections.
        """
        logger.info("Cleaning up reference database resources")

        with self._lock:
            if self.engine:
                try:
                    self.engine.dispose()
                    logger.debug("Engine disposed successfully")
                except Exception as e:
                    logger.warning("Error disposing engine: %s", e)
                finally:
                    self.engine = None
                    self._session_local = None


