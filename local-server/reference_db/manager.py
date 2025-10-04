"""
Manager for reference database operations.

This module provides the ReferenceManager class for managing reference nodes and links,
including schema version detection, database rebuild, and embedding operations.
"""

import os
import shutil
import logging
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from database.utils import get_engine, init_db
from reference_db.models import Base, ReferenceNode, ReferenceLink
from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION, EMBEDDING_MODEL_VERSION

# Configure logging
logger = logging.getLogger(__name__)


class ReferenceManager:
    """
    Manager for reference database operations.

    Provides high-level operations for managing reference nodes and links, including:
    - Schema version detection and automatic rebuild
    - CRUD operations for reference nodes and links
    - Embedding management and validation
    - Connection lifecycle management

    The manager supports both context manager protocol for automatic cleanup and
    explicit cleanup via the close() method.

    Resource Management:
        Use context manager for automatic cleanup:
            >>> with ReferenceManager(config) as manager:
            ...     manager.add_reference_node(...)
            # Cleanup happens automatically

        Or manage manually:
            >>> manager = ReferenceManager(config)
            >>> try:
            ...     manager.add_reference_node(...)
            ... finally:
            ...     manager.close()

    Performance Considerations:
        - Current implementation loads embeddings into memory (suitable for small/medium datasets)
        - For large-scale operations, consider implementing streaming/chunking
        - Connection pooling can be added for concurrent access patterns

    Attributes:
        config: ReferenceConfig instance with operational parameters
        db_path: Path to the reference database file
        engine: SQLAlchemy engine instance
        SessionLocal: SQLAlchemy session factory
        session: Current database session
    """

    def __init__(self, config: ReferenceConfig, db_path: str | None = None):
        """
        Initialize the reference database manager.

        Args:
            config: ReferenceConfig instance with operational parameters
            db_path: Optional path to the database file (for testing)

        Raises:
            ValueError: If configuration validation fails
            RuntimeError: If database initialization fails
        """
        self.config = config
        self.db_path = db_path or self._get_default_db_path()
        self.engine = None
        self.SessionLocal = None
        self.session: Session | None = None

        self._initialize_database()

    def __enter__(self):
        """Context manager entry - returns self for use in with statements."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup on exit."""
        self.close()
        return False  # Don't suppress exceptions

    def close(self):
        """
        Close the database session and cleanup resources.

        This method should be called when done with the manager to release
        database connections and other resources. It is automatically called
        when using the context manager protocol.

        Examples:
            >>> manager = ReferenceManager(config)
            >>> try:
            ...     # Use manager
            ... finally:
            ...     manager.close()
        """
        if self.session:
            self.session.close()
            self.session = None
        if self.engine:
            self.engine.dispose()
            self.engine = None

    def _get_default_db_path(self) -> str:
        """
        Get the default path for the reference database.

        Returns:
            Path to the reference database file
        """
        # This will be overridden by the application config
        from config import get_config
        app_config = get_config()
        return app_config.database.reference_path

    def _initialize_database(self):
        """
        Initialize the database connection and verify schema.

        This method:
        1. Creates database connection using existing utilities
        2. Verifies schema version matches expected version
        3. Rebuilds database if schema mismatch detected
        4. Creates session for database operations

        Raises:
            RuntimeError: If database initialization fails
        """
        logger.info(f"Initializing reference database at: {self.db_path}")

        # Ensure database directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Use existing database utilities for engine creation
        # This ensures sqlite-vec extension is loaded properly
        try:
            # Convert file path to SQLAlchemy URL format
            db_url = f"sqlite:///{self.db_path}"
            self.engine = get_engine(db_url)
        except Exception as e:
            error_msg = str(e)
            if 'sqlite-vec' in error_msg or 'vec0' in error_msg:
                raise RuntimeError(
                    "Vector search dependencies missing. Install sqlite-vec: pip install sqlite-vec"
                ) from e
            raise RuntimeError(f"Failed to create database engine: {error_msg}") from e

        # Verify schema version
        if not self._verify_schema_version():
            logger.warning(
                f"Schema version mismatch detected. Expected schema={REFERENCE_SCHEMA_VERSION}, "
                f"embedding_model={EMBEDDING_MODEL_VERSION}"
            )
            self._rebuild_database()

        # Initialize database tables using existing utility
        init_db(self.engine, Base)

        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()

        logger.info("Reference database initialized successfully")

    def _verify_schema_version(self) -> bool:
        """
        Verify that the database schema version matches the expected version.

        This method checks both the schema version and the embedding model version
        to determine if the database structure is compatible with the current code.

        Returns:
            True if schema version matches, False if rebuild is needed

        Raises:
            Exception: Re-raises any unexpected exceptions (not OperationalError)

        Notes:
            Only catches OperationalError for missing tables. Other exceptions
            indicate real problems (e.g., database corruption) and are re-raised.
        """
        try:
            # Create temporary session for version check
            SessionLocal = sessionmaker(bind=self.engine)
            session = SessionLocal()

            try:
                # Query the schema_version table
                result = session.execute(
                    text("SELECT schema_version, embedding_model FROM schema_version LIMIT 1")
                ).first()

                if result:
                    schema_ver, embed_model = result
                    logger.info(
                        f"Found schema version: {schema_ver}, embedding model: {embed_model}"
                    )
                    return (
                        schema_ver == REFERENCE_SCHEMA_VERSION and
                        embed_model == EMBEDDING_MODEL_VERSION
                    )
                else:
                    logger.warning("Schema version table exists but is empty")
                    return False

            finally:
                session.close()

        except OperationalError as e:
            # Expected error when table doesn't exist
            if 'no such table' in str(e).lower():
                logger.info("Schema version table does not exist, rebuild required")
                return False
            # Re-raise other operational errors (e.g., database locked, corrupted)
            raise

        except Exception:
            # Re-raise any unexpected exceptions to surface real problems
            raise

    def _rebuild_database(self):
        """
        Rebuild the database from scratch.

        This method:
        1. Creates a timestamped backup of the existing database
        2. Validates the backup was created successfully
        3. Deletes the old database file
        4. Creates new database with current schema
        5. Initializes schema version table

        The rebuild process uses atomic lock file creation to prevent concurrent
        rebuilds from causing race conditions.

        Raises:
            RuntimeError: If backup creation fails or lock file cannot be acquired

        Notes:
            Lock file is guaranteed to be removed even if rebuild fails, via
            finally block.
        """
        logger.info("Starting database rebuild process")

        # Create timestamped backup (only for non-empty databases)
        timestamp = date.today().isoformat()
        backup_path = f"{self.db_path}.backup.{timestamp}"

        if os.path.exists(self.db_path):
            # Check if database file has content worth backing up
            db_size = os.path.getsize(self.db_path)

            if db_size > 0:
                logger.info(f"Creating backup at: {backup_path}")
                try:
                    shutil.copy2(self.db_path, backup_path)

                    # Validate backup was created successfully
                    if not os.path.exists(backup_path):
                        raise RuntimeError(
                            f"Backup file was not created at: {backup_path}"
                        )

                    backup_size = os.path.getsize(backup_path)
                    if backup_size == 0:
                        raise RuntimeError(
                            f"Backup file is empty (0 bytes): {backup_path}"
                        )

                    logger.info(
                        f"Backup created successfully: {backup_path} ({backup_size} bytes)"
                    )

                except Exception as e:
                    raise RuntimeError(
                        f"Failed to create database backup: {str(e)}"
                    ) from e
            else:
                logger.info(
                    f"Skipping backup of empty database file: {self.db_path} (0 bytes)"
                )

        # Use atomic lock file creation to prevent race conditions
        lock_path = f"{self.db_path}.rebuild.lock"
        lock_fd = None

        try:
            # Try to create lock file atomically (fails if file exists)
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            logger.info(f"Acquired rebuild lock: {lock_path}")

            # Close existing connection before deleting database
            if self.session:
                self.session.close()
            if self.engine:
                self.engine.dispose()

            # Delete old database
            if os.path.exists(self.db_path):
                logger.info(f"Removing old database: {self.db_path}")
                os.remove(self.db_path)

            # Create new database with schema
            logger.info("Creating new database with current schema")
            db_url = f"sqlite:///{self.db_path}"
            self.engine = get_engine(db_url)

            # Initialize tables and schema version in a transaction
            with self.engine.begin() as conn:
                Base.metadata.create_all(bind=self.engine)

                # Create schema version table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        id INTEGER PRIMARY KEY,
                        schema_version TEXT NOT NULL,
                        embedding_model TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """))

                # Insert current schema version
                conn.execute(
                    text("""
                        INSERT INTO schema_version (schema_version, embedding_model, created_at)
                        VALUES (:schema_ver, :embed_model, :created_at)
                    """),
                    {
                        "schema_ver": REFERENCE_SCHEMA_VERSION,
                        "embed_model": EMBEDDING_MODEL_VERSION,
                        "created_at": date.today().isoformat()
                    }
                )

            logger.info(
                f"Database rebuild complete. Schema version: {REFERENCE_SCHEMA_VERSION}, "
                f"Embedding model: {EMBEDDING_MODEL_VERSION}"
            )

        except FileExistsError:
            raise RuntimeError(
                f"Database rebuild already in progress (lock file exists): {lock_path}"
            )

        finally:
            # Ensure lock file is always removed, even on error
            if lock_fd is not None:
                os.close(lock_fd)
            if os.path.exists(lock_path):
                os.remove(lock_path)
                logger.info(f"Released rebuild lock: {lock_path}")

    def _validate_embedding_dimensions(self, embedding: bytes, expected_dims: int) -> bool:
        """
        Validate that an embedding has the expected number of dimensions.

        Args:
            embedding: Binary embedding data
            expected_dims: Expected number of dimensions (based on embedding model)

        Returns:
            True if embedding dimensions match expected value

        Raises:
            ValueError: If embedding dimensions don't match expected value

        Notes:
            Assumes embeddings are stored as float32 arrays (4 bytes per dimension).
            This validation prevents inconsistent vector data from being stored.

        Examples:
            >>> manager._validate_embedding_dimensions(b'\\x00' * 512, 128)  # 512 bytes / 4 = 128 dims
            True

            >>> manager._validate_embedding_dimensions(b'\\x00' * 256, 128)  # 256 bytes / 4 = 64 dims
            Traceback (most recent call last):
                ...
            ValueError: Embedding dimension mismatch: expected 128, got 64
        """
        if not embedding:
            raise ValueError("Embedding cannot be empty")

        # Calculate actual dimensions (assuming float32 = 4 bytes per dimension)
        actual_dims = len(embedding) // 4

        if actual_dims != expected_dims:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected_dims}, got {actual_dims}. "
                f"Embedding size: {len(embedding)} bytes"
            )

        return True

    def add_reference_node(
        self,
        title: str,
        definition: str,
        source: str,
        external_id: str,
        attributes: Dict[str, Any] | None = None,
        title_embedding: bytes | None = None,
        definition_embedding: bytes | None = None,
        embedding_dims: int = 1536  # Default for text-embedding-3-small
    ) -> ReferenceNode:
        """
        Add a new reference node to the database.

        Args:
            title: Human-readable title
            definition: Detailed description or definition
            source: Source identifier (e.g., 'schema.org')
            external_id: Source-specific identifier
            attributes: Optional dictionary of additional metadata
            title_embedding: Optional embedding vector for title
            definition_embedding: Optional embedding vector for definition
            embedding_dims: Expected embedding dimensions (default: 1536 for text-embedding-3-small)

        Returns:
            Created ReferenceNode instance

        Raises:
            ValueError: If embedding dimensions don't match expected value
            IntegrityError: If (source, external_id) already exists

        Examples:
            >>> node = manager.add_reference_node(
            ...     title="Person",
            ...     definition="A human being",
            ...     source="schema.org",
            ...     external_id="Person"
            ... )
        """
        # Validate embeddings if provided
        if title_embedding:
            self._validate_embedding_dimensions(title_embedding, embedding_dims)
        if definition_embedding:
            self._validate_embedding_dimensions(definition_embedding, embedding_dims)

        # Create node with transaction
        with self.session.begin():
            node = ReferenceNode(
                id=str(uuid4()),
                title=title,
                definition=definition,
                source=source,
                external_id=external_id,
                attributes=str(attributes) if attributes else None,
                title_embedding=title_embedding,
                definition_embedding=definition_embedding,
                created_at=date.today().isoformat(),
                updated_at=date.today().isoformat()
            )
            self.session.add(node)

        logger.debug(
            f"Added reference node: source={source}, external_id={external_id}, title={title}"
        )
        return node

    def add_reference_link(
        self,
        subject_node: str,
        predicate: str,
        object_node: str,
        attributes: Dict[str, Any] | None = None
    ) -> ReferenceLink:
        """
        Add a new reference link to the database.

        Args:
            subject_node: UUID of the subject reference node
            predicate: Relationship type (e.g., 'subClassOf')
            object_node: UUID of the object reference node
            attributes: Optional dictionary of additional metadata

        Returns:
            Created ReferenceLink instance

        Raises:
            IntegrityError: If referenced nodes don't exist

        Examples:
            >>> link = manager.add_reference_link(
            ...     subject_node=person_node.id,
            ...     predicate="subClassOf",
            ...     object_node=thing_node.id
            ... )
        """
        # Create link with transaction
        with self.session.begin():
            link = ReferenceLink(
                id=str(uuid4()),
                subject_node=subject_node,
                predicate=predicate,
                object_node=object_node,
                attributes=str(attributes) if attributes else None,
                created_at=date.today().isoformat(),
                updated_at=date.today().isoformat()
            )
            self.session.add(link)

        logger.debug(
            f"Added reference link: {subject_node} --{predicate}--> {object_node}"
        )
        return link

    def get_reference_node(self, node_id: str) -> ReferenceNode | None:
        """
        Retrieve a reference node by ID.

        Args:
            node_id: UUID of the reference node

        Returns:
            ReferenceNode instance or None if not found

        Examples:
            >>> node = manager.get_reference_node("550e8400-e29b-41d4-a716-446655440000")
        """
        return self.session.query(ReferenceNode).filter_by(id=node_id).first()

    def get_reference_node_by_source(self, source: str, external_id: str) -> ReferenceNode | None:
        """
        Retrieve a reference node by source and external ID.

        Args:
            source: Source identifier
            external_id: Source-specific identifier

        Returns:
            ReferenceNode instance or None if not found

        Examples:
            >>> node = manager.get_reference_node_by_source("schema.org", "Person")
        """
        return self.session.query(ReferenceNode).filter_by(
            source=source,
            external_id=external_id
        ).first()

    def list_reference_nodes(
        self,
        source: str | None = None,
        limit: int | None = None
    ) -> List[ReferenceNode]:
        """
        List reference nodes, optionally filtered by source.

        Args:
            source: Optional source filter
            limit: Optional limit on number of results

        Returns:
            List of ReferenceNode instances

        Examples:
            >>> nodes = manager.list_reference_nodes(source="schema.org", limit=100)
        """
        query = self.session.query(ReferenceNode)

        if source:
            query = query.filter_by(source=source)

        if limit:
            query = query.limit(limit)

        return query.all()
