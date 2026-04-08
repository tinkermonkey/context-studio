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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ==================== Request Schemas ====================

class CycleCheckRequest(BaseModel):
    """Request to check if adding an edge would create a cycle."""

    source_id: str = Field(..., description="ID of the proposed edge source")
    target_id: str = Field(..., description="ID of the proposed edge target")


class SPARQLRequest(BaseModel):
    """Request to execute a SPARQL query."""

    query: str = Field(..., max_length=10000, description="SPARQL SELECT query string (max 10000 characters)")


# ==================== Response Schemas ====================

class KnowledgeGraphResponse(BaseModel):
    """Response containing knowledge graph metadata."""

    model_config = ConfigDict(from_attributes=True)

    node_count: int = Field(..., description="Number of nodes in the graph")
    edge_count: int = Field(..., description="Number of edges in the graph")
    is_directed: bool = Field(..., description="Whether the graph is directed")
    timestamp: datetime = Field(..., description="Timestamp when the graph was last built")


class GraphMetricsResponse(BaseModel):
    """Response containing computed graph metrics."""

    model_config = ConfigDict(from_attributes=True)

    density: float = Field(..., description="Edge density of the graph")
    average_degree: float = Field(..., description="Average degree of nodes")
    connected_components: int = Field(..., description="Number of connected components")
    degree_distribution: dict[str, int] = Field(..., description="Distribution of node degrees")
    centrality: dict[str, float] = Field(..., description="Centrality scores for all nodes")
    communities: list[list[str]] = Field(..., description="Detected communities as lists of node IDs")
    algorithm: str = Field(..., description="Name of the centrality algorithm used")
    computed_at: datetime = Field(..., description="Timestamp when metrics were computed")


class PathResultResponse(BaseModel):
    """Response containing a single path between two nodes."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    source_id: str = Field(..., description="ID of the starting node")
    target_id: str = Field(..., description="ID of the ending node")
    nodes: list[str] = Field(..., alias="path", serialization_alias="nodes", description="Ordered list of node IDs from source to target")
    distance: int = Field(..., alias="length", serialization_alias="distance", description="Number of edges in the path")
    relationships: list[str] = Field(..., description="Relationship types traversed along the path")


class CentralityResponse(BaseModel):
    """Response containing centrality scores."""

    model_config = ConfigDict(from_attributes=True)

    algorithm: str = Field(..., description="Name of the centrality algorithm")
    scores: dict[str, float] = Field(..., description="Centrality scores mapped by node ID")


class CommunitiesResponse(BaseModel):
    """Response containing community detection results."""

    model_config = ConfigDict(from_attributes=True)

    algorithm: str = Field(..., description="Name of the community detection algorithm")
    communities: list[list[str]] = Field(..., description="Communities as sorted lists of node IDs")


class NeighborsResponse(BaseModel):
    """Response containing neighbor nodes."""

    model_config = ConfigDict(from_attributes=True)

    node_id: str = Field(..., description="ID of the queried node")
    incoming: list[str] = Field(..., description="List of nodes with edges pointing to this node")
    outgoing: list[str] = Field(..., description="List of nodes this node has edges pointing to")


class CycleCheckResponse(BaseModel):
    """Response from cycle detection check."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str = Field(..., description="ID of the proposed edge source")
    target_id: str = Field(..., description="ID of the proposed edge target")
    would_create_cycle: bool = Field(..., description="Whether adding this edge would create a cycle")


class SPARQLResponse(BaseModel):
    """Response from SPARQL query execution."""

    model_config = ConfigDict(from_attributes=True)

    results: list[dict] = Field(..., description="Query result bindings")
    triple_count: int = Field(..., description="Total number of triples in the graph")


class TripleResponse(BaseModel):
    """Response containing a single RDF triple."""

    subject: str = Field(..., description="RDF subject")
    predicate: str = Field(..., description="RDF predicate")
    object: str = Field(..., description="RDF object")


class TriplesResponse(BaseModel):
    """Response containing RDF triples."""

    model_config = ConfigDict(from_attributes=True)

    triples: list[TripleResponse] = Field(..., description="List of RDF triples")
    count: int = Field(..., description="Number of triples returned")


class TripleCountResponse(BaseModel):
    """Response containing RDF triple count."""

    model_config = ConfigDict(from_attributes=True)

    count: int = Field(..., description="Number of RDF triples in the graph")


class DegreeDistributionResponse(BaseModel):
    """Response containing degree distribution for all nodes."""

    model_config = ConfigDict(from_attributes=True)

    in_degree: dict[str, int] = Field(..., description="Mapping of node IDs to their in-degrees")
    out_degree: dict[str, int] = Field(..., description="Mapping of node IDs to their out-degrees")


class SubgraphDataResponse(BaseModel):
    """Response containing subgraph nodes and edges."""

    model_config = ConfigDict(from_attributes=True)

    nodes: list[str] = Field(..., description="IDs of all nodes in the subgraph")
    edges: list[tuple[str, str]] = Field(..., description="Edges connecting nodes in the subgraph as (source, target) tuples")


class SubgraphResultResponse(BaseModel):
    """Response containing depth-based subgraph extraction result."""

    model_config = ConfigDict(from_attributes=True)

    node_id: str = Field(..., description="ID of the center node")
    subgraph: SubgraphDataResponse = Field(..., description="The extracted subgraph containing nodes and edges")
    depth: int = Field(..., description="Maximum traversal depth from center node")
