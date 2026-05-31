"""
Pydantic schemas for the Pipeline Orchestration bounded context.

Request schemas (for POST/PUT):
- IndividualExtractionRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaExtractionRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaGroundingRunRequest — Per-type request; documented for Wave B per-type implementation
- SchemaDefinitionRefinementRunRequest — Per-type request; documented for Wave B
  per-type implementation
- SchemaConnectionRefinementRunRequest — Per-type request; documented for Wave B
  per-type implementation

Response schemas (for GET/returns):
- PipelineRunResponse
- PipelineTypeResponse
- ImplementationResponse
- ConfigurationResponse

Per-type request schemas are defined for forward compatibility and documentation of
expected inputs per pipeline type. They are actively used in per-type implementation
sub-issues. The generic PipelineRunRequest is used in the Wave B generic endpoint;
type-specific fields are refined in later sub-issues.

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from datetime import datetime
from typing import Any, Optional, Union

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

    model_config = ConfigDict(extra="allow")

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

    edges: list[dict[str, Any]] = Field(
        ..., min_length=1, description="Edges (connections) to refine"
    )
    strategy: Optional[str] = Field(None, description="Refinement strategy (optional)")


GenericPipelineRunRequest = Union[
    IndividualExtractionRunRequest,
    SchemaExtractionRunRequest,
    SchemaGroundingRunRequest,
    SchemaDefinitionRefinementRunRequest,
    SchemaConnectionRefinementRunRequest,
]


class PipelineRunResponse(BaseModel):
    """Response containing a PipelineRun."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique run ID")
    batch_run_id: str = Field(..., description="Batch run FK")
    pipeline_type: str = Field(..., description="Pipeline type (discriminator)")
    implementation_id: str = Field(..., description="Implementation ID")
    configuration_ref: str = Field(..., description="Configuration reference")
    input_summary: dict[str, Any] = Field(default_factory=dict, description="Input metadata")
    output_summary: dict[str, Any] = Field(
        default_factory=dict, description="Output counts/metrics"
    )
    llm_metadata: dict[str, Any] = Field(default_factory=dict, description="LLM execution metadata")
    status: str = Field(..., description="Current status")
    created_at: Optional[datetime] = Field(
        None, description="Creation timestamp (reserved for future use)"
    )
    updated_at: Optional[datetime] = Field(
        None, description="Last update timestamp (reserved for future use)"
    )


class ApplyRunResponse(BaseModel):
    """Response from applying a pipeline run's output to the ontology."""

    run_id: str = Field(..., description="ID of the applied pipeline run")
    pipeline_type: str = Field(..., description="Pipeline type that was applied")
    classes_created: int = Field(default=0, description="Class entities created")
    classes_skipped: int = Field(default=0, description="Class candidates skipped (already exist)")
    properties_created: int = Field(default=0, description="PropertyDefinition entities created")
    properties_skipped: int = Field(
        default=0, description="PropertyDefinition candidates skipped (already exist)"
    )
    relationships_created: int = Field(default=0, description="Relationship entities created")
    relationships_skipped: int = Field(
        default=0, description="Relationship candidates skipped (already exist or unresolvable)"
    )
    individuals_created: int = Field(default=0, description="Individual entities created")
    individuals_skipped: int = Field(
        default=0, description="Individual candidates skipped (already exist)"
    )


class CandidateResponse(BaseModel):
    """Response containing a single candidate from a pipeline run.

    Represents a candidate result from pipeline execution with full provenance
    and confidence information. Structure adapts based on pipeline type but
    maintains a consistent interface.
    """

    model_config = ConfigDict(from_attributes=True)

    uri: str = Field(..., description="Candidate URI or identifier")
    label: str = Field(..., description="Human-readable candidate label")
    description: str = Field(default="", description="Candidate description or definition")
    source: str = Field(default="", description="Source or database where candidate originates")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    provenance: str = Field(default="", description="Rationale or provenance for the candidate")
