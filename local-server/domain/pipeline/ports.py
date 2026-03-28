"""
Port interfaces (protocols) for the LLM Pipeline Management bounded context.

PipelineRepository defines the contract for persisting and retrieving pipeline
configurations and execution records. Using typing.Protocol enables structural
subtyping — implementations do not explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Protocol

from .entities import Execution, PipelineConfiguration


class PipelineRepository(Protocol):
    """
    Port for persisting and retrieving pipeline configurations and executions.

    The PipelineRepository handles all data access for pipeline management,
    including configuration lifecycle (CRUD) and execution history tracking.
    """

    def get_config(self, config_id: str) -> PipelineConfiguration | None:
        """
        Retrieve a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration

        Returns:
            PipelineConfiguration if found, None otherwise
        """
        ...

    def list_configs(self, enabled_only: bool = False) -> list[PipelineConfiguration]:
        """
        List all pipeline configurations.

        Args:
            enabled_only: If True, return only enabled configurations (default False)

        Returns:
            List of PipelineConfiguration objects
        """
        ...

    def save_config(self, config: PipelineConfiguration) -> PipelineConfiguration:
        """
        Create or update a pipeline configuration.

        If the configuration's ID already exists, it is updated.
        Otherwise, a new configuration is created.

        Args:
            config: PipelineConfiguration to save

        Returns:
            The saved PipelineConfiguration
        """
        ...

    def delete_config(self, config_id: str) -> bool:
        """
        Delete a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration to delete

        Returns:
            True if deletion was successful, False if configuration was not found
        """
        ...

    def record_execution(self, execution: Execution) -> Execution:
        """
        Record a pipeline execution.

        Args:
            execution: Execution record to store

        Returns:
            The recorded Execution
        """
        ...

    def get_executions(self, pipeline_config_id: str, limit: int = 50) -> list[Execution]:
        """
        Retrieve execution history for a pipeline configuration.

        Results are returned in reverse chronological order (most recent first).

        Args:
            pipeline_config_id: ID of the pipeline configuration
            limit: Maximum number of execution records to return (default 50)

        Returns:
            List of Execution objects, up to limit
        """
        ...
