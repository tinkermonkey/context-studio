"""
E2E test configuration and fixtures.

Sets up a real FastAPI application with real databases for end-to-end testing.
"""

import sys
import os
import tempfile
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def temp_db_dir():
    """Create a temporary directory for test databases."""
    with tempfile.TemporaryDirectory(prefix="e2e_test_") as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="module")
def e2e_config_file(temp_db_dir):
    """
    Create a temporary config.json file with test database paths.

    Returns the path to the temporary config file.
    """
    config_data = {
        "server": {
            "host": "127.0.0.1",
            "port": 8000,
            "cors_origins": ["*"]
        },
        "database": {
            "local_db_path": str(temp_db_dir / "local.db"),
            "operations_db_path": str(temp_db_dir / "operations.db")
        },
        "logging": {
            "log_level": "INFO",
            "max_bytes": 10485760,
            "backup_count": 5
        },
        "llm": {
            "openai_api_key": "",
            "anthropic_api_key": ""
        },
        "nlp": {},
        "reference": {
            "cache_db_path": str(temp_db_dir / "reference_api_cache.db"),
            "reference_db_path": str(temp_db_dir / "reference.db")
        },
        "sync": {
            "adapter": "none"
        }
    }

    config_file = temp_db_dir / "config.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)

    return str(config_file)


@pytest.fixture(scope="module", autouse=True)
def setup_e2e_config(e2e_config_file):
    """
    Set CONFIG_PATH environment variable to use test config.

    This must be done before any imports of config or app modules
    that depend on CONFIG_PATH.
    """
    original_config_path = os.environ.get("CONFIG_PATH")
    os.environ["CONFIG_PATH"] = e2e_config_file

    # Clear the global config manager cache so it reloads with the new config path
    import config
    config._config_manager = None

    yield

    # Restore original environment
    if original_config_path is not None:
        os.environ["CONFIG_PATH"] = original_config_path
    else:
        os.environ.pop("CONFIG_PATH", None)
    config._config_manager = None


@pytest.fixture(scope="module")
def init_db(setup_e2e_config, temp_db_dir):
    """
    Run database migrations to set up schema.

    Migrations must be run after config is set up but before
    the app is created.
    """
    import subprocess

    local_server_dir = Path(__file__).parent.parent.parent

    # Run migrations for both databases
    # Set PYTHONPATH to include the local-server directory so alembic can import modules
    env = os.environ.copy()
    env["PYTHONPATH"] = str(local_server_dir)

    result = subprocess.run(
        ["python", "scripts/run_migrations.py", "all", "upgrade", "heads"],
        cwd=str(local_server_dir),
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to run migrations: {result.stderr}")

    yield


@pytest.fixture(scope="module")
def e2e_app(init_db):
    """
    Create a fully initialized FastAPI application with real services.

    Uses real databases in temp directories, real embedding service,
    and real adapters for all external services. The init_db fixture
    ensures the database schema is set up before the app is created.
    """
    # Import app after config path is set and migrations are run
    from app import app as real_app

    return real_app


@pytest.fixture(scope="module")
def e2e_client(e2e_app):
    """
    Create an HTTP test client for making API calls to the real app.

    The TestClient context manager handles app startup/shutdown.
    """
    with TestClient(e2e_app) as client:
        yield client
