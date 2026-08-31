"""
API Models for Ontology Entities

This module contains the Pydantic models for the new ontology_entities API,
using new terminology (taxonomy, concept_scheme, class) alongside the
existing structure_nodes API.
"""

import re
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class EntityTypeEnum(str, Enum):
    """API enum for ontology entity types (new terminology)."""

    TAXONOMY = "taxonomy"
    CONCEPT_SCHEME = "concept_scheme"
    CLASS = "class"


class EntityBase(BaseModel):
    """Base model for ontology entity data."""

    node_type: EntityTypeEnum
    parent_entity_id: UUID | None = None
    title: str = Field(..., min_length=2, max_length=255)
    definition: str | None = None
    structural_predicate_id: UUID | None = None


class EntityCreate(EntityBase):
    """Model for creating a new ontology entity."""

    @field_validator("parent_entity_id")
    @classmethod
    def validate_parent_for_type(cls, v, info):
        """Validate parent entity requirements based on entity type."""
        node_type = info.data.get("node_type")
        if node_type == EntityTypeEnum.TAXONOMY and v is not None:
            raise ValueError("Taxonomies cannot have parent entities")
        if (
            node_type in [EntityTypeEnum.CONCEPT_SCHEME, EntityTypeEnum.CLASS]
            and v is None
        ):
            raise ValueError(
                f"{node_type.value.title().replace('_', ' ')} must have a parent entity"
            )
        return v


class EntityUpdate(BaseModel):
    """Model for updating an existing ontology entity."""

    title: str | None = Field(None, min_length=2, max_length=255)
    definition: str | None = None
    parent_entity_id: UUID | None = None
    structural_predicate_id: UUID | None = None


class EntityOut(EntityBase):
    """Model for ontology entity output/response."""

    id: UUID
    title_embedding: list[float] | None = None
    definition_embedding: list[float] | None = None
    created_at: str  # ISO8601 string
    version: int
    last_modified: str  # ISO8601 string

    model_config = ConfigDict(from_attributes=True)


class RelationshipBase(BaseModel):
    """Base model for entity relationships."""

    source_entity_id: UUID
    target_entity_id: UUID
    predicate: str
    predicate_id: UUID | None = None


class RelationshipCreate(RelationshipBase):
    """Model for creating a new entity relationship."""



class RelationshipOut(RelationshipBase):
    """Model for entity relationship output/response."""

    id: UUID
    created_at: str  # ISO8601 string

    model_config = ConfigDict(from_attributes=True)


class EntitySearchRequest(BaseModel):
    """Model for ontology entity search requests."""

    query: str = Field(..., min_length=1, description="Search query text")
    node_type: EntityTypeEnum | None = Field(
        None, description="Filter by entity type"
    )
    parent_entity_id: UUID | None = Field(
        None, description="Filter by parent entity"
    )
    threshold: float | None = Field(
        0.0, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    limit: int | None = Field(
        20, ge=1, le=100, description="Maximum number of results"
    )


class EntitySearchResult(EntityOut):
    """Model for ontology entity search results."""

    score: float
    distance: float


class PaginatedEntitiesResponse(BaseModel):
    """Model for paginated ontology entity responses."""

    data: list[EntityOut]
    total: int
    skip: int
    limit: int


class PaginatedRelationshipsResponse(BaseModel):
    """Model for paginated entity relationship responses."""

    data: list[RelationshipOut]
    total: int
    skip: int
    limit: int


# Move operation models (using new terminology)
class MoveEntitiesRequest(BaseModel):
    """Model for moving ontology entities to a new parent."""

    entity_ids: list[UUID] = Field(
        ..., min_length=1, description="List of entity IDs to move"
    )
    target_parent_id: UUID | None = Field(
        None, description="Target parent entity ID (None for root level)"
    )
    move_children: bool = Field(
        True, description="Whether to move all child entities"
    )
    handle_conflicts: str = Field(
        "warn",
        pattern="^(warn|rename|error)$",
        description="How to handle title conflicts",
    )


class MoveEntitiesResponse(BaseModel):
    """Model for move operation results with automatic type conversion."""

    moved_entities: list[EntityOut] = Field(
        description="List of successfully moved entities"
    )
    updated_children: list[EntityOut] = Field(
        description="List of child entities that were also moved"
    )
    converted_entities: list[EntityOut] = Field(
        default_factory=list,
        description="List of entities that had their type automatically converted",
    )
    warnings: list[str] = Field(
        description="List of warnings encountered during the move"
    )
    errors: list[str] = Field(
        description="List of errors that prevented some moves"
    )


# Utility models for hierarchy operations
class EntityHierarchy(BaseModel):
    """Model representing an ontology entity with its children."""

    entity: EntityOut
    children: list["EntityHierarchy"] = []

    model_config = ConfigDict(from_attributes=True)


# Update forward references
EntityHierarchy.model_rebuild()


# Models for Reference Links and Word Senses (reusing same concepts from structure_nodes)
class ReferenceLink(BaseModel):
    """Model for reference data links from external knowledge sources."""

    source: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Source identifier (e.g., 'schema.org', 'wikidata', 'conceptnet')",
    )
    external_id: str = Field(
        ..., min_length=1, max_length=255, description="Source-specific identifier"
    )

    model_config = ConfigDict(from_attributes=True)


