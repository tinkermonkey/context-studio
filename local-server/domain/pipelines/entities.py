"""
Domain entities for the LLM Pipeline Management bounded context.

PipelineRun and its per-type subclasses represent execution records for
knowledge extraction and refinement pipelines. They use inheritance to
share common fields while maintaining type-specific fields.

Architectural note: These entities are immutable (frozen dataclasses).
State transitions are represented by constructing new instances; the
repository manages persistence. Pipeline runs produce audit records
(change_events) that are individually revertable; the run itself is
not rolled back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class PipelineRunStatus(str, Enum):
    """Status of a pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchStatus(str, Enum):
    """Status of a batch."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineType(str, Enum):
    """Enumeration of pipeline types."""

    NO_OP = "no_op"
    INDIVIDUAL_EXTRACTION = "individual_extraction"
    SCHEMA_EXTRACTION = "schema_extraction"
    SCHEMA_NODE_GROUNDING = "schema_node_grounding"
    SCHEMA_NODE_DEFINITION_REFINEMENT = "schema_node_definition_refinement"
    SCHEMA_NODE_CONNECTION_REFINEMENT = "schema_node_connection_refinement"


@dataclass(frozen=True)
class Batch:
    """
    Domain entity for a batch of pipeline runs.

    A batch is a container for one or more pipeline runs, providing lifecycle
    management and aggregated status. Each batch has its own UUID identity,
    independent of any single run. A batch transitions through states as its
    child runs complete, fail, or are cancelled.

    Attributes:
        id: Unique identifier (UUID as string)
        status: Current batch status (pending | running | completed | failed | cancelled)
        created_at: UTC timestamp of batch creation
        started_at: UTC timestamp when transitioned to RUNNING (None if not started)
        completed_at: UTC timestamp when transitioned to terminal state (None if not done)
        last_updated: UTC timestamp of last status change or run update
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    status: BatchStatus = BatchStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, created_at: datetime | None = None) -> "Batch":
        """Create a new batch with status=PENDING."""
        now = created_at or datetime.now(timezone.utc)
        return cls(
            id=str(uuid4()),
            status=BatchStatus.PENDING,
            created_at=now,
            last_updated=now,
        )


