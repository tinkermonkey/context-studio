"""Value objects and enums for the System Administration bounded context."""

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


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


@dataclass(frozen=True)
class DatabaseHealth:
    """
    Health status of the database component.

    Attributes:
        connected: Whether database is accessible
        issues: Tuple of issues encountered, if any
    """

    connected: bool
    issues: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ServiceMetrics:
    """
    Metrics about system services and availability.

    Attributes:
        uptime_seconds: System uptime in seconds since startup
        llm_providers_available: Tuple of available LLM provider names
    """

    uptime_seconds: float
    llm_providers_available: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComponentStatus:
    """
    Health status of an individual system component.

    Attributes:
        available: Whether the component is available/ready
        details: Human-readable detail about the component status
    """

    available: bool
    details: str = ""


def _make_empty_mapping_proxy() -> MappingProxyType:
    """Create an empty MappingProxyType for default factory."""
    return MappingProxyType({})


@dataclass(frozen=True)
class BackgroundTaskSummary:
    """
    Summary of background task execution status.

    Attributes:
        by_status: Immutable mapping of task counts grouped by status
    """

    by_status: MappingProxyType = field(default_factory=_make_empty_mapping_proxy)

    @property
    def total(self) -> int:
        """Total number of background tasks, computed from by_status counts."""
        return sum(self.by_status.values())
