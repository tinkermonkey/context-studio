"""
E2E test configuration and fixtures.

This module provides E2E-specific fixtures for end-to-end tests that validate
complete workflows through the HTTP API with real services (database, embeddings).

Key fixtures:
- e2e_client: Module-scoped HTTP client for a fully initialized app
- clean_tables: Function-scoped autouse fixture that truncates all tables after each test
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import create_app
from database.migrations.migration_manager import MigrationManager
from database.utils import (
    get_engine,
    get_session_local,
    init_db,
    set_current_engine_for_testing,
)
from services.service_factory import ServiceFactory, set_service_factory
from utils.event_processor import get_global_event_processor, set_global_event_processor

logger = logging.getLogger(__name__)


def create_e2e_database_with_migrations(tmp_path_factory):
    """
    Create a dedicated E2E database with all migrations applied.

    Returns:
        Tuple[Engine, SessionLocal, str]: Database engine, session factory, and db path
    """
    db_dir = tmp_path_factory.mktemp("e2e_db")
    db_path = str(db_dir / "e2e_test.db")
    db_url = f"sqlite:///{db_path}"

    try:
        engine = get_engine(db_url)
        session_local = get_session_local(engine)
        init_db(engine=engine)

        migration_manager = MigrationManager(db_path)
        success = migration_manager.migrate_to_latest()
        if not success:
            raise RuntimeError("Failed to apply migrations to E2E test database")

        return engine, session_local, db_path
    except Exception:
        # Cleanup on failure
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except OSError:
                pass
        raise


@pytest.fixture(scope="module")
def e2e_app(tmp_path_factory):
    """
    Create a fully initialized app with real services for E2E tests.

    Module-scoped so all tests in a file share the same app/database.
    This fixture creates a dedicated temporary database with migrations applied,
    a real SentenceTransformer embedding service, and a fully initialized FastAPI app.

    Yields:
        Tuple[FastAPI, Engine, SessionLocal]: The app instance, database engine, and session factory  # noqa: E501
    """
    engine, session_local, db_path = create_e2e_database_with_migrations(tmp_path_factory)

    try:
        # Set up the service factory with optimized test settings
        factory = ServiceFactory(cache_ttl_seconds=30, cleanup_interval=5)
        set_service_factory(factory)

        # Set the global engine state for testing
        set_current_engine_for_testing(engine, session_local)

        # Create the app with the real services
        app = create_app(
            engine=engine,
            session_local=session_local,
            service_factory=factory,
        )

        yield app, engine, session_local
    finally:
        # Cleanup — log all exceptions to prevent silent failures that corrupt subsequent tests
        cleanup_errors = []

        # Clear service factory cache
        try:
            factory.clear_cache()
        except Exception as e:
            error_msg = f"Failed to clear service factory cache: {e}"
            logger.exception(error_msg)
            cleanup_errors.append(error_msg)

        # Stop any running EventProcessor
        try:
            global_processor = get_global_event_processor()
            if global_processor:
                global_processor.stop()
                set_global_event_processor(None)
        except Exception as e:
            error_msg = f"Failed to stop EventProcessor: {e}"
            logger.exception(error_msg)
            cleanup_errors.append(error_msg)

        # Delete the temporary database file
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except OSError as e:
            error_msg = f"Failed to delete temporary database file {db_path}: {e}"
            logger.exception(error_msg)
            cleanup_errors.append(error_msg)

        # If any cleanup errors occurred, log a summary
        if cleanup_errors:
            logger.warning(
                f"e2e_app fixture teardown had {len(cleanup_errors)} error(s): "
                + " | ".join(cleanup_errors)
            )


@pytest.fixture(scope="module")
def e2e_client(e2e_app):
    """
    Provide an HTTP test client for E2E tests.

    Uses the module-scoped app, so all tests in a file share the same database.
    The client is wrapped in a context manager to ensure proper cleanup.

    Yields:
        TestClient: A FastAPI TestClient instance ready to make HTTP requests
    """
    app, engine, session_local = e2e_app
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function", autouse=True)
def clean_tables(e2e_app):
    """
    Autouse function-scoped fixture that truncates all tables after each test.

    This ensures that a mid-test failure does not corrupt subsequent tests
    within the same module. Foreign key checks are disabled during cleanup
    to allow unrestricted deletion, then re-enabled afterward.

    The fixture yields before the test runs and cleans up after it completes,
    regardless of test outcome (pass/fail).
    """
    yield

    # After test runs, clean all tables
    app, engine, session_local = e2e_app
    cleanup_session = session_local()

    try:
        # Disable foreign key checks during cleanup
        cleanup_session.execute(text("PRAGMA foreign_keys = OFF"))

        # Truncate tables in reverse dependency order
        # (links depend on nodes and predicates; nodes depend on predicates)
        for table in ["structure_node_links", "structure_nodes", "predicates", "change_events"]:
            cleanup_session.execute(text(f"DELETE FROM {table}"))

        # Re-enable foreign key checks
        cleanup_session.execute(text("PRAGMA foreign_keys = ON"))
        cleanup_session.commit()
    except Exception:
        cleanup_session.rollback()
        # Log the error so it's visible in test output, not hidden like print() is
        logger.exception(
            "Cleanup failed during E2E test teardown. Subsequent tests may run "
            "against dirty data. Please review the test module state."
        )
    finally:
        cleanup_session.close()
