"""
Database test utilities for isolated testing.

This module provides utilities for creating isolated test databases,
managing database cleanup, and supporting both in-memory and file-based
test database configurations.
"""

import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional, List, Union
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from database.utils import (
    get_engine,
    get_session_local,
    init_db,
)
from database.migrations.migration_manager import MigrationManager


class TestDatabaseManager:
    """
    Manager for creating and managing isolated test databases.
    
    Provides methods for creating both in-memory and file-based test databases
    with complete isolation and automatic cleanup.
    """
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize test database manager.
        
        Args:
            temp_dir: Optional temporary directory path. If not provided,
                     a new temporary directory will be created.
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp())
        self.created_databases: List[Path] = []
        self.active_engines: List[Engine] = []
    
    def create_in_memory_database(self) -> Tuple[Engine, sessionmaker]:
        """
        Create an in-memory SQLite database for testing.
        
        In-memory databases are fastest and provide complete isolation,
        but data is lost when the connection closes.
        
        Returns:
            Tuple of (engine, session_local_factory)
        """
        db_url = "sqlite:///:memory:"
        engine = get_engine(db_url)
        session_local = get_session_local(engine)
        
        # Initialize database schema
        init_db(engine=engine)
        
        # Store reference for cleanup
        self.active_engines.append(engine)
        
        return engine, session_local
    
    def create_file_database(self, db_name: Optional[str] = None) -> Tuple[Engine, sessionmaker, Path]:
        """
        Create a file-based SQLite database for testing.
        
        File-based databases persist during the test and can be useful
        for debugging or tests that need to inspect database state.
        
        Args:
            db_name: Optional database filename. If not provided,
                    a unique name will be generated.
        
        Returns:
            Tuple of (engine, session_local_factory, db_path)
        """
        if db_name is None:
            db_name = f"test_db_{len(self.created_databases)}.db"
        
        db_path = self.temp_dir / db_name
        db_url = f"sqlite:///{db_path}"
        
        engine = get_engine(db_url)
        session_local = get_session_local(engine)
        
        # Initialize database schema
        init_db(engine=engine)
        
        # Store references for cleanup
        self.created_databases.append(db_path)
        self.active_engines.append(engine)
        
        return engine, session_local, db_path
    
    def create_migrated_database(self, db_name: Optional[str] = None) -> Tuple[Engine, sessionmaker, Path]:
        """
        Create a file-based database with all migrations applied.
        
        This creates a fully migrated database that matches the current
        schema, including vector tables and other migration-applied features.
        
        Args:
            db_name: Optional database filename
        
        Returns:
            Tuple of (engine, session_local_factory, db_path)
        """
        engine, session_local, db_path = self.create_file_database(db_name)
        
        # Apply migrations
        migration_manager = MigrationManager(str(db_path))
        success = migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError(f"Failed to apply migrations to test database: {db_path}")
        
        return engine, session_local, db_path
    
    def cleanup_database(self, db_path: Union[str, Path]) -> None:
        """
        Clean up a specific database file and related artifacts.
        
        Args:
            db_path: Path to database file to clean up
        """
        db_path = Path(db_path)
        
        # Remove from tracking
        if db_path in self.created_databases:
            self.created_databases.remove(db_path)
        
        # Clean up database files (including WAL and SHM files)
        for suffix in ["", "-wal", "-shm"]:
            file_path = Path(str(db_path) + suffix)
            if file_path.exists():
                try:
                    file_path.unlink()
                except (OSError, PermissionError):
                    # Handle cases where database might be locked
                    pass
    
    def cleanup_all(self) -> None:
        """Clean up all created databases and temporary resources."""
        # Close all engines
        for engine in self.active_engines:
            try:
                engine.dispose()
            except Exception:
                pass  # Engine might already be disposed
        
        self.active_engines.clear()
        
        # Clean up database files
        for db_path in self.created_databases.copy():
            self.cleanup_database(db_path)
        
        # Clean up temporary directory if we created it
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except (OSError, PermissionError):
                pass
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup_all()


