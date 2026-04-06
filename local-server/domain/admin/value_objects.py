"""Value objects and enums for the System Administration bounded context."""

from dataclasses import dataclass, field
from enum import Enum


class SystemHealthStatus(str, Enum):
    """Valid states for system health."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BackgroundTaskStatus(str, Enum):
    """Valid states for background tasks."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


CREDENTIAL_FIELD_NAMES = frozenset({
    "openai_api_key",
    "anthropic_api_key",
    "s3_access_key",
    "s3_secret_key",
})


@dataclass
class DatabaseHealth:
    """
    Health status of the database component.

    Attributes:
        connected: Whether database is accessible
        issues: List of issues encountered, if any
    """

    connected: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class ServiceMetrics:
    """
    Metrics about system services and availability.

    Attributes:
        uptime_seconds: System uptime in seconds since startup
        llm_providers_available: List of available LLM provider names
    """

    uptime_seconds: float
    llm_providers_available: list[str] = field(default_factory=list)


@dataclass
class ComponentStatus:
    """
    Health status of an individual system component.

    Attributes:
        available: Whether the component is available/ready
        details: Human-readable detail about the component status
    """

    available: bool
    details: str = ""


@dataclass
class BackgroundTaskSummary:
    """
    Summary of background task execution status.

    Attributes:
        total: Total number of background tasks registered
        by_status: Count of tasks grouped by status
    """

    total: int
    by_status: dict[str, int] = field(default_factory=dict)
