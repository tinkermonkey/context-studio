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


CREDENTIAL_FIELD_NAMES = frozenset(
    {
        "openai_api_key",
        "anthropic_api_key",
        "s3_access_key",
        "s3_secret_key",
    }
)


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
class DemoDatasetDescriptor:
    """
    Metadata describing a demo dataset users can load into a fresh workspace.

    Attributes:
        name: Stable machine-readable name (e.g., 'software-architecture').
        title: Human-readable title.
        description: One-paragraph description of the dataset and its purpose.
        paper_count: Number of paper fixtures that back the canon.
        taxonomy_count: Number of top-level taxonomies the dataset will create.
        class_count: Number of classes the dataset will materialize.
    """

    name: str
    title: str
    description: str
    paper_count: int
    taxonomy_count: int
    class_count: int


@dataclass(frozen=True)
class LoadResult:
    """
    Counts of entities persisted by a demo dataset load.

    Attributes:
        dataset_name: Stable name of the dataset that was loaded.
        source_run_id: Synthetic provenance id stamped on every entity created
            during the load (e.g., 'demo:software-architecture:<uuid>').
        taxonomies: Number of taxonomies created.
        concept_schemes: Number of concept schemes created.
        classes: Number of classes created.
        property_definitions: Number of property definitions created.
        individuals: Number of individuals created.
        relationships: Number of relationships created.
        external_references: Number of external references attached.
    """

    dataset_name: str
    source_run_id: str
    taxonomies: int
    concept_schemes: int
    classes: int
    property_definitions: int
    individuals: int
    relationships: int
    external_references: int


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
