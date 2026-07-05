"""
SQLite connection management and session factory creation.

This module provides factories for creating SQLAlchemy engines and sessions
for both local.db and operations.db databases.

Key design decisions:
- File-based SQLite uses SQLAlchemy's default QueuePool so each thread/session
  gets its own connection. The FastAPI app runs synchronous DB code on a thread
  pool (run_sync_in_executor), so concurrent queries must not share a single
  SQLite connection (SQLite connections are not safe for concurrent statement
  execution). WAL journaling + a busy_timeout are enabled per-connection so
  concurrent reads and writes are safe.
- In-memory SQLite (":memory:" / "mode=memory") uses StaticPool, which is
  required so every connection sees the same in-memory database instead of a
  fresh empty one. WAL is invalid for in-memory databases and is not applied.
- check_same_thread=False for multi-threaded server environments
- expire_on_commit=False to reduce unnecessary re-queries
- Separate engines for local.db and operations.db to support independent lifecycle
"""

from typing import Any, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Type alias for SQLAlchemy Engine (mypy compatibility)
Engine = Any  # type: ignore[misc]


def _is_memory_url(database_url: str) -> bool:
    """
    Return True if the SQLite URL refers to an in-memory database.

    In-memory databases are identified by the ":memory:" path, a
    "mode=memory" query parameter (shared-cache URI form), or the bare
    "sqlite://" / "sqlite:///" empty-path form (SQLAlchemy's default
    in-memory database when no path is given).
    """
    lowered = database_url.lower()
    if ":memory:" in lowered or "mode=memory" in lowered:
        return True
    # Bare empty-path forms ("sqlite://", "sqlite:///") are in-memory too.
    return lowered in ("sqlite://", "sqlite:///")


def _create_sqlite_engine(database_url: str) -> Engine:
    """
    Create a SQLite engine tuned for the database's storage type.

    File-based databases use the default QueuePool so each thread/session gets
    its own connection, and every new connection is configured with WAL
    journaling and a busy_timeout for safe concurrent access.

    In-memory databases use StaticPool so all connections share the same
    underlying database; WAL is not applied (it is invalid for :memory:).

    Args:
        database_url: SQLite connection string.

    Returns:
        A configured SQLAlchemy Engine.
    """
    if _is_memory_url(database_url):
        return create_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,  # Set to True for SQL debugging
        )

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=False,  # Set to True for SQL debugging
    )

    @event.listens_for(engine, "connect")
    def _configure_file_connection(dbapi_connection: Any, connection_record: Any) -> None:
        """Enable WAL journaling and a busy_timeout on every new connection."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

    return engine


def create_local_db_engine(database_url: str = "sqlite:///./local.db") -> Engine:
    """
    Create an SQLAlchemy engine for the primary local.db database.

    Args:
        database_url: SQLite connection string. Defaults to sqlite:///./local.db

    Returns:
        SQLAlchemy Engine configured for SQLite with appropriate defaults
    """
    return _create_sqlite_engine(database_url)


def create_operations_db_engine(
    database_url: str = "sqlite:///./operations.db",
) -> Engine:
    """
    Create an SQLAlchemy engine for the operations.db database.

    Used for pipeline configurations, execution logs, and background tasks.

    Args:
        database_url: SQLite connection string. Defaults to sqlite:///./operations.db

    Returns:
        SQLAlchemy Engine configured for SQLite with appropriate defaults
    """
    return _create_sqlite_engine(database_url)


def create_session_factory(engine: Engine) -> sessionmaker:
    """
    Create a SQLAlchemy session factory for the given engine.

    Sessions created from this factory will not expire ORM objects after commit,
    reducing unnecessary re-queries.

    Args:
        engine: SQLAlchemy Engine to bind the factory to

    Returns:
        SQLAlchemy sessionmaker configured for optimal defaults
    """
    return sessionmaker(
        bind=engine,
        expire_on_commit=False,  # Prevents ORM objects from expiring after commit
    )


def create_session(session_factory: sessionmaker) -> Session:
    """
    Create a new database session.

    Args:
        session_factory: sessionmaker instance from create_session_factory()

    Returns:
        A new SQLAlchemy Session instance
    """
    return session_factory()


class DatabaseManager:
    """
    Centralized manager for database connections and lifecycle.

    Handles creation, initialization, and cleanup of both local.db and operations.db.
    Provides dependency injection hooks for FastAPI.

    Usage in app.py:
        db_manager = DatabaseManager()
        db_manager.initialize(config)
        # In dependency injection:
        def get_local_session():
            session = db_manager.get_local_session()
            try:
                yield session
            finally:
                session.close()
    """

    def __init__(self) -> None:
        """Initialize the database manager with no engines yet."""
        self._local_engine: Optional[Engine] = None
        self._operations_engine: Optional[Engine] = None
        self._local_session_factory: Optional[sessionmaker] = None
        self._operations_session_factory: Optional[sessionmaker] = None

    def initialize(
        self,
        local_db_url: str = "sqlite:///./local.db",
        operations_db_url: str = "sqlite:///./operations.db",
    ) -> None:
        """
        Initialize database connections and session factories.

        Called during FastAPI lifespan startup.

        Args:
            local_db_url: Connection string for local.db
            operations_db_url: Connection string for operations.db
        """
        self._local_engine = create_local_db_engine(local_db_url)
        self._operations_engine = create_operations_db_engine(operations_db_url)
        self._local_session_factory = create_session_factory(self._local_engine)
        self._operations_session_factory = create_session_factory(self._operations_engine)

    def get_local_engine(self) -> Engine:
        """Return the local.db engine. Must call initialize() first."""
        if self._local_engine is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._local_engine

    def get_operations_engine(self) -> Engine:
        """Return the operations.db engine. Must call initialize() first."""
        if self._operations_engine is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._operations_engine

    def get_local_session(self) -> Session:
        """Create a new session for local.db. Must call initialize() first."""
        if self._local_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._local_session_factory()

    def get_local_session_factory(self) -> sessionmaker:
        """Return the local.db session factory. Must call initialize() first."""
        if self._local_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._local_session_factory

    def get_operations_session(self) -> Session:
        """Create a new session for operations.db. Must call initialize() first."""
        if self._operations_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._operations_session_factory()

    def get_operations_session_factory(self) -> sessionmaker:
        """Return the operations.db session factory. Must call initialize() first."""
        if self._operations_session_factory is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._operations_session_factory

    def dispose(self) -> None:
        """
        Close all connections and dispose of connection pools.

        Called during FastAPI lifespan shutdown.
        """
        if self._local_engine is not None:
            self._local_engine.dispose()
        if self._operations_engine is not None:
            self._operations_engine.dispose()

    def create_all_tables(self) -> None:
        """
        Create all tables in local.db and operations.db if they don't exist.

        Useful for development; production should use Alembic migrations.

        Requires that SQLAlchemy ORM models have been defined and imported.
        """
        if self._local_engine is None or self._operations_engine is None:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")

        # Import models to ensure they're registered with Base
        from adapters.persistence.sqlite.models import Base as LocalBase

        LocalBase.metadata.create_all(self._local_engine)

        # Import operations models and create tables
        from adapters.persistence.sqlite.operations.models import OperationsBase

        OperationsBase.metadata.create_all(self._operations_engine)
