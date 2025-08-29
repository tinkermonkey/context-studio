import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from triage_scripts.triage_helper import create_test_app_with_migrations, cleanup_test_database
from sqlalchemy import text
import pytest


def test_sqlite_vec_extension_loads():
    """Diagnostic test: attempt to import and load sqlite_vec into the test DB connection.

    Fail explicitly with the loader exception message so CI can capture the root cause.
    """
    app, test_db_fd, test_db_path, engine, TestingSessionLocal = create_test_app_with_migrations()
    try:
        # First ensure the sqlite_vec package is importable
        try:
            import sqlite_vec  # type: ignore
        except Exception as e:
            pytest.fail(f"sqlite_vec package import failed: {e}")

        # Now try to load into the DB connection used by the engine
        try:
            with engine.connect() as conn:
                try:
                    raw_conn = conn.connection
                except Exception:
                    raw_conn = conn.connection
                try:
                    raw_conn.enable_load_extension(True)
                except Exception:
                    # Some DB-API wrappers may not expose this; continue and let sqlite_vec.load raise if needed
                    pass
                try:
                    sqlite_vec.load(raw_conn)
                finally:
                    try:
                        raw_conn.enable_load_extension(False)
                    except Exception:
                        pass
        except Exception as e:
            pytest.fail(f"Failed to load sqlite_vec into DB connection: {e}")
    finally:
        try:
            cleanup_test_database(test_db_fd, test_db_path)
        except Exception:
            pass
