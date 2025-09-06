"""Shared test configuration and fixtures."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
from fastapi.testclient import TestClient
from app import create_app
from database.utils import get_engine, get_session_local, init_db
from database.migrations.migration_manager import MigrationManager
from sqlalchemy import text


def create_test_database_with_migrations():
    """Create a test database with all migrations applied."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
        db_url = f"sqlite:///{db_path}"
    
    try:
        # Initialize database with base schema
        engine = get_engine(db_url)
        session_local = get_session_local(engine)
        init_db(engine=engine)
        
        # Apply migrations to get vector tables
        migration_manager = MigrationManager(db_path)
        success = migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations to test database")
        
        return engine, session_local, db_path
    except Exception:
        # Cleanup on failure
        if os.path.exists(db_path):
            os.unlink(db_path)
        raise


@pytest.fixture(scope="session")
def shared_app():
    """Create shared app instance for the entire test session - reused across all tests."""
    engine, session_local, db_path = create_test_database_with_migrations()
    try:
        # Set the global engine state for testing
        from database.utils import set_current_engine_for_testing
        set_current_engine_for_testing(engine, session_local)
        
        app = create_app(engine=engine, session_local=session_local)
        yield app, engine, session_local
    finally:
        # Always cleanup the temporary database
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture(scope="session")
def shared_client(shared_app):
    """Create shared test client for the entire session - reused across all tests."""
    app, engine, session_local = shared_app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(shared_app):
    """Provide clean database session for each test function - auto-rollback."""
    app, engine, session_local = shared_app
    
    # Create a new session for this test
    session = session_local()
    
    try:
        yield session
    finally:
        # Always close the session first
        session.close()
        
        # Clean all tables for next test to ensure isolation
        cleanup_session = session_local()
        try:
            # Get all table names except migration tracking
            tables_result = cleanup_session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                AND name NOT IN ('migration_versions', 'alembic_version')
                ORDER BY name
            """)).fetchall()
            
            # Clear all data (preserve schema)
            cleanup_session.execute(text("PRAGMA foreign_keys = OFF"))
            for (table_name,) in tables_result:
                cleanup_session.execute(text(f"DELETE FROM {table_name}"))
            cleanup_session.execute(text("PRAGMA foreign_keys = ON"))
            cleanup_session.commit()
        except Exception:
            cleanup_session.rollback()
            raise
        finally:
            cleanup_session.close()


@pytest.fixture(scope="function") 
def clean_db_session(shared_app):
    """Provide clean database session that commits changes - use sparingly."""
    app, engine, session_local = shared_app
    
    # Create a new session for this test
    session = session_local()
    
    try:
        yield session
        # Commit any changes made during the test
        session.commit()
    except Exception:
        # Rollback on error
        session.rollback()
        raise
    finally:
        # Clean up the session
        session.close()
        
        # Clean all tables for next test (more thorough than rollback)
        cleanup_session = session_local()
        try:
            # Get all table names
            tables_result = cleanup_session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)).fetchall()
            
            # Clear all data (preserve schema)
            cleanup_session.execute(text("PRAGMA foreign_keys = OFF"))
            for (table_name,) in tables_result:
                if table_name not in ['migration_versions', 'alembic_version']:  # Preserve migration state
                    cleanup_session.execute(text(f"DELETE FROM {table_name}"))
            cleanup_session.execute(text("PRAGMA foreign_keys = ON"))
            cleanup_session.commit()
        finally:
            cleanup_session.close()


# Legacy fixtures for backwards compatibility - these now use the shared app
@pytest.fixture(scope="function")
def test_app(shared_app):
    """Legacy fixture name - now returns shared app for backwards compatibility."""
    app, engine, session_local = shared_app
    return app


@pytest.fixture(scope="function") 
def client(shared_client):
    """Legacy fixture name - now returns shared client for backwards compatibility."""
    return shared_client
