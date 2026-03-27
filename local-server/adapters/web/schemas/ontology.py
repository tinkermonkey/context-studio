"""
Pydantic schemas for the Ontology bounded context.

Request schemas (for POST/PUT):
- TaxonomyCreateRequest
- ConceptSchemeCreateRequest
- ClassCreateRequest
- ClassUpdateRequest
- RelationshipCreateRequest
- PropertyDefinitionCreateRequest

Response schemas (for GET/returns):
- TaxonomyResponse
- ConceptSchemeResponse
- ClassResponse
- RelationshipResponse
- PropertyDefinitionResponse

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== Taxonomy Schemas ====================

class TaxonomyCreateRequest(BaseModel):
    """Request to create a new taxonomy."""

    title: str = Field(..., description="Display name for the taxonomy", min_length=1)
    description: Optional[str] = Field(None, description="Optional longer description")


class TaxonomyUpdateRequest(BaseModel):
    """Request to update a taxonomy."""

    title: Optional[str] = Field(None, description="New title for the taxonomy", min_length=1)
    description: Optional[str] = Field(None, description="New description")


class TaxonomyResponse(BaseModel):
    """Response containing taxonomy data."""

    id: str = Field(..., description="Unique identifier")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")

    class Config:
        from_attributes = True


# ==================== ConceptScheme Schemas ====================

class ConceptSchemeCreateRequest(BaseModel):
    """Request to create a new concept scheme."""

    title: str = Field(..., description="Display name for the concept scheme", min_length=1)
    description: Optional[str] = Field(None, description="Optional longer description")


class ConceptSchemeUpdateRequest(BaseModel):
    """Request to update a concept scheme."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")


class ConceptSchemeResponse(BaseModel):
    """Response containing concept scheme data."""

    id: str = Field(..., description="Unique identifier")
    taxonomy_id: str = Field(..., description="Parent taxonomy ID")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")

    class Config:
        from_attributes = True


# ==================== Class Schemas ====================

class ExternalReferenceRequest(BaseModel):
    """Request to add an external reference."""

    uri: str = Field(..., description="URI to external resource")
    label: Optional[str] = Field(None, description="Display label for the reference")
    source: Optional[str] = Field(None, description="Source of the reference (e.g., 'dbpedia', 'wikidata')")


class LexicalSenseRequest(BaseModel):
    """Request to add a lexical sense."""

    word_sense: str = Field(..., description="Word sense identifier (e.g., 'synset-123')")
    definition: Optional[str] = Field(None, description="Definition of the sense")


class DataPropertyValueRequest(BaseModel):
    """Request to add a data property value."""

    property_name: str = Field(..., description="Name of the property")
    value: str = Field(..., description="Value of the property")
    value_type: Optional[str] = Field(None, description="Type of the value (e.g., 'string', 'integer')")


class ClassCreateRequest(BaseModel):
    """Request to create a new class."""

    title: str = Field(..., description="Display name for the class", min_length=1)
    description: Optional[str] = Field(None, description="Optional longer description")
    parent_class_id: Optional[str] = Field(None, description="Optional ID of parent class for hierarchy")


class ClassUpdateRequest(BaseModel):
    """Request to update a class."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")


class ClassMoveRequest(BaseModel):
    """Request to move a class to a different parent."""

    new_parent_id: Optional[str] = Field(None, description="ID of new parent class, or null to make root")


class ExternalReferenceResponse(BaseModel):
    """Response containing external reference data."""

    uri: str
    label: Optional[str] = None
    source: Optional[str] = None


class LexicalSenseResponse(BaseModel):
    """Response containing lexical sense data."""

    word_sense: str
    definition: Optional[str] = None


class DataPropertyValueResponse(BaseModel):
    """Response containing data property value."""

    property_name: str
    value: str
    value_type: Optional[str] = None


class ClassResponse(BaseModel):
    """Response containing class data."""

    id: str = Field(..., description="Unique identifier")
    concept_scheme_id: str = Field(..., description="Parent concept scheme ID")
    taxonomy_id: str = Field(..., description="Parent taxonomy ID")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    parent_class_id: Optional[str] = Field(None, description="Optional parent class ID")
    structural_property_id: Optional[str] = Field(None, description="Optional structural property ID")
    external_references: list[ExternalReferenceResponse] = Field(default_factory=list)
    lexical_senses: list[LexicalSenseResponse] = Field(default_factory=list)
    data_properties: list[DataPropertyValueResponse] = Field(default_factory=list)
    embedding: Optional[list[float]] = Field(None, description="Optional semantic embedding")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")

    class Config:
        from_attributes = True


# ==================== Relationship Schemas ====================

class RelationshipCreateRequest(BaseModel):
    """Request to create a new relationship."""

    source_id: str = Field(..., description="ID of source entity")
    target_id: str = Field(..., description="ID of target entity")
    property_definition_id: str = Field(..., description="ID of property definition (relationship type)")


class RelationshipResponse(BaseModel):
    """Response containing relationship data."""

    id: str = Field(..., description="Unique identifier")
    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    property_definition_id: str = Field(..., description="Property definition ID (relationship type)")

    class Config:
        from_attributes = True


# ==================== PropertyDefinition Schemas ====================

class PropertyDefinitionCreateRequest(BaseModel):
    """Request to create a new property definition."""

    identifier: str = Field(..., description="Machine-readable identifier", min_length=1)
    title: str = Field(..., description="Display name for the property", min_length=1)
    description: Optional[str] = Field(None, description="Optional longer description")


class PropertyDefinitionUpdateRequest(BaseModel):
    """Request to update a property definition."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")


class PropertyDefinitionResponse(BaseModel):
    """Response containing property definition data."""

    id: str = Field(..., description="Unique identifier")
    identifier: str = Field(..., description="Machine-readable identifier")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    is_relevant: bool = Field(default=True, description="Whether this property is relevant")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")

    class Config:
        from_attributes = True


# ==================== List Response Schemas ====================

class ListResponse(BaseModel):
    """Generic paginated list response."""

    items: list = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")

    class Config:
        from_attributes = True


# ==================== Error Response Schema ====================

class ErrorResponse(BaseModel):
    """Error response."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")
