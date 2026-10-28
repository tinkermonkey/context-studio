"""Root conftest for test configuration."""

import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Add the project root to sys.path so that utils, adapters, and domain modules can be imported
# This is needed because pytest may be run from different directories
# NOTE: This MUST be done at module load time, before any imports, to work during collection
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from domain.interchange.services import set_batch_run_context  # noqa: E402

# Pre-import utils to ensure it's available when other modules need it
try:
    import utils.async_executor  # noqa: F401
    import utils.logger  # noqa: F401
except ImportError:
    # If utils is not available yet, it will be handled when the root is added to sys.path
    pass

# Note: Pydantic validation errors are handled by FastAPI's default behavior
# which returns 422 (UNPROCESSABLE_ENTITY). No custom patching is needed.


@pytest.fixture(autouse=True)
def _clear_batch_run_context():
    """Clear the batch-run correlation context (also the import-run context) after each test.

    It is one process-wide ContextVar. A test that leaves it set makes later tests
    record change events against a batch run their database does not have.
    """
    yield
    set_batch_run_context(None)


@event.listens_for(Engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    """Enforce foreign keys on every SQLite engine a test creates.

    Production engines get this from connection.py. Many tests build their own
    engine with create_engine(), so this keeps them on the same rules. Alembic
    turns foreign keys back off on its own connection (see env.py).
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
