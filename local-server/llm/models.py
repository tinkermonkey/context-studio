from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid

class PipelineType(str, Enum):
    """Enumeration of supported pipeline types"""
    SUGGEST_TERM_DEFINITION = "suggest_term_definition"
    SUGGEST_LAYER_DEFINITION = "suggest_layer_definition"
    SUGGEST_DOMAIN_DEFINITION = "suggest_domain_definition"

class LLMConfig(BaseModel):
    """LLM configuration parameters"""
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p sampling")
    top_k: Optional[int] = Field(default=None, gt=0, description="Top-k sampling")
    max_tokens: Optional[int] = Field(default=None, gt=0, description="Maximum output tokens")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Presence penalty")

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
    last_updated: datetime = Field(..., description="Last update timestamp")
    date_created: datetime = Field(..., description="Creation timestamp")

class CreatePipelineFlavorRequest(BaseModel):
    """Request model for creating a new pipeline flavor"""
    pipeline: PipelineType = Field(..., description="Pipeline type")
    title: str = Field(..., min_length=1, max_length=200, description="Flavor title")
    llm_provider: str = Field(..., description="LLM provider identifier")
    llm_model: str = Field(..., description="LLM model name")
    llm_config: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    system_prompt: str = Field(..., min_length=1, description="System prompt template")
    user_prompt: str = Field(..., min_length=1, description="User prompt template")
    enabled: bool = Field(default=True, description="Whether flavor is enabled")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v.lower() == 'default':
            raise ValueError("Cannot create flavor with title 'default' - reserved name")
        return v

