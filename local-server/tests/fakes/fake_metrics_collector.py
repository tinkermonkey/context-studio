"""Fake in-memory implementation of MetricsCollector for testing."""

import os
import sys
from types import MappingProxyType
from typing import Optional
from domain.admin.value_objects import (

    BackgroundTaskSummary,
    ComponentStatus,
    DatabaseHealth,
    ServiceMetrics,
)


class FakeMetricsCollector:
    """
    Fake implementation of MetricsCollector for unit testing.

    Allows test code to specify granular health components or use sensible defaults.
    Supports raising exceptions from specific methods for testing error handling.
    """

    def __init__(
        self,
        database_health: Optional[DatabaseHealth] = None,
        service_metrics: Optional[ServiceMetrics] = None,
        embedding_status: Optional[ComponentStatus] = None,
        nlp_status: Optional[ComponentStatus] = None,
        task_summary: Optional[BackgroundTaskSummary] = None,
        database_health_error: Optional[Exception] = None,
        service_metrics_error: Optional[Exception] = None,
        embedding_status_error: Optional[Exception] = None,
        nlp_status_error: Optional[Exception] = None,
        task_summary_error: Optional[Exception] = None,
    ):
        """
        Initialize with optional pre-configured health components or exceptions.

        Args:
            database_health: Optional DatabaseHealth. If None, defaults to connected.
            service_metrics: Optional ServiceMetrics. If None, defaults to 0 uptime and no
            providers.
            embedding_status: Optional ComponentStatus. If None, defaults to available.
            nlp_status: Optional ComponentStatus. If None, defaults to available.
            task_summary: Optional BackgroundTaskSummary. If None, defaults to 0 tasks.
            database_health_error: Optional Exception to raise from get_database_health().
            service_metrics_error: Optional Exception to raise from get_service_metrics().
            embedding_status_error: Optional Exception to raise from get_embedding_model_status().
            nlp_status_error: Optional Exception to raise from get_nlp_pipeline_status().
            task_summary_error: Optional Exception to raise from get_background_task_summary().
        """
        self._database_health = database_health or DatabaseHealth(connected=True, issues=())
        self._service_metrics = service_metrics or ServiceMetrics(
            uptime_seconds=0.0, llm_providers_available=()
        )
        self._embedding_status = embedding_status or ComponentStatus(
            available=True, details="Embedding model loaded"
        )
        self._nlp_status = nlp_status or ComponentStatus(
            available=True, details="NLP pipeline ready"
        )
        self._task_summary = task_summary or BackgroundTaskSummary(by_status=MappingProxyType({}))
        self._database_health_error = database_health_error
        self._service_metrics_error = service_metrics_error
        self._embedding_status_error = embedding_status_error
        self._nlp_status_error = nlp_status_error
        self._task_summary_error = task_summary_error

    def get_database_health(self) -> DatabaseHealth:
        """
        Get database health status.

        Returns:
            DatabaseHealth with connectivity and issue details

        Raises:
            Exception if database_health_error was set in __init__
        """
        if self._database_health_error:
            raise self._database_health_error
        return self._database_health

    def get_service_metrics(self) -> ServiceMetrics:
        """
        Get service-level metrics.

        Returns:
            ServiceMetrics with uptime and available LLM providers

        Raises:
            Exception if service_metrics_error was set in __init__
        """
        if self._service_metrics_error:
            raise self._service_metrics_error
        return self._service_metrics

    def get_embedding_model_status(self) -> ComponentStatus:
        """
        Get embedding model component status.

        Returns:
            ComponentStatus of the embedding model

        Raises:
            Exception if embedding_status_error was set in __init__
        """
        if self._embedding_status_error:
            raise self._embedding_status_error
        return self._embedding_status

    def get_nlp_pipeline_status(self) -> ComponentStatus:
        """
        Get NLP pipeline component status.

        Returns:
            ComponentStatus of the NLP pipeline

        Raises:
            Exception if nlp_status_error was set in __init__
        """
        if self._nlp_status_error:
            raise self._nlp_status_error
        return self._nlp_status

    def get_background_task_summary(self) -> BackgroundTaskSummary:
        """
        Get summary of background task statuses.

        Returns:
            BackgroundTaskSummary with task counts by status

        Raises:
            Exception if task_summary_error was set in __init__
        """
        if self._task_summary_error:
            raise self._task_summary_error
        return self._task_summary
