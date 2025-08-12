"""Shared helper for triage scripts that need database setup with migrations."""
import sys
import os
import tempfile
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from app import create_app
from database.utils import get_engine, get_session_local, init_db
from database.migrations.migration_manager import MigrationManager


def create_test_app_with_migrations():
    """Create a test FastAPI app with a temporary database that has all migrations applied."""
    # Create temporary database
    test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
    database_url = f"sqlite:///{test_db_path}"
    
    try:
        # Initialize database with base schema
        engine = get_engine(database_url)
        session_local = get_session_local(engine)
        init_db(engine=engine)
        
        # Apply migrations to get vector tables
        migration_manager = MigrationManager(test_db_path)
        success = migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations to test database")
        
        # Create FastAPI app
        app = create_app(engine=engine, session_local=session_local)
        
        return app, test_db_fd, test_db_path, engine, session_local
    except Exception:
        # Cleanup on failure
        os.close(test_db_fd)
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
        raise


def cleanup_test_database(test_db_fd, test_db_path):
    """Clean up the temporary test database."""
    try:
        os.close(test_db_fd)
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    except Exception as e:
        print(f"Warning: Failed to cleanup test database: {e}")


def create_test_client(app):
    """Create a test client for the given app."""
    return TestClient(app)
