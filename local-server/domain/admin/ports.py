"""
Port interfaces (protocols) for the System Administration bounded context.

Ports define contracts for external adapters (configuration storage, metrics collection).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Protocol, Any, Sequence, Optional

from .entities import AppConfiguration, Dataset, DatasetMetrics
from .value_objects import (
    DatabaseHealth,
    ServiceMetrics,
    ComponentStatus,
    BackgroundTaskSummary,
)


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


class DatasetRepository(Protocol):
    """
    Port for persisting and retrieving datasets.

    Implementations handle storing dataset metadata and computing
    metrics from ontology data.
    """

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        Retrieve a dataset by ID.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dataset if found, None otherwise
        """
        ...

    def list_datasets(self) -> Sequence[Dataset]:
        """
        List all datasets.

        Returns:
            Sequence of all datasets
        """
        ...

    def save_dataset(self, dataset: Dataset) -> Dataset:
        """
        Save a dataset (create or update).

        Args:
            dataset: The dataset to save

        Returns:
            The saved dataset
        """
        ...

    def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete a dataset by ID.

        Args:
            dataset_id: The dataset ID to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    def get_active_dataset(self) -> Optional[Dataset]:
        """
        Get the currently active dataset.

        Returns:
            Active dataset if one is set, None otherwise
        """
        ...

    def set_active_dataset(self, dataset_id: str) -> Dataset:
        """
        Set a dataset as active and deactivate others.

        Args:
            dataset_id: The dataset ID to activate

        Returns:
            The activated dataset
        """
        ...

    def compute_metrics(self, dataset_id: str) -> DatasetMetrics:
        """
        Compute or refresh metrics for a dataset by querying the ontology data.

        Args:
            dataset_id: The dataset ID

        Returns:
            DatasetMetrics with current entity counts
        """
        ...
