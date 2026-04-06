"""
Domain entities for the System Administration bounded context.

These dataclasses represent system health, background task tracking,
and application configuration management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

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
    error: Optional[str] = None
    result: Optional[dict] = None


@dataclass
class AppConfiguration:
    """
    Represents the application configuration.

    Configuration is organized into explicit sections. The domain entity
    does NOT depend on Pydantic. API key values are unmasked here;
    masking is a presentation concern.

    Attributes:
        server: Server configuration (host, port, cors settings)
        database: Database configuration (paths, pool settings)
        llm: LLM configuration (provider keys, default models)
        nlp: NLP pipeline configuration (model name, components)
        embedding: Embedding model configuration (model name)
        reference_sources: External reference sources configuration (enabled sources, rate limits)
        sync: Optional S3/remote sync settings
        logging: Logging configuration (level, handlers, etc.)
    """

    server: dict[str, Any]
    database: dict[str, Any]
    llm: dict[str, Any]
    nlp: dict[str, Any]
    embedding: dict[str, Any]
    reference_sources: dict[str, Any]
    logging: dict[str, Any] = field(default_factory=lambda: {"level": "INFO"})
    sync: Optional[dict[str, Any]] = None
