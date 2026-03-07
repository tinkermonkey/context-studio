"""
Port interfaces for the Admin bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol

from domain.admin.entities import AppConfiguration


class ConfigurationStore(Protocol):
    """Store for application configuration."""

    def get_config(self) -> AppConfiguration:
        """Get the current application configuration."""
        ...

    def update_config(self, updates: dict) -> AppConfiguration:
        """Update configuration with partial updates and return the new configuration."""
        ...

    def reset_to_defaults(self) -> AppConfiguration:
        """Reset configuration to defaults and return the new configuration."""
        ...


class MetricsCollector(Protocol):
    """Collects system and application metrics."""

    def get_database_health(self) -> dict:
        """Get database health metrics (size, query performance, etc.)."""
        ...

    def get_service_metrics(self) -> dict:
        """Get service-level metrics (request counts, latencies, etc.)."""
        ...

    def get_embedding_model_status(self) -> dict:
        """Get embedding model status and performance."""
        ...

    def get_nlp_pipeline_status(self) -> dict:
        """Get NLP pipeline status and performance."""
        ...

    def get_background_task_summary(self) -> dict:
        """Get summary of background task execution."""
        ...
