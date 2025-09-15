"""Unified data models for the Context Studio reference facade"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Any, List
from enum import Enum
from datetime import datetime

class ReferenceSource(str, Enum):
    """Supported reference sources in the unified facade"""
    CONCEPTNET = "conceptnet"
    WORDNET = "wordnet"
    DBPEDIA = "dbpedia"
    WIKIDATA = "wikidata"
    SCHEMA_ORG = "schema_org"

class UnifiedNode(BaseModel):
    """Unified node representation across all reference sources"""
    id: str = Field(..., description="Unique identifier for cross-source deduplication")
    source: ReferenceSource = Field(..., description="Original source of the node")
    source_id: str = Field(..., description="Original ID in source system")
    title: str = Field(..., min_length=1, description="Primary label or title")
    definition: Optional[str] = Field(None, description="Definition or description")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Source-specific attributes")
    source_url: Optional[str] = Field(None, description="URL to original resource")
    confidence_score: float = Field(default=1.0, ge=0, le=1, description="Confidence in data quality")
    merged_from: Optional[List[str]] = Field(None, description="Track deduplication sources")

    @field_validator('source_url')
    @classmethod
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Invalid URL format')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UnifiedLink(BaseModel):
    """Unified link representation across all reference sources"""
    id: str = Field(..., description="Unique identifier for the link")
    source: ReferenceSource = Field(..., description="Original source of the link")
    subject: str = Field(..., description="Subject node ID or URL")
    predicate: str = Field(..., description="Relationship type or predicate")
    object: str = Field(..., description="Object node ID or URL")
    weight: float = Field(default=1.0, ge=0, le=1, description="Relationship strength")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Source-specific attributes")

class UnifiedSearchRequest(BaseModel):
    """Search request model for unified facade"""
    query: str = Field(..., min_length=1, description="Search query string")
    search_type: str = Field(default="title", pattern="^(title|definition|predicate)$", description="Type of search to perform")
    sources: Optional[List[ReferenceSource]] = Field(None, description="Specific sources to search (default: all)")
    node_id: Optional[str] = Field(None, description="Node ID for link searches")
    direction: Optional[str] = Field(default="both", pattern="^(from|to|both)$", description="Link direction for searches")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Result offset for pagination")

class UnifiedSearchResponse(BaseModel):
    """Search response model for unified facade"""
    query: str = Field(..., description="Original search query")
    results: List[UnifiedNode] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results available")
    sources_queried: List[str] = Field(..., description="Sources that were queried")
    source_errors: Dict[str, str] = Field(default_factory=dict, description="Errors encountered per source")
    offset: int = Field(..., description="Result offset used")
    limit: int = Field(..., description="Result limit used")
    search_time_ms: float = Field(..., description="Total search time in milliseconds")

class UnifiedLinksRequest(BaseModel):
    """Request model for retrieving links for a node"""
    node_id: str = Field(..., description="Node ID to get links for")
    direction: str = Field(default="both", pattern="^(from|to|both)$", description="Link direction")
    sources: Optional[List[ReferenceSource]] = Field(None, description="Specific sources to search")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of links")

class UnifiedLinksResponse(BaseModel):
    """Response model for node links"""
    node_id: str = Field(..., description="Node ID that was queried")
    links: List[UnifiedLink] = Field(..., description="Links found for the node")
    total_links: int = Field(..., description="Total number of links available")
    sources_queried: List[str] = Field(..., description="Sources that were queried")
    source_errors: Dict[str, str] = Field(default_factory=dict, description="Errors encountered per source")