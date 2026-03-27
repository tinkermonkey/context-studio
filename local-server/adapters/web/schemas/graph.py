"""
Pydantic schemas for the Graph Analysis bounded context.

Request schemas (for POST):
- CycleCheckRequest
- SPARQLRequest

Response schemas (for GET/returns):
- KnowledgeGraphResponse
- GraphMetricsResponse
- PathResultResponse
- CentralityResponse
- CommunitiesResponse
- NeighborsResponse
- CycleCheckResponse
- SPARQLResponse
- TripleResponse
- TriplesResponse
- TripleCountResponse

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== Request Schemas ====================

class CycleCheckRequest(BaseModel):
    """Request to check if adding an edge would create a cycle."""

    source_id: str = Field(..., description="ID of the proposed edge source")
    target_id: str = Field(..., description="ID of the proposed edge target")


class SPARQLRequest(BaseModel):
    """Request to execute a SPARQL query."""

    query: str = Field(..., description="SPARQL SELECT query string")


# ==================== Response Schemas ====================

class KnowledgeGraphResponse(BaseModel):
    """Response containing knowledge graph metadata."""

    node_count: int = Field(..., description="Number of nodes in the graph")
    edge_count: int = Field(..., description="Number of edges in the graph")
    is_directed: bool = Field(..., description="Whether the graph is directed")
    last_built: datetime = Field(..., description="Timestamp when the graph was last built")

    class Config:
        from_attributes = True


class GraphMetricsResponse(BaseModel):
    """Response containing computed graph metrics."""

    density: float = Field(..., description="Edge density of the graph")
    average_degree: float = Field(..., description="Average degree of nodes")
    connected_components: int = Field(..., description="Number of connected components")
    degree_distribution: dict[str, int] = Field(..., description="Distribution of node degrees")

    class Config:
        from_attributes = True


class PathResultResponse(BaseModel):
    """Response containing a single path between two nodes."""

    source_id: str = Field(..., description="ID of the starting node")
    target_id: str = Field(..., description="ID of the ending node")
    path: list[str] = Field(..., description="Ordered list of node IDs from source to target")
    length: int = Field(..., description="Number of edges in the path")
    relationships: list[str] = Field(..., description="Relationship types traversed along the path")

    class Config:
        from_attributes = True


class CentralityResponse(BaseModel):
    """Response containing centrality scores."""

    algorithm: str = Field(..., description="Name of the centrality algorithm")
    scores: dict[str, float] = Field(..., description="Centrality scores mapped by node ID")

    class Config:
        from_attributes = True


class CommunitiesResponse(BaseModel):
    """Response containing community detection results."""

    algorithm: str = Field(..., description="Name of the community detection algorithm")
    communities: list[list[str]] = Field(..., description="Communities as sorted lists of node IDs")

    class Config:
        from_attributes = True


class NeighborsResponse(BaseModel):
    """Response containing neighbor nodes."""

    node_id: str = Field(..., description="ID of the queried node")
    direction: str = Field(..., description="Direction of traversal: 'in', 'out', or 'both'")
    neighbors: list[str] = Field(..., description="List of neighboring node IDs")

    class Config:
        from_attributes = True


class CycleCheckResponse(BaseModel):
    """Response from cycle detection check."""

    source_id: str = Field(..., description="ID of the proposed edge source")
    target_id: str = Field(..., description="ID of the proposed edge target")
    would_create_cycle: bool = Field(..., description="Whether adding this edge would create a cycle")

    class Config:
        from_attributes = True


class SPARQLResponse(BaseModel):
    """Response from SPARQL query execution."""

    results: list[dict] = Field(..., description="Query result bindings")
    triple_count: int = Field(..., description="Total number of triples in the graph")

    class Config:
        from_attributes = True


class TripleResponse(BaseModel):
    """Response containing a single RDF triple."""

    subject: str = Field(..., description="RDF subject")
    predicate: str = Field(..., description="RDF predicate")
    object: str = Field(..., description="RDF object")


class TriplesResponse(BaseModel):
    """Response containing RDF triples."""

    triples: list[TripleResponse] = Field(..., description="List of RDF triples")
    count: int = Field(..., description="Number of triples returned")

    class Config:
        from_attributes = True


class TripleCountResponse(BaseModel):
    """Response containing RDF triple count."""

    count: int = Field(..., description="Number of RDF triples in the graph")

    class Config:
        from_attributes = True
