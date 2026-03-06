"""
API Models for StructureNodes

This module contains the Pydantic models for the unified structure_nodes API,
supporting the Great Normalization requirements.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict  # noqa: E501
from typing import Optional, List, Any
from uuid import UUID
from enum import Enum
import re


class NodeTypeEnum(str, Enum):
    """API enum for structure_node types."""
    LAYER = "layer"
    DOMAIN = "domain"
    TERM = "term"


class NodeBase(BaseModel):
    """Base model for structure_node data."""
    node_type: NodeTypeEnum
    parent_node_id: Optional[UUID] = None
    title: str = Field(..., min_length=2, max_length=255)
    definition: Optional[str] = None
    structural_predicate_id: Optional[UUID] = None


class NodeCreate(NodeBase):
    """Model for creating a new structure_node."""

    @field_validator('parent_node_id')
    @classmethod
    def validate_parent_for_type(cls, v, info):
        """Validate parent structure_node requirements based on structure_node type."""  # noqa: E501
        node_type = info.data.get('node_type')
        if node_type == NodeTypeEnum.LAYER and v is not None:
            raise ValueError("Layers cannot have parent structure_nodes")
        if node_type in [NodeTypeEnum.DOMAIN, NodeTypeEnum.TERM] and v is None:
            raise ValueError(f"{node_type.value.title()} must have a parent structure_node")  # noqa: E501
        return v


class NodeUpdate(BaseModel):
    """Model for updating an existing structure_node."""
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    definition: Optional[str] = None
    parent_node_id: Optional[UUID] = None
    structural_predicate_id: Optional[UUID] = None


class NodeOut(NodeBase):
    """Model for structure_node output/response."""
    id: UUID
    title_embedding: Optional[List[float]] = None
    definition_embedding: Optional[List[float]] = None
    created_at: str  # ISO8601 string
    version: int
    last_modified: str  # ISO8601 string

    model_config = ConfigDict(from_attributes=True)


class NodeLinkBase(BaseModel):
    """Base model for structure_node links."""
    source_node_id: UUID
    target_node_id: UUID
    predicate: str
    predicate_id: Optional[UUID] = None


class NodeLinkCreate(NodeLinkBase):
    """Model for creating a new structure_node link."""
    pass


class NodeLinkOut(NodeLinkBase):
    """Model for structure_node link output/response."""
    id: UUID
    created_at: str  # ISO8601 string

    model_config = ConfigDict(from_attributes=True)


class NodeSearchRequest(BaseModel):
    """Model for structure_node search requests."""
    query: str = Field(..., min_length=1, description="Search query text")
    node_type: Optional[NodeTypeEnum] = Field(None, description="Filter by node type")  # noqa: E501
    parent_node_id: Optional[UUID] = Field(None, description="Filter by parent node")  # noqa: E501
    threshold: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score")  # noqa: E501
    limit: Optional[int] = Field(20, ge=1, le=100, description="Maximum number of results")  # noqa: E501


class NodeSearchResult(NodeOut):
    """Model for structure_node search results."""
    score: float
    distance: float


class PaginatedNodesResponse(BaseModel):
    """Model for paginated structure_node responses."""
    data: List[NodeOut]
    total: int
    skip: int
    limit: int


class PaginatedNodeLinksResponse(BaseModel):
    """Model for paginated structure_node link responses."""
    data: List[NodeLinkOut]
    total: int
    skip: int
    limit: int


# Move operation models
class MoveNodesRequest(BaseModel):
    """Model for moving structure_nodes to a new parent."""
    node_ids: List[UUID] = Field(..., min_length=1, description="List of structure_node IDs to move")  # noqa: E501
    target_parent_id: Optional[UUID] = Field(None, description="Target parent structure_node ID (None for root level)")  # noqa: E501
    move_children: bool = Field(True, description="Whether to move all child structure_nodes")  # noqa: E501
    handle_conflicts: str = Field("warn", pattern="^(warn|rename|error)$", description="How to handle title conflicts")  # noqa: E501


class MoveNodesResponse(BaseModel):
    """Model for move operation results with automatic type conversion."""
    moved_nodes: List[NodeOut] = Field(description="List of successfully moved structure_nodes")  # noqa: E501
    updated_children: List[NodeOut] = Field(description="List of child structure_nodes that were also moved")  # noqa: E501
    converted_nodes: List[NodeOut] = Field(default_factory=list, description="List of nodes that had their type automatically converted")  # noqa: E501
    warnings: List[str] = Field(description="List of warnings encountered during the move")  # noqa: E501
    errors: List[str] = Field(description="List of errors that prevented some moves")  # noqa: E501


# Utility models for hierarchy operations
class NodeHierarchy(BaseModel):
    """Model representing a structure_node with its children."""
    structure_node: NodeOut
    children: List['NodeHierarchy'] = []

    model_config = ConfigDict(from_attributes=True)


# Update forward references
NodeHierarchy.model_rebuild()


# Models for Reference Links and Word Senses
class ReferenceLink(BaseModel):
    """Model for reference data links from external knowledge sources."""
    source: str = Field(..., min_length=1, max_length=255, description="Source identifier (e.g., 'schema.org', 'wikidata', 'conceptnet')")  # noqa: E501
    external_id: str = Field(..., min_length=1, max_length=255, description="Source-specific identifier")  # noqa: E501

    model_config = ConfigDict(from_attributes=True)


class WordSense(BaseModel):
    """Model for word sense identifiers from NLP analysis."""
    term: str = Field(..., min_length=1, max_length=255, description="The term/word this sense refers to")  # noqa: E501
    sense_type: str = Field(..., description="Type of sense system (e.g., 'wordnet')")  # noqa: E501
    sense_id: str = Field(..., description="Unique identifier for the sense (e.g., 'bank.n.01')")  # noqa: E501
    definition: str = Field(..., description="Human-readable definition of the sense")  # noqa: E501
    domain: Optional[str] = Field(None, description="Semantic domain or category (e.g., 'noun.group')")  # noqa: E501

    model_config = ConfigDict(from_attributes=True)


class SelectedWordSensesUpdate(BaseModel):
    """Model for updating selected word senses on a structure node."""
    selected_senses: List[WordSense] = Field(..., description="List of word senses to persist as selected")  # noqa: E501

    model_config = ConfigDict(from_attributes=True)


class AttributeValueType(str, Enum):
    """Enum for supported attribute value types."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    URL = "url"


