"""
API Models for Nodes

This module contains the Pydantic models for the unified nodes API,
supporting the Great Normalization requirements.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from uuid import UUID
from enum import Enum
from datetime import datetime


class NodeTypeEnum(str, Enum):
    """API enum for node types."""
    LAYER = "layer"
    DOMAIN = "domain"
    TERM = "term"


class NodeBase(BaseModel):
    """Base model for node data."""
    node_type: NodeTypeEnum
    parent_node_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=255)
    definition: Optional[str] = None
    structural_predicate_id: Optional[UUID] = None


class NodeCreate(NodeBase):
    """Model for creating a new node."""
    
    @field_validator('parent_node_id')
    @classmethod
    def validate_parent_for_type(cls, v, info):
        """Validate parent node requirements based on node type."""
        node_type = info.data.get('node_type')
        if node_type == NodeTypeEnum.LAYER and v is not None:
            raise ValueError("Layers cannot have parent nodes")
        if node_type in [NodeTypeEnum.DOMAIN, NodeTypeEnum.TERM] and v is None:
            raise ValueError(f"{node_type.value.title()} must have a parent node")
        return v


class NodeUpdate(BaseModel):
    """Model for updating an existing node."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    definition: Optional[str] = None
    parent_node_id: Optional[UUID] = None
    structural_predicate_id: Optional[UUID] = None


class NodeOut(NodeBase):
    """Model for node output/response."""
    id: UUID
    title_embedding: Optional[List[float]] = None
    definition_embedding: Optional[List[float]] = None
    created_at: str  # ISO8601 string
    version: int
    last_modified: str  # ISO8601 string

    model_config = ConfigDict(from_attributes=True)


class NodeLinkBase(BaseModel):
    """Base model for node links."""
    source_node_id: UUID
    target_node_id: UUID
    predicate: str
    predicate_id: Optional[UUID] = None


class NodeLinkCreate(NodeLinkBase):
    """Model for creating a new node link."""
    pass


class NodeLinkOut(NodeLinkBase):
    """Model for node link output/response."""
    id: UUID
    created_at: str  # ISO8601 string

    model_config = ConfigDict(from_attributes=True)


class NodeSearchRequest(BaseModel):
    """Model for node search requests."""
    title: Optional[str] = None
    definition: Optional[str] = None
    node_type: Optional[NodeTypeEnum] = None
    parent_node_id: Optional[UUID] = None
    created_at: Optional[str] = None  # ISO8601 string
    minimum_score: Optional[float] = Field(0.7, ge=0.0, le=1.0)
    limit: Optional[int] = Field(10, ge=1, le=100)


class NodeSearchResult(NodeOut):
    """Model for node search results."""
    score: float
    distance: float


class PaginatedNodesResponse(BaseModel):
    """Model for paginated node responses."""
    data: List[NodeOut]
    total: int
    skip: int
    limit: int


# Utility models for hierarchy operations
class NodeHierarchy(BaseModel):
    """Model representing a node with its children."""
    node: NodeOut
    children: List['NodeHierarchy'] = []

    model_config = ConfigDict(from_attributes=True)


# Update forward references
NodeHierarchy.model_rebuild()
