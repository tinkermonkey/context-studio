"""
Domain entities for the admin bounded context.

Entities represent system health, background tasks, and application configuration.
They import only from Python stdlib.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from typing import Optional

from domain.admin.enums import SystemHealthStatus, BackgroundTaskStatus, BackgroundTaskType, LogLevel


@dataclass
class SystemHealth:
    """
    Represents the overall health status of the system.

    Attributes:
        status: Overall health status (healthy, degraded, unhealthy).
        database_ok: Whether the database is accessible and responding.
        embedding_service_ok: Whether the embedding service is accessible and responding.
        details: Additional diagnostic details as immutable read-only mapping.
    """

    status: SystemHealthStatus
    database_ok: bool
    embedding_service_ok: bool
    details: types.MappingProxyType = field(default_factory=lambda: types.MappingProxyType({}))

    def __post_init__(self) -> None:
        """Validate system health invariants."""
        if not isinstance(self.status, SystemHealthStatus):
            raise TypeError(
                f"status must be a SystemHealthStatus enum, got {type(self.status).__name__}"
            )
        if not isinstance(self.database_ok, bool):
            raise TypeError("database_ok must be a boolean")
        if not isinstance(self.embedding_service_ok, bool):
            raise TypeError("embedding_service_ok must be a boolean")
        if not isinstance(self.details, types.MappingProxyType):
            raise TypeError("details must be a MappingProxyType (immutable mapping)")


@dataclass
class BackgroundTask:
    """
    Represents a long-running task executing in the background.

    Attributes:
        id: Unique identifier for this task.
        task_type: Type of task (sync, embedding, export, import, maintenance, backup).
        status: Current status (pending, running, completed, failed).
        progress: Progress as a float between 0.0 and 1.0.
        created_at: ISO 8601 timestamp of task creation.
        completed_at: ISO 8601 timestamp of task completion.
        error: Optional error message if the task failed.
    """

    id: str
    task_type: BackgroundTaskType
    status: BackgroundTaskStatus
    progress: float
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate background task invariants."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("BackgroundTask id must be a non-empty string")
        if not isinstance(self.task_type, BackgroundTaskType):
            raise TypeError(
                f"task_type must be a BackgroundTaskType enum, got {type(self.task_type).__name__}"
            )
        if not isinstance(self.status, BackgroundTaskStatus):
            raise TypeError(
                f"status must be a BackgroundTaskStatus enum, got {type(self.status).__name__}"
            )
        if isinstance(self.progress, bool) or not isinstance(self.progress, (int, float)) or not (0.0 <= self.progress <= 1.0):
            raise ValueError("progress must be a number between 0.0 and 1.0")
        if not self.created_at or not isinstance(self.created_at, str):
            raise ValueError("BackgroundTask created_at must be a non-empty timestamp string")
        if self.completed_at is not None and not isinstance(self.completed_at, str):
            raise TypeError("completed_at must be None or a timestamp string")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be None or a string")


@dataclass
class AppConfiguration:
    """
    Represents the application's runtime configuration.

    Attributes:
        llm_provider: The LLM provider being used (e.g., "openai", "anthropic").
        embedding_model: The embedding model being used.
        database_path: Path to the local database file.
        log_level: Logging level (debug, info, warning, error, critical).
        extra: Additional configuration options as immutable read-only mapping.
    """

    llm_provider: str
    embedding_model: str
    database_path: str
    log_level: LogLevel
    extra: types.MappingProxyType = field(default_factory=lambda: types.MappingProxyType({}))

    def __post_init__(self) -> None:
        """Validate application configuration invariants."""
        if not self.llm_provider or not isinstance(self.llm_provider, str):
            raise ValueError("AppConfiguration llm_provider must be a non-empty string")
        if not self.embedding_model or not isinstance(self.embedding_model, str):
            raise ValueError("AppConfiguration embedding_model must be a non-empty string")
        if not self.database_path or not isinstance(self.database_path, str):
            raise ValueError("AppConfiguration database_path must be a non-empty string")
        if not isinstance(self.log_level, LogLevel):
            raise TypeError(
                f"log_level must be a LogLevel enum, got {type(self.log_level).__name__}"
            )
        if not isinstance(self.extra, types.MappingProxyType):
            raise TypeError("extra must be a MappingProxyType (immutable mapping)")
