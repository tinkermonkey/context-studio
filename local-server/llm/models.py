from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class PipelineType(str, Enum):
    """Enumeration of supported pipeline types"""

    SUGGEST_TERM_DEFINITION = "suggest_term_definition"
    SUGGEST_LAYER_DEFINITION = "suggest_layer_definition"
    SUGGEST_DOMAIN_DEFINITION = "suggest_domain_definition"
    EXTRACT_ENTITIES = "extract_entities"


class LLMConfig(BaseModel):
    """LLM configuration parameters"""

    temperature: float = Field(
        default=0.0, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Top-p sampling"
    )
    top_k: Optional[int] = Field(default=None, gt=0, description="Top-k sampling")
    max_tokens: Optional[int] = Field(
        default=None, gt=0, description="Maximum output tokens"
    )
    frequency_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )


class PipelineFlavor(BaseModel):
    """Database model for pipeline flavors"""

    id: str = Field(..., description="Unique identifier")
    pipeline: PipelineType = Field(..., description="Pipeline type")
    title: str = Field(..., min_length=1, max_length=200, description="Flavor title")
    llm_provider: str = Field(..., description="LLM provider identifier")
    llm_model: str = Field(..., description="LLM model name")
    llm_config: LLMConfig = Field(..., description="LLM configuration")
    system_prompt: str = Field(..., min_length=1, description="System prompt template")
    user_prompt: str = Field(..., min_length=1, description="User prompt template")
    version: int = Field(..., ge=1, description="Version number")
    enabled: bool = Field(default=True, description="Whether flavor is enabled")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CreatePipelineFlavorRequest(BaseModel):
    """Request model for creating a new pipeline flavor"""

    pipeline: PipelineType = Field(..., description="Pipeline type")
    title: str = Field(..., min_length=1, max_length=200, description="Flavor title")
    llm_provider: str = Field(..., description="LLM provider identifier")
    llm_model: str = Field(..., description="LLM model name")
    llm_config: LLMConfig = Field(
        default_factory=LLMConfig, description="LLM configuration"
    )
    system_prompt: str = Field(..., min_length=1, description="System prompt template")
    user_prompt: str = Field(..., min_length=1, description="User prompt template")
    enabled: bool = Field(default=True, description="Whether flavor is enabled")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if v.lower() == "default":
            raise ValueError(
                "Cannot create flavor with title 'default' - reserved name"
            )
        return v


class UpdatePipelineFlavorRequest(BaseModel):
    """Request model for updating a pipeline flavor"""

    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="Flavor title"
    )
    llm_provider: Optional[str] = Field(None, description="LLM provider identifier")
    llm_model: Optional[str] = Field(None, description="LLM model name")
    llm_config: Optional[LLMConfig] = Field(None, description="LLM configuration")
    system_prompt: Optional[str] = Field(
        None, min_length=1, description="System prompt template"
    )
    user_prompt: Optional[str] = Field(
        None, min_length=1, description="User prompt template"
    )
    enabled: Optional[bool] = Field(None, description="Whether flavor is enabled")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if v and v.lower() == "default":
            raise ValueError("Cannot rename flavor to 'default' - reserved name")
        return v


class PipelineFlavorListResponse(BaseModel):
    """Response model for listing pipeline flavors"""

    flavors: List[PipelineFlavor] = Field(..., description="List of pipeline flavors")
    total_count: int = Field(..., description="Total number of flavors")


