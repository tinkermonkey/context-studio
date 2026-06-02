"""
Port interfaces (protocols) for the Pipeline Management bounded context.

Ports define contracts for external adapters (persistence, embedding, events, etc.).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from .entities import Batch, BatchStatus, PipelineRun, PipelineRunStatus, PipelineType

# ============================================================================
# LLM provider value types and port
# ============================================================================


@dataclass(frozen=True)
class LLMResponse:
    """
    Response from an LLM completion request.

    Attributes:
        content: The generated text response
        tokens_in: Count of input tokens consumed
        tokens_out: Count of output tokens generated
        duration_ms: Time spent processing the request in milliseconds
        finish_reason: Reason the model stopped (e.g., 'stop', 'length')
        model: Name of the model that generated the response
    """

    content: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str
    model: str


class LLMProvider(Protocol):
    """Port for LLM completion and model introspection."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """Request a completion from an LLM."""
        ...

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        """Request a completion from an LLM (async version)."""
        ...

    def is_model_available(self, model: str) -> bool:
        """Check if a specific model is available."""
        ...

    def list_available_models(self) -> list[str]:
        """Get list of available model identifiers."""
        ...


class TripleExtractionResult(Protocol):
    """
    Result returned by ExtractionPort.extract_triples().

    Matches the shape of domain.extraction.entities.TripleExtractionResult
    without importing it, breaking the cross-context dependency.
    """

    triples: list[dict]
    warnings: list[str]
    metadata: dict[str, Any]


class ExtractionPort(Protocol):
    """
    Port describing what the pipelines context needs from the extraction context.

    Decouples IndividualExtractionOrchestrator from the concrete ExtractionService.
    Any object that exposes extract_triples() with this signature satisfies the protocol.
    """

    def extract_triples(
        self,
        text: str,
        ontology_id: str,
        model: str,
        temperature: float,
    ) -> TripleExtractionResult:
        """Extract RDF triples from text scoped to a specific ontology."""
        ...


PipelineRunList = list[PipelineRun]
BatchList = list[Batch]
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
        configuration_slug: str,
        configuration_version: int,
        specific_data: dict[str, Any] | None = None,
    ) -> PipelineRun:
        """
        Create a new pipeline run and persist it.

        Args:
            batch_run_id: ID of the batch this run belongs to
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            configuration_ref: Configuration reference (the full ref)
            configuration_slug: Configuration slug part
            configuration_version: Configuration version part
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

        When status is PENDING, implementations must ensure failure_reason is cleared to maintain
        the invariant that failure_reason is None when status is PENDING.

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

    def list_by_batch_id(self, batch_id: str) -> PipelineRunList:
        """
        List all pipeline runs in a specific batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of domain entities
        """
        ...

    def list_filtered(
        self,
        pipeline_type: PipelineType | None = None,
        status: PipelineRunStatus | None = None,
        implementation_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[PipelineRunList, int]:
        """
        List pipeline runs with DB-level filtering and pagination.

        Args:
            pipeline_type: Filter by pipeline type
            status: Filter by status
            implementation_id: Filter by implementation ID
            start_date: Include only runs created on or after this UTC datetime
            end_date: Include only runs created on or before this UTC datetime
            limit: Maximum number of rows to return
            offset: Number of rows to skip (for pagination)

        Returns:
            Tuple of (page of domain entities, total matching count)
        """
        ...

    def update_running_status(self, run_id: str, started_at: datetime) -> bool:
        """
        Atomically update status to RUNNING and set started_at timestamp.

        Args:
            run_id: Pipeline run ID
            started_at: Started timestamp

        Returns:
            True if updated, False if not found
        """
        ...

    def update_failure_info(
        self,
        run_id: str,
        failure_reason: str,
        output_summary: dict[str, Any] | None = None,
    ) -> bool:
        """
        Atomically update status to FAILED, set failure_reason, and optionally
        update output_summary.

        Args:
            run_id: Pipeline run ID
            failure_reason: Failure reason string
            output_summary: Output metadata dict (optional)

        Returns:
            True if updated, False if not found
        """
        ...

    def update_started_at(self, run_id: str, started_at: datetime) -> bool:
        """
        Update a pipeline run's started_at timestamp.

        Args:
            run_id: Pipeline run ID
            started_at: Started timestamp

        Returns:
            True if updated, False if not found
        """
        ...

    def update_failure_reason(self, run_id: str, failure_reason: str) -> bool:
        """
        Update a pipeline run's failure_reason.

        Args:
            run_id: Pipeline run ID
            failure_reason: Failure reason string

        Returns:
            True if updated, False if not found
        """
        ...


class BatchRepository(Protocol):
    """
    Port for persisting and retrieving batch entities.

    Handles batch lifecycle management, including creation, status updates,
    and retrieval of batch-level information.
    """

    def create(self) -> Batch:
        """
        Create a new batch and persist it.

        Returns:
            Domain entity with status=PENDING
        """
        ...

    def get(self, batch_id: str) -> Batch | None:
        """
        Retrieve a batch by ID.

        Args:
            batch_id: Batch ID

        Returns:
            Domain entity if found, None otherwise
        """
        ...

    def list(self) -> BatchList:
        """
        List all batches.

        Returns:
            List of all domain entities
        """
        ...

    def list_by_status(self, status: BatchStatus) -> BatchList:
        """
        List all batches with a specific status.

        Args:
            status: BatchStatus to filter by

        Returns:
            List of domain entities
        """
        ...

    def update_status(self, batch_id: str, status: BatchStatus) -> bool:
        """
        Update a batch's status.

        Args:
            batch_id: Batch ID
            status: New status

        Returns:
            True if updated, False if not found
        """
        ...

    def update_started_at(self, batch_id: str) -> bool:
        """
        Update a batch's started_at timestamp (PENDING -> RUNNING transition).

        Args:
            batch_id: Batch ID

        Returns:
            True if updated, False if not found
        """
        ...

    def update_completed_at(self, batch_id: str) -> bool:
        """
        Update a batch's completed_at timestamp (terminal state transition).

        Args:
            batch_id: Batch ID

        Returns:
            True if updated, False if not found
        """
        ...

    def compute_aggregate_status(self, batch_id: str) -> BatchStatus:
        """
        Compute batch status from child pipeline runs.

        Batch status priority (when all runs are terminal):
        1. COMPLETED: At least one run is COMPLETED
        2. CANCELLED: No runs COMPLETED, but at least one CANCELLED
        3. FAILED: All runs are FAILED

        Batch status transitions:
        - PENDING: No child runs started yet, or all runs still PENDING
        - RUNNING: At least one run is RUNNING
        - COMPLETED: All runs terminal, at least one COMPLETED (highest priority)
        - CANCELLED: All runs terminal, no COMPLETED, at least one CANCELLED
        - FAILED: All runs terminal, all FAILED (lowest priority)

        Args:
            batch_id: Batch ID

        Returns:
            Computed BatchStatus (does not update database)
        """
        ...

    def get_run_counts(self, batch_id: str) -> dict[str, int]:
        """
        Get count of runs in each status for a batch.

        Args:
            batch_id: Batch ID

        Returns:
            Dict with keys: pending, running, completed, failed, cancelled
        """
        ...


class PipelineRunStatusWriter(Protocol):
    """Port for writing pipeline run status to persistence.

    Narrower interface than PipelineRunRepository — orchestrators use this
    to update run status at the start of execution without depending on the
    full repository contract.
    """

    def update_running_status(self, run_id: str, started_at: datetime) -> bool:
        """Update run status to RUNNING with started_at timestamp."""
        ...