class UpdatePipelineFlavorRequest(BaseModel):
    """Request model for updating a pipeline flavor"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Flavor title")
    llm_provider: Optional[str] = Field(None, description="LLM provider identifier")
    llm_model: Optional[str] = Field(None, description="LLM model name")
    llm_config: Optional[LLMConfig] = Field(None, description="LLM configuration")
    system_prompt: Optional[str] = Field(None, min_length=1, description="System prompt template")
    user_prompt: Optional[str] = Field(None, min_length=1, description="User prompt template")
    enabled: Optional[bool] = Field(None, description="Whether flavor is enabled")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v and v.lower() == 'default':
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
    execution_id: Optional[str] = Field(None, description="Execution ID (set when streaming starts)")
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
    selected_definitions: List[str] = Field(default_factory=list, description="Selected sense definitions")
    selected_relations: List[SelectedRelation] = Field(default_factory=list, description="Selected ConceptNet relations")

class DefinitionSuggestionRequest(BaseModel):
    """Request model for term definition suggestion endpoint"""
    term: str = Field(..., description="Term to be analyzed")
    domain_title: Optional[str] = Field(None, description="Title of the domain")
    domain_definition: Optional[str] = Field(None, description="Definition of the domain")
    parent_term_title: Optional[str] = Field(None, description="Title of the parent term")
    parent_term_definition: Optional[str] = Field(None, description="Definition of the parent term")
    parent_relationship_predicate: Optional[str] = Field(None, description="Relationship predicate to parent")
    component_terms: List[ComponentTerm] = Field(default_factory=list, description="Component terms with their context")
    current_definition: Optional[str] = Field(None, alias="current definition", description="Current definition if any")
    dbpedia_context: Dict[str, Any] = Field(default_factory=dict, description="DBpedia context information")
    wikidata_context: Dict[str, Any] = Field(default_factory=dict, description="Wikidata context information")
    flavor: Optional[str] = Field(None, description="Flavor ID or title to use for this request")

class LayerDefinitionRequest(BaseModel):
    """Request model for layer definition suggestion endpoint"""
    layer_title: str = Field(..., description="Title of the layer to be analyzed")
    layer_description: Optional[str] = Field(None, description="Current description of the layer")
    parent_layer_title: Optional[str] = Field(None, description="Title of the parent layer")
    parent_layer_definition: Optional[str] = Field(None, description="Definition of the parent layer")
    contained_domains: List[str] = Field(default_factory=list, description="List of domain titles contained in this layer")
    layer_purpose: Optional[str] = Field(None, description="Purpose or role of this layer")
    current_definition: Optional[str] = Field(None, description="Current definition if any")
    reference_context: Dict[str, Any] = Field(default_factory=dict, description="Additional reference context")
    flavor: Optional[str] = Field(None, description="Flavor ID or title to use for this request")

    @field_validator('layer_title')
    @classmethod
    def validate_layer_title(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Layer title cannot be empty")
        return v

    @field_validator('contained_domains')
    @classmethod
    def validate_contained_domains(cls, v):
        if not v:  # Empty list
            raise ValueError("Contained domains cannot be empty")
        return v

class DomainDefinitionRequest(BaseModel):
    """Request model for domain definition suggestion endpoint"""
    domain_title: str = Field(..., description="Title of the domain to be analyzed")
    domain_description: Optional[str] = Field(None, description="Current description of the domain")
    layer_title: Optional[str] = Field(None, description="Title of the containing layer")
    layer_definition: Optional[str] = Field(None, description="Definition of the containing layer")
    contained_terms: List[str] = Field(default_factory=list, description="List of term titles contained in this domain")
    domain_scope: Optional[str] = Field(None, description="Scope or boundaries of this domain")
    related_domains: List[str] = Field(default_factory=list, description="List of related domain titles")
    current_definition: Optional[str] = Field(None, description="Current definition if any")
    reference_context: Dict[str, Any] = Field(default_factory=dict, description="Additional reference context")
    flavor: Optional[str] = Field(None, description="Flavor ID or title to use for this request")

    @field_validator('domain_title')
    @classmethod
    def validate_domain_title(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Domain title cannot be empty")
        return v

    @field_validator('contained_terms')
    @classmethod
    def validate_contained_terms(cls, v):
        if not v:  # Empty list
            raise ValueError("Contained terms cannot be empty")
        return v

class DefinitionSuggestionResponse(BaseModel):
    """Response model for definition suggestion"""
    definition: str = Field(..., description="The suggested 2-3 sentence definition")
    reasoning: str = Field(..., description="Brief reasoning for the definitional choices")
    discrepancies: Optional[str] = Field(None, description="Notable discrepancies between sources")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class LayerDefinitionResponse(BaseModel):
    """Response model for layer definition suggestion"""
    definition: str = Field(..., description="The suggested 2-3 sentence layer definition")
    purpose: str = Field(..., description="Purpose of the layer in the knowledge structure")
    rationale: str = Field(..., description="Brief rationale for the definitional choices")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class DomainDefinitionResponse(BaseModel):
    """Response model for domain definition suggestion"""
    definition: str = Field(..., description="The suggested 2-3 sentence domain definition")
    purpose: str = Field(..., description="Purpose of the domain in the knowledge structure")
    scope: str = Field(..., description="Scope and boundaries of the domain")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class LLMHealthResponse(BaseModel):
    """Health check response for LLM service"""
    status: str = Field(..., description="Service status")
    model_info: Dict[str, Any] = Field(..., description="Information about the current model")
    timestamp: str = Field(..., description="Timestamp of the health check")

# Error response models
class LLMErrorResponse(BaseModel):
    """Error response for LLM endpoints"""
    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    details: Optional[str] = Field(None, description="Additional error details")

class LLMSuccessResponse(BaseModel):
    """Success response wrapper for LLM endpoints"""
    success: bool = Field(True, description="Always true for success responses")
    data: DefinitionSuggestionResponse = Field(..., description="The response data")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class LayerLLMSuccessResponse(BaseModel):
    """Success response wrapper for layer LLM endpoints"""
    success: bool = Field(True, description="Always true for success responses")
    data: LayerDefinitionResponse = Field(..., description="The response data")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class DomainLLMSuccessResponse(BaseModel):
    """Success response wrapper for domain LLM endpoints"""
    success: bool = Field(True, description="Always true for success responses")
    data: DomainDefinitionResponse = Field(..., description="The response data")
    execution_id: str = Field(..., description="Unique execution ID for tracing")


class RecordSelectionRequest(BaseModel):
    """Request model for recording user selection of LLM suggestions."""
    execution_id: str = Field(..., description="Execution ID from LLM response")
    record_type: str = Field(..., description="Type of record (structure_node, etc.)")
    record_id: str = Field(..., description="Primary key of the record")
    suggestion_field: str = Field(..., description="Field that was selected (definition, etc.)")
    selected_content: str = Field(..., description="The content that was selected")


class SelectionResponse(BaseModel):
    """Response model for selection recording."""
    success: bool = Field(..., description="Whether selection was recorded successfully")
    selection_id: str = Field(..., description="ID of the recorded selection")
    message: str = Field(..., description="Status message")
