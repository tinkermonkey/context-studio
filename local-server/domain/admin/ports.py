"""
Port interfaces (protocols) for the System Administration bounded context.

Ports define contracts for external adapters (configuration storage, metrics collection).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Protocol

from .entities import SystemHealth, AppConfiguration


class MetricsCollector(Protocol):
    """
    Port for collecting system health metrics.

    Implementations should gather real-time information about system state:
    database connectivity, pipeline readiness, model loading status, etc.
    """

    def collect_health(self) -> SystemHealth:
        """
        Collect current system health metrics.

        Returns:
            SystemHealth object with current system state
        """
        ...


class ConfigurationStore(Protocol):
    """
    Port for persisting and retrieving application configuration.

    Implementations handle loading configuration from files or other
    storage, and saving configuration changes.
    """

    def load(self) -> AppConfiguration:
        """
        Load application configuration.

        Returns:
            AppConfiguration object with all configuration sections
        """
        ...

    def save(self, config: AppConfiguration) -> None:
        """
        Save application configuration.

        Args:
            config: AppConfiguration object to persist
        """
        ...
