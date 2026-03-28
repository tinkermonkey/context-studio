"""
Extraction domain entities.

Mutable dataclasses representing the core domain model for knowledge extraction.
"""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


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
        uri: Optional URI linking to external knowledge base
        description: Optional free-text description
        properties: Optional key-value metadata associated with the entity
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    label: str = ""
    entity_type: str = ""
    source_layer: int = 0
    confidence: float = 0.0
    uri: str | None = None
    description: str | None = None
    properties: dict = field(default_factory=dict)


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
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    text: str = ""
    extracted_entities: list[ExtractedEntity] = field(default_factory=list)
    layers_executed: list = field(default_factory=list)  # list[ExtractionLayerResult]
    total_duration_ms: int = 0
    created_at: datetime = field(default_factory=datetime.now)
