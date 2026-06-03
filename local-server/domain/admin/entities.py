"""
Domain entities for the System Administration bounded context.

These dataclasses represent system health, background task tracking,
and application configuration management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Optional

from domain.admin.exceptions import InvalidStateTransitionError
from domain.admin.value_objects import BackgroundTaskStatus, SystemHealthStatus


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

    # Valid state transitions for background tasks
    _VALID_TRANSITIONS: ClassVar[dict[BackgroundTaskStatus, set[BackgroundTaskStatus]]] = {
        BackgroundTaskStatus.PENDING: {
            BackgroundTaskStatus.RUNNING,
            BackgroundTaskStatus.COMPLETED,
            BackgroundTaskStatus.FAILED,
        },
        BackgroundTaskStatus.RUNNING: {
            BackgroundTaskStatus.COMPLETED,
            BackgroundTaskStatus.FAILED,
        },
        BackgroundTaskStatus.COMPLETED: set(),
        BackgroundTaskStatus.FAILED: set(),
    }

    def can_transition_to(self, target_status: BackgroundTaskStatus) -> bool:
        """
        Check if the task can transition to the target status.

        Args:
            target_status: The desired status to transition to

        Returns:
            True if the transition is valid, False otherwise
        """
        return target_status in self._VALID_TRANSITIONS.get(self.status, set())

    def transition_to(
        self,
        target_status: BackgroundTaskStatus,
        timestamp: datetime,
        error: Optional[str] = None,
        result: Optional[dict] = None,
    ) -> None:
        """
        Transition the task to a new status with validation.

        Updates timestamps and additional data (error/result) as appropriate
        for the target status.

        Args:
            target_status: The status to transition to
            timestamp: Current timestamp for setting started_at/completed_at
            error: Error message if transitioning to FAILED
            result: Result data if transitioning to COMPLETED

        Raises:
            InvalidStateTransitionError: If the transition is not valid
        """
        if not self.can_transition_to(target_status):
            raise InvalidStateTransitionError(
                f"Cannot transition task from {self.status.value} to" f" {target_status.value}"
            )

        self.status = target_status
        if target_status == BackgroundTaskStatus.RUNNING:
            self.started_at = timestamp
        elif target_status in (
            BackgroundTaskStatus.COMPLETED,
            BackgroundTaskStatus.FAILED,
        ):
            self.completed_at = timestamp

        self.error = error
        self.result = result


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

    @property
    def sections(self) -> dict[str, dict[str, Any]]:
        """
        Get all configuration sections as a dict.

        Returns:
            Dictionary with section names as keys and section dicts as values
        """
        result = {
            "server": self.server,
            "database": self.database,
            "llm": self.llm,
            "nlp": self.nlp,
            "embedding": self.embedding,
            "reference_sources": self.reference_sources,
            "logging": self.logging,
        }
        if self.sync is not None:
            result["sync"] = self.sync
        return result


@dataclass
class DatasetMetrics:
    """
    Aggregated metrics about a dataset's contents.

    These are computed on import and cached; they should be refreshed
    after large import operations.
    """

    layers_count: int = 0
    domains_count: int = 0
    terms_count: int = 0
    relationships_count: int = 0
    individuals_count: int = 0


@dataclass
class Dataset:
    """
    Represents an importable or imported dataset (SQLite database file).

    Attributes:
        id: Unique identifier (UUID as string)
        title: Display name for the dataset
        filename: Original filename (e.g., 'production_2024.db')
        description: Optional longer description
        created_at: Timestamp of creation
        last_accessed: Timestamp of last import/activation
        schema_version: Database schema version (for migration tracking)
        metrics: DatasetMetrics (layers, domains, terms, relationships counts)
        is_active: Whether this is the currently active dataset
        version: Version number for optimistic concurrency control
    """

    id: str
    title: str
    filename: str
    created_at: datetime
    last_accessed: datetime
    schema_version: str
    metrics: DatasetMetrics = field(default_factory=DatasetMetrics)
    is_active: bool = False
    description: Optional[str] = None
    version: int = 1

    def __post_init__(self) -> None:
        """Validate dataset invariants."""
        if not self.title or not self.title.strip():
            raise ValueError("Title cannot be empty")
        if not self.filename or not self.filename.strip():
            raise ValueError("Filename cannot be empty")
        if not self.schema_version or not self.schema_version.strip():
            raise ValueError("Schema version cannot be empty")

    def rename(self, new_title: str) -> None:
        """Rename the dataset."""
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.last_accessed = datetime.now(timezone.utc)

    def mark_accessed(self) -> None:
        """Update last_accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)
