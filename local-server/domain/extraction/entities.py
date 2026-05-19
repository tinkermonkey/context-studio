"""
Extraction domain entities.

Immutable dataclasses representing the core domain model for knowledge extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from domain.extraction.value_objects import ExtractionLayerResult


class ExtractionRunStatus(str, Enum):
    """
    Status of an extraction run.

    Unlike ImportRunStatus (which has ROLLED_BACK), ExtractionRunStatus
    is simpler: extraction produces candidate triples that are individually
    revertable via change_events. The run itself has no rollback operation.
    """

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExtractedEntity:
    """
    An entity extracted from text through one or more extraction layers.

    Attributes:
        id: Unique identifier for this extracted entity (UUID)
        label: The extracted entity label/name
        entity_type: Classification of the entity (e.g., PERSON, ORGANIZATION, LOCATION)
        source_layer: Which layer extracted this entity (0=KG, 1=LLM, 2=NLP, 3=reference)
        confidence: Confidence score from 0.0 to 1.0
        matched_class_id: Optional ID linking to an existing Class entity when resolved
        uri: Optional URI linking to external knowledge base
        description: Optional free-text description
        properties: Optional key-value metadata associated with the entity

    Raises:
        ValueError: If source_layer is not 0-3 or confidence is not 0.0-1.0
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    label: str = ""
    entity_type: str = ""
    source_layer: int = 0
    confidence: float = 0.0
    matched_class_id: str | None = None
    uri: str | None = None
    description: str | None = None
    properties: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate extracted entity invariants."""
        if not 0 <= self.source_layer <= 3:
            raise ValueError(f"source_layer must be 0-3, got {self.source_layer}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


@dataclass(frozen=True)
class ProcessingMetrics:
    """
    Metrics for an extraction layer or full extraction operation.

    Attributes:
        layer_name: Name of the layer or overall operation
        duration_ms: Time spent processing (milliseconds)
        tokens_processed: Total tokens processed
        entities_found: Number of entities found in this stage
        relationships_found: Number of relationships found in this stage
        error_count: Number of errors encountered
        skipped_count: Number of items skipped

    Raises:
        ValueError: If any metric is negative
    """

    layer_name: str
    duration_ms: int
    tokens_processed: int = 0
    entities_found: int = 0
    relationships_found: int = 0
    error_count: int = 0
    skipped_count: int = 0

    def __post_init__(self) -> None:
        """Validate processing metrics invariants."""
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be non-negative, got {self.duration_ms}")
        if self.tokens_processed < 0:
            raise ValueError(f"tokens_processed must be non-negative, got {self.tokens_processed}")
        if self.entities_found < 0:
            raise ValueError(f"entities_found must be non-negative, got {self.entities_found}")
        if self.relationships_found < 0:
            raise ValueError(
                "relationships_found must be non-negative, got" f" {self.relationships_found}"
            )
        if self.error_count < 0:
            raise ValueError(f"error_count must be non-negative, got {self.error_count}")
        if self.skipped_count < 0:
            raise ValueError(f"skipped_count must be non-negative, got {self.skipped_count}")


@dataclass
class ExtractionResult:
    """
    The complete output of an extraction operation.

    Attributes:
        id: Unique identifier for this extraction result (UUID)
        text: The source text that was extracted
        extracted_entities: Deduplicated list of extracted entities
        layers_executed: Execution details for each layer that ran
        total_duration_ms: Total time spent on extraction (milliseconds)
        created_at: Timestamp when extraction completed

    Raises:
        ValueError: If total_duration_ms is negative
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    text: str = ""
    extracted_entities: list[ExtractedEntity] = field(default_factory=list)
    layers_executed: list[ExtractionLayerResult] = field(default_factory=list)
    total_duration_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate extraction result invariants."""
        if self.total_duration_ms < 0:
            raise ValueError(
                f"total_duration_ms must be non-negative, got {self.total_duration_ms}"
            )


@dataclass(frozen=True)
class ExtractionRun:
    """
    First-class domain entity representing an extraction operation.

    Tracks an extraction operation from inception through completion,
    recording the pipeline configuration, LLM settings, resource metrics,
    and outcome counts. This entity is immutable once constructed. State
    transitions are represented by constructing new ExtractionRun instances
    with updated field values; the repository manages this lifecycle.

    ARCHITECTURAL NOTE: This entity MUST NOT have a rollback mechanism.
    Unlike ImportRun (which can be rolled back, undoing all changes),
    extraction produces candidate triples that are individually revertable
    via change_events in the versioning context. The ExtractionRun itself
    is a read-only audit record of what was extracted, not a reversible
    operation.

    This entity carries no reference to benchmark runs; that link belongs in
    the benchmark harness (see #698), not in the core data model.

    Attributes:
        id: Unique identifier (UUID as string)
        source_document_uri: Optional URI/filename of the source document
        source_text_hash: SHA256 hash of the extracted-from text (audit)
        pipeline_config_ref: Pipeline configuration slug (e.g., "extraction-default")
            Validation that this slug exists is deferred to the repository.
        model: LLM model name (e.g., "gpt-4", "claude-opus")
        temperature: Sampling temperature (0.0–2.0, typically 0.0–1.0)
        tokens_used: Total tokens consumed by the LLM call
        duration_ms: Total wall-clock execution time (milliseconds)
        triples_extracted: Count of triples returned by the LLM API
        triples_committed: Count of triples persisted after review
        status: Current status (pending, completed, failed)
            Status transitions are managed by the repository, not by this entity.
    """

    id: str
    source_document_uri: str | None
    source_text_hash: str
    pipeline_config_ref: str
    model: str
    temperature: float
    tokens_used: int
    duration_ms: int
    triples_extracted: int
    triples_committed: int
    status: ExtractionRunStatus

    def __post_init__(self) -> None:
        """Validate extraction run invariants."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {self.temperature}")
        if self.tokens_used < 0:
            raise ValueError(f"tokens_used must be non-negative, got {self.tokens_used}")
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be non-negative, got {self.duration_ms}")
        if self.triples_extracted < 0:
            raise ValueError(
                f"triples_extracted must be non-negative, got {self.triples_extracted}"
            )
        if self.triples_committed < 0:
            raise ValueError(
                f"triples_committed must be non-negative, got {self.triples_committed}"
            )
        if self.triples_committed > self.triples_extracted:
            raise ValueError(
                f"triples_committed ({self.triples_committed}) cannot exceed "
                f"triples_extracted ({self.triples_extracted})"
            )

    @staticmethod
    def create(
        id: str,
        source_document_uri: str | None,
        source_text_hash: str,
        pipeline_config_ref: str,
        model: str,
        temperature: float,
    ) -> ExtractionRun:
        """
        Create a new ExtractionRun with status=PENDING.

        The created run has all metrics zeroed; the repository will update
        these fields as the extraction completes.

        Args:
            id: Unique identifier (UUID string)
            source_document_uri: Optional document URI for audit trail
            source_text_hash: SHA256 hash of source text
            pipeline_config_ref: Pipeline configuration slug
            model: LLM model name
            temperature: Sampling temperature

        Returns:
            New ExtractionRun with status=PENDING, all metrics at 0

        Raises:
            ValueError: If temperature is invalid (not 0.0–2.0)
        """
        return ExtractionRun(
            id=id,
            source_document_uri=source_document_uri,
            source_text_hash=source_text_hash,
            pipeline_config_ref=pipeline_config_ref,
            model=model,
            temperature=temperature,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )


@dataclass
class TripleExtractionResult:
    """
    Result of triple extraction from text.

    Attributes:
        triples: List of extracted triple dictionaries
        warnings: List of warnings or validation issues encountered
        metadata: Extraction metadata (model, tokens_used, duration_ms)
    """

    triples: list[dict]
    warnings: list[str]
    metadata: dict[str, int | str]
