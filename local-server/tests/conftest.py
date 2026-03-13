"""Shared test configuration and fixtures."""

import asyncio
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from config import (  # noqa: E402
    notify_configuration_change,
    Settings,
)
from database.migrations.migration_manager import MigrationManager  # noqa: E402, E501
from database.utils import (  # noqa: E402
    get_engine,
    get_session_local,
    init_db,
    get_database_manager,
    cleanup_database_resources,
    set_current_engine_for_testing,
)
from dataset.manager import DatasetManager  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from services.service_factory import (  # noqa: E402
    ServiceFactory,
    set_service_factory,
)
from tests.test_config import TestConfigurationManager  # noqa: E402
from utils.event_processor import (
    get_global_event_processor,
    set_global_event_processor,
)  # noqa: E402, E501


def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip utility classes that start with Test."""
    # No need to modify items, just hook for future use
    pass


def pytest_ignore_collect(collection_path, config):
    """Ignore collection from utility files that have non-test Test* classes."""  # noqa: E501
    # Get the string representation of the path
    path_str = str(collection_path)

    # List of utility files that should not be collected
    utility_files = [
        "test_config.py",
        "test_db_utils.py",
        "test_environment.py",
    ]  # noqa: E501

    # Check if this is one of our utility files (not in subdirectories)
    for util_file in utility_files:
        if path_str.endswith(f"/tests/{util_file}") or path_str.endswith(
            f"\\tests\\{util_file}"
        ):
            return True

    return False


def create_test_database_with_migrations():
    """Create a test database with all migrations applied."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
        db_url = f"sqlite:///{db_path}"

    try:
        # Initialize database with base schema
        # Use NullPool with check_same_thread=False for testing
        # Use default isolation level (not autocommit) for proper transaction handling
        engine = get_engine(
            db_url,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
                # Note: Don't set isolation_level here - let SQLAlchemy handle it
            },
        )

        # Enable WAL mode to improve concurrency and visibility
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()

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