@dataclass(frozen=True)
class PipelineRun:
    """
    Base domain entity for all pipeline runs.

    Tracks a pipeline execution from inception through completion,
    recording the pipeline type, implementation, configuration,
    and LLM metadata. This entity is immutable once constructed.

    A pipeline run belongs to a batch (identified by batch_id), which provides
    lifecycle management and status aggregation across multiple runs.

    Attributes:
        id: Unique identifier (UUID as string)
        batch_run_id: Batch identifier (FK to batches.id)
        pipeline_type: Discriminator (individual_extraction | schema_extraction | ...)
        implementation_id: Reference to registered implementation
        configuration_ref: Primary user-facing configuration identifier
        configuration_slug: Configuration slug part (non-null, immutable; used with
            configuration_version to uniquely identify a pinned configuration)
        configuration_version: Configuration version part (non-null, immutable; used with
            configuration_slug to uniquely identify a pinned configuration)
        input_summary: JSON dict with input metadata (small)
        output_summary: JSON dict with output counts and metrics
        llm_metadata: JSON dict with model, tokens_used, duration_ms
        status: Current status (pending | running | completed | failed | cancelled)
        created_at: UTC timestamp of run creation
        started_at: UTC timestamp when run actually started executing (RUNNING status)
        failure_reason: String description of failure reason if status=FAILED
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    batch_run_id: str = ""
    pipeline_type: PipelineType = PipelineType.INDIVIDUAL_EXTRACTION
    implementation_id: str = ""
    configuration_ref: str = ""
    configuration_slug: str = ""
    configuration_version: int = 1
    input_summary: dict = field(default_factory=dict)
    output_summary: dict = field(default_factory=dict)
    llm_metadata: dict = field(default_factory=dict)
    status: PipelineRunStatus = PipelineRunStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.batch_run_id:
            raise ValueError("batch_run_id cannot be empty")
        if self.configuration_version <= 0:
            raise ValueError("configuration_version must be greater than 0")
        if self.status == PipelineRunStatus.PENDING and self.failure_reason is not None:
            raise ValueError(
                "status=PENDING is incompatible with a set failure_reason"
            )


@dataclass(frozen=True)
class NoOpPipelineRun(PipelineRun):
    """
    No-op pipeline execution record for testing.

    Exercises the full pipeline framework without domain logic:
    - Pipeline type and implementation registration
    - PipelineRun persistence
    - change_events linkage with batch_run_id

    This is used in functional tests to verify infrastructure and framework
    contracts before per-type implementations are added.
    """

    pipeline_type: PipelineType = field(default=PipelineType.NO_OP, init=False)


@dataclass(frozen=True)
class IndividualExtractionRun(PipelineRun):
    """
    Domain entity for individual text extraction operations.

    Migrated from Wave A's ExtractionRun; maintains backward compatibility
    with existing extraction pipeline configurations and results.

    Per-type fields:
        source_text_hash: SHA256 hash of extracted-from text (audit)
        source_document_uri: Optional URI/filename of the source document

    Inherits from PipelineRun:
        All pipeline-shared fields (pipeline_type, implementation_id, configuration_ref, etc.)
    """

    pipeline_type: PipelineType = field(default=PipelineType.INDIVIDUAL_EXTRACTION, init=False)
    source_text_hash: str = ""
    source_document_uri: str | None = None

    @classmethod
    def create(
        cls,
        id: str,
        batch_run_id: str,
        implementation_id: str,
        configuration_ref: str,
        configuration_slug: str,
        configuration_version: int,
        source_text_hash: str,
        source_document_uri: str | None = None,
        created_at: datetime | None = None,
    ) -> "IndividualExtractionRun":
        """
        Create a new IndividualExtractionRun with status=PENDING.

        Args:
            id: Unique identifier (UUID string)
            batch_run_id: FK to batches.id
            implementation_id: Implementation identifier
            configuration_ref: Configuration reference
            configuration_slug: Configuration slug part
            configuration_version: Configuration version part
            source_text_hash: SHA256 hash of source text
            source_document_uri: Optional document URI
            created_at: UTC timestamp (defaults to now)

        Returns:
            New IndividualExtractionRun with status=PENDING
        """
        return cls(
            id=id,
            batch_run_id=batch_run_id,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            configuration_slug=configuration_slug,
            configuration_version=configuration_version,
            input_summary={},
            output_summary={},
            llm_metadata={},
            status=PipelineRunStatus.PENDING,
            source_text_hash=source_text_hash,
            source_document_uri=source_document_uri,
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class SchemaExtractionRun(PipelineRun):
    """
    Domain entity for schema-level extraction operations.

    Per-type fields: (none at this stage; added in concrete implementation)

    Inherits from PipelineRun:
        All pipeline-shared fields
    """

    pipeline_type: PipelineType = field(default=PipelineType.SCHEMA_EXTRACTION, init=False)

    @classmethod
    def create(
        cls,
        id: str,
        batch_run_id: str,
        implementation_id: str,
        configuration_ref: str,
        configuration_slug: str,
        configuration_version: int,
        created_at: datetime | None = None,
    ) -> "SchemaExtractionRun":
        """Create a new SchemaExtractionRun with status=PENDING."""
        return cls(
            id=id,
            batch_run_id=batch_run_id,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            configuration_slug=configuration_slug,
            configuration_version=configuration_version,
            input_summary={},
            output_summary={},
            llm_metadata={},
            status=PipelineRunStatus.PENDING,
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class SchemaGroundingRun(PipelineRun):
    """
    Domain entity for schema node grounding operations.

    Per-type fields: (none at this stage; added in concrete implementation)

    Inherits from PipelineRun:
        All pipeline-shared fields
    """

    pipeline_type: PipelineType = field(default=PipelineType.SCHEMA_NODE_GROUNDING, init=False)

    @classmethod
    def create(
        cls,
        id: str,
        batch_run_id: str,
        implementation_id: str,
        configuration_ref: str,
        configuration_slug: str,
        configuration_version: int,
        created_at: datetime | None = None,
    ) -> "SchemaGroundingRun":
        """Create a new SchemaGroundingRun with status=PENDING."""
        return cls(
            id=id,
            batch_run_id=batch_run_id,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            configuration_slug=configuration_slug,
            configuration_version=configuration_version,
            input_summary={},
            output_summary={},
            llm_metadata={},
            status=PipelineRunStatus.PENDING,
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class SchemaDefinitionRefinementRun(PipelineRun):
    """
    Domain entity for schema node definition refinement operations.

    Per-type fields: (none at this stage; added in concrete implementation)

    Inherits from PipelineRun:
        All pipeline-shared fields
    """

    pipeline_type: PipelineType = field(
        default=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT, init=False
    )

    @classmethod
    def create(
        cls,
        id: str,
        batch_run_id: str,
        implementation_id: str,
        configuration_ref: str,
        configuration_slug: str,
        configuration_version: int,
        created_at: datetime | None = None,
    ) -> "SchemaDefinitionRefinementRun":
        """Create a new SchemaDefinitionRefinementRun with status=PENDING."""
        return cls(
            id=id,
            batch_run_id=batch_run_id,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            configuration_slug=configuration_slug,
            configuration_version=configuration_version,
            input_summary={},
            output_summary={},
            llm_metadata={},
            status=PipelineRunStatus.PENDING,
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class SchemaConnectionRefinementRun(PipelineRun):
    """
    Domain entity for schema node connection refinement operations.

    Per-type fields: (none at this stage; added in concrete implementation)

    Inherits from PipelineRun:
        All pipeline-shared fields
    """

    pipeline_type: PipelineType = field(
        default=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT, init=False
    )

    @classmethod
    def create(
        cls,
        id: str,
        batch_run_id: str,
        implementation_id: str,
        configuration_ref: str,
        configuration_slug: str,
        configuration_version: int,
        created_at: datetime | None = None,
    ) -> "SchemaConnectionRefinementRun":
        """Create a new SchemaConnectionRefinementRun with status=PENDING."""
        return cls(
            id=id,
            batch_run_id=batch_run_id,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            configuration_slug=configuration_slug,
            configuration_version=configuration_version,
            input_summary={},
            output_summary={},
            llm_metadata={},
            status=PipelineRunStatus.PENDING,
            created_at=created_at or datetime.now(timezone.utc),
        )
