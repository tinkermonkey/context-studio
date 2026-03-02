"""
Domain entities for the extraction bounded context.

Entities represent extracted information from text: entities, relationships,
and complete extraction results. They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ExtractedEntity:
    """
    Represents an entity extracted from text.

    Attributes:
        text: The actual text of the extracted entity.
        entity_type: The type/classification of the entity (e.g., "person", "location").
        confidence: Confidence score between 0.0 and 1.0.
        start_pos: Starting character position in the source text.
        end_pos: Ending character position in the source text.
        suggested_class_id: Optional ID of a suggested Class to map this entity to.
    """

    text: str
    entity_type: str
    confidence: float
    start_pos: int
    end_pos: int
    suggested_class_id: Optional[str] = None


@dataclass
class ExtractionLayerResult:
    """
    Represents the results of a single extraction layer.

    An extraction layer is a processing step that extracts entities and/or
    relationships from text using a specific technique or model.

    Attributes:
        layer_name: The name of the extraction layer.
        entities: Entities extracted by this layer.
        relationships: Relationships extracted by this layer (as dicts).
    """

    layer_name: str
    entities: List[ExtractedEntity]
    relationships: List[dict] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """
    Represents the complete results of text extraction.

    Attributes:
        source_text: The original text from which extraction occurred.
        layers: Results from each extraction layer.
        execution_id: Optional ID linking to a pipeline execution.
    """

    source_text: str
    layers: List[ExtractionLayerResult]
    execution_id: Optional[str] = None