@pytest.fixture(scope="session", autouse=True)
def global_test_isolation():
    """
    Provide global test isolation for the entire test session.

    This fixture runs automatically for all tests and prevents any modification
    of the global config.json file by monkey-patching the ConfigurationManager
    to prevent file writes during testing.
    """
    # Create temporary directory for test session
    temp_dir = Path(tempfile.mkdtemp(prefix="test_session_"))

    # Create test configuration manager
    config_manager = TestConfigurationManager(str(temp_dir))
    test_settings = config_manager.get_test_settings()

    # Comprehensive monkey-patching to prevent config.json pollution
    import config as config_module

    # Store original methods
    original_get_config_manager = config_module.get_config_manager
    original_ConfigurationManager = config_module.ConfigurationManager
    original_config_manager_instance = None

    # Create a mock ConfigurationManager class that prevents file writes
    class MockConfigurationManager:
        def __init__(self, config_file: str = "./config.json"):
            self.config_file = config_file  # Store but don't use
            self.settings = test_settings  # Use test settings instead
            self._lock = None

        def load(self):
            return self.settings

        def save(self):
            # Prevent any file writes during tests
            return True

        def get(self, path: str):
            # Delegate to our test configuration manager if needed
            parts = path.split(".")
            current = self.settings.model_dump()
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Configuration path not found: {path}")
            return current

        def set(self, path: str, value):
            # Actually update the values in test settings for proper testing
            try:
                parts = path.split(".")
                obj = self.settings

                # Navigate to parent object
                for part in parts[:-1]:
                    if hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        raise KeyError(
                            f"Configuration path not found: {'.'.join(parts[:-1])}"  # noqa: E501
                        )

                # Set the final value
                final_key = parts[-1]
                if hasattr(obj, final_key):
                    setattr(obj, final_key, value)

                    # Trigger notifications like the real ConfigurationManager does  # noqa: E501
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(notify_configuration_change(path))
                    except RuntimeError:
                        # No event loop available, skip notifications
                        pass

                    return True
                else:
                    raise KeyError(f"Configuration key not found: {final_key}")
            except Exception:
                return False

        def validate(self):
            # Add the validate method that the API endpoint needs
            errors = []
            try:
                # Re-create settings object to trigger validation
                Settings(**self.settings.model_dump())
            except ValidationError as e:
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error["loc"])
                    errors.append(f"{field}: {error['msg']}")
            return errors

        def update(self, updates: dict):
            # Prevent modifications during tests
            return True

    # Mock the get_config_manager function
    def get_test_config_manager():
        nonlocal original_config_manager_instance
        if original_config_manager_instance is None:
            original_config_manager_instance = MockConfigurationManager()
        return original_config_manager_instance

    # Apply monkey patches
    config_module.get_config_manager = get_test_config_manager
    config_module.ConfigurationManager = MockConfigurationManager

    # Also patch the global instance if it exists
    if hasattr(config_module, "_config_manager"):
        config_module._config_manager = None  # Force recreation with our mock

    # Add dataset manager isolation
    import database.utils as db_utils

    original_get_dataset_manager = db_utils.get_dataset_manager

    def get_test_dataset_manager():
        return DatasetManager(
            datasets_config_path=str(temp_dir / "test_datasets.json"),
            datasets_directory=str(temp_dir / "test_datasets"),
        )

    # Apply dataset manager monkey patch
    db_utils.get_dataset_manager = get_test_dataset_manager

    # Reset the global dataset manager instance to force recreation with test settings  # noqa: E501
    if hasattr(db_utils, "_dataset_manager"):
        db_utils._dataset_manager = None

    try:
        yield
    finally:
        # Restore original classes and functions
        config_module.get_config_manager = original_get_config_manager
        config_module.ConfigurationManager = original_ConfigurationManager
        config_module._config_manager = None  # Reset global instance

        # Restore dataset manager
        db_utils.get_dataset_manager = original_get_dataset_manager
        db_utils._dataset_manager = None  # Reset global instance

        # Enhanced cleanup and verification
        config_manager.cleanup()

        # Verify test isolation - check that critical files haven't been polluted  # noqa: E501
        if os.path.exists("./config.json") and os.path.exists(
            "./datasets.json"
        ):  # noqa: E501
            # Verify config.json and datasets.json were not modified by tests
            # This is critical for data safety
            try:
                result = subprocess.run(
                    [
                        "git",
                        "status",
                        "--porcelain",
                        "config.json",
                        "datasets.json",
                    ],  # noqa: E501
                    capture_output=True,
                    text=True,
                    cwd=".",
                )
                if result.stdout.strip():
                    print(
                        f"WARNING: Test isolation failed - critical files modified: {result.stdout.strip()}"  # noqa: E501
                    )
            except Exception:
                # Git not available or other issue, skip verification
                pass

        # Cleanup any stray test database files in root directory
        root_test_files = glob.glob("test_*.db") + glob.glob("*test*.json")
        if root_test_files:
            print(
                f"WARNING: Test isolation incomplete - cleaning up {len(root_test_files)} stray test files"  # noqa: E501
            )
            for test_file in root_test_files:
                try:
                    os.unlink(test_file)
                except (OSError, PermissionError):
                    pass

        # Cleanup temporary directory
        try:
            shutil.rmtree(temp_dir)
        except (OSError, PermissionError):
            pass


@pytest.fixture(scope="session")
def test_service_factory():
    """Create test service factory with optimized settings for testing."""
    # Create factory with shorter TTL and more frequent cleanup for tests
    factory = ServiceFactory(
        cache_ttl_seconds=30,  # Shorter TTL for tests
        cleanup_interval=5,  # More frequent cleanup
    )
    set_service_factory(factory)
    yield factory
    # Cleanup at end of session
    try:
        factory.clear_cache()
    except Exception as e:
        # Ignore errors during cleanup (e.g., closed file handles)
        print(f"Warning: Error during service factory cleanup: {e}")


@pytest.fixture(scope="session")
def test_database_manager():
    """Create and manage test database manager."""
    # Get the global database manager (will be created if needed)
    manager = get_database_manager()
    yield manager
    # Cleanup at end of session
    cleanup_database_resources()


@pytest.fixture(autouse=True, scope="function")
def reset_service_factory_cache(request, test_service_factory):
    """Auto-reset service factory cache between each test for isolation."""
    # Skip this fixture for integration tests
    if "integration_tests" in str(request.fspath):
        yield
        return

    # Clear cache before test
    try:
        test_service_factory.clear_cache()
    except Exception as e:
        print(
            f"Warning: Error clearing service factory cache before test: {e}"
        )  # noqa: E501

    yield

    # Clear cache after test
    try:
        test_service_factory.clear_cache()
    except Exception as e:
        print(f"Warning: Error clearing service factory cache after test: {e}")


@pytest.fixture(scope="function")
def test_settings(tmp_path):
    """
    Provide isolated test settings for each test function.

    This fixture creates a completely isolated configuration environment
    for each test, preventing test data pollution in config.json and
    ensuring database files are created in temporary directories.

    Args:
        tmp_path: pytest's temporary directory fixture

    Yields:
        Settings: Isolated settings instance for the test
    """
    # Create test configuration manager
    config_manager = TestConfigurationManager(str(tmp_path))

    try:
        # Get isolated test settings
        settings = config_manager.get_test_settings()
        yield settings
    finally:
        # Clean up test artifacts
        config_manager.cleanup()


