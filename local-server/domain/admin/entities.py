"""
Domain entities for the System Administration bounded context.

These dataclasses represent system health, background task tracking,
and application configuration management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.admin.value_objects import SystemHealthStatus, BackgroundTaskStatus


@dataclass
class SystemHealth:
    """
    Represents the overall health status of the system.

    Attributes:
        status: Health status ('healthy', 'degraded', or 'unhealthy')
        database_connected: Whether database is accessible
        nlp_pipeline_ready: Whether NLP pipeline is initialized
        embedding_model_loaded: Whether embedding model is loaded
        llm_providers_available: List of available LLM provider names
        uptime_seconds: System uptime in seconds
        checked_at: Timestamp of health check
        issues: List of health issues identified (if any)
    """

    status: SystemHealthStatus
    database_connected: bool
    nlp_pipeline_ready: bool
    embedding_model_loaded: bool
    llm_providers_available: list[str]
    uptime_seconds: float
    checked_at: datetime
    issues: list[str] = field(default_factory=list)


@dataclass
class BackgroundTask:
    """
    Represents a long-running background task.

    Attributes:
        id: Unique identifier for the task
        name: Human-readable task name
        status: Task status ('pending', 'running', 'completed', or 'failed')
        progress: Task progress as a float between 0.0 and 1.0
        created_at: Timestamp when task was registered
        started_at: Timestamp when task started execution
        completed_at: Timestamp when task finished
        error: Error message if task failed
        result: Result data if task completed successfully
    """

    id: str
    name: str
    status: BackgroundTaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[float] = None
    error: Optional[str] = None
    result: Optional[dict] = None

    def __post_init__(self):
        """Validate progress field is within valid range."""
        if self.progress is not None and not (0.0 <= self.progress <= 1.0):
            raise ValueError(f"progress must be between 0.0 and 1.0, got {self.progress}")


@dataclass
class AppConfiguration:
    """
    Represents the application configuration.

    Wraps configuration sections as plain dicts. The domain entity
    does NOT depend on Pydantic. API key values are unmasked here;
    masking is a presentation concern.

    Attributes:
        sections: Dictionary mapping section names to their configuration dicts
    """

    sections: dict
