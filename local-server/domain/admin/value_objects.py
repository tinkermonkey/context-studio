"""Value objects and enums for the System Administration bounded context."""

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
