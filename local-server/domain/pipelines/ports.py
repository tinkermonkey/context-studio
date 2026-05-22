"""
Port interfaces (protocols) for the Pipeline Management bounded context.

Ports define contracts for external adapters (persistence, embedding, events, etc.).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Any, Protocol

from .entities import PipelineRun, PipelineRunStatus, PipelineType

PipelineRunList = list[PipelineRun]
ChangeEventDictList = list[dict[str, Any]]


class PipelineRunRepository(Protocol):
    """
    Port for persisting and retrieving pipeline run entities.

    Handles all data access for pipeline runs, including creation, updates,
    status queries, and change_events correlation.
    """

    def create(
        self,
        batch_run_id: str,
        pipeline_type: PipelineType,
        implementation_id: str,
        configuration_ref: str,
        specific_data: dict[str, Any] | None = None,
    ) -> PipelineRun:
        """
        Create a new pipeline run and persist it.

        Args:
            batch_run_id: ID of the existing batch_run
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            configuration_ref: Configuration reference
            specific_data: Type-specific fields

        Returns:
            Domain entity
        """
        ...

    def get(self, run_id: str) -> PipelineRun | None:
        """
        Retrieve a pipeline run by ID.

        Args:
            run_id: Pipeline run ID

        Returns:
            Domain entity if found, None otherwise
        """
        ...

    def list(self) -> PipelineRunList:
        """
        List all pipeline runs.

        Returns:
            List of all domain entities
        """
        ...

    def list_by_status(self, status: PipelineRunStatus) -> PipelineRunList:
        """
        List all pipeline runs with a specific status.

        Args:
            status: PipelineRunStatus to filter by

        Returns:
            List of domain entities
        """
        ...

    def list_by_type(self, pipeline_type: PipelineType) -> PipelineRunList:
        """
        List all pipeline runs of a specific type.

        Args:
            pipeline_type: PipelineType to filter by

        Returns:
            List of domain entities
        """
        ...

    def update_status(self, run_id: str, status: PipelineRunStatus) -> bool:
        """
        Update a pipeline run's status.

        Args:
            run_id: Pipeline run ID
            status: New status

        Returns:
            True if updated, False if not found
        """
        ...

    def update_summaries(
        self,
        run_id: str,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        llm_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update pipeline run summaries and metadata.

        Args:
            run_id: Pipeline run ID
            input_summary: Input metadata dict
            output_summary: Output counts/metrics dict
            llm_metadata: LLM metadata dict

        Returns:
            True if updated, False if not found
        """
        ...

    def get_change_events_for_run(self, run_id: str) -> ChangeEventDictList:
        """
        Get all change_events correlated with a pipeline run via batch_run_id.

        Args:
            run_id: Pipeline run ID

        Returns:
            List of change_event dicts
        """
        ...
