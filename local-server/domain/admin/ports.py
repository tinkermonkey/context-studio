"""
Port interfaces for the Admin bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol

from domain.admin.entities import AppConfiguration, SystemHealth


class ConfigurationStore(Protocol):
    """Store port for managing application configuration."""

    def load(self) -> AppConfiguration:
        """Load application configuration."""
        ...

    def save(self, config: AppConfiguration) -> None:
        """Save application configuration."""
        ...


class MetricsCollector(Protocol):
    """Collector port for recording and retrieving system metrics."""

    def record_latency(self, operation: str, duration_ms: float) -> None:
        """Record the latency of an operation."""
        ...

    def get_health(self) -> SystemHealth:
        """Get the current system health status."""
        ...
