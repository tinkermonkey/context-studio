"""
Pytest configuration and shared fixtures for unit tests.
Ensures proper test isolation by managing singletons and shared state.
"""

import pytest
import sys
import os

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

@pytest.fixture(autouse=True)
def clean_nlp_pipeline():
    """
    Automatically clean up the NLP pipeline singleton between tests.
    This prevents component initialization errors when tests are run together.
    """
    from nlp import pipeline

    # Store original instance

    yield

    # Clean up after test
    try:
        if pipeline._pipeline_instance is not None:
            pipeline._pipeline_instance.shutdown()
    except Exception:
        pass
    finally:
        # Reset to None to force reinitialization for next test
        pipeline._pipeline_instance = None


@pytest.fixture(autouse=True)
def clean_service_factory():
    """
    Clean up service factory state between tests.
    """
    from services.service_factory import ServiceFactory

    yield

    # Clear all service factory instances
    try:
        # Get all active instances and clear them
        for instance in ServiceFactory._instances.values():
            try:
                instance.clear_cache()
            except Exception:
                pass
        ServiceFactory._instances.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_performance_monitor():
    """
    Clean up performance monitor state between tests.
    """
    yield

    # Clear performance monitor state
    try:
        from services.performance_monitor import PerformanceMonitor
        # Reset any class-level state if it exists
        if hasattr(PerformanceMonitor, '_instances'):
            PerformanceMonitor._instances.clear()
    except ImportError:
        pass  # Module might not exist yet