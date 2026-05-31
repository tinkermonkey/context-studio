"""
Port interfaces (protocols) for the Pipeline Management bounded context.

Ports define contracts for external adapters (persistence, embedding, events, etc.).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    def list_by_batch_id(self, batch_id: str) -> PipelineRunList:
        """
        List all pipeline runs in a specific batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of domain entities
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