class WordSense(BaseModel):
    """Model for word sense identifiers from NLP analysis."""

    term: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The term/word this sense refers to",
    )
    sense_type: str = Field(
        ..., description="Type of sense system (e.g., 'wordnet')"
    )
    sense_id: str = Field(
        ..., description="Unique identifier for the sense (e.g., 'bank.n.01')"
    )
    definition: str = Field(
        ..., description="Human-readable definition of the sense"
    )
    domain: str | None = Field(
        None, description="Semantic domain or category (e.g., 'noun.group')"
    )

    model_config = ConfigDict(from_attributes=True)


class SelectedWordSensesUpdate(BaseModel):
    """Model for updating selected word senses on an entity."""

    selected_senses: list[WordSense] = Field(
        ..., description="List of word senses to persist as selected"
    )

    model_config = ConfigDict(from_attributes=True)


class AttributeValueType(str, Enum):
    """Enum for supported attribute value types."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    URL = "url"


class EntityAttribute(BaseModel):
    """Model for entity attributes with type validation."""

    key: str = Field(
        ..., pattern="^[a-z][a-z0-9_]*$", description="Underscore-delimited identifier"
    )
    title: str = Field(..., min_length=1, description="Human-readable display name")
    value_type: AttributeValueType = Field(
        ..., description="Type constraint for values"
    )
    value: Any | None = Field(None, description="The actual attribute value")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("value")
    @classmethod
    def validate_value_type(cls, v, info):
        """Validate value matches declared value_type."""
        if v is None:
            return v

        value_type = info.data.get("value_type")

        if value_type == AttributeValueType.STRING:
            return str(v)
        elif value_type == AttributeValueType.NUMBER:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError("Value must be numeric")
            return v
        elif value_type == AttributeValueType.BOOLEAN:
            if not isinstance(v, bool):
                raise ValueError("Value must be boolean")
            return v
        elif value_type == AttributeValueType.DATE:
            # Validate ISO 8601 format
            if not re.match(r"^\d{4}-\d{2}-\d{2}", str(v)):
                raise ValueError("Date must be ISO 8601 format")
            return str(v)
        elif value_type == AttributeValueType.URL:
            # Validate RFC 3986 compliant URLs
            url_str = str(v)
            if not url_str.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return url_str

        return v


class ResolvedAttribute(EntityAttribute):
    """Model for resolved attributes with inheritance information."""

    inherited: bool = Field(False, description="True if inherited from ancestor")
    source_entity_id: UUID | None = Field(
        None, description="ID of the entity defining this attribute"
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_inheritance_relationship(self):
        """Validate inherited flag matches source_entity_id presence."""
        if self.inherited and self.source_entity_id is None:
            raise ValueError("Inherited attributes must have source_entity_id")
        return self


class SetEntityAttributesRequest(BaseModel):
    """Request model for setting entity attributes with optimistic locking support."""

    attributes: list[EntityAttribute] = Field(
        ..., description="List of attributes to set on the entity"
    )
    expected_version: int | None = Field(
        None,
        description="Expected entity version for optimistic locking. If provided, the update will fail with 409 Conflict if the current version doesn't match.",
    )

    model_config = ConfigDict(from_attributes=True)
