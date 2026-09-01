"""
Port interfaces for the Pipeline bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""

from collections.abc import Sequence
from typing import Protocol

from domain.pipeline.entities import Execution, PipelineConfiguration


class PipelineRepository(Protocol):
    """Repository for pipeline configurations and execution logs."""

    def get_config(self, config_id: str) -> PipelineConfiguration | None:
        """Retrieve a pipeline configuration by ID."""
        ...

    def list_configs(
        self, pipeline: str | None = None, enabled_only: bool = False
    ) -> Sequence[PipelineConfiguration]:
        """List pipeline configurations with optional filtering."""
        ...

    def save_config(self, config: PipelineConfiguration) -> PipelineConfiguration:
        """Save or update a pipeline configuration."""
        ...

    def delete_config(self, config_id: str) -> bool:
        """Delete a pipeline configuration. Return True if deleted, False if not found."""
        ...

    def record_execution(self, execution: Execution) -> Execution:
        """Record a pipeline execution."""
        ...

    def get_executions(
        self, pipeline_config_id: str, limit: int = 50
    ) -> Sequence[Execution]:
        """Retrieve execution records for a pipeline configuration."""
        ...
