"""
Domain service for System Administration bounded context.

AdminService orchestrates system health monitoring, configuration management,
and background task lifecycle.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from .entities import SystemHealth, BackgroundTask, AppConfiguration
from .value_objects import BackgroundTaskStatus, SystemHealthStatus, DatabaseHealth, ServiceMetrics, ComponentStatus, BackgroundTaskSummary
from .ports import MetricsCollector, ConfigurationStore
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
    ) -> None:
        """
        Initialize AdminService with required port implementations.

        Args:
            metrics_collector: Port implementation for collecting health metrics
            config_store: Port implementation for configuration persistence
        """
        self._metrics = metrics_collector
        self._config = config_store
        self._tasks: dict[str, BackgroundTask] = {}

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
        db_health = DatabaseHealth(connected=False, issues=[])
        service_metrics = ServiceMetrics(uptime_seconds=0.0, llm_providers_available=[])
        embedding_status = ComponentStatus(available=False, details="Health check not performed")
        nlp_status = ComponentStatus(available=False, details="Health check not performed")
        task_summary = BackgroundTaskSummary(by_status={})

        # Call each port method with individual error handling
        try:
            db_health = self._metrics.get_database_health()
        except Exception as e:
            db_health = DatabaseHealth(
                connected=False, issues=[f"Error checking database health: {e}"]
            )

        service_metrics_error = None
        try:
            service_metrics = self._metrics.get_service_metrics()
        except Exception as e:
            service_metrics_error = str(e)
            service_metrics = ServiceMetrics(
                uptime_seconds=0.0, llm_providers_available=[]
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

        try:
            task_summary = self._metrics.get_background_task_summary()
        except Exception:
            task_summary = BackgroundTaskSummary(by_status={})

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

        # Check for failed background tasks
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
            llm_providers_available=service_metrics.llm_providers_available,
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

    def update_configuration(
        self, section: str, updates: dict
    ) -> AppConfiguration:
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
            ConfigurationError: If the section does not exist or is not configured
        """
        config = self._config.load()

        # Valid configuration sections
        valid_sections = {"server", "database", "llm", "nlp", "embedding", "reference_sources", "logging", "sync"}
        if section not in valid_sections:
            raise ConfigurationError(f"Unknown config section: {section}")

        # Get the current section value
        section_value = getattr(config, section, None)
        if section_value is None:
            raise ConfigurationError(f"Configuration section '{section}' is not configured")

        # Update the section with the provided updates
        if isinstance(section_value, dict):
            section_value.update(updates)
            setattr(config, section, section_value)
        else:
            raise ConfigurationError(f"Configuration section '{section}' is not a dictionary")

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
        """
        task = self.get_task(task_id)
        task.status = status
        if status == BackgroundTaskStatus.RUNNING:
            task.started_at = datetime.now(timezone.utc)
        elif status in (BackgroundTaskStatus.COMPLETED, BackgroundTaskStatus.FAILED):
            task.completed_at = datetime.now(timezone.utc)
        task.error = error
        task.result = result
        return task
