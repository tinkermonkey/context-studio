import sqlite3
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from database.models import Base
from utils.logger import get_logger
import sqlite_vec
import os

logger = get_logger(__name__)

# Global state for current dataset
_current_engine = None
_current_session_local = None
_dataset_manager = None

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

    url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./local.db')
    if use_static_pool and url.startswith("sqlite:///:memory:"):
        from sqlalchemy.pool import StaticPool
        return create_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool
        )
    return create_engine(url, connect_args=connect_args)

def get_session_local(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def init_db(engine=None, database_url=None, connect_args=None):
    logger.info("init_db retrieving engine...")
    if engine is None:
        engine = get_engine(database_url=database_url, connect_args=connect_args)

    @event.listens_for(engine, "connect")
    def receive_connect(connection, _):
        try:
            logger.info("Enabling SQLite extensions...")
            connection.enable_load_extension(True)
            sqlite_vec.load(connection)
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load SQLite vec extension: {e}")
            raise e
        finally:
            # Disable extension loading after use
            logger.info("Extension loaded successfully, disabling further loading.")
            connection.enable_load_extension(False)

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
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="No active dataset")
    
    db = session_local()
    try:
        yield db
    finally:
        db.close()
