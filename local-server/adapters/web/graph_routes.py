"""
FastAPI routes for the Graph Analysis bounded context.

This module implements all HTTP endpoints for graph analysis operations:
- GET /metrics - Graph-level structural metrics
- GET /paths/shortest - Shortest path between two nodes
- GET /paths/all - All paths between two nodes
- GET /centrality - Node centrality scores
- GET /communities - Community detection results
- GET /nodes/{node_id}/neighbors - Neighbor traversal
- GET /nodes/{node_id}/subgraph - Subgraph extraction
- POST /cycle-check - Cycle detection for proposed edge
- POST /sparql - SPARQL query execution
- GET /rdf/triples - RDF triple access
- GET /rdf/count - RDF triple count

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with appropriate parameters
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from domain.graph.services import GraphAnalysisService
from domain.graph.exceptions import (
    GraphError,
    NodeNotFoundError,
    InvalidAlgorithmError,
    SPARQLValidationError,
)

from adapters.web.dependencies import get_graph_service
from adapters.web.schemas.graph import (
    KnowledgeGraphResponse,
    GraphMetricsResponse,
    PathResultResponse,
    CentralityResponse,
    CommunitiesResponse,
    NeighborsResponse,
    CycleCheckRequest,
    CycleCheckResponse,
    SPARQLRequest,
    SPARQLResponse,
    TriplesResponse,
    TripleCountResponse,
    TripleResponse,
)

router = APIRouter(prefix="/graph", tags=["graph"])


# ==================== Error Handler Utilities ====================

def _handle_graph_error(exc: GraphError) -> NoReturn:
    """
    Map domain exceptions to HTTP status codes and raise HTTPException.

    Args:
        exc: The domain exception from the graph service

    Raises:
        HTTPException: With appropriate status code and detail message
    """
    if isinstance(exc, NodeNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    elif isinstance(exc, (InvalidAlgorithmError, SPARQLValidationError)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ==================== Graph Metrics Endpoint ====================

@router.get("/metrics", response_model=GraphMetricsResponse)
async def get_metrics(
    algorithm: str = Query("betweenness", description="Centrality algorithm to use"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> GraphMetricsResponse:
    """
    Get structural metrics for the entire graph.

    Args:
        algorithm: Centrality algorithm to use (betweenness, pagerank, closeness, degree)
        service: GraphAnalysisService from dependency injection

    Returns:
        GraphMetricsResponse containing density, degree stats, and community info

    Raises:
        HTTPException: 400 if algorithm is invalid, 422 if graph error occurs
    """
    try:
        metrics = service.get_metrics(algorithm=algorithm)
        # Convert communities (list of sets) to list of sorted lists for JSON serialization
        communities_as_lists = [sorted(list(community)) for community in metrics.communities]
        return GraphMetricsResponse(
            density=metrics.density,
            average_degree=metrics.average_degree,
            connected_components=metrics.connected_components,
            degree_distribution={},  # Would be populated by graph engine in future enhancement
            centrality=metrics.centrality,
            communities=communities_as_lists,
            algorithm=metrics.algorithm,
            computed_at=metrics.computed_at,
        )
    except (InvalidAlgorithmError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== Path Finding Endpoints ====================

@router.get("/paths/shortest", response_model=Optional[PathResultResponse])
async def get_shortest_path(
    source_id: str = Query(..., description="ID of the starting node"),
    target_id: str = Query(..., description="ID of the ending node"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> Optional[PathResultResponse]:
    """
    Find the shortest path between two nodes.

    Args:
        source_id: ID of the starting node
        target_id: ID of the ending node
        service: GraphAnalysisService from dependency injection

    Returns:
        PathResultResponse if a path exists, None otherwise

    Raises:
        HTTPException: 404 if either node is not found, 422 if graph error occurs
    """
    try:
        path_result = service.find_shortest_path(source_id, target_id)
        if path_result is None:
            return None
        return PathResultResponse.model_validate(path_result)
    except (NodeNotFoundError, GraphError) as exc:
        _handle_graph_error(exc)


@router.get("/paths/all", response_model=list[PathResultResponse])
async def get_all_paths(
    source_id: str = Query(..., description="ID of the starting node"),
    target_id: str = Query(..., description="ID of the ending node"),
    max_depth: int = Query(5, description="Maximum path length to explore", ge=1),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> list[PathResultResponse]:
    """
    Find all simple paths between two nodes up to a maximum depth.

    Args:
        source_id: ID of the starting node
        target_id: ID of the ending node
        max_depth: Maximum path length to explore (minimum 1)
        service: GraphAnalysisService from dependency injection

    Returns:
        List of PathResultResponse objects, one for each found path

    Raises:
        HTTPException: 404 if either node is not found, 422 if graph error occurs
    """
    try:
        path_results = service.find_all_paths(source_id, target_id, max_depth)
        return [PathResultResponse.model_validate(p) for p in path_results]
    except (NodeNotFoundError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== Centrality Endpoint ====================

@router.get("/centrality", response_model=CentralityResponse)
async def get_centrality(
    algorithm: str = Query("betweenness", description="Centrality algorithm to use"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> CentralityResponse:
    """
    Compute centrality scores for all nodes using the specified algorithm.

    Args:
        algorithm: Name of the centrality algorithm (betweenness, pagerank, closeness, degree)
        service: GraphAnalysisService from dependency injection

    Returns:
        CentralityResponse mapping node IDs to centrality scores

    Raises:
        HTTPException: 400 if algorithm is not recognized, 422 if graph error occurs
    """
    try:
        scores = service.get_centrality(algorithm)
        return CentralityResponse(algorithm=algorithm, scores=scores)
    except (InvalidAlgorithmError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== Community Detection Endpoint ====================

@router.get("/communities", response_model=CommunitiesResponse)
async def get_communities(
    algorithm: str = Query("louvain", description="Community detection algorithm to use"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> CommunitiesResponse:
    """
    Partition the graph into communities using the specified algorithm.

    Args:
        algorithm: Name of the community detection algorithm (louvain, label_propagation)
        service: GraphAnalysisService from dependency injection

    Returns:
        CommunitiesResponse containing detected communities as lists of node IDs

    Raises:
        HTTPException: 400 if algorithm is not recognized, 422 if graph error occurs
    """
    try:
        communities = service.get_communities(algorithm)
        # Convert communities (list of sets) to list of sorted lists for JSON serialization
        communities_as_lists = [sorted(list(community)) for community in communities]
        return CommunitiesResponse(algorithm=algorithm, communities=communities_as_lists)
    except (InvalidAlgorithmError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== Neighbor Traversal Endpoint ====================

@router.get("/nodes/{node_id}/neighbors", response_model=NeighborsResponse)
async def get_neighbors(
    node_id: str,
    direction: str = Query("both", description="Direction: 'in', 'out', or 'both'"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> NeighborsResponse:
    """
    Get all neighbors of a node with optional directional filtering.

    Args:
        node_id: ID of the queried node
        direction: Direction of traversal (in, out, or both)
        service: GraphAnalysisService from dependency injection

    Returns:
        NeighborsResponse containing list of neighboring node IDs

    Raises:
        HTTPException: 404 if node is not found, 422 if graph error occurs
    """
    try:
        neighbors = service.get_neighbors(node_id, direction)
        return NeighborsResponse(
            node_id=node_id,
            direction=direction,
            neighbors=sorted(list(neighbors)),
        )
    except (NodeNotFoundError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== Subgraph Extraction Endpoint ====================

@router.get("/nodes/{node_id}/subgraph", response_model=KnowledgeGraphResponse)
async def get_subgraph(
    node_id: str,
    depth: int = Query(1, description="Maximum distance from center node", ge=1),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> KnowledgeGraphResponse:
    """
    Extract a subgraph around a node up to a specified depth.

    Args:
        node_id: ID of the center node
        depth: Maximum distance from the center node (minimum 1)
        service: GraphAnalysisService from dependency injection

    Returns:
        KnowledgeGraphResponse describing the extracted subgraph

    Raises:
        HTTPException: 404 if node is not found, 422 if graph error occurs
    """
    try:
        subgraph = service.extract_subgraph(node_id, depth)
        return KnowledgeGraphResponse.model_validate(subgraph)
    except (NodeNotFoundError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== Cycle Check Endpoint ====================

@router.post("/cycle-check", response_model=CycleCheckResponse)
async def check_cycle(
    request: CycleCheckRequest,
    service: GraphAnalysisService = Depends(get_graph_service),
) -> CycleCheckResponse:
    """
    Check if adding an edge from source to target would create a cycle.

    Args:
        request: CycleCheckRequest with source_id and target_id
        service: GraphAnalysisService from dependency injection

    Returns:
        CycleCheckResponse indicating whether a cycle would be created

    Raises:
        HTTPException: 404 if either node is not found, 422 if graph error occurs
    """
    try:
        would_create_cycle = service.check_cycle(request.source_id, request.target_id)
        return CycleCheckResponse(
            source_id=request.source_id,
            target_id=request.target_id,
            would_create_cycle=would_create_cycle,
        )
    except (NodeNotFoundError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== SPARQL Query Endpoint ====================

@router.post("/sparql", response_model=SPARQLResponse)
async def execute_sparql(
    request: SPARQLRequest,
    service: GraphAnalysisService = Depends(get_graph_service),
) -> SPARQLResponse:
    """
    Execute a SPARQL SELECT query against the RDF graph.

    Args:
        request: SPARQLRequest containing the query string
        service: GraphAnalysisService from dependency injection

    Returns:
        SPARQLResponse containing query results and triple count

    Raises:
        HTTPException: 400 if query is invalid, 422 if graph error occurs
    """
    try:
        results = service.execute_sparql(request.query)
        triple_count = service.get_triple_count()
        return SPARQLResponse(results=results, triple_count=triple_count)
    except (SPARQLValidationError, GraphError) as exc:
        _handle_graph_error(exc)


# ==================== RDF Triple Endpoints ====================

@router.get("/rdf/triples", response_model=TriplesResponse)
async def get_rdf_triples(
    subject: Optional[str] = Query(None, description="Optional RDF subject to filter"),
    predicate: Optional[str] = Query(None, description="Optional RDF predicate to filter"),
    object_param: Optional[str] = Query(None, alias="object", description="Optional RDF object to filter"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> TriplesResponse:
    """
    Retrieve RDF triples matching optional subject/predicate/object patterns.

    Args:
        subject: Optional subject to match
        predicate: Optional predicate to match
        object_param: Optional object to match
        service: GraphAnalysisService from dependency injection

    Returns:
        TriplesResponse containing matching triples and count

    Raises:
        HTTPException: 422 if graph error occurs
    """
    try:
        triples = service.get_triples(subject, predicate, object_param)
        triple_responses = [
            TripleResponse(subject=s, predicate=p, object=o) for s, p, o in triples
        ]
        return TriplesResponse(triples=triple_responses, count=len(triple_responses))
    except GraphError as exc:
        _handle_graph_error(exc)


@router.get("/rdf/count", response_model=TripleCountResponse)
async def get_rdf_triple_count(
    service: GraphAnalysisService = Depends(get_graph_service),
) -> TripleCountResponse:
    """
    Get the number of RDF triples in the graph.

    Args:
        service: GraphAnalysisService from dependency injection

    Returns:
        TripleCountResponse containing the triple count

    Raises:
        HTTPException: 422 if graph error occurs
    """
    try:
        count = service.get_triple_count()
        return TripleCountResponse(count=count)
    except GraphError as exc:
        _handle_graph_error(exc)
