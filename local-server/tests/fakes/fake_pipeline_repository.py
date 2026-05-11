"""Fake in-memory implementation of PipelineRepository for testing."""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.pipeline.entities import Execution, PipelineConfiguration, PipelineFlavor
from domain.pipeline.ports import ExecutionWithTitle


class FakePipelineRepository:
    """In-memory repository for pipeline configurations and executions."""

    def __init__(self) -> None:
        self._configs: dict[str, PipelineConfiguration] = {}
        self._executions: dict[str, list[Execution]] = {}
        self._flavors: dict[str, PipelineFlavor] = {}

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

    def get_executions(
        self, pipeline_config_id: str, limit: int = 50
    ) -> list[Execution]:
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

    def get_all_executions(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ExecutionWithTitle], int]:
        """
        Retrieve execution history across all pipeline configurations.

        Returns results in reverse chronological order (most recent first).
        Only includes executions whose pipeline configurations exist.

        Args:
            status: Optional status filter ("success", "error", "timeout")
            limit: Maximum number of execution records to return
            offset: Number of execution records to skip for pagination

        Returns:
            Tuple of (list of ExecutionWithTitle objects, total count)
        """
        all_executions = []
        for config_id, executions in self._executions.items():
            config = self._configs.get(config_id)
            if config:
                for execution in executions:
                    if status is None or execution.status == status:
                        all_executions.append(
                            ExecutionWithTitle(execution=execution, pipeline_title=config.title)
                        )

        sorted_executions = sorted(
            all_executions, key=lambda x: x.execution.timestamp, reverse=True
        )
        total = len(sorted_executions)
        paginated = sorted_executions[offset : offset + limit]

        return paginated, total

    def get_flavor(self, flavor_id: str) -> PipelineFlavor | None:
        """
        Retrieve a pipeline flavor by ID.

        Args:
            flavor_id: Unique identifier of the flavor

        Returns:
            PipelineFlavor if found, None otherwise
        """
        return self._flavors.get(flavor_id)

    def list_flavors(self) -> list[PipelineFlavor]:
        """
        List all pipeline flavors.

        Returns:
            List of PipelineFlavor objects
        """
        return list(self._flavors.values())

    def save_flavor(self, flavor: PipelineFlavor) -> PipelineFlavor:
        """
        Create or update a pipeline flavor.

        Args:
            flavor: PipelineFlavor to save

        Returns:
            The saved PipelineFlavor
        """
        self._flavors[flavor.id] = flavor
        return flavor

    def delete_flavor(self, flavor_id: str) -> bool:
        """
        Delete a pipeline flavor by ID.

        Args:
            flavor_id: Unique identifier of the flavor

        Returns:
            True if deleted, False if not found
        """
        if flavor_id in self._flavors:
            del self._flavors[flavor_id]
            return True
        return False
