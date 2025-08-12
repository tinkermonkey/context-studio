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


@pytest.fixture(scope="function")
def test_app():
    """Create test app with migrated database - new database per test."""
    engine, session_local, db_path = create_test_database_with_migrations()
    try:
        app = create_app(engine=engine, session_local=session_local)
        yield app
    finally:
        # Always cleanup the temporary database
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_app):
    """Create test client - depends on test_app fixture."""
    with TestClient(test_app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(test_app):
    """Provide direct database session for tests that need it."""
    from database.utils import get_current_session_local
    session_local = get_current_session_local()
    if not session_local:
        pytest.skip("No active session local available")
    
    session = session_local()
    try:
        yield session
    finally:
        session.close()
