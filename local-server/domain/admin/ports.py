"""
Port interfaces (protocols) for the System Administration bounded context.

Ports define contracts for external adapters (configuration storage, metrics collection).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Protocol, Any

from .entities import AppConfiguration
from .value_objects import DatabaseHealth, ServiceMetrics, ComponentStatus, BackgroundTaskSummary


class MetricsCollector(Protocol):
    """
    Port for collecting system health metrics.

    Implementations should gather real-time information about system state:
    database connectivity, pipeline readiness, model loading status, etc.
    """

    def get_database_health(self) -> DatabaseHealth:
        """
        Get database health status.

        Returns:
            DatabaseHealth with connectivity and issue details
        """
        ...

    def get_service_metrics(self) -> ServiceMetrics:
        """
        Get service-level metrics.

        Returns:
            ServiceMetrics with uptime and available LLM providers
        """
        ...

    def get_embedding_model_status(self) -> ComponentStatus:
        """
        Get embedding model component status.

        Returns:
            ComponentStatus of the embedding model
        """
        ...

    def get_nlp_pipeline_status(self) -> ComponentStatus:
        """
        Get NLP pipeline component status.

        Returns:
            ComponentStatus of the NLP pipeline
        """
        ...

    def get_background_task_summary(self) -> BackgroundTaskSummary:
        """
        Get summary of background task statuses.

        Returns:
            BackgroundTaskSummary with task counts by status
        """
        ...


class HealthCheckableNLP(Protocol):
    """
    Narrow protocol for health-checking NLP components.

    Defines the minimal interface needed for health checks.
    """

    def is_ready(self) -> bool:
        """
        Check if NLP component is ready.

        Returns:
            True if ready, False otherwise
        """
        ...


class HealthCheckableEmbedding(Protocol):
    """
    Narrow protocol for health-checking embedding components.

    Defines the minimal interface needed for health checks.
    """

    def is_loaded(self) -> bool:
        """
        Check if embedding model is loaded.

        Returns:
            True if loaded, False otherwise
        """
        ...


class HealthCheckableLLM(Protocol):
    """
    Narrow protocol for health-checking LLM components.

    Defines the minimal interface needed for health checks.
    """

    def list_available_providers(self) -> list[str]:
        """
        List available LLM providers.

        Returns:
            List of provider names
        """
        ...


class ConfigurationStore(Protocol):
    """
    Port for persisting and retrieving application configuration.

    Implementations handle loading configuration from files or other
    storage, and updating configuration changes.
    """

    def load(self) -> AppConfiguration:
        """
        Load application configuration.

        Returns:
            AppConfiguration object with all configuration sections
        """
        ...

    def save(self, config: AppConfiguration) -> AppConfiguration:
        """
        Save application configuration.

        Args:
            config: AppConfiguration object with updated configuration

        Returns:
            AppConfiguration object that was saved
        """
        ...

    def get_config(self) -> AppConfiguration:
        """
        Get current application configuration.

        Returns:
            AppConfiguration object with all configuration sections
        """
        ...

    def update_config(self, updates: dict[str, dict[str, Any]]) -> AppConfiguration:
        """
        Update application configuration with partial updates.

        Args:
            updates: Dictionary with section names as keys and dicts of updates as values.
                    Merges updates into existing sections.

        Returns:
            AppConfiguration object with updates applied
        """
        ...

    def reset_to_defaults(self) -> AppConfiguration:
        """
        Reset configuration to defaults while preserving credentials.

        Returns:
            AppConfiguration reset to defaults with credentials preserved
        """
        ...
