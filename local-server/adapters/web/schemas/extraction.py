"""
Pydantic schemas for the Knowledge Extraction bounded context.

Request schemas (for POST):
- ExtractRequest
- AnalyzeTextRequest
- EnrichFromReferencesRequest

Response schemas (for GET/returns):
- ExtractedEntitySchema
- ExtractionLayerResultSchema
- ExtractionResultSchema

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ExtractedEntitySchema(BaseModel):
    """Response containing extracted entity data."""

    id: str = Field(..., description="Unique identifier for the entity")
    label: str = Field(..., description="The extracted entity label/name")
    entity_type: str = Field(..., description="Classification of the entity")
    source_layer: int = Field(..., description="Which layer extracted this entity (0-3)")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")
    uri: Optional[str] = Field(None, description="Optional URI to external knowledge base")
    description: Optional[str] = Field(None, description="Optional description of the entity")
    properties: dict = Field(default_factory=dict, description="Optional metadata key-value pairs")

    class Config:
        from_attributes = True


class ExtractionLayerResultSchema(BaseModel):
    """Response containing execution metadata for a single extraction layer."""

    layer_number: int = Field(..., description="Layer index (0-3)")
    layer_name: str = Field(..., description="Human-readable name of the layer")
    entities_found: int = Field(..., description="Count of entities extracted by this layer")
    duration_ms: int = Field(..., description="Execution time in milliseconds")
    success: bool = Field(..., description="Whether layer completed successfully")
    error_message: Optional[str] = Field(None, description="Error message if layer failed")

    class Config:
        from_attributes = True


class ExtractionResultSchema(BaseModel):
    """Response containing the complete output of an extraction operation."""

    id: str = Field(..., description="Unique identifier for this extraction result")
    text: str = Field(..., description="The source text that was extracted")
    extracted_entities: list[ExtractedEntitySchema] = Field(
        default_factory=list,
        description="Deduplicated list of extracted entities"
    )
    layers_executed: list[ExtractionLayerResultSchema] = Field(
        default_factory=list,
        description="Execution details for each layer that ran"
    )
    total_duration_ms: int = Field(..., description="Total extraction time in milliseconds")
    created_at: str = Field(..., description="ISO 8601 timestamp when extraction completed")

    class Config:
        from_attributes = True


class ExtractRequest(BaseModel):
    """Request to extract entities from text."""

    text: str = Field(..., description="Text to extract entities from", min_length=1)


class AnalyzeTextRequest(BaseModel):
    """Request to analyze text for linguistic features and named entities."""

    text: str = Field(..., description="Text to analyze", min_length=1)


class EnrichFromReferencesRequest(BaseModel):
    """Request to enrich extracted entities with external reference knowledge."""

    text: str = Field(..., description="Original source text", min_length=1)
    extracted_entities: list[ExtractedEntitySchema] = Field(
        ..., description="Entities to enrich with reference knowledge"
    )