class StructureNodeAttribute(BaseModel):
    """Model for structure node attributes with type validation."""
    key: str = Field(
        ...,
        pattern="^[a-z][a-z0-9_]*$",
        description="Underscore-delimited identifier"
    )
    title: str = Field(
        ...,
        min_length=1,
        description="Human-readable display name"
    )
    value_type: AttributeValueType = Field(
        ...,
        description="Type constraint for values"
    )
    value: Optional[Any] = Field(
        None,
        description="The actual attribute value"
    )

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


class ResolvedAttribute(StructureNodeAttribute):
    """Model for resolved attributes with inheritance information."""
    inherited: bool = Field(
        False,
        description="True if inherited from ancestor"
    )
    source_node_id: Optional[UUID] = Field(
        None,
        description="ID of the node defining this attribute"
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def validate_inheritance_relationship(self):
        """Validate inherited flag matches source_node_id presence."""
        if self.inherited and self.source_node_id is None:
            raise ValueError("Inherited attributes must have source_node_id")
        return self


class SetNodeAttributesRequest(BaseModel):
    """Request model for setting node attributes with optimistic locking support."""  # noqa: E501
    attributes: List[StructureNodeAttribute] = Field(
        ...,
        description="List of attributes to set on the node"
    )
    expected_version: Optional[int] = Field(
        None,
        description="Expected node version for optimistic locking. If provided, the update will fail with 409 Conflict if the current version doesn't match."  # noqa: E501
    )

    model_config = ConfigDict(from_attributes=True)
