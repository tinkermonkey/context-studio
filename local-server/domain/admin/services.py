"""
Domain service for System Administration bounded context.

AdminService orchestrates system health monitoring, configuration management,
and background task lifecycle.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Optional

from .entities import SystemHealth, BackgroundTask, AppConfiguration, Dataset, DatasetMetrics
from .value_objects import (
    BackgroundTaskStatus,
    SystemHealthStatus,
    DatabaseHealth,
    ServiceMetrics,
    ComponentStatus,
    BackgroundTaskSummary,
)
from .ports import MetricsCollector, ConfigurationStore, DatasetRepository
from .exceptions import TaskNotFoundError, ConfigurationError


class AdminService:
    """
    Service for system administration operations.

    Coordinates health monitoring, configuration management, and task tracking
    using injected port implementations.
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        config_store: ConfigurationStore,
        dataset_repository: Optional[DatasetRepository] = None,
    ) -> None:
        """
        Initialize AdminService with required port implementations.

        Args:
            metrics_collector: Port implementation for collecting health metrics
            config_store: Port implementation for configuration persistence
            dataset_repository: Optional port implementation for dataset persistence
        """
        self._metrics = metrics_collector
        self._config = config_store
        self._tasks: dict[str, BackgroundTask] = {}
        self._datasets = dataset_repository

    def check_health(self) -> SystemHealth:
        """
        Check current system health by aggregating granular health checks.

        Calls all 5 granular port methods with resilience to individual failures
        and computes overall system health status:
        - UNHEALTHY if database is not connected
        - DEGRADED if any issues are reported
        - HEALTHY otherwise

        Returns:
            SystemHealth object describing current system status
        """
        # Initialize defaults for safe fallback on any component failure
        db_health = DatabaseHealth(connected=False, issues=())
        service_metrics = ServiceMetrics(uptime_seconds=0.0, llm_providers_available=())
        embedding_status = ComponentStatus(
            available=False, details="Health check not performed"
        )
        nlp_status = ComponentStatus(
            available=False, details="Health check not performed"
        )
        task_summary = BackgroundTaskSummary(by_status=MappingProxyType({}))

        # Call each port method with individual error handling
        try:
            db_health = self._metrics.get_database_health()
        except Exception as e:
            db_health = DatabaseHealth(
                connected=False, issues=(f"Error checking database health: {e}",)
            )

        service_metrics_error = None
        try:
            service_metrics = self._metrics.get_service_metrics()
        except Exception as e:
            service_metrics_error = str(e)
            service_metrics = ServiceMetrics(
                uptime_seconds=0.0, llm_providers_available=()
            )

        try:
            embedding_status = self._metrics.get_embedding_model_status()
        except Exception as e:
            embedding_status = ComponentStatus(
                available=False, details=f"Error checking embedding model: {e}"
            )

        try:
            nlp_status = self._metrics.get_nlp_pipeline_status()
        except Exception as e:
            nlp_status = ComponentStatus(
                available=False, details=f"Error checking NLP pipeline: {e}"
            )

        task_summary_error = None
        try:
            task_summary = self._metrics.get_background_task_summary()
        except Exception as e:
            task_summary_error = str(e)
            task_summary = BackgroundTaskSummary(by_status=MappingProxyType({}))

        # Aggregate all issues
        issues: list[str] = []
        issues.extend(db_health.issues)
        if not embedding_status.available:
            issues.append(f"Embedding model: {embedding_status.details}")
        if not nlp_status.available:
            issues.append(f"NLP pipeline: {nlp_status.details}")

        # Check LLM providers: report error or config gap based on check success
        if service_metrics_error:
            issues.append(f"Error checking service metrics: {service_metrics_error}")
        elif not service_metrics.llm_providers_available:
            issues.append("No LLM providers configured")

        # Check for background task errors or failures
        if task_summary_error:
            issues.append(f"Error checking background tasks: {task_summary_error}")
        else:
            failed_tasks = task_summary.by_status.get(BackgroundTaskStatus.FAILED, 0)
            if failed_tasks > 0:
                issues.append(f"{failed_tasks} background task(s) failed")

        # Derive overall status based on business rules
        if not db_health.connected:
            status = SystemHealthStatus.UNHEALTHY
        elif issues:
            status = SystemHealthStatus.DEGRADED
        else:
            status = SystemHealthStatus.HEALTHY

        return SystemHealth(
            status=status,
            database_connected=db_health.connected,
            nlp_pipeline_ready=nlp_status.available,
            embedding_model_loaded=embedding_status.available,
            llm_providers_available=list(service_metrics.llm_providers_available),
            uptime_seconds=service_metrics.uptime_seconds,
            checked_at=datetime.now(timezone.utc),
            issues=issues,
        )

    def get_database_health(self) -> DatabaseHealth:
        """
        Get database health status.

        Returns:
            DatabaseHealth with connectivity and issue details
        """
        return self._metrics.get_database_health()

    def get_service_metrics(self) -> ServiceMetrics:
        """
        Get service-level metrics.

        Returns:
            ServiceMetrics with uptime and available LLM providers
        """
        return self._metrics.get_service_metrics()

    def get_embedding_model_status(self) -> ComponentStatus:
        """
        Get embedding model component status.

        Returns:
            ComponentStatus of the embedding model
        """
        return self._metrics.get_embedding_model_status()

    def get_nlp_pipeline_status(self) -> ComponentStatus:
        """
        Get NLP pipeline component status.

        Returns:
            ComponentStatus of the NLP pipeline
        """
        return self._metrics.get_nlp_pipeline_status()

    def get_background_task_summary(self) -> BackgroundTaskSummary:
        """
        Get summary of background task statuses.

        Returns:
            BackgroundTaskSummary with task counts by status
        """
        return self._metrics.get_background_task_summary()

    def get_configuration(self) -> AppConfiguration:
        """
        Retrieve current application configuration.

        Delegates to ConfigurationStore to load configuration.

        Returns:
            AppConfiguration object with all configuration sections
        """
        return self._config.load()

    def reset_configuration(self) -> AppConfiguration:
        """
        Reset configuration to defaults while preserving credentials.

        Delegates to ConfigurationStore.reset_to_defaults() to perform
        the reset operation.

        Returns:
            AppConfiguration reset to defaults with credentials preserved
        """
        return self._config.reset_to_defaults()

    def update_configuration(self, section: str, updates: dict) -> AppConfiguration:
        """
        Update a configuration section.

        Validates the section exists, updates it with new values,
        and persists the result via ConfigurationStore.

        Args:
            section: Name of the configuration section to update
            updates: Dictionary of key-value pairs to update in the section

        Returns:
            Updated AppConfiguration object

        Raises:
            ConfigurationError: If the section does not exist, is not configured, or is not a dict
        """
        config = self._config.load()

        # Valid configuration sections derived from AppConfiguration fields
        valid_sections = {f.name for f in dataclasses.fields(AppConfiguration)}
        if section not in valid_sections:
            raise ConfigurationError(f"Unknown config section: {section}")

        # Get the current section value
        section_value = getattr(config, section, None)
        if section_value is None:
            raise ConfigurationError(
                f"Configuration section '{section}' is not configured"
            )

        # Validate that section_value is a dict before attempting to update
        if not isinstance(section_value, dict):
            raise ConfigurationError(
                f"Configuration section '{section}' is not a dictionary (got {type(section_value).__name__})"
            )

        # Update the section with the provided updates
        section_value.update(updates)
        setattr(config, section, section_value)

        return self._config.save(config)

    def register_task(self, name: str) -> BackgroundTask:
        """
        Register a new background task.

        Creates a task with pending status and stores it in-memory.

        Args:
            name: Human-readable name of the task

        Returns:
            BackgroundTask object representing the registered task
        """
        task = BackgroundTask(
            id=str(uuid.uuid4()),
            name=name,
            status=BackgroundTaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> BackgroundTask:
        """
        Retrieve a background task by ID.

        Args:
            task_id: ID of the task to retrieve

        Returns:
            BackgroundTask object

        Raises:
            TaskNotFoundError: If task_id does not exist
        """
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return self._tasks[task_id]

    def list_tasks(self) -> list[BackgroundTask]:
        """
        List all background tasks.

        Returns:
            List of all BackgroundTask objects
        """
        return list(self._tasks.values())

    def update_task_status(
        self,
        task_id: str,
        status: BackgroundTaskStatus,
        error: Optional[str] = None,
        result: Optional[dict] = None,
    ) -> BackgroundTask:
        """
        Update the status of a background task.

        Updates task status and sets started_at or completed_at timestamps
        as appropriate. If status is RUNNING, sets started_at to current time.
        If status is COMPLETED or FAILED, sets completed_at to current time.

        Args:
            task_id: ID of the task to update
            status: New status value (RUNNING, COMPLETED, or FAILED)
            error: Error message if task failed
            result: Result data if task completed successfully

        Returns:
            Updated BackgroundTask object

        Raises:
            TaskNotFoundError: If task_id does not exist
            InvalidStateTransitionError: If the status transition is invalid
        """
        task = self.get_task(task_id)
        task.transition_to(
            status, datetime.now(timezone.utc), error=error, result=result
        )
        return task

    def create_dataset(
        self,
        title: str,
        filename: str,
        description: Optional[str] = None,
    ) -> Dataset:
        """
        Create a new dataset.

        Args:
            title: Display name for the dataset
            filename: Original filename
            description: Optional description

        Returns:
            Created Dataset

        Raises:
            ValueError: If title is empty
            RuntimeError: If dataset repository is not configured
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        if not title or not title.strip():
            raise ValueError("Title cannot be empty")

        dataset = Dataset(
            id=str(uuid.uuid4()),
            title=title,
            filename=filename,
            description=description,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            schema_version="1.0",
        )

        dataset.metrics = self._datasets.compute_metrics(dataset.id)
        return self._datasets.save_dataset(dataset)

    def get_dataset(self, dataset_id: str) -> Dataset:
        """
        Retrieve a dataset by ID.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dataset if found

        Raises:
            RuntimeError: If dataset repository is not configured
            ValueError: If dataset not found
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        dataset = self._datasets.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")
        return dataset

    def list_datasets(self) -> list[Dataset]:
        """
        List all datasets.

        Returns:
            List of all datasets

        Raises:
            RuntimeError: If dataset repository is not configured
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        return list(self._datasets.list_datasets())

    def update_dataset(
        self,
        dataset_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dataset:
        """
        Update dataset metadata.

        Args:
            dataset_id: The dataset ID
            title: New title (optional)
            description: New description (optional)

        Returns:
            Updated Dataset

        Raises:
            RuntimeError: If dataset repository is not configured
            ValueError: If title is empty or dataset not found
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        dataset = self.get_dataset(dataset_id)

        if title is not None:
            if not title.strip():
                raise ValueError("Title cannot be empty")
            dataset.rename(title)

        if description is not None:
            dataset.description = description

        dataset.version += 1
        return self._datasets.save_dataset(dataset)

    def delete_dataset(self, dataset_id: str) -> None:
        """
        Delete a dataset.

        Args:
            dataset_id: The dataset ID to delete

        Raises:
            RuntimeError: If dataset repository is not configured
            ValueError: If dataset not found or is active
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        dataset = self.get_dataset(dataset_id)

        if dataset.is_active:
            raise ValueError("Cannot delete the active dataset")

        self._datasets.delete_dataset(dataset_id)

    def activate_dataset(self, dataset_id: str) -> Dataset:
        """
        Activate a dataset as the current workspace.

        Args:
            dataset_id: The dataset ID to activate

        Returns:
            The activated Dataset

        Raises:
            RuntimeError: If dataset repository is not configured
            ValueError: If dataset not found
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        dataset = self.get_dataset(dataset_id)
        dataset.is_active = True
        dataset.mark_accessed()
        return self._datasets.set_active_dataset(dataset_id)

    def get_active_dataset(self) -> Optional[Dataset]:
        """
        Get the currently active dataset.

        Returns:
            Active dataset if one is set, None otherwise

        Raises:
            RuntimeError: If dataset repository is not configured
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        return self._datasets.get_active_dataset()

    def refresh_dataset_metrics(self, dataset_id: str) -> Dataset:
        """
        Recompute metrics for a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dataset with refreshed metrics

        Raises:
            RuntimeError: If dataset repository is not configured
            ValueError: If dataset not found
        """
        if not self._datasets:
            raise RuntimeError("Dataset repository not configured")

        dataset = self.get_dataset(dataset_id)
        dataset.metrics = self._datasets.compute_metrics(dataset_id)
        return self._datasets.save_dataset(dataset)
