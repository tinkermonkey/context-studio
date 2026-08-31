"""
Domain entities for the extraction bounded context.

Entities represent extracted information from text: entities, relationships,
and complete extraction results. They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.extraction.enums import EntityType, LayerName


@dataclass
class ExtractedEntity:
    """
    Represents an entity extracted from text.

    Attributes:
        text: The actual text of the extracted entity.
        entity_type: The type/classification of the entity (person, location, organization, concept).
        confidence: Confidence score between 0.0 and 1.0.
        start_pos: Starting character position in the source text.
        end_pos: Ending character position in the source text.
        suggested_class_id: Optional ID of a suggested Class to map this entity to.
    """

    text: str
    entity_type: EntityType
    confidence: float
    start_pos: int
    end_pos: int
    suggested_class_id: str | None = None

    def __post_init__(self) -> None:
        """Validate extracted entity invariants."""
        if not self.text or not isinstance(self.text, str):
            raise ValueError("ExtractedEntity text must be a non-empty string")
        if not isinstance(self.entity_type, EntityType):
            raise TypeError(
                f"entity_type must be an EntityType enum, got {type(self.entity_type).__name__}"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not (0.0 <= self.confidence <= 1.0)
        ):
            raise ValueError("confidence must be a number between 0.0 and 1.0")
        if (
            isinstance(self.start_pos, bool)
            or not isinstance(self.start_pos, int)
            or self.start_pos < 0
        ):
            raise ValueError("start_pos must be a non-negative integer")
        if (
            isinstance(self.end_pos, bool)
            or not isinstance(self.end_pos, int)
            or self.end_pos < 0
        ):
            raise ValueError("end_pos must be a non-negative integer")
        if self.end_pos <= self.start_pos:
            raise ValueError("end_pos must be greater than start_pos")
        if self.suggested_class_id is not None and not isinstance(
            self.suggested_class_id, str
        ):
            raise TypeError("suggested_class_id must be None or a string")


@dataclass
class ExtractionLayerResult:
    """
    Represents the results of a single extraction layer.

    An extraction layer is a processing step that extracts entities and/or
    relationships from text using a specific technique or model.

    Attributes:
        layer_name: The name of the extraction layer (kg, nlp, llm, web).
        entities: Entities extracted by this layer (immutable).
        relationships: Relationships extracted by this layer as immutable tuple of dicts.
    """

    layer_name: LayerName
    entities: tuple[ExtractedEntity, ...] = field(default_factory=tuple)
    relationships: tuple[dict, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate extraction layer result invariants."""
        if not isinstance(self.layer_name, LayerName):
            raise TypeError(
                f"layer_name must be a LayerName enum, got {type(self.layer_name).__name__}"
            )
        if not isinstance(self.entities, tuple):
            raise TypeError("entities must be a tuple of ExtractedEntity instances")
        for entity in self.entities:
            if not isinstance(entity, ExtractedEntity):
                raise TypeError(
                    f"All entities must be ExtractedEntity instances, got {type(entity).__name__}"
                )
        if not isinstance(self.relationships, tuple):
            raise TypeError("relationships must be a tuple of dicts (immutable)")
        for rel in self.relationships:
            if not isinstance(rel, dict):
                raise TypeError(
                    f"All relationships must be dicts, got {type(rel).__name__}"
                )


@dataclass
class ExtractionResult:
    """
    Represents the complete results of text extraction.

    Attributes:
        source_text: The original text from which extraction occurred.
        layers: Results from each extraction layer (immutable).
        execution_id: Optional ID linking to a pipeline execution.
    """

    source_text: str
    layers: tuple[ExtractionLayerResult, ...] = field(default_factory=tuple)
    execution_id: str | None = None

    def __post_init__(self) -> None:
        """Validate extraction result invariants."""
        if not self.source_text or not isinstance(self.source_text, str):
            raise ValueError("ExtractionResult source_text must be a non-empty string")
        if not isinstance(self.layers, tuple):
            raise TypeError("layers must be a tuple of ExtractionLayerResult instances")
        for layer in self.layers:
            if not isinstance(layer, ExtractionLayerResult):
                raise TypeError(
                    f"All layers must be ExtractionLayerResult instances, got {type(layer).__name__}"
                )
        if self.execution_id is not None and not isinstance(self.execution_id, str):
            raise TypeError("execution_id must be None or a string")
