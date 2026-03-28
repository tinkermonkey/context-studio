"""Fake in-memory implementation of PipelineRepository for testing."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.pipeline.entities import Execution, PipelineConfiguration


class FakePipelineRepository:
    """In-memory repository for pipeline configurations and executions."""

    def __init__(self) -> None:
        self._configs: dict[str, PipelineConfiguration] = {}
        self._executions: dict[str, list[Execution]] = {}

    def get_config(self, config_id: str) -> PipelineConfiguration | None:
        """
        Retrieve a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration

        Returns:
            PipelineConfiguration if found, None otherwise
        """
        return self._configs.get(config_id)

    def list_configs(self, enabled_only: bool = False) -> list[PipelineConfiguration]:
        """
        List all pipeline configurations.

        Args:
            enabled_only: If True, return only enabled configurations

        Returns:
            List of PipelineConfiguration objects
        """
        configs = list(self._configs.values())
        if enabled_only:
            configs = [c for c in configs if c.enabled]
        return configs

    def save_config(self, config: PipelineConfiguration) -> PipelineConfiguration:
        """
        Create or update a pipeline configuration.

        Args:
            config: PipelineConfiguration to save

        Returns:
            The saved PipelineConfiguration
        """
        self._configs[config.id] = config
        return config

    def delete_config(self, config_id: str) -> bool:
        """
        Delete a pipeline configuration by ID.

        Args:
            config_id: Unique identifier of the configuration

        Returns:
            True if deleted, False if not found
        """
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False

    def record_execution(self, execution: Execution) -> Execution:
        """
        Record a pipeline execution.

        Args:
            execution: Execution record to store

        Returns:
            The recorded Execution
        """
        config_id = execution.pipeline_config_id
        if config_id not in self._executions:
            self._executions[config_id] = []
        self._executions[config_id].append(execution)
        return execution

    def get_executions(self, pipeline_config_id: str, limit: int = 50) -> list[Execution]:
        """
        Retrieve execution history for a pipeline configuration.

        Returns results in reverse chronological order (most recent first).

        Args:
            pipeline_config_id: ID of the pipeline configuration
            limit: Maximum number of execution records to return

        Returns:
            List of Execution objects, up to limit
        """
        executions = self._executions.get(pipeline_config_id, [])
        # Sort by timestamp descending (most recent first)
        sorted_executions = sorted(executions, key=lambda e: e.timestamp, reverse=True)
        return sorted_executions[:limit]
