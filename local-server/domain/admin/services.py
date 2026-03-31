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
        Check current system health.

        Delegates to MetricsCollector to gather system state.

        Returns:
            SystemHealth object describing current system status
        """
        return self._metrics.collect_health()

    def get_configuration(self) -> AppConfiguration:
        """
        Retrieve current application configuration.

        Delegates to ConfigurationStore to load configuration.

        Returns:
            AppConfiguration object with all configuration sections
        """
        return self._config.load()

    def update_configuration(
        self, section: str, updates: dict
    ) -> AppConfiguration:
        """
        Update a configuration section.

        Loads configuration, updates the specified section with new values,
        and saves the result.

        Args:
            section: Name of the configuration section to update
            updates: Dictionary of key-value pairs to update in the section

        Returns:
            Updated AppConfiguration object

        Raises:
            ConfigurationError: If the section does not exist
        """
        config = self._config.load()
        if section not in config.sections:
            raise ConfigurationError(f"Unknown config section: {section}")
        config.sections[section].update(updates)
        self._config.save(config)
        return config

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
            status="pending",
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
        status: str,
        error: Optional[str] = None,
        result: Optional[dict] = None,
    ) -> BackgroundTask:
        """
        Update the status of a background task.

        Updates task status and sets started_at or completed_at timestamps
        as appropriate. If status is 'running', sets started_at to current time.
        If status is 'completed' or 'failed', sets completed_at to current time.

        Args:
            task_id: ID of the task to update
            status: New status value ('running', 'completed', or 'failed')
            error: Error message if task failed
            result: Result data if task completed successfully

        Returns:
            Updated BackgroundTask object

        Raises:
            TaskNotFoundError: If task_id does not exist
        """
        task = self.get_task(task_id)
        task.status = status
        if status == "running":
            task.started_at = datetime.now(timezone.utc)
        elif status in ("completed", "failed"):
            task.completed_at = datetime.now(timezone.utc)
        task.error = error
        task.result = result
        return task
