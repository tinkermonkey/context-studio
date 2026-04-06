"""Fake in-memory implementation of MetricsCollector for testing."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone
from typing import Optional

from domain.admin.entities import SystemHealth
from domain.admin.value_objects import (
    SystemHealthStatus,
    DatabaseHealth,
    ServiceMetrics,
    ComponentStatus,
    BackgroundTaskSummary,
)


class FakeMetricsCollector:
    """
    Fake implementation of MetricsCollector for unit testing.

    Allows test code to specify granular health components or use sensible defaults.
    """

    def __init__(
        self,
        health: Optional[SystemHealth] = None,
        database_health: Optional[DatabaseHealth] = None,
        service_metrics: Optional[ServiceMetrics] = None,
        embedding_status: Optional[ComponentStatus] = None,
        nlp_status: Optional[ComponentStatus] = None,
        task_summary: Optional[BackgroundTaskSummary] = None,
    ):
        """
        Initialize with optional pre-configured health components.

        Args:
            health: Optional SystemHealth (deprecated, for backward compatibility)
            database_health: Optional DatabaseHealth. If None, defaults to connected.
            service_metrics: Optional ServiceMetrics. If None, defaults to 0 uptime and no providers.
            embedding_status: Optional ComponentStatus. If None, defaults to available.
            nlp_status: Optional ComponentStatus. If None, defaults to available.
            task_summary: Optional BackgroundTaskSummary. If None, defaults to 0 tasks.
        """
        self._health = health
        self._database_health = database_health or DatabaseHealth(
            connected=True, issues=[]
        )
        self._service_metrics = service_metrics or ServiceMetrics(
            uptime_seconds=0.0, llm_providers_available=[]
        )
        self._embedding_status = embedding_status or ComponentStatus(
            available=True, details="Embedding model loaded"
        )
        self._nlp_status = nlp_status or ComponentStatus(
            available=True, details="NLP pipeline ready"
        )
        self._task_summary = task_summary or BackgroundTaskSummary(
            total=0, by_status={}
        )

    def get_database_health(self) -> DatabaseHealth:
        """
        Get database health status.

        Returns:
            DatabaseHealth with connectivity and issue details
        """
        return self._database_health

    def get_service_metrics(self) -> ServiceMetrics:
        """
        Get service-level metrics.

        Returns:
            ServiceMetrics with uptime and available LLM providers
        """
        return self._service_metrics

    def get_embedding_model_status(self) -> ComponentStatus:
        """
        Get embedding model component status.

        Returns:
            ComponentStatus of the embedding model
        """
        return self._embedding_status

    def get_nlp_pipeline_status(self) -> ComponentStatus:
        """
        Get NLP pipeline component status.

        Returns:
            ComponentStatus of the NLP pipeline
        """
        return self._nlp_status

    def get_background_task_summary(self) -> BackgroundTaskSummary:
        """
        Get summary of background task statuses.

        Returns:
            BackgroundTaskSummary with task counts by status
        """
        return self._task_summary
