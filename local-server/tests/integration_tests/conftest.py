"""
Minimal conftest for Phase 1 integration tests
Avoids loading full app dependencies
"""

import sys
import gc
import time
from pathlib import Path
import pytest
from sqlalchemy import pool

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(autouse=True)
def test_cleanup_database_resources():
    """
    Auto-use fixture to ensure proper cleanup of database resources
    between tests to prevent test isolation issues.
    """
    yield
    
    # Use the built-in cleanup function
    try:
        from database.utils import cleanup_database_resources
        cleanup_database_resources()
    except Exception:
        pass
    
    # Force garbage collection to clean up any remaining references
    gc.collect()
    
    # Small delay to ensure resources are fully released
    time.sleep(0.01)


@pytest.fixture(autouse=True)
def reset_service_factory():
    """
    Auto-use fixture to reset the service factory between tests
    to prevent cached services from interfering.
    """
    yield
    
    try:
        from services.service_factory import ServiceFactory
        # Clear any cached instances
        for factory in ServiceFactory._instances.values():
            factory.clear_cache()
        ServiceFactory._instances.clear()
    except Exception:
        pass
