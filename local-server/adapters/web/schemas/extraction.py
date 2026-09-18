"""
Pydantic schemas for the Knowledge Extraction bounded context.

Entity extraction:
- ExtractRequest (entity-centric)
- ExtractionResultSchema (entity-centric response)
- ExtractedEntitySchema, ExtractionLayerResultSchema (supporting)

Text analysis & enrichment:
- AnalyzeTextRequest, EnrichFromReferencesRequest

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceSpanSchema(BaseModel):
    """Immutable representation of a span in source text with provenance information."""

    model_config = ConfigDict(from_attributes=True)

    quote: Optional[str] = Field(
        None,
        description="The verbatim or matched text from the source, or None if unresolved",
    )
    start: Optional[int] = Field(
        None,
        ge=0,
        description="Zero-indexed character position where the span begins, or None if unresolved",
    )
    end: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Zero-indexed character position where the span ends "
            "(exclusive), or None if unresolved"
        ),
    )


class ExtractedEntitySchema(BaseModel):
    """Response containing extracted entity data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for the entity")
    label: str = Field(..., description="The extracted entity label/name")
    entity_type: str = Field(..., description="Classification of the entity")
    source_layer: int = Field(..., description="Which layer extracted this entity (0-3)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    uri: Optional[str] = Field(None, description="Optional URI to external knowledge base")
    description: Optional[str] = Field(None, description="Optional description of the entity")
    matched_class_id: Optional[str] = Field(
        None, description="ID of matched ontology class, if any"
    )
    span: Optional[SourceSpanSchema] = Field(
        None, description="Optional span with provenance information (quote and character offsets)"
    )
    properties: dict = Field(default_factory=dict, description="Optional metadata key-value pairs")


class ExtractionLayerResultSchema(BaseModel):
    """Response containing execution metadata for a single extraction layer."""

    model_config = ConfigDict(from_attributes=True)

    layer_number: int = Field(..., description="Layer index (0-3)")
    layer_name: str = Field(..., description="Human-readable name of the layer")
    entities_found: int = Field(..., description="Count of entities extracted by this layer")
    duration_ms: int = Field(..., description="Execution time in milliseconds")
    success: bool = Field(..., description="Whether layer completed successfully")
    error_message: Optional[str] = Field(None, description="Error message if layer failed")


class ExtractionResultSchema(BaseModel):
    """Response containing the complete output of an extraction operation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for this extraction result")
    text: str = Field(..., description="The source text that was extracted")
    extracted_entities: list[ExtractedEntitySchema] = Field(
        default_factory=list, description="Deduplicated list of extracted entities"
    )
    layers_executed: list[ExtractionLayerResultSchema] = Field(
        default_factory=list, description="Execution details for each layer that ran"
    )
    total_duration_ms: int = Field(..., description="Total extraction time in milliseconds")
    created_at: str = Field(..., description="ISO 8601 timestamp when extraction completed")


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


class RecognitionPreviewRequest(BaseModel):
    """Request to preview recognition results for a pipeline run."""

    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for extracted mentions (0.0–1.0). "
        "Mentions below this threshold are skipped.",
    )
    recognition_threshold: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for individual recognition matches (0.0–1.0). "
        "Matches below this threshold are not reported.",
    )


class RecognitionPreviewHitSchema(BaseModel):
    """Preview of recognition result for a single extracted mention."""

    model_config = ConfigDict(from_attributes=True)

    mention_label: str = Field(..., description="The extracted mention's surface text")
    resolved_individual_id: Optional[str] = Field(
        None,
        description="ID of the matched existing individual, or None if no match",
    )
    resolved_individual_title: Optional[str] = Field(
        None,
        description="Canonical title of the matched individual, or None if no match",
    )
    match_method: Optional[str] = Field(
        None,
        description='Match method when resolved: "exact", "vector", or "llm", or None',
    )
    match_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence of the match (0.0–1.0), or None if no match",
    )
    will_match_existing: bool = Field(
        ...,
        description="True if the mention would match an existing individual, "
        "False if it would be created as new",
    )


class RecognitionPreviewResponse(BaseModel):
    """Response from recognition preview endpoint."""

    model_config = ConfigDict(from_attributes=True)

    hits: list[RecognitionPreviewHitSchema] = Field(
        default_factory=list,
        description="Preview results for each distinct extracted individual mention",
    )
    total_mentions: int = Field(
        ...,
        ge=0,
        description="Total number of distinct individual mentions previewed",
    )
    matched_count: int = Field(
        ...,
        ge=0,
        description="Number of mentions that would match an existing individual",
    )
    unmatched_count: int = Field(
        ...,
        ge=0,
        description="Number of mentions that would be created as new",
    )
    skipped_count: int = Field(
        ...,
        ge=0,
        description="Number of mentions skipped due to being below the confidence threshold",
    )
