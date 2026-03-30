"""
Extraction domain value objects.

Immutable dataclasses representing immutable values in the extraction domain.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING
from types import MappingProxyType

if TYPE_CHECKING:
    from domain.extraction.entities import ExtractedEntity


@dataclass(frozen=True)
class ExtractionLayerResult:
    """
    Metadata about a single extraction layer execution.

    Attributes:
        layer_number: Numeric identifier for the layer (0–3)
        layer_name: Human-readable name of the layer
        entities_found: Count of entities extracted by this layer
        duration_ms: Time spent in this layer (milliseconds)
        success: Whether the layer completed without unhandled exceptions
        error_message: If success=False, the error message explaining the failure

    Raises:
        ValueError: If layer_number is not 0-3
    """
    layer_number: int
    layer_name: str
    entities_found: int
    duration_ms: int
    success: bool
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate extraction layer result invariants."""
        if not 0 <= self.layer_number <= 3:
            raise ValueError(f"layer_number must be 0-3, got {self.layer_number}")


@dataclass(frozen=True)
class LayerInput:
    """
    Input passed to each extraction layer.

    Attributes:
        text: The source text to extract from
        existing_entities: Entities found by previous layers
        kg_context: Optional knowledge graph context from layer 0
    """
    text: str
    existing_entities: tuple["ExtractedEntity", ...]
    kg_context: tuple[dict, ...] | None = None


@dataclass(frozen=True)
class LayerOutput:
    """
    Output produced by each extraction layer.

    Attributes:
        entities: Tuple of entities found by this layer
        metadata: Optional immutable key-value metadata about the extraction
    """
    entities: tuple["ExtractedEntity", ...]
    metadata: MappingProxyType | None = None
