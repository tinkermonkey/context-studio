"""
Domain entities for the admin bounded context.

Entities represent system health, background tasks, and application configuration.
They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SystemHealth:
    """
    Represents the overall health status of the system.

    Attributes:
        status: Overall health status: "healthy", "degraded", or "unhealthy".
        database_ok: Whether the database is accessible and responding.
        embedding_service_ok: Whether the embedding service is accessible and responding.
        details: Additional diagnostic details as a dict.
    """

    status: str
    database_ok: bool
    embedding_service_ok: bool
    details: dict = field(default_factory=dict)


@dataclass
class BackgroundTask:
    """
    Represents a long-running task executing in the background.

    Attributes:
        id: Unique identifier for this task.
        task_type: Type of task (e.g., "sync", "embedding", "export").
        status: Current status (e.g., "pending", "running", "completed", "failed").
        progress: Progress as a float between 0.0 and 1.0.
        created_at: ISO 8601 timestamp of task creation.
        completed_at: ISO 8601 timestamp of task completion.
        error: Optional error message if the task failed.
    """

    id: str
    task_type: str
    status: str
    progress: float
    created_at: str
    completed_at: Optional[str]
    error: Optional[str]


@dataclass
class AppConfiguration:
    """
    Represents the application's runtime configuration.

    Attributes:
        llm_provider: The LLM provider being used (e.g., "openai", "anthropic").
        embedding_model: The embedding model being used.
        database_path: Path to the local database file.
        log_level: Logging level (e.g., "debug", "info", "warning", "error").
        extra: Additional configuration options as a dict.
    """

    llm_provider: str
    embedding_model: str
    database_path: str
    log_level: str
    extra: dict = field(default_factory=dict)
