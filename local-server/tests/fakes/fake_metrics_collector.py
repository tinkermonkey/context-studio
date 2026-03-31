"""Fake in-memory implementation of MetricsCollector for testing."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone
from domain.admin.entities import SystemHealth


class FakeMetricsCollector:
    """
    Fake implementation of MetricsCollector for unit testing.

    Allows test code to specify health state or use sensible defaults.
    """

    def __init__(self, health: SystemHealth = None):
        """
        Initialize with optional pre-configured health state.

        Args:
            health: Optional SystemHealth to return. If None, returns a healthy default.
        """
        self._health = health or SystemHealth(
            status="healthy",
            database_connected=True,
            nlp_pipeline_ready=True,
            embedding_model_loaded=True,
            llm_providers_available=[],
            uptime_seconds=0.0,
            checked_at=datetime.now(timezone.utc),
        )

    def collect_health(self) -> SystemHealth:
        """
        Return the configured health state.

        Returns:
            SystemHealth object
        """
        return self._health
