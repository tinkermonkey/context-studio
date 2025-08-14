import os
import sqlite3
import sqlite_vec
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from utils.logger import get_logger
from sqlalchemy.pool import StaticPool


logger = get_logger(__name__)

# Global state for current dataset
_current_engine = None
_current_session_local = None
_dataset_manager = None

# Global tracking of loaded extensions to prevent duplicates
_loaded_connections = set()

# Track engines that have been initialized to prevent duplicate listeners
_initialized_engines = set()


def get_dataset_manager():
    """Get the global dataset manager instance."""
    global _dataset_manager
    if _dataset_manager is None:
        from dataset.manager import DatasetManager
        _dataset_manager = DatasetManager()
    return _dataset_manager


def switch_active_database(dataset_id: str) -> bool:
    """Switch the active database connection."""
    global _current_engine, _current_session_local

    dataset_manager = get_dataset_manager()
    if dataset_manager.switch_dataset(dataset_id):
        _current_engine = dataset_manager.active_engine
        _current_session_local = dataset_manager.active_session_local
        return True
    return False


def get_current_engine():
    """Get the current active engine."""
    global _current_engine
    if _current_engine is None:
        # Initialize with default dataset
        dataset_manager = get_dataset_manager()
        _current_engine = dataset_manager.active_engine
    return _current_engine


def get_current_session_local():
    """Get the current active session local."""
    global _current_session_local
    if _current_session_local is None:
        # Initialize with default dataset
        dataset_manager = get_dataset_manager()
        _current_session_local = dataset_manager.active_session_local
    return _current_session_local


def get_engine(database_url=None, use_static_pool=False, connect_args={"check_same_thread": False}):
    logger.info("SQLite Version: %s", sqlite3.sqlite_version)
    logger.info("SQLite File: %s", sqlite3.__file__)

    if connect_args is None:
        connect_args = {"check_same_thread": False}
    else:
        logger.info("Using custom connect_args: %s", connect_args)

    url = database_url or os.getenv("DATABASE_URL", "sqlite:///./local.db")
    if use_static_pool and url.startswith("sqlite:///:memory:"):
        return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
    return create_engine(url, connect_args=connect_args)


def get_session_local(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def cleanup_database_resources():
    """Clean up all database resources and event listeners."""
    global _current_engine, _current_session_local, _loaded_connections, _initialized_engines

    logger.info("Cleaning up database resources...")

    # Clear connection tracking
    _loaded_connections.clear()

    # Clear engine tracking (event listeners will be cleaned up automatically when engines are disposed)
    _initialized_engines.clear()

    # Dispose of current engine
    if _current_engine:
        try:
            _current_engine.dispose()
            logger.info("Disposed current engine")
        except Exception as e:
            logger.warning(f"Error disposing engine: {e}")
        _current_engine = None

    _current_session_local = None
    logger.info("Database resources cleanup complete")


def init_db(engine=None, database_url=None, connect_args=None):
    logger.info("init_db retrieving engine...")
    if engine is None:
        engine = get_engine(database_url=database_url, connect_args=connect_args)

    # Check if this engine already has our listeners to avoid duplicates
    engine_id = id(engine)
    if engine_id in _initialized_engines:
        logger.debug(f"Engine {engine_id} already has event listeners, skipping")
        return engine

    def receive_connect(connection, connection_record):
        # Use connection ID to track if extension is already loaded
        connection_id = id(connection)
        if connection_id in _loaded_connections:
            logger.debug(f"Extension already loaded for connection {connection_id}")
            return

        try:
            logger.info("Enabling SQLite extensions...")
            connection.enable_load_extension(True)
            sqlite_vec.load(connection)
            _loaded_connections.add(connection_id)
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load SQLite vec extension: {e}")
            raise e
        finally:
            # Disable extension loading after use
            logger.info("Extension loaded successfully, disabling further loading.")
            connection.enable_load_extension(False)

    def receive_close(connection, connection_record):
        # Clean up tracking when connection is closed
        connection_id = id(connection)
        _loaded_connections.discard(connection_id)
        logger.debug(f"Cleaned up extension tracking for connection {connection_id}")

    # Attach event listeners
    event.listen(engine, "connect", receive_connect)
    event.listen(engine, "close", receive_close)

    # Track this engine as initialized
    _initialized_engines.add(engine_id)

    logger.debug(f"Added event listeners to engine {engine_id}")

    # Do not create tables here; rely on migration manager for schema creation
    logger.info("init_db complete (no tables created, use migration manager for schema)")
    return engine


def get_db(SessionLocal=None):
    """Get database session for dependency injection."""
    if SessionLocal is None:
        # Use current dataset's session local
        SessionLocal = get_current_session_local()
        if SessionLocal is None:
            raise RuntimeError("No active dataset or session available")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_for_current_dataset():
    """Get database session for currently active dataset."""
    session_local = get_current_session_local()
    if not session_local:
        raise HTTPException(status_code=500, detail="No active dataset")

    db = session_local()
    try:
        yield db
    finally:
        db.close()
