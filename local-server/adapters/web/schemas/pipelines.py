"""
Pydantic schemas for the Pipeline Orchestration bounded context.

Request schemas (for POST/PUT):
- IndividualExtractionRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaExtractionRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaGroundingRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaDefinitionRefinementRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaConnectionRefinementRunRequest — Per-type request; documented for Wave B per-type implementation

Response schemas (for GET/returns):
- PipelineRunResponse
- PipelineTypeResponse
- ImplementationResponse
- ConfigurationResponse

Per-type request schemas are defined for forward compatibility and documentation of expected inputs
per pipeline type. They are actively used in per-type implementation sub-issues. The generic
PipelineRunRequest is used in the Wave B generic endpoint; type-specific fields are refined
in later sub-issues.

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class PipelineTypeResponse(BaseModel):
    """Response containing pipeline type metadata."""

    model_config = ConfigDict(from_attributes=True)

    pipeline_type: str = Field(..., description="Pipeline type identifier")
    description: str = Field(..., description="Human-readable description")
    input_contract: dict[str, Any] = Field(..., description="Expected input schema")
    output_contract: dict[str, Any] = Field(..., description="Expected output schema")


class ImplementationResponse(BaseModel):
    """Response containing implementation metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Implementation identifier")
    pipeline_type: str = Field(..., description="Pipeline type for this implementation")


class ConfigurationResponse(BaseModel):
    """Response containing configuration metadata."""

    model_config = ConfigDict(from_attributes=True)

    config_ref: str = Field(..., description="Configuration reference slug")
    version: int = Field(..., description="Configuration version number")
    config: dict[str, Any] = Field(..., description="Configuration data")


class PipelineRunRequest(BaseModel):
    """Base request to invoke a pipeline (polymorphic)."""

    implementation_id: str = Field(
        default="default", description="Implementation identifier (defaults to 'default')"
    )
    configuration_ref: str = Field(
        default="default", description="Configuration reference (defaults to 'default')"
    )


class IndividualExtractionRunRequest(PipelineRunRequest):
    """Request to invoke individual_extraction pipeline."""

    text: str = Field(..., min_length=1, description="Source text to extract from")
    ontology_id: str = Field(..., min_length=1, description="Target ontology ID")


class SchemaExtractionRunRequest(PipelineRunRequest):
    """Request to invoke schema_extraction pipeline."""

    documents: list[str] = Field(..., min_length=1, description="Source documents")
    scope: Optional[str] = Field(None, description="Extraction scope (optional)")


class SchemaGroundingRunRequest(PipelineRunRequest):
    """Request to invoke schema_node_grounding pipeline."""

    nodes: list[dict[str, Any]] = Field(..., min_length=1, description="Schema nodes to ground")
    sources: list[str] = Field(..., min_length=1, description="External knowledge sources")


class SchemaDefinitionRefinementRunRequest(PipelineRunRequest):
    """Request to invoke schema_node_definition_refinement pipeline."""

    nodes: list[dict[str, Any]] = Field(..., min_length=1, description="Schema nodes to refine")
    context: Optional[str] = Field(None, description="Additional context (optional)")


class SchemaConnectionRefinementRunRequest(PipelineRunRequest):
    """Request to invoke schema_node_connection_refinement pipeline."""

    edges: list[dict[str, Any]] = Field(..., min_length=1, description="Edges (connections) to refine")
    strategy: Optional[str] = Field(None, description="Refinement strategy (optional)")


GenericPipelineRunRequest = Union[
    IndividualExtractionRunRequest,
    SchemaExtractionRunRequest,
    SchemaGroundingRunRequest,
    SchemaDefinitionRefinementRunRequest,
    SchemaConnectionRefinementRunRequest,
]


class IndividualExtractionOutput(BaseModel):
    """Per-type output schema for individual_extraction with provenance and confidence."""

    model_config = ConfigDict(from_attributes=True)

    text_offset_start: Optional[int] = Field(None, description="Character offset start of extracted match")
    text_offset_end: Optional[int] = Field(None, description="Character offset end of extracted match")
    source_uri: Optional[str] = Field(None, description="URI or identifier of source document")
    raw_match: Optional[str] = Field(None, description="Raw matched text from source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for extraction (0.0-1.0)")


class SchemaExtractionOutput(BaseModel):
    """Per-type output schema for schema_extraction with provenance and confidence."""

    model_config = ConfigDict(from_attributes=True)

    source_uri: Optional[str] = Field(None, description="URI or identifier of source document")
    raw_match: Optional[str] = Field(None, description="Raw matched text from source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for extraction (0.0-1.0)")


class SchemaGroundingOutput(BaseModel):
    """Per-type output schema for schema_node_grounding with provenance and confidence."""

    model_config = ConfigDict(from_attributes=True)

    source_uri: Optional[str] = Field(None, description="URI of grounding source")
    raw_match: Optional[str] = Field(None, description="Raw grounding match")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for grounding (0.0-1.0)")


class SchemaDefinitionRefinementOutput(BaseModel):
    """Per-type output schema for schema_node_definition_refinement with provenance and confidence."""

    model_config = ConfigDict(from_attributes=True)

    source_uri: Optional[str] = Field(None, description="URI of refinement source")
    raw_match: Optional[str] = Field(None, description="Raw refinement text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for refinement (0.0-1.0)")


class SchemaConnectionRefinementOutput(BaseModel):
    """Per-type output schema for schema_node_connection_refinement with provenance and confidence."""

    model_config = ConfigDict(from_attributes=True)

    source_uri: Optional[str] = Field(None, description="URI of refinement source")
    raw_match: Optional[str] = Field(None, description="Raw refinement text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for refinement (0.0-1.0)")


class PipelineRunResponse(BaseModel):
    """Response containing a PipelineRun."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique run ID")
    batch_run_id: str = Field(..., description="Batch run FK")
    pipeline_type: str = Field(..., description="Pipeline type (discriminator)")
    implementation_id: str = Field(..., description="Implementation ID")
    configuration_ref: str = Field(..., description="Configuration reference")
    input_summary: dict[str, Any] = Field(default_factory=dict, description="Input metadata")
    output_summary: dict[str, Any] = Field(default_factory=dict, description="Output counts/metrics")
    llm_metadata: dict[str, Any] = Field(default_factory=dict, description="LLM execution metadata")
    status: str = Field(..., description="Current status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp (reserved for future use)")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp (reserved for future use)")
