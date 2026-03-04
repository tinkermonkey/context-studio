"""
Port interfaces for the Pipeline bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol, Optional, Sequence

from domain.pipeline.entities import PipelineConfiguration, Execution


class PipelineRepository(Protocol):
    """Repository port for managing pipeline configurations and executions."""

    def get_configuration(self, pipeline_id: str) -> Optional[PipelineConfiguration]:
        """Retrieve a pipeline configuration by ID."""
        ...

    def list_configurations(self) -> Sequence[PipelineConfiguration]:
        """List all pipeline configurations."""
        ...

    def save_configuration(
        self, config: PipelineConfiguration
    ) -> PipelineConfiguration:
        """Save or update a pipeline configuration."""
        ...

    def record_execution(self, execution: Execution) -> Execution:
        """Record a pipeline execution."""
        ...

    def get_execution(self, execution_id: str) -> Optional[Execution]:
        """Retrieve a pipeline execution by ID."""
        ...