@pytest.fixture(scope="function")
def isolated_test_settings(tmp_path):
    """
    Provide isolated test settings with custom overrides.

    This fixture allows tests to specify custom configuration overrides
    while maintaining complete isolation from the global configuration.

    Usage:
        def test_with_custom_config(isolated_test_settings):
            settings = isolated_test_settings({
                "database.default_url": "sqlite:///:memory:",
                "logging.level": "DEBUG"
            })
            # Test with custom settings

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Function that creates settings with overrides
    """

    def _create_settings_with_overrides(overrides=None):
        config_manager = TestConfigurationManager(str(tmp_path))
        return config_manager.get_test_settings(overrides)

    return _create_settings_with_overrides


# Note: For performance reasons, we maintain the existing shared database approach  # noqa: E501
# and only provide configuration isolation. Database isolation fixtures are available  # noqa: E501
# in tests/test_db_utils.py and tests/test_environment.py for tests that specifically  # noqa: E501
# need complete database isolation.


@pytest.fixture(scope="session")
def shared_app(test_service_factory):
    """Create shared app instance for the entire test session - reused across all tests."""  # noqa: E501
    engine, session_local, db_path = create_test_database_with_migrations()
    try:
        # Set the global engine state for testing
        set_current_engine_for_testing(engine, session_local)

        app = create_app(
            engine=engine,
            session_local=session_local,
            service_factory=test_service_factory,
            testing=True,
        )
        yield app, engine, session_local
    finally:
        # Stop any running EventProcessor threads before database cleanup
        # Get and stop the global EventProcessor if it exists
        global_processor = get_global_event_processor()
        if global_processor:
            try:
                global_processor.stop()
                set_global_event_processor(None)
            except Exception as e:
                print(
                    f"Warning: Error stopping global EventProcessor during cleanup: {e}"  # noqa: E501
                )

        # Always cleanup the temporary database
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture(scope="session")
def shared_client(shared_app):
    """Create shared test client for the entire session - reused across all tests."""  # noqa: E501
    app, engine, session_local = shared_app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(shared_app):
    """Provide clean database session for each test function - auto-rollback."""  # noqa: E501
    app, engine, session_local = shared_app

    # Create a new session for this test
    session = session_local()

    try:
        yield session
    finally:
        # Stop any EventProcessor threads created during this test
        global_processor = get_global_event_processor()
        if global_processor:
            try:
                # Stop the processor but don't clear global reference
                # (that's handled in session cleanup)
                global_processor.stop()
            except Exception as e:
                print(
                    f"Warning: Error stopping EventProcessor in test cleanup: {e}"
                )  # noqa: E501

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
                if table_name not in [
                    "migration_versions",
                    "alembic_version",
                ]:  # Preserve migration state
                    cleanup_session.execute(text(f"DELETE FROM {table_name}"))
            cleanup_session.execute(text("PRAGMA foreign_keys = ON"))
            cleanup_session.commit()
        finally:
            cleanup_session.close()


# Legacy fixtures for backwards compatibility - these now use the shared app
@pytest.fixture(scope="function")
def managed_db_session(shared_app, test_database_manager):
    """Provide managed database session using DatabaseManager for testing."""  # noqa: E501
    app, engine, session_local = shared_app

    # Use database manager for optimized session handling
    try:
        # Use the shared app's engine through database manager
        engine_id = f"test_engine_{id(engine)}"
        if engine_id not in test_database_manager._session_locals:
            # Register the test engine with the manager
            test_database_manager._engines[engine_id] = engine
            test_database_manager._session_locals[engine_id] = session_local

        with test_database_manager.get_session(engine_id) as session:
            yield session

    except Exception:
        # Fallback to regular session if optimized fails
        session = session_local()
        try:
            yield session
        finally:
            session.close()


# Legacy fixtures for backwards compatibility - these now use the shared app
@pytest.fixture(scope="function")
def test_app(shared_app):
    """Legacy fixture name - now returns shared app for backwards compatibility."""  # noqa: E501
    app, engine, session_local = shared_app
    return app


@pytest.fixture(scope="function")
def client(request, shared_client):
    """Legacy fixture name - now returns shared client for backwards compatibility."""  # noqa: E501
    # Skip for integration tests to avoid fixture collisions
    if "integration_tests" in str(request.fspath):
        pytest.skip("Skipping conftest client fixture for integration tests")
    return shared_client
