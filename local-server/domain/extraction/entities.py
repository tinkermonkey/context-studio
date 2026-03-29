"""
Extraction domain entities.

Mutable dataclasses representing the core domain model for knowledge extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.extraction.value_objects import ExtractionLayerResult


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


@dataclass
class ExtractionLayer:
    """
    A first-class domain entity representing an extraction layer.

    Extraction layers are the core components of the extraction pipeline.
    Each layer has identity (layer_number), behavior (execute as a callable),
    and metadata describing its purpose and constraints.

    Attributes:
        layer_number: Numeric identifier for the layer (0–3)
        name: Human-readable name of the layer
        description: Purpose and role of this layer in the extraction pipeline
        min_confidence: Minimum confidence threshold for results from this layer
        enabled: Whether this layer participates in extraction
    """
    layer_number: int
    name: str
    description: str = ""
    min_confidence: float = 0.0
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate extraction layer invariants."""
        if not 0 <= self.layer_number <= 3:
            raise ValueError(f"layer_number must be 0-3, got {self.layer_number}")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be 0.0-1.0, got {self.min_confidence}")


@dataclass
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
    """
    layer_name: str
    duration_ms: int
    tokens_processed: int = 0
    entities_found: int = 0
    relationships_found: int = 0
    error_count: int = 0
    skipped_count: int = 0


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
            raise ValueError(f"total_duration_ms must be non-negative, got {self.total_duration_ms}")
