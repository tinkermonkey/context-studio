"""
E2E test configuration and fixtures.

This module extends the main test conftest with E2E-specific fixtures,
providing a real application instance with a fully migrated database
for end-to-end tests that validate complete workflows through the HTTP API.
"""

import pytest


@pytest.fixture(scope="module")
def e2e_app(shared_app):
    """
    Provide the shared app instance for E2E tests.

    This fixture reuses the session-scoped shared_app to ensure consistency
    across E2E tests while allowing module-level organization.

    Yields:
        Tuple[FastAPI, Engine, SessionLocal]: The app instance, database engine, and session factory  # noqa: E501
    """
    yield shared_app


@pytest.fixture(scope="module")
def e2e_client(shared_client):
    """
    Provide the shared test client for E2E tests.

    This fixture reuses the session-scoped shared_client to ensure consistency
    across E2E tests. The client uses a real, fully migrated database.

    Yields:
        TestClient: A FastAPI TestClient instance ready to make HTTP requests
    """
    yield shared_client
