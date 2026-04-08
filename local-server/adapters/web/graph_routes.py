"""
FastAPI routes for the Graph Analysis bounded context.

This module implements all HTTP endpoints for graph analysis operations:
- POST /build - Explicitly build the graph from current ontology
- GET /metrics - Graph-level structural metrics
- GET /degree-distribution - Node degree distribution
- GET /paths/shortest - Shortest path between two nodes
- GET /paths/all - All paths between two nodes
- GET /centrality - Node centrality scores
- GET /communities - Community detection results
- GET /nodes/{node_id}/neighbors - Neighbor traversal
- GET /subgraph - Subgraph extraction (multi-node query)
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

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from domain.graph.services import GraphAnalysisService
from domain.graph.exceptions import (
    GraphError,
    NodeNotFoundError,
    InvalidAlgorithmError,
    SPARQLValidationError,
    CommunityDetectionError,
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
    DegreeDistributionResponse,
    SubgraphDataResponse,
    SubgraphResultResponse,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


# ==================== Error Handler Utilities ====================

def _handle_graph_error(exc: GraphError) -> tuple[int, str]:
    """
    Map domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception from the graph service

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, NodeNotFoundError):
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, (InvalidAlgorithmError, SPARQLValidationError, CommunityDetectionError)):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        return (status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


# ==================== Graph Construction Endpoint ====================

@router.post("/build", response_model=KnowledgeGraphResponse)
async def build_graph(
    service: GraphAnalysisService = Depends(get_graph_service),
) -> KnowledgeGraphResponse:
    """
    Explicitly build the in-memory graph from current ontology data.

    This endpoint allows clients to trigger graph construction on demand. Graph building
    normally happens lazily on first query, but this endpoint enables explicit control
    over graph refresh timing and validates that the graph can be built without errors.

    Args:
        service: GraphAnalysisService from dependency injection

    Returns:
        KnowledgeGraphResponse containing node count, edge count, and build timestamp

    Raises:
        HTTPException: 422 if graph construction fails
    """
    try:
        graph = service.build_graph()
        graph_dict = asdict(graph)
        graph_dict['timestamp'] = graph_dict.pop('last_built', datetime.now(timezone.utc))
        return KnowledgeGraphResponse.model_validate(graph_dict)
    except GraphError as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        GraphMetricsResponse containing density, average degree, connected components, degree distribution, centrality scores, communities, algorithm, and computed timestamp

    Raises:
        HTTPException: 400 if algorithm is invalid or community detection fails, 422 if graph error occurs
    """
    try:
        metrics = service.get_metrics(algorithm=algorithm)
        # Convert communities from sets to sorted lists for JSON serialization
        metrics_dict = asdict(metrics)
        metrics_dict["communities"] = [sorted(list(community)) for community in metrics.communities]
        return GraphMetricsResponse.model_validate(metrics_dict)
    except (InvalidAlgorithmError, CommunityDetectionError, GraphError) as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Degree Distribution Endpoint ====================

@router.get("/degree-distribution", response_model=DegreeDistributionResponse)
async def get_degree_distribution(
    service: GraphAnalysisService = Depends(get_graph_service),
) -> DegreeDistributionResponse:
    """
    Get the degree distribution across all nodes in the graph.

    The degree of a node is the number of edges connected to it. This endpoint
    provides the in-degree and out-degree counts for each node, useful for network analysis
    and topology studies.

    Args:
        service: GraphAnalysisService from dependency injection

    Returns:
        DegreeDistributionResponse containing node ID to degree mappings

    Raises:
        HTTPException: 422 if graph error occurs
    """
    try:
        in_degree, out_degree = service.get_degree_distributions()
        return DegreeDistributionResponse(
            in_degree=in_degree,
            out_degree=out_degree,
        )
    except GraphError as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Path Finding Endpoints ====================

@router.get("/paths/shortest", response_model=PathResultResponse)
async def get_shortest_path(
    source_id: str = Query(..., description="ID of the starting node"),
    target_id: str = Query(..., description="ID of the ending node"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> PathResultResponse:
    """
    Find the shortest path between two nodes.

    Args:
        source_id: ID of the starting node
        target_id: ID of the ending node
        service: GraphAnalysisService from dependency injection

    Returns:
        PathResultResponse if a path exists

    Raises:
        HTTPException: 404 if either node is not found or no path exists, 422 if graph error occurs
    """
    try:
        path_result = service.find_shortest_path(source_id, target_id)
        if path_result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No path exists between '{source_id}' and '{target_id}'"
            )
        return PathResultResponse.model_validate(path_result)
    except (NodeNotFoundError, GraphError) as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/paths/all", response_model=list[PathResultResponse])
async def get_all_paths(
    source_id: str = Query(..., description="ID of the starting node"),
    target_id: str = Query(..., description="ID of the ending node"),
    max_depth: int = Query(5, description="Maximum path length to explore", ge=1, le=20),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> list[PathResultResponse]:
    """
    Find all simple paths between two nodes up to a maximum depth.

    Args:
        source_id: ID of the starting node
        target_id: ID of the ending node
        max_depth: Maximum path length to explore (minimum 1, maximum 20)
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
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        HTTPException: 400 if algorithm is not recognized or community detection fails, 422 if graph error occurs
    """
    try:
        communities = service.get_communities(algorithm)
        # Convert communities (list of sets) to list of sorted lists for JSON serialization
        communities_as_lists = [sorted(list(community)) for community in communities]
        return CommunitiesResponse(algorithm=algorithm, communities=communities_as_lists)
    except (InvalidAlgorithmError, CommunityDetectionError, GraphError) as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Neighbor Traversal Endpoint ====================

@router.get("/nodes/{node_id}/neighbors", response_model=NeighborsResponse)
async def get_neighbors(
    node_id: str,
    direction: Literal["in", "out", "both"] = Query("both", description="Direction: 'in', 'out', or 'both'"),
    depth: int = Query(1, description="Maximum traversal depth from center node", ge=1, le=10),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> NeighborsResponse:
    """
    Get all neighbors of a node up to a specified depth with optional directional filtering.

    Args:
        node_id: ID of the queried node
        direction: Direction of traversal (in, out, or both)
        depth: Maximum distance from center node (minimum 1, maximum 10, default 1)
        service: GraphAnalysisService from dependency injection

    Returns:
        NeighborsResponse containing lists of incoming and outgoing neighbors

    Raises:
        HTTPException: 404 if node is not found, 400 if direction is invalid, 422 if graph error occurs
    """
    try:
        # Get all neighbors of the node using the public service method
        # The service validates the node exists and raises NodeNotFoundError if not
        neighbors = service.get_neighbors(node_id, direction=direction, depth=depth)

        # Build separate incoming and outgoing lists for the response
        # For the GraphAnalysisService, we need to query neighbors for each direction separately
        # since the service method returns a combined set based on the direction parameter
        incoming = []
        outgoing = []

        if direction in ("in", "both"):
            incoming = sorted(list(service.get_neighbors(node_id, direction="in", depth=depth)))
        if direction in ("out", "both"):
            outgoing = sorted(list(service.get_neighbors(node_id, direction="out", depth=depth)))

        return NeighborsResponse(
            node_id=node_id,
            direction=direction,
            incoming=incoming,
            outgoing=outgoing,
        )
    except (NodeNotFoundError, InvalidAlgorithmError, GraphError) as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Subgraph Extraction Endpoints ====================

@router.get("/subgraph", response_model=SubgraphDataResponse)
async def get_subgraph(
    nodes: str = Query(..., description="Comma-separated list of node IDs to extract subgraph for"),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> SubgraphDataResponse:
    """
    Extract a subgraph containing the specified nodes and all edges between them.

    This endpoint extracts a subgraph from a pre-computed list of node IDs.
    For depth-based neighborhood extraction, use GET /nodes/{node_id}/subgraph instead.

    Args:
        nodes: Comma-separated list of node IDs (e.g., "id1,id2,id3")
        service: GraphAnalysisService from dependency injection

    Returns:
        SubgraphDataResponse containing the nodes and edges in the subgraph

    Raises:
        HTTPException: 404 if any node is not found, 400 if nodes parameter is invalid, 422 if graph error occurs
    """
    try:
        # Parse and validate the comma-separated node IDs
        node_list = [node_id.strip() for node_id in nodes.split(",") if node_id.strip()]

        if not node_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="nodes parameter must contain at least one node ID"
            )

        # Use the public service method to extract subgraph with edges
        subgraph = service.extract_subgraph_with_edges(node_list)

        return SubgraphDataResponse(
            nodes=subgraph.node_ids,
            edges=subgraph.edge_ids,
            node_count=subgraph.node_count,
            edge_count=subgraph.edge_count,
        )
    except (NodeNotFoundError, GraphError) as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/nodes/{node_id}/subgraph", response_model=SubgraphResultResponse)
async def get_subgraph_by_depth(
    node_id: str,
    depth: int = Query(1, description="Maximum traversal depth from center node", ge=1, le=10),
    service: GraphAnalysisService = Depends(get_graph_service),
) -> SubgraphResultResponse:
    """
    Extract a subgraph containing a center node and all nodes within a specified depth (FR-9).

    This implements depth-based subgraph extraction where depth 1 returns the center node
    and its immediate neighbors, depth 2 returns two hops away, etc.

    Args:
        node_id: ID of the center node
        depth: Maximum distance from center node (minimum 1, maximum 10, default 1)
        service: GraphAnalysisService from dependency injection

    Returns:
        SubgraphResultResponse containing center node ID, subgraph data, and depth

    Raises:
        HTTPException: 404 if center node is not found, 400 if depth is invalid, 422 if graph error occurs
    """
    try:
        subgraph_result = service.extract_subgraph_by_depth(node_id, depth)

        # Use the domain entity's actual properties (node_ids and edge_ids)
        # The SubgraphResult dataclass always has these attributes
        return SubgraphResultResponse(
            node_id=node_id,
            subgraph=SubgraphDataResponse(
                nodes=subgraph_result.node_ids,
                edges=subgraph_result.edge_ids,
                node_count=subgraph_result.node_count,
                edge_count=subgraph_result.edge_count,
            ),
            depth=depth
        )
    except (NodeNotFoundError, GraphError) as exc:
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


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
        status_code, message = _handle_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
