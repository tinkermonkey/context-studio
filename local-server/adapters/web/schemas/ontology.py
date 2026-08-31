"""
Pydantic schemas for the Ontology bounded context.

Request schemas (for POST/PUT):
- TaxonomyCreateRequest
- ConceptSchemeCreateRequest
- ClassCreateRequest
- ClassUpdateRequest
- RelationshipCreateRequest
- PropertyDefinitionCreateRequest
- IndividualCreateRequest
- IndividualUpdateRequest
- IndividualClassRequest
- IndividualClassListRequest

Response schemas (for GET/returns):
- TaxonomyResponse
- ConceptSchemeResponse
- ClassResponse
- RelationshipResponse
- PropertyDefinitionResponse
- IndividualResponse

These schemas handle serialization/deserialization between HTTP and domain models.
"""

import re
from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-f]{6}$")


def _validate_identifier(value: str) -> str:
    candidate = value.strip().lower()
    if not _IDENTIFIER_PATTERN.match(candidate):
        raise ValueError(
            "identifier must start with a lowercase letter and contain only "
            "lowercase letters, digits, and underscores (2-64 chars)"
        )
    return candidate


def _validate_color(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if not _HEX_COLOR_PATTERN.match(candidate):
        raise ValueError("color must be a 7-char hex string like '#a3f2e4'")
    return candidate


def slugify_title(text: str) -> str:
    """Generate a slug-style identifier from a title."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ==================== Taxonomy Schemas ====================


class TaxonomyCreateRequest(BaseModel):
    """Request to create a new taxonomy."""

    title: str = Field(..., description="Display name for the taxonomy", min_length=1)
    identifier: Optional[str] = Field(
        None,
        description="Optional slug-style identifier (e.g. 'tax_life'); auto-generated from title",
    )
    description: Optional[str] = Field(None, description="Optional longer description")
    color: Optional[str] = Field(None, description="Optional hex color '#rrggbb'")

    @field_validator("title")
    @classmethod
    def _validate_title_field(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Title cannot be empty")
        return value

    @field_validator("color")
    @classmethod
    def _validate_color_field(cls, value: Optional[str]) -> Optional[str]:
        return _validate_color(value)


class TaxonomyUpdateRequest(BaseModel):
    """Request to update a taxonomy. Identifier is immutable post-create."""

    title: Optional[str] = Field(None, description="New title for the taxonomy", min_length=1)
    description: Optional[str] = Field(None, description="New description")
    color: Optional[str] = Field(None, description="New hex color '#rrggbb' or null to clear")

    @field_validator("color")
    @classmethod
    def _validate_color_field(cls, value: Optional[str]) -> Optional[str]:
        return _validate_color(value)


class TaxonomyPublishRequest(BaseModel):
    """Request to publish a taxonomy."""

    commit_message: str = Field(..., description="Commit message for the publication", min_length=1)


class PublishDiffStats(BaseModel):
    """Response containing diff statistics for publishing."""

    added: int = Field(..., description="Number of classes that will be added")
    modified: int = Field(..., description="Number of classes that will be modified")
    removed: int = Field(..., description="Number of classes that will be removed")


class TaxonomyResponse(BaseModel):
    """Response containing taxonomy data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier (UUID)")
    identifier: str = Field(..., description="Slug-style identifier (e.g. 'tax_life')")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    color: Optional[str] = Field(None, description="Optional hex color '#rrggbb'")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")
    status: Literal["draft", "published"] = Field(
        default="draft", description="Publication status (draft or published)"
    )


# ==================== ConceptScheme Schemas ====================


class ConceptSchemeCreateRequest(BaseModel):
    """Request to create a new concept scheme."""

    title: str = Field(..., description="Display name for the concept scheme", min_length=1)
    identifier: Optional[str] = Field(
        None,
        description="Optional slug-style identifier (e.g. 'scheme_ecology'); auto-generated",
    )
    description: Optional[str] = Field(None, description="Optional longer description")

    @field_validator("title")
    @classmethod
    def _validate_title_field(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Title cannot be empty")
        return value


class ConceptSchemeUpdateRequest(BaseModel):
    """Request to update a concept scheme. Identifier is immutable post-create."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")
    color: Optional[str] = Field(None, description="New hex color '#rrggbb' or null to clear")
    taxonomy_id: Optional[str] = Field(None, description="Move scheme to a different taxonomy")

    @field_validator("color")
    @classmethod
    def _validate_color_field(cls, value: Optional[str]) -> Optional[str]:
        return _validate_color(value)


class ConceptSchemeResponse(BaseModel):
    """Response containing concept scheme data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier (UUID)")
    taxonomy_id: str = Field(..., description="Parent taxonomy ID")
    identifier: str = Field(..., description="Slug-style identifier (e.g. 'scheme_ecology')")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    color: Optional[str] = Field(None, description="Optional hex color '#rrggbb'")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")
    status: Literal["draft", "published"] = Field(
        default="draft", description="Publication status (draft or published)"
    )


# ==================== Class Schemas ====================


class ExternalReferenceRequest(BaseModel):
    """Request to add an external reference."""

    source: str = Field(..., description="Source of the reference (e.g., 'dbpedia', 'wikidata')")
    identifier: str = Field(..., description="External identifier")
    uri: Optional[str] = Field(None, description="URI to external resource")
    metadata: Optional[dict[str, Any]] = Field(None, description="Source-specific metadata")


class LexicalSenseRequest(BaseModel):
    """Request to add a lexical sense."""

    label: str = Field(..., description="The sense label or term")
    language_code: str = Field(..., description="ISO 639-1 language code")
    sense_type: str = Field(..., description="Type of sense (e.g., 'synset', 'word_sense')")


class DataPropertyValueRequest(BaseModel):
    """Request to add a data property value."""

    property_identifier: str = Field(..., description="Property identifier")
    value: str | int | float | bool | None = Field(..., description="Value of the property")
    datatype: Optional[str] = Field(
        None, description="Type of the value (e.g., 'xsd:string', 'xsd:integer')"
    )


class ClassCreateRequest(BaseModel):
    """Request to create a new class."""

    title: str = Field(..., description="Display name for the class", min_length=1)
    identifier: Optional[str] = Field(
        None,
        description="Optional slug-style identifier (e.g. 'cls_gene'); auto-generated from title",
    )
    description: Optional[str] = Field(None, description="Optional longer description")
    parent_class_id: Optional[str] = Field(
        None, description="Optional ID of parent class for hierarchy"
    )

    @field_validator("title")
    @classmethod
    def _validate_title_field(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Title cannot be empty")
        return value


class ClassUpdateRequest(BaseModel):
    """Request to update a class. Identifier is immutable post-create."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")
    color: Optional[str] = Field(None, description="New hex color '#rrggbb' or null to clear")

    @field_validator("color")
    @classmethod
    def _validate_color_field(cls, value: Optional[str]) -> Optional[str]:
        return _validate_color(value)


class ClassMoveRequest(BaseModel):
    """Request to move a class to a different concept scheme."""

    target_scheme_id: str = Field(..., description="ID of the target concept scheme")


class ExternalReferenceResponse(BaseModel):
    """Response containing external reference data."""

    model_config = ConfigDict(from_attributes=True)

    source: str = Field(..., description="Source of the reference")
    identifier: str = Field(..., description="External identifier")
    uri: Optional[str] = Field(None, description="External URI")
    metadata: Optional[dict[str, Any]] = Field(None, description="Source-specific metadata")


class LexicalSenseResponse(BaseModel):
    """Response containing lexical sense data."""

    model_config = ConfigDict(from_attributes=True)

    label: str = Field(..., description="The sense label or term")
    language_code: str = Field(..., description="ISO 639-1 language code")
    sense_type: str = Field(..., description="Type of sense")


class DataPropertyValueResponse(BaseModel):
    """Response containing data property value."""

    model_config = ConfigDict(from_attributes=True)

    property_identifier: str = Field(..., description="Property identifier")
    value: str | int | float | bool | None = Field(..., description="Value of the property")
    datatype: Optional[str] = Field(None, description="Type of the value")


class ClassResponse(BaseModel):
    """Response containing class data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier (UUID)")
    concept_scheme_id: str = Field(..., description="Parent concept scheme ID")
    taxonomy_id: str = Field(..., description="Parent taxonomy ID")
    identifier: str = Field(..., description="Slug-style identifier (e.g. 'cls_organism')")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    color: Optional[str] = Field(None, description="Optional hex color '#rrggbb'")
    parent_class_id: Optional[str] = Field(None, description="Optional parent class ID")
    structural_property_id: Optional[str] = Field(
        None, description="Optional structural property ID"
    )
    external_references: list[ExternalReferenceResponse] = Field(default_factory=list)
    lexical_senses: list[LexicalSenseResponse] = Field(default_factory=list)
    data_properties: list[DataPropertyValueResponse] = Field(default_factory=list)
    embedding: Optional[list[float]] = Field(None, description="Optional semantic embedding")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")
    status: Literal["draft", "published"] = Field(
        default="draft", description="Publication status (draft or published)"
    )


# ==================== Relationship Schemas ====================


class RelationshipCreateRequest(BaseModel):
    """Request to create a new relationship."""

    source_id: str = Field(..., description="ID of source entity")
    target_id: str = Field(..., description="ID of target entity")
    relationship_type: str = Field(
        ...,
        description="Relationship type identifier (e.g., 'related_to', 'parent_of')",
    )


class RelationshipResponse(BaseModel):
    """Response containing relationship data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    property_definition_id: str = Field(
        ..., description="Property definition ID (relationship type)"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


# ==================== PropertyDefinition Schemas ====================


class PropertyDefinitionCreateRequest(BaseModel):
    """Request to create a new property definition."""

    identifier: str = Field(..., description="Machine-readable identifier", min_length=1)
    title: str = Field(..., description="Display name for the property", min_length=1)
    description: Optional[str] = Field(None, description="Optional longer description")
    canonical_predicate: Optional[str] = Field(
        None,
        description=(
            "Bare canonical relation verb this property represents (e.g. "
            "'navigates-to') — the form extraction clamps predicates to"
        ),
    )


class PropertyDefinitionUpdateRequest(BaseModel):
    """Request to update a property definition."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")
    canonical_predicate: Optional[str] = Field(
        None,
        description=(
            "New bare canonical relation verb, or null to clear it. Only applied "
            "when the field is present in the request body."
        ),
    )
    is_relevant: Optional[bool] = Field(
        None,
        description="Relevance flag (None=not evaluated, True=relevant, False=irrelevant)",
    )


class PropertyDefinitionResponse(BaseModel):
    """Response containing property definition data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    identifier: str = Field(..., description="Machine-readable identifier")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    canonical_predicate: Optional[str] = Field(
        None,
        description=(
            "Bare canonical relation verb this property represents (e.g. "
            "'navigates-to'), or null if not set"
        ),
    )
    is_relevant: Optional[bool] = Field(
        None,
        description=("Relevance flag (None=not evaluated, True=relevant, False=irrelevant)"),
    )
    lexical_senses: list[LexicalSenseResponse] = Field(
        default_factory=list,
        description=(
            "Word-sense disambiguation entries. A property whose label has "
            "more than one distinct meaning across the corpus (e.g. 'service' "
            "or 'clock') carries one LexicalSense per sense."
        ),
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")
    status: Literal["draft", "published"] = Field(
        default="draft", description="Publication status (draft or published)"
    )


# ==================== Individual Schemas ====================


class IndividualCreateRequest(BaseModel):
    """Request to create a new individual."""

    class_ids: list[str] | str = Field(
        ...,
        description="ID(s) of the class(es) this individual instantiates (≥1 required)",
    )
    title: str = Field(..., description="Display name for the individual", min_length=1)
    description: Optional[str] = Field(None, description="Optional longer description")

    @field_validator("class_ids", mode="before")
    @classmethod
    def validate_class_ids(cls, v: list[str] | str) -> list[str]:
        """Normalize class_ids to list and validate it's not empty."""
        # Normalize string to list
        if isinstance(v, str):
            v = [v]

        # Reject empty lists
        if not v:
            raise ValueError("At least one class ID is required")

        return v


class IndividualUpdateRequest(BaseModel):
    """Request to update an individual."""

    title: Optional[str] = Field(None, description="New title for the individual", min_length=1)
    description: Optional[str] = Field(None, description="New description")


class IndividualResponse(BaseModel):
    """Response containing individual data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    class_ids: list[str] = Field(..., description="Ordered list of parent class IDs")
    title: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Optional description")
    data_properties: list[DataPropertyValueResponse] = Field(default_factory=list)
    external_references: list[ExternalReferenceResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")
    status: Literal["draft", "published"] = Field(
        default="draft", description="Publication status (draft or published)"
    )


class IndividualClassRequest(BaseModel):
    """Request to manage individual class membership."""

    class_id: str = Field(..., description="ID of the class")


class IndividualClassListRequest(BaseModel):
    """Request to reorder individual class membership."""

    class_ids: list[str] = Field(
        ..., description="Ordered list of class IDs (must match current membership)"
    )


# ==================== AttributeDefinition Schemas ====================


class AttributeDefinitionCreateRequest(BaseModel):
    """Request to create a new attribute definition."""

    identifier: str = Field(..., description="Machine-readable identifier", min_length=1)
    title: str = Field(..., description="Display name for the attribute", min_length=1)
    datatype: str = Field(
        ...,
        description="Data type (e.g. 'string', 'integer', 'boolean', 'array', 'object')",
        min_length=1,
    )
    description: Optional[str] = Field(None, description="Optional longer description")
    is_required: bool = Field(False, description="Whether attribute is required on instances")
    allowed_values: Optional[list[str]] = Field(None, description="Optional enum constraint")
    default_value: Optional[str] = Field(None, description="Optional default value")
    sort_order: int = Field(0, description="Display order within the class's attribute list")

    @field_validator("title")
    @classmethod
    def _validate_title_field(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Title cannot be empty")
        return value

    @field_validator("datatype")
    @classmethod
    def _validate_datatype_field(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Datatype cannot be empty")
        valid_types = {"string", "integer", "boolean", "array", "object"}
        if value.strip().lower() not in valid_types:
            raise ValueError(
                f"Invalid datatype '{value}'. Must be one of: {', '.join(sorted(valid_types))}"
            )
        return value.strip().lower()


class AttributeDefinitionUpdateRequest(BaseModel):
    """Request to update an attribute definition (partial update)."""

    title: Optional[str] = Field(None, description="New title", min_length=1)
    description: Optional[str] = Field(None, description="New description")
    datatype: Optional[str] = Field(
        None,
        description="New data type (e.g. 'string', 'integer', 'boolean', 'array', 'object')",
        min_length=1,
    )
    is_required: Optional[bool] = Field(None, description="Update required flag")
    allowed_values: Optional[list[str]] = Field(
        None, description="Update enum constraint; pass [] to clear"
    )
    default_value: Optional[str] = Field(
        None, description="Update default value; pass empty string to clear"
    )
    sort_order: Optional[int] = Field(None, description="Update display order")

    @field_validator("datatype")
    @classmethod
    def _validate_datatype_field(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("Datatype cannot be empty")
        if value is not None:
            valid_types = {"string", "integer", "boolean", "array", "object"}
            if value.strip().lower() not in valid_types:
                raise ValueError(
                    f"Invalid datatype '{value}'. Must be one of: {', '.join(sorted(valid_types))}"
                )
            return value.strip().lower()
        return value


class AttributeDefinitionResponse(BaseModel):
    """Response containing attribute definition data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier (UUID)")
    class_id: str = Field(..., description="Parent class ID")
    identifier: str = Field(..., description="Machine-readable identifier")
    title: str = Field(..., description="Display name")
    datatype: str = Field(..., description="Data type (e.g. 'string', 'integer', 'boolean')")
    description: Optional[str] = Field(None, description="Optional description")
    is_required: bool = Field(False, description="Whether this attribute is required")
    allowed_values: Optional[list[str]] = Field(None, description="Optional enum constraint")
    default_value: Optional[str] = Field(None, description="Optional default value")
    sort_order: int = Field(0, description="Display order within the class's attributes")
    external_references: list[ExternalReferenceResponse] = Field(
        default_factory=list, description="References to external knowledge bases"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    version: int = Field(default=1, description="Version number for optimistic concurrency control")
    status: Literal["draft", "published"] = Field(
        default="draft", description="Publication status (draft or published)"
    )
    source_run_id: Optional[str] = Field(
        None, description="ID of the pipeline run that created or last modified this entity"
    )


# ==================== List Response Schemas ====================


class ListResponse(BaseModel, Generic[T]):
    """Generic paginated list response."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")


# ==================== Error Response Schema ====================


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")