@contextmanager
def isolated_database(db_type: str = "file", temp_dir: Optional[str] = None):
    """
    Context manager for creating isolated test databases.
    
    Args:
        db_type: Type of database to create ("memory" or "file")
        temp_dir: Optional temporary directory path
        
    Yields:
        Tuple of (engine, session_local_factory, [db_path])
        db_path is only returned for file-based databases
    """
    with TestDatabaseManager(temp_dir) as manager:
        if db_type == "memory":
            engine, session_local = manager.create_in_memory_database()
            yield engine, session_local
        elif db_type == "file":
            engine, session_local, db_path = manager.create_file_database()
            yield engine, session_local, db_path
        elif db_type == "migrated":
            engine, session_local, db_path = manager.create_migrated_database()
            yield engine, session_local, db_path
        else:
            raise ValueError(f"Unknown database type: {db_type}")


@contextmanager
def isolated_session(db_type: str = "memory", temp_dir: Optional[str] = None):
    """
    Context manager for creating isolated database sessions.
    
    Args:
        db_type: Type of database to create ("memory", "file", or "migrated")
        temp_dir: Optional temporary directory path
        
    Yields:
        SQLAlchemy Session: Isolated database session
    """
    with isolated_database(db_type, temp_dir) as db_result:
        if db_type == "memory":
            engine, session_local = db_result
        else:
            engine, session_local, _ = db_result
        
        session = session_local()
        try:
            yield session
        finally:
            session.close()


def clean_database_tables(session: Session, exclude_tables: Optional[List[str]] = None) -> None:
    """
    Clean all data from database tables while preserving schema.
    
    Args:
        session: SQLAlchemy session
        exclude_tables: Optional list of table names to exclude from cleaning
    """
    if exclude_tables is None:
        exclude_tables = ["migration_versions", "alembic_version"]
    
    try:
        # Get all table names
        tables_result = session.execute(
            text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
        ).fetchall()
        
        # Clean all data (preserve schema)
        session.execute(text("PRAGMA foreign_keys = OFF"))
        
        for (table_name,) in tables_result:
            if table_name not in exclude_tables:
                session.execute(text(f"DELETE FROM {table_name}"))
        
        session.execute(text("PRAGMA foreign_keys = ON"))
        session.commit()
        
    except Exception:
        session.rollback()
        raise


def verify_database_isolation(test_func):
    """
    Decorator to verify that a test doesn't create database files in the root directory.
    
    Args:
        test_func: Test function to wrap
        
    Returns:
        Wrapped test function that verifies isolation
    """
    def wrapper(*args, **kwargs):
        # Get current directory files before test
        current_dir = Path.cwd()
        before_files = set(current_dir.glob("*.db*"))
        
        try:
            # Run the test
            result = test_func(*args, **kwargs)
            
            # Check for new database files after test
            after_files = set(current_dir.glob("*.db*"))
            new_files = after_files - before_files
            
            if new_files:
                raise AssertionError(
                    f"Test created database files in root directory: {new_files}"
                )
            
            return result
            
        finally:
            # Clean up any accidentally created files
            after_files = set(current_dir.glob("*.db*"))
            new_files = after_files - before_files
            for file_path in new_files:
                try:
                    file_path.unlink()
                except (OSError, PermissionError):
                    pass
    
    return wrapper


# Convenience functions for common test patterns
def create_test_database_in_memory() -> Tuple[Engine, sessionmaker]:
    """Create an in-memory test database with schema."""
    with TestDatabaseManager() as manager:
        return manager.create_in_memory_database()


def create_test_database_with_migrations(temp_dir: Optional[str] = None) -> Tuple[Engine, sessionmaker, Path]:
    """Create a file-based test database with all migrations applied."""
    with TestDatabaseManager(temp_dir) as manager:
        return manager.create_migrated_database()