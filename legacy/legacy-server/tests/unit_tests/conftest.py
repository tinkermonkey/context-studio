"""
Pytest configuration and shared fixtures for unit tests.
Ensures proper test isolation by managing singletons and shared state.
"""

import os
import sys

import pytest

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


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
        if hasattr(PerformanceMonitor, "_instances"):
            PerformanceMonitor._instances.clear()
    except ImportError:
        pass  # Module might not exist yet