class StreamingLLMResponse(BaseModel):
    """Model for streaming LLM response chunks"""

    token: Optional[str] = Field(None, description="Token content")
    done: bool = Field(default=False, description="Whether streaming is complete")
    flavor_id: str = Field(..., description="ID of the flavor generating this response")
    execution_id: Optional[str] = Field(
        None, description="Execution ID (set when streaming starts)"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class SelectedRelation(BaseModel):
    """A selected ConceptNet relation for a component term"""

    predicate: str = Field(..., description="The relation predicate")
    object: str = Field(..., description="The target object of the relation")
    weight: float = Field(..., description="The weight/confidence of the relation")
    text: Optional[str] = Field(None, description="Text representation of the relation")


class ComponentTerm(BaseModel):
    """A component term with its selected definitions and relations"""

    text: str = Field(..., description="The term text")
    selected_definitions: List[str] = Field(
        default_factory=list, description="Selected sense definitions"
    )
    selected_relations: List[SelectedRelation] = Field(
        default_factory=list, description="Selected ConceptNet relations"
    )


class LLMHealthResponse(BaseModel):
    """Health check response for LLM service"""

    status: str = Field(..., description="Service status")
    model_info: Dict[str, Any] = Field(
        ..., description="Information about the current model"
    )
    timestamp: str = Field(..., description="Timestamp of the health check")


# Error response models
class LLMErrorResponse(BaseModel):
    """Error response for LLM endpoints"""

    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    details: Optional[str] = Field(None, description="Additional error details")


class RecordSelectionRequest(BaseModel):
    """Request model for recording user selection of LLM suggestions."""

    execution_id: str = Field(..., description="Execution ID from LLM response")
    record_type: str = Field(..., description="Type of record (structure_node, etc.)")
    record_id: str = Field(..., description="Primary key of the record")
    suggestion_field: str = Field(
        ..., description="Field that was selected (definition, etc.)"
    )
    selected_content: str = Field(..., description="The content that was selected")


class SelectionResponse(BaseModel):
    """Response model for selection recording."""

    success: bool = Field(
        ..., description="Whether selection was recorded successfully"
    )
    selection_id: str = Field(..., description="ID of the recorded selection")
    message: str = Field(..., description="Status message")


class ExecutionHistoryResponse(BaseModel):
    """Response model for execution history by flavor"""

    executions: List[Dict[str, Any]] = Field(
        ..., description="List of executions for the flavor"
    )
    total_count: int = Field(..., description="Total number of executions")
    flavor_id: str = Field(..., description="Flavor ID that was filtered")


class FlavorAnalyticsResponse(BaseModel):
    """Response model for flavor-specific analytics"""

    flavor_id: str = Field(..., description="Flavor ID")
    analytics: Dict[str, Any] = Field(..., description="Analytics data for the flavor")
    time_range_days: int = Field(..., description="Number of days of data included")


class ModelCapabilitiesResponse(BaseModel):
    """Response model for model capabilities information"""

    model_name: str = Field(..., description="Model name")
    capabilities: Dict[str, Any] = Field(
        ..., description="Model capabilities and constraints"
    )


class SupportedModelsResponse(BaseModel):
    """Response model for listing supported models"""

    models: List[ModelCapabilitiesResponse] = Field(
        ..., description="List of supported models with capabilities"
    )
    total_count: int = Field(..., description="Total number of supported models")


class PipelineExecutionRequest(BaseModel):
    """Generic request model for pipeline execution with arbitrary context data"""

    flavor_id: str = Field(..., description="ID of the pipeline flavor to use")
    pipeline_type: PipelineType = Field(..., description="Type of pipeline to execute")
    context_data: Dict[str, Any] = Field(
        ..., description="Arbitrary context data for template rendering"
    )

    @field_validator("context_data")
    @classmethod
    def validate_context_data(cls, v):
        if not isinstance(v, dict):
            raise ValueError("context_data must be a dictionary")
        if not v:  # Empty dict
            raise ValueError("context_data cannot be empty")
        return v


class StructuredOutputDefinition(BaseModel):
    """Structured output model for pipeline responses with definition, reasoning, and discrepancies"""

    definition: str = Field(..., description="The generated definition")
    reasoning: Optional[str] = Field(
        None, description="Brief reasoning explaining the definitional choices"
    )
    discrepancies: Optional[str] = Field(
        None, description="Any noted discrepancies between sources"
    )


# Entity model for structured output
class ExtractedEntitySchema(BaseModel):
    """Schema for a single extracted entity"""

    model_config = {"extra": "forbid"}  # Forbid additional properties

    text: str = Field(..., description="Entity text as it appears")
    entity_type: str = Field(..., description="Type of entity (CONCEPT, PERSON, etc.)")
    confidence: float = Field(..., description="Confidence score 0.0-1.0")
    sentence_index: int = Field(
        ..., description="Index of sentence where entity was found"
    )
    reasoning: Optional[str] = Field(None, description="Brief reasoning for extraction")


# Structured output model for entity extraction
class StructuredOutputEntities(BaseModel):
    """Structured output model for entity extraction responses"""

    model_config = {"extra": "forbid"}  # Forbid additional properties

    entities: List[ExtractedEntitySchema] = Field(
        default_factory=list, description="List of extracted entities with properties"
    )


# Static mapping from PipelineType to structured output types
# All pipeline types currently use the same StructuredOutput model
PIPELINE_STRUCTURED_OUTPUT_MAPPING = {
    PipelineType.SUGGEST_TERM_DEFINITION: StructuredOutputDefinition,
    PipelineType.SUGGEST_LAYER_DEFINITION: StructuredOutputDefinition,
    PipelineType.SUGGEST_DOMAIN_DEFINITION: StructuredOutputDefinition,
    PipelineType.EXTRACT_ENTITIES: StructuredOutputEntities,
}


class PipelineExecutionResponse(BaseModel):
    """Generic response model for pipeline execution"""

    response_content: str = Field(..., description="Raw LLM response content")
    execution_id: str = Field(..., description="Unique execution ID for tracing")
    flavor_id: str = Field(
        ..., description="ID of the flavor that generated this response"
    )
    pipeline_type: str = Field(..., description="Type of pipeline that was executed")
    token_usage: Optional[Dict[str, int]] = Field(
        None, description="Token usage statistics if available"
    )
    structured_output: Optional[Dict[str, Any]] = Field(
        None, description="Structured output data parsed from LLM response"
    )
