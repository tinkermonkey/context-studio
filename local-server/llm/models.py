from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

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
    """Request model for definition suggestion endpoint"""
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

class DefinitionSuggestionResponse(BaseModel):
    """Response model for definition suggestion"""
    definition: str = Field(..., description="The suggested 2-3 sentence definition")
    reasoning: str = Field(..., description="Brief reasoning for the definitional choices")
    discrepancies: Optional[str] = Field(None, description="Notable discrepancies between sources")

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
