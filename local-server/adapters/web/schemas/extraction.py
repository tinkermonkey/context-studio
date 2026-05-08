"""
Pydantic schemas for the Knowledge Extraction bounded context.

Entity extraction:
- ExtractRequest (entity-centric)
- ExtractionResultSchema (entity-centric response)
- ExtractedEntitySchema, ExtractionLayerResultSchema (supporting)

Triple extraction (RDF):
- ExtractTripleRequest (triple-centric)
- ExtractTripleResponse (triple-centric response)
- Related node and provenance schemas (supporting)

Text analysis & enrichment:
- AnalyzeTextRequest, EnrichFromReferencesRequest

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ExtractedEntitySchema(BaseModel):
    """Response containing extracted entity data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for the entity")
    label: str = Field(..., description="The extracted entity label/name")
    entity_type: str = Field(..., description="Classification of the entity")
    source_layer: int = Field(
        ..., description="Which layer extracted this entity (0-3)"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0"
    )
    uri: Optional[str] = Field(
        None, description="Optional URI to external knowledge base"
    )
    description: Optional[str] = Field(
        None, description="Optional description of the entity"
    )
    matched_class_id: Optional[str] = Field(
        None, description="ID of matched ontology class, if any"
    )
    properties: dict = Field(
        default_factory=dict, description="Optional metadata key-value pairs"
    )


class ExtractionLayerResultSchema(BaseModel):
    """Response containing execution metadata for a single extraction layer."""

    model_config = ConfigDict(from_attributes=True)

    layer_number: int = Field(..., description="Layer index (0-3)")
    layer_name: str = Field(..., description="Human-readable name of the layer")
    entities_found: int = Field(
        ..., description="Count of entities extracted by this layer"
    )
    duration_ms: int = Field(..., description="Execution time in milliseconds")
    success: bool = Field(..., description="Whether layer completed successfully")
    error_message: Optional[str] = Field(
        None, description="Error message if layer failed"
    )


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
    total_duration_ms: int = Field(
        ..., description="Total extraction time in milliseconds"
    )
    created_at: str = Field(
        ..., description="ISO 8601 timestamp when extraction completed"
    )


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


# ==================== Triple Extraction (RDF) Schemas ====================


class ExtractTripleOptions(BaseModel):
    """Options for triple extraction."""

    model: str = Field(
        ...,
        description="Model identifier for extraction (e.g., 'gpt-4', 'claude-opus')",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 = deterministic, up to 2.0)",
    )
    max_tokens: Optional[int] = Field(
        None,
        ge=100,
        le=8000,
        description="Maximum tokens in LLM response",
    )


class ExtractTripleRequest(BaseModel):
    """Request to extract triples from text scoped to an ontology."""

    text: str = Field(
        ..., min_length=1, description="Source text to extract triples from"
    )
    ontology_id: str = Field(
        ...,
        description="ID of the ontology scoping extraction to specific classes/individuals",
    )
    options: ExtractTripleOptions = Field(
        ..., description="Extraction options (model, temperature, etc.)"
    )


class TripleProvenance(BaseModel):
    """Provenance metadata for an extracted triple."""

    text_offset_start: int = Field(
        ..., ge=0, description="Character offset where triple evidence begins"
    )
    text_offset_end: int = Field(
        ..., ge=0, description="Character offset where triple evidence ends"
    )
    raw: str = Field(..., description="Exact text span supporting this triple")


class SubjectNode(BaseModel):
    """Subject node of a triple—individual or class."""

    kind: Literal["individual", "class"]
    id: str = Field(..., description="Entity ID in the ontology")
    label: str = Field(..., description="Human-readable label")


class PredicateNode(BaseModel):
    """Predicate node of a triple—a property definition."""

    property_definition_id: str = Field(..., description="ID of the property definition")
    label: str = Field(..., description="Human-readable property name")


class ObjectNodeIndividual(BaseModel):
    """Object node: individual instance."""

    kind: Literal["individual"] = "individual"
    id: str = Field(..., description="Individual ID in the ontology")
    label: str = Field(..., description="Human-readable label")


class ObjectNodeClass(BaseModel):
    """Object node: class/concept."""

    kind: Literal["class"] = "class"
    id: str = Field(..., description="Class ID in the ontology")
    label: str = Field(..., description="Human-readable label")


class ObjectNodeLiteral(BaseModel):
    """Object node: literal value."""

    kind: Literal["literal"] = "literal"
    value: str | int | float | bool | None = Field(
        ..., description="Literal value (string, number, boolean, or null)"
    )
    datatype: Optional[str] = Field(
        None, description="XSD datatype (e.g., 'xsd:string', 'xsd:integer')"
    )


class ExtractedTriple(BaseModel):
    """A single extracted triple with confidence and provenance."""

    subject: SubjectNode
    predicate: PredicateNode
    object: Union[ObjectNodeIndividual, ObjectNodeClass, ObjectNodeLiteral] = Field(
        ..., discriminator="kind", description="Object node discriminated by 'kind' field"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0–1.0)"
    )
    provenance: TripleProvenance = Field(
        ..., description="Provenance linking triple to source text"
    )


class ExtractionMetadata(BaseModel):
    """Metadata about a triple extraction operation."""

    model: str = Field(..., description="Model used for extraction")
    tokens_used: int = Field(..., ge=0, description="Total tokens consumed")
    duration_ms: int = Field(..., ge=0, description="Extraction duration in milliseconds")


class ExtractTripleResponse(BaseModel):
    """Response containing extracted triples."""

    triples: list[ExtractedTriple] = Field(
        ..., description="List of extracted triples"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings (e.g., confidence out of range, invalid provenance)",
    )
    metadata: ExtractionMetadata = Field(
        ..., description="Metadata about the extraction operation"
    )
