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
- PipelineConfigurationResponse (rich schema for user-editable configs)

Candidate response schemas:
- SourceSpanSchema — quote and character offsets (start, end)
- CandidateBase — shared candidate fields (candidate_type, confidence, provenance)
- Discriminated union variants:
  - SchemaClassCandidate — class extraction candidate
  - SchemaPropertyCandidate — property definition candidate
  - SchemaConnectionCandidate — connection/relationship candidate
  - NodeReference — reference to an extracted node (individual_extraction)
  - PredicateReference — reference to a predicate/property (individual_extraction)
  - TripleCandidate — subject-predicate-object triple (individual_extraction)
  - GroundingCandidate — external knowledge grounding (schema_node_grounding)
  - RefinementCandidate — refined definition or connection (refinement pipelines)
- CandidateItem — Annotated discriminated union covering all variants

Legacy schemas (deprecated, kept for reference):
- CandidateResponse — flat candidate schema (replaced by discriminated union)

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag


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


class PipelineConfigurationParameters(BaseModel):
    """LLM parameters for a pipeline configuration."""

    temperature: float = Field(default=0.4, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=800, ge=64, le=4096, description="Maximum tokens to generate")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling probability")


class PipelineConfigurationCreateRequest(BaseModel):
    """Request body for creating a new user pipeline configuration."""

    name: str = Field(..., min_length=1, max_length=120, description="Configuration display name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    provider: str = Field(..., description="LLM provider (openai or anthropic)")
    model: str = Field(..., description="Model identifier")
    system_prompt: Optional[str] = Field(None, description="System prompt text")
    user_prompt_template: str = Field(
        ..., min_length=1, description="User prompt template (Jinja2)"
    )
    parameters: PipelineConfigurationParameters = Field(
        default_factory=PipelineConfigurationParameters,
        description="LLM generation parameters",
    )
    enabled: bool = Field(default=True, description="Whether this configuration is active")


class PipelineConfigurationUpdateRequest(BaseModel):
    """Request body for updating an existing user pipeline configuration."""

    name: str = Field(..., min_length=1, max_length=120, description="Configuration display name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    provider: str = Field(..., description="LLM provider (openai or anthropic)")
    model: str = Field(..., description="Model identifier")
    system_prompt: Optional[str] = Field(None, description="System prompt text")
    user_prompt_template: str = Field(
        ..., min_length=1, description="User prompt template (Jinja2)"
    )
    parameters: PipelineConfigurationParameters = Field(
        ..., description="LLM generation parameters"
    )
    enabled: bool = Field(..., description="Whether this configuration is active")


class PipelineConfigurationResponse(BaseModel):
    """Rich response for a pipeline configuration (user-created or system-defined)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Stable configuration UUID (synthetic for system configs)")
    config_ref: str = Field(..., description="Configuration reference slug (registry key)")
    pipeline_type: str = Field(..., description="Pipeline type identifier")
    implementation_id: str = Field(..., description="Implementation identifier")
    name: str = Field(..., description="Configuration display name")
    description: Optional[str] = Field(None, description="Optional description")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model identifier")
    system_prompt: Optional[str] = Field(None, description="System prompt text")
    user_prompt_template: Optional[str] = Field(None, description="User prompt template")
    parameters: Optional[PipelineConfigurationParameters] = Field(
        None, description="LLM generation parameters"
    )
    enabled: bool = Field(default=True, description="Whether this configuration is active")
    version: int = Field(..., description="Configuration version number")
    is_system: bool = Field(..., description="True for code-defined system configurations")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class PipelineRunRequest(BaseModel):
    """Base request to invoke a pipeline (polymorphic)."""

    model_config = ConfigDict(extra="allow")

    implementation_id: str = Field(
        default="default",
        description="Implementation identifier (defaults to 'default')",
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

    node_id: str = Field(..., min_length=1, description="Schema node ID to refine")
    current_definition: str = Field(..., description="Current definition to refine")
    groundings: Optional[list[dict[str, Any]]] = Field(
        None, description="External groundings (optional)"
    )
    extraction_usages: Optional[list[dict[str, Any]]] = Field(
        None, description="Extraction usage examples (optional)"
    )


class SchemaConnectionRefinementRunRequest(PipelineRunRequest):
    """Request to invoke schema_node_connection_refinement pipeline."""

    scope_id: str = Field(..., min_length=1, description="Schema node ID to refine connections for")
    current_connections: list[dict[str, Any]] = Field(
        ..., description="Current connections for the scope"
    )
    groundings: Optional[list[dict[str, Any]]] = Field(
        None, description="External groundings (optional)"
    )
    extraction_usages: Optional[list[dict[str, Any]]] = Field(
        None, description="Extraction usage examples (optional)"
    )


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
    configuration_slug: str = Field(..., description="Configuration slug")
    configuration_version: int = Field(..., description="Configuration version")
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
    started_at: Optional[datetime] = Field(
        None, description="Timestamp when run transitioned to RUNNING"
    )
    failure_reason: Optional[str] = Field(None, description="Failure reason if status=FAILED")


class ApplyRunResponse(BaseModel):
    """Response from applying a pipeline run's output to the ontology."""

    run_id: str = Field(..., description="ID of the applied pipeline run")
    pipeline_type: str = Field(..., description="Pipeline type that was applied")
    classes_created: int = Field(default=0, description="Class entities created")
    classes_updated: int = Field(default=0, description="Class entities updated")
    classes_skipped: int = Field(default=0, description="Class candidates skipped (already exist)")
    properties_created: int = Field(default=0, description="PropertyDefinition entities created")
    properties_skipped: int = Field(
        default=0, description="PropertyDefinition candidates skipped (already exist)"
    )
    relationships_created: int = Field(default=0, description="Relationship entities created")
    relationships_removed: int = Field(default=0, description="Relationship entities removed")
    relationships_modified: int = Field(default=0, description="Relationship entities modified")
    relationships_skipped: int = Field(
        default=0,
        description="Relationship candidates skipped (already exist or unresolvable)",
    )
    individuals_created: int = Field(default=0, description="Individual entities created")
    individuals_skipped: int = Field(
        default=0, description="Individual candidates skipped (already exist)"
    )
    individuals_recognized: int = Field(
        default=0,
        description="Individual candidates resolved to an existing graph node by recognition",
    )
    external_references_created: int = Field(
        default=0, description="External references added to classes"
    )
    external_references_skipped: int = Field(
        default=0, description="External references skipped (already exist)"
    )
    created_class_ids: list[str] = Field(default_factory=list, description="IDs of created classes")
    created_individual_ids: list[str] = Field(
        default_factory=list, description="IDs of created individuals"
    )
    created_relationship_ids: list[str] = Field(
        default_factory=list, description="IDs of created relationships"
    )
    created_property_definition_ids: list[str] = Field(
        default_factory=list, description="IDs of created property definitions"
    )
    created_external_reference_ids: list[str] = Field(
        default_factory=list, description="URIs of created external references"
    )
    recognized_individual_ids: list[str] = Field(
        default_factory=list,
        description="IDs of individuals resolved to an existing graph node by recognition",
    )


class RevertRunResponse(BaseModel):
    """Response from reverting a pipeline run."""

    run_id: str = Field(..., description="ID of the reverted pipeline run")
    events_reverted: int = Field(..., description="Number of change events reverted")
    classes_deleted: int = Field(default=0, description="Number of classes deleted during revert")
    individuals_deleted: int = Field(
        default=0, description="Number of individuals deleted during revert"
    )
    relationships_deleted: int = Field(
        default=0, description="Number of relationships deleted during revert"
    )
    properties_deleted: int = Field(
        default=0, description="Number of properties deleted during revert"
    )
    taxonomies_deleted: int = Field(
        default=0, description="Number of taxonomies deleted during revert"
    )
    concept_schemes_deleted: int = Field(
        default=0, description="Number of concept schemes deleted during revert"
    )
    entities_restored: int = Field(
        default=0, description="Number of entities restored during revert"
    )


class SourceSpanSchema(BaseModel):
    """Represents a span in source text with optional character offsets.

    Encodes provenance via nullable fields:
    - Fully resolved: all three fields populated
    - Quote-only: quote populated, offsets are None
    - Unresolved: all fields are None
    """

    model_config = ConfigDict(from_attributes=True)

    quote: Optional[str] = Field(None, description="The verbatim or matched text from source")
    start: Optional[int] = Field(None, ge=0, description="Zero-indexed character start position")
    end: Optional[int] = Field(None, ge=0, description="Zero-indexed character end position (exclusive)")


class CandidateBase(BaseModel):
    """Base class for all candidates from pipeline execution.

    Provides shared fields: candidate_type (discriminator), confidence, and provenance.
    Each concrete candidate type specifies its variant via candidate_type.
    """

    model_config = ConfigDict(from_attributes=True)

    candidate_type: str = Field(..., description="Discriminator: identifies the candidate variant")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    provenance: list[SourceSpanSchema] = Field(
        default_factory=list, description="List of source spans with provenance information"
    )


class SchemaClassCandidate(CandidateBase):
    """Candidate class entity from schema extraction or grounding.

    Represents a proposed or grounded class in the schema.
    """

    candidate_type: Literal["schema_class"] = "schema_class"
    uri: str = Field(..., description="Class URI or identifier")
    label: str = Field(..., description="Class label/name")
    description: str = Field(default="", description="Class description or definition")


class SchemaPropertyCandidate(CandidateBase):
    """Candidate property definition from schema extraction.

    Represents a proposed property/relationship type.
    """

    candidate_type: Literal["schema_property"] = "schema_property"
    uri: str = Field(..., description="Property URI or identifier")
    label: str = Field(..., description="Property label/name")
    description: str = Field(default="", description="Property description or semantics")


class SchemaConnectionCandidate(CandidateBase):
    """Candidate connection/relationship from schema extraction or refinement.

    Represents a proposed relationship between schema entities.
    """

    candidate_type: Literal["schema_connection"] = "schema_connection"
    source_uri: str = Field(..., description="Source entity URI")
    property_uri: str = Field(..., description="Property/relationship type URI")
    target_uri: str = Field(..., description="Target entity URI")
    description: str = Field(default="", description="Relationship description or rationale")


class NodeReference(BaseModel):
    """Reference to an extracted node (individual) in individual extraction.

    Identifies a node without full triple context.
    """

    model_config = ConfigDict(from_attributes=True)

    label: str = Field(..., description="Node label/name")
    kind: str = Field(..., description="Node kind/type (e.g., 'individual', 'class')")


class PredicateReference(BaseModel):
    """Reference to a predicate/property in individual extraction.

    Identifies a property without full triple context.
    """

    model_config = ConfigDict(from_attributes=True)

    label: str = Field(..., description="Predicate label/name")
    kind: str = Field(..., description="Predicate kind/type (e.g., 'property')")


class TripleCandidate(CandidateBase):
    """Subject-predicate-object triple candidate from individual extraction.

    Represents a proposed relationship between two extracted entities.
    """

    candidate_type: Literal["triple"] = "triple"
    subject: NodeReference = Field(..., description="Subject node reference")
    predicate: PredicateReference = Field(..., description="Predicate reference")
    object: NodeReference = Field(..., description="Object node reference")


class GroundingCandidate(CandidateBase):
    """Grounding candidate linking a schema node to external knowledge.

    Represents an external resource that grounds or validates a schema entity.
    """

    candidate_type: Literal["grounding"] = "grounding"
    uri: str = Field(..., description="External resource URI or identifier")
    label: str = Field(..., description="External resource label")
    description: str = Field(default="", description="External resource description")
    source: str = Field(default="", description="Source database or knowledge base")


class RefinementCandidate(CandidateBase):
    """Refined definition or connection candidate from refinement pipelines.

    Represents a proposed refinement to an existing schema entity or relationship.
    """

    candidate_type: Literal["refinement"] = "refinement"
    content: str = Field(..., description="Refined text content (definition or relationship)")
    scope_id: Optional[str] = Field(None, description="Target entity ID for this refinement")


CandidateItem = Annotated[
    Union[
        Annotated[SchemaClassCandidate, Tag("schema_class")],
        Annotated[SchemaPropertyCandidate, Tag("schema_property")],
        Annotated[SchemaConnectionCandidate, Tag("schema_connection")],
        Annotated[TripleCandidate, Tag("triple")],
        Annotated[GroundingCandidate, Tag("grounding")],
        Annotated[RefinementCandidate, Tag("refinement")],
    ],
    Discriminator("candidate_type"),
]


class CandidateResponse(BaseModel):
    """Response containing a single candidate from a pipeline run.

    DEPRECATED: Use CandidateItem (discriminated union) for new implementations.

    Represents a candidate result from pipeline execution with full provenance
    and confidence information. Structure adapts based on pipeline type but
    maintains a consistent interface. Kept for backwards compatibility until
    all consumers migrate to discriminated union variants.
    """

    model_config = ConfigDict(from_attributes=True)

    uri: str = Field(..., description="Candidate URI or identifier")
    label: str = Field(..., description="Human-readable candidate label")
    description: str = Field(default="", description="Candidate description or definition")
    source: str = Field(default="", description="Source or database where candidate originates")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    provenance: str = Field(default="", description="Rationale or provenance for the candidate")


class RunCountsResponse(BaseModel):
    """Response containing run counts by status."""

    model_config = ConfigDict(from_attributes=True)

    pending: int = Field(..., ge=0, description="Number of pending runs")
    running: int = Field(..., ge=0, description="Number of running runs")
    completed: int = Field(..., ge=0, description="Number of completed runs")
    failed: int = Field(..., ge=0, description="Number of failed runs")
    cancelled: int = Field(..., ge=0, description="Number of cancelled runs")


class BatchResponse(BaseModel):
    """Response containing batch information."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Batch UUID")
    status: str = Field(
        ...,
        description="Status: pending, running, completed, failed, or cancelled",
    )
    created_at: datetime = Field(..., description="UTC timestamp of batch creation")
    started_at: Optional[datetime] = Field(None, description="UTC timestamp when batch started")
    completed_at: Optional[datetime] = Field(None, description="UTC timestamp when batch completed")
    last_updated: datetime = Field(..., description="UTC timestamp of last update")
    run_count: int = Field(..., ge=0, description="Total number of runs in batch")
    run_counts: RunCountsResponse = Field(..., description="Breakdown of runs by status")


class EnqueueBatchRunsRequest(BaseModel):
    """Request to enqueue multiple runs in a batch."""

    model_config = ConfigDict(from_attributes=True)

    runs: list[dict[str, Any]] = Field(..., min_length=1, description="Run specs to enqueue")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key for replay")


class EnqueueBatchRunsResponse(BaseModel):
    """Response from batch enqueue operation."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: str = Field(..., description="Batch UUID")
    run_ids: list[str] = Field(..., description="IDs of created runs")
    run_count: int = Field(..., ge=0, description="Total runs now in batch")


class CancelBatchResponse(BaseModel):
    """Response from batch cancel operation."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: str = Field(..., description="Batch UUID")
    cancelled_count: int = Field(..., ge=0, description="Number of runs cancelled")
    status: str = Field(..., description="Batch status after operation")
    run_counts: RunCountsResponse = Field(..., description="Run counts after operation")


class ResumeBatchResponse(BaseModel):
    """Response from batch resume operation."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: str = Field(..., description="Batch UUID")
    resumed_count: int = Field(..., ge=0, description="Number of runs resumed")
    status: str = Field(..., description="Batch status after operation")
    run_counts: RunCountsResponse = Field(..., description="Run counts after operation")
