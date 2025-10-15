"""
Minimal conftest for Phase 1 integration tests

Note: This file inherits fixtures from the root conftest.py.
The 'client' fixture is provided by tests/conftest.py.
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Set up mock environment BEFORE any imports
os.environ["OPENAI_API_KEY"] = "sk-test1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN"

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def minimal_reference_client():
    """
    Create a minimal FastAPI test client with just the reference router.

    This avoids loading the full app and all its dependencies.
    Used by reference API tests that don't need the full application.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.reference import router
    from services.service_factory import ServiceFactory, set_service_factory

    # Create and set up a service factory for the tests
    factory = ServiceFactory(cache_ttl_seconds=30)
    set_service_factory(factory)

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as test_client:
        yield test_client

    # Clean up the service factory after tests
    set_service_factory(None)
