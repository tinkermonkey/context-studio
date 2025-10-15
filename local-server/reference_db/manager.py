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
from typing import Optional, List, Dict, Any, Literal
from uuid import uuid4
import sqlite3

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from database.utils import get_engine, init_db
from reference_db.models import Base, ReferenceNode, ReferenceLink
from reference_db.config import ReferenceConfig, REFERENCE_SCHEMA_VERSION
from embeddings.generate_embeddings import generate_embedding

# Configure logging
logger = logging.getLogger(__name__)

# Constants
EMBEDDING_DIMENSION = 768  # Dimension for sentence-transformers/all-MiniLM-L6-v2

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

    def get_connection(self):
        """
        Get a raw database connection for direct SQL operations.

        This method returns a SQLite connection object that can be used for
        direct database operations outside of the SQLAlchemy ORM.

        Returns:
            sqlite3.Connection: Raw SQLite database connection

        Examples:
            >>> conn = manager.get_connection()
            >>> cursor = conn.cursor()
            >>> cursor.execute("SELECT * FROM reference_nodes LIMIT 1")
            >>> conn.close()

        Note:
            The caller is responsible for closing the connection when done.
        """
        import sqlite3
        return sqlite3.connect(self.db_path)

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
                f"Schema version mismatch detected. Expected schema={REFERENCE_SCHEMA_VERSION}"
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

        This method checks the schema version to determine if the database structure
        is compatible with the current code.

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
                    text("SELECT schema_version FROM schema_version LIMIT 1")
                ).first()

                if result:
                    schema_ver = result[0]
                    logger.info(f"Found schema version: {schema_ver}")
                    return schema_ver == REFERENCE_SCHEMA_VERSION
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
                        created_at TEXT NOT NULL
                    )
                """))

                # Insert current schema version
                conn.execute(
                    text("""
                        INSERT INTO schema_version (schema_version, created_at)
                        VALUES (:schema_ver, :created_at)
                    """),
                    {
                        "schema_ver": REFERENCE_SCHEMA_VERSION,
                        "created_at": date.today().isoformat()
                    }
                )

            logger.info(
                f"Database rebuild complete. Schema version: {REFERENCE_SCHEMA_VERSION}"
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
        embedding_dims: int = EMBEDDING_DIMENSION  # Use constant from config
    ) -> ReferenceNode:
        """
        Add a new reference node to the database.

        Embeddings are automatically generated using the existing embeddings module
        if not provided. The embeddings use sentence-transformers/all-MiniLM-L6-v2
        model with 768 dimensions.

        Args:
            title: Human-readable title
            definition: Detailed description or definition
            source: Source identifier (e.g., 'schema.org')
            external_id: Source-specific identifier
            attributes: Optional dictionary of additional metadata
            title_embedding: Optional embedding vector for title (auto-generated if None)
            definition_embedding: Optional embedding vector for definition (auto-generated if None)
            embedding_dims: Expected embedding dimensions (default: 768 for all-MiniLM-L6-v2)

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
        # Auto-generate embeddings if not provided
        if title_embedding is None:
            logger.debug(f"Generating embedding for title: {title}")
            title_embedding = generate_embedding(title)
        else:
            self._validate_embedding_dimensions(title_embedding, embedding_dims)
            
        if definition_embedding is None:
            logger.debug(f"Generating embedding for definition")
            definition_embedding = generate_embedding(definition)
        else:
            self._validate_embedding_dimensions(definition_embedding, embedding_dims)

        # Create node with transaction
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
        self.session.commit()

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
        self.session.commit()

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

    def _distance_to_similarity(self, distance: float) -> float:
        """
        Convert vector distance to cosine similarity.

        For cosine distance, the relationship is: similarity = 1 - distance

        Edge cases:
        - distance 0.0 → similarity 1.0 (identical vectors)
        - distance 1.0 → similarity 0.0 (orthogonal vectors)
        - distance 2.0 → similarity -1.0 (opposite vectors)

        Args:
            distance: Vector distance from sqlite-vec (0.0 to 2.0 for cosine)

        Returns:
            Cosine similarity score (-1.0 to 1.0)

        Examples:
            >>> manager._distance_to_similarity(0.0)
            1.0
            >>> manager._distance_to_similarity(1.0)
            0.0
            >>> manager._distance_to_similarity(2.0)
            -1.0
        """
        return 1.0 - distance

    def search_by_similarity(
        self,
        query_text: str,
        source: str | None = None,
        node_type: str | None = None,
        limit: int = 20,
        threshold: float = 0.7,
        embedding_generator = None
    ) -> List[tuple[ReferenceNode, float]]:
        """
        Search for reference nodes by semantic similarity.

        Uses the existing embeddings module (sentence-transformers/all-MiniLM-L6-v2)
        to generate query embeddings by default.

        This method:
        1. Generates embeddings for the query text using the embeddings module
        2. Performs vector search using sqlite-vec
        3. Computes max(title_similarity, definition_similarity) for ranking
        4. Filters results by similarity threshold
        5. Returns nodes ordered by similarity (descending)

        Args:
            query_text: Text query to search for
            source: Optional source filter (e.g., 'schema.org')
            node_type: Optional node type filter (from attributes)
            limit: Maximum number of results (default: 20, max: 10000)
            threshold: Minimum similarity threshold (-1.0 to 1.0, default: 0.7)
            embedding_generator: Optional custom function that takes text and returns embedding bytes.
                               If None, uses the default embeddings.generate_embedding function.

        Returns:
            List of (ReferenceNode, similarity_score) tuples ordered by similarity descending

        Raises:
            ValueError: If inputs are invalid (empty query_text, invalid threshold/limit)
            sqlite3.Error: If vector search database operation fails
            RuntimeError: If vector search fails for other reasons

        Examples:
            >>> results = manager.search_by_similarity(
            ...     "person entity",
            ...     source="schema.org",
            ...     limit=10,
            ...     threshold=0.8
            ... )
            >>> for node, score in results:
            ...     print(f"{node.title}: {score:.3f}")
        """
        # Input validation
        if not query_text or not query_text.strip():
            raise ValueError("query_text cannot be empty")

        # Use default embedding generator if not provided
        if embedding_generator is None:
            embedding_generator = generate_embedding

        if not -1.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between -1.0 and 1.0, got {threshold}")

        if not isinstance(limit, int) or limit < 1:
            raise ValueError(f"limit must be a positive integer, got {limit}")

        if limit > 10000:
            raise ValueError(f"limit must not exceed 10000, got {limit}")

        try:
            # Generate embeddings for the query
            query_embedding = embedding_generator(query_text)

            if not query_embedding or len(query_embedding) == 0:
                raise ValueError("embedding_generator returned empty embedding")

            # Convert embedding to the format expected by sqlite-vec
            import numpy as np
            if isinstance(query_embedding, bytes):
                query_vec = np.frombuffer(query_embedding, dtype=np.float32)
            else:
                query_vec = np.array(query_embedding, dtype=np.float32)

            # Serialize to JSON array format for sqlite-vec
            import json
            query_vec_json = json.dumps(query_vec.tolist())

            # Build the vector search query using parameterized SQL to prevent injection
            # We compute similarity as (1.0 - cosine_distance) for both title and definition
            # and take the maximum similarity value for ranking
            sql_query = """
            WITH similarities AS (
                SELECT
                    rn.id,
                    rn.title,
                    rn.definition,
                    rn.source,
                    rn.external_id,
                    rn.attributes,
                    rn.created_at,
                    rn.updated_at,
                    CASE
                        -- Both embeddings present: compute max similarity
                        WHEN rn.title_embedding IS NOT NULL AND rn.definition_embedding IS NOT NULL THEN
                            MAX(
                                (1.0 - vec_distance_cosine(rn.title_embedding, :query_vec)),
                                (1.0 - vec_distance_cosine(rn.definition_embedding, :query_vec))
                            )
                        -- Only title embedding: use title similarity
                        WHEN rn.title_embedding IS NOT NULL THEN
                            (1.0 - vec_distance_cosine(rn.title_embedding, :query_vec))
                        -- Only definition embedding: use definition similarity
                        WHEN rn.definition_embedding IS NOT NULL THEN
                            (1.0 - vec_distance_cosine(rn.definition_embedding, :query_vec))
                        -- No embeddings: zero similarity (filtered out by HAVING clause)
                        ELSE 0.0
                    END AS max_similarity
                FROM reference_nodes rn
                WHERE rn.title_embedding IS NOT NULL OR rn.definition_embedding IS NOT NULL
            )
            SELECT * FROM similarities
            WHERE max_similarity >= :threshold
            """

            # Add source filter if provided (using parameterized query)
            if source:
                sql_query += " AND source = :source"

            # Add node_type filter if provided (using parameterized query)
            if node_type:
                sql_query += " AND attributes LIKE :node_type_pattern"

            # Add ordering and limit
            sql_query += " ORDER BY max_similarity DESC LIMIT :limit"

            # Build parameters dictionary
            params = {
                'query_vec': query_vec_json,
                'threshold': threshold,
                'limit': limit
            }

            if source:
                params['source'] = source

            if node_type:
                params['node_type_pattern'] = f'%"@type": "{node_type}"%'

            # Execute the query with explicit connection management
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_query), params)

                # Convert results to (ReferenceNode, similarity) tuples
                results = []
                for row in result:
                    node = ReferenceNode(
                        id=row.id,
                        title=row.title,
                        definition=row.definition,
                        source=row.source,
                        external_id=row.external_id,
                        attributes=row.attributes,
                        title_embedding=None,  # Don't load embeddings in results
                        definition_embedding=None,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    similarity = float(row.max_similarity)
                    results.append((node, similarity))

            return results

        except ValueError:
            # Re-raise validation errors
            raise
        except sqlite3.Error as e:
            logger.error(f"Vector search database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise RuntimeError(f"Vector search failed: {e}") from e

    def get_node_links(
        self,
        node_id: str,
        direction: Literal["inbound", "outbound", "both"] = "both",
        predicate: str | None = None,
        limit: int | None = None
    ) -> List[ReferenceLink]:
        """
        Retrieve links connected to a reference node.

        Args:
            node_id: UUID of the reference node
            direction: Link direction - "inbound", "outbound", or "both" (default: "both")
            predicate: Optional predicate filter for exact match
            limit: Optional limit on number of results

        Returns:
            List of ReferenceLink instances ordered by created_at DESC

        Raises:
            ValueError: If direction is not one of "inbound", "outbound", "both"

        Examples:
            >>> # Get all links for a node
            >>> links = manager.get_node_links("550e8400-e29b-41d4-a716-446655440000")

            >>> # Get only outbound "subClassOf" links
            >>> links = manager.get_node_links(
            ...     "550e8400-e29b-41d4-a716-446655440000",
            ...     direction="outbound",
            ...     predicate="subClassOf"
            ... )
        """
        # Validate direction parameter
        if direction not in ["inbound", "outbound", "both"]:
            raise ValueError(f"Invalid direction: '{direction}'. Must be 'inbound', 'outbound', or 'both'")

        # Use explicit connection management
        with self.engine.connect() as conn:
            query = self.session.query(ReferenceLink)

            # Apply direction filter
            if direction == "inbound":
                query = query.filter(ReferenceLink.object_node == node_id)
            elif direction == "outbound":
                query = query.filter(ReferenceLink.subject_node == node_id)
            else:  # both
                query = query.filter(
                    (ReferenceLink.subject_node == node_id) |
                    (ReferenceLink.object_node == node_id)
                )

            # Apply predicate filter if provided
            if predicate:
                query = query.filter(ReferenceLink.predicate == predicate)

            # Order by created_at DESC
            query = query.order_by(ReferenceLink.created_at.desc())

            # Apply limit if provided
            if limit:
                query = query.limit(limit)

            return query.all()

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of the reference database.

        Returns dictionary with:
        - status: "healthy", "degraded", "missing", or "error"
        - node_count: Total number of reference nodes
        - vec_count: Number of nodes with embeddings
        - schema_version: Current database schema version
        - model_version: Embedding model version
        - last_import_at: Timestamp of last import (if available)
        - database_size: Size of database file in bytes
        - database_path: Path to database file
        - connection_healthy: Whether database connection is functional
        - remediation: Suggested action if status is not healthy

        The health status is determined as:
        - "healthy": node_count == vec_count and versions match
        - "degraded": vec_count mismatch or version mismatch detected
        - "missing": database file doesn't exist
        - "error": database operations failed

        Returns:
            Status dictionary with comprehensive database information

        Examples:
            >>> status = manager.get_status()
            >>> print(status['status'])  # "healthy"
            >>> print(status['node_count'])  # 1000
        """
        import os
        from datetime import datetime, UTC

        # Constants for version checking
        EXPECTED_SCHEMA_VERSION = REFERENCE_SCHEMA_VERSION

        status = {
            "status": "missing",
            "node_count": 0,
            "vec_count": 0,
            "schema_version": None,
            "last_import_at": None,
            "database_size": 0,
            "database_path": self.db_path,
            "connection_healthy": False,
            "checked_at": datetime.now(UTC).isoformat()
        }

        # Check if database file exists
        if not os.path.exists(self.db_path):
            status["remediation"] = "Database file does not exist. Run import pipeline to create it."
            logger.debug(f"Database file does not exist: {self.db_path}")
            return status

        # Get database file size
        try:
            status["database_size"] = os.path.getsize(self.db_path)
        except Exception as e:
            logger.warning(f"Could not get database size: {e}")
            status["status"] = "error"
            status["error"] = f"Unable to read database file: {str(e)}"
            status["remediation"] = "Check file system permissions and disk health."
            return status

        # Test database connection and query capabilities
        try:
            # Test connection pool health
            with self.engine.connect() as conn:
                # Simple query to verify connection
                conn.execute(text("SELECT 1")).scalar()
                status["connection_healthy"] = True
                logger.debug("Database connection verified")

                # Get schema version information
                try:
                    version_result = conn.execute(
                        text("SELECT schema_version, created_at FROM schema_version LIMIT 1")
                    ).first()

                    if version_result:
                        status["schema_version"] = version_result[0]
                        # Use created_at as a proxy for last import (can be improved)
                        status["last_import_at"] = version_result[1]
                except Exception as e:
                    logger.debug(f"Could not get schema version: {e}")
                    status["status"] = "degraded"
                    status["degraded_reason"] = "schema_version_table_missing"
                    status["remediation"] = "Run database migration to create schema_version table."

                # Get node count
                try:
                    node_count_result = conn.execute(
                        text("SELECT COUNT(*) FROM reference_nodes")
                    ).scalar()
                    status["node_count"] = int(node_count_result or 0)
                except Exception as e:
                    logger.warning(f"Could not get node count: {e}")
                    status["status"] = "error"
                    status["error"] = f"Unable to query reference_nodes: {str(e)}"
                    status["remediation"] = "Verify database schema integrity. May need to rebuild database."
                    return status

                # Get vector count (nodes with embeddings)
                try:
                    vec_count_result = conn.execute(
                        text("""
                            SELECT COUNT(*) FROM reference_nodes
                            WHERE title_embedding IS NOT NULL OR definition_embedding IS NOT NULL
                        """)
                    ).scalar()
                    status["vec_count"] = int(vec_count_result or 0)
                except Exception as e:
                    logger.warning(f"Could not get vector count: {e}")
                    status["vec_count"] = 0
                    status["status"] = "degraded"
                    status["degraded_reason"] = "vector_query_failed"
                    status["remediation"] = "Check sqlite-vec extension installation."
                    return status

                # Determine health status
                if status["node_count"] == 0:
                    status["status"] = "missing"
                    status["remediation"] = "No reference nodes found. Run import pipeline to populate database."
                elif status["node_count"] == status["vec_count"]:
                    # Check if versions match expected
                    if status["schema_version"] == EXPECTED_SCHEMA_VERSION:
                        status["status"] = "healthy"
                        logger.debug("Database status: healthy")
                    else:
                        status["status"] = "degraded"
                        status["degraded_reason"] = "schema_version_mismatch"
                        status["remediation"] = (
                            f"Schema version mismatch. Expected schema={EXPECTED_SCHEMA_VERSION}. "
                            f"Run migration or reimport."
                        )
                else:
                    status["status"] = "degraded"
                    status["degraded_reason"] = "embedding_count_mismatch"
                    embedding_pct = (status["vec_count"] / status["node_count"] * 100) if status["node_count"] > 0 else 0
                    status["embedding_coverage_pct"] = round(embedding_pct, 2)
                    status["remediation"] = (
                        f"Only {status['vec_count']}/{status['node_count']} nodes have embeddings "
                        f"({embedding_pct:.1f}%). Run import pipeline to sync vectors."
                    )

        except Exception as e:
            logger.error(f"Error getting database status: {e}", exc_info=True)
            status["status"] = "error"
            status["error"] = "Database connection or query failed"
            status["remediation"] = "Check database file integrity and connection pool. May need to restart application."
            status["connection_healthy"] = False

        return status
